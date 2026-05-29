#!/usr/bin/env python3
"""Filter script for tmux session picker. Reads config from env vars."""

import os
import signal
import subprocess
import sys

import frecency
from pick_session_grouping import (
    cached_resolve,
    grouped_output,
)


def _row_matches_only(line, only_filter):
    """Return True if a TSV row passes the active --only view filter.

    Reads the cache `meta` column (index 3): `status=...,dirty` for dirty,
    `pr=NUM:STATE:REVIEW:...` with REVIEW in {CHANGES_REQUESTED, REVIEW_REQUIRED}
    for review-needed.
    """
    parts = line.split("\t")
    if len(parts) < 4:
        return False
    meta = parts[3] or ""
    if only_filter == "dirty":
        for segment in meta.split("|"):
            if segment.startswith("status=") and "dirty" in segment[len("status=") :].split(","):
                return True
        return False
    if only_filter == "review":
        for segment in meta.split("|"):
            if not segment.startswith("pr="):
                continue
            fields = segment[len("pr=") :].split(":")
            if len(fields) >= 3 and fields[2].upper() in ("CHANGES_REQUESTED", "REVIEW_REQUIRED"):
                return True
        return False
    return True


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
    only_filter = (os.environ.get("PICK_SESSION_ONLY", "") or "").strip().lower()

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

    if only_filter in ("dirty", "review"):
        lines = [line for line in lines if _row_matches_only(line, only_filter)]

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
