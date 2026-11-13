"""Smoke test: print environment + IMU readings sent by the sketch over the Bridge."""
from arduino.app_utils import App, Bridge


def on_env(temp_c, rh, ax, ay, az):
    print(f"T={temp_c:.1f}C RH={rh:.0f}% acc=({ax:.2f},{ay:.2f},{az:.2f})g")


Bridge.provide("env", on_env)
App.run()
