"""Dataset schema, range, leakage-boundary, and truth consistency checks."""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    ARCHETYPE_SPLITS,
    FEATURE_COLUMNS,
    GROUND_TRUTH_COLUMNS,
    MAX_ONE_SECOND_SENSOR_CHANGE_C,
    METADATA_COLUMNS,
    OUTGOING_VALIDATION_BOUNDS_C,
    OUTSIDE_VALIDATION_BOUNDS_C,
)
from .scenarios import SCENARIOS_BY_LABEL


def _defrost_runs(modes: np.ndarray) -> tuple[int, int]:
    is_defrost = modes == "defrost"
    count = int(np.count_nonzero(is_defrost & ~np.r_[False, is_defrost[:-1]]))
    return count, int(np.count_nonzero(is_defrost))


def validate_dataset(
    output: Path,
    healthy: int,
    unhealthy: int,
    duration_seconds: int,
    with_ground_truth: bool,
) -> dict:
    """Raise for structural failures and report, never clip, physical outliers."""
    metadata_path = output / "metadata.csv"
    metadata = pd.read_csv(metadata_path)
    if tuple(metadata.columns) != METADATA_COLUMNS:
        raise ValueError(f"Unexpected metadata columns: {tuple(metadata.columns)}")
    expected_names = {
        *(f"healthy_{index:04d}.csv" for index in range(1, healthy + 1)),
        *(f"unhealthy_{index:04d}.csv" for index in range(1, unhealthy + 1)),
    }
    if set(metadata["filename"]) != expected_names or len(metadata) != healthy + unhealthy:
        raise ValueError("Metadata filenames/count do not match requested class counts.")
    scenario_labels = {
        scenario.name: label
        for label, scenarios in SCENARIOS_BY_LABEL.items()
        for scenario in scenarios
    }

    warnings_found: list[str] = []
    scenario_counts = metadata["scenario"].value_counts().sort_index().to_dict()
    split_counts = metadata["split"].value_counts().sort_index().to_dict()
    sensor_min = {"outside_temp_c": float("inf"), "outgoing_temp_c": float("inf")}
    sensor_max = {"outside_temp_c": float("-inf"), "outgoing_temp_c": float("-inf")}
    maximum_step = 0.0
    class_defrost_counts: dict[str, list[int]] = {"healthy": [], "unhealthy": []}

    for row in metadata.to_dict(orient="records"):
        if not str(row["filename"]).startswith(f"{row['label']}_"):
            raise ValueError(f"{row['filename']}: filename prefix and label disagree.")
        if scenario_labels.get(row["scenario"]) != row["label"]:
            raise ValueError(f"{row['filename']}: scenario and label disagree.")
        archetype = int(row["unit_archetype"])
        if ARCHETYPE_SPLITS.get(archetype) != row["split"]:
            raise ValueError(f"{row['filename']}: split does not match unit archetype.")
        if row["label"] == "healthy" and (
            float(row["fault_severity"]) != 0.0 or int(row["fault_start_second"]) != -1
        ):
            raise ValueError(f"{row['filename']}: healthy metadata contains active fault values.")
        if row["label"] == "unhealthy" and (
            float(row["fault_severity"]) <= 0.0
            or int(row["fault_start_second"]) < 0
            or int(row["fault_start_second"]) >= duration_seconds
        ):
            raise ValueError(f"{row['filename']}: unhealthy metadata has invalid fault values.")
        feature_path = output / row["filename"]
        frame = pd.read_csv(feature_path)
        if tuple(frame.columns) != FEATURE_COLUMNS:
            raise ValueError(f"{feature_path.name}: feature schema mismatch.")
        if len(frame) != duration_seconds:
            raise ValueError(f"{feature_path.name}: expected {duration_seconds} rows.")
        if not pd.api.types.is_integer_dtype(frame["second"]):
            raise ValueError(f"{feature_path.name}: second must have integer type.")
        if not np.array_equal(frame["second"].to_numpy(), np.arange(duration_seconds)):
            raise ValueError(f"{feature_path.name}: seconds are not consecutive.")
        temperatures = frame.loc[:, ["outside_temp_c", "outgoing_temp_c"]].to_numpy(dtype=float)
        if not np.isfinite(temperatures).all():
            raise ValueError(f"{feature_path.name}: non-finite temperature.")
        for column, bounds in (
            ("outside_temp_c", OUTSIDE_VALIDATION_BOUNDS_C),
            ("outgoing_temp_c", OUTGOING_VALIDATION_BOUNDS_C),
        ):
            values = frame[column].to_numpy(dtype=float)
            sensor_min[column] = min(sensor_min[column], float(values.min()))
            sensor_max[column] = max(sensor_max[column], float(values.max()))
            outside_bounds = (float(values.min()) < bounds[0]) or (float(values.max()) > bounds[1])
            if outside_bounds:
                warnings_found.append(
                    f"{feature_path.name}: {column} range {values.min():.2f}..{values.max():.2f} "
                    f"exceeds broad review bounds {bounds}; values were not clipped."
                )
            step = float(np.abs(np.diff(values)).max(initial=0.0))
            maximum_step = max(maximum_step, step)
            if step > MAX_ONE_SECOND_SENSOR_CHANGE_C:
                warnings_found.append(
                    f"{feature_path.name}: {column} has a one-second jump of {step:.2f} C; "
                    "values were not clipped."
                )

        truth_path = output / "ground_truth" / row["filename"]
        if with_ground_truth:
            truth = pd.read_csv(truth_path)
            if tuple(truth.columns) != GROUND_TRUTH_COLUMNS:
                raise ValueError(f"{truth_path.name}: ground-truth schema mismatch.")
            if len(truth) != duration_seconds or not np.array_equal(
                truth["second"].to_numpy(), np.arange(duration_seconds)
            ):
                raise ValueError(f"{truth_path.name}: truth seconds/row count mismatch.")
            if not bool(truth["mode"].isin(("startup", "heating", "defrost", "recovery", "off")).all()):
                raise ValueError(f"{truth_path.name}: invalid operating mode.")
            truth_count, truth_seconds = _defrost_runs(truth["mode"].to_numpy())
            if truth_count != int(row["defrost_count"]):
                raise ValueError(f"{truth_path.name}: defrost count disagrees with metadata.")
            if truth_seconds != int(row["defrost_total_seconds"]):
                raise ValueError(f"{truth_path.name}: defrost duration disagrees with metadata.")
            class_defrost_counts[row["label"]].append(truth_count)
        elif truth_path.exists():
            raise ValueError("Ground-truth file exists but --with-ground-truth was not requested.")

    if warnings_found:
        for message in warnings_found:
            warnings.warn(message, RuntimeWarning, stacklevel=2)
    if with_ground_truth and healthy >= 8 and not any(class_defrost_counts["healthy"]):
        raise ValueError("No healthy sample contains a normal defrost event.")
    if (
        with_ground_truth
        and unhealthy >= 8
        and not any(count == 0 for count in class_defrost_counts["unhealthy"])
    ):
        raise ValueError("No unhealthy sample demonstrates an unobserved/no-defrost window.")
    if with_ground_truth and healthy >= 8 and unhealthy >= 8:
        if not any(count == 0 for count in class_defrost_counts["healthy"]):
            raise ValueError("Healthy examples need both defrost and no-defrost windows.")
        if not any(count > 0 for count in class_defrost_counts["unhealthy"]):
            raise ValueError("Unhealthy examples need at least one observable defrost.")
    if healthy >= 8 and unhealthy >= 8:
        healthy_rows = metadata.loc[metadata["label"] == "healthy"]
        unhealthy_rows = metadata.loc[metadata["label"] == "unhealthy"]
        for column in ("ambient_mean_c", "relative_humidity_pct", "heating_load"):
            lower = max(float(healthy_rows[column].min()), float(unhealthy_rows[column].min()))
            upper = min(float(healthy_rows[column].max()), float(unhealthy_rows[column].max()))
            if lower > upper:
                raise ValueError(f"Class distributions do not overlap for {column}.")
    if set(metadata["label"]) - {"healthy", "unhealthy"}:
        raise ValueError("Metadata contains an invalid label.")
    if not metadata["fault_severity"].between(0.0, 1.0).all():
        raise ValueError("Fault severity must be between zero and one.")
    if not metadata["heating_load"].between(0.0, 1.0).all():
        raise ValueError("Heating load must be between zero and one.")
    return {
        "files": len(metadata),
        "rows_per_file": duration_seconds,
        "scenario_counts": scenario_counts,
        "split_counts": split_counts,
        "sensor_min": sensor_min,
        "sensor_max": sensor_max,
        "maximum_one_second_change_c": maximum_step,
        "warnings": warnings_found,
    }
