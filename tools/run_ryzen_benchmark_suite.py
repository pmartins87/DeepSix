#!/usr/bin/env python3
"""Run a reproducible DeepSix engineering benchmark suite.

The suite is designed for the project's Ryzen-class workstation but works on any
machine. It never guesses workstation performance from CI. Instead it records the
exact Git commit, Python/platform metadata, command lines, elapsed wall time and
SHA-256 of every JSON result in one durable manifest.

Profiles are explicit:

* smoke       - wiring check only;
* engineering - first useful comparative run;
* long        - larger convergence/performance run.

Manifest contract v3 adds pure simulator throughput to the five v2 strategy
benchmark outputs. The analyzer remains backward-compatible with v1 and v2.

The suite does not promote a strategy automatically. It packages auditable
evidence so action/state abstraction and solver choices can be made from measured
error/cost trade-offs on the target machine.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE_VERSION = "deepsix_ryzen_benchmark_suite_v3"


class RyzenSuiteError(RuntimeError):
    pass


@dataclass(frozen=True)
class BenchmarkCommand:
    name: str
    argv: tuple[str, ...]
    output_name: str


@dataclass(frozen=True)
class Profile:
    action_iterations: int
    scalable_raise_iterations: int
    state_iterations: int
    state_fixture_limit: int | None
    state_convergence_checkpoints: str
    state_convergence_fixture_limit: int | None
    solver_checkpoints: str
    solver_fixture_limit: int | None
    simulator_hands: int


PROFILES = {
    "smoke": Profile(
        action_iterations=10,
        scalable_raise_iterations=10,
        state_iterations=1,
        state_fixture_limit=1,
        state_convergence_checkpoints="1,2",
        state_convergence_fixture_limit=1,
        solver_checkpoints="2",
        solver_fixture_limit=1,
        simulator_hands=20,
    ),
    "engineering": Profile(
        action_iterations=5000,
        scalable_raise_iterations=3000,
        state_iterations=1000,
        state_fixture_limit=None,
        state_convergence_checkpoints="100,300,1000",
        state_convergence_fixture_limit=None,
        solver_checkpoints="100,300,1000,3000",
        solver_fixture_limit=None,
        simulator_hands=10_000,
    ),
    "long": Profile(
        action_iterations=30000,
        scalable_raise_iterations=15000,
        state_iterations=5000,
        state_fixture_limit=None,
        state_convergence_checkpoints="300,1000,3000,5000",
        state_convergence_fixture_limit=None,
        solver_checkpoints="300,1000,3000,10000",
        solver_fixture_limit=None,
        simulator_hands=100_000,
    ),
}


def _git(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RyzenSuiteError(f"git {' '.join(args)} failed") from exc
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _commands(profile: Profile, output_dir: Path) -> tuple[BenchmarkCommand, ...]:
    python = sys.executable

    state_args = [
        python,
        "tools/benchmark_river_state_abstraction_battery.py",
        "--iterations",
        str(profile.state_iterations),
        "--bucket-counts",
        "6,4,2",
        "--output",
        str(output_dir / "state_abstraction_battery.json"),
    ]
    if profile.state_fixture_limit is not None:
        state_args.extend(["--fixture-limit", str(profile.state_fixture_limit)])

    convergence_args = [
        python,
        "tools/benchmark_river_state_abstraction_convergence.py",
        "--checkpoints",
        profile.state_convergence_checkpoints,
        "--bucket-count",
        "4",
        "--output",
        str(output_dir / "state_abstraction_convergence.json"),
    ]
    if profile.state_convergence_fixture_limit is not None:
        convergence_args.extend(
            ["--fixture-limit", str(profile.state_convergence_fixture_limit)]
        )

    solver_args = [
        python,
        "tools/benchmark_river_solver_algorithms.py",
        "--checkpoints",
        profile.solver_checkpoints,
        "--rmplus-delay",
        "50" if profile.solver_checkpoints != "2" else "0",
        "--output",
        str(output_dir / "solver_algorithms.json"),
    ]
    if profile.solver_fixture_limit is not None:
        solver_args.extend(["--fixture-limit", str(profile.solver_fixture_limit)])

    return (
        BenchmarkCommand(
            "action_abstraction",
            (
                python,
                "tools/benchmark_river_action_abstraction.py",
                "--iterations",
                str(profile.action_iterations),
                "--output",
                str(output_dir / "action_abstraction.json"),
            ),
            "action_abstraction.json",
        ),
        BenchmarkCommand(
            "scalable_multisize_raise",
            (
                python,
                "tools/benchmark_river_multisize_raise_scalable.py",
                "--iterations",
                str(profile.scalable_raise_iterations),
                "--sizes",
                "2,4,8,12",
                "--raise-to",
                "18",
                "--output",
                str(output_dir / "scalable_multisize_raise.json"),
            ),
            "scalable_multisize_raise.json",
        ),
        BenchmarkCommand(
            "state_abstraction_battery",
            tuple(state_args),
            "state_abstraction_battery.json",
        ),
        BenchmarkCommand(
            "state_abstraction_convergence",
            tuple(convergence_args),
            "state_abstraction_convergence.json",
        ),
        BenchmarkCommand(
            "solver_algorithms",
            tuple(solver_args),
            "solver_algorithms.json",
        ),
        BenchmarkCommand(
            "simulator_throughput",
            (
                python,
                "tools/benchmark_simulator_throughput.py",
                "--hands",
                str(profile.simulator_hands),
                "--players",
                "2,4,6",
                "--output",
                str(output_dir / "simulator_throughput.json"),
            ),
            "simulator_throughput.json",
        ),
    )


def _machine_metadata() -> dict:
    cpu_count = os.cpu_count()
    return {
        "machine": platform.machine(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "logical_cpu_count": cpu_count,
    }


def _run_one(command: BenchmarkCommand, output_dir: Path) -> dict:
    log_path = output_dir / f"{command.name}.stdout.log"
    started = dt.datetime.now(dt.timezone.utc)
    start = time.perf_counter()
    completed = subprocess.run(
        command.argv,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start
    log_path.write_text(
        completed.stdout
        + ("\n--- STDERR ---\n" + completed.stderr if completed.stderr else ""),
        encoding="utf-8",
    )
    output_path = output_dir / command.output_name
    record = {
        "name": command.name,
        "argv": list(command.argv),
        "started_utc": started.isoformat(),
        "elapsed_seconds": elapsed,
        "returncode": completed.returncode,
        "stdout_log": log_path.name,
        "stdout_log_sha256": _sha256(log_path),
        "output": output_path.name,
        "output_exists": output_path.exists(),
    }
    if output_path.exists():
        record["output_sha256"] = _sha256(output_path)
    if completed.returncode != 0:
        raise RyzenSuiteError(
            f"benchmark {command.name} failed with exit code {completed.returncode}; "
            f"see {log_path}"
        )
    if not output_path.exists():
        raise RyzenSuiteError(
            f"benchmark {command.name} succeeded but did not create {output_path}"
        )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES),
        default="engineering",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "benchmark_runs",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow benchmark execution with uncommitted repository changes",
    )
    args = parser.parse_args()

    commit = _git(["rev-parse", "HEAD"])
    dirty_lines = _git(["status", "--porcelain"])
    if dirty_lines and not args.allow_dirty:
        raise RyzenSuiteError(
            "repository has uncommitted changes; commit/stash them or pass --allow-dirty"
        )

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_root.resolve() / f"{timestamp}_{args.profile}_{commit[:12]}"
    output_dir.mkdir(parents=True, exist_ok=False)

    profile = PROFILES[args.profile]
    manifest = {
        "suite": SUITE_VERSION,
        "profile": args.profile,
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repository_root": str(ROOT),
        "git_commit": commit,
        "git_dirty": bool(dirty_lines),
        "git_status_porcelain": dirty_lines.splitlines() if dirty_lines else [],
        "machine": _machine_metadata(),
        "profile_parameters": {
            "action_iterations": profile.action_iterations,
            "scalable_raise_iterations": profile.scalable_raise_iterations,
            "state_iterations": profile.state_iterations,
            "state_fixture_limit": profile.state_fixture_limit,
            "state_convergence_checkpoints": profile.state_convergence_checkpoints,
            "state_convergence_fixture_limit": profile.state_convergence_fixture_limit,
            "solver_checkpoints": profile.solver_checkpoints,
            "solver_fixture_limit": profile.solver_fixture_limit,
            "simulator_hands": profile.simulator_hands,
        },
        "commands": [],
    }
    manifest_path = output_dir / "manifest.json"

    try:
        for command in _commands(profile, output_dir):
            record = _run_one(command, output_dir)
            manifest["commands"].append(record)
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except Exception:
        manifest["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        manifest["success"] = False
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise

    manifest["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest["success"] = True
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output_dir)
    print(f"manifest_sha256={_sha256(manifest_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
