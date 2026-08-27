"""Exact synchronous tabular CFR/RM+ adapter for the F5 HU reference game.

This is a correctness solver, not the production architecture winner. It keeps
all regrets, reach weights, chance probabilities and average-strategy weights as
``Fraction`` so the first multi-street solver loop can be audited without
floating-point ambiguity.

Only ``GROSS_POKER_DELTA`` is accepted for training because the v1 CFR regret
sign/update logic relies on a two-player zero-sum utility. The same frozen
average policy may later be evaluated under ``NET_CASH_DELTA`` by the reference
game, but net-rake utility is not silently fed into zero-sum CFR guarantees.

Iterations are synchronous: every private deal and board/action branch in one
iteration sees the same start-of-iteration regret table. Deltas are committed
only after the full traversal, matching the deterministic methodology already
gated in the river laboratory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Mapping

from .hu_multistreet_reference import (
    GROSS_POKER_DELTA,
    HuReferenceMicrogame,
    HuReferenceMicrogameError,
    MicroAction,
)
from .multistreet_branch import BranchNodeKind, ExactBranchState
from .multistreet_state import PrivateDecisionState, decision_state_from_components
from deepsix_simulator.utility import utility_from_settlement


HU_MULTISTREET_CFR_VERSION = "deepsix_f5_exact_hu_tabular_cfr_2026-08-26_v1"


class HuMultiStreetCFRError(ValueError):
    pass


class RegretMode(str, Enum):
    VANILLA = "vanilla_cfr"
    PLUS = "regret_matching_plus"


@dataclass
class _ExactNode:
    actions: tuple[MicroAction, ...]
    regrets: list[Fraction] = field(init=False)
    strategy_sum: list[Fraction] = field(init=False)

    def __post_init__(self) -> None:
        if len(self.actions) < 2:
            raise HuMultiStreetCFRError("CFR node requires at least two actions")
        if len(set(self.actions)) != len(self.actions):
            raise HuMultiStreetCFRError("CFR node actions must be unique")
        self.regrets = [Fraction(0, 1) for _ in self.actions]
        self.strategy_sum = [Fraction(0, 1) for _ in self.actions]

    def current_strategy(self) -> tuple[Fraction, ...]:
        positive = tuple(max(Fraction(0, 1), regret) for regret in self.regrets)
        total = sum(positive, Fraction(0, 1))
        if total > 0:
            return tuple(value / total for value in positive)
        probability = Fraction(1, len(self.actions))
        return (probability,) * len(self.actions)

    def average_strategy(self) -> tuple[Fraction, ...]:
        total = sum(self.strategy_sum, Fraction(0, 1))
        if total > 0:
            return tuple(value / total for value in self.strategy_sum)
        probability = Fraction(1, len(self.actions))
        return (probability,) * len(self.actions)


@dataclass
class _ExactIterationDelta:
    actions: tuple[MicroAction, ...]
    regrets: list[Fraction] = field(init=False)
    strategy: list[Fraction] = field(init=False)

    def __post_init__(self) -> None:
        self.regrets = [Fraction(0, 1) for _ in self.actions]
        self.strategy = [Fraction(0, 1) for _ in self.actions]


@dataclass(frozen=True)
class ExactPolicyRow:
    actions: tuple[MicroAction, ...]
    probabilities: tuple[Fraction, ...]

    def validate(self) -> None:
        if len(self.actions) < 1 or len(self.actions) != len(self.probabilities):
            raise HuMultiStreetCFRError("policy row action/probability mismatch")
        if len(set(self.actions)) != len(self.actions):
            raise HuMultiStreetCFRError("policy row contains duplicate action")
        if any(probability < 0 for probability in self.probabilities):
            raise HuMultiStreetCFRError("policy probability cannot be negative")
        if sum(self.probabilities, Fraction(0, 1)) != 1:
            raise HuMultiStreetCFRError("policy row probabilities must sum exactly to one")


class ExactTabularPolicy:
    """Exact rational policy callable compatible with `HuReferenceMicrogame.evaluate`."""

    def __init__(self, rows: Mapping[str, ExactPolicyRow]) -> None:
        self.rows = dict(rows)
        for key, row in self.rows.items():
            if not isinstance(key, str) or len(key) != 64:
                raise HuMultiStreetCFRError("policy infoset key must be SHA-256 hex")
            row.validate()

    def __call__(
        self,
        state: PrivateDecisionState,
        actions: tuple[MicroAction, ...],
    ) -> Mapping[MicroAction, Fraction]:
        key = state.fingerprint()
        row = self.rows.get(key)
        if row is None:
            probability = Fraction(1, len(actions))
            return {action: probability for action in actions}
        if row.actions != actions:
            raise HuMultiStreetCFRError("policy action support differs from infoset support")
        return dict(zip(row.actions, row.probabilities))

    def fingerprint(self) -> str:
        import hashlib
        import json

        payload = []
        for key in sorted(self.rows):
            row = self.rows[key]
            payload.append(
                {
                    "key": key,
                    "actions": [action.value for action in row.actions],
                    "probabilities": [
                        [probability.numerator, probability.denominator]
                        for probability in row.probabilities
                    ],
                }
            )
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class ExactHuMultiStreetCFR:
    """Full-tree exact synchronous CFR or regret-matching+ on the tiny F5 game."""

    def __init__(
        self,
        game: HuReferenceMicrogame,
        *,
        regret_mode: RegretMode = RegretMode.VANILLA,
    ) -> None:
        if not isinstance(game, HuReferenceMicrogame):
            raise HuMultiStreetCFRError("solver requires HuReferenceMicrogame")
        if not isinstance(regret_mode, RegretMode):
            raise HuMultiStreetCFRError("regret_mode must be RegretMode")
        self.game = game
        self.regret_mode = regret_mode
        self.nodes: dict[str, _ExactNode] = {}
        self.iterations = 0

    def _node(self, key: str, actions: tuple[MicroAction, ...]) -> _ExactNode:
        node = self.nodes.get(key)
        if node is None:
            node = _ExactNode(actions)
            self.nodes[key] = node
        elif node.actions != actions:
            raise HuMultiStreetCFRError("infoset action support changed")
        return node

    @staticmethod
    def _delta(
        deltas: dict[str, _ExactIterationDelta],
        key: str,
        actions: tuple[MicroAction, ...],
    ) -> _ExactIterationDelta:
        delta = deltas.get(key)
        if delta is None:
            delta = _ExactIterationDelta(actions)
            deltas[key] = delta
        elif delta.actions != actions:
            raise HuMultiStreetCFRError("iteration action support changed")
        return delta

    def _terminal_utility_p0(self, branch: ExactBranchState) -> Fraction:
        settlement = branch.settle()
        utility = utility_from_settlement(
            branch.state,
            settlement,
            stake_cents=branch.stake_cents,
            rules=branch.rules,
        )
        seats = tuple(sorted(seat for seat, _ in self.game.config.stacks))
        p0 = seats[0]
        row = utility.for_seat(p0)
        return row.gross_poker_delta_antes

    def _strategic_state(self, branch: ExactBranchState) -> PrivateDecisionState:
        actor = branch.actor_seat
        if actor is None:
            raise HuMultiStreetCFRError("decision branch has no actor")
        return decision_state_from_components(
            branch.state,
            actor_hole_cards=branch.hole_cards_mapping()[actor],
            stake_cents=branch.stake_cents,
            rules=branch.rules,
            bbj_enabled=branch.bbj_enabled,
        )

    def _traverse(
        self,
        branch: ExactBranchState,
        *,
        reach0: Fraction,
        reach1: Fraction,
        chance_reach: Fraction,
        deltas: dict[str, _ExactIterationDelta],
    ) -> Fraction:
        if branch.node_kind == BranchNodeKind.TERMINAL:
            return self._terminal_utility_p0(branch)

        if branch.node_kind == BranchNodeKind.CHANCE:
            value = Fraction(0, 1)
            for outcome in branch.chance_outcomes():
                value += outcome.probability * self._traverse(
                    branch.apply_chance(outcome.revealed),
                    reach0=reach0,
                    reach1=reach1,
                    chance_reach=chance_reach * outcome.probability,
                    deltas=deltas,
                )
            return value

        strategic = self._strategic_state(branch)
        key = strategic.fingerprint()
        actions = self.game.abstract_actions(branch)
        if len(actions) == 1:
            return self._traverse(
                self.game._apply_micro_action(branch, actions[0]),
                reach0=reach0,
                reach1=reach1,
                chance_reach=chance_reach,
                deltas=deltas,
            )
        node = self._node(key, actions)
        strategy = node.current_strategy()
        actor_position = strategic.public.actor_position
        # HU canonical positions are Dealer=0 and the other dealt seat=1.  Map
        # back to physical seat ordering used for zero-sum p0 sign/reach.
        physical_actor = branch.actor_seat
        seats = tuple(sorted(seat for seat, _ in self.game.config.stacks))
        if physical_actor not in seats:
            raise HuMultiStreetCFRError("actor is outside HU solver seats")
        player = seats.index(physical_actor)
        if actor_position not in (0, 1):
            raise HuMultiStreetCFRError("HU strategic actor position must be 0 or 1")

        action_values: list[Fraction] = []
        node_value = Fraction(0, 1)
        for index, action in enumerate(actions):
            child = self.game._apply_micro_action(branch, action)
            if player == 0:
                action_value = self._traverse(
                    child,
                    reach0=reach0 * strategy[index],
                    reach1=reach1,
                    chance_reach=chance_reach,
                    deltas=deltas,
                )
            else:
                action_value = self._traverse(
                    child,
                    reach0=reach0,
                    reach1=reach1 * strategy[index],
                    chance_reach=chance_reach,
                    deltas=deltas,
                )
            action_values.append(action_value)
            node_value += strategy[index] * action_value

        delta = self._delta(deltas, key, actions)
        if player == 0:
            counterfactual_reach = chance_reach * reach1
            average_reach = chance_reach * reach0
            for index in range(len(actions)):
                delta.regrets[index] += counterfactual_reach * (
                    action_values[index] - node_value
                )
                delta.strategy[index] += average_reach * strategy[index]
        else:
            counterfactual_reach = chance_reach * reach0
            average_reach = chance_reach * reach1
            for index in range(len(actions)):
                delta.regrets[index] += counterfactual_reach * (
                    node_value - action_values[index]
                )
                delta.strategy[index] += average_reach * strategy[index]
        return node_value

    def train(self, iterations: int) -> None:
        if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
            raise HuMultiStreetCFRError("iterations must be a positive integer")

        for _ in range(iterations):
            deltas: dict[str, _ExactIterationDelta] = {}
            for deal, root in self.game.root_branches():
                self._traverse(
                    root,
                    reach0=Fraction(1, 1),
                    reach1=Fraction(1, 1),
                    chance_reach=deal.probability,
                    deltas=deltas,
                )

            for key, delta in deltas.items():
                node = self.nodes[key]
                for index in range(len(node.actions)):
                    updated = node.regrets[index] + delta.regrets[index]
                    if self.regret_mode == RegretMode.PLUS:
                        updated = max(Fraction(0, 1), updated)
                    node.regrets[index] = updated
                    node.strategy_sum[index] += delta.strategy[index]
            self.iterations += 1

    def average_policy(self) -> ExactTabularPolicy:
        rows = {
            key: ExactPolicyRow(node.actions, node.average_strategy())
            for key, node in self.nodes.items()
        }
        return ExactTabularPolicy(rows)

    def current_policy(self) -> ExactTabularPolicy:
        rows = {
            key: ExactPolicyRow(node.actions, node.current_strategy())
            for key, node in self.nodes.items()
        }
        return ExactTabularPolicy(rows)

    def average_gross_value(self):
        return self.game.evaluate(
            self.average_policy(),
            objective_id=GROSS_POKER_DELTA,
        )

    def all_regrets_nonnegative(self) -> bool:
        return all(
            regret >= 0
            for node in self.nodes.values()
            for regret in node.regrets
        )

    def semantic_snapshot(self) -> tuple:
        """Stable exact state for determinism/split-training regression tests."""
        return (
            HU_MULTISTREET_CFR_VERSION,
            self.regret_mode.value,
            self.iterations,
            tuple(
                (
                    key,
                    tuple(node.actions),
                    tuple(node.regrets),
                    tuple(node.strategy_sum),
                )
                for key, node in sorted(self.nodes.items())
            ),
        )
