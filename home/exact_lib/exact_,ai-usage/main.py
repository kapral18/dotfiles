#!/usr/bin/env python3
"""Cost-weighted token usage from the local records every AI harness leaves behind.

Raw "input tokens" overstate cost: providers re-read most of a long conversation from
cache at a discounted rate, and only new material (tool output, the agent's own text)
is written at full price. This report splits every session into fresh input, cache
read, cache write, output and reasoning so routes can be compared on the numbers
that are actually billed. It applies no prices: provider discounts differ and change.

Sources (all local, read-only, stdlib only):

- Claude Code   ~/.claude/projects/*/*.jsonl      assistant rows carry message.usage per API
                                                   call; rows sharing a requestId are one call.
                                                   input_tokens is fresh; cache_* are separate.
- Codex         ~/.codex/sessions/**/rollout-*.jsonl  the last token_count event carries the
                                                   session total; input_tokens INCLUDES cached
                                                   tokens, so fresh = input - cached.
- Pi            ~/.pi/agent/sessions/*/*.jsonl    message.usage per call; input is fresh and
                                                   totalTokens = input+output+cacheRead+cacheWrite.
- OMP           ~/.omp/agent/sessions/*/*.jsonl   same row shape as Pi (OMP is a Pi fork), with
                                                   reasoningTokens; input is treated as fresh like Pi.
                                                   No cached OMP row was available locally to confirm.
- OpenCode      ~/.local/share/opencode/opencode.db  session rows carry tokens_* rollups and a
                                                   model JSON; calls are counted from assistant
                                                   message rows.
- Copilot       ~/.copilot/session-state/*/events.jsonl  session.shutdown carries per-model usage
                                                   (inputTokens INCLUDES cache read/write); sessions
                                                   still open only have per-call outputTokens.

Harnesses without a local record (or with one this tool cannot read yet) are listed in
the footer so their absence reads as "unknown", never as zero.

Usage:
    ,ai-usage [--days N] [--harness NAME ...] [--by session|harness|model] [--json]
              [--limit N]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

DEFAULT_DAYS = 7
DEFAULT_LIMIT = 40
FIELDS = ("fresh_input", "cache_read", "cache_write", "output", "reasoning")
# Text the per-prompt hook injects; counting it per session gives the dilution experiment
# its two variables: how often the user corrected the agent, and how often the SOP excerpt
# was re-injected (AGENT_REINFORCE=off sessions show zero of the latter).
CORRECTION_MARKER = "### User correction signal"
REINFORCEMENT_MARKER = "[SOP REINFORCEMENT"
# Routes the user runs that leave no per-call usage record this tool can read. Reported in
# the footer so a missing row is never mistaken for zero usage.
UNRECORDED = {
    "cursor": "no local per-request usage record exists (Cursor dashboard only)",
    "adapters": "Claude/Cursor/Codex over the Codex or Copilot subscription adapters report through the frontend record; the adapters pass cache fields through since 2026-09-06, older adapter-routed records show zero cache",
}


@dataclass
class Session:
    harness: str
    session_id: str
    path: str
    started: float  # epoch seconds
    model: str = ""
    provider: str = ""
    calls: int = 0
    prompts: int = 0
    corrections: int = 0
    reinforcements: int = 0
    fresh_input: int = 0
    cache_read: int = 0
    cache_write: int = 0
    output: int = 0
    reasoning: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def context_tokens(self) -> int:
        return self.fresh_input + self.cache_read + self.cache_write

    @property
    def hit_rate(self) -> float | None:
        total = self.context_tokens
        return (self.cache_read / total) if total else None

    def add(self, other: "Session") -> None:
        self.calls += other.calls
        self.prompts += other.prompts
        self.corrections += other.corrections
        self.reinforcements += other.reinforcements
        for name in FIELDS:
            setattr(self, name, getattr(self, name) + getattr(other, name))


def _home() -> Path:
    return Path(os.environ.get("AI_USAGE_HOME") or Path.home())


def _int(value: object) -> int:
    return int(value) if isinstance(value, (int, float)) and value == value else 0


def _iter_json_lines(path: Path) -> Iterable[dict]:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def _parse_ts(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value) / (1000.0 if value > 1e12 else 1.0)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _recent(paths: Iterable[str], since: float) -> list[Path]:
    out = []
    for raw in paths:
        path = Path(raw)
        try:
            if path.stat().st_mtime >= since:
                out.append(path)
        except OSError:
            continue
    return out


# ---------------------------------------------------------------- readers


def read_claude(since: float) -> list[Session]:
    sessions = []
    for path in _recent(glob.glob(str(_home() / ".claude" / "projects" / "*" / "*.jsonl")), since):
        session = Session("claude", path.stem, str(path), path.stat().st_mtime)
        seen: set[str] = set()
        first_ts = None
        for row in _iter_json_lines(path):
            ts = _parse_ts(row.get("timestamp"))
            if ts is not None and first_ts is None:
                first_ts = ts
            if row.get("type") == "user":
                content = (row.get("message") or {}).get("content")
                # Only prompt text counts: tool results are user rows too, and may quote the markers.
                if isinstance(content, str):
                    texts = [content]
                else:
                    texts = [
                        b.get("text", "") for b in (content or []) if isinstance(b, dict) and b.get("type") == "text"
                    ]
                if texts and not row.get("isSidechain"):
                    session.prompts += 1
                joined = "\n".join(texts)
                session.corrections += joined.count(CORRECTION_MARKER)
                session.reinforcements += joined.count(REINFORCEMENT_MARKER)
                continue
            if row.get("type") != "assistant":
                continue
            message = row.get("message") or {}
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            request_id = str(row.get("requestId") or row.get("uuid") or "")
            if request_id in seen:
                continue
            seen.add(request_id)
            session.calls += 1
            session.fresh_input += _int(usage.get("input_tokens"))
            session.cache_read += _int(usage.get("cache_read_input_tokens"))
            session.cache_write += _int(usage.get("cache_creation_input_tokens"))
            session.output += _int(usage.get("output_tokens"))
            session.reasoning += _int((usage.get("output_tokens_details") or {}).get("thinking_tokens"))
            model = str(message.get("model") or "")
            if model and model != "<synthetic>":
                session.model = model
        if first_ts is not None:
            session.started = first_ts
        if session.calls:
            sessions.append(session)
    return sessions


def read_codex(since: float) -> list[Session]:
    sessions = []
    pattern = str(_home() / ".codex" / "sessions" / "*" / "*" / "*" / "rollout-*.jsonl")
    for path in _recent(glob.glob(pattern), since):
        session = Session(
            "codex", path.stem.rsplit("-", 5)[-1] if "-" in path.stem else path.stem, str(path), path.stat().st_mtime
        )
        total = None
        calls = 0
        last_usage = None
        for row in _iter_json_lines(path):
            payload = row.get("payload") or {}
            if row.get("type") == "session_meta":
                ts = _parse_ts(payload.get("timestamp") or row.get("timestamp"))
                if ts is not None:
                    session.started = ts
                session.session_id = str(payload.get("id") or payload.get("session_id") or session.session_id)
            elif row.get("type") == "turn_context":
                session.model = str(payload.get("model") or session.model)
            elif (
                row.get("type") == "response_item"
                and payload.get("type") == "message"
                and payload.get("role") in ("user", "developer")
            ):
                text = json.dumps(payload.get("content"))
                if payload.get("role") == "user":
                    session.prompts += 1
                session.corrections += text.count(CORRECTION_MARKER)
                session.reinforcements += text.count(REINFORCEMENT_MARKER)
            elif row.get("type") == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info") or {}
                usage = info.get("last_token_usage")
                if isinstance(usage, dict) and usage != last_usage:
                    calls += 1
                    last_usage = usage
                if isinstance(info.get("total_token_usage"), dict):
                    total = info["total_token_usage"]
        if not total:
            continue
        cached = _int(total.get("cached_input_tokens"))
        session.calls = calls
        session.fresh_input = max(0, _int(total.get("input_tokens")) - cached)
        session.cache_read = cached
        session.cache_write = _int(total.get("cache_write_input_tokens"))
        session.output = _int(total.get("output_tokens"))
        session.reasoning = _int(total.get("reasoning_output_tokens"))
        session.provider = "native"
        sessions.append(session)
    return sessions


def read_pi(since: float) -> list[Session]:
    sessions = []
    for path in _recent(glob.glob(str(_home() / ".pi" / "agent" / "sessions" / "*" / "*.jsonl")), since):
        session = Session("pi", path.stem, str(path), path.stat().st_mtime)
        first_ts = None
        for row in _iter_json_lines(path):
            ts = _parse_ts(row.get("timestamp"))
            if ts is not None and first_ts is None:
                first_ts = ts
            message = row.get("message") or {}
            usage = message.get("usage")
            if row.get("type") != "message" or not isinstance(usage, dict):
                continue
            session.calls += 1
            session.fresh_input += _int(usage.get("input"))
            session.cache_read += _int(usage.get("cacheRead"))
            session.cache_write += _int(usage.get("cacheWrite"))
            session.output += _int(usage.get("output"))
            session.reasoning += _int(usage.get("reasoning"))
            session.model = str(message.get("model") or session.model)
            session.provider = str(message.get("provider") or session.provider)
        if first_ts is not None:
            session.started = first_ts
        if session.calls:
            sessions.append(session)
    return sessions


def read_omp(since: float) -> list[Session]:
    sessions = []
    for path in _recent(glob.glob(str(_home() / ".omp" / "agent" / "sessions" / "*" / "*.jsonl")), since):
        session = Session("omp", path.stem, str(path), path.stat().st_mtime)
        first_ts = None
        for row in _iter_json_lines(path):
            ts = _parse_ts(row.get("timestamp"))
            if ts is not None and first_ts is None:
                first_ts = ts
            message = row.get("message") or {}
            usage = message.get("usage")
            if row.get("type") != "message" or message.get("role") != "assistant" or not isinstance(usage, dict):
                continue
            session.calls += 1
            session.fresh_input += _int(usage.get("input"))
            session.cache_read += _int(usage.get("cacheRead"))
            session.cache_write += _int(usage.get("cacheWrite"))
            session.output += _int(usage.get("output"))
            session.reasoning += _int(usage.get("reasoningTokens") or usage.get("reasoning"))
            session.model = str(message.get("model") or session.model)
            session.provider = str(message.get("provider") or session.provider)
        if first_ts is not None:
            session.started = first_ts
        if session.calls:
            sessions.append(session)
    return sessions


def read_opencode(since: float) -> list[Session]:
    import sqlite3

    db = _home() / ".local" / "share" / "opencode" / "opencode.db"
    if not db.is_file():
        return []
    sessions = []
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "select id, model, time_created, time_updated, tokens_input, tokens_output, tokens_reasoning, "
                "tokens_cache_read, tokens_cache_write from session where time_updated >= ?",
                (int(since * 1000),),
            ).fetchall()
            calls = dict(
                conn.execute(
                    "select session_id, count(*) from message where json_extract(data, '$.role') = 'assistant' "
                    "group by session_id"
                ).fetchall()
            )
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    for sid, model_json, created, updated, inp, out, reasoning, cache_read, cache_write in rows:
        model = provider = ""
        try:
            spec = json.loads(model_json) if isinstance(model_json, str) else {}
            model = str(spec.get("id") or spec.get("modelID") or "")
            provider = str(spec.get("providerID") or spec.get("provider") or "")
        except ValueError:
            pass
        session = Session("opencode", str(sid), str(db), (created or updated or 0) / 1000.0, model, provider)
        session.calls = int(calls.get(sid, 0))
        session.fresh_input = _int(inp)
        session.output = _int(out)
        session.reasoning = _int(reasoning)
        session.cache_read = _int(cache_read)
        session.cache_write = _int(cache_write)
        if session.calls or session.context_tokens or session.output:
            sessions.append(session)
    return sessions


def read_copilot(since: float) -> list[Session]:
    sessions = []
    for path in _recent(glob.glob(str(_home() / ".copilot" / "session-state" / "*" / "events.jsonl")), since):
        session = Session("copilot", path.parent.name, str(path), path.stat().st_mtime)
        first_ts = None
        shutdown = None
        per_call_output = 0
        calls = 0
        for row in _iter_json_lines(path):
            ts = _parse_ts(row.get("timestamp"))
            if ts is not None and first_ts is None:
                first_ts = ts
            data = row.get("data") or {}
            if row.get("type") == "assistant.message" and isinstance(data, dict):
                calls += 1
                per_call_output += _int(data.get("outputTokens"))
                session.model = str(data.get("model") or session.model)
            elif row.get("type") == "session.shutdown" and isinstance(data, dict):
                shutdown = data
        if first_ts is not None:
            session.started = first_ts
        metrics = (shutdown or {}).get("modelMetrics")
        if isinstance(metrics, dict) and metrics:
            for model_id, entry in metrics.items():
                usage = (entry or {}).get("usage") or {}
                requests = (entry or {}).get("requests") or {}
                cache_read = _int(usage.get("cacheReadTokens"))
                cache_write = _int(usage.get("cacheWriteTokens"))
                session.fresh_input += max(0, _int(usage.get("inputTokens")) - cache_read - cache_write)
                session.cache_read += cache_read
                session.cache_write += cache_write
                session.output += _int(usage.get("outputTokens"))
                session.reasoning += _int(usage.get("reasoningTokens"))
                session.calls += _int(requests.get("count"))
                session.model = str(model_id)
            if not session.calls:
                session.calls = calls
        elif calls:
            session.calls = calls
            session.output = per_call_output
            session.notes.append("no session.shutdown rollup yet: input/cache unknown, output from per-call events")
        if session.calls:
            sessions.append(session)
    return sessions


READERS: dict[str, Callable[[float], list[Session]]] = {
    "claude": read_claude,
    "codex": read_codex,
    "pi": read_pi,
    "omp": read_omp,
    "opencode": read_opencode,
    "copilot": read_copilot,
}


# ---------------------------------------------------------------- reporting


def collect(days: float, harnesses: Iterable[str] | None = None) -> list[Session]:
    since = time.time() - days * 86400.0
    names = list(harnesses) if harnesses else list(READERS)
    sessions: list[Session] = []
    for name in names:
        reader = READERS.get(name)
        if reader is None:
            continue
        sessions.extend(reader(since))
    sessions.sort(key=lambda s: s.started, reverse=True)
    return sessions


def group(sessions: list[Session], by: str) -> list[Session]:
    if by == "session":
        return sessions
    buckets: dict[str, Session] = {}
    for session in sessions:
        key = session.harness if by == "harness" else f"{session.harness} {session.provider} {session.model}".strip()
        bucket = buckets.get(key)
        if bucket is None:
            bucket = Session(session.harness, key, "", session.started, session.model, session.provider)
            buckets[key] = bucket
        bucket.add(session)
        bucket.started = max(bucket.started, session.started)
        bucket.notes.append(session.session_id)
    rows = list(buckets.values())
    rows.sort(key=lambda s: s.context_tokens + s.output, reverse=True)
    return rows


def _fmt(n: int) -> str:
    return f"{n:,}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _when(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%m-%d %H:%M")


def render(
    rows: list[Session], by: str, days: float, limit: int, harnesses: Iterable[str], signals: bool = False
) -> str:
    lines = []
    head = ("harness", "when", "id/model", "calls", "fresh", "cache read", "cache write", "output", "reasoning", "hit")
    if signals:
        head = (
            "harness",
            "when",
            "id/model",
            "calls",
            "prompts",
            "corrections",
            "reinforce",
            "cache read",
            "output",
            "hit",
        )
    table = []
    for row in rows[:limit]:
        ident = row.session_id[:28] if by == "session" else row.session_id[:44]
        if by == "session" and row.model:
            ident = f"{ident} {row.model}"[:52]
        if signals:
            table.append(
                (
                    row.harness,
                    _when(row.started),
                    ident,
                    str(row.calls),
                    str(row.prompts),
                    str(row.corrections),
                    str(row.reinforcements),
                    _fmt(row.cache_read),
                    _fmt(row.output),
                    _pct(row.hit_rate),
                )
            )
            continue
        table.append(
            (
                row.harness,
                _when(row.started),
                ident,
                str(row.calls),
                _fmt(row.fresh_input),
                _fmt(row.cache_read),
                _fmt(row.cache_write),
                _fmt(row.output),
                _fmt(row.reasoning),
                _pct(row.hit_rate),
            )
        )
    widths = [max(len(head[i]), *(len(r[i]) for r in table)) if table else len(head[i]) for i in range(len(head))]
    fmt = "  ".join("{:<%d}" % w if i < 3 else "{:>%d}" % w for i, w in enumerate(widths))
    lines.append(fmt.format(*head))
    for r in table:
        lines.append(fmt.format(*r))
    if len(rows) > limit:
        lines.append(f"... {len(rows) - limit} more row(s); raise --limit")
    total = Session("all", "total", "", 0)
    for row in rows:
        total.add(row)
    lines.append("")
    lines.append(
        f"last {days:g} day(s): {len(rows)} {by}(s) · calls {_fmt(total.calls)} · fresh {_fmt(total.fresh_input)} · "
        f"cache read {_fmt(total.cache_read)} · cache write {_fmt(total.cache_write)} · output {_fmt(total.output)} "
        f"(reasoning {_fmt(total.reasoning)}) · hit {_pct(total.hit_rate)}"
    )
    if signals:
        lines.append(
            f"signals: prompts {_fmt(total.prompts)} · user corrections {_fmt(total.corrections)} · "
            f"SOP re-injections {_fmt(total.reinforcements)} (Claude transcripts and Codex rollouts only; "
            "compare sessions run with AGENT_REINFORCE=off against the rest)"
        )
    lines.append(
        "raw provider counts; no prices applied (cache discounts differ per provider and are not verified here)"
    )
    missing = [f"{name}: {why}" for name, why in UNRECORDED.items() if name not in READERS]
    wanted = set(harnesses)
    if missing and (not wanted or wanted & set(UNRECORDED)):
        lines.append("not measured: " + " | ".join(missing))
    return "\n".join(lines)


def to_json(rows: list[Session]) -> str:
    payload = []
    for row in rows:
        data = asdict(row)
        data["context_tokens"] = row.context_tokens
        data["hit_rate"] = row.hit_rate
        payload.append(data)
    return json.dumps(
        {"sessions": payload, "not_measured": {k: v for k, v in UNRECORDED.items() if k not in READERS}}, indent=2
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=",ai-usage",
        description="Cost-weighted token usage (fresh / cache read / cache write / output) from local harness records.",
    )
    parser.add_argument(
        "--days", type=float, default=DEFAULT_DAYS, help=f"look back this many days (default {DEFAULT_DAYS})"
    )
    parser.add_argument(
        "--harness", action="append", choices=sorted(READERS), help="restrict to a harness (repeatable)"
    )
    parser.add_argument(
        "--by", choices=("session", "harness", "model"), default="session", help="grouping (default session)"
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"rows to print (default {DEFAULT_LIMIT})")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument(
        "--signals",
        action="store_true",
        help="show prompts, user-correction signals and SOP re-injections per row (dilution experiment view)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sessions = collect(args.days, args.harness)
    rows = group(sessions, args.by)
    if args.json:
        print(to_json(rows))
    else:
        print(render(rows, args.by, args.days, args.limit, args.harness or (), signals=args.signals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
