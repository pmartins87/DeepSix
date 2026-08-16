import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_core.hand import (
    HandConfig,
    HandPhase,
    apply_hand_action,
    deal_next_board,
    start_hand,
)
from deepsix_core.showdown import ShowdownError, resolve_gross_showdown_fractional
from deepsix_core.state import ActionKind


class ShowdownSettlementTests(unittest.TestCase):
    def _config(self):
        return HandConfig(
            ante=1,
            preflop_full_raise_increment=2,
            postflop_min_bet=2,
        )

    def _allin_three_way_10_20_20(self):
        state = start_hand(
            dealer_seat=2,
            stacks=((0, 10), (1, 20), (2, 20)),
            config=self._config(),
        )
        state = apply_hand_action(state, ActionKind.RAISE_TO, 10)
        state = apply_hand_action(state, ActionKind.RAISE_TO, 20)
        state = apply_hand_action(state, ActionKind.CALL)
        self.assertEqual(state.pot(), 50)
        state = deal_next_board(
            state,
            tuple(parse_card(card) for card in ("Ac", "Kd", "Qh")),
        )
        state = deal_next_board(state, (parse_card("Js"),))
        state = deal_next_board(state, (parse_card("6c"),))
        self.assertEqual(state.phase, HandPhase.SHOWDOWN)
        return state

    def _allin_heads_up_20_20(self):
        state = start_hand(
            dealer_seat=1,
            stacks=((0, 20), (1, 20)),
            config=self._config(),
        )
        state = apply_hand_action(state, ActionKind.RAISE_TO, 20)
        state = apply_hand_action(state, ActionKind.CALL)
        state = deal_next_board(
            state,
            tuple(parse_card(card) for card in ("Ac", "Kd", "Qh")),
        )
        state = deal_next_board(state, (parse_card("Js"),))
        state = deal_next_board(state, (parse_card("Tc"),))
        self.assertEqual(state.phase, HandPhase.SHOWDOWN)
        return state

    def test_short_stack_wins_main_pot_and_deeper_player_wins_side_pot(self):
        state = self._allin_three_way_10_20_20()
        result = resolve_gross_showdown_fractional(
            state,
            {
                0: (parse_card("Tc"), parse_card("9c")),
                1: (parse_card("9d"), parse_card("9h")),
                2: (parse_card("8d"), parse_card("8h")),
            },
        )
        self.assertEqual(len(result.layers), 2)
        self.assertEqual(result.layers[0].amount, 30)
        self.assertEqual(result.layers[0].winners, (0,))
        self.assertEqual(result.layers[1].amount, 20)
        self.assertEqual(result.layers[1].winners, (1,))
        self.assertEqual(result.award_for(0), Fraction(30, 1))
        self.assertEqual(result.award_for(1), Fraction(20, 1))
        self.assertEqual(result.award_for(2), Fraction(0, 1))
        self.assertEqual(result.total_awarded(), Fraction(50, 1))

    def test_tied_layer_uses_exact_fraction_without_guessing_odd_chip_rule(self):
        state = self._allin_heads_up_20_20()
        result = resolve_gross_showdown_fractional(
            state,
            {
                0: (parse_card("6c"), parse_card("7c")),
                1: (parse_card("6d"), parse_card("7d")),
            },
        )
        self.assertEqual(len(result.layers), 1)
        self.assertEqual(result.layers[0].winners, (0, 1))
        self.assertEqual(result.layers[0].share_per_winner, Fraction(20, 1))
        self.assertEqual(result.award_for(0), Fraction(20, 1))
        self.assertEqual(result.award_for(1), Fraction(20, 1))
        self.assertEqual(result.total_awarded(), Fraction(40, 1))

    def test_missing_hole_cards_are_rejected(self):
        state = self._allin_heads_up_20_20()
        with self.assertRaises(ShowdownError):
            resolve_gross_showdown_fractional(
                state,
                {0: (parse_card("6c"), parse_card("7c"))},
            )

    def test_duplicate_card_across_players_is_rejected(self):
        state = self._allin_heads_up_20_20()
        with self.assertRaises(ShowdownError):
            resolve_gross_showdown_fractional(
                state,
                {
                    0: (parse_card("6c"), parse_card("7c")),
                    1: (parse_card("6c"), parse_card("8d")),
                },
            )

    def test_cannot_settle_before_showdown(self):
        state = start_hand(
            dealer_seat=1,
            stacks=((0, 20), (1, 20)),
            config=self._config(),
        )
        with self.assertRaises(ShowdownError):
            resolve_gross_showdown_fractional(
                state,
                {
                    0: (parse_card("6c"), parse_card("7c")),
                    1: (parse_card("6d"), parse_card("7d")),
                },
            )


if __name__ == "__main__":
    unittest.main()
