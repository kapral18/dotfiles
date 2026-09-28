from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.formal_support import (
    CliError,
    audit_mod,
    commit_all,
    exe_mod,
    init_git_repo,
    manifest_mod,
    paths_mod,
    replay_mod,
    run_formal,
    write_json,
)


class TestReplay(unittest.TestCase):
    """WHEN a real-code adapter's observed output is compared to the model's expectations."""

    _PASS_ADAPTER = """
import json, os
traces = [json.loads(l) for l in open(os.environ["FORMAL_TRACES"]) if l.strip()]
with open(os.environ["FORMAL_OUT"], "w") as f:
    for t in traces:
        cur = dict(t.get("init_obs", {}))
        steps = []
        for step in t.get("steps", []):
            cur.update(step.get("expect", {}))
            steps.append({"observed": dict(cur)})
        f.write(json.dumps({"trace_id": t["trace_id"], "init_obs": dict(t.get("init_obs", {})), "steps": steps}) + "\\n")
"""

    _MISMATCH_ADAPTER = """
import json, os
traces = [json.loads(l) for l in open(os.environ["FORMAL_TRACES"]) if l.strip()]
with open(os.environ["FORMAL_OUT"], "w") as f:
    for t in traces:
        steps = [{"observed": {"state": "wrong"}} for _ in t.get("steps", [])]
        f.write(json.dumps({"trace_id": t["trace_id"], "init_obs": t.get("init_obs", {}), "steps": steps}) + "\\n")
"""

    _MISSING_ADAPTER = """
import json, os
traces = [json.loads(l) for l in open(os.environ["FORMAL_TRACES"]) if l.strip()]
with open(os.environ["FORMAL_OUT"], "w") as f:
    for t in traces[1:]:
        cur = dict(t.get("init_obs", {}))
        steps = []
        for step in t.get("steps", []):
            cur.update(step.get("expect", {}))
            steps.append({"observed": dict(cur)})
        f.write(json.dumps({"trace_id": t["trace_id"], "init_obs": dict(t.get("init_obs", {})), "steps": steps}) + "\\n")
"""

    _ERROR_ADAPTER = """
import json, os
traces = [json.loads(l) for l in open(os.environ["FORMAL_TRACES"]) if l.strip()]
with open(os.environ["FORMAL_OUT"], "w") as f:
    for t in traces:
        f.write(json.dumps({"trace_id": t["trace_id"], "error": "boom"}) + "\\n")
"""

    def _setup(self, tmp: Path, adapter_source: str) -> tuple[Path, Path, dict[str, Any]]:
        unit_dir = tmp / "unit"
        (unit_dir / "traces").mkdir(parents=True)
        traces = [
            {
                "trace_id": "t0",
                "init": 0,
                "init_obs": {"state": "idle"},
                "steps": [{"event": {"name": "start"}, "expect": {"state": "running"}}],
            },
            {
                "trace_id": "t1",
                "init": 0,
                "init_obs": {"state": "idle"},
                "steps": [{"event": {"name": "finish"}, "expect": {"state": "done"}}],
            },
        ]
        traces_path = unit_dir / "traces" / "traces.jsonl"
        traces_path.write_text("\n".join(json.dumps(t) for t in traces) + "\n", encoding="utf-8")
        adapter_path = tmp / "adapter.py"
        adapter_path.write_text(adapter_source, encoding="utf-8")
        manifest = {"adapter": {"cmd": f"{sys.executable} {adapter_path}", "cwd": "unit"}}
        return unit_dir, tmp, manifest

    def test_when_observed_output_matches_expectations_replay_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace, manifest = self._setup(Path(tmp), self._PASS_ADAPTER)
            receipt = replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertTrue(receipt["ok"])
            self.assertEqual(2, receipt["passed"])

    def test_when_observed_output_diverges_replay_reports_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace, manifest = self._setup(Path(tmp), self._MISMATCH_ADAPTER)
            receipt = replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertFalse(receipt["ok"])
            self.assertTrue(all(r["status"] == "mismatch" for r in receipt["results"]))

    def test_when_a_trace_is_absent_from_observed_output_replay_reports_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace, manifest = self._setup(Path(tmp), self._MISSING_ADAPTER)
            receipt = replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertFalse(receipt["ok"])
            statuses = {r["trace_id"]: r["status"] for r in receipt["results"]}
            self.assertEqual("missing", statuses["t0"])

    def test_when_the_adapter_reports_an_error_replay_surfaces_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace, manifest = self._setup(Path(tmp), self._ERROR_ADAPTER)
            receipt = replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertFalse(receipt["ok"])
            self.assertTrue(all(r["status"] == "error" for r in receipt["results"]))

    def test_when_a_trace_has_zero_steps_it_is_not_counted_as_compared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp) / "unit"
            (unit_dir / "traces").mkdir(parents=True)
            traces = [
                {"trace_id": "t0", "init": 0, "init_obs": {"state": "idle"}, "steps": []},
                {
                    "trace_id": "t1",
                    "init": 0,
                    "init_obs": {"state": "idle"},
                    "steps": [{"event": {"name": "start"}, "expect": {"state": "running"}}],
                },
            ]
            (unit_dir / "traces" / "traces.jsonl").write_text(
                "\n".join(json.dumps(t) for t in traces) + "\n", encoding="utf-8"
            )
            adapter_path = Path(tmp) / "adapter.py"
            adapter_path.write_text(self._PASS_ADAPTER, encoding="utf-8")
            manifest = {"adapter": {"cmd": f"{sys.executable} {adapter_path}", "cwd": "unit"}}

            receipt = replay_mod.run_replay(unit_dir, Path(tmp), manifest, None, timeout=30)

            self.assertEqual(1, receipt["total"])
            self.assertEqual({"t1"}, {r["trace_id"] for r in receipt["results"]})

    def test_when_every_trace_has_zero_steps_replay_fails_with_no_traces_compared(self) -> None:
        """0 traces compared must never read as a vacuous pass (0 == 0)."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp) / "unit"
            (unit_dir / "traces").mkdir(parents=True)
            traces = [{"trace_id": "t0", "init": 0, "init_obs": {"state": "idle"}, "steps": []}]
            (unit_dir / "traces" / "traces.jsonl").write_text(
                "\n".join(json.dumps(t) for t in traces) + "\n", encoding="utf-8"
            )
            adapter_path = Path(tmp) / "adapter.py"
            adapter_path.write_text(self._PASS_ADAPTER, encoding="utf-8")
            manifest = {"adapter": {"cmd": f"{sys.executable} {adapter_path}", "cwd": "unit"}}

            receipt = replay_mod.run_replay(unit_dir, Path(tmp), manifest, None, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertEqual(0, receipt["total"])
            self.assertEqual("no traces compared", receipt.get("note"))

    def test_when_the_adapter_crashes_without_writing_output_it_is_a_check_failure_not_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace, manifest = self._setup(Path(tmp), "import sys\nsys.exit(3)\n")
            with self.assertRaises(replay_mod.CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)


class TestReplayMalformedAdapterOutput(unittest.TestCase):
    """WHEN the adapter writes malformed JSONL (A2): invalid JSON, a non-object line, or an entry
    missing/mistyping trace_id/steps must become an ordinary CliError (code 1, not an
    environment error), never an uncaught exception that would abort `,formal audit` before
    audit.json is written or before a later required stage runs."""

    def _traces_dir(self, tmp: Path) -> tuple[Path, Path]:
        unit_dir = tmp / "unit"
        (unit_dir / "traces").mkdir(parents=True)
        (unit_dir / "traces" / "traces.jsonl").write_text(
            json.dumps({"trace_id": "t0", "init": 0, "init_obs": {}, "steps": [{"event": {"name": "x"}, "expect": {}}]})
            + "\n",
            encoding="utf-8",
        )
        return unit_dir, tmp

    def _adapter_writing(self, tmp: Path, out_body: str) -> dict[str, Any]:
        adapter_path = tmp / "adapter.py"
        adapter_path.write_text(
            f'import os\nopen(os.environ["FORMAL_OUT"], "w").write({out_body!r})\n', encoding="utf-8"
        )
        return {"adapter": {"cmd": f"{sys.executable} {adapter_path}", "cwd": "unit"}}

    def _adapter_writing_bytes(self, tmp: Path, out_body: bytes) -> dict[str, Any]:
        adapter_path = tmp / "adapter.py"
        adapter_path.write_text(
            f'import os\nopen(os.environ["FORMAL_OUT"], "wb").write({out_body!r})\n', encoding="utf-8"
        )
        return {"adapter": {"cmd": f"{sys.executable} {adapter_path}", "cwd": "unit"}}

    def test_invalid_json_line_becomes_a_cli_error_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(Path(tmp), "not json\n")

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)
            self.assertFalse(ctx.exception.environment_error)

    def test_invalid_utf8_becomes_a_cli_error_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing_bytes(Path(tmp), b'{"trace_id":"t0","steps":[],"note":"\xff"}\n')

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)
            self.assertFalse(ctx.exception.environment_error)
            self.assertIn("invalid UTF-8", ctx.exception.message)

    def test_duplicate_trace_id_rejects_error_then_success_instead_of_overwriting_the_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            out_body = (
                json.dumps({"trace_id": "t0", "error": "boom"})
                + "\n"
                + json.dumps({"trace_id": "t0", "steps": [{"observed": {}}]})
                + "\n"
            )
            manifest = self._adapter_writing(Path(tmp), out_body)

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)
            self.assertIn("duplicate 'trace_id' 't0'", ctx.exception.message)

    def test_non_object_line_becomes_a_cli_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(Path(tmp), "[1, 2]\n")

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)

    def test_missing_trace_id_becomes_a_cli_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(Path(tmp), json.dumps({"steps": []}) + "\n")

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)

    def test_missing_steps_becomes_a_cli_error_naming_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(Path(tmp), json.dumps({"trace_id": "t0"}) + "\n")

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)
            self.assertIn("missing 'steps'", ctx.exception.message)

    def test_steps_wrong_type_becomes_a_cli_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(Path(tmp), json.dumps({"trace_id": "t0", "steps": "nope"}) + "\n")

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)

    def test_steps_as_a_dict_becomes_a_cli_error_naming_a_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(Path(tmp), json.dumps({"trace_id": "t0", "steps": {}}) + "\n")

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)
            self.assertIn("must be a list", ctx.exception.message)

    def test_a_non_object_step_element_becomes_a_cli_error_with_line_and_trace_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(Path(tmp), json.dumps({"trace_id": "t0", "steps": [1]}) + "\n")

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)
            self.assertIn("line 1", ctx.exception.message)
            self.assertIn("'t0'", ctx.exception.message)
            self.assertIn("step 0", ctx.exception.message)

    def test_a_list_step_element_becomes_a_cli_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(Path(tmp), json.dumps({"trace_id": "t0", "steps": [[1, 2]]}) + "\n")

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)

    def test_a_non_object_observed_field_becomes_a_cli_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(
                Path(tmp), json.dumps({"trace_id": "t0", "steps": [{"observed": "wrong"}]}) + "\n"
            )

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)
            self.assertIn("'observed' must be an object", ctx.exception.message)

    def test_an_explicit_null_observed_field_becomes_a_cli_error_with_line_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(
                Path(tmp), json.dumps({"trace_id": "t0", "steps": [{"observed": None}]}) + "\n"
            )

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)
            self.assertIn("'observed' must be an object", ctx.exception.message)
            self.assertIn("line 1", ctx.exception.message)

    def test_a_falsy_error_key_still_requires_steps_validation(self) -> None:
        """A present-but-falsy `error` (e.g. `null`) must not exempt the entry from step
        validation the way a truthy `error` does (matching `compare_trace`'s own truthy check)."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(
                Path(tmp), json.dumps({"trace_id": "t0", "error": None, "steps": [7]}) + "\n"
            )

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual(1, ctx.exception.code)

    def test_load_jsonl_splits_on_literal_newline_only_not_unicode_line_separators(self) -> None:
        """A raw U+2028 (LINE SEPARATOR) byte inside a JSON string value is valid on an otherwise
        single JSONL line; `str.splitlines()` would wrongly treat it as a second line boundary
        and shatter the JSON, so `load_jsonl` must split on a literal `\\n` only."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observed.jsonl"
            entry = {"trace_id": "t0", "steps": [{"observed": {"note": "line1 line2"}}]}
            path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")

            loaded = replay_mod.load_jsonl(path)

            self.assertEqual(1, len(loaded))
            self.assertEqual("t0", loaded[0]["trace_id"])
            self.assertEqual("line1 line2", loaded[0]["steps"][0]["observed"]["note"])

    def test_blank_lines_between_jsonl_entries_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observed.jsonl"
            entries = [{"trace_id": "t0", "steps": []}, {"trace_id": "t1", "steps": []}]
            path.write_text(
                json.dumps(entries[0]) + "\n\n" + json.dumps(entries[1]) + "\n",
                encoding="utf-8",
            )

            loaded = replay_mod.load_jsonl(path)

            self.assertEqual(["t0", "t1"], [entry["trace_id"] for entry in loaded])

    def test_error_entry_without_steps_is_still_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace = self._traces_dir(Path(tmp))
            manifest = self._adapter_writing(Path(tmp), json.dumps({"trace_id": "t0", "error": "boom"}) + "\n")

            receipt = replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)
            self.assertEqual("error", receipt["results"][0]["status"])

    def test_audit_catches_the_malformed_output_as_a_fail_stage_and_still_writes_audit_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "stub", "tier": "F2"})
            snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
            write_json(
                audit_mod.stage_receipt_path(unit_dir, snapshot, "anchors"),
                {"kind": "anchors", "ok": True, "anchors": []},
            )
            write_json(
                audit_mod.stage_receipt_path(unit_dir, snapshot, "build"),
                {"kind": "build", "ok": True, "error_count": 0, "warning_count": 0, "errors": []},
            )
            manifest = self._adapter_writing(Path(tmp), "not json\n")
            manifest.update({"unit": "stub", "tier": "F2", "design": False, "budgets": {}})
            manifest["adapter"]["cwd"] = "repo"
            fake_traces = (
                json.dumps(
                    {"trace_id": "t0", "init": 0, "init_obs": {}, "steps": [{"event": {"name": "x"}, "expect": {}}]}
                )
                + "\n"
            )

            with mock.patch.object(audit_mod.exe_mod, "traces", return_value=fake_traces):
                receipt = audit_mod.run_audit(
                    unit_dir, workspace, manifest, snapshot, "anchors,build,replay", False, 30
                )

            self.assertEqual("fail", receipt["stages"]["replay"]["status"])
            self.assertFalse(receipt["has_error"])
            self.assertTrue((unit_dir / "receipts" / snapshot / "audit.json").exists())
            replay_failure_path = audit_mod.stage_receipt_path(unit_dir, snapshot, "replay")
            self.assertTrue(replay_failure_path.exists())
            replay_failure = json.loads(replay_failure_path.read_text(encoding="utf-8"))
            self.assertFalse(replay_failure["ok"])
            self.assertIn("invalid JSON", replay_failure["message"])

    def _run_audit_with_malformed_observed(self, tmp: Path, out_body: str | bytes) -> tuple[dict[str, Any], Path, str]:
        workspace = tmp / "workspace"
        init_git_repo(workspace)
        unit_dir = tmp / "unit"
        unit_dir.mkdir()
        write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "stub", "tier": "F2"})
        snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
        write_json(
            audit_mod.stage_receipt_path(unit_dir, snapshot, "anchors"),
            {"kind": "anchors", "ok": True, "anchors": []},
        )
        write_json(
            audit_mod.stage_receipt_path(unit_dir, snapshot, "build"),
            {"kind": "build", "ok": True, "error_count": 0, "warning_count": 0, "errors": []},
        )
        manifest = (
            self._adapter_writing_bytes(tmp, out_body)
            if isinstance(out_body, bytes)
            else self._adapter_writing(tmp, out_body)
        )
        manifest.update({"unit": "stub", "tier": "F2", "design": False, "budgets": {}})
        manifest["adapter"]["cwd"] = "repo"
        fake_traces = (
            json.dumps({"trace_id": "t0", "init": 0, "init_obs": {}, "steps": [{"event": {"name": "x"}, "expect": {}}]})
            + "\n"
        )

        with mock.patch.object(audit_mod.exe_mod, "traces", return_value=fake_traces):
            receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, "anchors,build,replay", False, 30)
        return receipt, unit_dir, snapshot

    def test_audit_catches_a_null_observed_field_as_a_fail_stage_and_still_writes_audit_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_body = json.dumps({"trace_id": "t0", "steps": [{"observed": None}]}) + "\n"
            receipt, unit_dir, snapshot = self._run_audit_with_malformed_observed(Path(tmp), out_body)

            self.assertEqual("fail", receipt["stages"]["replay"]["status"])
            self.assertFalse(receipt["has_error"])
            self.assertTrue((unit_dir / "receipts" / snapshot / "audit.json").exists())

    def test_audit_catches_a_falsy_error_with_non_dict_steps_as_a_fail_stage_and_still_writes_audit_json(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_body = json.dumps({"trace_id": "t0", "error": None, "steps": [7]}) + "\n"
            receipt, unit_dir, snapshot = self._run_audit_with_malformed_observed(Path(tmp), out_body)

            self.assertEqual("fail", receipt["stages"]["replay"]["status"])
            self.assertFalse(receipt["has_error"])
            self.assertTrue((unit_dir / "receipts" / snapshot / "audit.json").exists())

    def test_audit_persists_a_failure_receipt_for_invalid_utf8_adapter_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt, unit_dir, snapshot = self._run_audit_with_malformed_observed(
                Path(tmp), b'{"trace_id":"t0","steps":[],"note":"\xff"}\n'
            )

            self.assertEqual("fail", receipt["stages"]["replay"]["status"])
            replay_failure_path = audit_mod.stage_receipt_path(unit_dir, snapshot, "replay")
            self.assertTrue(replay_failure_path.exists())
            replay_failure = json.loads(replay_failure_path.read_text(encoding="utf-8"))
            self.assertFalse(replay_failure["ok"])
            self.assertIn("invalid UTF-8", replay_failure["message"])
            self.assertTrue((unit_dir / "receipts" / snapshot / "audit.json").exists())

    def test_audit_persists_a_failure_receipt_for_duplicate_adapter_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_body = (
                json.dumps({"trace_id": "t0", "error": "boom"})
                + "\n"
                + json.dumps({"trace_id": "t0", "steps": [{"observed": {}}]})
                + "\n"
            )
            receipt, unit_dir, snapshot = self._run_audit_with_malformed_observed(Path(tmp), out_body)

            self.assertEqual("fail", receipt["stages"]["replay"]["status"])
            replay_failure_path = audit_mod.stage_receipt_path(unit_dir, snapshot, "replay")
            self.assertTrue(replay_failure_path.exists())
            replay_failure = json.loads(replay_failure_path.read_text(encoding="utf-8"))
            self.assertFalse(replay_failure["ok"])
            self.assertIn("duplicate 'trace_id'", replay_failure["message"])
            self.assertTrue((unit_dir / "receipts" / snapshot / "audit.json").exists())


class TestReplayDifferential(unittest.TestCase):
    """WHEN --against exports REF via a throwaway git index (S4.2), never a git worktree or
    git archive."""

    _ENV_ADAPTER = """
