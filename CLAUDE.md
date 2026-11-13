# Heat Pump Doctor — Junction 2026, Arduino challenge

## Goal
Edge-AI retrofit sensor that hears heat pump faults and slow efficiency loss (coil fouling) before the electricity bill does. Runs fully on Arduino UNO Q. 48 h hackathon: demo must work, code must be simple.

Judging (Arduino "Green European Renaissance"): Edge AI and UNO Q use 30 %, environmental/social impact 30 %, creativity 20 %, working prototype 20 %. Must also be published on Arduino Project Hub with the tag "Junction Finland 2026".

## Hardware
- Arduino UNO Q: STM32U585 MCU (Zephyr, Arduino sketch) and Qualcomm QRB2210 (Debian Linux, Python), linked by the Arduino Bridge (RPC)
- Modulino Movement (LSM6DSOX 6-axis IMU, Qwiic/I²C) for vibration
- Modulino Thermo (temperature and humidity) for operating point and frost risk
- Modulino Buzzer for the alarm; Modulino Pixels (if available) for the status LED
- USB microphone (sound anomalies) and USB camera (coil icing / frost detection) on the Linux side, via a USB-C hub
- Setup steps and installed toolchain: see SETUP.md
- Demo rig: desk fan as the "heat pump". Faults: coin or tape on a blade (imbalance), loose mount, cardboard over the intake (blocked coil)
- Optional: Jetson for training only. The final demo runs on the UNO Q.

## Architecture
```
IMU --I2C--> STM32 sketch
             - LSM6DSOX ODR ~1.66–3.33 kHz, FIFO burst reads, I2C 400 kHz
             - Hann window, FFT (CMSIS-DSP), ~64 log band energies + RMS + 1x peak freq
             - send features ~1 Hz over Bridge (no raw data across Bridge)
                     |
                     v
Linux Python app
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
