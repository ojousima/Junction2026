# Setup

## Mac (dev machine) — done
- `arduino-cli` 1.6.0 (Homebrew), core `arduino:zephyr` 1.1.0 (FQBN `arduino:zephyr:unoq`)
- Libraries: `Arduino_Modulino` 0.10.0 (Thermo only), `Arduino_RouterBridge` 0.4.4 (+ deps, pinned in `sketch/sketch.yaml`)
- `adb` (Homebrew cask `android-platform-tools`) for a shell on the UNO Q over USB
- Python 3.13 venv in `.venv/` with `requirements-dev.txt` (numpy, scipy, scikit-learn, pandas, matplotlib, opencv, sounddevice, soundfile)
- Edge Impulse CLI 1.40.2 (`npm install -g edge-impulse-cli`, Node 26): `edge-impulse-daemon`, `-data-forwarder`,
  `-uploader`, `-run-impulse`. Log in on first use (`edge-impulse-uploader --clean` asks for the account).

Edge Impulse CLI install gotchas on this Mac:
- `~/.npm` has a few root-owned cache dirs (old `sudo npm`). Use `--cache "$TMPDIR/npm-cache"` or fix with
  `sudo chown -R $(whoami) ~/.npm`.
- `/Library/Developer/CommandLineTools/usr/include/c++/v1` is a stale partial copy that hides the SDK's libc++
  headers, so native modules (serialport) fail with `'memory' file not found`. Workaround without sudo:
  ```bash
  CXXFLAGS="-isystem $(xcrun --show-sdk-path)/usr/include/c++/v1" npm install -g edge-impulse-cli --cache "$TMPDIR/npm-cache"
  ```
- The installed bin scripts lack the execute bit (`permission denied`). Fix:
  `chmod +x /opt/homebrew/lib/node_modules/edge-impulse-cli/build/cli/*.js`

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

Update done the same evening: Wi-Fi `Koti_A499_2GM` (10.149.88.102), `arduino-app-cli system update --only-arduino --yes`
brought `arduino-app-cli` 0.14.1, `arduino-router` 0.11.0 and Zephyr core 1.1.0 (matches the Mac).
Still open:
- Kernel 7.0 is installed but not booted. Needs `sudo reboot` (the `arduino` password is set; `adb reboot` does nothing).
- Docker image pull for `ei-models-runner` was killed at 78 %. Rerun the update after the reboot; the Edge Impulse bricks need it.
- The board has no working IPv6; DNS returns AAAA records, but IPv4 is used and works.

**adb gotcha:** `adb shell` sets `TMPDIR=/data/local/tmp` (Android default), which does not exist on the board.
arduino-cli then fails with only "Some indexes could not be updated." Always `export TMPDIR=/tmp` first.

Deploy from the Mac without the App Lab GUI (`app restart` refuses a running app, so stop + start):

```bash
adb shell 'mkdir -p /home/arduino/ArduinoApps/heatpump-doctor'
adb push app.yaml python sketch /home/arduino/ArduinoApps/heatpump-doctor/
adb shell 'export TMPDIR=/tmp; cd ~/ArduinoApps/heatpump-doctor && arduino-app-cli app stop .; arduino-app-cli app start .'
adb shell 'docker logs -f heatpump-doctor-main-1'
```

Smoke test result: Thermo OK (24.0 °C, 35 % RH). We have no Modulino Movement; sketch reads Thermo only.
Example apps worth reading on the board: `~/.local/share/arduino-app-cli/examples/`
(`real-time-accelerometer`, `audio-classification` uses `arduino.app_peripherals.microphone.Microphone`).

## Sensors
| Signal | Sensor | Runs on |
|---|---|---|
| Temperature / humidity | Modulino Thermo | STM32 sketch, ~1 Hz over Bridge |
| Sound / vibration | USB microphone | Linux Python (FFT features) |
| Coil icing | USB camera | Linux Python (OpenCV) |
| Alarm | On-board LEDs / web dashboard (TBD) | STM32 sketch / Linux |

No Modulino Movement: vibration faults are detected acoustically.
