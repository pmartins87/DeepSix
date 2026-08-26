"""Stable reset/observe/step boundary for trainer and self-play workers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from deepsix_core.betting import RoundLegalActions
from deepsix_core.ggpoker_economy import ggpoker_shortdeck_stake
from deepsix_core.state import ActionEvent

from .environment import (
    SIMULATOR_ENV_VERSION,
    SimulatedHand,
    SimulatorAction,
    SimulatorEnvironmentError,
    SimulatorObservation,
)
from .rules import DEFAULT_SIMULATOR_RULES, SimulatorRulesProfile
from .settlement import SimulatorSettlement


SIMULATOR_OBSERVATION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SimulatorResetConfig:
    stake_cents: int
    dealer_seat: int
    stacks: tuple[tuple[int, int], ...]
    bbj_enabled: bool = True

    def validate(self) -> None:
        ggpoker_shortdeck_stake(self.stake_cents)
        seats = [seat for seat, _ in self.stacks]
        if len(seats) < 2 or len(seats) > 6 or len(set(seats)) != len(seats):
            raise SimulatorEnvironmentError("reset requires 2..6 unique seats")
        if any(
            isinstance(seat, bool)
            or not isinstance(seat, int)
            or seat < 0
            or seat >= 6
            for seat in seats
        ):
            raise SimulatorEnvironmentError("reset seats must be physical 0..5")
        if self.dealer_seat not in seats:
            raise SimulatorEnvironmentError("reset Dealer must be one of the seats")
        if any(
            isinstance(stack, bool) or not isinstance(stack, int) or stack <= 0
            for _, stack in self.stacks
        ):
            raise SimulatorEnvironmentError("reset stacks must be positive integers")
        if not isinstance(self.bbj_enabled, bool):
            raise SimulatorEnvironmentError("bbj_enabled must be bool")


@dataclass(frozen=True)
class SimulatorStepResult:
    acted_seat: int
    decision_index: int
    terminal: bool
    next_actor_seat: int | None
    next_observation: SimulatorObservation | None
    settlement: SimulatorSettlement | None


def _legal_to_dict(legal: RoundLegalActions | None) -> dict[str, Any] | None:
    if legal is None:
        return None
    return {
        "can_fold": legal.can_fold,
        "can_check": legal.can_check,
        "can_call": legal.can_call,
        "call_amount": legal.call_amount,
        "can_raise": legal.can_raise,
        "min_raise_to": legal.min_raise_to,
        "max_raise_to": legal.max_raise_to,
        "full_raise_to": legal.full_raise_to,
        "raise_right_open": legal.raise_right_open,
    }


def _event_to_dict(event: ActionEvent) -> dict[str, Any]:
    return {
        "seq": event.seq,
        "street": event.street.value,
        "actor_seat": event.actor_seat,
        "action": event.action.value,
        "amount_to": event.amount_to,
    }


def observation_to_dict(observation: SimulatorObservation) -> dict[str, Any]:
    """Serialize only the information available to the requested seat."""
    return {
        "schema_version": SIMULATOR_OBSERVATION_SCHEMA_VERSION,
        "env_version": observation.env_version,
        "rules_version": observation.rules_version,
        "economy_version": observation.economy_version,
        "hand_id": observation.hand_id,
        "decision_index": observation.decision_index,
        "hero_seat": observation.hero_seat,
        "dealer_seat": observation.dealer_seat,
        "actor_seat": observation.actor_seat,
        "street": observation.street.value,
        "phase": observation.phase.value,
        "board": list(observation.board),
        "hero_hole_cards": list(observation.hero_hole_cards),
        "pot": observation.pot,
        "players": [
            {
                "seat": player.seat,
                "stack": player.stack,
                "committed_total": player.committed_total,
                "folded": player.folded,
                "all_in": player.all_in,
            }
            for player in observation.players
        ],
        "actions": [_event_to_dict(event) for event in observation.actions],
        "legal": _legal_to_dict(observation.legal),
    }


def observation_canonical_json(observation: SimulatorObservation) -> str:
    return json.dumps(
        observation_to_dict(observation),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def observation_fingerprint(observation: SimulatorObservation) -> str:
    return hashlib.sha256(
        observation_canonical_json(observation).encode("utf-8")
    ).hexdigest()


class DeepSixEnv:
    """Gym-like but dependency-free single-hand environment.

    The environment is intentionally small: reset creates one hand, observe is
    seat-local, and step consumes exactly one in-turn action. Session management
    lives in `DeepSixTable`; trainer workers can choose either boundary.
    """

    def __init__(
        self,
        config: SimulatorResetConfig,
        *,
        rules: SimulatorRulesProfile = DEFAULT_SIMULATOR_RULES,
    ) -> None:
        config.validate()
        rules.validate()
        self.config = config
        self.rules = rules
        self.hand: SimulatedHand | None = None
        self.reset_count = 0

    def reset(self, *, seed: int, hand_id: str | None = None) -> SimulatorObservation | None:
        self.config.validate()
        if hand_id is None:
            hand_id = f"env-{self.reset_count:08d}-seed-{seed}"
        self.hand = SimulatedHand.start(
            hand_id=hand_id,
            stake_cents=self.config.stake_cents,
            seed=seed,
            dealer_seat=self.config.dealer_seat,
            stacks=self.config.stacks,
            rules=self.rules,
            bbj_enabled=self.config.bbj_enabled,
        )
        self.reset_count += 1
        return self.current_observation()

    def _require_hand(self) -> SimulatedHand:
        if self.hand is None:
            raise SimulatorEnvironmentError("environment must be reset before use")
        return self.hand

    def observe(self, seat: int) -> SimulatorObservation:
        return self._require_hand().observation(seat)

    def current_observation(self) -> SimulatorObservation | None:
        hand = self._require_hand()
        actor = hand.actor_seat
        if actor is None:
            return None
        return hand.observation(actor)

    def legal_actions(self, seat: int) -> RoundLegalActions:
        observation = self.observe(seat)
        if not observation.is_hero_turn or observation.legal is None:
            raise SimulatorEnvironmentError("legal_actions requested out of turn")
        return observation.legal

    def step(
        self,
        decision: SimulatorAction,
        *,
        seat: int | None = None,
    ) -> SimulatorStepResult:
        hand = self._require_hand()
        if hand.terminal:
            raise SimulatorEnvironmentError("cannot step a terminal environment")
        actor = hand.actor_seat
        if actor is None:
            raise SimulatorEnvironmentError("nonterminal environment has no actor")
        if seat is not None and seat != actor:
            raise SimulatorEnvironmentError("step seat differs from current actor")
        before_index = hand.decision_index
        hand.act(actor, decision)
        next_obs = self.current_observation()
        return SimulatorStepResult(
            acted_seat=actor,
            decision_index=before_index,
            terminal=hand.terminal,
            next_actor_seat=hand.actor_seat,
            next_observation=next_obs,
            settlement=hand.settlement if hand.terminal else None,
        )
