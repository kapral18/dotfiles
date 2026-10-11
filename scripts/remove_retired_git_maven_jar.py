#!/usr/bin/env python3
"""Remove launchers left by the retired git_maven_jar custom-package format.

Usage:
    remove_retired_git_maven_jar.py <state_file>

The state file is TSV: output_name<TAB>launcher_path<TAB>repo_dir.
Launchers are deleted. Repo checkouts may hold unpushed commits, stashes, or
linked worktrees, so they are only reported. The state file, and its directory
when empty, are removed afterwards. A missing state file is a no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path


def remove_retired(state_file: Path) -> list[str]:
    """Delete listed launchers and the state file; return messages to print."""
    if not state_file.is_file():
        return []
    messages: list[str] = []
    for line in state_file.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) != 3 or not fields[0]:
            continue
        name, launcher, repo = fields
        launcher_path = Path(launcher)
        if launcher and (launcher_path.is_file() or launcher_path.is_symlink()):
            launcher_path.unlink()
            messages.append(f"Removed retired launcher for {name}: {launcher}")
        if repo and Path(repo).is_dir():
            messages.append(f"Retired source checkout left in place; remove it when no longer needed: {repo}")
    state_file.unlink()
    try:
        state_file.parent.rmdir()
    except OSError:
        pass
    return messages


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: remove_retired_git_maven_jar.py <state_file>", file=sys.stderr)
        return 1
    for message in remove_retired(Path(sys.argv[1])):
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
