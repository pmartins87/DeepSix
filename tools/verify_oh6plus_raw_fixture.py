#!/usr/bin/env python3
"""Verify an OH6Plus C++ RawTableSnapshot fixture against Python/Core."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deepsix_core.raw_snapshot import raw_snapshot_from_json  # noqa: E402


EXPECTED_AUDIT_FINGERPRINT = (
    "dcef7d020294c104067ae5804cf0c2df653ec8d32b19e324e476a1ec1329c21d"
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_oh6plus_raw_fixture.py <fixture.txt>")

    lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise AssertionError(f"expected exactly one raw JSON line, got {len(lines)}")

    cpp_line = lines[0]
    snapshot = raw_snapshot_from_json(cpp_line)
    python_line = snapshot.canonical_json()
    if cpp_line != python_line:
        raise AssertionError("OH6Plus C++ raw JSON differs from Python canonical bytes")

    fingerprint = snapshot.audit_fingerprint()
    if fingerprint != EXPECTED_AUDIT_FINGERPRINT:
        raise AssertionError(
            f"raw audit fingerprint mismatch: {fingerprint} != "
            f"{EXPECTED_AUDIT_FINGERPRINT}"
        )

    print("OH6Plus raw C++ -> Python contract: PASS")
    print(f"audit_fingerprint={fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
