CREATE_SYNTHETIC_DATA — HeatPump Doctor synthetic temperature time series
Purpose
This document is an implementation brief for an IDE coding agent. Implement and run a reproducible Python synthetic-data generator, not merely a collection of sample CSVs. The resulting dataset will support rapid prototyping of a model that identifies frost-related deterioration of outdoor heat-pump performance using temperature time series.
We need many different realistic-looking one-hour snippets, sampled at exactly 1 Hz, including normal/healthy operation and unhealthy operation involving excessive outdoor-coil frosting and/or ineffective defrosting. At minimum, simulate:
Outdoor intake/ambient air temperature (`outside_temp_c`)
Outdoor unit discharge-air temperature (`outgoing_temp_c`): air that has passed over the outdoor evaporator and is expelled from the unit
The heat pump operates in HEATING mode except during startup, shutdown, and defrost. In normal heating, discharge air is generally colder than outdoor intake air. During reverse-cycle defrost, this relationship can change because the outdoor coil is heated; the outdoor fan is often stopped, so an outgoing-air temperature observation may be undefined or stale. Do not treat coil temperature and outgoing-air temperature as interchangeable.
Critical scientific qualification
This is a qualitative, physically motivated simulator, not a validated refrigerant-cycle or heat-exchanger model. The synthetic labels must be described as scenario labels, not real confirmed diagnoses or efficiency measurements. Two air-temperature sensors alone cannot uniquely identify frost, estimate COP, or prove that a coil is dirty. Do not train a model and present its accuracy on these simulations as evidence of field accuracy.
Required deliverables
Create this project structure:
```text
synthetic_heatpump/
├── README.md
├── requirements.txt
├── generate.py
├── heatpump_sim/
│   ├── __init__.py
│   ├── config.py
│   ├── simulator.py
│   ├── scenarios.py
│   ├── io.py
│   └── validation.py
├── tests/
│   └── test_generator.py
├── scripts/
│   └── preview.py
└── data/
    ├── healthy_0001.csv
    ├── healthy_0002.csv
    ├── ...
    ├── unhealthy_0001.csv
    ├── unhealthy_0002.csv
    └── metadata.csv
```
`data/` is generated at runtime. Keep production code readable, commented where physics requires explanation, and independently testable. Prefer Python 3.11+, `numpy`, `pandas`, `matplotlib`, and `pytest`; minimize other dependencies. Code should run without network access.
Public CSV schema (strict)
Each one-hour file contains exactly 3,600 data rows, one per second. Use these columns in this order:
```csv
second,outside_temp_c,outgoing_temp_c
0,1.72,-2.84
1,1.72,-2.91
2,1.71,-2.87
```
`second`: integer 0 through 3599 inclusive, no gaps or duplicates.
Both temperature columns are decimal Celsius values, with enough resolution to show sensor noise (e.g., 2–3 decimal places). No missing values in the default baseline dataset.
No label, fault state, frost index, setpoint, scenario ID, or hidden internal variables in the public feature CSVs: avoid leakage.
No time-of-day, equipment model, or random seed in the feature CSV unless a later version explicitly requests those variables.
Write ordinary UTF-8 comma-separated files compatible with `pandas.read_csv`.
Outgoing temperatures during fan-off defrost: choose one documented operational interpretation and keep the strict schema: a simulated probe in the outdoor discharge airstream can record an evolving local sensor temperature even when there is little or no airflow. It must not be portrayed as meaningful mass-flow-weighted outgoing-air temperature during fan-off. In this baseline dataset, produce a continuous finite signal that captures sensor thermal inertia and ambient/coil influence during defrost. Put the ground-truth fan state in metadata or internal traces. Consider optional advanced `NaN` values only under a distinct, separately documented dataset version.
Metadata and ground truth
Create `data/metadata.csv` with one row per snippet. At least:
`filename`, `label` (`healthy` / `unhealthy`), `scenario`, `seed`
`ambient_mean_c`, `relative_humidity_pct`, `heating_load` (unitless 0–1)
`fan_speed_fraction`, `heating_delta_nominal_c`, `frost_growth_factor`
`defrost_count`, `defrost_total_seconds`, `defrost_effectiveness`
`fault_start_second` (-1 for none), `fault_severity` (0–1)
`notes` explaining the simulated mechanism and not claiming a verified physical COP loss
Optionally put richer truth in `data/ground_truth/healthy_0001.csv` etc. containing `second`, `mode` (`startup`, `heating`, `defrost`, `recovery`, `off`), `frost_index`, `effective_airflow_fraction`, `fan_on`, `fault_active`, and latent heat-transfer capacity. Do not load these into a feature-only classifier. Save simulation parameters in metadata and/or a `manifest.json` for reproducibility.
Physical picture and signs
Basic temperature relation
Use a modest, state-dependent nominal cooling of passing air:
```text
T_outgoing = T_outside - ΔT_air + sensor/transient effects  (during heating and fan on)
```
Here `ΔT_air` is positive for an active heating-mode outdoor evaporator. It depends on compressor/heating demand, effective airflow, frost and the underlying extraction of heat.
Important non-identifiability: If frosting reduces air flow, `ΔT_air` might increase, decrease, or vary non-monotonically, depending on refrigerant control and heat-transfer degradation. Do not enforce the simplistic rule that “more frost always causes colder outgoing air.” Show scenarios with different qualitative responses. The clearest simulated indicators should emerge from temporal patterns, altered cycle frequency, incomplete recovery, and relative comparison under similar ambient/load conditions—not one hardcoded threshold.
Frost accumulation
Maintain latent `frost_index` (e.g. 0–1), increasing primarily when coil conditions are below freezing and moisture is available. A qualitative model may combine ambient temperature, relative humidity, active heating runtime, and stochastic variation. Introduce thermal/flow degradation smoothly as frost accumulates.
A simplified effective heat-transfer factor can decline with high frost, but the exact coefficients are freely chosen simulator parameters. Avoid hardcoded universal thresholds for actual heat pumps. A low-RH cold day may have little frost; around-freezing, humid conditions are often conducive to significant frost.
Defrost state machine
Implement at least `startup → heating ↔ defrost → recovery → heating`, with optional off/cycling periods.
During heating, produce correlated ambient temperature drift, operation-dependent discharge-air cooling, mild control cycles, and sensor noise.
A defrost event causes a change in the outdoor-coil thermal state. Outdoor fan behavior may change or cease. The observed discharge-air probe can show a transient toward ambient/warmer temperatures, but should not be forced to a fixed +10°C spike in every case.
During recovery, allow thermal lag and a gradual return to heating-mode discharge temperatures.
Defrost timing/duration should be variable and depend partly on environmental and latent system conditions. Avoid perfectly periodic events or predetermined counts based on class.
Unhealthy is a scenario, not an intrinsic observable
Frost-related unhealthy cases can include excessive frosting relative to comparable conditions, shorter heating intervals between defrosts, prolonged defrosts, partial/incomplete frost removal, slow post-defrost recovery, and persistent effective-heat-transfer deterioration. Some one-hour unhealthy snippets may be subtle or even indistinguishable from healthy on temperature alone. Keep such ambiguous examples in the dataset and document them.
Diverse operating conditions — vary independently of label
Randomly sample at minimum:
Factor	Example range / behavior
Outdoor mean temperature	approximately -15 to +8°C, with frost likelihood depending on conditions
Relative humidity	approximately 35–100%; include dry and humid cases
Ambient temporal changes	slow drifts, weather changes, occasional small fluctuations
Heating demand	light to heavy, time-varying
Fan speed	several plausible regimes; occasional speed changes
Sensor noise	varied per-sensor Gaussian + autocorrelated noise, quantization
Sensor lag	first-order thermal response, different time constants
Unit differences	different nominal air-cooling ranges, defrost logic, sensitivity
Starting state	cold startup, settled heating, defrost already in progress
Operating cycles	continuous heating, thermostat cycling, intermittent defrost
These are broad sandbox settings, not calibrated limits or expected real-world distributions. Prevent impossible combinations with sensible soft constraints (e.g., frost is much less likely with warm coils); still include a few unusual edge cases.
Crucial anti-shortcut rule: The marginal distributions of ambient temperature, humidity, heat demand, sensor noise, startup timing, and equipment type should broadly overlap between healthy and unhealthy. Do not make all unhealthy files cold/humid, all healthy files warm/dry, or every unhealthy case have a defrost while every healthy case lacks one. Healthy units can and should perform normal defrosts. Some unhealthy cases should not contain an observable defrost in the one-hour window.
Scenario catalog (implement all; extend if time)
Healthy scenarios:
`steady_mild`: stable operation above likely frost conditions, low variations.
`cold_dry`: cold but dry, little frost, variable heating load.
`humid_near_freezing`: gradual frosting, successful normal defrost when appropriate.
`normal_multiple_defrosts`: several plausible successful defrost events under challenging conditions.
`normal_startup`: startup transient followed by stable heating.
`normal_cycling`: thermostat or demand-driven on/off / output variation.
`changing_weather`: slow outdoor temperature/humidity changes.
`variable_fan_and_load`: changes that resemble fault signatures without a fault.
Unhealthy scenarios:
`rapid_frost_accumulation`: faster-than-baseline degradation under the same sorts of environmental conditions.
`frequent_defrost`: unnecessarily frequent defrost interventions or short periods of useful heating.
`prolonged_defrost`: long recovery/defrost compared with an appropriate matched baseline.
`incomplete_defrost`: frost remains after defrost, causing faster subsequent deterioration.
`ineffective_defrost`: defrost attempt has little effect on the latent frost index.
`slow_recovery`: temperature/operating performance returns unusually slowly.
`frost_related_airflow_restriction`: reduced effective airflow, with a variety of discharge-temperature responses.
`progressive_frost_degradation`: observable deterioration without a defrost event inside the hour.
Also add hard negatives: healthy but unusual-looking traces (weather changes, fan-speed changes, normal defrosts), and hard positives: unhealthy but subtle traces. These matter more than simply making visually distinct line plots.
Suggested simulator implementation (not required to follow exactly)
Use a one-second discrete-time latent-state simulator:
Draw scenario parameters from a seeded NumPy RNG.
Generate smooth ambient series with drift + bounded autocorrelated perturbations.
Update operating demand/fan-speed schedules with random dwell times.
At each second, update latent coil/airflow/frost state and the defrost state machine.
Compute a target discharge-probe temperature. For heating with fan on, anchor this in intake temperature minus a varying cooling term, with a frost-response curve that differs between units. For defrost or fan-off, model local probe behavior separately (no physical claim of through-flow air temperature).
Apply first-order sensor response and realistic measurement noise/quantization.
Save feature CSV and per-file metadata; optionally save ground-truth trace.
Useful equations (illustrative only):
```text
ambient[t+1] = ambient[t] + slow_drift + weather_noise
frost[t+1] = clamp(frost[t] + growth[t] - removal[t], 0, 1)
measured_temp[t+1] = measured_temp[t] + (target_temp[t] - measured_temp[t]) / tau + noise[t]
```
You may introduce latent `coil_temp` in the simulator to drive frost and defrost; it must not be mislabeled as the outgoing air measurement. Keep parameter ranges configurable in `config.py` rather than buried in deeply nested logic.
Dataset size, deterministic splits, and naming
Default: 100 healthy and 100 unhealthy files, each exactly 3,600 observations (720,000 rows total).
Provide CLI flags `--healthy`, `--unhealthy`, `--duration-seconds` (default 3600; standard dataset must remain 3600), `--seed`, `--output`, `--overwrite`, and optionally `--with-ground-truth`.
File naming: `healthy_0001.csv` ... and `unhealthy_0001.csv` ... starting at 0001.
Same seed + same arguments must generate byte-for-byte identical feature files and metadata. Avoid timestamps generated from the actual clock.
Metadata should include a `split` with `train`, `validation`, `test` assigned deterministically at the simulation-unit level. If producing variations sharing the same latent unit parameters, keep all those variations in the same split to avoid leakage.
Avoid creating near-duplicate time series across train/test. Prefer multiple simulator unit archetypes and hold some archetypes out for testing.
Validation — implement automated tests
At minimum verify:
Correct counts and consecutive filenames, exactly 3,600 rows each by default.
Exact CSV column names and numerical types, finite temperatures, `second == range(3600)`.
Physically sensible broad bounds (no unexplained 100°C air temperatures or 10°C one-second sensor jumps); report rather than silently clip extreme data.
Heating-mode, fan-on samples should ordinarily have outgoing air colder than incoming, allowing configurable transient tolerance.
Healthy examples with normal defrost events; unhealthy examples with none; genuine overlap between classes.
No class-dependent hardcoding of sensor precision, noise distribution, timestamps, or output formatting.
Fixed seed reproducibility; distinct seeds yield distinct data.
Metadata labels match filenames and scenario truth; ground truth kept separate from model inputs.
Defrost event counts and total defrost duration in metadata agree with latent ground-truth state.
Normal scenario parameters and fault severity varied across generated files.
Diagnostics and preview plots
Provide `scripts/preview.py` that can:
Plot `outside_temp_c` and `outgoing_temp_c` for a selected file on one axis, labeled in °C and minutes.
Plot `outside_temp_c - outgoing_temp_c` on a second axis.
If ground truth is enabled, shade heating/defrost/recovery intervals and show frost index separately; clearly mark this information as simulation ground truth, not observed sensor features.
Produce an overview image grid showing a variety of healthy and unhealthy cases, including difficult examples.
Optionally create distributions of defrost duration, heating intervals, average temperature differences, and scenario/condition balance by label.
README expectations
Explain:
Install: `python -m pip install -r requirements.txt`
Generate: `python generate.py --healthy 100 --unhealthy 100 --seed 42 --output data --with-ground-truth`
Preview: `python scripts/preview.py --file data/unhealthy_0001.csv` (adjust script import handling so this works from the project root)
Tests: `python -m pytest -q`
What each column actually means and sensor-placement assumptions.
All unvalidated physics/behavior assumptions, known limitations, and non-identifiability of efficiency loss.
Clear distinction between real frost, defrost, compressor cycling, and sensor signal interpretation.
Acceptance criteria / definition of done
Do not stop after writing source code. Run the generator and tests. Create the default 200-file dataset. Inspect at least 8 plots across the catalog, including ambiguous cases. Print a concise summary of generated files, durations, sensor ranges, scenarios, and split counts. Correct any failures before reporting completion. Ensure the data folder contains no accidental huge binary files.
Optional phase 2 (only after phase 1 works)
Additional optional sensors in a separate schema/version: coil surface temperature, relative humidity, fan on/off, electrical power, flow/return temperatures.
Missing readings, temporary sensor detachment, clock drift, sensor bias, sensor relocation, and icing on the sensor itself.
Simulated outdoor intake/discharge recirculation.
Compare a naive absolute-threshold detector against an ambient-conditioned time-series model.
Evaluate generalization to held-out simulated unit archetypes and weather conditions; emphasize that simulation-only scores do not establish real-world reliability.
Agent execution instruction
Implement the complete first version now, prioritizing working and validated code over sophistication. If an assumption is scientifically ambiguous, write it down and choose a modest, consistent simulator convention. Do not fabricate empirical calibration or external datasets. Avoid a black-box generator in which fault labels are encoded in obvious constant offsets or deterministic signatures. Deliver the code, example output files, validation tests, and preview plots.