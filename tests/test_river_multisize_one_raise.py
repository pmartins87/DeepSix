import itertools
import unittest

from deepsix_core.cards import parse_card
from deepsix_trainer.river_microgame import RangeHand
from deepsix_trainer.river_one_raise import (
    RiverOneRaiseConfig,
    expected_value as one_raise_expected_value,
    exploitability as one_raise_exploitability,
    uniform_policy as one_raise_uniform,
)
from deepsix_trainer.river_multisize_one_raise import (
    RiverMultiSizeOneRaiseCFR,
    RiverMultiSizeOneRaiseConfig,
    RiverMultiSizeOneRaiseError,
    RiverMultiSizeOneRaisePolicy,
    best_response_value_player0,
    best_response_value_player1,
    expected_value,
    exploitability,
    legal_actions,
    player_histories,
    pure_plan_count,
    pure_plans_for_player,
    terminal_utility_p0,
    uniform_policy,
)


def c(text):
    return parse_card(text)


def ranges():
    return (
        (
            RangeHand((c("Tc"), c("7d"))),
            RangeHand((c("Kc"), c("9s"))),
            RangeHand((c("Jc"), c("Tc"))),
        ),
        (
            RangeHand((c("Th"), c("7s"))),
            RangeHand((c("Kh"), c("9d"))),
            RangeHand((c("Jh"), c("Th"))),
        ),
    )


def config(*, sizes=(4, 8), raise_to=14, p0_range=None, p1_range=None):
    default_p0, default_p1 = ranges()
    return RiverMultiSizeOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=12,
        bet_sizes=tuple(sizes),
        raise_to=raise_to,
        p0_range=default_p0 if p0_range is None else p0_range,
        p1_range=default_p1 if p1_range is None else p1_range,
    )


def policy_from_plan_map(cfg, player, plan_by_hand, fixed_other):
    strategies = dict(fixed_other.strategies)
    hands = cfg.p0_range if player == 0 else cfg.p1_range
    for hand in hands:
        cards = hand.canonical_cards()
        plan = plan_by_hand[cards]
        for history in player_histories(cfg, player):
            count = len(legal_actions(cfg, history))
            chosen = plan[history]
            strategies[(player, cards, history)] = tuple(
                1.0 if index == chosen else 0.0 for index in range(count)
            )
    return RiverMultiSizeOneRaisePolicy(strategies)


def independent_global_bruteforce(cfg, br_player, opponent):
    hands = cfg.p0_range if br_player == 0 else cfg.p1_range
    cards = [hand.canonical_cards() for hand in hands]
    plans = pure_plans_for_player(cfg, br_player)
    best = float("-inf") if br_player == 0 else float("inf")
    for combination in itertools.product(plans, repeat=len(cards)):
        plan_map = dict(zip(cards, combination))
        candidate = policy_from_plan_map(cfg, br_player, plan_map, opponent)
        value = (
            expected_value(cfg, candidate, opponent)
            if br_player == 0
            else expected_value(cfg, opponent, candidate)
        )
        best = max(best, value) if br_player == 0 else min(best, value)
    return best


