import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_ryzen_benchmark_suite import RyzenAnalysisError, analyze_run


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, payload):
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


class AnalyzeRyzenBenchmarkSuiteTests(unittest.TestCase):
    def make_run(
        self,
        root: Path,
        suite: str = "deepsix_ryzen_benchmark_suite_v2",
    ):
        outputs = {
            "action_abstraction": {
                "cases": [{"sizes": [4], "nodes": 10}, {"sizes": [4, 8], "nodes": 20}]
            },
            "scalable_multisize_raise": {
                "cases": [{"bet_sizes": [4], "nodes": 12}, {"bet_sizes": [4, 8], "nodes": 24}]
            },
            "state_abstraction_battery": {
                "aggregate": [
                    {
                        "mapping": "identity",
                        "fixtures": 2,
                        "mean_exploitability_over_pot": 0.01,
                        "max_exploitability_over_pot": 0.02,
                        "mean_iterations_per_second": 100.0,
                        "mean_nodes": 100.0,
                        "mean_mapping_build_seconds": 0.01,
                        "max_mapping_build_seconds": 0.02,
                    },
                    {
                        "mapping": "compressed",
                        "fixtures": 2,
                        "mean_exploitability_over_pot": 0.02,
                        "max_exploitability_over_pot": 0.03,
                        "mean_iterations_per_second": 180.0,
                        "mean_nodes": 40.0,
                        "mean_mapping_build_seconds": 0.2,
                        "max_mapping_build_seconds": 0.3,
                    },
                    {
                        "mapping": "dominated",
                        "fixtures": 2,
                        "mean_exploitability_over_pot": 0.03,
                        "max_exploitability_over_pot": 0.04,
                        "mean_iterations_per_second": 150.0,
                        "mean_nodes": 60.0,
                        "mean_mapping_build_seconds": 0.1,
                        "max_mapping_build_seconds": 0.15,
                    },
                ]
            },
            "state_abstraction_convergence": {
                "aggregate_by_checkpoint": {
                    "100": [
                        {
                            "mapping": "identity",
                            "fixtures": 2,
                            "iterations": 100,
                            "mean_exploitability_over_pot": 0.03,
                            "median_exploitability_over_pot": 0.03,
                            "max_exploitability_over_pot": 0.04,
                            "mean_cumulative_training_seconds": 10.0,
                            "mean_iterations_per_second": 10.0,
                            "mean_nodes": 100.0,
                            "mean_mapping_build_seconds": 0.01,
                        },
                        {
                            "mapping": "compressed",
                            "fixtures": 2,
                            "iterations": 100,
                            "mean_exploitability_over_pot": 0.04,
                            "median_exploitability_over_pot": 0.04,
                            "max_exploitability_over_pot": 0.05,
                            "mean_cumulative_training_seconds": 5.0,
                            "mean_iterations_per_second": 20.0,
                            "mean_nodes": 40.0,
                            "mean_mapping_build_seconds": 0.2,
                        },
                        {
                            "mapping": "dominated",
                            "fixtures": 2,
                            "iterations": 100,
                            "mean_exploitability_over_pot": 0.05,
                            "median_exploitability_over_pot": 0.05,
                            "max_exploitability_over_pot": 0.06,
                            "mean_cumulative_training_seconds": 7.0,
                            "mean_iterations_per_second": 14.0,
                            "mean_nodes": 60.0,
                            "mean_mapping_build_seconds": 0.1,
                        },
                    ],
                    "300": [
                        {
                            "mapping": "identity",
                            "fixtures": 2,
                            "iterations": 300,
                            "mean_exploitability_over_pot": 0.01,
                            "median_exploitability_over_pot": 0.01,
                            "max_exploitability_over_pot": 0.02,
                            "mean_cumulative_training_seconds": 30.0,
                            "mean_iterations_per_second": 10.0,
                            "mean_nodes": 100.0,
                            "mean_mapping_build_seconds": 0.01,
                        },
                        {
                            "mapping": "compressed",
                            "fixtures": 2,
                            "iterations": 300,
                            "mean_exploitability_over_pot": 0.02,
                            "median_exploitability_over_pot": 0.02,
                            "max_exploitability_over_pot": 0.03,
                            "mean_cumulative_training_seconds": 15.0,
                            "mean_iterations_per_second": 20.0,
                            "mean_nodes": 40.0,
                            "mean_mapping_build_seconds": 0.2,
                        },
                        {
                            "mapping": "dominated",
                            "fixtures": 2,
                            "iterations": 300,
                            "mean_exploitability_over_pot": 0.03,
                            "median_exploitability_over_pot": 0.03,
                            "max_exploitability_over_pot": 0.04,
                            "mean_cumulative_training_seconds": 20.0,
                            "mean_iterations_per_second": 15.0,
                            "mean_nodes": 60.0,
                            "mean_mapping_build_seconds": 0.1,
                        },
                    ],
                }
            },
            "solver_algorithms": {
                "rows": [
                    {
                        "algorithm": "cfr",
                        "iterations": 100,
                        "training_seconds": 10.0,
                        "iterations_per_second": 10.0,
                        "exploitability_over_pot": 0.02,
                    },
                    {
                        "algorithm": "rmplus",
                        "iterations": 100,
                        "training_seconds": 8.0,
                        "iterations_per_second": 12.5,
                        "exploitability_over_pot": 0.015,
                    },
                    {
                        "algorithm": "cfr",
                        "iterations": 300,
                        "training_seconds": 30.0,
                        "iterations_per_second": 10.0,
                        "exploitability_over_pot": 0.01,
                    },
                    {
                        "algorithm": "rmplus",
                        "iterations": 300,
                        "training_seconds": 24.0,
                        "iterations_per_second": 12.5,
                        "exploitability_over_pot": 0.008,
                    },
                ]
            },
        }
        if suite == "deepsix_ryzen_benchmark_suite_v1":
            outputs.pop("state_abstraction_convergence")

        commands = []
        for name, payload in outputs.items():
            output = root / f"{name}.json"
            log = root / f"{name}.log"
            write_json(output, payload)
            log.write_text(f"{name} ok\n", encoding="utf-8")
            commands.append(
                {
                    "name": name,
                    "output": output.name,
                    "output_sha256": sha(output),
                    "stdout_log": log.name,
                    "stdout_log_sha256": sha(log),
                }
            )
        manifest = {
            "suite": suite,
            "profile": "engineering",
            "git_commit": "abc123",
            "machine": {"processor": "fixture"},
            "success": True,
            "commands": commands,
        }
        write_json(root / "manifest.json", manifest)

    def test_verified_v2_analysis_finds_expected_pareto_candidates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_run(root)
            result = analyze_run(root)
            self.assertTrue(result["evidence_sha256_verified"])
            self.assertEqual(result["analysis"], "deepsix_ryzen_benchmark_analysis_v2")
            self.assertEqual(result["source_suite"], "deepsix_ryzen_benchmark_suite_v2")
            self.assertEqual(result["solver"]["final_checkpoint"], 300)
            self.assertEqual(result["solver"]["pareto_candidates"], ["rmplus"])
            self.assertIn("identity", result["state_abstraction"]["pareto_candidates"])
            self.assertIn("compressed", result["state_abstraction"]["pareto_candidates"])
            self.assertNotIn("dominated", result["state_abstraction"]["pareto_candidates"])

            convergence = result["state_abstraction_convergence"]["checkpoints"]
            self.assertEqual(tuple(convergence), ("100", "300"))
            self.assertIn("identity", convergence["300"]["pareto_candidates"])
            self.assertIn("compressed", convergence["300"]["pareto_candidates"])
            self.assertNotIn("dominated", convergence["300"]["pareto_candidates"])

    def test_legacy_v1_manifest_remains_verifiable_and_analyzable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_run(root, suite="deepsix_ryzen_benchmark_suite_v1")
            result = analyze_run(root)
            self.assertTrue(result["evidence_sha256_verified"])
            self.assertEqual(result["source_suite"], "deepsix_ryzen_benchmark_suite_v1")
            self.assertIsNone(result["state_abstraction_convergence"])
            self.assertIn("legacy_note", result)
            self.assertEqual(result["solver"]["final_checkpoint"], 300)

    def test_tampered_output_is_rejected_before_analysis(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_run(root)
            path = root / "solver_algorithms.json"
            path.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(RyzenAnalysisError):
                analyze_run(root)

    def test_unsuccessful_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_run(root)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["success"] = False
            write_json(manifest_path, manifest)
            with self.assertRaises(RyzenAnalysisError):
                analyze_run(root)


if __name__ == "__main__":
    unittest.main()
