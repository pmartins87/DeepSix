import unittest

from deepsix_simulator.soak import (
    SIMULATOR_SOAK_SCHEMA_VERSION,
    SimulatorSoakPlan,
)
from tools.run_simulator_soak import run_one


class SixWayAsymmetricSimulatorStressTests(unittest.TestCase):
    def test_400_seeded_sixway_hands_with_wide_stack_range_settle_cleanly(self):
        plan = SimulatorSoakPlan(
            schema_version=SIMULATOR_SOAK_SCHEMA_VERSION,
            seed_base=60620260826,
            total_global_hands=400,
            shard_count=1,
            shard_index=0,
            stake_cents=2,
            player_counts=(6,),
            stack_min_antes=1,
            stack_max_antes=300,
            bbj_enabled=True,
            replay_every=31,
        )
        plan.validate()

        replays = 0
        terminal_counts = {0: 0, 3: 0, 4: 0, 5: 0}
        observed_stack_spreads = []
        for ordinal in range(plan.local_target_hands):
            hand, replay_checked = run_one(plan, ordinal)
            self.assertTrue(hand.terminal)
            self.assertIsNotNone(hand.settlement)
            self.assertEqual(len(hand.state.players), 6)
            terminal_counts[len(hand.state.board)] += 1
            replays += int(replay_checked)

            starting = [
                player.stack + player.committed_total
                for player in hand.state.players
            ]
            observed_stack_spreads.append(max(starting) - min(starting))

        self.assertEqual(sum(terminal_counts.values()), 400)
        self.assertGreater(replays, 0)
        # Deterministic wide-stack sampling must actually exercise materially
        # asymmetric tables rather than accidentally collapsing to near-equal stacks.
        self.assertGreater(max(observed_stack_spreads), 250)


if __name__ == "__main__":
    unittest.main()
