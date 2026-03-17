#!/usr/bin/env python3
"""Patch gh_picker cache TSV to mark items as having local worktrees.

The GitHub picker renders items from a cached TSV file:
  ~/.cache/tmux/gh_picker_<mode>.tsv

The first column is an ANSI-colored display string. The local-worktree marker
is the character immediately after the first literal space following the first
ANSI reset token ("\x1b[0m ").

This script flips that marker to '◆' for matching (kind, repo, num) tuples.
It does not attempt to re-compute anything from GitHub or git; it's a cheap
local UI patch to enable progressive feedback during background worktree
creation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RESET_SPACE = "\x1b[0m "
MARK = "◆"


def patch_display(display: str) -> str:
    pos = display.find(RESET_SPACE)
    if pos < 0:
        return display
    idx = pos + len(RESET_SPACE)
    if idx >= len(display):
        return display
    if display[idx] == MARK:
        return display
    return display[:idx] + MARK + display[idx + 1 :]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cache-file", required=True)
    p.add_argument("--kind", required=True, choices=["pr", "issue"])
    p.add_argument("--repo", required=True)
    p.add_argument("--num", required=True)
    args = p.parse_args()

    cache = Path(args.cache_file)
    if not cache.exists():
        return 0

    try:
        lines = cache.read_text(encoding="utf-8", errors="replace").splitlines(True)
    except Exception:
        return 0

    out: list[str] = []
    changed = False
    for line in lines:
        if "\t" not in line:
            out.append(line)
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            out.append(line)
            continue
        display, kind, repo, num = parts[0], parts[1], parts[2], parts[3]
        if kind == args.kind and repo == args.repo and num == args.num:
            new_display = patch_display(display)
            if new_display != display:
                parts[0] = new_display
                changed = True
            out.append("\t".join(parts) + "\n")
        else:
            out.append(line)

    if changed:
        try:
            cache.write_text("".join(out), encoding="utf-8")
        except Exception:
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
