import unittest

from deepsix_core.cards import parse_card
from deepsix_trainer.river_hand_features import (
    all_exact_river_hand_features,
    exact_river_hand_features,
    feature_borda_quantile_bucket_map,
)
from deepsix_trainer.river_microgame import RangeHand
from deepsix_trainer.river_multisize_one_raise_scalable import (
    ScalableRiverMultiSizeOneRaiseConfig,
)
from deepsix_trainer.river_state_abstraction import RiverStateAbstractionError


def c(text):
    return parse_card(text)


def blocker_config():
    return ScalableRiverMultiSizeOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=12,
        bet_sizes=(4, 8),
        raise_to=14,
        p0_range=(
            RangeHand((c("Kc"), c("9s"))),
            RangeHand((c("Jc"), c("Tc"))),
            RangeHand((c("9c"), c("7d"))),
            RangeHand((c("Th"), c("7h"))),
        ),
        p1_range=(
            RangeHand((c("Kc"), c("Qc")), weight=2.0),
            RangeHand((c("Kh"), c("Qh")), weight=1.0),
            RangeHand((c("Jh"), c("Th")), weight=1.5),
            RangeHand((c("Tc"), c("7s")), weight=0.5),
        ),
    )


def nut_config():
    return ScalableRiverMultiSizeOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("Jh"), c("7s")),
        pot=10,
        bet_sizes=(3, 6),
        raise_to=12,
        p0_range=(
            RangeHand((c("Tc"), c("9c"))),
            RangeHand((c("Kc"), c("8d"))),
        ),
        p1_range=(
            RangeHand((c("Th"), c("9h"))),
            RangeHand((c("Kh"), c("8c"))),
            RangeHand((c("9d"), c("8s"))),
        ),
    )


class RiverHandFeatureTests(unittest.TestCase):
    def test_exact_features_are_bounded_and_cover_every_configured_hand(self):
        cfg = blocker_config()
        features = all_exact_river_hand_features(cfg)
        self.assertEqual(len(features), len(cfg.p0_range) + len(cfg.p1_range))
        for item in features:
            item.validate()
            self.assertGreaterEqual(item.nutness, item.universal_equity)

    def test_blocked_weight_and_blocked_stronger_weight_are_measured_exactly(self):
        cfg = blocker_config()
        cards = tuple(sorted((c("Kc"), c("9s"))))
        features = exact_river_hand_features(cfg, 0, cards)
        # P1 total weight = 5.0. KcQc (weight 2.0) is blocked by Kc.
        self.assertAlmostEqual(features.blocked_range_weight_fraction, 2.0 / 5.0)
        self.assertGreater(features.blocked_stronger_weight_fraction, 0.0)
        self.assertLessEqual(features.blocked_stronger_weight_fraction, 1.0)

    def test_broadway_nut_has_no_strictly_stronger_universal_combo(self):
        cfg = nut_config()
        cards = tuple(sorted((c("Tc"), c("9c"))))
        features = exact_river_hand_features(cfg, 0, cards)
        self.assertEqual(features.nutness, 1.0)
        # Other tens can tie the broadway straight, so equity need not be 1.0.
        self.assertLessEqual(features.universal_equity, 1.0)
        self.assertGreater(features.universal_equity, 0.9)
        self.assertEqual(features.blocked_stronger_weight_fraction, 0.0)

    def test_feature_borda_buckets_are_deterministic_and_use_requested_count(self):
        cfg = blocker_config()
        first = feature_borda_quantile_bucket_map(cfg, 3)
        second = feature_borda_quantile_bucket_map(cfg, 3)
        self.assertEqual(first, second)
        self.assertEqual(first.bucket_count(0), 3)
        self.assertEqual(first.bucket_count(1), 3)

        identity_width = feature_borda_quantile_bucket_map(cfg, 99)
        self.assertEqual(identity_width.bucket_count(0), len(cfg.p0_range))
        self.assertEqual(identity_width.bucket_count(1), len(cfg.p1_range))

    def test_feature_builder_rejects_hand_outside_configured_range(self):
        cfg = blocker_config()
        with self.assertRaises(RiverStateAbstractionError):
            exact_river_hand_features(cfg, 0, tuple(sorted((c("As"), c("Ks")))))
        with self.assertRaises(RiverStateAbstractionError):
            feature_borda_quantile_bucket_map(cfg, 0)


if __name__ == "__main__":
    unittest.main()
