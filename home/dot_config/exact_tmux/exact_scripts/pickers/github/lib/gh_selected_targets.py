#!/usr/bin/env python3
"""Emit each selected GitHub target once as kind/repository/number TSV."""

from __future__ import annotations

import argparse
from pathlib import Path


def selected_targets(path: Path) -> list[tuple[str, str, str]]:
    targets: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").split("\n"):
        parts = line.removesuffix("\r").split("\t")
        if len(parts) < 4:
            continue
        kind, repo, num = parts[1:4]
        if kind not in {"pr", "issue"} or not repo or not num:
            continue
        target = (kind, repo, num)
        if target not in seen:
            seen.add(target)
            targets.append(target)
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection_file", type=Path)
    args = parser.parse_args()
    try:
        targets = selected_targets(args.selection_file)
    except OSError as error:
        parser.exit(1, f"selected targets: {error}\n")
    for target in targets:
        print("\t".join(target))


if __name__ == "__main__":
    main()
