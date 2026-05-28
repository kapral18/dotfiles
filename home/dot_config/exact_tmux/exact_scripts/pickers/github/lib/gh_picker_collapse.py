#!/usr/bin/env python3
"""Manage the GitHub picker collapse-state file.

Subcommands:
    toggle <state_path> <parent_id>
        Add or remove a single parent_id from the collapse set. Used by the
        `alt-z` binding: caller resolves the cursor row's parent identity
        first, then invokes this verb with the resulting `kind:repo:num`
        string.

    global-toggle <state_path> <rendered_tsv_path>
        If any parent in the rendered TSV is currently collapsed, expand
        everything. Otherwise collapse every parent that has at least one
        child in the rendered TSV. This matches the user-facing `alt-Z`
        behaviour: one press collapses everything you can see; a second
        press expands it all again.

Both subcommands persist the resulting set back to `state_path` (one
parent_id per line, ASCII-sorted for stability). They print nothing on
stdout — the caller is responsible for triggering an fzf reload via
`gh_items.sh --cache-only` so the new state is reflected.
"""

from __future__ import annotations

import sys
from pathlib import Path

_COL_KIND = 1
_COL_REPO = 2
_COL_NUM = 3
_COL_PARENT_ID = 11
_COL_TREE_ROLE = 12


def _read_set(path: Path) -> set[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return set()
    out: set[str] = set()
    for line in raw.splitlines():
        tok = line.strip()
        if not tok or tok.startswith("#"):
            continue
        out.add(tok)
    return out


def _write_set(path: Path, members: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(sorted(members))
    if content:
        content += "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def cmd_toggle(state_path: str, parent_id: str) -> int:
    if not parent_id:
        return 0
    p = Path(state_path)
    current = _read_set(p)
    if parent_id in current:
        current.discard(parent_id)
    else:
        current.add(parent_id)
    _write_set(p, current)
    return 0


def cmd_global_toggle(state_path: str, rendered_tsv_path: str) -> int:
    rendered = Path(rendered_tsv_path)
    try:
        text = rendered.read_text(encoding="utf-8")
    except Exception:
        return 0
    parents: set[str] = set()
    parents_with_children: set[str] = set()
    parent_ids_in_view: set[str] = set()
    for line in text.splitlines():
        parts = line.split("\t")
        role = parts[_COL_TREE_ROLE] if len(parts) > _COL_TREE_ROLE else ""
        if role == "parent" and len(parts) > _COL_NUM:
            kind = parts[_COL_KIND]
            repo = parts[_COL_REPO]
            num = parts[_COL_NUM]
            if kind and repo and num and kind != "header":
                parents.add(f"{kind}:{repo}:{num}")
        elif role == "child" and len(parts) > _COL_PARENT_ID:
            pid = parts[_COL_PARENT_ID]
            if pid:
                parent_ids_in_view.add(pid)
                parents_with_children.add(pid)

    # Phase E behavior: if anything in the view is collapsed (which means we
    # don't see those children) OR if any parent on screen is currently in the
    # collapse set, treat the global toggle as expand-all. Otherwise collapse
    # every visible family.
    p = Path(state_path)
    current = _read_set(p)
    if current & parents:
        # Something visible is collapsed → expand everything.
        new = current - parents
    elif parents_with_children:
        new = current | parents_with_children
    else:
        # Nothing to collapse and nothing currently collapsed.
        return 0
    _write_set(p, new)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        return 1
    verb = sys.argv[1]
    if verb == "toggle" and len(sys.argv) == 4:
        return cmd_toggle(sys.argv[2], sys.argv[3])
    if verb == "global-toggle" and len(sys.argv) == 4:
        return cmd_global_toggle(sys.argv[2], sys.argv[3])
    return 1


if __name__ == "__main__":
    sys.exit(main())
