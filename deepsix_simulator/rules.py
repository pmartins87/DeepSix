"""Versioned rules profile for the autonomous DeepSix Short Deck simulator.

The simulator deliberately separates *game semantics* from *operator economy*.
GGPoker is the current economic reference, while unresolved live-client details
are frozen here as explicit simulator conventions instead of being smuggled into
the generic Core.

Changing any convention below requires a new profile version. Historical runs
must continue to identify the exact profile that generated them.
"""

from __future__ import annotations

from dataclasses import dataclass

from deepsix_core.betting import BettingConfig, ShortAllInReopenPolicy
from deepsix_core.ggpoker_economy import ggpoker_shortdeck_stake
from deepsix_core.hand import HandConfig


SIMULATOR_RULES_VERSION = "deepsix_shortdeck_sim_rules_2026-08-25_v1"


class SimulatorRulesError(ValueError):
    pass


@dataclass(frozen=True)
class SimulatorRulesProfile:
    """Complete deterministic game-rule choices needed by the simulator.

    ``stake_unit_is_ante`` is an explicit simulator convention.  The public
    GGPoker table mixes blind/ante terminology; v1 maps the published stake
    denomination to one ante so that all monetary quantities remain exact cents.

    ``button_total_ante_multiple=2`` means every player posts one ante and the
    Button has two antes total.

    The minimum full-raise increment and postflop minimum bet are both two
    antes in v1.  This is a versioned simulation rule, not a claim about an
    undocumented live-client edge case.
    """

    version: str = SIMULATOR_RULES_VERSION
    stake_unit_is_ante: bool = True
    button_total_ante_multiple: int = 2
    preflop_full_raise_increment_antes: int = 2
    postflop_min_bet_antes: int = 2
    short_all_in_reopen: ShortAllInReopenPolicy = (
        ShortAllInReopenPolicy.CUMULATIVE_FULL_RAISE
    )
    allow_short_all_in_raise: bool = True
    odd_chip_clockwise_left_of_dealer: bool = True

    def validate(self) -> None:
        if self.version != SIMULATOR_RULES_VERSION:
            raise SimulatorRulesError(f"unsupported simulator rules version: {self.version}")
        if not self.stake_unit_is_ante:
            raise SimulatorRulesError("v1 requires stake denomination == ante unit")
        if self.button_total_ante_multiple != 2:
            raise SimulatorRulesError("v1 requires Button total contribution = 2 antes")
        if self.preflop_full_raise_increment_antes <= 0:
            raise SimulatorRulesError("preflop full-raise increment must be positive")
        if self.postflop_min_bet_antes <= 0:
            raise SimulatorRulesError("postflop minimum bet must be positive")
        if not isinstance(self.short_all_in_reopen, ShortAllInReopenPolicy):
            raise SimulatorRulesError("invalid short-all-in reopen policy")
        if not isinstance(self.allow_short_all_in_raise, bool):
            raise SimulatorRulesError("allow_short_all_in_raise must be bool")
        if not self.odd_chip_clockwise_left_of_dealer:
            raise SimulatorRulesError(
                "v1 freezes odd chips clockwise from the first seat left of Dealer"
            )

    def ante_units(self, stake_cents: int) -> int:
        self.validate()
        # Also validates that the stake exists in the date-versioned GGPoker table.
        ggpoker_shortdeck_stake(stake_cents)
        return stake_cents

    def hand_config(self, stake_cents: int) -> HandConfig:
        ante = self.ante_units(stake_cents)
        config = HandConfig(
            ante=ante,
            preflop_full_raise_increment=(
                ante * self.preflop_full_raise_increment_antes
            ),
            postflop_min_bet=ante * self.postflop_min_bet_antes,
            betting=BettingConfig(
                short_all_in_reopen=self.short_all_in_reopen,
                allow_short_all_in_raise=self.allow_short_all_in_raise,
            ),
        )
        config.validate()
        return config


DEFAULT_SIMULATOR_RULES = SimulatorRulesProfile()
