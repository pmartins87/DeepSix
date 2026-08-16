#!/usr/bin/env python3
"""Compare vanilla synchronous CFR and synchronous RM+ on exact river games.

The benchmark changes only the regret-update / averaging algorithm.  Cards,
chance, action tree and exact exploitability oracle remain identical.  This is
the correct place to ask whether a more aggressive regret scheme buys lower
error per CPU-hour before promoting it to larger abstractions.

CI should use a tiny smoke.  Engineering conclusions require all fixtures,
multiple iteration budgets and Ryzen 9 measurements.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deepsix_trainer.river_lab_fixtures import benchmark_fixture_battery  # noqa: E402
from deepsix_trainer.river_multisize_one_raise import RiverMultiSizeOneRaiseCFR  # noqa: E402
from deepsix_trainer.river_multisize_one_raise_dpbr import exploitability_dp  # noqa: E402
from deepsix_trainer.river_rmplus import RiverRegretMatchingPlus  # noqa: E402


def parse_checkpoints(text: str) -> tuple[int, ...]:
    try:
        values = tuple(int(value.strip()) for value in text.split(",") if value.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("checkpoints must be comma-separated integers") from exc
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("checkpoints must be positive")
    if tuple(sorted(set(values))) != values:
        raise argparse.ArgumentTypeError("checkpoints must be unique and increasing")
    return values


def run_vanilla(cfg, checkpoints: tuple[int, ...]) -> list[dict]:
    trainer = RiverMultiSizeOneRaiseCFR(cfg)
    rows = []
    trained = 0
    elapsed = 0.0
    for target in checkpoints:
        start = time.perf_counter()
        trainer.train(target - trained)
        elapsed += time.perf_counter() - start
        trained = target
        loss = exploitability_dp(cfg, trainer.average_policy())
        rows.append(
            {
                "algorithm": "vanilla_cfr",
                "iterations": target,
                "training_seconds": elapsed,
                "iterations_per_second": target / elapsed,
                "exact_exploitability": loss,
                "exploitability_over_pot": loss / cfg.pot,
                "nodes": len(trainer.nodes),
            }
        )
    return rows


def run_rmplus(cfg, checkpoints: tuple[int, ...], averaging_delay: int) -> list[dict]:
    trainer = RiverRegretMatchingPlus(
        cfg,
        averaging_delay=averaging_delay,
        linear_averaging=True,
    )
    rows = []
    trained = 0
    elapsed = 0.0
    for target in checkpoints:
        start = time.perf_counter()
        trainer.train(target - trained)
        elapsed += time.perf_counter() - start
        trained = target
        loss = trainer.exact_exploitability()
        rows.append(
            {
                "algorithm": "synchronous_rmplus_linear_average",
                "averaging_delay": averaging_delay,
                "iterations": target,
                "training_seconds": elapsed,
                "iterations_per_second": target / elapsed,
                "exact_exploitability": loss,
                "exploitability_over_pot": loss / cfg.pot,
                "nodes": len(trainer.nodes),
                "regrets_nonnegative": trainer.all_regrets_nonnegative(),
            }
        )
    return rows


def aggregate(rows: list[dict], checkpoint: int) -> list[dict]:
    names = []
    for row in rows:
        if row["algorithm"] not in names:
            names.append(row["algorithm"])
    result = []
    for name in names:
        selected = [
            row
            for row in rows
            if row["algorithm"] == name and row["iterations"] == checkpoint
        ]
        normalized = [row["exploitability_over_pot"] for row in selected]
        throughput = [row["iterations_per_second"] for row in selected]
        result.append(
            {
                "algorithm": name,
                "checkpoint": checkpoint,
                "fixtures": len(selected),
                "mean_exploitability_over_pot": statistics.fmean(normalized),
                "median_exploitability_over_pot": statistics.median(normalized),
                "max_exploitability_over_pot": max(normalized),
                "mean_iterations_per_second": statistics.fmean(throughput),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoints",
        type=parse_checkpoints,
        default=parse_checkpoints("100,300,1000,3000"),
    )
    parser.add_argument("--rmplus-delay", type=int, default=50)
    parser.add_argument("--fixture-limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.rmplus_delay < 0:
        parser.error("--rmplus-delay must be non-negative")
    if args.fixture_limit is not None and args.fixture_limit <= 0:
        parser.error("--fixture-limit must be positive")

    battery = benchmark_fixture_battery()
    if args.fixture_limit is not None:
        battery = battery[: args.fixture_limit]

    rows = []
    for spec, cfg in battery:
        for row in run_vanilla(cfg, args.checkpoints):
            rows.append({"fixture": spec.name, **row})
        for row in run_rmplus(cfg, args.checkpoints, args.rmplus_delay):
            rows.append({"fixture": spec.name, **row})

    result = {
        "benchmark": "deepsix_river_solver_algorithm_battery_v1",
        "oracle": "dynamic_exact_best_response",
        "machine": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "fixture_count": len(battery),
        "checkpoints": list(args.checkpoints),
        "rmplus_averaging_delay": args.rmplus_delay,
        "warning": (
            "synthetic river battery; algorithm promotion requires long Ryzen 9 runs "
            "and should consider exploitability per wall-clock second, not iteration count alone"
        ),
        "rows": rows,
        "aggregate_by_checkpoint": {
            str(checkpoint): aggregate(rows, checkpoint)
            for checkpoint in args.checkpoints
        },
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
