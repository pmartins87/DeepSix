import unittest

from deepsix_core.state import ActionKind
from deepsix_simulator import SimulatedHand, SimulatorAction
from deepsix_trainer.multistreet_branch import BranchNodeKind, ExactBranchState
from deepsix_trainer.multistreet_state import (
    MultiStreetStateError,
    decision_state_from_components,
    decision_state_from_hand,
)


class MultiStreetComponentBoundaryTests(unittest.TestCase):
    def _pair(self, *, seed=20260827):
        hand = SimulatedHand.start(
            hand_id=f"component-parity-{seed}",
            stake_cents=25,
            seed=seed,
            dealer_seat=0,
            stacks=((0, 1000), (1, 1000)),
            bbj_enabled=True,
        )
        branch = ExactBranchState.from_private_assignment(
            stake_cents=hand.stake_cents,
            dealer_seat=hand.state.dealer_seat,
            stacks=((0, 1000), (1, 1000)),
            hole_cards=hand.hole_cards,
            rules=hand.rules,
            bbj_enabled=hand.bbj_enabled,
        )
        return hand, branch

    def _component_state(self, branch):
        actor = branch.actor_seat
        self.assertIsNotNone(actor)
        return decision_state_from_components(
            branch.state,
            actor_hole_cards=branch.hole_cards_mapping()[actor],
            stake_cents=branch.stake_cents,
            rules=branch.rules,
            bbj_enabled=branch.bbj_enabled,
        )

    def _passive(self, branch):
        legal = branch.legal_actions()
        if legal.can_check:
            return ActionKind.CHECK
        if legal.can_call:
            return ActionKind.CALL
        if legal.can_fold:
            return ActionKind.FOLD
        raise AssertionError("no passive legal action")

    def test_component_constructor_equals_simulator_wrapper_on_every_street(self):
        hand, branch = self._pair(seed=1111)
        seen_streets = set()
        guard = 0

        while branch.node_kind != BranchNodeKind.TERMINAL:
            self.assertEqual(branch.node_kind, BranchNodeKind.DECISION)
            self.assertEqual(branch.state, hand.state)
            self.assertEqual(branch.actor_seat, hand.actor_seat)

            from_branch = self._component_state(branch)
            from_simulator = decision_state_from_hand(hand)
            self.assertEqual(from_branch, from_simulator)
            self.assertEqual(
                from_branch.public.fingerprint(),
                from_simulator.public.fingerprint(),
            )
            self.assertEqual(from_branch.fingerprint(), from_simulator.fingerprint())
            seen_streets.add(branch.state.street)

            actor = branch.actor_seat
            self.assertIsNotNone(actor)
            action = self._passive(branch)
            branch = branch.apply_action(action)
            hand.act(actor, SimulatorAction(action))

            if branch.node_kind == BranchNodeKind.CHANCE:
                revealed = hand.state.board[len(branch.state.board):]
                branch = branch.apply_chance(revealed)
                self.assertEqual(branch.state, hand.state)

            guard += 1
            self.assertLess(guard, 100)

        self.assertEqual(len(seen_streets), 4)
        self.assertTrue(hand.terminal)
        self.assertEqual(branch.state, hand.state)

    def test_component_constructor_rejects_profile_drift(self):
        _, branch = self._pair(seed=2222)
        actor = branch.actor_seat
        self.assertIsNotNone(actor)
        with self.assertRaises(MultiStreetStateError):
            decision_state_from_components(
                branch.state,
                actor_hole_cards=branch.hole_cards_mapping()[actor],
                stake_cents=50,
                rules=branch.rules,
                bbj_enabled=branch.bbj_enabled,
            )

    def test_component_constructor_rejects_wrong_actor_private_shape(self):
        _, branch = self._pair(seed=3333)
        with self.assertRaises(MultiStreetStateError):
            decision_state_from_components(
                branch.state,
                actor_hole_cards=(branch.private_cards_flat()[0],),
                stake_cents=branch.stake_cents,
                rules=branch.rules,
                bbj_enabled=branch.bbj_enabled,
            )


if __name__ == "__main__":
    unittest.main()
