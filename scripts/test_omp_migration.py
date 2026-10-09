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
# Work leads with "openrouter", which OMP 18.1.22 does not define as a search provider id
# (SEARCH_PROVIDER_OPTIONS in src/web/search/types.ts has no such value, and
# config/provider-globals.ts applies `.filter(isSearchProviderId)`), so the runtime drops it and
# the effective chain starts at codex. It is therefore absent from OMP_SEARCH_PROVIDER_ORDER and
# never appears in the rendered exclude list.
WORK_WEB_SEARCH_ORDER = ("openrouter", "codex", "gemini", "google", "duckduckgo")
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

    def test_omp_installs_via_unpinned_pnpm_not_brew(self):
        brewfile = (REPO / "home/.chezmoitemplates/brews/shared/38-ai-large-language-models.brewfile").read_text()
        pnpm_pkgs = (REPO / "home/readonly_dot_default-pnpm-pkgs").read_text()

        self.assertNotIn("can1357/tap/omp", brewfile)
        self.assertIn("@oh-my-pi/pi-coding-agent\n", pnpm_pkgs)
        self.assertNotIn("@oh-my-pi/pi-coding-agent@", pnpm_pkgs)

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

    def test_config_renders_one_profile_independent_model_roles_block(self):
        # The role table is profile-independent and uses the subscription provider;
        # category and effort relationships are covered by the band invariants.
        expected_roles = {"default", "smol", "slow", "vision", "plan", "commit", "tiny", "task", "advisor", "web"}
        shared_values = (
            "modelRoles:\n",
            "async:\n  enabled: true\n",
            "bash:\n  autoBackground:\n    enabled: false\n",
            "eval:\n  autoBackground:\n    enabled: false\n",
            "defaultThinkingLevel: high\n",
            "extendedContext: true\n",
            "memory:\n  backend: off\n",
            "autolearn:\n  enabled: false\n  autoContinue: false\n",
            "dev:\n  autoqaConsent: granted\n",
            "skills:\n  enabled: true\n  enableSkillCommands: true\n",
            'task:\n  isolation:\n    mode: auto\n  enableEffort: true\n  enableLsp: true\n  maxRecursionDepth: 1\n  disabledAgents:\n    - reviewer\n    - security-reviewer\n  agentAdvisor:\n    task: "off"\n',
            "retry:\n  enabled: true\n  maxRetries: 3\n",
            "symbolPreset: nerd\n",
            "theme:\n  dark: dark-catppuccin\n",
            "setupVersion: 2\n",
        )

        rendered = {is_work: self.render_omp_config(is_work) for is_work in (True, False)}
        for is_work, config in rendered.items():
            with self.subTest(is_work=is_work):
                self.assertNotIn("{{", config)
                for value in shared_values:
                    self.assertIn(value, config)
                roles = config.split("modelRoles:\n", 1)[1].split("\n\n", 1)[0]
                pairs = dict(re.findall(r"(?m)^  ([a-z]+): (.+)$", roles))
                self.assertEqual(set(pairs), expected_roles)
                self.assertEqual(pairs["web"], "openai-codex/gpt-6-luna")
                self.assertTrue(all(value.startswith("openai-codex/") for value in pairs.values()))
        self.assertEqual(
            rendered[True].split("modelRoles:\n", 1)[1].split("\n\n", 1)[0],
            rendered[False].split("modelRoles:\n", 1)[1].split("\n\n", 1)[0],
        )

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
        expected = ["context-mode.ts.tmpl"]

        for name in expected:
            text = (extensions / name).read_text()
            self.assertIn("@oh-my-pi/pi-coding-agent", text)
            self.assertNotIn("@earendil-works/pi-coding-agent", text)

    def test_selected_agents_use_omp_frontmatter_schema(self):
        agents = REPO / "home/dot_omp/private_agent/exact_agents"
        required = {"k-agent-reviewer"}
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
            self.assertIn("model:", text)


if __name__ == "__main__":
    unittest.main()
