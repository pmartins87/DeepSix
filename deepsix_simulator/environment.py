"""Deterministic 2..6-player Short Deck simulator environment.

This module is the first runtime that is actually on the DeepSix critical path.
It consumes the already-gated Core state machine, deals hidden/public cards from
one seeded 36-card deck, exposes seat-specific observations, accepts only legal
Core actions and settles terminal hands with the versioned GGPoker-economy
simulator layer.

There is no dependency on OpenHoldem, scraping or a real poker client.
"""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Callable, Mapping

from deepsix_core.betting import RoundLegalActions, legal_actions
from deepsix_core.ggpoker_economy import (
    GGPOKER_SHORTDECK_ECONOMY_VERSION,
    ggpoker_shortdeck_stake,
)
from deepsix_core.hand import (
    HandPhase,
    HandState,
    apply_hand_action,
    deal_next_board,
    start_hand,
)
from deepsix_core.state import ActionEvent, ActionKind, Street

from .rules import DEFAULT_SIMULATOR_RULES, SimulatorRulesProfile
from .settlement import SimulatorSettlement, settle_terminal_hand


SIMULATOR_ENV_VERSION = "deepsix_simulator_env_2026-08-25_v1"


class SimulatorEnvironmentError(ValueError):
    pass


@dataclass(frozen=True)
class SimulatorAction:
    action: ActionKind
    amount_to: int | None = None


@dataclass(frozen=True)
class PublicPlayerState:
    seat: int
    stack: int
    committed_total: int
    folded: bool
    all_in: bool


@dataclass(frozen=True)
class SimulatorObservation:
    env_version: str
    rules_version: str
    economy_version: str
    hand_id: str
    decision_index: int
    hero_seat: int
    dealer_seat: int
    actor_seat: int | None
    street: Street
    phase: HandPhase
    board: tuple[int, ...]
    hero_hole_cards: tuple[int, int]
    pot: int
    players: tuple[PublicPlayerState, ...]
    actions: tuple[ActionEvent, ...]
    legal: RoundLegalActions | None

    @property
    def is_hero_turn(self) -> bool:
        return self.actor_seat == self.hero_seat and self.phase == HandPhase.BETTING

    @property
    def terminal(self) -> bool:
        return self.phase in (HandPhase.SHOWDOWN, HandPhase.TERMINAL_FOLD)


AgentPolicy = Callable[[SimulatorObservation], SimulatorAction]


