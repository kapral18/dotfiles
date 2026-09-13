#!/usr/bin/env python3
"""Tests for generate_session_models.py."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import generate_session_models
from _test_support import REPO


class TestGenerateSessionModels(unittest.TestCase):
    KIND_SOURCES = (
        (
            "claude.json",
            REPO / "home/dot_claude/settings.work.json",
            generate_session_models.apply_claude,
            "claude_code",
        ),
        ("codex.toml", REPO / "home/dot_codex/private_config.work.toml", generate_session_models.apply_codex, "codex"),
        (
            "copilot.json",
            REPO / "home/private_dot_copilot/settings.json",
            generate_session_models.apply_copilot,
            "copilot",
        ),
        ("pi.json", REPO / "home/dot_pi/agent/readonly_settings.work.json", generate_session_models.apply_pi, "pi"),
        (
            "omp.yml",
            REPO / "home/dot_omp/private_agent/readonly_config.yml.tmpl",
            generate_session_models.apply_omp,
            "omp",
        ),
        (
            "antigravity.json",
            REPO / "home/dot_gemini/antigravity-cli/readonly_settings.policy.json",
            generate_session_models.apply_antigravity,
            "antigravity",
        ),
    )

    def setUp(self):
        self.session = generate_session_models.ai_models.load_session_models(generate_session_models.REGISTRY)

    def _copy_kinds(self, directory: Path) -> list[tuple[Path, dict, object]]:
        targets = []
        for name, source, apply, harness in self.KIND_SOURCES:
            dest = directory / name
            shutil.copy2(source, dest)
            targets.append((dest, self.session[harness], apply))
        return targets

    def test_write_on_temp_copies_of_the_six_kinds_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            targets = self._copy_kinds(directory)
            self.assertEqual(0, generate_session_models.reconcile("write", targets))
            first = {path: path.read_text(encoding="utf-8") for path, _, _ in targets}
            self.assertEqual(0, generate_session_models.reconcile("write", targets))
            second = {path: path.read_text(encoding="utf-8") for path, _, _ in targets}
            self.assertEqual(first, second)
            self.assertEqual(0, generate_session_models.reconcile("check", targets))

    def test_check_mode_flags_a_drifted_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            targets = self._copy_kinds(directory)
            self.assertEqual(0, generate_session_models.reconcile("write", targets))
            drifted = next(path for path, _, apply in targets if apply is generate_session_models.apply_claude)
            settings = json.loads(drifted.read_text(encoding="utf-8"))
            settings["model"] = "drifted-model"
            drifted.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(1, generate_session_models.reconcile("check", targets))

    # Each apply_* is driven with a row that differs from the committed file on every field, so a
    # generator that silently drops or misplaces a field cannot hide behind already-matching sources.
    DRIFT = {"model": "vendor/drift-model-9", "effort": "low", "context": "short"}

    def test_apply_claude_writes_model_both_effort_slots_and_keeps_other_model_settings(self):
        current = (REPO / "home/dot_claude/settings.work.json").read_text(encoding="utf-8")
        before = json.loads(current)
        before["modelSettings"]["other-model"] = {"effortLevel": "max"}
        current = json.dumps(before, indent=2) + "\n"
        after = json.loads(generate_session_models.apply_claude(current, self.DRIFT))
        self.assertEqual("vendor/drift-model-9", after["model"])
        self.assertEqual("low", after["effortLevel"])
        self.assertEqual("low", after["modelSettings"]["vendor/drift-model-9"]["effortLevel"])
        self.assertEqual({"effortLevel": "max"}, after["modelSettings"]["other-model"])
        self.assertEqual(before["alwaysThinkingEnabled"], after["alwaysThinkingEnabled"])

    def test_apply_codex_rewrites_only_the_top_level_model_and_effort_lines(self):
        current = (REPO / "home/dot_codex/private_config.work.toml").read_text(encoding="utf-8")
        after = generate_session_models.apply_codex(current, self.DRIFT)
        self.assertIn('\nmodel = "vendor/drift-model-9"\n', after)
        self.assertIn('\nmodel_reasoning_effort = "low"\n', after)
        self.assertEqual(current.count("\n"), after.count("\n"))
        self.assertEqual(
            [line for line in current.splitlines() if line.startswith("[")],
            [line for line in after.splitlines() if line.startswith("[")],
        )
        with self.assertRaisesRegex(ValueError, "no top-level model assignment"):
            generate_session_models.apply_codex('approval_policy = "never"\n', self.DRIFT)
        with self.assertRaisesRegex(ValueError, "no top-level model_reasoning_effort"):
            generate_session_models.apply_codex('model = "x"\n', self.DRIFT)

    def test_apply_copilot_writes_root_fields_and_leaves_subagents_alone(self):
        current = (REPO / "home/private_dot_copilot/settings.json").read_text(encoding="utf-8")
        before = json.loads(current)
        after = json.loads(generate_session_models.apply_copilot(current, self.DRIFT))
        self.assertEqual("vendor/drift-model-9", after["model"])
        self.assertEqual("low", after["effortLevel"])
        self.assertEqual("default", after["contextTier"])
        self.assertEqual(before["subagents"], after["subagents"])

    def test_apply_pi_splits_provider_on_the_first_slash_and_writes_thinking(self):
        current = (REPO / "home/dot_pi/agent/readonly_settings.work.json").read_text(encoding="utf-8")
        row = {"model": "openrouter/meta/drift-9", "effort": "low", "context": "short"}
        after = json.loads(generate_session_models.apply_pi(current, row))
        self.assertEqual("openrouter", after["defaultProvider"])
        self.assertEqual("meta/drift-9", after["defaultModel"])
        self.assertEqual("low", after["defaultThinkingLevel"])
        with self.assertRaisesRegex(ValueError, "no provider/model split"):
            generate_session_models.apply_pi(current, self.DRIFT | {"model": "no-slash"})

    def test_apply_omp_rewrites_only_model_roles_default_with_effort_suffix(self):
        current = (REPO / "home/dot_omp/private_agent/readonly_config.yml.tmpl").read_text(encoding="utf-8")
        after = generate_session_models.apply_omp(current, self.DRIFT)
        self.assertIn("\n  default: vendor/drift-model-9:low\n", after)
        changed = [(old, new) for old, new in zip(current.splitlines(), after.splitlines()) if old != new]
        self.assertEqual(1, len(changed), changed)
        self.assertTrue(changed[0][0].startswith("  default: "))
        with self.assertRaisesRegex(ValueError, "no modelRoles.default line"):
            generate_session_models.apply_omp("modelRoles:\n  plan: a/b:high\nother: 1\n", self.DRIFT)
        # A `default:` line outside modelRoles is not the role pin.
        with self.assertRaisesRegex(ValueError, "no modelRoles.default line"):
            generate_session_models.apply_omp("advisor:\n  default: a/b:high\n", self.DRIFT)

    def test_apply_antigravity_renders_display_name_with_capitalized_effort(self):
        current = (REPO / "home/dot_gemini/antigravity-cli/readonly_settings.policy.json").read_text(encoding="utf-8")
        after = json.loads(
            generate_session_models.apply_antigravity(current, {"model": "gemini-3.8-flash", "effort": "low"})
        )
        self.assertEqual("Gemini 3.8 Flash (Low)", after["model"])
        self.assertEqual("gemini", after["modelProvider"])

    def test_unmapped_antigravity_id_raises(self):
        current = (REPO / "home/dot_gemini/antigravity-cli/readonly_settings.policy.json").read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unmapped antigravity model id"):
            generate_session_models.apply_antigravity(current, {"model": "not-a-gemini-id", "effort": "high"})


if __name__ == "__main__":
    unittest.main()
