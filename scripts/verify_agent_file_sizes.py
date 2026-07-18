#!/usr/bin/env python3
"""Verify agent skill reference markdown stays viewable in one read.

The strictest harness view tool truncates files larger than 20 KB (20480
bytes), so a skill's "load this reference" pointer to an oversized file breaks
mid-flow (observed live: `k-review/references/judging_core.md` failed to load
during an incident response). Every markdown file under
``home/exact_dot_agents/`` must stay under that bound; approaching it is a
sprawl signal — split or disclose sections behind pointers instead of trimming
qualifiers (see `k-writing-great-skills`).

``SKILL.md`` files are exempt: harnesses deliver them through their skill
loaders, not the size-capped view tool.

Usage:
    verify_agent_file_sizes.py [REPO_ROOT]

Exit status is non-zero when any non-``SKILL.md`` markdown file under
``home/exact_dot_agents/`` is 20480 bytes or larger.
"""

from __future__ import annotations

import sys
from pathlib import Path

MAX_BYTES = 20480
AGENT_TREE = Path("home/exact_dot_agents")
# chezmoi attribute prefixes that may precede the deployed basename.
NAME_PREFIXES = ("readonly_", "private_", "executable_")


def deployed_basename(path: Path) -> str:
    name = path.name
    for prefix in NAME_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix) :]
    return name


def oversized_files(repo_root: Path) -> list[tuple[Path, int]]:
    """Return (path, size) for every gated agent markdown file at/over the bound."""
    offenders: list[tuple[Path, int]] = []
    for path in sorted((repo_root / AGENT_TREE).rglob("*.md")):
        if deployed_basename(path) == "SKILL.md":
            continue
        size = path.stat().st_size
        if size >= MAX_BYTES:
            offenders.append((path.relative_to(repo_root), size))
    return offenders


def main(argv: list[str]) -> int:
    repo_root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    if not (repo_root / AGENT_TREE).is_dir():
        print(f"verify_agent_file_sizes: missing {AGENT_TREE} under {repo_root}", file=sys.stderr)
        return 1
    offenders = oversized_files(repo_root)
    if offenders:
        print(
            f"verify_agent_file_sizes: {len(offenders)} file(s) at/over {MAX_BYTES} bytes "
            "(harness view tools truncate them; split or disclose behind pointers):",
            file=sys.stderr,
        )
        for path, size in offenders:
            print(f"  {size:>6}  {path}", file=sys.stderr)
        return 1
    print(f"verify_agent_file_sizes: all agent markdown files under {MAX_BYTES} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
