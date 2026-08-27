"""Exact range-weighted board-chance oracle for DeepSix F5.

The fixed-assignment chance oracle answers "which board reveal is next when all
private cards are known?".  Imperfect-information traversal needs one layer
above that: private hands are uncertain and weighted by the current public
reach.  Card removal then makes the *marginal* probability of a public reveal
depend on the range/reach state.

For one reveal R and a set of factored private reach vectors, this module uses

    P(R | public history, fixed private cards)
      = compatible_reach_mass(R)
        / total_compatible_reach_mass
        / physical_reveals_per_private_assignment

Every compatible private assignment fixes the same number of cards, so the
physical chance denominator is constant across assignments.  All arithmetic is
exact ``Fraction`` arithmetic.  The implementation is deliberately a small-
support correctness oracle; production traversal may later sample or cache the
same distribution after proving parity.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import itertools
import math
from typing import Sequence

from deepsix_core.cards import NUM_CARDS, decode_card
from deepsix_core.state import Street

from .reach import (
    PrivateReachVector,
    PublicReachState,
    ReachError,
    compatible_joint_mass,
)


class RangeWeightedChanceError(ValueError):
    """Raised when a range-conditioned chance state is malformed."""


@dataclass(frozen=True)
class RangeWeightedChanceOutcome:
    street: Street
    revealed: tuple[int, ...]
    next_board: tuple[int, ...]
    compatible_reach_mass: Fraction
    probability: Fraction


def _validate_cards(cards: Sequence[int], *, name: str) -> tuple[int, ...]:
    values = tuple(cards)
    if len(set(values)) != len(values):
        raise RangeWeightedChanceError(f"{name} contains duplicate cards")
    try:
        for card in values:
            decode_card(card)
    except (TypeError, ValueError) as exc:
        raise RangeWeightedChanceError(
            f"{name} contains invalid Short Deck card"
        ) from exc
    return values


def _resolve_vectors(
    reach: PublicReachState | Sequence[PrivateReachVector],
) -> tuple[PrivateReachVector, ...]:
    if isinstance(reach, PublicReachState):
        vectors = reach.vectors
    else:
        vectors = tuple(reach)
    if any(not isinstance(vector, PrivateReachVector) for vector in vectors):
        raise RangeWeightedChanceError(
            "reach must contain only PrivateReachVector objects"
        )
    seats = tuple(vector.seat for vector in vectors)
    if len(set(seats)) != len(seats):
        raise RangeWeightedChanceError("reach vectors must belong to unique seats")
    return vectors


def _street_geometry(board: tuple[int, ...]) -> tuple[Street | None, int]:
    if len(board) == 0:
        return Street.FLOP, 3
    if len(board) == 3:
        return Street.TURN, 1
    if len(board) == 4:
        return Street.RIVER, 1
    if len(board) == 5:
        return None, 0
    raise RangeWeightedChanceError("board must contain 0, 3, 4 or 5 cards")


def _next_board(board: tuple[int, ...], revealed: tuple[int, ...]) -> tuple[int, ...]:
    if len(board) == 0:
        return tuple(sorted(revealed))
    return board + revealed


def enumerate_range_weighted_board_chance(
    board: Sequence[int],
    reach: PublicReachState | Sequence[PrivateReachVector],
    *,
    fixed_private_cards: Sequence[int] = (),
) -> tuple[RangeWeightedChanceOutcome, ...]:
    """Marginalize exact board chance over a tractable private reach state.

    ``fixed_private_cards`` represents complete known private cards that are not
    already represented by a reach vector, typically the traverser's two-card
    hand.  Each reach vector represents one additional player's two-card private
    support.  Do not represent the same private player in both places.

    Zero-probability reveals are omitted from the returned support.
    """

    board = _validate_cards(board, name="board")
    next_street, reveal_count = _street_geometry(board)
    fixed = _validate_cards(fixed_private_cards, name="fixed_private_cards")
    if len(fixed) % 2 != 0:
        raise RangeWeightedChanceError(
            "fixed_private_cards must contain complete two-card private hands"
        )
    if set(board) & set(fixed):
        raise RangeWeightedChanceError("public and fixed private cards overlap")

    vectors = _resolve_vectors(reach)
    private_player_count = len(fixed) // 2 + len(vectors)
    if private_player_count < 1 or private_player_count > 6:
        raise RangeWeightedChanceError(
            "chance oracle requires private support for 1..6 players"
        )

    if next_street is None:
        return ()

    base_dead = board + fixed
    try:
        if vectors:
            total_mass = compatible_joint_mass(vectors, dead_cards=base_dead)
        else:
            total_mass = Fraction(1, 1)
    except ReachError as exc:
        raise RangeWeightedChanceError(str(exc)) from exc
    if total_mass <= 0:
        raise RangeWeightedChanceError(
            "public/fixed cards eliminate the entire private reach support"
        )

    cards_left_per_assignment = (
        NUM_CARDS - len(board) - len(fixed) - 2 * len(vectors)
    )
    if cards_left_per_assignment < reveal_count:
        raise RangeWeightedChanceError(
            "insufficient physical cards for next board reveal"
        )
    physical_reveals_per_assignment = math.comb(
        cards_left_per_assignment, reveal_count
    )
    if physical_reveals_per_assignment <= 0:
        raise RangeWeightedChanceError("physical chance denominator is empty")

    globally_available = tuple(
        card for card in range(NUM_CARDS) if card not in set(base_dead)
    )
    if reveal_count == 3:
        candidates = itertools.combinations(globally_available, 3)
    else:
        candidates = ((card,) for card in globally_available)

    outcomes: list[RangeWeightedChanceOutcome] = []
    denominator = total_mass * physical_reveals_per_assignment
    for raw_reveal in candidates:
        revealed = tuple(raw_reveal)
        try:
            if vectors:
                reveal_mass = compatible_joint_mass(
                    vectors,
                    dead_cards=base_dead + revealed,
                )
            else:
                reveal_mass = Fraction(1, 1)
        except ReachError as exc:  # pragma: no cover - inputs validated above
            raise RangeWeightedChanceError(str(exc)) from exc
        if reveal_mass == 0:
            continue
        probability = reveal_mass / denominator
        outcomes.append(
            RangeWeightedChanceOutcome(
                street=next_street,
                revealed=revealed,
                next_board=_next_board(board, revealed),
                compatible_reach_mass=reveal_mass,
                probability=probability,
            )
        )

    if not outcomes:
        raise RangeWeightedChanceError("range-weighted chance support is empty")
    total_probability = sum(
        (outcome.probability for outcome in outcomes), Fraction(0, 1)
    )
    if total_probability != 1:
        raise RangeWeightedChanceError(
            "range-weighted chance probabilities do not sum exactly to one"
        )
    return tuple(outcomes)
