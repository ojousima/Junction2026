#!/usr/bin/env python3
"""Download public machine-sound data into data/audio/ for Edge Impulse.

Everything is converted to 16 kHz mono 16-bit WAV (same as the UNO Q mic
pipeline). Raw downloads are cached in data/audio/raw/ so re-runs are cheap.
Only needs the Python standard library and ffmpeg on PATH.

    python3 tools/fetch_audio.py                 # all sources, default sizes
    python3 tools/fetch_audio.py --only candas   # one source
    python3 tools/fetch_audio.py --per-class 20  # smaller subset

Sources and licenses: see data/audio/README.md.
"""
import argparse
import csv
import io
import json
import random
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "audio"
RAW = ROOT / "raw"
UA = {"User-Agent": "heatpump-doctor-fetch/1.0"}

CANDAS_API = "https://huggingface.co/api/datasets/IoTDataAtelier/CANDAS/tree/main/"
CANDAS_FILE = "https://huggingface.co/datasets/IoTDataAtelier/CANDAS/resolve/main/"
MIMII_FAN_ZIP = "https://zenodo.org/api/records/3678171/files/dev_data_fan.zip/content"
HEATPUMP_ZIP = "https://zenodo.org/api/records/18619500/files/Stimuli.zip/content"
ESC50_ZIP = "https://codeload.github.com/karolpiczak/ESC-50/zip/refs/heads/master"

# ESC-50 classes that sound like the outdoors around a heat pump.
ESC50_NOISE = ["rain", "wind", "thunderstorm", "crickets", "chirping_birds",
               "engine", "car_horn", "footsteps", "dog", "airplane"]


def fetch(url, dest, quiet=False):
    """Download url to dest unless it is already there."""
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if not quiet:
        print(f"  download {url}")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    tmp.rename(dest)
    return dest