class RiverMultiSizeOneRaiseTests(unittest.TestCase):
    def test_one_size_uniform_game_is_exactly_equivalent_to_one_raise_v1(self):
        p0, p1 = ranges()
        combined = config(sizes=(4,), raise_to=10, p0_range=p0, p1_range=p1)
        original = RiverOneRaiseConfig(
            board=combined.board,
            pot=combined.pot,
            bet_size=4,
            raise_to=10,
            p0_range=p0,
            p1_range=p1,
        )
        policy_combined = uniform_policy(combined)
        policy_original = one_raise_uniform(original)
        self.assertAlmostEqual(
            expected_value(combined, policy_combined, policy_combined),
            one_raise_expected_value(original, policy_original, policy_original),
            places=12,
        )
        self.assertAlmostEqual(
            exploitability(combined, policy_combined),
            one_raise_exploitability(original, policy_original),
            places=12,
        )

    def test_plan_count_scales_as_documented(self):
        one = config(sizes=(4,), raise_to=10)
        two = config(sizes=(4, 8), raise_to=14)
        self.assertEqual(pure_plan_count(one), 12)
        self.assertEqual(pure_plan_count(two), 108)
        self.assertEqual(len(pure_plans_for_player(two, 0)), 108)
        self.assertEqual(len(pure_plans_for_player(two, 1)), 108)

    def test_two_size_tree_and_terminal_accounting(self):
        cfg = config()
        win = next(deal for deal in cfg.compatible_deals() if deal.showdown_sign == 1)
        loss = next(deal for deal in cfg.compatible_deals() if deal.showdown_sign == -1)
        self.assertEqual(legal_actions(cfg, ()), ("x", "b4", "b8"))
        self.assertEqual(legal_actions(cfg, ("b4",)), ("f", "c", "r"))
        self.assertEqual(legal_actions(cfg, ("b8", "r")), ("f", "c"))

        self.assertEqual(terminal_utility_p0(cfg, win, ("b4", "f")), 6.0)
        self.assertEqual(terminal_utility_p0(cfg, win, ("b8", "c")), 14.0)
        self.assertEqual(terminal_utility_p0(cfg, win, ("b4", "r", "f")), -10.0)
        self.assertEqual(terminal_utility_p0(cfg, win, ("b8", "r", "c")), 20.0)
        self.assertEqual(terminal_utility_p0(cfg, win, ("x", "b8", "r", "f")), 14.0)
        self.assertEqual(terminal_utility_p0(cfg, loss, ("x", "b4", "r", "c")), -20.0)

    def test_two_size_exact_best_response_matches_global_bruteforce(self):
        # Two own hands exercise the decomposition; one opponent hand keeps the
        # independent global enumeration small enough for every CI run.
        cfg = config(
            p0_range=(
                RangeHand((c("Tc"), c("7d"))),
                RangeHand((c("Kc"), c("9s"))),
            ),
            p1_range=(RangeHand((c("Th"), c("7s"))),),
        )
        baseline = uniform_policy(cfg)
        self.assertAlmostEqual(
            best_response_value_player0(cfg, baseline),
            independent_global_bruteforce(cfg, 0, baseline),
            places=10,
        )

        # Mirror the same audit for P1 with two P1 private hands.
        mirrored = config(
            p0_range=(RangeHand((c("Tc"), c("7d"))),),
            p1_range=(
                RangeHand((c("Th"), c("7s"))),
                RangeHand((c("Kh"), c("9d"))),
            ),
        )
        baseline = uniform_policy(mirrored)
        self.assertAlmostEqual(
            best_response_value_player1(mirrored, baseline),
            independent_global_bruteforce(mirrored, 1, baseline),
            places=10,
        )

    def test_two_size_cfr_reduces_exact_exploitability(self):
        cfg = config()
        initial = exploitability(cfg, uniform_policy(cfg))
        trainer = RiverMultiSizeOneRaiseCFR(cfg)
        trainer.train(3000)
        final = exploitability(cfg, trainer.average_policy())
        self.assertLess(final, initial * 0.15)
        self.assertLess(final, cfg.pot * 0.025)

    def test_training_is_deterministic_and_resumable(self):
        cfg = config()
        split = RiverMultiSizeOneRaiseCFR(cfg)
        single = RiverMultiSizeOneRaiseCFR(cfg)
        split.train(500)
        split.train(500)
        single.train(1000)
        self.assertEqual(split.average_policy(), single.average_policy())
        self.assertAlmostEqual(
            exploitability(cfg, split.average_policy()),
            exploitability(cfg, single.average_policy()),
            places=12,
        )

    def test_invalid_action_sets_are_rejected(self):
        base = config()
        for sizes, raise_to in (
            ((), 10),
            ((4, 4), 10),
            ((8, 4), 10),
            ((4, 8, 10), 14),
            ((4, 8), 8),
        ):
            candidate = RiverMultiSizeOneRaiseConfig(
                board=base.board,
                pot=base.pot,
                bet_sizes=sizes,
                raise_to=raise_to,
                p0_range=base.p0_range,
                p1_range=base.p1_range,
            )
            with self.subTest(sizes=sizes, raise_to=raise_to), self.assertRaises(
                RiverMultiSizeOneRaiseError
            ):
                candidate.validate()


if __name__ == "__main__":
    unittest.main()
