"""Exact hand-start evidence for OH6Plus projected snapshots.

This module provides a deliberately strict proof candidate for the first stable
preflop state of a KKPoker-style Short Deck hand.  It does not guess from a
board reset alone.  Instead, under an explicit ante configuration, it requires
the complete forced-contribution pattern to be visible simultaneously:

* every dealt player has cards and is active;
* every non-Dealer dealt player has exactly one ante committed;
* the Dealer has exactly ``dealer_total_antes`` committed (currently 2 in the
  frozen DeepSix rule model);
* no waiting/non-dealt mapped seat has a current bet;
* visible stack accounting is exact.

If real-client captures show a different scraper timing, this detector should
remain strict and a separately versioned detector should encode the observed
semantics.  Do not weaken this proof merely to increase coverage.
"""

from __future__ import annotations

from dataclasses import dataclass

from .raw_reconstructor import ProjectedSnapshot, RawTransitionKind, classify_raw_transition
from .state import Street


class HandStartEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class HandStartEvidence:
    matched: bool
    dealt_seats: tuple[int, ...]
    ante: int
    dealer_total_antes: int
    reason: str


def exact_forced_bet_baseline(
    snapshot: ProjectedSnapshot,
    *,
    ante: int,
    dealer_total_antes: int = 2,
) -> HandStartEvidence:
    """Return whether one snapshot proves the exact pre-action forced baseline."""
    if isinstance(ante, bool) or not isinstance(ante, int) or ante <= 0:
        raise HandStartEvidenceError("ante must be a positive integer")
    if (
        isinstance(dealer_total_antes, bool)
        or not isinstance(dealer_total_antes, int)
        or dealer_total_antes < 2
    ):
        raise HandStartEvidenceError("dealer_total_antes must be an integer >= 2")

    def fail(reason: str, dealt: tuple[int, ...] = ()) -> HandStartEvidence:
        return HandStartEvidence(False, dealt, ante, dealer_total_antes, reason)

    if snapshot.street != Street.PREFLOP or snapshot.board:
        return fail("snapshot is not an empty-board preflop state")
    if not snapshot.seats:
        return fail("snapshot has no mapped seats")

    dealt = tuple(
        seat.seat
        for seat in snapshot.seats
        if seat.seated and seat.has_any_cards
    )
    if len(dealt) < 2 or len(dealt) > 6:
        return fail("exact hand start requires 2..6 dealt seats", dealt)
    if snapshot.dealer_seat not in dealt:
        return fail("Dealer does not have dealt-card evidence", dealt)

    dealer_flags = tuple(seat.seat for seat in snapshot.seats if seat.dealer)
    if dealer_flags != (snapshot.dealer_seat,):
        return fail("Dealer engine/seat flag is not uniquely consistent", dealt)

    for seat in snapshot.seats:
        is_dealt = seat.seat in dealt
        if is_dealt:
            if not seat.active:
                return fail(f"dealt seat {seat.seat} is not active", dealt)
            if seat.all_in:
                return fail(
                    f"dealt seat {seat.seat} is already all-in; v1 exact baseline "
                    "does not prove clipped forced bets",
                    dealt,
                )
            expected = ante * (
                dealer_total_antes if seat.seat == snapshot.dealer_seat else 1
            )
            if seat.current_bet != expected:
                return fail(
                    f"seat {seat.seat} current_bet={seat.current_bet} != exact "
                    f"forced contribution {expected}",
                    dealt,
                )
            if seat.stack_including_current_bet != seat.balance + seat.current_bet:
                return fail(
                    f"seat {seat.seat} visible stack accounting is not exact",
                    dealt,
                )
        else:
            if seat.current_bet != 0:
                return fail(
                    f"non-dealt mapped seat {seat.seat} has a current bet",
                    dealt,
                )
            if seat.has_known_cards:
                return fail(
                    f"non-dealt mapped seat {seat.seat} exposes known cards",
                    dealt,
                )

    return HandStartEvidence(
        True,
        dealt,
        ante,
        dealer_total_antes,
        "exact preflop forced-contribution baseline observed",
    )


def confirm_new_hand_from_exact_baseline(
    previous: ProjectedSnapshot,
    current: ProjectedSnapshot,
    *,
    ante: int,
    dealer_total_antes: int = 2,
) -> HandStartEvidence:
    """Confirm a new hand only when reset + Dealer movement + exact baseline agree."""
    transition = classify_raw_transition(previous, current)
    baseline = exact_forced_bet_baseline(
        current,
        ante=ante,
        dealer_total_antes=dealer_total_antes,
    )
    if transition.kind != RawTransitionKind.HAND_BOUNDARY_CANDIDATE:
        return HandStartEvidence(
            False,
            baseline.dealt_seats,
            ante,
            dealer_total_antes,
            f"transition is {transition.kind.value}, not a hand-boundary candidate",
        )
    if current.dealer_seat == previous.dealer_seat:
        return HandStartEvidence(
            False,
            baseline.dealt_seats,
            ante,
            dealer_total_antes,
            "Dealer did not move across candidate hand boundary",
        )
    if not baseline.matched:
        return baseline
    return HandStartEvidence(
        True,
        baseline.dealt_seats,
        ante,
        dealer_total_antes,
        "board reset, Dealer movement and exact forced baseline jointly confirm new hand",
    )
