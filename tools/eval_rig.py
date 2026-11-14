#!/usr/bin/env python3
"""Which features and which training scheme detect heat pump faults under real noise?

1. Per unit (the device learns its own unit after install): train a GMM on that unit's
   healthy windows only, score its held-out healthy clips and synthetic faults, both
   with unseen background noise.
2. Leave one unit out (a factory model shipped to a new unit): train on the other units,
   test on the held-out one. Shows whether a model transfers between devices.
3. Other machines: a unit's model should reject other units and indoor units.

A clip's score is the median of its 1 s window scores, so a car passing by for two
seconds does not decide the result. Alarm threshold = 99th percentile of the training
scores, so "false alarm" is the share of healthy test clips above it.

    .venv/bin/python tools/eval_rig.py
"""
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "tools"))
from physics_features import SR, features, windows  # noqa: E402
from rig_augment import (AUDIO, FAULTS, clip_seconds, load, make_set, noise_pool,  # noqa: E402
                         rig_units, split_unit)

EDGES = np.geomspace(50, SR / 2, 65)  # same 64 log bands as python/main.py


def generic(x):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    idx = np.digitize(np.fft.rfftfreq(len(x), 1 / SR), EDGES) - 1
    return 10 * np.log10(np.array([spec[idx == i].sum() for i in range(64)]) / len(x) + 1e-12)


FEATS = {"generic 64 bands": generic, "physics 22": features,
         "physics + generic": lambda w: np.concatenate([features(w), generic(w)])}


class Model:
    def __init__(self, n_components=2):
        self.scaler = StandardScaler()
        self.gmm = GaussianMixture(n_components, covariance_type="full", reg_covar=1e-2, random_state=0)

    def fit(self, X):
        self.gmm.fit(self.scaler.fit_transform(X))
        self.thr = np.percentile(self.score(X), 99)
        return self

    def score(self, X):
        return -self.gmm.score_samples(self.scaler.transform(X))


def clip_features(clips, fn):
    return [np.array([fn(w) for w in windows(y)]) for *_, y in clips]


def evaluate(model, test_X, kinds):
    s = np.array([np.median(model.score(c)) for c in test_X])
    normal = kinds == "normal"
    row = {"false alarm": np.mean(s[normal] > model.thr)}
    for f in FAULTS:
        m = normal | (kinds == f)
        row[f] = roc_auc_score(kinds[m] == f, s[m])
    row["AUC all"] = roc_auc_score(kinds != "normal", s)
    return row


def table(title, rows, group_keys):
    keys = ["false alarm", *FAULTS, "AUC all"]
    print(f"\n{title}")
    print(" " * 36 + " ".join(f"{k[:12]:>12s}" for k in keys))
    groups = sorted({tuple(r[g] for g in group_keys) for r in rows}, key=str)
    for g in groups:
        sel = [r for r in rows if tuple(r[k] for k in group_keys) == g]
        print(f"{' / '.join(g):36s}" + " ".join(f"{np.mean([r[k] for r in sel]):12.2f}" for k in keys))


def main():
    rng = np.random.default_rng(1)
    train_noise, test_noise = noise_pool("train"), noise_pool("test")
    units = rig_units()
    other_audio = {p.stem: load(p) for p in sorted((AUDIO / "rig" / "other").glob("*.wav"))}

    data = {}
    for unit, x in units.items():
        tr, te = split_unit(x)
        test = make_set(te, "test", rng, 20, clip_seconds(te), test_noise, faults=FAULTS)
        data[unit] = {
            "clean only": make_set(tr, "train", rng, 60, clip_seconds(tr), train_noise, clean_share=1.0),
            "noise-augmented": make_set(tr, "train", rng, 60, clip_seconds(tr), train_noise),
            "test": test, "kinds": np.array([k for k, *_ in test]), "test_part": te,
        }

    per_unit, louo, others = [], [], []
    for fname, fn in FEATS.items():
        X = {u: {k: clip_features(d[k], fn) for k in ("clean only", "noise-augmented", "test")}
             for u, d in data.items()}
        for unit, d in data.items():
            for tname in ("clean only", "noise-augmented"):
                model = Model().fit(np.vstack(X[unit][tname]))
                per_unit.append({"unit": unit, "features": fname, "training": tname,
                                 **evaluate(model, X[unit]["test"], d["kinds"])})
                if tname == "noise-augmented":
                    foreign = {**other_audio, **{u: data[u]["test_part"] for u in units if u != unit}}
                    for name, y in foreign.items():
                        sc = np.median(model.score(np.array([fn(w) for w in windows(y)])))
                        others.append((unit, fname, name, sc / model.thr))
            # Factory model: trained on all other units, never heard this one
            pooled = np.vstack([c for u in units if u != unit for c in X[u]["noise-augmented"]])
            model = Model(n_components=len(units) - 1).fit(pooled)
            louo.append({"unit": unit, "features": fname, "training": "other units only",
                         **evaluate(model, X[unit]["test"], d["kinds"])})
        print(f"done: {fname}", flush=True)

    table("1) Per-unit model, mean over units (AUC per fault, 0.5 = chance)", per_unit, ["features", "training"])
    table("   ... per unit, noise-augmented",
          [r for r in per_unit if r["training"] == "noise-augmented"], ["unit", "features"])
    table("2) Factory model: trained on the OTHER units only (leave one unit out)", louo, ["features", "training"])
    print("\n3) Other machines through each unit's noise-augmented model "
          "(score / alarm threshold; > 1 = rejected as not this unit):")
    for unit in units:
        for fname in FEATS:
            sel = [(n, r) for u, f, n, r in others if u == unit and f == fname]
            print(f"{unit[:22]:22s} {fname:17s} " + "  ".join(f"{n[:14]}={r:.1f}" for n, r in sel))


if __name__ == "__main__":
    main()