import json, os
traces = [json.loads(l) for l in open(os.environ["FORMAL_TRACES"]) if l.strip()]
with open(os.environ["FORMAL_OUT"], "w") as f:
    for t in traces:
        steps = [{"observed": {"repo_root": os.environ.get("FORMAL_REPO_ROOT", "")}} for _ in t.get("steps", [])]
        f.write(json.dumps({"trace_id": t["trace_id"], "steps": steps}) + "\\n")
"""

    def test_against_ref_exports_via_a_throwaway_index_and_sets_formal_repo_root_per_side(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "workspace"
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            base_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=workspace, check=True, capture_output=True, text=True
            ).stdout.strip()
            (workspace / "marker.txt").write_text("head\n", encoding="utf-8")
            commit_all(workspace, "advance head")

            unit_dir = Path(tmp) / "unit"
            (unit_dir / "traces").mkdir(parents=True)
            traces = [{"trace_id": "t0", "init": 0, "init_obs": {}, "steps": [{"event": {"name": "x"}, "expect": {}}]}]
            (unit_dir / "traces" / "traces.jsonl").write_text(
                "\n".join(json.dumps(t) for t in traces) + "\n", encoding="utf-8"
            )
            adapter_path = Path(tmp) / "adapter.py"
            adapter_path.write_text(self._ENV_ADAPTER, encoding="utf-8")
            manifest = {"adapter": {"cmd": f"{sys.executable} {adapter_path}", "cwd": "repo"}}

            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

            receipt = replay_mod.run_replay_differential(
                layout, unit_dir, layout.workspace, manifest, None, base_sha, timeout=30
            )

            self.assertEqual("differential", receipt["mode"])
            # F9: `repo_root` genuinely differs between the head and ref sides (the adapter
            # observes it directly), so `_compare_differential`'s field comparison must report
            # this trace as a `mismatch`, and that must flip the whole receipt's `ok` to False.
            self.assertFalse(receipt["ok"])
            self.assertEqual("mismatch", receipt["results"][0]["status"])
            head_entry = json.loads((unit_dir / "traces" / "observed-head.jsonl").read_text())
            ref_entry = json.loads((unit_dir / "traces" / "observed-ref.jsonl").read_text())
            head_root = head_entry["steps"][0]["observed"]["repo_root"]
            ref_root = ref_entry["steps"][0]["observed"]["repo_root"]
            self.assertEqual(str(layout.workspace), head_root)
            self.assertNotEqual(head_root, ref_root)
            self.assertTrue(ref_root.startswith(str(layout.root)))
            # No git-worktree side effects on the real repo.
            worktree_list = subprocess.run(
                ["git", "worktree", "list"], cwd=workspace, check=True, capture_output=True, text=True
            )
            self.assertEqual(1, len(worktree_list.stdout.strip().splitlines()))
            # The export dir is removed once the differential run completes.
            self.assertFalse(Path(ref_root).exists())

    def _stub_differential_setup(self, tmp: Path, formal_home: Path) -> tuple[Any, Path, dict[str, Any]]:
        workspace = tmp / "workspace"
        init_git_repo(workspace)
        unit_dir = tmp / "unit"
        (unit_dir / "traces").mkdir(parents=True)
        traces = [{"trace_id": "t0", "init": 0, "init_obs": {}, "steps": [{"event": {"name": "x"}, "expect": {}}]}]
        (unit_dir / "traces" / "traces.jsonl").write_text(
            "\n".join(json.dumps(t) for t in traces) + "\n", encoding="utf-8"
        )
        manifest = {"adapter": {"cmd": "true", "cwd": "repo"}}
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
        return layout, unit_dir, manifest

    def test_against_an_unknown_ref_raises_a_clear_error_before_attempting_the_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout, unit_dir, manifest = self._stub_differential_setup(Path(tmp), Path(home_tmp))

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay_differential(
                    layout, unit_dir, layout.workspace, manifest, None, "nosuchref-typo", timeout=30
                )

            self.assertEqual(2, ctx.exception.code)
            self.assertIn("unknown ref", ctx.exception.message)

    def test_a_read_tree_failure_during_a_differential_run_is_never_masked_as_success(self) -> None:
        """S4.2: `_export_ref` no longer shells `git archive | tar -x`; a failing `git read-tree`
        inside a differential run must still surface as a `CliError`, not a silent empty export."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout, unit_dir, manifest = self._stub_differential_setup(Path(tmp), Path(home_tmp))
            real_run = replay_mod.run

            def fake_run(argv, **kwargs):
                if argv[:2] == ["git", "rev-parse"]:
                    return subprocess.CompletedProcess(argv, 0, "deadbeef\n", "")
                if argv[:2] == ["git", "read-tree"]:
                    return subprocess.CompletedProcess(argv, 128, "", "fatal: not a tree object")
                return real_run(argv, **kwargs)

            with mock.patch.object(replay_mod, "run", side_effect=fake_run):
                with self.assertRaises(CliError) as ctx:
                    replay_mod.run_replay_differential(
                        layout, unit_dir, layout.workspace, manifest, None, "nosuchref-typo", timeout=30
                    )

            self.assertEqual(2, ctx.exception.code)
            self.assertIn("git read-tree", ctx.exception.message)


