import unittest
from fractions import Fraction

from deepsix_core.ggpoker_economy import (
    GGPOKER_SHORTDECK_ECONOMY_VERSION,
    GGPOKER_SHORTDECK_STAKES,
    ggpoker_shortdeck_bbj_contribution,
    ggpoker_shortdeck_rake_config,
    ggpoker_shortdeck_stake,
)
from deepsix_core.rake import RakeError, compute_exact_rake


class GGPokerEconomyTests(unittest.TestCase):
    def test_schedule_contains_all_nine_published_cash_stakes(self):
        self.assertEqual(
            tuple(stake.stake_cents for stake in GGPOKER_SHORTDECK_STAKES),
            (2, 5, 10, 25, 50, 100, 200, 500, 1000),
        )
        self.assertTrue(GGPOKER_SHORTDECK_ECONOMY_VERSION.endswith("_v1"))

    def test_low_and_middle_caps_are_player_count_specific(self):
        stake = ggpoker_shortdeck_stake(25)
        self.assertEqual(stake.default_buy_in_cents, 1000)
        self.assertEqual(stake.cap_for_players(2), 13)
        self.assertEqual(stake.cap_for_players(3), 25)
        self.assertEqual(stake.cap_for_players(4), 38)
        self.assertEqual(stake.cap_for_players(5), 50)
        self.assertEqual(stake.cap_for_players(6), 50)

    def test_high_stakes_bb_caps_are_converted_exactly_to_cents(self):
        self.assertEqual(
            (
                ggpoker_shortdeck_stake(200).cap_for_players(2),
                ggpoker_shortdeck_stake(200).cap_for_players(4),
                ggpoker_shortdeck_stake(500).cap_for_players(3),
                ggpoker_shortdeck_stake(1000).cap_for_players(5),
            ),
            (76, 226, 375, 1500),
        )

    def test_rake_profile_is_five_percent_with_published_cap(self):
        config = ggpoker_shortdeck_rake_config(stake_cents=10, dealt_players=6)
        self.assertEqual(config.rate, Fraction(5, 100))
        self.assertEqual(config.cap_units, 30)
        self.assertFalse(config.no_rake_preflop)
        self.assertIsNone(config.no_rake_at_or_below)

        uncapped = compute_exact_rake(200, ended_preflop=False, config=config)
        self.assertEqual(uncapped.rake_before_client_rounding, 10)
        capped = compute_exact_rake(1000, ended_preflop=False, config=config)
        self.assertEqual(capped.rake_before_client_rounding, 30)

    def test_published_table_profile_does_not_invent_preflop_exemption(self):
        config = ggpoker_shortdeck_rake_config(stake_cents=50, dealt_players=2)
        result = compute_exact_rake(100, ended_preflop=True, config=config)
        self.assertTrue(result.eligible)
        self.assertEqual(result.rake_before_client_rounding, 5)

    def test_bbj_threshold_is_inclusive_at_one_hundred_antes(self):
        self.assertEqual(ggpoker_shortdeck_bbj_contribution(999, ante_units=10), 0)
        self.assertEqual(ggpoker_shortdeck_bbj_contribution(1000, ante_units=10), 10)
        self.assertEqual(ggpoker_shortdeck_bbj_contribution(5000, ante_units=10), 10)

    def test_invalid_stake_player_count_and_ante_are_rejected(self):
        with self.assertRaises(RakeError):
            ggpoker_shortdeck_stake(3)
        with self.assertRaises(RakeError):
            ggpoker_shortdeck_rake_config(stake_cents=25, dealt_players=1)
        with self.assertRaises(RakeError):
            ggpoker_shortdeck_bbj_contribution(100, ante_units=0)


if __name__ == "__main__":
    unittest.main()
