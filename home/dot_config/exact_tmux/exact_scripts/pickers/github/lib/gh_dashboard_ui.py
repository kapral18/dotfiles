#!/usr/bin/env python3
"""Status line helper for the tmux GitHub picker.

Only renders the cockpit header (mode/scope/counts/cache age + key actions).
The picker remains the action surface; this module exists so the bash glue
stays free of TSV parsing logic.
"""

from __future__ import annotations

import argparse
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class Row:
    display: str
    kind: str
    repo: str
    num: str
    url: str
    search: str
    meta: str
    mergeable: str
    section: str = ""


def strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value)


def clean_text(value: str) -> str:
    return " ".join(value.replace("\t", " ").replace("\r", " ").split())


def read_rows(path: str) -> list[Row]:
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    rows: list[Row] = []
    current_section = ""
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        parts += [""] * (9 - len(parts))
        row = Row(
            display=parts[0],
            kind=parts[1],
            repo=parts[2],
            num=parts[3],
            url=parts[4],
            search=parts[5],
            meta=parts[6],
            mergeable=parts[7],
            section=parts[8],
        )
        if row.kind == "header":
            current_section = clean_text(parts[5] or strip_ansi(parts[0]))
            continue
        if row.kind not in ("pr", "issue"):
            continue
        if not row.section:
            row.section = current_section
        rows.append(row)
    return rows


def cache_age(path: str) -> str:
    try:
        seconds = max(0, int(time.time() - os.path.getmtime(path)))
    except Exception:
        return "no cache"
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h"


def status_line(cache_file: str, mode: str, scope: str) -> str:
    rows = read_rows(cache_file)
    sections = {row.section for row in rows if row.section}
    prs = sum(1 for row in rows if row.kind == "pr")
    issues = sum(1 for row in rows if row.kind == "issue")
    total = prs + issues
    age = cache_age(cache_file)
    return (
        f"mode:{mode} scope:{scope} items:{total} prs:{prs} issues:{issues} "
        f"sections:{len(sections)} cache:{age} | "
        "enter checkout ctrl-r refresh alt-A Ralph ? help"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status")
    p_status.add_argument("--cache-file", required=True)
    p_status.add_argument("--mode", required=True)
    p_status.add_argument("--scope", required=True)

    args = parser.parse_args()
    if args.cmd == "status":
        print(status_line(args.cache_file, args.mode, args.scope))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
