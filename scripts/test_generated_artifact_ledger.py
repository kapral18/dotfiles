#!/usr/bin/env python3
"""Tests for the generated AI artifact ledger."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401  (puts scripts/ on sys.path)


class TestGeneratedArtifactLedger(unittest.TestCase):
    def _fixture(self, root: Path):
        source = root / "source.json"
        transform = root / "transform.py"
        target = root / "target.json"
        source.write_text('{"declared":1}\n')
        transform.write_text("# transform\n")
        target.write_text('{"declared":1,"runtime":1}\n')
        return source, transform, target

    def test_record_is_atomic_idempotent_and_forget_is_literal(self):
        import generated_artifact_ledger as ledger_module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "state/ledger.json"
            source, transform, target = self._fixture(root)
            spec = {
                "artifact_id": "fixture",
                "producer": "hook",
                "profile": "work",
                "target": str(target),
                "inputs": [str(source)],
                "transforms": [str(transform)],
                "ownership": {"adapter": "whole-file"},
                "consumer": {"id": "true", "command": ["/usr/bin/true"]},
                "live_probe": {"kind": "command", "argv": ["/usr/bin/true"]},
            }
            self.assertTrue(ledger_module.record_artifact(ledger, spec))
            before = ledger.stat()
            self.assertFalse(ledger_module.record_artifact(ledger, spec))
            after = ledger.stat()
            self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
            self.assertEqual(stat.S_IMODE(ledger.stat().st_mode), 0o600)
            self.assertEqual(list(ledger.parent.glob("ledger.json.*")), [])
            self.assertTrue(ledger_module.forget_artifact(ledger, "fixture"))
            self.assertEqual(ledger_module.load_ledger(ledger)["artifacts"], {})

    def test_json_selectors_ignore_runtime_fields_and_detect_owned_drift(self):
        import generated_artifact_ledger as ledger_module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.json"
            source, transform, target = self._fixture(root)
            spec = {
                "artifact_id": "fixture",
                "producer": "hook",
                "profile": "work",
                "target": str(target),
                "inputs": [str(source)],
                "transforms": [str(transform)],
                "ownership": {"adapter": "json-selectors", "selectors": ["declared"]},
                "consumer": {"id": "true", "command": ["/usr/bin/true"]},
                "live_probe": {"kind": "command", "argv": ["/usr/bin/true"]},
            }
            ledger_module.record_artifact(ledger, spec)
            row = ledger_module.load_ledger(ledger)["artifacts"]["fixture"]
            target.write_text('{"declared":1,"runtime":2}\n')
            self.assertEqual(ledger_module.evaluate_artifact(row)["status"], "ok")
            target.write_text('{"declared":2,"runtime":2}\n')
            self.assertEqual(ledger_module.evaluate_artifact(row)["status"], "owned-drift")

    def test_json_declared_ignores_runtime_keys_and_keeps_exact_agents_owned(self):
        import generated_artifact_ledger as ledger_module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.json"
            baseline = root / "baseline.json"
            source = root / "source.json"
            transform = root / "transform.py"
            target = root / "target.json"
            baseline.write_text(
                json.dumps(
                    {
                        "effortLevel": "xhigh",
                        "subagents": {"agents": {"review-worker": {"effortLevel": "xhigh"}}},
                    }
                )
            )
            source.write_text("source")
            transform.write_text("transform")
            target.write_text(
                json.dumps(
                    {
                        "effortLevel": "xhigh",
                        "model": "runtime-owned",
                        "subagents": {"agents": {"review-worker": {"effortLevel": "xhigh"}}},
                    }
                )
            )
            spec = {
                "artifact_id": "copilot-settings",
                "producer": "hook",
                "profile": "work",
                "target": str(target),
                "inputs": [str(baseline), str(source)],
                "transforms": [str(transform)],
                "ownership": {
                    "adapter": "json-declared",
                    "baseline_path": str(baseline),
                    "exact_selectors": ["subagents.agents"],
                },
                "consumer": {"id": "true", "command": ["/usr/bin/true"]},
                "live_probe": {"kind": "command", "argv": ["/usr/bin/true"]},
            }
            ledger_module.record_artifact(ledger, spec)
            row = ledger_module.load_ledger(ledger)["artifacts"]["copilot-settings"]

            live = json.loads(target.read_text())
            live["model"] = "another-runtime-value"
            target.write_text(json.dumps(live))
            self.assertEqual(ledger_module.evaluate_artifact(row)["status"], "ok")
            live["subagents"]["agents"]["stale"] = {"effortLevel": "low"}
            target.write_text(json.dumps(live))
            self.assertEqual(ledger_module.evaluate_artifact(row)["status"], "owned-drift")

    def test_toml_exclusions_ignore_runtime_buckets_and_detect_generated_drift(self):
        import generated_artifact_ledger as ledger_module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.json"
            source = root / "source.toml"
            transform = root / "transform.py"
            target = root / "target.toml"
            source.write_text('model = "gpt"\n')
            transform.write_text("transform")
            target.write_text(
                'model = "gpt"\n'
                '[projects."/tmp/repo"]\n'
                'trust_level = "trusted"\n'
                "[mcp_servers.slack]\n"
                'url = "https://example"\n'
                'default_tools_approval_mode = "prompt"\n'
                "[mcp_servers.slack.tools.search]\n"
                'approval_mode = "allow"\n'
                '[hooks.state."abc"]\n'
                'trusted_hash = "old"\n'
                "[tui.model_availability_nux]\n"
                '"gpt" = 3\n'
            )
            spec = {
                "artifact_id": "codex-config",
                "producer": "hook",
                "profile": "work",
                "target": str(target),
                "inputs": [str(source)],
                "transforms": [str(transform)],
                "ownership": {
                    "adapter": "toml-line-excludes",
                    "exclude_sections": [
                        r"^projects\.",
                        r"^tui\.model_availability_nux$",
                        r"^hooks\.state\.",
                        r"^mcp_servers\..*\.tools(\.|$)",
                    ],
                    "exclude_keys": [
                        {"section": r"^mcp_servers\.[^.]+$", "key": r"^default_tools_approval_mode$"},
                    ],
                },
                "consumer": {"id": "true", "command": ["/usr/bin/true"]},
                "live_probe": {"kind": "command", "argv": ["/usr/bin/true"]},
            }
            ledger_module.record_artifact(ledger, spec)
            row = ledger_module.load_ledger(ledger)["artifacts"]["codex-config"]

            runtime_changed = target.read_text().replace('"trusted"', '"untrusted"')
            runtime_changed = runtime_changed.replace('trusted_hash = "old"', 'trusted_hash = "new"')
            runtime_changed = runtime_changed.replace('"gpt" = 3', '"gpt" = 9')
            runtime_changed = runtime_changed.replace(
                'default_tools_approval_mode = "prompt"',
                'default_tools_approval_mode = "allow"',
            )
            runtime_changed = runtime_changed.replace('approval_mode = "allow"', 'approval_mode = "deny"')
            runtime_changed += '[mcp_servers.slack.tools.newtool]\napproval_mode = "auto"\n'
            target.write_text(runtime_changed)
            self.assertEqual(ledger_module.evaluate_artifact(row)["status"], "ok")
            target.write_text(runtime_changed.replace('model = "gpt"', 'model = "other"'))
            self.assertEqual(ledger_module.evaluate_artifact(row)["status"], "owned-drift")

    def test_report_deduplicates_live_probe_argv(self):
        import generated_artifact_ledger as ledger_module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.json"
            source, transform, target = self._fixture(root)
            for artifact_id in ("one", "two"):
                ledger_module.record_artifact(
                    ledger,
                    {
                        "artifact_id": artifact_id,
                        "producer": "hook",
                        "profile": "work",
                        "target": str(target),
                        "inputs": [str(source)],
                        "transforms": [str(transform)],
                        "ownership": {"adapter": "whole-file"},
                        "consumer": {"id": "true", "command": ["/usr/bin/true"]},
                        "live_probe": {"kind": "command", "argv": ["/usr/bin/true"]},
                    },
                )
            with mock.patch.object(
                ledger_module,
                "_run_probe",
                return_value={"status": "ok", "exit_code": 0, "detail": ""},
            ) as probe:
                payload = ledger_module.report_payload(ledger, live=True)
            self.assertTrue(payload["ok"])
            probe.assert_called_once_with(["/usr/bin/true"])

    def test_unknown_schema_fails_closed(self):
        import generated_artifact_ledger as ledger_module

        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.json"
            ledger.write_text(json.dumps({"schema_version": 99, "artifacts": {}}))
            with self.assertRaisesRegex(ValueError, "schema"):
                ledger_module.load_ledger(ledger)

    def test_cli_default_path_honors_environment_override(self):
        import generated_artifact_ledger as ledger_module

        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp) / "custom.json"
            with mock.patch.dict(os.environ, {"CHEZMOI_ARTIFACT_LEDGER": str(override)}):
                self.assertEqual(ledger_module.default_ledger_path(), override)


if __name__ == "__main__":
    unittest.main()
