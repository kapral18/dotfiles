#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def git(root: Path, *args: str, patch: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], input=patch, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def capture(root: Path) -> tuple[bytes, bytes, bytes, bytes, bytes]:
    options = ["--binary", "--full-index", "--no-ext-diff", "--no-textconv", "--no-renames"]
    return (
        git(root, "rev-parse", "HEAD"),
        git(root, "diff", "--cached", *options),
        git(root, "diff", *options),
        git(root, "diff", "HEAD", *options),
        git(root, "diff", "--cached", "--ita-visible-in-index", *options),
    )


def apply(root: Path, patch: bytes, *options: str) -> None:
    if patch:
        git(root, "apply", "--whitespace=nowarn", *options, "-", patch=patch)


def transfer(source: Path, target: Path) -> None:
    if source == target:
        raise RuntimeError("source and target are the same worktree")
    if git(source, "ls-files", "-u") or git(target, "ls-files", "-u"):
        raise RuntimeError("resolve unmerged index entries before transferring changes")
    snapshot = capture(source)
    _, staged, unstaged, combined, source_index = snapshot
    if not staged and not unstaged:
        return
    backup = Path(tempfile.mkdtemp(prefix="git-wtgrab-"))
    for name, patch in (
        ("staged.patch", staged),
        ("unstaged.patch", unstaged),
        ("combined.patch", combined),
        ("source-index.patch", source_index),
    ):
        (backup / name).write_bytes(patch)
    keep_backup = False
    try:
        apply(target, staged, "--index")
        try:
            apply(target, unstaged, "--intent-to-add")
        except RuntimeError:
            try:
                apply(target, staged, "--reverse", "--index")
            except RuntimeError as error:
                keep_backup = True
                raise RuntimeError(f"target rollback failed; recovery patches: {backup}; {error}") from error
            raise
        if capture(source) != snapshot:
            keep_backup = True
            raise RuntimeError(
                f"source changed during transfer; source was left intact, target has the copy; patches: {backup}"
            )
        try:
            apply(source, combined, "--reverse", "--check")
            apply(source, source_index, "--reverse", "--cached", "--check")
            apply(source, combined, "--reverse")
            try:
                apply(source, source_index, "--reverse", "--cached")
            except RuntimeError:
                apply(source, combined)
                raise
        except RuntimeError as error:
            keep_backup = True
            raise RuntimeError(
                f"source cleanup failed; target has the copy; recovery patches: {backup}; {error}"
            ) from error
    finally:
        if not keep_backup:
            shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser(prog="git wtgrab")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    try:
        source = Path(git(args.source, "rev-parse", "--show-toplevel").decode().rstrip("\n")).resolve()
        target = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().rstrip("\n")).resolve()
        transfer(source, target)
    except (OSError, RuntimeError) as error:
        print(f"git wtgrab: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