class TestReplayDifferentialGate(unittest.TestCase):
    """WHEN `--against` is requested but the unit has not opted into differential replay (F7)."""

    def test_when_manifest_does_not_opt_in_against_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            result = run_formal(workspace, formal_home, "replay", "u", "--against", "HEAD")

            self.assertEqual(2, result.returncode)
            self.assertIn("replay.differential", result.stderr)

    def test_when_manifest_opts_in_against_proceeds_past_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u")
            manifest = manifest_mod.load_manifest(unit_dir)
            manifest["replay"] = {"differential": True}
            manifest_mod.save_manifest(unit_dir, manifest)

            result = run_formal(workspace, formal_home, "replay", "u", "--against", "HEAD")

            # Past the gate: fails for an unrelated reason (no traces.jsonl generated yet), not
            # the differential-opt-in message.
            self.assertNotIn("replay.differential", result.stderr)


class TestReplayDifferentialZeroSteps(unittest.TestCase):
    """WHEN every differential trace has zero steps (F15): must never read as a vacuous pass."""

    _ZERO_STEP_ADAPTER = """
import json, os
traces = [json.loads(l) for l in open(os.environ["FORMAL_TRACES"]) if l.strip()]
with open(os.environ["FORMAL_OUT"], "w") as f:
    for t in traces:
        f.write(json.dumps({"trace_id": t["trace_id"], "steps": []}) + "\\n")
"""

    def test_all_zero_step_traces_fail_with_no_traces_compared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "workspace"
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            base_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=workspace, check=True, capture_output=True, text=True
            ).stdout.strip()

            unit_dir = Path(tmp) / "unit"
            (unit_dir / "traces").mkdir(parents=True)
            traces = [{"trace_id": "t0", "init": 0, "init_obs": {}, "steps": []}]
            (unit_dir / "traces" / "traces.jsonl").write_text(
                "\n".join(json.dumps(t) for t in traces) + "\n", encoding="utf-8"
            )
            adapter_path = Path(tmp) / "adapter.py"
            adapter_path.write_text(self._ZERO_STEP_ADAPTER, encoding="utf-8")
            manifest = {"adapter": {"cmd": f"{sys.executable} {adapter_path}", "cwd": "repo"}}

            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

            receipt = replay_mod.run_replay_differential(
                layout, unit_dir, layout.workspace, manifest, None, base_sha, timeout=30
            )

            self.assertFalse(receipt["ok"])
            self.assertEqual(0, receipt["total"])
            self.assertEqual("no traces compared", receipt.get("note"))


