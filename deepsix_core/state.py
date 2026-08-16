"""Versioned observation contract shared by replay, OH6Plus and DeepSix Core.

This is intentionally an observation schema, not yet the final strategic
canonicalizer. Monetary amounts are integers in the table's smallest exact unit
to avoid float drift at the runtime boundary.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum

from .cards import ShortDeckCardError, decode_card


SCHEMA_VERSION = 1


class ObservationError(ValueError):
    pass


class Street(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class ActionKind(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE_TO = "raise_to"


@dataclass(frozen=True)
class SeatObservation:
    seat: int
    dealt: bool
    folded: bool
    all_in: bool
    stack: int
    committed_street: int
    committed_total: int

    def validate(self) -> None:
        if self.seat < 0 or self.seat >= 6:
            raise ObservationError("seat must be in physical OH6Plus range 0..5")
        for name in ("stack", "committed_street", "committed_total"):
            if getattr(self, name) < 0:
                raise ObservationError(f"{name} must be non-negative")
        if self.committed_street > self.committed_total:
            raise ObservationError("committed_street cannot exceed committed_total")
        if self.folded and self.all_in:
            raise ObservationError("a seat cannot be folded and all-in simultaneously")


@dataclass(frozen=True)
class ActionEvent:
    seq: int
    street: Street
    actor_seat: int
    action: ActionKind
    amount_to: int | None = None

    def validate(self) -> None:
        if self.seq < 0:
            raise ObservationError("action seq must be non-negative")
        if self.actor_seat < 0 or self.actor_seat >= 6:
            raise ObservationError("action actor_seat must be in physical OH6Plus range 0..5")
        if self.action == ActionKind.RAISE_TO:
            if self.amount_to is None or self.amount_to < 0:
                raise ObservationError("raise_to requires non-negative amount_to")
        elif self.amount_to is not None:
            raise ObservationError("only raise_to may carry amount_to")


@dataclass(frozen=True)
class TableObservation:
    schema_version: int
    hand_id: str
    observation_seq: int
    source_timestamp_ms: int
    street: Street
    dealer_seat: int
    hero_seat: int
    hero_cards: tuple[int, int]
    board: tuple[int, ...]
    seats: tuple[SeatObservation, ...]
    actions: tuple[ActionEvent, ...]
    ante: int
    pot: int
    to_call: int
    min_raise_to: int
    max_raise_to: int

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ObservationError(
                f"unsupported schema version {self.schema_version}; expected {SCHEMA_VERSION}"
            )
        if not self.hand_id:
            raise ObservationError("hand_id is required")
        if self.observation_seq < 0 or self.source_timestamp_ms < 0:
            raise ObservationError("observation_seq/timestamp must be non-negative")
        if len(self.seats) < 2 or len(self.seats) > 6:
            raise ObservationError("Short Deck table must have 2..6 observed seats")

        for seat in self.seats:
            seat.validate()
        seat_ids = [seat.seat for seat in self.seats]
        if len(set(seat_ids)) != len(seat_ids):
            raise ObservationError("duplicate seat ids")
        if self.dealer_seat not in seat_ids:
            raise ObservationError("dealer_seat must exist in seats")
        if self.hero_seat not in seat_ids:
            raise ObservationError("hero_seat must exist in seats")

        if len(self.hero_cards) != 2:
            raise ObservationError("hero must have exactly two hole cards")
        expected_board = {
            Street.PREFLOP: 0,
            Street.FLOP: 3,
            Street.TURN: 4,
            Street.RIVER: 5,
        }[self.street]
        if len(self.board) != expected_board:
            raise ObservationError(
                f"{self.street.value} requires {expected_board} board cards"
            )

        known_cards = tuple(self.hero_cards) + tuple(self.board)
        if len(set(known_cards)) != len(known_cards):
            raise ObservationError("duplicate known cards")
        try:
            for card in known_cards:
                decode_card(card)
        except ShortDeckCardError as exc:
            raise ObservationError(str(exc)) from exc

        for name in ("ante", "pot", "to_call", "min_raise_to", "max_raise_to"):
            if getattr(self, name) < 0:
                raise ObservationError(f"{name} must be non-negative")
        if self.min_raise_to > self.max_raise_to:
            raise ObservationError("min_raise_to cannot exceed max_raise_to")

        previous_seq = -1
        for action in self.actions:
            action.validate()
            if action.actor_seat not in seat_ids:
                raise ObservationError("action actor_seat must exist in seats")
            if action.seq <= previous_seq:
                raise ObservationError("action sequence must be strictly increasing")
            previous_seq = action.seq

    def _payload(self, include_transport: bool) -> dict:
        self.validate()
        payload = asdict(self)
        payload["street"] = self.street.value
        payload["actions"] = [
            {
                "seq": action.seq,
                "street": action.street.value,
                "actor_seat": action.actor_seat,
                "action": action.action.value,
                "amount_to": action.amount_to,
            }
            for action in self.actions
        ]
        if not include_transport:
            payload.pop("hand_id")
            payload.pop("observation_seq")
            payload.pop("source_timestamp_ms")
        return payload

    def semantic_fingerprint(self) -> str:
        """Hash only game semantics, excluding transport/staleness metadata."""
        raw = json.dumps(
            self._payload(include_transport=False),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def observation_fingerprint(self) -> str:
        """Hash the complete observation, including hand/seq/timestamp."""
        raw = json.dumps(
            self._payload(include_transport=True),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
