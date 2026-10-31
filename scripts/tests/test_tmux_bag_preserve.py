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
        (self.wrapper / "feature/x").mkdir(parents=True)

    def run_bag(self) -> None:
        env = {**os.environ, "WRAPPER": str(self.wrapper), "BAG_ROOT": str(self.bag), "WT_RELS": "feature/x"}
        subprocess.run([sys.executable, str(SCRIPT)], env=env, check=True, capture_output=True, text=True)

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


if __name__ == "__main__":
    unittest.main()
