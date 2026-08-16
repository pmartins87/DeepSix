"""Pot and side-pot accounting primitives independent from hand ranking/rake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet, Mapping


class PotAccountingError(ValueError):
    pass


@dataclass(frozen=True)
class PotLayer:
    """One main/side-pot layer created by contribution caps."""

    cap: int
    amount: int
    contributors: tuple[int, ...]
    eligible: tuple[int, ...]


def build_pot_layers(
    contributions: Mapping[int, int], folded: AbstractSet[int] = frozenset()
) -> tuple[PotLayer, ...]:
    """Build exact main/side-pot layers from total hand contributions.

    Folded chips remain in the pot but folded players are removed from eligibility.
    The function does not distribute tied/odd chips; site-specific odd-chip rules
    remain a separate unresolved settlement concern.
    """
    if not contributions:
        return ()

    normalized: dict[int, int] = {}
    for seat, amount in contributions.items():
        if isinstance(seat, bool) or not isinstance(seat, int) or seat < 0:
            raise PotAccountingError(f"invalid seat: {seat!r}")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise PotAccountingError(f"invalid contribution for seat {seat}: {amount!r}")
        normalized[seat] = amount

    unknown_folded = set(folded) - set(normalized)
    if unknown_folded:
        raise PotAccountingError(f"folded seats absent from contributions: {sorted(unknown_folded)}")

    levels = sorted({amount for amount in normalized.values() if amount > 0})
    layers: list[PotLayer] = []
    previous = 0
    for level in levels:
        contributors = tuple(sorted(seat for seat, amount in normalized.items() if amount >= level))
        amount = (level - previous) * len(contributors)
        eligible = tuple(seat for seat in contributors if seat not in folded)
        if amount <= 0:
            raise PotAccountingError("non-positive pot layer generated")
        if not eligible:
            raise PotAccountingError(
                f"pot layer at cap {level} has no non-folded eligible player"
            )
        layers.append(
            PotLayer(
                cap=level,
                amount=amount,
                contributors=contributors,
                eligible=eligible,
            )
        )
        previous = level

    if sum(layer.amount for layer in layers) != sum(normalized.values()):
        raise PotAccountingError("pot layers do not conserve contributions")
    return tuple(layers)
