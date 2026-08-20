#!/usr/bin/env python3
"""Reconcile Antigravity MCP servers with runtime-managed entries.

Usage:
    merge_antigravity_mcp.py <live_json> <desired_json> <previous_desired_json>

Previously declared server names are removed before the current declaration is
applied. Undeclared live servers and top-level runtime state survive.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any


def _load_config(path: Path, label: str, *, missing_ok: bool) -> dict[str, Any]:
    if missing_ok and not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as err:
        raise ValueError(f"{label} config could not be read: {err.strerror or 'I/O error'}") from err
    except json.JSONDecodeError as err:
        raise ValueError(f"{label} config is not valid JSON at line {err.lineno}, column {err.colno}") from err
    if not isinstance(value, dict):
        raise ValueError(f"{label} config root must be an object")
    servers = value.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"{label} mcpServers must be an object")
    return value


def merge_antigravity_mcp(
    live: dict[str, Any],
    desired: dict[str, Any],
    previous_desired: dict[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(live)
    live_servers = merged.setdefault("mcpServers", {})
    desired_servers = desired.get("mcpServers", {})
    previous_servers = previous_desired.get("mcpServers", {})
    if not isinstance(live_servers, dict):
        raise ValueError("live mcpServers must be an object")
    if not isinstance(desired_servers, dict):
        raise ValueError("desired mcpServers must be an object")
    if not isinstance(previous_servers, dict):
        raise ValueError("previous desired mcpServers must be an object")

    for name in previous_servers:
        live_servers.pop(name, None)
    live_servers.update(copy.deepcopy(desired_servers))
    return merged


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2

    try:
        live = _load_config(Path(sys.argv[1]), "live", missing_ok=True)
        desired = _load_config(Path(sys.argv[2]), "desired", missing_ok=False)
        previous = _load_config(Path(sys.argv[3]), "previous desired", missing_ok=True)
        merged = merge_antigravity_mcp(live, desired, previous)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print(json.dumps(merged, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
