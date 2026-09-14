#!/usr/bin/env python3
"""Tests for Pi subagent child session telemetry aggregation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
import subagent_child_stats


def _child(root: Path, run: str, agent: str, *, peaks: list[int], compactions: int = 0) -> Path:
    path = root / "ws" / "parent" / run / "run-0" / "session.jsonl"
    path.parent.mkdir(parents=True)
    rows = [
        {"type": "session", "version": 3, "id": run},
        {"type": "session_info", "id": "i", "name": f"subagent-{agent}-4af80c41-3678-4189-ad4c-f9afb1c7683d-1"},
        {"type": "message", "id": "u", "message": {"role": "user", "content": "packet"}},
    ]
    for index, peak in enumerate(peaks):
        rows.append(
            {
                "type": "message",
                "id": f"a{index}",
                "message": {
                    "role": "assistant",
                    "content": [],
                    "usage": {"input": peak, "cacheRead": 0, "cacheWrite": 0},
                },
            }
        )
    rows.extend({"type": "compaction", "id": f"c{index}", "summary": "x"} for index in range(compactions))
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


class SubagentChildStatsTest(unittest.TestCase):
    def test_summary_groups_by_agent_and_lists_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _child(root, "r1", "k-agent-mechanical", peaks=[2000, 3000])
            _child(root, "r2", "k-agent-mechanical", peaks=[2500])
            _child(root, "r3", "k-agent-code-searcher", peaks=[40_000, 160_000], compactions=1)
            runs = [
                r
                for r in (
                    subagent_child_stats.analyze_child(p) for p in subagent_child_stats._iter_child_sessions(root)
                )
                if r
            ]
            summary = subagent_child_stats.summarize(runs)

            self.assertEqual(summary["k-agent-mechanical"]["runs"], 2)
            self.assertEqual(summary["k-agent-mechanical"]["peak_context_max"], 3000)
            self.assertEqual(summary["k-agent-mechanical"]["compactions"], 0)
            self.assertEqual(summary["k-agent-code-searcher"]["runs_with_compaction"], 1)
            self.assertEqual(summary["k-agent-code-searcher"]["peak_context_max"], 160_000)

            text = subagent_child_stats.render(summary, 150_000)
            self.assertIn("at or above threshold", text)
            self.assertIn("k-agent-code-searcher", text.split("at or above threshold")[1])
            self.assertNotIn("k-agent-mechanical", text.split("at or above threshold")[1])

    def test_below_threshold_message_and_unknown_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = _child(root, "r1", "k-agent-smol", peaks=[1000])
            path.write_text(
                path.read_text(encoding="utf-8").replace("subagent-k-agent-smol-", "weird-"), encoding="utf-8"
            )
            runs = [subagent_child_stats.analyze_child(path)]
            summary = subagent_child_stats.summarize(runs)
            self.assertIn("unknown", summary)
            self.assertIn("below threshold", subagent_child_stats.render(summary, 150_000))

    def test_threshold_only_without_compaction_is_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _child(root, "r1", "k-agent-mechanical", peaks=[160_000])
            runs = [
                r
                for r in (
                    subagent_child_stats.analyze_child(p) for p in subagent_child_stats._iter_child_sessions(root)
                )
                if r
            ]
            summary = subagent_child_stats.summarize(runs)
            self.assertEqual(summary["k-agent-mechanical"]["compactions"], 0)
            text = subagent_child_stats.render(summary, 150_000)
            self.assertIn("k-agent-mechanical", text.split("at or above threshold")[1])

    def test_compaction_only_below_threshold_is_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _child(root, "r1", "k-agent-smol", peaks=[1000], compactions=2)
            runs = [
                r
                for r in (
                    subagent_child_stats.analyze_child(p) for p in subagent_child_stats._iter_child_sessions(root)
                )
                if r
            ]
            summary = subagent_child_stats.summarize(runs)
            self.assertEqual(summary["k-agent-smol"]["runs_with_compaction"], 1)
            text = subagent_child_stats.render(summary, 150_000)
            self.assertIn("k-agent-smol", text.split("at or above threshold")[1])

    def test_neither_compaction_nor_threshold_stays_below(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _child(root, "r1", "k-agent-smol", peaks=[1000, 2000])
            runs = [
                r
                for r in (
                    subagent_child_stats.analyze_child(p) for p in subagent_child_stats._iter_child_sessions(root)
                )
                if r
            ]
            summary = subagent_child_stats.summarize(runs)
            text = subagent_child_stats.render(summary, 150_000)
            self.assertIn("below threshold", text)
            self.assertNotIn("at or above threshold", text)

    def test_json_summary_preserves_keys_and_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _child(root, "r1", "k-agent-mechanical", peaks=[2000, 3000])
            _child(root, "r2", "k-agent-mechanical", peaks=[2500])
            runs = [
                r
                for r in (
                    subagent_child_stats.analyze_child(p) for p in subagent_child_stats._iter_child_sessions(root)
                )
                if r
            ]
            summary = subagent_child_stats.summarize(runs)
            row = summary["k-agent-mechanical"]
            self.assertEqual(
                set(row),
                {
                    "runs",
                    "messages_median",
                    "messages_p90",
                    "compactions",
                    "runs_with_compaction",
                    "peak_context_median",
                    "peak_context_p90",
                    "peak_context_max",
                },
            )
            self.assertEqual(row["runs"], 2)
            self.assertEqual(row["peak_context_max"], 3000)
            round_tripped = json.loads(json.dumps(summary, sort_keys=True))
            self.assertEqual(round_tripped, summary)

    def test_empty_or_invalid_session_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text("not json\n\n", encoding="utf-8")
            self.assertIsNone(subagent_child_stats.analyze_child(path))


if __name__ == "__main__":
    unittest.main()
