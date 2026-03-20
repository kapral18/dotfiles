#!/usr/bin/env python3
"""Shared display-name formatting for LiteLLM model entries."""

from __future__ import annotations


def format_display_name(m: dict) -> str:
    """Build a human-readable display name from a LiteLLM model dict.

    Format: ``<name> [reasoning-emoji] [(cost)] (LiteLLM)``
    """
    name = m.get("name", m["id"])

    if m.get("reasoning"):
        name += " \U0001f9e0"

    if "cost" in m:
        c = m["cost"]
        in_cost = f"{c['input']:g}" if isinstance(c["input"], float) else c["input"]
        out_cost = f"{c['output']:g}" if isinstance(c["output"], float) else c["output"]
        name += f" (${in_cost}in/${out_cost}out)"

    return name
