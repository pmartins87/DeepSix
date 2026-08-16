import unittest

from deepsix_core.betting import (
    BettingConfig,
    BettingPlayer,
    BettingStateError,
    ShortAllInReopenPolicy,
    apply_action,
    legal_actions,
    round_chip_total,
    start_betting_round,
)
from deepsix_core.state import ActionKind, Street


class BettingRoundTests(unittest.TestCase):
    def _three_way_preflop(self, *, policy=ShortAllInReopenPolicy.NEVER):
        # Action order is left of Dealer through Dealer. Dealer is seat 2 here.
        # Forced contributions intentionally model 1A/1A/2A using A=2 units.
        return start_betting_round(
            street=Street.PREFLOP,
            players=(
                BettingPlayer(0, stack=98, committed_street=2),
                BettingPlayer(1, stack=98, committed_street=2),
                BettingPlayer(2, stack=96, committed_street=4),
            ),
            # Caller supplies the game-specific initial full-raise increment.
            initial_full_raise_increment=4,
            config=BettingConfig(short_all_in_reopen=policy),
        )

    def test_limp_limp_dealer_check_closes_round(self):
        state = self._three_way_preflop()
        self.assertEqual(state.next_actor, 0)
        self.assertEqual(legal_actions(state).call_amount, 2)
        initial_total = round_chip_total(state)

        state = apply_action(state, ActionKind.CALL)
        self.assertEqual(state.next_actor, 1)
        state = apply_action(state, ActionKind.CALL)
        self.assertEqual(state.next_actor, 2)
        legal = legal_actions(state)
        self.assertTrue(legal.can_check)
        self.assertFalse(legal.can_call)
        state = apply_action(state, ActionKind.CHECK)

        self.assertTrue(state.closed)
        self.assertFalse(state.hand_ended)
        self.assertIsNone(state.next_actor)
        self.assertEqual(round_chip_total(state), initial_total)
        self.assertEqual([event.action for event in state.events], [
            ActionKind.CALL,
            ActionKind.CALL,
            ActionKind.CHECK,
        ])

    def test_full_raise_reopens_every_other_live_player(self):
        state = self._three_way_preflop()
        legal = legal_actions(state)
        self.assertEqual(legal.full_raise_to, 8)
        self.assertEqual((legal.min_raise_to, legal.max_raise_to), (8, 100))

        state = apply_action(state, ActionKind.RAISE_TO, 8)
        self.assertEqual(state.current_bet, 8)
        self.assertEqual(state.last_full_raise_increment, 4)
        state = apply_action(state, ActionKind.CALL)  # seat 1

        # Dealer makes another full raise to 12; seat 0 must regain raise rights.
        state = apply_action(state, ActionKind.RAISE_TO, 12)
        self.assertEqual(state.next_actor, 0)
        self.assertTrue(legal_actions(state).raise_right_open)
        self.assertEqual(legal_actions(state).min_raise_to, 16)

    def test_short_allin_does_not_reopen_under_never_policy(self):
        state = start_betting_round(
            street=Street.FLOP,
            players=(
                BettingPlayer(0, stack=100, committed_street=0),
                BettingPlayer(1, stack=12, committed_street=0),
                BettingPlayer(2, stack=100, committed_street=0),
            ),
            initial_full_raise_increment=4,
            config=BettingConfig(
                short_all_in_reopen=ShortAllInReopenPolicy.NEVER
            ),
        )
        state = apply_action(state, ActionKind.RAISE_TO, 10)  # full raise, +10
        state = apply_action(state, ActionKind.RAISE_TO, 12)  # seat 1 short all-in +2
        state = apply_action(state, ActionKind.CALL)          # seat 2 calls 12

        self.assertEqual(state.next_actor, 0)
        legal = legal_actions(state)
        self.assertEqual(legal.call_amount, 2)
        self.assertFalse(legal.raise_right_open)
        self.assertFalse(legal.can_raise)
        state = apply_action(state, ActionKind.CALL)
        self.assertTrue(state.closed)

    def test_cumulative_short_allins_can_reopen_when_configured(self):
        state = start_betting_round(
            street=Street.FLOP,
            players=(
                BettingPlayer(0, stack=100, committed_street=0),
                BettingPlayer(1, stack=12, committed_street=0),
                BettingPlayer(2, stack=16, committed_street=0),
            ),
            initial_full_raise_increment=4,
            config=BettingConfig(
                short_all_in_reopen=ShortAllInReopenPolicy.CUMULATIVE_FULL_RAISE
            ),
        )
        state = apply_action(state, ActionKind.RAISE_TO, 10)  # last full increment = 10
        state = apply_action(state, ActionKind.RAISE_TO, 12)  # +2 short all-in
        state = apply_action(state, ActionKind.RAISE_TO, 16)  # +4 short all-in

        self.assertEqual(state.next_actor, 0)
        legal = legal_actions(state)
        # Seat 0 now faces +6, still below the prior full-raise increment of 10.
        self.assertFalse(legal.raise_right_open)
        self.assertFalse(legal.can_raise)

    def test_cumulative_short_allins_reopen_at_full_increment(self):
        state = start_betting_round(
            street=Street.FLOP,
            players=(
                BettingPlayer(0, stack=100, committed_street=0),
                BettingPlayer(1, stack=12, committed_street=0),
                BettingPlayer(2, stack=20, committed_street=0),
            ),
            initial_full_raise_increment=4,
            config=BettingConfig(
                short_all_in_reopen=ShortAllInReopenPolicy.CUMULATIVE_FULL_RAISE
            ),
        )
        state = apply_action(state, ActionKind.RAISE_TO, 10)  # last full increment = 10
        state = apply_action(state, ActionKind.RAISE_TO, 12)  # +2 short
        state = apply_action(state, ActionKind.RAISE_TO, 20)  # +8 short; cumulative +10

        self.assertEqual(state.next_actor, 0)
        legal = legal_actions(state)
        self.assertTrue(legal.raise_right_open)
        self.assertTrue(legal.can_raise)
        self.assertEqual(legal.full_raise_to, 30)
        self.assertEqual(legal.min_raise_to, 30)

    def test_any_increase_policy_reopens_immediately(self):
        state = start_betting_round(
            street=Street.FLOP,
            players=(
                BettingPlayer(0, stack=100, committed_street=0),
                BettingPlayer(1, stack=12, committed_street=0),
                BettingPlayer(2, stack=100, committed_street=0),
            ),
            initial_full_raise_increment=4,
            config=BettingConfig(
                short_all_in_reopen=ShortAllInReopenPolicy.ANY_INCREASE
            ),
        )
        state = apply_action(state, ActionKind.RAISE_TO, 10)
        state = apply_action(state, ActionKind.RAISE_TO, 12)
        state = apply_action(state, ActionKind.CALL)
        self.assertTrue(legal_actions(state).raise_right_open)

    def test_only_exact_short_allin_is_available_below_full_minimum(self):
        state = start_betting_round(
            street=Street.TURN,
            players=(
                BettingPlayer(0, stack=7, committed_street=0),
                BettingPlayer(1, stack=100, committed_street=4),
            ),
            initial_full_raise_increment=4,
        )
        legal = legal_actions(state)
        self.assertEqual(legal.call_amount, 4)
        self.assertEqual(legal.full_raise_to, 8)
        self.assertTrue(legal.can_raise)
        self.assertEqual((legal.min_raise_to, legal.max_raise_to), (7, 7))
        self.assertFalse(legal.is_raise_to_legal(6))
        self.assertTrue(legal.is_raise_to_legal(7))
        state = apply_action(state, ActionKind.RAISE_TO, 7)
        self.assertTrue(state.player(0).all_in)
        self.assertEqual(state.current_bet, 7)
        self.assertEqual(state.last_full_raise_increment, 4)

    def test_short_stack_call_is_not_raise(self):
        state = start_betting_round(
            street=Street.RIVER,
            players=(
                BettingPlayer(0, stack=3, committed_street=0),
                BettingPlayer(1, stack=100, committed_street=10),
            ),
            initial_full_raise_increment=10,
        )
        legal = legal_actions(state)
        self.assertEqual(legal.call_amount, 3)
        self.assertFalse(legal.can_raise)
        state = apply_action(state, ActionKind.CALL)
        self.assertTrue(state.player(0).all_in)
        self.assertEqual(state.player(0).committed_street, 3)
        self.assertTrue(state.closed)

    def test_fold_to_one_player_ends_hand(self):
        state = start_betting_round(
            street=Street.FLOP,
            players=(
                BettingPlayer(0, stack=90, committed_street=10),
                BettingPlayer(1, stack=100, committed_street=0),
            ),
            initial_full_raise_increment=10,
        )
        self.assertEqual(state.next_actor, 0)
        # Seat 0 is already at the current price, so check; seat 1 then faces no bet.
        state = apply_action(state, ActionKind.CHECK)
        self.assertEqual(state.next_actor, 1)
        state = apply_action(state, ActionKind.RAISE_TO, 10)
        self.assertEqual(state.next_actor, 0)
        state = apply_action(state, ActionKind.FOLD)
        self.assertTrue(state.closed)
        self.assertTrue(state.hand_ended)

    def test_out_of_turn_and_illegal_actions_are_rejected(self):
        state = self._three_way_preflop()
        with self.assertRaises(BettingStateError):
            legal_actions(state, seat=1)
        with self.assertRaises(BettingStateError):
            apply_action(state, ActionKind.CHECK)
        with self.assertRaises(BettingStateError):
            apply_action(state, ActionKind.RAISE_TO, 7)  # not all-in and below min 8

    def test_chip_conservation_through_raise_call_fold(self):
        state = self._three_way_preflop()
        total = round_chip_total(state)
        state = apply_action(state, ActionKind.RAISE_TO, 8)
        self.assertEqual(round_chip_total(state), total)
        state = apply_action(state, ActionKind.CALL)
        self.assertEqual(round_chip_total(state), total)
        state = apply_action(state, ActionKind.FOLD)
        self.assertEqual(round_chip_total(state), total)


if __name__ == "__main__":
    unittest.main()
