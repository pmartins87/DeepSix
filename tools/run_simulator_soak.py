#!/usr/bin/env python3
"""Run a deterministic, resumable DeepSix Simulator correctness soak.

This tool is intentionally single-process. Use --shard-count/--shard-index to
partition the global hand schedule across externally launched processes after
profiling justifies parallel workers.

Each hand is independent, with deterministic asymmetric stacks and deterministic
random legal actions. That allows very long stability runs without a cash session
ending because bankroll has been depleted by rake. Persistent-session
snapshot/restart is validated separately.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deepsix_core.state import ActionKind
from deepsix_simulator import (
    DEFAULT_SIMULATOR_RULES,
    SIMULATOR_SOAK_SCHEMA_VERSION,
    SimulatedHand,
    SimulatorAction,
    SimulatorSoakCheckpoint,
    SimulatorSoakError,
    SimulatorSoakPlan,
    replay_transcript,
    transcript_from_hand,
)


class DeterministicRandomPolicy:
    """Stress policy: uniformly samples a small legal action candidate set."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def __call__(self, observation):
        legal = observation.legal
        if legal is None:
            raise RuntimeError("soak policy called without legal actions")

        choices: list[SimulatorAction] = []
        if legal.can_check:
            choices.append(SimulatorAction(ActionKind.CHECK))
        if legal.can_call:
            choices.append(SimulatorAction(ActionKind.CALL))
        if legal.can_fold:
            choices.append(SimulatorAction(ActionKind.FOLD))
        if legal.can_raise:
            choices.append(SimulatorAction(ActionKind.RAISE_TO, legal.min_raise_to))
            if legal.max_raise_to != legal.min_raise_to:
                choices.append(SimulatorAction(ActionKind.RAISE_TO, legal.max_raise_to))
        if not choices:
            raise RuntimeError("soak policy found no legal action")
        return self.rng.choice(choices)


def parse_player_counts(text: str) -> tuple[int, ...]:
    try:
        values = tuple(int(part.strip()) for part in text.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "player counts must be comma-separated integers"
        ) from exc
    if not values or any(value < 2 or value > 6 for value in values):
        raise argparse.ArgumentTypeError("player counts must all be within 2..6")
    if len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("player counts must be unique")
    return values


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def build_plan(args: argparse.Namespace) -> SimulatorSoakPlan:
    plan = SimulatorSoakPlan(
        schema_version=SIMULATOR_SOAK_SCHEMA_VERSION,
        seed_base=args.seed_base,
        total_global_hands=args.hands,
        shard_count=args.shard_count,
        shard_index=args.shard_index,
        stake_cents=args.stake_cents,
        player_counts=args.players,
        stack_min_antes=args.stack_min_antes,
        stack_max_antes=args.stack_max_antes,
        bbj_enabled=args.bbj,
        replay_every=args.replay_every,
    )
    plan.validate()
    DEFAULT_SIMULATOR_RULES.ante_units(plan.stake_cents)
    return plan


def load_or_create_checkpoint(
    checkpoint_path: Path,
    plan: SimulatorSoakPlan,
    *,
    resume: bool,
) -> SimulatorSoakCheckpoint:
    if checkpoint_path.exists():
        if not resume:
            raise SimulatorSoakError(
                f"checkpoint already exists at {checkpoint_path}; pass --resume"
            )
        checkpoint = SimulatorSoakCheckpoint.from_json(
            checkpoint_path.read_text(encoding="utf-8")
        )
        if checkpoint.plan != plan:
            raise SimulatorSoakError(
                "existing checkpoint plan differs from requested CLI plan"
            )
        return checkpoint
    if resume:
        raise SimulatorSoakError(
            f"--resume requested but checkpoint does not exist: {checkpoint_path}"
        )
    return SimulatorSoakCheckpoint.new(plan)


def _stack_schedule(
    plan: SimulatorSoakPlan,
    *,
    seed: int,
    player_count: int,
) -> tuple[tuple[int, int], ...]:
    ante_units = DEFAULT_SIMULATOR_RULES.ante_units(plan.stake_cents)
    rng = random.Random((seed << 17) ^ 0x9E3779B97F4A7C15)
    return tuple(
        (
            seat,
            rng.randint(plan.stack_min_antes, plan.stack_max_antes) * ante_units,
        )
        for seat in range(player_count)
    )


def _policy_seed(seed: int, seat: int) -> int:
    return (seed * 1_000_003) ^ (seat * 97_409) ^ 0xD1B54A32D192ED03


def _validate_terminal(
    hand: SimulatedHand,
    *,
    starting_stacks: tuple[tuple[int, int], ...],
) -> None:
    if hand.settlement is None or not hand.terminal:
        raise RuntimeError("soak hand did not settle")
    settlement = hand.settlement
    starting_total = sum(stack for _, stack in starting_stacks)

    if sum(value for _, value in settlement.gross_awards) != settlement.gross_pot_units:
        raise RuntimeError("gross awards do not conserve gross pot")
    if (
        sum(value for _, value in settlement.net_awards)
        != settlement.gross_pot_units - settlement.deductions.total_units
    ):
        raise RuntimeError("net awards do not match pot minus house deductions")
    if (
        sum(value for _, value in settlement.post_hand_stacks)
        != starting_total - settlement.deductions.total_units
    ):
        raise RuntimeError("post-hand stacks violate money conservation")
    if len(hand.state.board) not in (0, 3, 4, 5):
        raise RuntimeError("terminal board has impossible card count")

    known_cards = [
        card
        for cards in hand.hole_cards.values()
        for card in cards
    ] + list(hand.state.board)
    if len(known_cards) != len(set(known_cards)):
        raise RuntimeError("duplicate known card detected in terminal hand")


