import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_trainer.hu_multistreet_cfr import (
    ExactHuMultiStreetCFR,
    HuMultiStreetCFRError,
    RegretMode,
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
    def test_one_exact_iteration_creates_valid_infosets_and_average_policy(self):
        solver = ExactHuMultiStreetCFR(tiny_game())
        solver.train(1)
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
        left = ExactHuMultiStreetCFR(tiny_game())
        right = ExactHuMultiStreetCFR(tiny_game())
        left.train(1)
        right.train(1)
        self.assertEqual(left.semantic_snapshot(), right.semantic_snapshot())
        self.assertEqual(
            left.average_policy().fingerprint(),
            right.average_policy().fingerprint(),
        )

    def test_rm_plus_clips_all_cumulative_regrets_nonnegative(self):
        solver = ExactHuMultiStreetCFR(
            tiny_game(),
            regret_mode=RegretMode.PLUS,
        )
        solver.train(1)
        self.assertTrue(solver.all_regrets_nonnegative())

    def test_average_policy_can_be_evaluated_by_exact_reference_game(self):
        solver = ExactHuMultiStreetCFR(tiny_game())
        solver.train(1)
        result = solver.average_gross_value()
        self.assertEqual(result.objective_id, GROSS_POKER_DELTA)
        self.assertEqual(result.seat_sum_antes, Fraction(0, 1))
        self.assertEqual(result.private_deal_count, 1)

    def test_invalid_iteration_and_mode_fail_closed(self):
        solver = ExactHuMultiStreetCFR(tiny_game())
        with self.assertRaises(HuMultiStreetCFRError):
            solver.train(0)
        with self.assertRaises(HuMultiStreetCFRError):
            ExactHuMultiStreetCFR(tiny_game(), regret_mode="plus")


if __name__ == "__main__":
    unittest.main()