class TestReplayPreconditionsExit2(unittest.TestCase):
    """WHEN `run_replay` is missing traces entirely (no file, or an empty file) or has no
    adapter configured: each refuses with `CliError` code 2 and a message naming the problem.
    A unit whose `traces.jsonl` holds only zero-step traces is a different case -- it passes
    this precondition (the file has entries) and instead returns a failing receipt from
    `run_replay` (`ok=False`, "no traces compared"), never a `CliError`
    (test-integrity group "replay preconditions exit 2", F10)."""

    def test_no_traces_jsonl_at_all_raises_code_2_naming_traces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp) / "unit"
            (unit_dir / "traces").mkdir(parents=True)
            manifest = {"adapter": {"cmd": "true", "cwd": "unit"}}

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, Path(tmp), manifest, None, timeout=5)

            self.assertEqual(2, ctx.exception.code)
            self.assertIn("No traces found", ctx.exception.message)
            self.assertIn(",formal traces", ctx.exception.message)

    def test_an_empty_traces_jsonl_file_raises_code_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp) / "unit"
            (unit_dir / "traces").mkdir(parents=True)
            (unit_dir / "traces" / "traces.jsonl").write_text("", encoding="utf-8")
            manifest = {"adapter": {"cmd": "true", "cwd": "unit"}}

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, Path(tmp), manifest, None, timeout=5)

            self.assertEqual(2, ctx.exception.code)

    def test_no_adapter_configured_raises_code_2_naming_the_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp) / "unit"
            (unit_dir / "traces").mkdir(parents=True)
            (unit_dir / "traces" / "traces.jsonl").write_text(
                json.dumps({"trace_id": "t0", "init": 0, "init_obs": {}, "steps": [{"event": {}, "expect": {}}]})
                + "\n",
                encoding="utf-8",
            )
            manifest = {"adapter": None}

            with self.assertRaises(CliError) as ctx:
                replay_mod.run_replay(unit_dir, Path(tmp), manifest, None, timeout=5)

            self.assertEqual(2, ctx.exception.code)
            self.assertIn("No adapter configured", ctx.exception.message)

    def test_only_zero_step_traces_returns_a_failing_receipt_not_a_cli_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp) / "unit"
            (unit_dir / "traces").mkdir(parents=True)
            (unit_dir / "traces" / "traces.jsonl").write_text(
                json.dumps({"trace_id": "t0", "init": 0, "init_obs": {}, "steps": []}) + "\n",
                encoding="utf-8",
            )
            manifest = {"adapter": {"cmd": "true", "cwd": "unit"}}

            receipt = replay_mod.run_replay(unit_dir, Path(tmp), manifest, None, timeout=5)

            self.assertFalse(receipt["ok"])
            self.assertEqual(0, receipt["total"])
            self.assertEqual("no traces compared", receipt.get("note"))


