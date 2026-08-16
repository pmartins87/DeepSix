"""Full-hand state machine layered on the deterministic betting-round engine.

This module joins the already-tested betting-round semantics into an auditable
Short Deck hand lifecycle:

    forced antes -> preflop betting -> flop chance -> flop betting ->
    turn chance -> turn betting -> river chance -> river betting -> showdown

A hand can also terminate early when every player but one folds.  When all
remaining opponents are all-in, betting rounds close as dry side pots and the
state machine waits only for the remaining board cards.

The still-client-dependent KKPoker short-all-in reopen rule is inherited from
``BettingConfig`` and remains parameterized.  The caller also supplies the
preflop opening full-raise increment and postflop minimum bet explicitly, so
this module does not smuggle unresolved UI/rule assumptions into the Core.

All chip amounts are exact integer table units.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .betting import (
    BettingConfig,
    BettingPlayer,
    BettingRoundState,
    BettingStateError,
    apply_action as apply_round_action,
    start_betting_round,
)
from .cards import ShortDeckCardError, decode_card
from .state import ActionEvent, ActionKind, Street


class HandStateError(ValueError):
    pass


class HandPhase(str, Enum):
    BETTING = "betting"
    WAITING_FLOP = "waiting_flop"
    WAITING_TURN = "waiting_turn"
    WAITING_RIVER = "waiting_river"
    SHOWDOWN = "showdown"
    TERMINAL_FOLD = "terminal_fold"


@dataclass(frozen=True)
class HandConfig:
    ante: int
    preflop_full_raise_increment: int
    postflop_min_bet: int
    betting: BettingConfig = BettingConfig()

    def validate(self) -> None:
        for name in ("ante", "preflop_full_raise_increment", "postflop_min_bet"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise HandStateError(f"{name} must be a positive integer")
        if not isinstance(self.betting, BettingConfig):
            raise HandStateError("betting must be a BettingConfig")


@dataclass(frozen=True)
class HandPlayer:
    seat: int
    stack: int
    committed_total: int
    folded: bool = False
    all_in: bool = False

    def validate(self) -> None:
        if isinstance(self.seat, bool) or not isinstance(self.seat, int):
            raise HandStateError("seat must be an integer")
        if self.seat < 0 or self.seat >= 6:
            raise HandStateError("seat must be in physical OH6Plus range 0..5")
        if self.stack < 0 or self.committed_total < 0:
            raise HandStateError("stack/committed_total must be non-negative")
        if self.folded and self.all_in:
            raise HandStateError("player cannot be folded and all-in")
        if self.stack == 0 and not self.folded and not self.all_in:
            raise HandStateError("zero-stack live player must be marked all-in")
        if self.all_in and self.stack != 0:
            raise HandStateError("all-in player must have zero stack behind")


@dataclass(frozen=True)
class HandState:
    config: HandConfig
    dealer_seat: int
    action_order: tuple[int, ...]
    players: tuple[HandPlayer, ...]
    initial_total_chips: int
    street: Street
    phase: HandPhase
    board: tuple[int, ...]
    actions: tuple[ActionEvent, ...]
    betting_round: BettingRoundState

    def player(self, seat: int) -> HandPlayer:
        for player in self.players:
            if player.seat == seat:
                return player
        raise HandStateError(f"unknown seat {seat}")

    def pot(self) -> int:
        return sum(player.committed_total for player in self.players)

    def validate(self) -> None:
        self.config.validate()
        if len(self.players) < 2 or len(self.players) > 6:
            raise HandStateError("hand requires 2..6 dealt players")
        for player in self.players:
            player.validate()
        seats = tuple(player.seat for player in self.players)
        if len(set(seats)) != len(seats):
            raise HandStateError("duplicate player seat")
        if self.dealer_seat not in seats:
            raise HandStateError("dealer_seat must be dealt")
        expected_order = _action_order_from_physical_seats(seats, self.dealer_seat)
        if self.action_order != expected_order:
            raise HandStateError("action_order is not clockwise left-of-Dealer through Dealer")
        if seats != self.action_order:
            raise HandStateError("players must be stored in action_order order")

        if isinstance(self.initial_total_chips, bool) or not isinstance(
            self.initial_total_chips, int
        ) or self.initial_total_chips <= 0:
            raise HandStateError("initial_total_chips must be a positive integer")
        if hand_chip_total(self) != self.initial_total_chips:
            raise HandStateError("hand chip conservation violated")

        expected_board = {
            Street.PREFLOP: 0,
            Street.FLOP: 3,
            Street.TURN: 4,
            Street.RIVER: 5,
        }[self.street]
        if len(self.board) != expected_board:
            raise HandStateError(
                f"{self.street.value} requires {expected_board} board cards"
            )
        if len(set(self.board)) != len(self.board):
            raise HandStateError("duplicate board card")
        try:
            for card in self.board:
                decode_card(card)
        except ShortDeckCardError as exc:
            raise HandStateError(str(exc)) from exc

        if self.betting_round.street != self.street:
            raise HandStateError("betting round street differs from hand street")
        self.betting_round.validate()
        round_seats = tuple(player.seat for player in self.betting_round.players)
        if round_seats != self.action_order:
            raise HandStateError("betting round action order differs from hand")
        for round_player in self.betting_round.players:
            hand_player = self.player(round_player.seat)
            if round_player.stack != hand_player.stack:
                raise HandStateError("round/player stack mismatch")
            if round_player.folded != hand_player.folded:
                raise HandStateError("round/player folded mismatch")
            if round_player.all_in != hand_player.all_in:
                raise HandStateError("round/player all-in mismatch")
            if round_player.committed_street > hand_player.committed_total:
                raise HandStateError("street commitment exceeds total commitment")

        if self.phase == HandPhase.BETTING:
            if self.betting_round.closed:
                raise HandStateError("BETTING phase requires an open betting round")
        else:
            if not self.betting_round.closed:
                raise HandStateError("non-BETTING phase requires a closed betting round")

        nonfolded = [player for player in self.players if not player.folded]
        if self.phase == HandPhase.TERMINAL_FOLD:
            if len(nonfolded) != 1 or not self.betting_round.hand_ended:
                raise HandStateError("TERMINAL_FOLD requires exactly one nonfolded player")
        elif len(nonfolded) <= 1:
            raise HandStateError("single-player hand must be TERMINAL_FOLD")

        expected_phase = {
            HandPhase.WAITING_FLOP: Street.PREFLOP,
            HandPhase.WAITING_TURN: Street.FLOP,
            HandPhase.WAITING_RIVER: Street.TURN,
            HandPhase.SHOWDOWN: Street.RIVER,
        }
        if self.phase in expected_phase and self.street != expected_phase[self.phase]:
            raise HandStateError("phase/street mismatch")
        if self.phase == HandPhase.SHOWDOWN and len(self.board) != 5:
            raise HandStateError("showdown requires a complete board")

        previous_street_index = -1
        for expected_seq, event in enumerate(self.actions):
            event.validate()
            if event.seq != expected_seq:
                raise HandStateError("hand action sequence must be contiguous from zero")
            if event.actor_seat not in seats:
                raise HandStateError("hand action actor is not dealt")
            street_index = _street_index(event.street)
            if street_index < previous_street_index:
                raise HandStateError("hand actions cannot move backwards across streets")
            if street_index > _street_index(self.street):
                raise HandStateError("hand action occurs after current street")
            previous_street_index = street_index


def _street_index(street: Street) -> int:
    return {
        Street.PREFLOP: 0,
        Street.FLOP: 1,
        Street.TURN: 2,
        Street.RIVER: 3,
    }[street]


def _action_order_from_physical_seats(
    seats: tuple[int, ...], dealer_seat: int
) -> tuple[int, ...]:
    """Match OH6Plus clockwise chair semantics for sparse 0..5 physical seats."""
    if dealer_seat not in seats:
        raise HandStateError("dealer_seat must be dealt")
    seat_set = set(seats)
    order: list[int] = []
    chair = dealer_seat
    for _ in range(5):
        for offset in range(1, 7):
            candidate = (chair + offset) % 6
            if candidate in seat_set:
                chair = candidate
                break
        else:
            raise HandStateError("could not find next dealt chair")
        if chair == dealer_seat:
            break
        order.append(chair)
    order.append(dealer_seat)
    if set(order) != seat_set or len(order) != len(seats):
        raise HandStateError("failed to construct complete physical action order")
    return tuple(order)


def _phase_after_closed_round(round_state: BettingRoundState) -> HandPhase:
    if not round_state.closed:
        return HandPhase.BETTING
    if round_state.hand_ended:
        return HandPhase.TERMINAL_FOLD
    return {
        Street.PREFLOP: HandPhase.WAITING_FLOP,
        Street.FLOP: HandPhase.WAITING_TURN,
        Street.TURN: HandPhase.WAITING_RIVER,
        Street.RIVER: HandPhase.SHOWDOWN,
    }[round_state.street]


def _round_players(players: tuple[HandPlayer, ...], *, reset_street: bool) -> tuple[BettingPlayer, ...]:
    return tuple(
        BettingPlayer(
            seat=player.seat,
            stack=player.stack,
            committed_street=0 if reset_street else player.committed_total,
            folded=player.folded,
            all_in=player.all_in,
        )
        for player in players
    )


def start_hand(
    *,
    dealer_seat: int,
    stacks: tuple[tuple[int, int], ...],
    config: HandConfig,
) -> HandState:
    """Start a hand from pre-forced-bet stacks.

    ``stacks`` contains ``(physical_seat, chips_before_forced_bets)`` entries.
    Every dealt player posts one ante and the Dealer posts two antes total.  A
    pathological short stack is clipped to its available stack and marked
    all-in rather than creating negative chips.
    """
    config.validate()
    if len(stacks) < 2 or len(stacks) > 6:
        raise HandStateError("hand requires 2..6 starting stacks")
    raw_seats = tuple(seat for seat, _ in stacks)
    if len(set(raw_seats)) != len(raw_seats):
        raise HandStateError("duplicate starting seat")
    for seat, stack in stacks:
        if isinstance(seat, bool) or not isinstance(seat, int) or seat < 0 or seat >= 6:
            raise HandStateError("starting seat must be in physical OH6Plus range 0..5")
        if isinstance(stack, bool) or not isinstance(stack, int) or stack <= 0:
            raise HandStateError("starting stack must be a positive integer")
    if dealer_seat not in raw_seats:
        raise HandStateError("dealer_seat must be among starting stacks")

    action_order = _action_order_from_physical_seats(raw_seats, dealer_seat)
    stack_by_seat = dict(stacks)
    players: list[HandPlayer] = []
    for seat in action_order:
        starting_stack = stack_by_seat[seat]
        required = config.ante * (2 if seat == dealer_seat else 1)
        posted = min(starting_stack, required)
        remaining = starting_stack - posted
        players.append(
            HandPlayer(
                seat=seat,
                stack=remaining,
                committed_total=posted,
                all_in=(remaining == 0),
            )
        )
    player_tuple = tuple(players)
    round_state = start_betting_round(
        street=Street.PREFLOP,
        players=_round_players(player_tuple, reset_street=False),
        initial_full_raise_increment=config.preflop_full_raise_increment,
        config=config.betting,
    )
    state = HandState(
        config=config,
        dealer_seat=dealer_seat,
        action_order=action_order,
        players=player_tuple,
        initial_total_chips=sum(stack for _, stack in stacks),
        street=Street.PREFLOP,
        phase=_phase_after_closed_round(round_state),
        board=(),
        actions=(),
        betting_round=round_state,
    )
    state.validate()
    return state


def _sync_players_after_round_action(
    hand_players: tuple[HandPlayer, ...],
    before: BettingRoundState,
    after: BettingRoundState,
) -> tuple[HandPlayer, ...]:
    before_by_seat = {player.seat: player for player in before.players}
    after_by_seat = {player.seat: player for player in after.players}
    result: list[HandPlayer] = []
    for player in hand_players:
        before_player = before_by_seat[player.seat]
        after_player = after_by_seat[player.seat]
        paid = before_player.stack - after_player.stack
        if paid < 0:
            raise HandStateError("betting action increased a player's stack")
        result.append(
            replace(
                player,
                stack=after_player.stack,
                committed_total=player.committed_total + paid,
                folded=after_player.folded,
                all_in=after_player.all_in,
            )
        )
    return tuple(result)


def apply_hand_action(
    state: HandState,
    action: ActionKind,
    amount_to: int | None = None,
) -> HandState:
    """Apply the current actor's action and advance phase if the street closes."""
    state.validate()
    if state.phase != HandPhase.BETTING:
        raise HandStateError("cannot apply betting action outside BETTING phase")
    before = state.betting_round
    try:
        after = apply_round_action(before, action, amount_to)
    except BettingStateError as exc:
        raise HandStateError(str(exc)) from exc

    players = _sync_players_after_round_action(state.players, before, after)
    actor = before.next_actor
    if actor is None:
        raise HandStateError("open betting round has no actor")
    event = ActionEvent(
        seq=len(state.actions),
        street=state.street,
        actor_seat=actor,
        action=action,
        amount_to=amount_to if action == ActionKind.RAISE_TO else None,
    )
    result = replace(
        state,
        players=players,
        phase=_phase_after_closed_round(after),
        actions=state.actions + (event,),
        betting_round=after,
    )
    result.validate()
    return result


