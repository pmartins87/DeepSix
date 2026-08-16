"""Reference vectors transcribed from PokerKit ShortDeckHoldemHand doctests.

Primary-source snapshot:
uoftcprg/pokerkit@5841c0afe4d6eb71ae5db0f8a6a376ee3e329afb
pokerkit/hands.py and pokerkit/lookups.py.
"""

import unittest

from deepsix_core.cards import parse_card
from deepsix_core.evaluator import HandCategory, evaluate_five


def hand(text):
    return evaluate_five(
        tuple(parse_card(text[i : i + 2]) for i in range(0, len(text), 2))
    )


class PokerKitReferenceVectorTests(unittest.TestCase):
    def test_documented_shortdeck_order_chain(self):
        h0 = hand("6c7d8h9sJc")
        h1 = hand("7c7d7hTsQc")
        h2 = hand("As6c7h8h9h")
        h3 = hand("AsAhKcKhKd")
        h4 = hand("6s7s8sTsQs")
        self.assertLess(h0, h1)
        self.assertLess(h1, h2)
        self.assertLess(h2, h3)
        self.assertLess(h3, h4)
        self.assertEqual(h1.category, HandCategory.THREE_OF_A_KIND)
        self.assertEqual(h2.category, HandCategory.STRAIGHT)
        self.assertEqual(h3.category, HandCategory.FULL_HOUSE)
        self.assertEqual(h4.category, HandCategory.FLUSH)

    def test_documented_a6789_lookup_vector(self):
        self.assertEqual(hand("Ah6h7s8c9s").category, HandCategory.STRAIGHT)


if __name__ == "__main__":
    unittest.main()
