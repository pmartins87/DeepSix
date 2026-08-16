"""Exact counterfactual-value features for the Short Deck river abstraction lab.

The earlier DeepSix private-state baselines use showdown equity, nutness and
blocker pressure.  Those features describe cards well, but they do not directly
ask the strategic question that state abstraction ultimately cares about:

    do two private hands have similar values for the actions available to them?

This module adds a deliberately transparent first answer.  For every exact
private hand and every infoset belonging to that player in the gated
``multi-size + one-raise`` river game, it computes the value of *forcing each
legal action* and then following a fixed uniform continuation policy.

The values are normalized counterfactual action values (CFVs): chance is
conditioned on the player's exact hand, the player's own reach before the
infoset is excluded, and opponent reach is induced by the fixed reference
policy.  With a uniform reference policy the opponent action probability for a
given public history is hand-independent, so it cancels during normalization;
the remaining weights are exactly the compatible chance probabilities for that
private hand.

The resulting vector is not claimed to be an optimal production abstraction.
It is an auditable strategic feature baseline.  ``cfv_kmedoids_bucket_map``
clusters those vectors with deterministic k-medoids and the resulting policy is
still judged by the unabstracted Dynamic Exact Best Response.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import isfinite

from .river_multisize_one_raise import (
    History,
    MultiSizeOneRaiseDeal,
    RiverMultiSizeOneRaiseConfig,
    is_terminal,
    legal_actions,
    player_histories,
    player_to_act,
    terminal_utility_p0,
)
from .river_state_abstraction import RiverBucketMap, RiverStateAbstractionError


@dataclass(frozen=True)
class CounterfactualHistoryValues:
    history: History
    actions: tuple[str, ...]
    action_values: tuple[float, ...]

    def validate(self) -> None:
        if not self.actions or len(self.actions) != len(self.action_values):
            raise RiverStateAbstractionError(
                "counterfactual history actions/value arity mismatch"
            )
        if any(not isfinite(value) for value in self.action_values):
            raise RiverStateAbstractionError(
                "counterfactual action values must be finite"
            )


@dataclass(frozen=True)
class RiverCounterfactualFeatures:
    player: int
    cards: tuple[int, int]
    histories: tuple[CounterfactualHistoryValues, ...]
    normalized_cfv_vector: tuple[float, ...]

    def validate(self) -> None:
        if self.player not in (0, 1):
            raise RiverStateAbstractionError("feature player must be 0 or 1")
        if len(self.cards) != 2 or self.cards[0] == self.cards[1]:
            raise RiverStateAbstractionError(
                "feature cards must contain two distinct cards"
            )
        if not self.histories or not self.normalized_cfv_vector:
            raise RiverStateAbstractionError(
                "counterfactual feature vector cannot be empty"
            )
        expected = 0
        for item in self.histories:
            item.validate()
            expected += len(item.action_values)
        if expected != len(self.normalized_cfv_vector):
            raise RiverStateAbstractionError(
                "flattened counterfactual vector has wrong dimension"
            )
        if any(not isfinite(value) for value in self.normalized_cfv_vector):
            raise RiverStateAbstractionError(
                "normalized counterfactual values must be finite"
            )


@lru_cache(maxsize=None)
def _uniform_deal_value_p0(
    config: RiverMultiSizeOneRaiseConfig,
    deal: MultiSizeOneRaiseDeal,
    history: History,
) -> float:
    """P0 value from ``history`` when every future decision is uniform."""
    if is_terminal(config, history):
        return terminal_utility_p0(config, deal, history)
    actions = legal_actions(config, history)
    probability = 1.0 / len(actions)
    return sum(
        probability
        * _uniform_deal_value_p0(config, deal, history + (action,))
        for action in actions
    )


def _configured_cards(
    config: RiverMultiSizeOneRaiseConfig,
    player: int,
) -> set[tuple[int, int]]:
    if player == 0:
        hands = config.p0_range
    elif player == 1:
        hands = config.p1_range
    else:
        raise RiverStateAbstractionError("player must be 0 or 1")
    return {hand.canonical_cards() for hand in hands}


@lru_cache(maxsize=None)
def exact_uniform_counterfactual_features(
    config: RiverMultiSizeOneRaiseConfig,
    player: int,
    cards: tuple[int, int],
) -> RiverCounterfactualFeatures:
    """Compute normalized uniform-reference action CFVs for one exact hand.

    ``action_values`` use the acting player's utility convention: larger is
    always better for the player whose hand is being described.  The flattened
    vector is divided by the current pot so fixtures with different chip scales
    remain comparable when the benchmark aggregates results.
    """
    config.validate()
    if player not in (0, 1):
        raise RiverStateAbstractionError("player must be 0 or 1")
    cards = tuple(sorted(cards))
    if cards not in _configured_cards(config, player):
        raise RiverStateAbstractionError(
            f"exact hand {cards} is not in player {player} configured range"
        )

    deals = tuple(
        deal
        for deal in config.compatible_deals()
        if (deal.p0_cards if player == 0 else deal.p1_cards) == cards
    )
    chance_mass = sum(deal.probability for deal in deals)
    if chance_mass <= 0.0:
        raise RiverStateAbstractionError(
            "configured hand has no compatible chance mass"
        )

    histories: list[CounterfactualHistoryValues] = []
    flat: list[float] = []
    utility_sign = 1.0 if player == 0 else -1.0

    for history in player_histories(config, player):
        if player_to_act(config, history) != player:
            raise RiverStateAbstractionError(
                "player_histories returned a history for the wrong actor"
            )
        actions = legal_actions(config, history)
        values = []
        for action in actions:
            next_history = history + (action,)
            expected_p0 = sum(
                deal.probability
                * _uniform_deal_value_p0(config, deal, next_history)
                for deal in deals
            ) / chance_mass
            own_value = utility_sign * expected_p0
            values.append(own_value)
            flat.append(own_value / config.pot)
        item = CounterfactualHistoryValues(
            history=history,
            actions=actions,
            action_values=tuple(values),
        )
        item.validate()
        histories.append(item)

    output = RiverCounterfactualFeatures(
        player=player,
        cards=cards,
        histories=tuple(histories),
        normalized_cfv_vector=tuple(flat),
    )
    output.validate()
    return output


def all_exact_uniform_counterfactual_features(
    config: RiverMultiSizeOneRaiseConfig,
) -> tuple[RiverCounterfactualFeatures, ...]:
    config.validate()
    output = []
    for player, hands in ((0, config.p0_range), (1, config.p1_range)):
        for hand in hands:
            output.append(
                exact_uniform_counterfactual_features(
                    config,
                    player,
                    hand.canonical_cards(),
                )
            )
    return tuple(output)


def _squared_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise RiverStateAbstractionError(
            "counterfactual feature vectors have different dimensions"
        )
    return sum((a - b) ** 2 for a, b in zip(left, right))


def _deterministic_kmedoids(
    vectors: dict[tuple[int, int], tuple[float, ...]],
    bucket_count: int,
) -> dict[tuple[int, int], int]:
    """Small deterministic PAM-style clustering for exact river feature vectors."""
    hands = tuple(sorted(vectors))
    if not hands:
        raise RiverStateAbstractionError("cannot cluster an empty hand set")
    k = min(bucket_count, len(hands))
    if k == len(hands):
        return {cards: index for index, cards in enumerate(hands)}

    # Farthest-first deterministic initialization.  The first medoid is the hand
    # with the largest total squared distance to the population; later medoids
    # maximize distance to the closest selected medoid.
    first = max(
        hands,
        key=lambda cards: sum(
            _squared_distance(vectors[cards], vectors[other]) for other in hands
        ),
    )
    medoids = [first]
    while len(medoids) < k:
        candidates = tuple(cards for cards in hands if cards not in medoids)
        next_medoid = max(
            candidates,
            key=lambda cards: min(
                _squared_distance(vectors[cards], vectors[medoid])
                for medoid in medoids
            ),
        )
        medoids.append(next_medoid)

    for _ in range(50):
        clusters: list[list[tuple[int, int]]] = [[] for _ in medoids]
        medoid_index = {cards: index for index, cards in enumerate(medoids)}
        for cards in hands:
            # Preserve one owner for each medoid even when two feature vectors
            # are exactly identical; this prevents deterministic empty clusters.
            if cards in medoid_index:
                index = medoid_index[cards]
            else:
                index = min(
                    range(len(medoids)),
                    key=lambda candidate: (
                        _squared_distance(
                            vectors[cards], vectors[medoids[candidate]]
                        ),
                        candidate,
                    ),
                )
            clusters[index].append(cards)

        updated = []
        for cluster in clusters:
            if not cluster:
                raise RiverStateAbstractionError(
                    "deterministic k-medoids produced an empty cluster"
                )
            updated.append(
                min(
                    cluster,
                    key=lambda candidate: (
                        sum(
                            _squared_distance(
                                vectors[candidate], vectors[other]
                            )
                            for other in cluster
                        ),
                        candidate,
                    ),
                )
            )
        if updated == medoids:
            break
        medoids = updated

    assignments = {}
    medoid_index = {cards: index for index, cards in enumerate(medoids)}
    for cards in hands:
        if cards in medoid_index:
            index = medoid_index[cards]
        else:
            index = min(
                range(len(medoids)),
                key=lambda candidate: (
                    _squared_distance(vectors[cards], vectors[medoids[candidate]]),
                    candidate,
                ),
            )
        assignments[cards] = index
    return assignments


def cfv_kmedoids_bucket_map(
    config: RiverMultiSizeOneRaiseConfig,
    bucket_count: int,
) -> RiverBucketMap:
    """Cluster exact hands by uniform-reference normalized action-CFV vectors."""
    config.validate()
    if (
        isinstance(bucket_count, bool)
        or not isinstance(bucket_count, int)
        or bucket_count <= 0
    ):
        raise RiverStateAbstractionError("bucket_count must be a positive integer")

    buckets = {}
    for player, hands in ((0, config.p0_range), (1, config.p1_range)):
        features = {
            hand.canonical_cards(): exact_uniform_counterfactual_features(
                config,
                player,
                hand.canonical_cards(),
            ).normalized_cfv_vector
            for hand in hands
        }
        assignments = _deterministic_kmedoids(features, bucket_count)
        for cards, bucket in assignments.items():
            buckets[(player, cards)] = bucket

    mapping = RiverBucketMap(buckets, name=f"cfv_kmedoids_{bucket_count}")
    mapping.validate(config)
    return mapping
