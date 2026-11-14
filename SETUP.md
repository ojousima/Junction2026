# Setup

## Mac (dev machine) — done
- `arduino-cli` 1.6.0 (Homebrew), core `arduino:zephyr` 1.1.0 (FQBN `arduino:zephyr:unoq`)
- Libraries: `Arduino_Modulino` 0.10.0 (Thermo, Buzzer), `Arduino_RouterBridge` 0.4.4 (+ deps, pinned in `sketch/sketch.yaml`)
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
5. Copy this project into App Lab's apps folder (or open it from App Lab) and run it. The smoke test prints temperature and humidity once per second.

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
- Rebooted into kernel 7.0.0 (`sudo reboot` with the `arduino` password; `adb reboot` does nothing).
- Brick images are pulled lazily when an app first uses a brick. Pre-pulled so the demo works offline:
  `ghcr.io/arduino/app-bricks/ei-models-runner:0.13.2` (audio/vibration/visual anomaly, image classification)
  and `influxdb:2.7-alpine` (`dbstorage_tsstore`). Image tags per brick:
  `/var/lib/arduino-app-cli/assets/0.13.2/compose/arduino/*/brick_compose.yaml`. 2.7 GB left on `/`.
- Run long jobs detached on the board (`nohup ... &`); a pull through a foreground `adb shell` was killed at 78 %.
- The board has no working IPv6; DNS returns AAAA records, but IPv4 is used and works.

**adb gotcha:** `adb shell` sets `TMPDIR=/data/local/tmp` (Android default), which does not exist on the board.
arduino-cli then fails with only "Some indexes could not be updated." Always `export TMPDIR=/tmp` first.

Deploy from the Mac without the App Lab GUI (`app restart` refuses a running app, so stop + start):

```bash
adb shell 'mkdir -p /home/arduino/ArduinoApps/heatpump-doctor'
adb push app.yaml python sketch assets /home/arduino/ArduinoApps/heatpump-doctor/
adb shell 'export TMPDIR=/tmp; cd ~/ArduinoApps/heatpump-doctor && arduino-app-cli app stop .; arduino-app-cli app start .'
adb shell 'docker logs -f heatpump-doctor-main-1'
```

Smoke test result: Thermo OK (24.0 °C, 35 % RH). We have no Modulino Movement; sketch reads Thermo only.
Example apps worth reading on the board: `~/.local/share/arduino-app-cli/examples/`
(`real-time-accelerometer`, `audio-classification` uses `arduino.app_peripherals.microphone.Microphone`).

## Cloud telemetry

The app can publish the latest real Thermo reading to PostgreSQL every 60
seconds. Audio and video cloud telemetry are placeholders only; local analytics
are unchanged. The app keeps running locally if telemetry is not configured or
the database is unreachable. The [schema contract](schema/README.md) describes
the existing table, proposed future metric table, IDs and limitations. Only one
temperature sensor is currently connected.

1. Have a database administrator inspect the existing `sensors.measurements`
   schema. The device user needs `USAGE` on schema `sensors` and `INSERT` on
   `sensors.measurements`. Do not use the Terraform state credentials.
2. Obtain the database connection URI for a restricted writer and the Aiven CA
   certificate. Copy `python/.env.example` to `python/.env` on the board,
   set `PG_CONNINFO`. The app derives its sensor ID from the board's hardware
   serial; no device ID needs to be configured.
   Put the CA at `python/aiven-ca.pem`, or set `PGSSLROOTCERT` to its path
   (relative paths are relative to the Python directory). The connection always
   uses `sslmode=verify-full` and validates the hostname.
3. Keep the `.env` file and certificate out of Git. Restrict access to the
   credentials while ensuring the App Lab container can read them. This is a
   temporary provisioning method: the file may be copied into the app/container
   during deployment and is accessible to users or processes with sufficient
   board/container access. Never share it, and rotate the password if exposed.
4. Deploy the app, including its Python dependencies and configuration, and
   restart it. For the existing USB deployment flow, the `adb push` of the
   `python` directory includes `python/.env` if it is present on the Mac; or
   place it in the board's app `python` directory before restarting. Check
   `docker logs -f heatpump-doctor-main-1` for `telemetry published` or an
   explicit configuration/connection error. A new dependency install may
   require internet on the board.

The simulator must be stopped separately if only real readings are desired.
Telemetry uses different sensor IDs, so real and simulated rows are distinct.

## Wireless access (SSH)
SSH was off on the stock image and had no host keys. Enabled once over adb (needs the `arduino` password):

```bash
adb shell -t "sudo ssh-keygen -A && sudo systemctl enable --now ssh"
```

Key login from the Mac uses a board-only key `~/.ssh/id_ed25519_unoq` and this `~/.ssh/config` entry:

```
Host uno-q
  HostName 10.149.88.102
  User arduino
  IdentityFile ~/.ssh/id_ed25519_unoq
  IdentitiesOnly yes
```

Deploy over Wi-Fi:

```bash
scp -r app.yaml python sketch assets uno-q:ArduinoApps/heatpump-doctor/
ssh uno-q 'cd ~/ArduinoApps/heatpump-doctor && arduino-app-cli app stop .; arduino-app-cli app start .'
ssh uno-q 'docker logs -f heatpump-doctor-main-1'
```

Live data view: http://10.149.88.102:7000 (any device on the same Wi-Fi).

**Autostart:** Heat Pump Doctor is the board's default app, so it starts on every boot.
Check or undo with:

