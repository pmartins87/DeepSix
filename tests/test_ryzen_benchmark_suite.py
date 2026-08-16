import tempfile
import unittest
from pathlib import Path

from tools.run_ryzen_benchmark_suite import PROFILES, _commands


class RyzenBenchmarkSuiteTests(unittest.TestCase):
    def test_profiles_are_strictly_ordered_by_primary_budgets(self):
        smoke = PROFILES["smoke"]
        engineering = PROFILES["engineering"]
        long = PROFILES["long"]
        self.assertLess(smoke.action_iterations, engineering.action_iterations)
        self.assertLess(engineering.action_iterations, long.action_iterations)
        self.assertLess(smoke.scalable_raise_iterations, engineering.scalable_raise_iterations)
        self.assertLess(engineering.scalable_raise_iterations, long.scalable_raise_iterations)
        self.assertLess(smoke.state_iterations, engineering.state_iterations)
        self.assertLess(engineering.state_iterations, long.state_iterations)
        self.assertEqual(smoke.state_fixture_limit, 1)
        self.assertIsNone(engineering.state_fixture_limit)
        self.assertIsNone(long.state_fixture_limit)

    def test_suite_contains_four_nonoverlapping_benchmark_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            commands = _commands(PROFILES["engineering"], output_dir)
            self.assertEqual(
                tuple(command.name for command in commands),
                (
                    "action_abstraction",
                    "scalable_multisize_raise",
                    "state_abstraction_battery",
                    "solver_algorithms",
                ),
            )
            outputs = tuple(command.output_name for command in commands)
            self.assertEqual(len(outputs), len(set(outputs)))
            for command in commands:
                self.assertIn("--output", command.argv)
                self.assertTrue(str(output_dir) in " ".join(command.argv))

    def test_smoke_limits_expensive_batteries_to_one_fixture(self):
        with tempfile.TemporaryDirectory() as temporary:
            commands = _commands(PROFILES["smoke"], Path(temporary))
            state = next(command for command in commands if command.name == "state_abstraction_battery")
            solver = next(command for command in commands if command.name == "solver_algorithms")
            self.assertIn("--fixture-limit", state.argv)
            self.assertIn("--fixture-limit", solver.argv)
            self.assertIn("1", state.argv)
            self.assertIn("1", solver.argv)

    def test_engineering_and_long_do_not_silently_limit_fixture_batteries(self):
        with tempfile.TemporaryDirectory() as temporary:
            for profile_name in ("engineering", "long"):
                commands = _commands(PROFILES[profile_name], Path(temporary))
                for name in ("state_abstraction_battery", "solver_algorithms"):
                    command = next(item for item in commands if item.name == name)
                    self.assertNotIn("--fixture-limit", command.argv)


if __name__ == "__main__":
    unittest.main()
