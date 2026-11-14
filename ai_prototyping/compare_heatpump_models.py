#!/usr/bin/env python3
"""Compare Random Forest and 1D CNN on 10-minute heat-pump temperature windows.

Expected CSV columns: second, outside_temp_c, outgoing_temp_c.
Expected filenames: healthy_0001.csv, unhealthy_0001.csv, etc.

Install: pip install numpy pandas scikit-learn torch
Run: python compare_heatpump_models.py --data-dir synthetic_data
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, accuracy_score, precision_recall_fscore_support


def get_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir', type=Path, default=Path('synthetic_heatpump/data'))
    p.add_argument('--window', type=int, default=600)
    p.add_argument('--stride', type=int, default=600)
    p.add_argument('--val-fraction', type=float, default=0.2)
    p.add_argument('--epochs', type=int, default=15)
    p.add_argument('--batch-size', type=int, default=64)
    p.add_argument('--seed', type=int, default=42)
    return p.parse_args()


def load_windows(data_dir, window, stride):
    windows, labels, file_ids = [], [], []
    files = sorted(data_dir.glob('healthy_*.csv')) + sorted(data_dir.glob('unhealthy_*.csv'))
    if not files:
        raise ValueError(f'No healthy_*.csv or unhealthy_*.csv files in {data_dir}')

    for path in files:
        label = 0 if path.name.startswith('healthy_') else 1
        df = pd.read_csv(path)
        required = {'outside_temp_c', 'outgoing_temp_c'}
        if not required.issubset(df.columns):
            raise ValueError(f'{path}: missing {required - set(df.columns)}')
        arr = df[['outside_temp_c', 'outgoing_temp_c']].to_numpy(dtype=np.float32)
        if not np.isfinite(arr).all():
            raise ValueError(f'{path}: nonfinite/missing temperature values')
        if 'second' in df.columns:
            seconds = df['second'].to_numpy()
            if len(seconds) > 1 and not np.allclose(np.diff(seconds), 1):
                raise ValueError(f'{path}: expected consecutive 1-second sampling')
        for start in range(0, len(arr) - window + 1, stride):
            windows.append(arr[start:start + window])
            labels.append(label)
            file_ids.append(path.name)

    if not windows:
        raise ValueError(f'All files shorter than window={window}')
    return np.stack(windows), np.asarray(labels), np.asarray(file_ids)


def rf_features(windows):
    """Time-series features; computed separately for each window."""
    result = []
    for w in windows:
        outside, outgoing = w[:, 0], w[:, 1]
        delta = outside - outgoing
        row = []
        for series in (outside, outgoing, delta):
            row.extend([
                float(np.mean(series)), float(np.std(series)),
                float(np.min(series)), float(np.max(series)),
                float(np.percentile(series, 10)), float(np.percentile(series, 90)),
                float(series[-1] - series[0]),
                float(np.std(np.diff(series))),
            ])
        row.extend([
            float(np.mean(delta < 0)),
            float(np.mean(outgoing > outside)),
            float(np.mean(np.abs(np.diff(outgoing)) > 0.1)),
        ])
        result.append(row)
    return np.asarray(result, dtype=np.float32)


def report(name, split, truth, pred):
    cm = confusion_matrix(truth, pred, labels=[0, 1])
    print(f'\n{name} — {split} ({len(truth)} windows)')
    print(f'Overall accuracy: {accuracy_score(truth, pred):.1%}')
    print('Actual class | Correct | Incorrect | Recall')
    for i, label in enumerate(('Healthy', 'Unhealthy')):
        correct, incorrect = cm[i, i], cm[i, 1 - i]
        recall = correct / (correct + incorrect) if correct + incorrect else float('nan')
        print(f'{label:12s} | {correct:7d} | {incorrect:9d} | {recall:6.1%}')
    print('Confusion matrix (rows=actual, columns=predicted):')
    print('                   Healthy  Unhealthy')
    print(f'  Actual Healthy   {cm[0, 0]:7d}  {cm[0, 1]:9d}')
    print(f'  Actual Unhealthy {cm[1, 0]:7d}  {cm[1, 1]:9d}')
    precision, recall, f1, _ = precision_recall_fscore_support(
        truth, pred, labels=[1], zero_division=0
    )
    print(f'Unhealthy precision={precision[0]:.3f} recall={recall[0]:.3f} F1={f1[0]:.3f}')


def train_cnn(X_train, y_train, X_val, args):
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise SystemExit('CNN needs PyTorch: pip install torch') from exc

    torch.manual_seed(args.seed)
    torch.set_num_threads(min(torch.get_num_threads(), 4))

    # Standardize from training windows ONLY, avoiding validation leakage.
    mean = X_train.mean(axis=(0, 1), keepdims=True)
    std = X_train.std(axis=(0, 1), keepdims=True).clip(min=1e-6)
    Xtr = np.ascontiguousarray(((X_train - mean) / std).transpose(0, 2, 1))
    Xva = np.ascontiguousarray(((X_val - mean) / std).transpose(0, 2, 1))

    # Shape for Conv1d: (batch, 2 temperatures, 600 time samples).
    train_ds = TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(y_train.astype(np.int64)))
    loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)

    class TemperatureCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv1d(2, 16, kernel_size=9, padding=4), nn.ReLU(),
                nn.MaxPool1d(4),
                nn.Conv1d(16, 32, kernel_size=7, padding=3), nn.ReLU(),
                nn.MaxPool1d(4),
                nn.Conv1d(32, 64, kernel_size=5, padding=2), nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.head = nn.Linear(64, 2)

        def forward(self, x):
            return self.head(self.features(x).squeeze(-1))

    model = TemperatureCNN()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.CrossEntropyLoss()
    print('\nTraining CNN...')
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(yb)
        print(f'Epoch {epoch + 1:02d}/{args.epochs}: train loss={total_loss / len(train_ds):.4f}')

    def predict(X):
        model.eval()
        outputs = []
        with torch.no_grad():
            for start in range(0, len(X), args.batch_size):
                scores = model(torch.from_numpy(X[start:start + args.batch_size]))
                outputs.append(scores.argmax(dim=1).numpy())
        return np.concatenate(outputs)

    return predict(Xtr), predict(Xva)


def main():
    args = get_args()
    if args.window < 2 or args.stride < 1:
        raise ValueError('window must be >= 2 and stride must be >= 1')
    X, y, file_ids = load_windows(args.data_dir, args.window, args.stride)

    # Split at FILE level, not window level, to prevent trivial overlap leakage.
    unique_files = np.unique(file_ids)
    file_labels = np.array([y[np.flatnonzero(file_ids == f)[0]] for f in unique_files])
    train_files, val_files = train_test_split(
        unique_files, test_size=args.val_fraction, random_state=args.seed,
        stratify=file_labels
    )
    is_train = np.isin(file_ids, train_files)
    X_train, X_val = X[is_train], X[~is_train]
    y_train, y_val = y[is_train], y[~is_train]
    print(f'Files: train={len(train_files)}, validation={len(val_files)}')
    print(f'Windows: train={len(y_train)}, validation={len(y_val)}; window={args.window}s stride={args.stride}s')
    print('Note: labels are inherited from filenames for ALL windows in each file.')

    forest = RandomForestClassifier(
        n_estimators=200, min_samples_leaf=3, class_weight='balanced',
        random_state=args.seed, n_jobs=-1
    )
    rf_train = rf_features(X_train)
    rf_val = rf_features(X_val)
    forest.fit(rf_train, y_train)
    report('Random Forest', 'TRAIN', y_train, forest.predict(rf_train))
    report('Random Forest', 'VALIDATION', y_val, forest.predict(rf_val))

    cnn_train, cnn_val = train_cnn(X_train, y_train, X_val, args)
    report('1D CNN', 'TRAIN', y_train, cnn_train)
    report('1D CNN', 'VALIDATION', y_val, cnn_val)
    print('\nCAUTION: performance on simulated data does not establish real-world fault detection accuracy.')


if __name__ == '__main__':
    main()