class TestReplayResolveAdapterOverride(unittest.TestCase):
    """WHEN `--adapter` is passed on the command line: it must override MANIFEST.json's
    `adapter.cmd` entirely (and always run with `cwd="repo"`), never fall through to (or merge
    with) the manifest's own adapter config (test-integrity group "adapter cwd")."""

    def test_an_explicit_adapter_flag_wins_over_a_different_manifest_adapter(self) -> None:
        manifest = {"adapter": {"cmd": "manifest-cmd", "cwd": "unit"}}

        cmd, cwd_kind = replay_mod.resolve_adapter(manifest, "flag-cmd")

        self.assertEqual("flag-cmd", cmd)
        self.assertEqual("repo", cwd_kind)

    def test_no_adapter_flag_falls_back_to_the_manifest_adapter(self) -> None:
        manifest = {"adapter": {"cmd": "manifest-cmd", "cwd": "unit"}}

        cmd, cwd_kind = replay_mod.resolve_adapter(manifest, None)

        self.assertEqual("manifest-cmd", cmd)
        self.assertEqual("unit", cwd_kind)


class TestReplayAdapterCwd(unittest.TestCase):
    """WHEN the adapter's `cwd` kind is `unit` vs `repo`: it must actually run there
    (test-integrity group "adapter cwd")."""

    _CWD_ADAPTER = """
import json, os
traces = [json.loads(l) for l in open(os.environ["FORMAL_TRACES"]) if l.strip()]
with open(os.environ["FORMAL_OUT"], "w") as f:
    for t in traces:
        steps = [{"observed": {"cwd": os.getcwd()}} for _ in t.get("steps", [])]
        f.write(json.dumps({"trace_id": t["trace_id"], "steps": steps}) + "\\n")
"""

    def _setup(self, tmp: Path) -> tuple[Path, Path, Path]:
        unit_dir = tmp / "unit"
        (unit_dir / "traces").mkdir(parents=True)
        traces = [{"trace_id": "t0", "init": 0, "init_obs": {}, "steps": [{"event": {}, "expect": {}}]}]
        (unit_dir / "traces" / "traces.jsonl").write_text(
            "\n".join(json.dumps(t) for t in traces) + "\n", encoding="utf-8"
        )
        adapter_path = tmp / "adapter.py"
        adapter_path.write_text(self._CWD_ADAPTER, encoding="utf-8")
        return unit_dir, tmp, adapter_path

    def test_cwd_kind_unit_runs_the_adapter_inside_the_unit_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace, adapter_path = self._setup(Path(tmp))
            manifest = {"adapter": {"cmd": f"{sys.executable} {adapter_path}", "cwd": "unit"}}

            receipt = replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)

            observed_cwd = json.loads((unit_dir / "traces" / "observed.jsonl").read_text().splitlines()[0])
            self.assertEqual(str(unit_dir.resolve()), observed_cwd["steps"][0]["observed"]["cwd"])

    def test_cwd_kind_repo_runs_the_adapter_inside_the_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir, workspace, adapter_path = self._setup(Path(tmp))
            manifest = {"adapter": {"cmd": f"{sys.executable} {adapter_path}", "cwd": "repo"}}

            receipt = replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=30)

            observed_cwd = json.loads((unit_dir / "traces" / "observed.jsonl").read_text().splitlines()[0])
            self.assertEqual(str(workspace.resolve()), observed_cwd["steps"][0]["observed"]["cwd"])


