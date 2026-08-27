import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_trainer.hu_multistreet_cfr import ExactHuMultiStreetCFR, RegretMode
from deepsix_trainer.hu_multistreet_float_cfr import (
    FloatHuMultiStreetCFR,
    exact_float_max_errors,
)
from deepsix_trainer.hu_multistreet_reference import (
    GROSS_POKER_DELTA,
    HuMicrogameConfig,
    HuReferenceMicrogame,
)
from deepsix_trainer.reach import PrivateReachVector


def cards(*texts):
    return tuple(parse_card(text) for text in texts)


def vector(seat, rows):
    return PrivateReachVector.from_mapping(seat, rows)


def tiny_game():
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


class FloatHuMultiStreetCFRTests(unittest.TestCase):
    def test_float_one_iteration_is_deterministic_and_finite(self):
        left = FloatHuMultiStreetCFR(tiny_game())
        right = FloatHuMultiStreetCFR(tiny_game())
        left.train(1)
        right.train(1)
        self.assertEqual(left.semantic_snapshot(), right.semantic_snapshot())
        self.assertEqual(
            left.average_policy().fingerprint(),
            right.average_policy().fingerprint(),
        )
        self.assertGreater(len(left.nodes), 0)

    def test_float_matches_exact_one_iteration_to_tight_tolerance(self):
        exact = ExactHuMultiStreetCFR(tiny_game())
        fast = FloatHuMultiStreetCFR(tiny_game())
        exact.train(1)
        fast.train(1)
        errors = exact_float_max_errors(exact, fast)
        self.assertLessEqual(errors["max_regret_abs_error"], 1e-12)
        self.assertLessEqual(errors["max_strategy_sum_abs_error"], 1e-12)
        self.assertLessEqual(errors["max_average_policy_abs_error"], 1e-12)

    def test_rm_plus_keeps_float_regrets_nonnegative(self):
        solver = FloatHuMultiStreetCFR(
            tiny_game(),
            regret_mode=RegretMode.PLUS,
        )
        solver.train(1)
        self.assertTrue(solver.all_regrets_nonnegative())

    def test_float_policy_exact_adapter_is_strictly_normalized(self):
        solver = FloatHuMultiStreetCFR(tiny_game())
        solver.train(1)
        exact_policy = solver.average_policy().to_exact_policy()
        for row in exact_policy.rows.values():
            self.assertEqual(sum(row.probabilities, Fraction(0, 1)), Fraction(1, 1))

        result = tiny_game().evaluate(
            exact_policy,
            objective_id=GROSS_POKER_DELTA,
        )
        self.assertEqual(result.seat_sum_antes, Fraction(0, 1))

    def test_invalid_iterations_fail_closed(self):
        solver = FloatHuMultiStreetCFR(tiny_game())
        with self.assertRaises(ValueError):
            solver.train(0)


if __name__ == "__main__":
    unittest.main()
