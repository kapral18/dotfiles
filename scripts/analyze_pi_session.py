#!/usr/bin/env python3
"""Report aggregate cache, compaction, and re-read metrics from a Pi v3 session.

Usage:
    analyze_pi_session.py SESSION.jsonl [threshold options]

The report intentionally omits prompts, summaries, tool output, and file paths.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_VERSION = 3


def _load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON at line {line_number}: {error.msg}") from error
            if not isinstance(row, dict):
                raise ValueError(f"line {line_number}: session entry must be an object")
            rows.append(row)
    if not rows or rows[0].get("type") != "session":
        raise ValueError("first entry must be a Pi session header")
    version = rows[0].get("version")
    if version != SUPPORTED_VERSION:
        raise ValueError(f"unsupported Pi session version {version!r}; expected {SUPPORTED_VERSION}")
    return rows


def _active_branch(entries: list[dict]) -> list[dict]:
    if not entries:
        return []
    by_id: dict[str, dict] = {}
    for entry in entries:
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError("session entry is missing a non-empty id")
        if entry_id in by_id:
            raise ValueError(f"duplicate session entry id {entry_id!r}")
        by_id[entry_id] = entry

    branch: list[dict] = []
    seen: set[str] = set()
    entry = entries[-1]
    while True:
        entry_id = entry["id"]
        if entry_id in seen:
            raise ValueError(f"cycle in session parent chain at {entry_id!r}")
        seen.add(entry_id)
        branch.append(entry)
        parent_id = entry.get("parentId")
        if parent_id is None:
            break
        if parent_id not in by_id:
            raise ValueError(f"missing parent entry {parent_id!r}")
        entry = by_id[parent_id]
    branch.reverse()
    return branch


def _usage_number(usage: dict, key: str) -> float:
    value = usage.get(key, 0)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _read_paths(message: dict) -> list[str]:
    paths: list[str] = []
    content = message.get("content")
    if not isinstance(content, list):
        return paths
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "toolCall" or block.get("name") != "read":
            continue
        arguments = block.get("arguments")
        path = arguments.get("path") if isinstance(arguments, dict) else None
        if isinstance(path, str) and path:
            paths.append(path)
    return paths


def _assistant_message(entry: dict) -> dict | None:
    message = entry.get("message") if entry.get("type") == "message" else None
    return message if isinstance(message, dict) and message.get("role") == "assistant" else None


def _assistant_usage_report(branch: list[dict]) -> dict:
    assistant_messages = 0
    prompt_tokens = 0.0
    output_tokens = 0.0
    cache_read = 0.0
    cache_write = 0.0
    cost = 0.0
    cache_reporting_observed = False

    for entry in branch:
        message = _assistant_message(entry)
        if message is None:
            continue
        assistant_messages += 1
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        message_cache_read = _usage_number(usage, "cacheRead")
        message_cache_write = _usage_number(usage, "cacheWrite")
        prompt_tokens += _usage_number(usage, "input") + message_cache_read + message_cache_write
        output_tokens += _usage_number(usage, "output")
        cache_read += message_cache_read
        cache_write += message_cache_write
        cache_reporting_observed = cache_reporting_observed or message_cache_read > 0 or message_cache_write > 0
        usage_cost = usage.get("cost")
        if isinstance(usage_cost, dict):
            cost += _usage_number(usage_cost, "total")

    cache_hit_rate = cache_read / prompt_tokens if cache_reporting_observed and prompt_tokens > 0 else None
    return {
        "assistant_messages": assistant_messages,
        "tokens": {
            "prompt": int(prompt_tokens),
            "output": int(output_tokens),
            "cache_read": int(cache_read),
            "cache_write": int(cache_write),
        },
        "cache": {
            "reporting_observed": cache_reporting_observed,
            "hit_rate": cache_hit_rate,
            "reported_cost": cost,
        },
    }


@dataclass
class _CompactionMetrics:
    count: int = 0
    tokens_before: list[float] = field(default_factory=list)
    assistant_messages_before_each: list[int] = field(default_factory=list)
    assistant_messages_since_compaction: int = 0
    tracked_read_files: set[str] | None = None
    read_tracking_compactions: int = 0
    post_compaction_read_calls: int = 0
    post_compaction_reread_calls: int = 0
    reread_files: set[str] = field(default_factory=set)

    def start(self, entry: dict) -> None:
        self.count += 1
        self.assistant_messages_before_each.append(self.assistant_messages_since_compaction)
        self.assistant_messages_since_compaction = 0
        tokens_before = entry.get("tokensBefore")
        if isinstance(tokens_before, (int, float)) and not isinstance(tokens_before, bool):
            self.tokens_before.append(tokens_before)
        details = entry.get("details")
        read_files = details.get("readFiles") if isinstance(details, dict) else None
        self.tracked_read_files = None
        if isinstance(read_files, list) and all(isinstance(path, str) for path in read_files):
            self.tracked_read_files = set(read_files)
            self.read_tracking_compactions += 1

    def record_assistant(self, message: dict) -> None:
        self.assistant_messages_since_compaction += 1
        if self.tracked_read_files is None:
            return
        for path in _read_paths(message):
            self.post_compaction_read_calls += 1
            if path in self.tracked_read_files:
                self.post_compaction_reread_calls += 1
                self.reread_files.add(path)

    def report(self) -> dict:
        reread_ratio = (
            self.post_compaction_reread_calls / self.post_compaction_read_calls
            if self.read_tracking_compactions and self.post_compaction_read_calls
            else None
        )
        return {
            "count": self.count,
            "tokens_before": self.tokens_before,
            "assistant_messages_before_each": self.assistant_messages_before_each,
            "read_tracking_compactions": self.read_tracking_compactions,
            "read_tracking_complete": self.read_tracking_compactions == self.count,
            "post_compaction_read_calls": self.post_compaction_read_calls,
            "post_compaction_reread_calls": self.post_compaction_reread_calls,
            "unique_reread_files": len(self.reread_files),
            "reread_ratio": reread_ratio,
        }


def _compaction_report(branch: list[dict]) -> dict:
    metrics = _CompactionMetrics()
    for entry in branch:
        if entry.get("type") == "compaction":
            metrics.start(entry)
            continue
        message = _assistant_message(entry)
        if message is not None:
            metrics.record_assistant(message)
    return metrics.report()


def analyze_rows(rows: list[dict]) -> dict:
    branch = _active_branch(rows[1:])
    return {
        "format_version": rows[0]["version"],
        **_assistant_usage_report(branch),
        "compaction": _compaction_report(branch),
    }


def analyze_path(path: Path) -> dict:
    return analyze_rows(_load_rows(path))


def threshold_violations(
    report: dict,
    *,
    max_compactions: int | None,
    max_reread_ratio: float | None,
    min_cache_hit_rate: float | None,
) -> list[str]:
    violations: list[str] = []
    compaction = report["compaction"]
    cache = report["cache"]
    if max_compactions is not None and compaction["count"] > max_compactions:
        violations.append(f"compaction count {compaction['count']} exceeds {max_compactions}")
    if max_reread_ratio is not None:
        ratio = compaction["reread_ratio"]
        if ratio is None:
            violations.append("post-compaction re-read ratio unavailable")
        elif ratio > max_reread_ratio:
            violations.append(f"post-compaction re-read ratio {ratio:.3f} exceeds {max_reread_ratio:.3f}")
    if min_cache_hit_rate is not None:
        hit_rate = cache["hit_rate"]
        if hit_rate is None:
            violations.append("cache hit rate unavailable")
        elif hit_rate < min_cache_hit_rate:
            violations.append(f"cache hit rate {hit_rate:.3f} is below {min_cache_hit_rate:.3f}")
    return violations


def _ratio(value: str) -> float:
    number = float(value)
    if not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("expected a value between 0 and 1")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path, help="Pi v3 session JSONL file")
    parser.add_argument("--max-compactions", type=int, default=None)
    parser.add_argument("--max-reread-ratio", type=_ratio, default=None)
    parser.add_argument("--min-cache-hit-rate", type=_ratio, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_compactions is not None and args.max_compactions < 0:
        raise SystemExit("--max-compactions must be >= 0")
    try:
        report = analyze_path(args.session)
    except (OSError, ValueError) as error:
        print(f"analyze_pi_session: {error}", file=sys.stderr)
        return 1
    violations = threshold_violations(
        report,
        max_compactions=args.max_compactions,
        max_reread_ratio=args.max_reread_ratio,
        min_cache_hit_rate=args.min_cache_hit_rate,
    )
    report["violations"] = violations
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