class TestConformanceComparisonEdges(unittest.TestCase):
    """WHEN a step's expected field is absent from the observed output, or fewer steps were
    observed than expected (test-integrity group "conformance comparison edges")."""

    def test_a_missing_observed_field_is_reported_by_name(self) -> None:
        divergence = replay_mod.compare_field_by_field({"state": "done"}, {"other": 1})

        self.assertEqual("missing observed field 'state'", divergence)

    def test_fewer_observed_steps_than_expected_mismatches_at_the_first_missing_step(self) -> None:
        trace = {
            "trace_id": "t0",
            "steps": [
                {"event": {"name": "a"}, "expect": {"state": "x"}},
                {"event": {"name": "b"}, "expect": {"state": "y"}},
            ],
        }
        observed_entry = {"trace_id": "t0", "steps": [{"observed": {"state": "x"}}]}

        result = replay_mod.compare_trace(trace, observed_entry)

        self.assertEqual("mismatch", result["status"])
        self.assertEqual(1, result["step"])
        self.assertIn("missing observed step 1", result["detail"])

    def test_bool_true_and_int_one_are_not_treated_as_equal(self) -> None:
        """S4.1: plain `!=` would call `True == 1` a match; `_json_equal` must not."""
        divergence = replay_mod.compare_field_by_field({"flag": True}, {"flag": 1})

        self.assertEqual("field 'flag' expected True, observed 1", divergence)

    def test_bool_false_and_int_zero_are_not_treated_as_equal(self) -> None:
        divergence = replay_mod.compare_field_by_field({"flag": False}, {"flag": 0})

        self.assertEqual("field 'flag' expected False, observed 0", divergence)

    def test_a_list_of_bools_and_a_list_of_ints_are_not_treated_as_equal(self) -> None:
        """The bool/int conflation must be caught inside a nested list too."""
        divergence = replay_mod.compare_field_by_field({"flags": [True, False]}, {"flags": [1, 0]})

        self.assertIsNotNone(divergence)

    def test_matching_bool_values_are_not_reported_as_a_divergence(self) -> None:
        divergence = replay_mod.compare_field_by_field({"flag": True}, {"flag": True})

        self.assertIsNone(divergence)

    def test_int_one_and_float_one_point_zero_are_treated_as_equal(self) -> None:
        """U4.1: Lean's `toJson (1.0 : Float)` prints `1`; a Python adapter's `json.dumps` prints
        `1.0` for the same value, so the non-bool numeric comparison must not report a divergence."""
        divergence = replay_mod.compare_field_by_field({"count": 1}, {"count": 1.0})

        self.assertIsNone(divergence)

    def test_a_list_of_ints_and_a_list_of_equal_floats_are_treated_as_equal(self) -> None:
        divergence = replay_mod.compare_field_by_field({"counts": [1, 2]}, {"counts": [1.0, 2.0]})

        self.assertIsNone(divergence)

    def test_nested_bool_vs_int_field_is_a_divergence_mutant_472(self) -> None:
        """Mutant 472: a nested `True` vs `1` under a matching outer key must still be caught --
        the numeric int/float relaxation must not also relax the bool/int distinction."""
        divergence = replay_mod.compare_field_by_field({"k": {"a": True}}, {"k": {"a": 1}})

        self.assertEqual("field 'k' expected {'a': True}, observed {'a': 1}", divergence)

    def test_string_vs_int_field_is_a_divergence(self) -> None:
        """Mutants 472/495: `str` and `int` are neither both `bool` nor both numeric, so this must
        fall through to the plain `type(expected) is not type(observed)` check at line 135."""
        divergence = replay_mod.compare_field_by_field({"k": "1"}, {"k": 1})

        self.assertEqual("field 'k' expected '1', observed 1", divergence)

    def test_list_vs_string_field_is_a_divergence(self) -> None:
        """Mutants 472/495: a `list` compared against a `str` must not slip past the type check
        just because iterating a string also yields elements."""
        divergence = replay_mod.compare_field_by_field({"k": ["a", "b"]}, {"k": "ab"})

        self.assertEqual("field 'k' expected ['a', 'b'], observed 'ab'", divergence)

    def test_none_vs_int_field_is_a_divergence(self) -> None:
        """Mutants 472/495: `None` compared against `0` must not slip past the type check via a
        falsy-value shortcut."""
        divergence = replay_mod.compare_field_by_field({"k": None}, {"k": 0})

        self.assertEqual("field 'k' expected None, observed 0", divergence)

    def test_dict_vs_string_field_is_a_divergence(self) -> None:
        """Mutants 472/495: a `dict` compared against a `str` must not slip past the type check."""
        divergence = replay_mod.compare_field_by_field({"k": {"a": 1}}, {"k": "x"})

        self.assertEqual("field 'k' expected {'a': 1}, observed 'x'", divergence)


