"""Replay serialization and stale-decision safety tokens for DeepSix/OH6Plus."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .canonical import canonicalize_observation
from .state import (
    ActionEvent,
    ActionKind,
    SCHEMA_VERSION,
    SeatObservation,
    Street,
    TableObservation,
)

REPLAY_SCHEMA_VERSION = 1


class ReplayIntegrityError(ValueError):
    pass


def observation_to_dict(observation: TableObservation) -> dict:
    observation.validate()
    return {
        "schema_version": observation.schema_version,
        "hand_id": observation.hand_id,
        "observation_seq": observation.observation_seq,
        "source_timestamp_ms": observation.source_timestamp_ms,
        "street": observation.street.value,
        "dealer_seat": observation.dealer_seat,
        "hero_seat": observation.hero_seat,
        "hero_cards": list(observation.hero_cards),
        "board": list(observation.board),
        "seats": [
            {
                "seat": seat.seat,
                "dealt": seat.dealt,
                "folded": seat.folded,
                "all_in": seat.all_in,
                "stack": seat.stack,
                "committed_street": seat.committed_street,
                "committed_total": seat.committed_total,
            }
            for seat in observation.seats
        ],
        "actions": [
            {
                "seq": action.seq,
                "street": action.street.value,
                "actor_seat": action.actor_seat,
                "action": action.action.value,
                "amount_to": action.amount_to,
            }
            for action in observation.actions
        ],
        "ante": observation.ante,
        "pot": observation.pot,
        "to_call": observation.to_call,
        "min_raise_to": observation.min_raise_to,
        "max_raise_to": observation.max_raise_to,
    }


def observation_from_dict(data: dict) -> TableObservation:
    required = {
        "schema_version",
        "hand_id",
        "observation_seq",
        "source_timestamp_ms",
        "street",
        "dealer_seat",
        "hero_seat",
        "hero_cards",
        "board",
        "seats",
        "actions",
        "ante",
        "pot",
        "to_call",
        "min_raise_to",
        "max_raise_to",
    }
    if set(data) != required:
        missing = sorted(required - set(data))
        extra = sorted(set(data) - required)
        raise ReplayIntegrityError(
            f"observation keys mismatch missing={missing} extra={extra}"
        )

    observation = TableObservation(
        schema_version=int(data["schema_version"]),
        hand_id=str(data["hand_id"]),
        observation_seq=int(data["observation_seq"]),
        source_timestamp_ms=int(data["source_timestamp_ms"]),
        street=Street(data["street"]),
        dealer_seat=int(data["dealer_seat"]),
        hero_seat=int(data["hero_seat"]),
        hero_cards=tuple(int(x) for x in data["hero_cards"]),
        board=tuple(int(x) for x in data["board"]),
        seats=tuple(
            SeatObservation(
                seat=int(row["seat"]),
                dealt=bool(row["dealt"]),
                folded=bool(row["folded"]),
                all_in=bool(row["all_in"]),
                stack=int(row["stack"]),
                committed_street=int(row["committed_street"]),
                committed_total=int(row["committed_total"]),
            )
            for row in data["seats"]
        ),
        actions=tuple(
            ActionEvent(
                seq=int(row["seq"]),
                street=Street(row["street"]),
                actor_seat=int(row["actor_seat"]),
                action=ActionKind(row["action"]),
                amount_to=None if row["amount_to"] is None else int(row["amount_to"]),
            )
            for row in data["actions"]
        ),
        ante=int(data["ante"]),
        pot=int(data["pot"]),
        to_call=int(data["to_call"]),
        min_raise_to=int(data["min_raise_to"]),
        max_raise_to=int(data["max_raise_to"]),
    )
    observation.validate()
    return observation


@dataclass(frozen=True)
class DecisionToken:
    hand_id: str
    observation_schema_version: int
    canonical_fingerprint: str

    @classmethod
    def capture(cls, observation: TableObservation) -> "DecisionToken":
        observation.validate()
        return cls(
            hand_id=observation.hand_id,
            observation_schema_version=observation.schema_version,
            canonical_fingerprint=canonicalize_observation(observation).fingerprint(),
        )

    def matches(self, observation: TableObservation) -> bool:
        if observation.hand_id != self.hand_id:
            return False
        if observation.schema_version != self.observation_schema_version:
            return False
        return (
            canonicalize_observation(observation).fingerprint()
            == self.canonical_fingerprint
        )


@dataclass(frozen=True)
class ReplayFrame:
    replay_schema_version: int
    observation: TableObservation
    observation_fingerprint: str
    canonical_fingerprint: str

    @classmethod
    def capture(cls, observation: TableObservation) -> "ReplayFrame":
        observation.validate()
        return cls(
            replay_schema_version=REPLAY_SCHEMA_VERSION,
            observation=observation,
            observation_fingerprint=observation.observation_fingerprint(),
            canonical_fingerprint=canonicalize_observation(observation).fingerprint(),
        )

    def verify(self) -> None:
        if self.replay_schema_version != REPLAY_SCHEMA_VERSION:
            raise ReplayIntegrityError("unsupported replay schema version")
        if self.observation.schema_version != SCHEMA_VERSION:
            raise ReplayIntegrityError("unsupported observation schema version")
        if self.observation.observation_fingerprint() != self.observation_fingerprint:
            raise ReplayIntegrityError("observation fingerprint mismatch")
        if (
            canonicalize_observation(self.observation).fingerprint()
            != self.canonical_fingerprint
        ):
            raise ReplayIntegrityError("canonical fingerprint mismatch")

    def to_json(self) -> str:
        self.verify()
        return json.dumps(
            {
                "replay_schema_version": self.replay_schema_version,
                "observation": observation_to_dict(self.observation),
                "observation_fingerprint": self.observation_fingerprint,
                "canonical_fingerprint": self.canonical_fingerprint,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, text: str) -> "ReplayFrame":
        data = json.loads(text)
        required = {
            "replay_schema_version",
            "observation",
            "observation_fingerprint",
            "canonical_fingerprint",
        }
        if set(data) != required:
            raise ReplayIntegrityError("replay keys mismatch")
        frame = cls(
            replay_schema_version=int(data["replay_schema_version"]),
            observation=observation_from_dict(data["observation"]),
            observation_fingerprint=str(data["observation_fingerprint"]),
            canonical_fingerprint=str(data["canonical_fingerprint"]),
        )
        frame.verify()
        return frame
