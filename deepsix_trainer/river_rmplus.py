"""Synchronous Regret-Matching+ laboratory for the exact river action game.

This module tests an algorithmic axis without changing cards, chance, actions or
utility.  It is deliberately named Regret-Matching+ (RM+) rather than claiming
bit-for-bit equivalence with every published CFR+ implementation.

Relative to the existing synchronous full-chance CFR trainer:

* cumulative regrets are clipped at zero after each full iteration;
* current strategy is regret matching over those non-negative regrets;
* average strategy can use linear iteration weights after an explicit delay;
* all chance deals in an iteration still see the same start-of-iteration
  strategy, preserving the project's deterministic synchronous semantics.

The trained policy is evaluated by the already-gated dynamic exact best response
of the unabstracted river game.  We do not gate on RM+ outperforming vanilla
CFR in every fixture; superiority is an empirical benchmark question.  Gates
cover correctness, determinism/resume and genuine convergence instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .river_multisize_one_raise import (
    History,
    MultiSizeOneRaiseDeal,
    PolicyKey,
    RiverMultiSizeOneRaiseConfig,
    RiverMultiSizeOneRaisePolicy,
    is_terminal,
    legal_actions,
    player_histories,
    player_to_act,
    terminal_utility_p0,
)
from .river_multisize_one_raise_dpbr import exploitability_dp


class RiverRMPlusError(ValueError):
    pass


@dataclass
class _PlusNode:
    action_count: int
    regret_plus: list[float] = field(init=False)
    strategy_sum: list[float] = field(init=False)

    def __post_init__(self) -> None:
        if self.action_count < 2:
            raise RiverRMPlusError("decision node requires at least two actions")
        self.regret_plus = [0.0] * self.action_count
        self.strategy_sum = [0.0] * self.action_count

    def current_strategy(self) -> tuple[float, ...]:
        total = sum(self.regret_plus)
        if total > 0.0:
            return tuple(value / total for value in self.regret_plus)
        probability = 1.0 / self.action_count
        return (probability,) * self.action_count

    def average_strategy(self) -> tuple[float, ...]:
        total = sum(self.strategy_sum)
        if total > 0.0:
            return tuple(value / total for value in self.strategy_sum)
        probability = 1.0 / self.action_count
        return (probability,) * self.action_count


@dataclass
class _IterationDelta:
    action_count: int
    regret: list[float] = field(init=False)
    strategy: list[float] = field(init=False)

    def __post_init__(self) -> None:
        self.regret = [0.0] * self.action_count
        self.strategy = [0.0] * self.action_count


class RiverRegretMatchingPlus:
    """Full-chance synchronous RM+ with optional delayed linear averaging."""

    def __init__(
        self,
        config: RiverMultiSizeOneRaiseConfig,
        *,
        averaging_delay: int = 0,
        linear_averaging: bool = True,
    ) -> None:
        config.validate()
        if (
            isinstance(averaging_delay, bool)
            or not isinstance(averaging_delay, int)
            or averaging_delay < 0
        ):
            raise RiverRMPlusError("averaging_delay must be a non-negative integer")
        if not isinstance(linear_averaging, bool):
            raise RiverRMPlusError("linear_averaging must be bool")
        self.config = config
        self.averaging_delay = averaging_delay
        self.linear_averaging = linear_averaging
        self.deals = config.compatible_deals()
        self.nodes: dict[PolicyKey, _PlusNode] = {}
        self.iterations = 0

    def _node(self, key: PolicyKey, action_count: int) -> _PlusNode:
        node = self.nodes.get(key)
        if node is None:
            node = _PlusNode(action_count)
            self.nodes[key] = node
        elif node.action_count != action_count:
            raise RiverRMPlusError("infoset action count changed")
        return node

    @staticmethod
    def _delta(
        deltas: dict[PolicyKey, _IterationDelta],
        key: PolicyKey,
        action_count: int,
    ) -> _IterationDelta:
        delta = deltas.get(key)
        if delta is None:
            delta = _IterationDelta(action_count)
            deltas[key] = delta
        elif delta.action_count != action_count:
            raise RiverRMPlusError("iteration delta action count changed")
        return delta

    def _traverse(
        self,
        deal: MultiSizeOneRaiseDeal,
        history: History,
        reach0: float,
        reach1: float,
        chance_reach: float,
        deltas: dict[PolicyKey, _IterationDelta],
    ) -> float:
        if is_terminal(self.config, history):
            return terminal_utility_p0(self.config, deal, history)

        player = player_to_act(self.config, history)
        cards = deal.p0_cards if player == 0 else deal.p1_cards
        key: PolicyKey = (player, tuple(sorted(cards)), history)
        actions = legal_actions(self.config, history)
        node = self._node(key, len(actions))
        strategy = node.current_strategy()

        action_values = [0.0] * len(actions)
        node_value = 0.0
        for index, action in enumerate(actions):
            next_history = history + (action,)
            if player == 0:
                value = self._traverse(
                    deal,
                    next_history,
                    reach0 * strategy[index],
                    reach1,
                    chance_reach,
                    deltas,
                )
            else:
                value = self._traverse(
                    deal,
                    next_history,
                    reach0,
                    reach1 * strategy[index],
                    chance_reach,
                    deltas,
                )
            action_values[index] = value
            node_value += strategy[index] * value

        delta = self._delta(deltas, key, len(actions))
        if player == 0:
            counterfactual_reach = chance_reach * reach1
            average_reach = chance_reach * reach0
            for index in range(len(actions)):
                delta.regret[index] += counterfactual_reach * (
                    action_values[index] - node_value
                )
                delta.strategy[index] += average_reach * strategy[index]
        else:
            counterfactual_reach = chance_reach * reach0
            average_reach = chance_reach * reach1
            for index in range(len(actions)):
                delta.regret[index] += counterfactual_reach * (
                    node_value - action_values[index]
                )
                delta.strategy[index] += average_reach * strategy[index]
        return node_value

    def _average_weight(self, iteration_number: int) -> float:
        after_delay = iteration_number - self.averaging_delay
        if after_delay <= 0:
            return 0.0
        return float(after_delay if self.linear_averaging else 1)

    def train(self, iterations: int) -> None:
        if (
            isinstance(iterations, bool)
            or not isinstance(iterations, int)
            or iterations <= 0
        ):
            raise RiverRMPlusError("iterations must be a positive integer")

        for _ in range(iterations):
            iteration_number = self.iterations + 1
            deltas: dict[PolicyKey, _IterationDelta] = {}
            for deal in self.deals:
                self._traverse(
                    deal,
                    (),
                    1.0,
                    1.0,
                    deal.probability,
                    deltas,
                )

            average_weight = self._average_weight(iteration_number)
            for key, delta in deltas.items():
                node = self.nodes[key]
                for index in range(node.action_count):
                    node.regret_plus[index] = max(
                        0.0,
                        node.regret_plus[index] + delta.regret[index],
                    )
                    if average_weight > 0.0:
                        node.strategy_sum[index] += (
                            average_weight * delta.strategy[index]
                        )
            self.iterations += 1

    def average_policy(self) -> RiverMultiSizeOneRaisePolicy:
        strategies: dict[PolicyKey, tuple[float, ...]] = {}
        for player, hands in ((0, self.config.p0_range), (1, self.config.p1_range)):
            for hand in hands:
                cards = hand.canonical_cards()
                for history in player_histories(self.config, player):
                    actions = legal_actions(self.config, history)
                    key: PolicyKey = (player, cards, history)
                    node = self.nodes.get(key)
                    if node is None:
                        probability = 1.0 / len(actions)
                        strategies[key] = (probability,) * len(actions)
                    else:
                        strategies[key] = node.average_strategy()
        return RiverMultiSizeOneRaisePolicy(strategies)

    def exact_exploitability(self) -> float:
        return exploitability_dp(self.config, self.average_policy())

    def all_regrets_nonnegative(self) -> bool:
        return all(
            regret >= 0.0
            for node in self.nodes.values()
            for regret in node.regret_plus
        )
