"""Chance-sampled float64 CFR foundation for DeepSix F5 HU.

This layer changes only the chance traversal axis relative to the full-tree
float solver: one private deal is sampled at the root and one public chance
outcome is sampled at each chance node, while *all player actions* remain
enumerated. Sampling is performed from exact Fraction distributions with a
seeded PRNG.

For vanilla CFR, removing the explicit chance-reach multiplier is deliberate:
when chance/private outcomes are sampled from their true distribution, the
visited counterfactual-regret and average-strategy updates are unbiased
estimators of the corresponding full-tree sums.

Opponent-action sampling (external-sampling MCCFR) is a later, separate axis.
Keeping this intermediate layer makes any future discrepancy diagnosable as
numeric, chance-sampling, or opponent-sampling error rather than mixing all
three at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import math
import random
from typing import Sequence

from deepsix_simulator.utility import utility_from_settlement

from .hu_multistreet_cfr import HuMultiStreetCFRError
from .hu_multistreet_float_cfr import FloatPolicyRow, FloatTabularPolicy
from .hu_multistreet_reference import HuReferenceMicrogame, MicroAction
from .multistreet_branch import BranchNodeKind, ExactBranchState
from .multistreet_state import PrivateDecisionState, decision_state_from_components


HU_MULTISTREET_CHANCE_SAMPLED_CFR_VERSION = (
    "deepsix_f5_chance_sampled_hu_cfr_2026-08-27_v1"
)


def _validate_algorithm_seed(seed: int) -> int:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise HuMultiStreetCFRError("algorithm_seed must be a non-negative integer")
    return seed


def _integer_weights(probabilities: Sequence[Fraction]) -> tuple[int, ...]:
    if not probabilities:
        raise HuMultiStreetCFRError("sample distribution cannot be empty")
    if any(not isinstance(value, Fraction) or value < 0 for value in probabilities):
        raise HuMultiStreetCFRError("sample probabilities must be non-negative Fractions")
    if sum(probabilities, Fraction(0, 1)) != 1:
        raise HuMultiStreetCFRError("sample probabilities must sum exactly to one")
    denominator = 1
    for value in probabilities:
        denominator = math.lcm(denominator, value.denominator)
    weights = tuple(value.numerator * (denominator // value.denominator) for value in probabilities)
    if sum(weights) != denominator or sum(weights) <= 0:
        raise HuMultiStreetCFRError("failed to integerize exact sample distribution")
    return weights


def sample_fraction_index(
    rng: random.Random,
    probabilities: Sequence[Fraction],
) -> int:
    """Draw exactly from a rational categorical distribution.

    ``randrange`` accepts arbitrary-size Python integers, so the correctness
    implementation does not need to convert probabilities to float. Large-scale
    trainers may later promote a faster alias/cumulative sampler only after
    parity benchmarking.
    """
    if not isinstance(rng, random.Random):
        raise HuMultiStreetCFRError("rng must be random.Random")
    weights = _integer_weights(tuple(probabilities))
    ticket = rng.randrange(sum(weights))
    cumulative = 0
    for index, weight in enumerate(weights):
        cumulative += weight
        if ticket < cumulative:
            return index
    raise HuMultiStreetCFRError("exact categorical sampler fell through support")


@dataclass
class _SampledNode:
    actions: tuple[MicroAction, ...]
    regrets: list[float] = field(init=False)
    strategy_sum: list[float] = field(init=False)

    def __post_init__(self) -> None:
        if len(self.actions) < 2 or len(set(self.actions)) != len(self.actions):
            raise HuMultiStreetCFRError("sampled CFR node requires unique multi-action support")
        self.regrets = [0.0] * len(self.actions)
        self.strategy_sum = [0.0] * len(self.actions)

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
class _SampledDelta:
    actions: tuple[MicroAction, ...]
    regrets: list[float] = field(init=False)
    strategy: list[float] = field(init=False)

    def __post_init__(self) -> None:
        self.regrets = [0.0] * len(self.actions)
        self.strategy = [0.0] * len(self.actions)


@dataclass(frozen=True)
class ChanceSampleStats:
    iterations: int
    private_deals_sampled: int
    public_chance_events_sampled: int
    terminal_visits: int


class ChanceSampledHuMultiStreetCFR:
    """Seeded vanilla CFR with exact categorical chance sampling."""

    def __init__(self, game: HuReferenceMicrogame, *, algorithm_seed: int) -> None:
        if not isinstance(game, HuReferenceMicrogame):
            raise HuMultiStreetCFRError("solver requires HuReferenceMicrogame")
        self.game = game
        self.algorithm_seed = _validate_algorithm_seed(algorithm_seed)
        self.rng = random.Random(self.algorithm_seed)
        self.nodes: dict[str, _SampledNode] = {}
        self.iterations = 0
        self.private_deals_sampled = 0
        self.public_chance_events_sampled = 0
        self.terminal_visits = 0
        self._seats = tuple(sorted(seat for seat, _ in game.config.stacks))
        self._deal_probabilities = tuple(deal.probability for deal in game.deals)

    def _node(self, key: str, actions: tuple[MicroAction, ...]) -> _SampledNode:
        node = self.nodes.get(key)
        if node is None:
            node = _SampledNode(actions)
            self.nodes[key] = node
        elif node.actions != actions:
            raise HuMultiStreetCFRError("sampled infoset action support changed")
        return node

    @staticmethod
    def _delta(
        deltas: dict[str, _SampledDelta],
        key: str,
        actions: tuple[MicroAction, ...],
    ) -> _SampledDelta:
        delta = deltas.get(key)
        if delta is None:
            delta = _SampledDelta(actions)
            deltas[key] = delta
        elif delta.actions != actions:
            raise HuMultiStreetCFRError("sampled iteration action support changed")
        return delta

    def _terminal_utility_p0(self, branch: ExactBranchState) -> float:
        self.terminal_visits += 1
        settlement = branch.settle()
        utility = utility_from_settlement(
            branch.state,
            settlement,
            stake_cents=branch.stake_cents,
            rules=branch.rules,
        )
        return float(utility.for_seat(self._seats[0]).gross_poker_delta_antes)

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

    def _sample_chance_child(self, branch: ExactBranchState) -> ExactBranchState:
        outcomes = branch.chance_outcomes()
        if not outcomes:
            raise HuMultiStreetCFRError("chance node has empty outcome support")
        index = sample_fraction_index(
            self.rng,
            tuple(outcome.probability for outcome in outcomes),
        )
        self.public_chance_events_sampled += 1
        return branch.apply_chance(outcomes[index].revealed)

    def _traverse(
        self,
        branch: ExactBranchState,
        *,
        reach0: float,
        reach1: float,
        deltas: dict[str, _SampledDelta],
    ) -> float:
        if branch.node_kind == BranchNodeKind.TERMINAL:
            return self._terminal_utility_p0(branch)
        if branch.node_kind == BranchNodeKind.CHANCE:
            return self._traverse(
                self._sample_chance_child(branch),
                reach0=reach0,
                reach1=reach1,
                deltas=deltas,
            )

        strategic = self._strategic_state(branch)
        key = strategic.fingerprint()
        actions = self.game.abstract_actions(branch)
        if len(actions) == 1:
            return self._traverse(
                self.game._apply_micro_action(branch, actions[0]),
                reach0=reach0,
                reach1=reach1,
                deltas=deltas,
            )

        node = self._node(key, actions)
        strategy = node.current_strategy()
        actor = branch.actor_seat
        if actor not in self._seats:
            raise HuMultiStreetCFRError("actor is outside HU solver seats")
        player = self._seats.index(actor)

        action_values: list[float] = []
        weighted: list[float] = []
        for index, action in enumerate(actions):
            child = self.game._apply_micro_action(branch, action)
            if player == 0:
                value = self._traverse(
                    child,
                    reach0=reach0 * strategy[index],
                    reach1=reach1,
                    deltas=deltas,
                )
            else:
                value = self._traverse(
                    child,
                    reach0=reach0,
                    reach1=reach1 * strategy[index],
                    deltas=deltas,
                )
            action_values.append(value)
            weighted.append(strategy[index] * value)
        node_value = math.fsum(weighted)

        delta = self._delta(deltas, key, actions)
        if player == 0:
            counterfactual_reach = reach1
            average_reach = reach0
            for index in range(len(actions)):
                delta.regrets[index] += counterfactual_reach * (
                    action_values[index] - node_value
                )
                delta.strategy[index] += average_reach * strategy[index]
        else:
            counterfactual_reach = reach0
            average_reach = reach1
            for index in range(len(actions)):
                delta.regrets[index] += counterfactual_reach * (
                    node_value - action_values[index]
                )
                delta.strategy[index] += average_reach * strategy[index]
        return node_value

    def _sample_root(self) -> ExactBranchState:
        roots = self.game.root_branches()
        if len(roots) != len(self._deal_probabilities):
            raise HuMultiStreetCFRError("root/deal support drift")
        index = sample_fraction_index(self.rng, self._deal_probabilities)
        self.private_deals_sampled += 1
        return roots[index][1]

    def train(self, iterations: int) -> None:
        if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
            raise HuMultiStreetCFRError("iterations must be a positive integer")
        for _ in range(iterations):
            deltas: dict[str, _SampledDelta] = {}
            self._traverse(
                self._sample_root(),
                reach0=1.0,
                reach1=1.0,
                deltas=deltas,
            )
            for key, delta in deltas.items():
                node = self.nodes[key]
                for index in range(len(node.actions)):
                    regret = node.regrets[index] + delta.regrets[index]
                    strategy_mass = node.strategy_sum[index] + delta.strategy[index]
                    if not math.isfinite(regret) or not math.isfinite(strategy_mass):
                        raise HuMultiStreetCFRError("sampled CFR produced non-finite state")
                    node.regrets[index] = regret
                    node.strategy_sum[index] = strategy_mass
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

    def stats(self) -> ChanceSampleStats:
        return ChanceSampleStats(
            iterations=self.iterations,
            private_deals_sampled=self.private_deals_sampled,
            public_chance_events_sampled=self.public_chance_events_sampled,
            terminal_visits=self.terminal_visits,
        )

    def semantic_snapshot(self) -> tuple:
        rng_digest = hashlib.sha256(repr(self.rng.getstate()).encode("utf-8")).hexdigest()
        return (
            HU_MULTISTREET_CHANCE_SAMPLED_CFR_VERSION,
            self.algorithm_seed,
            self.iterations,
            self.private_deals_sampled,
            self.public_chance_events_sampled,
            self.terminal_visits,
            rng_digest,
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
