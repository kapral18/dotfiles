#!/usr/bin/env python3
"""Tests for merge_antigravity_mcp.py."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO, SCRIPTS
from merge_antigravity_mcp import merge_antigravity_mcp

SCRIPT = SCRIPTS / "merge_antigravity_mcp.py"
HOOK = REPO / "home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl"


class TestMergeAntigravityMcp(unittest.TestCase):
    """WHEN Antigravity's mixed-ownership MCP config is reconciled."""

    def test_SHOULD_preserve_runtime_servers_replace_declared_and_remove_retired(self):
        live = {
            "mcpServers": {
                "runtime": {"command": "runtime"},
                "changed": {"command": "old"},
                "retired": {"command": "old"},
            },
            "runtimeState": {"keep": True},
        }
        desired = {
            "mcpServers": {
                "changed": {"command": "new"},
                "added": {"command": "added"},
            }
        }
        previous = {
            "mcpServers": {
                "changed": {"command": "old"},
                "retired": {"command": "old"},
            }
        }

        merged = merge_antigravity_mcp(live, desired, previous)

        self.assertEqual(
            merged,
            {
                "mcpServers": {
                    "runtime": {"command": "runtime"},
                    "changed": {"command": "new"},
                    "added": {"command": "added"},
                },
                "runtimeState": {"keep": True},
            },
        )

    def test_SHOULD_fail_closed_on_invalid_live_or_declared_shapes(self):
        cases = (
            ("[]", '{"mcpServers": {}}', "{}"),
            ("{}", "[]", "{}"),
            ('{"mcpServers": []}', '{"mcpServers": {}}', "{}"),
            ("{}", '{"mcpServers": []}', "{}"),
            ("{}", '{"mcpServers": {}}', '{"mcpServers": []}'),
        )
        for live, desired, previous in cases:
            with self.subTest(live=live, desired=desired, previous=previous), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                paths = [root / name for name in ("live.json", "desired.json", "previous.json")]
                for path, content in zip(paths, (live, desired, previous)):
                    path.write_text(content, encoding="utf-8")
                result = subprocess.run(
                    ["python3", str(SCRIPT), *(str(path) for path in paths)],
                    cwd=REPO,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("Error:", result.stderr)

    def test_SHOULD_wire_mixed_ownership_and_gemini_retirement_into_the_hook(self):
        hook = HOOK.read_text(encoding="utf-8")
        self.assertIn("merge_antigravity_mcp.py hash:", hook)
        self.assertIn('python3 "$antigravity_merge"', hook)
        self.assertIn("--ownership-adapter json-declared", hook)
        self.assertIn("--consumer agy", hook)
        self.assertIn('chezmoi_forget_checksum "$antigravity_target"', hook)
        self.assertIn('chezmoi_forget_checksum "$HOME/.gemini/settings.json"', hook)
        self.assertIn('chezmoi_forget_artifact "gemini-settings"', hook)


if __name__ == "__main__":
    unittest.main()
