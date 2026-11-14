#!/usr/bin/env python3
"""Turn a few minutes of healthy heat pump audio into a training and test set.

1. Background noise: healthy audio + traffic, aircraft, helicopters, speech, rain, ...
   at -5..20 dB SNR is still healthy. The model learns to ignore it.
2. Synthetic faults from physics (test only, never train on them):
   imbalance    fan airflow noise amplitude-modulated at the rotation rate (4-15 Hz)
   rattle       loose mount: a short metallic click once per fan revolution
   fan_rub      something touching the fan (leaf, ice, bent grille): a scrape each time a
                blade passes (blade-pass rate = blades x rotation) + friction hiss
   fan_bearing  worn fan-motor bearing: resonance impulses at the outer-race defect rate
                (~3.2 x fan rotation), amplitude-modulated once per revolution
   comp_bearing worn compressor bearing: impulses at ~3.2 x compressor speed (found from
                the compressor's harmonic series), modulated at compressor speed
   blocked      blocked or fouled coil: fan and compressor run 4-10 % faster, airflow louder
   compressor   electrical/valve fault: extra sub/inter-harmonic line next to the compressor tone

Defect rates are given relative to the shaft speed (orders), so the same fault model works
on any unit: only the speeds differ.

Healthy recordings are split in time per unit (first 70 % train, last 30 % test) and the
noise clips are split by file, so test windows use audio and noise never seen in training.

    .venv/bin/python tools/rig_augment.py            # write WAVs for Edge Impulse
"""
import argparse
import sys
import zlib
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))
from physics_features import FEATURE_NAMES, SR, features  # noqa: E402

AUDIO = ROOT / "data" / "audio"
FAULTS = ["imbalance", "rattle", "fan_rub", "fan_bearing", "comp_bearing", "blocked", "compressor"]


# --- Loading ---------------------------------------------------------------------
def load(path):
    """Read audio as float mono at 16 kHz (converting with ffmpeg if needed)."""
    path = Path(path)
    if path.suffix.lower() != ".wav":
        import subprocess
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1",
                              "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
        return np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    x, fs = sf.read(path, dtype="float64", always_2d=True)
    x = x.mean(axis=1)
    if fs != SR:
        x = np.interp(np.arange(0, len(x) * SR / fs) * fs / SR, np.arange(len(x)), x)
    return x


def rig_units():
    """Healthy recordings: one file per outdoor unit in data/audio/rig/training/normal."""
    d = AUDIO / "rig" / "training" / "normal"
    return {p.stem: load(p) for p in sorted(d.iterdir()) if p.suffix.lower() in (".wav", ".m4a", ".mp3", ".flac")}


def noise_pool(split):
    """Background noise clips, split by file name hash so train and test never share a clip."""
    files = sorted((AUDIO / "noise").glob("*.wav"))
    pick = [f for f in files if (zlib.crc32(f.name.encode()) % 5 == 0) == (split == "test")]
    return [(f.name, load(f)) for f in pick]


def noise_kind(name):
    """esc50_car_horn_1-123-A-44.wav -> car_horn, speech_1234-5-0001.wav -> speech"""
    if name.startswith("esc50_"):
        return name[len("esc50_"):].rsplit("_", 1)[0]
    return name.split("_")[0]


# --- Signal helpers ----------------------------------------------------------------
def rms(x):
    return np.sqrt(np.mean(x ** 2)) + 1e-12


