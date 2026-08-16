import itertools
import unittest

from deepsix_core.cards import parse_card
from deepsix_trainer.river_microgame import RangeHand
from deepsix_trainer.river_one_raise import (
    RiverOneRaiseCFR,
    RiverOneRaiseConfig,
    RiverOneRaiseError,
    RiverOneRaisePolicy,
    best_response_value_player0,
    best_response_value_player1,
    expected_value,
    exploitability,
    legal_actions,
    player_histories,
    pure_plans_for_player,
    terminal_utility_p0,
    uniform_policy,
)


def c(text):
    return parse_card(text)


def config(*, p0_range=None, p1_range=None):
    return RiverOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=12,
        bet_size=4,
        raise_to=10,
        p0_range=p0_range
        or (
            RangeHand((c("Tc"), c("7d"))),
            RangeHand((c("Kc"), c("9s"))),
            RangeHand((c("Jc"), c("Tc"))),
        ),
        p1_range=p1_range
        or (
            RangeHand((c("Th"), c("7s"))),
            RangeHand((c("Kh"), c("9d"))),
            RangeHand((c("Jh"), c("Th"))),
        ),
    )


def policy_from_plan_map(cfg, player, plan_by_hand, fixed_other):
    strategies = dict(fixed_other.strategies)
    hands = cfg.p0_range if player == 0 else cfg.p1_range
    for hand in hands:
        cards = hand.canonical_cards()
        plan = plan_by_hand[cards]
        for history in player_histories(player):
            count = len(legal_actions(history))
            chosen = plan[history]
            strategy = tuple(1.0 if i == chosen else 0.0 for i in range(count))
            strategies[(player, cards, history)] = strategy
    return RiverOneRaisePolicy(strategies)


def independent_global_brute_force(cfg, br_player, opponent):
    hands = cfg.p0_range if br_player == 0 else cfg.p1_range
    cards = [hand.canonical_cards() for hand in hands]
    plans = pure_plans_for_player(br_player)
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


class RiverOneRaiseTests(unittest.TestCase):
    def test_tree_and_terminal_accounting(self):
        cfg = config()
        deal_win = next(deal for deal in cfg.compatible_deals() if deal.showdown_sign == 1)
        deal_loss = next(deal for deal in cfg.compatible_deals() if deal.showdown_sign == -1)

        self.assertEqual(legal_actions(()), ("x", "b"))
        self.assertEqual(legal_actions(("b",)), ("f", "c", "r"))
        self.assertEqual(legal_actions(("b", "r")), ("f", "c"))

        self.assertEqual(terminal_utility_p0(cfg, deal_win, ("b", "f")), 6.0)
        self.assertEqual(terminal_utility_p0(cfg, deal_win, ("b", "c")), 10.0)
        self.assertEqual(terminal_utility_p0(cfg, deal_win, ("b", "r", "f")), -10.0)
        self.assertEqual(terminal_utility_p0(cfg, deal_win, ("b", "r", "c")), 16.0)
        self.assertEqual(terminal_utility_p0(cfg, deal_win, ("x", "b", "f")), -6.0)
        self.assertEqual(terminal_utility_p0(cfg, deal_win, ("x", "b", "r", "f")), 10.0)
        self.assertEqual(terminal_utility_p0(cfg, deal_loss, ("x", "b", "r", "c")), -16.0)

    def test_each_private_hand_has_twelve_pure_response_plans(self):
        self.assertEqual(len(pure_plans_for_player(0)), 12)
        self.assertEqual(len(pure_plans_for_player(1)), 12)

    def test_exact_best_response_matches_independent_global_bruteforce(self):
        small = config(
            p0_range=(
                RangeHand((c("Tc"), c("7d"))),
                RangeHand((c("Kc"), c("9s"))),
            ),
            p1_range=(
                RangeHand((c("Th"), c("7s"))),
                RangeHand((c("Kh"), c("9d"))),
            ),
        )
        baseline = uniform_policy(small)
        self.assertAlmostEqual(
            best_response_value_player0(small, baseline),
            independent_global_brute_force(small, 0, baseline),
            places=10,
        )
        self.assertAlmostEqual(
            best_response_value_player1(small, baseline),
            independent_global_brute_force(small, 1, baseline),
            places=10,
        )

    def test_cfr_substantially_reduces_exact_exploitability(self):
        cfg = config()
        initial = exploitability(cfg, uniform_policy(cfg))
        trainer = RiverOneRaiseCFR(cfg)
        trainer.train(2500)
        final = exploitability(cfg, trainer.average_policy())
        self.assertLess(final, initial * 0.15)
        self.assertLess(final, cfg.pot * 0.02)

    def test_training_is_deterministic_and_resumable(self):
        cfg = config()
        a = RiverOneRaiseCFR(cfg)
        b = RiverOneRaiseCFR(cfg)
        a.train(900)
        a.train(600)
        b.train(1500)
        self.assertEqual(a.iterations, 1500)
        self.assertEqual(b.iterations, 1500)
        self.assertEqual(a.average_policy(), b.average_policy())
        self.assertAlmostEqual(
            exploitability(cfg, a.average_policy()),
            exploitability(cfg, b.average_policy()),
            places=12,
        )

    def test_real_short_deck_evaluator_drives_chance_strength(self):
        cfg = config()
        deals = cfg.compatible_deals()
        self.assertTrue(any(deal.showdown_sign > 0 for deal in deals))
        self.assertTrue(any(deal.showdown_sign < 0 for deal in deals))
        self.assertAlmostEqual(sum(deal.probability for deal in deals), 1.0)

    def test_invalid_parameters_are_rejected(self):
        base = config()
        with self.assertRaises(RiverOneRaiseError):
            RiverOneRaiseConfig(
                board=base.board,
                pot=base.pot,
                bet_size=4,
                raise_to=4,
                p0_range=base.p0_range,
                p1_range=base.p1_range,
            ).validate()
        with self.assertRaises(RiverOneRaiseError):
            RiverOneRaiseConfig(
                board=base.board,
                pot=0,
                bet_size=4,
                raise_to=10,
                p0_range=base.p0_range,
                p1_range=base.p1_range,
            ).validate()
        with self.assertRaises(RiverOneRaiseError):
            legal_actions(("r",))


if __name__ == "__main__":
    unittest.main()
