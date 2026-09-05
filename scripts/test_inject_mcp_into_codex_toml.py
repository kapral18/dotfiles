#!/usr/bin/env python3
"""Tests for inject_mcp_into_codex_toml.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import (
    FIXTURES,
    run_script,
)


def _table_body(document: str, heading: str) -> str | None:
    marker = f"[{heading}]"
    lines = document.splitlines()
    try:
        start = lines.index(marker) + 1
    except ValueError:
        return None
    end = start
    while end < len(lines) and not lines[end].startswith("["):
        end += 1
    return "\n".join(lines[start:end]).strip()


class TestInjectMcpIntoCodexToml(unittest.TestCase):
    """WHEN injecting MCP servers into Codex TOML."""

    def _render_existing(self, content: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "config.toml"
            existing.write_text(content)
            return run_script(
                [
                    "inject_mcp_into_codex_toml.py",
                    str(FIXTURES / "codex_base.toml"),
                    str(FIXTURES / "mcp_servers.yaml"),
                    "false",
                    "codex",
                    str(existing),
                ]
            )

    def test_SHOULD_preserve_all_runtime_buckets_with_commented_quoted_headers(self):
        project = '/tmp/hash#dot.]quote"slash\\'
        content = "\n".join(
            [
                f"[projects.{json.dumps(project)}]",
                'trust_level = "trusted"',
                "[hooks.state.'hook#dot.]']",
                'trusted_hash = "sha256:abc"',
                "[tui.model_availability_nux]",
                '"gpt-5.5" = 2',
                "[mcp_servers.http-tool]",
                'default_tools_approval_mode = "prompt"',
                "[mcp_servers.http-tool.tools.'search#dot.]']",
                'approval_mode = "approve"',
            ]
        )
        expected = self._render_existing(content)
        commented = "\n".join(
            line + " # runtime state ]" if line.startswith("[") else line for line in content.splitlines()
        )
        actual = self._render_existing(commented)
        self.assertEqual(actual, expected)
        self.assertEqual(_table_body(actual, f"projects.{json.dumps(project)}"), 'trust_level = "trusted"')
        self.assertEqual(_table_body(actual, 'hooks.state."hook#dot.]"'), 'trusted_hash = "sha256:abc"')
        self.assertEqual(_table_body(actual, "tui.model_availability_nux"), '"gpt-5.5" = 2')
        self.assertIn('default_tools_approval_mode = "prompt"', _table_body(actual, "mcp_servers.http-tool"))
        self.assertEqual(_table_body(actual, 'mcp_servers.http-tool.tools."search#dot.]"'), 'approval_mode = "approve"')

    def test_SHOULD_reset_runtime_context_at_invalid_array_and_unowned_tables(self):
        for boundary in (
            "[unrelated] # another table",
            "[[unrelated]]",
            "[invalid table]",
            "[unclosed",
            '["unterminated]',
            '["trailing\\',
            "[unrelated] trailing",
            "[unrelated # invalid]",
        ):
            with self.subTest(boundary=boundary):
                content = "\n".join(
                    [
                        '[projects."/tmp/repo"]',
                        'trust_level = "trusted"',
                        boundary,
                        'trust_level = "untrusted"',
                        "[hooks.state.startup]",
                        'trusted_hash = "sha256:good"',
                        boundary,
                        'trusted_hash = "sha256:leaked"',
                        "[tui.model_availability_nux]",
                        '"kept" = 1',
                        boundary,
                        '"leaked" = 2',
                        "[mcp_servers.http-tool]",
                        'default_tools_approval_mode = "prompt"',
                        boundary,
                        'default_tools_approval_mode = "auto"',
                        "[mcp_servers.http-tool.tools.search]",
                        'approval_mode = "approve"',
                        boundary,
                        'approval_mode = "auto"',
                    ]
                )
                actual = self._render_existing(content)
                self.assertEqual(_table_body(actual, 'projects."/tmp/repo"'), 'trust_level = "trusted"')
                self.assertEqual(_table_body(actual, "hooks.state.startup"), 'trusted_hash = "sha256:good"')
                self.assertEqual(_table_body(actual, "tui.model_availability_nux"), '"kept" = 1')
                self.assertIn('default_tools_approval_mode = "prompt"', _table_body(actual, "mcp_servers.http-tool"))
                self.assertEqual(_table_body(actual, "mcp_servers.http-tool.tools.search"), 'approval_mode = "approve"')

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
                        "[mcp_servers.bridge-tool.tools.invalid]",
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
        assert '[mcp_servers.http-tool]\ncommand = ",mcp-token"' in actual
        assert 'default_tools_approval_mode = "prompt"' in actual
        assert "[mcp_servers.public-tool.tools.search]" in actual
        assert "[mcp_servers.http-tool.tools.list_indices]" in actual
        assert 'approval_mode = "approve"' in actual
        assert "work-tool.tools.hidden" not in actual
        assert "bridge-tool.tools.invalid" not in actual

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

    def test_SHOULD_preserve_only_valid_project_trust_and_u32_tui_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "config.toml"
            existing.write_text(
                "\n".join(
                    [
                        '[projects."/tmp/trusted.project"]',
                        'trust_level = "trusted"',
                        'runtime_note = "drop-me"',
                        "",
                        '[projects."/tmp/untrusted-project"]',
                        'trust_level = "untrusted"',
                        "",
                        '[projects."/tmp/invalid-project"]',
                        'trust_level = "owner"',
                        "",
                        "[tui.model_availability_nux]",
                        '"gpt-5.5" = 4',
                        '"gpt-5.6-terra" = 7',
                        '"zero" = 0',
                        '"max-u32" = 4294967295',
                        '"negative" = -1',
                        '"overflow" = 4294967296',
                        '"boolean" = true',
                        '"float" = 1.5',
                        '"string" = "four"',
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

        assert _table_body(actual, 'projects."/tmp/trusted.project"') == 'trust_level = "trusted"'
        assert _table_body(actual, 'projects."/tmp/untrusted-project"') == 'trust_level = "untrusted"'
        assert 'projects."/tmp/invalid-project"' not in actual
        assert "runtime_note" not in actual
        assert _table_body(actual, "tui.model_availability_nux") == "\n".join(
            [
                '"gpt-5.5" = 4',
                '"gpt-5.6-terra" = 7',
                '"zero" = 0',
                '"max-u32" = 4294967295',
            ]
        )
        for invalid in ("negative", "overflow", "boolean", "float", "string"):
            assert f'"{invalid}"' not in actual

    def test_SHOULD_keep_source_runtime_tables_authoritative_when_live_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.toml"
            existing = root / "config.toml"
            base.write_text(
                "\n".join(
                    [
                        "[model]",
                        'id = "source-model"',
                        "",
                        "# __MCP_SERVERS__",
                        "",
                        '[projects."/tmp/source-project"]',
                        'trust_level = "trusted"',
                        "",
                        "[tui.model_availability_nux]",
                        '"source-model" = 9',
                        "",
                    ]
                )
            )
            existing.write_text(
                "\n".join(
                    [
                        '[projects."/tmp/source-project"]',
                        'trust_level = "untrusted"',
                        "",
                        '[projects."/tmp/live-project"]',
                        'trust_level = "trusted"',
                        "",
                        "[tui.model_availability_nux]",
                        '"source-model" = 1',
                        '"live-model" = 2',
                        "",
                    ]
                )
            )

            actual = run_script(
                [
                    "inject_mcp_into_codex_toml.py",
                    str(base),
                    str(FIXTURES / "mcp_servers.yaml"),
                    "false",
                    "codex",
                    str(existing),
                ]
            )

        assert actual.count('[projects."/tmp/source-project"]') == 1
        assert _table_body(actual, 'projects."/tmp/source-project"') == 'trust_level = "trusted"'
        assert _table_body(actual, 'projects."/tmp/live-project"') == 'trust_level = "trusted"'
        assert actual.count("[tui.model_availability_nux]") == 1
        assert _table_body(actual, "tui.model_availability_nux") == '"source-model" = 9'

    def test_SHOULD_round_trip_escaped_project_paths_and_tui_model_keys(self):
        project_path = '/tmp/project\\"quoted\nline'
        model_id = 'model\\"quoted\nline'
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "config.toml"
            existing.write_text(
                "\n".join(
                    [
                        f"[projects.{json.dumps(project_path)}]",
                        'trust_level = "trusted"',
                        "",
                        "[tui.model_availability_nux]",
                        f"{json.dumps(model_id)} = 12",
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

        assert _table_body(actual, f"projects.{json.dumps(project_path)}") == 'trust_level = "trusted"'
        assert _table_body(actual, "tui.model_availability_nux") == f"{json.dumps(model_id)} = 12"


if __name__ == "__main__":
    unittest.main()
