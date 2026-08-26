"""Deterministic training-stream scheduling and durable checkpoint lineage.

This module transfers a process lesson from SpinCore without importing any
Spin&Go game semantics: stochastic/model lineages are explicit, work for one
lineage is serial, only independent lineages may run concurrently, and an
iteration is not allowed to advance until durable checkpoint bytes exist.

DeepSix deliberately keeps this scheduler solver-agnostic.  It does not derive
per-root seeds, mutate a solver RNG, own replay buffers/reservoirs, or decide
which algorithm wins F4.  Those semantics remain the responsibility of the
selected trainer.  The scheduler only protects ordering, crash recovery and
checkpoint ancestry.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable


TRAINING_STREAM_SCHEMA_VERSION = 1
TRAINING_STREAM_SCHEDULER_SCHEMA = "DEEPSIX_TRAINING_STREAM_SCHEDULER_V1"
TRAINING_STREAM_CHECKPOINT_SCHEMA = "DEEPSIX_TRAINING_STREAM_CHECKPOINT_V1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TrainingStreamError(ValueError):
    pass


def _require_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TrainingStreamError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True, order=True)
class TrainingStreamKey:
    """Identity of one independent stochastic/model lineage.

    ``experiment_id`` should freeze all state/action/rules/economy choices that
    materially affect training.  ``solver_family`` identifies the algorithmic
    family.  ``player_count`` is explicit because HU and multiway Short Deck are
    not interchangeable games.  ``algorithm_seed`` owns one independent RNG and
    checkpoint lineage.
    """

    experiment_id: str
    solver_family: str
    player_count: int
    algorithm_seed: int

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise TrainingStreamError("experiment_id is required")
        if not self.solver_family.strip():
            raise TrainingStreamError("solver_family is required")
        if isinstance(self.player_count, bool) or not isinstance(self.player_count, int):
            raise TrainingStreamError("player_count must be an integer")
        if not 2 <= self.player_count <= 6:
            raise TrainingStreamError("player_count must be within 2..6")
        _require_positive_int("algorithm_seed", self.algorithm_seed)

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "solver_family": self.solver_family,
            "player_count": self.player_count,
            "algorithm_seed": self.algorithm_seed,
        }

    @property
    def stream_id(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return "deepsix-stream-v1:" + hashlib.sha256(payload).hexdigest()

    @classmethod
    def from_dict(cls, payload: dict) -> "TrainingStreamKey":
        expected = {
            "experiment_id",
            "solver_family",
            "player_count",
            "algorithm_seed",
        }
        if set(payload) != expected:
            raise TrainingStreamError("training stream key differs from schema v1")
        return cls(
            experiment_id=str(payload["experiment_id"]),
            solver_family=str(payload["solver_family"]),
            player_count=payload["player_count"],
            algorithm_seed=payload["algorithm_seed"],
        )


@dataclass(frozen=True)
class TrainingStreamPlan:
    key: TrainingStreamKey
    total_iterations: int

    def __post_init__(self) -> None:
        _require_positive_int("total_iterations", self.total_iterations)


@dataclass(frozen=True)
class TrainingIterationLease:
    key: TrainingStreamKey
    iteration: int
    lease_id: str

    def __post_init__(self) -> None:
        _require_positive_int("lease iteration", self.iteration)
        if not self.lease_id.startswith("deepsix-lease-v1:"):
            raise TrainingStreamError("invalid lease id")


@dataclass(frozen=True)
class DurableTrainingReceipt:
    """Proof that checkpoint bytes for one leased iteration are durable."""

    key: TrainingStreamKey
    iteration: int
    lease_id: str
    checkpoint_locator: str
    checkpoint_sha256: str
    checkpoint_size_bytes: int
    parent_checkpoint_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_positive_int("receipt iteration", self.iteration)
        if not self.lease_id.startswith("deepsix-lease-v1:"):
            raise TrainingStreamError("invalid receipt lease id")
        if not self.checkpoint_locator.strip():
            raise TrainingStreamError("checkpoint locator is required")
        if not _SHA256_RE.fullmatch(self.checkpoint_sha256):
            raise TrainingStreamError("checkpoint SHA256 must be 64 lowercase hex chars")
        _require_positive_int("checkpoint_size_bytes", self.checkpoint_size_bytes)
        if self.parent_checkpoint_sha256 is not None:
            if not _SHA256_RE.fullmatch(self.parent_checkpoint_sha256):
                raise TrainingStreamError("parent checkpoint SHA256 is invalid")
            if self.parent_checkpoint_sha256 == self.checkpoint_sha256:
                raise TrainingStreamError("checkpoint cannot be its own parent")

    @classmethod
    def from_file(
        cls,
        lease: TrainingIterationLease,
        path: str | Path,
        *,
        parent_checkpoint_sha256: str | None,
        locator: str | None = None,
    ) -> "DurableTrainingReceipt":
        source = Path(path)
        raw = source.read_bytes()
        if not raw:
            raise TrainingStreamError("checkpoint file is empty")
        return cls(
            key=lease.key,
            iteration=lease.iteration,
            lease_id=lease.lease_id,
            checkpoint_locator=str(locator or source),
            checkpoint_sha256=hashlib.sha256(raw).hexdigest(),
            checkpoint_size_bytes=len(raw),
            parent_checkpoint_sha256=parent_checkpoint_sha256,
        )

    @property
    def receipt_id(self) -> str:
        payload = (
            f"{self.key.stream_id}|{self.iteration}|{self.checkpoint_sha256}|"
            f"{self.parent_checkpoint_sha256 or 'GENESIS'}"
        ).encode("utf-8")
        return "deepsix-receipt-v1:" + hashlib.sha256(payload).hexdigest()


@dataclass
class _Progress:
    total_iterations: int
    next_iteration: int = 1
    active_lease_id: str | None = None
    failed_attempts_for_next_iteration: int = 0
    last_checkpoint_sha256: str | None = None
    last_checkpoint_locator: str | None = None
    last_checkpoint_size_bytes: int | None = None
    last_receipt_id: str | None = None


class TrainingStreamScheduler:
    """Parallelize only independent streams; serialize each stream exactly."""

    def __init__(self, plans: Iterable[TrainingStreamPlan]) -> None:
        rows = sorted(plans, key=lambda row: row.key)
        if not rows:
            raise TrainingStreamError("at least one training stream is required")
        if len({row.key for row in rows}) != len(rows):
            raise TrainingStreamError("duplicate training stream key")
        self._progress = {
            row.key: _Progress(total_iterations=row.total_iterations) for row in rows
        }
        self._lease_counter = 0

    def _new_lease_id(self, key: TrainingStreamKey, iteration: int) -> str:
        self._lease_counter += 1
        raw = f"{key.stream_id}|{iteration}|{self._lease_counter}".encode("utf-8")
        return "deepsix-lease-v1:" + hashlib.sha256(raw).hexdigest()

    def lease(self, max_workers: int) -> tuple[TrainingIterationLease, ...]:
        _require_positive_int("max_workers", max_workers)
        out: list[TrainingIterationLease] = []
        for key in sorted(self._progress):
            if len(out) >= max_workers:
                break
            state = self._progress[key]
            if state.active_lease_id is not None:
                continue
            if state.next_iteration > state.total_iterations:
                continue
            lease_id = self._new_lease_id(key, state.next_iteration)
            state.active_lease_id = lease_id
            out.append(TrainingIterationLease(key, state.next_iteration, lease_id))
        return tuple(out)

    def _validate_active(self, lease: TrainingIterationLease) -> _Progress:
        state = self._progress.get(lease.key)
        if state is None:
            raise TrainingStreamError("lease belongs to unknown stream")
        if lease.iteration != state.next_iteration:
            raise TrainingStreamError("lease iteration is stale or out of order")
        if state.active_lease_id != lease.lease_id:
            raise TrainingStreamError("lease is not the active lease")
        return state

    def complete(
        self,
        lease: TrainingIterationLease,
        receipt: DurableTrainingReceipt | None,
    ) -> None:
        state = self._validate_active(lease)
        if receipt is None:
            raise TrainingStreamError("durable checkpoint receipt is required")
        if (
            receipt.key != lease.key
            or receipt.iteration != lease.iteration
            or receipt.lease_id != lease.lease_id
        ):
            raise TrainingStreamError("receipt does not belong to active lease")
        if receipt.parent_checkpoint_sha256 != state.last_checkpoint_sha256:
            raise TrainingStreamError("checkpoint parent does not match accepted lineage")

        state.last_checkpoint_sha256 = receipt.checkpoint_sha256
        state.last_checkpoint_locator = receipt.checkpoint_locator
        state.last_checkpoint_size_bytes = receipt.checkpoint_size_bytes
        state.last_receipt_id = receipt.receipt_id
        state.active_lease_id = None
        state.next_iteration += 1
        state.failed_attempts_for_next_iteration = 0

    def fail(self, lease: TrainingIterationLease) -> None:
        state = self._validate_active(lease)
        state.active_lease_id = None
        state.failed_attempts_for_next_iteration += 1

    def last_checkpoint_sha256(self, key: TrainingStreamKey) -> str | None:
        try:
            return self._progress[key].last_checkpoint_sha256
        except KeyError as exc:
            raise TrainingStreamError("unknown training stream") from exc

    @property
    def complete_all(self) -> bool:
        return all(
            state.next_iteration > state.total_iterations
            and state.active_lease_id is None
            for state in self._progress.values()
        )

    @property
    def active_stream_ids(self) -> tuple[str, ...]:
        return tuple(
            key.stream_id
            for key in sorted(self._progress)
            if self._progress[key].active_lease_id is not None
        )

    def state_dict(self) -> dict[str, object]:
        return {
            "schema_version": TRAINING_STREAM_SCHEMA_VERSION,
            "schema": TRAINING_STREAM_SCHEDULER_SCHEMA,
            "lease_counter": self._lease_counter,
            "execution_target": "OFFLINE_SIMULATOR",
            "streams": [
                {
                    **key.to_dict(),
                    "stream_id": key.stream_id,
                    "total_iterations": state.total_iterations,
                    "next_iteration": state.next_iteration,
                    "active_lease_id": state.active_lease_id,
                    "failed_attempts_for_next_iteration": state.failed_attempts_for_next_iteration,
                    "last_checkpoint_sha256": state.last_checkpoint_sha256,
                    "last_checkpoint_locator": state.last_checkpoint_locator,
                    "last_checkpoint_size_bytes": state.last_checkpoint_size_bytes,
                    "last_receipt_id": state.last_receipt_id,
                }
                for key, state in sorted(self._progress.items())
            ],
        }

    @classmethod
    def from_state_dict(
        cls,
        payload: dict,
        *,
        clear_active_leases: bool = True,
    ) -> "TrainingStreamScheduler":
        if payload.get("schema_version") != TRAINING_STREAM_SCHEMA_VERSION:
            raise TrainingStreamError("unsupported scheduler schema version")
        if payload.get("schema") != TRAINING_STREAM_SCHEDULER_SCHEMA:
            raise TrainingStreamError("wrong training scheduler schema")
        if payload.get("execution_target") != "OFFLINE_SIMULATOR":
            raise TrainingStreamError("unexpected training execution target")
        rows = list(payload.get("streams") or [])
        plans: list[TrainingStreamPlan] = []
        keys: list[TrainingStreamKey] = []
        for row in rows:
            key = TrainingStreamKey(
                experiment_id=str(row["experiment_id"]),
                solver_family=str(row["solver_family"]),
                player_count=row["player_count"],
                algorithm_seed=row["algorithm_seed"],
            )
            if row.get("stream_id") != key.stream_id:
                raise TrainingStreamError("training stream identity hash mismatch")
            keys.append(key)
            plans.append(TrainingStreamPlan(key, row["total_iterations"]))
        obj = cls(plans)
        obj._lease_counter = int(payload.get("lease_counter", 0))
        if obj._lease_counter < 0:
            raise TrainingStreamError("lease counter must be non-negative")

        for key, row in zip(keys, rows):
            state = obj._progress[key]
            state.next_iteration = int(row["next_iteration"])
            state.failed_attempts_for_next_iteration = int(
                row.get("failed_attempts_for_next_iteration", 0)
            )
            if state.failed_attempts_for_next_iteration < 0:
                raise TrainingStreamError("failed-attempt counter is negative")
            state.active_lease_id = (
                None if clear_active_leases else row.get("active_lease_id")
            )
            if not 1 <= state.next_iteration <= state.total_iterations + 1:
                raise TrainingStreamError("invalid next iteration")

            sha = row.get("last_checkpoint_sha256")
            locator = row.get("last_checkpoint_locator")
            size = row.get("last_checkpoint_size_bytes")
            receipt_id = row.get("last_receipt_id")
            completed = state.next_iteration - 1
            if completed == 0:
                if any(value is not None for value in (sha, locator, size, receipt_id)):
                    raise TrainingStreamError("genesis stream already contains receipt metadata")
            else:
                if not isinstance(sha, str) or not _SHA256_RE.fullmatch(sha):
                    raise TrainingStreamError("completed stream lacks checkpoint SHA256")
                if not isinstance(locator, str) or not locator.strip():
                    raise TrainingStreamError("completed stream lacks checkpoint locator")
                if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
                    raise TrainingStreamError("completed stream lacks checkpoint size")
                if not isinstance(receipt_id, str) or not receipt_id.startswith(
                    "deepsix-receipt-v1:"
                ):
                    raise TrainingStreamError("completed stream lacks receipt identity")
            state.last_checkpoint_sha256 = sha
            state.last_checkpoint_locator = locator
            state.last_checkpoint_size_bytes = size
            state.last_receipt_id = receipt_id
        return obj


@dataclass(frozen=True)
class TrainingSchedulerCheckpointReceipt:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.path:
            raise TrainingStreamError("scheduler checkpoint path is required")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise TrainingStreamError("scheduler checkpoint SHA256 is invalid")
        _require_positive_int("scheduler checkpoint size", self.size_bytes)


def _scheduler_payload(scheduler: TrainingStreamScheduler) -> bytes:
    wrapper = {
        "schema": TRAINING_STREAM_CHECKPOINT_SCHEMA,
        "scheduler": scheduler.state_dict(),
    }
    return (
        json.dumps(wrapper, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def save_training_scheduler_checkpoint_atomic(
    path: str | Path,
    scheduler: TrainingStreamScheduler,
) -> TrainingSchedulerCheckpointReceipt:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _scheduler_payload(scheduler)
    digest = hashlib.sha256(payload).hexdigest()
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=target.name + ".tmp-",
            dir=target.parent,
            delete=False,
        ) as handle:
            tmp_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
        tmp_name = None
        try:
            directory_fd = os.open(target.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
    return TrainingSchedulerCheckpointReceipt(str(target), digest, len(payload))


def load_training_scheduler_checkpoint(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
    clear_active_leases: bool = True,
) -> TrainingStreamScheduler:
    raw = Path(path).read_bytes()
    if not raw:
        raise TrainingStreamError("scheduler checkpoint is empty")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise TrainingStreamError("scheduler checkpoint SHA256 mismatch")
    try:
        wrapper = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrainingStreamError("scheduler checkpoint is invalid JSON") from exc
    if not isinstance(wrapper, dict) or wrapper.get("schema") != TRAINING_STREAM_CHECKPOINT_SCHEMA:
        raise TrainingStreamError("wrong durable training checkpoint schema")
    scheduler_payload = wrapper.get("scheduler")
    if not isinstance(scheduler_payload, dict):
        raise TrainingStreamError("scheduler payload is missing")
    return TrainingStreamScheduler.from_state_dict(
        scheduler_payload,
        clear_active_leases=clear_active_leases,
    )