def to_16k(src, dest):
    """Convert any audio file (path or bytes) to 16 kHz mono 16-bit WAV."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.stem}.part{dest.suffix}")
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", "pipe:0" if isinstance(src, bytes) else str(src),
           "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(tmp)]
    try:
        subprocess.run(cmd, input=src if isinstance(src, bytes) else None, check=True)
        tmp.replace(dest)
    finally:
        if tmp.exists():
            tmp.unlink()


def split(items, n, test_share, seed):
    """Pick n items at random (fixed seed) and split them into train and test."""
    items = sorted(items)
    random.Random(seed).shuffle(items)
    items = items[:n]
    k = round(len(items) * (1 - test_share))
    return items[:k], items[k:]


# --- CANDAS: two small DC cooling fans, magnets on blades (imbalance) -------------
def candas(per_class, test_share):
    out = ROOT / "candas"
    jobs = []
    for fan in ("A2", "A3"):
        for volt in ("9V", "12V"):
            # Config 1 is the balanced fan. Its "normal" folder is the same in every pair.
            normal = list_hf(f"{fan}/{volt}/config1config2/normal")
            train, test = split(normal, per_class, test_share, seed=1)
            jobs += [(p, out / "training/normal" / name("candas", p)) for p in train]
            jobs += [(p, out / "testing/normal" / name("candas", p)) for p in test]
            # Configs 2..5: more and more magnets, from light to severe imbalance.
            for cfg in (2, 3, 4, 5):
                ab = list_hf(f"{fan}/{volt}/config1config{cfg}/abnormal")
                picked, _ = split(ab, per_class // 4 or 1, 0, seed=cfg)
                jobs += [(p, out / "testing/anomaly" / name("candas", p)) for p in picked]

    def one(job):
        path, dest = job
        if dest.exists():
            return
        raw = fetch(CANDAS_FILE + urllib.parse.quote(path), RAW / "candas" / path, quiet=True)
        to_16k(raw, dest)

    print(f"CANDAS: {len(jobs)} clips")
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(one, jobs))


def list_hf(folder):
    """List the WAV files in one Hugging Face dataset folder."""
    url = CANDAS_API + urllib.parse.quote(folder)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r:
        entries = json.load(r)
    return [e["path"] for e in entries if e["type"] == "file" and e["path"].endswith(".wav")]


def name(prefix, hf_path):
    """A2/12V/config1config3/abnormal/000012.wav -> candas_A2_12V_cfg3_abnormal_000012.wav"""
    fan, volt, pair, label, f = hf_path.split("/")
    cfg = "1" if label == "normal" else pair[-1]
    return f"{prefix}_{fan}_{volt}_cfg{cfg}_{label}_{f}"


# --- MIMII fan (DCASE 2020 Task 2 dev set): industrial fans, real factory noise ---
def mimii_fan(per_class, test_share):
    out = ROOT / "mimii_fan"
    z = zipfile.ZipFile(fetch(MIMII_FAN_ZIP, RAW / "mimii" / "dev_data_fan.zip"))
    wavs = [m for m in z.namelist() if m.endswith(".wav")]
    n = 0
    for mid in ("id_00", "id_02", "id_04", "id_06"):
        train = [m for m in wavs if "/train/" in m and mid in m]
        test_norm = [m for m in wavs if "/test/normal_" in m and mid in m]
        test_anom = [m for m in wavs if "/test/anomaly_" in m and mid in m]
        n_test = max(1, round(per_class * test_share))
        picks = [("training/normal", split(train, per_class - n_test, 0, 1)[0]),
                 ("testing/normal", split(test_norm, n_test, 0, 2)[0]),
                 ("testing/anomaly", split(test_anom, n_test, 0, 3)[0])]
        for sub, members in picks:
            for m in members:
                # Build our own file name; never trust paths stored inside the zip.
                dest = out / sub / f"mimii_fan_{mid}_{Path(m).name}"
                if not dest.exists():
                    to_16k(z.read(m), dest)
                n += 1
    print(f"MIMII fan: {n} clips")


# --- RWTH heat pump stimuli: real air-to-water heat pump, healthy, for reference ---
def heatpump_ref():
    out = ROOT / "heatpump_ref"
    z = zipfile.ZipFile(fetch(HEATPUMP_ZIP, RAW / "heatpump_ref" / "Stimuli.zip"))
    n = 0
    for m in z.namelist():
        if m.lower().endswith(".wav") and not Path(m).name.startswith("."):
            to_16k(z.read(m), out / f"rwth_{Path(m).name}")
            n += 1
    print(f"Heat pump reference: {n} clips")


# --- ESC-50 outdoor background noise ----------------------------------------------
def noise(per_class):
    out = ROOT / "noise"
    z = zipfile.ZipFile(fetch(ESC50_ZIP, RAW / "esc50" / "ESC-50-master.zip"))
    meta = next(m for m in z.namelist() if m.endswith("meta/esc50.csv"))
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(meta), encoding="utf-8")))
    audio_dir = meta.replace("meta/esc50.csv", "audio/")
    n = 0
    for cat in ESC50_NOISE:
        files = [r["filename"] for r in rows if r["category"] == cat]
        for f in split(files, per_class, 0, 4)[0]:
            dest = out / f"esc50_{cat}_{f}"
            if not dest.exists():
                to_16k(z.read(audio_dir + f), dest)
            n += 1
    print(f"Noise: {n} clips")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=["candas", "mimii_fan", "heatpump_ref", "noise"])
    ap.add_argument("--per-class", type=int, default=60,
                    help="normal clips per fan/voltage (CANDAS) or per machine id (MIMII); default 60")
    ap.add_argument("--test-share", type=float, default=0.2, help="share of normal clips kept for testing")
    args = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found: brew install ffmpeg (or apt install ffmpeg)")

    steps = {
        "candas": lambda: candas(args.per_class, args.test_share),
        "mimii_fan": lambda: mimii_fan(args.per_class, args.test_share),
        "heatpump_ref": heatpump_ref,
        "noise": lambda: noise(min(args.per_class, 40)),
    }
    for key, step in steps.items():
        if args.only in (None, key):
            step()
    print(f"Done. Files in {ROOT}")


if __name__ == "__main__":
    main()
