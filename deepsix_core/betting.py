"""Deterministic no-limit betting-round state machine for DeepSix.

This module is deliberately game-structure-first. It does not hard-code the
still-client-dependent KKPoker preflop reopen details. The caller supplies the
initial full-raise increment and a short-all-in reopen policy.

Stacks and commitments are exact integer table units.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .state import ActionEvent, ActionKind, Street


class BettingStateError(ValueError):
    pass


class ShortAllInReopenPolicy(str, Enum):
    """How prior actors regain raise rights after sub-minimum all-in raises."""

    NEVER = "never"
    ANY_INCREASE = "any_increase"
    CUMULATIVE_FULL_RAISE = "cumulative_full_raise"


@dataclass(frozen=True)
class BettingConfig:
    short_all_in_reopen: ShortAllInReopenPolicy = ShortAllInReopenPolicy.NEVER
    allow_short_all_in_raise: bool = True


@dataclass(frozen=True)
class BettingPlayer:
    seat: int
    stack: int
    committed_street: int
    folded: bool = False
    all_in: bool = False

    def validate(self) -> None:
        if self.seat < 0:
            raise BettingStateError("seat must be non-negative")
        if self.stack < 0 or self.committed_street < 0:
            raise BettingStateError("stack/commitment must be non-negative")
        if self.folded and self.all_in:
            raise BettingStateError("player cannot be folded and all-in")
        if self.stack == 0 and not self.folded and not self.all_in:
            raise BettingStateError("zero-stack live player must be marked all-in")
        if self.all_in and self.stack != 0:
            raise BettingStateError("all-in player must have zero stack behind")


@dataclass(frozen=True)
class RoundLegalActions:
    can_fold: bool
    can_check: bool
    can_call: bool
    call_amount: int
    can_raise: bool
    min_raise_to: int
    max_raise_to: int
    full_raise_to: int
    raise_right_open: bool

    def is_raise_to_legal(self, amount_to: int) -> bool:
        return (
            self.can_raise
            and isinstance(amount_to, int)
            and not isinstance(amount_to, bool)
            and self.min_raise_to <= amount_to <= self.max_raise_to
        )


@dataclass(frozen=True)
class BettingRoundState:
    street: Street
    action_order: tuple[int, ...]
    players: tuple[BettingPlayer, ...]
    current_bet: int
    last_full_raise_increment: int
    needs_action: frozenset[int]
    # None means the player has not acted since the last full raise and thus has
    # normal raise rights. Otherwise this stores the current_bet they faced when
    # they last acted in that full-raise epoch.
    acted_at_bet: tuple[tuple[int, int | None], ...]
    next_actor: int | None
    config: BettingConfig
    events: tuple[ActionEvent, ...] = ()
    closed: bool = False
    hand_ended: bool = False

    def player(self, seat: int) -> BettingPlayer:
        for player in self.players:
            if player.seat == seat:
                return player
        raise BettingStateError(f"unknown seat {seat}")

    def acted_at(self, seat: int) -> int | None:
        for known_seat, value in self.acted_at_bet:
            if known_seat == seat:
                return value
        raise BettingStateError(f"unknown seat {seat}")

    def validate(self) -> None:
        if len(self.players) < 2 or len(self.players) > 6:
            raise BettingStateError("betting round requires 2..6 players")
        seats = [player.seat for player in self.players]
        if len(set(seats)) != len(seats):
            raise BettingStateError("duplicate player seat")
        if tuple(seats) != self.action_order:
            raise BettingStateError("players must be stored in action_order order")
        if self.current_bet < 0 or self.last_full_raise_increment <= 0:
            raise BettingStateError("invalid current bet/full-raise increment")
        for player in self.players:
            player.validate()
            if player.committed_street > self.current_bet:
                raise BettingStateError("player commitment exceeds current bet")
        if max(player.committed_street for player in self.players) != self.current_bet:
            raise BettingStateError("current_bet must equal maximum street commitment")

        acted = dict(self.acted_at_bet)
        if set(acted) != set(seats) or len(acted) != len(self.acted_at_bet):
            raise BettingStateError("acted_at_bet must contain every seat exactly once")
        if any(value is not None and value < 0 for value in acted.values()):
            raise BettingStateError("acted-at bet cannot be negative")

        eligible = {
            player.seat
            for player in self.players
            if not player.folded and not player.all_in and player.stack > 0
        }
        if not self.needs_action <= eligible:
            raise BettingStateError("needs_action contains an ineligible player")
        if self.closed:
            if self.next_actor is not None or self.needs_action:
                raise BettingStateError("closed round cannot have pending actor/action")
        else:
            if not self.needs_action:
                raise BettingStateError("open round must have pending action")
            if self.next_actor not in self.needs_action:
                raise BettingStateError("next_actor must need action")
        nonfolded = [player for player in self.players if not player.folded]
        if self.hand_ended != (len(nonfolded) <= 1):
            raise BettingStateError("hand_ended inconsistent with folded players")

        previous_seq = -1
        for event in self.events:
            event.validate()
            if event.street != self.street:
                raise BettingStateError("event street differs from betting round")
            if event.actor_seat not in seats:
                raise BettingStateError("event actor is not in betting round")
            if event.seq <= previous_seq:
                raise BettingStateError("event sequence must be strictly increasing")
            previous_seq = event.seq


def _replace_player(
    players: tuple[BettingPlayer, ...], updated: BettingPlayer
) -> tuple[BettingPlayer, ...]:
    return tuple(updated if player.seat == updated.seat else player for player in players)


def _replace_acted(
    acted: tuple[tuple[int, int | None], ...], seat: int, value: int | None
) -> tuple[tuple[int, int | None], ...]:
    return tuple((known, value if known == seat else old) for known, old in acted)


def _next_pending(
    action_order: tuple[int, ...], needs_action: frozenset[int], after: int | None
) -> int | None:
    if not needs_action:
        return None
    if after is None:
        for seat in action_order:
            if seat in needs_action:
                return seat
        raise BettingStateError("pending action missing from action order")
    start = action_order.index(after)
    for offset in range(1, len(action_order) + 1):
        seat = action_order[(start + offset) % len(action_order)]
        if seat in needs_action:
            return seat
    raise BettingStateError("pending action missing from action order")


def _normalize_needs_action(
    players: tuple[BettingPlayer, ...],
    current_bet: int,
    needs_action: frozenset[int],
) -> frozenset[int]:
    """Remove impossible dry-side-pot actions while preserving call/fold duties.

    If exactly one player still has chips behind, no further bet/raise can create
    action because every opponent is folded or all-in. That lone player still
    must act if below the current price, but needs no redundant check when
    already matched.
    """
    actionable = [
        player
        for player in players
        if not player.folded and not player.all_in and player.stack > 0
    ]
    if len(actionable) == 1:
        lone = actionable[0]
        if lone.committed_street >= current_bet:
            return frozenset(seat for seat in needs_action if seat != lone.seat)
    return needs_action


def start_betting_round(
    *,
    street: Street,
    players: tuple[BettingPlayer, ...],
    initial_full_raise_increment: int,
    config: BettingConfig | None = None,
) -> BettingRoundState:
    """Start a round from exact stacks and already-posted street commitments."""
    if not players:
        raise BettingStateError("players are required")
    for player in players:
        player.validate()
    if initial_full_raise_increment <= 0:
        raise BettingStateError("initial full-raise increment must be positive")
    seats = tuple(player.seat for player in players)
    if len(set(seats)) != len(seats):
        raise BettingStateError("duplicate player seat")

    current_bet = max(player.committed_street for player in players)
    nonfolded = [player for player in players if not player.folded]
    hand_ended = len(nonfolded) <= 1
    needs_action = frozenset(
        player.seat
        for player in players
        if not player.folded and not player.all_in and player.stack > 0
    )
    if hand_ended:
        needs_action = frozenset()
    else:
        needs_action = _normalize_needs_action(players, current_bet, needs_action)
    closed = not needs_action
    state = BettingRoundState(
        street=street,
        action_order=seats,
        players=players,
        current_bet=current_bet,
        last_full_raise_increment=initial_full_raise_increment,
        needs_action=needs_action,
        acted_at_bet=tuple((seat, None) for seat in seats),
        next_actor=None if closed else _next_pending(seats, needs_action, None),
        config=config or BettingConfig(),
        closed=closed,
        hand_ended=hand_ended,
    )
    state.validate()
    return state


def _raise_right_open(state: BettingRoundState, seat: int) -> bool:
    acted_at = state.acted_at(seat)
    if acted_at is None:
        return True
    increase_faced = state.current_bet - acted_at
    policy = state.config.short_all_in_reopen
    if policy == ShortAllInReopenPolicy.NEVER:
        return False
    if policy == ShortAllInReopenPolicy.ANY_INCREASE:
        return increase_faced > 0
    if policy == ShortAllInReopenPolicy.CUMULATIVE_FULL_RAISE:
        return increase_faced >= state.last_full_raise_increment
    raise BettingStateError(f"unsupported reopen policy {policy!r}")


def legal_actions(state: BettingRoundState, seat: int | None = None) -> RoundLegalActions:
    state.validate()
    if state.closed:
        raise BettingStateError("betting round is closed")
    actor = state.next_actor if seat is None else seat
    if actor != state.next_actor:
        raise BettingStateError("legal actions requested for out-of-turn seat")
    if actor is None:
        raise BettingStateError("missing next actor")
    player = state.player(actor)

    to_call = state.current_bet - player.committed_street
    if to_call < 0:
        raise BettingStateError("negative to_call")
    call_amount = min(to_call, player.stack)
    raise_right = _raise_right_open(state, actor)
    max_raise_to = player.committed_street + player.stack
    full_raise_to = state.current_bet + state.last_full_raise_increment
    opponent_can_respond = any(
        other.seat != actor
        and not other.folded
        and not other.all_in
        and other.stack > 0
        for other in state.players
    )

    can_raise = False
    min_raise_to = 0
    legal_max_raise_to = 0
    if raise_right and opponent_can_respond and max_raise_to > state.current_bet:
        if max_raise_to >= full_raise_to:
            can_raise = True
            min_raise_to = full_raise_to
            legal_max_raise_to = max_raise_to
        elif state.config.allow_short_all_in_raise:
            # A sub-minimum raise can only be the player's exact all-in target.
            can_raise = True
            min_raise_to = max_raise_to
            legal_max_raise_to = max_raise_to

    return RoundLegalActions(
        can_fold=to_call > 0,
        can_check=to_call == 0,
        can_call=to_call > 0 and player.stack > 0,
        call_amount=call_amount,
        can_raise=can_raise,
        min_raise_to=min_raise_to,
        max_raise_to=legal_max_raise_to,
        full_raise_to=full_raise_to,
        raise_right_open=raise_right,
    )


def apply_action(
    state: BettingRoundState,
    action: ActionKind,
    amount_to: int | None = None,
) -> BettingRoundState:
    """Apply the in-turn action and return a new, fully validated round state."""
    state.validate()
    if state.closed or state.next_actor is None:
        raise BettingStateError("cannot act on a closed betting round")
    actor = state.next_actor
    player = state.player(actor)
    legal = legal_actions(state)

    if action == ActionKind.FOLD:
        if not legal.can_fold or amount_to is not None:
            raise BettingStateError("illegal fold")
        updated_player = replace(player, folded=True)
        players = _replace_player(state.players, updated_player)
        current_bet = state.current_bet
        last_full_raise = state.last_full_raise_increment
        needs_action = frozenset(seat for seat in state.needs_action if seat != actor)
        acted = _replace_acted(state.acted_at_bet, actor, state.current_bet)

    elif action == ActionKind.CHECK:
        if not legal.can_check or amount_to is not None:
            raise BettingStateError("illegal check")
        players = state.players
        current_bet = state.current_bet
        last_full_raise = state.last_full_raise_increment
        needs_action = frozenset(seat for seat in state.needs_action if seat != actor)
        acted = _replace_acted(state.acted_at_bet, actor, state.current_bet)

    elif action == ActionKind.CALL:
        if not legal.can_call or amount_to is not None:
            raise BettingStateError("illegal call")
        paid = legal.call_amount
        updated_player = replace(
            player,
            stack=player.stack - paid,
            committed_street=player.committed_street + paid,
            all_in=(player.stack - paid == 0),
        )
        players = _replace_player(state.players, updated_player)
        current_bet = state.current_bet
        last_full_raise = state.last_full_raise_increment
        needs_action = frozenset(seat for seat in state.needs_action if seat != actor)
        acted = _replace_acted(state.acted_at_bet, actor, state.current_bet)

    elif action == ActionKind.RAISE_TO:
        if amount_to is None or not legal.is_raise_to_legal(amount_to):
            raise BettingStateError("illegal raise_to")
        paid = amount_to - player.committed_street
        if paid <= 0 or paid > player.stack:
            raise BettingStateError("raise payment outside stack")
        old_current_bet = state.current_bet
        increment = amount_to - old_current_bet
        is_full_raise = increment >= state.last_full_raise_increment
        updated_player = replace(
            player,
            stack=player.stack - paid,
            committed_street=amount_to,
            all_in=(player.stack - paid == 0),
        )
        if not is_full_raise and not updated_player.all_in:
            raise BettingStateError("sub-minimum raise must be all-in")
        players = _replace_player(state.players, updated_player)
        current_bet = amount_to

        if is_full_raise:
            last_full_raise = increment
            # A full raise reopens action for every other live, non-all-in player.
            needs_action = frozenset(
                other.seat
                for other in players
                if other.seat != actor
                and not other.folded
                and not other.all_in
                and other.stack > 0
            )
            acted = tuple(
                (seat, current_bet if seat == actor else None)
                for seat in state.action_order
            )
        else:
            last_full_raise = state.last_full_raise_increment
            # A short all-in changes the price. Everyone still live and below the
            # new price must respond, but prior raise rights are not reset here.
            needs_action = frozenset(
                other.seat
                for other in players
                if other.seat != actor
                and not other.folded
                and not other.all_in
                and other.stack > 0
                and other.committed_street < current_bet
            )
            acted = _replace_acted(state.acted_at_bet, actor, current_bet)

    else:
        raise BettingStateError(f"unsupported action {action!r}")

    nonfolded = [other for other in players if not other.folded]
    hand_ended = len(nonfolded) <= 1
    if hand_ended:
        needs_action = frozenset()
    else:
        eligible = {
            other.seat
            for other in players
            if not other.folded and not other.all_in and other.stack > 0
        }
        needs_action = frozenset(seat for seat in needs_action if seat in eligible)
        needs_action = _normalize_needs_action(players, current_bet, needs_action)

    closed = not needs_action
    next_actor = None if closed else _next_pending(state.action_order, needs_action, actor)
    next_seq = state.events[-1].seq + 1 if state.events else 0
    event = ActionEvent(
        seq=next_seq,
        street=state.street,
        actor_seat=actor,
        action=action,
        amount_to=amount_to if action == ActionKind.RAISE_TO else None,
    )

    result = BettingRoundState(
        street=state.street,
        action_order=state.action_order,
        players=players,
        current_bet=current_bet,
        last_full_raise_increment=last_full_raise,
        needs_action=needs_action,
        acted_at_bet=acted,
        next_actor=next_actor,
        config=state.config,
        events=state.events + (event,),
        closed=closed,
        hand_ended=hand_ended,
    )
    result.validate()
    return result


def round_chip_total(state: BettingRoundState) -> int:
    """Conserved chips represented by stack-behind + street commitment."""
    state.validate()
    return sum(player.stack + player.committed_street for player in state.players)
