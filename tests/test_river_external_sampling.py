import unittest

from deepsix_core.cards import parse_card
from deepsix_trainer.river_external_sampling import RiverExternalSamplingMCCFR
from deepsix_trainer.river_microgame import RangeHand
from deepsix_trainer.river_multisize_one_raise import RiverMultiSizeOneRaiseError, uniform_policy
from deepsix_trainer.river_multisize_one_raise_dpbr import exploitability_dp
from deepsix_trainer.river_multisize_one_raise_scalable import (
    ScalableRiverMultiSizeOneRaiseConfig,
)


def c(text):
    return parse_card(text)


def config():
    return ScalableRiverMultiSizeOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=12,
        bet_sizes=(4, 8),
        raise_to=14,
        p0_range=(
            RangeHand((c("Tc"), c("7d"))),
            RangeHand((c("Kc"), c("9s"))),
            RangeHand((c("Jc"), c("Tc"))),
        ),
        p1_range=(
            RangeHand((c("Th"), c("7s"))),
            RangeHand((c("Kh"), c("9d"))),
            RangeHand((c("Jh"), c("Th"))),
        ),
    )


class RiverExternalSamplingMCCFRTests(unittest.TestCase):
    def test_same_seed_is_exactly_deterministic(self):
        cfg = config()
        left = RiverExternalSamplingMCCFR(cfg, seed=1234)
        right = RiverExternalSamplingMCCFR(cfg, seed=1234)
        left.train(300)
        right.train(300)
        self.assertEqual(left.average_policy(), right.average_policy())
        self.assertEqual(left.sampled_deals, right.sampled_deals)
        self.assertEqual(left.nodes_visited, right.nodes_visited)

    def test_split_training_matches_single_run(self):
        cfg = config()
        split = RiverExternalSamplingMCCFR(cfg, seed=991)
        single = RiverExternalSamplingMCCFR(cfg, seed=991)
        split.train(150)
        split.train(150)
        single.train(300)
        self.assertEqual(split.average_policy(), single.average_policy())
        self.assertEqual(split.iterations, single.iterations)
        self.assertEqual(split.sampled_deals, 300)
        self.assertEqual(split.nodes_visited, single.nodes_visited)

    def test_sampling_candidate_reduces_exact_exploitability(self):
        cfg = config()
        initial = exploitability_dp(cfg, uniform_policy(cfg))
        trainer = RiverExternalSamplingMCCFR(cfg, seed=20260826)
        trainer.train(4000)
        final = exploitability_dp(cfg, trainer.average_policy())
        self.assertLess(final, initial)
        self.assertTrue(trainer.all_regrets_finite())
        self.assertEqual(trainer.sampled_deals, 4000)

    def test_invalid_seed_and_iteration_count_are_rejected(self):
        cfg = config()
        with self.assertRaises(RiverMultiSizeOneRaiseError):
            RiverExternalSamplingMCCFR(cfg, seed=-1)
        trainer = RiverExternalSamplingMCCFR(cfg)
        with self.assertRaises(RiverMultiSizeOneRaiseError):
            trainer.train(0)


if __name__ == "__main__":
    unittest.main()
