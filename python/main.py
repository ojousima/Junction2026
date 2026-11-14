"""Heat Pump Doctor: live data view and self-learning fault detector.

Collects Thermo readings (over the Bridge), microphone band energies and physics
features, camera frames; learns this unit's healthy sound after start (detector.py),
scores every second, sounds the Modulino Buzzer on an alarm, logs everything to CSV
under data/, and serves a browser view on port 7000.
"""
import csv
import glob
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone

import alsaaudio
import cv2
import numpy as np
from fastapi import Response

from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App, Bridge

import telemetry
from detector import Detector
from physics_features import FEATURE_NAMES, features

MIC_DEVICE = "plughw:CARD=Camera,DEV=0"
CAM_GLOB = "/dev/v4l/by-id/usb-*-video-index0"  # /dev/videoN number changes between boots
SR = 16000
N_BANDS = 64
HISTORY_S = 300

lock = threading.Lock()
state = {
    "temp_c": None,
    "rh": None,
    "rms_dbfs": None,
    "peak_hz": None,
    "bands_db": [],
    "band_edges_hz": [],
    "cam_brightness": None,
    "cam_ok": False,
    "mic_ok": False,
    "comp_f0_hz": None,
    "detector": {"mode": "learning", "progress": 0.0, "score": None, "threshold": None,
                 "alarm": False, "reasons": []},
}
physics = []  # latest physics feature vector, for the CSV log
history = deque(maxlen=HISTORY_S)  # (t, temp_c, rh, rms_dbfs, peak_hz, anomaly_score)
detector = Detector("/app/data/baseline.npz")
latest_jpeg = None
sample_times = {"thermo": None}


# --- Thermo over Bridge -------------------------------------------------------
def on_env(temp_c, rh):
    with lock:
        state["temp_c"] = round(float(temp_c), 2)
        state["rh"] = round(float(rh), 1)
        sample_times["thermo"] = datetime.now(timezone.utc)


def on_sensor_error(name):
    if name == "thermo":
        with lock:
            state.update(temp_c=None, rh=None)
            sample_times["thermo"] = None
    print(f"sensor not found: {name}")


Bridge.provide("env", on_env)
Bridge.provide("sensor_error", on_sensor_error)


# --- Microphone: 1 s blocks -> log band energies ------------------------------
EDGES = np.geomspace(50, SR / 2, N_BANDS + 1)


def band_features(x):
    w = np.hanning(len(x))
    spec = np.abs(np.fft.rfft(x * w)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    idx = np.digitize(freqs, EDGES) - 1
    bands = np.array([spec[idx == i].sum() for i in range(N_BANDS)])
    bands_db = 10 * np.log10(bands / len(x) + 1e-12)
    rms_dbfs = 20 * np.log10(np.sqrt(np.mean(x**2)) + 1e-12)
    valid = freqs > 30
    peak_hz = float(freqs[valid][np.argmax(spec[valid])])
    return bands_db, rms_dbfs, peak_hz


def set_alarm(on):
    """Buzzer on the MCU side; never let a Bridge problem stop the mic loop."""
    try:
        Bridge.call("alarm", bool(on))
    except Exception as e:
        print(f"alarm call failed: {e}")


def mic_loop():
    global physics
    alarm_was = False
    while True:
        try:
            pcm = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, device=MIC_DEVICE, channels=1, rate=SR,
                                format=alsaaudio.PCM_FORMAT_S16_LE, periodsize=SR // 10)
            buf = []
            n = 0
            while True:
                length, data = pcm.read()
                if length <= 0:
                    continue
                chunk = np.frombuffer(data, np.int16).astype(np.float32) / 32768
                buf.append(chunk)
                n += len(chunk)
                if n >= SR:
                    x = np.concatenate(buf)[:SR]
                    buf, n = [], 0
                    bands_db, rms_dbfs, peak_hz = band_features(x)
                    feats = features(x)
                    det = detector.update(feats)
                    if det["alarm"] != alarm_was:
                        set_alarm(det["alarm"])
                        alarm_was = det["alarm"]
                    with lock:
                        physics = [round(float(v), 3) for v in feats]
                        state.update(mic_ok=True, rms_dbfs=round(float(rms_dbfs), 1), peak_hz=round(peak_hz),
                                     bands_db=[round(float(b), 1) for b in bands_db], detector=det,
                                     comp_f0_hz=round(float(feats[FEATURE_NAMES.index("comp_f0_hz")]), 1))
        except Exception as e:
            with lock:
                state.update(mic_ok=False, rms_dbfs=None, peak_hz=None, bands_db=[])
            print(f"mic error: {e}; retrying in 3 s")
            time.sleep(3)


# --- Camera: grab continuously, decode one frame per second -------------------
def cam_loop():
    global latest_jpeg
    while True:
        found = sorted(glob.glob(CAM_GLOB))
        cap = cv2.VideoCapture(os.path.realpath(found[0]) if found else "/dev/video0", cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        last = 0.0
        while cap.isOpened():
            if not cap.grab():
                break
            if time.time() - last < 1.0:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                break
            last = time.time()
            ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            with lock:
                latest_jpeg = jpg.tobytes() if ok else latest_jpeg
                state.update(cam_ok=True, cam_brightness=round(float(frame.mean()), 1))
        cap.release()
        with lock:
            state.update(cam_ok=False, cam_brightness=None)
        print("camera error; retrying in 3 s")
        time.sleep(3)


# --- 1 Hz history + CSV log ---------------------------------------------------
def log_loop():
    os.makedirs("/app/data", exist_ok=True)
    path = time.strftime("/app/data/live_%Y%m%d_%H%M%S.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "label", "temp_c", "rh", "rms_dbfs", "peak_hz", "cam_brightness",
                    "anomaly_score", "anomaly_threshold", "alarm"]
                   + [f"band{i}" for i in range(N_BANDS)] + FEATURE_NAMES)
        while True:
            time.sleep(1)
            with lock:
                s = dict(state)
                ph = list(physics)
            d = s["detector"]
            t = time.time()
            history.append((round(t, 1), s["temp_c"], s["rh"], s["rms_dbfs"], s["peak_hz"], d["score"]))
            w.writerow([round(t, 1), "unlabeled", s["temp_c"], s["rh"], s["rms_dbfs"], s["peak_hz"],
                        s["cam_brightness"], d["score"], d["threshold"], int(d["alarm"])]
                       + s["bands_db"] + ph)
            f.flush()


# --- Web UI -------------------------------------------------------------------
def api_state():
    with lock:
        s = dict(state)
        s["history"] = list(history)
    s["band_edges_hz"] = [round(float(e)) for e in EDGES]
    return s


def api_reset_baseline():
    """Forget this unit's baseline and learn again (e.g. after moving the sensor)."""
    detector.reset()
    set_alarm(False)
    return {"ok": True}


def api_frame():
    with lock:
        jpg = latest_jpeg
    if jpg is None:
        return Response(status_code=204)
    return Response(content=jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


def telemetry_snapshot():
    with lock:
        return dict(state), dict(sample_times)


ui = WebUI()
ui.expose_api("GET", "/api/state", api_state)
ui.expose_api("GET", "/api/frame.jpg", api_frame)
ui.expose_api("POST", "/api/baseline/reset", api_reset_baseline)

for target in (mic_loop, cam_loop, log_loop):
    threading.Thread(target=target, daemon=True).start()

threading.Thread(target=telemetry.run, args=(telemetry_snapshot,), daemon=True).start()

App.run()
