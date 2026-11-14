#!/usr/bin/env python3
"""Replay a recording through the device's detector, one second at a time.

Same code as the UNO Q app (python/physics_features.py + python/detector.py), so this
shows what the dashboard and buzzer would do. Scenario per unit:
  learn   LEARN_S s of healthy audio (train part, with background noise mixed in)
  healthy 60 s of held-out healthy audio with unseen background noise
  <fault> 30 s per synthetic fault, also with background noise

    .venv/bin/python tools/replay_detector.py                 # all units
    .venv/bin/python tools/replay_detector.py --unit freesound
"""
import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "tools"))
import detector as det_mod  # noqa: E402
from physics_features import SR, features  # noqa: E402
from rig_augment import FAULTS, add_noise, fault, noise_pool, rig_units, split_unit  # noqa: E402


def stream(x, seconds, rng, noise, fault_kind=None, clean_share=0.3):
    """Yield 1 s blocks: random 4 s stretches of x, faulted and noise-mixed like the field."""
    out = []
    while len(out) < seconds:
        L = min(len(x) - 1, int(4.5 * SR))
        s = rng.integers(0, max(1, len(x) - L))
        seg = x[s:s + L]
        if fault_kind:
            seg = fault(seg, fault_kind, rng)
        if rng.random() > clean_share:
            name, nz = noise[rng.integers(len(noise))]
            seg = add_noise(seg, nz, rng.uniform(0, 20), rng)
        out += [seg[i:i + SR] for i in range(0, len(seg) - SR + 1, SR)]
    return out[:seconds]


def run(unit, x, rng, train_noise, test_noise):
    tr, te = split_unit(x)
    with tempfile.TemporaryDirectory() as d:
        det = det_mod.Detector(str(Path(d) / "baseline.npz"))
        for blk in stream(tr, det_mod.LEARN_S, rng, train_noise):
            det.update(features(blk))
        assert det.model is not None, "still learning"
        print(f"\n{unit}: learned {det_mod.LEARN_S} s, threshold {det.model['thr']:.2f}")
        for phase in ["healthy", *FAULTS]:
            secs = 60 if phase == "healthy" else 30
            blocks = stream(te, secs, rng, test_noise, None if phase == "healthy" else phase)
            res = [det.update(features(b)) for b in blocks]
            alarm_s = sum(r["alarm"] for r in res)
            first = next((i for i, r in enumerate(res) if r["alarm"]), None)
            reasons = {}
            for r in res:
                for why in r["reasons"][:1]:
                    reasons[why["meaning"]] = reasons.get(why["meaning"], 0) + 1
            top = max(reasons, key=reasons.get) if reasons else "-"
            print(f"  {phase:13s} alarm {alarm_s:3d}/{secs} s"
                  f"  first after {'-' if first is None else str(first) + ' s':>5s}"
                  f"  median score {np.median([r['score'] for r in res]):6.2f}   top reason: {top}")
            # do not let one fault's alarm state leak into the next phase
            det.recent_scores.clear()
            det.recent_feats.clear()
            det.above = 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unit", help="substring of the unit name")
    args = ap.parse_args()
    rng = np.random.default_rng(3)
    train_noise, test_noise = noise_pool("train"), noise_pool("test")
    for unit, x in rig_units().items():
        if args.unit and args.unit.lower() not in unit.lower():
            continue
        run(unit, x, rng, train_noise, test_noise)


if __name__ == "__main__":
    main()
