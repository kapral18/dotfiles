#!/usr/bin/env python3
"""Tests for the OMP chezmoi migration surface."""

from __future__ import annotations

import subprocess
import tempfile
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO


class TestOmpMigration(unittest.TestCase):
    """WHEN wiring OMP into the repo-owned AI workflow."""

    def test_brewfile_installs_omp_from_upstream_tap(self):
        brewfile = REPO / "home/.chezmoitemplates/brews/shared/38-ai-large-language-models.brewfile"
        text = brewfile.read_text()

        self.assertIn('tap "can1357/tap"', text)
        self.assertIn('brew "can1357/tap/omp"', text)

    def render_omp_config(self, is_work: bool) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml") as config:
            config.write(f"[data]\nisWork = {str(is_work).lower()}\n")
            config.flush()
            result = subprocess.run(
                [
                    "chezmoi",
                    "--config",
                    config.name,
                    "execute-template",
                    (REPO / "home/dot_omp/private_agent/readonly_config.yml.tmpl").read_text(),
                ],
                cwd=REPO,
                check=True,
                capture_output=True,
                text=True,
            )
        return result.stdout

    def test_config_renders_profile_specific_model_roles(self):
        expected_values = {
            True: (
                "default: openai-codex/gpt-5.5:high",
                "smol: openai-codex/gpt-5.3-codex-spark:xhigh",
                "vision: openai-codex/gpt-5.5:high",
                "slow: openai-codex/gpt-5.5:high",
                "plan: openai-codex/gpt-5.5:high",
                "task: openai-codex/gpt-5.5:high",
                "advisor: openai-codex/gpt-5.5:high",
                "modelProviderOrder:\n  - openai-codex\n  - github-copilot\n  - openrouter\n  - anthropic\n  - openai\n",
            ),
            False: (
                "default: openai-codex/gpt-5.5:high",
                "smol: openai-codex/gpt-5.3-codex-spark:xhigh",
                "vision: openai-codex/gpt-5.5:high",
                "slow: openai-codex/gpt-5.5:high",
                "plan: openai-codex/gpt-5.5:high",
                "task: openai-codex/gpt-5.5:high",
                "advisor: openai-codex/gpt-5.5:high",
                "modelProviderOrder:\n  - openai-codex\n  - github-copilot\n  - openrouter\n  - anthropic\n  - openai\n",
            ),
        }
        shared_values = (
            "modelRoles:\n",
            "advisor:\n  enabled: true\n  subagents: true\n  syncBacklog: 1\n  immuneTurns: 0\n",
            "defaultThinkingLevel: medium\n",
            "memory:\n  backend: off\n",
            "autolearn:\n  enabled: false\n  autoContinue: false\n",
            "dev:\n  autoqaConsent: granted\n",
            "skills:\n  enabled: true\n  enableSkillCommands: true\n",
            "task:\n  isolation:\n    mode: auto\n  enableEffort: true\n  enableLsp: true\n  maxRecursionDepth: 2\n",
            "retry:\n  enabled: true\n  maxRetries: 5\n",
            "symbolPreset: nerd\n",
            "theme:\n  dark: titanium\n",
            "setupVersion: 1\n",
        )

        for is_work, values in expected_values.items():
            with self.subTest(is_work=is_work):
                config = self.render_omp_config(is_work)

                self.assertNotIn("{{", config)
                for value in (*values, *shared_values):
                    self.assertIn(value, config)

    def test_system_policy_appends_without_replacing_omp_prompt(self):
        agent_dir = REPO / "home/dot_omp/private_agent"

        self.assertTrue((agent_dir / "readonly_APPEND_SYSTEM.md").is_file())
        self.assertTrue((agent_dir / "readonly_RULES.md").is_file())
        self.assertFalse((agent_dir / "readonly_SYSTEM.md").exists())
        self.assertFalse((agent_dir / "SYSTEM.md").exists())

    def test_skills_root_points_at_shared_skill_corpus(self):
        target = (REPO / "home/dot_omp/private_agent/symlink_skills").read_text().strip()

        self.assertEqual(target, "../../.agents/skills")

    def test_extensions_use_current_omp_package_import(self):
        extensions = REPO / "home/dot_omp/private_agent/extensions"
        expected = ["ai-kb-recall.ts", "runtime-parity.ts"]

        for name in expected:
            text = (extensions / name).read_text()
            self.assertIn("@oh-my-pi/pi-coding-agent", text)
            self.assertNotIn("@earendil-works/pi-coding-agent", text)

    def test_selected_agents_use_omp_frontmatter_schema(self):
        agents = REPO / "home/dot_omp/private_agent/exact_agents"
        required = {
            "researcher",
            "reviewer",
            "review-controller",
            "code-searcher",
            "change-auditor",
            "findings-auditor",
            "live-ui-review",
            "post-review",
            "pr-necessity-auditor",
            "adversarial-verifier",
            "fresh-eyes",
            "criteria-verifier",
        }
        seen = {p.name.removesuffix(".md.tmpl") for p in agents.glob("*.md.tmpl")}

        self.assertEqual(required - seen, set())

        legacy = (
            "systemPromptMode:",
            "inheritProjectContext:",
            "inheritSkills:",
            "skills:",
            "maxSubagentDepth:",
        )
        for path in agents.glob("*.md.tmpl"):
            text = path.read_text()
            for marker in legacy:
                self.assertNotIn(marker, text, f"{path} has legacy frontmatter {marker}")
            self.assertIn("name:", text)
            self.assertIn("description:", text)
            self.assertIn(".omp", text)
            self.assertNotIn(".pi", text)


if __name__ == "__main__":
    unittest.main()
