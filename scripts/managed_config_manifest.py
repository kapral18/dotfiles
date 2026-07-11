#!/usr/bin/env python3
"""Atomically record or forget literal paths in managed_configs.tsv.

Usage: managed_config_manifest.py record|forget <manifest_path> <target_path>
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _validate_target(target: str) -> None:
    if not target:
        raise ValueError("target path must not be empty")
    if any(separator in target for separator in ("\t", "\n", "\r")):
        raise ValueError("target path must not contain tab or newline characters")


def _matches_target(line: bytes, target: bytes) -> bool:
    return line.split(b"\t", 1)[0] == target


def _atomic_replace(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f"{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise


def record_checksum(manifest: Path, target: Path) -> bool:
    target_text = os.fspath(target)
    _validate_target(target_text)
    if not target.is_file():
        return False

    target_bytes = os.fsencode(target_text)
    checksum = hashlib.sha256(target.read_bytes()).hexdigest().encode("ascii")
    existing = manifest.read_bytes() if manifest.is_file() else b""
    lines = existing.splitlines(keepends=True)
    matching = [line for line in lines if _matches_target(line, target_bytes)]
    if len(matching) == 1:
        fields = matching[0].rstrip(b"\r\n").split(b"\t")
        if len(fields) >= 2 and fields[1] == checksum:
            return False

    retained = b"".join(line for line in lines if not _matches_target(line, target_bytes))
    if retained and not retained.endswith((b"\n", b"\r")):
        retained += b"\n"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ").encode("ascii")
    _atomic_replace(manifest, retained + target_bytes + b"\t" + checksum + b"\t" + timestamp + b"\n")
    return True


def forget_checksum(manifest: Path, target: str) -> bool:
    _validate_target(target)
    if not manifest.is_file():
        return False

    target_bytes = os.fsencode(target)
    existing = manifest.read_bytes()
    lines = existing.splitlines(keepends=True)
    if not any(_matches_target(line, target_bytes) for line in lines):
        return False

    retained = b"".join(line for line in lines if not _matches_target(line, target_bytes))
    _atomic_replace(manifest, retained)
    return True


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] not in {"record", "forget"}:
        print("Usage: managed_config_manifest.py record|forget <manifest_path> <target_path>", file=sys.stderr)
        return 2

    operation, manifest_raw, target_raw = sys.argv[1:]
    try:
        _validate_target(target_raw)
        if operation == "record":
            record_checksum(Path(manifest_raw), Path(target_raw))
        else:
            forget_checksum(Path(manifest_raw), target_raw)
    except (OSError, ValueError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
