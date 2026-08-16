#!/usr/bin/env python3
"""Verify the native Short Deck evaluator against the Python reference oracle.

The C++ fixture emits an FNV-1a digest over every 5-card combination and over
fixed deterministic samples of 6-card and 7-card best-hand evaluations.  This
script independently recomputes the same streams with ``deepsix_core`` and
requires exact equality.
"""

from __future__ import annotations

import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

from deepsix_core.evaluator import HandValue, evaluate_best, evaluate_five


FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211
MASK64 = (1 << 64) - 1


def encode_hand_value(value: HandValue) -> int:
    encoded = int(value.category)
    encoded = (encoded << 4) | len(value.tiebreak)
    for index in range(5):
        rank = value.tiebreak[index] if index < len(value.tiebreak) else 0
        if rank < 0 or rank > 15:
            raise AssertionError(f"tiebreak rank outside packed range: {rank}")
        encoded = (encoded << 4) | rank
    return encoded


def fnv_update(hash_value: int, value: int) -> int:
    for index in range(8):
        hash_value ^= (value >> (index * 8)) & 0xFF
        hash_value = (hash_value * FNV_PRIME) & MASK64
    return hash_value


class Lcg64:
    def __init__(self, seed: int):
        self.state = seed & MASK64

    def next_u32(self) -> int:
        self.state = (
            self.state * 6364136223846793005 + 1442695040888963407
        ) & MASK64
        return (self.state >> 32) & 0xFFFFFFFF


def sample_unique_cards(rng: Lcg64, count: int) -> tuple[int, ...]:
    deck = list(range(36))
    for index in range(count):
        remaining = 36 - index
        swap_index = index + (rng.next_u32() % remaining)
        deck[index], deck[swap_index] = deck[swap_index], deck[index]
    return tuple(deck[:count])


def sample_best_digest(card_count: int, samples: int, seed: int) -> int:
    rng = Lcg64(seed)
    digest = FNV_OFFSET
    for _ in range(samples):
        value = evaluate_best(sample_unique_cards(rng, card_count))
        digest = fnv_update(digest, encode_hand_value(value))
    return digest


def parse_fixture(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        if "=" not in raw_line:
            raise AssertionError(f"malformed fixture line: {raw_line!r}")
        key, value = raw_line.split("=", 1)
        if key in result:
            raise AssertionError(f"duplicate fixture key: {key}")
        result[key] = value
    return result


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_native_evaluator_digest.py <fixture.txt>")
    fixture = parse_fixture(Path(sys.argv[1]))

    five_digest = FNV_OFFSET
    category_counts: Counter[int] = Counter()
    five_total = 0
    for cards in combinations(range(36), 5):
        value = evaluate_five(cards)
        five_digest = fnv_update(five_digest, encode_hand_value(value))
        category_counts[int(value.category)] += 1
        five_total += 1

    expected_counts = ",".join(str(category_counts[index]) for index in range(9))
    checks = {
        "five_total": str(five_total),
        "five_digest": f"{five_digest:016x}",
        "five_counts": expected_counts,
        "six_samples": "4000",
        "six_digest": f"{sample_best_digest(6, 4000, 0x6D5A56DA2D4F1B3C):016x}",
        "seven_samples": "6000",
        "seven_digest": f"{sample_best_digest(7, 6000, 0x9E3779B97F4A7C15):016x}",
    }

    missing = set(checks) - set(fixture)
    if missing:
        raise AssertionError(f"fixture missing keys: {sorted(missing)}")
    for key, expected in checks.items():
        actual = fixture[key]
        if actual != expected:
            raise AssertionError(
                f"native evaluator mismatch for {key}: actual={actual} expected={expected}"
            )

    print(
        "native evaluator parity PASS: "
        f"{five_total} exhaustive five-card hands, 4000 six-card samples, "
        "6000 seven-card samples"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
