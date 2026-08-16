"""Auditable Short Deck river microgame for solver architecture experiments.

This is intentionally *not* the production cash-game abstraction. It is the
first solver bridge that uses the real 36-card evaluator while keeping the game
small enough to compute exact best responses.

Tree (single configurable bet size, no raises):

    P0: CHECK / BET
      CHECK -> P1: CHECK / BET
        CHECK -> showdown
        BET -> P0: FOLD / CALL
      BET -> P1: FOLD / CALL

Utilities are zero-sum from the point immediately before P0 acts on the river.
The existing pot is treated as sunk: a showdown without betting pays +/- pot/2,
a bet-fold pays +/- pot/2 to the bettor, and a called bet pays
+/-(pot/2 + bet). Ties have zero utility.

Ranges are finite sets of exact two-card Short Deck combos with positive
weights. Chance deals are the compatible ordered range pairs, normalized by
product weights. Showdown ordering is computed once and cached per immutable
configuration.

As in the Kuhn reference trainer, a CFR iteration is synchronous: every chance
branch is traversed under the strategy that existed at the start of the
iteration, then all regret/average-strategy deltas are committed together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from itertools import product
from math import isfinite
from typing import Mapping

from deepsix_core.cards import ShortDeckCardError, decode_card
from deepsix_core.evaluator import HandValue, evaluate_best


ACTIONS = ("passive", "aggressive")
TERMINALS = frozenset(("xx", "bf", "bc", "xbf", "xbc"))


class RiverMicrogameError(ValueError):
    pass


@dataclass(frozen=True)
class RangeHand:
    cards: tuple[int, int]
    weight: float = 1.0

    def canonical_cards(self) -> tuple[int, int]:
        if len(self.cards) != 2 or self.cards[0] == self.cards[1]:
            raise RiverMicrogameError("range hand must contain two distinct cards")
        try:
            decode_card(self.cards[0])
            decode_card(self.cards[1])
        except ShortDeckCardError as exc:
            raise RiverMicrogameError(str(exc)) from exc
        if not isfinite(self.weight) or self.weight <= 0.0:
            raise RiverMicrogameError("range weight must be finite and positive")
        return tuple(sorted(self.cards))


@dataclass(frozen=True)
class RiverDeal:
    p0_cards: tuple[int, int]
    p1_cards: tuple[int, int]
    probability: float
    showdown_sign: int


@dataclass(frozen=True)
class RiverMicrogameConfig:
    board: tuple[int, int, int, int, int]
    pot: int
    bet: int
    p0_range: tuple[RangeHand, ...]
    p1_range: tuple[RangeHand, ...]

    def validate(self) -> None:
        if len(self.board) != 5 or len(set(self.board)) != 5:
            raise RiverMicrogameError("river board must contain five distinct cards")
        try:
            for card in self.board:
                decode_card(card)
        except ShortDeckCardError as exc:
            raise RiverMicrogameError(str(exc)) from exc
        for name in ("pot", "bet"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise RiverMicrogameError(f"{name} must be a positive integer")
        if not self.p0_range or not self.p1_range:
            raise RiverMicrogameError("both player ranges must be non-empty")

        board_set = set(self.board)
        for label, range_hands in (("p0", self.p0_range), ("p1", self.p1_range)):
            seen: set[tuple[int, int]] = set()
            for hand in range_hands:
                cards = hand.canonical_cards()
                if set(cards) & board_set:
                    raise RiverMicrogameError(f"{label} range overlaps board")
                if cards in seen:
                    raise RiverMicrogameError(f"duplicate exact combo in {label} range")
                seen.add(cards)

        if not self.compatible_deals():
            raise RiverMicrogameError("ranges contain no compatible chance deal")

    @lru_cache(maxsize=None)
    def compatible_deals(self) -> tuple[RiverDeal, ...]:
        board_set = set(self.board)
        raw: list[tuple[tuple[int, int], tuple[int, int], float, int]] = []
        total_weight = 0.0
        for p0 in self.p0_range:
            p0_cards = p0.canonical_cards()
            if set(p0_cards) & board_set:
                continue
            for p1 in self.p1_range:
                p1_cards = p1.canonical_cards()
                if set(p1_cards) & board_set or set(p0_cards) & set(p1_cards):
                    continue
                weight = p0.weight * p1.weight
                p0_value: HandValue = evaluate_best(p0_cards + self.board)
                p1_value: HandValue = evaluate_best(p1_cards + self.board)
                sign = 1 if p0_value > p1_value else -1 if p0_value < p1_value else 0
                raw.append((p0_cards, p1_cards, weight, sign))
                total_weight += weight
        if not raw or total_weight <= 0.0:
            return ()
        return tuple(
            RiverDeal(p0_cards, p1_cards, weight / total_weight, sign)
            for p0_cards, p1_cards, weight, sign in raw
        )


@dataclass(frozen=True)
class RiverPolicy:
    """Behavioral policy over every range-hand/history infoset."""

    strategies: Mapping[tuple[int, tuple[int, int], str], tuple[float, float]]

    def strategy(
        self, player: int, cards: tuple[int, int], history: str
    ) -> tuple[float, float]:
        key = (player, tuple(sorted(cards)), history)
        try:
            strategy = self.strategies[key]
        except KeyError as exc:
            raise RiverMicrogameError(f"policy missing infoset {key}") from exc
        if len(strategy) != 2:
            raise RiverMicrogameError("strategy must contain two probabilities")
        if any((not isfinite(value)) or value < 0.0 for value in strategy):
            raise RiverMicrogameError("invalid strategy probability")
        if abs(strategy[0] + strategy[1] - 1.0) > 1e-9:
            raise RiverMicrogameError("strategy probabilities must sum to one")
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


def _player_to_act(history: str) -> int:
    if history == "":
        return 0
    if history in ("x", "b"):
        return 1
    if history == "xb":
        return 0
    if history in TERMINALS:
        raise RiverMicrogameError("terminal history has no actor")
    raise RiverMicrogameError(f"invalid history {history!r}")


def _actions_for_history(history: str) -> tuple[str, str]:
    if history in ("", "x"):
        return "x", "b"  # CHECK, BET
    if history in ("b", "xb"):
        return "f", "c"  # FOLD, CALL
    raise RiverMicrogameError(f"history has no legal actions: {history!r}")


def _terminal_utility_p0(
    config: RiverMicrogameConfig,
    deal: RiverDeal,
    history: str,
) -> float:
    half_pot = config.pot / 2.0
    if history == "bf":
        return half_pot
    if history == "xbf":
        return -half_pot
    if history == "xx":
        return deal.showdown_sign * half_pot
    if history in ("bc", "xbc"):
        return deal.showdown_sign * (half_pot + config.bet)
    raise RiverMicrogameError("history is not terminal")


class RiverCFR:
    """Synchronous full-chance vanilla CFR for a configured river microgame."""

    def __init__(self, config: RiverMicrogameConfig) -> None:
        config.validate()
        self.config = config
        self.deals = config.compatible_deals()
        self.nodes: dict[tuple[int, tuple[int, int], str], _Node] = {}
        self.iterations = 0

    def _node(self, player: int, cards: tuple[int, int], history: str) -> _Node:
        key = (player, tuple(sorted(cards)), history)
        if key not in self.nodes:
            self.nodes[key] = _Node()
        return self.nodes[key]

    @staticmethod
    def _delta(
        deltas: dict[tuple[int, tuple[int, int], str], _NodeDelta],
        key: tuple[int, tuple[int, int], str],
    ) -> _NodeDelta:
        if key not in deltas:
            deltas[key] = _NodeDelta()
        return deltas[key]

    def _cfr(
        self,
        deal: RiverDeal,
        history: str,
        reach0: float,
        reach1: float,
        chance_reach: float,
        deltas: dict[tuple[int, tuple[int, int], str], _NodeDelta],
    ) -> float:
        if history in TERMINALS:
            return _terminal_utility_p0(self.config, deal, history)

        player = _player_to_act(history)
        cards = deal.p0_cards if player == 0 else deal.p1_cards
        key = (player, tuple(sorted(cards)), history)
        node = self._node(player, cards, history)
        strategy = node.current_strategy()
        actions = _actions_for_history(history)

        action_values = [0.0, 0.0]
        node_value = 0.0
        for index, action in enumerate(actions):
            if player == 0:
                value = self._cfr(
                    deal,
                    history + action,
                    reach0 * strategy[index],
                    reach1,
                    chance_reach,
                    deltas,
                )
            else:
                value = self._cfr(
                    deal,
                    history + action,
                    reach0,
                    reach1 * strategy[index],
                    chance_reach,
                    deltas,
                )
            action_values[index] = value
            node_value += strategy[index] * value

        delta = self._delta(deltas, key)
        if player == 0:
            counterfactual_reach = chance_reach * reach1
            average_reach = chance_reach * reach0
            for index in range(2):
                delta.regret[index] += counterfactual_reach * (
                    action_values[index] - node_value
                )
                delta.strategy[index] += average_reach * strategy[index]
        else:
            counterfactual_reach = chance_reach * reach0
            average_reach = chance_reach * reach1
            for index in range(2):
                # P1 maximizes -u0.
                delta.regret[index] += counterfactual_reach * (
                    node_value - action_values[index]
                )
                delta.strategy[index] += average_reach * strategy[index]
        return node_value

    def train(self, iterations: int) -> None:
        if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
            raise RiverMicrogameError("iterations must be a positive integer")
        for _ in range(iterations):
            deltas: dict[tuple[int, tuple[int, int], str], _NodeDelta] = {}
            for deal in self.deals:
                self._cfr(
                    deal,
                    "",
                    1.0,
                    1.0,
                    deal.probability,
                    deltas,
                )
            for key, delta in deltas.items():
                node = self.nodes[key]
                for index in range(2):
                    node.regret_sum[index] += delta.regret[index]
                    node.strategy_sum[index] += delta.strategy[index]
            self.iterations += 1

    def average_policy(self) -> RiverPolicy:
        strategies: dict[
            tuple[int, tuple[int, int], str], tuple[float, float]
        ] = {}
        for player, range_hands, histories in (
            (0, self.config.p0_range, ("", "xb")),
            (1, self.config.p1_range, ("x", "b")),
        ):
            for range_hand in range_hands:
                cards = range_hand.canonical_cards()
                for history in histories:
                    node = self.nodes.get((player, cards, history))
                    strategies[(player, cards, history)] = (
                        node.average_strategy() if node else (0.5, 0.5)
                    )
        return RiverPolicy(strategies)


def _deal_value(
    config: RiverMicrogameConfig,
    policy0: RiverPolicy,
    policy1: RiverPolicy,
    deal: RiverDeal,
    history: str = "",
) -> float:
    if history in TERMINALS:
        return _terminal_utility_p0(config, deal, history)
    player = _player_to_act(history)
    policy = policy0 if player == 0 else policy1
    cards = deal.p0_cards if player == 0 else deal.p1_cards
    strategy = policy.strategy(player, cards, history)
    actions = _actions_for_history(history)
    return sum(
        strategy[index]
        * _deal_value(config, policy0, policy1, deal, history + action)
        for index, action in enumerate(actions)
    )


def expected_value(
    config: RiverMicrogameConfig,
    policy0: RiverPolicy,
    policy1: RiverPolicy,
) -> float:
    config.validate()
    return sum(
        deal.probability * _deal_value(config, policy0, policy1, deal)
        for deal in config.compatible_deals()
    )


def _pure_policy_for_player(
    config: RiverMicrogameConfig,
    player: int,
    bits: tuple[int, ...],
) -> RiverPolicy:
    if player == 0:
        own_range = config.p0_range
        own_histories = ("", "xb")
        other_range = config.p1_range
        other_histories = ("x", "b")
    elif player == 1:
        own_range = config.p1_range
        own_histories = ("x", "b")
        other_range = config.p0_range
        other_histories = ("", "xb")
    else:
        raise RiverMicrogameError("player must be 0 or 1")

    keys = [
        (player, hand.canonical_cards(), history)
        for hand in own_range
        for history in own_histories
    ]
    if len(bits) != len(keys):
        raise RiverMicrogameError("wrong pure-policy bit count")

    strategies: dict[
        tuple[int, tuple[int, int], str], tuple[float, float]
    ] = {}
    for key, bit in zip(keys, bits):
        strategies[key] = (1.0, 0.0) if bit == 0 else (0.0, 1.0)
    other_player = 1 - player
    for hand in other_range:
        cards = hand.canonical_cards()
        for history in other_histories:
            strategies[(other_player, cards, history)] = (0.5, 0.5)
    return RiverPolicy(strategies)


def best_response_value_player0(
    config: RiverMicrogameConfig,
    opponent: RiverPolicy,
) -> float:
    infosets = 2 * len(config.p0_range)
    if infosets > 16:
        raise RiverMicrogameError(
            "exact pure best response intentionally capped at 16 binary infosets"
        )
    best = float("-inf")
    for bits in product((0, 1), repeat=infosets):
        best = max(
            best,
            expected_value(config, _pure_policy_for_player(config, 0, bits), opponent),
        )
    return best


def best_response_value_player1(
    config: RiverMicrogameConfig,
    opponent: RiverPolicy,
) -> float:
    """Minimum P0 utility achievable by an exact pure best response from P1."""
    infosets = 2 * len(config.p1_range)
    if infosets > 16:
        raise RiverMicrogameError(
            "exact pure best response intentionally capped at 16 binary infosets"
        )
    best_for_p1 = float("inf")
    for bits in product((0, 1), repeat=infosets):
        best_for_p1 = min(
            best_for_p1,
            expected_value(config, opponent, _pure_policy_for_player(config, 1, bits)),
        )
    return best_for_p1


def exploitability(config: RiverMicrogameConfig, policy: RiverPolicy) -> float:
    """Exact half-NashConv for small ranges, in configured chip units/hand."""
    br0 = best_response_value_player0(config, policy)
    br1_as_p0 = best_response_value_player1(config, policy)
    return (br0 - br1_as_p0) / 2.0
