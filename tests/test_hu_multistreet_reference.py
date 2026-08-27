import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_trainer.hu_multistreet_reference import (
    GROSS_POKER_DELTA,
    NET_CASH_DELTA,
    HuMicrogameConfig,
    HuReferenceMicrogame,
    HuReferenceMicrogameError,
    MicroAction,
    check_call_micro_policy,
    min_bet_call_micro_policy,
)
from deepsix_trainer.multistreet_state import decision_state_from_components
from deepsix_trainer.reach import PrivateReachVector


def cards(*texts):
    return tuple(parse_card(text) for text in texts)


def vector(seat, rows):
    return PrivateReachVector.from_mapping(seat, rows)


class HuMultiStreetReferenceTests(unittest.TestCase):
    def _game(self):
        config = HuMicrogameConfig(
            stake_cents=25,
            dealer_seat=0,
            stacks=((0, 1000), (1, 1000)),
            flop=cards("6c", "7d", "8h"),
            bbj_enabled=False,
        )
        ranges = (
            vector(
                0,
                {
                    cards("As", "Ks"): Fraction(1, 3),
                    cards("Ah", "Kh"): Fraction(2, 3),
                },
            ),
            vector(1, {cards("Qc", "Jc"): 1}),
        )
        return HuReferenceMicrogame(config, ranges)

    def test_private_deal_distribution_is_exact_and_normalized(self):
        game = self._game()
        self.assertEqual(len(game.deals), 2)
        self.assertEqual(
            sorted(deal.probability for deal in game.deals),
            [Fraction(1, 3), Fraction(2, 3)],
        )
        self.assertEqual(
            sum((deal.probability for deal in game.deals), Fraction(0, 1)),
            Fraction(1, 1),
        )

    def test_private_assignment_does_not_change_public_flop_root(self):
        game = self._game()
        roots = game.root_branches()
        self.assertEqual(len(roots), 2)
        public = set()
        private = set()
        for _, branch in roots:
            actor = branch.actor_seat
            self.assertIsNotNone(actor)
            state = decision_state_from_components(
                branch.state,
                actor_hole_cards=branch.hole_cards_mapping()[actor],
                stake_cents=branch.stake_cents,
                rules=branch.rules,
                bbj_enabled=branch.bbj_enabled,
            )
            public.add(state.public.fingerprint())
            private.add(state.fingerprint())
        self.assertEqual(len(public), 1)
        # Seat 1 acts first postflop and has one fixed hand in this fixture, so
        # its complete infoset is also identical across seat-0 assignments.
        self.assertEqual(len(private), 1)

    def test_root_action_abstraction_is_real_core_check_or_min_bet(self):
        game = self._game()
        _, root = game.root_branches()[0]
        self.assertEqual(
            game.abstract_actions(root),
            (MicroAction.CHECK, MicroAction.BET_MIN),
        )

    def test_check_call_policy_exact_gross_utility_is_zero_sum(self):
        game = self._game()
        result = game.evaluate(
            check_call_micro_policy,
            objective_id=GROSS_POKER_DELTA,
        )
        self.assertEqual(result.private_deal_count, 2)
        self.assertEqual(result.seat_sum_antes, Fraction(0, 1))
        self.assertEqual(result.expected_house_deduction_antes, Fraction(1, 5))
        self.assertEqual(len(result.root_public_fingerprint), 64)

    def test_same_tree_net_cash_utility_keeps_rake_visible(self):
        game = self._game()
        result = game.evaluate(
            check_call_micro_policy,
            objective_id=NET_CASH_DELTA,
        )
        self.assertEqual(result.expected_house_deduction_antes, Fraction(1, 5))
        self.assertEqual(result.seat_sum_antes, Fraction(-1, 5))

    def test_aggressive_reference_policy_is_deterministic_and_changes_economics(self):
        game = self._game()
        a = game.evaluate(min_bet_call_micro_policy, objective_id=NET_CASH_DELTA)
        b = game.evaluate(min_bet_call_micro_policy, objective_id=NET_CASH_DELTA)
        self.assertEqual(a, b)
        self.assertGreater(a.expected_house_deduction_antes, Fraction(1, 5))

    def test_malformed_policy_distribution_fails_closed(self):
        game = self._game()

        def bad_policy(state, actions):
            del state
            return {actions[0]: Fraction(1, 1)}

        with self.assertRaises(HuReferenceMicrogameError):
            game.evaluate(bad_policy, objective_id=GROSS_POKER_DELTA)

    def test_board_blocked_private_support_is_removed_and_renormalized(self):
        config = HuMicrogameConfig(
            stake_cents=25,
            dealer_seat=0,
            stacks=((0, 1000), (1, 1000)),
            flop=cards("Ac", "7d", "8h"),
            bbj_enabled=False,
        )
        game = HuReferenceMicrogame(
            config,
            (
                vector(
                    0,
                    {
                        cards("Ac", "Kc"): Fraction(9, 10),
                        cards("As", "Ks"): Fraction(1, 10),
                    },
                ),
                vector(1, {cards("Qc", "Jc"): 1}),
            ),
        )
        self.assertEqual(len(game.deals), 1)
        self.assertEqual(game.deals[0].probability, Fraction(1, 1))


if __name__ == "__main__":
    unittest.main()
