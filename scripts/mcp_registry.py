#!/usr/bin/env python3
"""Utilities for reading the canonical MCP registry.

The source of truth for MCP servers lives in:
  home/.chezmoidata/mcp_servers.yaml

This module intentionally avoids external dependencies (no PyYAML).
"""

from __future__ import annotations

import re
from typing import Any


def _parse_scalar(raw: str):
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1].replace('\\"', '"')
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    if raw == "true":
        return True
    if raw == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    return raw


def load_servers(path: str, is_work: bool) -> dict[str, dict[str, Any]]:
    """Load servers from the canonical YAML registry.

    Returns mapping:
      name -> { "command": str, "args": list[str] }
    """
    with open(path, "r") as f:
        lines = f.readlines()

    servers: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_args = False
    args_indent = 0

    for line in lines:
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if stripped.lstrip() == "mcp_servers:":
            continue

        indent = len(line) - len(line.lstrip())

        new_entry = re.match(r"^\s+-\s+(\w[\w_]*):\s*(.*)", stripped)
        if new_entry:
            in_args = False
            current = {"name": None, "work_only": False, "command": None, "args": []}
            servers.append(current)
            key, val = new_entry.group(1), new_entry.group(2).strip()
            current[key] = _parse_scalar(val)
            continue

        if in_args and current is not None:
            item = re.match(r"^\s+-\s+(.*)", stripped)
            if item and indent >= args_indent:
                current["args"].append(_parse_scalar(item.group(1)))
                continue
            else:
                in_args = False

        kv = re.match(r"^\s+(\w[\w_]*):\s*(.*)", stripped)
        if kv and current is not None:
            key, val = kv.group(1), kv.group(2).strip()
            if key == "args" and not val:
                in_args = True
                args_indent = indent + 2
            else:
                current[key] = _parse_scalar(val)

    result: dict[str, dict[str, Any]] = {}
    for s in servers:
        if s.get("work_only") and not is_work:
            continue
        result[s["name"]] = {"command": s["command"], "args": s["args"]}
    return result
