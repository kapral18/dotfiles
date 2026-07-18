#!/usr/bin/env python3
"""Inspect, set, and wipe hook memory under /tmp/specs for the current workspace."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TOPIC = "current"
DEFAULT_BRANCH_NAMES = {"main", "master", "dev", "develop", "trunk"}
SPEC_ROOT = Path(os.environ.get("AGENT_MEMORY_SPEC_ROOT", "/tmp/specs"))
SESSION_TOPIC_PREFIX = ".session-topic-"
PARENT_SESSION_ENV = "COPILOT_AGENT_SESSION_ID"
# One vocabulary with the durable store: note kinds are the `,ai-kb` capsule
# kinds (minus ingestion-only `doc`) plus task-scoped `question` and `decision`.
# The kind is the knowledge TYPE; verification status is carried by where the
# item lives (worklog note = unverified candidate, capsule = verified). A
# `decision` note harvests as a `fact` capsule candidate; `question` never
# harvests. Keep in sync with CAPSULE_KINDS in scripts/ai_kb.py.
NOTE_KINDS = ("fact", "gotcha", "pattern", "anti_pattern", "recipe", "principle", "question", "decision")
NOTE_TEXT_MAX_CHARS = 2000
TOPIC_SUFFIXES = (
    ".txt",
    ".worklog.jsonl",
    ".no_context",
)
SELECT_CONTEXT_WORKLOG_LINES = 12
SELECT_CONTEXT_WORKLOG_CHARS = 3000
# Mirrors MAX_SPEC_CHARS + REVIEW_CONCLUSION_HEADINGS in
# home/exact_dot_agents/exact_hooks/executable_session_context.py — change both
# together. `,agent-memory select` is a second clean-room entrypoint (agent_memory.py
# cannot import session_context.py: it always runs from the repo source via the
# `,agent-memory` launcher, while session_context.py is deployed standalone to
# ~/.agents/hooks/ and imports only its sibling hook_common.py).
SELECT_CONTEXT_MAX_SPEC_CHARS = 2500
REVIEW_CONCLUSION_HEADINGS = (
    "verified facts",
    "findings",
    "verdict",
    "inline comments",
    "pending review draft",
    "things checked",
    "net",
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


def session_key(value: str | None) -> str | None:
    if not value:
        return None
    topic = safe_topic(value)
    return topic if topic != DEFAULT_TOPIC else None


def parent_session_key() -> str | None:
    return session_key(os.environ.get(PARENT_SESSION_ENV))


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


def is_review_topic(topic: str, text: str) -> bool:
    """Mirrors session_context.py's is_review_topic — change both together."""
    return topic.startswith("review") or "\ntarget: PR " in f"\n{text}"


def neutral_review_spec(text: str, spec_path: Path) -> str:
    """Mirrors session_context.py's neutral_review_spec — change both together.

    Strips prior conclusions/findings/verdicts (everything from the first
    conclusion heading onward) so a review-topic session starts clean-room,
    whether that session begins via sessionStart or `,agent-memory select`.
    """
    lines: list[str] = []
    for line in text.splitlines():
        normalized = line.strip().rstrip(":").lower()
        if normalized in REVIEW_CONCLUSION_HEADINGS:
            break
        lines.append(line)

    body = "\n".join(lines).strip()
    if not body:
        body = f"Review topic spec exists at `{spec_path}`."

    return (
        body + "\n\n[review clean-room mode: prior findings, verdicts, verified-facts blocks, "
        f"and worklog tails are omitted from startup context. Read `{spec_path}` manually "
        "only if you intentionally want prior-session conclusions.]"
    )


