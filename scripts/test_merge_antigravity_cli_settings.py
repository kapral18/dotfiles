#!/usr/bin/env python3
"""Tests for merge_antigravity_cli_settings.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO, SCRIPTS
from merge_antigravity_cli_settings import merge_antigravity_cli_settings

SCRIPT = SCRIPTS / "merge_antigravity_cli_settings.py"
HOOK = REPO / "home/.chezmoiscripts/run_onchange_after_07-merge-antigravity-cli-settings.sh.tmpl"
POLICY = REPO / "home/dot_gemini/antigravity-cli/readonly_settings.policy.json"


class TestMergeAntigravityCliSettings(unittest.TestCase):
    """WHEN Antigravity CLI settings are reconciled with declared policy."""

    def test_SHOULD_preserve_runtime_state_and_apply_declared_provider_model(self):
        live = {
            "model": "Gemini 3.1 Pro",
            "modelProvider": "gcp",
            "trustedWorkspaces": ["/tmp/live"],
            "permissions": {"allow": ["command(ls)"]},
            "statusLine": {"enabled": True},
            "gcp": {"project": "elastic-cloud-dev", "location": "global"},
        }
        policy = {
            "enableTelemetry": False,
            "modelProvider": "gemini",
            "model": "Gemini 3.1 Pro",
        }

        merged = merge_antigravity_cli_settings(live, policy)

        self.assertEqual(merged["modelProvider"], "gemini")
        self.assertEqual(merged["model"], "Gemini 3.1 Pro")
        self.assertEqual(merged["enableTelemetry"], False)
        self.assertEqual(merged["trustedWorkspaces"], ["/tmp/live"])
        self.assertEqual(merged["permissions"], {"allow": ["command(ls)"]})
        self.assertEqual(merged["statusLine"], {"enabled": True})
        self.assertNotIn("gcp", merged)

    def test_SHOULD_strip_gcp_even_when_policy_omits_it(self):
        merged = merge_antigravity_cli_settings(
            {"gcp": {"project": "elastic-kibana-184716"}, "model": "live"},
            {"modelProvider": "gemini"},
        )
        self.assertNotIn("gcp", merged)
        self.assertEqual(merged["modelProvider"], "gemini")
        self.assertEqual(merged["model"], "live")

    def test_SHOULD_accept_missing_live_file_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "missing.json"
            policy = Path(tmp) / "policy.json"
            policy.write_text(
                json.dumps({"modelProvider": "gemini", "model": "Gemini 3.1 Pro"}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(live), str(policy)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                json.loads(result.stdout),
                {"modelProvider": "gemini", "model": "Gemini 3.1 Pro"},
            )

    def test_SHOULD_pin_policy_file_to_gemini_api_key_path(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(policy["modelProvider"], "gemini")
        self.assertEqual(policy["model"], "Gemini 3.1 Pro")
        self.assertIs(policy["enableTelemetry"], False)
        self.assertNotIn("gcp", policy)

    def test_SHOULD_wire_hook_to_policy_and_merge_script(self):
        text = HOOK.read_text(encoding="utf-8")
        self.assertIn("readonly_settings.policy.json", text)
        self.assertIn("merge_antigravity_cli_settings.py", text)
        self.assertIn(".gemini/antigravity-cli/settings.json", text)


if __name__ == "__main__":
    unittest.main()
