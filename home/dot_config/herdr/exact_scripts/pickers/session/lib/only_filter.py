"""The alt-o view filter. PICK_SESSION_ONLY_FILE holds the picker's mode; every reload reads it."""

import os
from pathlib import Path

MODES = ("dirty", "review")


def active_mode() -> str:
    path = os.environ.get("PICK_SESSION_ONLY_FILE", "")
    if not path:
        return ""
    try:
        mode = Path(path).read_text().strip()
    except OSError:
        return ""
    return mode if mode in MODES else ""


def row_matches(line: str, mode: str) -> bool:
    """Match the cache `meta` column (index 3): `status=...,dirty` or a `pr=NUM:STATE:REVIEW` needing review."""
    parts = line.split("\t")
    if len(parts) < 4:
        return False
    segments = (parts[3] or "").split("|")
    if mode == "dirty":
        return any(s.startswith("status=") and "dirty" in s[len("status=") :].split(",") for s in segments)
    if mode == "review":
        for segment in segments:
            if not segment.startswith("pr="):
                continue
            fields = segment[len("pr=") :].split(":")
            if len(fields) >= 3 and fields[2].upper() in ("CHANGES_REQUESTED", "REVIEW_REQUIRED"):
                return True
        return False
    return True


def apply(lines: list[str]) -> list[str]:
    mode = active_mode()
    return [line for line in lines if row_matches(line, mode)] if mode else lines
