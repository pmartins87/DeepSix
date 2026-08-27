import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_trainer.hu_multistreet_cfr import (
    ExactHuMultiStreetCFR,
    HuMultiStreetCFRError,
    RegretMode,
)
from deepsix_trainer.hu_multistreet_float_cfr import (
    FloatHuMultiStreetCFR,
    exact_float_max_errors,
)
from deepsix_trainer.hu_multistreet_reference import (
    GROSS_POKER_DELTA,
    HuMicrogameConfig,
    HuReferenceMicrogame,
    MicroAction,
)
from deepsix_trainer.reach import PrivateReachVector


def cards(*texts):
    return tuple(parse_card(text) for text in texts)


def vector(seat, rows):
    return PrivateReachVector.from_mapping(seat, rows)


def tiny_game():
    # 51-unit stacks leave exactly one unit behind each after the passive
    # preflop completion. This keeps the exact chance tree full while making
    # postflop action depth tiny enough for a deterministic CI solver gate.
    return HuReferenceMicrogame(
        HuMicrogameConfig(
            stake_cents=25,
            dealer_seat=0,
            stacks=((0, 51), (1, 51)),
            flop=cards("6c", "7d", "8h"),
            bbj_enabled=False,
        ),
        (
            vector(0, {cards("As", "Ks"): 1}),
            vector(1, {cards("Qc", "Jc"): 1}),
        ),
    )


class ExactHuMultiStreetCFRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vanilla_left = ExactHuMultiStreetCFR(tiny_game())
        cls.vanilla_right = ExactHuMultiStreetCFR(tiny_game())
        cls.rm_plus = ExactHuMultiStreetCFR(
            tiny_game(),
            regret_mode=RegretMode.PLUS,
        )
        cls.float64 = FloatHuMultiStreetCFR(tiny_game())

        cls.vanilla_left.train(1)
        cls.vanilla_right.train(1)
        cls.rm_plus.train(1)
        cls.float64.train(1)

    def test_one_exact_iteration_creates_valid_infosets_and_average_policy(self):
        solver = self.vanilla_left
        self.assertEqual(solver.iterations, 1)
        self.assertGreater(len(solver.nodes), 0)

        policy = solver.average_policy()
        self.assertEqual(len(policy.fingerprint()), 64)
        for row in policy.rows.values():
            self.assertEqual(
                sum(row.probabilities, Fraction(0, 1)),
                Fraction(1, 1),
            )
            self.assertEqual(len(row.actions), len(row.probabilities))
            self.assertTrue(set(row.actions) <= set(MicroAction))

    def test_exact_one_iteration_is_deterministic(self):
        self.assertEqual(
            self.vanilla_left.semantic_snapshot(),
            self.vanilla_right.semantic_snapshot(),
        )
        self.assertEqual(
            self.vanilla_left.average_policy().fingerprint(),
            self.vanilla_right.average_policy().fingerprint(),
        )

    def test_rm_plus_clips_all_cumulative_regrets_nonnegative(self):
        self.assertTrue(self.rm_plus.all_regrets_nonnegative())

    def test_average_policy_can_be_evaluated_by_exact_reference_game(self):
        result = self.vanilla_left.average_gross_value()
        self.assertEqual(result.objective_id, GROSS_POKER_DELTA)
        self.assertEqual(result.seat_sum_antes, Fraction(0, 1))
        self.assertEqual(result.private_deal_count, 1)

    def test_float64_matches_exact_first_iteration(self):
        errors = exact_float_max_errors(self.vanilla_left, self.float64)
        self.assertLessEqual(errors["max_regret_abs_error"], 1e-12)
        self.assertLessEqual(errors["max_strategy_sum_abs_error"], 1e-12)
        self.assertLessEqual(errors["max_average_policy_abs_error"], 1e-12)

    def test_invalid_iteration_and_mode_fail_closed(self):
        solver = ExactHuMultiStreetCFR(tiny_game())
        with self.assertRaises(HuMultiStreetCFRError):
            solver.train(0)
        with self.assertRaises(HuMultiStreetCFRError):
            ExactHuMultiStreetCFR(tiny_game(), regret_mode="plus")


if __name__ == "__main__":
    unittest.main()
