#!/usr/bin/env python3
"""Tests for the OMP chezmoi migration surface."""

from __future__ import annotations

import re
import subprocess
import tempfile
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO

# OMP 17.2.15 SEARCH_PROVIDER_ORDER. Listing perplexity in webSearchOrder makes
# it explicit and routes through OpenRouter sonar-pro. Unlisted ids stay in the
# fallback chain, so exclude must be every id not in the profile's order.
OMP_SEARCH_PROVIDER_ORDER = (
    "perplexity",
    "gemini",
    "anthropic",
    "codex",
    "xai",
    "zai",
    "exa",
    "tinyfish",
    "jina",
    "kagi",
    "tavily",
    "firecrawl",
    "brave",
    "kimi",
    "parallel",
    "synthetic",
    "searxng",
    "startpage",
    "duckduckgo",
    "ecosia",
    "google",
    "mojeek",
    "public",
)
OMP_KEYLESS_SEARCH_PROVIDERS = ("startpage", "duckduckgo", "ecosia", "google", "mojeek", "public")
WORK_WEB_SEARCH_ORDER = ("codex", "gemini", "google", "duckduckgo")
PERSONAL_WEB_SEARCH_ORDER = ("codex", *OMP_KEYLESS_SEARCH_PROVIDERS)

YAML_LIST_RE = re.compile(
    r"(?m)^(?P<indent> *)(?P<key>webSearch(?:Order|Exclude)):\n(?P<body>(?:(?P=indent)  - .+\n)+)"
)


def _yaml_string_list(config: str, key: str) -> list[str]:
    for match in YAML_LIST_RE.finditer(config):
        if match.group("key") == key:
            return [line.strip()[2:] for line in match.group("body").splitlines() if line.strip()]
    raise AssertionError(f"missing YAML list for {key}")


class TestOmpMigration(unittest.TestCase):
    """WHEN wiring OMP into the repo-owned AI workflow."""

    def test_omp_installs_via_unpinned_yarn_not_brew(self):
        brewfile = (REPO / "home/.chezmoitemplates/brews/shared/38-ai-large-language-models.brewfile").read_text()
        yarn_pkgs = (REPO / "home/readonly_dot_default-yarn-pkgs").read_text()

        self.assertNotIn("can1357/tap/omp", brewfile)
        self.assertIn("@oh-my-pi/pi-coding-agent\n", yarn_pkgs)
        self.assertNotIn("@oh-my-pi/pi-coding-agent@", yarn_pkgs)

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
            # OMP work defaults primary roles to DeepSeek max while vision stays on Kimi high.
            # Personal keeps the Cursor pins, with vision on kimi-k3-high too.
            True: (
                "default: openrouter/deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max:max",
                "smol: openrouter/deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max:max",
                "vision: openrouter/moonshotai/kimi-k3@preset/kimi-lanes:high",
                "slow: openrouter/deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max:max",
                "plan: openrouter/deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max:max",
                "task: openrouter/deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max:max",
                "advisor: openrouter/deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max:max",
                "modelProviderOrder:\n  - openrouter\n  - cursor\n  - openai-codex\n  - anthropic\n  - openai\n",
            ),
            False: (
                "default: cursor/kimi-k3-high:high",
                "smol: cursor/composer-2.5:high",
                "vision: cursor/kimi-k3-high:high",
                "slow: cursor/kimi-k3-high:high",
                "plan: cursor/kimi-k3-high:high",
                "task: cursor/kimi-k3-high:high",
                "advisor: cursor/kimi-k3-high:high",
                "modelProviderOrder:\n  - cursor\n  - openai-codex\n  - openrouter\n  - anthropic\n  - openai\n",
            ),
        }
        shared_values = (
            "modelRoles:\n",
            "advisor:\n  enabled: true\n  subagents: true\n  syncBacklog: 1\n  immuneTurns: 0\n",
            "defaultThinkingLevel: high\n",
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

    def test_web_search_uses_profile_specific_provider_chains(self):
        expected = {
            True: WORK_WEB_SEARCH_ORDER,
            False: PERSONAL_WEB_SEARCH_ORDER,
        }
        for is_work, wanted_order in expected.items():
            with self.subTest(is_work=is_work):
                config = self.render_omp_config(is_work)
                order = tuple(_yaml_string_list(config, "webSearchOrder"))
                exclude = tuple(_yaml_string_list(config, "webSearchExclude"))
                leftover = tuple(provider for provider in OMP_SEARCH_PROVIDER_ORDER if provider not in wanted_order)

                self.assertEqual(order, wanted_order)
                self.assertEqual(exclude, leftover)
                self.assertIn("perplexity", exclude)
                self.assertNotIn("perplexity", order)
                self.assertEqual(set(order) & set(exclude), set())

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
            # Review roles read `.agent_review_models.omp`; the rest resolve a band through
            # agent-model.partial. Either way the harness is named, and a Pi copy-paste is the
            # failure this guards against.
            self.assertTrue(
                ".agent_review_models.omp" in text or '"harness" "omp"' in text,
                f"{path} does not resolve its model from an omp registry entry",
            )
            self.assertNotIn(".agent_review_models.pi", text)
            self.assertNotIn('"harness" "pi"', text)


if __name__ == "__main__":
    unittest.main()
