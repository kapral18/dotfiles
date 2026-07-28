#!/usr/bin/env python3
"""Tests for ai_models.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _test_support import FIXTURES, REPO


class TestAiModels(unittest.TestCase):
    """WHEN loading AI models from YAML."""

    def test_load_litellm_models(self):
        from ai_models import load_litellm

        models = load_litellm(str(FIXTURES / "ai_models.yaml"))
        assert len(models) == 2
        assert models[0]["id"] == "llm-gateway/model-a"
        assert models[0]["reasoning"] is True
        assert models[0]["cost"]["input"] == 5
        assert models[1]["reasoning"] is False
        assert models[1]["cost"]["input"] == 0.5

    def test_load_azure_models_empty(self):
        from ai_models import load_azure

        models = load_azure(str(FIXTURES / "ai_models.yaml"))
        assert len(models) == 0

    def test_load_model_mirror_policy_sections(self):
        from ai_models import (
            load_agent_review_models,
            load_cursor_models,
            load_pi_extra_models,
            load_provider_models,
        )

        path = FIXTURES / "ai_models.yaml"
        cursor = load_cursor_models(path)
        pi = load_pi_extra_models(path)
        providers = load_provider_models(path)
        review = load_agent_review_models(path)

        assert cursor == [
            {"id": "cursor-model-a", "recommended": True},
            {"id": "cursor-model-b"},
        ]
        assert pi == [{"id": "openrouter/model-a", "recommended": True}]
        assert providers == [{"provider": "openrouter", "id": "provider-model-a", "recommended": True}]
        assert review["cursor"] == {"lanes": "cursor-model-a", "verifier": "cursor-model-b"}
        assert review["copilot"] == {"lanes": "gpt-model", "verifier": "claude-model"}

    def test_cursor_policy_fails_closed_when_missing_empty_or_unrecognized(self):
        from ai_models import load_cursor_models

        cases = {
            "missing": "litellm_models:\n  - id: model-a\n",
            "empty": "cursor_models:\nlitellm_models:\n",
            "unrecognized": "cursor_models:\n  models: cursor-model-a\n",
        }
        for name, contents in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "ai_models.yaml"
                path.write_text(contents)
                with self.assertRaisesRegex(ValueError, "cursor_models"):
                    load_cursor_models(path)

    def test_load_model_tier_map(self):
        from ai_models import load_model_tier_map

        tiers = load_model_tier_map(str(FIXTURES / "ai_models.yaml"))
        assert set(tiers.keys()) == {"claude_code"}
        assert tiers["claude_code"]["gruntwork"] == {
            "model": "model-b",
            "effort": "high",
            "thinking": "no",
            "context": "short",
            "band": "cheap",
        }
        assert tiers["claude_code"]["orchestration"] == {
            "model": "model-a",
            "effort": "high",
            "thinking": "off",
            "context": "long",
            "band": "max",
            "fallback": {
                "model": "model-fallback",
                "effort": "medium",
                "context": "long",
            },
        }

    def test_parse_flow_map_nested(self):
        from ai_models import _parse_flow_map

        assert _parse_flow_map('{ model: "x", effort: "high", fallback: { model: "y", effort: "medium" } }') == {
            "model": "x",
            "effort": "high",
            "fallback": {"model": "y", "effort": "medium"},
        }

    def test_parse_flow_map_trailing_comment(self):
        from ai_models import _parse_flow_map

        assert _parse_flow_map('{ model: "x", effort: "high" }') == {
            "model": "x",
            "effort": "high",
        }

    def test_parse_flow_map_empty_string_scalar(self):
        from ai_models import _parse_flow_map

        assert _parse_flow_map('{ model: "x", effort: "", context: "" }') == {
            "model": "x",
            "effort": "",
            "context": "",
        }

    def test_bucket_line_with_trailing_comment_is_parsed(self):
        from ai_models import load_model_tier_map

        content = 'model_tier_map:\n  claude_code:\n    gruntwork: { model: "x", effort: "high" } # trailing comment\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ai_models.yaml"
            path.write_text(content)
            tiers = load_model_tier_map(str(path))
        assert tiers == {"claude_code": {"gruntwork": {"model": "x", "effort": "high"}}}

    def test_claude_builtin_agent_shadows_are_declared(self):
        agents = REPO / "home/dot_claude/exact_agents"
        expected = {
            "Explore.md.tmpl": "name: Explore",
            "Plan.md.tmpl": "name: Plan",
            "general-purpose.md.tmpl": "name: general-purpose",
            "claude-code-guide.md.tmpl": "name: claude-code-guide",
            "claude.md.tmpl": "name: claude",
        }
        for filename, name_line in expected.items():
            with self.subTest(filename=filename):
                text = (agents / filename).read_text()
                assert name_line in text
                assert "model:" in text

    def test_claude_litellm_does_not_override_subagent_models_by_default(self):
        wrapper = (REPO / "home/exact_bin/executable_,claude-litellm").read_text()

        assert "CLAUDE_CODE_SUBAGENT_MODEL:-inherit" in wrapper
        assert "CLAUDE_CODE_SUBAGENT_MODEL:-llm-gateway/claude-opus-4-8[1m]" not in wrapper


if __name__ == "__main__":
    unittest.main()
