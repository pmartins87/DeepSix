"""Legal-action view over a validated TableObservation.

This module intentionally does not infer KKPoker's minimum-raise rule yet.
`TableObservation.min_raise_to` and `max_raise_to` are a boundary contract: the
runtime or game engine must provide the actual legal raise-to interval. DeepSix
then validates that interval against Hero's stack and exposes unambiguous
semantic actions.
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import TableObservation


class LegalActionError(ValueError):
    pass


@dataclass(frozen=True)
class LegalActionSet:
    can_fold: bool
    can_check: bool
    can_call: bool
    call_amount: int
    can_raise: bool
    min_raise_to: int
    max_raise_to: int

    def is_raise_to_legal(self, amount_to: int) -> bool:
        return (
            self.can_raise
            and isinstance(amount_to, int)
            and not isinstance(amount_to, bool)
            and self.min_raise_to <= amount_to <= self.max_raise_to
        )


def legal_actions_for_hero(observation: TableObservation) -> LegalActionSet:
    """Return Hero's legal semantic action window for an observed decision."""
    observation.validate()
    hero = next(seat for seat in observation.seats if seat.seat == observation.hero_seat)
    if not hero.dealt or hero.folded or hero.all_in or hero.stack <= 0:
        raise LegalActionError("hero is not in a state that can make a decision")

    to_call = observation.to_call
    if to_call == 0:
        can_fold = False
        can_check = True
        can_call = False
        call_amount = 0
    else:
        can_fold = True
        can_check = False
        can_call = True
        call_amount = min(to_call, hero.stack)

    call_target = hero.committed_street + call_amount
    max_stack_target = hero.committed_street + hero.stack
    min_raise_to = observation.min_raise_to
    max_raise_to = observation.max_raise_to

    if min_raise_to == 0 and max_raise_to == 0:
        can_raise = False
    else:
        if min_raise_to <= 0 or max_raise_to <= 0:
            raise LegalActionError("raise bounds must both be zero or both be positive")
        if min_raise_to > max_raise_to:
            raise LegalActionError("min_raise_to cannot exceed max_raise_to")
        if min_raise_to <= call_target:
            raise LegalActionError("raise-to minimum must exceed the call/check target")
        if max_raise_to > max_stack_target:
            raise LegalActionError("raise-to maximum exceeds Hero's stack target")
        can_raise = max_raise_to > call_target

    return LegalActionSet(
        can_fold=can_fold,
        can_check=can_check,
        can_call=can_call,
        call_amount=call_amount,
        can_raise=can_raise,
        min_raise_to=min_raise_to if can_raise else 0,
        max_raise_to=max_raise_to if can_raise else 0,
    )
