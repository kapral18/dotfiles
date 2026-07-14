#!/usr/bin/env python3
"""tmux status-right fragment for ,palantir.

Prints a terse segment (empty when no legions exist) so the statusline stays
clean on machines that never summoned anything:

    P:2 H:1 C:1 O:1 E:1

P/H/C are in-flight, holding, and cleared-for-human counts. O surfaces a
terminal legion whose teardown is absent/incomplete; E surfaces corrupt state.
"""

from __future__ import annotations

import sys

import legion_state
import machine

ACTIVE_STAGES = frozenset(machine.STAGES) - machine.TERMINAL_STAGES - machine.ATTENTION_STAGES


def fragment() -> str:
    state = legion_state.LegionState()
    rows = state.summaries()
    if not rows:
        return ""
    active = sum(1 for r in rows if r.get("stage") in ACTIVE_STAGES)
    holding = sum(1 for r in rows if r.get("stage") == "holding")
    cleared = sum(1 for r in rows if r.get("stage") == "cleared_for_human")
    orphaned = sum(1 for r in rows if r.get("stage") == "banished" and r.get("teardown_status") != "complete")
    corrupt = sum(1 for r in rows if r.get("stage") == "corrupt")
    if not (active or holding or cleared or orphaned or corrupt):
        return ""
    parts = []
    if active:
        parts.append(f"P:{active}")
    if holding:
        parts.append(f"H:{holding}")
    if cleared:
        parts.append(f"C:{cleared}")
    if orphaned:
        parts.append(f"O:{orphaned}")
    if corrupt:
        parts.append(f"E:{corrupt}")
    return " ".join(parts)


if __name__ == "__main__":
    out = fragment()
    if out:
        print(out)
    sys.exit(0)
