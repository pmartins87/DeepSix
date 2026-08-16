#!/usr/bin/env python3
"""Measure the marginal cost of adding one raise to a fixed river abstraction.

The no-raise and one-raise games use the same Short Deck board, ranges, pot and
initial bet size.  Exploitability values live in different action spaces and
must not be interpreted as an apples-to-apples strategy-quality ranking.  The
benchmark is primarily for tree size, throughput and convergence-shape cost.
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
    exploitability as no_raise_exploitability,
    uniform_policy as no_raise_uniform,
)
from deepsix_trainer.river_one_raise import (  # noqa: E402
    RiverOneRaiseCFR,
    RiverOneRaiseConfig,
    exploitability as one_raise_exploitability,
    uniform_policy as one_raise_uniform,
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


def fixtures(*, pot: int, bet_size: int, raise_to: int):
    p0, p1 = ranges()
    board = (c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s"))
    return (
        RiverMultiSizeConfig(
            board=board,
            pot=pot,
            bet_sizes=(bet_size,),
            p0_range=p0,
            p1_range=p1,
        ),
        RiverOneRaiseConfig(
            board=board,
            pot=pot,
            bet_size=bet_size,
            raise_to=raise_to,
            p0_range=p0,
            p1_range=p1,
        ),
    )


def run_no_raise(config: RiverMultiSizeConfig, iterations: int) -> dict:
    baseline = no_raise_uniform(config)
    initial = no_raise_exploitability(config, baseline)
    trainer = RiverMultiSizeCFR(config)
    start = time.perf_counter()
    trainer.train(iterations)
    seconds = time.perf_counter() - start
    final = no_raise_exploitability(config, trainer.average_policy())
    return {
        "game": "no_raise",
        "chance_deals": len(config.compatible_deals()),
        "initial_exploitability": initial,
        "final_exploitability": final,
        "iterations": iterations,
        "iterations_per_second": iterations / seconds,
        "nodes": len(trainer.nodes),
        "node_action_slots": sum(node.action_count for node in trainer.nodes.values()),
        "seconds": seconds,
    }


def run_one_raise(config: RiverOneRaiseConfig, iterations: int) -> dict:
    baseline = one_raise_uniform(config)
    initial = one_raise_exploitability(config, baseline)
    trainer = RiverOneRaiseCFR(config)
    start = time.perf_counter()
    trainer.train(iterations)
    seconds = time.perf_counter() - start
    final = one_raise_exploitability(config, trainer.average_policy())
    return {
        "game": "one_raise",
        "chance_deals": len(config.compatible_deals()),
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
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--pot", type=int, default=12)
    parser.add_argument("--bet-size", type=int, default=4)
    parser.add_argument("--raise-to", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be positive")

    no_raise, one_raise = fixtures(
        pot=args.pot,
        bet_size=args.bet_size,
        raise_to=args.raise_to,
    )
    no_raise.validate()
    one_raise.validate()

    no_raise_result = run_no_raise(no_raise, args.iterations)
    one_raise_result = run_one_raise(one_raise, args.iterations)
    if no_raise_result["chance_deals"] != one_raise_result["chance_deals"]:
        raise AssertionError("comparison fixtures do not share the same chance space")

    result = {
        "benchmark": "deepsix_river_raise_dimension_v1",
        "warning": (
            "exploitability is measured inside each game's own action space; use it "
            "for convergence diagnostics, not direct cross-game quality ranking"
        ),
        "machine": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "fixture": {
            "pot": args.pot,
            "bet_size": args.bet_size,
            "raise_to": args.raise_to,
        },
        "cases": [no_raise_result, one_raise_result],
        "marginal": {
            "node_ratio": one_raise_result["nodes"] / no_raise_result["nodes"],
            "action_slot_ratio": (
                one_raise_result["node_action_slots"]
                / no_raise_result["node_action_slots"]
            ),
            "throughput_ratio": (
                one_raise_result["iterations_per_second"]
                / no_raise_result["iterations_per_second"]
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
