"""Exact board-chance enumeration oracle for DeepSix multi-street work.

The production solver may later sample chance, but tractable regression fixtures
need a mathematical reference. Given a *complete private assignment* for the
players represented by the traversal, this module enumerates every legal next
public board reveal with exact rational probability.

It deliberately does not marginalize unknown opponent cards. Range/reach
integration belongs one layer above this oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import itertools
from typing import Iterable, Sequence

from deepsix_core.cards import NUM_CARDS, decode_card
from deepsix_core.state import Street


class MultiStreetChanceError(ValueError):
    """Raised when an exact chance support is malformed."""


@dataclass(frozen=True)
class ExactChanceOutcome:
    street: Street
    revealed: tuple[int, ...]
    next_board: tuple[int, ...]
    probability: Fraction


def _validate_cards(cards: Sequence[int], *, name: str) -> tuple[int, ...]:
    values = tuple(cards)
    if len(set(values)) != len(values):
        raise MultiStreetChanceError(f"{name} contains duplicate cards")
    try:
        for card in values:
            decode_card(card)
    except (TypeError, ValueError) as exc:
        raise MultiStreetChanceError(f"{name} contains invalid Short Deck card") from exc
    return values


def _street_from_board(board: tuple[int, ...]) -> Street:
    return {
        0: Street.PREFLOP,
        3: Street.FLOP,
        4: Street.TURN,
        5: Street.RIVER,
    }[len(board)]


def enumerate_exact_board_chance(
    board: Sequence[int],
    private_cards: Iterable[int],
) -> tuple[ExactChanceOutcome, ...]:
    """Enumerate the next public reveal for one exact private-card assignment.

    ``private_cards`` must contain every private card that is fixed in the
    traversal branch. The caller is responsible for integrating this oracle
    over range/reach assignments when private cards are uncertain.
    """
    board = _validate_cards(board, name="board")
    if len(board) not in (0, 3, 4, 5):
        raise MultiStreetChanceError("board must contain 0, 3, 4 or 5 cards")
    private = _validate_cards(tuple(private_cards), name="private_cards")
    if set(board) & set(private):
        raise MultiStreetChanceError("public and private cards overlap")

    street = _street_from_board(board)
    if street == Street.RIVER:
        return ()

    used = set(board) | set(private)
    remaining = tuple(card for card in range(NUM_CARDS) if card not in used)
    reveal_count = 3 if street == Street.PREFLOP else 1
    if len(remaining) < reveal_count:
        raise MultiStreetChanceError("insufficient cards for next public reveal")

    if reveal_count == 3:
        reveals = tuple(itertools.combinations(remaining, 3))
    else:
        reveals = tuple((card,) for card in remaining)
    if not reveals:
        raise MultiStreetChanceError("chance support is unexpectedly empty")

    probability = Fraction(1, len(reveals))
    outcomes: list[ExactChanceOutcome] = []
    for revealed in reveals:
        if street == Street.PREFLOP:
            next_board = tuple(sorted(revealed))
            next_street = Street.FLOP
        elif street == Street.FLOP:
            next_board = tuple(board[:3]) + revealed
            next_street = Street.TURN
        elif street == Street.TURN:
            next_board = tuple(board[:4]) + revealed
            next_street = Street.RIVER
        else:  # pragma: no cover - protected above
            raise MultiStreetChanceError("unsupported street")
        outcomes.append(
            ExactChanceOutcome(
                street=next_street,
                revealed=tuple(revealed),
                next_board=next_board,
                probability=probability,
            )
        )

    if sum((outcome.probability for outcome in outcomes), Fraction(0, 1)) != 1:
        raise MultiStreetChanceError("exact chance probabilities do not sum to one")
    return tuple(outcomes)
