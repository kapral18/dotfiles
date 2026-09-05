#!/usr/bin/env python3
"""Inject active topic context at the start of Cursor/Claude sessions."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from hook_common import (
    agent_depth,
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
AI_EMBED_WARM_ENV = "AI_EMBED_WARM"
TRUE_VALUES = {"1", "true", "yes", "on"}
EMBED_WARM_TIMEOUT_SECONDS = 4

# Reconcile GitHub identity so PR-discovery / authorship checks below are anchored to
# the verified `gh` principal, not assumed from `git config user.email`. Failed commands
# or empty output are silent — `gh_identity_line` returns "" and the block is omitted.
# Without this line, agents that assume "auth principal != upstream owner" can chase
# the wrong repo for five rounds before discovering `gh auth status` (see failure-modes doc).
GH_IDENTITY_TIMEOUT_SECONDS = 2

PREFIX_REL_PATH = "tmux/agent_prompts/prefix.txt"
# Sized to hold the whole prefix.txt discipline core with headroom. A silent mid-sentence
# truncation here drops the tail rules (time neutrality, line-shape) from every session,
# and greps against the file still find them — so raise this whenever prefix.txt grows.
MAX_PREFIX_CHARS = 6000

WARMSTART_LIMIT = 3
WARMSTART_QUERY_CHARS = 600
WARMSTART_SEARCH_TIMEOUT = 6
TOPIC_BUCKET_LIMIT = 8
TOPIC_BUCKET_SUMMARY_CHARS = 180
TOPIC_BUCKET_TIME_FORMAT = "%Y-%m-%d %H:%M"
# Relative relevance floor: drop hits far worse than the best hit (see the same
# constant + rationale in dot_pi/.../ai-kb-recall.ts). bm25() is SQLite's negative
# log score (smaller = better), so we negate to "larger = better" before comparing.
WARMSTART_RELEVANCE_FLOOR_FRACTION = 0.6

AIKB_REMINDER = (
    "### Durable Memory (,ai-kb)\n"
    "The `k-agent-smol` operator (~/.agents/skills/k-ai-kb/references/smol-operator.md) owns the KB boundary in both directions. "
    "Recall before non-trivial work by delegating the ACTUAL task as a recall query to `k-agent-smol` (judge mode, query-recall variant); "
    "fold in only its returned lines (`NONE` = inject nothing). "
    "Persist verified, reusable insights before finishing by handing `k-agent-smol` (scribe mode) the one-line insight, "
    "evidence anchors, and suggested kind/scope; scribe owns search-first dedupe, metadata selection, and read-back. "
    "Do not run `,ai-kb search`/`get`/`remember` inline in the parent session; "
    "only when no isolated spawn exists, apply the inline fallback per the k-ai-kb skill "
    "(~/.agents/skills/k-ai-kb/references/cli.md) with every metadata field deliberate."
)
NO_PERTURN_RECALL_NOTICE = (
    "### Recall Notice\n"
    "This harness has no automatic per-turn `,ai-kb` recall: only session-start context is injected. "
    "Delegate a recall query to the `k-agent-smol` operator (judge mode) whenever the task shifts — "
    "inline `,ai-kb search` only where no isolated spawn exists — "
    "and record mid-task decisions/ideas with `,agent-memory note` so they survive the session."
)


def warm_resident_embedder(payload: dict) -> None:
    """Bounded, fail-open warmup for adapters that also invoke per-turn recall."""
    if agent_depth() == "fast":
        return
    if not per_turn_recall_requested(payload):
        return
    client = Path.home() / "lib/,ai-kb/embed_client.py"
    if not client.is_file():
        return
    try:
        subprocess.run(
            [sys.executable, str(client), "ensure", "--timeout", str(EMBED_WARM_TIMEOUT_SECONDS)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=EMBED_WARM_TIMEOUT_SECONDS + 1,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def per_turn_recall_requested(payload: dict) -> bool:
    """True when the invoking adapter has per-turn recall wiring.

    Adapters with per-turn retrieval (Claude, Gemini, OpenCode, Copilot,
    Codex, Cursor, Pi) request the resident warm-up via `AI_EMBED_WARM=1` or the
    `warm_embedder` payload flag; an adapter that sends neither has no
    per-turn hook surface, so its mid-session recall must come from a
    delegated k-agent-smol recall query (the Recall Notice below).
    """
    if os.environ.get(AI_EMBED_WARM_ENV, "").strip().lower() in TRUE_VALUES:
        return True
    return payload.get("warm_embedder") is True


# Staging contract tokens, pinned by the pi/omp mirror parity test.
SMOL_CONTRACT_PATH = "~/.agents/skills/k-ai-kb/references/smol-operator.md"
STAGING_HEADER = "### ,ai-kb candidates staged"


def seen_file_for(spec_path: Path, session_key_value: str) -> Path:
    return spec_path.parent / f".recall-seen-{session_key_value}.json"


def candidates_file_for(spec_path: Path, session_key_value: str) -> Path:
    return spec_path.parent / f".recall-candidates-{session_key_value}.json"


def staged_file_for(spec_path: Path, session_key_value: str) -> Path:
    return spec_path.parent / f".recall-staged-{session_key_value}.json"


def pointed_file_for(spec_path: Path, session_key_value: str) -> Path:
    return spec_path.parent / f".recall-pointed-{session_key_value}.json"


def already_pointed(pointed_path: Path, topic: str) -> bool:
    """True when this session already received the pointer for `topic`."""
    try:
        marker = json.loads(pointed_path.read_text())
        return marker.get("topic") == topic and marker.get("pointed", True) is True
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        return False


def load_seen(path: Path | None) -> set[str]:
    if path is None:
        return set()
    try:
        return set(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError, TypeError):
        return set()


def save_seen(path: Path | None, seen: set[str]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(seen)))
    except OSError:
        pass


def stage_candidates(rows: list, seen: set[str], spec_path: Path, key: str, *, warm_start: bool = False) -> str:
    """Write gate-passing rows to the candidates file; return the pointer block.

    The cross-repo scope gate is owned by `,ai-kb search --workspace-gate`.
    This hook filters ids k-agent-smol already admitted (seen-file) and points the
    parent at the staged set once per session-topic binding transition (pointed marker):
    a judge spawn per prompt cost more than the lines it admitted, so later
    turns stage silently and the pull path owns mid-task recall. A new binding
    may re-point unadmitted ids. Returns "" when nothing new is staged, the
    session was already pointed at this topic, or any state write fails
    (fail-open: no partial pointer without a file).
    """
    if not key:
        return ""
    pointed_path = pointed_file_for(spec_path, key)
    topic = spec_path.stem
    pointed = already_pointed(pointed_path, topic)
    if not pointed:
        try:
            pointed_path.parent.mkdir(parents=True, exist_ok=True)
            pointed_path.write_text(json.dumps({"topic": topic, "pointed": False}))
        except OSError:
            return ""
    warm_path = spec_path.parent / f".recall-warm-{key}.json"
    if warm_start:
        rows = rows[:WARMSTART_LIMIT]
        try:
            warm_path.write_text(json.dumps({"topic": topic, "rows": rows}))
        except OSError:
            return ""
    elif rows:
        try:
            warm = json.loads(warm_path.read_text())
            if warm.get("topic") == topic and isinstance(warm.get("rows"), list):
                rows = [*warm["rows"][:WARMSTART_LIMIT], *rows]
        except (OSError, json.JSONDecodeError, AttributeError, TypeError):
            pass
    # Startup contributes at most three rows; each later retrieval replaces its own lane.
    # A current retrieval may refresh the same id without growing a cumulative history.
    by_id = {str(row.get("id")): row for row in rows if row.get("id")}
    candidates = [row for key_id, row in by_id.items() if key_id not in seen]
    if not candidates:
        return ""
    staged_path = staged_file_for(spec_path, key)
    staged = load_seen(staged_path)
    candidate_ids = {str(row.get("id")) for row in candidates}
    if pointed and not candidate_ids - staged:
        return ""
    candidates_path = candidates_file_for(spec_path, key)
    try:
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        candidates_path.write_text(json.dumps(candidates, indent=2))
    except OSError:
        return ""
    # Marker first, ledger second: if the marker write fails, the ids stay unstaged so the next
    # turn retries instead of silently consuming this session's one pointer.
    if not pointed:
        try:
            pointed_path.write_text(json.dumps({"topic": topic}))
        except OSError:
            return ""
    save_seen(staged_path, staged | candidate_ids)
    if pointed:
        return ""
    worklog_path = spec_path.with_name(spec_path.stem + ".worklog.jsonl")
    return "\n".join(
        [
            STAGING_HEADER,
            f"{len(candidates)} candidate(s): {candidates_path}",
            f"Session state: {spec_path} + {worklog_path}",
            "This pointer fires once per session-topic binding; later turns stage new rows into the same file for pull-path recall.",
            f"Delegate to the `k-agent-smol` subagent (judge mode) per {SMOL_CONTRACT_PATH}, passing those paths and the current prompt;"
            " inject only its returned lines (`NONE` = inject nothing).",
            "When the `k-agent-smol` profile is unreachable (e.g. a fixed Task subagent set), spawn a generic isolated subagent"
            " on the memory-band model with the k-agent-smol operator contract per the k-ai-kb skill;"
            " never a harness-CLI one-shot and never the subagent type's own default model.",
            "Do not read the candidates file into this context.",
        ]
    )


def aikb_warmstart(workspace: Path, query: str) -> list:
    """Retrieve complete relevance-gated candidates for startup judgment.

    Fires only for named-topic sessions (gated by the caller). Uses the active
    topic spec as the query and the bm25 lane (no embedder) to stay fast and
    dependency-light inside the hook timeout. `--workspace-gate` makes the KB
    itself keep only capsules that are local to this workspace or deliberately
    cross-project (domain/universal scope), so a large or unrelated KB cannot
    stuff the context with noise. Returns an empty list on any failure or
    when no relevant capsule clears the gate.
    """
    aikb = shutil.which(",ai-kb")
    query = " ".join(query.split())[:WARMSTART_QUERY_CHARS].strip()
    if not aikb or not query:
        return []

    try:
        result = subprocess.run(
            [
                aikb,
                "search",
                "--query-stdin",
                "--limit",
                str(WARMSTART_LIMIT * 2),
                "--mode",
                "bm25",
                "--workspace",
                str(workspace),
                "--workspace-gate",
                "--json",
            ],
            capture_output=True,
            check=False,
            input=query,
            text=True,
            timeout=WARMSTART_SEARCH_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    rows = _apply_relevance_floor(rows if isinstance(rows, list) else [])

    # Keep complete rows: only the isolated judge admits memory into parent context.
    return [row for row in rows if row.get("id") and str(row.get("title") or "").strip()][:WARMSTART_LIMIT]


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


def gh_identity_line() -> str:
    """One-line `gh api user` probe, prefixed into every SessionStart context block.

    Failures are silent (return empty string). The hook's timeout is the same
    `EMBED_WARM_TIMEOUT_SECONDS` family — kept short because this is best-effort
    context, not a gate.
    """
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            check=False,
            text=True,
            timeout=GH_IDENTITY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    login = result.stdout.strip()
    if not login:
        return ""
    # Account-type / host are deferred: per-harness adapters can decorate later if needed.
    return f"### GitHub identity\n- `gh api user` -> `{login}` (run `gh auth status` for the active host/scopes)"


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
        heading = re.sub(r"^#{1,6}\s+", "", line.strip())
        heading = re.sub(r"\s+#+\s*$", "", heading)
        normalized = heading.rstrip(":").lower()
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
    """Mirrors agent_memory.py's bounded_or_omitted — change both together.

    Applies the shared oversized-spec contract to already-final text (review
    text must already be sanitized by neutral_review_spec() before reaching
    here). Content is never truncated mid-context: once it exceeds the bound
    it is replaced wholesale with a pointer, so a sanitized-but-still-huge
    review body cannot leak past the size limit just because it is "already
    clean".
    """
    if len(text) <= MAX_SPEC_CHARS:
        return text

    return (
        f"Active topic spec omitted because it is {len(text)} characters, "
        f"exceeding the {MAX_SPEC_CHARS}-character injection limit. "
        f"Read `{spec_path}` before relying on prior session context."
    )


def spec_context(spec_path: Path, topic: str) -> str:
    text = spec_path.read_text(errors="replace").strip()
    if is_review_topic(topic, text):
        return bounded_or_omitted(neutral_review_spec(text, spec_path), spec_path)

    return bounded_or_omitted(text, spec_path)


def context_for_harness(parts: list[str], optional_parts: list[tuple[int, str]]) -> str:
    """Cursor carriers cap trimmed context at 10,000 JavaScript UTF-16 units.

    Omit whole optional artifacts, retaining a read pointer. Never slice a rule,
    spec, or JSONL row to fit. Other harnesses retain their existing envelope.
    """
    context = "\n".join(parts)
    if os.environ.get("AGENT_HOOK_HARNESS") != "cursor":
        return context
    selected = list(parts)
    for index, pointer in optional_parts:
        if len(context.encode("utf-16-le")) // 2 <= 10_000:
            return context
        selected[index] = pointer
        context = "\n".join(selected)
    if len(context.encode("utf-16-le")) // 2 > 10_000:
        raise ValueError(
            "Required startup instructions exceed Cursor's 10,000 UTF-16-unit context limit; refusing partial instructions"
        )
    return context


def main() -> None:
    payload = read_payload()
    if os.environ.get("AGENT_HOOK_OUTPUT") == "antigravity" and payload.get("invocation_num") != 0:
        emit({})
        return
    workspace, topic, spec_path, worklog_path = topic_paths(payload)

    # Self-heal named topics from the persistent mirror after a /tmp wipe
    # (macOS reboot), then re-resolve: a restored _active_topic.txt or spec
    # can change which topic this session loads. Best-effort by design.
    try:
        import spec_mirror
    except ImportError:
        spec_mirror = None
    if spec_mirror is not None and spec_mirror.restore_topics(spec_path.parent, workspace):
        workspace, topic, spec_path, worklog_path = topic_paths(payload)

    if context_disabled(spec_path, topic):
        emit({"context_disabled": True} if payload.get("context_status") is True else {})
        return

    try:
        import worklog_queue
    except ImportError as err:
        print(f"[agent-worklog] session-start flush failed: {err}", file=sys.stderr)
    else:
        try:
            flush_result = worklog_queue.flush_spec_dir(spec_path.parent)
            if flush_result.errors or flush_result.pending:
                print(
                    f"[agent-worklog] session-start flush incomplete: "
                    f"pending={flush_result.pending} errors={flush_result.errors}",
                    file=sys.stderr,
                )
        except (OSError, ValueError, worklog_queue.QueueError) as err:
            print(f"[agent-worklog] session-start flush failed: {err}", file=sys.stderr)

    warm_resident_embedder(payload)

    optional_parts: list[tuple[int, str]] = []
    parts = [
        "## Agent Hook Context",
        f"- Workspace: `{workspace}`",
        f"- Active topic: `{topic}`",
    ]

    prefix = prefix_block()
    if prefix:
        parts.extend(["", prefix])

    gh_identity = gh_identity_line()
    if gh_identity:
        parts.extend(["", gh_identity])

    spec_dir = spec_path.parent
    key = session_key(payload)
    if key:
        stage_candidates([], set(), spec_path, key)
    has_session_binding = bool(key and session_topic_path(spec_dir, key).exists())
    no_session_key_default_branch = not key and is_default_branch_workspace(workspace)
    if not has_session_binding and should_offer_topic_buckets(spec_path, topic, no_session_key_default_branch):
        parts.extend(["", topic_buckets_context(spec_dir, payload)])
        optional_parts.append(
            (
                len(parts) - 1,
                f"### Topic Buckets\nBucket details omitted for Cursor’s context limit. Inspect `{spec_dir}` and bind with `,agent-memory select <topic> --session-id {key or '<session-id>'}` before relying on prior state.",
            )
        )
        if not per_turn_recall_requested(payload):
            parts.extend(["", NO_PERTURN_RECALL_NOTICE])
        parts.extend(["", AIKB_REMINDER])
        context = context_for_harness(parts, optional_parts)
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
            optional_parts.append(
                (
                    len(parts) - 1,
                    f"Spec omitted for Cursor’s context limit. Read `{spec_path}` before relying on prior state.",
                )
            )

    worklog = "" if is_review else transcript_tail(worklog_path, lines=MAX_WORKLOG_LINES, limit=MAX_WORKLOG_CHARS)
    if worklog:
        parts.extend(["", "### Recent Hook Worklog", worklog])
        optional_parts.insert(
            0,
            (
                len(parts) - 1,
                f"Worklog omitted for Cursor’s context limit. Read complete rows from `{worklog_path}` when prior activity is needed.",
            ),
        )

    if key and is_named_topic(topic) and not is_review and spec_text_source.strip() and agent_depth() != "fast":
        rows = aikb_warmstart(workspace, spec_text_source)
        pointer = stage_candidates(rows, load_seen(seen_file_for(spec_path, key)), spec_path, key, warm_start=True)
        if pointer:
            parts.extend(["", pointer])

    if not per_turn_recall_requested(payload):
        parts.extend(["", NO_PERTURN_RECALL_NOTICE])
    parts.extend(["", AIKB_REMINDER])

    if spec_mirror is not None:
        spec_mirror.sync_topic(spec_dir, workspace, topic)

    context = context_for_harness(parts, optional_parts)
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
