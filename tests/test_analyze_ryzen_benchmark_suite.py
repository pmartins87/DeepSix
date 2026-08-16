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
    def make_run(self, root: Path):
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
                    },
                    {
                        "mapping": "compressed",
                        "fixtures": 2,
                        "mean_exploitability_over_pot": 0.02,
                        "max_exploitability_over_pot": 0.03,
                        "mean_iterations_per_second": 180.0,
                        "mean_nodes": 40.0,
                    },
                    {
                        "mapping": "dominated",
                        "fixtures": 2,
                        "mean_exploitability_over_pot": 0.03,
                        "max_exploitability_over_pot": 0.04,
                        "mean_iterations_per_second": 150.0,
                        "mean_nodes": 60.0,
                    },
                ]
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
            "suite": "deepsix_ryzen_benchmark_suite_v1",
            "profile": "engineering",
            "git_commit": "abc123",
            "machine": {"processor": "fixture"},
            "success": True,
            "commands": commands,
        }
        write_json(root / "manifest.json", manifest)

    def test_verified_analysis_finds_expected_pareto_candidates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_run(root)
            result = analyze_run(root)
            self.assertTrue(result["evidence_sha256_verified"])
            self.assertEqual(result["solver"]["final_checkpoint"], 300)
            self.assertEqual(result["solver"]["pareto_candidates"], ["rmplus"])
            self.assertIn("identity", result["state_abstraction"]["pareto_candidates"])
            self.assertIn("compressed", result["state_abstraction"]["pareto_candidates"])
            self.assertNotIn("dominated", result["state_abstraction"]["pareto_candidates"])

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
