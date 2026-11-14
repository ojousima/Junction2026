"""Self-baselining anomaly detector: the sensor learns its own heat pump after install.

No pre-trained model. After start (or a reset) the detector collects LEARN_S seconds of
physics features from this unit, fits a robust Gaussian (median/IQR scaling + shrunk
covariance), and from then on scores every 1 s window by its Mahalanobis distance.

- Noise robustness: the score shown is the median over the last SMOOTH windows, so a car
  passing or someone talking for a few seconds does not raise an alarm.
- Alarm: smoothed score above threshold for ALARM_S seconds in a row (threshold = 99th
  percentile of the baseline's own smoothed scores x MARGIN).
- Operating points: windows that look clearly healthy keep being added to the baseline
  (up to MAX_WINDOWS, newest kept) and the model is refit every REFIT_S seconds, so new
  compressor speeds or weather are learned. Slow degradation (fouling) is NOT detected
  here on purpose; that is the trend tracker's job, against a frozen long-term baseline.
- Explanation: the features that moved most are mapped to the mechanism they measure.

numpy only. The baseline is saved to disk, so a restart keeps what was learned.
"""
import os
import threading
import time
from collections import deque

import numpy as np

from physics_features import FEATURE_NAMES

LEARN_S = 120        # seconds of healthy audio before monitoring starts (demo: 2 min)
SMOOTH = 5           # windows in the rolling median score
ALARM_S = 5          # consecutive seconds above threshold before the alarm sounds
MARGIN = 0.8         # threshold = MARGIN x 99th percentile of the baseline scores
MAX_WINDOWS = 3600   # baseline memory (1 h of windows)
REFIT_S = 600        # refit with newly learned healthy windows every 10 min
KEEP_BELOW = 0.5     # only windows scoring below KEEP_BELOW x threshold are learned
SHRINK = 0.3         # covariance shrinkage towards the diagonal (few-data robustness)

# What a large change in each feature means, physically
MEANING = {
    "mod_air": "fan airflow pulsing: imbalance or something touching the fan",
    "mod_air_peak_db": "fan airflow pulsing at one steady rate: imbalance or fan rub",
    "mod_high": "periodic clicks or scraping: rattle, fan rub or bearing",
    "mod_high_peak_db": "clicks at a steady rate: loose mount, fan rub or bearing",
    "kurt_high": "impacts: loose part, rattle or bearing damage",
    "crest": "impacts: loose part or rattle",
    "inharm_db": "new tonal lines off the compressor harmonics: bearing or electrical fault",
    "n_tones": "new tonal lines: bearing or electrical fault",
    "comp_f0_hz": "compressor speed changed (load change or blocked coil)",
    "comb_db": "compressor tone strength changed",
    "tone_prom_db": "compressor tone strength changed",
    "tonality_db": "more or less tonal sound: compressor or bearing",
    "band_3200_6400_db": "more high-frequency noise: bearing wear or scraping",
    "band_1600_3200_db": "more high-frequency noise: scraping or airflow",
    "level_db": "overall louder: higher load, blocked coil or loose part",
    "flatness": "sound became more noise-like: airflow or scraping",
    "centroid_hz": "sound got brighter: scraping, bearing or airflow",
}


def _meaning(name):
    if name in MEANING:
        return MEANING[name]
    if name.startswith("band_"):
        lo = int(name.split("_")[1])
        return "low-frequency hum changed: compressor or fan" if lo < 400 else "airflow noise changed: fan speed or coil"
    return name


class Detector:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.windows = deque(maxlen=MAX_WINDOWS)  # baseline feature vectors
        self.recent_scores = deque(maxlen=SMOOTH)
        self.recent_feats = deque(maxlen=SMOOTH)
        self.model = None
        self.above = 0
        self.last_fit = 0.0
        self._load()

    # --- persistence ---------------------------------------------------------
    def _load(self):
        if os.path.exists(self.path):
            try:
                d = np.load(self.path)
                if list(d["names"]) == FEATURE_NAMES:
                    self.windows.extend(d["windows"])
                    if len(self.windows) >= LEARN_S:
                        self._fit()
            except Exception as e:  # corrupt or old file: start learning again
                print(f"baseline not loaded: {e}")

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp.npz"
        np.savez(tmp, windows=np.array(self.windows), names=np.array(FEATURE_NAMES))
        os.replace(tmp, self.path)

    def reset(self):
        with self.lock:
            self.windows.clear()
            self.recent_scores.clear()
            self.recent_feats.clear()
            self.model, self.above = None, 0
            if os.path.exists(self.path):
                os.remove(self.path)

    # --- model ---------------------------------------------------------------
    def _fit(self):
        X = np.array(self.windows)
        med = np.median(X, axis=0)
        iqr = np.subtract(*np.percentile(X, [75, 25], axis=0))
        scale = np.where(iqr > 1e-9, iqr / 1.349, X.std(axis=0) + 1e-9)
        Z = (X - med) / scale
        S = np.cov(Z, rowvar=False)
        S = (1 - SHRINK) * S + SHRINK * np.diag(np.diag(S)) + 1e-3 * np.eye(len(S))
        P = np.linalg.inv(S)
        mu = Z.mean(axis=0)
        d = np.einsum("ij,jk,ik->i", Z - mu, P, Z - mu) / Z.shape[1]
        # threshold from the baseline's own smoothed scores
        sm = np.array([np.median(d[max(0, i - SMOOTH + 1):i + 1]) for i in range(len(d))])
        self.model = {"med": med, "scale": scale, "mu": mu, "P": P,
                      "thr": MARGIN * float(np.percentile(sm, 99))}
        self.last_fit = time.time()
        self._save()

    def _score(self, f):
        m = self.model
        z = (f - m["med"]) / m["scale"]
        dz = z - m["mu"]
        return float(dz @ m["P"] @ dz / len(z)), z

    # --- main entry: one feature vector per second -----------------------------
    def update(self, f):
        """Returns a dict for the dashboard: mode, progress, score, threshold, alarm, reasons."""
        f = np.asarray(f, dtype=float)
        with self.lock:
            if self.model is None:
                self.windows.append(f)
                if len(self.windows) >= LEARN_S:
                    self._fit()
                return {"mode": "learning", "progress": min(1.0, len(self.windows) / LEARN_S),
                        "score": None, "threshold": None, "alarm": False, "reasons": []}

            raw, _ = self._score(f)
            self.recent_scores.append(raw)
            self.recent_feats.append(f)
            score = float(np.median(self.recent_scores))
            thr = self.model["thr"]
            self.above = self.above + 1 if score > thr else 0
            alarm = self.above >= ALARM_S

            if raw < KEEP_BELOW * thr:  # clearly healthy: learn this operating point too
                self.windows.append(f)
            if time.time() - self.last_fit > REFIT_S:
                self._fit()

            reasons = []
            if score > thr:
                _, z = self._score(np.median(np.array(self.recent_feats), axis=0))
                for i in np.argsort(-np.abs(z))[:3]:
                    if abs(z[i]) < 3:
                        break
                    reasons.append({"feature": FEATURE_NAMES[i], "z": round(float(z[i]), 1),
                                    "meaning": _meaning(FEATURE_NAMES[i])})
            return {"mode": "monitoring", "progress": 1.0, "score": round(score, 2),
                    "threshold": round(thr, 2), "alarm": alarm, "reasons": reasons}
