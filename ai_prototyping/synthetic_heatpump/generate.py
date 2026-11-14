#!/usr/bin/env python3
"""Generate a reproducible, qualitative heat-pump temperature dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from heatpump_sim.config import (
    ARCHETYPE_COUNT,
    ARCHETYPE_SPLITS,
    DEFAULT_DURATION_SECONDS,
)
from heatpump_sim.io import (
    write_feature_csv,
    write_ground_truth_csv,
    write_manifest,
    write_metadata_csv,
)
from heatpump_sim.scenarios import SCENARIOS_BY_LABEL, Scenario
from heatpump_sim.simulator import simulate_snippet
from heatpump_sim.validation import validate_dataset


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--healthy", type=int, default=100, help="number of healthy scenarios")
    parser.add_argument("--unhealthy", type=int, default=100, help="number of unhealthy scenarios")
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=DEFAULT_DURATION_SECONDS,
        help="seconds per snippet (standard dataset: 3600)",
    )
    parser.add_argument("--seed", type=int, default=42, help="base random seed")
    parser.add_argument("--output", type=Path, default=Path("data"), help="output directory")
    parser.add_argument("--overwrite", action="store_true", help="replace generated dataset files")
    parser.add_argument(
        "--with-ground-truth",
        action="store_true",
        help="write latent simulation state into the separate ground_truth directory",
    )
    args = parser.parse_args()
    if args.healthy < 0 or args.unhealthy < 0 or args.healthy + args.unhealthy == 0:
        parser.error("class counts must be non-negative and their sum must be positive")
    if args.duration_seconds < 2:
        parser.error("--duration-seconds must be at least 2")
    if args.seed < 0:
        parser.error("--seed must be non-negative")
    return args


def _prepare_output(output: Path, names: list[str], overwrite: bool) -> None:
    output.mkdir(parents=True, exist_ok=True)
    generated = [output / name for name in names]
    generated.extend((output / "metadata.csv", output / "manifest.json"))
    existing_dataset_files = [
        *output.glob("healthy_*.csv"),
        *output.glob("unhealthy_*.csv"),
        output / "metadata.csv",
        output / "manifest.json",
    ]
    if not overwrite:
        existing = [path for path in existing_dataset_files if path.exists()]
        if existing:
            raise FileExistsError(
                "Output already contains generated dataset files. Choose another --output "
                "directory or pass --overwrite. First existing file: "
                f"{existing[0]}"
            )
        return
    for path in existing_dataset_files:
        if path.is_file():
            path.unlink()
    truth_dir = output / "ground_truth"
    if truth_dir.exists():
        for path in truth_dir.glob("*.csv"):
            path.unlink()
        try:
            truth_dir.rmdir()
        except OSError:
            pass


def _scenario_schedule(
    label: str, count: int, rng: np.random.Generator
) -> list[Scenario]:
    scenarios = SCENARIOS_BY_LABEL[label]
    scheduled = [scenarios[index % len(scenarios)] for index in range(count)]
    rng.shuffle(scheduled)
    return scheduled


def generate_dataset(
    healthy: int,
    unhealthy: int,
    duration_seconds: int,
    seed: int,
    output: Path,
    overwrite: bool = False,
    with_ground_truth: bool = False,
) -> dict:
    """Generate feature files, metadata, optional truth, and a deterministic manifest."""
    root_seed = np.random.SeedSequence(seed)
    schedule_rng = np.random.default_rng(root_seed.spawn(1)[0])
    class_scenarios = {
        "healthy": _scenario_schedule("healthy", healthy, schedule_rng),
        "unhealthy": _scenario_schedule("unhealthy", unhealthy, schedule_rng),
    }
    work: list[tuple[str, int, Scenario]] = []
    for label in ("healthy", "unhealthy"):
        work.extend(
            (label, index, scenario)
            for index, scenario in enumerate(class_scenarios[label], start=1)
        )
    sample_seeds = root_seed.spawn(len(work))
    expected_names = [
        f"{label}_{index:04d}.csv" for label, index, _ in work
    ]
    _prepare_output(output, expected_names, overwrite)

    truth_dir = output / "ground_truth"
    if with_ground_truth:
        truth_dir.mkdir(parents=True, exist_ok=True)
    metadata_rows: list[dict] = []
    summary_rows: list[dict] = []
    for (label, index, scenario), sample_seed in zip(work, sample_seeds):
        snippet_seed = int(sample_seed.generate_state(1, dtype=np.uint32)[0])
        rng = np.random.default_rng(sample_seed)
        unit_archetype = int(rng.integers(0, ARCHETYPE_COUNT))
        filename = f"{label}_{index:04d}.csv"
        result = simulate_snippet(
            rng,
            scenario,
            duration_seconds,
            unit_archetype,
        )
        write_feature_csv(output / filename, result)
        if with_ground_truth:
            write_ground_truth_csv(truth_dir / filename, result)
        metadata_rows.append(
            {
                "filename": filename,
                "label": label,
                "scenario": scenario.name,
                "seed": snippet_seed,
                "split": ARCHETYPE_SPLITS[unit_archetype],
                "unit_archetype": unit_archetype,
                "ambient_mean_c": f"{result.ambient_mean_c:.4f}",
                "relative_humidity_pct": f"{result.relative_humidity_pct:.3f}",
                "heating_load": f"{result.heating_load:.4f}",
                "fan_speed_fraction": f"{result.fan_speed_fraction:.4f}",
                "heating_delta_nominal_c": f"{result.nominal_heating_delta_c:.4f}",
                "frost_growth_factor": f"{result.frost_growth_factor:.4f}",
                "defrost_count": result.defrost_count,
                "defrost_total_seconds": result.defrost_total_seconds,
                "defrost_effectiveness": f"{result.defrost_effectiveness:.4f}",
                "fault_start_second": result.fault_start_second,
                "fault_severity": f"{result.fault_severity:.4f}",
                "notes": (
                    f"{scenario.mechanism}; qualitative simulator label, not a confirmed "
                    "diagnosis or measured COP loss."
                ),
            }
        )
        summary_rows.append(
            {
                "filename": filename,
                "label": label,
                "scenario": scenario.name,
                "split": ARCHETYPE_SPLITS[unit_archetype],
                "outside_min": float(np.min(result.features["outside_temp_c"])),
                "outside_max": float(np.max(result.features["outside_temp_c"])),
                "outgoing_min": float(np.min(result.features["outgoing_temp_c"])),
                "outgoing_max": float(np.max(result.features["outgoing_temp_c"])),
            }
        )
    write_metadata_csv(output / "metadata.csv", metadata_rows)
    manifest = {
        "format_version": 1,
        "base_seed": seed,
        "healthy_count": healthy,
        "unhealthy_count": unhealthy,
        "duration_seconds": duration_seconds,
        "sampling_rate_hz": 1,
        "with_ground_truth": with_ground_truth,
        "feature_columns": ["second", "outside_temp_c", "outgoing_temp_c"],
        "scenario_catalog": {
            label: [scenario.name for scenario in scenarios]
            for label, scenarios in SCENARIOS_BY_LABEL.items()
        },
        "split_by_unit_archetype": {
            str(archetype): ARCHETYPE_SPLITS[archetype]
            for archetype in range(ARCHETYPE_COUNT)
        },
        "seed_derivation": "NumPy SeedSequence.spawn; per-file seeds are in metadata.csv",
        "truth_interpretation": (
            "Ground truth is simulated latent state, not observed data. During fan-off "
            "defrost, outgoing_temp_c is a lagged local probe signal, not mass-flow-weighted air."
        ),
    }
    write_manifest(output / "manifest.json", manifest)
    report = validate_dataset(
        output,
        healthy,
        unhealthy,
        duration_seconds,
        with_ground_truth,
    )
    report["summary_rows"] = summary_rows
    report["metadata_rows"] = metadata_rows
    return report


def print_summary(report: dict, output: Path, seed: int) -> None:
    print(f"Generated {report['files']} snippets ({report['rows_per_file']} rows each) in {output}")
    print(f"Base seed: {seed}")
    print("Scenarios: " + json.dumps(report["scenario_counts"], sort_keys=True))
    print("Splits: " + json.dumps(report["split_counts"], sort_keys=True))
    for column in ("outside_temp_c", "outgoing_temp_c"):
        print(
            f"{column}: {report['sensor_min'][column]:.2f}.."
            f"{report['sensor_max'][column]:.2f} C"
        )
    print(
        f"Maximum one-second sensor change: "
        f"{report['maximum_one_second_change_c']:.2f} C"
    )
    if report["warnings"]:
        print(f"Review warnings: {len(report['warnings'])}")
    for label in ("healthy", "unhealthy"):
        class_rows = [row for row in report["metadata_rows"] if row["label"] == label]
        event_counts = [int(row["defrost_count"]) for row in class_rows]
        durations = [int(row["defrost_total_seconds"]) for row in class_rows]
        print(
            f"{label}: files={len(class_rows)}, defrost-count range="
            f"{min(event_counts, default=0)}..{max(event_counts, default=0)}, "
            f"defrost-seconds range={min(durations, default=0)}..{max(durations, default=0)}"
        )


def main() -> int:
    args = _arguments()
    try:
        report = generate_dataset(
            healthy=args.healthy,
            unhealthy=args.unhealthy,
            duration_seconds=args.duration_seconds,
            seed=args.seed,
            output=args.output,
            overwrite=args.overwrite,
            with_ground_truth=args.with_ground_truth,
        )
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        return 2
    print_summary(report, args.output, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
