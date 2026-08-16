"""Polynomial exact best response for the multi-size + one-raise river game.

The v1 auditor enumerates every pure response plan for one private hand.  That
is excellent as an independent oracle at S<=2, but the count grows as
``(1+S)*6**S`` and would eventually make validation itself the bottleneck.

This module computes the same exact best response by dynamic programming over
information sets.  For one fixed BR private hand, the state carries a weighted
set of compatible chance deals.  The weights contain chance probability and
opponent realization reach only:

* at a BR node, the same action must be chosen for all opponent deals in that
  infoset, so the algorithm evaluates every legal action on the *same* weighted
  deal set and takes max/min;
* at an opponent node, each deal is split by that opponent hand's mixed
  strategy, then child weighted values are summed;
* at a terminal node, exact configured utility is weighted and summed.

This is the standard perfect-recall best-response idea specialized to the tiny
river tree.  It is exact, avoids enumerating complete pure plans, and is gated
against the independent enumerative oracle before it can replace that oracle
for larger action sets.
"""

from __future__ import annotations

from dataclasses import dataclass

from .river_multisize_one_raise import (
    History,
    MultiSizeOneRaiseDeal,
    RiverMultiSizeOneRaiseConfig,
    RiverMultiSizeOneRaisePolicy,
    is_terminal,
    legal_actions,
    player_to_act,
    terminal_utility_p0,
)


class DynamicBestResponseError(ValueError):
    pass


@dataclass(frozen=True)
class WeightedDeal:
    deal: MultiSizeOneRaiseDeal
    weight: float


def _weighted_value(
    config: RiverMultiSizeOneRaiseConfig,
    opponent: RiverMultiSizeOneRaisePolicy,
    br_player: int,
    weighted_deals: tuple[WeightedDeal, ...],
    history: History = (),
) -> float:
    if not weighted_deals:
        return 0.0
    if is_terminal(config, history):
        return sum(
            item.weight * terminal_utility_p0(config, item.deal, history)
            for item in weighted_deals
        )

    actor = player_to_act(config, history)
    actions = legal_actions(config, history)
    if actor == br_player:
        child_values = tuple(
            _weighted_value(
                config,
                opponent,
                br_player,
                weighted_deals,
                history + (action,),
            )
            for action in actions
        )
        return max(child_values) if br_player == 0 else min(child_values)

    branch_values = 0.0
    for action_index, action in enumerate(actions):
        child: list[WeightedDeal] = []
        for item in weighted_deals:
            cards = item.deal.p0_cards if actor == 0 else item.deal.p1_cards
            strategy = opponent.strategy(config, actor, cards, history)
            probability = strategy[action_index]
            if probability > 0.0:
                child.append(
                    WeightedDeal(item.deal, item.weight * probability)
                )
        if child:
            branch_values += _weighted_value(
                config,
                opponent,
                br_player,
                tuple(child),
                history + (action,),
            )
    return branch_values


def _best_response_value(
    config: RiverMultiSizeOneRaiseConfig,
    opponent: RiverMultiSizeOneRaisePolicy,
    br_player: int,
) -> float:
    config.validate()
    if br_player not in (0, 1):
        raise DynamicBestResponseError("br_player must be 0 or 1")
    deals = config.compatible_deals()
    own_range = config.p0_range if br_player == 0 else config.p1_range
    total = 0.0
    for hand in own_range:
        cards = hand.canonical_cards()
        hand_deals = tuple(
            WeightedDeal(deal, deal.probability)
            for deal in deals
            if (deal.p0_cards if br_player == 0 else deal.p1_cards) == cards
        )
        if hand_deals:
            total += _weighted_value(
                config,
                opponent,
                br_player,
                hand_deals,
            )
    return total


def best_response_value_player0_dp(
    config: RiverMultiSizeOneRaiseConfig,
    opponent: RiverMultiSizeOneRaisePolicy,
) -> float:
    return _best_response_value(config, opponent, 0)


def best_response_value_player1_dp(
    config: RiverMultiSizeOneRaiseConfig,
    opponent: RiverMultiSizeOneRaisePolicy,
) -> float:
    """Minimum P0 utility achievable by P1's exact best response."""
    return _best_response_value(config, opponent, 1)


def exploitability_dp(
    config: RiverMultiSizeOneRaiseConfig,
    policy: RiverMultiSizeOneRaisePolicy,
) -> float:
    br0 = best_response_value_player0_dp(config, policy)
    br1_as_p0 = best_response_value_player1_dp(config, policy)
    return (br0 - br1_as_p0) / 2.0