class TestCompareDifferentialTable(unittest.TestCase):
    """WHEN `_compare_differential` classifies one trace's head-vs-ref comparison
    (test-integrity group "differential comparison", F9)."""

    def test_either_side_missing_is_status_missing(self) -> None:
        self.assertEqual("missing", replay_mod._compare_differential("t0", 0, None, {"steps": []})["status"])
        self.assertEqual("missing", replay_mod._compare_differential("t0", 0, {"steps": []}, None)["status"])

    def test_either_side_reporting_an_adapter_error_is_status_error(self) -> None:
        result = replay_mod._compare_differential("t0", 0, {"error": "boom"}, {"steps": []})
        self.assertEqual("error", result["status"])
        self.assertEqual("boom", result["detail"])

    def test_a_differing_step_count_is_a_mismatch(self) -> None:
        head = {"steps": [{"observed": {"x": 1}}, {"observed": {"x": 2}}]}
        ref = {"steps": [{"observed": {"x": 1}}]}

        result = replay_mod._compare_differential("t0", 2, head, ref)

        self.assertEqual("mismatch", result["status"])
        self.assertIn("step count differs", result["detail"])

    def test_equal_empty_outputs_mismatch_a_nonempty_input_trace(self) -> None:
        result = replay_mod._compare_differential("t0", 1, {"steps": []}, {"steps": []})

        self.assertEqual("mismatch", result["status"])
        self.assertIn("expected 1", result["detail"])

    def test_equally_truncated_outputs_mismatch_the_input_trace_length(self) -> None:
        one_step = {"steps": [{"observed": {"x": 1}}]}

        result = replay_mod._compare_differential("t0", 2, one_step, one_step)

        self.assertEqual("mismatch", result["status"])
        self.assertIn("head=1, ref=1", result["detail"])

    def test_a_differing_field_value_at_equal_step_counts_is_a_mismatch(self) -> None:
        head = {"steps": [{"observed": {"x": 1}}]}
        ref = {"steps": [{"observed": {"x": 2}}]}

        result = replay_mod._compare_differential("t0", 1, head, ref)

        self.assertEqual("mismatch", result["status"])
        self.assertEqual(0, result["step"])

    def test_a_missing_field_differs_from_an_explicit_json_null_on_either_side(self) -> None:
        missing = {"steps": [{"observed": {}}]}
        explicit_null = {"steps": [{"observed": {"result": None}}]}

        for head, ref in ((missing, explicit_null), (explicit_null, missing)):
            with self.subTest(head=head, ref=ref):
                result = replay_mod._compare_differential("t0", 1, head, ref)
                self.assertEqual("mismatch", result["status"])
                self.assertEqual(0, result["step"])
                self.assertIn("result", result["detail"])

    def test_identical_observed_output_on_both_sides_passes(self) -> None:
        head = {"steps": [{"observed": {"x": 1}}]}
        ref = {"steps": [{"observed": {"x": 1}}]}

        result = replay_mod._compare_differential("t0", 1, head, ref)

        self.assertEqual("pass", result["status"])

    def test_equal_integer_and_float_json_numbers_on_both_sides_pass(self) -> None:
        head = {"steps": [{"observed": {"count": 1}}]}
        ref = {"steps": [{"observed": {"count": 1.0}}]}

        result = replay_mod._compare_differential("t0", 1, head, ref)

        self.assertEqual("pass", result["status"])

    def test_a_bool_vs_int_field_value_at_equal_step_counts_is_a_mismatch(self) -> None:
        """S4.1: plain `!=` would call `True == 1` a match; `_json_equal` must not."""
        head = {"steps": [{"observed": {"flag": True}}]}
        ref = {"steps": [{"observed": {"flag": 1}}]}

        result = replay_mod._compare_differential("t0", 1, head, ref)

        self.assertEqual("mismatch", result["status"])
        self.assertEqual(0, result["step"])

    def test_matching_bool_values_on_both_sides_pass(self) -> None:
        head = {"steps": [{"observed": {"flag": False}}]}
        ref = {"steps": [{"observed": {"flag": False}}]}

        result = replay_mod._compare_differential("t0", 1, head, ref)

        self.assertEqual("pass", result["status"])


