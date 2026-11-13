# Setup

## Mac (dev machine) — done
- `arduino-cli` 1.6.0 (Homebrew), core `arduino:zephyr` 1.1.0 (FQBN `arduino:zephyr:unoq`)
- Libraries: `Arduino_Modulino` 0.10.0, `Arduino_RouterBridge` 0.4.4 (+ deps, pinned in `sketch/sketch.yaml`)
- `adb` (Homebrew cask `android-platform-tools`) for a shell on the UNO Q over USB
- Python 3.13 venv in `.venv/` with `requirements-dev.txt` (numpy, scipy, scikit-learn, pandas, matplotlib, opencv, sounddevice, soundfile)

Check the sketch builds:

```bash
arduino-cli compile --profile default sketch
```

## Mac — manual step
- Install **Arduino App Lab** (.dmg) from https://docs.arduino.cc/software/app-lab/ and move it to Applications.
- Use a data-capable USB-C cable. First connection runs a setup wizard and board updates; do not unplug during updates.

## UNO Q (first boot)
1. Plug in the board, open App Lab, finish the wizard (Wi-Fi, user password, updates).
2. Check the shell: `adb devices`, then `adb shell` (or `ssh arduino@<board>.local` once on Wi-Fi).
3. Connect a USB-C hub (powered): USB webcam (with mic) or separate USB mic.
4. On the board, verify the devices:
   ```bash
   lsusb
   v4l2-ctl --list-devices   # camera
   arecord -l                # microphone
   ```
5. Copy this project into App Lab's apps folder (or open it from App Lab) and run it. The smoke test prints temperature, humidity and acceleration once per second.

## Board state (2026-11-13, first connection)
- Hostname `uno-q`, user `arduino`, Debian 13 trixie, kernel 6.16, Python 3.13.5, **2 GB RAM** variant, 3.1 GB free on `/`.
- Visible over USB to `adb` after ~60 s boot (`adb devices`).
- Old image: Zephyr core **0.51.0**, `arduino-app-cli` 0.6.6. Needs the App Lab update before building (Mac has core 1.1.0).
- No Wi-Fi configured. Without internet `arduino-app-cli app start` cannot fetch libraries and fails
  (`Arduino_Modulino.h: No such file or directory`).
- Built-in bricks worth reusing: `vibration_anomaly_detection`, `audio_classification`,
  `visual_anomaly_detection`, `dbstorage_tsstore`, `web_ui`.
- **The board has one USB-C port.** Once a hub with camera/mic is attached, the board is the USB host and the
  Mac's `adb` link is gone. Work over Wi-Fi from then on (`ssh arduino@uno-q.local`, App Lab network mode).

Deploy from the Mac without the App Lab GUI:

```bash
adb push app.yaml python sketch /home/arduino/ArduinoApps/heatpump-doctor/
adb shell 'cd ~/ArduinoApps/heatpump-doctor && arduino-app-cli app start .'
adb shell 'arduino-app-cli app logs ~/ArduinoApps/heatpump-doctor'
```

## Sensors
| Signal | Sensor | Runs on |
|---|---|---|
| Vibration | Modulino Movement (LSM6DSOX) | STM32 sketch, features over Bridge |
| Temperature / humidity | Modulino Thermo | STM32 sketch |
| Sound | USB microphone | Linux Python |
| Coil icing | USB camera | Linux Python (OpenCV) |
| Alarm | Modulino Buzzer / Pixels | STM32 sketch |
