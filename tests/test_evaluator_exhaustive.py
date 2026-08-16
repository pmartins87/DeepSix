import unittest
from collections import Counter
from itertools import combinations

from deepsix_core.evaluator import HandCategory, evaluate_five


class ExhaustiveFiveCardDistributionTests(unittest.TestCase):
    def test_all_376992_five_card_hands_match_analytic_category_counts(self):
        counts = Counter(
            evaluate_five(combo).category for combo in combinations(range(36), 5)
        )
        expected = {
            HandCategory.HIGH_CARD: 122400,
            HandCategory.ONE_PAIR: 193536,
            HandCategory.TWO_PAIR: 36288,
            HandCategory.THREE_OF_A_KIND: 16128,
            HandCategory.STRAIGHT: 6120,
            HandCategory.FULL_HOUSE: 1728,
            HandCategory.FLUSH: 480,
            HandCategory.FOUR_OF_A_KIND: 288,
            HandCategory.STRAIGHT_FLUSH: 24,
        }
        self.assertEqual(counts, expected)
        self.assertEqual(sum(counts.values()), 376992)


if __name__ == "__main__":
    unittest.main()
