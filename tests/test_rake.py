import unittest
from fractions import Fraction

from deepsix_core.rake import (
    RakeConfig,
    RakeError,
    compute_exact_rake,
    shortdeck_percentage_cap_config,
)


class ExactRakeTests(unittest.TestCase):
    def config(self):
        return RakeConfig(
            rate=Fraction(3, 100),
            cap_units=30,
            no_rake_at_or_below=100,
        )

    def test_preflop_end_is_rake_free(self):
        result = compute_exact_rake(1000, ended_preflop=True, config=self.config())
        self.assertFalse(result.eligible)
        self.assertEqual(result.exemption_reason, "preflop_end")
        self.assertEqual(result.rake_before_client_rounding, 0)
        self.assertEqual(result.net_pot_before_client_rounding, 1000)

    def test_small_pot_threshold_is_inclusive(self):
        at_threshold = compute_exact_rake(
            100, ended_preflop=False, config=self.config()
        )
        self.assertFalse(at_threshold.eligible)
        self.assertEqual(at_threshold.exemption_reason, "small_pot")

        above = compute_exact_rake(101, ended_preflop=False, config=self.config())
        self.assertTrue(above.eligible)
        self.assertEqual(above.rake_before_client_rounding, Fraction(303, 100))
        self.assertTrue(above.requires_rounding)

    def test_exact_three_percent_without_rounding(self):
        result = compute_exact_rake(250, ended_preflop=False, config=self.config())
        self.assertEqual(result.percentage_rake, Fraction(15, 2))
        self.assertEqual(result.rake_before_client_rounding, Fraction(15, 2))
        self.assertEqual(result.net_pot_before_client_rounding, Fraction(485, 2))
        self.assertTrue(result.requires_rounding)

    def test_cap_is_applied_before_any_client_rounding(self):
        result = compute_exact_rake(5000, ended_preflop=False, config=self.config())
        self.assertEqual(result.percentage_rake, 150)
        self.assertEqual(result.cap, 30)
        self.assertEqual(result.rake_before_client_rounding, 30)
        self.assertFalse(result.requires_rounding)

    def test_explicit_short_table_multiplier_is_exact(self):
        config = RakeConfig(
            rate=Fraction(3, 100),
            cap_units=1000,
            table_size_multiplier=Fraction(1, 2),
        )
        result = compute_exact_rake(1000, ended_preflop=False, config=config)
        self.assertEqual(result.percentage_rake, 15)
        self.assertEqual(result.rake_before_client_rounding, 15)

    def test_player_count_is_not_silently_interpreted(self):
        full = RakeConfig(rate=Fraction(3, 100), cap_units=1000)
        half = RakeConfig(
            rate=Fraction(3, 100),
            cap_units=1000,
            table_size_multiplier=Fraction(1, 2),
        )
        self.assertEqual(
            compute_exact_rake(1000, ended_preflop=False, config=full).rake_before_client_rounding,
            30,
        )
        self.assertEqual(
            compute_exact_rake(1000, ended_preflop=False, config=half).rake_before_client_rounding,
            15,
        )

    def test_shortdeck_helper_converts_only_explicit_ante_multiples(self):
        config = shortdeck_percentage_cap_config(
            ante_units=10,
            cap_antes=3,
            no_rake_threshold_antes=10,
        )
        self.assertEqual(config.rate, Fraction(3, 100))
        self.assertEqual(config.cap_units, 30)
        self.assertEqual(config.no_rake_at_or_below, 100)

    def test_shortdeck_helper_can_leave_threshold_unresolved(self):
        config = shortdeck_percentage_cap_config(
            ante_units=10,
            cap_antes=3,
            no_rake_threshold_antes=None,
        )
        self.assertIsNone(config.no_rake_at_or_below)
        result = compute_exact_rake(10, ended_preflop=False, config=config)
        self.assertEqual(result.rake_before_client_rounding, Fraction(3, 10))

    def test_zero_pot_is_safe_even_without_threshold(self):
        config = RakeConfig(rate=Fraction(3, 100), cap_units=10)
        result = compute_exact_rake(0, ended_preflop=False, config=config)
        self.assertTrue(result.eligible)
        self.assertEqual(result.rake_before_client_rounding, 0)
        self.assertEqual(result.net_pot_before_client_rounding, 0)

    def test_invalid_values_are_rejected(self):
        bad_configs = (
            RakeConfig(rate=Fraction(-1, 100), cap_units=1),
            RakeConfig(rate=Fraction(101, 100), cap_units=1),
            RakeConfig(rate=Fraction(3, 100), cap_units=-1),
            RakeConfig(
                rate=Fraction(3, 100),
                cap_units=1,
                table_size_multiplier=Fraction(3, 2),
            ),
        )
        for config in bad_configs:
            with self.subTest(config=config), self.assertRaises(RakeError):
                config.validate()

        with self.assertRaises(RakeError):
            compute_exact_rake(-1, ended_preflop=False, config=self.config())
        with self.assertRaises(RakeError):
            shortdeck_percentage_cap_config(
                ante_units=0,
                cap_antes=3,
                no_rake_threshold_antes=10,
            )


if __name__ == "__main__":
    unittest.main()
