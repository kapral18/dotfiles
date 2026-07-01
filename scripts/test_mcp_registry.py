#!/usr/bin/env python3
"""Tests for mcp_registry.py."""

from __future__ import annotations

import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import FIXTURES


class TestMcpRegistry(unittest.TestCase):
    """WHEN loading MCP servers from YAML."""

    def test_personal_excludes_work_only(self):
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False)
        assert "public-tool" in servers
        assert "work-tool" not in servers
        assert "http-tool" in servers

    def test_work_includes_all(self):
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=True)
        assert "public-tool" in servers
        assert "work-tool" in servers
        assert "http-tool" in servers

    def test_http_server_shape_with_tool(self):
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False, tool="claude")
        http = servers["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert http["oauth"]["clientId"] == "resolved-client-id"
        assert http["oauth"]["callbackPort"] == 3118

    def test_http_server_oauth_by_tool_cursor(self):
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False, tool="cursor")
        http = servers["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert http["oauth"]["clientId"] == "cursor-client-id"
        assert "callbackPort" not in http["oauth"]

    def test_http_server_no_tool_no_oauth(self):
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False)
        http = servers["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert "oauth" not in http

    def test_http_server_unknown_tool_omits_tool_specific_oauth_server(self):
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False, tool="gemini")
        assert "http-tool" not in servers

    def test_exclude_tools_omits_server_for_listed_tool_only(self):
        from mcp_registry import load_servers

        fixture = str(FIXTURES / "mcp_servers_exclude.yaml")

        copilot = load_servers(fixture, is_work=False, tool="copilot")
        assert "shared-tool" in copilot
        assert "excluded-tool" not in copilot

        claude = load_servers(fixture, is_work=False, tool="claude")
        assert "excluded-tool" in claude
        assert claude["excluded-tool"]["command"] == "docker"

        no_tool = load_servers(fixture, is_work=False)
        assert "excluded-tool" in no_tool


if __name__ == "__main__":
    unittest.main()
