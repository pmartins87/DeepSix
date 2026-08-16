import unittest

from deepsix_core.rules import (
    GameRuleError,
    action_order_from_dealer,
    initial_ante_contributions,
)


class FrozenRuleTests(unittest.TestCase):
    def test_action_order_is_left_of_dealer_through_dealer(self):
        for n in range(2, 7):
            self.assertEqual(action_order_from_dealer(n), tuple(range(1, n)) + (0,))

    def test_dealer_posts_two_antes_total(self):
        for n in range(2, 7):
            contributions = initial_ante_contributions(n, 10)
            self.assertEqual(contributions[0], 20)
            self.assertTrue(all(x == 10 for x in contributions[1:]))
            self.assertEqual(sum(contributions), (n + 1) * 10)

    def test_invalid_counts_and_ante_rejected(self):
        for n in (0, 1, 7):
            with self.assertRaises(GameRuleError):
                action_order_from_dealer(n)
        for ante in (0, -1):
            with self.assertRaises(GameRuleError):
                initial_ante_contributions(6, ante)


if __name__ == "__main__":
    unittest.main()
