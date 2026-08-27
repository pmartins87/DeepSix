"""Exact solver-facing action/chance branch state for DeepSix F5.

`SimulatedHand` owns a seeded shuffled deck and automatically advances chance.
That is ideal for sessions and replay, but a game solver must be able to fork a
state and choose/enumerate an arbitrary legal public chance outcome.  This
module decouples those concerns without creating a second poker rules engine:
all betting transitions still go through `apply_hand_action`, all board
transitions still go through `deal_next_board`, and terminal settlement still
goes through the simulator's versioned settlement layer.

The object stores a complete fixed private assignment.  It is therefore an
exact perfect-information branch primitive / correctness oracle, not the final
imperfect-information solver state. Range/reach marginalization lives above it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from deepsix_core.betting import RoundLegalActions, legal_actions
from deepsix_core.cards import decode_card
from deepsix_core.ggpoker_economy import ggpoker_shortdeck_stake
from deepsix_core.hand import (
    HandPhase,
    HandState,
    HandStateError,
    apply_hand_action,
    deal_next_board,
    start_hand,
)
from deepsix_core.state import ActionKind
from deepsix_simulator.environment import SimulatedHand
from deepsix_simulator.rules import DEFAULT_SIMULATOR_RULES, SimulatorRulesProfile
from deepsix_simulator.settlement import SimulatorSettlement, settle_terminal_hand

from .multistreet_chance import ExactChanceOutcome, enumerate_exact_board_chance


class ExactBranchError(ValueError):
    """Raised when an exact solver branch violates the authoritative game state."""


class BranchNodeKind(str, Enum):
    DECISION = "decision"
    CHANCE = "chance"
    TERMINAL = "terminal"


def _canonical_hole_map(
    hole_cards: Mapping[int, Sequence[int]],
) -> tuple[tuple[int, tuple[int, int]], ...]:
    rows: list[tuple[int, tuple[int, int]]] = []
    used: set[int] = set()
    for seat in sorted(hole_cards):
        if isinstance(seat, bool) or not isinstance(seat, int) or not 0 <= seat <= 5:
            raise ExactBranchError("hole-card seat must be an integer within 0..5")
        raw = tuple(hole_cards[seat])
        if len(raw) != 2 or raw[0] == raw[1]:
            raise ExactBranchError(f"seat {seat} must have two distinct hole cards")
        try:
            decode_card(raw[0])
            decode_card(raw[1])
        except (TypeError, ValueError) as exc:
            raise ExactBranchError(f"seat {seat} has invalid Short Deck hole cards") from exc
        if raw[0] in used or raw[1] in used:
            raise ExactBranchError("private assignment contains duplicate cards")
        used.update(raw)
        rows.append((seat, (raw[0], raw[1])))
    return tuple(rows)


@dataclass(frozen=True)
class ExactBranchState:
    """One immutable fixed-private branch with explicit action/chance stepping."""

    stake_cents: int
    rules: SimulatorRulesProfile
    bbj_enabled: bool
    state: HandState
    hole_cards: tuple[tuple[int, tuple[int, int]], ...]

    def __post_init__(self) -> None:
        try:
            ggpoker_shortdeck_stake(self.stake_cents)
            self.rules.validate()
            self.state.validate()
        except Exception as exc:
            raise ExactBranchError(str(exc)) from exc
        if not isinstance(self.bbj_enabled, bool):
            raise ExactBranchError("bbj_enabled must be bool")
        if self.state.config != self.rules.hand_config(self.stake_cents):
            raise ExactBranchError("branch HandConfig differs from rules/stake profile")

        seats = tuple(player.seat for player in self.state.players)
        hole_seats = tuple(seat for seat, _ in self.hole_cards)
        if hole_seats != tuple(sorted(hole_seats)) or len(set(hole_seats)) != len(hole_seats):
            raise ExactBranchError("hole-card rows must be uniquely seat-sorted")
        if set(hole_seats) != set(seats):
            raise ExactBranchError("private assignment must cover every dealt seat exactly")

        used: set[int] = set()
        for seat, cards in self.hole_cards:
            if isinstance(seat, bool) or not isinstance(seat, int) or not 0 <= seat <= 5:
                raise ExactBranchError("hole-card seat must be an integer within 0..5")
            if len(cards) != 2 or cards[0] == cards[1]:
                raise ExactBranchError(f"seat {seat} must have two distinct hole cards")
            try:
                decode_card(cards[0])
                decode_card(cards[1])
            except (TypeError, ValueError) as exc:
                raise ExactBranchError(f"seat {seat} has invalid Short Deck hole cards") from exc
            if cards[0] in used or cards[1] in used:
                raise ExactBranchError("private assignment contains duplicate cards")
            used.update(cards)
        if used & set(self.state.board):
            raise ExactBranchError("private assignment overlaps public board")

    @classmethod
    def from_private_assignment(
        cls,
        *,
        stake_cents: int,
        dealer_seat: int,
        stacks: tuple[tuple[int, int], ...],
        hole_cards: Mapping[int, Sequence[int]],
        rules: SimulatorRulesProfile = DEFAULT_SIMULATOR_RULES,
        bbj_enabled: bool = True,
    ) -> "ExactBranchState":
        rows = _canonical_hole_map(hole_cards)
        try:
            state = start_hand(
                dealer_seat=dealer_seat,
                stacks=stacks,
                config=rules.hand_config(stake_cents),
            )
        except Exception as exc:
            raise ExactBranchError(str(exc)) from exc
        return cls(
            stake_cents=stake_cents,
            rules=rules,
            bbj_enabled=bbj_enabled,
            state=state,
            hole_cards=rows,
        )

    @classmethod
    def from_simulated_hand(cls, hand: SimulatedHand) -> "ExactBranchState":
        if not isinstance(hand, SimulatedHand):
            raise ExactBranchError("from_simulated_hand requires SimulatedHand")
        return cls(
            stake_cents=hand.stake_cents,
            rules=hand.rules,
            bbj_enabled=hand.bbj_enabled,
            state=hand.state,
            hole_cards=_canonical_hole_map(hand.hole_cards),
        )

    @property
    def node_kind(self) -> BranchNodeKind:
        if self.state.phase == HandPhase.BETTING:
            return BranchNodeKind.DECISION
        if self.state.phase in (
            HandPhase.WAITING_FLOP,
            HandPhase.WAITING_TURN,
            HandPhase.WAITING_RIVER,
        ):
            return BranchNodeKind.CHANCE
        if self.state.phase in (HandPhase.SHOWDOWN, HandPhase.TERMINAL_FOLD):
            return BranchNodeKind.TERMINAL
        raise ExactBranchError(f"unsupported hand phase {self.state.phase!r}")

    @property
    def actor_seat(self) -> int | None:
        if self.node_kind != BranchNodeKind.DECISION:
            return None
        return self.state.betting_round.next_actor

    def hole_cards_mapping(self) -> dict[int, tuple[int, int]]:
        return dict(self.hole_cards)

    def private_cards_flat(self) -> tuple[int, ...]:
        return tuple(card for _, cards in self.hole_cards for card in cards)

    def legal_actions(self) -> RoundLegalActions:
        if self.node_kind != BranchNodeKind.DECISION:
            raise ExactBranchError("legal actions require a decision node")
        try:
            return legal_actions(self.state.betting_round)
        except Exception as exc:
            raise ExactBranchError(str(exc)) from exc

    def apply_action(
        self,
        action: ActionKind,
        amount_to: int | None = None,
    ) -> "ExactBranchState":
        if self.node_kind != BranchNodeKind.DECISION:
            raise ExactBranchError("betting action requires a decision node")
        try:
            child = apply_hand_action(self.state, action, amount_to)
        except HandStateError as exc:
            raise ExactBranchError(str(exc)) from exc
        return ExactBranchState(
            stake_cents=self.stake_cents,
            rules=self.rules,
            bbj_enabled=self.bbj_enabled,
            state=child,
            hole_cards=self.hole_cards,
        )

    def chance_outcomes(self) -> tuple[ExactChanceOutcome, ...]:
        if self.node_kind != BranchNodeKind.CHANCE:
            raise ExactBranchError("chance outcomes require a chance node")
        return enumerate_exact_board_chance(
            self.state.board,
            self.private_cards_flat(),
        )

    def apply_chance(self, revealed: Sequence[int]) -> "ExactBranchState":
        if self.node_kind != BranchNodeKind.CHANCE:
            raise ExactBranchError("board reveal requires a chance node")
        cards = tuple(revealed)
        private = set(self.private_cards_flat())
        if private & set(cards):
            raise ExactBranchError("board reveal overlaps fixed private cards")
        try:
            child = deal_next_board(self.state, cards)
        except HandStateError as exc:
            raise ExactBranchError(str(exc)) from exc
        return ExactBranchState(
            stake_cents=self.stake_cents,
            rules=self.rules,
            bbj_enabled=self.bbj_enabled,
            state=child,
            hole_cards=self.hole_cards,
        )

    def settle(self) -> SimulatorSettlement:
        if self.node_kind != BranchNodeKind.TERMINAL:
            raise ExactBranchError("settlement requires a terminal branch")
        try:
            return settle_terminal_hand(
                self.state,
                self.hole_cards_mapping(),
                stake_cents=self.stake_cents,
                bbj_enabled=self.bbj_enabled,
                rules=self.rules,
            )
        except Exception as exc:
            raise ExactBranchError(str(exc)) from exc
