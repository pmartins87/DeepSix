import random
import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_trainer.hu_multistreet_chance_sampled_cfr import (
    ChanceSampledHuMultiStreetCFR,
    sample_fraction_index,
)
from deepsix_trainer.hu_multistreet_reference import HuMicrogameConfig, HuReferenceMicrogame
from deepsix_trainer.reach import PrivateReachVector


def cards(*texts):
    return tuple(parse_card(text) for text in texts)


def tiny_game():
    return HuReferenceMicrogame(
        HuMicrogameConfig(
            stake_cents=25,
            dealer_seat=0,
            stacks=((0, 51), (1, 51)),
            flop=cards("6c", "7d", "8h"),
            bbj_enabled=False,
        ),
        (
            PrivateReachVector.from_mapping(0, {cards("As", "Ks"): 1}),
            PrivateReachVector.from_mapping(1, {cards("Qc", "Jc"): 1}),
        ),
    )


class ChanceSampledHuMultiStreetCFRTests(unittest.TestCase):
    def test_exact_fraction_sampler_respects_weighted_support(self):
        rng = random.Random(20260827)
        probabilities = (Fraction(1, 4), Fraction(3, 4))
        counts = [0, 0]
        for _ in range(4000):
            counts[sample_fraction_index(rng, probabilities)] += 1
        self.assertEqual(sum(counts), 4000)
        self.assertGreater(counts[0], 850)
        self.assertLess(counts[0], 1150)

    def test_same_seed_is_bit_deterministic(self):
        left = ChanceSampledHuMultiStreetCFR(tiny_game(), algorithm_seed=17)
        right = ChanceSampledHuMultiStreetCFR(tiny_game(), algorithm_seed=17)
        left.train(4)
        right.train(4)
        self.assertEqual(left.semantic_snapshot(), right.semantic_snapshot())
        self.assertEqual(
            left.average_policy().fingerprint(),
            right.average_policy().fingerprint(),
        )

    def test_split_training_preserves_rng_and_solver_identity(self):
        continuous = ChanceSampledHuMultiStreetCFR(tiny_game(), algorithm_seed=99)
        split = ChanceSampledHuMultiStreetCFR(tiny_game(), algorithm_seed=99)
        continuous.train(6)
        split.train(2)
        split.train(4)
        self.assertEqual(continuous.semantic_snapshot(), split.semantic_snapshot())

    def test_sampling_counters_and_exact_policy_adapter(self):
        solver = ChanceSampledHuMultiStreetCFR(tiny_game(), algorithm_seed=5)
        solver.train(3)
        stats = solver.stats()
        self.assertEqual(stats.iterations, 3)
        self.assertEqual(stats.private_deals_sampled, 3)
        self.assertGreater(stats.public_chance_events_sampled, 0)
        self.assertGreater(stats.terminal_visits, 0)
        self.assertGreater(len(solver.nodes), 0)

        exact_policy = solver.average_policy().to_exact_policy()
        for row in exact_policy.rows.values():
            self.assertEqual(sum(row.probabilities, Fraction(0, 1)), Fraction(1, 1))

    def test_bad_seed_and_iterations_fail_closed(self):
        with self.assertRaises(ValueError):
            ChanceSampledHuMultiStreetCFR(tiny_game(), algorithm_seed=-1)
        solver = ChanceSampledHuMultiStreetCFR(tiny_game(), algorithm_seed=1)
        with self.assertRaises(ValueError):
            solver.train(0)


if __name__ == "__main__":
    unittest.main()
