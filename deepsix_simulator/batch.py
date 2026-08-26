"""Deterministic multi-hand session runner for DeepSix Simulator.

This is intentionally single-process. Its first purpose is correctness,
reproducibility and soak evidence. Parallel workers should wrap this boundary
only after profiling shows where process-level parallelism pays off.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping

from .environment import AgentPolicy, DeepSixTable, SimulatorEnvironmentError
from .replay import transcript_from_hand


SIMULATOR_SESSION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SessionHandRecord:
    hand_index: int
    seed: int
    dealer_seat: int
    dealt_players: int
    decisions: int
    gross_pot_units: int
    rake_units: int
    bbj_units: int
    transcript_fingerprint: str


@dataclass(frozen=True)
class SimulatorSessionResult:
    schema_version: int
    stake_cents: int
    starting_stacks: tuple[tuple[int, int], ...]
    final_stacks: tuple[tuple[int, int], ...]
    hands: tuple[SessionHandRecord, ...]
    stop_reason: str

    @property
    def hands_played(self) -> int:
        return len(self.hands)

    @property
    def decisions(self) -> int:
        return sum(record.decisions for record in self.hands)

    @property
    def total_rake_units(self) -> int:
        return sum(record.rake_units for record in self.hands)

    @property
    def total_bbj_units(self) -> int:
        return sum(record.bbj_units for record in self.hands)

    @property
    def total_house_deductions(self) -> int:
        return self.total_rake_units + self.total_bbj_units

    def validate(self) -> None:
        if self.schema_version != SIMULATOR_SESSION_SCHEMA_VERSION:
            raise SimulatorEnvironmentError("unsupported simulator session schema")
        start_seats = [seat for seat, _ in self.starting_stacks]
        final_seats = [seat for seat, _ in self.final_stacks]
        if start_seats != final_seats or len(set(start_seats)) != len(start_seats):
            raise SimulatorEnvironmentError("session stack seat sets differ")
        if any(stack < 0 for _, stack in self.final_stacks):
            raise SimulatorEnvironmentError("negative final stack")
        if self.stop_reason not in ("seed_schedule_exhausted", "insufficient_funded_seats"):
            raise SimulatorEnvironmentError("unknown session stop reason")
        for expected, record in enumerate(self.hands):
            if record.hand_index != expected:
                raise SimulatorEnvironmentError("session hand indexes must be contiguous")
            if record.dealt_players < 2 or record.dealt_players > 6:
                raise SimulatorEnvironmentError("invalid dealt-player count in session")
            if record.decisions < 1:
                raise SimulatorEnvironmentError("settled session hand has no decisions")
            if record.gross_pot_units < 0 or record.rake_units < 0 or record.bbj_units < 0:
                raise SimulatorEnvironmentError("negative monetary session statistic")
            if len(record.transcript_fingerprint) != 64:
                raise SimulatorEnvironmentError("invalid transcript fingerprint")

        start_total = sum(stack for _, stack in self.starting_stacks)
        final_total = sum(stack for _, stack in self.final_stacks)
        if final_total != start_total - self.total_house_deductions:
            raise SimulatorEnvironmentError("session bankroll conservation failed")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "stake_cents": self.stake_cents,
            "starting_stacks": [list(item) for item in self.starting_stacks],
            "final_stacks": [list(item) for item in self.final_stacks],
            "hands": [
                {
                    "hand_index": record.hand_index,
                    "seed": record.seed,
                    "dealer_seat": record.dealer_seat,
                    "dealt_players": record.dealt_players,
                    "decisions": record.decisions,
                    "gross_pot_units": record.gross_pot_units,
                    "rake_units": record.rake_units,
                    "bbj_units": record.bbj_units,
                    "transcript_fingerprint": record.transcript_fingerprint,
                }
                for record in self.hands
            ],
            "stop_reason": self.stop_reason,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def run_seeded_session(
    table: DeepSixTable,
    agents: Mapping[int, AgentPolicy],
    seeds: Iterable[int],
    *,
    max_decisions_per_hand: int = 1000,
) -> SimulatorSessionResult:
    """Run one deterministic session over an explicit seed schedule."""

    if max_decisions_per_hand <= 0:
        raise SimulatorEnvironmentError("max_decisions_per_hand must be positive")
    starting_stacks = tuple(sorted(table.stacks.items()))
    records: list[SessionHandRecord] = []
    stop_reason = "seed_schedule_exhausted"

    for seed in seeds:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise SimulatorEnvironmentError("every session seed must be an integer")
        if len(table._live_seats()) < 2:
            stop_reason = "insufficient_funded_seats"
            break

        hand = table.start_hand(seed=seed)
        dealer = hand.state.dealer_seat
        dealt_players = len(hand.state.players)
        hand.play_to_terminal(agents, max_decisions=max_decisions_per_hand)
        if hand.settlement is None:
            raise SimulatorEnvironmentError("settled session hand missing settlement")
        transcript = transcript_from_hand(hand)
        settlement = table.commit_settlement(hand)
        records.append(
            SessionHandRecord(
                hand_index=len(records),
                seed=seed,
                dealer_seat=dealer,
                dealt_players=dealt_players,
                decisions=hand.decision_index,
                gross_pot_units=settlement.gross_pot_units,
                rake_units=settlement.deductions.rounded_rake_units,
                bbj_units=settlement.deductions.bbj_units,
                transcript_fingerprint=transcript.fingerprint(),
            )
        )

    result = SimulatorSessionResult(
        schema_version=SIMULATOR_SESSION_SCHEMA_VERSION,
        stake_cents=table.stake_cents,
        starting_stacks=starting_stacks,
        final_stacks=tuple(sorted(table.stacks.items())),
        hands=tuple(records),
        stop_reason=stop_reason,
    )
    result.validate()
    return result
