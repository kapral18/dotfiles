#!/usr/bin/env python3
"""Set declared top-level keys in Claude Code's ~/.claude.json while preserving its runtime state."""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

DATA_KEY = "claude_global_config"
# The hook pastes keys unquoted into a bash array, and the ledger reads dots as nesting.
KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _load_config(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise ValueError(f"{label} config is not valid JSON at line {err.lineno}, column {err.colno}") from err
    if not isinstance(data, dict):
        raise ValueError(f"{label} config root must be an object")
    return data


def _canonical(value: object) -> str:
    # JSON-typed comparison: Python's False == 0 must still count as drift.
    return json.dumps(value, sort_keys=True)


def _replace(target: Path, text: str, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: merge_claude_global_config.py <desired_path> <target_path>")

    desired_path, target_path = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    desired = _load_config(desired_path, "desired").get(DATA_KEY)
    if not isinstance(desired, dict) or not desired:
        raise ValueError(f"desired {DATA_KEY} must be a non-empty object")
    invalid = sorted(key for key in desired if not KEY_RE.fullmatch(key))
    if invalid:
        raise ValueError(f"desired {DATA_KEY} keys must be identifiers: {', '.join(map(repr, invalid))}")
    try:
        data = _load_config(target_path, "live")
        mode = target_path.stat().st_mode & 0o777
    except FileNotFoundError:
        data, mode = None, 0o600

    if data is not None and all(key in data and _canonical(data[key]) == _canonical(v) for key, v in desired.items()):
        return

    merged = {**(data or {}), **desired}
    # Default ensure_ascii escapes lone surrogates a cut emoji can leave; UTF-8 cannot encode them.
    _replace(target_path, json.dumps(merged, indent=2) + "\n", mode)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as err:
        sys.exit(f"Error: {err}")
