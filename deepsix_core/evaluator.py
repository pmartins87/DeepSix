"""Correctness-first Short Deck hand evaluator.

Target default is the KKPoker 6+ ranking:
straight flush > quads > flush > full house > straight > trips > two pair
> pair > high card.

The unusual A6789 wheel is supported with a straight high card of 9.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import IntEnum
from itertools import combinations
from typing import Iterable, Sequence

from .cards import ShortDeckCardError, decode_card


class HandCategory(IntEnum):
    HIGH_CARD = 0
    ONE_PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FULL_HOUSE = 5
    FLUSH = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8


@dataclass(frozen=True)
class HandValue:
    category: HandCategory
    tiebreak: tuple[int, ...]

    def _key(self) -> tuple[int, tuple[int, ...]]:
        return int(self.category), self.tiebreak

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, HandValue):
            return NotImplemented
        return self._key() < other._key()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, HandValue):
            return NotImplemented
        return self._key() <= other._key()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, HandValue):
            return NotImplemented
        return self._key() > other._key()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, HandValue):
            return NotImplemented
        return self._key() >= other._key()


def _validated_cards(cards: Iterable[int], expected: int | None = None) -> tuple[int, ...]:
    out = tuple(cards)
    if expected is not None and len(out) != expected:
        raise ShortDeckCardError(f"expected {expected} cards, got {len(out)}")
    if len(set(out)) != len(out):
        raise ShortDeckCardError("duplicate cards are not legal")
    for card in out:
        decode_card(card)
    return out


def rank_value(card: int) -> int:
    """Return conventional numeric rank 6..14."""
    decoded = decode_card(card)
    rank = decoded.rank
    if rank == "A":
        return 14
    if rank == "K":
        return 13
    if rank == "Q":
        return 12
    if rank == "J":
        return 11
    if rank == "T":
        return 10
    return int(rank)


def straight_high(ranks: Sequence[int]) -> int | None:
    """Return straight high card, including A6789 as a 9-high straight."""
    unique = set(int(r) for r in ranks)
    if len(unique) != 5:
        return None
    if unique == {14, 6, 7, 8, 9}:
        return 9
    ordered = sorted(unique)
    if all(ordered[i + 1] == ordered[i] + 1 for i in range(4)):
        return ordered[-1]
    return None


def evaluate_five(cards: Iterable[int]) -> HandValue:
    """Evaluate exactly five cards under the KKPoker 6+ ranking."""
    five = _validated_cards(cards, expected=5)
    ranks = [rank_value(card) for card in five]
    suits = [decode_card(card).suit for card in five]
    counts = Counter(ranks)
    by_count_then_rank = sorted(
        counts.items(), key=lambda item: (item[1], item[0]), reverse=True
    )
    is_flush = len(set(suits)) == 1
    sh = straight_high(ranks)

    if is_flush and sh is not None:
        return HandValue(HandCategory.STRAIGHT_FLUSH, (sh,))

    if by_count_then_rank[0][1] == 4:
        quad = by_count_then_rank[0][0]
        kicker = max(rank for rank in ranks if rank != quad)
        return HandValue(HandCategory.FOUR_OF_A_KIND, (quad, kicker))

    # KKPoker Short Deck: flush outranks full house.
    if is_flush:
        return HandValue(HandCategory.FLUSH, tuple(sorted(ranks, reverse=True)))

    if (
        by_count_then_rank[0][1] == 3
        and len(by_count_then_rank) > 1
        and by_count_then_rank[1][1] == 2
    ):
        return HandValue(
            HandCategory.FULL_HOUSE,
            (by_count_then_rank[0][0], by_count_then_rank[1][0]),
        )

    if sh is not None:
        return HandValue(HandCategory.STRAIGHT, (sh,))

    if by_count_then_rank[0][1] == 3:
        trips = by_count_then_rank[0][0]
        kickers = sorted((rank for rank in ranks if rank != trips), reverse=True)
        return HandValue(HandCategory.THREE_OF_A_KIND, (trips, *kickers))

    pairs = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)
    if len(pairs) == 2:
        kicker = max(rank for rank in ranks if rank not in pairs)
        return HandValue(HandCategory.TWO_PAIR, (pairs[0], pairs[1], kicker))

    if len(pairs) == 1:
        pair = pairs[0]
        kickers = sorted((rank for rank in ranks if rank != pair), reverse=True)
        return HandValue(HandCategory.ONE_PAIR, (pair, *kickers))

    return HandValue(HandCategory.HIGH_CARD, tuple(sorted(ranks, reverse=True)))


def evaluate_best(cards: Iterable[int]) -> HandValue:
    """Evaluate the best five-card hand from 5, 6 or 7 cards."""
    all_cards = _validated_cards(cards)
    if len(all_cards) not in (5, 6, 7):
        raise ShortDeckCardError(
            f"best-hand evaluation requires 5, 6 or 7 cards, got {len(all_cards)}"
        )
    return max(evaluate_five(combo) for combo in combinations(all_cards, 5))