```bash
ssh uno-q 'arduino-app-cli properties get default'
ssh uno-q 'arduino-app-cli properties set default none'
```

After a reset the board needs about a minute to rejoin Wi-Fi.

### Backup Wi-Fi

NetworkManager can save multiple Wi-Fi profiles. It prefers the available
autoconnect profile with the higher priority when establishing a connection;
it does not switch merely because the connected network has lost internet.
Avoid putting Wi-Fi passwords in source control or command history. On the
board, configure a network interactively with `nmcli --ask` and set
`connection.autoconnect-priority` on its saved profile. A negative priority
can keep a backup below a primary with priority zero.

Docker captures its upstream DNS servers when the app container starts. After
switching networks, the old DNS server may be unreachable even though the
board itself can resolve names. To refresh DNS automatically, install the
NetworkManager dispatcher script below. It restarts only the running Heat Pump
Doctor container when `wlan0` connects; the dashboard and sensor collection
briefly stop. It logs failures to the system journal. This does not detect
internet-only failures or preserve unsent telemetry during a restart.

```bash
adb push tools/heatpump-wifi-dns /home/arduino/heatpump-wifi-dns
adb shell -t 'sudo install -o root -g root -m 755 /home/arduino/heatpump-wifi-dns /etc/NetworkManager/dispatcher.d/90-heatpump-wifi-dns'
```

Check `journalctl -t heatpump-wifi-dns` on the board after a network change.

**App Lab over Wi-Fi:** network mode was off on the stock image, so App Lab and mDNS could not find the board.
Enabled with `ssh -t uno-q 'arduino-app-cli system network-mode enable'` (asks for the `arduino` password).
The board now announces `_arduino._tcp` as `uno-q` and resolves as `uno-q.local`, so App Lab lists it as a
network board and `ssh arduino@uno-q.local` works without knowing the IP.

### Team access
Each teammate makes their own key and sends only the **public** half (`.pub`). Never share a private key.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_unoq -C "<name>-uno-q"
cat ~/.ssh/id_ed25519_unoq.pub      # send this line
```

Someone with access appends it on the board:

```bash
ssh uno-q 'cat >> ~/.ssh/authorized_keys' < teammate.pub
```

Teammates must be on the same Wi-Fi as the board and add the same `Host uno-q` block to their `~/.ssh/config`.
The IP comes from DHCP: if it changes, check the router or run `ip -4 -br addr show wlan0` on the board.

## Camera and mic (Arduino USB Camera on the hub)
- Enumerates as `1c45:6200 HHWei Technology Web Camera`. The `/dev/videoN` number changes between boots
  (seen as `/dev/video2` and `/dev/video0`), so open it by name: `/dev/v4l/by-id/usb-*-video-index0`.
- Video: MJPEG 320x240 … 4656x3496 (incl. 1920x1080, 3840x2160); YUYV only 640x480 / 320x240. ~24 fps at 1280x720.
- Mic: ALSA card 0 (`plughw:0,0`), S16_LE, 48 kHz, 2 channels (identical, so effectively mono). Ambient level
  in a quiet room about −15 dBFS RMS with peaks near 0 dBFS: input gain is high, watch for clipping.
- Quick test on the board:
  ```bash
  v4l2-ctl -d /dev/v4l/by-id/usb-*-video-index0 --set-fmt-video=width=1280,height=720,pixelformat=MJPG --stream-mmap --stream-count=60 --stream-to=/tmp/burst.mjpg
  arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2 -d 5 /tmp/mic.wav
  ```
- The hub also has an RTL8152 Ethernet adapter, usable as a wired fallback.
- Image was all black (mean 1/255) with the lens cover on. Auto exposure (`auto_exposure=0`) works once it is off.
  Do not set `exposure_time_absolute=10000` (≈1 s per frame); a capture with it stalled and the board dropped off Wi-Fi.

### From the app container (verified)
The generated compose (`~/ArduinoApps/heatpump-doctor/.cache/app-compose.yaml`) binds `/dev` and allows video (81)
and ALSA (116) devices, so plain OpenCV and `alsaaudio` work in `python/main.py` with no `app.yaml` changes.
Measured: 30/30 frames at 1280x720 (~20 fps), and 16 kHz mono capture (ALSA resamples from 48 kHz).

```python
import glob, os, cv2, alsaaudio
cam = os.path.realpath(sorted(glob.glob("/dev/v4l/by-id/usb-*-video-index0"))[0])
cap = cv2.VideoCapture(cam, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
pcm = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, device="plughw:CARD=Camera,DEV=0", channels=1,
                    rate=16000, format=alsaaudio.PCM_FORMAT_S16_LE, periodsize=1600)
```

Available in the container: `cv2`, `numpy`, `alsaaudio`, `arduino.app_peripherals.{camera,microphone,speaker}`.
Not available: `sounddevice`. Use the ALSA card name (`CARD=Camera`), not the number, which can change.

## Sensors
| Signal | Sensor | Runs on |
|---|---|---|
| Temperature / humidity | Modulino Thermo | STM32 sketch, ~1 Hz over Bridge |
| Sound / vibration | Arduino USB Camera microphone | Linux Python (FFT features) |
| Coil icing | Arduino USB Camera (TPX00246) | Linux Python (OpenCV) |
| Alarm | Modulino Buzzer | STM32 sketch |
| Status | On-board LEDs / web dashboard | STM32 sketch / Linux |

No Modulino Movement: vibration faults are detected acoustically.
