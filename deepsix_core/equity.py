"""Exact heads-up equity oracle for Short Deck reference tests.

This implementation is correctness-first, not the production trainer hot path.
With two known two-card hands, preflop has C(32, 5) = 201,376 board runouts.
The combinatorics are manageable for offline validation, but the pure-Python
reference evaluator is intentionally not optimized for repeated preflop sweeps.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .cards import NUM_CARDS, ShortDeckCardError, decode_card
from .evaluator import evaluate_best


@dataclass(frozen=True)
class EquityResult:
    wins: int
    ties: int
    losses: int

    @property
    def total(self) -> int:
        return self.wins + self.ties + self.losses

    @property
    def equity(self) -> float:
        if self.total == 0:
            raise ZeroDivisionError("equity result has no runouts")
        return (self.wins + 0.5 * self.ties) / self.total


def exact_heads_up_equity(
    hero_hole: tuple[int, int],
    villain_hole: tuple[int, int],
    board: tuple[int, ...] = (),
) -> EquityResult:
    """Enumerate every legal remaining board and return Hero exact equity."""
    if len(hero_hole) != 2 or len(villain_hole) != 2:
        raise ShortDeckCardError("each player must have exactly two hole cards")
    if len(board) not in (0, 3, 4, 5):
        raise ShortDeckCardError("board must contain 0, 3, 4 or 5 cards")

    known = tuple(hero_hole) + tuple(villain_hole) + tuple(board)
    if len(set(known)) != len(known):
        raise ShortDeckCardError("duplicate known cards")
    for card in known:
        decode_card(card)

    known_set = set(known)
    remaining = tuple(card for card in range(NUM_CARDS) if card not in known_set)
    cards_to_come = 5 - len(board)

    wins = ties = losses = 0
    for runout in combinations(remaining, cards_to_come):
        final_board = tuple(board) + tuple(runout)
        hero_value = evaluate_best(tuple(hero_hole) + final_board)
        villain_value = evaluate_best(tuple(villain_hole) + final_board)
        if hero_value > villain_value:
            wins += 1
        elif hero_value < villain_value:
            losses += 1
        else:
            ties += 1
    return EquityResult(wins=wins, ties=ties, losses=losses)
