"""Scalable action-set wrapper for the multi-size + one-raise river game.

The original v1 game intentionally caps initial bet sizes at two because its
primary exact-BR oracle enumerates complete pure response plans.  After the
dynamic exact best response was implemented and gated against that enumerative
oracle, this module safely lifts the *trainer* laboratory to as many as four
initial sizings while keeping the same tree semantics.

Only the validation boundary changes.  CFR, chance, utilities and policies are
reused directly from the already-gated game.  Exact exploitability in this
module always uses the dynamic best response; it never calls the exponential
pure-plan enumerator.
"""

from __future__ import annotations

from dataclasses import dataclass

from deepsix_core.cards import ShortDeckCardError, decode_card
from .river_multisize_one_raise import (
    RiverMultiSizeOneRaiseCFR,
    RiverMultiSizeOneRaiseConfig,
    RiverMultiSizeOneRaiseError,
    RiverMultiSizeOneRaisePolicy,
    pure_plan_count,
    uniform_policy,
)
from .river_multisize_one_raise_dpbr import (
    best_response_value_player0_dp,
    best_response_value_player1_dp,
    exploitability_dp,
)


MAX_SCALABLE_INITIAL_SIZES = 4


@dataclass(frozen=True)
class ScalableRiverMultiSizeOneRaiseConfig(RiverMultiSizeOneRaiseConfig):
    """Same game semantics as v1, but 1..4 initial bet sizes are allowed."""

    def validate(self) -> None:
        if len(self.board) != 5 or len(set(self.board)) != 5:
            raise RiverMultiSizeOneRaiseError(
                "river board must contain five distinct cards"
            )
        try:
            for card in self.board:
                decode_card(card)
        except ShortDeckCardError as exc:
            raise RiverMultiSizeOneRaiseError(str(exc)) from exc
        if isinstance(self.pot, bool) or not isinstance(self.pot, int) or self.pot <= 0:
            raise RiverMultiSizeOneRaiseError("pot must be a positive integer")
        if not self.bet_sizes:
            raise RiverMultiSizeOneRaiseError("at least one bet size is required")
        if len(self.bet_sizes) > MAX_SCALABLE_INITIAL_SIZES:
            raise RiverMultiSizeOneRaiseError(
                f"scalable lab caps initial bet sizes at {MAX_SCALABLE_INITIAL_SIZES}"
            )
        previous = 0
        for size in self.bet_sizes:
            if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
                raise RiverMultiSizeOneRaiseError(
                    "bet sizes must be positive integers"
                )
            if size <= previous:
                raise RiverMultiSizeOneRaiseError(
                    "bet sizes must be unique and strictly increasing"
                )
            previous = size
        if (
            isinstance(self.raise_to, bool)
            or not isinstance(self.raise_to, int)
            or self.raise_to <= max(self.bet_sizes)
        ):
            raise RiverMultiSizeOneRaiseError(
                "raise_to must be an integer strictly above every bet size"
            )
        if not self.p0_range or not self.p1_range:
            raise RiverMultiSizeOneRaiseError("both ranges must be non-empty")

        board_set = set(self.board)
        for label, hands in (("p0", self.p0_range), ("p1", self.p1_range)):
            seen: set[tuple[int, int]] = set()
            for hand in hands:
                try:
                    cards = hand.canonical_cards()
                except Exception as exc:
                    raise RiverMultiSizeOneRaiseError(str(exc)) from exc
                if set(cards) & board_set:
                    raise RiverMultiSizeOneRaiseError(f"{label} range overlaps board")
                if cards in seen:
                    raise RiverMultiSizeOneRaiseError(
                        f"duplicate exact combo in {label} range"
                    )
                seen.add(cards)
        if not self.compatible_deals():
            raise RiverMultiSizeOneRaiseError(
                "ranges contain no compatible chance deal"
            )


def exact_best_response_value_player0(
    config: ScalableRiverMultiSizeOneRaiseConfig,
    opponent: RiverMultiSizeOneRaisePolicy,
) -> float:
    return best_response_value_player0_dp(config, opponent)


def exact_best_response_value_player1(
    config: ScalableRiverMultiSizeOneRaiseConfig,
    opponent: RiverMultiSizeOneRaisePolicy,
) -> float:
    return best_response_value_player1_dp(config, opponent)


def exact_exploitability(
    config: ScalableRiverMultiSizeOneRaiseConfig,
    policy: RiverMultiSizeOneRaisePolicy,
) -> float:
    return exploitability_dp(config, policy)


__all__ = [
    "MAX_SCALABLE_INITIAL_SIZES",
    "ScalableRiverMultiSizeOneRaiseConfig",
    "RiverMultiSizeOneRaiseCFR",
    "RiverMultiSizeOneRaisePolicy",
    "uniform_policy",
    "pure_plan_count",
    "exact_best_response_value_player0",
    "exact_best_response_value_player1",
    "exact_exploitability",
]
