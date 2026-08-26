"""External-sampling MCCFR candidate for the exact Short Deck river lab.

SpinCore provides strong evidence that external sampling is worth testing before
committing a Ryzen-scale blueprint, but its 3-player tournament/ICM state cannot
be copied into DeepSix.  This module ports only the algorithmic idea into the
existing DeepSix river game so it competes against full-chance CFR and RM+ under
the same cards, action tree and dynamic exact best-response oracle.

One MCCFR iteration samples exactly one compatible private-card deal from the
configured chance distribution.  For each traverser, traverser actions are
fully enumerated while opponent actions are sampled from the frozen strategy at
the start of the iteration.  Regret deltas for both players are committed only
after both traversals, preserving a synchronous strategy snapshot.

Average-strategy accumulation uses a separate own-reach sampler: target-player
actions are sampled and opponent actions are enumerated.  This mirrors the
important own-reach idea used by SpinCore without importing its neural network,
reservoir, action width, ICM utility or 52-card representation.

The checkpoint contract serializes the exact RNG state and every regret/average
accumulator.  A resumed process must therefore continue the same stochastic
lineage byte-semantically rather than merely start a statistically similar run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from math import isfinite
import random

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


EXTERNAL_SAMPLING_CHECKPOINT_SCHEMA = "DEEPSIX_RIVER_EXTERNAL_SAMPLING_CHECKPOINT_V1"


def _nested_lists(value):
    if isinstance(value, tuple):
        return [_nested_lists(item) for item in value]
    return value


def _nested_tuples(value):
    if isinstance(value, list):
        return tuple(_nested_tuples(item) for item in value)
    return value


def external_sampling_config_fingerprint(config: RiverMultiSizeOneRaiseConfig) -> str:
    """Exact semantic identity of the tiny game used by one checkpoint."""

    config.validate()

    def range_payload(rows):
        return [
            {
                "cards": list(item.canonical_cards()),
                "weight_hex": float(item.weight).hex(),
            }
            for item in rows
        ]

    payload = {
        "board": list(config.board),
        "pot": config.pot,
        "bet_sizes": list(config.bet_sizes),
        "raise_to": config.raise_to,
        "p0_range": range_payload(config.p0_range),
        "p1_range": range_payload(config.p1_range),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass
class _SamplingNode:
    action_count: int
    regret_sum: list[float] = field(init=False)
    strategy_sum: list[float] = field(init=False)

    def __post_init__(self) -> None:
        if self.action_count < 2:
            raise RiverMultiSizeOneRaiseError("decision node requires at least two actions")
        self.regret_sum = [0.0] * self.action_count
        self.strategy_sum = [0.0] * self.action_count

    def current_strategy(self) -> tuple[float, ...]:
        positive = [max(0.0, value) for value in self.regret_sum]
        total = sum(positive)
        if total > 0.0:
            return tuple(value / total for value in positive)
        probability = 1.0 / self.action_count
        return (probability,) * self.action_count

    def average_strategy(self) -> tuple[float, ...]:
        total = sum(self.strategy_sum)
        if total > 0.0:
            return tuple(value / total for value in self.strategy_sum)
        probability = 1.0 / self.action_count
        return (probability,) * self.action_count


@dataclass
class _RegretDelta:
    action_count: int
    values: list[float] = field(init=False)

    def __post_init__(self) -> None:
        self.values = [0.0] * self.action_count


class RiverExternalSamplingMCCFR:
    """Deterministic-seed external-sampling MCCFR for the one-raise river lab."""

    def __init__(
        self,
        config: RiverMultiSizeOneRaiseConfig,
        *,
        seed: int = 20260826,
    ) -> None:
        config.validate()
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise RiverMultiSizeOneRaiseError("seed must be a non-negative integer")
        self.config = config
        self.deals = config.compatible_deals()
        self.seed = seed
        self.rng = random.Random(seed)
        self.nodes: dict[PolicyKey, _SamplingNode] = {}
        self.iterations = 0
        self.sampled_deals = 0
        self.regret_nodes_visited = 0
        self.average_nodes_visited = 0

    def _node(self, key: PolicyKey, action_count: int) -> _SamplingNode:
        node = self.nodes.get(key)
        if node is None:
            node = _SamplingNode(action_count)
            self.nodes[key] = node
        elif node.action_count != action_count:
            raise RiverMultiSizeOneRaiseError("infoset action count changed")
        return node

    @staticmethod
    def _delta(
        deltas: dict[PolicyKey, _RegretDelta],
        key: PolicyKey,
        action_count: int,
    ) -> _RegretDelta:
        delta = deltas.get(key)
        if delta is None:
            delta = _RegretDelta(action_count)
            deltas[key] = delta
        elif delta.action_count != action_count:
            raise RiverMultiSizeOneRaiseError("regret-delta action count changed")
        return delta

    def _sample_index(self, probabilities: tuple[float, ...]) -> int:
        if not probabilities or any(
            (not isfinite(value)) or value < 0.0 for value in probabilities
        ):
            raise RiverMultiSizeOneRaiseError("invalid sampling probabilities")
        total = sum(probabilities)
        if abs(total - 1.0) > 1e-9:
            raise RiverMultiSizeOneRaiseError("sampling probabilities must sum to one")
        draw = self.rng.random()
        cumulative = 0.0
        for index, probability in enumerate(probabilities):
            cumulative += probability
            if draw < cumulative:
                return index
        return len(probabilities) - 1

    def _sample_deal(self) -> MultiSizeOneRaiseDeal:
        draw = self.rng.random()
        cumulative = 0.0
        for deal in self.deals:
            cumulative += deal.probability
            if draw < cumulative:
                self.sampled_deals += 1
                return deal
        self.sampled_deals += 1
        return self.deals[-1]

    @staticmethod
    def _utility_for_player(
        config: RiverMultiSizeOneRaiseConfig,
        deal: MultiSizeOneRaiseDeal,
        history: History,
        player: int,
    ) -> float:
        utility0 = terminal_utility_p0(config, deal, history)
        return utility0 if player == 0 else -utility0

    def _regret_traverse(
        self,
        deal: MultiSizeOneRaiseDeal,
        history: History,
        traverser: int,
        deltas: dict[PolicyKey, _RegretDelta],
    ) -> float:
        self.regret_nodes_visited += 1
        if is_terminal(self.config, history):
            return self._utility_for_player(self.config, deal, history, traverser)

        actor = player_to_act(self.config, history)
        cards = deal.p0_cards if actor == 0 else deal.p1_cards
        key: PolicyKey = (actor, tuple(sorted(cards)), history)
        actions = legal_actions(self.config, history)
        node = self._node(key, len(actions))
        strategy = node.current_strategy()

        if actor == traverser:
            action_values = []
            for action in actions:
                action_values.append(
                    self._regret_traverse(
                        deal,
                        history + (action,),
                        traverser,
                        deltas,
                    )
                )
            node_value = sum(
                strategy[index] * value
                for index, value in enumerate(action_values)
            )
            delta = self._delta(deltas, key, len(actions))
            for index, value in enumerate(action_values):
                delta.values[index] += value - node_value
            return node_value

        sampled = self._sample_index(strategy)
        return self._regret_traverse(
            deal,
            history + (actions[sampled],),
            traverser,
            deltas,
        )

    def _collect_average_strategy(
        self,
        deal: MultiSizeOneRaiseDeal,
        history: History,
        target_player: int,
    ) -> None:
        self.average_nodes_visited += 1
        if is_terminal(self.config, history):
            return
        actor = player_to_act(self.config, history)
        cards = deal.p0_cards if actor == 0 else deal.p1_cards
        key: PolicyKey = (actor, tuple(sorted(cards)), history)
        actions = legal_actions(self.config, history)
        node = self._node(key, len(actions))
        strategy = node.current_strategy()

        if actor == target_player:
            # Sampling target actions makes state visitation proportional to
            # target-player own reach.  Adding sigma unweighted avoids squaring
            # that reach probability.
            for index, probability in enumerate(strategy):
                node.strategy_sum[index] += probability
            sampled = self._sample_index(strategy)
            self._collect_average_strategy(
                deal,
                history + (actions[sampled],),
                target_player,
            )
            return

        # Opponent reach must not weight the target player's behavioral average;
        # enumerate opponent branches while target-player actions are sampled.
        for action in actions:
            self._collect_average_strategy(
                deal,
                history + (action,),
                target_player,
            )

    def train(self, iterations: int) -> None:
        if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
            raise RiverMultiSizeOneRaiseError("iterations must be a positive integer")

        for _ in range(iterations):
            deal = self._sample_deal()
            deltas: dict[PolicyKey, _RegretDelta] = {}

            # Both traversers see the same pre-update strategy snapshot.  Regret
            # mutation is delayed until both traversals are complete.
            self._regret_traverse(deal, (), 0, deltas)
            self._regret_traverse(deal, (), 1, deltas)
            self._collect_average_strategy(deal, (), 0)
            self._collect_average_strategy(deal, (), 1)

            for key, delta in deltas.items():
                node = self.nodes[key]
                for index, value in enumerate(delta.values):
                    node.regret_sum[index] += value
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

    @property
    def nodes_visited(self) -> int:
        return self.regret_nodes_visited + self.average_nodes_visited

    def all_regrets_finite(self) -> bool:
        return all(
            isfinite(value)
            for node in self.nodes.values()
            for value in node.regret_sum
        )

    def state_dict(self) -> dict[str, object]:
        """Return an exact JSON-compatible stochastic/checkpoint state."""

        rows = []
        for key in sorted(self.nodes):
            player, cards, history = key
            node = self.nodes[key]
            rows.append(
                {
                    "player": player,
                    "cards": list(cards),
                    "history": list(history),
                    "action_count": node.action_count,
                    "regret_hex": [float(value).hex() for value in node.regret_sum],
                    "strategy_hex": [float(value).hex() for value in node.strategy_sum],
                }
            )
        return {
            "schema": EXTERNAL_SAMPLING_CHECKPOINT_SCHEMA,
            "config_sha256": external_sampling_config_fingerprint(self.config),
            "seed": self.seed,
            "iterations": self.iterations,
            "sampled_deals": self.sampled_deals,
            "regret_nodes_visited": self.regret_nodes_visited,
            "average_nodes_visited": self.average_nodes_visited,
            "rng_state": _nested_lists(self.rng.getstate()),
            "nodes": rows,
        }

    def checkpoint_json(self) -> str:
        return json.dumps(
            self.state_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def checkpoint_sha256(self) -> str:
        return hashlib.sha256(self.checkpoint_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_state_dict(
        cls,
        config: RiverMultiSizeOneRaiseConfig,
        payload: dict,
    ) -> "RiverExternalSamplingMCCFR":
        expected = {
            "schema",
            "config_sha256",
            "seed",
            "iterations",
            "sampled_deals",
            "regret_nodes_visited",
            "average_nodes_visited",
            "rng_state",
            "nodes",
        }
        if set(payload) != expected:
            raise RiverMultiSizeOneRaiseError("external-sampling checkpoint keys differ from v1")
        if payload.get("schema") != EXTERNAL_SAMPLING_CHECKPOINT_SCHEMA:
            raise RiverMultiSizeOneRaiseError("wrong external-sampling checkpoint schema")
        if payload.get("config_sha256") != external_sampling_config_fingerprint(config):
            raise RiverMultiSizeOneRaiseError("external-sampling checkpoint/config mismatch")

        seed = payload.get("seed")
        trainer = cls(config, seed=seed)
        for counter in (
            "iterations",
            "sampled_deals",
            "regret_nodes_visited",
            "average_nodes_visited",
        ):
            value = payload.get(counter)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RiverMultiSizeOneRaiseError(f"invalid checkpoint counter {counter}")
            setattr(trainer, counter, value)
        if trainer.sampled_deals != trainer.iterations:
            raise RiverMultiSizeOneRaiseError("sampled-deal count must equal iteration count")

        allowed_cards = {
            0: {row.canonical_cards() for row in config.p0_range},
            1: {row.canonical_cards() for row in config.p1_range},
        }
        allowed_histories = {
            0: set(player_histories(config, 0)),
            1: set(player_histories(config, 1)),
        }
        rows = payload.get("nodes")
        if not isinstance(rows, list):
            raise RiverMultiSizeOneRaiseError("checkpoint nodes must be a list")
        seen: set[PolicyKey] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise RiverMultiSizeOneRaiseError("checkpoint node must be an object")
            if set(row) != {
                "player",
                "cards",
                "history",
                "action_count",
                "regret_hex",
                "strategy_hex",
            }:
                raise RiverMultiSizeOneRaiseError("checkpoint node keys differ from v1")
            player = row["player"]
            if player not in (0, 1):
                raise RiverMultiSizeOneRaiseError("checkpoint node player must be 0 or 1")
            try:
                cards = tuple(int(value) for value in row["cards"])
                history = tuple(str(value) for value in row["history"])
            except (TypeError, ValueError) as exc:
                raise RiverMultiSizeOneRaiseError("malformed checkpoint node key") from exc
            if len(cards) != 2 or cards not in allowed_cards[player]:
                raise RiverMultiSizeOneRaiseError("checkpoint node cards outside player range")
            if history not in allowed_histories[player]:
                raise RiverMultiSizeOneRaiseError("checkpoint node history is not a player infoset")
            key: PolicyKey = (player, cards, history)
            if key in seen:
                raise RiverMultiSizeOneRaiseError("duplicate checkpoint infoset")
            seen.add(key)
            expected_actions = len(legal_actions(config, history))
            action_count = row["action_count"]
            if action_count != expected_actions:
                raise RiverMultiSizeOneRaiseError("checkpoint node action count mismatch")
            try:
                regrets = [float.fromhex(value) for value in row["regret_hex"]]
                strategies = [float.fromhex(value) for value in row["strategy_hex"]]
            except (TypeError, ValueError) as exc:
                raise RiverMultiSizeOneRaiseError("invalid checkpoint float encoding") from exc
            if len(regrets) != action_count or len(strategies) != action_count:
                raise RiverMultiSizeOneRaiseError("checkpoint node vector length mismatch")
            if any(not isfinite(value) for value in regrets + strategies):
                raise RiverMultiSizeOneRaiseError("checkpoint node contains nonfinite value")
            if any(value < 0.0 for value in strategies):
                raise RiverMultiSizeOneRaiseError("checkpoint strategy sum is negative")
            node = _SamplingNode(action_count)
            node.regret_sum = regrets
            node.strategy_sum = strategies
            trainer.nodes[key] = node

        try:
            trainer.rng.setstate(_nested_tuples(payload["rng_state"]))
        except (TypeError, ValueError) as exc:
            raise RiverMultiSizeOneRaiseError("invalid checkpoint RNG state") from exc
        return trainer

    @classmethod
    def from_checkpoint_json(
        cls,
        config: RiverMultiSizeOneRaiseConfig,
        text: str,
    ) -> "RiverExternalSamplingMCCFR":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RiverMultiSizeOneRaiseError("invalid external-sampling checkpoint JSON") from exc
        if not isinstance(payload, dict):
            raise RiverMultiSizeOneRaiseError("external-sampling checkpoint must be an object")
        return cls.from_state_dict(config, payload)
