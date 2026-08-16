#!/usr/bin/env python3
"""Benchmark private-hand bucket compression under one fixed action game.

Every case uses the same exact Short Deck board, ranges and action tree. Only
the mapping from exact private combos to CFR infosets changes. After training,
the bucket policy is expanded back to exact combos and evaluated with the
unabstracted dynamic exact best response.

This makes the reported exploitability a direct measure of both residual
training error and private-state abstraction error in the original exact game.
Longer, multi-fixture runs are required before choosing a production abstraction;
the CI invocation is smoke-only.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deepsix_core.cards import parse_card  # noqa: E402
from deepsix_trainer.river_microgame import RangeHand  # noqa: E402
from deepsix_trainer.river_multisize_one_raise_scalable import (  # noqa: E402
    ScalableRiverMultiSizeOneRaiseConfig,
)
from deepsix_trainer.river_state_abstraction import (  # noqa: E402
    BucketedRiverCFR,
    RiverBucketMap,
    equity_quantile_bucket_map,
    identity_bucket_map,
    showdown_category_bucket_map,
    single_bucket_map,
)


def c(text: str) -> int:
    return parse_card(text)


def config() -> ScalableRiverMultiSizeOneRaiseConfig:
    return ScalableRiverMultiSizeOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=12,
        bet_sizes=(4, 8),
        raise_to=14,
        p0_range=(
            RangeHand((c("Ts"), c("9c"))),
            RangeHand((c("Tc"), c("7d"))),
            RangeHand((c("Kc"), c("7h"))),
            RangeHand((c("Kc"), c("9s"))),
            RangeHand((c("Jc"), c("Tc"))),
        ),
        p1_range=(
            RangeHand((c("Td"), c("9h"))),
            RangeHand((c("Th"), c("7s"))),
            RangeHand((c("Kh"), c("7c"))),
            RangeHand((c("Kh"), c("9d"))),
            RangeHand((c("Jh"), c("Th"))),
        ),
    )


def run_case(
    cfg: ScalableRiverMultiSizeOneRaiseConfig,
    mapping: RiverBucketMap,
    iterations: int,
) -> dict:
    mapping.validate(cfg)
    trainer = BucketedRiverCFR(cfg, mapping)
    start = time.perf_counter()
    trainer.train(iterations)
    seconds = time.perf_counter() - start
    exact_loss = trainer.exact_unabstracted_exploitability()
    exact_hands = (len(cfg.p0_range), len(cfg.p1_range))
    bucket_counts = (mapping.bucket_count(0), mapping.bucket_count(1))
    return {
        "name": mapping.name,
        "exact_hands": list(exact_hands),
        "bucket_counts": list(bucket_counts),
        "private_state_compression": [
            exact_hands[0] / bucket_counts[0],
            exact_hands[1] / bucket_counts[1],
        ],
        "chance_deals": len(cfg.compatible_deals()),
        "iterations": iterations,
        "iterations_per_second": iterations / seconds,
        "nodes": len(trainer.nodes),
        "node_action_slots": sum(node.action_count for node in trainer.nodes.values()),
        "exact_unabstracted_exploitability": exact_loss,
        "exact_unabstracted_exploitability_over_pot": exact_loss / cfg.pot,
        "seconds": seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=2500)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be positive")

    cfg = config()
    cfg.validate()
    mappings = (
        identity_bucket_map(cfg),
        equity_quantile_bucket_map(cfg, 3),
        equity_quantile_bucket_map(cfg, 2),
        showdown_category_bucket_map(cfg),
        single_bucket_map(cfg),
    )
    cases = [run_case(cfg, mapping, args.iterations) for mapping in mappings]
    identity = cases[0]
    for case in cases:
        case["relative_to_identity"] = {
            "node_ratio": case["nodes"] / identity["nodes"],
            "action_slot_ratio": (
                case["node_action_slots"] / identity["node_action_slots"]
            ),
            "throughput_ratio": (
                case["iterations_per_second"]
                / identity["iterations_per_second"]
            ),
            "exploitability_ratio": (
                None
                if identity["exact_unabstracted_exploitability"] == 0.0
                else case["exact_unabstracted_exploitability"]
                / identity["exact_unabstracted_exploitability"]
            ),
        }

    result = {
        "benchmark": "deepsix_river_private_state_abstraction_v1",
        "exact_evaluation": "expanded_bucket_policy_vs_unabstracted_dynamic_BR",
        "warning": (
            "single fixture and finite CFR iterations; use only as infrastructure "
            "evidence until a broad board/range/SPR battery is run"
        ),
        "machine": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "action_game": {
            "pot": cfg.pot,
            "bet_sizes": list(cfg.bet_sizes),
            "raise_to": cfg.raise_to,
        },
        "cases": cases,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
