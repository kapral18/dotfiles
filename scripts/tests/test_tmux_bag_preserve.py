#!/usr/bin/env python3
"""Behavior tests for the session picker's bag_preserve_non_wt.py."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401
from _test_support import TMUX_PICKERS

SCRIPT = TMUX_PICKERS / "session/lib/bag_preserve_non_wt.py"


class BagPreserveTests(unittest.TestCase):
    """WHEN leftovers in a worktree wrapper are moved into the bag."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.wrapper = self.root / "repo"
        self.bag = self.root / "bag"
        self.status = self.root / "bag-status"
        (self.wrapper / "feature/x").mkdir(parents=True)

    def run_bag(self) -> None:
        env = {
            **os.environ,
            "WRAPPER": str(self.wrapper),
            "BAG_ROOT": str(self.bag),
            "WT_RELS": "feature/x",
            "BAG_PRESERVE_STATUS_FILE": str(self.status),
        }
        subprocess.run([sys.executable, str(SCRIPT)], env=env, check=True, capture_output=True, text=True, timeout=5)

    def test_symlink_to_a_bagged_file_does_not_overwrite_it(self) -> None:
        (self.wrapper / "notes.txt").write_text("precious\n", encoding="utf-8")
        (self.wrapper / "feature/link").symlink_to("../notes.txt")

        self.run_bag()

        bagged = [p for p in self.bag.rglob("*") if p.is_file() and not p.is_symlink()]
        self.assertEqual([p.read_text(encoding="utf-8") for p in bagged], ["precious\n"])
        self.assertTrue((self.bag / "feature/link").is_symlink())

    def test_same_name_leftovers_are_both_kept(self) -> None:
        (self.bag / "notes.txt").parent.mkdir(parents=True)
        (self.bag / "notes.txt").write_text("earlier\n", encoding="utf-8")
        (self.wrapper / "notes.txt").write_text("later\n", encoding="utf-8")

        self.run_bag()

        contents = sorted(p.read_text(encoding="utf-8") for p in self.bag.rglob("notes.txt*"))
        self.assertEqual(contents, ["earlier\n", "later\n"])

    def test_deep_independent_repository_keeps_wrapper_content_in_place(self) -> None:
        sibling = self.wrapper / "other/one/two/three/four/five/six/seven/eight/nine/repo"
        sibling.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(sibling)], check=True, capture_output=True, text=True, timeout=5)
        (sibling / "notes.txt").write_text("keep repository content\n", encoding="utf-8")
        (self.wrapper / "notes.txt").write_text("keep wrapper content\n", encoding="utf-8")

        self.run_bag()

        self.assertTrue((sibling / ".git").is_dir())
        self.assertEqual((sibling / "notes.txt").read_text(encoding="utf-8"), "keep repository content\n")
        self.assertEqual((self.wrapper / "notes.txt").read_text(encoding="utf-8"), "keep wrapper content\n")
        self.assertEqual(self.status.read_text(encoding="utf-8"), "blocked_by_unselected_git_root=1\n")
        self.assertFalse(self.bag.exists())

    @unittest.skipIf(os.geteuid() == 0, "root can inspect permission-restricted directories")
    def test_scan_failure_preserves_all_content_before_moving(self) -> None:
        unreadable = self.wrapper / "unreadable"
        unreadable.mkdir()
        (unreadable / "notes").write_text("keep uninspected content\n")
        (self.wrapper / "notes").write_text("keep wrapper content\n")
        unreadable.chmod(0)
        try:
            with self.assertRaises(subprocess.CalledProcessError):
                self.run_bag()
        finally:
            for path in [unreadable, self.bag / "unreadable"]:
                if path.exists():
                    path.chmod(0o700)

        self.assertEqual((unreadable / "notes").read_text(), "keep uninspected content\n")
        self.assertEqual((self.wrapper / "notes").read_text(), "keep wrapper content\n")
        self.assertFalse(self.bag.exists())


if __name__ == "__main__":
    unittest.main()