def bounded_or_omitted(text: str, spec_path: Path) -> str:
    """Mirrors session_context.py's bounded_or_omitted — change both together.

    Applies the shared oversized-spec contract to already-final text (review
    text must already be sanitized by neutral_review_spec() before reaching
    here). Content is never truncated mid-context: once it exceeds the bound
    it is replaced wholesale with a pointer, so a sanitized-but-still-huge
    review body cannot leak past the size limit just because it is "already
    clean".
    """
    if len(text) <= SELECT_CONTEXT_MAX_SPEC_CHARS:
        return text

    return (
        f"Active topic spec omitted because it is {len(text)} characters, "
        f"exceeding the {SELECT_CONTEXT_MAX_SPEC_CHARS}-character injection limit. "
        f"Read `{spec_path}` before relying on prior session context."
    )


def bounded_spec_text(text: str, spec_path: Path, topic: str) -> tuple[str, bool]:
    """Apply the same clean-room + size-bound rules as session_context.py's spec_context.

    Returns (rendered text, is_review) so callers can also gate the worklog on
    is_review without re-deriving it from raw text.
    """
    text = text.strip()
    is_review = is_review_topic(topic, text)
    if is_review:
        return bounded_or_omitted(neutral_review_spec(text, spec_path), spec_path), True

    return bounded_or_omitted(text, spec_path), False


def selected_context(spec_dir: Path, topic: str) -> str:
    spec_file = spec_dir / f"{topic}.txt"
    worklog_file = spec_dir / f"{topic}.worklog.jsonl"
    try:
        spec_text_source = spec_file.read_text(errors="replace")
    except OSError:
        spec_text_source = ""

    spec_text, is_review = bounded_spec_text(spec_text_source, spec_file, topic)

    lines = [
        "### Selected Topic Context",
        f"- Topic: `{topic}`",
        f"- Spec: `{spec_file}`",
        "",
        "#### Active Topic Spec",
        spec_text or f"Topic spec exists at `{spec_file}`.",
    ]

    worklog = "" if is_review else transcript_tail(worklog_file)
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


def topic_material_exists(spec_dir: Path, topic: str) -> bool:
    return (spec_dir / f"{topic}.txt").exists() or (spec_dir / f"{topic}.worklog.jsonl").exists()


def utc_merge_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def pointer_targets_topic(path: Path, topic: str) -> bool:
    try:
        raw_topic = path.read_text().strip()
    except OSError:
        return False
    try:
        return safe_topic(raw_topic or DEFAULT_TOPIC) == topic
    except SystemExit:
        return False


def source_topic_bindings(spec_dir: Path, source: str) -> list[Path]:
    return sorted(path for path in spec_dir.glob(f"{SESSION_TOPIC_PREFIX}*.txt") if pointer_targets_topic(path, source))


def append_merged_spec(spec_dir: Path, source: str, dest: str, merged_at: str) -> tuple[Path, bool, bool]:
    source_path = spec_dir / f"{source}.txt"
    dest_path = spec_dir / f"{dest}.txt"
    dest_existed = dest_path.exists()
    source_existed = source_path.exists()
    if not source_existed and dest_existed:
        return dest_path, dest_existed, source_existed

    if dest_existed:
        dest_text = dest_path.read_text(encoding="utf-8", errors="replace")
    else:
        dest_text = f"topic: {dest}\n"

    if source_existed:
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
        if dest_text and not dest_text.endswith("\n"):
            dest_text += "\n"
        if dest_text:
            dest_text += "\n"
        dest_text += f"--- merged from {source} on {merged_at} ---\n"
        dest_text += source_text
        if source_text and not source_text.endswith("\n"):
            dest_text += "\n"

    dest_path.write_text(dest_text, encoding="utf-8")
    return dest_path, dest_existed, source_existed


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

    key = session_key(session_id)
    parent_key = parent_session_key()
    has_distinct_parent = bool(parent_key and parent_key != key)
    if has_distinct_parent:
        parent_topic = session_selected_topic(spec_dir, parent_key)
        if parent_topic:
            return parent_topic

    if session_id:
        if current_git_branch(workspace) in DEFAULT_BRANCH_NAMES:
            fallback = session_fallback_topic(parent_key if has_distinct_parent else session_id)
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


