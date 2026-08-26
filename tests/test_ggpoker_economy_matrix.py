import unittest
from fractions import Fraction

from deepsix_core.ggpoker_economy import (
    GGPOKER_SHORTDECK_STAKES,
    ggpoker_shortdeck_bbj_contribution,
    ggpoker_shortdeck_rake_config,
)
from deepsix_core.rake import compute_exact_rake


# Golden v1 economic schedule. This intentionally duplicates the published-table
# values instead of deriving expected caps from the implementation under test.
GOLDEN_STAKES = (
    (2, 80, 2, 3, 5, 6),
    (5, 200, 4, 8, 11, 15),
    (10, 400, 8, 15, 23, 30),
    (25, 1000, 13, 25, 38, 50),
    (50, 2000, 25, 50, 75, 100),
    (100, 4000, 50, 100, 150, 200),
    (200, 8000, 76, 150, 226, 300),
    (500, 20000, 190, 375, 565, 750),
    (1000, 50000, 380, 750, 1130, 1500),
)


class GGPokerEconomyMatrixRegressionTests(unittest.TestCase):
    def test_full_published_stake_buyin_cap_matrix_matches_golden_v1(self):
        actual = tuple(
            (
                stake.stake_cents,
                stake.default_buy_in_cents,
                stake.cap_2p_cents,
                stake.cap_3p_cents,
                stake.cap_4p_cents,
                stake.cap_5plus_cents,
            )
            for stake in GGPOKER_SHORTDECK_STAKES
        )
        self.assertEqual(actual, GOLDEN_STAKES)

    def test_every_stake_and_player_count_has_exact_cap_transition(self):
        cap_index = {2: 2, 3: 3, 4: 4, 5: 5, 6: 5}
        cases = 0
        for row in GOLDEN_STAKES:
            stake_cents = row[0]
            for players in range(2, 7):
                cap = row[cap_index[players]]
                config = ggpoker_shortdeck_rake_config(
                    stake_cents=stake_cents,
                    dealt_players=players,
                )
                self.assertEqual(config.cap_units, cap)
                # Five percent reaches cap at cap*20. Check the exact rational
                # value immediately before, at, and after the transition.
                for pot in (max(1, cap * 20 - 1), cap * 20, cap * 20 + 1):
                    result = compute_exact_rake(
                        pot,
                        ended_preflop=False,
                        config=config,
                    )
                    expected = min(Fraction(pot, 20), Fraction(cap, 1))
                    self.assertEqual(result.rake_before_client_rounding, expected)
                    cases += 1
        self.assertEqual(cases, 9 * 5 * 3)

    def test_bbj_threshold_regression_across_all_nine_ante_units(self):
        for row in GOLDEN_STAKES:
            ante = row[0]
            threshold = 100 * ante
            self.assertEqual(
                ggpoker_shortdeck_bbj_contribution(threshold - 1, ante_units=ante),
                0,
            )
            self.assertEqual(
                ggpoker_shortdeck_bbj_contribution(threshold, ante_units=ante),
                ante,
            )
            self.assertEqual(
                ggpoker_shortdeck_bbj_contribution(threshold + 1, ante_units=ante),
                ante,
            )


if __name__ == "__main__":
    unittest.main()
