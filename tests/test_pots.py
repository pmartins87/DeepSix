import random
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

    def test_5000_randomized_2_to_6_player_layers_preserve_exact_invariants(self):
        rng = random.Random(20260826)
        cases = 0
        for player_count in range(2, 7):
            for _ in range(1000):
                contributions = {
                    seat: rng.randint(0, 250)
                    for seat in range(player_count)
                }
                if not any(contributions.values()):
                    contributions[rng.randrange(player_count)] = rng.randint(1, 250)

                # Keep at least one deepest contributor live. This is sufficient
                # to guarantee that every lower layer also has an eligible seat.
                deepest = max(contributions.values())
                deepest_seats = [
                    seat for seat, value in contributions.items() if value == deepest
                ]
                protected = rng.choice(deepest_seats)
                folded = {
                    seat
                    for seat in range(player_count)
                    if seat != protected and rng.random() < 0.4
                }

                layers = build_pot_layers(contributions, folded)
                levels = sorted({value for value in contributions.values() if value > 0})
                self.assertEqual([layer.cap for layer in layers], levels)
                self.assertEqual(sum(layer.amount for layer in layers), sum(contributions.values()))

                previous = 0
                reconstructed = {seat: 0 for seat in contributions}
                for layer in layers:
                    contributors = tuple(
                        sorted(
                            seat
                            for seat, value in contributions.items()
                            if value >= layer.cap
                        )
                    )
                    eligible = tuple(seat for seat in contributors if seat not in folded)
                    width = layer.cap - previous
                    self.assertGreater(width, 0)
                    self.assertEqual(layer.contributors, contributors)
                    self.assertEqual(layer.eligible, eligible)
                    self.assertTrue(eligible)
                    self.assertEqual(layer.amount, width * len(contributors))
                    for seat in contributors:
                        reconstructed[seat] += width
                    previous = layer.cap

                self.assertEqual(reconstructed, contributions)
                cases += 1
        self.assertEqual(cases, 5000)


if __name__ == "__main__":
    unittest.main()
