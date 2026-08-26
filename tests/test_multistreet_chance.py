import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_core.state import Street
from deepsix_trainer.multistreet_chance import (
    MultiStreetChanceError,
    enumerate_exact_board_chance,
)


def cards(*items):
    return tuple(parse_card(item) for item in items)


class ExactMultiStreetChanceTests(unittest.TestCase):
    def test_hu_exact_support_counts_preflop_flop_turn(self):
        private = cards("Ac", "Kd", "Qh", "Js")

        preflop = enumerate_exact_board_chance((), private)
        self.assertEqual(len(preflop), 4960)  # C(32, 3)
        self.assertEqual(preflop[0].street, Street.FLOP)
        self.assertEqual(
            sum((row.probability for row in preflop), Fraction(0, 1)),
            Fraction(1, 1),
        )

        flop_board = cards("6c", "7d", "8h")
        flop = enumerate_exact_board_chance(flop_board, private)
        self.assertEqual(len(flop), 29)  # 36 - 4 private - 3 board
        self.assertTrue(all(row.street == Street.TURN for row in flop))
        self.assertEqual(
            sum((row.probability for row in flop), Fraction(0, 1)),
            Fraction(1, 1),
        )

        turn_board = flop_board + cards("9s")
        turn = enumerate_exact_board_chance(turn_board, private)
        self.assertEqual(len(turn), 28)
        self.assertTrue(all(row.street == Street.RIVER for row in turn))
        self.assertEqual(
            sum((row.probability for row in turn), Fraction(0, 1)),
            Fraction(1, 1),
        )

        river_board = turn_board + cards("Tc")
        self.assertEqual(enumerate_exact_board_chance(river_board, private), ())

    def test_six_way_support_counts_respect_all_fixed_private_cards(self):
        private = cards(
            "Ac", "Kd",
            "Qh", "Js",
            "Tc", "9d",
            "8h", "7s",
            "6c", "Ad",
            "Kh", "Qs",
        )
        preflop = enumerate_exact_board_chance((), private)
        self.assertEqual(len(preflop), 2024)  # C(24, 3)

        flop_board = cards("Jc", "Th", "9s")
        flop = enumerate_exact_board_chance(flop_board, private)
        self.assertEqual(len(flop), 21)
        turn = enumerate_exact_board_chance(flop_board + cards("8d"), private)
        self.assertEqual(len(turn), 20)

    def test_flop_reveal_is_an_unordered_combination_but_later_cards_are_ordered(self):
        private = cards("Ac", "Kd", "Qh", "Js")
        preflop = enumerate_exact_board_chance((), private)
        self.assertTrue(all(tuple(sorted(row.revealed)) == row.revealed for row in preflop))
        self.assertTrue(all(tuple(sorted(row.next_board)) == row.next_board for row in preflop))

        board = cards("6c", "7d", "8h")
        turn = enumerate_exact_board_chance(board, private)
        first = turn[0]
        self.assertEqual(first.next_board[:3], board)
        self.assertEqual(first.next_board[3:], first.revealed)

    def test_every_outcome_preserves_card_uniqueness(self):
        private = cards("Ac", "Kd", "Qh", "Js")
        board = cards("6c", "7d", "8h")
        for outcome in enumerate_exact_board_chance(board, private):
            known = private + outcome.next_board
            self.assertEqual(len(known), len(set(known)))

    def test_overlap_duplicates_and_bad_board_shape_fail_closed(self):
        with self.assertRaises(MultiStreetChanceError):
            enumerate_exact_board_chance(cards("Ac", "Ac", "Qh"), cards("Kd", "Js"))
        with self.assertRaises(MultiStreetChanceError):
            enumerate_exact_board_chance(cards("Ac", "Kd", "Qh"), cards("Ac", "Js"))
        with self.assertRaises(MultiStreetChanceError):
            enumerate_exact_board_chance(cards("Ac", "Kd"), cards("Qh", "Js"))


if __name__ == "__main__":
    unittest.main()
