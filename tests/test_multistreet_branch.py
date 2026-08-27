import unittest
from fractions import Fraction

from deepsix_core.state import ActionKind, Street
from deepsix_simulator import SimulatedHand, SimulatorAction
from deepsix_trainer.multistreet_branch import (
    BranchNodeKind,
    ExactBranchError,
    ExactBranchState,
)


class ExactMultiStreetBranchTests(unittest.TestCase):
    def _simulator_hand(self, *, seed=20260826):
        return SimulatedHand.start(
            hand_id=f"branch-parity-{seed}",
            stake_cents=25,
            seed=seed,
            dealer_seat=0,
            stacks=((0, 1000), (1, 1000)),
            bbj_enabled=True,
        )

    def _branch_from_initial_simulator_deal(self, hand):
        return ExactBranchState.from_private_assignment(
            stake_cents=hand.stake_cents,
            dealer_seat=hand.state.dealer_seat,
            stacks=((0, 1000), (1, 1000)),
            hole_cards=hand.hole_cards,
            rules=hand.rules,
            bbj_enabled=hand.bbj_enabled,
        )

    def _passive_action(self, branch):
        legal = branch.legal_actions()
        if legal.can_check:
            return ActionKind.CHECK, None
        if legal.can_call:
            return ActionKind.CALL, None
        if legal.can_fold:
            return ActionKind.FOLD, None
        raise AssertionError("branch has no passive legal action")

    def _advance_branch_and_simulator_one_decision(self, branch, hand):
        self.assertEqual(branch.node_kind, BranchNodeKind.DECISION)
        self.assertEqual(branch.actor_seat, hand.actor_seat)
        actor = branch.actor_seat
        self.assertIsNotNone(actor)
        action, amount_to = self._passive_action(branch)

        child = branch.apply_action(action, amount_to)
        hand.act(actor, SimulatorAction(action, amount_to))

        if child.node_kind == BranchNodeKind.CHANCE:
            before_board_len = len(child.state.board)
            revealed = hand.state.board[before_board_len:]
            self.assertIn(len(revealed), (1, 3))
            child = child.apply_chance(revealed)

        self.assertEqual(child.state, hand.state)
        return child

    def test_explicit_action_and_chance_branch_matches_seeded_simulator_end_to_end(self):
        hand = self._simulator_hand(seed=424242)
        branch = self._branch_from_initial_simulator_deal(hand)
        self.assertEqual(branch.state, hand.state)
        self.assertEqual(branch.node_kind, BranchNodeKind.DECISION)

        visited = {Street.PREFLOP}
        guard = 0
        while branch.node_kind != BranchNodeKind.TERMINAL:
            branch = self._advance_branch_and_simulator_one_decision(branch, hand)
            visited.add(branch.state.street)
            guard += 1
            self.assertLess(guard, 100)

        self.assertTrue(hand.terminal)
        self.assertIsNotNone(hand.settlement)
        self.assertEqual(
            visited,
            {Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER},
        )
        self.assertEqual(branch.settle(), hand.settlement)

    def test_waiting_flop_enumerates_all_4960_fixed_private_outcomes_exactly(self):
        hand = self._simulator_hand(seed=91)
        branch = self._branch_from_initial_simulator_deal(hand)
        while branch.node_kind == BranchNodeKind.DECISION:
            action, amount_to = self._passive_action(branch)
            branch = branch.apply_action(action, amount_to)

        self.assertEqual(branch.node_kind, BranchNodeKind.CHANCE)
        self.assertEqual(branch.state.street, Street.PREFLOP)
        outcomes = branch.chance_outcomes()
        self.assertEqual(len(outcomes), 4960)
        self.assertEqual(
            sum((outcome.probability for outcome in outcomes), Fraction(0, 1)),
            Fraction(1, 1),
        )

    def test_two_flop_forks_share_parent_but_produce_distinct_children(self):
        hand = self._simulator_hand(seed=17)
        parent = self._branch_from_initial_simulator_deal(hand)
        while parent.node_kind == BranchNodeKind.DECISION:
            action, amount_to = self._passive_action(parent)
            parent = parent.apply_action(action, amount_to)

        self.assertEqual(parent.node_kind, BranchNodeKind.CHANCE)
        parent_state = parent.state
        outcomes = parent.chance_outcomes()
        left = parent.apply_chance(outcomes[0].revealed)
        right = parent.apply_chance(outcomes[-1].revealed)

        self.assertEqual(parent.state, parent_state)
        self.assertEqual(parent.node_kind, BranchNodeKind.CHANCE)
        self.assertEqual(left.state.street, Street.FLOP)
        self.assertEqual(right.state.street, Street.FLOP)
        self.assertNotEqual(left.state.board, right.state.board)
        self.assertNotEqual(left.state, right.state)

    def test_private_card_cannot_be_revealed_as_public_chance(self):
        hand = self._simulator_hand(seed=123)
        branch = self._branch_from_initial_simulator_deal(hand)
        while branch.node_kind == BranchNodeKind.DECISION:
            action, amount_to = self._passive_action(branch)
            branch = branch.apply_action(action, amount_to)

        private_card = branch.private_cards_flat()[0]
        with self.assertRaises(ExactBranchError):
            branch.apply_chance((private_card, branch.chance_outcomes()[0].revealed[1], branch.chance_outcomes()[0].revealed[2]))

    def test_node_kind_guards_fail_closed(self):
        hand = self._simulator_hand(seed=314)
        branch = self._branch_from_initial_simulator_deal(hand)
        with self.assertRaises(ExactBranchError):
            branch.chance_outcomes()
        with self.assertRaises(ExactBranchError):
            branch.apply_chance((0, 1, 2))
        with self.assertRaises(ExactBranchError):
            branch.settle()

        while branch.node_kind == BranchNodeKind.DECISION:
            action, amount_to = self._passive_action(branch)
            branch = branch.apply_action(action, amount_to)
        with self.assertRaises(ExactBranchError):
            branch.legal_actions()
        with self.assertRaises(ExactBranchError):
            branch.apply_action(ActionKind.CHECK)

    def test_from_simulated_hand_preserves_current_exact_state_and_private_assignment(self):
        hand = self._simulator_hand(seed=2718)
        actor = hand.actor_seat
        self.assertIsNotNone(actor)
        obs = hand.observation(actor)
        legal = obs.legal
        self.assertIsNotNone(legal)
        action = ActionKind.CALL if legal.can_call else ActionKind.CHECK
        hand.act(actor, SimulatorAction(action))

        branch = ExactBranchState.from_simulated_hand(hand)
        self.assertEqual(branch.state, hand.state)
        self.assertEqual(branch.hole_cards_mapping(), hand.hole_cards)
        self.assertEqual(branch.actor_seat, hand.actor_seat)


if __name__ == "__main__":
    unittest.main()
