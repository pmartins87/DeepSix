#!/usr/bin/env python3
"""Scalable 1..4 initial-sizing benchmark with one raise layer.

Unlike the v1 one-vs-two benchmark, exploitability here uses the dynamic exact
best response.  This lets us measure prefixes up to four initial sizings without
paying the exponential pure-plan enumeration cost.  The theoretical pure-plan
count is still reported to quantify how much validation work the DP method
avoids.
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
    RiverMultiSizeOneRaiseCFR,
    ScalableRiverMultiSizeOneRaiseConfig,
    exact_exploitability,
    pure_plan_count,
    uniform_policy,
)


def c(text: str) -> int:
    return parse_card(text)


def parse_sizes(text: str) -> tuple[int, ...]:
    try:
        sizes = tuple(int(value.strip()) for value in text.split(",") if value.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("sizes must be comma-separated integers") from exc
    if not sizes or len(sizes) > 4:
        raise argparse.ArgumentTypeError("provide between one and four sizes")
    if any(size <= 0 for size in sizes):
        raise argparse.ArgumentTypeError("sizes must be positive")
    if tuple(sorted(set(sizes))) != sizes:
        raise argparse.ArgumentTypeError("sizes must be unique and strictly increasing")
    return sizes


def ranges():
    return (
        (
            RangeHand((c("Tc"), c("7d"))),
            RangeHand((c("Kc"), c("9s"))),
            RangeHand((c("Jc"), c("Tc"))),
        ),
        (
            RangeHand((c("Th"), c("7s"))),
            RangeHand((c("Kh"), c("9d"))),
            RangeHand((c("Jh"), c("Th"))),
        ),
    )


def make_config(*, pot: int, bet_sizes: tuple[int, ...], raise_to: int):
    p0, p1 = ranges()
    return ScalableRiverMultiSizeOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=pot,
        bet_sizes=bet_sizes,
        raise_to=raise_to,
        p0_range=p0,
        p1_range=p1,
    )


def run_case(config: ScalableRiverMultiSizeOneRaiseConfig, iterations: int) -> dict:
    config.validate()
    initial = exact_exploitability(config, uniform_policy(config))
    trainer = RiverMultiSizeOneRaiseCFR(config)
    start = time.perf_counter()
    trainer.train(iterations)
    seconds = time.perf_counter() - start
    final = exact_exploitability(config, trainer.average_policy())
    return {
        "bet_sizes": list(config.bet_sizes),
        "chance_deals": len(config.compatible_deals()),
        "theoretical_pure_plans_per_hand": pure_plan_count(config),
        "initial_exploitability": initial,
        "final_exploitability": final,
        "iterations": iterations,
        "iterations_per_second": iterations / seconds,
        "nodes": len(trainer.nodes),
        "node_action_slots": sum(node.action_count for node in trainer.nodes.values()),
        "seconds": seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=3000)
    parser.add_argument("--pot", type=int, default=12)
    parser.add_argument("--sizes", type=parse_sizes, default=parse_sizes("2,4,8,12"))
    parser.add_argument("--raise-to", type=int, default=18)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be positive")
    if args.raise_to <= max(args.sizes):
        parser.error("--raise-to must exceed every configured size")

    cases = []
    for count in range(1, len(args.sizes) + 1):
        cases.append(
            run_case(
                make_config(
                    pot=args.pot,
                    bet_sizes=args.sizes[:count],
                    raise_to=args.raise_to,
                ),
                args.iterations,
            )
        )

    baseline = cases[0]
    for case in cases:
        case["relative_to_one_size"] = {
            "node_ratio": case["nodes"] / baseline["nodes"],
            "action_slot_ratio": case["node_action_slots"] / baseline["node_action_slots"],
            "pure_plan_ratio_avoided_by_dp": (
                case["theoretical_pure_plans_per_hand"]
                / baseline["theoretical_pure_plans_per_hand"]
            ),
            "throughput_ratio": (
                case["iterations_per_second"]
                / baseline["iterations_per_second"]
            ),
        }

    result = {
        "benchmark": "deepsix_river_multisize_one_raise_scalable_v1",
        "exact_br": "dynamic_information_set_dp",
        "warning": (
            "exploitability belongs to each action space; use cross-case values as "
            "convergence diagnostics, while structure/throughput quantify marginal cost"
        ),
        "machine": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "fixture": {
            "pot": args.pot,
            "sizes": list(args.sizes),
            "raise_to": args.raise_to,
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
