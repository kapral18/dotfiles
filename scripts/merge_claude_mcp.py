#!/usr/bin/env python3
"""Replace declared MCP servers while preserving valid Claude runtime settings."""

import json
import sys
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


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: merge_claude_mcp.py <src_path> <target_path>")

    src_path, target_path = map(Path, sys.argv[1:])
    desired = _load_config(src_path, "desired").get("mcpServers", {})
    missing = False
    try:
        data = _load_config(target_path, "live")
    except FileNotFoundError:
        data, missing = {}, True

    current = data.get("mcpServers", {})
    if current == desired and not missing:
        sys.exit(0)

    data["mcpServers"] = desired
    with open(target_path, "w") as f:
        f.write(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as err:
        sys.exit(f"Error: {err}")
