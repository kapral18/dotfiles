#!/usr/bin/env python3
"""Tests for inject_mcp_into_codex_toml.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import (
    FIXTURES,
    run_script,
)


class TestInjectMcpIntoCodexToml(unittest.TestCase):
    """WHEN injecting MCP servers into Codex TOML."""

    def test_golden(self):
        actual = run_script(
            [
                "inject_mcp_into_codex_toml.py",
                str(FIXTURES / "codex_base.toml"),
                str(FIXTURES / "mcp_servers.yaml"),
                "false",
                "codex",
            ]
        )
        expected = (FIXTURES / "golden_codex_personal.toml").read_text()
        assert actual == expected

    def test_preserves_existing_mcp_approval_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "config.toml"
            existing.write_text(
                "\n".join(
                    [
                        "[mcp_servers.public-tool]",
                        'default_tools_approval_mode = "prompt"',
                        "",
                        "[mcp_servers.http-tool]",
                        'default_tools_approval_mode = "prompt"',
                        "",
                        "[mcp_servers.public-tool.tools.search]",
                        'approval_mode = "approve"',
                        "",
                        "[mcp_servers.http-tool.tools.list_indices]",
                        'approval_mode = "approve"',
                        "",
                        "[mcp_servers.work-tool.tools.hidden]",
                        'approval_mode = "approve"',
                        "",
                        "[mcp_servers.header-tool.tools.invalid]",
                        'approval_mode = "bogus"',
                        "",
                    ]
                )
            )

            actual = run_script(
                [
                    "inject_mcp_into_codex_toml.py",
                    str(FIXTURES / "codex_base.toml"),
                    str(FIXTURES / "mcp_servers.yaml"),
                    "false",
                    "codex",
                    str(existing),
                ]
            )

        assert 'default_tools_approval_mode = "approve"' in actual
        assert "[mcp_servers.http-tool]\nurl = " in actual
        assert 'default_tools_approval_mode = "prompt"' in actual
        assert "[mcp_servers.public-tool.tools.search]" in actual
        assert "[mcp_servers.http-tool.tools.list_indices]" in actual
        assert 'approval_mode = "approve"' in actual
        assert "work-tool.tools.hidden" not in actual
        assert "header-tool.tools.invalid" not in actual

    def test_preserves_existing_hook_trust_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "config.toml"
            existing.write_text(
                "\n".join(
                    [
                        '[hooks.state."/tmp/hooks.json:session_start:0:0"]',
                        'trusted_hash = "sha256:abc123"',
                        "",
                        '[hooks.state."/tmp/hooks.json:post_tool_use:0:0"]',
                        'trusted_hash = "sha256:def456"',
                        "",
                    ]
                )
            )

            actual = run_script(
                [
                    "inject_mcp_into_codex_toml.py",
                    str(FIXTURES / "codex_base.toml"),
                    str(FIXTURES / "mcp_servers.yaml"),
                    "false",
                    "codex",
                    str(existing),
                ]
            )

        assert '[hooks.state."/tmp/hooks.json:session_start:0:0"]' in actual
        assert 'trusted_hash = "sha256:abc123"' in actual
        assert '[hooks.state."/tmp/hooks.json:post_tool_use:0:0"]' in actual
        assert 'trusted_hash = "sha256:def456"' in actual


if __name__ == "__main__":
    unittest.main()
