import unittest

from deepsix_core.cards import parse_card
from deepsix_trainer.river_counterfactual_features import (
    all_exact_uniform_counterfactual_features,
    cfv_kmedoids_bucket_map,
    exact_uniform_counterfactual_features,
)
from deepsix_trainer.river_microgame import RangeHand
from deepsix_trainer.river_multisize_one_raise_scalable import (
    ScalableRiverMultiSizeOneRaiseConfig,
)
from deepsix_trainer.river_state_abstraction import RiverStateAbstractionError


def c(text):
    return parse_card(text)


def strategic_config():
    return ScalableRiverMultiSizeOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("Jh"), c("7s")),
        pot=10,
        bet_sizes=(3,),
        raise_to=10,
        p0_range=(
            RangeHand((c("Tc"), c("8c"))),  # Broadway straight.
            RangeHand((c("6c"), c("8d"))),  # High-card hand on this board.
            RangeHand((c("Kc"), c("Kh"))),  # Trips, below a straight in 6+.
        ),
        p1_range=(
            RangeHand((c("Td"), c("6d")), weight=2.0),
            RangeHand((c("9h"), c("9s")), weight=1.0),
            RangeHand((c("Qc"), c("Qh")), weight=1.5),
        ),
    )


class RiverCounterfactualFeatureTests(unittest.TestCase):
    def test_exact_cfv_features_cover_every_hand_and_have_stable_dimensions(self):
        cfg = strategic_config()
        features = all_exact_uniform_counterfactual_features(cfg)
        self.assertEqual(len(features), len(cfg.p0_range) + len(cfg.p1_range))
        for item in features:
            item.validate()

        p0_dimensions = {
            len(item.normalized_cfv_vector)
            for item in features
            if item.player == 0
        }
        p1_dimensions = {
            len(item.normalized_cfv_vector)
            for item in features
            if item.player == 1
        }
        self.assertEqual(len(p0_dimensions), 1)
        self.assertEqual(len(p1_dimensions), 1)
        self.assertGreater(next(iter(p0_dimensions)), 0)
        self.assertGreater(next(iter(p1_dimensions)), 0)

    def test_cfv_vector_detects_opposite_fold_call_incentives(self):
        cfg = strategic_config()
        nut_cards = tuple(sorted((c("Tc"), c("8c"))))
        weak_cards = tuple(sorted((c("6c"), c("8d"))))
        nut = exact_uniform_counterfactual_features(cfg, 0, nut_cards)
        weak = exact_uniform_counterfactual_features(cfg, 0, weak_cards)

        history = ("b3", "r")
        nut_values = next(item for item in nut.histories if item.history == history)
        weak_values = next(item for item in weak.histories if item.history == history)
        self.assertEqual(nut_values.actions, ("f", "c"))
        self.assertEqual(weak_values.actions, ("f", "c"))
        nut_fold, nut_call = nut_values.action_values
        weak_fold, weak_call = weak_values.action_values

        self.assertGreater(nut_call, nut_fold)
        self.assertGreater(weak_fold, weak_call)
        self.assertNotEqual(nut.normalized_cfv_vector, weak.normalized_cfv_vector)

    def test_cfv_kmedoids_is_deterministic_and_respects_requested_width(self):
        cfg = strategic_config()
        first = cfv_kmedoids_bucket_map(cfg, 2)
        second = cfv_kmedoids_bucket_map(cfg, 2)
        self.assertEqual(first, second)
        self.assertEqual(first.bucket_count(0), 2)
        self.assertEqual(first.bucket_count(1), 2)

        identity_width = cfv_kmedoids_bucket_map(cfg, 99)
        self.assertEqual(identity_width.bucket_count(0), len(cfg.p0_range))
        self.assertEqual(identity_width.bucket_count(1), len(cfg.p1_range))

    def test_invalid_inputs_are_rejected(self):
        cfg = strategic_config()
        with self.assertRaises(RiverStateAbstractionError):
            exact_uniform_counterfactual_features(
                cfg,
                0,
                tuple(sorted((c("As"), c("Ks")))),
            )
        with self.assertRaises(RiverStateAbstractionError):
            exact_uniform_counterfactual_features(
                cfg,
                2,
                tuple(sorted((c("Tc"), c("8c")))),
            )
        with self.assertRaises(RiverStateAbstractionError):
            cfv_kmedoids_bucket_map(cfg, 0)


if __name__ == "__main__":
    unittest.main()
