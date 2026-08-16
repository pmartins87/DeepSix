#!/usr/bin/env python3
"""Measure the marginal cost of adding a second initial sizing with one raise layer.

Both cases share the same Short Deck board, ranges, pot and absolute raise-to.
The one-size game is a strict subset of the two-size game. Exploitability still
belongs to each action space and is reported mainly as a convergence diagnostic;
the structural/throughput deltas are the primary cross-case measurements.
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
from deepsix_trainer.river_multisize_one_raise import (  # noqa: E402
    RiverMultiSizeOneRaiseCFR,
    RiverMultiSizeOneRaiseConfig,
    exploitability,
    pure_plan_count,
    uniform_policy,
)


def c(text: str) -> int:
    return parse_card(text)


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
    return RiverMultiSizeOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=pot,
        bet_sizes=bet_sizes,
        raise_to=raise_to,
        p0_range=p0,
        p1_range=p1,
    )


def run_case(config: RiverMultiSizeOneRaiseConfig, iterations: int) -> dict:
    config.validate()
    baseline = uniform_policy(config)
    initial = exploitability(config, baseline)
    trainer = RiverMultiSizeOneRaiseCFR(config)
    start = time.perf_counter()
    trainer.train(iterations)
    seconds = time.perf_counter() - start
    final = exploitability(config, trainer.average_policy())
    return {
        "bet_sizes": list(config.bet_sizes),
        "raise_to": config.raise_to,
        "chance_deals": len(config.compatible_deals()),
        "pure_plans_per_private_hand": pure_plan_count(config),
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
    parser.add_argument("--size-one", type=int, default=4)
    parser.add_argument("--size-two", type=int, default=8)
    parser.add_argument("--raise-to", type=int, default=14)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be positive")
    if args.size_two <= args.size_one:
        parser.error("--size-two must be greater than --size-one")

    one = make_config(
        pot=args.pot,
        bet_sizes=(args.size_one,),
        raise_to=args.raise_to,
    )
    two = make_config(
        pot=args.pot,
        bet_sizes=(args.size_one, args.size_two),
        raise_to=args.raise_to,
    )
    one_result = run_case(one, args.iterations)
    two_result = run_case(two, args.iterations)
    if one_result["chance_deals"] != two_result["chance_deals"]:
        raise AssertionError("comparison fixtures do not share the same chance space")

    result = {
        "benchmark": "deepsix_river_multisize_one_raise_v1",
        "warning": (
            "cross-case exploitability belongs to different action spaces; use it "
            "as convergence evidence, not a direct strategy-quality ranking"
        ),
        "machine": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "fixture": {
            "pot": args.pot,
            "size_one": args.size_one,
            "size_two": args.size_two,
            "raise_to": args.raise_to,
        },
        "cases": [one_result, two_result],
        "marginal": {
            "node_ratio": two_result["nodes"] / one_result["nodes"],
            "action_slot_ratio": (
                two_result["node_action_slots"]
                / one_result["node_action_slots"]
            ),
            "pure_plan_ratio": (
                two_result["pure_plans_per_private_hand"]
                / one_result["pure_plans_per_private_hand"]
            ),
            "throughput_ratio": (
                two_result["iterations_per_second"]
                / one_result["iterations_per_second"]
            ),
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
