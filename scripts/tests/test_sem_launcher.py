#!/usr/bin/env python3
"""Pins the hardened `,sem` launcher and its chezmoi-managed telemetry state."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / "home" / "exact_bin" / "executable_,sem"
STATE = REPO / "home" / "dot_sem" / "readonly_telemetry.json"
SKILL = REPO / "home" / "exact_dot_agents" / "exact_skills" / "exact_k-sem" / "readonly_SKILL.md"


class SemLauncherTests(unittest.TestCase):
    def test_SHOULD_force_telemetry_update_check_and_network_off(self):
        text = LAUNCHER.read_text()
        for var in ("DO_NOT_TRACK=1", "SEM_NO_TELEMETRY=1", "SEM_NO_UPDATE_CHECK=1", "SEM_NO_NETWORK=1"):
            self.assertIn(var, text)
        self.assertIn('exec "$(brew --prefix sem-cli)/bin/sem" "$@"', text)
        self.assertNotIn("brew --prefix sem)", text)

    def test_SHOULD_manage_telemetry_state_as_off(self):
        state = json.loads(STATE.read_text())
        self.assertEqual(state["mode"], "off")
        self.assertTrue(state["notice_shown"])

    def test_SHOULD_ban_network_subcommands_in_skill(self):
        text = SKILL.read_text()
        self.assertIn("NEVER run `telemetry on`, `cloud enable`/`cloud share`, `login`, or `update`", text)
        self.assertIn("NEVER run an indexed subcommand unless the user explicitly asks for it", text)


if __name__ == "__main__":
    unittest.main()
