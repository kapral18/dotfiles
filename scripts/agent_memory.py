#!/usr/bin/env python3
"""Inspect, set, and wipe hook memory under /tmp/specs for the current workspace."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_TOPIC = "current"
DEFAULT_BRANCH_NAMES = {"main", "master", "dev", "develop", "trunk"}
SPEC_ROOT = Path(os.environ.get("AGENT_MEMORY_SPEC_ROOT", "/tmp/specs"))
SESSION_TOPIC_PREFIX = ".session-topic-"
TOPIC_SUFFIXES = (
    ".txt",
    ".worklog.jsonl",
    ".no_context",
)
SELECT_CONTEXT_WORKLOG_LINES = 12
SELECT_CONTEXT_WORKLOG_CHARS = 3000


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


def session_key(value: str | None) -> str | None:
    if not value:
        return None
    topic = safe_topic(value)
    return topic if topic != DEFAULT_TOPIC else None


def session_fallback_topic(session_id: str | None) -> str | None:
    key = session_key(session_id)
    return f"session-{key[:24]}" if key else None


def session_topic_path(spec_dir: Path, key: str) -> Path:
    return spec_dir / f"{SESSION_TOPIC_PREFIX}{key}.txt"


def session_selected_topic(spec_dir: Path, session_id: str | None) -> str | None:
    key = session_key(session_id)
    if not key:
        return None
    try:
        raw_topic = session_topic_path(spec_dir, key).read_text().strip()
    except OSError:
        return None
    topic = safe_topic(raw_topic or DEFAULT_TOPIC)
    return topic if topic != DEFAULT_TOPIC else None


def topic_files(spec_dir: Path, topic: str) -> list[Path]:
    return [spec_dir / f"{topic}{suffix}" for suffix in TOPIC_SUFFIXES]


def transcript_tail(
    path: Path, lines: int = SELECT_CONTEXT_WORKLOG_LINES, limit: int = SELECT_CONTEXT_WORKLOG_CHARS
) -> str:
    try:
        raw_lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return ""

    tail: list[str] = []
    total = 0
    for line in reversed(raw_lines):
        next_total = total + len(line) + 1
        if tail and (len(tail) >= lines or next_total > limit):
            break
        tail.append(line)
        total = next_total
    return "\n".join(reversed(tail))


def selected_context(spec_dir: Path, topic: str) -> str:
    spec_file = spec_dir / f"{topic}.txt"
    worklog_file = spec_dir / f"{topic}.worklog.jsonl"
    try:
        spec_text = spec_file.read_text(errors="replace").strip()
    except OSError:
        spec_text = ""

    lines = [
        "### Selected Topic Context",
        f"- Topic: `{topic}`",
        f"- Spec: `{spec_file}`",
        "",
        "#### Active Topic Spec",
        spec_text or f"Topic spec exists at `{spec_file}`.",
    ]

    worklog = transcript_tail(worklog_file)
    if worklog:
        lines.extend(["", "#### Recent Hook Worklog", worklog])

    return "\n".join(lines)


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


def wipe_topic(spec_dir: Path, topic: str, dry_run: bool) -> list[Path]:
    removed: list[Path] = []
    for path in topic_files(spec_dir, topic):
        if not path.exists():
            continue
        removed.append(path)
        if not dry_run:
            path.unlink()
    return removed


def is_named_topic(topic: str) -> bool:
    """A deliberate named topic: not the generic fallback, not a per-session key."""
    return topic != DEFAULT_TOPIC and not topic.startswith("session-")


def resolve_selected_topic(
    spec_dir: Path,
    workspace: Path,
    requested_topic: str | None,
    session_id: str | None = None,
) -> str:
    if requested_topic:
        return safe_topic(requested_topic)

    session_topic = session_selected_topic(spec_dir, session_id)
    if session_topic:
        return session_topic

    if session_id:
        if current_git_branch(workspace) in DEFAULT_BRANCH_NAMES:
            fallback = session_fallback_topic(session_id)
            if fallback:
                return fallback
        return DEFAULT_TOPIC

    explicit = explicit_active_topic(spec_dir)
    if explicit:
        return explicit

    if current_git_branch(workspace) in DEFAULT_BRANCH_NAMES:
        session_topic = latest_session_topic(spec_dir)
        if session_topic:
            return session_topic

    return DEFAULT_TOPIC


def cmd_status(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    spec_dir = spec_dir_for(workspace)
    topic = resolve_selected_topic(spec_dir, workspace, args.topic, args.session_id)
    key = session_key(args.session_id)
    branch = current_git_branch(workspace)
    spec_file = spec_dir / f"{topic}.txt"

    if getattr(args, "json", False):
        payload = {
            "workspace": str(workspace),
            "spec_dir": str(spec_dir),
            "branch": branch,
            "session_id": args.session_id,
            "session_key": key,
            "selected_topic": topic,
            "session_selected_topic": session_selected_topic(spec_dir, args.session_id),
            "is_named_topic": is_named_topic(topic),
            "spec_file": str(spec_file),
            "spec_exists": spec_file.exists(),
            "files": {str(path): path.exists() for path in topic_files(spec_dir, topic)},
        }
        print(json.dumps(payload, sort_keys=True))
        return 0

    print(f"workspace: {workspace}")
    print(f"spec_dir: {spec_dir}")
    print(f"branch: {branch or '<none>'}")
    if args.session_id:
        print(f"session_id: {args.session_id}")
    print(f"selected_topic: {topic}")
    for path in topic_files(spec_dir, topic):
        print(f"{'exists' if path.exists() else 'missing'}: {path}")
    return 0


def cmd_select(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    spec_dir = spec_dir_for(workspace)
    topic = safe_topic(args.topic)
    if topic == DEFAULT_TOPIC:
        raise SystemExit(f"Refusing to select the generic topic {DEFAULT_TOPIC!r}; choose a named topic.")
    key = session_key(args.session_id)
    if not key:
        raise SystemExit("--session-id is required for session-scoped topic selection.")

    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_file = spec_dir / f"{topic}.txt"
    seeded = False
    if not spec_file.exists():
        if not args.create:
            raise SystemExit(f"Topic {topic!r} does not exist; pass --create to seed it.")
        spec_file.write_text(f"topic: {topic}\n")
        seeded = True

    binding = session_topic_path(spec_dir, key)
    binding.write_text(topic + "\n")
    print(f"session topic: {topic}")
    print(f"session_id: {key}")
    print(f"binding: {binding}")
    print(f"{'seeded' if seeded else 'exists'}: {spec_file}")
    print()
    print(selected_context(spec_dir, topic))
    return 0


def cmd_use(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    spec_dir = spec_dir_for(workspace)
    topic = safe_topic(args.topic)
    if topic == DEFAULT_TOPIC:
        raise SystemExit(f"Refusing to set the generic topic {DEFAULT_TOPIC!r}; choose a named topic.")

    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "_active_topic.txt").write_text(topic + "\n")

    spec_file = spec_dir / f"{topic}.txt"
    seeded = False
    if not spec_file.exists():
        spec_file.write_text(f"topic: {topic}\n")
        seeded = True

    print(f"active topic: {topic}")
    print(f"pointer: {spec_dir / '_active_topic.txt'}")
    print(f"{'seeded' if seeded else 'exists'}: {spec_file}")
    return 0


def cmd_wipe_current(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    spec_dir = spec_dir_for(workspace)
    topic = resolve_selected_topic(spec_dir, workspace, args.topic, args.session_id)
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
    status.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    status.set_defaults(func=cmd_status)

    select = subcommands.add_parser(
        "select",
        help="Bind this agent session to a topic bucket and print its selected context.",
    )
    select.add_argument("topic", help="Named topic bucket to bind this session to.")
    select.add_argument("--session-id", required=True, help="Stable session id from the agent runtime.")
    select.add_argument("--create", action="store_true", help="Seed <topic>.txt if the bucket does not exist.")
    select.add_argument(
        "--workspace",
        default=None,
        help="Workspace path. Defaults to the current directory.",
    )
    select.set_defaults(func=cmd_select)

    use = subcommands.add_parser(
        "use",
        help="Set the active named topic (writes _active_topic.txt, seeds <topic>.txt).",
    )
    use.add_argument("topic", help="Named topic (kebab-case); the generic 'current' is rejected.")
    use.add_argument(
        "--workspace",
        default=None,
        help="Workspace path. Defaults to the current directory.",
    )
    use.set_defaults(func=cmd_use)

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
    command.add_argument(
        "--session-id",
        default=default,
        help="Resolve a session-scoped topic binding for this runtime session.",
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
