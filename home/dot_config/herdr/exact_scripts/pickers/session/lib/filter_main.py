#!/usr/bin/env python3
"""Filter script for the session picker. Reads config from env vars."""

import os
import signal
import subprocess
import sys

import frecency
import only_filter
from pick_session_grouping import (
    cached_resolve,
    grouped_output,
)


def main():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    items_cmd = os.environ.get("ITEMS_CMD", "").strip()
    if not items_cmd:
        sys.exit(0)

    roots_raw = (os.environ.get("PICK_SESSION_SCAN_ROOTS", "") or "").strip()
    try:
        passthrough_rows = int((os.environ.get("PICK_SESSION_FILTER_PASSTHROUGH_ROWS", "0") or "0").strip())
    except Exception:
        passthrough_rows = 0
    force_order_raw = (os.environ.get("PICK_SESSION_FILTER_FORCE_ORDER", "") or "").strip().lower()
    force_order = force_order_raw in ("1", "true", "yes", "on")

    resolve_path = cached_resolve({})

    scan_roots = []
    for part in roots_raw.split(",") if roots_raw else []:
        part = part.strip()
        if not part:
            continue
        scan_roots.append(resolve_path(part))
    home_root = resolve_path("~")
    if home_root and home_root not in scan_roots:
        scan_roots.append(home_root)

    try:
        base_out = subprocess.run(
            [items_cmd],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout
    except Exception:
        sys.exit(0)

    if not base_out:
        sys.exit(0)

    lines = [line.rstrip("\n") for line in base_out.splitlines() if line.rstrip("\n")]

    lines = only_filter.apply(lines)

    if (not force_order) and passthrough_rows > 0 and len(lines) >= passthrough_rows:
        for line in lines:
            print(line)
        sys.exit(0)

    try:
        frecency_scores = frecency.scores()
    except Exception:
        frecency_scores = {}

    for line in grouped_output(lines, scan_roots, resolve_path, frecency_scores):
        print(line)


if __name__ == "__main__":
    main()
