#!/usr/bin/env python3
"""Inspect and wipe hook memory under /tmp/specs for the current workspace."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_TOPIC = "current"
DEFAULT_BRANCH_NAMES = {"main", "master", "dev", "develop", "trunk"}
SPEC_ROOT = Path(os.environ.get("AGENT_MEMORY_SPEC_ROOT", "/tmp/specs"))
TOPIC_SUFFIXES = (
    ".txt",
    ".worklog.jsonl",
    ".evidence_state.json",
    ".evidence_decisions.jsonl",
    ".no_context",
)


def safe_topic(value: str) -> str:
    topic = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    topic = topic.strip(".-")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}", topic):
        return topic
    raise SystemExit(f"Invalid topic: {value!r}")


def workspace_path(value: str | None) -> Path:
    return Path(value or os.getcwd()).expanduser().resolve()


def spec_dir_for(workspace: Path) -> Path:
    return SPEC_ROOT / str(workspace).lstrip(os.sep)


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


def explicit_active_topic(spec_dir: Path) -> str | None:
    try:
        raw_topic = (spec_dir / "_active_topic.txt").read_text().strip()
    except OSError:
        return None

    topic = safe_topic(raw_topic or DEFAULT_TOPIC)
    return topic if topic != DEFAULT_TOPIC else None


def topic_files(spec_dir: Path, topic: str) -> list[Path]:
    return [spec_dir / f"{topic}{suffix}" for suffix in TOPIC_SUFFIXES]


def latest_session_topic(spec_dir: Path) -> str | None:
    candidates: dict[str, float] = {}
    for path in spec_dir.glob("session-*.*"):
        topic = path.name.split(".", 1)[0]
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        candidates[topic] = max(candidates.get(topic, 0), mtime)

    if not candidates:
        return None

    return max(candidates.items(), key=lambda item: item[1])[0]


def selected_topic(spec_dir: Path, workspace: Path, requested_topic: str | None) -> str:
    if requested_topic:
        return safe_topic(requested_topic)

    explicit = explicit_active_topic(spec_dir)
    if explicit:
        return explicit

    if current_git_branch(workspace) in DEFAULT_BRANCH_NAMES:
        session_topic = latest_session_topic(spec_dir)
        if session_topic:
            return session_topic

    return DEFAULT_TOPIC


def wipe_topic(spec_dir: Path, topic: str, dry_run: bool) -> list[Path]:
    removed: list[Path] = []
    for path in topic_files(spec_dir, topic):
        if not path.exists():
            continue
        removed.append(path)
        if not dry_run:
            path.unlink()
    return removed


def cmd_status(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    spec_dir = spec_dir_for(workspace)
    topic = selected_topic(spec_dir, workspace, args.topic)
    print(f"workspace: {workspace}")
    print(f"spec_dir: {spec_dir}")
    print(f"branch: {current_git_branch(workspace) or '<none>'}")
    print(f"selected_topic: {topic}")
    for path in topic_files(spec_dir, topic):
        print(f"{'exists' if path.exists() else 'missing'}: {path}")
    return 0


def cmd_wipe_current(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    spec_dir = spec_dir_for(workspace)
    topic = selected_topic(spec_dir, workspace, args.topic)
    removed = wipe_topic(spec_dir, topic, args.dry_run)

    action = "would remove" if args.dry_run else "removed"
    print(f"{action} topic: {topic}")
    if not removed:
        print("no topic files found")
    for path in removed:
        print(path)

    if args.reset_active and not args.dry_run:
        active_pointer = spec_dir / "_active_topic.txt"
        if active_pointer.exists():
            active_pointer.unlink()
            print(f"removed active pointer: {active_pointer}")

    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    add_shared_options(root)

    subcommands = root.add_subparsers(dest="command", required=True)
    status = subcommands.add_parser("status", help="Show selected topic and files.")
    add_shared_options(status, subcommand=True)
    status.set_defaults(func=cmd_status)

    wipe = subcommands.add_parser("wipe-current", help="Delete files for the selected active topic.")
    add_shared_options(wipe, subcommand=True)
    wipe.add_argument("--dry-run", action="store_true", help="Print files without deleting them.")
    wipe.add_argument(
        "--reset-active",
        action="store_true",
        help="Also remove _active_topic.txt after deleting topic files.",
    )
    wipe.set_defaults(func=cmd_wipe_current)
    return root


def add_shared_options(command: argparse.ArgumentParser, subcommand: bool = False) -> None:
    default = argparse.SUPPRESS if subcommand else None
    command.add_argument(
        "--workspace",
        default=default,
        help="Workspace path. Defaults to the current directory.",
    )
    command.add_argument(
        "--topic",
        default=default,
        help="Override topic instead of resolving the active/current topic.",
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
