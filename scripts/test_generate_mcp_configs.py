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
            "args": ["bridge-source", "--bridge", "--url", "https://mcp.bridge.com/mcp"],
            "tools": ["*"],
        }
        assert "headers" not in bridge

    def _bridge_registry(self, root: Path, token_source: str) -> Path:
        registry = root / "mcp_servers.yaml"
        registry.write_text(
            f"""
mcp_servers:
  - name: first
    work_only: false
    type: http
    url: https://first.example/mcp
    oauth_by_tool:
      copilot:
        tokenBridge: "{token_source}"
""".lstrip()
        )
        return registry

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


if __name__ == "__main__":
    unittest.main()
