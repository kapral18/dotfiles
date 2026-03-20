#!/usr/bin/env python3
"""Minimal YAML parser for this project's data files.

Handles the specific list-of-dicts structure used by mcp_servers.yaml and
litellm_models.yaml.  Intentionally avoids external dependencies (no PyYAML).

Supported subset:
  - Top-level key followed by a list of dicts (sequence of mappings)
  - Scalar values: bool, int, float, single/double-quoted strings, bare strings
  - One level of nested dicts (key with empty value followed by indented k/v pairs)
  - Sequence values (key followed by indented ``- value`` items)
  - Comments and blank lines are ignored
"""

from __future__ import annotations


def parse_scalar(raw: str):
    """Parse a YAML scalar value into a Python type."""
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
    try:
        return float(raw)
    except ValueError:
        pass
    return raw
