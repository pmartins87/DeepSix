#!/usr/bin/env python3
"""Measure state-abstraction convergence at multiple cumulative checkpoints.

The main state-abstraction battery compares many bucket widths at one final
iteration budget.  This companion benchmark keeps one requested width fixed and
records convergence curves for the principal mapping families under the same
river fixtures and exact unabstracted best-response oracle.

This makes the CPU-hour tradeoff more visible: a method can use fewer nodes and
train faster yet converge to a worse policy, or spend more time per iteration
while buying enough strategic accuracy to remain competitive.
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

from deepsix_trainer.river_counterfactual_features import (  # noqa: E402
    cfv_kmedoids_bucket_map,
)
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


def parse_checkpoints(text: str) -> tuple[int, ...]:
    try:
        values = tuple(int(value.strip()) for value in text.split(",") if value.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "checkpoints must be comma-separated integers"
        ) from exc
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("checkpoints must be positive")
    if tuple(sorted(set(values))) != values:
        raise argparse.ArgumentTypeError(
            "checkpoints must be unique and strictly increasing"
        )
    return values


def build_mapping_family(
    cfg,
    bucket_count: int,
) -> tuple[tuple[RiverBucketMap, float], ...]:
    builders = (
        lambda: identity_bucket_map(cfg),
        lambda: equity_quantile_bucket_map(cfg, bucket_count),
        lambda: feature_borda_quantile_bucket_map(cfg, bucket_count),
        lambda: cfv_kmedoids_bucket_map(cfg, bucket_count),
        lambda: showdown_category_bucket_map(cfg),
        lambda: single_bucket_map(cfg),
    )
    output = []
    for builder in builders:
        start = time.perf_counter()
        mapping = builder()
        output.append((mapping, time.perf_counter() - start))
    return tuple(output)


def run_mapping(
    spec,
    cfg,
    mapping: RiverBucketMap,
    mapping_build_seconds: float,
    checkpoints: tuple[int, ...],
) -> list[dict]:
    trainer = BucketedRiverCFR(cfg, mapping)
    rows = []
    previous = 0
    cumulative_training_seconds = 0.0
    for checkpoint in checkpoints:
        increment = checkpoint - previous
        start = time.perf_counter()
        trainer.train(increment)
        cumulative_training_seconds += time.perf_counter() - start
        exact_loss = trainer.exact_unabstracted_exploitability()
        rows.append(
            {
                "fixture": spec.name,
                "mapping": mapping.name,
                "board": list(spec.board_text),
                "pot": cfg.pot,
                "bet_sizes": list(cfg.bet_sizes),
                "raise_to": cfg.raise_to,
                "bucket_counts": [
                    mapping.bucket_count(0),
                    mapping.bucket_count(1),
                ],
                "nodes": len(trainer.nodes),
                "action_slots": sum(
                    node.action_count for node in trainer.nodes.values()
                ),
                "iterations": checkpoint,
                "mapping_build_seconds": mapping_build_seconds,
                "cumulative_training_seconds": cumulative_training_seconds,
                "iterations_per_second": checkpoint / cumulative_training_seconds,
                "exact_unabstracted_exploitability": exact_loss,
                "exploitability_over_pot": exact_loss / cfg.pot,
            }
        )
        previous = checkpoint
    return rows


def aggregate_by_checkpoint(rows: list[dict]) -> dict[str, list[dict]]:
    output: dict[str, list[dict]] = {}
    checkpoints = sorted({int(row["iterations"]) for row in rows})
    for checkpoint in checkpoints:
        selected_checkpoint = [
            row for row in rows if int(row["iterations"]) == checkpoint
        ]
        methods = []
        names = []
        for row in selected_checkpoint:
            if row["mapping"] not in names:
                names.append(row["mapping"])
        for name in names:
            selected = [
                row for row in selected_checkpoint if row["mapping"] == name
            ]
            normalized = [row["exploitability_over_pot"] for row in selected]
            methods.append(
                {
                    "mapping": name,
                    "fixtures": len(selected),
                    "iterations": checkpoint,
                    "mean_exploitability_over_pot": statistics.fmean(normalized),
                    "median_exploitability_over_pot": statistics.median(normalized),
                    "max_exploitability_over_pot": max(normalized),
                    "mean_cumulative_training_seconds": statistics.fmean(
                        row["cumulative_training_seconds"] for row in selected
                    ),
                    "mean_iterations_per_second": statistics.fmean(
                        row["iterations_per_second"] for row in selected
                    ),
                    "mean_nodes": statistics.fmean(row["nodes"] for row in selected),
                    "mean_mapping_build_seconds": statistics.fmean(
                        row["mapping_build_seconds"] for row in selected
                    ),
                }
            )
        output[str(checkpoint)] = methods
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoints",
        type=parse_checkpoints,
        default=parse_checkpoints("100,300,1000"),
    )
    parser.add_argument("--bucket-count", type=int, default=4)
    parser.add_argument("--fixture-limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.bucket_count <= 0:
        parser.error("--bucket-count must be positive")
    if args.fixture_limit is not None and args.fixture_limit <= 0:
        parser.error("--fixture-limit must be positive")

    battery = benchmark_fixture_battery()
    if args.fixture_limit is not None:
        battery = battery[: args.fixture_limit]

    rows = []
    for spec, cfg in battery:
        for mapping, build_seconds in build_mapping_family(cfg, args.bucket_count):
            rows.extend(
                run_mapping(
                    spec,
                    cfg,
                    mapping,
                    build_seconds,
                    args.checkpoints,
                )
            )

    result = {
        "benchmark": "deepsix_river_state_abstraction_convergence_v1",
        "machine": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "fixture_count": len(battery),
        "bucket_count": args.bucket_count,
        "checkpoints": list(args.checkpoints),
        "mapping_families": [
            "identity",
            "conditional_equity_quantile",
            "equity_nutness_blocker_borda_quantile",
            "uniform_reference_cfv_kmedoids",
            "showdown_category",
            "single",
        ],
        "oracle": "expanded concrete policy vs unabstracted dynamic exact best response",
        "warning": (
            "checkpoints use equal iteration counts, not equal wall-clock. "
            "Cumulative training time is recorded so CPU-hour tradeoffs can be "
            "analyzed without pretending iteration counts have equal cost."
        ),
        "rows": rows,
        "aggregate_by_checkpoint": aggregate_by_checkpoint(rows),
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
