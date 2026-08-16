"""Date-versioned GGPoker Short Deck economy profile for the DeepSix simulator.

This module intentionally models the *published* GGPoker Short Deck cash-game
economy rather than a live-client integration.  The strategic target is an
offline/self-play simulator whose rake/cap schedule mirrors the current public
GGPoker table as observed on 2026-08-16.

Important boundaries:

* the published Short Deck table lists a 5% rake and player-count-dependent
  caps;
* some high-stakes caps are published in BB rather than dollars, so this module
  stores the exact dollar-equivalent cents for the listed stakes;
* the public Short Deck table does not state a preflop or small-pot exemption.
  The simulator profile therefore applies the published 5%/cap rule on every
  pot by default.  This is a simulator convention, not a claim about an
  undocumented live-client exception;
* client rounding is deliberately not guessed.  ``RakeConfig`` continues to
  return exact ``Fraction`` values before rounding;
* the current Bad Beat Jackpot contribution is represented separately because
  it is a promotional/economic deduction, not poker hand strength.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .rake import RakeConfig, RakeError


GGPOKER_SHORTDECK_ECONOMY_VERSION = "ggpoker_shortdeck_cash_2026-08-16_v1"
GGPOKER_SHORTDECK_RAKE_RATE = Fraction(5, 100)
GGPOKER_SHORTDECK_BBJ_THRESHOLD_ANTES = 100
GGPOKER_SHORTDECK_BBJ_CONTRIBUTION_ANTES = 1


@dataclass(frozen=True)
class GGPokerShortDeckStake:
    """One published GGPoker Short Deck cash stake.

    ``stake_cents`` preserves the value shown in the public table's stake/blind
    column without silently deciding whether the UI calls that unit an ante or
    a blind.  The simulator can map its forced-bet unit to this denomination in
    the game-rule profile.
    """

    stake_cents: int
    default_buy_in_cents: int
    cap_2p_cents: int
    cap_3p_cents: int
    cap_4p_cents: int
    cap_5plus_cents: int

    def cap_for_players(self, dealt_players: int) -> int:
        if isinstance(dealt_players, bool) or not isinstance(dealt_players, int):
            raise RakeError("dealt_players must be an integer")
        if dealt_players < 2 or dealt_players > 6:
            raise RakeError("GGPoker Short Deck dealt_players must be within [2, 6]")
        if dealt_players == 2:
            return self.cap_2p_cents
        if dealt_players == 3:
            return self.cap_3p_cents
        if dealt_players == 4:
            return self.cap_4p_cents
        return self.cap_5plus_cents


# Public GGPoker Short Deck table observed 2026-08-16.
# High-stakes caps are published as 0.38/0.75/1.13/1.5 BB for 2/3/4/5+
# players; the cent values below are exact products for each listed stake.
GGPOKER_SHORTDECK_STAKES: tuple[GGPokerShortDeckStake, ...] = (
    GGPokerShortDeckStake(2, 80, 2, 3, 5, 6),
    GGPokerShortDeckStake(5, 200, 4, 8, 11, 15),
    GGPokerShortDeckStake(10, 400, 8, 15, 23, 30),
    GGPokerShortDeckStake(25, 1000, 13, 25, 38, 50),
    GGPokerShortDeckStake(50, 2000, 25, 50, 75, 100),
    GGPokerShortDeckStake(100, 4000, 50, 100, 150, 200),
    GGPokerShortDeckStake(200, 8000, 76, 150, 226, 300),
    GGPokerShortDeckStake(500, 20000, 190, 375, 565, 750),
    GGPokerShortDeckStake(1000, 50000, 380, 750, 1130, 1500),
)

_STAKE_BY_CENTS = {stake.stake_cents: stake for stake in GGPOKER_SHORTDECK_STAKES}


def ggpoker_shortdeck_stake(stake_cents: int) -> GGPokerShortDeckStake:
    if isinstance(stake_cents, bool) or not isinstance(stake_cents, int):
        raise RakeError("stake_cents must be an integer")
    try:
        return _STAKE_BY_CENTS[stake_cents]
    except KeyError as exc:
        raise RakeError(f"unsupported published GGPoker Short Deck stake: {stake_cents}") from exc


def ggpoker_shortdeck_rake_config(
    *,
    stake_cents: int,
    dealt_players: int,
) -> RakeConfig:
    """Return the current published-table simulator rake profile.

    No undocumented preflop/small-pot exemption is invented.  Rounding remains
    outside this profile and is handled by the exact-rake boundary.
    """

    stake = ggpoker_shortdeck_stake(stake_cents)
    config = RakeConfig(
        rate=GGPOKER_SHORTDECK_RAKE_RATE,
        cap_units=stake.cap_for_players(dealt_players),
        no_rake_at_or_below=None,
        no_rake_preflop=False,
        table_size_multiplier=Fraction(1, 1),
    )
    config.validate()
    return config


def ggpoker_shortdeck_bbj_contribution(
    gross_pot_units: int,
    *,
    ante_units: int,
) -> int:
    """Return the current Short Deck Bad Beat Jackpot contribution.

    The current public GGPoker jackpot page states that Short Deck contributes
    one ante when the pot is at least 100 antes.  The caller chooses the integer
    table unit; the function never converts currency implicitly.
    """

    for name, value in (("gross_pot_units", gross_pot_units), ("ante_units", ante_units)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise RakeError(f"{name} must be an integer")
    if gross_pot_units < 0:
        raise RakeError("gross_pot_units must be non-negative")
    if ante_units <= 0:
        raise RakeError("ante_units must be positive")
    threshold = GGPOKER_SHORTDECK_BBJ_THRESHOLD_ANTES * ante_units
    if gross_pot_units >= threshold:
        return GGPOKER_SHORTDECK_BBJ_CONTRIBUTION_ANTES * ante_units
    return 0
