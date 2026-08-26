import unittest

from deepsix_simulator import (
    DeepSixTable,
    SimulatorTableSnapshot,
    check_call_policy,
    restore_table,
    snapshot_table,
    transcript_from_hand,
)


class SimulatorSnapshotTests(unittest.TestCase):
    def _table(self):
        return DeepSixTable(
            stake_cents=2,
            player_count=4,
            dealer_seat=0,
            initial_stacks={0: 300, 1: 300, 2: 300, 3: 300},
            bbj_enabled=False,
        )

    @staticmethod
    def _play_one(table, seed):
        hand = table.start_hand(seed=seed)
        hand.play_to_terminal({seat: check_call_policy for seat in table.seats})
        fp = transcript_from_hand(hand).fingerprint()
        table.commit_settlement(hand)
        return fp

    def test_snapshot_json_roundtrip_is_canonical(self):
        table = self._table()
        self._play_one(table, 100)
        snap = snapshot_table(table)
        decoded = SimulatorTableSnapshot.from_json(snap.canonical_json())
        self.assertEqual(decoded, snap)
        self.assertEqual(decoded.fingerprint(), snap.fingerprint())

    def test_resume_produces_identical_future_hands_and_final_stacks(self):
        original = self._table()
        for seed in (10, 11, 12):
            self._play_one(original, seed)

        snap = snapshot_table(original)
        restored = restore_table(SimulatorTableSnapshot.from_json(snap.canonical_json()))
        self.assertEqual(snapshot_table(restored), snap)

        future_a = []
        future_b = []
        for seed in (20, 21, 22, 23, 24):
            future_a.append(self._play_one(original, seed))
            future_b.append(self._play_one(restored, seed))

        self.assertEqual(future_a, future_b)
        self.assertEqual(original.stacks, restored.stacks)
        self.assertEqual(original.dealer_seat, restored.dealer_seat)
        self.assertEqual(original.hand_index, restored.hand_index)
        self.assertEqual(snapshot_table(original), snapshot_table(restored))

    def test_zero_stack_busted_chair_can_be_restored(self):
        table = self._table()
        table.stacks[2] = 0
        table.hand_index = 7
        snap = snapshot_table(table)
        restored = restore_table(snap)
        self.assertEqual(restored.stacks[2], 0)
        self.assertEqual(restored.hand_index, 7)
        self.assertNotIn(2, restored._live_seats())
        self.assertEqual(snapshot_table(restored), snap)

    def test_snapshot_tampering_changes_fingerprint(self):
        snap = snapshot_table(self._table())
        payload = snap.to_dict()
        payload["hand_index"] = 99
        other = SimulatorTableSnapshot.from_dict(payload)
        self.assertNotEqual(snap.fingerprint(), other.fingerprint())


if __name__ == "__main__":
    unittest.main()
