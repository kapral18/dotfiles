#!/usr/bin/env python3
"""Reconcile source-installed custom package artifacts.

Usage:
    reconcile_custom_packages.py <state_file> <desired_file>

Files are TSV with 3 fields per line:
    output_name<TAB>binary_path<TAB>repo_dir
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def load_tsv(path: Path) -> dict[str, tuple[str, str]]:
    if not path.exists():
        return {}
    records: dict[str, tuple[str, str]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        output_name, binary_path, repo_dir = parts
        records[output_name] = (binary_path, repo_dir)
    return records


def repo_is_dirty(repo_dir: Path) -> bool:
    git_dir = repo_dir / ".git"
    if not git_dir.exists():
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def remove_stale(previous: dict[str, tuple[str, str]], desired: dict[str, tuple[str, str]]) -> None:
    stale_keys = sorted(set(previous.keys()) - set(desired.keys()))
    for key in stale_keys:
        binary_path, repo_dir = previous[key]
        binary = Path(binary_path).expanduser()
        repo = Path(repo_dir).expanduser()

        if binary.exists():
            binary.unlink()
            print(f"Removed stale binary for {key}: {binary}")

        if not repo.exists():
            continue

        if repo_is_dirty(repo):
            print(f"Skipping stale repo removal for {key} (dirty git tree): {repo}", file=sys.stderr)
            continue

        shutil.rmtree(repo)
        print(f"Removed stale repo for {key}: {repo}")


def write_state(path: Path, desired: dict[str, tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{output_name}\t{binary_path}\t{repo_dir}" for output_name, (binary_path, repo_dir) in sorted(desired.items())
    ]
    text = "\n".join(lines)
    if lines:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: reconcile_custom_packages.py <state_file> <desired_file>", file=sys.stderr)
        return 1

    state_file = Path(sys.argv[1]).expanduser()
    desired_file = Path(sys.argv[2]).expanduser()

    previous = load_tsv(state_file)
    desired = load_tsv(desired_file)

    remove_stale(previous, desired)
    write_state(state_file, desired)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
