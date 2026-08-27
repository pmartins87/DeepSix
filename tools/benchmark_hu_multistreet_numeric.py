#!/usr/bin/env python3
"""Benchmark exact Fraction CFR against float64 CFR on the gated F5 HU game."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import time

from deepsix_core.cards import parse_card
from deepsix_trainer.hu_multistreet_cfr import ExactHuMultiStreetCFR, RegretMode
from deepsix_trainer.hu_multistreet_float_cfr import (
    FloatHuMultiStreetCFR,
    exact_float_max_errors,
)
from deepsix_trainer.hu_multistreet_reference import HuMicrogameConfig, HuReferenceMicrogame
from deepsix_trainer.reach import PrivateReachVector


def cards(*texts):
    return tuple(parse_card(text) for text in texts)


def fixture() -> HuReferenceMicrogame:
    return HuReferenceMicrogame(
        HuMicrogameConfig(
            stake_cents=25,
            dealer_seat=0,
            stacks=((0, 51), (1, 51)),
            flop=cards("6c", "7d", "8h"),
            bbj_enabled=False,
        ),
        (
            PrivateReachVector.from_mapping(0, {cards("As", "Ks"): 1}),
            PrivateReachVector.from_mapping(1, {cards("Qc", "Jc"): 1}),
        ),
    )


def timed_train(solver, iterations: int) -> float:
    started = time.perf_counter()
    solver.train(iterations)
    return time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument(
        "--mode",
        choices=[item.value for item in RegretMode],
        default=RegretMode.VANILLA.value,
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be positive")

    mode = RegretMode(args.mode)
    exact = ExactHuMultiStreetCFR(fixture(), regret_mode=mode)
    float64 = FloatHuMultiStreetCFR(fixture(), regret_mode=mode)

    exact_seconds = timed_train(exact, args.iterations)
    float_seconds = timed_train(float64, args.iterations)
    errors = exact_float_max_errors(exact, float64)

    payload = {
        "schema": "DEEPSIX_F5_NUMERIC_PARITY_BENCHMARK_V1",
        "iterations": args.iterations,
        "regret_mode": mode.value,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "exact_seconds": exact_seconds,
        "float64_seconds": float_seconds,
        "speedup_exact_over_float64": (
            exact_seconds / float_seconds if float_seconds > 0.0 else None
        ),
        "exact_infosets": len(exact.nodes),
        "float64_infosets": len(float64.nodes),
        **errors,
        "exact_policy_fingerprint": exact.average_policy().fingerprint(),
        "float64_policy_fingerprint": float64.average_policy().fingerprint(),
    }
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
