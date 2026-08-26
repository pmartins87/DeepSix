import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "benchmark_simulator_throughput",
    ROOT / "tools" / "benchmark_simulator_throughput.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SimulatorThroughputBenchmarkTests(unittest.TestCase):
    def test_player_count_parser(self):
        self.assertEqual(MODULE.parse_player_counts("2,4,6"), (2, 4, 6))
        with self.assertRaises(Exception):
            MODULE.parse_player_counts("1,6")
        with self.assertRaises(Exception):
            MODULE.parse_player_counts("2,2")

    def test_tiny_case_reports_positive_throughput_and_expected_decisions(self):
        result = MODULE.run_case(
            player_count=2,
            hands=3,
            stake_cents=2,
            seed_base=1,
        )
        self.assertEqual(result["player_count"], 2)
        self.assertEqual(result["hands"], 3)
        self.assertGreater(result["elapsed_seconds"], 0)
        self.assertGreater(result["hands_per_second"], 0)
        self.assertGreater(result["decisions_per_second"], 0)
        self.assertGreater(result["mean_decisions_per_hand"], 0)
        self.assertGreater(result["mean_gross_pot_units"], 0)
        self.assertGreaterEqual(result["mean_rake_units"], 0)


if __name__ == "__main__":
    unittest.main()
