import unittest
from dataclasses import replace

from deepsix_core.raw_hand_start import (
    HandStartEvidenceError,
    confirm_new_hand_from_exact_baseline,
    exact_forced_bet_baseline,
)
from deepsix_core.raw_reconstructor import ProjectedSeat, ProjectedSnapshot
from deepsix_core.state import Street


def make_seat(
    seat_id,
    *,
    balance=0,
    bet=0,
    seated=True,
    active=False,
    dealer=False,
    has_cards=False,
    all_in=False,
):
    return ProjectedSeat(
        seat=seat_id,
        raw_chair=seat_id,
        seated=seated,
        active=active,
        all_in=all_in,
        dealer=dealer,
        has_any_cards=has_cards,
        has_known_cards=False,
        balance=balance,
        current_bet=bet,
        stack_including_current_bet=balance + bet,
        hole_cards=(None, None),
    )


def exact_preflop(*, dealer=2, ante=1):
    seats = []
    for seat_id in range(6):
        dealt = seat_id in (0, 1, 2)
        bet = 0
        balance = 0
        if dealt:
            bet = ante * (2 if seat_id == dealer else 1)
            balance = 100 - bet
        seats.append(
            make_seat(
                seat_id,
                balance=balance,
                bet=bet,
                active=dealt,
                dealer=(seat_id == dealer),
                has_cards=dealt,
            )
        )
    return ProjectedSnapshot(
        source_audit_fingerprint="preflop",
        street=Street.PREFLOP,
        dealer_seat=dealer,
        hero_seat=0,
        hero_myturnbits=0,
        hero_sitting_in=True,
        board=(),
        seats=tuple(seats),
        pots=(4, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    )


def river(*, dealer=1):
    base = exact_preflop(dealer=dealer)
    cleared = tuple(
        replace(
            seat,
            current_bet=0,
            stack_including_current_bet=seat.balance,
        )
        for seat in base.seats
    )
    return replace(
        base,
        source_audit_fingerprint="river",
        street=Street.RIVER,
        board=(0, 5, 10, 15, 20),
        seats=cleared,
    )


class RawHandStartEvidenceTests(unittest.TestCase):
    def test_exact_three_hand_forced_pattern_matches(self):
        evidence = exact_forced_bet_baseline(exact_preflop(), ante=1)
        self.assertTrue(evidence.matched, evidence.reason)
        self.assertEqual(evidence.dealt_seats, (0, 1, 2))

    def test_first_call_already_made_no_longer_matches_baseline(self):
        snap = exact_preflop()
        acted = replace(
            snap.seats[0],
            balance=98,
            current_bet=2,
            stack_including_current_bet=100,
        )
        snap = replace(snap, seats=(acted,) + snap.seats[1:])
        evidence = exact_forced_bet_baseline(snap, ante=1)
        self.assertFalse(evidence.matched)
        self.assertIn("forced contribution", evidence.reason)

    def test_waiting_non_dealt_seat_may_be_seated_but_cannot_have_bet(self):
        snap = exact_preflop()
        waiting = replace(snap.seats[4], seated=True, balance=50)
        snap = replace(snap, seats=snap.seats[:4] + (waiting,) + snap.seats[5:])
        self.assertTrue(exact_forced_bet_baseline(snap, ante=1).matched)

        bad_waiting = replace(waiting, current_bet=1, stack_including_current_bet=51)
        bad = replace(snap, seats=snap.seats[:4] + (bad_waiting,) + snap.seats[5:])
        evidence = exact_forced_bet_baseline(bad, ante=1)
        self.assertFalse(evidence.matched)
        self.assertIn("non-dealt", evidence.reason)

    def test_clipped_forced_allin_is_deliberately_not_proven_by_v1(self):
        snap = exact_preflop()
        short = replace(
            snap.seats[0],
            balance=0,
            current_bet=1,
            stack_including_current_bet=1,
            all_in=True,
        )
        snap = replace(snap, seats=(short,) + snap.seats[1:])
        evidence = exact_forced_bet_baseline(snap, ante=1)
        self.assertFalse(evidence.matched)
        self.assertIn("clipped", evidence.reason)

    def test_postflop_or_nonempty_board_cannot_match(self):
        snap = replace(exact_preflop(), street=Street.FLOP, board=(0, 5, 10))
        evidence = exact_forced_bet_baseline(snap, ante=1)
        self.assertFalse(evidence.matched)
        self.assertIn("preflop", evidence.reason)

    def test_invalid_configuration_rejected(self):
        with self.assertRaises(HandStartEvidenceError):
            exact_forced_bet_baseline(exact_preflop(), ante=0)
        with self.assertRaises(HandStartEvidenceError):
            exact_forced_bet_baseline(exact_preflop(), ante=1, dealer_total_antes=1)

    def test_river_reset_plus_dealer_move_plus_exact_baseline_confirms(self):
        before = river(dealer=1)
        after = exact_preflop(dealer=2)
        evidence = confirm_new_hand_from_exact_baseline(before, after, ante=1)
        self.assertTrue(evidence.matched, evidence.reason)
        self.assertIn("confirm new hand", evidence.reason)

    def test_same_dealer_does_not_confirm_new_hand(self):
        before = river(dealer=2)
        after = exact_preflop(dealer=2)
        evidence = confirm_new_hand_from_exact_baseline(before, after, ante=1)
        self.assertFalse(evidence.matched)
        self.assertIn("Dealer did not move", evidence.reason)

    def test_board_reset_with_already_acted_preflop_is_not_confirmed(self):
        before = river(dealer=1)
        after = exact_preflop(dealer=2)
        acted = replace(
            after.seats[0],
            balance=98,
            current_bet=2,
            stack_including_current_bet=100,
        )
        after = replace(after, seats=(acted,) + after.seats[1:])
        evidence = confirm_new_hand_from_exact_baseline(before, after, ante=1)
        self.assertFalse(evidence.matched)
        self.assertIn("forced contribution", evidence.reason)


if __name__ == "__main__":
    unittest.main()
