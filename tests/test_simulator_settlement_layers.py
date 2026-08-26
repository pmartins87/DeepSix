import unittest

from deepsix_core.cards import parse_card
from deepsix_core.hand import (
    HandPhase,
    apply_hand_action,
    deal_next_board,
    start_hand,
)
from deepsix_core.state import ActionKind
from deepsix_simulator import DEFAULT_SIMULATOR_RULES, settle_terminal_hand


class SimulatorSettlementLayerTests(unittest.TestCase):
    def _deal_board(self, state, cards):
        state = deal_next_board(state, tuple(parse_card(c) for c in cards[:3]))
        if state.phase == HandPhase.WAITING_TURN:
            state = deal_next_board(state, (parse_card(cards[3]),))
        if state.phase == HandPhase.WAITING_RIVER:
            state = deal_next_board(state, (parse_card(cards[4]),))
        return state

    def test_odd_chip_goes_to_first_tied_winner_left_of_dealer(self):
        cfg = DEFAULT_SIMULATOR_RULES.hand_config(2)
        state = start_hand(
            dealer_seat=0,
            stacks=((0, 5), (1, 5), (2, 5)),
            config=cfg,
        )
        # Everyone completes to 4 preflop, leaving one unit each.
        state = apply_hand_action(state, ActionKind.CALL)
        state = apply_hand_action(state, ActionKind.CALL)
        state = apply_hand_action(state, ActionKind.CHECK)
        self.assertEqual(state.phase, HandPhase.WAITING_FLOP)
        state = deal_next_board(
            state,
            tuple(parse_card(c) for c in ("Ac", "Kd", "Qh")),
        )
        # Seat 1 short-all-in bets its final unit, seat 2 and Dealer call.
        state = apply_hand_action(state, ActionKind.RAISE_TO, 1)
        state = apply_hand_action(state, ActionKind.CALL)
        state = apply_hand_action(state, ActionKind.CALL)
        self.assertEqual(state.phase, HandPhase.WAITING_TURN)
        state = deal_next_board(state, (parse_card("9s"),))
        state = deal_next_board(state, (parse_card("8c"),))
        self.assertEqual(state.phase, HandPhase.SHOWDOWN)
        self.assertEqual(state.pot(), 15)

        holes = {
            1: (parse_card("Js"), parse_card("Tc")),
            2: (parse_card("Jd"), parse_card("Td")),
            0: (parse_card("6h"), parse_card("7h")),
        }
        settlement = settle_terminal_hand(
            state,
            holes,
            stake_cents=2,
            bbj_enabled=False,
        )
        # Seats 1 and 2 tie with Broadway; action order is 1,2,0, so seat 1
        # receives the one odd cent from the 15-cent layer.
        self.assertEqual(dict(settlement.gross_awards), {0: 0, 1: 8, 2: 7})
        self.assertEqual(settlement.deductions.rounded_rake_units, 0)
        self.assertEqual(dict(settlement.net_awards), {0: 0, 1: 8, 2: 7})

    def test_short_stack_wins_main_pot_deep_stack_wins_side_pot(self):
        cfg = DEFAULT_SIMULATOR_RULES.hand_config(2)
        state = start_hand(
            dealer_seat=0,
            stacks=((0, 9), (1, 5), (2, 9)),
            config=cfg,
        )
        # Seat 1 can only short-raise from the Button's forced 4 to 5.
        state = apply_hand_action(state, ActionKind.RAISE_TO, 5)
        # Seat 2 still has a full raise to 9 and jams.
        state = apply_hand_action(state, ActionKind.RAISE_TO, 9)
        # Dealer calls off the remaining five.
        state = apply_hand_action(state, ActionKind.CALL)
        self.assertEqual(state.phase, HandPhase.WAITING_FLOP)
        self.assertEqual(state.pot(), 23)

        state = self._deal_board(state, ("Ac", "Kd", "Qh", "9s", "8c"))
        self.assertEqual(state.phase, HandPhase.SHOWDOWN)
        holes = {
            1: (parse_card("Js"), parse_card("Tc")),  # Broadway, main-pot winner
            2: (parse_card("Ah"), parse_card("Ad")),  # trips A, side-pot winner
            0: (parse_card("6d"), parse_card("7d")),
        }
        settlement = settle_terminal_hand(
            state,
            holes,
            stake_cents=2,
            bbj_enabled=False,
        )
        self.assertEqual(dict(settlement.gross_awards), {0: 0, 1: 15, 2: 8})
        self.assertEqual(settlement.deductions.rounded_rake_units, 1)
        self.assertEqual(settlement.deductions.total_units, 1)
        self.assertEqual(sum(dict(settlement.net_awards).values()), 22)
        self.assertEqual(sum(dict(settlement.post_hand_stacks).values()), 22)


if __name__ == "__main__":
    unittest.main()
