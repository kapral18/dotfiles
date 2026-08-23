#!/usr/bin/env python3
"""Tests for ai_models.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _test_support import FIXTURES, REPO


class TestAiModels(unittest.TestCase):
    """WHEN loading AI models from YAML."""

    def test_load_model_mirror_policy_sections(self):
        from ai_models import (
            load_cursor_models,
            load_pi_extra_models,
            load_provider_models,
            load_review_model_overrides,
        )

        path = FIXTURES / "ai_models"
        cursor = load_cursor_models(path)
        pi = load_pi_extra_models(path)
        providers = load_provider_models(path)
        review = load_review_model_overrides(path)

        assert cursor == [
            {"id": "cursor-model-a", "recommended": True},
            {"id": "cursor-model-b"},
        ]
        assert pi == [{"id": "openrouter/model-a", "recommended": True}]
        assert providers == [{"provider": "openrouter", "id": "provider-model-a", "recommended": True}]
        assert review["claude"] == {"lanes": "inherit", "verifier": "inherit"}
        assert review["gemini"] == {"lanes": "pro", "verifier": "pro"}

    def test_cursor_policy_fails_closed_when_missing_empty_or_unrecognized(self):
        from ai_models import load_cursor_models

        cases = {
            "missing": "copilot_models:\n  - id: model-a\n",
            "empty": "cursor_models:\ncopilot_models:\n",
            "unrecognized": "cursor_models:\n  models: cursor-model-a\n",
            "absent file": None,
        }
        for name, contents in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                if contents is not None:
                    (Path(directory) / "harness-catalogs.yaml").write_text(contents)
                with self.assertRaisesRegex(ValueError, "cursor_models"):
                    load_cursor_models(directory)

    def test_load_model_bands(self):
        from ai_models import load_model_bands

        bands = load_model_bands(str(FIXTURES / "ai_models"))
        assert set(bands.keys()) == {"claude_code", "codex"}
        assert bands["claude_code"]["cheap"] == {
            "model": "model-b",
            "effort": "high",
            "thinking": "no",
            "context": "short",
        }
        assert bands["claude_code"]["max"] == {
            "model": "model-a",
            "effort": "high",
            "thinking": "off",
            "context": "long",
            "counter": {
                "model": "model-counter",
                "effort": "medium",
                "context": "long",
            },
        }
        assert bands["codex"]["max"] == {
            "model": "codex-max",
            "effort": "xhigh",
            "thinking": "",
            "context": "short",
        }

    def test_load_agent_categories_and_bindings(self):
        from ai_models import load_agent_bindings, load_agent_categories

        path = str(FIXTURES / "ai_models")
        assert load_agent_categories(path)["refute"] == {"band": "max", "family": "counter"}
        assert load_agent_bindings(path) == {
            "code-searcher": "search",
            "reviewer": "review",
            "adversarial-verifier": "refute",
        }

    def test_resolve_agent_model_reports_a_missing_counter_as_degraded(self):
        from ai_models import resolve_agent_model

        path = str(FIXTURES / "ai_models")
        assert resolve_agent_model(path, "claude_code", "code-searcher")["model"] == "model-b"

        refuter = resolve_agent_model(path, "claude_code", "adversarial-verifier")
        assert refuter["model"] == "model-counter"
        assert refuter["degraded"] is False

        # An unbound agent has no category, so there is no band to pin it to.
        assert resolve_agent_model(path, "claude_code", "not-an-agent") is None

    def test_resolve_review_agent_model_uses_overrides_and_bands(self):
        from ai_models import resolve_review_agent_model

        path = str(FIXTURES / "ai_models")

        claude_lane = resolve_review_agent_model(path, "claude", "reviewer")
        assert claude_lane["model"] == "inherit"
        assert claude_lane["slot"] == "lanes"
        assert claude_lane["source"] == "override"

        claude_refuter = resolve_review_agent_model(path, "claude_code", "adversarial-verifier")
        assert claude_refuter["model"] == "inherit"
        assert claude_refuter["slot"] == "verifier"
        assert claude_refuter["source"] == "override"
        assert claude_refuter["degraded"] is True
        assert claude_refuter["verifier_status"] == "degraded"

        gemini = resolve_review_agent_model(path, "gemini", "reviewer")
        assert gemini["model"] == "pro"
        assert gemini["source"] == "override"

        codex_lane = resolve_review_agent_model(path, "codex", "reviewer")
        assert codex_lane["model"] == "codex-max"
        assert codex_lane["slot"] == "lanes"
        assert codex_lane["source"] == "model_bands"
        assert codex_lane["degraded"] is False

        codex_refuter = resolve_review_agent_model(path, "codex", "adversarial-verifier")
        assert codex_refuter["model"] == "codex-max"
        assert codex_refuter["slot"] == "verifier"
        assert codex_refuter["source"] == "model_bands"
        assert codex_refuter["degraded"] is True
        assert codex_refuter["verifier_status"] == "degraded"

        assert resolve_review_agent_model(path, "codex", "not-an-agent") is None
        assert resolve_review_agent_model(path, "missing", "reviewer") is None

    def test_band_entries_keep_empty_strings_and_trailing_comments(self):
        from ai_models import load_model_bands

        content = (
            "model_bands:\n"
            "  claude_code:\n"
            "    cheap:\n"
            '      model: "x" # trailing comment\n'
            '      effort: ""\n'
            '      context: ""\n'
            "agent_bindings:\n"
            "  other: search\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "tiering.yaml").write_text(content)
            bands = load_model_bands(directory)
        assert bands == {"claude_code": {"cheap": {"model": "x", "effort": "", "context": ""}}}

    def test_a_flow_map_band_is_not_silently_read_as_a_pick(self):
        from ai_models import load_model_bands

        content = 'model_bands:\n  claude_code:\n    cheap: { model: "x", effort: "high" }\n'
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "tiering.yaml").write_text(content)
            bands = load_model_bands(directory)
        assert bands["claude_code"]["cheap"] == '{ model: "x", effort: "high" }'

    def test_sections_resolve_to_their_own_file(self):
        from ai_models import SECTION_FILES, section_path

        assert section_path("/registry", "model_bands").name == "tiering.yaml"
        assert section_path("/registry", "cursor_models").name == "harness-catalogs.yaml"
        with self.assertRaisesRegex(ValueError, "unknown registry section"):
            section_path("/registry", "not_a_section")
        for name in SECTION_FILES.values():
            assert (FIXTURES / "ai_models" / name).is_file()

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

    def test_claude_openrouter_pins_subagent_models(self):
        wrapper = (REPO / "home/exact_bin/executable_,claude-openrouter").read_text()

        assert 'export CLAUDE_CODE_SUBAGENT_MODEL="$OPENROUTER_WIRE_MODEL"' in wrapper


if __name__ == "__main__":
    unittest.main()