def _mirror_module():
    """Best-effort import of the persistent named-topic mirror (fail-open)."""
    try:
        import spec_mirror
    except ImportError:
        return None
    return spec_mirror


def mirror_restore(spec_dir: Path, workspace: Path) -> "list[str]":
    mirror = _mirror_module()
    if mirror is None:
        return []
    return mirror.restore_topics(spec_dir, workspace)


def mirror_sync(spec_dir: Path, workspace: Path, topic: str) -> "list[str]":
    mirror = _mirror_module()
    if mirror is None:
        return []
    return mirror.sync_topic(spec_dir, workspace, topic)


def mirror_forget(workspace: Path, topic: str) -> "list[str]":
    mirror = _mirror_module()
    if mirror is None:
        return []
    return mirror.forget_topic(workspace, topic)


def cmd_status(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    spec_dir = spec_dir_for(workspace)
    mirror_restore(spec_dir, workspace)
    topic = resolve_selected_topic(spec_dir, workspace, args.topic, args.session_id)
    mirror_sync(spec_dir, workspace, topic)
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


def migrate_session_fallback_worklog(spec_dir: Path, session_id: str | None, topic: str) -> int:
    """Fold this session's pre-bind fallback worklog into the bound topic.

    Before a session binds, its hook events land in the per-session
    `session-<key[:24]>` fallback bucket. At bind time the session's pending
    queue is flushed and the fallback worklog is merged into
    `<topic>.worklog.jsonl`, so the trail is not split across buckets and the
    printed selected context already includes pre-bind events. Best-effort:
    any failure returns 0 and never blocks binding.
    """
    fallback = session_fallback_topic(session_id)
    if not fallback or fallback == topic:
        return 0
    try:
        import worklog_queue
    except ImportError:
        return 0
    try:
        key = session_key(session_id)
        if key:
            worklog_queue.flush_session(worklog_queue.session_queue_dir(spec_dir, key))
        source = spec_dir / f"{fallback}.worklog.jsonl"
        if not source.exists():
            return 0
        return worklog_queue.migrate_worklog(spec_dir, source.name, f"{topic}.worklog.jsonl")
    except (OSError, worklog_queue.QueueError):
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
    mirror_restore(spec_dir, workspace)
    spec_file = spec_dir / f"{topic}.txt"
    seeded = False
    if not spec_file.exists():
        if not args.create:
            raise SystemExit(f"Topic {topic!r} does not exist; pass --create to seed it.")
        spec_file.write_text(f"topic: {topic}\n")
        seeded = True

    binding = session_topic_path(spec_dir, key)
    binding.write_text(topic + "\n")
    migrated = migrate_session_fallback_worklog(spec_dir, args.session_id, topic)
    mirror_sync(spec_dir, workspace, topic)
    print(f"session topic: {topic}")
    print(f"session_id: {key}")
    print(f"binding: {binding}")
    print(f"{'seeded' if seeded else 'exists'}: {spec_file}")
    if migrated:
        print(f"migrated: {migrated} pre-bind worklog events from {session_fallback_topic(args.session_id)}")
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
    mirror_sync(spec_dir, workspace, topic)

    print(f"active topic: {topic}")
    print(f"pointer: {spec_dir / '_active_topic.txt'}")
    print(f"{'seeded' if seeded else 'exists'}: {spec_file}")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    spec_dir = spec_dir_for(workspace)
    source = safe_topic(args.source_topic)
    dest = safe_topic(args.dest_topic)
    if source == dest:
        raise SystemExit("Refusing to merge a topic into itself.")
    if dest == DEFAULT_TOPIC:
        raise SystemExit(f"Refusing to merge into the generic topic {DEFAULT_TOPIC!r}; choose a named topic.")

    worklog_queue = None
    flush_result = None
    if not args.dry_run:
        try:
            import worklog_queue as loaded_worklog_queue
        except ImportError as err:
            raise SystemExit(f"Unable to load worklog queue before merge: {err}") from err
        worklog_queue = loaded_worklog_queue
        try:
            flush_result = worklog_queue.flush_spec_dir(spec_dir)
        except (OSError, worklog_queue.QueueError) as err:
            raise SystemExit(f"Unable to flush pending worklog queues before merge: {err}") from err

    if not topic_material_exists(spec_dir, source):
        raise SystemExit(f"Source topic {source!r} does not exist; expected {source}.txt or {source}.worklog.jsonl.")

    source_spec = spec_dir / f"{source}.txt"
    source_worklog = spec_dir / f"{source}.worklog.jsonl"
    source_sentinel = spec_dir / f"{source}.no_context"
    dest_spec = spec_dir / f"{dest}.txt"
    dest_worklog = spec_dir / f"{dest}.worklog.jsonl"
    bindings = source_topic_bindings(spec_dir, source)
    active_pointer = spec_dir / "_active_topic.txt"
    active_rewrite = pointer_targets_topic(active_pointer, source)

    if args.dry_run:
        print(f"dry-run merge: {source} -> {dest}")
        print(f"workspace: {workspace}")
        print(f"spec_dir: {spec_dir}")
        print("would flush pending worklog queues before merging")
        print(f"would {'append into' if dest_spec.exists() else 'create'} dest spec: {dest_spec}")
        if source_spec.exists():
            print(f"would append source spec under merge separator: {source_spec}")
        if source_worklog.exists():
            print(
                f"would merge worklogs by ts under the existing 200-line write cap: {source_worklog} -> {dest_worklog}"
            )
        else:
            print(f"no source worklog to merge: {source_worklog}")
        for binding in bindings:
            print(f"would rewrite session binding: {binding}")
        if active_rewrite:
            print(f"would rewrite active pointer: {active_pointer}")
        if source_sentinel.exists():
            print(f"would remove source no-context sentinel without propagating it: {source_sentinel}")
        for path in (source_spec, source_worklog, source_sentinel):
            if path.exists():
                print(f"would remove source file: {path}")
        return 0

    source_sentinel_existed = source_sentinel.exists()
    migrated = 0
    if source_worklog.exists():
        try:
            migrated = worklog_queue.migrate_worklog(spec_dir, source_worklog.name, dest_worklog.name)
        except (OSError, worklog_queue.QueueError) as err:
            raise SystemExit(f"Unable to merge worklog files: {err}") from err

    merged_at = utc_merge_timestamp()
    dest_spec, dest_existed, source_spec_existed = append_merged_spec(spec_dir, source, dest, merged_at)
    for binding in bindings:
        binding.write_text(dest + "\n")
    if active_rewrite:
        active_pointer.write_text(dest + "\n")
    for path in (source_spec, source_sentinel):
        if path.exists():
            path.unlink()

    print(f"merged topic: {source} -> {dest}")
    print(
        "flushed pending worklog events: "
        f"{flush_result.flushed} (duplicates: {flush_result.duplicates}, pending: {flush_result.pending}, errors: {flush_result.errors})"
    )
    print(f"{'updated' if dest_existed else 'created'} dest spec: {dest_spec}")
    if source_spec_existed:
        print(f"appended source spec under separator: {merged_at}")
    print(f"migrated worklog events: {migrated}")
    for binding in bindings:
        print(f"rewrote session binding: {binding}")
    if active_rewrite:
        print(f"rewrote active pointer: {active_pointer}")
    if source_sentinel_existed:
        print(f"removed source no-context sentinel without propagation: {source_sentinel}")
    mirror_forget(workspace, source)
    mirror_sync(spec_dir, workspace, dest)
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    """Record one structured insight into the bound topic's worklog.

    Notes are the deliberate capture surface for decisions, insights, ideas,
    and constraints that leave no failing command behind — `,ai-kb harvest`
    turns them into durable-memory candidates, and `question` notes stay
    task-scoped context. Events ride the same crash-safe queue as tool
    worklogs, flushed synchronously so the note lands before the CLI exits.
    """
    workspace = workspace_path(args.workspace)
    spec_dir = spec_dir_for(workspace)
    mirror_restore(spec_dir, workspace)
    topic = resolve_selected_topic(spec_dir, workspace, args.topic, args.session_id)
    text = " ".join(args.text.split()).strip()
    if not text:
        raise SystemExit("note text must not be empty")
    if len(text) > NOTE_TEXT_MAX_CHARS:
        raise SystemExit(f"note text exceeds {NOTE_TEXT_MAX_CHARS} characters; front-load the insight instead")
    try:
        import worklog_queue
    except ImportError as err:
        raise SystemExit(f"Unable to load worklog queue: {err}") from err

    key = session_key(args.session_id) or f"topic-{topic}"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace),
        "topic": topic,
        "event": "note",
        "note_kind": args.kind,
        "text": text,
        "refs": ",".join(args.ref or []),
    }
    spec_dir.mkdir(parents=True, exist_ok=True)
    worklog_path = spec_dir / f"{topic}.worklog.jsonl"
    try:
        receipt = worklog_queue.enqueue(
            spec_dir,
            key,
            topic,
            worklog_path,
            {k: v for k, v in entry.items() if v not in (None, "")},
            start_worker=False,
        )
        worklog_queue.run_worker(receipt.queue_dir)
    except (OSError, worklog_queue.QueueError) as err:
        raise SystemExit(f"Unable to record note: {err}") from err
    mirror_sync(spec_dir, workspace, topic)
    print(f"note recorded: {args.kind} -> {topic}")
    print(f"worklog: {worklog_path}")
    if args.kind == "question":
        print("questions stay task-scoped context; they are not harvested as durable candidates")
    else:
        print("surface it later with: ,ai-kb harvest")
    return 0


