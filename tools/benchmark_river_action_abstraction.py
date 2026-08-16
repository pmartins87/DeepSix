#!/usr/bin/env python3
"""Benchmark exact-auditable river action abstractions.

This benchmark is intended for the Ryzen 9 and other controlled machines.  It
uses one fixed Short Deck river/range fixture and varies only the number of bet
sizes, so throughput and convergence costs are directly comparable.

The sizing values are laboratory chip units, not production KKPoker sizing
recommendations.  Results are emitted as JSON for durable comparison across
machines/commits.
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
from deepsix_trainer.river_multisize import (  # noqa: E402
    RiverMultiSizeCFR,
    RiverMultiSizeConfig,
    expected_value,
    exploitability,
    uniform_policy,
)


def c(text: str) -> int:
    return parse_card(text)


def fixture(bet_sizes: tuple[int, ...]) -> RiverMultiSizeConfig:
    """Fixed symmetric three-level range fixture used by the CI microgames."""
    return RiverMultiSizeConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=12,
        bet_sizes=bet_sizes,
        p0_range=(
            RangeHand((c("Tc"), c("7d"))),
            RangeHand((c("Kc"), c("9s"))),
            RangeHand((c("Jc"), c("Tc"))),
        ),
        p1_range=(
            RangeHand((c("Th"), c("7s"))),
            RangeHand((c("Kh"), c("9d"))),
            RangeHand((c("Jh"), c("Th"))),
        ),
    )


def run_case(bet_sizes: tuple[int, ...], iterations: int) -> dict:
    config = fixture(bet_sizes)
    config.validate()
    baseline = uniform_policy(config)
    initial_exploitability = exploitability(config, baseline)

    trainer = RiverMultiSizeCFR(config)
    start = time.perf_counter()
    trainer.train(iterations)
    elapsed = time.perf_counter() - start

    policy = trainer.average_policy()
    final_exploitability = exploitability(config, policy)
    final_ev = expected_value(config, policy, policy)
    action_slots = sum(node.action_count for node in trainer.nodes.values())

    return {
        "bet_sizes": list(bet_sizes),
        "chance_deals": len(config.compatible_deals()),
        "final_ev": final_ev,
        "final_exploitability": final_exploitability,
        "final_exploitability_over_pot": final_exploitability / config.pot,
        "initial_exploitability": initial_exploitability,
        "initial_exploitability_over_pot": initial_exploitability / config.pot,
        "iterations": iterations,
        "iterations_per_second": iterations / elapsed,
        "node_action_slots": action_slots,
        "nodes": len(trainer.nodes),
        "seconds": elapsed,
    }


def parse_sizes(text: str) -> tuple[int, ...]:
    try:
        values = tuple(int(part.strip()) for part in text.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("sizes must be comma-separated integers") from exc
    if not values:
        raise argparse.ArgumentTypeError("at least one size is required")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--iterations",
        type=int,
        default=5000,
        help="CFR iterations per sizing configuration (default: 5000)",
    )
    parser.add_argument(
        "--sizes",
        type=parse_sizes,
        action="append",
        help=(
            "one comma-separated sizing set; repeat to add cases. "
            "Default cases: 8 ; 4,8 ; 3,5,8 ; 3,5,8,12"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON output path; stdout is always populated",
    )
    args = parser.parse_args()

    if args.iterations <= 0:
        parser.error("--iterations must be positive")
    cases = args.sizes or [(8,), (4, 8), (3, 5, 8), (3, 5, 8, 12)]

    result = {
        "benchmark": "deepsix_river_action_abstraction_v1",
        "machine": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.processor(),
        },
        "cases": [run_case(tuple(sizes), args.iterations) for sizes in cases],
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
