"""Refuse implicit deletion of independent submodule history."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def git(path: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
    ).stdout


def require_no_nested_git(path: Path, all_worktrees: bool) -> None:
    checkouts = [path]
    if all_worktrees:
        records = git(path, "worktree", "list", "--porcelain", "-z").split(b"\0")
        checkouts = [Path(os.fsdecode(record[9:])) for record in records if record.startswith(b"worktree ")]
        if not checkouts:
            raise ValueError("cannot identify repository worktrees")
    for checkout in checkouts:
        records = git(checkout, "ls-files", "--stage", "-z").split(b"\0")
        if any(record.startswith(b"160000 ") for record in records):
            raise ValueError(f"registered submodule gitlinks in {checkout} require --force")
    admin = Path(os.fsdecode(git(path, "rev-parse", "--absolute-git-dir").removesuffix(b"\n")))
    stores = [admin / "modules"]
    if all_worktrees:
        common = Path(
            os.fsdecode(git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").removesuffix(b"\n"))
        )
        stores.append(common / "modules")
        worktrees = common / "worktrees"
        if worktrees.exists():
            stores.extend(entry / "modules" for entry in worktrees.iterdir() if entry.is_dir())
    for store in stores:
        if store.exists() and any(store.iterdir()):
            raise ValueError(f"submodule history at {store} requires --force")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--all-worktrees", action="store_true")
    args = parser.parse_args()
    try:
        require_no_nested_git(args.path, args.all_worktrees)
    except (OSError, UnicodeError, subprocess.SubprocessError, ValueError) as error:
        print(f"Refusing removal of {args.path}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
