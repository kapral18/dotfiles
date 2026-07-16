#!/usr/bin/env python3
"""tmux status-right fragment for ,palantir.

Prints a terse segment (empty when no legions exist) so the statusline stays
clean on machines that never summoned anything:

    P:2 H:1 C:1 T:1 O:1 U:1 E:1

P/H/C are in-flight, holding, and cleared-for-human counts. T surfaces an
in-flight legion whose coordinator transport is erroring. O surfaces a
terminal legion whose teardown is absent/incomplete; U one whose closeout
memory packet is still unrouted; E surfaces corrupt state.
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
    transport = sum(1 for r in rows if r.get("attention") == "transport")
    orphaned = sum(1 for r in rows if r.get("stage") == "banished" and r.get("teardown_status") != "complete")
    unrouted = sum(1 for r in rows if r.get("attention") == "unrouted")
    corrupt = sum(1 for r in rows if r.get("stage") == "corrupt")
    if not (active or holding or cleared or transport or orphaned or unrouted or corrupt):
        return ""
    parts = []
    if active:
        parts.append(f"P:{active}")
    if holding:
        parts.append(f"H:{holding}")
    if cleared:
        parts.append(f"C:{cleared}")
    if transport:
        parts.append(f"T:{transport}")
    if orphaned:
        parts.append(f"O:{orphaned}")
    if unrouted:
        parts.append(f"U:{unrouted}")
    if corrupt:
        parts.append(f"E:{corrupt}")
    return " ".join(parts)


if __name__ == "__main__":
    out = fragment()
    if out:
        print(out)
    sys.exit(0)
