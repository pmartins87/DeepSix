import unittest

from deepsix_core.state import ActionKind, Street
from deepsix_simulator import SimulatedHand, SimulatorAction
from deepsix_trainer.multistreet_reference import (
    MultiStreetReferenceError,
    fork_apply,
    recovered_initial_stacks,
    reference_transition,
    replay_fork,
)
from deepsix_trainer.multistreet_state import decision_state_from_hand


class MultiStreetReplayForkTests(unittest.TestCase):
    def _hand(self, *, seed=20260826, player_count=3):
        return SimulatedHand.start(
            hand_id=f"fork-{seed}-{player_count}",
            stake_cents=25,
            seed=seed,
            dealer_seat=0,
            stacks=tuple((seat, 1000) for seat in range(player_count)),
            bbj_enabled=True,
        )

    def _passive(self, hand):
        actor = hand.actor_seat
        self.assertIsNotNone(actor)
        legal = hand.observation(actor).legal
        self.assertIsNotNone(legal)
        if legal.can_check:
            return SimulatorAction(ActionKind.CHECK)
        if legal.can_call:
            return SimulatorAction(ActionKind.CALL)
        return SimulatorAction(ActionKind.FOLD)

    def test_recovered_initial_stacks_are_exact(self):
        hand = self._hand()
        self.assertEqual(
            sum(stack for _, stack in recovered_initial_stacks(hand)),
            hand.state.initial_total_chips,
        )
        actor = hand.actor_seat
        hand.act(actor, self._passive(hand))
        self.assertEqual(
            sum(stack for _, stack in recovered_initial_stacks(hand)),
            hand.state.initial_total_chips,
        )

    def test_replay_fork_is_exact_at_preflop_decision(self):
        hand = self._hand(seed=11)
        source = decision_state_from_hand(hand)
        fork = replay_fork(hand)
        clone = decision_state_from_hand(fork)

        self.assertIsNot(fork, hand)
        self.assertEqual(fork.state, hand.state)
        self.assertEqual(fork.hole_cards, hand.hole_cards)
        self.assertEqual(source.public.fingerprint(), clone.public.fingerprint())
        self.assertEqual(source.fingerprint(), clone.fingerprint())

    def test_replay_fork_is_exact_after_crossing_to_flop(self):
        hand = self._hand(seed=12)
        guard = 0
        while hand.state.street == Street.PREFLOP:
            actor = hand.actor_seat
            hand.act(actor, self._passive(hand))
            guard += 1
            self.assertLess(guard, 20)

        self.assertEqual(hand.state.street, Street.FLOP)
        fork = replay_fork(hand)
        self.assertEqual(fork.state, hand.state)
        self.assertEqual(fork.state.board, hand.state.board)
        self.assertEqual(
            decision_state_from_hand(fork).fingerprint(),
            decision_state_from_hand(hand).fingerprint(),
        )

    def test_two_reference_branches_do_not_mutate_source(self):
        hand = self._hand(seed=13)
        original = decision_state_from_hand(hand)
        actor = hand.actor_seat
        legal = hand.observation(actor).legal
        self.assertTrue(legal.can_call)
        self.assertTrue(legal.can_raise)

        call_child = fork_apply(hand, SimulatorAction(ActionKind.CALL))
        raise_child = fork_apply(
            hand,
            SimulatorAction(ActionKind.RAISE_TO, legal.min_raise_to),
        )

        self.assertEqual(hand.decision_index, 0)
        self.assertEqual(
            decision_state_from_hand(hand).fingerprint(),
            original.fingerprint(),
        )
        self.assertNotEqual(
            decision_state_from_hand(call_child).public.fingerprint(),
            decision_state_from_hand(raise_child).public.fingerprint(),
        )

    def test_transition_receipt_binds_parent_action_and_child(self):
        hand = self._hand(seed=14)
        parent = decision_state_from_hand(hand)
        child, receipt = reference_transition(
            hand,
            SimulatorAction(ActionKind.CALL),
        )
        child_state = decision_state_from_hand(child)

        self.assertFalse(receipt.child_terminal)
        self.assertEqual(
            receipt.parent_public_fingerprint,
            parent.public.fingerprint(),
        )
        self.assertEqual(receipt.action, ActionKind.CALL)
        self.assertEqual(
            receipt.child_public_fingerprint,
            child_state.public.fingerprint(),
        )
        self.assertEqual(len(receipt.fingerprint()), 64)

    def test_heads_up_fold_receipt_binds_terminal_settlement(self):
        hand = self._hand(seed=15, player_count=2)
        actor = hand.actor_seat
        legal = hand.observation(actor).legal
        self.assertTrue(legal.can_fold)

        child, receipt = reference_transition(
            hand,
            SimulatorAction(ActionKind.FOLD),
        )
        self.assertTrue(child.terminal)
        self.assertTrue(receipt.child_terminal)
        self.assertIsNone(receipt.child_public_fingerprint)
        self.assertIsNone(receipt.child_private_fingerprint)
        self.assertIsNotNone(receipt.terminal_settlement_sha256)
        self.assertEqual(len(receipt.terminal_settlement_sha256), 64)

    def test_illegal_reference_child_fails_closed(self):
        hand = self._hand(seed=16)
        actor = hand.actor_seat
        legal = hand.observation(actor).legal
        self.assertTrue(legal.can_raise)
        with self.assertRaises(MultiStreetReferenceError):
            fork_apply(
                hand,
                SimulatorAction(ActionKind.RAISE_TO, legal.max_raise_to + 1),
            )


if __name__ == "__main__":
    unittest.main()
