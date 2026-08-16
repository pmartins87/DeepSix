import unittest
from dataclasses import replace

from deepsix_core.raw_reconstructor import ProjectedSeat, ProjectedSnapshot
from deepsix_core.raw_timeline import (
    RawEvidenceTimeline,
    TimelineEventKind,
    TimelineInferenceError,
    infer_unique_money_action,
)
from deepsix_core.state import ActionKind, Street


def seat(
    seat_id,
    *,
    balance=100,
    bet=0,
    active=True,
    all_in=False,
    seated=True,
    dealer=False,
):
    return ProjectedSeat(
        seat=seat_id,
        raw_chair=seat_id,
        seated=seated,
        active=active,
        all_in=all_in,
        dealer=dealer,
        has_any_cards=True,
        has_known_cards=False,
        balance=balance,
        current_bet=bet,
        stack_including_current_bet=balance + bet,
        hole_cards=(None, None),
    )


def snapshot(
    seats,
    *,
    street=Street.PREFLOP,
    board=(),
    pots=(10, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    hero_bits=0,
    hero_sitting=True,
    dealer=2,
):
    normalized = tuple(
        replace(player, dealer=(player.seat == dealer)) for player in seats
    )
    return ProjectedSnapshot(
        source_audit_fingerprint="fixture",
        street=street,
        dealer_seat=dealer,
        hero_seat=0,
        hero_myturnbits=hero_bits,
        hero_sitting_in=hero_sitting,
        board=tuple(board),
        seats=normalized,
        pots=tuple(pots),
    )


def exact_start(*, dealer=2):
    bets = {0: 1, 1: 1, 2: 1}
    bets[dealer] = 2
    return snapshot(
        tuple(seat(i, balance=100 - bets[i], bet=bets[i]) for i in range(3)),
        street=Street.PREFLOP,
        dealer=dealer,
    )


class RawTimelineInferenceTests(unittest.TestCase):
    def base_preflop(self):
        return snapshot(
            (
                seat(0, balance=98, bet=2),
                seat(1, balance=94, bet=6),
                seat(2, balance=94, bet=6),
            )
        )

    def test_exact_single_seat_call_is_inferred(self):
        before = self.base_preflop()
        after = replace(
            before,
            seats=(
                seat(0, balance=94, bet=6),
                before.seats[1],
                before.seats[2],
            ),
        )
        action, reason = infer_unique_money_action(before, after, seq=7)
        self.assertIsNotNone(action, reason)
        self.assertEqual(action.seq, 7)
        self.assertEqual(action.actor_seat, 0)
        self.assertEqual(action.action, ActionKind.CALL)
        self.assertEqual(action.paid, 4)
        self.assertEqual(action.prior_table_bet, 6)
        self.assertIsNone(action.amount_to)

    def test_exact_short_allin_call_below_price_is_inferred(self):
        before = snapshot(
            (
                seat(0, balance=3, bet=2),
                seat(1, balance=94, bet=6),
                seat(2, balance=94, bet=6),
            )
        )
        after_actor = seat(0, balance=0, bet=5, all_in=True)
        after = replace(
            before,
            seats=(after_actor, before.seats[1], before.seats[2]),
        )
        action, reason = infer_unique_money_action(before, after)
        self.assertIsNotNone(action, reason)
        self.assertEqual(action.action, ActionKind.CALL)
        self.assertEqual(action.resulting_actor_bet, 5)
        self.assertTrue(action.all_in)

    def test_exact_raise_to_is_inferred(self):
        before = self.base_preflop()
        after = replace(
            before,
            seats=(
                seat(0, balance=90, bet=10),
                before.seats[1],
                before.seats[2],
            ),
        )
        action, reason = infer_unique_money_action(before, after)
        self.assertIsNotNone(action, reason)
        self.assertEqual(action.action, ActionKind.RAISE_TO)
        self.assertEqual(action.amount_to, 10)
        self.assertEqual(action.paid, 8)

    def test_opening_postflop_bet_uses_raise_to_core_semantics(self):
        before = snapshot(
            (seat(0), seat(1), seat(2)),
            street=Street.FLOP,
            board=(0, 5, 10),
        )
        after = replace(
            before,
            seats=(
                seat(0, balance=96, bet=4),
                before.seats[1],
                before.seats[2],
            ),
        )
        action, reason = infer_unique_money_action(before, after)
        self.assertIsNotNone(action, reason)
        self.assertEqual(action.action, ActionKind.RAISE_TO)
        self.assertEqual(action.prior_table_bet, 0)
        self.assertEqual(action.amount_to, 4)

    def test_two_money_changing_seats_are_ambiguous(self):
        before = self.base_preflop()
        after = replace(
            before,
            seats=(
                seat(0, balance=94, bet=6),
                seat(1, balance=90, bet=10),
                before.seats[2],
            ),
        )
        action, reason = infer_unique_money_action(before, after)
        self.assertIsNone(action)
        self.assertIn("exactly one", reason)

    def test_pot_delta_blocks_action_inference(self):
        before = self.base_preflop()
        after = replace(
            before,
            seats=(
                seat(0, balance=94, bet=6),
                before.seats[1],
                before.seats[2],
            ),
            pots=(14, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        )
        action, reason = infer_unique_money_action(before, after)
        self.assertIsNone(action)
        self.assertIn("pot", reason)

    def test_balance_bet_nonconservation_blocks_inference(self):
        before = self.base_preflop()
        bad_actor = replace(
            before.seats[0],
            balance=93,
            current_bet=6,
            stack_including_current_bet=99,
        )
        after = replace(before, seats=(bad_actor, before.seats[1], before.seats[2]))
        action, reason = infer_unique_money_action(before, after)
        self.assertIsNone(action)
        self.assertTrue("balance" in reason or "stack" in reason)

    def test_fold_flag_delta_is_not_inferred_as_fold(self):
        before = self.base_preflop()
        folded = replace(before.seats[0], active=False, has_any_cards=False)
        after = replace(before, seats=(folded, before.seats[1], before.seats[2]))
        action, reason = infer_unique_money_action(before, after)
        self.assertIsNone(action)
        self.assertIn("active/card-presence", reason)

    def test_visible_button_delta_is_not_inferred_as_check(self):
        before = replace(self.base_preflop(), hero_myturnbits=0x04)
        after = replace(before, hero_myturnbits=0)
        action, reason = infer_unique_money_action(before, after)
        self.assertIsNone(action)
        self.assertIn("exactly one", reason)

    def test_timeline_emits_baseline_action_and_street_advance(self):
        timeline = RawEvidenceTimeline()
        before = self.base_preflop()
        baseline = timeline.push(before)
        self.assertEqual(baseline.kind, TimelineEventKind.BASELINE)
        self.assertFalse(timeline.complete_from_hand_start)

        called = replace(
            before,
            seats=(
                seat(0, balance=94, bet=6),
                before.seats[1],
                before.seats[2],
            ),
        )
        event = timeline.push(called)
        self.assertEqual(event.kind, TimelineEventKind.ACTION)
        self.assertEqual(event.action.seq, 0)
        self.assertEqual(event.action.action, ActionKind.CALL)
        self.assertIsNone(event.action.hand_index)

        flop_seats = tuple(
            replace(player, current_bet=0, stack_including_current_bet=player.balance)
            for player in called.seats
        )
        flop = replace(
            called,
            street=Street.FLOP,
            board=(0, 5, 10),
            seats=flop_seats,
        )
        event = timeline.push(flop)
        self.assertEqual(event.kind, TimelineEventKind.STREET_ADVANCE)
        self.assertEqual(len(timeline.inferred_actions), 1)

    def test_exact_forced_baseline_starts_complete_hand_epoch(self):
        timeline = RawEvidenceTimeline(ante_units=1)
        before = exact_start(dealer=2)
        event = timeline.push(before)
        self.assertEqual(event.kind, TimelineEventKind.HAND_START)
        self.assertEqual(event.hand_index, 0)
        self.assertTrue(timeline.complete_from_hand_start)
        self.assertEqual(timeline.current_hand_index, 0)

        called = replace(
            before,
            seats=(
                seat(0, balance=98, bet=2),
                before.seats[1],
                before.seats[2],
            ),
        )
        action_event = timeline.push(called)
        self.assertEqual(action_event.kind, TimelineEventKind.ACTION)
        self.assertEqual(action_event.action.seq, 0)
        self.assertEqual(action_event.action.hand_index, 0)
        self.assertTrue(timeline.complete_from_hand_start)

    def test_confirmed_new_hand_resets_action_sequence_and_restores_completeness(self):
        timeline = RawEvidenceTimeline(ante_units=1)
        first = exact_start(dealer=2)
        self.assertEqual(timeline.push(first).kind, TimelineEventKind.HAND_START)

        # Skip directly to a river fixture. That intentionally taints the first
        # hand, but the next exact hand-start proof must recover independently.
        river = snapshot(
            (seat(0), seat(1), seat(2)),
            street=Street.RIVER,
            board=(0, 5, 10, 15, 20),
            dealer=2,
        )
        self.assertEqual(timeline.push(river).kind, TimelineEventKind.AMBIGUOUS)
        self.assertFalse(timeline.complete_from_hand_start)

        second = exact_start(dealer=0)
        start_event = timeline.push(second)
        self.assertEqual(start_event.kind, TimelineEventKind.HAND_START)
        self.assertEqual(start_event.hand_index, 1)
        self.assertTrue(timeline.complete_from_hand_start)

        called = replace(
            second,
            seats=(
                second.seats[0],
                seat(1, balance=98, bet=2),
                second.seats[2],
            ),
        )
        action_event = timeline.push(called)
        self.assertEqual(action_event.kind, TimelineEventKind.ACTION)
        self.assertEqual(action_event.action.seq, 0)
        self.assertEqual(action_event.action.hand_index, 1)

    def test_invalid_timeline_ante_configuration_is_rejected(self):
        with self.assertRaises(TimelineInferenceError):
            RawEvidenceTimeline(ante_units=0)

    def test_ambiguous_delta_remains_ambiguous(self):
        timeline = RawEvidenceTimeline()
        before = self.base_preflop()
        timeline.push(before)
        changed = replace(before, hero_myturnbits=0x04)
        event = timeline.push(changed)
        self.assertEqual(event.kind, TimelineEventKind.AMBIGUOUS)
        self.assertEqual(timeline.inferred_actions, ())

    def test_board_reset_is_only_hand_boundary_candidate_without_ante_config(self):
        river = snapshot(
            (seat(0), seat(1), seat(2)),
            street=Street.RIVER,
            board=(0, 5, 10, 15, 20),
            dealer=2,
        )
        next_preflop = snapshot(
            (
                seat(0, bet=1, balance=99),
                seat(1, bet=1, balance=99),
                seat(2, bet=2, balance=98),
            ),
            street=Street.PREFLOP,
            dealer=0,
        )
        timeline = RawEvidenceTimeline()
        timeline.push(river)
        event = timeline.push(next_preflop)
        self.assertEqual(event.kind, TimelineEventKind.HAND_BOUNDARY_CANDIDATE)
        self.assertIn("candidate", event.reason)

    def test_mutated_same_street_board_is_ambiguous(self):
        before = snapshot(
            (seat(0), seat(1), seat(2)),
            street=Street.FLOP,
            board=(0, 5, 10),
        )
        after = replace(before, board=(0, 5, 11))
        timeline = RawEvidenceTimeline()
        timeline.push(before)
        event = timeline.push(after)
        self.assertEqual(event.kind, TimelineEventKind.AMBIGUOUS)


if __name__ == "__main__":
    unittest.main()
