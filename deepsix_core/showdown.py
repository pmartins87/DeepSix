"""Exact gross showdown settlement for a completed DeepSix hand.

The resolver combines the validated Short Deck evaluator with exact side-pot
layers.  It deliberately stops before site-specific rake and odd-chip rules:
when a pot layer ties, each winner receives an exact ``Fraction``.  This keeps
trainer/reference semantics mathematically lossless until KKPoker's real-client
odd-chip behavior is captured and frozen.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from .cards import ShortDeckCardError, decode_card
from .evaluator import HandValue, evaluate_best
from .hand import HandPhase, HandState
from .pots import PotAccountingError, PotLayer, build_pot_layers


class ShowdownError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedPotLayer:
    cap: int
    amount: int
    contributors: tuple[int, ...]
    eligible: tuple[int, ...]
    winners: tuple[int, ...]
    share_per_winner: Fraction


@dataclass(frozen=True)
class ShowdownResult:
    hand_values: tuple[tuple[int, HandValue], ...]
    layers: tuple[ResolvedPotLayer, ...]
    awards: tuple[tuple[int, Fraction], ...]

    def award_for(self, seat: int) -> Fraction:
        for known_seat, award in self.awards:
            if known_seat == seat:
                return award
        raise ShowdownError(f"unknown award seat {seat}")

    def total_awarded(self) -> Fraction:
        return sum((award for _, award in self.awards), Fraction(0, 1))


def resolve_gross_showdown_fractional(
    state: HandState,
    hole_cards: Mapping[int, tuple[int, int]],
) -> ShowdownResult:
    """Resolve every gross pot layer at showdown without rake/odd-chip rounding.

    Hole cards are required for every non-folded player.  Cards for folded
    players may be supplied for deal-integrity auditing but are not evaluated.
    All supplied cards are still required to be unique and valid Short Deck
    cards.
    """
    state.validate()
    if state.phase != HandPhase.SHOWDOWN:
        raise ShowdownError("showdown settlement requires SHOWDOWN phase")
    if len(state.board) != 5:
        raise ShowdownError("showdown requires five board cards")

    dealt = {player.seat for player in state.players}
    nonfolded = {player.seat for player in state.players if not player.folded}
    unknown = set(hole_cards) - dealt
    if unknown:
        raise ShowdownError(f"hole cards supplied for unknown seats: {sorted(unknown)}")
    missing = nonfolded - set(hole_cards)
    if missing:
        raise ShowdownError(f"missing hole cards for nonfolded seats: {sorted(missing)}")

    seen = set(state.board)
    try:
        for card in state.board:
            decode_card(card)
        for seat, cards in hole_cards.items():
            if len(cards) != 2:
                raise ShowdownError(f"seat {seat} must have exactly two hole cards")
            if cards[0] == cards[1]:
                raise ShowdownError(f"seat {seat} has duplicate hole cards")
            for card in cards:
                decode_card(card)
                if card in seen:
                    raise ShowdownError("duplicate known card across board/hole cards")
                seen.add(card)
    except ShortDeckCardError as exc:
        raise ShowdownError(str(exc)) from exc

    values = {
        seat: evaluate_best(tuple(hole_cards[seat]) + tuple(state.board))
        for seat in sorted(nonfolded)
    }
    contributions = {player.seat: player.committed_total for player in state.players}
    folded = {player.seat for player in state.players if player.folded}
    try:
        pot_layers: tuple[PotLayer, ...] = build_pot_layers(contributions, folded)
    except PotAccountingError as exc:
        raise ShowdownError(str(exc)) from exc

    awards = {seat: Fraction(0, 1) for seat in dealt}
    resolved_layers: list[ResolvedPotLayer] = []
    for layer in pot_layers:
        if not layer.eligible:
            raise ShowdownError("pot layer has no eligible player")
        best = max(values[seat] for seat in layer.eligible)
        winners = tuple(seat for seat in layer.eligible if values[seat] == best)
        if not winners:
            raise ShowdownError("pot layer produced no winner")
        share = Fraction(layer.amount, len(winners))
        for seat in winners:
            awards[seat] += share
        resolved_layers.append(
            ResolvedPotLayer(
                cap=layer.cap,
                amount=layer.amount,
                contributors=layer.contributors,
                eligible=layer.eligible,
                winners=winners,
                share_per_winner=share,
            )
        )

    result = ShowdownResult(
        hand_values=tuple((seat, values[seat]) for seat in sorted(values)),
        layers=tuple(resolved_layers),
        awards=tuple((seat, awards[seat]) for seat in sorted(awards)),
    )
    if result.total_awarded() != Fraction(state.pot(), 1):
        raise ShowdownError("showdown awards do not conserve the gross pot")
    return result
