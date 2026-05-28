#!/usr/bin/env python3
"""Compute fzf actions to toggle every row in the cursor's family.

Reads the rendered picker TSV from stdin (one row per line, post filter and
sort). Prints a single fzf action expression to stdout that:

  - For every row in the family, emits `pos(R)+toggle`.
  - Ends with `pos(<cursor>)` so the visible cursor returns to the original
    position when the operator releases the keybinding.

Family rules:

  - Cursor on a parent row (`tree_role=parent`): family is the parent itself
    plus every immediately-following row whose `parent_id` matches the
    parent's `kind:repo:num` identity.
  - Cursor on a child row (`tree_role=child`): family is the parent row
    (walked backwards) plus every consecutive sibling whose `parent_id`
    matches the child's.
  - Cursor on a loose row, section header, or backport-missing placeholder:
    no family; the script exits with no output.

Empty output means "no actions" — fzf treats that as a no-op.

Usage:
    gh_picker_mark_subtree.py <cursor_row_1_indexed>

The cursor row is 1-indexed to match `FZF_POS`. Stdin must be the same
content that fzf is currently displaying (`gh_items.sh --cache-only` output).
"""

from __future__ import annotations

import sys

_COL_KIND = 1
_COL_REPO = 2
_COL_NUM = 3
_COL_PARENT_ID = 11
_COL_TREE_ROLE = 12


def _identity(parts: list[str]) -> str:
    if len(parts) <= _COL_NUM:
        return ""
    kind = parts[_COL_KIND]
    repo = parts[_COL_REPO]
    num = parts[_COL_NUM]
    if not kind or not repo or not num or kind == "header":
        return ""
    return f"{kind}:{repo}:{num}"


def _role(parts: list[str]) -> str:
    return parts[_COL_TREE_ROLE] if len(parts) > _COL_TREE_ROLE else ""


def _parent_ref(parts: list[str]) -> str:
    return parts[_COL_PARENT_ID] if len(parts) > _COL_PARENT_ID else ""


def main() -> int:
    if len(sys.argv) != 2:
        return 1
    try:
        cursor = int(sys.argv[1])
    except ValueError:
        return 1
    if cursor < 1:
        return 0

    lines = sys.stdin.read().splitlines()
    if cursor > len(lines):
        return 0

    cursor_parts = lines[cursor - 1].split("\t")
    role = _role(cursor_parts)

    family_rows: list[int] = []

    if role == "parent":
        parent_identity = _identity(cursor_parts)
        if not parent_identity:
            return 0
        family_rows.append(cursor)
        for i in range(cursor, len(lines)):
            parts = lines[i].split("\t")
            if _role(parts) == "child" and _parent_ref(parts) == parent_identity:
                family_rows.append(i + 1)
            else:
                break

    elif role == "child":
        parent_identity = _parent_ref(cursor_parts)
        if not parent_identity:
            return 0
        parent_row = None
        for i in range(cursor - 2, -1, -1):  # cursor-2 = row above cursor (0-indexed)
            parts = lines[i].split("\t")
            this_role = _role(parts)
            if this_role == "parent" and _identity(parts) == parent_identity:
                parent_row = i + 1
                break
            if this_role == "child" and _parent_ref(parts) == parent_identity:
                continue
            break
        if parent_row is None:
            return 0
        family_rows.append(parent_row)
        for i in range(parent_row, len(lines)):
            parts = lines[i].split("\t")
            if _role(parts) == "child" and _parent_ref(parts) == parent_identity:
                family_rows.append(i + 1)
            else:
                break
    else:
        return 0

    if not family_rows:
        return 0

    actions = [f"pos({row})+toggle" for row in family_rows]
    actions.append(f"pos({cursor})")
    sys.stdout.write("+".join(actions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
