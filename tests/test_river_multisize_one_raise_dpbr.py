import unittest

from deepsix_core.cards import parse_card
from deepsix_trainer.river_microgame import RangeHand
from deepsix_trainer.river_multisize_one_raise import (
    RiverMultiSizeOneRaiseCFR,
    RiverMultiSizeOneRaiseConfig,
    best_response_value_player0,
    best_response_value_player1,
    exploitability,
    uniform_policy,
)
from deepsix_trainer.river_multisize_one_raise_dpbr import (
    DynamicBestResponseError,
    best_response_value_player0_dp,
    best_response_value_player1_dp,
    exploitability_dp,
)


def c(text):
    return parse_card(text)


def config(sizes=(4, 8), raise_to=14):
    return RiverMultiSizeOneRaiseConfig(
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


class DynamicExactBestResponseTests(unittest.TestCase):
    def assert_oracles_equal(self, cfg, policy):
        enum0 = best_response_value_player0(cfg, policy)
        enum1 = best_response_value_player1(cfg, policy)
        dp0 = best_response_value_player0_dp(cfg, policy)
        dp1 = best_response_value_player1_dp(cfg, policy)
        self.assertAlmostEqual(dp0, enum0, places=11)
        self.assertAlmostEqual(dp1, enum1, places=11)
        self.assertAlmostEqual(
            exploitability_dp(cfg, policy),
            exploitability(cfg, policy),
            places=11,
        )

    def test_uniform_one_size_matches_enumerative_oracle(self):
        cfg = config(sizes=(4,), raise_to=10)
        self.assert_oracles_equal(cfg, uniform_policy(cfg))

    def test_uniform_two_size_matches_enumerative_oracle(self):
        cfg = config()
        self.assert_oracles_equal(cfg, uniform_policy(cfg))

    def test_trained_two_size_policy_matches_enumerative_oracle(self):
        cfg = config()
        trainer = RiverMultiSizeOneRaiseCFR(cfg)
        trainer.train(250)
        self.assert_oracles_equal(cfg, trainer.average_policy())

    def test_weighted_ranges_match_enumerative_oracle(self):
        cfg = RiverMultiSizeOneRaiseConfig(
            board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
            pot=15,
            bet_sizes=(3, 9),
            raise_to=13,
            p0_range=(
                RangeHand((c("Tc"), c("7d")), weight=0.25),
                RangeHand((c("Kc"), c("9s")), weight=1.75),
            ),
            p1_range=(
                RangeHand((c("Th"), c("7s")), weight=2.0),
                RangeHand((c("Kh"), c("9d")), weight=0.4),
                RangeHand((c("Jh"), c("Th")), weight=0.8),
            ),
        )
        self.assert_oracles_equal(cfg, uniform_policy(cfg))

    def test_invalid_br_player_is_rejected_in_internal_entry(self):
        # Public wrappers cannot pass an invalid player. Importing the private
        # helper here is deliberate: this is a boundary guard regression test.
        from deepsix_trainer.river_multisize_one_raise_dpbr import _best_response_value

        cfg = config()
        with self.assertRaises(DynamicBestResponseError):
            _best_response_value(cfg, uniform_policy(cfg), 2)


if __name__ == "__main__":
    unittest.main()
