import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "external_sampling_repro_digest.py"


def run_digest(hash_seed: str):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fixture-index",
            "0",
            "--iterations",
            "80",
            "--seed",
            "20260826",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


class ExternalSamplingFreshProcessReproTests(unittest.TestCase):
    def test_fresh_process_and_hash_seed_do_not_change_semantic_digest(self):
        first = run_digest("1")
        second = run_digest("987654321")
        self.assertEqual(first["semantic_sha256"], second["semantic_sha256"])
        self.assertEqual(first["checkpoint_sha256"], second["checkpoint_sha256"])
        self.assertEqual(first["policy"], second["policy"])
        self.assertEqual(first["exploitability_hex"], second["exploitability_hex"])


if __name__ == "__main__":
    unittest.main()
