"""Versioned cash-table snapshots for crash/restart-safe simulator sessions.

Snapshots are taken only between hands.  They preserve every piece of state that
can affect future hands: stake, physical seat set, stacks (including busted
zero stacks), Dealer, hand index, rules version and BBJ toggle.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from deepsix_core.ggpoker_economy import GGPOKER_SHORTDECK_ECONOMY_VERSION

from .environment import DeepSixTable, SimulatorEnvironmentError
from .rules import DEFAULT_SIMULATOR_RULES, SIMULATOR_RULES_VERSION


SIMULATOR_TABLE_SNAPSHOT_SCHEMA_VERSION = 1


class SimulatorSnapshotError(ValueError):
    pass


@dataclass(frozen=True)
class SimulatorTableSnapshot:
    schema_version: int
    rules_version: str
    economy_version: str
    stake_cents: int
    seats: tuple[int, ...]
    stacks: tuple[tuple[int, int], ...]
    dealer_seat: int
    hand_index: int
    bbj_enabled: bool

    def validate(self) -> None:
        if self.schema_version != SIMULATOR_TABLE_SNAPSHOT_SCHEMA_VERSION:
            raise SimulatorSnapshotError("unsupported table snapshot schema")
        if self.rules_version != SIMULATOR_RULES_VERSION:
            raise SimulatorSnapshotError("table snapshot rules version mismatch")
        if self.economy_version != GGPOKER_SHORTDECK_ECONOMY_VERSION:
            raise SimulatorSnapshotError("table snapshot economy version mismatch")
        if self.stake_cents <= 0:
            raise SimulatorSnapshotError("snapshot stake must be positive")
        if len(self.seats) < 2 or len(self.seats) > 6:
            raise SimulatorSnapshotError("snapshot requires 2..6 physical seats")
        if tuple(sorted(self.seats)) != self.seats or len(set(self.seats)) != len(self.seats):
            raise SimulatorSnapshotError("snapshot seats must be sorted and unique")
        if any(
            isinstance(seat, bool)
            or not isinstance(seat, int)
            or seat < 0
            or seat >= 6
            for seat in self.seats
        ):
            raise SimulatorSnapshotError("snapshot seats must be physical 0..5")
        stack_seats = tuple(seat for seat, _ in self.stacks)
        if stack_seats != self.seats:
            raise SimulatorSnapshotError("snapshot stacks must cover seats in canonical order")
        if any(
            isinstance(stack, bool) or not isinstance(stack, int) or stack < 0
            for _, stack in self.stacks
        ):
            raise SimulatorSnapshotError("snapshot stacks must be non-negative integers")
        if self.dealer_seat not in self.seats:
            raise SimulatorSnapshotError("snapshot Dealer must be seated")
        if isinstance(self.hand_index, bool) or not isinstance(self.hand_index, int) or self.hand_index < 0:
            raise SimulatorSnapshotError("snapshot hand_index must be non-negative integer")
        if not isinstance(self.bbj_enabled, bool):
            raise SimulatorSnapshotError("snapshot bbj_enabled must be bool")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "rules_version": self.rules_version,
            "economy_version": self.economy_version,
            "stake_cents": self.stake_cents,
            "seats": list(self.seats),
            "stacks": [list(item) for item in self.stacks],
            "dealer_seat": self.dealer_seat,
            "hand_index": self.hand_index,
            "bbj_enabled": self.bbj_enabled,
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
    def from_dict(cls, payload: Mapping[str, Any]) -> "SimulatorTableSnapshot":
        expected = {
            "schema_version",
            "rules_version",
            "economy_version",
            "stake_cents",
            "seats",
            "stacks",
            "dealer_seat",
            "hand_index",
            "bbj_enabled",
        }
        if set(payload) != expected:
            raise SimulatorSnapshotError("table snapshot keys differ from schema v1")
        if not isinstance(payload.get("bbj_enabled"), bool):
            raise SimulatorSnapshotError("snapshot bbj_enabled JSON field must be boolean")
        try:
            snapshot = cls(
                schema_version=int(payload["schema_version"]),
                rules_version=str(payload["rules_version"]),
                economy_version=str(payload["economy_version"]),
                stake_cents=int(payload["stake_cents"]),
                seats=tuple(int(seat) for seat in payload["seats"]),
                stacks=tuple((int(item[0]), int(item[1])) for item in payload["stacks"]),
                dealer_seat=int(payload["dealer_seat"]),
                hand_index=int(payload["hand_index"]),
                bbj_enabled=payload["bbj_enabled"],
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise SimulatorSnapshotError("malformed table snapshot") from exc
        snapshot.validate()
        return snapshot

    @classmethod
    def from_json(cls, text: str) -> "SimulatorTableSnapshot":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SimulatorSnapshotError("invalid table snapshot JSON") from exc
        if not isinstance(payload, dict):
            raise SimulatorSnapshotError("table snapshot JSON must be an object")
        return cls.from_dict(payload)


def snapshot_table(table: DeepSixTable) -> SimulatorTableSnapshot:
    """Capture a canonical between-hands snapshot."""
    snapshot = SimulatorTableSnapshot(
        schema_version=SIMULATOR_TABLE_SNAPSHOT_SCHEMA_VERSION,
        rules_version=table.rules.version,
        economy_version=GGPOKER_SHORTDECK_ECONOMY_VERSION,
        stake_cents=table.stake_cents,
        seats=tuple(sorted(table.seats)),
        stacks=tuple((seat, int(table.stacks[seat])) for seat in sorted(table.seats)),
        dealer_seat=table.dealer_seat,
        hand_index=table.hand_index,
        bbj_enabled=table.bbj_enabled,
    )
    snapshot.validate()
    return snapshot


def restore_table(snapshot: SimulatorTableSnapshot) -> DeepSixTable:
    """Restore future-hand semantics exactly from a canonical snapshot.

    `DeepSixTable` normally starts every chair with a positive buy-in.  A saved
    session may contain busted zero-stack chairs, so restoration creates a valid
    table shell first and then replaces its between-hand state with the audited
    snapshot.  `start_hand()` already filters funded seats and refuses play when
    fewer than two remain.
    """
    snapshot.validate()
    if snapshot.rules_version != DEFAULT_SIMULATOR_RULES.version:
        raise SimulatorSnapshotError("no installed rules implementation for snapshot")

    table = DeepSixTable(
        stake_cents=snapshot.stake_cents,
        player_count=len(snapshot.seats),
        dealer_seat=snapshot.dealer_seat,
        rules=DEFAULT_SIMULATOR_RULES,
        bbj_enabled=snapshot.bbj_enabled,
    )
    if tuple(table.seats) != snapshot.seats:
        # v1 table chairs are contiguous 0..N-1. Refuse to silently remap a
        # future sparse-table snapshot to different physical identities.
        raise SimulatorSnapshotError("snapshot seat layout unsupported by table v1")
    table.stacks = dict(snapshot.stacks)
    table.dealer_seat = snapshot.dealer_seat
    table.hand_index = snapshot.hand_index

    roundtrip = snapshot_table(table)
    if roundtrip != snapshot:
        raise SimulatorSnapshotError("restored table does not reproduce snapshot")
    return table
