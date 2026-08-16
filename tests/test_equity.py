import unittest

from deepsix_core.cards import parse_card
from deepsix_core.equity import exact_heads_up_equity


def c(text):
    return tuple(parse_card(token) for token in text.split())


class ExactEquityTests(unittest.TestCase):
    def test_locked_river_win(self):
        result = exact_heads_up_equity(
            c("Ah Kh"),
            c("Qc Qd"),
            c("Th Jh Qh 6c 7d"),
        )
        self.assertEqual((result.wins, result.ties, result.losses), (1, 0, 0))
        self.assertEqual(result.equity, 1.0)

    def test_locked_board_tie(self):
        result = exact_heads_up_equity(
            c("6c 7d"),
            c("6d 7c"),
            c("Th Jh Qh Kh Ah"),
        )
        self.assertEqual((result.wins, result.ties, result.losses), (0, 1, 0))
        self.assertEqual(result.equity, 0.5)

    def test_turn_enumerates_every_remaining_river(self):
        # 4 hole + 4 board = 8 known from 36, so 28 legal river cards.
        result = exact_heads_up_equity(
            c("Ah Ks"),
            c("Qc Qd"),
            c("6c 7d 8h 9s"),
        )
        self.assertEqual(result.total, 28)
        self.assertGreaterEqual(result.equity, 0.0)
        self.assertLessEqual(result.equity, 1.0)


if __name__ == "__main__":
    unittest.main()
