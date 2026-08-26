import unittest

from fractions import Fraction

from deepsix_core.state import ActionKind
from deepsix_simulator import (
    SimulatedHand,
    SimulatorAction,
    SimulatorSettlementError,
    check_call_policy,
    utility_from_settlement,
)


def jam_or_call(obs):
    legal = obs.legal
    if legal is None:
        raise AssertionError("agent called without legal actions")
    if legal.can_raise:
        return SimulatorAction(ActionKind.RAISE_TO, legal.max_raise_to)
    if legal.can_call:
        return SimulatorAction(ActionKind.CALL)
    if legal.can_check:
        return SimulatorAction(ActionKind.CHECK)
    return SimulatorAction(ActionKind.FOLD)


class SimulatorUtilityTests(unittest.TestCase):
    def test_gross_is_zero_sum_net_is_negative_house_deduction(self):
        hand = SimulatedHand.start(
            hand_id="utility-checkdown",
            stake_cents=25,
            seed=123,
            dealer_seat=0,
            stacks=((0, 1000), (1, 1000), (2, 1000)),
            bbj_enabled=False,
        )
        settlement = hand.play_to_terminal(
            {0: check_call_policy, 1: check_call_policy, 2: check_call_policy}
        )
        utility = utility_from_settlement(
            hand.state,
            settlement,
            stake_cents=25,
        )
        self.assertEqual(utility.gross_sum_units, 0)
        self.assertEqual(
            utility.net_sum_units,
            -settlement.deductions.total_units,
        )
        self.assertEqual(utility.net_sum_units, -7)
        self.assertEqual(utility.ante_units, 25)
        for seat_utility in utility.seats:
            self.assertEqual(
                seat_utility.gross_poker_delta_antes,
                Fraction(seat_utility.gross_poker_delta_units, 25),
            )
            self.assertEqual(
                seat_utility.net_cash_delta_units,
                seat_utility.gross_poker_delta_units
                - seat_utility.house_charge_units,
            )

    def test_bbj_remains_visible_in_negative_sum_cash_utility(self):
        hand = SimulatedHand.start(
            hand_id="utility-bbj",
            stake_cents=2,
            seed=999,
            dealer_seat=0,
            stacks=((0, 500), (1, 500)),
            bbj_enabled=True,
        )
        settlement = hand.play_to_terminal({0: jam_or_call, 1: jam_or_call})
        utility = utility_from_settlement(
            hand.state,
            settlement,
            stake_cents=2,
        )
        self.assertEqual(settlement.deductions.rounded_rake_units, 2)
        self.assertEqual(settlement.deductions.bbj_units, 2)
        self.assertEqual(utility.gross_sum_units, 0)
        self.assertEqual(utility.net_sum_units, -4)
        self.assertEqual(
            sum(item.house_charge_units for item in utility.seats),
            4,
        )

    def test_wrong_stake_normalization_is_rejected(self):
        hand = SimulatedHand.start(
            hand_id="utility-stake",
            stake_cents=25,
            seed=5,
            dealer_seat=0,
            stacks=((0, 1000), (1, 1000)),
            bbj_enabled=False,
        )
        settlement = hand.play_to_terminal({0: check_call_policy, 1: check_call_policy})
        with self.assertRaises(SimulatorSettlementError):
            utility_from_settlement(hand.state, settlement, stake_cents=50)


if __name__ == "__main__":
    unittest.main()
