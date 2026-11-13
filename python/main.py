"""Smoke test: print temperature and humidity sent by the sketch over the Bridge."""
from arduino.app_utils import App, Bridge


def on_env(temp_c, rh):
    print(f"T={temp_c:.1f}C RH={rh:.0f}%")


def on_sensor_error(name):
    print(f"sensor not found: {name}")


Bridge.provide("env", on_env)
Bridge.provide("sensor_error", on_sensor_error)
App.run()
