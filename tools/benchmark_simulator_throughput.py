#!/usr/bin/env python3
"""Measure single-process DeepSix Simulator throughput reproducibly.

This benchmark measures the environment itself, not solver quality.  It creates
independent seeded hands with the frozen GGPoker-reference default buy-in and a
deterministic check/call policy, then reports hands/s and decisions/s for each
requested player count.
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

from deepsix_core.ggpoker_economy import ggpoker_shortdeck_stake
from deepsix_simulator import SimulatedHand, check_call_policy


BENCHMARK_SCHEMA = "deepsix_simulator_throughput_v1"


def parse_player_counts(text: str) -> tuple[int, ...]:
    try:
        values = tuple(int(part.strip()) for part in text.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("player counts must be comma-separated integers") from exc
    if not values or any(value < 2 or value > 6 for value in values):
        raise argparse.ArgumentTypeError("player counts must all be within 2..6")
    if len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("player counts must be unique")
    return values


def run_case(*, player_count: int, hands: int, stake_cents: int, seed_base: int) -> dict:
    stake = ggpoker_shortdeck_stake(stake_cents)
    stacks = tuple((seat, stake.default_buy_in_cents) for seat in range(player_count))
    agents = {seat: check_call_policy for seat in range(player_count)}

    total_decisions = 0
    total_gross_pot = 0
    total_rake = 0
    started = time.perf_counter()
    for index in range(hands):
        hand = SimulatedHand.start(
            hand_id=f"bench-{player_count}-{index}",
            stake_cents=stake_cents,
            seed=seed_base + player_count * 1_000_000 + index,
            dealer_seat=index % player_count,
            stacks=stacks,
            bbj_enabled=False,
        )
        settlement = hand.play_to_terminal(agents)
        total_decisions += hand.decision_index
        total_gross_pot += settlement.gross_pot_units
        total_rake += settlement.deductions.rounded_rake_units
    elapsed = time.perf_counter() - started
    if elapsed <= 0:
        raise RuntimeError("non-positive benchmark elapsed time")

    return {
        "player_count": player_count,
        "hands": hands,
        "elapsed_seconds": elapsed,
        "hands_per_second": hands / elapsed,
        "decisions": total_decisions,
        "decisions_per_second": total_decisions / elapsed,
        "mean_decisions_per_hand": total_decisions / hands,
        "mean_gross_pot_units": total_gross_pot / hands,
        "mean_rake_units": total_rake / hands,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hands", type=int, default=1000, help="Hands per player-count case")
    parser.add_argument("--players", type=parse_player_counts, default=(2, 4, 6))
    parser.add_argument("--stake-cents", type=int, default=2)
    parser.add_argument("--seed-base", type=int, default=20260825)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.hands <= 0:
        parser.error("--hands must be positive")
    if isinstance(args.seed_base, bool):
        parser.error("--seed-base must be integer")
    # Validate the requested date-versioned economy stake before timing.
    ggpoker_shortdeck_stake(args.stake_cents)

    cases = [
        run_case(
            player_count=player_count,
            hands=args.hands,
            stake_cents=args.stake_cents,
            seed_base=args.seed_base,
        )
        for player_count in args.players
    ]
    payload = {
        "schema": BENCHMARK_SCHEMA,
        "python": sys.version,
        "platform": platform.platform(),
        "logical_cpu_count": __import__("os").cpu_count(),
        "stake_cents": args.stake_cents,
        "hands_per_case": args.hands,
        "seed_base": args.seed_base,
        "cases": cases,
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