class SimulatedHand:
    """One complete deterministic hand, including hidden deck and settlement."""

    def __init__(
        self,
        *,
        hand_id: str,
        stake_cents: int,
        seed: int,
        state: HandState,
        hole_cards: Mapping[int, tuple[int, int]],
        remaining_deck: tuple[int, ...],
        rules: SimulatorRulesProfile,
        bbj_enabled: bool,
    ) -> None:
        self.hand_id = str(hand_id)
        self.stake_cents = int(stake_cents)
        self.seed = int(seed)
        self.state = state
        self.hole_cards = dict(hole_cards)
        self._deck = list(remaining_deck)
        self._deck_cursor = 0
        self.rules = rules
        self.bbj_enabled = bbj_enabled
        self.decision_index = 0
        self.settlement: SimulatorSettlement | None = None
        self._validate_private_deal()
        self._advance_automatic()

    @classmethod
    def start(
        cls,
        *,
        hand_id: str,
        stake_cents: int,
        seed: int,
        dealer_seat: int,
        stacks: tuple[tuple[int, int], ...],
        rules: SimulatorRulesProfile = DEFAULT_SIMULATOR_RULES,
        bbj_enabled: bool = True,
    ) -> "SimulatedHand":
        rules.validate()
        ggpoker_shortdeck_stake(stake_cents)
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise SimulatorEnvironmentError("seed must be an integer")
        if not isinstance(bbj_enabled, bool):
            raise SimulatorEnvironmentError("bbj_enabled must be bool")

        state = start_hand(
            dealer_seat=dealer_seat,
            stacks=stacks,
            config=rules.hand_config(stake_cents),
        )
        deck = list(range(36))
        random.Random(seed).shuffle(deck)
        cursor = 0
        dealt: dict[int, list[int]] = {seat: [] for seat in state.action_order}
        # Round-robin dealing is explicit even though every permutation is
        # uniform; this makes replay semantics easy to inspect.
        for _ in range(2):
            for seat in state.action_order:
                dealt[seat].append(deck[cursor])
                cursor += 1
        holes = {seat: (cards[0], cards[1]) for seat, cards in dealt.items()}
        return cls(
            hand_id=hand_id,
            stake_cents=stake_cents,
            seed=seed,
            state=state,
            hole_cards=holes,
            remaining_deck=tuple(deck[cursor:]),
            rules=rules,
            bbj_enabled=bbj_enabled,
        )

    def _validate_private_deal(self) -> None:
        seats = {player.seat for player in self.state.players}
        if set(self.hole_cards) != seats:
            raise SimulatorEnvironmentError("hole-card map must cover every dealt seat")
        known: list[int] = []
        for seat in sorted(self.hole_cards):
            cards = self.hole_cards[seat]
            if len(cards) != 2 or cards[0] == cards[1]:
                raise SimulatorEnvironmentError(f"invalid hole cards for seat {seat}")
            known.extend(cards)
        known.extend(self._deck)
        if len(known) != 36 or set(known) != set(range(36)):
            raise SimulatorEnvironmentError("private deal/deck is not a full 36-card partition")

    def _draw(self, count: int) -> tuple[int, ...]:
        if count <= 0:
            raise SimulatorEnvironmentError("draw count must be positive")
        end = self._deck_cursor + count
        if end > len(self._deck):
            raise SimulatorEnvironmentError("simulator deck exhausted")
        cards = tuple(self._deck[self._deck_cursor:end])
        self._deck_cursor = end
        return cards

    def _settle_if_terminal(self) -> None:
        if self.settlement is not None:
            return
        if self.state.phase in (HandPhase.SHOWDOWN, HandPhase.TERMINAL_FOLD):
            self.settlement = settle_terminal_hand(
                self.state,
                self.hole_cards,
                stake_cents=self.stake_cents,
                bbj_enabled=self.bbj_enabled,
                rules=self.rules,
            )

    def _advance_automatic(self) -> None:
        """Reveal forced runout cards until the next real decision or terminal."""
        while True:
            if self.state.phase == HandPhase.WAITING_FLOP:
                self.state = deal_next_board(self.state, self._draw(3))
                continue
            if self.state.phase == HandPhase.WAITING_TURN:
                self.state = deal_next_board(self.state, self._draw(1))
                continue
            if self.state.phase == HandPhase.WAITING_RIVER:
                self.state = deal_next_board(self.state, self._draw(1))
                continue
            break
        self._settle_if_terminal()

    @property
    def terminal(self) -> bool:
        return self.settlement is not None

    @property
    def actor_seat(self) -> int | None:
        if self.state.phase != HandPhase.BETTING:
            return None
        return self.state.betting_round.next_actor

    def observation(self, seat: int) -> SimulatorObservation:
        if seat not in self.hole_cards:
            raise SimulatorEnvironmentError(f"seat {seat} was not dealt")
        actor = self.actor_seat
        legal = None
        if self.state.phase == HandPhase.BETTING and actor == seat:
            legal = legal_actions(self.state.betting_round)
        players = tuple(
            PublicPlayerState(
                seat=player.seat,
                stack=player.stack,
                committed_total=player.committed_total,
                folded=player.folded,
                all_in=player.all_in,
            )
            for player in self.state.players
        )
        return SimulatorObservation(
            env_version=SIMULATOR_ENV_VERSION,
            rules_version=self.rules.version,
            economy_version=GGPOKER_SHORTDECK_ECONOMY_VERSION,
            hand_id=self.hand_id,
            decision_index=self.decision_index,
            hero_seat=seat,
            dealer_seat=self.state.dealer_seat,
            actor_seat=actor,
            street=self.state.street,
            phase=self.state.phase,
            board=self.state.board,
            hero_hole_cards=self.hole_cards[seat],
            pot=self.state.pot(),
            players=players,
            actions=self.state.actions,
            legal=legal,
        )

    def act(self, seat: int, decision: SimulatorAction) -> None:
        if self.terminal:
            raise SimulatorEnvironmentError("cannot act after settlement")
        if self.state.phase != HandPhase.BETTING:
            raise SimulatorEnvironmentError("hand is not waiting for a betting action")
        if seat != self.actor_seat:
            raise SimulatorEnvironmentError(
                f"out-of-turn action: actor={self.actor_seat}, submitted={seat}"
            )
        if not isinstance(decision, SimulatorAction):
            raise SimulatorEnvironmentError("decision must be SimulatorAction")
        self.state = apply_hand_action(
            self.state,
            decision.action,
            decision.amount_to,
        )
        self.decision_index += 1
        self._advance_automatic()

    def play_to_terminal(
        self,
        agents: Mapping[int, AgentPolicy],
        *,
        max_decisions: int = 1000,
    ) -> SimulatorSettlement:
        """Run a full closed-loop hand using seat-local policy callables."""
        if max_decisions <= 0:
            raise SimulatorEnvironmentError("max_decisions must be positive")
        while not self.terminal:
            if self.decision_index >= max_decisions:
                raise SimulatorEnvironmentError("decision guard exceeded")
            actor = self.actor_seat
            if actor is None:
                raise SimulatorEnvironmentError("nonterminal hand has no actor")
            try:
                agent = agents[actor]
            except KeyError as exc:
                raise SimulatorEnvironmentError(f"missing agent for seat {actor}") from exc
            obs = self.observation(actor)
            decision = agent(obs)
            self.act(actor, decision)
        if self.settlement is None:
            raise SimulatorEnvironmentError("terminal hand missing settlement")
        return self.settlement


