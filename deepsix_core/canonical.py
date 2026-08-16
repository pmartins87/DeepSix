"""Exact semantic canonicalization for DeepSix strategic states.

The canonicalizer removes only invariances that are mathematically exact:
- physical chair labels (positions become relative to the Dealer among dealt seats);
- order of the two Hero hole cards;
- order of the three simultaneously dealt flop cards;
- global suit-name permutations.

It deliberately does *not* abstract stack sizes, pot sizes, action sizes, turn/river
order or action history. Those may be approximated later by the trainer, but they
are strategically meaningful and must remain distinct in the correctness core.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import asdict, dataclass

from .cards import SUITS, decode_card, encode_card
from .state import ActionKind, Street, TableObservation


class CanonicalizationError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalSeat:
    position: int
    folded: bool
    all_in: bool
    stack: int
    committed_street: int
    committed_total: int


@dataclass(frozen=True)
class CanonicalAction:
    seq: int
    street: Street
    actor_position: int
    action: ActionKind
    amount_to: int | None = None


@dataclass(frozen=True)
class CanonicalState:
    schema_version: int
    street: Street
    num_players: int
    hero_position: int
    hero_cards: tuple[int, int]
    board: tuple[int, ...]
    seats: tuple[CanonicalSeat, ...]
    actions: tuple[CanonicalAction, ...]
    ante: int
    pot: int
    to_call: int
    min_raise_to: int
    max_raise_to: int

    def fingerprint(self) -> str:
        payload = asdict(self)
        payload["street"] = self.street.value
        payload["actions"] = [
            {
                "seq": action.seq,
                "street": action.street.value,
                "actor_position": action.actor_position,
                "action": action.action.value,
                "amount_to": action.amount_to,
            }
            for action in self.actions
        ]
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def _clockwise_dealt_seats(observation: TableObservation) -> tuple[int, ...]:
    dealt = {seat.seat for seat in observation.seats if seat.dealt}
    if observation.dealer_seat not in dealt:
        raise CanonicalizationError("dealer must be dealt in a strategic state")
    if observation.hero_seat not in dealt:
        raise CanonicalizationError("hero must be dealt in a strategic state")
    if len(dealt) < 2:
        raise CanonicalizationError("strategic state needs at least two dealt players")

    # OH chair ids are physical clockwise seats in the tablemap. Gaps and waiting
    # players are irrelevant; only the clockwise order of players dealt into the
    # current hand defines strategic position.
    ordered = sorted(dealt, key=lambda seat: ((seat - observation.dealer_seat) % 6))
    if ordered[0] != observation.dealer_seat:
        raise CanonicalizationError("failed to anchor relative positions at dealer")
    return tuple(ordered)


def _map_card_suit(card: int, suit_permutation: tuple[int, int, int, int]) -> int:
    decoded = decode_card(card)
    old_suit = SUITS.index(decoded.suit)
    new_suit = suit_permutation[old_suit]
    return encode_card(decoded.rank, SUITS[new_suit])


def _canonicalize_known_cards(
    hero_cards: tuple[int, int], board: tuple[int, ...]
) -> tuple[tuple[int, int], tuple[int, ...]]:
    best: tuple[tuple[int, int], tuple[int, ...]] | None = None
    for permutation in itertools.permutations(range(4)):
        mapped_hole = tuple(sorted(_map_card_suit(c, permutation) for c in hero_cards))
        mapped_board = tuple(_map_card_suit(c, permutation) for c in board)
        if len(mapped_board) >= 3:
            mapped_board = tuple(sorted(mapped_board[:3])) + mapped_board[3:]
        candidate = (mapped_hole, mapped_board)
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return best


def canonicalize_observation(observation: TableObservation) -> CanonicalState:
    """Convert a validated runtime observation into an exact canonical state."""
    observation.validate()
    ordered_seats = _clockwise_dealt_seats(observation)
    seat_to_position = {seat: pos for pos, seat in enumerate(ordered_seats)}
    seat_by_id = {seat.seat: seat for seat in observation.seats}

    hero_cards, board = _canonicalize_known_cards(observation.hero_cards, observation.board)

    canonical_seats = tuple(
        CanonicalSeat(
            position=seat_to_position[seat_id],
            folded=seat_by_id[seat_id].folded,
            all_in=seat_by_id[seat_id].all_in,
            stack=seat_by_id[seat_id].stack,
            committed_street=seat_by_id[seat_id].committed_street,
            committed_total=seat_by_id[seat_id].committed_total,
        )
        for seat_id in ordered_seats
    )

    canonical_actions: list[CanonicalAction] = []
    for action in observation.actions:
        # Events by players not dealt in this hand are transport noise and must
        # never silently enter strategic history.
        if action.actor_seat not in seat_to_position:
            raise CanonicalizationError(
                f"action actor seat {action.actor_seat} is not dealt in the hand"
            )
        canonical_actions.append(
            CanonicalAction(
                seq=action.seq,
                street=action.street,
                actor_position=seat_to_position[action.actor_seat],
                action=action.action,
                amount_to=action.amount_to,
            )
        )

    return CanonicalState(
        schema_version=observation.schema_version,
        street=observation.street,
        num_players=len(ordered_seats),
        hero_position=seat_to_position[observation.hero_seat],
        hero_cards=hero_cards,
        board=board,
        seats=canonical_seats,
        actions=tuple(canonical_actions),
        ante=observation.ante,
        pot=observation.pot,
        to_call=observation.to_call,
        min_raise_to=observation.min_raise_to,
        max_raise_to=observation.max_raise_to,
    )
