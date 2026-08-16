import math
import unittest

from deepsix_core.cards import parse_card
from deepsix_trainer.river_microgame import RangeHand
from deepsix_trainer.river_multisize_one_raise import RiverMultiSizeOneRaiseError
from deepsix_trainer.river_multisize_one_raise_scalable import (
    MAX_SCALABLE_INITIAL_SIZES,
    RiverMultiSizeOneRaiseCFR,
    ScalableRiverMultiSizeOneRaiseConfig,
    exact_exploitability,
    pure_plan_count,
    uniform_policy,
)


def c(text):
    return parse_card(text)


def config(sizes, raise_to=18):
    return ScalableRiverMultiSizeOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=12,
        bet_sizes=tuple(sizes),
        raise_to=raise_to,
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


class ScalableMultiSizeOneRaiseTests(unittest.TestCase):
    def test_three_and_four_sizes_validate_without_enumerating_plans(self):
        three = config((2, 4, 8), raise_to=16)
        four = config((2, 4, 8, 12), raise_to=18)
        three.validate()
        four.validate()
        self.assertEqual(MAX_SCALABLE_INITIAL_SIZES, 4)
        self.assertEqual(pure_plan_count(three), 864)
        self.assertEqual(pure_plan_count(four), 6480)

    def test_four_size_dynamic_exploitability_is_finite(self):
        cfg = config((2, 4, 8, 12), raise_to=18)
        value = exact_exploitability(cfg, uniform_policy(cfg))
        self.assertTrue(math.isfinite(value))
        self.assertGreaterEqual(value, 0.0)

    def test_four_size_cfr_reduces_dynamic_exact_exploitability(self):
        cfg = config((2, 4, 8, 12), raise_to=18)
        initial = exact_exploitability(cfg, uniform_policy(cfg))
        trainer = RiverMultiSizeOneRaiseCFR(cfg)
        trainer.train(1200)
        final = exact_exploitability(cfg, trainer.average_policy())
        self.assertLess(final, initial * 0.2)
        self.assertLess(final, cfg.pot * 0.04)

    def test_four_size_training_is_deterministic_and_resumable(self):
        cfg = config((2, 4, 8, 12), raise_to=18)
        split = RiverMultiSizeOneRaiseCFR(cfg)
        single = RiverMultiSizeOneRaiseCFR(cfg)
        split.train(200)
        split.train(200)
        single.train(400)
        self.assertEqual(split.average_policy(), single.average_policy())
        self.assertAlmostEqual(
            exact_exploitability(cfg, split.average_policy()),
            exact_exploitability(cfg, single.average_policy()),
            places=12,
        )

    def test_more_than_four_sizes_remains_rejected(self):
        cfg = config((2, 4, 6, 8, 10), raise_to=18)
        with self.assertRaises(RiverMultiSizeOneRaiseError):
            cfg.validate()


if __name__ == "__main__":
    unittest.main()
