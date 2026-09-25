#!/usr/bin/env python3
"""Tests for inject_codex_instructions.py: the SOP becomes the Codex root developer_instructions."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
import inject_codex_instructions as mod

BASE = 'model = "gpt-6-sol"\n\n[features]\nmulti_agent = true\n\n[agents.explorer]\nconfig_file = "~/.codex/agents/explorer.toml"\n'


def toml_loads(text: str) -> dict:
    """Parse with the stdlib TOML reader (Python >= 3.11), the same grammar Codex's config loader accepts."""
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib.loads(text)
    uv = shutil.which("uv")
    if uv is None:
        raise unittest.SkipTest("needs Python >= 3.11 or uv for a TOML parser")
    found = subprocess.run([uv, "python", "find", "3.11"], capture_output=True, text=True)
    if found.returncode != 0:
        raise unittest.SkipTest("no Python >= 3.11 interpreter available")
    code = "import json, sys, tomllib; print(json.dumps(tomllib.loads(sys.stdin.read())))"
    out = subprocess.run([found.stdout.strip(), "-c", code], input=text, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


class InjectCodexInstructionsTests(unittest.TestCase):
    def test_SHOULD_set_top_level_developer_instructions_to_the_exact_sop(self) -> None:
        for sop in (
            "# SOP\n\nUse `rg`; never `grep` \\d paths.\n",
            "Quote ''' inside and a \\ backslash and \"\"\" too\n",
        ):
            with self.subTest(sop=sop[:20]):
                data = toml_loads(mod.inject(BASE, sop))
                self.assertEqual(data["developer_instructions"], sop)
                self.assertEqual(data["model"], "gpt-6-sol")
                self.assertEqual(data["agents"]["explorer"]["config_file"], "~/.codex/agents/explorer.toml")
                self.assertNotIn("developer_instructions", data["features"])

    def test_SHOULD_refuse_a_base_that_already_sets_the_key(self) -> None:
        with self.assertRaises(ValueError):
            mod.inject('developer_instructions = "x"\n' + BASE, "SOP\n")


if __name__ == "__main__":
    unittest.main()
