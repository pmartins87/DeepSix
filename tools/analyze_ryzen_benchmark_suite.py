#!/usr/bin/env python3
"""Verify and summarize one DeepSix Ryzen benchmark-suite run.

The analyzer is intentionally conservative. It first verifies the SHA-256
recorded in ``manifest.json`` for every benchmark JSON and stdout log. Only then
does it derive comparison summaries.

Supported manifest contracts:

* v1 — four original benchmark outputs;
* v2 — adds state-abstraction convergence curves.

It can compute Pareto candidates where metrics are genuinely comparable:

* solver algorithms use the same exact game/oracle at the same checkpoint;
* private-state abstractions use the same action game and unabstracted exact BR;
* state-abstraction convergence compares methods at the same cumulative
  iteration checkpoint while preserving measured wall-clock as a cost axis.

It does **not** rank different action spaces by exploitability, because a richer
action set changes the game in which exploitability is defined. Those results
are reported as structure/throughput evidence only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path


SUPPORTED_SUITES = {
    "deepsix_ryzen_benchmark_suite_v1",
    "deepsix_ryzen_benchmark_suite_v2",
}


class RyzenAnalysisError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified_manifest(run_dir: Path) -> dict:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RyzenAnalysisError("manifest.json not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("suite") not in SUPPORTED_SUITES:
        raise RyzenAnalysisError("unsupported benchmark-suite manifest")
    if manifest.get("success") is not True:
        raise RyzenAnalysisError("benchmark suite is not marked successful")

    commands = manifest.get("commands")
    if not isinstance(commands, list) or not commands:
        raise RyzenAnalysisError("manifest has no benchmark commands")
    for record in commands:
        for path_key, hash_key in (
            ("output", "output_sha256"),
            ("stdout_log", "stdout_log_sha256"),
        ):
            relative = record.get(path_key)
            expected = record.get(hash_key)
            if not isinstance(relative, str) or not isinstance(expected, str):
                raise RyzenAnalysisError(
                    f"manifest record {record.get('name')} lacks {path_key}/{hash_key}"
                )
            path = run_dir / relative
            if not path.is_file():
                raise RyzenAnalysisError(f"missing benchmark evidence file: {relative}")
            actual = sha256_file(path)
            if actual != expected:
                raise RyzenAnalysisError(
                    f"SHA-256 mismatch for {relative}: {actual} != {expected}"
                )
    return manifest


def _command_outputs(manifest: dict, run_dir: Path) -> dict[str, dict]:
    outputs = {}
    for record in manifest["commands"]:
        name = record["name"]
        path = run_dir / record["output"]
        outputs[name] = json.loads(path.read_text(encoding="utf-8"))
    return outputs


def _pareto(items: list[dict], dimensions: tuple[tuple[str, bool], ...]) -> list[str]:
    """Return names not dominated. bool=True means larger is better."""
    winners = []
    for candidate in items:
        dominated = False
        for other in items:
            if other is candidate:
                continue
            no_worse = True
            strictly_better = False
            for key, larger_is_better in dimensions:
                a = candidate[key]
                b = other[key]
                if larger_is_better:
                    if b < a:
                        no_worse = False
                        break
                    if b > a:
                        strictly_better = True
                else:
                    if b > a:
                        no_worse = False
                        break
                    if b < a:
                        strictly_better = True
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            winners.append(candidate["name"])
    return winners


def analyze_solver(payload: dict) -> dict:
    rows = payload.get("rows", [])
    if not rows:
        raise RyzenAnalysisError("solver benchmark has no rows")
    final_checkpoint = max(int(row["iterations"]) for row in rows)
    algorithms = []
    for algorithm in dict.fromkeys(row["algorithm"] for row in rows):
        selected = [
            row
            for row in rows
            if row["algorithm"] == algorithm
            and int(row["iterations"]) == final_checkpoint
        ]
        if not selected:
            continue
        algorithms.append(
            {
                "name": algorithm,
                "fixtures": len(selected),
                "mean_exploitability_over_pot": statistics.fmean(
                    row["exploitability_over_pot"] for row in selected
                ),
                "max_exploitability_over_pot": max(
                    row["exploitability_over_pot"] for row in selected
                ),
                "mean_training_seconds": statistics.fmean(
                    row["training_seconds"] for row in selected
                ),
                "mean_iterations_per_second": statistics.fmean(
                    row["iterations_per_second"] for row in selected
                ),
            }
        )
    pareto = _pareto(
        algorithms,
        (
            ("mean_exploitability_over_pot", False),
            ("max_exploitability_over_pot", False),
            ("mean_training_seconds", False),
        ),
    )
    return {
        "final_checkpoint": final_checkpoint,
        "algorithms": algorithms,
        "pareto_candidates": pareto,
        "promotion_rule": (
            "Pareto membership is necessary evidence, not automatic promotion; "
            "repeat close results and inspect earlier checkpoints/worst fixtures"
        ),
    }


def analyze_state_abstraction(payload: dict) -> dict:
    aggregate = payload.get("aggregate", [])
    if not aggregate:
        raise RyzenAnalysisError("state-abstraction benchmark has no aggregate rows")
    methods = [
        {
            "name": row["mapping"],
            "fixtures": row["fixtures"],
            "mean_exploitability_over_pot": row["mean_exploitability_over_pot"],
            "max_exploitability_over_pot": row["max_exploitability_over_pot"],
            "mean_nodes": row["mean_nodes"],
            "mean_iterations_per_second": row["mean_iterations_per_second"],
            "mean_mapping_build_seconds": row.get("mean_mapping_build_seconds", 0.0),
            "max_mapping_build_seconds": row.get("max_mapping_build_seconds", 0.0),
        }
        for row in aggregate
    ]
    pareto = _pareto(
        methods,
        (
            ("mean_exploitability_over_pot", False),
            ("max_exploitability_over_pot", False),
            ("mean_nodes", False),
            ("mean_iterations_per_second", True),
        ),
    )
    return {
        "methods": methods,
        "pareto_candidates": pareto,
        "mapping_build_cost_note": (
            "mapping build time is reported separately and is not currently a "
            "Pareto dimension because it is a one-time/precompute cost that may "
            "amortize differently from CFR training throughput"
        ),
        "promotion_rule": (
            "do not choose only by mean; inspect worst-case texture, mapping "
            "construction cost and repeat near-frontier methods before changing "
            "blueprint abstraction"
        ),
    }


def analyze_state_convergence(payload: dict) -> dict:
    aggregate = payload.get("aggregate_by_checkpoint")
    if not isinstance(aggregate, dict) or not aggregate:
        raise RyzenAnalysisError(
            "state-abstraction convergence benchmark has no checkpoint aggregate"
        )

    checkpoints = {}
    for checkpoint_text in sorted(aggregate, key=lambda value: int(value)):
        source_rows = aggregate[checkpoint_text]
        if not isinstance(source_rows, list) or not source_rows:
            raise RyzenAnalysisError(
                f"state convergence checkpoint {checkpoint_text} has no methods"
            )
        methods = []
        for row in source_rows:
            methods.append(
                {
                    "name": row["mapping"],
                    "fixtures": row["fixtures"],
                    "iterations": int(row["iterations"]),
                    "mean_exploitability_over_pot": row[
                        "mean_exploitability_over_pot"
                    ],
                    "max_exploitability_over_pot": row[
                        "max_exploitability_over_pot"
                    ],
                    "mean_cumulative_training_seconds": row[
                        "mean_cumulative_training_seconds"
                    ],
                    "mean_iterations_per_second": row[
                        "mean_iterations_per_second"
                    ],
                    "mean_nodes": row["mean_nodes"],
                    "mean_mapping_build_seconds": row.get(
                        "mean_mapping_build_seconds", 0.0
                    ),
                }
            )
        pareto = _pareto(
            methods,
            (
                ("mean_exploitability_over_pot", False),
                ("max_exploitability_over_pot", False),
                ("mean_cumulative_training_seconds", False),
                ("mean_nodes", False),
            ),
        )
        checkpoints[str(int(checkpoint_text))] = {
            "methods": methods,
            "pareto_candidates": pareto,
        }

    return {
        "checkpoints": checkpoints,
        "comparison_boundary": (
            "all methods within a checkpoint have the same cumulative iteration "
            "count and exact oracle, but not equal wall-clock; measured cumulative "
            "training seconds are therefore retained as a Pareto cost axis"
        ),
        "mapping_build_cost_note": (
            "mapping construction remains reported separately because it is a "
            "one-time/precompute cost rather than per-iteration CFR cost"
        ),
        "promotion_rule": (
            "prefer methods that remain near the frontier across multiple "
            "checkpoints and fixtures; no single checkpoint can promote an "
            "abstraction family"
        ),
    }


def analyze_action_structure(payload: dict) -> dict:
    cases = payload.get("cases", [])
    if not cases:
        raise RyzenAnalysisError("action benchmark has no cases")
    return {
        "cases": cases,
        "comparison_boundary": (
            "different action spaces are not ranked by exploitability; use these "
            "rows to quantify tree width, action slots and throughput"
        ),
    }


def analyze_run(run_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    manifest = load_verified_manifest(run_dir)
    outputs = _command_outputs(manifest, run_dir)
    suite = manifest["suite"]
    legacy_required = {
        "action_abstraction",
        "scalable_multisize_raise",
        "state_abstraction_battery",
        "solver_algorithms",
    }
    if suite == "deepsix_ryzen_benchmark_suite_v1":
        required = legacy_required
    elif suite == "deepsix_ryzen_benchmark_suite_v2":
        required = legacy_required | {"state_abstraction_convergence"}
    else:  # guarded by load_verified_manifest; defensive for direct reuse.
        raise RyzenAnalysisError("unsupported benchmark-suite manifest")

    if set(outputs) != required:
        raise RyzenAnalysisError(
            f"unexpected benchmark outputs for {suite}: {sorted(outputs)}"
        )

    result = {
        "analysis": "deepsix_ryzen_benchmark_analysis_v2",
        "source_suite": suite,
        "git_commit": manifest["git_commit"],
        "profile": manifest["profile"],
        "machine": manifest["machine"],
        "evidence_sha256_verified": True,
        "solver": analyze_solver(outputs["solver_algorithms"]),
        "state_abstraction": analyze_state_abstraction(
            outputs["state_abstraction_battery"]
        ),
        "action_abstraction": analyze_action_structure(outputs["action_abstraction"]),
        "scalable_multisize_raise": analyze_action_structure(
            outputs["scalable_multisize_raise"]
        ),
    }
    if suite == "deepsix_ryzen_benchmark_suite_v2":
        result["state_abstraction_convergence"] = analyze_state_convergence(
            outputs["state_abstraction_convergence"]
        )
    else:
        result["state_abstraction_convergence"] = None
        result["legacy_note"] = (
            "v1 manifest predates the state-abstraction convergence battery; "
            "all original evidence remains verified and analyzable"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    analysis = analyze_run(args.run_dir)
    text = json.dumps(analysis, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
