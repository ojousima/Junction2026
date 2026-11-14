"""Configurable ranges and fixed dataset conventions for the simulator."""

from dataclasses import dataclass

DEFAULT_DURATION_SECONDS = 3600
FEATURE_COLUMNS = ("second", "outside_temp_c", "outgoing_temp_c")
GROUND_TRUTH_COLUMNS = (
    "second",
    "mode",
    "frost_index",
    "effective_airflow_fraction",
    "fan_on",
    "fault_active",
    "heat_transfer_capacity",
)
METADATA_COLUMNS = (
    "filename",
    "label",
    "scenario",
    "seed",
    "split",
    "unit_archetype",
    "ambient_mean_c",
    "relative_humidity_pct",
    "heating_load",
    "fan_speed_fraction",
    "heating_delta_nominal_c",
    "frost_growth_factor",
    "defrost_count",
    "defrost_total_seconds",
    "defrost_effectiveness",
    "fault_start_second",
    "fault_severity",
    "notes",
)

AMBIENT_MIN_C = -15.0
AMBIENT_MAX_C = 8.0
RELATIVE_HUMIDITY_MIN_PCT = 35.0
RELATIVE_HUMIDITY_MAX_PCT = 100.0
OUTSIDE_VALIDATION_BOUNDS_C = (-25.0, 15.0)
OUTGOING_VALIDATION_BOUNDS_C = (-30.0, 30.0)
MAX_ONE_SECOND_SENSOR_CHANGE_C = 5.0

# These are simulator conventions, not calibrated heat-pump operating limits.
ARCHETYPE_COUNT = 12
ARCHETYPE_SPLITS = {
    **{index: "train" for index in range(8)},
    **{index: "validation" for index in range(8, 10)},
    **{index: "test" for index in range(10, 12)},
}


@dataclass(frozen=True)
class UnitParameters:
    """Per-snippet equipment variation, sampled identically for both labels."""

    nominal_delta_c: float
    airflow_sensitivity: float
    frost_delta_response: float
    probe_lag_seconds: float
    ambient_sensor_lag_seconds: float
    sensor_noise_c: float
    noise_correlation: float
    defrost_threshold: float
    response_style: str
