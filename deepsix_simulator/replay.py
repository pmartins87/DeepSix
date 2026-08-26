"""Canonical post-hand transcript and exact replay for DeepSix Simulator.

A transcript is an audit artifact, not an agent observation. It stores the seed
and therefore reveals the private deal to anyone who replays it after the hand.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from deepsix_core.ggpoker_economy import GGPOKER_SHORTDECK_ECONOMY_VERSION
from deepsix_core.state import ActionKind

from .environment import SIMULATOR_ENV_VERSION, SimulatedHand, SimulatorAction
from .rules import DEFAULT_SIMULATOR_RULES, SIMULATOR_RULES_VERSION
from .settlement import SIMULATOR_SETTLEMENT_VERSION, SimulatorSettlement


SIMULATOR_TRANSCRIPT_SCHEMA_VERSION = 1


class SimulatorReplayError(ValueError):
    pass


@dataclass(frozen=True)
class SimulatorDecisionRecord:
    decision_index: int
    actor_seat: int
    action: str
    amount_to: int | None


@dataclass(frozen=True)
class SimulatorHandTranscript:
    schema_version: int
    env_version: str
    rules_version: str
    economy_version: str
    settlement_version: str
    hand_id: str
    stake_cents: int
    seed: int
    dealer_seat: int
    starting_stacks: tuple[tuple[int, int], ...]
    bbj_enabled: bool
    decisions: tuple[SimulatorDecisionRecord, ...]
    final_board: tuple[int, ...]
    private_deal_sha256: str
    settlement_sha256: str

    def validate(self) -> None:
        if self.schema_version != SIMULATOR_TRANSCRIPT_SCHEMA_VERSION:
            raise SimulatorReplayError("unsupported transcript schema version")
        if self.env_version != SIMULATOR_ENV_VERSION:
            raise SimulatorReplayError("transcript environment version mismatch")
        if self.rules_version != SIMULATOR_RULES_VERSION:
            raise SimulatorReplayError("transcript rules version mismatch")
        if self.economy_version != GGPOKER_SHORTDECK_ECONOMY_VERSION:
            raise SimulatorReplayError("transcript economy version mismatch")
        if self.settlement_version != SIMULATOR_SETTLEMENT_VERSION:
            raise SimulatorReplayError("transcript settlement version mismatch")
        if not self.hand_id:
            raise SimulatorReplayError("hand_id must be non-empty")
        if self.stake_cents <= 0:
            raise SimulatorReplayError("stake_cents must be positive")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise SimulatorReplayError("seed must be integer")
        seats = [seat for seat, _ in self.starting_stacks]
        if len(seats) < 2 or len(seats) > 6 or len(set(seats)) != len(seats):
            raise SimulatorReplayError("starting_stacks must contain 2..6 unique seats")
        if self.dealer_seat not in seats:
            raise SimulatorReplayError("dealer must be present in starting stacks")
        if any(stack <= 0 for _, stack in self.starting_stacks):
            raise SimulatorReplayError("starting stacks must be positive")
        if not isinstance(self.bbj_enabled, bool):
            raise SimulatorReplayError("bbj_enabled must be bool")
        if len(self.final_board) not in (0, 5):
            raise SimulatorReplayError("terminal transcript board must contain 0 or 5 cards")
        if len(self.private_deal_sha256) != 64 or len(self.settlement_sha256) != 64:
            raise SimulatorReplayError("transcript digest must be SHA-256 hex")
        for index, decision in enumerate(self.decisions):
            if decision.decision_index != index:
                raise SimulatorReplayError("decision indexes must be contiguous from zero")
            if decision.actor_seat not in seats:
                raise SimulatorReplayError("decision actor not in starting seats")
            try:
                action = ActionKind(decision.action)
            except ValueError as exc:
                raise SimulatorReplayError("unknown action in transcript") from exc
            if action == ActionKind.RAISE_TO:
                if decision.amount_to is None or decision.amount_to <= 0:
                    raise SimulatorReplayError("raise_to transcript action needs amount")
            elif decision.amount_to is not None:
                raise SimulatorReplayError("non-raise transcript action has amount")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "env_version": self.env_version,
            "rules_version": self.rules_version,
            "economy_version": self.economy_version,
            "settlement_version": self.settlement_version,
            "hand_id": self.hand_id,
            "stake_cents": self.stake_cents,
            "seed": self.seed,
            "dealer_seat": self.dealer_seat,
            "starting_stacks": [list(item) for item in self.starting_stacks],
            "bbj_enabled": self.bbj_enabled,
            "decisions": [
                {
                    "decision_index": item.decision_index,
                    "actor_seat": item.actor_seat,
                    "action": item.action,
                    "amount_to": item.amount_to,
                }
                for item in self.decisions
            ],
            "final_board": list(self.final_board),
            "private_deal_sha256": self.private_deal_sha256,
            "settlement_sha256": self.settlement_sha256,
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
    def from_dict(cls, payload: Mapping[str, Any]) -> "SimulatorHandTranscript":
        expected = {
            "schema_version",
            "env_version",
            "rules_version",
            "economy_version",
            "settlement_version",
            "hand_id",
            "stake_cents",
            "seed",
            "dealer_seat",
            "starting_stacks",
            "bbj_enabled",
            "decisions",
            "final_board",
            "private_deal_sha256",
            "settlement_sha256",
        }
        if set(payload) != expected:
            raise SimulatorReplayError("transcript keys differ from schema v1")
        try:
            transcript = cls(
                schema_version=int(payload["schema_version"]),
                env_version=str(payload["env_version"]),
                rules_version=str(payload["rules_version"]),
                economy_version=str(payload["economy_version"]),
                settlement_version=str(payload["settlement_version"]),
                hand_id=str(payload["hand_id"]),
                stake_cents=int(payload["stake_cents"]),
                seed=int(payload["seed"]),
                dealer_seat=int(payload["dealer_seat"]),
                starting_stacks=tuple(
                    (int(item[0]), int(item[1])) for item in payload["starting_stacks"]
                ),
                bbj_enabled=bool(payload["bbj_enabled"]),
                decisions=tuple(
                    SimulatorDecisionRecord(
                        decision_index=int(item["decision_index"]),
                        actor_seat=int(item["actor_seat"]),
                        action=str(item["action"]),
                        amount_to=(
                            None if item["amount_to"] is None else int(item["amount_to"])
                        ),
                    )
                    for item in payload["decisions"]
                ),
                final_board=tuple(int(card) for card in payload["final_board"]),
                private_deal_sha256=str(payload["private_deal_sha256"]),
                settlement_sha256=str(payload["settlement_sha256"]),
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise SimulatorReplayError("malformed transcript payload") from exc
        transcript.validate()
        return transcript

    @classmethod
    def from_json(cls, text: str) -> "SimulatorHandTranscript":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SimulatorReplayError("invalid transcript JSON") from exc
        if not isinstance(payload, dict):
            raise SimulatorReplayError("transcript JSON must be an object")
        return cls.from_dict(payload)


def _private_deal_sha256(hand: SimulatedHand) -> str:
    payload = {str(seat): list(hand.hole_cards[seat]) for seat in sorted(hand.hole_cards)}
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _settlement_payload(settlement: SimulatorSettlement) -> dict[str, Any]:
    return {
        "settlement_version": settlement.settlement_version,
        "economy_version": settlement.economy_version,
        "rules_version": settlement.rules_version,
        "gross_pot_units": settlement.gross_pot_units,
        "gross_awards": [list(item) for item in settlement.gross_awards],
        "house_charges": [list(item) for item in settlement.house_charges],
        "net_awards": [list(item) for item in settlement.net_awards],
        "post_hand_stacks": [list(item) for item in settlement.post_hand_stacks],
        "deductions": {
            "rake_numerator": settlement.deductions.exact_rake_before_rounding.numerator,
            "rake_denominator": settlement.deductions.exact_rake_before_rounding.denominator,
            "rounded_rake_units": settlement.deductions.rounded_rake_units,
            "bbj_units": settlement.deductions.bbj_units,
            "total_units": settlement.deductions.total_units,
        },
    }


def settlement_sha256(settlement: SimulatorSettlement) -> str:
    text = json.dumps(
        _settlement_payload(settlement),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def transcript_from_hand(hand: SimulatedHand) -> SimulatorHandTranscript:
    if not hand.terminal or hand.settlement is None:
        raise SimulatorReplayError("transcript requires a terminal settled hand")
    # stack-behind + committed_total is invariant for each seat throughout a hand,
    # so the exact pre-hand stack is recoverable even after settlement is computed.
    starting_stacks = tuple(
        sorted(
            (player.seat, player.stack + player.committed_total)
            for player in hand.state.players
        )
    )
    decisions = tuple(
        SimulatorDecisionRecord(
            decision_index=index,
            actor_seat=event.actor_seat,
            action=event.action.value,
            amount_to=event.amount_to,
        )
        for index, event in enumerate(hand.state.actions)
    )
    transcript = SimulatorHandTranscript(
        schema_version=SIMULATOR_TRANSCRIPT_SCHEMA_VERSION,
        env_version=SIMULATOR_ENV_VERSION,
        rules_version=hand.rules.version,
        economy_version=hand.settlement.economy_version,
        settlement_version=hand.settlement.settlement_version,
        hand_id=hand.hand_id,
        stake_cents=hand.stake_cents,
        seed=hand.seed,
        dealer_seat=hand.state.dealer_seat,
        starting_stacks=starting_stacks,
        bbj_enabled=hand.bbj_enabled,
        decisions=decisions,
        final_board=hand.state.board,
        private_deal_sha256=_private_deal_sha256(hand),
        settlement_sha256=settlement_sha256(hand.settlement),
    )
    transcript.validate()
    return transcript


def replay_transcript(transcript: SimulatorHandTranscript) -> SimulatedHand:
    """Recreate the hand and prove hidden deal, board and settlement identity."""
    transcript.validate()
    hand = SimulatedHand.start(
        hand_id=transcript.hand_id,
        stake_cents=transcript.stake_cents,
        seed=transcript.seed,
        dealer_seat=transcript.dealer_seat,
        stacks=transcript.starting_stacks,
        rules=DEFAULT_SIMULATOR_RULES,
        bbj_enabled=transcript.bbj_enabled,
    )
    for record in transcript.decisions:
        if hand.terminal:
            raise SimulatorReplayError("transcript contains decisions after terminal")
        if hand.decision_index != record.decision_index:
            raise SimulatorReplayError("decision index diverged during replay")
        if hand.actor_seat != record.actor_seat:
            raise SimulatorReplayError(
                f"actor diverged during replay: expected {record.actor_seat}, got {hand.actor_seat}"
            )
        hand.act(
            record.actor_seat,
            SimulatorAction(ActionKind(record.action), record.amount_to),
        )
    if not hand.terminal or hand.settlement is None:
        raise SimulatorReplayError("transcript ended before simulated hand terminal")
    if hand.state.board != transcript.final_board:
        raise SimulatorReplayError("board diverged during replay")
    if _private_deal_sha256(hand) != transcript.private_deal_sha256:
        raise SimulatorReplayError("private deal digest diverged during replay")
    if settlement_sha256(hand.settlement) != transcript.settlement_sha256:
        raise SimulatorReplayError("settlement digest diverged during replay")
    return hand
