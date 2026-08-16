import unittest

from deepsix_core.betting import legal_actions
from deepsix_core.cards import parse_card
from deepsix_core.hand import (
    HandConfig,
    HandPhase,
    HandStateError,
    apply_hand_action,
    deal_next_board,
    fold_winner,
    hand_chip_total,
    start_hand,
)
from deepsix_core.state import ActionKind, Street


class FullHandStateMachineTests(unittest.TestCase):
    def _config(self):
        return HandConfig(
            ante=2,
            preflop_full_raise_increment=4,
            postflop_min_bet=4,
        )

    def _three_way(self):
        return start_hand(
            dealer_seat=2,
            stacks=((0, 100), (1, 100), (2, 100)),
            config=self._config(),
        )

    def test_start_posts_native_antes_and_button_total_two_antes(self):
        state = self._three_way()
        self.assertEqual(state.action_order, (0, 1, 2))
        self.assertEqual(state.street, Street.PREFLOP)
        self.assertEqual(state.phase, HandPhase.BETTING)
        self.assertEqual(state.betting_round.next_actor, 0)
        self.assertEqual(state.player(0).committed_total, 2)
        self.assertEqual(state.player(1).committed_total, 2)
        self.assertEqual(state.player(2).committed_total, 4)
        self.assertEqual(state.player(0).stack, 98)
        self.assertEqual(state.player(2).stack, 96)
        self.assertEqual(state.pot(), 8)
        self.assertEqual(hand_chip_total(state), 300)
        self.assertEqual(legal_actions(state.betting_round).call_amount, 2)

    def test_sparse_physical_seats_use_clockwise_order(self):
        state = start_hand(
            dealer_seat=4,
            stacks=((1, 100), (4, 100), (5, 100)),
            config=self._config(),
        )
        self.assertEqual(state.action_order, (5, 1, 4))
        self.assertEqual(state.betting_round.next_actor, 5)
        self.assertEqual(state.player(4).committed_total, 4)

    def test_limp_preflop_then_full_checkdown_reaches_showdown(self):
        state = self._three_way()
        state = apply_hand_action(state, ActionKind.CALL)
        state = apply_hand_action(state, ActionKind.CALL)
        state = apply_hand_action(state, ActionKind.CHECK)
        self.assertEqual(state.phase, HandPhase.WAITING_FLOP)
        self.assertEqual(state.pot(), 12)

        flop = tuple(parse_card(card) for card in ("6c", "7d", "8h"))
        state = deal_next_board(state, flop)
        self.assertEqual(state.street, Street.FLOP)
        self.assertEqual(state.phase, HandPhase.BETTING)
        self.assertEqual(state.betting_round.next_actor, 0)
        for _ in range(3):
            state = apply_hand_action(state, ActionKind.CHECK)
        self.assertEqual(state.phase, HandPhase.WAITING_TURN)

        state = deal_next_board(state, (parse_card("9s"),))
        for _ in range(3):
            state = apply_hand_action(state, ActionKind.CHECK)
        self.assertEqual(state.phase, HandPhase.WAITING_RIVER)

        state = deal_next_board(state, (parse_card("Tc"),))
        for _ in range(3):
            state = apply_hand_action(state, ActionKind.CHECK)

        self.assertEqual(state.phase, HandPhase.SHOWDOWN)
        self.assertEqual(state.street, Street.RIVER)
        self.assertEqual(len(state.board), 5)
        self.assertEqual(len(state.actions), 12)
        self.assertEqual([event.seq for event in state.actions], list(range(12)))
        self.assertEqual(
            [event.street for event in state.actions],
            [Street.PREFLOP] * 3
            + [Street.FLOP] * 3
            + [Street.TURN] * 3
            + [Street.RIVER] * 3,
        )
        self.assertEqual(hand_chip_total(state), 300)

    def test_fold_early_is_terminal_and_reports_winner(self):
        state = start_hand(
            dealer_seat=1,
            stacks=((0, 100), (1, 100)),
            config=self._config(),
        )
        self.assertEqual(state.betting_round.next_actor, 0)
        state = apply_hand_action(state, ActionKind.FOLD)
        self.assertEqual(state.phase, HandPhase.TERMINAL_FOLD)
        self.assertEqual(fold_winner(state), 1)
        self.assertEqual(state.pot(), 6)
        with self.assertRaises(HandStateError):
            deal_next_board(
                state,
                tuple(parse_card(card) for card in ("6c", "7d", "8h")),
            )

    def test_preflop_allin_runout_skips_dry_side_pot_betting(self):
        state = start_hand(
            dealer_seat=1,
            stacks=((0, 20), (1, 20)),
            config=self._config(),
        )
        # Seat 0 has 18 behind after posting 1A and can raise-to its exact 20.
        state = apply_hand_action(state, ActionKind.RAISE_TO, 20)
        self.assertTrue(state.player(0).all_in)
        state = apply_hand_action(state, ActionKind.CALL)
        self.assertTrue(state.player(1).all_in)
        self.assertEqual(state.phase, HandPhase.WAITING_FLOP)
        self.assertEqual(state.pot(), 40)

        state = deal_next_board(
            state,
            tuple(parse_card(card) for card in ("Ac", "Kd", "Qh")),
        )
        self.assertEqual(state.phase, HandPhase.WAITING_TURN)
        self.assertTrue(state.betting_round.closed)
        state = deal_next_board(state, (parse_card("Js"),))
        self.assertEqual(state.phase, HandPhase.WAITING_RIVER)
        state = deal_next_board(state, (parse_card("Tc"),))
        self.assertEqual(state.phase, HandPhase.SHOWDOWN)
        self.assertEqual(state.pot(), 40)
        self.assertEqual(hand_chip_total(state), 40)
        self.assertEqual(len(state.actions), 2)

    def test_chip_conservation_across_multiple_streets_and_raise(self):
        state = self._three_way()
        initial = hand_chip_total(state)
        state = apply_hand_action(state, ActionKind.RAISE_TO, 8)
        state = apply_hand_action(state, ActionKind.CALL)
        state = apply_hand_action(state, ActionKind.CALL)
        self.assertEqual(state.phase, HandPhase.WAITING_FLOP)
        self.assertEqual(hand_chip_total(state), initial)

        state = deal_next_board(
            state,
            tuple(parse_card(card) for card in ("6c", "7c", "8d")),
        )
        state = apply_hand_action(state, ActionKind.CHECK)
        state = apply_hand_action(state, ActionKind.RAISE_TO, 10)
        state = apply_hand_action(state, ActionKind.CALL)
        state = apply_hand_action(state, ActionKind.FOLD)
        self.assertEqual(state.phase, HandPhase.WAITING_TURN)
        self.assertEqual(hand_chip_total(state), initial)
        self.assertEqual(state.pot(), sum(player.committed_total for player in state.players))

    def test_board_reveal_count_duplicate_and_invalid_phase_are_rejected(self):
        state = self._three_way()
        with self.assertRaises(HandStateError):
            deal_next_board(
                state,
                tuple(parse_card(card) for card in ("6c", "7d", "8h")),
            )
        state = apply_hand_action(state, ActionKind.CALL)
        state = apply_hand_action(state, ActionKind.CALL)
        state = apply_hand_action(state, ActionKind.CHECK)
        with self.assertRaises(HandStateError):
            deal_next_board(state, (parse_card("6c"),))
        with self.assertRaises(HandStateError):
            deal_next_board(
                state,
                (parse_card("6c"), parse_card("6c"), parse_card("8h")),
            )

    def test_short_dealer_stack_is_clipped_to_forced_contribution(self):
        state = start_hand(
            dealer_seat=1,
            stacks=((0, 20), (1, 3)),
            config=self._config(),
        )
        dealer = state.player(1)
        self.assertEqual(dealer.committed_total, 3)
        self.assertEqual(dealer.stack, 0)
        self.assertTrue(dealer.all_in)
        self.assertEqual(hand_chip_total(state), 23)
        # Seat 0 already owes the price difference and must still act once.
        self.assertEqual(state.betting_round.next_actor, 0)
        self.assertEqual(legal_actions(state.betting_round).call_amount, 1)


if __name__ == "__main__":
    unittest.main()
