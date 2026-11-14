# Heat Pump Doctor

Junction 2026, Arduino challenge.

Edge-AI retrofit sensor that hears heat pump faults and slow efficiency loss (coil fouling) before the electricity bill does. Runs fully on the Arduino UNO Q.

- `sketch/`: STM32 sketch (Modulino Thermo, temperature and humidity over the Arduino Bridge). ~~Modulino Movement~~: not available, vibration is detected acoustically
- `python/`: Linux-side Python app (anomaly score, fouling tracker, dashboard)
- `app.yaml`: Arduino App Lab app definition
- `data/`: recorded sessions (CSV/WAV/JPG are git-ignored)

Setup and toolchain: see [SETUP.md](SETUP.md). Architecture and plan: see [CLAUDE.md](CLAUDE.md).

CI builds the UNO Q sketch and checks Python syntax on a CRACI runner. The repository must be
connected to CRACI for the `craci` runner label to be available. Hardware and App Lab runtime
behavior still need to be tested on the UNO Q.
