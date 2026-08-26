import unittest

from deepsix_core.cards import SUITS, decode_card, encode_card, parse_card
from deepsix_core.state import ActionKind, Street
from deepsix_simulator import SimulatedHand, SimulatorAction
from deepsix_trainer.multistreet_state import (
    MultiStreetStateError,
    PrivateDecisionState,
    canonical_private_cards_under_public,
    canonical_public_board,
    decision_state_from_hand,
)


def c(text: str) -> int:
    return parse_card(text)


def permute_suits(cards, permutation):
    mapped = []
    for card in cards:
        decoded = decode_card(card)
        old = SUITS.index(decoded.suit)
        mapped.append(encode_card(decoded.rank, SUITS[permutation[old]]))
    return tuple(mapped)


class MultiStreetCanonicalizationTests(unittest.TestCase):
    def test_board_first_suit_canonicalization_is_globally_invariant(self):
        board = (c("Ac"), c("Kd"), c("Qh"), c("Js"), c("Tc"))
        hero = (c("9s"), c("8c"))
        permutation = (2, 0, 3, 1)

        public_a, residual_a = canonical_public_board(board)
        private_a = canonical_private_cards_under_public(hero, residual_a)

        mapped_board = permute_suits(board, permutation)
        mapped_hero = permute_suits(hero, permutation)
        public_b, residual_b = canonical_public_board(mapped_board)
        private_b = canonical_private_cards_under_public(mapped_hero, residual_b)

        self.assertEqual(public_a, public_b)
        self.assertEqual(private_a, private_b)

    def test_flop_order_is_invariant_but_turn_river_order_is_not(self):
        flop_a, _ = canonical_public_board((c("Ac"), c("Kd"), c("Qh")))
        flop_b, _ = canonical_public_board((c("Qh"), c("Ac"), c("Kd")))
        self.assertEqual(flop_a, flop_b)

        board_a, _ = canonical_public_board(
            (c("Ac"), c("Kd"), c("Qh"), c("Js"), c("Tc"))
        )
        board_b, _ = canonical_public_board(
            (c("Qh"), c("Ac"), c("Kd"), c("Tc"), c("Js"))
        )
        self.assertNotEqual(board_a, board_b)

    def test_invalid_board_and_private_cards_fail_closed(self):
        with self.assertRaises(MultiStreetStateError):
            canonical_public_board((c("Ac"), c("Kd")))
        with self.assertRaises(MultiStreetStateError):
            canonical_public_board((c("Ac"), c("Ac"), c("Qh")))
        _, residual = canonical_public_board(())
        with self.assertRaises(MultiStreetStateError):
            canonical_private_cards_under_public((c("Ac"), c("Ac")), residual)


class MultiStreetSimulatorBoundaryTests(unittest.TestCase):
    def _hand(self, *, dealer=0, seats=(0, 1, 2), seed=20260826):
        return SimulatedHand.start(
            hand_id=f"f5-{dealer}-{seed}",
            stake_cents=25,
            seed=seed,
            dealer_seat=dealer,
            stacks=tuple((seat, 1000) for seat in seats),
            bbj_enabled=True,
        )

    def _passive_action(self, hand):
        actor = hand.actor_seat
        self.assertIsNotNone(actor)
        obs = hand.observation(actor)
        legal = obs.legal
        self.assertIsNotNone(legal)
        if legal.can_check:
            return actor, SimulatorAction(ActionKind.CHECK)
        if legal.can_call:
            return actor, SimulatorAction(ActionKind.CALL)
        return actor, SimulatorAction(ActionKind.FOLD)

    def test_physical_chair_rotation_does_not_change_strategic_identity(self):
        a = self._hand(dealer=0, seats=(0, 1, 2))
        b = self._hand(dealer=3, seats=(3, 4, 5))
        state_a = decision_state_from_hand(a)
        state_b = decision_state_from_hand(b)

        self.assertEqual(state_a.public.fingerprint(), state_b.public.fingerprint())
        self.assertEqual(state_a.fingerprint(), state_b.fingerprint())
        self.assertEqual(state_a.public.dealer_position, 0)
        self.assertEqual(state_b.public.dealer_position, 0)

    def test_exact_current_street_commitments_and_raise_geometry_are_preserved(self):
        hand = self._hand()
        state = decision_state_from_hand(hand)
        round_by_position = {
            ((player.seat - hand.state.dealer_seat) % 6): player
            for player in hand.state.betting_round.players
        }
        for seat in state.public.seats:
            self.assertEqual(
                seat.committed_street,
                round_by_position[seat.position].committed_street,
            )
        self.assertEqual(
            state.public.current_bet,
            hand.state.betting_round.current_bet,
        )
        self.assertEqual(
            state.public.last_full_raise_increment,
            hand.state.betting_round.last_full_raise_increment,
        )
        self.assertEqual(
            state.public.legal.full_raise_to,
            hand.state.betting_round.current_bet
            + hand.state.betting_round.last_full_raise_increment,
        )
        self.assertEqual(
            state.public.pot,
            sum(seat.committed_total for seat in state.public.seats),
        )

    def test_public_identity_does_not_depend_on_private_cards(self):
        hand = self._hand()
        state = decision_state_from_hand(hand)
        _, residual = canonical_public_board(hand.state.board)
        other_cards = canonical_private_cards_under_public((c("Ac"), c("Qc")), residual)
        alternate = PrivateDecisionState(
            public=state.public,
            hero_position=state.hero_position,
            hero_cards=other_cards,
        )
        self.assertEqual(state.public.fingerprint(), alternate.public.fingerprint())
        self.assertNotEqual(state.fingerprint(), alternate.fingerprint())

    def test_public_action_changes_exact_public_fingerprint(self):
        hand = self._hand()
        before = decision_state_from_hand(hand)
        actor, action = self._passive_action(hand)
        hand.act(actor, action)
        after = decision_state_from_hand(hand)
        self.assertNotEqual(before.public.fingerprint(), after.public.fingerprint())
        self.assertEqual(len(after.public.actions), 1)
        self.assertEqual(after.public.actions[0].seq, 0)

    def test_preflop_to_flop_transition_uses_canonical_public_board(self):
        hand = self._hand(seed=55)
        guard = 0
        while not hand.terminal and hand.state.street == Street.PREFLOP:
            actor, action = self._passive_action(hand)
            hand.act(actor, action)
            guard += 1
            self.assertLess(guard, 20)

        self.assertFalse(hand.terminal)
        self.assertEqual(hand.state.street, Street.FLOP)
        state = decision_state_from_hand(hand)
        expected, _ = canonical_public_board(hand.state.board)
        self.assertEqual(state.public.board, expected)
        self.assertEqual(len(state.public.board), 3)
        self.assertTrue(any(action.street == Street.PREFLOP for action in state.public.actions))

    def test_terminal_hand_has_no_decision_state(self):
        hand = self._hand(seed=77)
        guard = 0
        while not hand.terminal:
            actor, action = self._passive_action(hand)
            hand.act(actor, action)
            guard += 1
            self.assertLess(guard, 100)
        with self.assertRaises(MultiStreetStateError):
            decision_state_from_hand(hand)


if __name__ == "__main__":
    unittest.main()
