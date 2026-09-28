"""Exact-text anchor recording and resolution.

Anchor snippets preserve every source character within their recorded line range: indentation,
internal and trailing whitespace, tabs, and blank lines are all semantically significant. Unique
snippets may relocate by exact-text matching. A snippet that was non-unique when recorded may
resolve only while the complete source file is byte-for-byte identical to its recorded state;
after any source change, text and coordinates alone cannot prove which duplicate is the original
occurrence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _split_lines(text: str) -> list[str]:
    """Split ``text`` on ``"\\n"`` only -- never ``str.splitlines()``, which also breaks lines on
    characters like ``"\\x0c"`` (form feed), ``"\\x1c"``-``"\\x1e"``, or ``"\\u2028"`` that a real
    text editor's line numbering never treats as a line break; using it here would silently shift
    every reported anchor line number after one. A trailing ``"\\n"`` (the common end-of-file
    case) never produces an extra empty final line, matching ``str.splitlines()``'s own
    trailing-newline behavior. An embedded ``"\\r"`` right before a ``"\\n"`` (CRLF) remains
    part of the exact source line."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def normalize_lines(text: str) -> list[tuple[int, str]]:
    """Return each exact physical source line with its 1-based line number."""
    return list(enumerate(_split_lines(text), start=1))


def normalize_snippet(text: str) -> str:
    """Retain the historical API name while preserving snippet text exactly."""
    return text


def norm_sha(text: str) -> str:
    return hashlib.sha256(normalize_snippet(text).encode("utf-8")).hexdigest()


def source_sha(path: Path) -> str:
    """Hash the complete exact source text used to identify a non-unique occurrence."""
    return hashlib.sha256(_read_text_or_raise(path).encode("utf-8")).hexdigest()


def _read_text_or_raise(path: Path) -> str:
    """Read exact UTF-8 source text without universal-newline translation.

    Filesystem and decoding failures use ``ValueError``, which anchor producers already convert
    to a CLI usage error.
    """
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"{path} cannot be read as UTF-8 text: {exc}") from exc


def extract_snippet(path: Path, start: int, end: int) -> str:
    lines = _split_lines(_read_text_or_raise(path))
    if start < 1 or end < start or end > len(lines):
        raise ValueError(f"anchor range {start}-{end} out of bounds for {path} ({len(lines)} lines)")
    return "\n".join(lines[start - 1 : end])


def trim_to_nonblank(path: Path, start: int, end: int) -> tuple[int, int]:
    """Trim a requested ``start``-``end`` range down to its first and last non-blank (not
    whitespace-only) line, so a leading/trailing blank line in the requested range is never
    itself recorded as part of the anchor. Raises ``ValueError`` when every line in the range is
    blank -- there is no snippet left to anchor."""
    lines = _split_lines(_read_text_or_raise(path))
    if start < 1 or end < start or end > len(lines):
        raise ValueError(f"anchor range {start}-{end} out of bounds for {path} ({len(lines)} lines)")
    segment = lines[start - 1 : end]
    nonblank_offsets = [offset for offset, line in enumerate(segment) if line.strip()]
    if not nonblank_offsets:
        raise ValueError(f"anchor range {start}-{end} in {path} is entirely blank lines")
    return start + nonblank_offsets[0], start + nonblank_offsets[-1]


def _find_all(file_norms: list[str], needle: list[str]) -> list[int]:
    """Every 0-based index in ``file_norms`` where ``needle`` occurs, in order."""
    span = len(needle)
    return [index for index in range(0, len(file_norms) - span + 1) if file_norms[index : index + span] == needle]


def count_occurrences(path: Path, normalized_snippet: str) -> int:
    """Count exact occurrences of an already-recorded snippet in the source line sequence."""
    if not normalized_snippet:
        return 0
    file_lines = [line for _, line in normalize_lines(_read_text_or_raise(path))]
    return len(_find_all(file_lines, normalized_snippet.split("\n")))


def check_anchor(workspace: Path, anchor: dict[str, Any]) -> dict[str, Any]:
    """Resolve one exact-text anchor against the current working tree.

    A missing or unreadable path resolves ``missing`` or ``edited`` respectively. A unique
    snippet resolves ``unchanged`` at its recorded coordinates or at its sole exact occurrence
    elsewhere in the file. For a snippet that was non-unique when recorded, the complete source
    digest must still match before its recorded coordinates can identify the same occurrence.
    Any source change makes reuse of a duplicate ambiguous, including deletion of one occurrence
    that shifts another duplicate into the recorded line range.
    """
    file_path = workspace / anchor["path"]
    result: dict[str, Any] = {"id": anchor.get("id"), "path": anchor["path"]}
    if not file_path.exists():
        result["status"] = "missing"
        return result
    try:
        raw_text = _read_text_or_raise(file_path)
    except ValueError:
        result["status"] = "edited"
        result["reason"] = "unreadable"
        return result
    file_lines = normalize_lines(raw_text)
    file_norms = [line for _, line in file_lines]
    file_linenos = [ln for ln, _ in file_lines]
    needle = anchor["snippet"].split("\n") if anchor.get("snippet") else []
    if not needle:
        result["status"] = "edited"
        return result
    span = len(needle)
    matches = _find_all(file_norms, needle)
    if not matches:
        result["status"] = "edited"
        return result

    def _span_at(index: int) -> tuple[int, int]:
        return file_linenos[index], file_linenos[index + span - 1]

    recorded = (anchor.get("start"), anchor.get("end"))
    source_unchanged = hashlib.sha256(raw_text.encode("utf-8")).hexdigest() == anchor.get("source_sha")
    if not anchor.get("unique") and not source_unchanged:
        result["status"] = "edited"
        result["reason"] = "ambiguous"
        return result
    for index in matches:
        if _span_at(index) == recorded:
            result["status"] = "unchanged"
            result["start"], result["end"] = recorded
            result["relocated"] = False
            return result

    if len(matches) == 1 and anchor.get("unique"):
        new_start, new_end = _span_at(matches[0])
        result["status"] = "unchanged"
        result["start"] = new_start
        result["end"] = new_end
        result["relocated"] = True
        return result

    result["status"] = "edited"
    result["reason"] = "ambiguous"
    return result
