import unittest

from deepsix_simulator import transcript_from_hand
from deepsix_simulator.soak import (
    SIMULATOR_SOAK_SCHEMA_VERSION,
    SimulatorSoakCheckpoint,
    SimulatorSoakError,
    SimulatorSoakPlan,
)
from tools.run_simulator_soak import run_one


def make_plan(**overrides):
    payload = dict(
        schema_version=SIMULATOR_SOAK_SCHEMA_VERSION,
        seed_base=1000,
        total_global_hands=23,
        shard_count=4,
        shard_index=0,
        stake_cents=2,
        player_counts=(2, 3, 4, 5, 6),
        stack_min_antes=1,
        stack_max_antes=200,
        bbj_enabled=False,
        replay_every=3,
    )
    payload.update(overrides)
    return SimulatorSoakPlan(**payload)


class SimulatorSoakPlanTests(unittest.TestCase):
    def test_shards_are_disjoint_and_cover_global_schedule(self):
        plans = [make_plan(shard_index=index) for index in range(4)]
        per_shard = [
            [plan.global_index(i) for i in range(plan.local_target_hands)]
            for plan in plans
        ]
        flattened = [value for shard in per_shard for value in shard]
        self.assertEqual(sorted(flattened), list(range(23)))
        self.assertEqual(len(flattened), len(set(flattened)))
        self.assertEqual(per_shard[0], [0, 4, 8, 12, 16, 20])
        self.assertEqual(per_shard[3], [3, 7, 11, 15, 19])
        self.assertEqual(
            [plans[2].seed_for_ordinal(i) for i in range(plans[2].local_target_hands)],
            [1002, 1006, 1010, 1014, 1018, 1022],
        )

    def test_player_count_schedule_uses_global_index(self):
        plan = make_plan(shard_index=1)
        observed = [
            plan.player_count_for_ordinal(i)
            for i in range(plan.local_target_hands)
        ]
        expected = [
            plan.player_counts[index % len(plan.player_counts)]
            for index in [1, 5, 9, 13, 17, 21]
        ]
        self.assertEqual(observed, expected)

    def test_replay_schedule_includes_final_local_hand(self):
        plan = make_plan(shard_index=3, replay_every=4)
        flags = [
            plan.should_replay(i)
            for i in range(plan.local_target_hands)
        ]
        self.assertEqual(flags, [False, False, False, True, True])

    def test_global_hand_semantics_do_not_depend_on_shard_topology(self):
        unsharded = make_plan(
            total_global_hands=12,
            shard_count=1,
            shard_index=0,
            replay_every=0,
        )
        sharded = make_plan(
            total_global_hands=12,
            shard_count=3,
            shard_index=2,
            replay_every=0,
        )
        # Global hand 5 is ordinal 5 unsharded and ordinal 1 in shard 2/3.
        self.assertEqual(unsharded.global_index(5), 5)
        self.assertEqual(sharded.global_index(1), 5)

        direct, _ = run_one(unsharded, 5)
        partitioned, _ = run_one(sharded, 1)
        self.assertEqual(direct.hand_id, partitioned.hand_id)
        self.assertEqual(direct.hole_cards, partitioned.hole_cards)
        self.assertEqual(direct.state.board, partitioned.state.board)
        self.assertEqual(direct.state.actions, partitioned.state.actions)
        self.assertEqual(direct.settlement, partitioned.settlement)
        self.assertEqual(
            transcript_from_hand(direct).fingerprint(),
            transcript_from_hand(partitioned).fingerprint(),
        )

    def test_invalid_plan_is_rejected(self):
        with self.assertRaises(SimulatorSoakError):
            make_plan(shard_count=0).validate()
        with self.assertRaises(SimulatorSoakError):
            make_plan(shard_index=4).validate()
        with self.assertRaises(SimulatorSoakError):
            make_plan(player_counts=(2, 2)).validate()
        with self.assertRaises(SimulatorSoakError):
            make_plan(stack_min_antes=10, stack_max_antes=9).validate()
        with self.assertRaises(SimulatorSoakError):
            make_plan(bbj_enabled=1).validate()


class SimulatorSoakCheckpointTests(unittest.TestCase):
    def test_checkpoint_roundtrip_and_histogram(self):
        plan = make_plan(total_global_hands=2, shard_count=1, replay_every=2)
        checkpoint = SimulatorSoakCheckpoint.new(plan)
        checkpoint = checkpoint.advance(
            decisions=7,
            gross_pot_units=20,
            rake_units=1,
            bbj_units=0,
            terminal_board_cards=3,
            replay_checked=False,
        )
        checkpoint = checkpoint.advance(
            decisions=0,
            gross_pot_units=8,
            rake_units=0,
            bbj_units=0,
            terminal_board_cards=5,
            replay_checked=True,
        )
        self.assertTrue(checkpoint.is_complete)
        self.assertEqual(checkpoint.completed_hands, 2)
        self.assertEqual(checkpoint.decisions, 7)
        self.assertEqual(checkpoint.zero_decision_hands, 1)
        self.assertEqual(checkpoint.terminal_board_3, 1)
        self.assertEqual(checkpoint.terminal_board_5, 1)
        self.assertEqual(checkpoint.replay_checks, 1)

        restored = SimulatorSoakCheckpoint.from_json(checkpoint.canonical_json())
        self.assertEqual(restored, checkpoint)
        self.assertEqual(restored.fingerprint(), checkpoint.fingerprint())

    def test_checkpoint_cannot_advance_past_target(self):
        plan = make_plan(total_global_hands=1, shard_count=1)
        checkpoint = SimulatorSoakCheckpoint.new(plan).advance(
            decisions=0,
            gross_pot_units=4,
            rake_units=0,
            bbj_units=0,
            terminal_board_cards=0,
            replay_checked=True,
        )
        with self.assertRaises(SimulatorSoakError):
            checkpoint.advance(
                decisions=1,
                gross_pot_units=4,
                rake_units=0,
                bbj_units=0,
                terminal_board_cards=0,
                replay_checked=False,
            )

    def test_invalid_terminal_board_count_is_rejected(self):
        plan = make_plan(total_global_hands=1, shard_count=1)
        checkpoint = SimulatorSoakCheckpoint.new(plan)
        with self.assertRaises(SimulatorSoakError):
            checkpoint.advance(
                decisions=1,
                gross_pot_units=4,
                rake_units=0,
                bbj_units=0,
                terminal_board_cards=2,
                replay_checked=False,
            )


if __name__ == "__main__":
    unittest.main()
