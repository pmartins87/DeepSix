#!/usr/bin/env python3
"""Verify the C++ OH6Plus observation fixture against the Python/Core contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deepsix_core.state import (  # noqa: E402
    ActionEvent,
    ActionKind,
    SeatObservation,
    Street,
    TableObservation,
)

EXPECTED_OBSERVATION_FINGERPRINT = (
    "e2b2ed3920c37a185ada2bb51ab30bc199718d51e5c5d44fa305067442899de9"
)
EXPECTED_SEMANTIC_FINGERPRINT = (
    "cd65dd8fe38717e924d6b5393e67ed3eddb0d08c0d2936ecfa030b237f136117"
)


def _observation_from_payload(payload: dict) -> TableObservation:
    return TableObservation(
        schema_version=payload["schema_version"],
        hand_id=payload["hand_id"],
        observation_seq=payload["observation_seq"],
        source_timestamp_ms=payload["source_timestamp_ms"],
        street=Street(payload["street"]),
        dealer_seat=payload["dealer_seat"],
        hero_seat=payload["hero_seat"],
        hero_cards=tuple(payload["hero_cards"]),
        board=tuple(payload["board"]),
        seats=tuple(SeatObservation(**seat) for seat in payload["seats"]),
        actions=tuple(
            ActionEvent(
                seq=action["seq"],
                street=Street(action["street"]),
                actor_seat=action["actor_seat"],
                action=ActionKind(action["action"]),
                amount_to=action["amount_to"],
            )
            for action in payload["actions"]
        ),
        ante=payload["ante"],
        pot=payload["pot"],
        to_call=payload["to_call"],
        min_raise_to=payload["min_raise_to"],
        max_raise_to=payload["max_raise_to"],
    )


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_cpp_observation_fixture.py <fixture.txt>")

    lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    if len(lines) != 2:
        raise AssertionError(f"expected exactly 2 canonical JSON lines, got {len(lines)}")

    full_line, semantic_line = lines
    full_payload = json.loads(full_line)
    semantic_payload = json.loads(semantic_line)

    observation = _observation_from_payload(full_payload)
    observation.validate()

    python_full = observation._payload(include_transport=True)
    python_semantic = observation._payload(include_transport=False)
    python_full_line = _canonical_json(python_full)
    python_semantic_line = _canonical_json(python_semantic)

    if full_line != python_full_line:
        raise AssertionError("C++ full observation JSON differs from Python canonical bytes")
    if semantic_line != python_semantic_line:
        raise AssertionError("C++ semantic JSON differs from Python canonical bytes")

    # JSON arrays decode as lists while dataclasses.asdict() preserves tuples.
    # Compare the JSON-normalized structures so tuple/list representation does
    # not create a false semantic mismatch after exact byte parity already passed.
    if full_payload != json.loads(python_full_line):
        raise AssertionError("C++ full payload differs from Python JSON-normalized payload")
    if semantic_payload != json.loads(python_semantic_line):
        raise AssertionError("C++ semantic payload differs from Python JSON-normalized payload")

    if observation.observation_fingerprint() != EXPECTED_OBSERVATION_FINGERPRINT:
        raise AssertionError("cross-language observation fingerprint mismatch")
    if observation.semantic_fingerprint() != EXPECTED_SEMANTIC_FINGERPRINT:
        raise AssertionError("cross-language semantic fingerprint mismatch")

    print("OH6Plus C++ -> Python canonical observation: PASS")
    print(f"observation_fingerprint={EXPECTED_OBSERVATION_FINGERPRINT}")
    print(f"semantic_fingerprint={EXPECTED_SEMANTIC_FINGERPRINT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
