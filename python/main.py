"""Smoke test: print environment + IMU readings sent by the sketch over the Bridge."""
from arduino.app_utils import App, Bridge


def on_env(temp_c, rh, ax, ay, az):
    print(f"T={temp_c:.1f}C RH={rh:.0f}% acc=({ax:.2f},{ay:.2f},{az:.2f})g")


def on_status(thermo_ok, imu_ok, imu_fresh):
    print(f"status thermo_ok={thermo_ok} imu_ok={imu_ok} imu_fresh={imu_fresh}")


Bridge.provide("env", on_env)
Bridge.provide("status", on_status)
App.run()
