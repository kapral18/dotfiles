#!/usr/bin/env python3
"""Tests for the OMP chezmoi migration surface."""

from __future__ import annotations

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

    def test_config_preserves_managed_omp_values(self):
        config = (REPO / "home/dot_omp/private_agent/config.yml").read_text()
        expected_values = (
            "modelRoles:\n",
            "default: github-copilot/gpt-5.6-terra:medium",
            "smol: github-copilot/gpt-5.6-terra:low",
            "slow: github-copilot/gpt-5.5:medium",
            "plan: github-copilot/gpt-5.5:medium",
            "advisor: github-copilot/gpt-5.5:medium",
            "advisor:\n  enabled: true\n",
            "modelProviderOrder:\n  - github-copilot\n  - openrouter\n  - anthropic\n  - openai\n",
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

        for value in expected_values:
            with self.subTest(value=value):
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
