#!/usr/bin/env python3
"""Tests for the `,handoff` cross-harness session note command."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMMAND = REPO / "home" / "exact_bin" / "executable_,handoff"


class TestHandoff(unittest.TestCase):
    """WHEN agents save and read handoff notes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "handoffs"
        self.cwd = Path(self.tmp.name) / "outside-git"
        self.cwd.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_handoff(self, *args: str, stdin: str = "", cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "AGENT_HANDOFF_DIR": str(self.root), "GIT_CEILING_DIRECTORIES": self.tmp.name}
        return subprocess.run(
            [sys.executable, str(COMMAND), *args],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=cwd or self.cwd,
            env=env,
        )

    def test_SHOULD_round_trip_a_note_and_keep_the_previous_version(self):
        first = self.run_handoff("save", "auth-fix", stdin="goal: one")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout.strip(), str(self.root / "global/auth-fix.md"))
        self.run_handoff("save", "auth-fix", stdin="goal: two\n")

        self.assertEqual(self.run_handoff("show", "auth-fix").stdout, "goal: two\n")
        self.assertEqual(self.run_handoff("show", "auth-fix", "--prev").stdout, "goal: one\n")

    def test_SHOULD_share_one_namespace_across_worktrees_of_a_repo(self):
        main = Path(self.tmp.name) / "My Repo"
        subprocess.run(["git", "init", "-q", str(main)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(main),
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@t",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "i",
            ],
            check=True,
        )
        tree = Path(self.tmp.name) / "wt"
        subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(tree)], check=True)

        saved = self.run_handoff("save", "plan", stdin="state\n", cwd=tree)
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertEqual(saved.stdout.strip(), str(self.root / "my-repo/plan.md"))
        self.assertEqual(self.run_handoff("show", "plan", cwd=main).stdout, "state\n")

    def test_SHOULD_list_newest_first_and_hide_previous_versions(self):
        self.run_handoff("save", "older", stdin="a\n")
        self.run_handoff("save", "newer", stdin="b\n")
        os.utime(self.root / "global/older.md", (1, 1))
        self.run_handoff("--repo", "other", "save", "elsewhere", stdin="c\n")
        self.run_handoff("save", "newer", stdin="b2\n")

        local = self.run_handoff("list").stdout.splitlines()
        self.assertEqual([line.split()[-1] for line in local], ["newer", "older"])
        every = self.run_handoff("list", "--all").stdout.splitlines()
        self.assertCountEqual([line.split()[-1] for line in every], ["global/newer", "global/older", "other/elsewhere"])

    def test_SHOULD_reject_empty_notes_bad_topics_and_missing_notes(self):
        cases = (
            (("save", "empty"), "  \n", "empty note"),
            (("save", "../escape"), "x", "invalid topic"),
            (("save", "Upper"), "x", "invalid topic"),
            (("show", "absent"), "", "no note at"),
        )
        for args, stdin, message in cases:
            with self.subTest(args=args):
                result = self.run_handoff(*args, stdin=stdin)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
        self.assertFalse((self.root / "global/empty.md").exists())

    def test_SHOULD_warn_but_save_an_oversized_note(self):
        result = self.run_handoff("save", "big", stdin="x" * 5000)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("keep it under 4096", result.stderr)
        self.assertTrue((self.root / "global/big.md").is_file())


if __name__ == "__main__":
    unittest.main()
