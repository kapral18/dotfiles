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

    def test_copilot_stdio_server_gets_local_type_and_tools(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "copilot"])
        )
        public = actual["mcpServers"]["public-tool"]
        assert public["type"] == "local"
        assert public["command"] == "docker"
        assert public["tools"] == ["*"]

    def test_copilot_http_oauth_uses_oauthclientid_and_redirectport(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "copilot"])
        )
        http = actual["mcpServers"]["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert http["tools"] == ["*"]
        assert http["oauthClientId"] == "copilot-client-id"
        assert http["auth"] == {"redirectPort": 4242}
        assert http["oauthScopes"] == ["openid", "email"]
        # Copilot config never carries the raw nested oauth block or a secret.
        assert "oauth" not in http
        assert "oauthPublicClient" not in http

    def test_copilot_token_bridge_emits_local_stdio_bridge(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "copilot"])
        )
        bridge = actual["mcpServers"]["bridge-tool"]
        # tokenBridge replaces launch-time header capture: the server runs as a
        # local stdio bridge that injects a fresh bearer per request, so no
        # Authorization value is ever baked into the config.
        assert bridge == {
            "type": "local",
            "command": ",mcp-token",
            "args": [
                "bridge-source",
                "--bridge",
                "--url",
                "https://mcp.bridge.com/mcp",
                "--retry-connect-timeouts",
            ],
            "tools": ["*"],
        }
        assert "headers" not in bridge

    def _bridge_registry(self, root: Path, token_source: str, tool: str = "copilot") -> Path:
        registry = root / "mcp_servers.yaml"
        registry.write_text(
            f"""
mcp_servers:
  - name: first
    work_only: false
    type: http
    url: https://first.example/mcp
    oauth_by_tool:
      {tool}:
        tokenBridge: "{token_source}"
""".lstrip()
        )
        return registry

    def test_pi_token_bridge_emits_stdio_bridge(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = self._bridge_registry(Path(temporary), "bridge-source", tool="pi")
            actual = json.loads(run_script(["generate_mcp_configs.py", str(registry), "false", "pi"]))

        bridge = actual["mcpServers"]["first"]
        # pi rides the shared ,mcp-token stdio bridge (fresh bearer per
        # request) instead of running Slack's OAuth flow itself.
        assert bridge == {
            "command": ",mcp-token",
            "args": ["bridge-source", "--bridge", "--url", "https://first.example/mcp"],
        }

    def test_copilot_token_bridge_rejects_invalid_token_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = self._bridge_registry(Path(temporary), "bad source!")
            result = subprocess.run(
                [sys.executable, str(REPO / "scripts/generate_mcp_configs.py"), str(registry), "false", "copilot"],
                capture_output=True,
                text=True,
                cwd=str(REPO / "scripts"),
            )

        assert result.returncode != 0
        assert "invalid tokenBridge token source" in result.stderr

    def test_copilot_token_bridge_does_not_retry_connect_timeouts_by_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = self._bridge_registry(Path(temporary), "bridge-source")
            actual = json.loads(run_script(["generate_mcp_configs.py", str(registry), "false", "copilot"]))

        assert actual["mcpServers"]["first"]["args"] == [
            "bridge-source",
            "--bridge",
            "--url",
            "https://first.example/mcp",
        ]

    def test_cursor_token_bridge_emits_stdio_bridge_without_oauth_url(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "cursor"])
        )
        bridge = actual["mcpServers"]["bridge-tool"]
        assert bridge == {
            "command": ",mcp-token",
            "args": [
                "bridge-source",
                "--bridge",
                "--url",
                "https://mcp.bridge.com/mcp",
                "--retry-connect-timeouts",
            ],
        }
        assert "url" not in bridge
        assert "oauth" not in bridge
        assert "auth" not in bridge

    def test_omp_token_bridge_emits_native_stdio_bridge(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = self._bridge_registry(Path(temporary), "bridge-source", tool="omp")
            actual = json.loads(run_script(["generate_mcp_configs.py", str(registry), "false", "omp"]))

        assert actual == {
            "$schema": "https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/src/config/mcp-schema.json",
            "mcpServers": {
                "first": {
                    "type": "stdio",
                    "command": ",mcp-token",
                    "args": ["bridge-source", "--bridge", "--url", "https://first.example/mcp"],
                }
            },
        }

    def test_cursor_oauth_mint_keeps_http_oauth_and_strips_bridge(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "cursor-oauth-mint"])
        )
        assert "public-tool" not in actual["mcpServers"]
        mint = actual["mcpServers"]["bridge-tool"]
        assert mint["url"] == "https://mcp.bridge.com/mcp"
        assert mint["auth"] == {"CLIENT_ID": "cursor-bridge-client"}
        assert mint["oauth"]["clientId"] == "cursor-bridge-client"
        assert mint["oauth"]["scopes"] == ["user"]
        assert "tokenBridge" not in mint.get("oauth", {})
        assert mint.get("command") != ",mcp-token"

    def test_gemini_transform_uses_antigravity_server_url(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "gemini"])
        )
        assert actual["mcpServers"]["http-tool"] == {"serverUrl": "https://mcp.example.com/mcp"}

    def test_gemini_token_bridge_emits_stdio_bridge(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "gemini"])
        )
        bridge = actual["mcpServers"]["bridge-tool"]
        assert bridge == {
            "command": ",mcp-token",
            "args": [
                "bridge-source",
                "--bridge",
                "--url",
                "https://mcp.bridge.com/mcp",
                "--retry-connect-timeouts",
            ],
        }


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
