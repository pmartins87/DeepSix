import unittest
from itertools import combinations

from deepsix_core.cards import NUM_CARDS
from deepsix_core.handclasses import (
    ALL_HAND_CLASSES,
    combo_count,
    hand_class_from_cards,
)


class ShortDeckHandClassTests(unittest.TestCase):
    def test_exactly_81_classes(self):
        self.assertEqual(len(ALL_HAND_CLASSES), 81)
        self.assertEqual(len(set(ALL_HAND_CLASSES)), 81)

    def test_combo_weights_sum_to_630(self):
        self.assertEqual(sum(combo_count(h) for h in ALL_HAND_CLASSES), 630)

    def test_every_exact_hole_combo_maps_to_one_class(self):
        counts = {hand: 0 for hand in ALL_HAND_CLASSES}
        for a, b in combinations(range(NUM_CARDS), 2):
            counts[hand_class_from_cards(a, b)] += 1
        self.assertEqual(sum(counts.values()), 630)
        for hand, count in counts.items():
            self.assertEqual(count, combo_count(hand), hand)


if __name__ == "__main__":
    unittest.main()
