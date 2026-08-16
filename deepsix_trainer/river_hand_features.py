"""Exact, transparent river hand features for private-state abstraction research.

The first DeepSix bucket baselines use showdown category or conditional equity.
Those are useful but omit two pieces of information that matter strategically on
a fixed river:

* **absolute nutness** against the complete compatible Short Deck combo space;
* **blocker pressure** on the configured opponent range, especially on holdings
  that would otherwise beat the player's hand.

This module computes those quantities exactly.  It deliberately avoids neural
embeddings or learned distances at this stage so every feature can be audited by
enumeration.

The supplied ``feature_borda_quantile_bucket_map`` is only a baseline.  It ranks
hands independently by four exact features, averages their percentile ranks with
equal weight, and then makes deterministic equal-count quantile buckets.  Equal
weight is explicit rather than tuned to one fixture.  Later learned/clustering
methods must beat this baseline under the unabstracted exact best response.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from deepsix_core.cards import NUM_CARDS
from deepsix_core.evaluator import HandValue, evaluate_best
from .river_multisize_one_raise import RiverMultiSizeOneRaiseConfig
from .river_state_abstraction import (
    RiverBucketMap,
    RiverStateAbstractionError,
    conditional_showdown_equity,
)


@dataclass(frozen=True)
class RiverHandFeatures:
    player: int
    cards: tuple[int, int]
    hand_value: HandValue
    conditional_range_equity: float
    universal_equity: float
    nutness: float
    blocked_range_weight_fraction: float
    blocked_stronger_weight_fraction: float

    def validate(self) -> None:
        if self.player not in (0, 1):
            raise RiverStateAbstractionError("feature player must be 0 or 1")
        if len(self.cards) != 2 or self.cards[0] == self.cards[1]:
            raise RiverStateAbstractionError("feature cards must be a distinct pair")
        for name in (
            "conditional_range_equity",
            "universal_equity",
            "nutness",
            "blocked_range_weight_fraction",
            "blocked_stronger_weight_fraction",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise RiverStateAbstractionError(f"{name} must be within [0, 1]")


def _opponent_range(config: RiverMultiSizeOneRaiseConfig, player: int):
    if player == 0:
        return config.p1_range
    if player == 1:
        return config.p0_range
    raise RiverStateAbstractionError("player must be 0 or 1")


def _universal_equity_and_nutness(
    config: RiverMultiSizeOneRaiseConfig,
    cards: tuple[int, int],
    own_value: HandValue,
) -> tuple[float, float]:
    excluded = set(config.board) | set(cards)
    remaining = tuple(card for card in range(NUM_CARDS) if card not in excluded)
    total = 0
    wins = 0
    ties = 0
    stronger = 0
    for opponent_cards in combinations(remaining, 2):
        opponent_value = evaluate_best(opponent_cards + config.board)
        total += 1
        if own_value > opponent_value:
            wins += 1
        elif own_value == opponent_value:
            ties += 1
        else:
            stronger += 1
    if total <= 0:
        raise RiverStateAbstractionError("no universal compatible opponent combos")
    equity = (wins + 0.5 * ties) / total
    nutness = 1.0 - (stronger / total)
    return equity, nutness


def exact_river_hand_features(
    config: RiverMultiSizeOneRaiseConfig,
    player: int,
    cards: tuple[int, int],
) -> RiverHandFeatures:
    """Compute exact river strength/blocker features for one configured hand."""
    config.validate()
    if player not in (0, 1):
        raise RiverStateAbstractionError("player must be 0 or 1")
    cards = tuple(sorted(cards))
    configured_hands = config.p0_range if player == 0 else config.p1_range
    configured_cards = {hand.canonical_cards() for hand in configured_hands}
    if cards not in configured_cards:
        raise RiverStateAbstractionError(
            f"exact hand {cards} is not in player {player} configured range"
        )

    own_value = evaluate_best(cards + config.board)
    range_equity = conditional_showdown_equity(config, player, cards)
    universal_equity, nutness = _universal_equity_and_nutness(
        config,
        cards,
        own_value,
    )

    opponent = _opponent_range(config, player)
    total_weight = sum(hand.weight for hand in opponent)
    blocked_weight = 0.0
    stronger_weight = 0.0
    blocked_stronger_weight = 0.0
    own_set = set(cards)
    for hand in opponent:
        opponent_cards = hand.canonical_cards()
        blocked = bool(set(opponent_cards) & own_set)
        opponent_value = evaluate_best(opponent_cards + config.board)
        if blocked:
            blocked_weight += hand.weight
        if opponent_value > own_value:
            stronger_weight += hand.weight
            if blocked:
                blocked_stronger_weight += hand.weight

    blocked_fraction = blocked_weight / total_weight if total_weight > 0.0 else 0.0
    blocked_stronger_fraction = (
        blocked_stronger_weight / stronger_weight if stronger_weight > 0.0 else 0.0
    )

    features = RiverHandFeatures(
        player=player,
        cards=cards,
        hand_value=own_value,
        conditional_range_equity=range_equity,
        universal_equity=universal_equity,
        nutness=nutness,
        blocked_range_weight_fraction=blocked_fraction,
        blocked_stronger_weight_fraction=blocked_stronger_fraction,
    )
    features.validate()
    return features


def all_exact_river_hand_features(
    config: RiverMultiSizeOneRaiseConfig,
) -> tuple[RiverHandFeatures, ...]:
    config.validate()
    output = []
    for player, hands in ((0, config.p0_range), (1, config.p1_range)):
        for hand in hands:
            output.append(
                exact_river_hand_features(config, player, hand.canonical_cards())
            )
    return tuple(output)


def _average_rank_score(
    features: tuple[RiverHandFeatures, ...],
) -> dict[tuple[int, int], float]:
    """Equal-weight average percentile rank over four exact scalar features."""
    if not features:
        return {}
    feature_names = (
        "conditional_range_equity",
        "universal_equity",
        "nutness",
        "blocked_stronger_weight_fraction",
    )
    rank_sums = {item.cards: 0.0 for item in features}
    n = len(features)
    denominator = max(1, n - 1)
    for name in feature_names:
        ordered = sorted(features, key=lambda item: (getattr(item, name), item.cards))
        # Average ranks for exact ties so arbitrary card ids do not change the
        # feature score; cards only make the final output ordering deterministic.
        start = 0
        while start < n:
            value = getattr(ordered[start], name)
            end = start + 1
            while end < n and getattr(ordered[end], name) == value:
                end += 1
            average_index = (start + end - 1) / 2.0
            percentile = average_index / denominator
            for index in range(start, end):
                rank_sums[ordered[index].cards] += percentile
            start = end
    return {cards: total / len(feature_names) for cards, total in rank_sums.items()}


def feature_borda_quantile_bucket_map(
    config: RiverMultiSizeOneRaiseConfig,
    bucket_count: int,
) -> RiverBucketMap:
    """Bucket by equal-weight rank aggregation of equity/nutness/blocker features."""
    config.validate()
    if (
        isinstance(bucket_count, bool)
        or not isinstance(bucket_count, int)
        or bucket_count <= 0
    ):
        raise RiverStateAbstractionError("bucket_count must be a positive integer")

    buckets = {}
    for player, hands in ((0, config.p0_range), (1, config.p1_range)):
        features = tuple(
            exact_river_hand_features(config, player, hand.canonical_cards())
            for hand in hands
        )
        scores = _average_rank_score(features)
        ordered = sorted(features, key=lambda item: (scores[item.cards], item.cards))
        n = len(ordered)
        effective = min(bucket_count, n)
        for index, item in enumerate(ordered):
            bucket = min(effective - 1, (index * effective) // n)
            buckets[(player, item.cards)] = bucket
    return RiverBucketMap(buckets, name=f"feature_borda_quantile_{bucket_count}")
