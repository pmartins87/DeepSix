"""Frozen structural KKPoker 6+ rules that do not depend on stake economics."""

from __future__ import annotations


class GameRuleError(ValueError):
    pass


def validate_player_count(num_players: int) -> None:
    if isinstance(num_players, bool) or not isinstance(num_players, int):
        raise GameRuleError("num_players must be an integer")
    if num_players < 2 or num_players > 6:
        raise GameRuleError("KKPoker 6+ target supports 2..6 dealt players")


def action_order_from_dealer(num_players: int) -> tuple[int, ...]:
    """Return canonical action order when Dealer/Button is position 0.

    KKPoker 6+ starts with the player immediately left of the Dealer on every
    betting round, including preflop, and the Dealer acts last.
    """
    validate_player_count(num_players)
    return tuple(range(1, num_players)) + (0,)


def initial_ante_contributions(num_players: int, ante: int) -> tuple[int, ...]:
    """Return forced contributions with Dealer/Button at canonical position 0.

    Every player posts one ante and the Dealer posts a second ante, so the
    Dealer's total forced contribution is 2*ante and the starting pot is
    (num_players + 1) * ante.
    """
    validate_player_count(num_players)
    if isinstance(ante, bool) or not isinstance(ante, int) or ante <= 0:
        raise GameRuleError("ante must be a positive integer table unit")
    return (2 * ante,) + tuple(ante for _ in range(num_players - 1))
