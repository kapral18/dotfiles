#!/usr/bin/env python3
"""tmux status-right fragment for ,palantir.

Prints a terse segment (empty when no legions exist) so the statusline stays
clean on machines that never summoned anything:

    P:2 H:1 C:1   (in-flight / holding / cleared_for_human counts)
"""

from __future__ import annotations

import sys

import legion_state


def fragment() -> str:
    state = legion_state.LegionState()
    rows = state.summaries()
    if not rows:
        return ""
    active = sum(1 for r in rows if r.get("stage") not in ("banished", "cleared_for_human", "holding", "corrupt"))
    holding = sum(1 for r in rows if r.get("stage") == "holding")
    cleared = sum(1 for r in rows if r.get("stage") == "cleared_for_human")
    if not (active or holding or cleared):
        return ""
    parts = []
    if active:
        parts.append(f"P:{active}")
    if holding:
        parts.append(f"H:{holding}")
    if cleared:
        parts.append(f"C:{cleared}")
    return " ".join(parts)


if __name__ == "__main__":
    out = fragment()
    if out:
        print(out)
    sys.exit(0)
