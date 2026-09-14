#!/usr/bin/env python3
"""Tests for ai_models.py."""

from __future__ import annotations

import json
import re
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
        )

        path = FIXTURES / "ai_models"
        cursor = load_cursor_models(path)
        pi = load_pi_extra_models(path)
        providers = load_provider_models(path)

        assert cursor == [
            {"id": "cursor-model-a", "recommended": True},
            {"id": "cursor-model-b"},
        ]
        assert pi == [{"id": "openrouter/model-a", "recommended": True}]
        assert providers == [{"provider": "openrouter", "id": "provider-model-a", "recommended": True}]

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

    def test_load_session_models(self):
        from ai_models import load_session_models

        session_models = load_session_models(str(FIXTURES / "ai_models"))
        assert session_models["claude_code"] == {
            "model": "session-claude",
            "effort": "high",
            "context": "long",
        }
        assert session_models["antigravity"]["model"] == "session-gemini"
        assert session_models["codex"]["effort"] == "high"

    def test_load_category_models(self):
        from ai_models import load_category_models

        category_models = load_category_models(str(FIXTURES / "ai_models"))
        assert set(category_models.keys()) == {"claude_code", "antigravity", "codex"}
        assert category_models["claude_code"]["lookup"] == {
            "model": "model-b",
            "effort": "high",
            "thinking": "no",
            "context": "short",
        }
        assert category_models["claude_code"]["refute"] == {
            "model": "model-counter",
            "effort": "medium",
            "thinking": "off",
            "context": "long",
            "verifier_status": "cross_family",
        }
        assert category_models["claude_code"]["review"] == {
            "model": "model-a",
            "effort": "high",
            "thinking": "off",
            "context": "long",
        }
        assert category_models["codex"]["refute"] == {
            "model": "codex-max",
            "effort": "xhigh",
            "thinking": "",
            "context": "short",
            "verifier_status": "degraded",
        }

    def test_load_agent_categories_and_bindings(self):
        from ai_models import load_agent_bindings, load_agent_categories

        path = str(FIXTURES / "ai_models")
        assert load_agent_categories(path)["refute"] == {
            "family": "counter",
            "contract": "adversarial-verification",
        }
        assert load_agent_bindings(path) == {
            "k-agent-code-searcher": "research",
            "k-agent-reviewer": "review",
            "k-agent-adversarial-verifier": "refute",
        }

    def test_resolve_agent_model_reports_a_missing_counter_as_degraded(self):
        from ai_models import resolve_agent_model

        path = str(FIXTURES / "ai_models")
        assert resolve_agent_model(path, "claude_code", "k-agent-code-searcher")["model"] == "model-c"

        refuter = resolve_agent_model(path, "claude_code", "k-agent-adversarial-verifier")
        assert refuter["model"] == "model-counter"
        assert refuter["degraded"] is False

        # An unbound agent has no category, so there is no matrix row to pin it to.
        assert resolve_agent_model(path, "claude_code", "not-an-agent") is None

    def test_resolve_agent_model_rejects_a_binding_to_an_unknown_category(self):
        from ai_models import resolve_agent_model

        content = (
            "agent_categories:\n"
            "  research:\n"
            '    family: "primary"\n'
            '    contract: "evidence-synthesis"\n'
            "agent_bindings:\n"
            "  Plan: orchestrate\n"
            "category_models:\n"
            "  claude_code:\n"
            "    research:\n"
            '      model: "x"\n'
            '      effort: "high"\n'
            '      context: "long"\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "tiering.yaml").write_text(content)
            with self.assertRaisesRegex(ValueError, "orchestrate"):
                resolve_agent_model(directory, "claude_code", "Plan")

    def test_resolve_review_agent_model_uses_category_models(self):
        from ai_models import load_category_models, resolve_review_agent_model

        path = str(FIXTURES / "ai_models")
        category_models = load_category_models(path)

        claude_lane = resolve_review_agent_model(path, "claude", "k-agent-reviewer")
        assert claude_lane["model"] == category_models["claude_code"]["review"]["model"]
        assert claude_lane["slot"] == "lanes"
        assert claude_lane["source"] == "category_models"
        assert claude_lane["band_harness"] == "claude_code"

        claude_refuter = resolve_review_agent_model(path, "claude_code", "k-agent-adversarial-verifier")
        assert claude_refuter["model"] == category_models["claude_code"]["refute"]["model"]
        assert claude_refuter["slot"] == "verifier"
        assert claude_refuter["source"] == "category_models"
        # The fixture row declares cross_family; the resolver reports the row's status, not a
        # harness-level assumption.
        assert claude_refuter["degraded"] is False
        assert claude_refuter["verifier_status"] == "cross_family"

        antigravity = resolve_review_agent_model(path, "antigravity", "k-agent-reviewer")
        assert antigravity["model"] == category_models["antigravity"]["review"]["model"]
        assert antigravity["source"] == "category_models"
        assert antigravity["band_harness"] == "antigravity"

        codex_lane = resolve_review_agent_model(path, "codex", "k-agent-reviewer")
        assert codex_lane["model"] == "codex-max"
        assert codex_lane["slot"] == "lanes"
        assert codex_lane["source"] == "category_models"
        assert codex_lane["degraded"] is False

        codex_refuter = resolve_review_agent_model(path, "codex", "k-agent-adversarial-verifier")
        assert codex_refuter["model"] == "codex-max"
        assert codex_refuter["slot"] == "verifier"
        assert codex_refuter["source"] == "category_models"
        assert codex_refuter["degraded"] is True
        assert codex_refuter["verifier_status"] == "degraded"

        assert resolve_review_agent_model(path, "codex", "not-an-agent") is None
        assert resolve_review_agent_model(path, "missing", "k-agent-reviewer") is None

    def test_category_model_entries_keep_empty_strings_and_trailing_comments(self):
        from ai_models import load_category_models

        content = (
            "category_models:\n"
            "  claude_code:\n"
            "    lookup:\n"
            '      model: "x" # trailing comment\n'
            '      effort: ""\n'
            '      context: ""\n'
            "agent_bindings:\n"
            "  other: lookup\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "tiering.yaml").write_text(content)
            category_models = load_category_models(directory)
        assert category_models == {"claude_code": {"lookup": {"model": "x", "effort": "", "context": ""}}}

    def test_a_flow_map_category_model_is_not_silently_read_as_a_pick(self):
        from ai_models import load_category_models

        content = 'category_models:\n  claude_code:\n    lookup: { model: "x", effort: "high" }\n'
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "tiering.yaml").write_text(content)
            category_models = load_category_models(directory)
        assert category_models["claude_code"]["lookup"] == '{ model: "x", effort: "high" }'

    def test_sections_resolve_to_their_own_file(self):
        from ai_models import SECTION_FILES, section_path

        assert section_path("/registry", "category_models").name == "tiering.yaml"
        assert section_path("/registry", "session_models").name == "tiering.yaml"
        assert section_path("/registry", "cursor_models").name == "harness-catalogs.yaml"
        assert section_path("/registry", "cursor_task_base_models").name == "harness-catalogs.yaml"
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

    def test_when_claude_profile_is_a_leaf_should_pin_tools_without_agent(self):
        # A Claude profile without `tools:` inherits every tool, `Agent` included, and Claude Code
        # 2.1.219+ lets subagents nest by default; the allowlist is the native no-spawn enforcement.
        agents = REPO / "home/dot_claude/exact_agents"
        tools_re = re.compile(r"^tools:\s*(?P<tools>.+)$", re.MULTILINE)
        checked = 0
        for profile in sorted(agents.glob("*.md.tmpl")):
            with self.subTest(profile=profile.name):
                text = profile.read_text(encoding="utf-8")
                front = text.split("---", 2)[1]
                match = tools_re.search(front)
                assert match, f"{profile.name} has no tools: allowlist"
                tools = [tool.strip() for tool in match.group("tools").split(",")]
                assert "Agent" not in tools, f"{profile.name} exposes the Agent tool to a leaf"
                assert "disallowedTools:" not in front, f"{profile.name} mixes a denylist with the allowlist"
                checked += 1
        assert checked >= 20

    def test_when_claude_root_settings_load_should_turn_subagent_nesting_off(self):
        for name in ("settings.work.json", "settings.personal.json"):
            with self.subTest(settings=name):
                settings = json.loads((REPO / "home/dot_claude" / name).read_text(encoding="utf-8"))
                assert settings["env"]["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"] == "1"
        for name in ("settings.llama-cpp.json.tmpl", "settings.llama-cpp.qwen3.8.json.tmpl"):
            with self.subTest(settings=name):
                text = (REPO / "home/dot_claude" / name).read_text(encoding="utf-8")
                assert '"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1"' in text

    def test_claude_openrouter_subagents_use_pi_backend_schema(self):
        wrapper = (REPO / "home/exact_bin/executable_,claude-openrouter").read_text()

        assert "unset CLAUDE_CODE_SUBAGENT_MODEL" in wrapper
        assert 'exec python3 "$HOME/lib/shared/claude_lanes.py" pi -- claude' in wrapper
        assert 'export AGENT_BAND_SCHEMA_HARNESS="pi"' in wrapper
        assert 'export AGENT_BAND_MODEL_FORMAT="openrouter-preset"' in wrapper


if __name__ == "__main__":
    unittest.main()
