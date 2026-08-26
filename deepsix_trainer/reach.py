"""Exact private-range reach propagation for tractable DeepSix audits.

This is a correctness/reference primitive for F5/F6, not a claim that the final
2..6-player solver should enumerate every joint private assignment.  A public
action likelihood multiplies only the acting player's private-hand reach.  When
joint probabilities are needed, card compatibility is imposed explicitly rather
than pretending opponent hands are independent after blocking.

The design is informed by SpinCore Phase2C0/C1's structurally successful
range/reach factorization, while deliberately *not* importing the failed
Phase2C2 conclusion that a richer range/reach target kernel improves a neural
representation.  DeepSix will benchmark that separately if/when neural targets
enter the architecture tournament.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from operator import mul
from typing import Iterable, Mapping, Sequence

from deepsix_core.cards import decode_card


PrivateHand = tuple[int, int]


class ReachError(ValueError):
    pass


def _fraction(value: int | Fraction) -> Fraction:
    if isinstance(value, bool):
        raise ReachError("boolean is not a reach weight")
    if isinstance(value, Fraction):
        result = value
    elif isinstance(value, int):
        result = Fraction(value, 1)
    else:
        raise ReachError("exact reach weights must be int or Fraction")
    if result < 0:
        raise ReachError("reach weight cannot be negative")
    return result


def canonical_private_hand(cards: Sequence[int]) -> PrivateHand:
    if len(cards) != 2:
        raise ReachError("private hand must contain exactly two cards")
    left, right = cards
    try:
        decode_card(left)
        decode_card(right)
    except (TypeError, ValueError) as exc:
        raise ReachError("private hand contains invalid Short Deck card") from exc
    if left == right:
        raise ReachError("private hand contains duplicate card")
    return tuple(sorted((left, right)))


@dataclass(frozen=True)
class PrivateReachVector:
    seat: int
    hands: tuple[PrivateHand, ...]
    weights: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        if isinstance(self.seat, bool) or not isinstance(self.seat, int) or not 0 <= self.seat <= 5:
            raise ReachError("seat must be an integer within 0..5")
        if not self.hands:
            raise ReachError("reach support must be non-empty")
        if len(self.hands) != len(self.weights):
            raise ReachError("reach hands/weights length mismatch")
        canonical = tuple(canonical_private_hand(hand) for hand in self.hands)
        if canonical != self.hands:
            raise ReachError("private hands must already be canonical")
        if len(set(self.hands)) != len(self.hands):
            raise ReachError("reach support contains duplicate private hand")
        exact = tuple(_fraction(weight) for weight in self.weights)
        if exact != self.weights:
            raise ReachError("weights must be exact Fractions")
        if sum(self.weights, Fraction(0, 1)) <= 0:
            raise ReachError("reach vector must contain positive mass")

    @classmethod
    def from_mapping(
        cls,
        seat: int,
        weights: Mapping[Sequence[int], int | Fraction],
    ) -> "PrivateReachVector":
        merged: dict[PrivateHand, Fraction] = {}
        for raw_hand, raw_weight in weights.items():
            hand = canonical_private_hand(raw_hand)
            weight = _fraction(raw_weight)
            if hand in merged:
                raise ReachError("reach mapping contains duplicate canonical hand")
            merged[hand] = weight
        ordered = tuple(sorted(merged))
        return cls(
            seat=seat,
            hands=ordered,
            weights=tuple(merged[hand] for hand in ordered),
        )

    @property
    def total_mass(self) -> Fraction:
        return sum(self.weights, Fraction(0, 1))

    @property
    def normalized(self) -> tuple[Fraction, ...]:
        total = self.total_mass
        return tuple(weight / total for weight in self.weights)

    @property
    def effective_support(self) -> Fraction:
        """Exact inverse-Simpson effective support: (sum w)^2 / sum w^2."""
        denominator = sum((weight * weight for weight in self.weights), Fraction(0, 1))
        if denominator == 0:
            raise ReachError("zero reach-square mass")
        return self.total_mass * self.total_mass / denominator

    def weight_for(self, hand: Sequence[int]) -> Fraction:
        canonical = canonical_private_hand(hand)
        try:
            index = self.hands.index(canonical)
        except ValueError as exc:
            raise ReachError("hand is outside reach support") from exc
        return self.weights[index]

    def multiply_likelihoods(
        self,
        likelihoods: Mapping[Sequence[int], int | Fraction],
    ) -> "PrivateReachVector":
        canonical_likelihoods: dict[PrivateHand, Fraction] = {}
        for raw_hand, raw_probability in likelihoods.items():
            hand = canonical_private_hand(raw_hand)
            if hand in canonical_likelihoods:
                raise ReachError("duplicate canonical likelihood hand")
            probability = _fraction(raw_probability)
            if probability > 1:
                raise ReachError("action likelihood cannot exceed one")
            canonical_likelihoods[hand] = probability
        if set(canonical_likelihoods) != set(self.hands):
            raise ReachError("action likelihood map must cover exact reach support")
        updated = tuple(
            weight * canonical_likelihoods[hand]
            for hand, weight in zip(self.hands, self.weights)
        )
        if sum(updated, Fraction(0, 1)) <= 0:
            raise ReachError("public action eliminated the entire private support")
        return PrivateReachVector(self.seat, self.hands, updated)


@dataclass(frozen=True)
class PublicReachState:
    """Factored per-seat reach state along one public action history."""

    vectors: tuple[PrivateReachVector, ...]
    public_event_count: int = 0

    def __post_init__(self) -> None:
        if not self.vectors:
            raise ReachError("at least one private reach vector is required")
        seats = tuple(vector.seat for vector in self.vectors)
        if seats != tuple(sorted(seats)) or len(set(seats)) != len(seats):
            raise ReachError("reach vectors must be uniquely seat-sorted")
        if isinstance(self.public_event_count, bool) or not isinstance(self.public_event_count, int):
            raise ReachError("public_event_count must be an integer")
        if self.public_event_count < 0:
            raise ReachError("public_event_count cannot be negative")

    @classmethod
    def from_vectors(cls, vectors: Iterable[PrivateReachVector]) -> "PublicReachState":
        return cls(tuple(sorted(vectors, key=lambda item: item.seat)), 0)

    def vector_for(self, seat: int) -> PrivateReachVector:
        for vector in self.vectors:
            if vector.seat == seat:
                return vector
        raise ReachError("unknown reach seat")

    def apply_public_action(
        self,
        actor: int,
        likelihoods: Mapping[Sequence[int], int | Fraction],
    ) -> "PublicReachState":
        found = False
        rows = []
        for vector in self.vectors:
            if vector.seat == actor:
                rows.append(vector.multiply_likelihoods(likelihoods))
                found = True
            else:
                rows.append(vector)
        if not found:
            raise ReachError("public actor is outside reach state")
        return PublicReachState(tuple(rows), self.public_event_count + 1)


def _validate_dead_cards(dead_cards: Iterable[int]) -> frozenset[int]:
    result = []
    for card in dead_cards:
        try:
            decode_card(card)
        except (TypeError, ValueError) as exc:
            raise ReachError("dead-card set contains invalid Short Deck card") from exc
        result.append(card)
    if len(set(result)) != len(result):
        raise ReachError("dead-card set contains duplicate card")
    return frozenset(result)


def compatible_joint_mass(
    vectors: Sequence[PrivateReachVector],
    *,
    dead_cards: Iterable[int] = (),
) -> Fraction:
    """Exact sum of product reach over mutually card-compatible assignments.

    Complexity is exponential in the number/support width of vectors; this is a
    correctness oracle for tractable supports and local audits, not the final
    multiway hot path.
    """

    if not vectors:
        raise ReachError("at least one reach vector is required")
    seats = [vector.seat for vector in vectors]
    if len(set(seats)) != len(seats):
        raise ReachError("joint reach vectors must belong to unique seats")
    blocked = _validate_dead_cards(dead_cards)

    def recurse(index: int, used: frozenset[int], mass: Fraction) -> Fraction:
        if index == len(vectors):
            return mass
        vector = vectors[index]
        total = Fraction(0, 1)
        for hand, weight in zip(vector.hands, vector.weights):
            if weight == 0:
                continue
            cards = frozenset(hand)
            if cards & used:
                continue
            total += recurse(index + 1, used | cards, mass * weight)
        return total

    return recurse(0, blocked, Fraction(1, 1))


def compatible_joint_assignment_count(
    vectors: Sequence[PrivateReachVector],
    *,
    dead_cards: Iterable[int] = (),
    positive_mass_only: bool = True,
) -> int:
    """Count compatible joint private assignments for small audit supports."""

    if not vectors:
        raise ReachError("at least one reach vector is required")
    blocked = _validate_dead_cards(dead_cards)

    def recurse(index: int, used: frozenset[int]) -> int:
        if index == len(vectors):
            return 1
        vector = vectors[index]
        total = 0
        for hand, weight in zip(vector.hands, vector.weights):
            if positive_mass_only and weight == 0:
                continue
            cards = frozenset(hand)
            if cards & used:
                continue
            total += recurse(index + 1, used | cards)
        return total

    return recurse(0, blocked)


def direct_public_history_weight(
    initial_vectors: Sequence[PrivateReachVector],
    events: Sequence[tuple[int, Mapping[Sequence[int], int | Fraction]]],
    assignment: Mapping[int, Sequence[int]],
) -> Fraction:
    """Direct full-history product for one fixed private assignment.

    Used to audit incremental reach propagation.  Returns zero for an
    incompatible assignment or for cards colliding with one another.
    """

    cards: set[int] = set()
    weight = Fraction(1, 1)
    by_seat = {vector.seat: vector for vector in initial_vectors}
    if set(assignment) != set(by_seat):
        raise ReachError("assignment seats must match reach vectors")
    canonical_assignment: dict[int, PrivateHand] = {}
    for seat, raw_hand in assignment.items():
        hand = canonical_private_hand(raw_hand)
        if any(card in cards for card in hand):
            return Fraction(0, 1)
        cards.update(hand)
        canonical_assignment[seat] = hand
        weight *= by_seat[seat].weight_for(hand)
    for actor, likelihoods in events:
        if actor not in canonical_assignment:
            raise ReachError("event actor outside assignment")
        canonical = {
            canonical_private_hand(hand): _fraction(probability)
            for hand, probability in likelihoods.items()
        }
        if any(value > 1 for value in canonical.values()):
            raise ReachError("action likelihood cannot exceed one")
        try:
            weight *= canonical[canonical_assignment[actor]]
        except KeyError as exc:
            raise ReachError("event likelihood map does not cover assigned hand") from exc
    return weight


def factorized_assignment_weight(
    state: PublicReachState,
    assignment: Mapping[int, Sequence[int]],
) -> Fraction:
    """Product of incrementally propagated reaches for one compatible assignment."""

    if set(assignment) != {vector.seat for vector in state.vectors}:
        raise ReachError("assignment seats must match reach state")
    used: set[int] = set()
    weights = []
    for vector in state.vectors:
        hand = canonical_private_hand(assignment[vector.seat])
        if any(card in used for card in hand):
            return Fraction(0, 1)
        used.update(hand)
        weights.append(vector.weight_for(hand))
    return reduce(mul, weights, Fraction(1, 1))
