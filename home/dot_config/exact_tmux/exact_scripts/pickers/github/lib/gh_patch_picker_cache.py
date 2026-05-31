#!/usr/bin/env python3
"""Patch gh_picker cache TSV to mark items as having local worktrees.

The GitHub picker renders items from a cached TSV file:
  ~/.cache/tmux/gh_picker_<mode>.tsv

The first column is an ANSI-colored display string laid out as:

    [tree-prefix] <state-icon> <local-marker> <review> <ci> ...

The local-worktree marker is the cell immediately after the *state icon*, i.e.
after the first reset+space ("\x1b[0m ") that is NOT part of an optional leading
tree prefix. Child rows (sub-issues in an epic, PRs in a family) render with a
dim tree prefix ("\x1b[2;...m├─\x1b[0m ") that also ends in reset+space, so we
must skip it before anchoring — otherwise the marker would overwrite the state
icon (the issue open/closed glyph) instead of the worktree column.

This script sets that marker for matching (kind, repo, num) tuples to one of:
  - done    -> '◆' (blue): worktree created locally
  - loading -> '◌' (amber): creation in progress (progressive feedback)
  - clear   -> ' ': no local worktree (revert a loading marker on skip/fail)

It does not attempt to re-compute anything from GitHub or git; it's a cheap
local UI patch to enable progressive feedback during background worktree
creation.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

RESET_SPACE = "\x1b[0m "
MARK_DONE = "\x1b[38;5;81m◆\x1b[0m"
MARK_LOADING = "\x1b[38;5;221m◌\x1b[0m"
MARK_CLEAR = " "

STATE_MARKERS = {"done": MARK_DONE, "loading": MARK_LOADING, "clear": MARK_CLEAR}

# The marker cell is exactly one of:
#   a single literal space (no worktree), or
#   a colored SGR glyph: ESC[<code>m <glyph> ESC[0m
# Match whichever form is present so any state can transition to any other
# while preserving column alignment (always one visible glyph wide).
_MARKER_CELL = re.compile(r"\x1b\[[0-9;]*m.\x1b\[0m| ")

# Optional leading tree prefix for child rows: a dim SGR token ("2;...") wrapping
# the tree glyph, followed by reset+space, e.g. "\x1b[2;38;5;244m├─\x1b[0m ".
# The state icon that follows is a non-dim SGR token, so the dim "2;" prefix is
# what distinguishes a tree prefix from the state icon.
_TREE_PREFIX = re.compile(r"\x1b\[2;[0-9;]*m.*?\x1b\[0m ")


def patch_display(display: str, marker: str) -> str:
    # Skip an optional leading tree prefix so we anchor on the state icon's
    # reset+space, not the tree glyph's (which would clobber the state icon).
    search_from = 0
    tp = _TREE_PREFIX.match(display)
    if tp:
        search_from = tp.end()
    pos = display.find(RESET_SPACE, search_from)
    if pos < 0:
        return display
    idx = pos + len(RESET_SPACE)
    if idx >= len(display):
        return display
    m = _MARKER_CELL.match(display, idx)
    if not m:
        return display
    if m.group(0) == marker:
        return display
    return display[:idx] + marker + display[m.end() :]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cache-file", required=True)
    p.add_argument("--kind", required=True, choices=["pr", "issue"])
    p.add_argument("--repo", required=True)
    p.add_argument("--num", required=True)
    p.add_argument("--state", choices=list(STATE_MARKERS), default="done")
    args = p.parse_args()

    marker = STATE_MARKERS[args.state]

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
            new_display = patch_display(display, marker)
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
