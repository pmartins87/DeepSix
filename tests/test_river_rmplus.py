import unittest

from deepsix_core.cards import parse_card
from deepsix_trainer.river_microgame import RangeHand
from deepsix_trainer.river_multisize_one_raise_scalable import (
    ScalableRiverMultiSizeOneRaiseConfig,
)
from deepsix_trainer.river_rmplus import RiverRMPlusError, RiverRegretMatchingPlus


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


class RiverRegretMatchingPlusTests(unittest.TestCase):
    def test_regrets_are_clipped_nonnegative_after_every_iteration(self):
        trainer = RiverRegretMatchingPlus(config())
        for _ in range(10):
            trainer.train(1)
            self.assertTrue(trainer.all_regrets_nonnegative())

    def test_training_is_deterministic_and_resumable_with_linear_averaging(self):
        cfg = config()
        split = RiverRegretMatchingPlus(cfg, averaging_delay=50, linear_averaging=True)
        single = RiverRegretMatchingPlus(cfg, averaging_delay=50, linear_averaging=True)
        split.train(300)
        split.train(300)
        single.train(600)
        self.assertEqual(split.average_policy(), single.average_policy())
        self.assertAlmostEqual(
            split.exact_exploitability(),
            single.exact_exploitability(),
            places=12,
        )

    def test_uniform_weighted_averaging_is_also_resumable(self):
        cfg = config()
        split = RiverRegretMatchingPlus(cfg, averaging_delay=20, linear_averaging=False)
        single = RiverRegretMatchingPlus(cfg, averaging_delay=20, linear_averaging=False)
        split.train(150)
        split.train(150)
        single.train(300)
        self.assertEqual(split.average_policy(), single.average_policy())

    def test_rmplus_substantially_reduces_exact_exploitability(self):
        cfg = config()
        trainer = RiverRegretMatchingPlus(cfg, averaging_delay=50)
        initial = trainer.exact_exploitability()
        trainer.train(1200)
        final = trainer.exact_exploitability()
        self.assertLess(final, initial * 0.15)
        self.assertLess(final, cfg.pot * 0.03)

    def test_delay_larger_than_training_keeps_uniform_average_policy(self):
        cfg = config()
        trainer = RiverRegretMatchingPlus(cfg, averaging_delay=1000)
        baseline = trainer.average_policy()
        trainer.train(20)
        self.assertEqual(trainer.average_policy(), baseline)
        self.assertTrue(trainer.all_regrets_nonnegative())

    def test_invalid_configuration_is_rejected(self):
        cfg = config()
        with self.assertRaises(RiverRMPlusError):
            RiverRegretMatchingPlus(cfg, averaging_delay=-1)
        with self.assertRaises(RiverRMPlusError):
            RiverRegretMatchingPlus(cfg, linear_averaging=1)
        trainer = RiverRegretMatchingPlus(cfg)
        with self.assertRaises(RiverRMPlusError):
            trainer.train(0)


if __name__ == "__main__":
    unittest.main()
