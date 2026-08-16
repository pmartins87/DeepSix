"""Deterministic river benchmark fixtures spanning several Short Deck textures.

Single hand-picked microgames are useful for unit tests but dangerous for model
selection.  This module creates a small, reproducible fixture battery whose
private ranges are selected mechanically from the full exact combo space rather
than chosen to favor one abstraction.

For each fixed board:

1. enumerate every legal exact two-card combo from the 31 unseen cards;
2. rank combos by the validated Short Deck ``HandValue`` on that river;
3. choose P0 and P1 ranges at two interleaved sets of evenly spaced quantile
   positions across the complete strength ordering.

The two phase offsets make the exact ranges distinct while covering weak,
medium and strong terminal hands.  Blockers remain fully real: chance-deal
construction later removes incompatible P0/P1 pairs exactly.

These fixtures are still synthetic.  They are intended for comparative
algorithm/abstraction benchmarks before real KKPoker range distributions are
available; they are not claims about population ranges or production strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from deepsix_core.cards import NUM_CARDS, parse_card
from deepsix_core.evaluator import evaluate_best
from .river_microgame import RangeHand
from .river_multisize_one_raise_scalable import (
    ScalableRiverMultiSizeOneRaiseConfig,
)


class RiverLabFixtureError(ValueError):
    pass


@dataclass(frozen=True)
class RiverLabFixtureSpec:
    name: str
    board_text: tuple[str, str, str, str, str]
    pot: int
    bet_sizes: tuple[int, ...]
    raise_to: int
    range_size: int = 10

    def board(self) -> tuple[int, int, int, int, int]:
        cards = tuple(parse_card(text) for text in self.board_text)
        if len(set(cards)) != 5:
            raise RiverLabFixtureError(f"fixture {self.name} board is not unique")
        return cards  # type: ignore[return-value]


FIXTURE_SPECS: tuple[RiverLabFixtureSpec, ...] = (
    RiverLabFixtureSpec(
        "broadway_dry",
        ("Ac", "Kd", "Qs", "8d", "6s"),
        pot=12,
        bet_sizes=(3, 6),
        raise_to=12,
    ),
    RiverLabFixtureSpec(
        "paired_ace",
        ("Ac", "Ad", "Ks", "9h", "6c"),
        pot=16,
        bet_sizes=(4, 8),
        raise_to=14,
    ),
    RiverLabFixtureSpec(
        "four_flush",
        ("Ah", "Kh", "Jh", "8h", "6c"),
        pot=14,
        bet_sizes=(3, 7),
        raise_to=13,
    ),
    RiverLabFixtureSpec(
        "low_connected",
        ("6c", "7d", "8s", "9h", "Qc"),
        pot=18,
        bet_sizes=(4, 9),
        raise_to=16,
    ),
    RiverLabFixtureSpec(
        "double_paired",
        ("Kc", "Kd", "8s", "8h", "6c"),
        pot=20,
        bet_sizes=(5, 10),
        raise_to=18,
    ),
    RiverLabFixtureSpec(
        "four_straight_broadway",
        ("As", "Kd", "Qc", "Jh", "7s"),
        pot=15,
        bet_sizes=(4, 8),
        raise_to=15,
    ),
)


def _all_ranked_hole_combos(
    board: tuple[int, int, int, int, int],
) -> tuple[tuple[int, int], ...]:
    board_set = set(board)
    remaining = tuple(card for card in range(NUM_CARDS) if card not in board_set)
    ranked = []
    for cards in combinations(remaining, 2):
        value = evaluate_best(cards + board)
        ranked.append((value, cards))
    ranked.sort(key=lambda item: (item[0]._key(), item[1]))
    return tuple(cards for _, cards in ranked)


def _quantile_sample(
    ranked: tuple[tuple[int, int], ...],
    *,
    count: int,
    phase_numerator: int,
    phase_denominator: int,
) -> tuple[tuple[int, int], ...]:
    if count <= 0 or count > len(ranked):
        raise RiverLabFixtureError("invalid fixture range size")
    if phase_denominator <= 0 or not 0 <= phase_numerator < phase_denominator:
        raise RiverLabFixtureError("invalid quantile phase")

    # index = floor(n * (k + phase) / count), computed with integers for exact
    # reproducibility across Python/platform versions.
    n = len(ranked)
    sampled = []
    seen = set()
    for k in range(count):
        numerator = (k * phase_denominator + phase_numerator) * n
        denominator = count * phase_denominator
        index = min(n - 1, numerator // denominator)
        cards = ranked[index]
        if cards in seen:
            raise RiverLabFixtureError(
                "quantile sampling produced duplicate combo; increase combo space"
            )
        seen.add(cards)
        sampled.append(cards)
    return tuple(sampled)


def build_fixture(spec: RiverLabFixtureSpec) -> ScalableRiverMultiSizeOneRaiseConfig:
    board = spec.board()
    ranked = _all_ranked_hole_combos(board)
    p0_cards = _quantile_sample(
        ranked,
        count=spec.range_size,
        phase_numerator=1,
        phase_denominator=4,
    )
    p1_cards = _quantile_sample(
        ranked,
        count=spec.range_size,
        phase_numerator=3,
        phase_denominator=4,
    )
    if set(p0_cards) & set(p1_cards):
        raise RiverLabFixtureError(
            f"fixture {spec.name} interleaved ranges unexpectedly overlap exactly"
        )

    config = ScalableRiverMultiSizeOneRaiseConfig(
        board=board,
        pot=spec.pot,
        bet_sizes=spec.bet_sizes,
        raise_to=spec.raise_to,
        p0_range=tuple(RangeHand(cards) for cards in p0_cards),
        p1_range=tuple(RangeHand(cards) for cards in p1_cards),
    )
    config.validate()
    return config


def benchmark_fixture_battery() -> tuple[
    tuple[RiverLabFixtureSpec, ScalableRiverMultiSizeOneRaiseConfig], ...
]:
    return tuple((spec, build_fixture(spec)) for spec in FIXTURE_SPECS)
