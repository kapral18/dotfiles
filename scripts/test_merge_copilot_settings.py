#!/usr/bin/env python3
"""Tests for merge_copilot_settings.py."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO, SCRIPTS
from merge_copilot_settings import merge_copilot_settings

SCRIPT = SCRIPTS / "merge_copilot_settings.py"


class TestMergeCopilotSettings(unittest.TestCase):
    """WHEN live Copilot settings are reconciled with declared policy."""

    def test_SHOULD_preserve_undeclared_runtime_state_and_replace_agents_exactly(self):
        live = {
            "model": "claude-opus-4.8",
            "allowedUrls": ["github.com"],
            "effortLevel": "low",
            "subagents": {
                "runtimeOnly": {"keep": True},
                "agents": {
                    "review-worker": {"model": "stale", "effortLevel": "low"},
                    "removed-reviewer": {"model": "obsolete"},
                },
            },
            "ui": {"theme": "dark", "nested": {"liveOnly": True, "baselineWins": "live"}},
        }
        baseline = {
            "effortLevel": "xhigh",
            "subagents": {
                "agents": {
                    "review-worker": {"effortLevel": "xhigh", "contextTier": "long_context"},
                    "adversarial-verifier": {"effortLevel": "xhigh", "contextTier": "long_context"},
                }
            },
            "ui": {"density": "compact", "nested": {"baselineWins": "baseline", "declaredOnly": True}},
        }

        merged = merge_copilot_settings(live, baseline)

        self.assertEqual(merged["model"], "claude-opus-4.8")
        self.assertEqual(merged["allowedUrls"], ["github.com"])
        self.assertEqual(merged["effortLevel"], "xhigh")
        self.assertEqual(merged["subagents"]["runtimeOnly"], {"keep": True})
        self.assertEqual(merged["subagents"]["agents"], baseline["subagents"]["agents"])
        self.assertEqual(
            merged["ui"],
            {
                "theme": "dark",
                "density": "compact",
                "nested": {"liveOnly": True, "baselineWins": "baseline", "declaredOnly": True},
            },
        )

    def test_SHOULD_let_declared_types_replace_runtime_types(self):
        baseline = {"subagents": {"agents": {}}, "object": {"declared": True}, "list": ["declared"]}
        merged = merge_copilot_settings(
            {"subagents": {"agents": {"stale": {}}}, "object": "runtime", "list": {"runtime": True}},
            baseline,
        )
        self.assertEqual(merged["object"], {"declared": True})
        self.assertEqual(merged["list"], ["declared"])
        self.assertEqual(merged["subagents"]["agents"], {})

    def test_SHOULD_fail_closed_on_malformed_or_structurally_invalid_inputs(self):
        cases = {
            "invalid live JSON": ("{", '{"subagents":{"agents":{}}}'),
            "non-object live root": ("[]", '{"subagents":{"agents":{}}}'),
            "non-object live subagents": ('{"subagents":[]}', '{"subagents":{"agents":{}}}'),
            "non-object live agents": ('{"subagents":{"agents":[]}}', '{"subagents":{"agents":{}}}'),
            "non-object baseline root": ("{}", "[]"),
            "missing baseline subagents": ("{}", "{}"),
            "non-object baseline subagents": ("{}", '{"subagents":[]}'),
            "missing baseline agents": ("{}", '{"subagents":{}}'),
            "non-object baseline agents": ("{}", '{"subagents":{"agents":[]}}'),
        }
        for label, (live_text, baseline_text) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                live_path = root / "live.json"
                baseline_path = root / "baseline.json"
                live_path.write_text(live_text)
                baseline_path.write_text(baseline_text)
                result = subprocess.run(
                    ["python3", str(SCRIPT), str(live_path), str(baseline_path)],
                    cwd=REPO,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("Error:", result.stderr)

    def test_SHOULD_wire_the_typed_reconciler_into_the_hash_gated_hook(self):
        hook = (REPO / "home/.chezmoiscripts/run_onchange_after_07-merge-copilot-config.sh.tmpl").read_text()
        self.assertIn("../scripts/merge_copilot_settings.py", hook)
        self.assertTrue(
            any("merge_copilot_settings.py" in line for line in hook.splitlines() if "hash" in line.lower())
        )
        self.assertNotIn("jq -s '.[0] * .[1]'", hook)
        self.assertNotIn('desired_settings="$(cat "$settings_src")"', hook)
        self.assertEqual(hook.count('python3 "$settings_merge"'), 1)
        delete = 'rm -f "$HOME/.copilot/hooks/agent-memory.json"'
        unregister = 'chezmoi_forget_checksum "$HOME/.copilot/hooks/agent-memory.json"'
        self.assertIn(delete, hook)
        self.assertIn(unregister, hook)
        self.assertLess(hook.index(delete), hook.index(unregister))


if __name__ == "__main__":
    unittest.main()
