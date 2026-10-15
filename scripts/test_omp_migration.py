#!/usr/bin/env python3
"""Tests for the OMP chezmoi migration surface."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO

# OMP 17.2.15 SEARCH_PROVIDER_ORDER. Listing perplexity in webSearchOrder makes
# it explicit and routes through OpenRouter sonar-pro. Unlisted ids stay in the
# fallback chain, so exclude must be every id not in the order.
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
WEB_SEARCH_ORDER = ("codex", *OMP_KEYLESS_SEARCH_PROVIDERS)

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

    def render_omp_config(self) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml") as config:
            config.write("[data]\n")
            config.flush()
            result = subprocess.run(
                [
                    "chezmoi",
                    "--config",
                    config.name,
                    "--source",
                    str(REPO / "home"),
                    "execute-template",
                    (REPO / "home/dot_omp/private_agent/readonly_config.yml.tmpl").read_text(),
                ],
                cwd=REPO,
                check=True,
                capture_output=True,
                text=True,
            )
        return result.stdout

    def test_config_renders_the_model_roles_block(self):
        # Working roles use the Claude subscription, the advisor and web search stay on Codex;
        # category and effort relationships are covered by the band invariants.
        expected_roles = {"default", "smol", "slow", "vision", "plan", "commit", "tiny", "task", "advisor", "web"}

        config = self.render_omp_config()
        self.assertNotIn("{{", config)
        roles = config.split("modelRoles:\n", 1)[1].split("\n\n", 1)[0]
        pairs = dict(re.findall(r"(?m)^  ([a-z]+): (.+)$", roles))
        self.assertEqual(set(pairs), expected_roles)
        self.assertEqual(pairs["advisor"], "openai-codex/gpt-6-astra:high")
        self.assertEqual(pairs["web"], "openai-codex/gpt-6-luna")
        working = {role: model for role, model in pairs.items() if role not in {"advisor", "web"}}
        self.assertTrue(all(model.startswith("anthropic/claude-") for model in working.values()), working)

    def test_web_search_uses_codex_then_keyless_providers(self):
        config = self.render_omp_config()
        order = tuple(_yaml_string_list(config, "webSearchOrder"))
        exclude = tuple(_yaml_string_list(config, "webSearchExclude"))
        leftover = tuple(provider for provider in OMP_SEARCH_PROVIDER_ORDER if provider not in WEB_SEARCH_ORDER)

        self.assertEqual(order, WEB_SEARCH_ORDER)
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

    def test_watchdog_replaces_default_advisor_with_final_answer_gate(self):
        path = REPO / "home/dot_omp/private_agent/readonly_WATCHDOG.yml"
        # OMP parses WATCHDOG.yml with Bun's YAML parser.
        result = subprocess.run(
            [
                "bun",
                "-e",
                "console.log(JSON.stringify(Bun.YAML.parse(await Bun.file(process.argv[1]).text())))",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        advisors = {entry["name"]: entry for entry in json.loads(result.stdout)["advisors"]}

        # A per-turn advisor would steer mid-run and share Gate's interrupt cooldown.
        self.assertEqual(list(advisors), ["Gate"])
        gate = advisors["Gate"]
        self.assertEqual((gate["reviewMode"], gate["syncBacklog"]), ("agent-end", "strict"))
        self.assertNotIn("model", gate)
        self.assertNotIn("tools", gate)
        # Gate judges against the SOP instead of restating its rules.
        self.assertIn("~/AGENTS.md", gate["instructions"])

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
