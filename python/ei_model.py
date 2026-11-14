"""Edge Impulse model (.eim) on the UNO Q: a second, independent anomaly score.

The model (project "heatpump-doctor-rig": Spectral Analysis + GMM, trained on four
healthy outdoor units with background noise) is a "factory" model: it never heard this
unit. Its raw score level differs from unit to unit, so we calibrate it per unit the same
way as detector.py: learn the score's normal range during the first LEARN_S seconds,
then flag when the rolling median rises above that.

Talks to the .eim directly over its Unix socket (the Edge Impulse Linux protocol), so no
extra Python package is needed. If no model file is present, everything is a no-op.
"""
import glob
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
from collections import deque

import numpy as np

from detector import LEARN_S, MARGIN, SMOOTH

MODEL_GLOB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model", "heatpump-doctor-rig*.eim")


class EIModel:
    def __init__(self, pattern=MODEL_GLOB):
        found = sorted(glob.glob(pattern))
        self.path = found[-1] if found else None
        self.proc = self.sock = None
        self.lock = threading.Lock()
        self.msg_id = 0
        self.info = None
        self.reset()
        if self.path:
            try:
                self._start()
            except Exception as e:
                print(f"edge impulse model not started: {e}")
                self.path = None

    # --- .eim process + socket -------------------------------------------------
    def _start(self):
        os.chmod(self.path, 0o755)
        sock_path = os.path.join(tempfile.mkdtemp(), "eim.sock")
        self.proc = subprocess.Popen([self.path, sock_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if os.path.exists(sock_path):
                break
            time.sleep(0.1)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(sock_path)
        self.info = self._send({"hello": 1})
        params = self.info.get("model_parameters", {})
        print(f"edge impulse model {os.path.basename(self.path)}: "
              f"{params.get('frequency')} Hz, {params.get('input_features_count')} inputs")

    def _send(self, msg):
        self.msg_id += 1
        msg["id"] = self.msg_id
        self.sock.sendall(json.dumps(msg).encode("utf-8"))
        data = b""
        while True:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("model process closed the socket")
            data += chunk
            text = data.rstrip(b"\x00").decode("utf-8", "ignore")
            try:
                resp = json.loads(text)
                break
            except json.JSONDecodeError:
                continue
        if not resp.get("success", True):
            raise RuntimeError(resp.get("error", "classification failed"))
        return resp

    # --- per-unit calibration ------------------------------------------------------
    def reset(self):
        self.learn_scores = []
        self.recent = deque(maxlen=SMOOTH)
        self.threshold = None

    def update(self, x):
        """Score one 1 s block (float samples, 16 kHz). Returns a dict for the dashboard."""
        if not self.path:
            return {"available": False}
        with self.lock:
            # Studio stores 16-bit WAV samples as raw integers, so feed the same scale
            feats = (np.asarray(x) * 32768).round().astype(int).tolist()
            raw = float(self._send({"classify": feats})["result"]["anomaly"])
            self.recent.append(raw)
            score = float(np.median(self.recent))
            if self.threshold is None:
                self.learn_scores.append(score)
                if len(self.learn_scores) >= LEARN_S:
                    # same rule as detector.py: margin x 99th percentile of this unit's scores
                    self.threshold = MARGIN * float(np.percentile(self.learn_scores, 99))
                return {"available": True, "mode": "learning", "score": round(score, 2), "threshold": None,
                        "unusual": False}
            return {"available": True, "mode": "monitoring", "score": round(score, 2),
                    "threshold": round(self.threshold, 2), "unusual": score > self.threshold}
