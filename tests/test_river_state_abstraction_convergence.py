import argparse
import unittest

from tools.benchmark_river_state_abstraction_convergence import (
    aggregate_by_checkpoint,
    parse_checkpoints,
)


class RiverStateAbstractionConvergenceBenchmarkTests(unittest.TestCase):
    def test_checkpoint_parser_requires_strictly_increasing_positive_values(self):
        self.assertEqual(parse_checkpoints("1,10,100"), (1, 10, 100))
        for text in ("", "0,1", "2,1", "1,1", "a,2"):
            with self.assertRaises(argparse.ArgumentTypeError):
                parse_checkpoints(text)

    def test_aggregate_preserves_checkpoint_and_mapping_costs(self):
        rows = [
            {
                "mapping": "identity",
                "iterations": 10,
                "exploitability_over_pot": 0.10,
                "cumulative_training_seconds": 2.0,
                "iterations_per_second": 5.0,
                "nodes": 100,
                "mapping_build_seconds": 0.01,
            },
            {
                "mapping": "identity",
                "iterations": 10,
                "exploitability_over_pot": 0.20,
                "cumulative_training_seconds": 4.0,
                "iterations_per_second": 2.5,
                "nodes": 100,
                "mapping_build_seconds": 0.03,
            },
            {
                "mapping": "compressed",
                "iterations": 10,
                "exploitability_over_pot": 0.30,
                "cumulative_training_seconds": 1.0,
                "iterations_per_second": 10.0,
                "nodes": 40,
                "mapping_build_seconds": 0.20,
            },
            {
                "mapping": "identity",
                "iterations": 30,
                "exploitability_over_pot": 0.05,
                "cumulative_training_seconds": 6.0,
                "iterations_per_second": 5.0,
                "nodes": 100,
                "mapping_build_seconds": 0.01,
            },
        ]
        aggregate = aggregate_by_checkpoint(rows)
        self.assertEqual(tuple(aggregate), ("10", "30"))
        identity10 = next(
            row for row in aggregate["10"] if row["mapping"] == "identity"
        )
        self.assertEqual(identity10["fixtures"], 2)
        self.assertAlmostEqual(identity10["mean_exploitability_over_pot"], 0.15)
        self.assertAlmostEqual(identity10["median_exploitability_over_pot"], 0.15)
        self.assertAlmostEqual(identity10["max_exploitability_over_pot"], 0.20)
        self.assertAlmostEqual(identity10["mean_cumulative_training_seconds"], 3.0)
        self.assertAlmostEqual(identity10["mean_mapping_build_seconds"], 0.02)


if __name__ == "__main__":
    unittest.main()
