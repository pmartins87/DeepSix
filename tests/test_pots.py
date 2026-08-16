import unittest

from deepsix_core.pots import PotAccountingError, build_pot_layers


class PotAccountingTests(unittest.TestCase):
    def test_equal_contributions_make_one_pot(self):
        layers = build_pot_layers({0: 100, 1: 100, 2: 100})
        self.assertEqual(len(layers), 1)
        self.assertEqual(layers[0].amount, 300)
        self.assertEqual(layers[0].eligible, (0, 1, 2))

    def test_three_allin_levels(self):
        layers = build_pot_layers({0: 50, 1: 100, 2: 200})
        self.assertEqual([p.amount for p in layers], [150, 100, 100])
        self.assertEqual([p.eligible for p in layers], [(0, 1, 2), (1, 2), (2,)])
        self.assertEqual(sum(p.amount for p in layers), 350)

    def test_folded_chips_remain_but_player_is_ineligible(self):
        layers = build_pot_layers({0: 100, 1: 100, 2: 50}, folded={1})
        self.assertEqual([p.amount for p in layers], [150, 100])
        self.assertEqual(layers[0].eligible, (0, 2))
        self.assertEqual(layers[1].eligible, (0,))

    def test_zero_contributor_does_not_create_layer(self):
        layers = build_pot_layers({0: 0, 1: 10, 2: 10})
        self.assertEqual(len(layers), 1)
        self.assertEqual(layers[0].amount, 20)

    def test_invalid_negative_contribution_rejected(self):
        with self.assertRaises(PotAccountingError):
            build_pot_layers({0: -1, 1: 10})

    def test_layer_with_only_folded_eligibles_rejected(self):
        with self.assertRaises(PotAccountingError):
            build_pot_layers({0: 100, 1: 50}, folded={0, 1})


if __name__ == "__main__":
    unittest.main()