def run_one(
    plan: SimulatorSoakPlan,
    ordinal: int,
) -> tuple[SimulatedHand, bool]:
    global_index = plan.global_index(ordinal)
    seed = plan.seed_for_ordinal(ordinal)
    player_count = plan.player_count_for_ordinal(ordinal)
    dealer = global_index % player_count
    stacks = _stack_schedule(plan, seed=seed, player_count=player_count)

    # The hand identity belongs to the global deterministic schedule, not to the
    # worker topology. Moving a global index between shard layouts must leave the
    # exact transcript fingerprint unchanged.
    hand = SimulatedHand.start(
        hand_id=f"soak-g{global_index:012d}",
        stake_cents=plan.stake_cents,
        seed=seed,
        dealer_seat=dealer,
        stacks=stacks,
        bbj_enabled=plan.bbj_enabled,
    )
    agents = {
        seat: DeterministicRandomPolicy(_policy_seed(seed, seat))
        for seat in range(player_count)
    }
    hand.play_to_terminal(agents, max_decisions=500)
    _validate_terminal(hand, starting_stacks=stacks)

    replay_checked = plan.should_replay(ordinal)
    if replay_checked:
        transcript = transcript_from_hand(hand)
        replayed = replay_transcript(transcript)
        if replayed.state.actions != hand.state.actions:
            raise RuntimeError("replayed action sequence diverged")
        if replayed.settlement != hand.settlement:
            raise RuntimeError("replayed settlement diverged")
    return hand, replay_checked


def failure_payload(
    plan: SimulatorSoakPlan,
    checkpoint: SimulatorSoakCheckpoint,
    ordinal: int,
    exc: BaseException,
) -> dict:
    global_index = (
        plan.global_index(ordinal)
        if ordinal < plan.local_target_hands
        else None
    )
    seed = (
        plan.seed_for_ordinal(ordinal)
        if ordinal < plan.local_target_hands
        else None
    )
    return {
        "schema": "deepsix_simulator_soak_failure_v1",
        "plan": plan.to_dict(),
        "checkpoint": checkpoint.to_dict(),
        "ordinal": ordinal,
        "global_index": global_index,
        "seed": seed,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hands", type=int, default=100_000)
    parser.add_argument("--players", type=parse_player_counts, default=(2, 3, 4, 5, 6))
    parser.add_argument("--stake-cents", type=int, default=2)
    parser.add_argument("--seed-base", type=int, default=20260825)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--stack-min-antes", type=int, default=1)
    parser.add_argument("--stack-max-antes", type=int, default=200)
    parser.add_argument(
        "--replay-every",
        type=int,
        default=1000,
        help="Replay every N local hands; 0 disables replay checks",
    )
    parser.add_argument("--checkpoint-every", type=int, default=1000)
    parser.add_argument("--bbj", action="store_true")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.checkpoint_every <= 0:
        parser.error("--checkpoint-every must be positive")
    try:
        plan = build_plan(args)
    except (SimulatorSoakError, ValueError) as exc:
        parser.error(str(exc))

    args.run_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.run_dir / "checkpoint.json"
    failure_path = args.run_dir / "failure.json"
    result_path = args.run_dir / "result.json"

    try:
        checkpoint = load_or_create_checkpoint(
            checkpoint_path,
            plan,
            resume=args.resume,
        )
    except SimulatorSoakError as exc:
        parser.error(str(exc))

    if checkpoint.is_complete:
        print(checkpoint.canonical_json())
        return

    segment_start_completed = checkpoint.completed_hands
    segment_start_decisions = checkpoint.decisions
    started = time.perf_counter()
    tracemalloc.start()

    try:
        while not checkpoint.is_complete:
            ordinal = checkpoint.next_ordinal
            hand, replay_checked = run_one(plan, ordinal)
            settlement = hand.settlement
            if settlement is None:
                raise RuntimeError("terminal hand unexpectedly missing settlement")
            checkpoint = checkpoint.advance(
                decisions=hand.decision_index,
                gross_pot_units=settlement.gross_pot_units,
                rake_units=settlement.deductions.rounded_rake_units,
                bbj_units=settlement.deductions.bbj_units,
                terminal_board_cards=len(hand.state.board),
                replay_checked=replay_checked,
            )
            if (
                checkpoint.completed_hands % args.checkpoint_every == 0
                or checkpoint.is_complete
            ):
                atomic_write_text(
                    checkpoint_path,
                    checkpoint.canonical_json() + "\n",
                )
    except BaseException as exc:
        atomic_write_text(
            failure_path,
            json.dumps(
                failure_payload(plan, checkpoint, checkpoint.next_ordinal, exc),
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        atomic_write_text(checkpoint_path, checkpoint.canonical_json() + "\n")
        raise

    elapsed = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    segment_hands = checkpoint.completed_hands - segment_start_completed
    segment_decisions = checkpoint.decisions - segment_start_decisions

    result = {
        "schema": "deepsix_simulator_soak_result_v1",
        "plan_fingerprint": plan.fingerprint(),
        "checkpoint_fingerprint": checkpoint.fingerprint(),
        "completed_hands": checkpoint.completed_hands,
        "target_local_hands": plan.local_target_hands,
        "segment_hands": segment_hands,
        "segment_decisions": segment_decisions,
        "segment_elapsed_seconds": elapsed,
        "segment_hands_per_second": (
            segment_hands / elapsed if elapsed > 0 else None
        ),
        "segment_decisions_per_second": (
            segment_decisions / elapsed if elapsed > 0 else None
        ),
        "tracemalloc_peak_bytes": peak_bytes,
        "checkpoint": checkpoint.to_dict(),
    }
    atomic_write_text(
        result_path,
        json.dumps(result, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
