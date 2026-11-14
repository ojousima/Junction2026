import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
import health


def detector(score, thr=1.0, alarm=False, features=()):
    return {"mode": "monitoring", "score": score, "threshold": thr, "alarm": alarm,
            "reasons": [{"feature": f} for f in features]}


class HealthTests(unittest.TestCase):
    def levels(self, **state):
        state.setdefault("mic_ok", True)
        s = health.summarize(state)
        return {k: v["level"] for k, v in s["components"].items()}, s["overall"]

    def test_all_healthy(self):
        lv, overall = self.levels(detector=detector(0.3), temp_c=12, rh=60,
                                  coil={"status": "monitoring", "cleanliness_pct": 92})
        self.assertEqual(lv, {"coil": "ok", "fan": "ok", "compressor": "ok", "defrost": "ok"})
        self.assertEqual(overall, "ok")

    def test_fan_alarm_points_at_fan_only(self):
        lv, overall = self.levels(detector=detector(3, alarm=True, features=["mod_high", "kurt_high"]))
        self.assertEqual((lv["fan"], lv["compressor"]), ("alert", "ok"))
        self.assertEqual(overall, "alert")

    def test_compressor_watch_before_alarm(self):
        lv, _ = self.levels(detector=detector(2, features=["inharm_db", "mod_air"]))
        self.assertEqual((lv["compressor"], lv["fan"]), ("watch", "watch"))

    def test_unclear_anomaly_is_watch_not_alert(self):
        lv, _ = self.levels(detector=detector(3, alarm=True, features=[]))
        self.assertEqual((lv["fan"], lv["compressor"]), ("watch", "watch"))

    def test_learning_or_mic_offline_is_unknown(self):
        lv, _ = self.levels(detector={"mode": "learning"})
        self.assertEqual(lv["fan"], "unknown")
        lv, _ = self.levels(mic_ok=False, detector=detector(3, alarm=True, features=["mod_high"]))
        self.assertEqual(lv["fan"], "unknown")

    def test_coil_thresholds(self):
        for pct, want in [(90, "ok"), (65, "watch"), (40, "alert")]:
            lv, _ = self.levels(coil={"status": "monitoring", "cleanliness_pct": pct})
            self.assertEqual(lv["coil"], want)
        lv, _ = self.levels(coil={"status": "learning"})
        self.assertEqual(lv["coil"], "unknown")

    def test_defrost(self):
        self.assertEqual(self.levels(temp_c=1, rh=90)[0]["defrost"], "watch")  # frost weather
        self.assertEqual(self.levels(temp_c=1, rh=90, icing=0.8)[0]["defrost"], "alert")
        self.assertEqual(self.levels(temp_c=None, rh=None)[0]["defrost"], "unknown")

    def test_texts_are_plain_english(self):
        s = health.summarize({"mic_ok": True, "detector": detector(0.1), "temp_c": 12, "rh": 50})
        self.assertEqual(s["components"]["fan"]["text"], "Fan OK")


if __name__ == "__main__":
    unittest.main()
