#!/usr/bin/env python3
"""Behavioral tests for the `,doctor` command."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO

DOCTOR = REPO / "home/exact_lib/exact_,doctor/main.sh"


class TestDoctor(unittest.TestCase):
    def test_missing_antigravity_configs_are_reported_when_agy_is_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            bindir = home / "bin"
            bindir.mkdir()
            agy = bindir / "agy"
            agy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            agy.chmod(0o755)

            result = subprocess.run(
                ["bash", str(DOCTOR), "--quiet"],
                cwd=home,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": os.pathsep.join((str(bindir), os.environ["PATH"])),
                    "XDG_STATE_HOME": str(home / ".local/state"),
                },
                capture_output=True,
                text=True,
            )

            self.assertIn("Antigravity hooks missing", result.stdout)
            self.assertIn("Antigravity MCP missing", result.stdout)


if __name__ == "__main__":
    unittest.main()
