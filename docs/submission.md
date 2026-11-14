# Submission drafts

Two submissions are needed for the Arduino "Green European Renaissance" challenge:

1. **Junction platform** (hackjunction.app, Project Submission): judging and peer review happen here.
2. **Arduino Project Hub** (projecthub.arduino.cc, + NEW PROJECT, tag **Junction Finland 2026**): required to be eligible for prizes.

Text in `[brackets]` still needs a team decision or a link.

---

## 1. Junction platform form

### Project Name (max 30)

```
Heat Pump Doctor
```

### Punchline (max 200)

```
An Arduino UNO Q that listens to your heat pump, learns how it sounds when healthy, and tells you which part is failing, fully offline, before your electricity bill does.
```

### Challenge Picker

The Green European Renaissance (Arduino)

### Description (max 5000, markdown)

```markdown
## The problem

Europe is betting on heat pumps to get homes off oil and gas. But an outdoor unit sits outside for 15+ years, and nobody listens to it. An unbalanced fan, a loose mount, a worn bearing or a coil clogged with leaves makes the unit work harder, use more electricity and wear out sooner. Most owners only find out when the bill goes up or the unit breaks in the middle of winter.

Existing monitoring is either built into new premium units, or needs the cloud. The tens of millions of heat pumps already installed have nothing.

## What we built

Heat Pump Doctor is a retrofit sensor you put next to an existing outdoor unit. It runs fully on the **Arduino UNO Q**, with no cloud and no account:

1. **Listens.** The USB camera's microphone records 16 kHz audio. Every second the Linux side of the UNO Q computes 22 **physics-based features**, each tied to one heat pump mechanism: compressor speed from its harmonic series, fan airflow modulation (imbalance), periodic clicks (loose mount, fan rub), impacts and high-frequency tones (bearing wear), off-harmonic lines (electrical or valve faults), and band levels (blocked coil).
2. **Learns its own unit.** No pre-trained model. After install the sensor learns this unit's healthy sound for 2 minutes, then keeps learning new healthy operating points (compressor speeds, weather) while it runs. One "Re-learn this unit" button starts over.
3. **Detects and explains.** Every second it scores how far the sound is from healthy (robust Mahalanobis distance). A 5 s median ignores passing cars, aircraft and people talking. After 5 s above threshold it raises an alarm and names the likely cause in plain words, e.g. *"fan airflow pulsing: imbalance or something touching the fan"*.
4. **Alerts locally.** The STM32 MCU reads the **Modulino Thermo** (temperature, humidity: operating point and frost risk) and sounds the **Modulino Buzzer**. The Linux app and the MCU talk over the Arduino Bridge.
5. **Shows it.** A web dashboard served from the board shows the live spectrum, anomaly score, detected compressor speed, the reasons for an alarm, temperature and humidity, and a camera view of the coil.
6. **Optional fleet history.** If an installer configures a database, the board publishes temperature and humidity to PostgreSQL (Aiven) once a minute. It is off by default; detection never depends on it.

## Edge AI on the UNO Q

- **MCU (STM32U585, Zephyr):** Modulino Thermo over I²C, buzzer alarm, Bridge RPC.
- **MPU (Qualcomm QRB2210, Debian):** audio capture, FFT and features (numpy only), self-learning anomaly model, CSV logging, web dashboard. Everything runs on the board.
- The model is small enough to retrain on the device in seconds, so every unit gets its own model instead of a generic one. Few features means minutes of data are enough, and every alarm can be explained.

## How we tested it

We used recordings of four real outdoor units (three recorded by the team, one public Freesound clip), mixed in unseen background noise (traffic, aircraft, rain, wind, speech) at −5 to 20 dB SNR, and synthesised faults from heat pump physics (imbalance, loose mount, fan rub, bearing wear, blocked coil, compressor defect). Results on held-out audio, averaged over 4 units:

- Our 22 physics features cut false alarms on noisy healthy audio from 54 % (generic 64-band spectrum) to 12 %, with the same fault detection (mean AUC 0.70).
- Best detected: fan bearing wear (AUC 0.81), rattle (0.79), fan rub (0.77), compressor bearing (0.76). Fan imbalance and compressor defects are still hard (0.55).
- A model learned on the unit itself beats a "factory" model trained on other units (AUC 0.70 vs 0.59). That is why the sensor learns its own heat pump.

The live demo uses a desk fan as the "heat pump": a coin on a blade (imbalance), a loose mount, and cardboard over the intake (blocked coil).

## Impact

- **Energy:** a fault caught early means the unit stops wasting electricity weeks or months sooner. [Add a sourced figure for the efficiency loss of a fouled coil or faulty fan.]
- **Lifetime and materials:** fixing a fan or bearing early avoids replacing a whole outdoor unit and its refrigerant.
- **People:** elderly and rural households get a warning before the heating fails in winter.
- **European and local:** retrofit, offline, open source, no subscription and no data leaving the home.

## What's next

Slow-degradation tracking (coil fouling) against a frozen long-term baseline, normalised by operating point (outdoor temperature, compressor speed); coil icing detection from the camera; a phone notification over BLE.

## Team

[names and roles]
```

### Links

