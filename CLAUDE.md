# Heat Pump Doctor — Junction 2026, Arduino challenge

## Goal
Edge-AI retrofit sensor that hears heat pump faults and slow efficiency loss (coil fouling) before the electricity bill does. Runs fully on Arduino UNO Q. 48 h hackathon: demo must work, code must be simple.

Judging (Arduino "Green European Renaissance"): Edge AI and UNO Q use 30 %, environmental/social impact 30 %, creativity 20 %, working prototype 20 %. Must also be published on Arduino Project Hub with the tag "Junction Finland 2026".

## Hardware
- Arduino UNO Q: STM32U585 MCU (Zephyr, Arduino sketch) and Qualcomm QRB2210 (Debian Linux, Python), linked by the Arduino Bridge (RPC)
- Modulino Thermo (temperature and humidity) for operating point and frost risk
- Modulino Buzzer for the alarm
- No IMU (no Modulino Movement) and no Modulino Pixels. Vibration faults are heard through the camera microphone instead.
- Arduino USB Camera (TPX00246) on the Linux side, via a USB-C hub: camera for coil icing / frost, built-in microphone for sound/vibration anomalies
- Status output: UNO Q on-board LED matrix / RGB LEDs, or the web dashboard
- Setup steps and installed toolchain: see SETUP.md
- Demo rig: desk fan as the "heat pump". Faults: coin or tape on a blade (imbalance), loose mount, cardboard over the intake (blocked coil)
- Optional: Jetson for training only. The final demo runs on the UNO Q.

## Architecture
```
Thermo --I2C--> STM32 sketch
             - temperature + humidity ~1 Hz over Bridge (operating point, frost risk)
             - drives the Modulino Buzzer alarm
                     |
                     v
Linux Python app
             - USB mic: 16 kHz audio, Hann window, FFT, ~64 log band energies + RMS + peak freq per ~1 s
             - USB camera: periodic frame of the coil, icing/frost score (OpenCV, later a visual model)
             - Layer 1: instant anomaly score (Edge Impulse model or sklearn IsolationForest/GMM)
             - Layer 2: slow-fouling tracker: residual = feature - healthy_model(operating point);
               Kalman filter with random-walk "fouling" state, plus CUSUM alarm
             - Web dashboard (App Lab): live spectrum, anomaly score, fouling estimate ± uncertainty
             - Alerts: buzzer/LEDs, optional BLE to phone
```

## Toolchain
- Arduino App Lab (sketch + Python app in one project)
- Edge Impulse Studio (optional, baseline anomaly model)
- Python: numpy, scipy, scikit-learn

## Milestones
1. Fri night: raw IMU streaming at kHz rate, healthy baseline recorded
2. Sat midday: features on the MCU, anomaly score on Linux, live dashboard
3. Sat evening: fouling tracker + stepwise cardboard demo (10 → 50 % covered), alarms
4. Sun morning: demo video, README, Project Hub post

## Pitch
"Your heat pump loses efficiency silently. We hear it before your electricity bill does."
Differentiator vs. existing on/off-vibration demos: operating-point normalisation and slow degradation tracking, not just sudden faults.

## Conventions
- Keep it hackathon-simple: readable code, minimal dependencies, everything runs offline on the device
- Log raw sessions to CSV under data/ with a label and timestamp for retraining
