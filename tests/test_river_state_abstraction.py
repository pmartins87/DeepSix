import unittest

from deepsix_core.cards import parse_card
from deepsix_trainer.river_microgame import RangeHand
from deepsix_trainer.river_multisize_one_raise import RiverMultiSizeOneRaiseCFR
from deepsix_trainer.river_multisize_one_raise_dpbr import exploitability_dp
from deepsix_trainer.river_multisize_one_raise_scalable import (
    ScalableRiverMultiSizeOneRaiseConfig,
)
from deepsix_trainer.river_state_abstraction import (
    BucketedRiverCFR,
    RiverBucketMap,
    RiverStateAbstractionError,
    conditional_showdown_equity,
    equity_quantile_bucket_map,
    identity_bucket_map,
    showdown_category_bucket_map,
    single_bucket_map,
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
            RangeHand((c("Ts"), c("9c"))),
            RangeHand((c("Tc"), c("7d"))),
            RangeHand((c("Kc"), c("7h"))),
            RangeHand((c("Kc"), c("9s"))),
            RangeHand((c("Jc"), c("Tc"))),
        ),
        p1_range=(
            RangeHand((c("Td"), c("9h"))),
            RangeHand((c("Th"), c("7s"))),
            RangeHand((c("Kh"), c("7c"))),
            RangeHand((c("Kh"), c("9d"))),
            RangeHand((c("Jh"), c("Th"))),
        ),
    )


class RiverStateAbstractionTests(unittest.TestCase):
    def test_identity_bucket_training_is_exactly_equivalent_to_unabstracted_cfr(self):
        cfg = config()
        exact = RiverMultiSizeOneRaiseCFR(cfg)
        bucketed = BucketedRiverCFR(cfg, identity_bucket_map(cfg))
        exact.train(120)
        bucketed.train(120)
        self.assertEqual(bucketed.concrete_average_policy(), exact.average_policy())
        self.assertAlmostEqual(
            bucketed.exact_unabstracted_exploitability(),
            exploitability_dp(cfg, exact.average_policy()),
            places=12,
        )

    def test_single_bucket_compresses_infosets_and_shares_strategy(self):
        cfg = config()
        identity = BucketedRiverCFR(cfg, identity_bucket_map(cfg))
        single = BucketedRiverCFR(cfg, single_bucket_map(cfg))
        identity.train(20)
        single.train(20)
        self.assertLess(len(single.nodes), len(identity.nodes))
        self.assertEqual(single.bucket_map.bucket_count(0), 1)
        self.assertEqual(single.bucket_map.bucket_count(1), 1)

        policy = single.concrete_average_policy()
        p0_hands = [hand.canonical_cards() for hand in cfg.p0_range]
        first = policy.strategy(cfg, 0, p0_hands[0], ())
        for cards in p0_hands[1:]:
            self.assertEqual(policy.strategy(cfg, 0, cards, ()), first)

    def test_showdown_category_bucket_merges_distinct_same_category_hands(self):
        cfg = config()
        mapping = showdown_category_bucket_map(cfg)
        high_a = cfg.p0_range[0].canonical_cards()
        high_b = cfg.p0_range[1].canonical_cards()
        self.assertNotEqual(high_a, high_b)
        self.assertEqual(
            mapping.bucket_for(0, high_a),
            mapping.bucket_for(0, high_b),
        )
        self.assertLess(mapping.bucket_count(0), len(cfg.p0_range))

    def test_conditional_equity_is_blocker_aware_and_bounded(self):
        cfg = config()
        values = [
            conditional_showdown_equity(cfg, 0, hand.canonical_cards())
            for hand in cfg.p0_range
        ]
        self.assertTrue(all(0.0 <= value <= 1.0 for value in values))
        self.assertGreater(max(values), min(values))
        # The Broadway straight must have at least as much showdown equity as
        # a high-card hand in this fixed river range.
        self.assertGreaterEqual(values[-1], values[0])

    def test_equity_quantiles_are_deterministic_and_respect_requested_count(self):
        cfg = config()
        first = equity_quantile_bucket_map(cfg, 3)
        second = equity_quantile_bucket_map(cfg, 3)
        self.assertEqual(first, second)
        self.assertEqual(first.bucket_count(0), 3)
        self.assertEqual(first.bucket_count(1), 3)

        over = equity_quantile_bucket_map(cfg, 99)
        self.assertEqual(over.bucket_count(0), len(cfg.p0_range))
        self.assertEqual(over.bucket_count(1), len(cfg.p1_range))

    def test_exact_unabstracted_br_exposes_deliberately_coarse_policy_loss(self):
        cfg = config()
        identity = BucketedRiverCFR(cfg, identity_bucket_map(cfg))
        coarse = BucketedRiverCFR(cfg, single_bucket_map(cfg))
        identity.train(700)
        coarse.train(700)
        exact_loss = identity.exact_unabstracted_exploitability()
        coarse_loss = coarse.exact_unabstracted_exploitability()
        self.assertLess(exact_loss, cfg.pot * 0.04)
        self.assertGreater(coarse_loss, exact_loss * 2.0)

    def test_invalid_or_incomplete_bucket_map_is_rejected(self):
        cfg = config()
        with self.assertRaises(RiverStateAbstractionError):
            RiverBucketMap({}, name="empty").validate(cfg)
        with self.assertRaises(RiverStateAbstractionError):
            equity_quantile_bucket_map(cfg, 0)


if __name__ == "__main__":
    unittest.main()
