#!/usr/bin/env python3
"""Tests for aggregate Pi session compaction and cache analysis."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
import analyze_pi_session

SCRIPT = Path(__file__).with_name("analyze_pi_session.py")


def _assistant(entry_id: str, parent_id: str | None, *, reads: list[str], usage: dict) -> dict:
    return {
        "type": "message",
        "id": entry_id,
        "parentId": parent_id,
        "timestamp": "2026-07-21T10:00:00Z",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "toolCall", "id": f"call-{entry_id}-{index}", "name": "read", "arguments": {"path": path}}
                for index, path in enumerate(reads)
            ],
            "usage": usage,
        },
    }


def _usage(*, input_tokens: int, output: int, cache_read: int = 0, cache_write: int = 0) -> dict:
    return {
        "input": input_tokens,
        "output": output,
        "cacheRead": cache_read,
        "cacheWrite": cache_write,
        "cost": {"total": 0.25},
    }


class TestAnalyzePiSession(unittest.TestCase):
    """WHEN analyzing a Pi v3 JSONL session."""

    def _write_session(self, rows: list[dict]) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        with tmp:
            for row in rows:
                tmp.write(json.dumps(row) + "\n")
        self.addCleanup(Path(tmp.name).unlink, missing_ok=True)
        return Path(tmp.name)

    def test_SHOULD_follow_active_branch_and_measure_post_compaction_rereads(self):
        rows = [
            {"type": "session", "version": 3, "id": "session-1", "timestamp": "now", "cwd": "/repo"},
            _assistant("a1", None, reads=["src/a.py"], usage=_usage(input_tokens=100, output=10, cache_write=20)),
            {
                "type": "compaction",
                "id": "c1",
                "parentId": "a1",
                "timestamp": "2026-07-21T10:01:00Z",
                "summary": "secret summary",
                "firstKeptEntryId": "a1",
                "tokensBefore": 130,
                "details": {"readFiles": ["src/a.py"], "modifiedFiles": []},
            },
            _assistant("abandoned", "c1", reads=["secret/abandoned.py"], usage=_usage(input_tokens=999, output=1)),
            _assistant(
                "a2",
                "c1",
                reads=["src/a.py", "src/b.py"],
                usage=_usage(input_tokens=50, output=5, cache_read=100),
            ),
        ]

        report = analyze_pi_session.analyze_path(self._write_session(rows))

        self.assertEqual(report["format_version"], 3)
        self.assertEqual(report["assistant_messages"], 2)
        self.assertEqual(report["tokens"]["prompt"], 270)
        self.assertEqual(report["tokens"]["output"], 15)
        self.assertEqual(report["tokens"]["cache_read"], 100)
        self.assertEqual(report["tokens"]["cache_write"], 20)
        self.assertAlmostEqual(report["cache"]["hit_rate"], 100 / 270)
        self.assertTrue(report["cache"]["reporting_observed"])
        self.assertEqual(report["compaction"]["count"], 1)
        self.assertEqual(report["compaction"]["tokens_before"], [130])
        self.assertEqual(report["compaction"]["post_compaction_read_calls"], 2)
        self.assertEqual(report["compaction"]["post_compaction_reread_calls"], 1)
        self.assertEqual(report["compaction"]["unique_reread_files"], 1)
        self.assertEqual(report["compaction"]["reread_ratio"], 0.5)
        rendered = json.dumps(report)
        self.assertNotIn("src/a.py", rendered)
        self.assertNotIn("secret summary", rendered)
        self.assertNotIn("abandoned", rendered)

    def test_SHOULD_report_unknown_cache_rate_without_positive_provider_signal(self):
        rows = [
            {"type": "session", "version": 3, "id": "session-2", "timestamp": "now", "cwd": "/repo"},
            _assistant("a1", None, reads=[], usage=_usage(input_tokens=100, output=5)),
        ]

        report = analyze_pi_session.analyze_path(self._write_session(rows))

        self.assertFalse(report["cache"]["reporting_observed"])
        self.assertIsNone(report["cache"]["hit_rate"])
        self.assertIsNone(report["compaction"]["reread_ratio"])

    def test_SHOULD_exit_two_when_an_explicit_threshold_is_crossed(self):
        rows = [
            {"type": "session", "version": 3, "id": "session-3", "timestamp": "now", "cwd": "/repo"},
            _assistant("a1", None, reads=[], usage=_usage(input_tokens=100, output=5)),
            {
                "type": "compaction",
                "id": "c1",
                "parentId": "a1",
                "timestamp": "now",
                "summary": "summary",
                "firstKeptEntryId": "a1",
                "tokensBefore": 100,
                "details": {"readFiles": [], "modifiedFiles": []},
            },
        ]
        report = analyze_pi_session.analyze_path(self._write_session(rows))

        self.assertEqual(
            analyze_pi_session.threshold_violations(
                report,
                max_compactions=0,
                max_reread_ratio=None,
                min_cache_hit_rate=0.5,
            ),
            ["compaction count 1 exceeds 0", "cache hit rate unavailable"],
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self._write_session(rows)), "--max-compactions", "0"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["violations"], ["compaction count 1 exceeds 0"])

    def test_SHOULD_reject_unsupported_session_formats(self):
        rows = [
            {"type": "session", "version": 4, "id": "session-4", "timestamp": "now", "cwd": "/repo"},
            _assistant("a1", None, reads=[], usage=_usage(input_tokens=100, output=5)),
        ]

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self._write_session(rows))],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("unsupported Pi session version 4", result.stderr)
        self.assertEqual(result.stdout, "")

        rows[0]["version"] = 4
        with self.assertRaisesRegex(ValueError, "unsupported Pi session version 4"):
            analyze_pi_session.analyze_path(self._write_session(rows))


if __name__ == "__main__":
    unittest.main()
