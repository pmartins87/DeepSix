"""Private-state abstraction laboratory for the gated river action game.

Action abstraction and private-state abstraction are deliberately separated.
This module keeps the exact same Short Deck river chance model, terminal
utilities and action tree from ``river_multisize_one_raise`` while allowing
multiple exact hole-card combos to share one CFR infoset bucket.

The key validation pattern is:

    abstracted CFR policy
      -> expand bucket strategy back to every exact private hand
      -> evaluate with the *unabstracted* dynamic exact best response

Therefore a coarse bucket policy cannot hide behind an abstract-game best
response.  Any strategic information lost by bucketing is visible as
exploitability in the original exact private-hand game.

This is a laboratory for measuring abstraction error, not a production bucket
scheme.  Three deterministic builders are supplied:

* identity: one bucket per exact combo (zero intentional abstraction);
* showdown category: merge hands with the same final HandCategory;
* conditional-equity quantiles: sort each player's exact hands by blocker-aware
  river showdown equity versus the configured opponent range, then partition
  them into N deterministic quantile buckets.

The equity builder uses only terminal showdown information.  It is intentionally
simple so that later neural/feature abstractions can be judged against a clear
baseline rather than against an opaque heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Hashable, Mapping

from deepsix_core.evaluator import evaluate_best
from .river_multisize_one_raise import (
    History,
    MultiSizeOneRaiseDeal,
    PolicyKey,
    RiverMultiSizeOneRaiseConfig,
    RiverMultiSizeOneRaiseError,
    RiverMultiSizeOneRaisePolicy,
    is_terminal,
    legal_actions,
    player_histories,
    player_to_act,
    terminal_utility_p0,
)
from .river_multisize_one_raise_dpbr import exploitability_dp


Bucket = Hashable
BucketKey = tuple[int, Bucket, History]
ConcreteHandKey = tuple[int, tuple[int, int]]


class RiverStateAbstractionError(ValueError):
    pass


@dataclass(frozen=True)
class RiverBucketMap:
    """Player-specific mapping from exact private combo to abstract bucket."""

    buckets: Mapping[ConcreteHandKey, Bucket]
    name: str = "custom"

    def validate(self, config: RiverMultiSizeOneRaiseConfig) -> None:
        config.validate()
        expected: set[ConcreteHandKey] = set()
        for player, hands in ((0, config.p0_range), (1, config.p1_range)):
            for hand in hands:
                expected.add((player, hand.canonical_cards()))
        actual = set(self.buckets)
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            raise RiverStateAbstractionError(
                f"bucket map key mismatch: missing={len(missing)} extra={len(extra)}"
            )
        for key, bucket in self.buckets.items():
            try:
                hash(bucket)
            except TypeError as exc:
                raise RiverStateAbstractionError(
                    f"bucket for {key} is not hashable"
                ) from exc

    def bucket_for(self, player: int, cards: tuple[int, int]) -> Bucket:
        key = (player, tuple(sorted(cards)))
        try:
            return self.buckets[key]
        except KeyError as exc:
            raise RiverStateAbstractionError(f"bucket missing exact hand {key}") from exc

    def bucket_count(self, player: int) -> int:
        if player not in (0, 1):
            raise RiverStateAbstractionError("player must be 0 or 1")
        return len(
            {
                bucket
                for (mapped_player, _), bucket in self.buckets.items()
                if mapped_player == player
            }
        )


@dataclass
class _Node:
    action_count: int
    regret_sum: list[float] = field(init=False)
    strategy_sum: list[float] = field(init=False)

    def __post_init__(self) -> None:
        if self.action_count < 2:
            raise RiverStateAbstractionError(
                "abstract decision node requires at least two actions"
            )
        self.regret_sum = [0.0] * self.action_count
        self.strategy_sum = [0.0] * self.action_count

    def current_strategy(self) -> tuple[float, ...]:
        positive = [max(value, 0.0) for value in self.regret_sum]
        total = sum(positive)
        if total > 0.0:
            return tuple(value / total for value in positive)
        p = 1.0 / self.action_count
        return (p,) * self.action_count

    def average_strategy(self) -> tuple[float, ...]:
        total = sum(self.strategy_sum)
        if total > 0.0:
            return tuple(value / total for value in self.strategy_sum)
        p = 1.0 / self.action_count
        return (p,) * self.action_count


@dataclass
class _NodeDelta:
    action_count: int
    regret: list[float] = field(init=False)
    strategy: list[float] = field(init=False)

    def __post_init__(self) -> None:
        self.regret = [0.0] * self.action_count
        self.strategy = [0.0] * self.action_count


class BucketedRiverCFR:
    """Synchronous full-chance CFR over shared private-state buckets."""

    def __init__(
        self,
        config: RiverMultiSizeOneRaiseConfig,
        bucket_map: RiverBucketMap,
    ) -> None:
        config.validate()
        bucket_map.validate(config)
        self.config = config
        self.bucket_map = bucket_map
        self.deals = config.compatible_deals()
        self.nodes: dict[BucketKey, _Node] = {}
        self.iterations = 0

    def _node(self, key: BucketKey, action_count: int) -> _Node:
        node = self.nodes.get(key)
        if node is None:
            node = _Node(action_count)
            self.nodes[key] = node
        elif node.action_count != action_count:
            raise RiverStateAbstractionError(
                "abstract infoset action count changed"
            )
        return node

    @staticmethod
    def _delta(
        deltas: dict[BucketKey, _NodeDelta],
        key: BucketKey,
        action_count: int,
    ) -> _NodeDelta:
        delta = deltas.get(key)
        if delta is None:
            delta = _NodeDelta(action_count)
            deltas[key] = delta
        elif delta.action_count != action_count:
            raise RiverStateAbstractionError(
                "abstract delta action count changed"
            )
        return delta

    def _cfr(
        self,
        deal: MultiSizeOneRaiseDeal,
        history: History,
        reach0: float,
        reach1: float,
        chance_reach: float,
        deltas: dict[BucketKey, _NodeDelta],
    ) -> float:
        if is_terminal(self.config, history):
            return terminal_utility_p0(self.config, deal, history)

        player = player_to_act(self.config, history)
        cards = deal.p0_cards if player == 0 else deal.p1_cards
        bucket = self.bucket_map.bucket_for(player, cards)
        key: BucketKey = (player, bucket, history)
        actions = legal_actions(self.config, history)
        node = self._node(key, len(actions))
        strategy = node.current_strategy()

        values = [0.0] * len(actions)
        node_value = 0.0
        for index, action in enumerate(actions):
            next_history = history + (action,)
            if player == 0:
                value = self._cfr(
                    deal,
                    next_history,
                    reach0 * strategy[index],
                    reach1,
                    chance_reach,
                    deltas,
                )
            else:
                value = self._cfr(
                    deal,
                    next_history,
                    reach0,
                    reach1 * strategy[index],
                    chance_reach,
                    deltas,
                )
            values[index] = value
            node_value += strategy[index] * value

        delta = self._delta(deltas, key, len(actions))
        if player == 0:
            counterfactual = chance_reach * reach1
            average_reach = chance_reach * reach0
            for index in range(len(actions)):
                delta.regret[index] += counterfactual * (values[index] - node_value)
                delta.strategy[index] += average_reach * strategy[index]
        else:
            counterfactual = chance_reach * reach0
            average_reach = chance_reach * reach1
            for index in range(len(actions)):
                delta.regret[index] += counterfactual * (node_value - values[index])
                delta.strategy[index] += average_reach * strategy[index]
        return node_value

    def train(self, iterations: int) -> None:
        if (
            isinstance(iterations, bool)
            or not isinstance(iterations, int)
            or iterations <= 0
        ):
            raise RiverStateAbstractionError(
                "iterations must be a positive integer"
            )
        for _ in range(iterations):
            deltas: dict[BucketKey, _NodeDelta] = {}
            for deal in self.deals:
                self._cfr(deal, (), 1.0, 1.0, deal.probability, deltas)
            for key, delta in deltas.items():
                node = self.nodes[key]
                for index in range(node.action_count):
                    node.regret_sum[index] += delta.regret[index]
                    node.strategy_sum[index] += delta.strategy[index]
            self.iterations += 1

    def concrete_average_policy(self) -> RiverMultiSizeOneRaisePolicy:
        """Expand shared bucket strategies back to every exact private combo."""
        strategies: dict[PolicyKey, tuple[float, ...]] = {}
        for player, hands in ((0, self.config.p0_range), (1, self.config.p1_range)):
            for hand in hands:
                cards = hand.canonical_cards()
                bucket = self.bucket_map.bucket_for(player, cards)
                for history in player_histories(self.config, player):
                    actions = legal_actions(self.config, history)
                    node = self.nodes.get((player, bucket, history))
                    if node is None:
                        p = 1.0 / len(actions)
                        strategy = (p,) * len(actions)
                    else:
                        strategy = node.average_strategy()
                    if any((not isfinite(value)) or value < 0.0 for value in strategy):
                        raise RiverStateAbstractionError(
                            "invalid expanded strategy probability"
                        )
                    strategies[(player, cards, history)] = strategy
        return RiverMultiSizeOneRaisePolicy(strategies)

    def exact_unabstracted_exploitability(self) -> float:
        """Evaluate the expanded policy against the exact private-hand game BR."""
        return exploitability_dp(self.config, self.concrete_average_policy())


def identity_bucket_map(config: RiverMultiSizeOneRaiseConfig) -> RiverBucketMap:
    config.validate()
    buckets: dict[ConcreteHandKey, Bucket] = {}
    for player, hands in ((0, config.p0_range), (1, config.p1_range)):
        for hand in hands:
            cards = hand.canonical_cards()
            buckets[(player, cards)] = cards
    return RiverBucketMap(buckets, name="identity")


def single_bucket_map(config: RiverMultiSizeOneRaiseConfig) -> RiverBucketMap:
    """Maximum deliberate compression baseline: one private bucket per player."""
    config.validate()
    buckets: dict[ConcreteHandKey, Bucket] = {}
    for player, hands in ((0, config.p0_range), (1, config.p1_range)):
        for hand in hands:
            buckets[(player, hand.canonical_cards())] = 0
    return RiverBucketMap(buckets, name="single")


def showdown_category_bucket_map(
    config: RiverMultiSizeOneRaiseConfig,
) -> RiverBucketMap:
    config.validate()
    buckets: dict[ConcreteHandKey, Bucket] = {}
    for player, hands in ((0, config.p0_range), (1, config.p1_range)):
        for hand in hands:
            cards = hand.canonical_cards()
            value = evaluate_best(cards + config.board)
            buckets[(player, cards)] = int(value.category)
    return RiverBucketMap(buckets, name="showdown_category")


def conditional_showdown_equity(
    config: RiverMultiSizeOneRaiseConfig,
    player: int,
    cards: tuple[int, int],
) -> float:
    """Blocker-aware river equity of one exact hand versus configured range.

    Win=1, tie=0.5, loss=0.  The conditional distribution is induced by the
    compatible chance-deal weights already used by the exact game.
    """
    config.validate()
    if player not in (0, 1):
        raise RiverStateAbstractionError("player must be 0 or 1")
    exact = tuple(sorted(cards))
    numerator = 0.0
    denominator = 0.0
    for deal in config.compatible_deals():
        own = deal.p0_cards if player == 0 else deal.p1_cards
        if own != exact:
            continue
        denominator += deal.probability
        sign_for_player = deal.showdown_sign if player == 0 else -deal.showdown_sign
        score = 1.0 if sign_for_player > 0 else 0.5 if sign_for_player == 0 else 0.0
        numerator += deal.probability * score
    if denominator <= 0.0:
        raise RiverStateAbstractionError(
            f"exact hand {exact} has no compatible opponent deal"
        )
    return numerator / denominator


def equity_quantile_bucket_map(
    config: RiverMultiSizeOneRaiseConfig,
    bucket_count: int,
) -> RiverBucketMap:
    """Deterministically partition each player's hands by exact river equity."""
    config.validate()
    if (
        isinstance(bucket_count, bool)
        or not isinstance(bucket_count, int)
        or bucket_count <= 0
    ):
        raise RiverStateAbstractionError("bucket_count must be a positive integer")

    buckets: dict[ConcreteHandKey, Bucket] = {}
    for player, hands in ((0, config.p0_range), (1, config.p1_range)):
        ranked = []
        for hand in hands:
            cards = hand.canonical_cards()
            ranked.append(
                (conditional_showdown_equity(config, player, cards), cards)
            )
        ranked.sort(key=lambda item: (item[0], item[1]))
        n = len(ranked)
        effective = min(bucket_count, n)
        for index, (_, cards) in enumerate(ranked):
            # Equal-count deterministic quantiles.  This intentionally does not
            # use floating bucket boundaries, so the same input is reproducible.
            bucket = min(effective - 1, (index * effective) // n)
            buckets[(player, cards)] = bucket
    return RiverBucketMap(buckets, name=f"equity_quantile_{bucket_count}")
