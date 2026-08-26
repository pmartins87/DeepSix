import unittest

from deepsix_simulator import (
    DeepSixTable,
    SimulatorEnvironmentError,
    check_call_policy,
    run_seeded_session,
)


class SimulatorBatchTests(unittest.TestCase):
    def _run(self):
        table = DeepSixTable(
            stake_cents=2,
            player_count=4,
            dealer_seat=0,
            initial_stacks={0: 1000, 1: 1000, 2: 1000, 3: 1000},
            bbj_enabled=False,
        )
        agents = {seat: check_call_policy for seat in range(4)}
        return run_seeded_session(table, agents, range(100, 112))

    def test_equal_seed_schedule_produces_identical_session_fingerprint(self):
        a = self._run()
        b = self._run()
        self.assertEqual(a, b)
        self.assertEqual(a.fingerprint(), b.fingerprint())
        self.assertEqual(a.hands_played, 12)
        self.assertEqual(a.stop_reason, "seed_schedule_exhausted")

    def test_session_conserves_bankroll_after_accumulated_house_deductions(self):
        result = self._run()
        self.assertEqual(
            sum(stack for _, stack in result.final_stacks),
            sum(stack for _, stack in result.starting_stacks)
            - result.total_house_deductions,
        )
        self.assertGreater(result.decisions, 0)
        self.assertEqual(result.total_bbj_units, 0)
        self.assertTrue(all(len(hand.transcript_fingerprint) == 64 for hand in result.hands))

    def test_empty_seed_schedule_is_a_valid_zero_hand_session(self):
        table = DeepSixTable(
            stake_cents=2,
            player_count=2,
            initial_stacks={0: 100, 1: 100},
        )
        result = run_seeded_session(
            table,
            {0: check_call_policy, 1: check_call_policy},
            (),
        )
        self.assertEqual(result.hands_played, 0)
        self.assertEqual(result.starting_stacks, result.final_stacks)
        self.assertEqual(result.total_house_deductions, 0)

    def test_noninteger_seed_is_rejected(self):
        table = DeepSixTable(
            stake_cents=2,
            player_count=2,
            initial_stacks={0: 100, 1: 100},
        )
        with self.assertRaises(SimulatorEnvironmentError):
            run_seeded_session(
                table,
                {0: check_call_policy, 1: check_call_policy},
                (True,),
            )


if __name__ == "__main__":
    unittest.main()
