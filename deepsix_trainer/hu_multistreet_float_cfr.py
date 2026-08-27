"""Float64 synchronous CFR/RM+ validation candidate for DeepSix F5.

The exact rational solver in ``hu_multistreet_cfr`` remains the mathematical
oracle.  This module mirrors the same traversal, infoset identity, action
support and synchronous update schedule using binary64 arithmetic so we can
measure the numerical/performance trade-off before committing to a production
trainer implementation.

This is intentionally still a full-tree solver: chance and private deals are
fully enumerated.  Sampling is a separate axis and must be validated against
both the exact rational oracle and this deterministic float baseline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import math
from typing import Mapping

from deepsix_simulator.utility import utility_from_settlement

from .hu_multistreet_cfr import (
    ExactPolicyRow,
    ExactTabularPolicy,
    HuMultiStreetCFRError,
    RegretMode,
)
from .hu_multistreet_reference import (
    GROSS_POKER_DELTA,
    HuReferenceMicrogame,
    MicroAction,
)
from .multistreet_branch import BranchNodeKind, ExactBranchState
from .multistreet_state import PrivateDecisionState, decision_state_from_components


HU_MULTISTREET_FLOAT_CFR_VERSION = (
    "deepsix_f5_float64_hu_tabular_cfr_2026-08-27_v1"
)
_FLOAT_PROBABILITY_TOLERANCE = 1e-12


@dataclass
class _FloatNode:
    actions: tuple[MicroAction, ...]
    regrets: list[float] = field(init=False)
    strategy_sum: list[float] = field(init=False)

    def __post_init__(self) -> None:
        if len(self.actions) < 2:
            raise HuMultiStreetCFRError("CFR node requires at least two actions")
        if len(set(self.actions)) != len(self.actions):
            raise HuMultiStreetCFRError("CFR node actions must be unique")
        self.regrets = [0.0 for _ in self.actions]
        self.strategy_sum = [0.0 for _ in self.actions]

    def current_strategy(self) -> tuple[float, ...]:
        positive = tuple(max(0.0, regret) for regret in self.regrets)
        total = math.fsum(positive)
        if total > 0.0:
            return tuple(value / total for value in positive)
        probability = 1.0 / len(self.actions)
        return (probability,) * len(self.actions)

    def average_strategy(self) -> tuple[float, ...]:
        total = math.fsum(self.strategy_sum)
        if total > 0.0:
            return tuple(value / total for value in self.strategy_sum)
        probability = 1.0 / len(self.actions)
        return (probability,) * len(self.actions)


@dataclass
class _FloatIterationDelta:
    actions: tuple[MicroAction, ...]
    regrets: list[float] = field(init=False)
    strategy: list[float] = field(init=False)

    def __post_init__(self) -> None:
        self.regrets = [0.0 for _ in self.actions]
        self.strategy = [0.0 for _ in self.actions]


@dataclass(frozen=True)
class FloatPolicyRow:
    actions: tuple[MicroAction, ...]
    probabilities: tuple[float, ...]

    def validate(self) -> None:
        if len(self.actions) < 1 or len(self.actions) != len(self.probabilities):
            raise HuMultiStreetCFRError("policy row action/probability mismatch")
        if len(set(self.actions)) != len(self.actions):
            raise HuMultiStreetCFRError("policy row contains duplicate action")
        if any(not math.isfinite(value) or value < 0.0 for value in self.probabilities):
            raise HuMultiStreetCFRError("float policy probabilities must be finite/nonnegative")
        if abs(math.fsum(self.probabilities) - 1.0) > _FLOAT_PROBABILITY_TOLERANCE:
            raise HuMultiStreetCFRError("float policy probabilities must sum to one")


class FloatTabularPolicy:
    """Deterministic binary64 policy with an exact-evaluation adapter."""

    def __init__(self, rows: Mapping[str, FloatPolicyRow]) -> None:
        self.rows = dict(rows)
        for key, row in self.rows.items():
            if not isinstance(key, str) or len(key) != 64:
                raise HuMultiStreetCFRError("policy infoset key must be SHA-256 hex")
            row.validate()

    def __call__(
        self,
        state: PrivateDecisionState,
        actions: tuple[MicroAction, ...],
    ) -> Mapping[MicroAction, float]:
        key = state.fingerprint()
        row = self.rows.get(key)
        if row is None:
            probability = 1.0 / len(actions)
            return {action: probability for action in actions}
        if row.actions != actions:
            raise HuMultiStreetCFRError("policy action support differs from infoset support")
        return dict(zip(row.actions, row.probabilities))

    def fingerprint(self) -> str:
        """Hash exact binary64 values rather than formatter-dependent decimals."""
        payload = []
        for key in sorted(self.rows):
            row = self.rows[key]
            payload.append(
                {
                    "key": key,
                    "actions": [action.value for action in row.actions],
                    "probabilities_hex": [value.hex() for value in row.probabilities],
                }
            )
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def to_exact_policy(self) -> ExactTabularPolicy:
        """Convert binary64 probabilities to exact normalized rational weights.

        ``Fraction.from_float`` captures the exact binary64 value.  The rows are
        then renormalized in rational arithmetic so the strict reference-game
        evaluator sees a probability mass of exactly one.  This is an audit
        adapter, not a claim that the float policy itself was trained exactly.
        """
        rows: dict[str, ExactPolicyRow] = {}
        for key, row in self.rows.items():
            exact = tuple(Fraction.from_float(value) for value in row.probabilities)
            total = sum(exact, Fraction(0, 1))
            if total <= 0:
                raise HuMultiStreetCFRError("cannot exact-normalize empty float policy mass")
            normalized = tuple(value / total for value in exact)
            rows[key] = ExactPolicyRow(row.actions, normalized)
        return ExactTabularPolicy(rows)


class FloatHuMultiStreetCFR:
    """Full-tree synchronous binary64 CFR or RM+ on the exact F5 microgame."""

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
        self.nodes: dict[str, _FloatNode] = {}
        self.iterations = 0
        self._seats = tuple(sorted(seat for seat, _ in game.config.stacks))

    def _node(self, key: str, actions: tuple[MicroAction, ...]) -> _FloatNode:
        node = self.nodes.get(key)
        if node is None:
            node = _FloatNode(actions)
            self.nodes[key] = node
        elif node.actions != actions:
            raise HuMultiStreetCFRError("infoset action support changed")
        return node

    @staticmethod
    def _delta(
        deltas: dict[str, _FloatIterationDelta],
        key: str,
        actions: tuple[MicroAction, ...],
    ) -> _FloatIterationDelta:
        delta = deltas.get(key)
        if delta is None:
            delta = _FloatIterationDelta(actions)
            deltas[key] = delta
        elif delta.actions != actions:
            raise HuMultiStreetCFRError("iteration action support changed")
        return delta

    def _terminal_utility_p0(self, branch: ExactBranchState) -> float:
        settlement = branch.settle()
        utility = utility_from_settlement(
            branch.state,
            settlement,
            stake_cents=branch.stake_cents,
            rules=branch.rules,
        )
        p0 = self._seats[0]
        return float(utility.for_seat(p0).gross_poker_delta_antes)

    @staticmethod
    def _strategic_state(branch: ExactBranchState) -> PrivateDecisionState:
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
        reach0: float,
        reach1: float,
        chance_reach: float,
        deltas: dict[str, _FloatIterationDelta],
    ) -> float:
        if branch.node_kind == BranchNodeKind.TERMINAL:
            return self._terminal_utility_p0(branch)

        if branch.node_kind == BranchNodeKind.CHANCE:
            terms: list[float] = []
            for outcome in branch.chance_outcomes():
                probability = float(outcome.probability)
                terms.append(
                    probability
                    * self._traverse(
                        branch.apply_chance(outcome.revealed),
                        reach0=reach0,
                        reach1=reach1,
                        chance_reach=chance_reach * probability,
                        deltas=deltas,
                    )
                )
            return math.fsum(terms)

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
        physical_actor = branch.actor_seat
        if physical_actor not in self._seats:
            raise HuMultiStreetCFRError("actor is outside HU solver seats")
        player = self._seats.index(physical_actor)
        if strategic.public.actor_position not in (0, 1):
            raise HuMultiStreetCFRError("HU strategic actor position must be 0 or 1")

        action_values: list[float] = []
        weighted_values: list[float] = []
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
            weighted_values.append(strategy[index] * action_value)
        node_value = math.fsum(weighted_values)

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
            deltas: dict[str, _FloatIterationDelta] = {}
            for deal, root in self.game.root_branches():
                self._traverse(
                    root,
                    reach0=1.0,
                    reach1=1.0,
                    chance_reach=float(deal.probability),
                    deltas=deltas,
                )

            for key, delta in deltas.items():
                node = self.nodes[key]
                for index in range(len(node.actions)):
                    updated = node.regrets[index] + delta.regrets[index]
                    if self.regret_mode == RegretMode.PLUS:
                        updated = max(0.0, updated)
                    if not math.isfinite(updated):
                        raise HuMultiStreetCFRError("non-finite cumulative regret")
                    strategy_sum = node.strategy_sum[index] + delta.strategy[index]
                    if not math.isfinite(strategy_sum):
                        raise HuMultiStreetCFRError("non-finite cumulative strategy mass")
                    node.regrets[index] = updated
                    node.strategy_sum[index] = strategy_sum
            self.iterations += 1

    def average_policy(self) -> FloatTabularPolicy:
        return FloatTabularPolicy(
            {
                key: FloatPolicyRow(node.actions, node.average_strategy())
                for key, node in self.nodes.items()
            }
        )

    def current_policy(self) -> FloatTabularPolicy:
        return FloatTabularPolicy(
            {
                key: FloatPolicyRow(node.actions, node.current_strategy())
                for key, node in self.nodes.items()
            }
        )

    def average_gross_value_exact_adapter(self):
        """Evaluate the float policy through the strict rational game oracle."""
        return self.game.evaluate(
            self.average_policy().to_exact_policy(),
            objective_id=GROSS_POKER_DELTA,
        )

    def all_regrets_nonnegative(self) -> bool:
        return all(
            regret >= 0.0
            for node in self.nodes.values()
            for regret in node.regrets
        )

    def semantic_snapshot(self) -> tuple:
        """Deterministic binary64 state using hexadecimal float encodings."""
        return (
            HU_MULTISTREET_FLOAT_CFR_VERSION,
            self.regret_mode.value,
            self.iterations,
            tuple(
                (
                    key,
                    tuple(node.actions),
                    tuple(value.hex() for value in node.regrets),
                    tuple(value.hex() for value in node.strategy_sum),
                )
                for key, node in sorted(self.nodes.items())
            ),
        )


def exact_float_max_errors(
    exact_solver,
    float_solver: FloatHuMultiStreetCFR,
) -> dict[str, float]:
    """Compare one aligned exact/float solver state without hiding drift."""
    if exact_solver.iterations != float_solver.iterations:
        raise HuMultiStreetCFRError("exact/float iteration counts differ")
    if set(exact_solver.nodes) != set(float_solver.nodes):
        raise HuMultiStreetCFRError("exact/float infoset supports differ")

    regret_errors: list[float] = []
    strategy_errors: list[float] = []
    policy_errors: list[float] = []
    exact_policy = exact_solver.average_policy()
    float_policy = float_solver.average_policy()
    for key in sorted(exact_solver.nodes):
        exact_node = exact_solver.nodes[key]
        float_node = float_solver.nodes[key]
        if exact_node.actions != float_node.actions:
            raise HuMultiStreetCFRError("exact/float action supports differ")
        regret_errors.extend(
            abs(float(left) - right)
            for left, right in zip(exact_node.regrets, float_node.regrets)
        )
        strategy_errors.extend(
            abs(float(left) - right)
            for left, right in zip(exact_node.strategy_sum, float_node.strategy_sum)
        )
        exact_row = exact_policy.rows[key]
        float_row = float_policy.rows[key]
        policy_errors.extend(
            abs(float(left) - right)
            for left, right in zip(exact_row.probabilities, float_row.probabilities)
        )
    return {
        "max_regret_abs_error": max(regret_errors, default=0.0),
        "max_strategy_sum_abs_error": max(strategy_errors, default=0.0),
        "max_average_policy_abs_error": max(policy_errors, default=0.0),
    }
