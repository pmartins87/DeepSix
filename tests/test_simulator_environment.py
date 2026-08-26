import unittest

from deepsix_core.betting import ShortAllInReopenPolicy
from deepsix_core.state import ActionKind
from deepsix_simulator import (
    DEFAULT_SIMULATOR_RULES,
    DeepSixTable,
    SimulatedHand,
    SimulatorAction,
    SimulatorEnvironmentError,
    check_call_policy,
)


def jam_or_call_policy(obs):
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


class SimulatorRulesTests(unittest.TestCase):
    def test_v1_rules_are_explicit_and_versioned(self):
        rules = DEFAULT_SIMULATOR_RULES
        rules.validate()
        cfg = rules.hand_config(25)
        self.assertEqual(cfg.ante, 25)
        self.assertEqual(cfg.preflop_full_raise_increment, 50)
        self.assertEqual(cfg.postflop_min_bet, 50)
        self.assertEqual(
            cfg.betting.short_all_in_reopen,
            ShortAllInReopenPolicy.CUMULATIVE_FULL_RAISE,
        )
        self.assertTrue(cfg.betting.allow_short_all_in_raise)


class SimulatedHandTests(unittest.TestCase):
    def _three_way_hand(self, seed=123):
        return SimulatedHand.start(
            hand_id=f"test-{seed}",
            stake_cents=25,
            seed=seed,
            dealer_seat=0,
            stacks=((0, 1000), (1, 1000), (2, 1000)),
        )

    def test_seeded_deal_is_reproducible_and_private(self):
        a = self._three_way_hand(123)
        b = self._three_way_hand(123)
        self.assertEqual(a.hole_cards, b.hole_cards)
        self.assertEqual(a.observation(1).hero_hole_cards, a.hole_cards[1])
        self.assertFalse(hasattr(a.observation(1), "opponent_hole_cards"))

        agents = {0: check_call_policy, 1: check_call_policy, 2: check_call_policy}
        sa = a.play_to_terminal(agents)
        sb = b.play_to_terminal(agents)
        self.assertEqual(a.state.board, b.state.board)
        self.assertEqual(sa, sb)
        self.assertEqual(len(a.state.board), 5)

    def test_out_of_turn_action_is_rejected(self):
        hand = self._three_way_hand()
        actor = hand.actor_seat
        self.assertIsNotNone(actor)
        wrong = next(seat for seat in hand.hole_cards if seat != actor)
        with self.assertRaises(SimulatorEnvironmentError):
            hand.act(wrong, SimulatorAction(ActionKind.CALL))

    def test_passive_three_way_checkdown_has_exact_integer_economy(self):
        hand = self._three_way_hand()
        settlement = hand.play_to_terminal(
            {0: check_call_policy, 1: check_call_policy, 2: check_call_policy}
        )
        # Forced contributions become 2A/1A/1A and the two non-Button seats
        # complete to 2A: 6 antes = 150 cents gross pot.
        self.assertEqual(settlement.gross_pot_units, 150)
        self.assertEqual(settlement.deductions.exact_rake_before_rounding, 15 / 2)
        self.assertEqual(settlement.deductions.rounded_rake_units, 7)
        self.assertEqual(settlement.deductions.bbj_units, 0)
        self.assertEqual(sum(v for _, v in settlement.net_awards), 143)
        self.assertEqual(sum(v for _, v in settlement.post_hand_stacks), 2993)

    def test_preflop_allin_auto_runs_board_and_applies_bbj_separately(self):
        hand = SimulatedHand.start(
            hand_id="bbj",
            stake_cents=2,
            seed=999,
            dealer_seat=0,
            stacks=((0, 500), (1, 500)),
            bbj_enabled=True,
        )
        settlement = hand.play_to_terminal({0: jam_or_call_policy, 1: jam_or_call_policy})
        self.assertEqual(settlement.gross_pot_units, 1000)
        self.assertEqual(len(hand.state.board), 5)
        self.assertEqual(settlement.deductions.rounded_rake_units, 2)  # 2p cap at $0.02
        self.assertEqual(settlement.deductions.bbj_units, 2)  # one ante at >=100A
        self.assertEqual(settlement.deductions.total_units, 4)
        self.assertEqual(sum(v for _, v in settlement.post_hand_stacks), 996)

    def test_bbj_can_be_disabled_without_changing_rake(self):
        hand = SimulatedHand.start(
            hand_id="no-bbj",
            stake_cents=2,
            seed=999,
            dealer_seat=0,
            stacks=((0, 500), (1, 500)),
            bbj_enabled=False,
        )
        settlement = hand.play_to_terminal({0: jam_or_call_policy, 1: jam_or_call_policy})
        self.assertEqual(settlement.deductions.rounded_rake_units, 2)
        self.assertEqual(settlement.deductions.bbj_units, 0)
        self.assertEqual(sum(v for _, v in settlement.post_hand_stacks), 998)


class DeepSixTableTests(unittest.TestCase):
    def test_table_uses_published_default_buyin_and_rotates_dealer(self):
        table = DeepSixTable(stake_cents=25, player_count=3, dealer_seat=0)
        self.assertEqual(table.stacks, {0: 1000, 1: 1000, 2: 1000})
        settlement = table.play_hand(
            {0: check_call_policy, 1: check_call_policy, 2: check_call_policy},
            seed=2026,
        )
        self.assertEqual(table.hand_index, 1)
        self.assertEqual(table.dealer_seat, 1)
        self.assertEqual(sum(table.stacks.values()), 3000 - settlement.deductions.total_units)


if __name__ == "__main__":
    unittest.main()
