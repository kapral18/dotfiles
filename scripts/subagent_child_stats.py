#!/usr/bin/env python3
"""Describe reported context telemetry across Pi subagent child sessions.

Usage:
    subagent_child_stats.py [--root DIR] [--json] [--min-peak N]

Per agent profile it reports run count, median/p90 message count, compaction count, and the median/p90 reported peak
context (largest ``input + cacheRead + cacheWrite`` seen on one assistant turn). Prompts,
summaries, and tool output are never printed.

Reported usage plus a cutoff does not determine actual window exhaustion or savings: this is a
descriptive compaction/threshold observation over the scanned sessions, not a verdict on window
capacity, cost, or whether nested delegation is warranted.

Child sessions live at ``<root>/<workspace>/<parent-session>/<run-id>/run-*/session.jsonl``;
the default root is ``~/.pi/agent/sessions``. The profile name is taken from the
``session_info`` record (``subagent-<agent>-<uuid>-<n>``).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOT = Path.home() / ".pi" / "agent" / "sessions"
_SESSION_INFO_NAME = re.compile(
    r"^subagent-(?P<agent>.+?)-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-\d+$"
)


@dataclass(frozen=True)
class ChildRun:
    agent: str
    path: Path
    messages: int
    compactions: int
    peak_context: int
    turns: int


def _iter_child_sessions(root: Path):
    yield from sorted(root.glob("*/*/*/run-*/session.jsonl"))


def _context_of(usage: dict) -> int:
    total = 0
    for key in ("input", "cacheRead", "cacheWrite"):
        value = usage.get(key, 0)
        if isinstance(value, (int, float)):
            total += int(value)
    return total


def analyze_child(path: Path) -> ChildRun | None:
    agent = "unknown"
    messages = compactions = turns = 0
    peak = 0
    try:
        handle = path.open(encoding="utf-8")
    except OSError:
        return None
    with handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = row.get("type")
            if kind == "session_info":
                match = _SESSION_INFO_NAME.match(str(row.get("name", "")))
                if match:
                    agent = match.group("agent")
            elif kind == "compaction":
                compactions += 1
            elif kind == "message":
                messages += 1
                message = row.get("message") or {}
                if message.get("role") == "assistant":
                    turns += 1
                    usage = message.get("usage")
                    if isinstance(usage, dict):
                        peak = max(peak, _context_of(usage))
    if messages == 0:
        return None
    return ChildRun(agent=agent, path=path, messages=messages, compactions=compactions, peak_context=peak, turns=turns)


def _p90(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))]


def summarize(runs: list[ChildRun]) -> dict[str, dict]:
    by_agent: dict[str, list[ChildRun]] = defaultdict(list)
    for run in runs:
        by_agent[run.agent].append(run)
    summary: dict[str, dict] = {}
    for agent, group in sorted(by_agent.items()):
        msgs = [run.messages for run in group]
        peaks = [run.peak_context for run in group]
        summary[agent] = {
            "runs": len(group),
            "messages_median": int(statistics.median(msgs)),
            "messages_p90": _p90(msgs),
            "compactions": sum(run.compactions for run in group),
            "runs_with_compaction": sum(1 for run in group if run.compactions),
            "peak_context_median": int(statistics.median(peaks)),
            "peak_context_p90": _p90(peaks),
            "peak_context_max": max(peaks),
        }
    return summary


def render(summary: dict[str, dict], min_peak: int) -> str:
    if not summary:
        return "no child sessions found"
    header = f"{'agent':<32} {'runs':>4} {'msgs med/p90':>13} {'compact':>8} {'peak ctx med/p90/max':>24}"
    lines = [header, "-" * len(header)]
    flagged: list[str] = []
    for agent, row in summary.items():
        lines.append(
            f"{agent:<32} {row['runs']:>4} {row['messages_median']:>6}/{row['messages_p90']:<6} "
            f"{row['runs_with_compaction']:>3}/{row['runs']:<4} "
            f"{row['peak_context_median']:>7}/{row['peak_context_p90']}/{row['peak_context_max']}"
        )
        if row["runs_with_compaction"] or row["peak_context_p90"] >= min_peak:
            flagged.append(agent)
    lines.append("")
    if flagged:
        lines.append(f"at or above threshold (compaction or p90 peak >= {min_peak}): {', '.join(flagged)}")
    else:
        lines.append(f"below threshold: no compactions and every p90 peak < {min_peak}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT, help="Pi sessions root (default ~/.pi/agent/sessions)"
    )
    parser.add_argument("--json", action="store_true", help="emit the per-agent summary as JSON")
    parser.add_argument(
        "--min-peak",
        type=int,
        default=150_000,
        help="p90 reported peak context listed at or above threshold in human output",
    )
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        print(f"subagent_child_stats: not a directory: {args.root}", file=sys.stderr)
        return 2
    runs = [run for run in (analyze_child(path) for path in _iter_child_sessions(args.root)) if run]
    summary = summarize(runs)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render(summary, args.min_peak))
    return 0


if __name__ == "__main__":
    sys.exit(main())
