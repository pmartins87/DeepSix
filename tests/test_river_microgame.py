import unittest

from deepsix_core.cards import parse_card
from deepsix_core.evaluator import evaluate_best
from deepsix_trainer.river_microgame import (
    RangeHand,
    RiverCFR,
    RiverMicrogameConfig,
    RiverMicrogameError,
    RiverPolicy,
    best_response_value_player0,
    best_response_value_player1,
    expected_value,
    exploitability,
)


def c(text):
    return parse_card(text)


def three_level_config():
    # Each player has one high-card combo, one pair-of-kings combo and one
    # Broadway combo. Corresponding strength levels use different physical
    # cards, so all 3x3 ordered chance deals are compatible. The weak holdings
    # deliberately avoid 7+9 here: with A,8,6 on this Short Deck board that
    # would form the special A6789 straight rather than a high-card hand.
    return RiverMicrogameConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=12,
        bet=8,
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


def uniform_policy(config):
    strategies = {}
    for hand in config.p0_range:
        cards = hand.canonical_cards()
        for history in ("", "xb"):
            strategies[(0, cards, history)] = (0.5, 0.5)
    for hand in config.p1_range:
        cards = hand.canonical_cards()
        for history in ("x", "b"):
            strategies[(1, cards, history)] = (0.5, 0.5)
    return RiverPolicy(strategies)


def passive_policy(config):
    strategies = {}
    for hand in config.p0_range:
        cards = hand.canonical_cards()
        strategies[(0, cards, "")] = (1.0, 0.0)   # check
        strategies[(0, cards, "xb")] = (1.0, 0.0)  # fold
    for hand in config.p1_range:
        cards = hand.canonical_cards()
        strategies[(1, cards, "x")] = (1.0, 0.0)  # check
        strategies[(1, cards, "b")] = (1.0, 0.0)  # fold
    return RiverPolicy(strategies)


class RiverMicrogameTests(unittest.TestCase):
    def test_range_strengths_use_real_short_deck_evaluator(self):
        config = three_level_config()
        config.validate()
        board = config.board
        p0_values = [evaluate_best(hand.canonical_cards() + board) for hand in config.p0_range]
        p1_values = [evaluate_best(hand.canonical_cards() + board) for hand in config.p1_range]
        self.assertLess(p0_values[0], p0_values[1])
        self.assertLess(p0_values[1], p0_values[2])
        self.assertEqual(p0_values[0], p1_values[0])
        self.assertEqual(p0_values[1], p1_values[1])
        self.assertEqual(p0_values[2], p1_values[2])
        deals = config.compatible_deals()
        self.assertEqual(len(deals), 9)
        self.assertAlmostEqual(sum(deal.probability for deal in deals), 1.0)

    def test_all_check_policy_has_zero_value_in_symmetric_ranges(self):
        config = three_level_config()
        policy = passive_policy(config)
        self.assertAlmostEqual(expected_value(config, policy, policy), 0.0, places=12)
        self.assertGreater(exploitability(config, policy), 0.0)

    def test_exact_best_responses_bound_policy_value(self):
        config = three_level_config()
        policy = uniform_policy(config)
        value = expected_value(config, policy, policy)
        br0 = best_response_value_player0(config, policy)
        br1 = best_response_value_player1(config, policy)
        self.assertGreaterEqual(br0 + 1e-12, value)
        self.assertLessEqual(br1 - 1e-12, value)
        self.assertGreater(exploitability(config, policy), 0.0)

    def test_cfr_substantially_reduces_exact_exploitability(self):
        config = three_level_config()
        initial = exploitability(config, uniform_policy(config))
        trainer = RiverCFR(config)
        trainer.train(30000)
        policy = trainer.average_policy()
        final = exploitability(config, policy)
        self.assertLess(final, initial * 0.08)
        self.assertLess(final / config.pot, 0.02)
        self.assertEqual(trainer.iterations, 30000)

    def test_training_is_deterministic_and_resumable(self):
        config = three_level_config()
        first = RiverCFR(config)
        second = RiverCFR(config)
        first.train(2000)
        second.train(1000)
        second.train(1000)
        self.assertEqual(first.average_policy().strategies, second.average_policy().strategies)
        self.assertEqual(
            exploitability(config, first.average_policy()),
            exploitability(config, second.average_policy()),
        )

    def test_overlapping_board_or_invalid_money_is_rejected(self):
        config = three_level_config()
        bad = RiverMicrogameConfig(
            board=config.board,
            pot=0,
            bet=config.bet,
            p0_range=config.p0_range,
            p1_range=config.p1_range,
        )
        with self.assertRaises(RiverMicrogameError):
            bad.validate()
        overlap = RiverMicrogameConfig(
            board=config.board,
            pot=config.pot,
            bet=config.bet,
            p0_range=(RangeHand((config.board[0], c("7d"))),),
            p1_range=config.p1_range,
        )
        with self.assertRaises(RiverMicrogameError):
            overlap.validate()


if __name__ == "__main__":
    unittest.main()
