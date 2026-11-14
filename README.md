# Heat Pump Doctor

Junction 2026, Arduino challenge.

Edge-AI retrofit sensor that hears heat pump faults and slow efficiency loss (coil fouling) before the electricity bill does. Runs fully on the Arduino UNO Q.

- `sketch/`: STM32 sketch (Modulino Thermo, temperature and humidity over the Arduino Bridge). ~~Modulino Movement~~: not available, vibration is detected acoustically
- `python/`: Linux-side Python app (anomaly score, fouling tracker, dashboard)
  - `physics_features.py`: 22 features tied to heat pump mechanisms (compressor harmonic
    series and speed, fan modulation, impacts, off-harmonic tones, band levels); numpy only
  - `detector.py`: self-learning detector. Learns this unit's healthy sound for 2 min after
    start, then scores every second (median of 5 s against noise), alarms after 5 s above
    threshold, names the likely mechanism, keeps learning new healthy operating points.
    No pre-trained model; "Re-learn this unit" on the dashboard starts over
  - `ei_model.py`: second, independent score from the Edge Impulse model
    `model/heatpump-doctor-rig*.eim` (Edge Impulse project "heatpump-doctor-rig":
    Spectral Analysis FFT 64 + GMM, trained on 4 healthy outdoor units with background
    noise). Calibrated per unit during the same learning phase; shown on the dashboard
    next to our detector. Talks to the .eim over its socket, no extra packages
- `app.yaml`: Arduino App Lab app definition
- `data/`: recorded sessions (CSV/WAV/JPG are git-ignored)
- `infra/aiven/`: Terraform configuration and import instructions for Aiven services

Setup and toolchain: see [SETUP.md](SETUP.md). Architecture and plan: see [CLAUDE.md](CLAUDE.md).
The database contract and device telemetry setup are documented in
[schema/](schema/) and [SETUP.md](SETUP.md#cloud-telemetry).

CI builds the UNO Q sketch and checks Python syntax on a CRACI runner. The repository must be
connected to CRACI for the `craci` runner label to be available. Hardware and App Lab runtime
behavior still need to be tested on the UNO Q.
