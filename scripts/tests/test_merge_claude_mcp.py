#!/usr/bin/env python3
"""Behavior tests for scripts/merge_claude_mcp.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "merge_claude_mcp.py"


class MergeClaudeMcpTests(unittest.TestCase):
    """WHEN declared MCP servers are merged into ~/.claude.json."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.src = self.root / "desired.json"
        self.src.write_text(json.dumps({"mcpServers": {"a": {"command": "x"}}}))
        self.target = self.root / "claude.json"

    def merge(self) -> None:
        subprocess.run([sys.executable, str(SCRIPT), str(self.src), str(self.target)], check=True, capture_output=True)

    def test_new_file_is_private(self) -> None:
        old = os.umask(0o022)
        try:
            self.merge()
        finally:
            os.umask(old)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.target.read_text())["mcpServers"], {"a": {"command": "x"}})

    def test_existing_settings_mode_and_symlink_are_kept(self) -> None:
        real = self.root / "real.json"
        real.write_text(json.dumps({"oauthAccount": {"id": 1}, "mcpServers": {}}))
        real.chmod(0o640)
        self.target.symlink_to(real)

        self.merge()

        self.assertTrue(self.target.is_symlink())
        self.assertEqual(real.stat().st_mode & 0o777, 0o640)
        data = json.loads(real.read_text())
        self.assertEqual(data["oauthAccount"], {"id": 1})
        self.assertEqual(data["mcpServers"], {"a": {"command": "x"}})


if __name__ == "__main__":
    unittest.main()
