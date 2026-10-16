#!/usr/bin/env python3
"""Tests for the OMP chezmoi migration surface."""

from __future__ import annotations

import json
import subprocess
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO


class TestOmpMigration(unittest.TestCase):
    """WHEN wiring OMP into the repo-owned AI workflow."""

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
