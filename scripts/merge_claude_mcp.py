#!/usr/bin/env python3
"""Replace declared MCP servers while preserving valid Claude runtime settings."""

import json
import os
import sys
import tempfile
from pathlib import Path


def _load_config(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise ValueError(f"{label} config is not valid JSON at line {err.lineno}, column {err.colno}") from err
    if not isinstance(data, dict):
        raise ValueError(f"{label} config root must be an object")
    if not isinstance(data.get("mcpServers", {}), dict):
        raise ValueError(f"{label} mcpServers must be an object")
    return data


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
        sys.exit("Usage: merge_claude_mcp.py <src_path> <target_path>")

    src_path, target_path = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    desired = _load_config(src_path, "desired").get("mcpServers", {})
    missing = False
    try:
        data = _load_config(target_path, "live")
        mode = target_path.stat().st_mode & 0o777
    except FileNotFoundError:
        data, missing, mode = {}, True, 0o600

    current = data.get("mcpServers", {})
    if current == desired and not missing:
        sys.exit(0)

    data["mcpServers"] = desired
    _replace(target_path, json.dumps(data, indent=2) + "\n", mode)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as err:
        sys.exit(f"Error: {err}")