- Project Demo: [link to the demo video or leave empty]
- Source Code: [https://github.com/OWNER/heatpump_diagnostics]
- Video: [YouTube or Loom link]
- Other Link: [Arduino Project Hub post URL]
- Presentation: [PDF export of `presentation/deck_0_1/index.html`, optional]

---

## 2. Arduino Project Hub post

Log in at https://projecthub.arduino.cc/, click **+ NEW PROJECT**, select the tag **Junction Finland 2026**.

### Title

Heat Pump Doctor: an Edge AI stethoscope for heat pumps

### Short description

Retrofit sensor on the Arduino UNO Q that learns how your heat pump sounds when healthy and names the failing part before your electricity bill does. Fully offline.

### Cover image

[Photo of the UNO Q with the camera and Modulinos next to the fan rig, or a dashboard screenshot during an alarm]

### Components and supplies

- Arduino UNO Q (2 GB)
- Arduino USB Camera (TPX00246): microphone and camera
- Modulino Thermo
- Modulino Buzzer
- Qwiic cable
- Powered USB-C hub
- Desk fan (demo stand-in for a heat pump outdoor unit), a coin, tape and cardboard for the faults

### Apps and platforms

- Arduino App Lab
- Python 3 with numpy, OpenCV
- Edge Impulse (used to explore a baseline sound classifier)

### Story

#### Why

Heat pumps are how Europe will heat its homes without oil and gas. But an outdoor unit sits outside for 15+ years and nobody listens to it. A fan that has gone out of balance, a loose mount, a worn bearing or a coil blocked by leaves all make the unit use more electricity and fail sooner, and owners usually find out from the bill or a cold house. Heat Pump Doctor is a small retrofit sensor that listens for you, runs fully on the board, and needs no cloud.

#### How it works

[Insert architecture diagram]

The UNO Q has two brains, and we use both:

- The **STM32U585 MCU** runs an Arduino sketch. It reads the Modulino Thermo (temperature and humidity, for the operating point and frost risk) once per second, sends it to Linux over the Arduino Bridge, and drives the Modulino Buzzer when Linux raises an alarm.
- The **Qualcomm QRB2210 MPU** runs Debian and our Python app. It records 16 kHz audio from the USB camera's microphone and, every second, computes 22 features based on heat pump physics.

Why physics features instead of a generic spectrum? An outdoor unit makes two kinds of sound we know in advance. The inverter compressor makes tonal lines whose frequency follows its speed. The fan makes broadband airflow noise modulated at its rotation rate. Each fault changes one of these in a specific way:

| Fault | What changes in the sound |
|---|---|
| Fan imbalance | Airflow noise pulses at the rotation rate |
| Loose mount, fan rub | Clicks or scrapes once per revolution |
| Bearing wear | High-frequency impulses, new tonal lines |
| Compressor electrical or valve defect | Lines between the compressor harmonics |
| Blocked coil | Fan and compressor run faster, airflow louder |

Because each feature maps to a mechanism, a few minutes of audio are enough to learn a unit, and each alarm comes with a reason.

#### Self-learning detector

There is no pre-trained model. Every heat pump sounds different, so the sensor learns its own unit:

1. **Learn:** for the first 2 minutes it collects healthy feature vectors and fits a robust Gaussian model (median/IQR scaling, shrunk covariance).
2. **Monitor:** every second it computes the Mahalanobis distance from healthy. The score shown is the median of the last 5 seconds, so a passing car or a conversation does not trigger an alarm.
3. **Alarm:** 5 seconds above threshold sounds the buzzer. The dashboard lists the features that moved most and what they mean physically.
4. **Keep learning:** windows that look clearly healthy are added to the baseline and the model is refit every 10 minutes, so new compressor speeds and weather are learned. The baseline is saved, so a restart keeps it.

#### Dashboard

[Screenshot]

The App Lab web UI on port 7000 shows the detector state, the anomaly score over the last 5 minutes, the 64-band sound spectrum, temperature and humidity, the detected compressor speed, and the camera view of the coil. Every session is logged to CSV for retraining.

#### Testing

We used recordings of four real outdoor units (three recorded by the team, one public Freesound clip), split each recording in time (first 70 % to learn, last 30 % to test), and mixed in background noise the model had never heard (traffic, aircraft, rain, wind, speech) at −5 to 20 dB SNR. Faults were synthesised from heat pump physics, with defect rates set in orders of the shaft speed so the same fault models apply to any unit. `tools/eval_rig.py` reproduces the numbers.

| Features (per-unit model, noisy test audio) | False alarms on healthy clips | Mean fault AUC |
|---|---|---|
| Generic 64-band spectrum | 54 % | 0.69 |
| **22 physics features (ours)** | **12 %** | **0.70** |

Per fault, the physics features reach AUC 0.81 for fan bearing wear, 0.79 for rattle, 0.77 for fan rub and 0.76 for compressor bearing wear. Fan imbalance and compressor electrical defects are still hard (0.55), and that is our next thing to improve. A model trained on the other units and shipped to a new one ("factory model") drops to AUC 0.59, which is why Heat Pump Doctor learns each unit after installation.

The live demo uses a desk fan: a coin on a blade, a loose mount, and cardboard over the intake.

#### Impact

- Catching a fault early stops wasted electricity sooner and avoids replacing a whole outdoor unit.
- It works with heat pumps that are already installed, not only new premium models.
- Offline and open source: no subscription and no data leaving the home.

#### What's next

- Slow-degradation tracking (coil fouling) normalised by operating point
- Coil icing detection from the camera
- Phone alerts over BLE

### Code

Link the GitHub repository: [https://github.com/OWNER/heatpump_diagnostics]

Key files: `sketch/sketch.ino` (MCU), `python/main.py` (app), `python/physics_features.py`, `python/detector.py`.

### Schematics

Modulino Thermo and Modulino Buzzer are daisy-chained on the UNO Q's Qwiic connector. The USB camera connects through a powered USB-C hub. [Add a photo or simple diagram.]

### Video

[Embed demo video]
