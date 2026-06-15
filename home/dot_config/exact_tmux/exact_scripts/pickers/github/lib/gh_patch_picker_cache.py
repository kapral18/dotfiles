#!/usr/bin/env python3
"""Patch gh_picker cache TSV item markers.

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
  - loading -> '◌' (amber): row-scoped operation in progress
  - clear   -> ' ': no local worktree (revert a worktree loader on skip/fail)
  - restore -> the marker saved by --save-file before a transient loader

It does not attempt to re-compute anything from GitHub or git; it's a cheap
local UI patch to enable progressive feedback during background worktree
creation and transient per-row GitHub waits.
"""

from __future__ import annotations

import argparse
import json
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
RESTORE_STATE = "restore"

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


def marker_cell(display: str) -> tuple[int, int, str] | None:
    # Skip an optional leading tree prefix so we anchor on the state icon's
    # reset+space, not the tree glyph's (which would clobber the state icon).
    search_from = 0
    tp = _TREE_PREFIX.match(display)
    if tp:
        search_from = tp.end()
    pos = display.find(RESET_SPACE, search_from)
    if pos < 0:
        return None
    idx = pos + len(RESET_SPACE)
    if idx >= len(display):
        return None
    m = _MARKER_CELL.match(display, idx)
    if not m:
        return None
    return idx, m.end(), m.group(0)


def patch_display(display: str, marker: str, *, loading_only: bool = False) -> str:
    cell = marker_cell(display)
    if cell is None:
        return display
    start, end, current = cell
    if loading_only and current != MARK_LOADING:
        return display
    if current == marker:
        return display
    return display[:start] + marker + display[end:]


def restore_key(kind: str, repo: str, num: str) -> str:
    return "\t".join((kind, repo, num))


def read_restore_file(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def write_restore_file(path: str, data: dict[str, str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=str(p.parent),
            prefix=f".{p.name}.",
            suffix=".tmp",
        ) as f:
            tmp_name = f.name
            json.dump(data, f, ensure_ascii=False, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(p))
        tmp_name = ""
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cache-file", required=True)
    p.add_argument("--kind", choices=["pr", "issue"])
    p.add_argument("--repo")
    p.add_argument("--num")
    p.add_argument("--all", action="store_true", help="patch every PR/issue row in the cache")
    p.add_argument("--state", choices=[*STATE_MARKERS, RESTORE_STATE], default="done")
    p.add_argument("--save-file", help="JSON file storing prior markers for transient restore")
    p.add_argument(
        "--restore-loading-only",
        action="store_true",
        help="for --state restore, only restore rows that still show the loading marker",
    )
    args = p.parse_args()

    if not args.all and not (args.kind and args.repo and args.num):
        p.error("--kind, --repo, and --num are required unless --all is used")

    restore = read_restore_file(args.save_file)
    restore_changed = False
    marker = STATE_MARKERS.get(args.state)

    cache = Path(args.cache_file)
    if not cache.exists():
        return 0

    try:
        lines = cache.read_text(encoding="utf-8", errors="replace").splitlines(True)
    except (OSError, UnicodeError):
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
        if kind in ("pr", "issue") and (args.all or (kind == args.kind and repo == args.repo and num == args.num)):
            key = restore_key(kind, repo, num)
            cell = marker_cell(display)
            if cell is None:
                out.append(line)
                continue
            if args.save_file and args.state != RESTORE_STATE and key not in restore:
                restore[key] = cell[2]
                restore_changed = True
            row_marker = marker
            if args.state == RESTORE_STATE:
                row_marker = restore.get(key)
                if row_marker is None:
                    out.append(line)
                    continue
            if row_marker is None:
                out.append(line)
                continue
            new_display = patch_display(
                display,
                row_marker,
                loading_only=bool(args.restore_loading_only and args.state == RESTORE_STATE),
            )
            if new_display != display:
                parts[0] = new_display
                changed = True
            out.append("\t".join(parts) + "\n")
        else:
            out.append(line)

    if restore_changed and args.save_file:
        try:
            write_restore_file(args.save_file, restore)
        except OSError:
            return 0

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
                    except OSError:
                        pass
        except OSError:
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
