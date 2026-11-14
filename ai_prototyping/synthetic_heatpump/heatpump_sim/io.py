"""Deterministic CSV and manifest output helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .config import FEATURE_COLUMNS, GROUND_TRUTH_COLUMNS, METADATA_COLUMNS
from .simulator import SimulationResult


def _write_rows(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_feature_csv(path: Path, result: SimulationResult) -> None:
    data = result.features
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(FEATURE_COLUMNS)
        for second, outside, outgoing in zip(
            data["second"], data["outside_temp_c"], data["outgoing_temp_c"]
        ):
            writer.writerow((int(second), f"{outside:.3f}", f"{outgoing:.3f}"))


def write_ground_truth_csv(path: Path, result: SimulationResult) -> None:
    truth = result.truth
    rows = []
    for index in range(len(truth["second"])):
        rows.append(
            {
                "second": int(truth["second"][index]),
                "mode": str(truth["mode"][index]),
                "frost_index": f"{truth['frost_index'][index]:.5f}",
                "effective_airflow_fraction": f"{truth['effective_airflow_fraction'][index]:.4f}",
                "fan_on": int(truth["fan_on"][index]),
                "fault_active": int(truth["fault_active"][index]),
                "heat_transfer_capacity": f"{truth['heat_transfer_capacity'][index]:.4f}",
            }
        )
    _write_rows(path, GROUND_TRUTH_COLUMNS, rows)


def write_metadata_csv(path: Path, rows: list[dict]) -> None:
    _write_rows(path, METADATA_COLUMNS, rows)


def write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