def check_call_policy(observation: SimulatorObservation) -> SimulatorAction:
    """Deterministic passive baseline used for simulator validation."""
    if not observation.is_hero_turn or observation.legal is None:
        raise SimulatorEnvironmentError("check_call_policy called out of turn")
    legal = observation.legal
    if legal.can_check:
        return SimulatorAction(ActionKind.CHECK)
    if legal.can_call:
        return SimulatorAction(ActionKind.CALL)
    if legal.can_fold:
        return SimulatorAction(ActionKind.FOLD)
    raise SimulatorEnvironmentError("no passive legal action")


def min_raise_else_check_call_policy(observation: SimulatorObservation) -> SimulatorAction:
    """Deterministic aggressive baseline for integration and stress tests."""
    if not observation.is_hero_turn or observation.legal is None:
        raise SimulatorEnvironmentError("aggressive baseline called out of turn")
    legal = observation.legal
    if legal.can_raise:
        return SimulatorAction(ActionKind.RAISE_TO, legal.min_raise_to)
    return check_call_policy(observation)


class DeepSixTable:
    """Cash-session shell that carries stacks and Dealer across simulator hands."""

    def __init__(
        self,
        *,
        stake_cents: int,
        player_count: int,
        dealer_seat: int = 0,
        initial_stacks: Mapping[int, int] | None = None,
        rules: SimulatorRulesProfile = DEFAULT_SIMULATOR_RULES,
        bbj_enabled: bool = True,
    ) -> None:
        rules.validate()
        stake = ggpoker_shortdeck_stake(stake_cents)
        if player_count < 2 or player_count > 6:
            raise SimulatorEnvironmentError("player_count must be within [2, 6]")
        seats = tuple(range(player_count))
        if dealer_seat not in seats:
            raise SimulatorEnvironmentError("dealer_seat must be seated")
        if initial_stacks is None:
            stacks = {seat: stake.default_buy_in_cents for seat in seats}
        else:
            if set(initial_stacks) != set(seats):
                raise SimulatorEnvironmentError("initial_stacks must cover every table seat")
            stacks = {seat: int(initial_stacks[seat]) for seat in seats}
        if any(value <= 0 for value in stacks.values()):
            raise SimulatorEnvironmentError("every initial stack must be positive")

        self.stake_cents = stake_cents
        self.seats = seats
        self.stacks = stacks
        self.dealer_seat = dealer_seat
        self.rules = rules
        self.bbj_enabled = bbj_enabled
        self.hand_index = 0

    def _live_seats(self) -> tuple[int, ...]:
        return tuple(seat for seat in self.seats if self.stacks.get(seat, 0) > 0)

    def _next_live_seat_clockwise(self, after: int) -> int:
        live = set(self._live_seats())
        if not live:
            raise SimulatorEnvironmentError("table has no live seats")
        for offset in range(1, 7):
            candidate = (after + offset) % 6
            if candidate in live:
                return candidate
        raise SimulatorEnvironmentError("could not rotate Dealer")

    def start_hand(self, *, seed: int) -> SimulatedHand:
        live = self._live_seats()
        if len(live) < 2:
            raise SimulatorEnvironmentError("fewer than two funded seats remain")
        dealer = self.dealer_seat
        if dealer not in live:
            dealer = self._next_live_seat_clockwise(dealer)
            self.dealer_seat = dealer
        return SimulatedHand.start(
            hand_id=f"sim-{self.hand_index:08d}-seed-{seed}",
            stake_cents=self.stake_cents,
            seed=seed,
            dealer_seat=dealer,
            stacks=tuple((seat, self.stacks[seat]) for seat in live),
            rules=self.rules,
            bbj_enabled=self.bbj_enabled,
        )

    def commit_settlement(self, hand: SimulatedHand) -> SimulatorSettlement:
        if not hand.terminal or hand.settlement is None:
            raise SimulatorEnvironmentError("cannot commit an unfinished hand")
        if hand.stake_cents != self.stake_cents:
            raise SimulatorEnvironmentError("hand/table stake mismatch")
        for seat, stack in hand.settlement.post_hand_stacks:
            self.stacks[seat] = stack
        old_dealer = hand.state.dealer_seat
        self.hand_index += 1
        if len(self._live_seats()) >= 2:
            self.dealer_seat = self._next_live_seat_clockwise(old_dealer)
        return hand.settlement

    def play_hand(
        self,
        agents: Mapping[int, AgentPolicy],
        *,
        seed: int,
        max_decisions: int = 1000,
    ) -> SimulatorSettlement:
        hand = self.start_hand(seed=seed)
        hand.play_to_terminal(agents, max_decisions=max_decisions)
        return self.commit_settlement(hand)
