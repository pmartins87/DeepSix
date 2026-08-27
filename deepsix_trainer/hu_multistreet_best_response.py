"""Exact dynamic best response for the F5 HU multi-street reference game.

The best responder may condition on its own private cards and every public event,
but never on the opponent's hidden cards.  To preserve that information-set
constraint, this module carries a *weighted set of compatible fixed-private
worlds* through the public tree:

* at a BR node, every hidden world in the same infoset must take the same action;
* at an opponent node, each hidden world is split by that opponent hand's fixed
  mixed strategy;
* at a chance node, worlds are grouped by the same public reveal and weighted by
  the exact physical chance probability;
* at terminal nodes, exact gross P0 utility is weighted and summed.

The root is handled separately for each BR private hand, so the responder is
allowed to choose a different plan for each hand it actually observes.  Deal
weights retain their original joint probability; they are not renormalized by
own hand, which makes the final sum the unconditional best-response value.

This is the multi-street analogue of DeepSix's gated river dynamic best-response
oracle.  It is intentionally exact and slow enough to serve as a convergence
judge for full-tree and sampled trainer candidates on tractable F5 games.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from deepsix_simulator.utility import utility_from_settlement

from .hu_multistreet_reference import (
    GROSS_POKER_DELTA,
    HuReferenceMicrogame,
    HuReferenceMicrogameError,
    MicroAction,
    MicroPolicy,
)
from .multistreet_branch import BranchNodeKind, ExactBranchState
from .multistreet_state import decision_state_from_components


HU_MULTISTREET_EXACT_BR_VERSION = "deepsix_f5_hu_exact_dynamic_br_2026-08-27_v1"


class HuMultiStreetBestResponseError(ValueError):
    pass


@dataclass(frozen=True)
class WeightedBranch:
    branch: ExactBranchState
    weight: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.branch, ExactBranchState):
            raise HuMultiStreetBestResponseError("weighted world requires ExactBranchState")
        if not isinstance(self.weight, Fraction) or self.weight < 0:
            raise HuMultiStreetBestResponseError("weighted world requires non-negative Fraction")


def _exact_probability(value) -> Fraction:
    if isinstance(value, bool):
        raise HuMultiStreetBestResponseError("boolean is not a policy probability")
    if isinstance(value, Fraction):
        probability = value
    elif isinstance(value, int):
        probability = Fraction(value, 1)
    else:
        raise HuMultiStreetBestResponseError(
            "best-response oracle requires exact int/Fraction opponent policy"
        )
    if probability < 0:
        raise HuMultiStreetBestResponseError("policy probability cannot be negative")
    return probability


def _policy_distribution(
    policy: MicroPolicy,
    branch: ExactBranchState,
    actions: tuple[MicroAction, ...],
) -> tuple[Fraction, ...]:
    actor = branch.actor_seat
    if actor is None:
        raise HuMultiStreetBestResponseError("policy requested outside decision node")
    strategic = decision_state_from_components(
        branch.state,
        actor_hole_cards=branch.hole_cards_mapping()[actor],
        stake_cents=branch.stake_cents,
        rules=branch.rules,
        bbj_enabled=branch.bbj_enabled,
    )
    raw = policy(strategic, actions)
    if not isinstance(raw, Mapping) or set(raw) != set(actions):
        raise HuMultiStreetBestResponseError("opponent policy must cover exact action support")
    probabilities = tuple(_exact_probability(raw[action]) for action in actions)
    if sum(probabilities, Fraction(0, 1)) != 1:
        raise HuMultiStreetBestResponseError("opponent policy probabilities must sum to one")
    return probabilities


def _common_state(weighted: tuple[WeightedBranch, ...]):
    if not weighted:
        raise HuMultiStreetBestResponseError("weighted world set cannot be empty")
    state = weighted[0].branch.state
    for item in weighted[1:]:
        if item.branch.state != state:
            raise HuMultiStreetBestResponseError(
                "weighted worlds at one recursion point differ in public HandState"
            )
    return state


def _terminal_p0_value(weighted: tuple[WeightedBranch, ...]) -> Fraction:
    total = Fraction(0, 1)
    for item in weighted:
        settlement = item.branch.settle()
        utility = utility_from_settlement(
            item.branch.state,
            settlement,
            stake_cents=item.branch.stake_cents,
            rules=item.branch.rules,
        )
        seats = tuple(sorted(seat for seat, _ in item.branch.hole_cards))
        p0 = seats[0]
        total += item.weight * utility.for_seat(p0).gross_poker_delta_antes
    return total


def _apply_same_action(
    game: HuReferenceMicrogame,
    weighted: tuple[WeightedBranch, ...],
    action: MicroAction,
) -> tuple[WeightedBranch, ...]:
    return tuple(
        WeightedBranch(game._apply_micro_action(item.branch, action), item.weight)
        for item in weighted
        if item.weight > 0
    )


def _weighted_value(
    game: HuReferenceMicrogame,
    opponent_policy: MicroPolicy,
    br_player: int,
    weighted: tuple[WeightedBranch, ...],
) -> Fraction:
    if not weighted:
        return Fraction(0, 1)
    state = _common_state(weighted)
    node_kind = weighted[0].branch.node_kind
    if any(item.branch.node_kind != node_kind for item in weighted):
        raise HuMultiStreetBestResponseError("weighted worlds disagree on node kind")

    if node_kind == BranchNodeKind.TERMINAL:
        return _terminal_p0_value(weighted)

    if node_kind == BranchNodeKind.CHANCE:
        # Group by the same observable public reveal.  Some reveals are absent
        # in worlds where an opponent privately blocks that card; weighting the
        # surviving worlds by physical chance handles range-conditioned removal
        # without revealing which hidden world actually occurred.
        groups: dict[tuple[int, ...], list[WeightedBranch]] = {}
        for item in weighted:
            outcomes = item.branch.chance_outcomes()
            for outcome in outcomes:
                if outcome.probability <= 0:
                    continue
                child = item.branch.apply_chance(outcome.revealed)
                groups.setdefault(tuple(outcome.revealed), []).append(
                    WeightedBranch(child, item.weight * outcome.probability)
                )
        return sum(
            (
                _weighted_value(
                    game,
                    opponent_policy,
                    br_player,
                    tuple(rows),
                )
                for _, rows in sorted(groups.items())
            ),
            Fraction(0, 1),
        )

    first = weighted[0].branch
    actions = game.abstract_actions(first)
    for item in weighted[1:]:
        if game.abstract_actions(item.branch) != actions:
            raise HuMultiStreetBestResponseError("hidden world changed public action support")
    if len(actions) == 1:
        return _weighted_value(
            game,
            opponent_policy,
            br_player,
            _apply_same_action(game, weighted, actions[0]),
        )

    actor_seat = first.actor_seat
    if actor_seat is None:
        raise HuMultiStreetBestResponseError("decision node missing actor")
    seats = tuple(sorted(seat for seat, _ in game.config.stacks))
    if actor_seat not in seats:
        raise HuMultiStreetBestResponseError("decision actor outside HU seats")
    actor = seats.index(actor_seat)

    if actor == br_player:
        # Information-set safety gate: BR private state must be identical across
        # all hidden opponent worlds before one common action is selected.
        fingerprints = set()
        for item in weighted:
            actor_hole = item.branch.hole_cards_mapping()[actor_seat]
            strategic = decision_state_from_components(
                item.branch.state,
                actor_hole_cards=actor_hole,
                stake_cents=item.branch.stake_cents,
                rules=item.branch.rules,
                bbj_enabled=item.branch.bbj_enabled,
            )
            fingerprints.add(strategic.fingerprint())
        if len(fingerprints) != 1:
            raise HuMultiStreetBestResponseError(
                "best-response node merged distinct responder infosets"
            )
        child_values = tuple(
            _weighted_value(
                game,
                opponent_policy,
                br_player,
                _apply_same_action(game, weighted, action),
            )
            for action in actions
        )
        return max(child_values) if br_player == 0 else min(child_values)

    total = Fraction(0, 1)
    for action_index, action in enumerate(actions):
        child_rows: list[WeightedBranch] = []
        for item in weighted:
            probabilities = _policy_distribution(
                opponent_policy,
                item.branch,
                actions,
            )
            probability = probabilities[action_index]
            if probability > 0:
                child_rows.append(
                    WeightedBranch(
                        game._apply_micro_action(item.branch, action),
                        item.weight * probability,
                    )
                )
        if child_rows:
            total += _weighted_value(
                game,
                opponent_policy,
                br_player,
                tuple(child_rows),
            )
    return total


def _best_response_value_p0_utility(
    game: HuReferenceMicrogame,
    opponent_policy: MicroPolicy,
    br_player: int,
) -> Fraction:
    if not isinstance(game, HuReferenceMicrogame):
        raise HuMultiStreetBestResponseError("best response requires HuReferenceMicrogame")
    if br_player not in (0, 1):
        raise HuMultiStreetBestResponseError("br_player must be 0 or 1")

    seats = tuple(sorted(seat for seat, _ in game.config.stacks))
    own_seat = seats[br_player]
    grouped: dict[tuple[int, int], list[WeightedBranch]] = {}
    for deal, root in game.root_branches():
        own_cards = deal.mapping()[own_seat]
        grouped.setdefault(tuple(sorted(own_cards)), []).append(
            WeightedBranch(root, deal.probability)
        )

    total = Fraction(0, 1)
    for _, rows in sorted(grouped.items()):
        total += _weighted_value(
            game,
            opponent_policy,
            br_player,
            tuple(rows),
        )
    return total


def best_response_value_player0_exact(
    game: HuReferenceMicrogame,
    opponent_policy: MicroPolicy,
) -> Fraction:
    """Maximum gross P0 utility against the fixed player-1 policy."""
    return _best_response_value_p0_utility(game, opponent_policy, 0)


def best_response_value_player1_exact(
    game: HuReferenceMicrogame,
    opponent_policy: MicroPolicy,
) -> Fraction:
    """Minimum gross P0 utility achievable by player 1's best response."""
    return _best_response_value_p0_utility(game, opponent_policy, 1)


def exploitability_exact(
    game: HuReferenceMicrogame,
    policy: MicroPolicy,
) -> Fraction:
    """Exact two-player zero-sum exploitability in ante units."""
    br0 = best_response_value_player0_exact(game, policy)
    br1_as_p0 = best_response_value_player1_exact(game, policy)
    result = (br0 - br1_as_p0) / 2
    if result < 0:
        raise HuMultiStreetBestResponseError("exact exploitability became negative")
    return result
