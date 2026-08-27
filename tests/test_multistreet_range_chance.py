import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_trainer.multistreet_chance import enumerate_exact_board_chance
from deepsix_trainer.multistreet_range_chance import (
    RangeWeightedChanceError,
    enumerate_range_weighted_board_chance,
)
from deepsix_trainer.reach import PrivateReachVector, PublicReachState


def cards(*items):
    return tuple(parse_card(item) for item in items)


def vector(seat, rows):
    return PrivateReachVector.from_mapping(seat, rows)


def probability_by_reveal(outcomes):
    return {outcome.revealed: outcome.probability for outcome in outcomes}


class RangeWeightedChanceTests(unittest.TestCase):
    def test_singleton_range_matches_fixed_assignment_oracle_exactly(self):
        hero = cards("Qs", "Js")
        villain = cards("Ac", "Kc")
        board = cards("6c", "7d", "8h")
        reach = PublicReachState.from_vectors((vector(1, {villain: 1}),))

        weighted = enumerate_range_weighted_board_chance(
            board,
            reach,
            fixed_private_cards=hero,
        )
        exact = enumerate_exact_board_chance(board, hero + villain)

        self.assertEqual(len(weighted), 29)
        self.assertEqual(
            probability_by_reveal(weighted),
            probability_by_reveal(exact),
        )
        self.assertNotIn((parse_card("Ac"),), probability_by_reveal(weighted))
        self.assertNotIn((parse_card("Kc"),), probability_by_reveal(weighted))

    def test_preflop_singleton_support_is_exact_4960_flops(self):
        hero = cards("Qs", "Js")
        villain = cards("Ac", "Kc")
        reach = (vector(1, {villain: 1}),)
        outcomes = enumerate_range_weighted_board_chance(
            (), reach, fixed_private_cards=hero
        )
        self.assertEqual(len(outcomes), 4960)
        self.assertTrue(all(len(outcome.revealed) == 3 for outcome in outcomes))
        self.assertTrue(
            all(tuple(sorted(outcome.revealed)) == outcome.revealed for outcome in outcomes)
        )
        self.assertEqual(
            sum((outcome.probability for outcome in outcomes), Fraction(0, 1)),
            Fraction(1, 1),
        )

    def test_uncertain_blocker_changes_marginal_turn_probability(self):
        hero = cards("Qs", "Js")
        board = cards("6c", "7d", "8h")
        ac_kc = cards("Ac", "Kc")
        ah_kh = cards("Ah", "Kh")
        reach = PublicReachState.from_vectors(
            (
                vector(
                    1,
                    {
                        ac_kc: Fraction(1, 2),
                        ah_kh: Fraction(1, 2),
                    },
                ),
            )
        )
        outcomes = enumerate_range_weighted_board_chance(
            board,
            reach,
            fixed_private_cards=hero,
        )
        probabilities = probability_by_reveal(outcomes)
        p_ac = probabilities[(parse_card("Ac"),)]
        p_neutral = probabilities[(parse_card("9d"),)]

        self.assertEqual(p_neutral, Fraction(1, 29))
        self.assertEqual(p_ac, Fraction(1, 58))
        self.assertEqual(p_ac * 2, p_neutral)
        self.assertEqual(
            sum(probabilities.values(), Fraction(0, 1)),
            Fraction(1, 1),
        )

    def test_public_action_reach_update_changes_future_chance_exactly(self):
        hero = cards("Qs", "Js")
        board = cards("6c", "7d", "8h")
        ac_kc = cards("Ac", "Kc")
        ah_kh = cards("Ah", "Kh")
        initial = PublicReachState.from_vectors(
            (
                vector(
                    1,
                    {
                        ac_kc: Fraction(1, 2),
                        ah_kh: Fraction(1, 2),
                    },
                ),
            )
        )
        after_action = initial.apply_public_action(
            1,
            {
                ac_kc: Fraction(1, 4),
                ah_kh: Fraction(3, 4),
            },
        )
        probabilities = probability_by_reveal(
            enumerate_range_weighted_board_chance(
                board,
                after_action,
                fixed_private_cards=hero,
            )
        )
        p_ac = probabilities[(parse_card("Ac"),)]
        p_neutral = probabilities[(parse_card("9d"),)]

        self.assertEqual(p_neutral, Fraction(1, 29))
        self.assertEqual(p_ac, Fraction(3, 116))
        self.assertEqual(p_ac * 4, p_neutral * 3)

    def test_small_multiway_support_normalizes_with_card_conflicts(self):
        hero = cards("Qs", "Js")
        board = cards("6c", "7d", "8h")
        reach = PublicReachState.from_vectors(
            (
                vector(
                    1,
                    {
                        cards("Ac", "Kc"): Fraction(1, 3),
                        cards("Ah", "Kh"): Fraction(2, 3),
                    },
                ),
                vector(
                    2,
                    {
                        cards("Ac", "Tc"): Fraction(1, 4),
                        cards("Ad", "Td"): Fraction(3, 4),
                    },
                ),
            )
        )
        outcomes = enumerate_range_weighted_board_chance(
            board,
            reach,
            fixed_private_cards=hero,
        )
        self.assertEqual(
            sum((outcome.probability for outcome in outcomes), Fraction(0, 1)),
            Fraction(1, 1),
        )
        self.assertTrue(all(outcome.compatible_reach_mass > 0 for outcome in outcomes))

    def test_river_has_no_future_board_chance(self):
        hero = cards("Qs", "Js")
        villain = cards("Ac", "Kc")
        board = cards("6c", "7d", "8h", "9s", "Tc")
        reach = (vector(1, {villain: 1}),)
        self.assertEqual(
            enumerate_range_weighted_board_chance(
                board, reach, fixed_private_cards=hero
            ),
            (),
        )

    def test_malformed_or_zero_mass_inputs_fail_closed(self):
        with self.assertRaises(RangeWeightedChanceError):
            enumerate_range_weighted_board_chance(
                cards("6c", "7d", "8h"),
                (vector(1, {cards("Ac", "Kc"): 1}),),
                fixed_private_cards=cards("Qs"),
            )

        with self.assertRaises(RangeWeightedChanceError):
            enumerate_range_weighted_board_chance(
                cards("6c", "7d", "8h"),
                (vector(1, {cards("Ac", "Kc"): 1}),),
                fixed_private_cards=cards("6c", "Js"),
            )

        with self.assertRaises(RangeWeightedChanceError):
            enumerate_range_weighted_board_chance(
                cards("6c", "7d", "8h"),
                (vector(1, {cards("Ac", "Kc"): 1}),),
                fixed_private_cards=cards("Ac", "Qs"),
            )


if __name__ == "__main__":
    unittest.main()
