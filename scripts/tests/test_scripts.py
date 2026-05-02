#!/usr/bin/env python3
"""Golden-file regression tests for the config generation scripts.

Run from the repo root:
    python3 -m pytest scripts/tests/ -v
Or directly:
    python3 scripts/tests/test_scripts.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
REPO = SCRIPTS.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _run(args: list[str], *, stdin: str | None = None) -> str:
    result = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS),
        input=stdin,
    )
    if result.returncode != 0:
        raise AssertionError(f"{args[0]} failed:\n{result.stderr}")
    return result.stdout


class TestYamlParser(unittest.TestCase):
    """WHEN parsing YAML scalars."""

    def test_parse_scalar_types(self):
        sys.path.insert(0, str(SCRIPTS))
        from yaml_parser import parse_scalar

        assert parse_scalar("true") is True
        assert parse_scalar("false") is False
        assert parse_scalar("42") == 42
        assert parse_scalar("3.14") == 3.14
        assert parse_scalar('"hello"') == "hello"
        assert parse_scalar("'world'") == "world"
        assert parse_scalar("bare") == "bare"


class TestMcpRegistry(unittest.TestCase):
    """WHEN loading MCP servers from YAML."""

    def test_personal_excludes_work_only(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False)
        assert "public-tool" in servers
        assert "work-tool" not in servers
        assert "http-tool" in servers

    def test_work_includes_all(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=True)
        assert "public-tool" in servers
        assert "work-tool" in servers
        assert "http-tool" in servers

    def test_http_server_shape_with_tool(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False, tool="claude")
        http = servers["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert http["oauth"]["clientId"] == "resolved-client-id"
        assert http["oauth"]["callbackPort"] == 3118

    def test_http_server_oauth_by_tool_cursor(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False, tool="cursor")
        http = servers["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert http["oauth"]["clientId"] == "cursor-client-id"
        assert "callbackPort" not in http["oauth"]

    def test_http_server_no_tool_no_oauth(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False)
        http = servers["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert "oauth" not in http

    def test_http_server_unknown_tool_no_oauth(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False, tool="gemini")
        http = servers["http-tool"]
        assert http["type"] == "http"
        assert "oauth" not in http


class TestAiModels(unittest.TestCase):
    """WHEN loading AI models from YAML."""

    def test_load_litellm_models(self):
        sys.path.insert(0, str(SCRIPTS))
        from ai_models import load_litellm

        models = load_litellm(str(FIXTURES / "ai_models.yaml"))
        assert len(models) == 2
        assert models[0]["id"] == "llm-gateway/model-a"
        assert models[0]["reasoning"] is True
        assert models[0]["cost"]["input"] == 5
        assert models[1]["reasoning"] is False
        assert models[1]["cost"]["input"] == 0.5

    def test_load_azure_models_empty(self):
        sys.path.insert(0, str(SCRIPTS))
        from ai_models import load_azure

        models = load_azure(str(FIXTURES / "ai_models.yaml"))
        assert len(models) == 0


class TestModelDisplay(unittest.TestCase):
    """WHEN formatting model display names."""

    def test_reasoning_model_with_cost(self):
        sys.path.insert(0, str(SCRIPTS))
        from model_display import format_display_name

        m = {"id": "test", "name": "Test", "reasoning": True, "cost": {"input": 5, "output": 25}}
        assert format_display_name(m) == "Test \U0001f9e0 ($5in/$25out)"

    def test_non_reasoning_model_with_float_cost(self):
        sys.path.insert(0, str(SCRIPTS))
        from model_display import format_display_name

        m = {"id": "test", "name": "Test", "reasoning": False, "cost": {"input": 0.5, "output": 1.5}}
        assert format_display_name(m) == "Test ($0.5in/$1.5out)"

    def test_model_without_cost(self):
        sys.path.insert(0, str(SCRIPTS))
        from model_display import format_display_name

        m = {"id": "test", "name": "Test"}
        assert format_display_name(m) == "Test"


class TestGenerateMcpConfigs(unittest.TestCase):
    """WHEN generating MCP JSON configs."""

    def test_personal_golden(self):
        actual = _run(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "claude"])
        expected = (FIXTURES / "golden_mcp_personal.json").read_text()
        assert json.loads(actual) == json.loads(expected)

    def test_work_golden(self):
        actual = _run(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "true", "claude"])
        expected = (FIXTURES / "golden_mcp_work.json").read_text()
        assert json.loads(actual) == json.loads(expected)


class TestGeneratePiModels(unittest.TestCase):
    """WHEN generating Pi models JSON."""

    def test_golden(self):
        actual = _run(
            [
                "generate_pi_models.py",
                str(REPO / "home/dot_pi/agent/readonly_models.json"),
                str(FIXTURES / "ai_models.yaml"),
                "http://localhost:4000/v1",
                "https://test-resource.services.ai.azure.com/openai/v1",
            ]
        )
        expected = (FIXTURES / "golden_pi_models.json").read_text()
        assert json.loads(actual) == json.loads(expected)


class TestInjectMcpIntoCodexToml(unittest.TestCase):
    """WHEN injecting MCP servers into Codex TOML."""

    def test_golden(self):
        actual = _run(
            [
                "inject_mcp_into_codex_toml.py",
                str(FIXTURES / "codex_base.toml"),
                str(FIXTURES / "mcp_servers.yaml"),
                "false",
            ]
        )
        expected = (FIXTURES / "golden_codex_personal.toml").read_text()
        assert actual == expected


class TestInjectMcpIntoOpencode(unittest.TestCase):
    """WHEN injecting MCP servers into OpenCode JSONC."""

    def test_golden(self):
        base = (FIXTURES / "opencode_base.jsonc").read_text()
        actual = _run(
            ["inject_mcp_into_opencode_jsonc.py", str(FIXTURES / "mcp_servers.yaml"), "false"],
            stdin=base,
        )
        expected = (FIXTURES / "golden_opencode_personal.jsonc").read_text()
        assert actual == expected


class TestMergeOpencodeModels(unittest.TestCase):
    """WHEN merging AI models into OpenCode JSONC."""

    def test_golden(self):
        actual = _run(
            [
                "merge_opencode_models.py",
                str(FIXTURES / "opencode_work_base.jsonc"),
                str(FIXTURES / "ai_models.yaml"),
            ]
        )
        expected = (FIXTURES / "golden_opencode_models.jsonc").read_text()
        assert actual == expected

    def test_claude_models_routed_to_litellm_anthropic(self):
        actual = _run(
            [
                "merge_opencode_models.py",
                str(FIXTURES / "opencode_work_base.jsonc"),
                str(FIXTURES / "ai_models_with_claude.yaml"),
            ]
        )
        expected = (FIXTURES / "golden_opencode_models_with_claude.jsonc").read_text()
        assert actual == expected


if __name__ == "__main__":
    unittest.main()
