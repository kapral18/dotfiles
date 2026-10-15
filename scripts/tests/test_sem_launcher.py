#!/usr/bin/env python3
"""Checks the sem launcher's privacy controls and managed telemetry state."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / "home" / "exact_bin" / "executable_,sem"
STATE = REPO / "home" / "dot_sem" / "readonly_telemetry.json"


class SemLauncherTests(unittest.TestCase):
    def test_SHOULD_force_telemetry_update_check_and_network_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / "bin"
            bindir.mkdir()
            brew = bindir / "brew"
            brew.write_text(f'#!/bin/sh\n[ "$*" = "--prefix sem-cli" ] || exit 2\nprintf "%s\\n" "{root}"\n')
            brew.chmod(0o755)
            sem = bindir / "sem"
            sem.write_text(
                f"#!{sys.executable}\nimport json, os, sys\n"
                "print(json.dumps({'argv': sys.argv[1:], 'privacy': {"
                "key: os.environ[key] for key in ('DO_NOT_TRACK', 'SEM_NO_TELEMETRY', "
                "'SEM_NO_UPDATE_CHECK', 'SEM_NO_NETWORK')}}))\n"
            )
            sem.chmod(0o755)
            result = subprocess.run(
                ["/bin/sh", str(LAUNCHER), "diff", "--", "path with spaces"],
                env={
                    "PATH": str(bindir),
                    "HOME": str(root),
                    "DO_NOT_TRACK": "0",
                    "SEM_NO_TELEMETRY": "0",
                    "SEM_NO_UPDATE_CHECK": "0",
                    "SEM_NO_NETWORK": "0",
                },
                capture_output=True,
                text=True,
                timeout=5,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(result.stdout)
        self.assertEqual(actual["argv"], ["diff", "--", "path with spaces"])
        self.assertEqual(
            actual["privacy"],
            {"DO_NOT_TRACK": "1", "SEM_NO_TELEMETRY": "1", "SEM_NO_UPDATE_CHECK": "1", "SEM_NO_NETWORK": "1"},
        )

    def test_SHOULD_manage_telemetry_state_as_off(self):
        state = json.loads(STATE.read_text())
        self.assertEqual(state["mode"], "off")
        self.assertTrue(state["notice_shown"])


if __name__ == "__main__":
    unittest.main()
