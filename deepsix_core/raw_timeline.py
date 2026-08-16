"""Conservative temporal inference over stable OH6Plus projected snapshots.

The raw scraper boundary intentionally treats each frame as evidence rather than
an action log.  This module adds the first temporal layer above that boundary:
it may label a betting action only when the *visible accounting delta itself*
has exactly one legal poker interpretation under deliberately strict guards.

V1 is intentionally narrow:

* one and only one seat may change money/commitment for an inferred action;
* that seat's balance loss must exactly equal its current-bet increase;
* stack-including-current-bet must therefore remain unchanged;
* pot slots and all other seats' structural/money evidence must remain stable;
* a call is inferred only when the new commitment exactly matches the prior
  table price, or when an exact short all-in ends below that price;
* any commitment above the prior table price is represented as RAISE_TO (the
  Core uses RAISE_TO for both an opening bet from zero and a raise);
* checks are never inferred from disappearing buttons or unchanged chips;
* folds are never inferred from an ``active`` flag transition alone;
* ambiguous evidence stays ambiguous.

This is a local evidence classifier, not yet a complete hand-history
reconstructor.  In particular it does not claim that a baseline snapshot is the
start of a hand, and it does not confirm a new hand from a board reset alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .raw_reconstructor import (
    ProjectedSeat,
    ProjectedSnapshot,
    RawTransition,
    RawTransitionKind,
    classify_raw_transition,
)
from .state import ActionKind, Street


class TimelineInferenceError(ValueError):
    pass


class TimelineEventKind(str, Enum):
    BASELINE = "baseline"
    ACTION = "action"
    STREET_ADVANCE = "street_advance"
    HAND_BOUNDARY_CANDIDATE = "hand_boundary_candidate"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class InferredAction:
    seq: int
    street: Street
    actor_seat: int
    action: ActionKind
    amount_to: int | None
    paid: int
    prior_table_bet: int
    prior_actor_bet: int
    resulting_actor_bet: int
    all_in: bool
    reason: str

    def validate(self) -> None:
        if self.seq < 0:
            raise TimelineInferenceError("inferred action seq must be non-negative")
        if self.actor_seat < 0 or self.actor_seat >= 6:
            raise TimelineInferenceError("inferred actor seat must be in 0..5")
        if self.paid <= 0:
            raise TimelineInferenceError("inferred paid amount must be positive")
        if self.prior_table_bet < 0 or self.prior_actor_bet < 0:
            raise TimelineInferenceError("prior commitments must be non-negative")
        if self.resulting_actor_bet <= self.prior_actor_bet:
            raise TimelineInferenceError("inferred action must increase actor commitment")
        if self.action == ActionKind.RAISE_TO:
            if self.amount_to != self.resulting_actor_bet:
                raise TimelineInferenceError("raise_to amount must equal resulting bet")
        elif self.action == ActionKind.CALL:
            if self.amount_to is not None:
                raise TimelineInferenceError("call cannot carry amount_to")
        else:
            raise TimelineInferenceError(
                "raw timeline v1 only infers CALL or RAISE_TO"
            )


@dataclass(frozen=True)
class TimelineEvent:
    kind: TimelineEventKind
    transition: RawTransition | None
    snapshot: ProjectedSnapshot
    action: InferredAction | None = None
    reason: str = ""

    def validate(self) -> None:
        if self.kind == TimelineEventKind.ACTION:
            if self.action is None:
                raise TimelineInferenceError("ACTION event requires inferred action")
            self.action.validate()
        elif self.action is not None:
            raise TimelineInferenceError("non-ACTION event cannot carry inferred action")


@dataclass
class RawEvidenceTimeline:
    """Append-only timeline over already-stable projected snapshots.

    The first snapshot is a baseline only.  Subsequent local actions can be
    inferred, but ``complete_from_hand_start`` remains false until a future
    hand-boundary confirmer can prove that the observed baseline is the actual
    start of a hand.
    """

    _last: ProjectedSnapshot | None = None
    _next_action_seq: int = 0
    _events: list[TimelineEvent] = field(default_factory=list)
    complete_from_hand_start: bool = False

    @property
    def events(self) -> tuple[TimelineEvent, ...]:
        return tuple(self._events)

    @property
    def inferred_actions(self) -> tuple[InferredAction, ...]:
        return tuple(
            event.action
            for event in self._events
            if event.action is not None
        )

    def push(self, snapshot: ProjectedSnapshot) -> TimelineEvent | None:
        if self._last is None:
            event = TimelineEvent(
                kind=TimelineEventKind.BASELINE,
                transition=None,
                snapshot=snapshot,
                reason="first stable snapshot is evidence baseline, not proven hand start",
            )
            event.validate()
            self._events.append(event)
            self._last = snapshot
            return event

        transition = classify_raw_transition(self._last, snapshot)
        if transition.kind == RawTransitionKind.UNCHANGED:
            self._last = snapshot
            return None

        if transition.kind == RawTransitionKind.SAME_STREET_DELTA:
            action, reason = infer_unique_money_action(
                self._last,
                snapshot,
                seq=self._next_action_seq,
            )
            if action is not None:
                event = TimelineEvent(
                    kind=TimelineEventKind.ACTION,
                    transition=transition,
                    snapshot=snapshot,
                    action=action,
                    reason=reason,
                )
                self._next_action_seq += 1
            else:
                event = TimelineEvent(
                    kind=TimelineEventKind.AMBIGUOUS,
                    transition=transition,
                    snapshot=snapshot,
                    reason=reason,
                )
                self.complete_from_hand_start = False
        elif transition.kind == RawTransitionKind.FORWARD_STREET:
            event = TimelineEvent(
                kind=TimelineEventKind.STREET_ADVANCE,
                transition=transition,
                snapshot=snapshot,
                reason=transition.reason,
            )
        elif transition.kind == RawTransitionKind.HAND_BOUNDARY_CANDIDATE:
            event = TimelineEvent(
                kind=TimelineEventKind.HAND_BOUNDARY_CANDIDATE,
                transition=transition,
                snapshot=snapshot,
                reason=(
                    "preflop regression is only a candidate; v1 does not reset action "
                    "sequence or claim a new hand without stronger evidence"
                ),
            )
            self.complete_from_hand_start = False
        else:
            event = TimelineEvent(
                kind=TimelineEventKind.AMBIGUOUS,
                transition=transition,
                snapshot=snapshot,
                reason=transition.reason,
            )
            self.complete_from_hand_start = False

        event.validate()
        self._events.append(event)
        self._last = snapshot
        return event


def _seat_structure_key(seat: ProjectedSeat) -> tuple:
    """Fields that must not silently change during a unique money action."""
    return (
        seat.seat,
        seat.raw_chair,
        seat.seated,
        seat.dealer,
        seat.has_known_cards,
        seat.hole_cards,
    )


def _seat_nonmoney_action_key(seat: ProjectedSeat) -> tuple:
    """Action-compatible non-money fields.

    ``all_in`` may legitimately become true as the result of a call/raise.
    ``active`` is required to stay true because v1 refuses to combine a money
    action with a simultaneous fold/sit-out interpretation. ``has_any_cards``
    must remain stable for the same reason.
    """
    return (seat.active, seat.has_any_cards)


def infer_unique_money_action(
    previous: ProjectedSnapshot,
    current: ProjectedSnapshot,
    *,
    seq: int = 0,
) -> tuple[InferredAction | None, str]:
    """Infer CALL/RAISE_TO only from an exact, single-seat accounting delta."""
    if seq < 0:
        raise TimelineInferenceError("action seq must be non-negative")

    transition = classify_raw_transition(previous, current)
    if transition.kind != RawTransitionKind.SAME_STREET_DELTA:
        return None, f"transition is {transition.kind.value}, not a same-street delta"

    if previous.hero_sitting_in != current.hero_sitting_in:
        return None, "Hero sitting-in state changed during the delta"
    if previous.pots != current.pots:
        return None, "pot slots changed; timing/accounting is not uniquely attributable"
    if len(previous.seats) != len(current.seats):
        return None, "seat vector length changed"

    changed_money: list[int] = []
    for before, after in zip(previous.seats, current.seats):
        if _seat_structure_key(before) != _seat_structure_key(after):
            return None, f"seat {before.seat} structural evidence changed"
        if _seat_nonmoney_action_key(before) != _seat_nonmoney_action_key(after):
            return None, f"seat {before.seat} active/card-presence evidence changed"
        if before.all_in and not after.all_in:
            return None, f"seat {before.seat} left all-in state within a street"

        money_before = (
            before.balance,
            before.current_bet,
            before.stack_including_current_bet,
        )
        money_after = (
            after.balance,
            after.current_bet,
            after.stack_including_current_bet,
        )
        if money_before != money_after:
            changed_money.append(before.seat)
        elif before.all_in != after.all_in:
            # An all-in flag change without the exact money movement that caused
            # it is not enough evidence to infer an action.
            return None, f"seat {before.seat} all-in flag changed without money delta"

    if len(changed_money) != 1:
        return None, f"expected exactly one money-changing seat, observed {len(changed_money)}"

    actor_seat = changed_money[0]
    before = next(seat for seat in previous.seats if seat.seat == actor_seat)
    after = next(seat for seat in current.seats if seat.seat == actor_seat)

    if not before.seated or not before.active or not after.seated or not after.active:
        return None, "money-changing seat is not continuously seated and active"

    bet_delta = after.current_bet - before.current_bet
    balance_delta = after.balance - before.balance
    stack_total_delta = (
        after.stack_including_current_bet - before.stack_including_current_bet
    )
    if bet_delta <= 0:
        return None, "actor current bet did not strictly increase"
    if balance_delta != -bet_delta:
        return None, "balance loss does not exactly equal current-bet increase"
    if stack_total_delta != 0:
        return None, "stack including current bet changed during candidate action"

    prior_table_bet = max(seat.current_bet for seat in previous.seats)
    new_bet = after.current_bet

    if new_bet > prior_table_bet:
        action_kind = ActionKind.RAISE_TO
        amount_to: int | None = new_bet
        reason = (
            f"seat {actor_seat} alone moved {bet_delta} chips and its commitment "
            f"rose above prior table bet {prior_table_bet} to {new_bet}"
        )
    elif before.current_bet < prior_table_bet and new_bet == prior_table_bet:
        action_kind = ActionKind.CALL
        amount_to = None
        reason = (
            f"seat {actor_seat} alone paid exactly to prior table bet "
            f"{prior_table_bet}"
        )
    elif (
        before.current_bet < prior_table_bet
        and new_bet < prior_table_bet
        and after.all_in
        and after.balance == 0
    ):
        action_kind = ActionKind.CALL
        amount_to = None
        reason = (
            f"seat {actor_seat} alone paid its exact remaining stack and is all-in "
            f"below prior table bet {prior_table_bet}"
        )
    else:
        return None, (
            "single-seat money delta does not uniquely match call or raise_to "
            f"(old={before.current_bet}, new={new_bet}, table={prior_table_bet})"
        )

    action = InferredAction(
        seq=seq,
        street=previous.street,
        actor_seat=actor_seat,
        action=action_kind,
        amount_to=amount_to,
        paid=bet_delta,
        prior_table_bet=prior_table_bet,
        prior_actor_bet=before.current_bet,
        resulting_actor_bet=new_bet,
        all_in=after.all_in,
        reason=reason,
    )
    action.validate()
    return action, reason
