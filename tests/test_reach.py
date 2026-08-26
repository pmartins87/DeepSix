import itertools
import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_trainer.reach import (
    PrivateReachVector,
    PublicReachState,
    ReachError,
    compatible_joint_assignment_count,
    compatible_joint_mass,
    direct_public_history_weight,
    factorized_assignment_weight,
)


def c(text):
    return parse_card(text)


def vec(seat, rows):
    return PrivateReachVector.from_mapping(seat, rows)


class ExactReachPropagationTests(unittest.TestCase):
    def setUp(self):
        self.v0 = vec(
            0,
            {
                (c("Ac"), c("Kc")): Fraction(1, 2),
                (c("Ah"), c("Kh")): Fraction(1, 2),
            },
        )
        self.v1 = vec(
            1,
            {
                (c("Qc"), c("Jc")): Fraction(1, 3),
                (c("Qh"), c("Jh")): Fraction(2, 3),
            },
        )
        self.v2 = vec(
            2,
            {
                (c("Tc"), c("9c")): Fraction(3, 5),
                (c("Th"), c("9h")): Fraction(2, 5),
            },
        )

    def test_incremental_public_reach_matches_direct_full_history_exactly(self):
        initial = (self.v0, self.v1, self.v2)
        p0 = {
            self.v0.hands[0]: Fraction(1, 4),
            self.v0.hands[1]: Fraction(3, 4),
        }
        p1 = {
            self.v1.hands[0]: Fraction(2, 5),
            self.v1.hands[1]: Fraction(1, 5),
        }
        p0_again = {
            self.v0.hands[0]: Fraction(1, 2),
            self.v0.hands[1]: Fraction(1, 3),
        }
        events = ((0, p0), (1, p1), (0, p0_again))

        state = PublicReachState.from_vectors(initial)
        for actor, likelihoods in events:
            state = state.apply_public_action(actor, likelihoods)
        self.assertEqual(state.public_event_count, 3)

        supports = [vector.hands for vector in initial]
        for hands in itertools.product(*supports):
            assignment = {vector.seat: hand for vector, hand in zip(initial, hands)}
            self.assertEqual(
                factorized_assignment_weight(state, assignment),
                direct_public_history_weight(initial, events, assignment),
            )

    def test_card_compatibility_is_explicit_in_joint_normalizer(self):
        left = vec(
            0,
            {
                (c("Ac"), c("Kc")): Fraction(1, 2),
                (c("Ah"), c("Kh")): Fraction(1, 2),
            },
        )
        right = vec(
            1,
            {
                (c("Ac"), c("Qc")): Fraction(1, 4),
                (c("As"), c("Qs")): Fraction(3, 4),
            },
        )
        # Four cartesian assignments have total product mass one, but the first
        # left hand conflicts with the first right hand on Ac.  That removes
        # exactly (1/2)*(1/4)=1/8 of mass.
        self.assertEqual(compatible_joint_mass((left, right)), Fraction(7, 8))
        self.assertEqual(compatible_joint_assignment_count((left, right)), 3)

    def test_dead_cards_filter_joint_mass_without_mutating_private_reaches(self):
        mass = compatible_joint_mass(
            (self.v0, self.v1),
            dead_cards=(c("Ac"),),
        )
        # The AcKc branch of seat 0 is dead; remaining v0 mass is 1/2 and both
        # v1 hands are compatible with AhKh.
        self.assertEqual(mass, Fraction(1, 2))
        self.assertEqual(self.v0.total_mass, Fraction(1, 1))

    def test_only_acting_seat_reach_changes_on_public_action(self):
        state = PublicReachState.from_vectors((self.v0, self.v1, self.v2))
        action = {
            self.v1.hands[0]: Fraction(1, 10),
            self.v1.hands[1]: Fraction(9, 10),
        }
        changed = state.apply_public_action(1, action)
        self.assertEqual(changed.vector_for(0), self.v0)
        self.assertEqual(changed.vector_for(2), self.v2)
        self.assertNotEqual(changed.vector_for(1), self.v1)
        self.assertEqual(
            changed.vector_for(1).weights,
            (Fraction(1, 30), Fraction(3, 5)),
        )

    def test_normalized_posterior_and_effective_support_are_exact(self):
        vector = vec(
            0,
            {
                (c("Ac"), c("Kc")): Fraction(1, 4),
                (c("Ah"), c("Kh")): Fraction(3, 4),
            },
        )
        self.assertEqual(vector.normalized, (Fraction(1, 4), Fraction(3, 4)))
        self.assertEqual(vector.effective_support, Fraction(8, 5))

    def test_zero_mass_likelihood_and_incomplete_support_fail_closed(self):
        with self.assertRaises(ReachError):
            self.v0.multiply_likelihoods(
                {
                    self.v0.hands[0]: 0,
                    self.v0.hands[1]: 0,
                }
            )
        with self.assertRaises(ReachError):
            self.v0.multiply_likelihoods({self.v0.hands[0]: Fraction(1, 2)})

    def test_incompatible_assignment_has_zero_direct_and_factorized_weight(self):
        left = vec(0, {(c("Ac"), c("Kc")): 1})
        right = vec(1, {(c("Ac"), c("Qc")): 1})
        state = PublicReachState.from_vectors((left, right))
        assignment = {0: left.hands[0], 1: right.hands[0]}
        self.assertEqual(factorized_assignment_weight(state, assignment), 0)
        self.assertEqual(direct_public_history_weight((left, right), (), assignment), 0)


if __name__ == "__main__":
    unittest.main()
