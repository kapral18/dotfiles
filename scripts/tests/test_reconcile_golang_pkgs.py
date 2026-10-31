#!/usr/bin/env python3
"""Behavior tests for scripts/reconcile_golang_pkgs.py."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "reconcile_golang_pkgs.py"


class ReconcileGolangPkgsTests(unittest.TestCase):
    """WHEN the Go tool list changes."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.gobin = self.root / "bin"
        self.gobin.mkdir()
        self.desired = self.root / "desired"
        self.state = self.root / "state"
        self.installed = self.root / "installed"

    def reconcile(self, desired: list[str], installed: list[str]) -> None:
        self.desired.write_text("".join(f"{m}\n" for m in desired))
        self.installed.write_text("".join(f"{m}\n" for m in installed))
        subprocess.run(
            [sys.executable, str(SCRIPT), str(self.desired), str(self.gobin), str(self.state), str(self.installed)],
            check=True,
            capture_output=True,
        )

    def test_hand_installed_binary_survives_its_module_leaving_the_list(self) -> None:
        mine = self.gobin / "tool"
        mine.write_text("hand-installed")
        self.reconcile(["example.com/tool"], installed=[])
        self.reconcile([], installed=[])
        self.assertTrue(mine.exists())

    def test_binary_this_tooling_installed_is_removed_when_unlisted(self) -> None:
        (self.gobin / "tool").write_text("installed by the hook")
        self.reconcile(["example.com/tool"], installed=["example.com/tool"])
        self.reconcile([], installed=[])
        self.assertFalse((self.gobin / "tool").exists())


if __name__ == "__main__":
    unittest.main()
