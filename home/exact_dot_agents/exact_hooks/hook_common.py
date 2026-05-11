#!/usr/bin/env python3
"""Shared helpers for Cursor/Claude agent hook scripts."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TOPIC = "current"
DEFAULT_BRANCH_NAMES = {"main", "master", "dev", "develop", "trunk"}
SPEC_ROOT = Path("/tmp/specs")


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def emit(data: dict[str, Any]) -> None:
    print(json.dumps(data, sort_keys=True))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def workspace_root(payload: dict[str, Any]) -> Path:
    roots = payload.get("workspace_roots")
    if isinstance(roots, list) and roots:
        return Path(str(roots[0])).expanduser().resolve()

    cwd = payload.get("cwd")
    if cwd:
        return Path(str(cwd)).expanduser().resolve()

    return Path.cwd().resolve()


def spec_dir_for(workspace: Path) -> Path:
    return SPEC_ROOT / str(workspace).lstrip(os.sep)


def safe_topic(value: Any) -> str:
    topic = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip())
    topic = topic.strip(".-")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}", topic):
        return topic
    return DEFAULT_TOPIC


def session_topic(payload: dict[str, Any]) -> str:
    for key in ("conversation_id", "session_id", "generation_id"):
        value = payload.get(key)
        if value:
            topic = safe_topic(value)
            if topic != DEFAULT_TOPIC:
                return f"session-{topic[:24]}"
    return DEFAULT_TOPIC


def current_git_branch(workspace: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "branch", "--show-current"],
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""

    return result.stdout.strip()


def is_default_branch_workspace(workspace: Path) -> bool:
    return current_git_branch(workspace) in DEFAULT_BRANCH_NAMES


def active_topic(spec_dir: Path, workspace: Path, payload: dict[str, Any]) -> str:
    pointer = spec_dir / "_active_topic.txt"
    try:
        raw_topic = pointer.read_text().strip()
    except OSError:
        raw_topic = ""

    topic = safe_topic(raw_topic)
    if topic != DEFAULT_TOPIC:
        return topic

    if is_default_branch_workspace(workspace):
        return session_topic(payload)

    return DEFAULT_TOPIC


def topic_paths(payload: dict[str, Any]) -> tuple[Path, str, Path, Path]:
    workspace = workspace_root(payload)
    spec_dir = spec_dir_for(workspace)
    topic = active_topic(spec_dir, workspace, payload)
    return workspace, topic, spec_dir / f"{topic}.txt", spec_dir / f"{topic}.worklog.jsonl"


def append_jsonl(path: Path, entry: dict[str, Any], max_lines: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    if max_lines is not None:
        trim_jsonl(path, max_lines=max_lines)


def trim_jsonl(path: Path, max_lines: int) -> None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return

    if len(lines) <= max_lines:
        return

    path.write_text("\n".join(lines[-max_lines:]) + "\n", encoding="utf-8")


def bounded_text(value: Any, limit: int = 1200) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... truncated {len(text) - limit} chars"


def transcript_tail(path: Path, lines: int = 20, limit: int = 4000) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    selected: list[str] = []
    selected_chars = 0
    omitted = 0
    for line in reversed(content[-lines:]):
        line_len = len(line) + (1 if selected else 0)
        if selected and selected_chars + line_len > limit:
            omitted += 1
            continue
        if not selected and line_len > limit:
            omitted += 1
            continue
        selected.append(line)
        selected_chars += line_len

    selected.reverse()
    if omitted:
        selected.insert(
            0, f"[omitted {omitted} older worklog entr{'y' if omitted == 1 else 'ies'} to keep context atomic]"
        )
    return "\n".join(selected)