class TestExportRefGitFailure(unittest.TestCase):
    """WHEN `git read-tree` or the following `git checkout-index` fails: `_export_ref` must
    still raise `CliError` code 2 and remove the partial export directory, never silently
    produce (or report success for) an incomplete export (test-integrity group "export
    failure")."""

    def _layout(self, workspace: Path, formal_home: Path) -> Any:
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            return paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

    def test_a_read_tree_failure_raises_code_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            real_run = replay_mod.run

            def fake_run(argv, **kwargs):
                if argv[:2] == ["git", "rev-parse"]:
                    return subprocess.CompletedProcess(argv, 0, "deadbeef\n", "")
                if argv[:2] == ["git", "read-tree"]:
                    return subprocess.CompletedProcess(argv, 128, "", "fatal: not a tree object")
                return real_run(argv, **kwargs)

            with mock.patch.object(replay_mod, "run", side_effect=fake_run):
                with self.assertRaises(CliError) as ctx:
                    replay_mod._export_ref(layout, workspace, "HEAD", timeout=30)

            self.assertEqual(2, ctx.exception.code)
            self.assertIn("git read-tree", ctx.exception.message)

    def test_a_checkout_index_failure_raises_code_2_and_removes_the_partial_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            real_run = replay_mod.run
            captured: dict[str, Path] = {}

            def fake_run(argv, **kwargs):
                if argv[:2] == ["git", "rev-parse"]:
                    return subprocess.CompletedProcess(argv, 0, "deadbeef\n", "")
                if argv[:2] == ["git", "checkout-index"]:
                    prefix_arg = next(a for a in argv if a.startswith("--prefix="))
                    captured["export_dir"] = Path(prefix_arg[len("--prefix=") :].rstrip("/"))
                    return subprocess.CompletedProcess(argv, 1, "", "fatal: unable to write new index file")
                return real_run(argv, **kwargs)

            with mock.patch.object(replay_mod, "run", side_effect=fake_run):
                with self.assertRaises(CliError) as ctx:
                    replay_mod._export_ref(layout, workspace, "HEAD", timeout=30)

            self.assertEqual(2, ctx.exception.code)
            self.assertIn("git checkout-index", ctx.exception.message)
            self.assertFalse(captured["export_dir"].exists())


class TestExportRefAttributes(unittest.TestCase):
    """WHEN `ref`'s `.gitattributes` sets `export-ignore` or `export-subst` (S4.2): the export
    must reflect a plain checkout of `ref`, never `git archive`'s attribute-driven rewriting,
    and must never write to the real repo's `.git/index`."""

    def _layout(self, workspace: Path, formal_home: Path) -> Any:
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            return paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

    def test_export_ignore_does_not_drop_the_attributed_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            (workspace / "tests").mkdir()
            (workspace / "tests" / "helper.py").write_text("x = 1\n", encoding="utf-8")
            (workspace / ".gitattributes").write_text("tests/ export-ignore\n", encoding="utf-8")
            commit_all(workspace, "attrs")
            layout = self._layout(workspace, Path(home_tmp))

            export_dir = replay_mod._export_ref(layout, workspace, "HEAD", timeout=30)
            try:
                self.assertTrue((export_dir / "tests" / "helper.py").exists())
            finally:
                shutil.rmtree(export_dir, ignore_errors=True)

    def test_export_subst_placeholder_is_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            (workspace / ".gitattributes").write_text("version.txt export-subst\n", encoding="utf-8")
            (workspace / "version.txt").write_text("$Format:%H$\n", encoding="utf-8")
            commit_all(workspace, "attrs")
            layout = self._layout(workspace, Path(home_tmp))

            export_dir = replay_mod._export_ref(layout, workspace, "HEAD", timeout=30)
            try:
                self.assertEqual("$Format:%H$\n", (export_dir / "version.txt").read_text())
            finally:
                shutil.rmtree(export_dir, ignore_errors=True)

    def test_export_never_writes_to_the_real_git_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            real_index = workspace / ".git" / "index"
            before = real_index.read_bytes() if real_index.exists() else None

            export_dir = replay_mod._export_ref(layout, workspace, "HEAD", timeout=30)
            try:
                after = real_index.read_bytes() if real_index.exists() else None
                self.assertEqual(before, after)
            finally:
                shutil.rmtree(export_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
