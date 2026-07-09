#!/usr/bin/env python3
"""Inject active topic context at the start of Cursor/Claude sessions."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from hook_common import (
    emit,
    is_default_branch_workspace,
    is_named_topic,
    is_session_topic,
    read_payload,
    session_key,
    session_topic_path,
    topic_paths,
    transcript_tail,
)

MAX_SPEC_CHARS = 2500
MAX_WORKLOG_CHARS = 3000
MAX_WORKLOG_LINES = 12
DISABLE_CONTEXT_ENV = "AGENT_HOOK_CONTEXT"
DISABLE_CONTEXT_VALUES = {"0", "false", "no", "off", "disabled"}

PREFIX_REL_PATH = "tmux/agent_prompts/prefix.txt"
MAX_PREFIX_CHARS = 3000

WARMSTART_LIMIT = 3
WARMSTART_QUERY_CHARS = 600
WARMSTART_BODY_CHARS = 240
WARMSTART_SEARCH_TIMEOUT = 6
CROSS_PROJECT_SCOPES = {"domain", "universal"}
TOPIC_BUCKET_LIMIT = 8
TOPIC_BUCKET_SUMMARY_CHARS = 180
TOPIC_BUCKET_TIME_FORMAT = "%Y-%m-%d %H:%M"
# Relative relevance floor: drop hits far worse than the best hit (see the same
# constant + rationale in dot_pi/.../ai-kb-recall.ts). bm25() is SQLite's negative
# log score (smaller = better), so we negate to "larger = better" before comparing.
WARMSTART_RELEVANCE_FLOOR_FRACTION = 0.6

AIKB_REMINDER = (
    "### Durable Memory (,ai-kb)\n"
    "Recall before non-trivial work by searching with the ACTUAL task as the query: "
    '`,ai-kb search "<the concrete thing you are about to do>" --limit 5 --json` '
    "(a precise task query returns the most relevant capsules). "
    "Persist verified, reusable insights before finishing with DELIBERATE metadata "
    "(each field drives retrieval/curation — do not leave defaults): "
    "`,ai-kb remember --title <searchable, names the exact symbol/file/error> "
    "--body <front-loaded with the literal identifiers a future query would use> "
    "--kind <fact|gotcha|pattern|anti_pattern|recipe|principle|doc> "
    "--scope <workspace|project|domain|universal> --source <path:line|command|URL you verified> "
    '--confidence <0..1, honest> --domain <tag>` — add `--workspace "$(pwd)"` only for '
    "workspace/project scope. See the ai-kb skill for the full write contract."
)


def aikb_warmstart(workspace: Path, query: str, injected_ids: list[str] | None = None) -> str:
    """Inject a small, relevance-gated block of durable learnings at session start.

    Fires only for named-topic sessions (gated by the caller). Uses the active
    topic spec as the query and the bm25 lane (no embedder) to stay fast and
    dependency-light inside the hook timeout. Keeps only capsules that are local
    to this workspace or are deliberately cross-project (domain/universal scope),
    so a large or unrelated KB cannot stuff the context with noise. Returns an
    empty string on any failure or when no relevant capsule clears the gate.
    """
    aikb = shutil.which(",ai-kb")
    query = " ".join(query.split())[:WARMSTART_QUERY_CHARS].strip()
    if not aikb or not query:
        return ""

    try:
        result = subprocess.run(
            [
                aikb,
                "search",
                query,
                "--limit",
                str(WARMSTART_LIMIT * 2),
                "--mode",
                "bm25",
                "--workspace",
                str(workspace),
                "--json",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=WARMSTART_SEARCH_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""

    if result.returncode != 0 or not result.stdout.strip():
        return ""

    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""

    rows = _apply_relevance_floor(rows if isinstance(rows, list) else [])

    workspace_str = str(workspace)
    selected: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if len(selected) >= WARMSTART_LIMIT:
            break
        scope = str(row.get("scope") or "")
        same_workspace = str(row.get("workspace_path") or "") == workspace_str
        if not same_workspace and scope not in CROSS_PROJECT_SCOPES:
            continue
        title = " ".join(str(row.get("title") or "").split()).strip()
        if not title:
            continue
        body = " ".join(str(row.get("body") or "").split()).strip()
        if len(body) > WARMSTART_BODY_CHARS:
            body = body[:WARMSTART_BODY_CHARS].rstrip() + "…"
        kind = str(row.get("kind") or "note")
        line = f"- **{title}** ({kind})"
        if body:
            line += f": {body}"
        selected.append(line)
        capsule_id = str(row.get("id") or "")
        if injected_ids is not None and capsule_id:
            injected_ids.append(capsule_id)

    if not selected:
        return ""

    return "\n".join(
        [
            "### Relevant Learnings (,ai-kb)",
            "Surfaced from durable memory for this topic; verify before relying on them, "
            "and search again with your specific task for more.",
            *selected,
        ]
    )


def _apply_relevance_floor(rows: list) -> list:
    """Drop bm25 hits whose relevance is far below the best hit's.

    Warm-start uses --mode bm25, so bm25_score (negative; smaller = better) is the
    real relevance signal. A relative gap to the best hit is stable across queries
    where an absolute threshold is not. Keeps the top hit always and keeps any row
    missing a score so a scoring gap never swallows everything. Assumes best-first.
    """
    if len(rows) <= 1:
        return rows
    best = None
    for row in rows:
        raw = row.get("bm25_score")
        if isinstance(raw, (int, float)):
            best = -float(raw)
            break
    if best is None or best <= 0:
        return rows
    floor = best * WARMSTART_RELEVANCE_FLOOR_FRACTION
    kept = []
    for row in rows:
        raw = row.get("bm25_score")
        if not isinstance(raw, (int, float)) or -float(raw) >= floor:
            kept.append(row)
    return kept


def prefix_block() -> str:
    """Inject the verification-discipline prefix at session start.

    Reads the same `prefix.txt` the tmux agent-prompt wrap pastes manually, so the
    grounding discipline is in context from the first turn without the user having
    to paste it. The file is the single source of truth and now holds only the
    discipline core (no forward-pointing "User prompt follows:" line). This path
    injects a standalone sessionStart context block — the user's first prompt is a
    separate later message, not glued after this text — so it frames the discipline
    as applying to subsequent prompts rather than claiming one follows.
    Returns an empty string if the file is missing or empty.
    """
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(config_home) / PREFIX_REL_PATH
    try:
        text = path.read_text(errors="replace").strip()
    except OSError:
        return ""
    if not text:
        return ""
    core = text[:MAX_PREFIX_CHARS]
    return f"{core}\n\nApply the discipline above to this session's prompts."


def collapse(text: str, max_chars: int) -> str:
    flat = " ".join(text.split()).strip()
    if len(flat) <= max_chars:
        return flat
    return flat[:max_chars].rstrip() + "…"


def topic_bucket_mtime(path: Path) -> float:
    mtime = 0.0
    try:
        mtime = path.stat().st_mtime
    except OSError:
        pass
    worklog = path.parent / f"{path.stem}.worklog.jsonl"
    try:
        mtime = max(mtime, worklog.stat().st_mtime)
    except OSError:
        pass
    return mtime


def format_topic_timestamp(timestamp: float) -> str:
    if timestamp <= 0:
        return "unknown time"
    return datetime.fromtimestamp(timestamp).strftime(TOPIC_BUCKET_TIME_FORMAT)


def format_topic_age(timestamp: float, now: float) -> str:
    if timestamp <= 0:
        return "unknown age"
    delta = max(0.0, now - timestamp)
    if delta < 90:
        return "just now"
    minutes = int(delta // 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = int(delta // 3600)
    if hours < 48:
        return f"{hours}h ago"
    days = int(delta // 86400)
    return f"{days}d ago"


def topic_bucket_files(spec_dir: Path) -> list[Path]:
    files = []
    for path in spec_dir.glob("*.txt"):
        topic = path.stem
        if path.name == "_active_topic.txt" or topic.startswith("."):
            continue
        if not is_named_topic(topic):
            continue
        files.append(path)
    return sorted(files, key=topic_bucket_mtime, reverse=True)


def topic_summary(path: Path) -> str:
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        lines = []
    for line in lines:
        if line.lower().startswith("summary:"):
            summary = collapse(line[len("summary:") :], TOPIC_BUCKET_SUMMARY_CHARS).strip()
            if summary:
                return summary
            break
    fields: list[str] = []
    for label, prefix in (("target", "target:"), ("action", "action:")):
        for line in lines:
            if line.lower().startswith(prefix):
                fields.append(f"{label}={collapse(line[len(prefix) :], TOPIC_BUCKET_SUMMARY_CHARS).strip()}")
                break
    return "; ".join(fields) if fields else "no summary"


def topic_buckets_context(spec_dir: Path, payload: dict) -> str:
    key = session_key(payload)
    session_arg = key or "<session-id>"
    buckets = topic_bucket_files(spec_dir)[:TOPIC_BUCKET_LIMIT]
    lines = [
        "### Topic Buckets",
        "Agent should bind automatically when exactly one bucket clearly matches the user's request.",
        "Ask the user only when multiple buckets plausibly match, or when joining vs creating changes the work thread.",
    ]
    if not buckets:
        lines.extend(
            [
                "No existing topic buckets.",
                "Agent should create a new bucket automatically for this request:",
                f"`,agent-memory select <new-topic> --create --session-id {session_arg}`",
            ]
        )
        return "\n".join(lines)

    lines.append("Existing buckets (newest first by last update):")
    now = time.time()
    for path in buckets:
        mtime = topic_bucket_mtime(path)
        timestamp = format_topic_timestamp(mtime)
        age = format_topic_age(mtime, now)
        lines.append(f"- `{path.stem}` — updated {timestamp} ({age}); {topic_summary(path)}")
    lines.extend(
        [
            f"Bind this session with: `,agent-memory select <topic> --session-id {session_arg}`.",
            f"If none match, create one with: `,agent-memory select <new-topic> --create --session-id {session_arg}`.",
        ]
    )
    return "\n".join(lines)


def should_offer_topic_buckets(spec_path: Path, topic: str, no_session_key_default_branch: bool = False) -> bool:
    spec_dir = spec_path.parent
    return (
        no_session_key_default_branch
        or is_session_topic(topic)
        or (spec_dir / "_active_topic.txt").exists()
        or not spec_path.exists()
    )


REVIEW_CONCLUSION_HEADINGS = (
    "verified facts",
    "findings",
    "verdict",
    "inline comments",
    "pending review draft",
    "things checked",
    "net",
)


def context_disabled(spec_path: Path, topic: str) -> bool:
    env_value = os.environ.get(DISABLE_CONTEXT_ENV, "").strip().lower()
    if env_value in DISABLE_CONTEXT_VALUES:
        return True

    spec_dir = spec_path.parent
    return (spec_dir / "_no_session_context").exists() or (spec_dir / f"{topic}.no_context").exists()


def is_review_topic(topic: str, text: str) -> bool:
    return topic.startswith("review") or "\ntarget: PR " in f"\n{text}"


def neutral_review_spec(text: str, spec_path: Path) -> str:
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


def spec_context(spec_path: Path, topic: str) -> str:
    text = spec_path.read_text(errors="replace").strip()
    if is_review_topic(topic, text):
        return neutral_review_spec(text, spec_path)

    if len(text) <= MAX_SPEC_CHARS:
        return text

    return (
        f"Active topic spec omitted because it is {len(text)} characters, "
        f"exceeding the {MAX_SPEC_CHARS}-character injection limit. "
        f"Read `{spec_path}` before relying on prior session context."
    )


def main() -> None:
    payload = read_payload()
    workspace, topic, spec_path, worklog_path = topic_paths(payload)

    if context_disabled(spec_path, topic):
        emit({})
        return

    parts = [
        "## Agent Hook Context",
        f"- Workspace: `{workspace}`",
        f"- Active topic: `{topic}`",
    ]

    prefix = prefix_block()
    if prefix:
        parts.extend(["", prefix])

    spec_dir = spec_path.parent
    key = session_key(payload)
    has_session_binding = bool(key and session_topic_path(spec_dir, key).exists())
    no_session_key_default_branch = not key and is_default_branch_workspace(workspace)
    if not has_session_binding and should_offer_topic_buckets(spec_path, topic, no_session_key_default_branch):
        parts.extend(["", topic_buckets_context(spec_dir, payload)])
        parts.extend(["", AIKB_REMINDER])
        context = "\n".join(parts)
        emit(
            {
                "additional_context": context,
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                },
            }
        )
        return

    is_review = False
    spec_text_source = ""
    if spec_path.exists():
        spec_text_source = spec_path.read_text(errors="replace")
        is_review = is_review_topic(topic, spec_text_source)
        spec_text = spec_context(spec_path, topic)
        if spec_text:
            parts.extend(["", "### Active Topic Spec", spec_text])

    worklog = "" if is_review else transcript_tail(worklog_path, lines=MAX_WORKLOG_LINES, limit=MAX_WORKLOG_CHARS)
    if worklog:
        parts.extend(["", "### Recent Hook Worklog", worklog])

    if is_named_topic(topic) and not is_review and spec_text_source.strip():
        injected_ids: list[str] = []
        warmstart = aikb_warmstart(workspace, spec_text_source, injected_ids)
        if warmstart:
            parts.extend(["", warmstart])
        # Record injected capsule ids so the per-turn recall hook
        # (perturn_recall.py) never re-injects them this session.
        if injected_ids and key:
            seen_path = spec_path.parent / f".recall-seen-{key}.json"
            try:
                seen_path.parent.mkdir(parents=True, exist_ok=True)
                seen_path.write_text(json.dumps(sorted(set(injected_ids))))
            except OSError:
                pass

    parts.extend(["", AIKB_REMINDER])

    context = "\n".join(parts)
    emit(
        {
            "additional_context": context,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            },
        }
    )


if __name__ == "__main__":
    main()
