import tempfile
import unittest
from pathlib import Path

from deepsix_trainer.stream_scheduler import (
    DurableTrainingReceipt,
    TrainingStreamError,
    TrainingStreamKey,
    TrainingStreamPlan,
    TrainingStreamScheduler,
    load_training_scheduler_checkpoint,
    save_training_scheduler_checkpoint_atomic,
)


def key(seed: int, *, player_count: int = 2, solver: str = "rmplus") -> TrainingStreamKey:
    return TrainingStreamKey(
        experiment_id="f4-lab-v1",
        solver_family=solver,
        player_count=player_count,
        algorithm_seed=seed,
    )


class TrainingStreamSchedulerTests(unittest.TestCase):
    def test_only_independent_streams_are_leased_concurrently(self):
        a = key(11)
        b = key(12)
        scheduler = TrainingStreamScheduler(
            (TrainingStreamPlan(a, 2), TrainingStreamPlan(b, 2))
        )
        leases = scheduler.lease(8)
        self.assertEqual(len(leases), 2)
        self.assertEqual({lease.key for lease in leases}, {a, b})
        self.assertEqual(len(scheduler.active_stream_ids), 2)
        # A second lease request cannot overlap either active lineage.
        self.assertEqual(scheduler.lease(8), ())

    def test_failure_retries_same_iteration_without_advancing(self):
        stream = key(21)
        scheduler = TrainingStreamScheduler((TrainingStreamPlan(stream, 2),))
        first = scheduler.lease(1)[0]
        scheduler.fail(first)
        retry = scheduler.lease(1)[0]
        self.assertEqual(retry.iteration, first.iteration)
        self.assertNotEqual(retry.lease_id, first.lease_id)

    def test_progress_requires_durable_receipt_and_exact_parent_lineage(self):
        stream = key(31)
        scheduler = TrainingStreamScheduler((TrainingStreamPlan(stream, 2),))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lease1 = scheduler.lease(1)[0]
            with self.assertRaises(TrainingStreamError):
                scheduler.complete(lease1, None)

            ckpt1 = root / "iteration-1.bin"
            ckpt1.write_bytes(b"iteration one")
            receipt1 = DurableTrainingReceipt.from_file(
                lease1,
                ckpt1,
                parent_checkpoint_sha256=None,
            )
            scheduler.complete(lease1, receipt1)
            self.assertEqual(
                scheduler.last_checkpoint_sha256(stream), receipt1.checkpoint_sha256
            )

            lease2 = scheduler.lease(1)[0]
            ckpt2 = root / "iteration-2.bin"
            ckpt2.write_bytes(b"iteration two")
            wrong = DurableTrainingReceipt.from_file(
                lease2,
                ckpt2,
                parent_checkpoint_sha256=None,
            )
            with self.assertRaises(TrainingStreamError):
                scheduler.complete(lease2, wrong)

            receipt2 = DurableTrainingReceipt.from_file(
                lease2,
                ckpt2,
                parent_checkpoint_sha256=receipt1.checkpoint_sha256,
            )
            scheduler.complete(lease2, receipt2)
            self.assertTrue(scheduler.complete_all)

    def test_checkpoint_roundtrip_clears_in_memory_lease_after_crash(self):
        stream = key(41, player_count=6, solver="external_sampling_mccfr")
        scheduler = TrainingStreamScheduler((TrainingStreamPlan(stream, 3),))
        active = scheduler.lease(1)[0]
        self.assertEqual(active.iteration, 1)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scheduler.json"
            receipt = save_training_scheduler_checkpoint_atomic(path, scheduler)
            restored = load_training_scheduler_checkpoint(
                path,
                expected_sha256=receipt.sha256,
            )
            self.assertEqual(restored.active_stream_ids, ())
            retry = restored.lease(1)[0]
            self.assertEqual(retry.key, stream)
            self.assertEqual(retry.iteration, 1)

    def test_checkpoint_sha_tampering_is_rejected(self):
        scheduler = TrainingStreamScheduler((TrainingStreamPlan(key(51), 1),))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scheduler.json"
            receipt = save_training_scheduler_checkpoint_atomic(path, scheduler)
            path.write_bytes(path.read_bytes() + b"tamper")
            with self.assertRaises(TrainingStreamError):
                load_training_scheduler_checkpoint(
                    path,
                    expected_sha256=receipt.sha256,
                )

    def test_stream_identity_changes_when_semantics_change(self):
        base = key(61)
        self.assertNotEqual(base.stream_id, key(62).stream_id)
        self.assertNotEqual(base.stream_id, key(61, player_count=3).stream_id)
        self.assertNotEqual(base.stream_id, key(61, solver="vanilla_cfr").stream_id)


if __name__ == "__main__":
    unittest.main()