def cmd_wipe_current(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    spec_dir = spec_dir_for(workspace)
    topic = resolve_selected_topic(spec_dir, workspace, args.topic, args.session_id)
    removed = wipe_topic(spec_dir, topic, args.dry_run)
    if not args.dry_run:
        mirror_forget(workspace, topic)

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

    merge = subcommands.add_parser(
        "merge",
        help="Merge a duplicate topic into a destination topic.",
        description=(
            "Merge <source-topic> into <dest-topic>. Pending worklog queues are flushed before the real merge. "
            "Source .no_context is deleted, not propagated, so merging cannot silently suppress destination context."
        ),
    )
    merge.add_argument("source_topic", help="Existing source topic with a spec or worklog file.")
    merge.add_argument(
        "dest_topic", help="Destination named topic; created if missing. The generic 'current' is rejected."
    )
    merge.add_argument("--dry-run", action="store_true", help="Print the full merge plan without touching files.")
    merge.add_argument(
        "--workspace",
        default=None,
        help="Workspace path. Defaults to the current directory.",
    )
    merge.set_defaults(func=cmd_merge)

    note = subcommands.add_parser(
        "note",
        help="Record a structured insight (fact/gotcha/pattern/anti_pattern/recipe/principle/question) into the topic worklog.",
        description=(
            "Deliberate capture surface for insights that leave no failing command behind. "
            "Kinds are the `,ai-kb` capsule kinds plus task-scoped `question`; the kind is the knowledge type, "
            "and living in the worklog (not the KB) is what marks it unverified. "
            "Non-question notes become `,ai-kb harvest` candidates; front-load literal identifiers a future query would use."
        ),
    )
    note.add_argument("kind", choices=NOTE_KINDS, help="Structured note category.")
    note.add_argument("text", help="The insight itself; front-load exact symbols, paths, and terms.")
    note.add_argument(
        "--ref",
        action="append",
        help="Evidence anchor such as path:line, command, or URL (repeat for multiple).",
    )
    add_shared_options(note, subcommand=True)
    note.set_defaults(func=cmd_note)

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
