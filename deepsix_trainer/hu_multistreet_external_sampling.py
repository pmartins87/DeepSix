"""External-sampling MCCFR candidate for the F5 HU multi-street game.

The algorithmic structure is ported from DeepSix's already-gated river external-
sampling implementation, which itself was informed by the useful SpinCore
sampling pattern.  Only the sampling idea is transferred: this module uses the
Short Deck multi-street Core, exact chance branches, canonical F5 infosets and
gross HU utility defined by DeepSix.

One iteration:

1. sample one compatible private deal from its exact rational distribution;
2. run one regret traversal per player using the same pre-update strategy;
3. at a traverser's nodes enumerate all actions;
4. at opponent nodes sample one action from current strategy;
5. sample public chance outcomes from their exact rational distribution;
6. collect behavioral average strategy with a separate own-reach sampler;
7. commit both players' regret deltas only after all traversals complete.

The average-strategy collector samples target-player actions and enumerates
opponent actions.  This makes target infoset visitation proportional to own
reach without accidentally weighting the behavioral average by opponent reach.

This remains a correctness/architecture candidate.  It is not promoted to the
production Ryzen trainer until convergence/error-per-CPU-hour beats the full-
tree baselines under shared oracles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import math
import random
from typing import Mapping, Sequence

from deepsix_simulator.utility import utility_from_settlement

from .hu_multistreet_cfr import HuMultiStreetCFRError
from .hu_multistreet_chance_sampled_cfr import sample_fraction_index
from .hu_multistreet_float_cfr import FloatPolicyRow, FloatTabularPolicy
from .hu_multistreet_reference import (
    HU_REFERENCE_MICROGAME_VERSION,
    HuReferenceMicrogame,
    MicroAction,
)
from .multistreet_branch import BranchNodeKind, ExactBranchState
from .multistreet_state import PrivateDecisionState, decision_state_from_components


HU_MULTISTREET_EXTERNAL_SAMPLING_VERSION = (
    "deepsix_f5_hu_external_sampling_mccfr_2026-08-27_v1"
)
HU_MULTISTREET_EXTERNAL_SAMPLING_CHECKPOINT_SCHEMA = (
    "DEEPSIX_F5_HU_EXTERNAL_SAMPLING_CHECKPOINT_V1"
)


def _nested_lists(value):
    if isinstance(value, tuple):
        return [_nested_lists(item) for item in value]
    return value


def _nested_tuples(value):
    if isinstance(value, list):
        return tuple(_nested_tuples(item) for item in value)
    return value


def _validate_seed(seed: int) -> int:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise HuMultiStreetCFRError("seed must be a non-negative integer")
    return seed


def hu_external_sampling_game_fingerprint(game: HuReferenceMicrogame) -> str:
    if not isinstance(game, HuReferenceMicrogame):
        raise HuMultiStreetCFRError("game fingerprint requires HuReferenceMicrogame")
    config = game.config
    config.validate()
    payload = {
        "microgame_version": HU_REFERENCE_MICROGAME_VERSION,
        "stake_cents": config.stake_cents,
        "dealer_seat": config.dealer_seat,
        "stacks": [list(row) for row in config.stacks],
        "flop": list(config.flop),
        "bbj_enabled": config.bbj_enabled,
        "rules_version": config.rules.version,
        "ranges": [
            {
                "seat": vector.seat,
                "hands": [list(hand) for hand in vector.hands],
                "weights": [
                    [weight.numerator, weight.denominator]
                    for weight in vector.weights
                ],
            }
            for vector in game.ranges
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sample_float_strategy_index(
    rng: random.Random,
    probabilities: Sequence[float],
) -> int:
    if not probabilities:
        raise HuMultiStreetCFRError("strategy sample support cannot be empty")
    if any(not math.isfinite(value) or value < 0.0 for value in probabilities):
        raise HuMultiStreetCFRError("strategy sample probabilities must be finite/nonnegative")
    total_float = math.fsum(probabilities)
    if total_float <= 0.0 or abs(total_float - 1.0) > 1e-12:
        raise HuMultiStreetCFRError("strategy sample probabilities must sum to one")
    exact = tuple(Fraction.from_float(value) for value in probabilities)
    total_exact = sum(exact, Fraction(0, 1))
    if total_exact <= 0:
        raise HuMultiStreetCFRError("strategy sample has zero exact binary64 mass")
    normalized = tuple(value / total_exact for value in exact)
    return sample_fraction_index(rng, normalized)


@dataclass
class _ExternalNode:
    actions: tuple[MicroAction, ...]
    regret_sum: list[float] = field(init=False)
    strategy_sum: list[float] = field(init=False)

    def __post_init__(self) -> None:
        if len(self.actions) < 2 or len(set(self.actions)) != len(self.actions):
            raise HuMultiStreetCFRError("external-sampling node requires unique multi-action support")
        self.regret_sum = [0.0] * len(self.actions)
        self.strategy_sum = [0.0] * len(self.actions)

    def current_strategy(self) -> tuple[float, ...]:
        positive = tuple(max(0.0, value) for value in self.regret_sum)
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
class _RegretDelta:
    actions: tuple[MicroAction, ...]
    values: list[float] = field(init=False)

    def __post_init__(self) -> None:
        self.values = [0.0] * len(self.actions)


@dataclass(frozen=True)
class ExternalSamplingStats:
    iterations: int
    sampled_deals: int
    sampled_public_chance: int
    sampled_opponent_actions: int
    sampled_average_target_actions: int
    regret_nodes_visited: int
    average_nodes_visited: int

    @property
    def nodes_visited(self) -> int:
        return self.regret_nodes_visited + self.average_nodes_visited


class HuMultiStreetExternalSamplingMCCFR:
    """Seeded external-sampling MCCFR for the F5 HU reference game."""

    def __init__(self, game: HuReferenceMicrogame, *, seed: int = 20260827) -> None:
        if not isinstance(game, HuReferenceMicrogame):
            raise HuMultiStreetCFRError("solver requires HuReferenceMicrogame")
        self.game = game
        self.seed = _validate_seed(seed)
        self.rng = random.Random(self.seed)
        self.nodes: dict[str, _ExternalNode] = {}
        self.iterations = 0
        self.sampled_deals = 0
        self.sampled_public_chance = 0
        self.sampled_opponent_actions = 0
        self.sampled_average_target_actions = 0
        self.regret_nodes_visited = 0
        self.average_nodes_visited = 0
        self._seats = tuple(sorted(seat for seat, _ in game.config.stacks))
        self._deal_probabilities = tuple(deal.probability for deal in game.deals)

    def _node(self, key: str, actions: tuple[MicroAction, ...]) -> _ExternalNode:
        node = self.nodes.get(key)
        if node is None:
            node = _ExternalNode(actions)
            self.nodes[key] = node
        elif node.actions != actions:
            raise HuMultiStreetCFRError("external-sampling infoset action support changed")
        return node

    @staticmethod
    def _delta(
        deltas: dict[str, _RegretDelta],
        key: str,
        actions: tuple[MicroAction, ...],
    ) -> _RegretDelta:
        delta = deltas.get(key)
        if delta is None:
            delta = _RegretDelta(actions)
            deltas[key] = delta
        elif delta.actions != actions:
            raise HuMultiStreetCFRError("external-sampling regret action support changed")
        return delta

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

    def _player_for_actor(self, branch: ExactBranchState) -> int:
        actor = branch.actor_seat
        if actor not in self._seats:
            raise HuMultiStreetCFRError("actor is outside HU solver seats")
        return self._seats.index(actor)

    def _terminal_utility(self, branch: ExactBranchState, player: int) -> float:
        settlement = branch.settle()
        utility = utility_from_settlement(
            branch.state,
            settlement,
            stake_cents=branch.stake_cents,
            rules=branch.rules,
        )
        value0 = float(utility.for_seat(self._seats[0]).gross_poker_delta_antes)
        if player == 0:
            return value0
        if player == 1:
            return -value0
        raise HuMultiStreetCFRError("HU traverser must be player 0 or 1")

    def _sample_chance_child(self, branch: ExactBranchState) -> ExactBranchState:
        outcomes = branch.chance_outcomes()
        if not outcomes:
            raise HuMultiStreetCFRError("chance node has empty support")
        index = sample_fraction_index(
            self.rng,
            tuple(outcome.probability for outcome in outcomes),
        )
        self.sampled_public_chance += 1
        return branch.apply_chance(outcomes[index].revealed)

    def _regret_traverse(
        self,
        branch: ExactBranchState,
        traverser: int,
        deltas: dict[str, _RegretDelta],
    ) -> float:
        self.regret_nodes_visited += 1
        if branch.node_kind == BranchNodeKind.TERMINAL:
            return self._terminal_utility(branch, traverser)
        if branch.node_kind == BranchNodeKind.CHANCE:
            return self._regret_traverse(
                self._sample_chance_child(branch),
                traverser,
                deltas,
            )

        strategic = self._strategic_state(branch)
        key = strategic.fingerprint()
        actions = self.game.abstract_actions(branch)
        if len(actions) == 1:
            return self._regret_traverse(
                self.game._apply_micro_action(branch, actions[0]),
                traverser,
                deltas,
            )
        node = self._node(key, actions)
        strategy = node.current_strategy()
        actor = self._player_for_actor(branch)

        if actor == traverser:
            action_values = [
                self._regret_traverse(
                    self.game._apply_micro_action(branch, action),
                    traverser,
                    deltas,
                )
                for action in actions
            ]
            node_value = math.fsum(
                strategy[index] * value
                for index, value in enumerate(action_values)
            )
            delta = self._delta(deltas, key, actions)
            for index, value in enumerate(action_values):
                delta.values[index] += value - node_value
            return node_value

        sampled = _sample_float_strategy_index(self.rng, strategy)
        self.sampled_opponent_actions += 1
        return self._regret_traverse(
            self.game._apply_micro_action(branch, actions[sampled]),
            traverser,
            deltas,
        )

    def _collect_average_strategy(
        self,
        branch: ExactBranchState,
        target_player: int,
    ) -> None:
        self.average_nodes_visited += 1
        if branch.node_kind == BranchNodeKind.TERMINAL:
            return
        if branch.node_kind == BranchNodeKind.CHANCE:
            self._collect_average_strategy(
                self._sample_chance_child(branch),
                target_player,
            )
            return

        strategic = self._strategic_state(branch)
        key = strategic.fingerprint()
        actions = self.game.abstract_actions(branch)
        if len(actions) == 1:
            self._collect_average_strategy(
                self.game._apply_micro_action(branch, actions[0]),
                target_player,
            )
            return
        node = self._node(key, actions)
        strategy = node.current_strategy()
        actor = self._player_for_actor(branch)

        if actor == target_player:
            for index, probability in enumerate(strategy):
                node.strategy_sum[index] += probability
            sampled = _sample_float_strategy_index(self.rng, strategy)
            self.sampled_average_target_actions += 1
            self._collect_average_strategy(
                self.game._apply_micro_action(branch, actions[sampled]),
                target_player,
            )
            return

        for action in actions:
            self._collect_average_strategy(
                self.game._apply_micro_action(branch, action),
                target_player,
            )

    def _sample_root(self) -> ExactBranchState:
        roots = self.game.root_branches()
        if len(roots) != len(self._deal_probabilities):
            raise HuMultiStreetCFRError("root/deal support drift")
        index = sample_fraction_index(self.rng, self._deal_probabilities)
        self.sampled_deals += 1
        return roots[index][1]

    def train(self, iterations: int) -> None:
        if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
            raise HuMultiStreetCFRError("iterations must be a positive integer")

        for _ in range(iterations):
            root = self._sample_root()
            deltas: dict[str, _RegretDelta] = {}

            # Synchronous regret snapshot: mutations wait until both traversers
            # and both average collectors have used the same current strategy.
            self._regret_traverse(root, 0, deltas)
            self._regret_traverse(root, 1, deltas)
            self._collect_average_strategy(root, 0)
            self._collect_average_strategy(root, 1)

            for key, delta in deltas.items():
                node = self.nodes[key]
                for index, value in enumerate(delta.values):
                    updated = node.regret_sum[index] + value
                    if not math.isfinite(updated):
                        raise HuMultiStreetCFRError("external-sampling regret became non-finite")
                    node.regret_sum[index] = updated
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

    def stats(self) -> ExternalSamplingStats:
        return ExternalSamplingStats(
            iterations=self.iterations,
            sampled_deals=self.sampled_deals,
            sampled_public_chance=self.sampled_public_chance,
            sampled_opponent_actions=self.sampled_opponent_actions,
            sampled_average_target_actions=self.sampled_average_target_actions,
            regret_nodes_visited=self.regret_nodes_visited,
            average_nodes_visited=self.average_nodes_visited,
        )

    def all_regrets_finite(self) -> bool:
        return all(
            math.isfinite(value)
            for node in self.nodes.values()
            for value in node.regret_sum
        )

    def state_dict(self) -> dict[str, object]:
        rows = []
        for key in sorted(self.nodes):
            node = self.nodes[key]
            rows.append(
                {
                    "key": key,
                    "actions": [action.value for action in node.actions],
                    "regret_hex": [value.hex() for value in node.regret_sum],
                    "strategy_hex": [value.hex() for value in node.strategy_sum],
                }
            )
        return {
            "schema": HU_MULTISTREET_EXTERNAL_SAMPLING_CHECKPOINT_SCHEMA,
            "solver_version": HU_MULTISTREET_EXTERNAL_SAMPLING_VERSION,
            "game_sha256": hu_external_sampling_game_fingerprint(self.game),
            "seed": self.seed,
            "iterations": self.iterations,
            "sampled_deals": self.sampled_deals,
            "sampled_public_chance": self.sampled_public_chance,
            "sampled_opponent_actions": self.sampled_opponent_actions,
            "sampled_average_target_actions": self.sampled_average_target_actions,
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
        game: HuReferenceMicrogame,
        payload: Mapping[str, object],
    ) -> "HuMultiStreetExternalSamplingMCCFR":
        expected = {
            "schema",
            "solver_version",
            "game_sha256",
            "seed",
            "iterations",
            "sampled_deals",
            "sampled_public_chance",
            "sampled_opponent_actions",
            "sampled_average_target_actions",
            "regret_nodes_visited",
            "average_nodes_visited",
            "rng_state",
            "nodes",
        }
        if set(payload) != expected:
            raise HuMultiStreetCFRError("external-sampling checkpoint keys differ from v1")
        if payload.get("schema") != HU_MULTISTREET_EXTERNAL_SAMPLING_CHECKPOINT_SCHEMA:
            raise HuMultiStreetCFRError("wrong external-sampling checkpoint schema")
        if payload.get("solver_version") != HU_MULTISTREET_EXTERNAL_SAMPLING_VERSION:
            raise HuMultiStreetCFRError("wrong external-sampling solver version")
        if payload.get("game_sha256") != hu_external_sampling_game_fingerprint(game):
            raise HuMultiStreetCFRError("external-sampling checkpoint/game mismatch")

        seed = payload.get("seed")
        trainer = cls(game, seed=seed)  # type: ignore[arg-type]
        counters = (
            "iterations",
            "sampled_deals",
            "sampled_public_chance",
            "sampled_opponent_actions",
            "sampled_average_target_actions",
            "regret_nodes_visited",
            "average_nodes_visited",
        )
        for name in counters:
            value = payload.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise HuMultiStreetCFRError(f"invalid checkpoint counter {name}")
            setattr(trainer, name, value)
        if trainer.sampled_deals != trainer.iterations:
            raise HuMultiStreetCFRError("sampled-deal count must equal iteration count")

        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list):
            raise HuMultiStreetCFRError("checkpoint nodes must be a list")
        seen: set[str] = set()
        for row in raw_nodes:
            if not isinstance(row, dict) or set(row) != {
                "key",
                "actions",
                "regret_hex",
                "strategy_hex",
            }:
                raise HuMultiStreetCFRError("malformed external-sampling checkpoint node")
            key = row["key"]
            if not isinstance(key, str) or len(key) != 64:
                raise HuMultiStreetCFRError("checkpoint infoset key must be SHA-256")
            try:
                int(key, 16)
            except ValueError as exc:
                raise HuMultiStreetCFRError("checkpoint infoset key is not hexadecimal") from exc
            if key in seen:
                raise HuMultiStreetCFRError("duplicate checkpoint infoset")
            seen.add(key)
            try:
                actions = tuple(MicroAction(value) for value in row["actions"])
            except (TypeError, ValueError) as exc:
                raise HuMultiStreetCFRError("invalid checkpoint action support") from exc
            if len(actions) < 2 or len(set(actions)) != len(actions):
                raise HuMultiStreetCFRError("checkpoint action support must be unique/multi-action")
            try:
                regrets = [float.fromhex(value) for value in row["regret_hex"]]
                strategies = [float.fromhex(value) for value in row["strategy_hex"]]
            except (TypeError, ValueError) as exc:
                raise HuMultiStreetCFRError("invalid checkpoint float encoding") from exc
            if len(regrets) != len(actions) or len(strategies) != len(actions):
                raise HuMultiStreetCFRError("checkpoint vector length differs from action support")
            if any(not math.isfinite(value) for value in regrets + strategies):
                raise HuMultiStreetCFRError("checkpoint contains non-finite accumulator")
            if any(value < 0.0 for value in strategies):
                raise HuMultiStreetCFRError("checkpoint strategy mass cannot be negative")
            node = _ExternalNode(actions)
            node.regret_sum = regrets
            node.strategy_sum = strategies
            trainer.nodes[key] = node

        try:
            trainer.rng.setstate(_nested_tuples(payload["rng_state"]))
        except (TypeError, ValueError) as exc:
            raise HuMultiStreetCFRError("invalid checkpoint RNG state") from exc
        return trainer

    @classmethod
    def from_checkpoint_json(
        cls,
        game: HuReferenceMicrogame,
        text: str,
    ) -> "HuMultiStreetExternalSamplingMCCFR":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HuMultiStreetCFRError("invalid external-sampling checkpoint JSON") from exc
        if not isinstance(payload, dict):
            raise HuMultiStreetCFRError("external-sampling checkpoint must be an object")
        return cls.from_state_dict(game, payload)
