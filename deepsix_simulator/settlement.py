"""Deterministic integer settlement for the DeepSix autonomous simulator.

The generic Core intentionally stops at exact fractional gross showdown awards.
A runnable cash-game simulator needs one more layer: odd chips, rake rounding,
operator deductions and post-hand stacks.  This module freezes those choices for
our simulator while keeping them visibly separate from claims about a live
client.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from deepsix_core.ggpoker_economy import (
    GGPOKER_SHORTDECK_ECONOMY_VERSION,
    ggpoker_shortdeck_bbj_contribution,
    ggpoker_shortdeck_rake_config,
)
from deepsix_core.hand import HandPhase, HandState, fold_winner
from deepsix_core.rake import compute_exact_rake
from deepsix_core.showdown import ShowdownResult, resolve_gross_showdown_fractional

from .rules import DEFAULT_SIMULATOR_RULES, SimulatorRulesProfile


SIMULATOR_SETTLEMENT_VERSION = "deepsix_sim_settlement_2026-08-25_v1"


class SimulatorSettlementError(ValueError):
    pass


@dataclass(frozen=True)
class HouseDeductions:
    exact_rake_before_rounding: Fraction
    rounded_rake_units: int
    bbj_units: int
    total_units: int


@dataclass(frozen=True)
class SimulatorSettlement:
    settlement_version: str
    economy_version: str
    rules_version: str
    gross_pot_units: int
    gross_awards: tuple[tuple[int, int], ...]
    house_charges: tuple[tuple[int, int], ...]
    net_awards: tuple[tuple[int, int], ...]
    post_hand_stacks: tuple[tuple[int, int], ...]
    deductions: HouseDeductions
    showdown: ShowdownResult | None

    def net_award_for(self, seat: int) -> int:
        for known, value in self.net_awards:
            if known == seat:
                return value
        raise SimulatorSettlementError(f"unknown seat {seat}")

    def post_hand_stack_for(self, seat: int) -> int:
        for known, value in self.post_hand_stacks:
            if known == seat:
                return value
        raise SimulatorSettlementError(f"unknown seat {seat}")


def _floor_fraction(value: Fraction) -> int:
    if value < 0:
        raise SimulatorSettlementError("cannot floor a negative monetary value")
    return value.numerator // value.denominator


def _action_order_rank(state: HandState) -> dict[int, int]:
    return {seat: index for index, seat in enumerate(state.action_order)}


def _integer_gross_awards_from_showdown(
    state: HandState,
    showdown: ShowdownResult,
) -> dict[int, int]:
    """Split every gross layer in integer units using the v1 odd-chip rule."""

    awards = {player.seat: 0 for player in state.players}
    order_rank = _action_order_rank(state)
    for layer in showdown.layers:
        winners = sorted(layer.winners, key=lambda seat: order_rank[seat])
        if not winners:
            raise SimulatorSettlementError("showdown layer has no winners")
        base, odd = divmod(layer.amount, len(winners))
        for seat in winners:
            awards[seat] += base
        for seat in winners[:odd]:
            awards[seat] += 1
    if sum(awards.values()) != state.pot():
        raise SimulatorSettlementError("integer gross awards do not conserve pot")
    return awards


def _gross_awards(
    state: HandState,
    hole_cards: Mapping[int, tuple[int, int]],
) -> tuple[dict[int, int], ShowdownResult | None]:
    if state.phase == HandPhase.TERMINAL_FOLD:
        winner = fold_winner(state)
        if winner is None:
            raise SimulatorSettlementError("fold terminal missing winner")
        awards = {player.seat: 0 for player in state.players}
        awards[winner] = state.pot()
        return awards, None
    if state.phase == HandPhase.SHOWDOWN:
        showdown = resolve_gross_showdown_fractional(state, hole_cards)
        return _integer_gross_awards_from_showdown(state, showdown), showdown
    raise SimulatorSettlementError("hand must be terminal before settlement")


def _allocate_house_charge_pro_rata(
    total_charge: int,
    gross_awards: Mapping[int, int],
    *,
    state: HandState,
) -> dict[int, int]:
    """Allocate an aggregate house deduction to winners by largest remainder.

    This is a simulator convention that avoids inventing operator-specific
    main-pot/side-pot rake attribution.  It preserves the exact aggregate rake
    and gives a deterministic integer result suitable for bankroll accounting.
    """

    if total_charge < 0:
        raise SimulatorSettlementError("negative house charge")
    gross = sum(gross_awards.values())
    if gross != state.pot():
        raise SimulatorSettlementError("gross awards differ from hand pot")
    if total_charge > gross:
        raise SimulatorSettlementError("house charge exceeds gross pot")
    charges = {seat: 0 for seat in gross_awards}
    if total_charge == 0 or gross == 0:
        return charges

    exact = {
        seat: Fraction(total_charge * award, gross)
        for seat, award in gross_awards.items()
        if award > 0
    }
    for seat, value in exact.items():
        charges[seat] = _floor_fraction(value)
    remaining = total_charge - sum(charges.values())
    order_rank = _action_order_rank(state)
    ranked = sorted(
        exact,
        key=lambda seat: (
            -(exact[seat] - charges[seat]),
            order_rank[seat],
        ),
    )
    for seat in ranked[:remaining]:
        charges[seat] += 1

    if sum(charges.values()) != total_charge:
        raise SimulatorSettlementError("house-charge allocation failed conservation")
    if any(charges[seat] > gross_awards[seat] for seat in charges):
        raise SimulatorSettlementError("house charge exceeds a seat's gross award")
    return charges


def settle_terminal_hand(
    state: HandState,
    hole_cards: Mapping[int, tuple[int, int]],
    *,
    stake_cents: int,
    bbj_enabled: bool = True,
    rules: SimulatorRulesProfile = DEFAULT_SIMULATOR_RULES,
) -> SimulatorSettlement:
    """Settle one terminal simulator hand into exact integer post-hand stacks.

    Rake is the date-versioned GGPoker reference profile.  The exact fractional
    rake is rounded *down to the simulator's integer monetary unit* in v1.
    Jackpot contribution is then added as a separate deduction when enabled.
    Both choices are simulator semantics and are versioned here.
    """

    state.validate()
    rules.validate()
    if not isinstance(bbj_enabled, bool):
        raise SimulatorSettlementError("bbj_enabled must be bool")
    if state.phase not in (HandPhase.SHOWDOWN, HandPhase.TERMINAL_FOLD):
        raise SimulatorSettlementError("cannot settle a nonterminal hand")

    gross_awards, showdown = _gross_awards(state, hole_cards)
    gross_pot = state.pot()
    dealt_players = len(state.players)
    rake_config = ggpoker_shortdeck_rake_config(
        stake_cents=stake_cents,
        dealt_players=dealt_players,
    )
    ended_preflop = (
        state.phase == HandPhase.TERMINAL_FOLD and state.street.value == "preflop"
    )
    rake_result = compute_exact_rake(
        gross_pot,
        ended_preflop=ended_preflop,
        config=rake_config,
    )
    rounded_rake = _floor_fraction(rake_result.rake_before_client_rounding)
    ante_units = rules.ante_units(stake_cents)
    bbj = (
        ggpoker_shortdeck_bbj_contribution(gross_pot, ante_units=ante_units)
        if bbj_enabled
        else 0
    )
    total_deduction = rounded_rake + bbj
    if total_deduction > gross_pot:
        raise SimulatorSettlementError("configured deductions exceed pot")

    charges = _allocate_house_charge_pro_rata(
        total_deduction,
        gross_awards,
        state=state,
    )
    net_awards = {
        seat: gross_awards[seat] - charges[seat]
        for seat in gross_awards
    }
    post_stacks = {
        player.seat: player.stack + net_awards[player.seat]
        for player in state.players
    }

    expected_player_total = state.initial_total_chips - total_deduction
    if sum(post_stacks.values()) != expected_player_total:
        raise SimulatorSettlementError("post-hand bankroll conservation failed")
    if sum(net_awards.values()) != gross_pot - total_deduction:
        raise SimulatorSettlementError("net awards do not match distributable pot")

    seats = sorted(gross_awards)
    return SimulatorSettlement(
        settlement_version=SIMULATOR_SETTLEMENT_VERSION,
        economy_version=GGPOKER_SHORTDECK_ECONOMY_VERSION,
        rules_version=rules.version,
        gross_pot_units=gross_pot,
        gross_awards=tuple((seat, gross_awards[seat]) for seat in seats),
        house_charges=tuple((seat, charges[seat]) for seat in seats),
        net_awards=tuple((seat, net_awards[seat]) for seat in seats),
        post_hand_stacks=tuple((seat, post_stacks[seat]) for seat in seats),
        deductions=HouseDeductions(
            exact_rake_before_rounding=rake_result.rake_before_client_rounding,
            rounded_rake_units=rounded_rake,
            bbj_units=bbj,
            total_units=total_deduction,
        ),
        showdown=showdown,
    )
