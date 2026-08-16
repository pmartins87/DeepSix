"""Conservative bridge from OH6Plus raw snapshots toward strategic state.

This module intentionally stops *before* action inference. A single scraped
frame is evidence, not a poker action log. We therefore provide only:

* explicit raw-chair -> strategic-seat mapping supplied by table configuration;
* exact decimal-money -> integer-unit conversion under an explicit unit;
* Short Deck card conversion at the boundary;
* raw Hero visible-turn evidence (F/C/K/R/A bitmask + sitting-in state);
* stable projected snapshots; and
* conservative transition classification.

No fold/call/raise, hand reset, total commitment or legal-raise history is
invented from ambiguous deltas. Visible action-button bits can prove what the
OpenHoldem scraper considered available at a frame; they do not prove what
poker action occurred between two frames.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

from .cards import ShortDeckCardError, legacy_rank_suit_to_core
from .raw_snapshot import RawCard, RawTableSnapshot
from .state import Street


class ReconstructionError(ValueError):
    pass


@dataclass(frozen=True)
class ChairLayout:
    """Explicit tablemap-owned mapping: tuple index is strategic seat 0..5."""

    raw_chairs_by_seat: tuple[int, ...]

    def validate(self) -> None:
        if len(self.raw_chairs_by_seat) < 2 or len(self.raw_chairs_by_seat) > 6:
            raise ReconstructionError("chair layout requires 2..6 strategic seats")
        if len(set(self.raw_chairs_by_seat)) != len(self.raw_chairs_by_seat):
            raise ReconstructionError("chair layout contains duplicate raw chairs")
        for raw_chair in self.raw_chairs_by_seat:
            if isinstance(raw_chair, bool) or not isinstance(raw_chair, int):
                raise ReconstructionError("raw chair id must be an integer")
            if raw_chair < 0 or raw_chair >= 10:
                raise ReconstructionError("raw chair id must be in OH range 0..9")

    def strategic_seat(self, raw_chair: int) -> int | None:
        self.validate()
        try:
            return self.raw_chairs_by_seat.index(raw_chair)
        except ValueError:
            return None

    def raw_chair(self, strategic_seat: int) -> int:
        self.validate()
        if strategic_seat < 0 or strategic_seat >= len(self.raw_chairs_by_seat):
            raise ReconstructionError("strategic seat outside configured layout")
        return self.raw_chairs_by_seat[strategic_seat]


@dataclass(frozen=True)
class MoneyScale:
    """Exact table monetary unit, represented as a decimal string."""

    unit: str

    def decimal_unit(self) -> Decimal:
        if not isinstance(self.unit, str) or not self.unit:
            raise ReconstructionError("money unit must be a non-empty decimal string")
        try:
            unit = Decimal(self.unit)
        except InvalidOperation as exc:
            raise ReconstructionError("money unit is not a decimal") from exc
        if not unit.is_finite() or unit <= 0:
            raise ReconstructionError("money unit must be finite and positive")
        return unit

    def to_units(self, text: str) -> int:
        unit = self.decimal_unit()
        if not isinstance(text, str) or not text:
            raise ReconstructionError("raw money must be a non-empty decimal string")
        try:
            value = Decimal(text)
        except InvalidOperation as exc:
            raise ReconstructionError("raw money is not a decimal") from exc
        if not value.is_finite() or value < 0:
            raise ReconstructionError("raw money must be finite and non-negative")
        quotient = value / unit
        integral = quotient.to_integral_value()
        if quotient != integral:
            raise ReconstructionError(
                f"raw money {text} is not an exact multiple of configured unit {self.unit}"
            )
        return int(integral)


@dataclass(frozen=True)
class ProjectedSeat:
    seat: int
    raw_chair: int
    seated: bool
    active: bool
    all_in: bool
    dealer: bool
    has_any_cards: bool
    has_known_cards: bool
    balance: int
    current_bet: int
    stack_including_current_bet: int
    hole_cards: tuple[int | None, int | None]


@dataclass(frozen=True)
class ProjectedSnapshot:
    source_audit_fingerprint: str
    street: Street
    dealer_seat: int
    hero_seat: int | None
    hero_myturnbits: int
    hero_sitting_in: bool
    board: tuple[int, ...]
    seats: tuple[ProjectedSeat, ...]
    pots: tuple[int, ...]

    def semantic_key(self) -> tuple:
        """Transport-independent raw evidence used for stability/transition gates."""
        return (
            self.street,
            self.dealer_seat,
            self.hero_seat,
            self.hero_myturnbits,
            self.hero_sitting_in,
            self.board,
            self.seats,
            self.pots,
        )


class RawTransitionKind(str, Enum):
    UNCHANGED = "unchanged"
    SAME_STREET_DELTA = "same_street_delta"
    FORWARD_STREET = "forward_street"
    HAND_BOUNDARY_CANDIDATE = "hand_boundary_candidate"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class RawTransition:
    kind: RawTransitionKind
    reason: str


@dataclass
class StableSnapshotGate:
    """Emit only after N consecutive semantically identical projected frames."""

    required_identical: int = 2
    _last_key: tuple | None = None
    _count: int = 0
    _last_emitted_key: tuple | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.required_identical, bool)
            or not isinstance(self.required_identical, int)
            or self.required_identical < 1
        ):
            raise ReconstructionError("required_identical must be a positive integer")

    def push(self, snapshot: ProjectedSnapshot) -> ProjectedSnapshot | None:
        key = snapshot.semantic_key()
        if key == self._last_key:
            self._count += 1
        else:
            self._last_key = key
            self._count = 1
        if self._count >= self.required_identical and key != self._last_emitted_key:
            self._last_emitted_key = key
            return snapshot
        return None


def _street_from_board_count(count: int) -> Street:
    try:
        return {
            0: Street.PREFLOP,
            3: Street.FLOP,
            4: Street.TURN,
            5: Street.RIVER,
        }[count]
    except KeyError as exc:
        raise ReconstructionError(f"unsupported raw board count: {count}") from exc


def _known_core_card(card: RawCard) -> int | None:
    if not card.known:
        return None
    try:
        return legacy_rank_suit_to_core(card.openholdem_rank, card.suit)
    except ShortDeckCardError as exc:
        raise ReconstructionError(str(exc)) from exc


def project_raw_snapshot(
    snapshot: RawTableSnapshot,
    *,
    layout: ChairLayout,
    money_scale: MoneyScale,
) -> ProjectedSnapshot:
    """Project one validated OH snapshot without inferring poker actions."""
    snapshot.validate()
    layout.validate()
    money_scale.decimal_unit()

    dealer_seat = layout.strategic_seat(snapshot.dealer_chair)
    if dealer_seat is None:
        raise ReconstructionError("raw dealer chair is outside configured 6+ layout")
    if snapshot.hero_chair == -1:
        hero_seat = None
    else:
        hero_seat = layout.strategic_seat(snapshot.hero_chair)
        if hero_seat is None:
            raise ReconstructionError("raw hero chair is outside configured 6+ layout")

    street = _street_from_board_count(snapshot.community_card_count)
    expected_board_cards = snapshot.community_card_count
    board: list[int] = []
    for index, raw_card in enumerate(snapshot.board):
        core = _known_core_card(raw_card)
        if index < expected_board_cards:
            if core is None:
                raise ReconstructionError(
                    "raw board count says card is revealed but card value is not known"
                )
            board.append(core)
        elif core is not None or raw_card.any_card:
            raise ReconstructionError("raw board exposes a card beyond current street")

    seats: list[ProjectedSeat] = []
    for seat, raw_chair in enumerate(layout.raw_chairs_by_seat):
        raw = snapshot.seats[raw_chair]
        cards = tuple(_known_core_card(card) for card in raw.hole_cards)
        seats.append(
            ProjectedSeat(
                seat=seat,
                raw_chair=raw_chair,
                seated=raw.seated,
                active=raw.active,
                all_in=raw.all_in,
                dealer=raw.dealer,
                has_any_cards=raw.has_any_cards,
                has_known_cards=raw.has_known_cards,
                balance=money_scale.to_units(raw.balance),
                current_bet=money_scale.to_units(raw.current_bet),
                stack_including_current_bet=money_scale.to_units(
                    raw.stack_including_current_bet
                ),
                hole_cards=cards,
            )
        )

    if not seats[dealer_seat].dealer:
        raise ReconstructionError(
            "dealer engine and mapped raw seat dealer flag disagree"
        )

    return ProjectedSnapshot(
        source_audit_fingerprint=snapshot.audit_fingerprint(),
        street=street,
        dealer_seat=dealer_seat,
        hero_seat=hero_seat,
        hero_myturnbits=snapshot.hero_myturnbits,
        hero_sitting_in=snapshot.hero_sitting_in,
        board=tuple(board),
        seats=tuple(seats),
        pots=tuple(money_scale.to_units(value) for value in snapshot.pots),
    )


def classify_raw_transition(
    previous: ProjectedSnapshot,
    current: ProjectedSnapshot,
) -> RawTransition:
    """Classify observable change; deliberately never infer a poker action."""
    if previous.semantic_key() == current.semantic_key():
        return RawTransition(RawTransitionKind.UNCHANGED, "semantic snapshot unchanged")

    previous_index = {
        Street.PREFLOP: 0,
        Street.FLOP: 1,
        Street.TURN: 2,
        Street.RIVER: 3,
    }[previous.street]
    current_index = {
        Street.PREFLOP: 0,
        Street.FLOP: 1,
        Street.TURN: 2,
        Street.RIVER: 3,
    }[current.street]

    if current_index < previous_index:
        if current.street == Street.PREFLOP:
            return RawTransition(
                RawTransitionKind.HAND_BOUNDARY_CANDIDATE,
                "board/street regressed to preflop; requires multi-frame new-hand confirmation",
            )
        return RawTransition(
            RawTransitionKind.AMBIGUOUS,
            "street regressed without reaching preflop",
        )

    if current.dealer_seat != previous.dealer_seat:
        return RawTransition(
            RawTransitionKind.AMBIGUOUS,
            "dealer changed without a confirmed hand boundary",
        )

    if current_index == previous_index:
        if current.board != previous.board:
            return RawTransition(
                RawTransitionKind.AMBIGUOUS,
                "board changed within the same street",
            )
        return RawTransition(
            RawTransitionKind.SAME_STREET_DELTA,
            "non-board raw evidence changed within the same street",
        )

    if current_index == previous_index + 1:
        if tuple(current.board[: len(previous.board)]) != previous.board:
            return RawTransition(
                RawTransitionKind.AMBIGUOUS,
                "forward street does not preserve prior board prefix",
            )
        expected_new_cards = 3 if current.street == Street.FLOP else 1
        if len(current.board) - len(previous.board) != expected_new_cards:
            return RawTransition(
                RawTransitionKind.AMBIGUOUS,
                "forward street revealed unexpected number of board cards",
            )
        return RawTransition(
            RawTransitionKind.FORWARD_STREET,
            "board advanced exactly one Holdem street",
        )

    return RawTransition(
        RawTransitionKind.AMBIGUOUS,
        "one or more streets were skipped between stable snapshots",
    )
