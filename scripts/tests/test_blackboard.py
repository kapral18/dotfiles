#!/usr/bin/env python3
"""Regression tests for the shared multi-agent blackboard CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "blackboard.py"


class TestBlackboard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = dict(os.environ, BLACKBOARD_HOME=self.tmp.name)

    def run_bb(self, *args: str, expect: int = 0) -> str:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env=self.env,
        )
        self.assertEqual(
            proc.returncode,
            expect,
            f"args={args} stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        return proc.stdout.strip()

    def seed_board(self) -> None:
        self.run_bb("signal", "--board", "b", "--content", "What is the retry count?", "--priority", "critical")
        self.run_bb(
            "add",
            "--board",
            "b",
            "--type",
            "observation",
            "--content",
            "retry count is 3 with 200ms backoff",
            "--source-ref",
            "src/foo.py:42",
            "--by",
            "w1",
            "--addresses",
            "s1",
        )

    def test_when_entry_addresses_signal_it_should_mark_signal_addressed(self):
        self.seed_board()
        state = json.loads(self.run_bb("state", "--board", "b", "--json"))
        self.assertEqual(state["signals"]["critical"], {"addressed": 1})
        self.assertEqual(state["open_blocking_signals"], [])

    def test_when_blocking_signal_open_gate_should_fail_and_pass_after_waive(self):
        self.run_bb("signal", "--board", "b", "--content", "open question", "--priority", "high")
        out = self.run_bb("gate", "--board", "b", expect=1)
        self.assertIn("s1", out)
        self.run_bb("waive", "--board", "b", "--signal", "s1", "--reason", "out of scope")
        self.run_bb("gate", "--board", "b", expect=0)

    def test_when_low_priority_signal_open_gate_should_pass(self):
        self.run_bb("signal", "--board", "b", "--content", "nice to know", "--priority", "low")
        self.run_bb("gate", "--board", "b", expect=0)

    def test_when_entry_contradicts_it_should_dispute_target_and_be_must_surface(self):
        self.seed_board()
        self.run_bb(
            "add",
            "--board",
            "b",
            "--type",
            "contradiction",
            "--content",
            "docs say 5 retries, code says 3",
            "--contradicts",
            "e1",
        )
        entries = json.loads(self.run_bb("query", "--board", "b", "--json"))
        by_id = {e["id"]: e for e in entries}
        self.assertEqual(by_id["e1"]["status"], "disputed")
        self.assertTrue(by_id["e2"]["must_surface"])

    def test_when_entry_supersedes_it_should_retire_target(self):
        self.seed_board()
        self.run_bb(
            "add",
            "--board",
            "b",
            "--type",
            "observation",
            "--content",
            "retry count is 4 after the patch",
            "--supersedes",
            "e1",
        )
        entries = json.loads(self.run_bb("query", "--board", "b", "--status", "superseded", "--json"))
        self.assertEqual([e["id"] for e in entries], ["e1"])

    def test_when_referencing_missing_ids_it_should_fail_without_inserting(self):
        self.run_bb("add", "--board", "b", "--type", "observation", "--content", "x", "--addresses", "s99", expect=1)
        self.run_bb("add", "--board", "b", "--type", "observation", "--content", "y", "--supports", "e99", expect=1)
        self.assertEqual(json.loads(self.run_bb("query", "--board", "b", "--json")), [])

    def test_when_query_filters_by_signal_it_should_return_addressing_entries(self):
        self.seed_board()
        self.run_bb("add", "--board", "b", "--type", "analysis", "--content", "unrelated")
        entries = json.loads(self.run_bb("query", "--board", "b", "--signal", "s1", "--json"))
        self.assertEqual([e["id"] for e in entries], ["e1"])

    def test_when_report_omits_must_surface_items_survival_should_fail(self):
        self.seed_board()
        self.run_bb(
            "add",
            "--board",
            "b",
            "--type",
            "calculation",
            "--content",
            "total exposure is $4,500,000 across 3 facilities",
            "--must-surface",
        )
        report = Path(self.tmp.name) / "report.md"
        report.write_text("The retry count is 3 with 200ms backoff.", encoding="utf-8")
        result = json.loads(self.run_bb("survival", "--board", "b", "--report", str(report), "--json", expect=1))
        self.assertFalse(result["pass"])
        self.assertEqual([m["id"] for m in result["missing"]], ["e2"])

    def test_when_report_discloses_everything_survival_should_pass(self):
        self.seed_board()
        self.run_bb("signal", "--board", "b", "--content", "Is bar deprecated upstream?")
        report = Path(self.tmp.name) / "report.md"
        report.write_text(
            "Retry count is 3 (200ms backoff). Open question: is bar deprecated upstream?",
            encoding="utf-8",
        )
        self.run_bb("survival", "--board", "b", "--report", str(report), expect=0)

    def test_when_writers_run_concurrently_all_entries_should_land(self):
        procs = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(SCRIPT),
                    "add",
                    "--board",
                    "c",
                    "--type",
                    "observation",
                    "--content",
                    f"finding {i}",
                    "--by",
                    f"w{i}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self.env,
            )
            for i in range(8)
        ]
        for p in procs:
            self.assertEqual(p.wait(), 0)
        state = json.loads(self.run_bb("state", "--board", "c", "--json"))
        self.assertEqual(state["entries_by_type"], {"observation": 8})

    def test_when_board_name_is_invalid_it_should_refuse(self):
        self.run_bb("state", "--board", "../escape", expect=1)

    def test_boards_should_list_created_boards(self):
        self.run_bb("signal", "--board", "alpha", "--content", "q")
        self.run_bb("signal", "--board", "beta", "--content", "q")
        self.assertEqual(json.loads(self.run_bb("boards", "--json")), ["alpha", "beta"])


if __name__ == "__main__":
    unittest.main()
