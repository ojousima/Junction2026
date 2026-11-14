# Synthetic heat-pump temperature data

This package creates reproducible one-second, one-hour outdoor heat-pump
temperature snippets for prototyping frost-related time-series methods. It is
a qualitative simulator, not a validated refrigerant-cycle or heat-exchanger
model. Labels describe generated scenarios; they are not confirmed diagnoses
or measured efficiency/COP loss.

## Install and run

From this directory:

```powershell
python -m pip install -r requirements.txt
python generate.py --healthy 100 --unhealthy 100 --seed 42 --output data --with-ground-truth
python scripts/preview.py --file data/unhealthy_0001.csv
python scripts/preview.py --overview --data data --output plots/overview.png
python -m pytest -q
```

By default the generator creates 100 files per class, 3,600 observations per
file, a metadata table, and a deterministic manifest. `--duration-seconds`
exists for short experiments; the standard dataset duration is 3,600 seconds.
The CLI also supports `--healthy`, `--unhealthy`, `--seed`, `--output`,
`--overwrite`, and `--with-ground-truth`. Existing generated files are never
replaced unless `--overwrite` is given.

`data/` contains the model-input feature files, `metadata.csv`, and
`manifest.json`. If requested, simulation-only latent state is written under
`data/ground_truth/`. Do not merge ground-truth files or metadata into a
feature-only classifier; filenames and metadata intentionally contain the
scenario label for dataset organization. Re-running with the same seed and
arguments creates byte-for-byte identical CSV and JSON files. The split is
assigned by simulator unit archetype; test archetypes are held out from train
archetypes.

## Feature CSV and sensor assumptions

Every feature CSV has exactly these columns, in order:

* `second`: elapsed integer seconds from 0 to 3,599.
* `outside_temp_c`: temperature at the outdoor-unit intake, upstream of the
  outdoor coil.
* `outgoing_temp_c`: temperature measured by a probe in the outdoor discharge
  airstream, downstream of the coil, when the fan is moving air.

During heating with the fan operating, the outgoing air is usually colder than
the intake air because the outdoor evaporator extracts heat. The amount is
varied by simulated demand, unit characteristics, airflow, frost, lag, and
noise. Frost is deliberately allowed to produce decreasing, increasing-then-
decreasing, or nearly stable discharge-temperature responses. Consequently,
there is no universal threshold or monotonic relationship between frost and
the temperature difference.

During reverse-cycle defrost the outdoor fan is simulated as off. The
`outgoing_temp_c` column remains finite and continuous: it represents a
thermally lagged local probe influenced by ambient air and coil warming. It is
not meaningful mass-flow-weighted outgoing air while airflow is absent. Fan
state, operating mode, frost index, fault-active state, effective airflow,
and latent heat-transfer capacity are available only in the optional separate
ground-truth CSVs.

## Scenario labels and limitations

The generator implements eight healthy and eight unhealthy scenario families
from the project brief. Healthy examples include cold/dry operation, normal
defrost, cycling, startup, weather change, and fan/load changes that can look
unusual. Unhealthy examples cover faster frost growth, frequent or prolonged
defrost, incomplete or ineffective defrost, slower recovery, airflow
restriction, and subtle degradation without an in-window defrost. Ambient
conditions, humidity, load, unit archetype, sensor lag, and noise are sampled
for both labels; named weather-specific scenarios can target a subrange, but
both labels cover overlapping ambient and humidity conditions. Neither class
is assigned a unique sensor precision or temperature range.

The latent frost model increases frost more readily when the simulated
evaporator is cold and moisture is available, while defrost removes a
scenario-dependent fraction. Correlated weather and sensor traces provide
smooth time series. Coefficients and distributions are hand-chosen sandbox
assumptions, not empirically calibrated limits. The model does not simulate
refrigerant pressures, coil surface measurements, electrical power,
condensate drainage, actual heat delivery, installation variation, or measured
COP.

Two air-temperature sensors alone cannot uniquely determine real frost,
defrost quality, compressor cycling, coil fouling, or efficiency loss. A
synthetic scenario label is not ground truth from a real heat pump. Performance
on these files is not evidence of field accuracy. Validate any detector on
independent hardware observations before making diagnostic or energy-saving
claims.

## Preview and tests

`scripts/preview.py --file PATH` plots the two temperatures in °C against
minutes and the outside-minus-outgoing temperature difference. If the sibling
`ground_truth/PATH.name` exists, the plot shades simulated modes and shows the
latent frost index in a separately labeled panel. `--overview` creates a
scenario grid including healthy hard negatives and subtle unhealthy examples.
Ground truth is always identified as simulated truth, never as observed input.

Run the automated tests with `python -m pytest -q`. Generator validation checks
schema, row counts, numeric/finite values, broad temperature and sensor-step
ranges, class overlap in defrost behavior, metadata, deterministic output, and
agreement between defrost metadata and ground-truth intervals. Physical
outliers are reported; they are not silently clipped.
