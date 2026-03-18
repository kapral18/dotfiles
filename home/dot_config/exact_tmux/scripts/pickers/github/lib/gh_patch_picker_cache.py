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
import os
import sys
import tempfile
from pathlib import Path

RESET_SPACE = "\x1b[0m "
MARK = "◆"
MARK_COLORED = "\x1b[38;5;81m◆\x1b[0m"


def patch_display(display: str) -> str:
    pos = display.find(RESET_SPACE)
    if pos < 0:
        return display
    idx = pos + len(RESET_SPACE)
    if idx >= len(display):
        return display
    # If the marker is already rendered via ANSI, do nothing.
    if display[idx : idx + 2] == "\x1b[":
        return display
    # If a previous patch wrote the raw marker, upgrade it to the colored marker.
    if display[idx] == MARK:
        return display[:idx] + MARK_COLORED + display[idx + 1 :]
    # Only patch the expected spacer (a single literal space).
    if display[idx] != " ":
        return display
    return display[:idx] + MARK_COLORED + display[idx + 1 :]


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
            tmp_name = ""
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    delete=False,
                    dir=str(cache.parent),
                    prefix=f".{cache.name}.",
                    suffix=".tmp",
                ) as f:
                    tmp_name = f.name
                    f.write("".join(out))
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_name, str(cache))
                tmp_name = ""
            finally:
                if tmp_name:
                    try:
                        os.unlink(tmp_name)
                    except Exception:
                        pass
        except Exception:
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