def bandpass(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def add_noise(x, noise, snr_db, rng):
    """Mix a random stretch of a noise clip into x at the given SNR (relative to x)."""
    n = noise[np.abs(noise) > 1e-4] if np.any(np.abs(noise) > 1e-4) else noise
    reps = int(np.ceil(len(x) / len(n))) + 1
    n = np.tile(n, reps)
    start = rng.integers(0, len(n) - len(x))
    n = n[start:start + len(x)]
    return x + n * rms(x) / rms(n) * 10 ** (-snr_db / 20)


# --- Synthetic faults (physics priors) ----------------------------------------------
def impulses(n, rate, rng, band, tau):
    """Decaying band-limited bursts repeating at `rate` Hz with a little timing jitter."""
    y = np.zeros(n)
    k = np.arange(int(6 * tau * SR)) / SR
    if rate <= 0 or len(k) < 8:
        return y + 1e-9
    burst = bandpass(rng.normal(size=len(k)) * np.exp(-k / tau), *band)
    for t0 in np.arange(rng.uniform(0, 1 / rate), n / SR - len(k) / SR, 1 / rate):
        i = int((t0 + rng.normal(0, 0.05 / rate)) * SR)
        if 0 <= i < n - len(k):
            y[i:i + len(k)] += rng.uniform(0.6, 1.0) * burst
    return y


def fault(x, kind, rng, severity=1.0):
    t = np.arange(len(x)) / SR
    f_rot = rng.uniform(4, 15)  # outdoor fan: ~250-900 rpm
    if kind == "imbalance":
        fan = bandpass(x, 100, 4000)
        depth = severity * rng.uniform(0.15, 0.4)
        return x - fan + fan * (1 + depth * np.sin(2 * np.pi * f_rot * t + rng.uniform(0, 6.3)))
    if kind == "rattle":
        y = x.copy()
        fc, tau = rng.uniform(2500, 5000), 0.004
        k = np.arange(int(0.03 * SR)) / SR
        click = np.exp(-k / tau) * np.sin(2 * np.pi * fc * k)
        amp = severity * rng.uniform(1.5, 4) * rms(x)
        for t0 in np.arange(rng.uniform(0, 1 / f_rot), t[-1] - 0.03, 1 / f_rot):
            i = int((t0 + rng.normal(0, 0.002)) * SR)
            if 0 <= i < len(y) - len(click):
                y[i:i + len(click)] += amp * rng.uniform(0.6, 1.0) * click
        return y
    if kind == "fan_rub":
        blades = rng.choice([3, 4, 5])
        bpf = blades * f_rot  # an obstacle is hit by every blade
        scrape = impulses(len(x), bpf, rng, band=(1000, 6000), tau=rng.uniform(0.004, 0.012))
        hiss = bandpass(rng.normal(size=len(x)), 1500, 6000)
        hiss *= 1 + 0.8 * np.sin(2 * np.pi * bpf * t)
        level = severity * rng.uniform(0.15, 0.5) * rms(x)
        return x + level * (scrape / rms(scrape) + 0.5 * hiss / rms(hiss))
    if kind in ("fan_bearing", "comp_bearing"):
        if kind == "fan_bearing":
            shaft = f_rot
        else:  # compressor speed from its harmonic series
            shaft = features(x[:SR])[FEATURE_NAMES.index("comp_f0_hz")]
        f_def = rng.uniform(2.8, 3.6) * shaft  # outer-race defect order for ~8-10 balls
        fc = rng.uniform(2500, 6000)            # bearing/housing resonance
        hits = impulses(len(x), f_def, rng, band=(fc - 400, fc + 400), tau=rng.uniform(0.001, 0.003))
        hits *= 1 + 0.5 * np.sin(2 * np.pi * shaft * t)  # load zone passes once per turn
        level = severity * 10 ** (rng.uniform(-16, -6) / 20) * rms(x)
        return x + level * hits / rms(hits)
    if kind == "blocked":
        speed = 1 + severity * rng.uniform(0.04, 0.10)
        idx = np.arange(int(len(x) / speed)) * speed  # play faster: every tone shifts up
        y = np.interp(idx, np.arange(len(x)), x)
        air = bandpass(y, 200, 2000)
        return y + air * (10 ** (severity * rng.uniform(2, 4) / 20) - 1)
    if kind == "compressor":
        f0 = features(x[:SR])[FEATURE_NAMES.index("comp_f0_hz")]
        ratio = rng.choice([0.5, 1.5, 2.5])
        level = 10 ** (rng.uniform(-18, -8) / 20) * severity
        tone = np.sin(2 * np.pi * f0 * ratio * t + rng.uniform(0, 6.3))
        return x + np.sqrt(2) * rms(x) * level * tone
    raise ValueError(kind)


# --- Data sets -------------------------------------------------------------------
def split_unit(x, train_share=0.7):
    k = int(len(x) * train_share)
    return x[:k], x[k:]


def segments(x, seconds, n, rng):
    """n random stretches of the given length."""
    L = int(seconds * SR)
    starts = rng.integers(0, len(x) - L, size=n)
    return [x[s:s + L] for s in starts]


def clip_seconds(x, wanted=5.0):
    """Clip length that fits a (possibly very short) recording, at least 2 s."""
    return max(2.0, min(wanted, 0.85 * len(x) / SR / 1.12))


def make_set(x, split, rng, n_clips, seconds, noise, clean_share=0.2, snr=(-5, 20), faults=()):
    """Clips of healthy (and optionally faulty) audio with background noise mixed in."""
    out = []
    L = int(seconds * SR)
    for kind in ["normal", *faults]:
        # Take 12 % extra so "blocked" (played faster) still fills the clip
        for seg in segments(x, seconds * 1.12, n_clips, rng):
            y = (seg if kind == "normal" else fault(seg, kind, rng))[:L]
            if rng.random() < clean_share:
                out.append((kind, "clean", None, y))
            else:
                name, nz = noise[rng.integers(len(noise))]
                s = rng.uniform(*snr)
                out.append((kind, noise_kind(name), s, add_noise(y, nz, s, rng)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train-clips", type=int, default=60, help="healthy training clips per unit")
    ap.add_argument("--test-clips", type=int, default=20, help="test clips per unit and condition")
    ap.add_argument("--seconds", type=float, default=5.0)
    args = ap.parse_args()
    rng = np.random.default_rng(0)
    out = AUDIO / "rig" / "augmented"
    train_noise, test_noise = noise_pool("train"), noise_pool("test")
    n = 0
    for unit, x in rig_units().items():
        tr, te = split_unit(x)
        sets = [("training", make_set(tr, "train", rng, args.train_clips, clip_seconds(tr, args.seconds), train_noise)),
                ("testing", make_set(te, "test", rng, args.test_clips, clip_seconds(te, args.seconds),
                                     test_noise, faults=FAULTS))]
        for category, clips in sets:
            for i, (kind, nk, snr, y) in enumerate(clips):
                label = "normal" if kind == "normal" else "anomaly"
                tag = nk if snr is None else f"{nk}{snr:+.0f}dB"
                dest = out / category / label / f"{unit}_{kind}_{tag}_{i:03d}.wav"
                dest.parent.mkdir(parents=True, exist_ok=True)
                sf.write(dest, np.clip(y / max(1.0, np.max(np.abs(y))), -1, 1), SR, subtype="PCM_16")
                n += 1
    print(f"Wrote {n} clips to {out}")


if __name__ == "__main__":
    main()
