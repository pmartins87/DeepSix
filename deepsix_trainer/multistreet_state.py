"""Exact multi-street strategic state boundary for DeepSix F5.

This module is intentionally solver-facing and consumes the authoritative
``SimulatedHand`` rather than a lossy policy observation.  Its job is to create
a stable exact public node plus the acting player's private infoset while
removing only mathematically exact symmetries.

The public node is canonicalized *before* private cards.  Global suit
permutations are first used to find the canonical public board; only the
residual suit permutations that preserve that canonical public board may then
canonicalize the actor's hole cards.  This prevents private cards from changing
the identity of a public node.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import itertools
import json
from typing import Iterable, Sequence

from deepsix_core.betting import legal_actions
from deepsix_core.cards import SUITS, decode_card, encode_card
from deepsix_core.hand import HandPhase
from deepsix_core.state import ActionKind, Street
from deepsix_simulator.environment import SIMULATOR_ENV_VERSION, SimulatedHand
from deepsix_core.ggpoker_economy import GGPOKER_SHORTDECK_ECONOMY_VERSION


MULTISTREET_STATE_SCHEMA_VERSION = 1


class MultiStreetStateError(ValueError):
    """Raised when an exact F5 strategic state cannot be constructed."""


SuitPermutation = tuple[int, int, int, int]


@dataclass(frozen=True)
class PublicSeatState:
    position: int
    stack: int
    committed_street: int
    committed_total: int
    folded: bool
    all_in: bool


@dataclass(frozen=True)
class PublicActionState:
    seq: int
    street: Street
    actor_position: int
    action: ActionKind
    amount_to: int | None


@dataclass(frozen=True)
class PublicLegalState:
    can_fold: bool
    can_check: bool
    can_call: bool
    call_amount: int
    can_raise: bool
    min_raise_to: int
    max_raise_to: int
    full_raise_to: int
    raise_right_open: bool


@dataclass(frozen=True)
class PublicDecisionState:
    schema_version: int
    env_version: str
    rules_version: str
    economy_version: str
    stake_cents: int
    bbj_enabled: bool
    street: Street
    num_players: int
    dealer_position: int
    actor_position: int
    board: tuple[int, ...]
    seats: tuple[PublicSeatState, ...]
    actions: tuple[PublicActionState, ...]
    ante: int
    pot: int
    current_bet: int
    last_full_raise_increment: int
    legal: PublicLegalState

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "env_version": self.env_version,
            "rules_version": self.rules_version,
            "economy_version": self.economy_version,
            "stake_cents": self.stake_cents,
            "bbj_enabled": self.bbj_enabled,
            "street": self.street.value,
            "num_players": self.num_players,
            "dealer_position": self.dealer_position,
            "actor_position": self.actor_position,
            "board": list(self.board),
            "seats": [
                {
                    "position": seat.position,
                    "stack": seat.stack,
                    "committed_street": seat.committed_street,
                    "committed_total": seat.committed_total,
                    "folded": seat.folded,
                    "all_in": seat.all_in,
                }
                for seat in self.seats
            ],
            "actions": [
                {
                    "seq": action.seq,
                    "street": action.street.value,
                    "actor_position": action.actor_position,
                    "action": action.action.value,
                    "amount_to": action.amount_to,
                }
                for action in self.actions
            ],
            "ante": self.ante,
            "pot": self.pot,
            "current_bet": self.current_bet,
            "last_full_raise_increment": self.last_full_raise_increment,
            "legal": {
                "can_fold": self.legal.can_fold,
                "can_check": self.legal.can_check,
                "can_call": self.legal.can_call,
                "call_amount": self.legal.call_amount,
                "can_raise": self.legal.can_raise,
                "min_raise_to": self.legal.min_raise_to,
                "max_raise_to": self.legal.max_raise_to,
                "full_raise_to": self.legal.full_raise_to,
                "raise_right_open": self.legal.raise_right_open,
            },
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PrivateDecisionState:
    public: PublicDecisionState
    hero_position: int
    hero_cards: tuple[int, int]

    def to_dict(self) -> dict:
        return {
            "public": self.public.to_dict(),
            "hero_position": self.hero_position,
            "hero_cards": list(self.hero_cards),
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _map_card_suit(card: int, permutation: SuitPermutation) -> int:
    decoded = decode_card(card)
    old_suit = SUITS.index(decoded.suit)
    new_suit = permutation[old_suit]
    return encode_card(decoded.rank, SUITS[new_suit])


def _normalize_board_order(board: Sequence[int]) -> tuple[int, ...]:
    values = tuple(board)
    if len(values) >= 3:
        return tuple(sorted(values[:3])) + values[3:]
    return values


def _mapped_board(board: Sequence[int], permutation: SuitPermutation) -> tuple[int, ...]:
    return _normalize_board_order(tuple(_map_card_suit(card, permutation) for card in board))


def canonical_public_board(
    board: Sequence[int],
) -> tuple[tuple[int, ...], tuple[SuitPermutation, ...]]:
    """Canonicalize public board and retain its residual exact suit symmetries."""
    board = tuple(board)
    if len(board) not in (0, 3, 4, 5):
        raise MultiStreetStateError("board must contain 0, 3, 4 or 5 cards")
    if len(set(board)) != len(board):
        raise MultiStreetStateError("board contains duplicate cards")
    try:
        for card in board:
            decode_card(card)
    except (TypeError, ValueError) as exc:
        raise MultiStreetStateError("board contains invalid Short Deck card") from exc

    candidates: list[tuple[tuple[int, ...], SuitPermutation]] = []
    for raw in itertools.permutations(range(4)):
        permutation: SuitPermutation = tuple(raw)  # type: ignore[assignment]
        candidates.append((_mapped_board(board, permutation), permutation))
    best = min(candidate for candidate, _ in candidates)
    residual = tuple(
        permutation for candidate, permutation in candidates if candidate == best
    )
    if not residual:
        raise MultiStreetStateError("failed to retain public suit stabilizer")
    return best, residual


def canonical_private_cards_under_public(
    cards: Sequence[int],
    residual_permutations: Iterable[SuitPermutation],
) -> tuple[int, int]:
    """Canonicalize one private hand without changing canonical public identity."""
    cards = tuple(cards)
    if len(cards) != 2 or cards[0] == cards[1]:
        raise MultiStreetStateError("private hand must contain two distinct cards")
    try:
        decode_card(cards[0])
        decode_card(cards[1])
    except (TypeError, ValueError) as exc:
        raise MultiStreetStateError("private hand contains invalid Short Deck card") from exc

    residual = tuple(residual_permutations)
    if not residual:
        raise MultiStreetStateError("residual suit-permutation set is empty")
    candidates = [
        tuple(sorted(_map_card_suit(card, permutation) for card in cards))
        for permutation in residual
    ]
    return min(candidates)


def _relative_seats(hand: SimulatedHand) -> tuple[int, ...]:
    dealer = hand.state.dealer_seat
    seats = {player.seat for player in hand.state.players}
    if dealer not in seats:
        raise MultiStreetStateError("Dealer must be dealt")
    ordered = tuple(sorted(seats, key=lambda seat: ((seat - dealer) % 6)))
    if len(ordered) < 2 or len(ordered) > 6 or ordered[0] != dealer:
        raise MultiStreetStateError("invalid dealt-seat geometry")
    return ordered


def _validate_street_board(street: Street, board: Sequence[int]) -> None:
    expected = {
        Street.PREFLOP: 0,
        Street.FLOP: 3,
        Street.TURN: 4,
        Street.RIVER: 5,
    }[street]
    if len(board) != expected:
        raise MultiStreetStateError(
            f"{street.value} requires exactly {expected} public cards"
        )


def decision_state_from_hand(hand: SimulatedHand) -> PrivateDecisionState:
    """Build the exact F5 public node + acting player's private infoset."""
    if not isinstance(hand, SimulatedHand):
        raise MultiStreetStateError("decision state requires a SimulatedHand")
    hand.state.validate()
    if hand.state.phase != HandPhase.BETTING or hand.terminal:
        raise MultiStreetStateError("decision state requires an open betting decision")

    actor = hand.actor_seat
    if actor is None or actor not in hand.hole_cards:
        raise MultiStreetStateError("open decision is missing a valid acting seat")
    _validate_street_board(hand.state.street, hand.state.board)

    ordered = _relative_seats(hand)
    seat_to_position = {seat: position for position, seat in enumerate(ordered)}
    if actor not in seat_to_position:
        raise MultiStreetStateError("acting seat is not dealt")

    canonical_board, residual = canonical_public_board(hand.state.board)
    hero_cards = canonical_private_cards_under_public(hand.hole_cards[actor], residual)
    if set(hand.hole_cards[actor]) & set(hand.state.board):
        raise MultiStreetStateError("actor private cards collide with public board")

    round_by_seat = {
        player.seat: player for player in hand.state.betting_round.players
    }
    hand_by_seat = {player.seat: player for player in hand.state.players}
    if set(round_by_seat) != set(ordered) or set(hand_by_seat) != set(ordered):
        raise MultiStreetStateError("hand/round seat support drift")

    seats = tuple(
        PublicSeatState(
            position=seat_to_position[seat],
            stack=hand_by_seat[seat].stack,
            committed_street=round_by_seat[seat].committed_street,
            committed_total=hand_by_seat[seat].committed_total,
            folded=hand_by_seat[seat].folded,
            all_in=hand_by_seat[seat].all_in,
        )
        for seat in ordered
    )
    for seat in seats:
        if seat.committed_street < 0 or seat.committed_total < seat.committed_street:
            raise MultiStreetStateError("invalid commitment geometry")

    actions: list[PublicActionState] = []
    previous_street_index = -1
    street_index = {
        Street.PREFLOP: 0,
        Street.FLOP: 1,
        Street.TURN: 2,
        Street.RIVER: 3,
    }
    for expected_seq, action in enumerate(hand.state.actions):
        if action.seq != expected_seq:
            raise MultiStreetStateError("action history must be contiguous from zero")
        if action.actor_seat not in seat_to_position:
            raise MultiStreetStateError("action actor is not dealt")
        current_index = street_index[action.street]
        if current_index < previous_street_index or current_index > street_index[hand.state.street]:
            raise MultiStreetStateError("action street history is inconsistent")
        previous_street_index = current_index
        actions.append(
            PublicActionState(
                seq=action.seq,
                street=action.street,
                actor_position=seat_to_position[action.actor_seat],
                action=action.action,
                amount_to=action.amount_to,
            )
        )

    round_state = hand.state.betting_round
    legal = legal_actions(round_state)
    if round_state.next_actor != actor:
        raise MultiStreetStateError("betting-round actor drift")
    if max(seat.committed_street for seat in seats) != round_state.current_bet:
        raise MultiStreetStateError("current bet differs from exact street commitments")
    if sum(seat.committed_total for seat in seats) != hand.state.pot():
        raise MultiStreetStateError("public pot differs from exact total commitments")

    public = PublicDecisionState(
        schema_version=MULTISTREET_STATE_SCHEMA_VERSION,
        env_version=SIMULATOR_ENV_VERSION,
        rules_version=hand.rules.version,
        economy_version=GGPOKER_SHORTDECK_ECONOMY_VERSION,
        stake_cents=hand.stake_cents,
        bbj_enabled=hand.bbj_enabled,
        street=hand.state.street,
        num_players=len(ordered),
        dealer_position=0,
        actor_position=seat_to_position[actor],
        board=canonical_board,
        seats=seats,
        actions=tuple(actions),
        ante=hand.state.config.ante,
        pot=hand.state.pot(),
        current_bet=round_state.current_bet,
        last_full_raise_increment=round_state.last_full_raise_increment,
        legal=PublicLegalState(
            can_fold=legal.can_fold,
            can_check=legal.can_check,
            can_call=legal.can_call,
            call_amount=legal.call_amount,
            can_raise=legal.can_raise,
            min_raise_to=legal.min_raise_to,
            max_raise_to=legal.max_raise_to,
            full_raise_to=legal.full_raise_to,
            raise_right_open=legal.raise_right_open,
        ),
    )
    return PrivateDecisionState(
        public=public,
        hero_position=seat_to_position[actor],
        hero_cards=hero_cards,
    )