def deal_next_board(state: HandState, cards: tuple[int, ...]) -> HandState:
    """Reveal the next board chunk and start (or auto-close) the next street.

    FLOP is revealed as exactly three simultaneous cards.  TURN and RIVER are
    revealed one card at a time.  No board chance event is accepted after a
    fold terminal or after showdown.
    """
    state.validate()
    transition = {
        HandPhase.WAITING_FLOP: (Street.FLOP, 3),
        HandPhase.WAITING_TURN: (Street.TURN, 1),
        HandPhase.WAITING_RIVER: (Street.RIVER, 1),
    }
    if state.phase not in transition:
        raise HandStateError("hand is not waiting for a board reveal")
    next_street, expected_count = transition[state.phase]
    if len(cards) != expected_count:
        raise HandStateError(
            f"{state.phase.value} requires exactly {expected_count} revealed card(s)"
        )
    try:
        for card in cards:
            decode_card(card)
    except ShortDeckCardError as exc:
        raise HandStateError(str(exc)) from exc
    if len(set(cards)) != len(cards) or set(cards) & set(state.board):
        raise HandStateError("duplicate board card")

    board = state.board + tuple(cards)
    round_state = start_betting_round(
        street=next_street,
        players=_round_players(state.players, reset_street=True),
        initial_full_raise_increment=state.config.postflop_min_bet,
        config=state.config.betting,
    )
    result = replace(
        state,
        street=next_street,
        phase=_phase_after_closed_round(round_state),
        board=board,
        betting_round=round_state,
    )
    result.validate()
    return result


def fold_winner(state: HandState) -> int | None:
    """Return the winning seat only for an early fold terminal."""
    state.validate()
    if state.phase != HandPhase.TERMINAL_FOLD:
        return None
    winners = [player.seat for player in state.players if not player.folded]
    if len(winners) != 1:
        raise HandStateError("fold terminal does not have exactly one winner")
    return winners[0]


def hand_chip_total(state: HandState) -> int:
    """Conserved chips represented by stack-behind plus gross pot contributions."""
    return sum(player.stack + player.committed_total for player in state.players)
