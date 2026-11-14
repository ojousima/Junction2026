#!/usr/bin/env python3
"""Plot feature signals and optional simulation-only ground truth."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


OVERVIEW_SCENARIOS = (
    "humid_near_freezing",
    "normal_multiple_defrosts",
    "normal_cycling",
    "variable_fan_and_load",
    "rapid_frost_accumulation",
    "ineffective_defrost",
    "slow_recovery",
    "progressive_frost_degradation",
)


def _plot_file(feature_path: Path, output_path: Path | None = None) -> Path:
    frame = pd.read_csv(feature_path)
    if not {"second", "outside_temp_c", "outgoing_temp_c"}.issubset(frame.columns):
        raise ValueError(f"{feature_path} does not have the expected feature columns.")
    truth_path = feature_path.parent / "ground_truth" / feature_path.name
    truth = pd.read_csv(truth_path) if truth_path.is_file() else None
    minutes = frame["second"].to_numpy(dtype=float) / 60.0
    outside = frame["outside_temp_c"].to_numpy(dtype=float)
    outgoing = frame["outgoing_temp_c"].to_numpy(dtype=float)

    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    axes[0].plot(minutes, outside, label="Outside intake air", linewidth=1.0)
    axes[0].plot(minutes, outgoing, label="Outdoor discharge probe", linewidth=1.0)
    axes[0].set_ylabel("Temperature (°C)")
    axes[0].legend(loc="best")
    axes[0].grid(alpha=0.25)
    axes[1].plot(minutes, outside - outgoing, color="tab:purple", linewidth=0.9)
    axes[1].axhline(0, color="black", linewidth=0.6)
    axes[1].set_ylabel("Outside − outgoing (°C)")
    axes[1].grid(alpha=0.25)
    axes[2].set_xlabel("Time (minutes)")
    axes[2].set_ylabel("Frost index (unitless)")
    axes[2].grid(alpha=0.25)

    if truth is not None:
        mode = truth["mode"].astype(str).to_numpy()
        frost = truth["frost_index"].to_numpy(dtype=float)
        colors = {
            "startup": "gold",
            "defrost": "tomato",
            "recovery": "lightskyblue",
            "off": "lightgray",
        }
        run_start = 0
        for index in range(1, len(mode) + 1):
            if index == len(mode) or mode[index] != mode[run_start]:
                color = colors.get(mode[run_start])
                if color:
                    axes[0].axvspan(
                        run_start / 60.0,
                        index / 60.0,
                        color=color,
                        alpha=0.18,
                        linewidth=0,
                    )
                run_start = index
        axes[2].plot(minutes, frost, color="tab:green", label="Latent frost index")
        axes[2].set_ylim(-0.02, 1.02)
        axes[2].legend(loc="upper left")
        axes[2].text(
            0.99,
            0.95,
            "SIMULATION GROUND TRUTH (not a sensor feature)",
            transform=axes[2].transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color="darkred",
        )
        axes[0].text(
            0.99,
            0.95,
            "Shading shows simulated mode",
            transform=axes[0].transAxes,
            ha="right",
            va="top",
            fontsize=8,
        )
    else:
        axes[2].text(
            0.5,
            0.5,
            "Ground truth not generated for this dataset",
            transform=axes[2].transAxes,
            ha="center",
        )

    fig.suptitle(feature_path.name)
    output = output_path or feature_path.with_suffix(".png")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=140)
    plt.close(fig)
    return output


def _plot_overview(data_dir: Path, output_path: Path | None = None) -> Path:
    metadata = pd.read_csv(data_dir / "metadata.csv")
    fig, axes = plt.subplots(4, 2, figsize=(15, 13), sharex=True, constrained_layout=True)
    for axis, scenario_name in zip(axes.flat, OVERVIEW_SCENARIOS):
        matches = metadata.loc[metadata["scenario"] == scenario_name]
        if matches.empty:
            axis.set_title(f"{scenario_name} (not present)")
            axis.axis("off")
            continue
        row = matches.iloc[0]
        frame = pd.read_csv(data_dir / row["filename"])
        minutes = frame["second"].to_numpy(dtype=float) / 60.0
        outside = frame["outside_temp_c"].to_numpy(dtype=float)
        outgoing = frame["outgoing_temp_c"].to_numpy(dtype=float)
        axis.plot(minutes, outside, label="Outside", linewidth=0.8)
        axis.plot(minutes, outgoing, label="Outgoing probe", linewidth=0.8)
        axis.set_title(f"{row['label']}: {scenario_name}", fontsize=9)
        axis.set_ylabel("°C")
        axis.grid(alpha=0.2)
        axis.legend(loc="best", fontsize=7)
        delta_axis = axis.twinx()
        delta_axis.plot(minutes, outside - outgoing, color="tab:purple", alpha=0.35, linewidth=0.65)
        delta_axis.set_ylabel("Δ °C", color="tab:purple", fontsize=7)
        delta_axis.tick_params(axis="y", labelsize=7, colors="tab:purple")
    for axis in axes[-1, :]:
        axis.set_xlabel("Time (minutes)")
    fig.suptitle("Synthetic scenario overview — purple line: outside − outgoing")
    output = output_path or data_dir / "overview.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, help="feature CSV to plot")
    parser.add_argument("--overview", action="store_true", help="plot representative scenarios")
    parser.add_argument("--data", type=Path, default=Path("data"), help="dataset directory for overview")
    parser.add_argument("--output", type=Path, help="PNG destination")
    args = parser.parse_args()
    if bool(args.file) == args.overview:
        parser.error("choose exactly one of --file or --overview")
    try:
        output = (
            _plot_file(args.file, args.output)
            if args.file
            else _plot_overview(args.data, args.output)
        )
    except (OSError, ValueError, KeyError) as exc:
        print(f"Preview failed: {exc}", file=sys.stderr)
        return 2
    print(f"Saved plot: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
