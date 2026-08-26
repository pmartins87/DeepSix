"""Exact per-seat utility vectors for DeepSix Simulator training/evaluation.

The adapter exposes two objects deliberately instead of pretending rake leaves a
zero-sum game:

* gross poker delta: awards before house deductions minus contributions;
* net cash delta: post-hand stack minus pre-hand stack.

Gross deltas sum to zero. Net deltas sum to minus rake/BBJ. A trainer must choose
which object its mathematical guarantees actually support; this module never
silently renormalizes away the house deduction.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from deepsix_core.hand import HandState

from .rules import DEFAULT_SIMULATOR_RULES, SimulatorRulesProfile
from .settlement import SimulatorSettlement, SimulatorSettlementError


SIMULATOR_UTILITY_VERSION = "deepsix_sim_utility_2026-08-25_v1"


@dataclass(frozen=True)
class SeatUtility:
    seat: int
    starting_stack_units: int
    committed_units: int
    gross_award_units: int
    house_charge_units: int
    net_award_units: int
    post_hand_stack_units: int
    gross_poker_delta_units: int
    net_cash_delta_units: int
    gross_poker_delta_antes: Fraction
    net_cash_delta_antes: Fraction


@dataclass(frozen=True)
class SimulatorUtilityVector:
    version: str
    rules_version: str
    economy_version: str
    settlement_version: str
    ante_units: int
    seats: tuple[SeatUtility, ...]
    total_house_deduction_units: int

    @property
    def gross_sum_units(self) -> int:
        return sum(item.gross_poker_delta_units for item in self.seats)

    @property
    def net_sum_units(self) -> int:
        return sum(item.net_cash_delta_units for item in self.seats)

    def for_seat(self, seat: int) -> SeatUtility:
        for item in self.seats:
            if item.seat == seat:
                return item
        raise SimulatorSettlementError(f"unknown utility seat {seat}")

    def validate(self) -> None:
        if self.version != SIMULATOR_UTILITY_VERSION:
            raise SimulatorSettlementError("unsupported simulator utility version")
        if self.ante_units <= 0:
            raise SimulatorSettlementError("utility ante unit must be positive")
        seat_ids = [item.seat for item in self.seats]
        if len(seat_ids) < 2 or len(seat_ids) > 6 or len(set(seat_ids)) != len(seat_ids):
            raise SimulatorSettlementError("utility requires 2..6 unique seats")
        if self.gross_sum_units != 0:
            raise SimulatorSettlementError("gross poker utility must be zero-sum")
        if self.net_sum_units != -self.total_house_deduction_units:
            raise SimulatorSettlementError(
                "net cash utility must sum to negative house deductions"
            )
        for item in self.seats:
            if item.starting_stack_units < 0 or item.committed_units < 0:
                raise SimulatorSettlementError("negative stack/contribution in utility")
            if item.gross_award_units < 0 or item.house_charge_units < 0:
                raise SimulatorSettlementError("negative award/charge in utility")
            if item.net_award_units < 0 or item.post_hand_stack_units < 0:
                raise SimulatorSettlementError("negative net award/post stack in utility")
            if item.gross_award_units - item.house_charge_units != item.net_award_units:
                raise SimulatorSettlementError("gross-charge != net award")
            if item.starting_stack_units - item.committed_units + item.net_award_units != item.post_hand_stack_units:
                raise SimulatorSettlementError("utility post-stack identity failed")
            if item.gross_poker_delta_units != item.gross_award_units - item.committed_units:
                raise SimulatorSettlementError("gross utility identity failed")
            if item.net_cash_delta_units != item.net_award_units - item.committed_units:
                raise SimulatorSettlementError("net utility identity failed")
            if item.gross_poker_delta_antes != Fraction(
                item.gross_poker_delta_units, self.ante_units
            ):
                raise SimulatorSettlementError("gross ante normalization mismatch")
            if item.net_cash_delta_antes != Fraction(
                item.net_cash_delta_units, self.ante_units
            ):
                raise SimulatorSettlementError("net ante normalization mismatch")


def utility_from_settlement(
    state: HandState,
    settlement: SimulatorSettlement,
    *,
    stake_cents: int,
    rules: SimulatorRulesProfile = DEFAULT_SIMULATOR_RULES,
) -> SimulatorUtilityVector:
    """Build exact gross and rake-aware utility for every dealt seat."""

    state.validate()
    rules.validate()
    if settlement.rules_version != rules.version:
        raise SimulatorSettlementError("settlement/rules version mismatch")
    if settlement.gross_pot_units != state.pot():
        raise SimulatorSettlementError("settlement/state pot mismatch")

    gross = dict(settlement.gross_awards)
    charges = dict(settlement.house_charges)
    net = dict(settlement.net_awards)
    post = dict(settlement.post_hand_stacks)
    state_seats = {player.seat for player in state.players}
    if set(gross) != state_seats or set(charges) != state_seats or set(net) != state_seats or set(post) != state_seats:
        raise SimulatorSettlementError("settlement utility seat set mismatch")

    ante = rules.ante_units(stake_cents)
    rows: list[SeatUtility] = []
    for player in sorted(state.players, key=lambda item: item.seat):
        starting = player.stack + player.committed_total
        gross_delta = gross[player.seat] - player.committed_total
        net_delta = net[player.seat] - player.committed_total
        rows.append(
            SeatUtility(
                seat=player.seat,
                starting_stack_units=starting,
                committed_units=player.committed_total,
                gross_award_units=gross[player.seat],
                house_charge_units=charges[player.seat],
                net_award_units=net[player.seat],
                post_hand_stack_units=post[player.seat],
                gross_poker_delta_units=gross_delta,
                net_cash_delta_units=net_delta,
                gross_poker_delta_antes=Fraction(gross_delta, ante),
                net_cash_delta_antes=Fraction(net_delta, ante),
            )
        )

    result = SimulatorUtilityVector(
        version=SIMULATOR_UTILITY_VERSION,
        rules_version=settlement.rules_version,
        economy_version=settlement.economy_version,
        settlement_version=settlement.settlement_version,
        ante_units=ante,
        seats=tuple(rows),
        total_house_deduction_units=settlement.deductions.total_units,
    )
    result.validate()
    return result
