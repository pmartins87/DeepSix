"""Python mirror of the read-only OH6Plus RawTableSnapshot audit contract.

This layer preserves raw scraper evidence. Money is intentionally represented as
canonical decimal strings, not as strategic integer units and not as Python
binary floats. Conversion to the exact configured table unit belongs to the
state reconstructor after stake/client precision is frozen.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation


RAW_SNAPSHOT_SCHEMA_VERSION = 1
RAW_MAX_CHAIRS = 10
RAW_HOLE_CARDS = 2
RAW_BOARD_CARDS = 5
RAW_POT_SLOTS = 10


class RawSnapshotError(ValueError):
    pass


def _validate_money(text: str, name: str) -> None:
    if not isinstance(text, str) or not text:
        raise RawSnapshotError(f"{name} must be a non-empty decimal string")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise RawSnapshotError(f"{name} is not a decimal string") from exc
    if not value.is_finite() or value < 0:
        raise RawSnapshotError(f"{name} must be finite and non-negative")


@dataclass(frozen=True)
class RawCard:
    any_card: bool
    card_back: bool
    known: bool
    openholdem_rank: int
    suit: int

    def validate(self) -> None:
        if self.known:
            if self.openholdem_rank < 6 or self.openholdem_rank > 14:
                raise RawSnapshotError("known raw card rank must be 6..14")
            if self.suit < 0 or self.suit > 3:
                raise RawSnapshotError("known raw card suit must be 0..3")
        else:
            if self.openholdem_rank != -1 or self.suit != -1:
                raise RawSnapshotError(
                    "unknown raw card must use rank/suit sentinel -1/-1"
                )


@dataclass(frozen=True)
class RawSeat:
    active: bool
    all_in: bool
    balance: str
    chair: int
    current_bet: str
    dealer: bool
    has_any_cards: bool
    has_known_cards: bool
    hole_cards: tuple[RawCard, RawCard]
    seated: bool
    stack_including_current_bet: str

    def validate(self) -> None:
        if self.chair < 0 or self.chair >= RAW_MAX_CHAIRS:
            raise RawSnapshotError("raw seat chair outside 0..9")
        if len(self.hole_cards) != RAW_HOLE_CARDS:
            raise RawSnapshotError("raw seat must expose exactly two card slots")
        _validate_money(self.balance, "balance")
        _validate_money(self.current_bet, "current_bet")
        _validate_money(
            self.stack_including_current_bet, "stack_including_current_bet"
        )
        for card in self.hole_cards:
            card.validate()


@dataclass(frozen=True)
class RawTableSnapshot:
    board: tuple[RawCard, RawCard, RawCard, RawCard, RawCard]
    community_card_count: int
    dealer_chair: int
    hero_chair: int
    pots: tuple[str, ...]
    schema_version: int
    seats: tuple[RawSeat, ...]

    def validate(self) -> None:
        if self.schema_version != RAW_SNAPSHOT_SCHEMA_VERSION:
            raise RawSnapshotError(
                f"unsupported raw snapshot schema {self.schema_version}"
            )
        if self.dealer_chair < 0 or self.dealer_chair >= RAW_MAX_CHAIRS:
            raise RawSnapshotError("raw dealer chair outside 0..9")
        if self.hero_chair < -1 or self.hero_chair >= RAW_MAX_CHAIRS:
            raise RawSnapshotError("raw hero chair outside -1..9")
        if self.community_card_count not in (0, 3, 4, 5):
            raise RawSnapshotError("raw board count is not a Holdem street boundary")
        if len(self.board) != RAW_BOARD_CARDS:
            raise RawSnapshotError("raw snapshot must expose five board slots")
        if len(self.seats) != RAW_MAX_CHAIRS:
            raise RawSnapshotError("raw snapshot must expose ten physical chairs")
        if len(self.pots) != RAW_POT_SLOTS:
            raise RawSnapshotError("raw snapshot must expose ten pot slots")

        for index, seat in enumerate(self.seats):
            seat.validate()
            if seat.chair != index:
                raise RawSnapshotError("raw seats must be stored by physical chair index")
        for card in self.board:
            card.validate()
        for index, pot in enumerate(self.pots):
            _validate_money(pot, f"pot[{index}]")

        seen: set[tuple[int, int]] = set()
        known_cards = list(self.board)
        for seat in self.seats:
            known_cards.extend(seat.hole_cards)
        for card in known_cards:
            if not card.known:
                continue
            key = (card.openholdem_rank, card.suit)
            if key in seen:
                raise RawSnapshotError("duplicate known raw card")
            seen.add(key)

    def payload(self) -> dict:
        self.validate()
        return asdict(self)

    def canonical_json(self) -> str:
        return json.dumps(
            self.payload(), sort_keys=True, separators=(",", ":")
        )

    def audit_fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def raw_snapshot_from_dict(payload: dict) -> RawTableSnapshot:
    try:
        board = tuple(RawCard(**card) for card in payload["board"])
        seats = tuple(
            RawSeat(
                active=seat["active"],
                all_in=seat["all_in"],
                balance=seat["balance"],
                chair=seat["chair"],
                current_bet=seat["current_bet"],
                dealer=seat["dealer"],
                has_any_cards=seat["has_any_cards"],
                has_known_cards=seat["has_known_cards"],
                hole_cards=tuple(RawCard(**card) for card in seat["hole_cards"]),
                seated=seat["seated"],
                stack_including_current_bet=seat["stack_including_current_bet"],
            )
            for seat in payload["seats"]
        )
        snapshot = RawTableSnapshot(
            board=board,
            community_card_count=payload["community_card_count"],
            dealer_chair=payload["dealer_chair"],
            hero_chair=payload["hero_chair"],
            pots=tuple(payload["pots"]),
            schema_version=payload["schema_version"],
            seats=seats,
        )
    except (KeyError, TypeError) as exc:
        raise RawSnapshotError("malformed raw snapshot payload") from exc
    snapshot.validate()
    return snapshot


def raw_snapshot_from_json(text: str) -> RawTableSnapshot:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RawSnapshotError("invalid raw snapshot JSON") from exc
    if not isinstance(payload, dict):
        raise RawSnapshotError("raw snapshot JSON root must be an object")
    return raw_snapshot_from_dict(payload)
