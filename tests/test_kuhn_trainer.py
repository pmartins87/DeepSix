import unittest

from deepsix_trainer.kuhn import (
    KuhnCFR,
    KuhnPolicy,
    best_response_value_player0,
    best_response_value_player1,
    expected_value,
    exploitability,
)


class KuhnTrainerBaselineTests(unittest.TestCase):
    def test_uniform_policy_exact_value_and_best_responses_are_finite(self):
        uniform = KuhnPolicy(
            {
                (card, history): (0.5, 0.5)
                for card in (0, 1, 2)
                for history in ("", "p", "b", "pb")
            }
        )
        value = expected_value(uniform, uniform)
        self.assertTrue(-2.0 <= value <= 2.0)
        br0 = best_response_value_player0(uniform)
        br1 = best_response_value_player1(uniform)
        self.assertGreaterEqual(br0, value)
        self.assertLessEqual(br1, value)
        self.assertGreater(exploitability(uniform), 0.0)

    def test_cfr_converges_toward_known_kuhn_value_and_low_exploitability(self):
        trainer = KuhnCFR()
        trainer.train(50000)
        policy = trainer.average_policy()
        value = expected_value(policy, policy)
        # Standard Kuhn poker value for player 0 with one-chip antes.
        self.assertAlmostEqual(value, -1.0 / 18.0, delta=0.004)
        self.assertLess(exploitability(policy), 0.015)
        self.assertEqual(trainer.iterations, 50000)

    def test_training_is_deterministic(self):
        first = KuhnCFR()
        second = KuhnCFR()
        first.train(2000)
        second.train(2000)
        self.assertEqual(first.average_policy().strategies, second.average_policy().strategies)
        self.assertEqual(
            exploitability(first.average_policy()),
            exploitability(second.average_policy()),
        )

    def test_split_training_matches_single_run(self):
        split = KuhnCFR()
        split.train(1000)
        split.train(1000)
        single = KuhnCFR()
        single.train(2000)
        self.assertEqual(split.average_policy().strategies, single.average_policy().strategies)


if __name__ == "__main__":
    unittest.main()
