"""Deterministic, shardable soak-run contracts for DeepSix Simulator.

The soak harness deliberately uses independent hands rather than a persistent cash
session. That keeps a long correctness run from terminating because all bankroll
has been lost to rake or because only one funded seat remains. Persistent-session
restart semantics are gated separately by SimulatorTableSnapshot.

Each shard processes a deterministic subsequence of the global hand indexes:
    shard_index, shard_index + shard_count, ...

This makes shards disjoint, reproducible and resumable without storing a huge seed
list in checkpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any, Mapping


SIMULATOR_SOAK_SCHEMA_VERSION = 1


class SimulatorSoakError(ValueError):
    pass


def _require_int(name: str, value: object, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SimulatorSoakError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise SimulatorSoakError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True)
class SimulatorSoakPlan:
    schema_version: int
    seed_base: int
    total_global_hands: int
    shard_count: int
    shard_index: int
    stake_cents: int
    player_counts: tuple[int, ...]
    stack_min_antes: int
    stack_max_antes: int
    bbj_enabled: bool
    replay_every: int

    def validate(self) -> None:
        _require_int("schema_version", self.schema_version, minimum=1)
        if self.schema_version != SIMULATOR_SOAK_SCHEMA_VERSION:
            raise SimulatorSoakError("unsupported soak schema version")
        _require_int("seed_base", self.seed_base, minimum=0)
        _require_int("total_global_hands", self.total_global_hands, minimum=1)
        _require_int("shard_count", self.shard_count, minimum=1)
        _require_int("shard_index", self.shard_index, minimum=0)
        if self.shard_index >= self.shard_count:
            raise SimulatorSoakError("shard_index must be smaller than shard_count")
        _require_int("stake_cents", self.stake_cents, minimum=1)
        if not self.player_counts:
            raise SimulatorSoakError("player_counts must be non-empty")
        if len(set(self.player_counts)) != len(self.player_counts):
            raise SimulatorSoakError("player_counts must be unique")
        for value in self.player_counts:
            _require_int("player_count", value, minimum=2)
            if value > 6:
                raise SimulatorSoakError("player_count must be within 2..6")
        _require_int("stack_min_antes", self.stack_min_antes, minimum=1)
        _require_int("stack_max_antes", self.stack_max_antes, minimum=1)
        if self.stack_min_antes > self.stack_max_antes:
            raise SimulatorSoakError("stack_min_antes must be <= stack_max_antes")
        if not isinstance(self.bbj_enabled, bool):
            raise SimulatorSoakError("bbj_enabled must be boolean")
        _require_int("replay_every", self.replay_every, minimum=0)

    @property
    def local_target_hands(self) -> int:
        self.validate()
        if self.shard_index >= self.total_global_hands:
            return 0
        return (
            (self.total_global_hands - 1 - self.shard_index) // self.shard_count
        ) + 1

    def global_index(self, ordinal: int) -> int:
        self.validate()
        _require_int("ordinal", ordinal, minimum=0)
        if ordinal >= self.local_target_hands:
            raise SimulatorSoakError("ordinal is outside this shard")
        return self.shard_index + ordinal * self.shard_count

    def seed_for_ordinal(self, ordinal: int) -> int:
        return self.seed_base + self.global_index(ordinal)

    def player_count_for_ordinal(self, ordinal: int) -> int:
        global_index = self.global_index(ordinal)
        return self.player_counts[global_index % len(self.player_counts)]

    def should_replay(self, ordinal: int) -> bool:
        self.global_index(ordinal)
        if self.replay_every == 0:
            return False
        return (ordinal + 1) % self.replay_every == 0 or (
            ordinal + 1 == self.local_target_hands
        )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "seed_base": self.seed_base,
            "total_global_hands": self.total_global_hands,
            "shard_count": self.shard_count,
            "shard_index": self.shard_index,
            "stake_cents": self.stake_cents,
            "player_counts": list(self.player_counts),
            "stack_min_antes": self.stack_min_antes,
            "stack_max_antes": self.stack_max_antes,
            "bbj_enabled": self.bbj_enabled,
            "replay_every": self.replay_every,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SimulatorSoakPlan":
        expected = {
            "schema_version",
            "seed_base",
            "total_global_hands",
            "shard_count",
            "shard_index",
            "stake_cents",
            "player_counts",
            "stack_min_antes",
            "stack_max_antes",
            "bbj_enabled",
            "replay_every",
        }
        if set(payload) != expected:
            raise SimulatorSoakError("soak plan keys differ from schema v1")
        if not isinstance(payload.get("bbj_enabled"), bool):
            raise SimulatorSoakError("bbj_enabled JSON field must be boolean")
        try:
            plan = cls(
                schema_version=payload["schema_version"],
                seed_base=payload["seed_base"],
                total_global_hands=payload["total_global_hands"],
                shard_count=payload["shard_count"],
                shard_index=payload["shard_index"],
                stake_cents=payload["stake_cents"],
                player_counts=tuple(payload["player_counts"]),
                stack_min_antes=payload["stack_min_antes"],
                stack_max_antes=payload["stack_max_antes"],
                bbj_enabled=payload["bbj_enabled"],
                replay_every=payload["replay_every"],
            )
        except (KeyError, TypeError) as exc:
            raise SimulatorSoakError("malformed soak plan") from exc
        plan.validate()
        return plan


@dataclass(frozen=True)
class SimulatorSoakCheckpoint:
    schema_version: int
    plan: SimulatorSoakPlan
    next_ordinal: int
    completed_hands: int
    decisions: int
    gross_pot_units: int
    rake_units: int
    bbj_units: int
    replay_checks: int
    zero_decision_hands: int
    terminal_board_0: int
    terminal_board_3: int
    terminal_board_4: int
    terminal_board_5: int

    @classmethod
    def new(cls, plan: SimulatorSoakPlan) -> "SimulatorSoakCheckpoint":
        plan.validate()
        result = cls(
            schema_version=SIMULATOR_SOAK_SCHEMA_VERSION,
            plan=plan,
            next_ordinal=0,
            completed_hands=0,
            decisions=0,
            gross_pot_units=0,
            rake_units=0,
            bbj_units=0,
            replay_checks=0,
            zero_decision_hands=0,
            terminal_board_0=0,
            terminal_board_3=0,
            terminal_board_4=0,
            terminal_board_5=0,
        )
        result.validate()
        return result

    @property
    def is_complete(self) -> bool:
        return self.next_ordinal == self.plan.local_target_hands

    def validate(self) -> None:
        if self.schema_version != SIMULATOR_SOAK_SCHEMA_VERSION:
            raise SimulatorSoakError("unsupported soak checkpoint schema")
        self.plan.validate()
        for name in (
            "next_ordinal",
            "completed_hands",
            "decisions",
            "gross_pot_units",
            "rake_units",
            "bbj_units",
            "replay_checks",
            "zero_decision_hands",
            "terminal_board_0",
            "terminal_board_3",
            "terminal_board_4",
            "terminal_board_5",
        ):
            _require_int(name, getattr(self, name), minimum=0)
        if self.next_ordinal != self.completed_hands:
            raise SimulatorSoakError("checkpoint ordinal/completed count diverged")
        if self.completed_hands > self.plan.local_target_hands:
            raise SimulatorSoakError("checkpoint exceeds shard target")
        board_total = (
            self.terminal_board_0
            + self.terminal_board_3
            + self.terminal_board_4
            + self.terminal_board_5
        )
        if board_total != self.completed_hands:
            raise SimulatorSoakError("terminal board histogram does not cover every hand")
        if self.replay_checks > self.completed_hands:
            raise SimulatorSoakError("replay checks exceed completed hands")
        if self.zero_decision_hands > self.completed_hands:
            raise SimulatorSoakError("zero-decision hands exceed completed hands")

    def advance(
        self,
        *,
        decisions: int,
        gross_pot_units: int,
        rake_units: int,
        bbj_units: int,
        terminal_board_cards: int,
        replay_checked: bool,
    ) -> "SimulatorSoakCheckpoint":
        self.validate()
        if self.is_complete:
            raise SimulatorSoakError("cannot advance a completed soak checkpoint")
        _require_int("decisions", decisions, minimum=0)
        _require_int("gross_pot_units", gross_pot_units, minimum=0)
        _require_int("rake_units", rake_units, minimum=0)
        _require_int("bbj_units", bbj_units, minimum=0)
        if terminal_board_cards not in (0, 3, 4, 5):
            raise SimulatorSoakError("terminal board must contain 0, 3, 4 or 5 cards")
        if not isinstance(replay_checked, bool):
            raise SimulatorSoakError("replay_checked must be boolean")

        board_field = f"terminal_board_{terminal_board_cards}"
        result = replace(
            self,
            next_ordinal=self.next_ordinal + 1,
            completed_hands=self.completed_hands + 1,
            decisions=self.decisions + decisions,
            gross_pot_units=self.gross_pot_units + gross_pot_units,
            rake_units=self.rake_units + rake_units,
            bbj_units=self.bbj_units + bbj_units,
            replay_checks=self.replay_checks + int(replay_checked),
            zero_decision_hands=self.zero_decision_hands + int(decisions == 0),
            **{board_field: getattr(self, board_field) + 1},
        )
        result.validate()
        return result

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "plan": self.plan.to_dict(),
            "next_ordinal": self.next_ordinal,
            "completed_hands": self.completed_hands,
            "decisions": self.decisions,
            "gross_pot_units": self.gross_pot_units,
            "rake_units": self.rake_units,
            "bbj_units": self.bbj_units,
            "replay_checks": self.replay_checks,
            "zero_decision_hands": self.zero_decision_hands,
            "terminal_board_0": self.terminal_board_0,
            "terminal_board_3": self.terminal_board_3,
            "terminal_board_4": self.terminal_board_4,
            "terminal_board_5": self.terminal_board_5,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SimulatorSoakCheckpoint":
        expected = {
            "schema_version",
            "plan",
            "next_ordinal",
            "completed_hands",
            "decisions",
            "gross_pot_units",
            "rake_units",
            "bbj_units",
            "replay_checks",
            "zero_decision_hands",
            "terminal_board_0",
            "terminal_board_3",
            "terminal_board_4",
            "terminal_board_5",
        }
        if set(payload) != expected:
            raise SimulatorSoakError("soak checkpoint keys differ from schema v1")
        plan_payload = payload.get("plan")
        if not isinstance(plan_payload, Mapping):
            raise SimulatorSoakError("soak checkpoint plan must be an object")
        try:
            checkpoint = cls(
                schema_version=payload["schema_version"],
                plan=SimulatorSoakPlan.from_dict(plan_payload),
                next_ordinal=payload["next_ordinal"],
                completed_hands=payload["completed_hands"],
                decisions=payload["decisions"],
                gross_pot_units=payload["gross_pot_units"],
                rake_units=payload["rake_units"],
                bbj_units=payload["bbj_units"],
                replay_checks=payload["replay_checks"],
                zero_decision_hands=payload["zero_decision_hands"],
                terminal_board_0=payload["terminal_board_0"],
                terminal_board_3=payload["terminal_board_3"],
                terminal_board_4=payload["terminal_board_4"],
                terminal_board_5=payload["terminal_board_5"],
            )
        except (KeyError, TypeError) as exc:
            raise SimulatorSoakError("malformed soak checkpoint") from exc
        checkpoint.validate()
        return checkpoint

    @classmethod
    def from_json(cls, text: str) -> "SimulatorSoakCheckpoint":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SimulatorSoakError("invalid soak checkpoint JSON") from exc
        if not isinstance(payload, dict):
            raise SimulatorSoakError("soak checkpoint JSON must be an object")
        return cls.from_dict(payload)
