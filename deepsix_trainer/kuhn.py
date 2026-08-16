"""Tiny exact CFR baseline using Kuhn poker.

Kuhn is deliberately not a Short Deck strategy model. It is a trainer
correctness fixture: imperfect information, chance, bluffing, mixed strategy,
and exact best-response exploitability all fit in a few auditable states.

Action alphabet:

* ``p`` = pass/check when no bet is faced, fold when facing a bet;
* ``b`` = bet when no bet is faced, call when facing a bet.

Cards are J=0, Q=1, K=2. Utilities are net chips for player 0 after both
players ante one chip, so the equilibrium value is -1/18 for player 0.

One CFR iteration is synchronous across all six chance deals: every branch is
traversed under the strategy that existed at the start of that iteration, then
all regret/average-strategy deltas are committed together. This makes the tiny
baseline a clean reference for larger DeepSix trainers rather than silently
turning chance branches into sequential micro-iterations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations, product
from math import isfinite
from typing import Mapping


ACTIONS = ("p", "b")
CARDS = (0, 1, 2)
DEALS = tuple(permutations(CARDS, 2))
TERMINALS = frozenset(("pp", "bp", "bb", "pbp", "pbb"))


class KuhnError(ValueError):
    pass


def _terminal_utility_p0(cards: tuple[int, int], history: str) -> float:
    if history not in TERMINALS:
        raise KuhnError("history is not terminal")
    p0_wins_showdown = cards[0] > cards[1]
    if history == "pp":
        return 1.0 if p0_wins_showdown else -1.0
    if history == "bp":
        return 1.0
    if history == "pbp":
        return -1.0
    if history in ("bb", "pbb"):
        return 2.0 if p0_wins_showdown else -2.0
    raise AssertionError("unreachable terminal history")


def _player_to_act(history: str) -> int:
    if history in TERMINALS:
        raise KuhnError("terminal history has no actor")
    if history == "":
        return 0
    if history in ("p", "b"):
        return 1
    if history == "pb":
        return 0
    raise KuhnError(f"invalid nonterminal history {history!r}")


def _infoset(card: int, history: str) -> tuple[int, str]:
    if card not in CARDS:
        raise KuhnError("invalid Kuhn card")
    _player_to_act(history)
    return card, history


@dataclass(frozen=True)
class KuhnPolicy:
    """Behavioral policy: probability of ``p``/``b`` at each infoset."""

    strategies: Mapping[tuple[int, str], tuple[float, float]]

    def strategy(self, card: int, history: str) -> tuple[float, float]:
        key = _infoset(card, history)
        try:
            strategy = self.strategies[key]
        except KeyError as exc:
            raise KuhnError(f"policy missing infoset {key}") from exc
        if len(strategy) != 2:
            raise KuhnError("strategy must contain exactly two probabilities")
        if any((not isfinite(value)) or value < 0.0 for value in strategy):
            raise KuhnError("invalid strategy probability")
        total = strategy[0] + strategy[1]
        if abs(total - 1.0) > 1e-9:
            raise KuhnError("strategy probabilities must sum to one")
        return strategy


@dataclass
class _Node:
    regret_sum: list[float] = field(default_factory=lambda: [0.0, 0.0])
    strategy_sum: list[float] = field(default_factory=lambda: [0.0, 0.0])

    def current_strategy(self) -> tuple[float, float]:
        positive = [max(value, 0.0) for value in self.regret_sum]
        normalizer = positive[0] + positive[1]
        if normalizer > 0.0:
            return positive[0] / normalizer, positive[1] / normalizer
        return 0.5, 0.5

    def average_strategy(self) -> tuple[float, float]:
        normalizer = self.strategy_sum[0] + self.strategy_sum[1]
        if normalizer > 0.0:
            return (
                self.strategy_sum[0] / normalizer,
                self.strategy_sum[1] / normalizer,
            )
        return 0.5, 0.5


@dataclass
class _NodeDelta:
    regret: list[float] = field(default_factory=lambda: [0.0, 0.0])
    strategy: list[float] = field(default_factory=lambda: [0.0, 0.0])


class KuhnCFR:
    """Synchronous full-chance vanilla CFR with deterministic deal order."""

    def __init__(self) -> None:
        self.nodes: dict[tuple[int, str], _Node] = {}
        self.iterations = 0

    def _node(self, card: int, history: str) -> _Node:
        key = _infoset(card, history)
        if key not in self.nodes:
            self.nodes[key] = _Node()
        return self.nodes[key]

    @staticmethod
    def _delta(
        deltas: dict[tuple[int, str], _NodeDelta], key: tuple[int, str]
    ) -> _NodeDelta:
        if key not in deltas:
            deltas[key] = _NodeDelta()
        return deltas[key]

    def _cfr(
        self,
        cards: tuple[int, int],
        history: str,
        reach0: float,
        reach1: float,
        chance_reach: float,
        deltas: dict[tuple[int, str], _NodeDelta],
    ) -> float:
        """Return P0 utility and accumulate, but do not yet apply, CFR deltas."""
        if history in TERMINALS:
            return _terminal_utility_p0(cards, history)

        player = _player_to_act(history)
        card = cards[player]
        key = _infoset(card, history)
        node = self._node(card, history)
        strategy = node.current_strategy()

        action_values = [0.0, 0.0]
        node_value = 0.0
        for action_index, action in enumerate(ACTIONS):
            if player == 0:
                value = self._cfr(
                    cards,
                    history + action,
                    reach0 * strategy[action_index],
                    reach1,
                    chance_reach,
                    deltas,
                )
            else:
                value = self._cfr(
                    cards,
                    history + action,
                    reach0,
                    reach1 * strategy[action_index],
                    chance_reach,
                    deltas,
                )
            action_values[action_index] = value
            node_value += strategy[action_index] * value

        delta = self._delta(deltas, key)
        if player == 0:
            counterfactual_reach = chance_reach * reach1
            average_reach = chance_reach * reach0
            for action_index in range(2):
                delta.regret[action_index] += counterfactual_reach * (
                    action_values[action_index] - node_value
                )
                delta.strategy[action_index] += average_reach * strategy[action_index]
        else:
            counterfactual_reach = chance_reach * reach0
            average_reach = chance_reach * reach1
            for action_index in range(2):
                # Player 1 maximizes -u0.
                delta.regret[action_index] += counterfactual_reach * (
                    node_value - action_values[action_index]
                )
                delta.strategy[action_index] += average_reach * strategy[action_index]
        return node_value

    def train(self, iterations: int) -> None:
        if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
            raise KuhnError("iterations must be a positive integer")
        chance_weight = 1.0 / len(DEALS)
        for _ in range(iterations):
            deltas: dict[tuple[int, str], _NodeDelta] = {}
            for cards in DEALS:
                self._cfr(cards, "", 1.0, 1.0, chance_weight, deltas)
            for key, delta in deltas.items():
                node = self.nodes[key]
                for action_index in range(2):
                    node.regret_sum[action_index] += delta.regret[action_index]
                    node.strategy_sum[action_index] += delta.strategy[action_index]
            self.iterations += 1

    def average_policy(self) -> KuhnPolicy:
        strategies: dict[tuple[int, str], tuple[float, float]] = {}
        for card in CARDS:
            for history in ("", "pb", "p", "b"):
                key = (card, history)
                node = self.nodes.get(key)
                strategies[key] = node.average_strategy() if node else (0.5, 0.5)
        return KuhnPolicy(strategies)


def _deal_value(
    policy0: KuhnPolicy,
    policy1: KuhnPolicy,
    cards: tuple[int, int],
    history: str = "",
) -> float:
    if history in TERMINALS:
        return _terminal_utility_p0(cards, history)
    player = _player_to_act(history)
    policy = policy0 if player == 0 else policy1
    strategy = policy.strategy(cards[player], history)
    return sum(
        strategy[index]
        * _deal_value(policy0, policy1, cards, history + action)
        for index, action in enumerate(ACTIONS)
    )


def expected_value(policy0: KuhnPolicy, policy1: KuhnPolicy) -> float:
    """Exact expected net utility for player 0 over all six chance deals."""
    return sum(_deal_value(policy0, policy1, cards) for cards in DEALS) / len(DEALS)


def _pure_policy_for_player(player: int, bits: tuple[int, ...]) -> KuhnPolicy:
    if player not in (0, 1):
        raise KuhnError("player must be 0 or 1")
    histories = ("", "pb") if player == 0 else ("p", "b")
    keys = [(card, history) for card in CARDS for history in histories]
    if len(bits) != len(keys):
        raise KuhnError("wrong pure-strategy bit count")
    strategies: dict[tuple[int, str], tuple[float, float]] = {}
    for key, action_index in zip(keys, bits):
        strategies[key] = (1.0, 0.0) if action_index == 0 else (0.0, 1.0)
    other_histories = ("p", "b") if player == 0 else ("", "pb")
    for card in CARDS:
        for history in other_histories:
            strategies[(card, history)] = (0.5, 0.5)
    return KuhnPolicy(strategies)


def best_response_value_player0(opponent: KuhnPolicy) -> float:
    best = float("-inf")
    for bits in product((0, 1), repeat=6):
        best = max(best, expected_value(_pure_policy_for_player(0, bits), opponent))
    return best


def best_response_value_player1(opponent: KuhnPolicy) -> float:
    """Minimum player-0 utility achievable by an exact pure best response P1."""
    best_for_player1 = float("inf")
    for bits in product((0, 1), repeat=6):
        best_for_player1 = min(
            best_for_player1,
            expected_value(opponent, _pure_policy_for_player(1, bits)),
        )
    return best_for_player1


def exploitability(policy: KuhnPolicy) -> float:
    """Exact two-player zero-sum exploitability of a shared average policy.

    Returns half of NashConv: ``(BR0 - BR1) / 2`` in chips/hand.
    """
    br0 = best_response_value_player0(policy)
    br1_as_p0_value = best_response_value_player1(policy)
    return (br0 - br1_as_p0_value) / 2.0
