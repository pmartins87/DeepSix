#!/usr/bin/env python3
"""Emit a timing-free exact digest for external-sampling reproducibility gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deepsix_trainer.river_external_sampling import (  # noqa: E402
    RiverExternalSamplingMCCFR,
    external_sampling_config_fingerprint,
)
from deepsix_trainer.river_lab_fixtures import benchmark_fixture_battery  # noqa: E402
from deepsix_trainer.river_multisize_one_raise_dpbr import exploitability_dp  # noqa: E402


def policy_payload(policy) -> list[dict]:
    rows = []
    for (player, cards, history), probabilities in sorted(policy.strategies.items()):
        rows.append(
            {
                "player": player,
                "cards": list(cards),
                "history": list(history),
                "probability_hex": [float(value).hex() for value in probabilities],
            }
        )
    return rows


def build_digest(*, fixture_index: int, iterations: int, seed: int) -> dict:
    battery = benchmark_fixture_battery()
    if fixture_index < 0 or fixture_index >= len(battery):
        raise ValueError("fixture_index outside benchmark battery")
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if seed < 0:
        raise ValueError("seed must be non-negative")

    spec, config = battery[fixture_index]
    trainer = RiverExternalSamplingMCCFR(config, seed=seed)
    trainer.train(iterations)
    policy = trainer.average_policy()
    semantic = {
        "schema": "deepsix_external_sampling_repro_digest_v1",
        "fixture": spec.name,
        "config_sha256": external_sampling_config_fingerprint(config),
        "iterations": iterations,
        "seed": seed,
        "sampled_deals": trainer.sampled_deals,
        "nodes_visited": trainer.nodes_visited,
        "checkpoint_sha256": trainer.checkpoint_sha256(),
        "exploitability_hex": float(exploitability_dp(config, policy)).hex(),
        "policy": policy_payload(policy),
    }
    canonical = json.dumps(
        semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        **semantic,
        "semantic_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-index", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260826)
    args = parser.parse_args()
    try:
        result = build_digest(
            fixture_index=args.fixture_index,
            iterations=args.iterations,
            seed=args.seed,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
