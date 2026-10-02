#!/usr/bin/env python3
"""Tests for generate_mcp_configs.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import (
    FIXTURES,
    REPO,
    run_script,
)


class TestGenerateMcpConfigs(unittest.TestCase):
    """WHEN generating MCP JSON configs."""

    def test_personal_golden(self):
        actual = run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "claude"])
        expected = (FIXTURES / "golden_mcp_personal.json").read_text()
        assert json.loads(actual) == json.loads(expected)

    def test_work_golden(self):
        actual = run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "true", "claude"])
        expected = (FIXTURES / "golden_mcp_work.json").read_text()
        assert json.loads(actual) == json.loads(expected)

    def test_omp_transform_names_each_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "mcp_servers.yaml"
            registry.write_text(
                """
mcp_servers:
  - name: remote
    work_only: false
    type: http
    url: https://first.example/mcp
    oauth_by_tool:
      omp: {}
  - name: local
    work_only: false
    command: echo
    args:
      - plain
""".lstrip()
            )
            actual = json.loads(run_script(["generate_mcp_configs.py", str(registry), "false", "omp"]))

        assert actual["mcpServers"] == {
            "remote": {"type": "http", "url": "https://first.example/mcp"},
            "local": {"type": "stdio", "command": "echo", "args": ["plain"]},
        }

    def test_gemini_transform_uses_antigravity_server_url(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "gemini"])
        )
        assert actual["mcpServers"]["http-tool"] == {"serverUrl": "https://mcp.example.com/mcp"}


class TestMergeClaudeMcp(unittest.TestCase):
    """WHEN replacing declared MCP servers in a runtime-owned Claude config."""

    def _merge(self, desired, current):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source, target = root / "desired.json", root / "live.json"
        source.write_text(desired)
        if current is not None:
            target.write_text(current)
        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/merge_claude_mcp.py"), str(source), str(target)],
            capture_output=True,
            text=True,
        )
        return result, target, source

    def test_SHOULD_reject_invalid_documents_without_writing_live_bytes(self):
        valid = '{"mcpServers":{"declared":{"command":"safe"}}}'
        for invalid in ('{"runtime_state":"preserve",', "[]", '{"mcpServers":[]}'):
            for source_invalid in (False, True):
                with self.subTest(invalid=invalid, source_invalid=source_invalid):
                    current = valid if source_invalid else invalid
                    result, target, _ = self._merge(invalid if source_invalid else valid, current)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(target.read_text(), current)
                    self.assertIn("Error:", result.stderr)

    def test_SHOULD_bootstrap_missing_targets_including_an_empty_registry(self):
        for servers in ({}, {"declared": {"command": "safe"}}):
            with self.subTest(servers=servers):
                result, target, _ = self._merge(json.dumps({"mcpServers": servers}), None)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(target.read_text()), {"mcpServers": servers})

    def test_SHOULD_preserve_runtime_state_and_skip_an_identical_second_write(self):
        result, target, source = self._merge(
            '{"mcpServers":{"declared":{"command":"safe"}}}',
            '{"runtime_state":{"nested":"preserve"},"mcpServers":{"retired":{"command":"old"}}}',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(target.read_text()),
            {"runtime_state": {"nested": "preserve"}, "mcpServers": {"declared": {"command": "safe"}}},
        )
        before = (target.read_bytes(), target.stat().st_mtime_ns)
        subprocess.run(
            [sys.executable, str(REPO / "scripts/merge_claude_mcp.py"), str(source), str(target)], check=True
        )
        self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), before)


if __name__ == "__main__":
    unittest.main()
