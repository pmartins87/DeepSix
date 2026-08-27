#!/usr/bin/env python3
"""Compare F5 HU trainer candidates under one exact best-response oracle.

This is an engineering benchmark, not a CI-sized test.  Every candidate trains
on the same tiny Short Deck multi-street game and its frozen average policy is
judged by ``exploitability_exact`` after conversion to an exact rational policy
when necessary.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
import platform
import time

from deepsix_core.cards import parse_card
from deepsix_trainer.hu_multistreet_best_response import exploitability_exact
from deepsix_trainer.hu_multistreet_cfr import ExactHuMultiStreetCFR, RegretMode
from deepsix_trainer.hu_multistreet_chance_sampled_cfr import ChanceSampledHuMultiStreetCFR
from deepsix_trainer.hu_multistreet_external_sampling import (
    HuMultiStreetExternalSamplingMCCFR,
)
from deepsix_trainer.hu_multistreet_float_cfr import FloatHuMultiStreetCFR
from deepsix_trainer.hu_multistreet_reference import (
    HuMicrogameConfig,
    HuReferenceMicrogame,
    uniform_micro_policy,
)
from deepsix_trainer.reach import PrivateReachVector


SCHEMA = "DEEPSIX_F5_HU_ARCHITECTURE_BENCHMARK_V1"


def cards(*texts):
    return tuple(parse_card(text) for text in texts)


def benchmark_game(*, multi_private: bool) -> HuReferenceMicrogame:
    p0 = {cards("As", "Ks"): 1}
    p1 = {cards("Qc", "Jc"): 1}
    if multi_private:
        p0[cards("Ah", "Kh")] = 1
        p1[cards("Qd", "Jd")] = 1
    return HuReferenceMicrogame(
        HuMicrogameConfig(
            stake_cents=25,
            dealer_seat=0,
            stacks=((0, 51), (1, 51)),
            flop=cards("6c", "7d", "8h"),
            bbj_enabled=False,
        ),
        (
            PrivateReachVector.from_mapping(0, p0),
            PrivateReachVector.from_mapping(1, p1),
        ),
    )


def fraction_payload(value: Fraction) -> dict[str, object]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "float": float(value),
    }


def timed_exploitability(game: HuReferenceMicrogame, exact_policy):
    started = time.perf_counter()
    value = exploitability_exact(game, exact_policy)
    return value, time.perf_counter() - started


def train_and_score_exact(game, iterations: int, mode: RegretMode) -> dict:
    solver = ExactHuMultiStreetCFR(game, regret_mode=mode)
    started = time.perf_counter()
    solver.train(iterations)
    train_seconds = time.perf_counter() - started
    policy = solver.average_policy()
    exploitability, oracle_seconds = timed_exploitability(game, policy)
    return {
        "solver": "exact_fraction_full_tree",
        "regret_mode": mode.value,
        "iterations": iterations,
        "train_seconds": train_seconds,
        "oracle_seconds": oracle_seconds,
        "infosets": len(solver.nodes),
        "policy_sha256": policy.fingerprint(),
        "exploitability_antes": fraction_payload(exploitability),
    }


def train_and_score_float(game, iterations: int, mode: RegretMode) -> dict:
    solver = FloatHuMultiStreetCFR(game, regret_mode=mode)
    started = time.perf_counter()
    solver.train(iterations)
    train_seconds = time.perf_counter() - started
    policy = solver.average_policy()
    exact_policy = policy.to_exact_policy()
    exploitability, oracle_seconds = timed_exploitability(game, exact_policy)
    return {
        "solver": "float64_full_tree",
        "regret_mode": mode.value,
        "iterations": iterations,
        "train_seconds": train_seconds,
        "oracle_seconds": oracle_seconds,
        "infosets": len(solver.nodes),
        "policy_sha256": policy.fingerprint(),
        "exploitability_antes": fraction_payload(exploitability),
    }


def train_and_score_chance(game, iterations: int, seed: int) -> dict:
    solver = ChanceSampledHuMultiStreetCFR(game, algorithm_seed=seed)
    started = time.perf_counter()
    solver.train(iterations)
    train_seconds = time.perf_counter() - started
    policy = solver.average_policy()
    exact_policy = policy.to_exact_policy()
    exploitability, oracle_seconds = timed_exploitability(game, exact_policy)
    stats = solver.stats()
    return {
        "solver": "float64_chance_sampled_cfr",
        "regret_mode": "vanilla_cfr",
        "seed": seed,
        "iterations": iterations,
        "train_seconds": train_seconds,
        "oracle_seconds": oracle_seconds,
        "infosets": len(solver.nodes),
        "private_deals_sampled": stats.private_deals_sampled,
        "public_chance_events_sampled": stats.public_chance_events_sampled,
        "terminal_visits": stats.terminal_visits,
        "policy_sha256": policy.fingerprint(),
        "exploitability_antes": fraction_payload(exploitability),
    }


def train_and_score_external(game, iterations: int, seed: int) -> dict:
    solver = HuMultiStreetExternalSamplingMCCFR(game, seed=seed)
    started = time.perf_counter()
    solver.train(iterations)
    train_seconds = time.perf_counter() - started
    policy = solver.average_policy()
    exact_policy = policy.to_exact_policy()
    exploitability, oracle_seconds = timed_exploitability(game, exact_policy)
    stats = solver.stats()
    return {
        "solver": "float64_external_sampling_mccfr",
        "regret_mode": "vanilla_cfr",
        "seed": seed,
        "iterations": iterations,
        "train_seconds": train_seconds,
        "oracle_seconds": oracle_seconds,
        "infosets": len(solver.nodes),
        "sampled_deals": stats.sampled_deals,
        "sampled_public_chance": stats.sampled_public_chance,
        "sampled_opponent_actions": stats.sampled_opponent_actions,
        "sampled_average_target_actions": stats.sampled_average_target_actions,
        "regret_nodes_visited": stats.regret_nodes_visited,
        "average_nodes_visited": stats.average_nodes_visited,
        "nodes_visited": stats.nodes_visited,
        "policy_sha256": policy.fingerprint(),
        "exploitability_antes": fraction_payload(exploitability),
    }


def parse_seeds(text: str) -> tuple[int, ...]:
    try:
        values = tuple(int(value.strip()) for value in text.split(",") if value.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from exc
    if not values or any(value < 0 for value in values) or len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("seeds must be unique non-negative integers")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-iterations", type=int, default=1)
    parser.add_argument("--float-iterations", type=int, default=1)
    parser.add_argument("--sampled-iterations", type=int, default=50)
    parser.add_argument("--external-iterations", type=int, default=50)
    parser.add_argument("--seeds", type=parse_seeds, default=(17, 29, 43))
    parser.add_argument("--multi-private", action="store_true")
    parser.add_argument("--include-rmplus", action="store_true")
    parser.add_argument("--skip-exact", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    for name in (
        "exact_iterations",
        "float_iterations",
        "sampled_iterations",
        "external_iterations",
    ):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")

    game = benchmark_game(multi_private=args.multi_private)
    rows: list[dict] = []

    baseline, baseline_seconds = timed_exploitability(game, uniform_micro_policy)

    if not args.skip_exact:
        rows.append(train_and_score_exact(game, args.exact_iterations, RegretMode.VANILLA))
        if args.include_rmplus:
            rows.append(train_and_score_exact(game, args.exact_iterations, RegretMode.PLUS))

    rows.append(train_and_score_float(game, args.float_iterations, RegretMode.VANILLA))
    if args.include_rmplus:
        rows.append(train_and_score_float(game, args.float_iterations, RegretMode.PLUS))

    for seed in args.seeds:
        rows.append(train_and_score_chance(game, args.sampled_iterations, seed))
        rows.append(train_and_score_external(game, args.external_iterations, seed))

    payload = {
        "schema": SCHEMA,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "multi_private": args.multi_private,
        "private_deal_count": len(game.deals),
        "uniform_exploitability_antes": fraction_payload(baseline),
        "uniform_oracle_seconds": baseline_seconds,
        "runs": rows,
    }
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
