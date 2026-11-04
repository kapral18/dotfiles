#!/usr/bin/env python3
"""Behavior tests for scripts/reconcile_golang_pkgs.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_failed_removal_stays_owned_until_the_next_reconciliation(self) -> None:
        spec = importlib.util.spec_from_file_location("reconcile_golang_pkgs", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        binary = self.gobin / "tool"
        binary.write_text("installed by the hook")
        self.state.write_text("example.com/tool\n")
        self.desired.write_text("")
        self.installed.write_text("")
        unlink = Path.unlink

        def deny_owned(path, *args, **kwargs):
            if path == binary:
                raise PermissionError("fixture denied removal")
            return unlink(path, *args, **kwargs)

        argv = [str(SCRIPT), str(self.desired), str(self.gobin), str(self.state), str(self.installed)]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(Path, "unlink", deny_owned):
            self.assertEqual(module.main(), 0)
        self.assertEqual(self.state.read_text(), "example.com/tool\n")
        self.reconcile([], [])
        self.assertFalse(binary.exists())

    def test_binary_this_tooling_installed_is_removed_when_unlisted(self) -> None:
        (self.gobin / "tool").write_text("installed by the hook")
        self.reconcile(["example.com/tool"], installed=["example.com/tool"])
        self.reconcile([], installed=[])
        self.assertFalse((self.gobin / "tool").exists())


if __name__ == "__main__":
    unittest.main()
