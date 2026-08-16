#!/usr/bin/env python3
"""Run private-state abstraction comparisons across deterministic board textures.

The battery is intentionally synthetic and mechanically generated. It exists to
reduce single-fixture overfitting while real-game range distributions are not
yet available. Each trained bucket policy is expanded to exact private hands
and evaluated by the unabstracted dynamic best response.

Two transparent quantile families are compared at the same requested widths:

* showdown-equity-only quantiles;
* equal-rank feature aggregation using range equity, universal equity, nutness
  and stronger-range blocker pressure.

No benchmark result automatically promotes either family.
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

from deepsix_trainer.river_hand_features import (  # noqa: E402
    feature_borda_quantile_bucket_map,
)
from deepsix_trainer.river_lab_fixtures import benchmark_fixture_battery  # noqa: E402
from deepsix_trainer.river_state_abstraction import (  # noqa: E402
    BucketedRiverCFR,
    RiverBucketMap,
    equity_quantile_bucket_map,
    identity_bucket_map,
    showdown_category_bucket_map,
    single_bucket_map,
)


def parse_bucket_counts(text: str) -> tuple[int, ...]:
    try:
        values = tuple(int(value.strip()) for value in text.split(",") if value.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bucket counts must be comma-separated integers") from exc
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("bucket counts must be positive")
    if len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("bucket counts must be unique")
    return values


def mapping_family(cfg, bucket_counts: tuple[int, ...]) -> tuple[RiverBucketMap, ...]:
    return (
        identity_bucket_map(cfg),
        *(equity_quantile_bucket_map(cfg, count) for count in bucket_counts),
        *(feature_borda_quantile_bucket_map(cfg, count) for count in bucket_counts),
        showdown_category_bucket_map(cfg),
        single_bucket_map(cfg),
    )


def run_case(spec, cfg, mapping: RiverBucketMap, iterations: int) -> dict:
    trainer = BucketedRiverCFR(cfg, mapping)
    start = time.perf_counter()
    trainer.train(iterations)
    seconds = time.perf_counter() - start
    exact_loss = trainer.exact_unabstracted_exploitability()
    return {
        "fixture": spec.name,
        "mapping": mapping.name,
        "board": list(spec.board_text),
        "pot": cfg.pot,
        "bet_sizes": list(cfg.bet_sizes),
        "raise_to": cfg.raise_to,
        "chance_deals": len(cfg.compatible_deals()),
        "bucket_counts": [mapping.bucket_count(0), mapping.bucket_count(1)],
        "nodes": len(trainer.nodes),
        "action_slots": sum(node.action_count for node in trainer.nodes.values()),
        "iterations": iterations,
        "iterations_per_second": iterations / seconds,
        "exact_unabstracted_exploitability": exact_loss,
        "exploitability_over_pot": exact_loss / cfg.pot,
        "seconds": seconds,
    }


def aggregate(cases: list[dict]) -> list[dict]:
    names = []
    for case in cases:
        if case["mapping"] not in names:
            names.append(case["mapping"])
    output = []
    for name in names:
        selected = [case for case in cases if case["mapping"] == name]
        normalized = [case["exploitability_over_pot"] for case in selected]
        throughputs = [case["iterations_per_second"] for case in selected]
        nodes = [case["nodes"] for case in selected]
        output.append(
            {
                "mapping": name,
                "fixtures": len(selected),
                "mean_exploitability_over_pot": statistics.fmean(normalized),
                "max_exploitability_over_pot": max(normalized),
                "median_exploitability_over_pot": statistics.median(normalized),
                "mean_iterations_per_second": statistics.fmean(throughputs),
                "mean_nodes": statistics.fmean(nodes),
            }
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1500)
    parser.add_argument("--bucket-counts", type=parse_bucket_counts, default=parse_bucket_counts("6,4,2"))
    parser.add_argument("--fixture-limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be positive")
    if args.fixture_limit is not None and args.fixture_limit <= 0:
        parser.error("--fixture-limit must be positive")

    battery = benchmark_fixture_battery()
    if args.fixture_limit is not None:
        battery = battery[: args.fixture_limit]

    cases = []
    for spec, cfg in battery:
        for mapping in mapping_family(cfg, args.bucket_counts):
            cases.append(run_case(spec, cfg, mapping, args.iterations))

    result = {
        "benchmark": "deepsix_river_state_abstraction_battery_v2",
        "machine": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "iterations_per_case": args.iterations,
        "fixture_count": len(battery),
        "bucket_counts": list(args.bucket_counts),
        "mapping_families": [
            "identity",
            "conditional_equity_quantiles",
            "equity_nutness_blocker_borda_quantiles",
            "showdown_category",
            "single",
        ],
        "warning": (
            "synthetic mechanically sampled river ranges; use for comparative "
            "abstraction engineering, not as a model of live population ranges"
        ),
        "cases": cases,
        "aggregate": aggregate(cases),
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
