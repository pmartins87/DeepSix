import unittest

from deepsix_core.evaluator import evaluate_best
from deepsix_trainer.river_lab_fixtures import FIXTURE_SPECS, benchmark_fixture_battery, build_fixture


class RiverLabFixtureTests(unittest.TestCase):
    def test_battery_has_six_named_distinct_textures(self):
        self.assertEqual(len(FIXTURE_SPECS), 6)
        names = tuple(spec.name for spec in FIXTURE_SPECS)
        self.assertEqual(len(set(names)), len(names))

    def test_fixture_generation_is_deterministic(self):
        for spec in FIXTURE_SPECS:
            with self.subTest(spec=spec.name):
                self.assertEqual(build_fixture(spec), build_fixture(spec))

    def test_ranges_are_exactly_sampled_and_distinct(self):
        for spec, cfg in benchmark_fixture_battery():
            with self.subTest(spec=spec.name):
                self.assertEqual(len(cfg.p0_range), spec.range_size)
                self.assertEqual(len(cfg.p1_range), spec.range_size)
                board = set(cfg.board)
                p0 = {hand.canonical_cards() for hand in cfg.p0_range}
                p1 = {hand.canonical_cards() for hand in cfg.p1_range}
                self.assertEqual(len(p0), spec.range_size)
                self.assertEqual(len(p1), spec.range_size)
                self.assertFalse(p0 & p1)
                for cards in p0 | p1:
                    self.assertFalse(set(cards) & board)
                self.assertGreater(len(cfg.compatible_deals()), 0)

    def test_each_range_spans_multiple_terminal_strengths(self):
        # The battery samples quantiles of the complete HandValue ordering, not
        # categories.  On some textures (notably double-paired boards) a broad
        # strength span can legitimately occupy only two HandCategories.  The
        # correct invariant is therefore multiple exact strengths plus multiple
        # categories, not an arbitrary requirement of three categories.
        for spec, cfg in benchmark_fixture_battery():
            with self.subTest(spec=spec.name):
                for hands in (cfg.p0_range, cfg.p1_range):
                    values = {
                        evaluate_best(hand.canonical_cards() + cfg.board)
                        for hand in hands
                    }
                    categories = {value.category for value in values}
                    self.assertGreaterEqual(len(values), 3)
                    self.assertGreaterEqual(len(categories), 2)

    def test_action_parameters_are_legal_for_every_fixture(self):
        for spec, cfg in benchmark_fixture_battery():
            with self.subTest(spec=spec.name):
                cfg.validate()
                self.assertGreater(cfg.raise_to, max(cfg.bet_sizes))
                self.assertGreater(cfg.pot, 0)


if __name__ == "__main__":
    unittest.main()
