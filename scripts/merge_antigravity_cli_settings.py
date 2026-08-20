#!/usr/bin/env python3
"""Reconcile live Antigravity CLI settings with declared policy.

Usage: merge_antigravity_cli_settings.py <live_json> <policy_json>

Declared values win recursively while undeclared live values survive.
Top-level ``gcp`` is always removed so apply cannot leave a Vertex pin.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any


def _merge_declared_over_live(live: object, policy: object) -> object:
    if not isinstance(live, dict) or not isinstance(policy, dict):
        return copy.deepcopy(policy)

    merged = copy.deepcopy(live)
    for key, declared_value in policy.items():
        if key in live:
            merged[key] = _merge_declared_over_live(live[key], declared_value)
        else:
            merged[key] = copy.deepcopy(declared_value)
    return merged


def merge_antigravity_cli_settings(live: object, policy: object) -> dict[str, Any]:
    if not isinstance(live, dict):
        raise ValueError("live settings root must be an object")
    if not isinstance(policy, dict):
        raise ValueError("policy settings root must be an object")
    merged = _merge_declared_over_live(live, policy)
    assert isinstance(merged, dict)
    merged.pop("gcp", None)
    return merged


def _load_json(path: Path, label: str, *, missing_ok: bool) -> object:
    if missing_ok and not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as err:
        raise ValueError(f"{label} settings could not be read: {err.strerror or 'I/O error'}") from err
    except json.JSONDecodeError as err:
        raise ValueError(f"{label} settings are not valid JSON at line {err.lineno}, column {err.colno}") from err


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2

    try:
        live = _load_json(Path(sys.argv[1]), "live", missing_ok=True)
        policy = _load_json(Path(sys.argv[2]), "policy", missing_ok=False)
        merged = merge_antigravity_cli_settings(live, policy)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print(json.dumps(merged, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
