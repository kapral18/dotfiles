#!/usr/bin/env python3
"""Best-effort persistent mirror for named-topic hook memory.

`/tmp/specs` stays the primary, intentionally best-effort store for topic
specs and worklogs; macOS wipes it on reboot. This module mirrors NAMED
topics (never `current`, never `session-*` fallbacks) into a persistent
per-workspace directory and restores them when the primary copy is gone,
so a reboot no longer silently ends every long-running topic.

Contract:

- The mirror is a backup, never an authority: restore only copies files
  that are missing from the spec dir and never overwrites live state.
- Sync happens at deliberate checkpoints (session start, `,agent-memory`
  status/select/use/note/merge), not on the per-tool-event hot path.
- `forget_topic` keeps the mirror honest when a topic is wiped or merged
  away, so a wiped topic cannot resurrect from its mirror copy.
- Every entry point fails open: hook memory must never break a session.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

MIRROR_ROOT_ENV = "AGENT_MEMORY_MIRROR_ROOT"
TOPIC_SUFFIXES = (".txt", ".worklog.jsonl", ".no_context")
ACTIVE_POINTER = "_active_topic.txt"
MIRROR_FILE_MAX_BYTES = 512 * 1024
RESERVED_TOPICS = ("current",)
SESSION_FALLBACK_PREFIX = "session-"


def mirror_root() -> Path:
    """Resolve the mirror root per call so tests and subprocesses can redirect it."""
    return Path(os.environ.get(MIRROR_ROOT_ENV, str(Path.home() / ".local" / "state" / "agent-specs")))


def mirror_dir_for(workspace: Path) -> Path:
    return mirror_root() / str(workspace).lstrip(os.sep)


def is_mirrored_topic(topic: str) -> bool:
    """Named topics only: reserved and per-session fallback buckets stay ephemeral."""
    if not topic or topic in RESERVED_TOPICS:
        return False
    if topic.startswith(SESSION_FALLBACK_PREFIX) or topic.startswith((".", "_")):
        return False
    return True


def _copy_if_changed(src: Path, dst: Path) -> bool:
    try:
        if not src.is_file():
            return False
        data = src.read_bytes()
        if len(data) > MIRROR_FILE_MAX_BYTES:
            return False
        if dst.is_file() and dst.read_bytes() == data:
            return False
        dst.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, tmp_name = tempfile.mkstemp(dir=str(dst.parent), prefix=f".{dst.name}.")
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_name, dst)
        return True
    except OSError:
        return False


def sync_topic(spec_dir: Path, workspace: Path, topic: str) -> "list[str]":
    """Mirror one named topic's files plus the workspace active-topic pointer."""
    if not is_mirrored_topic(topic):
        return []
    mirror_dir = mirror_dir_for(workspace)
    synced: "list[str]" = []
    for suffix in TOPIC_SUFFIXES:
        name = f"{topic}{suffix}"
        if _copy_if_changed(spec_dir / name, mirror_dir / name):
            synced.append(name)
    if _copy_if_changed(spec_dir / ACTIVE_POINTER, mirror_dir / ACTIVE_POINTER):
        synced.append(ACTIVE_POINTER)
    return synced


def restore_topics(spec_dir: Path, workspace: Path) -> "list[str]":
    """Copy mirrored named topics back when their primary copies are gone.

    Only files missing from `spec_dir` are restored, so live `/tmp` state
    always wins over the mirror. Returns the restored file names.
    """
    mirror_dir = mirror_dir_for(workspace)
    restored: "list[str]" = []
    try:
        entries = sorted(mirror_dir.iterdir())
    except OSError:
        return restored
    for src in entries:
        name = src.name
        if name == ACTIVE_POINTER:
            topic = ""
        elif name.endswith(".worklog.jsonl"):
            topic = name[: -len(".worklog.jsonl")]
        elif name.endswith(".no_context"):
            topic = name[: -len(".no_context")]
        elif name.endswith(".txt"):
            topic = name[: -len(".txt")]
        else:
            continue
        if topic and not is_mirrored_topic(topic):
            continue
        dst = spec_dir / name
        try:
            if dst.exists():
                continue
        except OSError:
            continue
        if _copy_if_changed(src, dst):
            restored.append(name)
    return restored


def forget_topic(workspace: Path, topic: str) -> "list[str]":
    """Drop a topic's mirror copies so a wiped/merged-away topic stays gone."""
    mirror_dir = mirror_dir_for(workspace)
    removed: "list[str]" = []
    for suffix in TOPIC_SUFFIXES:
        path = mirror_dir / f"{topic}{suffix}"
        try:
            if path.is_file():
                path.unlink()
                removed.append(path.name)
        except OSError:
            continue
    return removed
