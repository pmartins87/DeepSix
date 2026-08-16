import unittest

from deepsix_core.cards import ShortDeckCardError, parse_card
from deepsix_core.evaluator import (
    HandCategory,
    evaluate_best,
    evaluate_five,
    straight_high,
)


def cards(text: str):
    return [parse_card(token) for token in text.split()]


class ShortDeckEvaluatorTests(unittest.TestCase):
    def test_a6789_is_lowest_straight(self):
        value = evaluate_five(cards("Ac 6d 7h 8s 9c"))
        self.assertEqual(value.category, HandCategory.STRAIGHT)
        self.assertEqual(value.tiebreak, (9,))
        self.assertLess(value, evaluate_five(cards("6c 7d 8h 9s Tc")))

    def test_flush_beats_full_house(self):
        flush = evaluate_five(cards("Ah Qh Jh 9h 7h"))
        full_house = evaluate_five(cards("Qc Qd Qh Ts Tc"))
        self.assertEqual(flush.category, HandCategory.FLUSH)
        self.assertEqual(full_house.category, HandCategory.FULL_HOUSE)
        self.assertGreater(flush, full_house)

    def test_quads_beats_flush(self):
        quads = evaluate_five(cards("Ac Ad Ah As Kc"))
        flush = evaluate_five(cards("Kh Qh Jh 9h 7h"))
        self.assertGreater(quads, flush)

    def test_straight_flush_beats_quads(self):
        straight_flush = evaluate_five(cards("Th Jh Qh Kh Ah"))
        quads = evaluate_five(cards("Ac Ad Ah As Kc"))
        self.assertGreater(straight_flush, quads)

    def test_best_of_seven_uses_any_five_cards(self):
        seven = cards("Ac Ad 6c 7d 8h 9s Tc")
        value = evaluate_best(seven)
        self.assertEqual(value.category, HandCategory.STRAIGHT)
        self.assertEqual(value.tiebreak, (10,))

    def test_duplicate_cards_rejected(self):
        with self.assertRaises(ShortDeckCardError):
            evaluate_five(cards("Ac Ac Qh Jh Th"))

    def test_invalid_card_count_rejected(self):
        with self.assertRaises(ShortDeckCardError):
            evaluate_best(cards("Ac Kc Qc Jc"))


class StraightPrimitiveTests(unittest.TestCase):
    def test_non_straight(self):
        self.assertIsNone(straight_high([14, 13, 12, 11, 9]))

    def test_broadway(self):
        self.assertEqual(straight_high([10, 11, 12, 13, 14]), 14)


if __name__ == "__main__":
    unittest.main()
