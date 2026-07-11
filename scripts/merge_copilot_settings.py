#!/usr/bin/env python3
"""Reconcile live Copilot settings with the chezmoi-declared baseline.

Usage: merge_copilot_settings.py <live_json> <baseline_json>

Declared values win recursively while undeclared live values survive. The
declared ``subagents.agents`` mapping is source-owned and replaces the live map
exactly, removing stale agents and undeclared per-agent overrides.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any


def _validate_settings(live: object, baseline: object) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(live, dict):
        raise ValueError("live settings root must be an object")
    if not isinstance(baseline, dict):
        raise ValueError("baseline settings root must be an object")
    live_subagents = live.get("subagents", {})
    if not isinstance(live_subagents, dict):
        raise ValueError("live subagents must be an object")
    if "agents" in live_subagents and not isinstance(live_subagents["agents"], dict):
        raise ValueError("live subagents.agents must be an object")
    subagents = baseline.get("subagents")
    if not isinstance(subagents, dict):
        raise ValueError("baseline subagents must be an object")
    if not isinstance(subagents.get("agents"), dict):
        raise ValueError("baseline subagents.agents must be an object")
    return live, baseline


def _merge_declared_over_live(live: object, baseline: object) -> object:
    if not isinstance(live, dict) or not isinstance(baseline, dict):
        return copy.deepcopy(baseline)

    merged = copy.deepcopy(live)
    for key, declared_value in baseline.items():
        if key in live:
            merged[key] = _merge_declared_over_live(live[key], declared_value)
        else:
            merged[key] = copy.deepcopy(declared_value)
    return merged


def merge_copilot_settings(live: object, baseline: object) -> dict[str, Any]:
    live_settings, baseline_settings = _validate_settings(live, baseline)
    merged = _merge_declared_over_live(live_settings, baseline_settings)
    assert isinstance(merged, dict)
    merged_subagents = merged["subagents"]
    baseline_subagents = baseline_settings["subagents"]
    assert isinstance(merged_subagents, dict)
    assert isinstance(baseline_subagents, dict)
    merged_subagents["agents"] = copy.deepcopy(baseline_subagents["agents"])
    return merged


def _load_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as err:
        raise ValueError(f"{label} settings could not be read: {err.strerror or 'I/O error'}") from err
    except json.JSONDecodeError as err:
        raise ValueError(f"{label} settings are not valid JSON at line {err.lineno}, column {err.colno}") from err


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: merge_copilot_settings.py <live_json> <baseline_json>", file=sys.stderr)
        return 2

    try:
        live = _load_json(Path(sys.argv[1]), "live")
        baseline = _load_json(Path(sys.argv[2]), "baseline")
        merged = merge_copilot_settings(live, baseline)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print(json.dumps(merged, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
