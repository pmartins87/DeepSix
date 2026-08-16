import unittest
from itertools import product

from deepsix_core.cards import parse_card
from deepsix_trainer.river_microgame import (
    RangeHand,
    RiverMicrogameConfig,
    RiverPolicy,
    expected_value as single_expected_value,
    exploitability as single_exploitability,
)
from deepsix_trainer.river_multisize import (
    RiverMultiSizeCFR,
    RiverMultiSizeConfig,
    RiverMultiSizeError,
    RiverMultiSizePolicy,
    best_response_value_player0,
    best_response_value_player1,
    expected_value,
    exploitability,
    uniform_policy,
)


def c(text):
    return parse_card(text)


def ranges():
    p0 = (
        RangeHand((c("Tc"), c("7d"))),
        RangeHand((c("Kc"), c("9s"))),
        RangeHand((c("Jc"), c("Tc"))),
    )
    p1 = (
        RangeHand((c("Th"), c("7s"))),
        RangeHand((c("Kh"), c("9d"))),
        RangeHand((c("Jh"), c("Th"))),
    )
    return p0, p1


def multi_config(*sizes):
    p0, p1 = ranges()
    return RiverMultiSizeConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=12,
        bet_sizes=tuple(sizes),
        p0_range=p0,
        p1_range=p1,
    )


def single_uniform_policy(config):
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


def whole_policy_pure_overrides(config, player):
    base = uniform_policy(config)
    keys = sorted(
        (key for key in base.strategies if key[0] == player),
        key=lambda key: (key[1], key[2]),
    )
    action_ranges = [range(len(base.strategies[key])) for key in keys]
    for selected in product(*action_ranges):
        strategies = dict(base.strategies)
        for key, action_index in zip(keys, selected):
            arity = len(strategies[key])
            strategies[key] = tuple(
                1.0 if index == action_index else 0.0 for index in range(arity)
            )
        yield RiverMultiSizePolicy(strategies)


class RiverMultiSizeTests(unittest.TestCase):
    def test_one_size_is_exactly_equivalent_to_v1_uniform_game(self):
        p0, p1 = ranges()
        single = RiverMicrogameConfig(
            board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
            pot=12,
            bet=8,
            p0_range=p0,
            p1_range=p1,
        )
        multi = multi_config(8)
        single_policy = single_uniform_policy(single)
        multi_policy = uniform_policy(multi)
        self.assertAlmostEqual(
            expected_value(multi, multi_policy, multi_policy),
            single_expected_value(single, single_policy, single_policy),
            places=12,
        )
        self.assertAlmostEqual(
            exploitability(multi, multi_policy),
            single_exploitability(single, single_policy),
            places=12,
        )

    def test_two_size_exact_best_response_matches_whole_policy_bruteforce(self):
        # Reduce to two hands/player so exhaustive whole-range pure-policy
        # enumeration remains a genuinely independent but cheap oracle.
        base = multi_config(4, 8)
        config = RiverMultiSizeConfig(
            board=base.board,
            pot=base.pot,
            bet_sizes=base.bet_sizes,
            p0_range=base.p0_range[:2],
            p1_range=base.p1_range[:2],
        )
        opponent = uniform_policy(config)
        brute0 = max(
            expected_value(config, candidate, opponent)
            for candidate in whole_policy_pure_overrides(config, 0)
        )
        brute1 = min(
            expected_value(config, opponent, candidate)
            for candidate in whole_policy_pure_overrides(config, 1)
        )
        self.assertAlmostEqual(
            best_response_value_player0(config, opponent), brute0, places=12
        )
        self.assertAlmostEqual(
            best_response_value_player1(config, opponent), brute1, places=12
        )

    def test_two_size_cfr_reduces_exact_exploitability(self):
        config = multi_config(4, 8)
        initial = exploitability(config, uniform_policy(config))
        trainer = RiverMultiSizeCFR(config)
        trainer.train(25000)
        policy = trainer.average_policy()
        final = exploitability(config, policy)
        self.assertLess(final, initial * 0.12)
        self.assertLess(final / config.pot, 0.025)
        self.assertEqual(trainer.iterations, 25000)

    def test_two_size_training_is_deterministic_and_resumable(self):
        config = multi_config(4, 8)
        first = RiverMultiSizeCFR(config)
        second = RiverMultiSizeCFR(config)
        first.train(1500)
        second.train(750)
        second.train(750)
        self.assertEqual(first.average_policy().strategies, second.average_policy().strategies)
        self.assertEqual(
            exploitability(config, first.average_policy()),
            exploitability(config, second.average_policy()),
        )

    def test_exact_best_response_handles_four_size_action_abstraction(self):
        config = multi_config(3, 5, 8, 12)
        policy = uniform_policy(config)
        value = expected_value(config, policy, policy)
        self.assertGreaterEqual(best_response_value_player0(config, policy) + 1e-12, value)
        self.assertLessEqual(best_response_value_player1(config, policy) - 1e-12, value)

    def test_invalid_size_sets_are_rejected(self):
        p0, p1 = ranges()
        kwargs = dict(
            board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
            pot=12,
            p0_range=p0,
            p1_range=p1,
        )
        for sizes in ((), (8, 8), (8, 4), (0, 4), (1, 2, 3, 4, 5)):
            with self.subTest(sizes=sizes):
                with self.assertRaises(RiverMultiSizeError):
                    RiverMultiSizeConfig(bet_sizes=sizes, **kwargs).validate()


if __name__ == "__main__":
    unittest.main()
