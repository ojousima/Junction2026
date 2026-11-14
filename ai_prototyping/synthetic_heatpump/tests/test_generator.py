from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from heatpump_sim.config import DEFAULT_DURATION_SECONDS, FEATURE_COLUMNS
from heatpump_sim.scenarios import HEALTHY_SCENARIOS, UNHEALTHY_SCENARIOS
from heatpump_sim.validation import validate_dataset
from generate import generate_dataset


class SyntheticGeneratorTests(unittest.TestCase):
    def test_scenario_catalog_covers_the_brief(self):
        self.assertEqual(
            {scenario.name for scenario in HEALTHY_SCENARIOS},
            {
                "steady_mild",
                "cold_dry",
                "humid_near_freezing",
                "normal_multiple_defrosts",
                "normal_startup",
                "normal_cycling",
                "changing_weather",
                "variable_fan_and_load",
            },
        )
        self.assertEqual(
            {scenario.name for scenario in UNHEALTHY_SCENARIOS},
            {
                "rapid_frost_accumulation",
                "frequent_defrost",
                "prolonged_defrost",
                "incomplete_defrost",
                "ineffective_defrost",
                "slow_recovery",
                "frost_related_airflow_restriction",
                "progressive_frost_degradation",
            },
        )

    def test_dataset_schema_metadata_and_ground_truth_are_consistent(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dataset"
            report = generate_dataset(8, 8, DEFAULT_DURATION_SECONDS, 12, output, True, True)
            self.assertEqual(report["files"], 16)
            features = pd.read_csv(output / "healthy_0001.csv")
            self.assertEqual(tuple(features.columns), FEATURE_COLUMNS)
            self.assertEqual(len(features), 3600)
            self.assertTrue(np.issubdtype(features["second"].dtype, np.integer))
            self.assertTrue(np.isfinite(features[["outside_temp_c", "outgoing_temp_c"]]).all().all())
            self.assertTrue(np.array_equal(features["second"], np.arange(3600)))
            metadata = pd.read_csv(output / "metadata.csv")
            self.assertEqual(set(metadata["label"]), {"healthy", "unhealthy"})
            self.assertEqual(set(metadata["split"]), {"train", "validation", "test"})
            self.assertTrue(metadata["fault_severity"].between(0.0, 1.0).all())
            self.assertTrue(metadata["heating_load"].between(0.0, 1.0).all())
            self.assertTrue(
                metadata.loc[metadata["label"] == "healthy", "ambient_mean_c"].max()
                >= metadata.loc[metadata["label"] == "unhealthy", "ambient_mean_c"].min()
            )
            self.assertTrue(
                metadata.loc[metadata["label"] == "unhealthy", "ambient_mean_c"].max()
                >= metadata.loc[metadata["label"] == "healthy", "ambient_mean_c"].min()
            )
            for row in metadata.to_dict(orient="records"):
                features = pd.read_csv(output / row["filename"])
                self.assertEqual(tuple(features.columns), FEATURE_COLUMNS)
                self.assertNotIn("frost_index", features.columns)
                truth_path = output / "ground_truth" / row["filename"]
                truth = pd.read_csv(truth_path)
                defrost = truth["mode"].eq("defrost")
                starts = defrost & ~defrost.shift(fill_value=False)
                self.assertEqual(int(starts.sum()), int(row["defrost_count"]))
                self.assertEqual(int(defrost.sum()), int(row["defrost_total_seconds"]))
            self.assertTrue(any(metadata.loc[metadata["label"] == "healthy", "defrost_count"] > 0))
            self.assertTrue(any(metadata.loc[metadata["label"] == "unhealthy", "defrost_count"] == 0))

    def test_seed_reproducibility_and_distinct_seed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            other_seed = root / "other"
            generate_dataset(2, 2, 180, 51, first, True, True)
            generate_dataset(2, 2, 180, 51, second, True, True)
            generate_dataset(2, 2, 180, 52, other_seed, True, True)
            for filename in ("healthy_0001.csv", "unhealthy_0002.csv", "metadata.csv"):
                self.assertEqual(
                    (first / filename).read_bytes(),
                    (second / filename).read_bytes(),
                )
            self.assertNotEqual(
                (first / "healthy_0001.csv").read_bytes(),
                (other_seed / "healthy_0001.csv").read_bytes(),
            )

    def test_overwrite_is_required_before_replacing_generated_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "healthy_0001.csv").write_text("keep\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                generate_dataset(1, 0, 30, 7, output)
            self.assertEqual(
                (output / "healthy_0001.csv").read_text(encoding="utf-8"),
                "keep\n",
            )

    def test_standard_duration_and_feature_format(self):
        self.assertEqual(DEFAULT_DURATION_SECONDS, 3600)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            generate_dataset(1, 1, 120, 23, output, True, False)
            with (output / "healthy_0001.csv").open(newline="", encoding="utf-8") as stream:
                reader = csv.reader(stream)
                self.assertEqual(tuple(next(reader)), FEATURE_COLUMNS)
                self.assertEqual(len(next(reader)), 3)
            self.assertFalse((output / "ground_truth").exists())

    def test_validator_reports_physical_ranges_without_mutating_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            generate_dataset(1, 1, 120, 24, output, True, True)
            before = (output / "healthy_0001.csv").read_bytes()
            report = validate_dataset(output, 1, 1, 120, True)
            self.assertIn("sensor_min", report)
            self.assertEqual(before, (output / "healthy_0001.csv").read_bytes())


if __name__ == "__main__":
    unittest.main()
