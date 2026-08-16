"""Exact, configurable rake accounting for DeepSix.

Rake is part of game utility, so silently rounding or translating a published
rule into an unverified client convention would contaminate training targets.
This module therefore separates three layers:

1. eligibility (for example, no rake when a hand ends preflop);
2. the exact rational percentage/cap calculation; and
3. client rounding, which is intentionally *not* performed here.

All chip/pot values are integer table units. Percentage results are represented
as :class:`fractions.Fraction` so the Core never loses information before a
client-confirmed rounding policy is supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


class RakeError(ValueError):
    pass


@dataclass(frozen=True)
class RakeConfig:
    """Exact rake parameters in the table's integer unit.

    ``no_rake_at_or_below`` is inclusive. Set it to ``None`` when no small-pot
    exemption is configured.

    ``table_size_multiplier`` exists because some operators publish reduced
    rake for short-handed tables. It defaults to 1 and is deliberately not
    inferred from the number of active players.
    """

    rate: Fraction
    cap_units: int
    no_rake_at_or_below: int | None = None
    no_rake_preflop: bool = True
    table_size_multiplier: Fraction = Fraction(1, 1)

    def validate(self) -> None:
        if not isinstance(self.rate, Fraction):
            raise RakeError("rate must be fractions.Fraction")
        if self.rate < 0 or self.rate > 1:
            raise RakeError("rate must be within [0, 1]")
        if isinstance(self.cap_units, bool) or not isinstance(self.cap_units, int):
            raise RakeError("cap_units must be an integer")
        if self.cap_units < 0:
            raise RakeError("cap_units must be non-negative")
        if self.no_rake_at_or_below is not None:
            if (
                isinstance(self.no_rake_at_or_below, bool)
                or not isinstance(self.no_rake_at_or_below, int)
                or self.no_rake_at_or_below < 0
            ):
                raise RakeError("no_rake_at_or_below must be a non-negative integer")
        if not isinstance(self.table_size_multiplier, Fraction):
            raise RakeError("table_size_multiplier must be fractions.Fraction")
        if self.table_size_multiplier < 0 or self.table_size_multiplier > 1:
            raise RakeError("table_size_multiplier must be within [0, 1]")
        if not isinstance(self.no_rake_preflop, bool):
            raise RakeError("no_rake_preflop must be bool")


@dataclass(frozen=True)
class ExactRakeResult:
    gross_pot_units: int
    ended_preflop: bool
    eligible: bool
    exemption_reason: str | None
    percentage_rake: Fraction
    cap: Fraction
    rake_before_client_rounding: Fraction
    net_pot_before_client_rounding: Fraction

    @property
    def requires_rounding(self) -> bool:
        return self.rake_before_client_rounding.denominator != 1


def compute_exact_rake(
    gross_pot_units: int,
    *,
    ended_preflop: bool,
    config: RakeConfig,
) -> ExactRakeResult:
    """Compute exact designated rake without inventing a rounding convention."""
    config.validate()
    if isinstance(gross_pot_units, bool) or not isinstance(gross_pot_units, int):
        raise RakeError("gross_pot_units must be an integer")
    if gross_pot_units < 0:
        raise RakeError("gross_pot_units must be non-negative")
    if not isinstance(ended_preflop, bool):
        raise RakeError("ended_preflop must be bool")

    exemption_reason: str | None = None
    if config.no_rake_preflop and ended_preflop:
        exemption_reason = "preflop_end"
    elif (
        config.no_rake_at_or_below is not None
        and gross_pot_units <= config.no_rake_at_or_below
    ):
        exemption_reason = "small_pot"

    if exemption_reason is not None:
        rake = Fraction(0, 1)
        percentage = Fraction(0, 1)
        eligible = False
    else:
        eligible = True
        percentage = (
            Fraction(gross_pot_units, 1)
            * config.rate
            * config.table_size_multiplier
        )
        cap = Fraction(config.cap_units, 1)
        rake = min(percentage, cap)

    cap = Fraction(config.cap_units, 1)
    return ExactRakeResult(
        gross_pot_units=gross_pot_units,
        ended_preflop=ended_preflop,
        eligible=eligible,
        exemption_reason=exemption_reason,
        percentage_rake=percentage,
        cap=cap,
        rake_before_client_rounding=rake,
        net_pot_before_client_rounding=Fraction(gross_pot_units, 1) - rake,
    )


def shortdeck_percentage_cap_config(
    *,
    ante_units: int,
    cap_antes: int,
    no_rake_threshold_antes: int | None,
    rate: Fraction = Fraction(3, 100),
    table_size_multiplier: Fraction = Fraction(1, 1),
) -> RakeConfig:
    """Build a Short Deck percentage/cap model from explicit ante multiples.

    This helper deliberately requires the threshold multiple instead of
    translating an operator's potentially ambiguous ``BB`` terminology.  For
    example, if external evidence later proves that a published 5BB threshold
    means 10 antes, the caller should pass ``no_rake_threshold_antes=10``.
    """
    for name, value in (("ante_units", ante_units), ("cap_antes", cap_antes)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RakeError(f"{name} must be a positive integer")
    if no_rake_threshold_antes is not None:
        if (
            isinstance(no_rake_threshold_antes, bool)
            or not isinstance(no_rake_threshold_antes, int)
            or no_rake_threshold_antes < 0
        ):
            raise RakeError(
                "no_rake_threshold_antes must be a non-negative integer or None"
            )
    config = RakeConfig(
        rate=rate,
        cap_units=ante_units * cap_antes,
        no_rake_at_or_below=(
            None
            if no_rake_threshold_antes is None
            else ante_units * no_rake_threshold_antes
        ),
        no_rake_preflop=True,
        table_size_multiplier=table_size_multiplier,
    )
    config.validate()
    return config
