"""Extract the project-provided OpenHoldem source dump reproducibly.

The source evidence artifact is a concatenation of text files separated by
markers of the form:

    ========== ARQUIVO: C:\\...\\OpenHoldem\\Foo.cpp ==========

This tool verifies the known artifact hash by default and reconstructs only
paths below the embedded `OpenHoldem\\` root. It deliberately does not claim to
recreate a build-complete working tree because solution/project/resources are
not present in the supplied dump.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

EXPECTED_SHA256 = "8a2809bf32b226775a237c9a51f970e8fd55148e777890f9a275b5fd6bd8521e"
EXPECTED_SIZE = 2_275_222
EXPECTED_FILES = 393
EXPECTED_CPP = 196
EXPECTED_H = 197

MARKER_RE = re.compile(r"^========== ARQUIVO: (.+?) ==========\s*$", re.MULTILINE)


class SourceDumpError(ValueError):
    pass


@dataclass(frozen=True)
class DumpEntry:
    relative_path: Path
    content: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_openholdem_path(raw_path: str) -> Path:
    parts = list(PureWindowsPath(raw_path).parts)
    try:
        root_index = next(i for i, part in enumerate(parts) if part.lower() == "openholdem")
    except StopIteration as exc:
        raise SourceDumpError(f"path does not contain OpenHoldem root: {raw_path!r}") from exc
    tail = parts[root_index + 1 :]
    if not tail:
        raise SourceDumpError(f"marker points to OpenHoldem directory, not a file: {raw_path!r}")
    if any(part in ("", ".", "..") for part in tail):
        raise SourceDumpError(f"unsafe relative path in marker: {raw_path!r}")
    return Path(*tail)


def parse_dump_text(text: str) -> tuple[DumpEntry, ...]:
    matches = list(MARKER_RE.finditer(text))
    if not matches:
        raise SourceDumpError("no source-file markers found")

    entries: list[DumpEntry] = []
    seen: set[Path] = set()
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        relative = relative_openholdem_path(match.group(1))
        if relative in seen:
            raise SourceDumpError(f"duplicate embedded path: {relative}")
        seen.add(relative)

        body = text[start:end]
        # The dump format inserts one newline after each marker. Remove exactly
        # that structural newline while preserving the embedded file thereafter.
        if body.startswith("\r\n"):
            body = body[2:]
        elif body.startswith("\n"):
            body = body[1:]
        entries.append(DumpEntry(relative_path=relative, content=body))
    return tuple(entries)


def verify_known_dump(data: bytes, entries: tuple[DumpEntry, ...]) -> None:
    digest = sha256_bytes(data)
    if digest != EXPECTED_SHA256:
        raise SourceDumpError(
            f"source dump SHA256 mismatch: got {digest}, expected {EXPECTED_SHA256}"
        )
    if len(data) != EXPECTED_SIZE:
        raise SourceDumpError(
            f"source dump size mismatch: got {len(data)}, expected {EXPECTED_SIZE}"
        )
    if len(entries) != EXPECTED_FILES:
        raise SourceDumpError(
            f"embedded file count mismatch: got {len(entries)}, expected {EXPECTED_FILES}"
        )
    cpp = sum(entry.relative_path.suffix.lower() == ".cpp" for entry in entries)
    headers = sum(entry.relative_path.suffix.lower() == ".h" for entry in entries)
    if (cpp, headers) != (EXPECTED_CPP, EXPECTED_H):
        raise SourceDumpError(
            f"extension counts mismatch: got cpp={cpp}, h={headers}; "
            f"expected cpp={EXPECTED_CPP}, h={EXPECTED_H}"
        )


def write_entries(entries: tuple[DumpEntry, ...], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    root = output.resolve()
    for entry in entries:
        target = (output / entry.relative_path).resolve()
        if root not in target.parents:
            raise SourceDumpError(f"refusing path outside output root: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(entry.content, encoding="utf-8", newline="")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="repositorio_completo_openholdem.txt")
    parser.add_argument("--out", type=Path, help="directory to reconstruct into")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--allow-unknown-hash",
        action="store_true",
        help="parse another compatible dump without asserting the canonical artifact hash",
    )
    args = parser.parse_args()

    data = args.source.read_bytes()
    text = data.decode("utf-8", errors="strict")
    entries = parse_dump_text(text)
    if not args.allow_unknown_hash:
        verify_known_dump(data, entries)

    cpp = sum(entry.relative_path.suffix.lower() == ".cpp" for entry in entries)
    headers = sum(entry.relative_path.suffix.lower() == ".h" for entry in entries)
    print(f"SHA256={sha256_bytes(data)}")
    print(f"bytes={len(data)} files={len(entries)} cpp={cpp} h={headers}")

    if args.verify_only:
        return
    if args.out is None:
        raise SystemExit("--out is required unless --verify-only is used")
    write_entries(entries, args.out)
    print(f"extracted_to={args.out.resolve()}")


if __name__ == "__main__":
    main()
