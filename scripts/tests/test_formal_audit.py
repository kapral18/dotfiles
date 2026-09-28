from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.formal_support import (
    CliError,
    audit_mod,
    build_mod,
    commit_all,
    exe_mod,
    init_git_repo,
    manifest_mod,
    paths_mod,
    replay_mod,
    run_formal,
    write_json,
)


class TestAudit(unittest.TestCase):
    """WHEN audit aggregates stage receipts for one snapshot (stubbed, no Lean required)."""

    def _stub_unit(self, tmp: Path) -> tuple[Path, Path, str]:
        workspace = Path(tmp) / "workspace"
        init_git_repo(workspace)
        unit_dir = Path(tmp) / "unit"
        unit_dir.mkdir()
        write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "stub", "tier": "F2"})
        snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
        return workspace, unit_dir, snapshot

    def _write_passing_stage_receipts(self, unit_dir: Path, snapshot: str) -> None:
        write_json(
            audit_mod.stage_receipt_path(unit_dir, snapshot, "anchors"), {"kind": "anchors", "ok": True, "anchors": []}
        )
        write_json(
            audit_mod.stage_receipt_path(unit_dir, snapshot, "build"),
            {"kind": "build", "ok": True, "error_count": 0, "warning_count": 0, "errors": []},
        )
        write_json(
            audit_mod.stage_receipt_path(unit_dir, snapshot, "explore"),
            {"kind": "explore", "ok": True, "states": 1, "transitions": 0, "depth": 0, "bounded": False, "props": []},
        )
        write_json(
            audit_mod.stage_receipt_path(unit_dir, snapshot, "mutate"),
            {"kind": "mutate", "ok": True, "control": {"ok": True, "violations": []}, "mutants": []},
        )

    def test_when_replay_is_unverified_and_not_allowed_the_verdict_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            self._write_passing_stage_receipts(unit_dir, snapshot)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}

            receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, None, False, 30)

            self.assertEqual("unverified", receipt["stages"]["replay"]["status"])
            self.assertEqual("fail", receipt["verdict"])

    def test_when_unverified_conformance_is_allowed_the_verdict_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            self._write_passing_stage_receipts(unit_dir, snapshot)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}

            receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, None, True, 30)

            self.assertEqual("pass", receipt["verdict"])
            self.assertIn("unverified", receipt["certifies"])

    def test_when_a_stage_fails_the_verdict_fails_even_with_allow_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            self._write_passing_stage_receipts(unit_dir, snapshot)
            write_json(
                audit_mod.stage_receipt_path(unit_dir, snapshot, "mutate"),
                {
                    "kind": "mutate",
                    "ok": False,
                    "control": {"ok": True, "violations": []},
                    "mutants": [{"name": "M1", "status": "survived"}],
                },
            )
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}

            receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, None, True, 30)

            self.assertEqual("fail", receipt["verdict"])
            self.assertEqual("fail", receipt["stages"]["mutate"]["status"])

    def test_when_run_twice_without_an_adapter_replay_reports_unverified_both_times(self) -> None:
        """Regression: a cached ``replay`` receipt from a no-adapter run must classify the same
        way as the fresh run that wrote it, not fall back to ``fail`` because the cached payload
        is truthy (``receipt is None`` alone cannot tell the two cases apart)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            self._write_passing_stage_receipts(unit_dir, snapshot)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}

            first = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, None, True, 30)
            second = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, None, True, 30)

            self.assertEqual("unverified", first["stages"]["replay"]["status"])
            self.assertEqual("unverified", second["stages"]["replay"]["status"])

    def test_run_stage_replay_with_no_adapter_marks_the_receipt_unverified(self) -> None:
        receipt = audit_mod.run_stage_replay(Path("/tmp"), Path("/tmp"), {"adapter": None, "budgets": {}}, timeout=30)
        self.assertTrue(receipt.get("unverified"))
        self.assertFalse(receipt["ok"])

    def test_conformance_summary_never_says_complete_cover_for_zero_traces(self) -> None:
        zero = audit_mod._conformance_summary("fail", {"total": 0, "passed": 0}, None, 500)
        self.assertNotIn("complete cover", zero)
        self.assertEqual("conformance: 0/0 traces compared", zero)

    def test_when_the_unit_is_a_design_unit_replay_is_skipped_as_n_a(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            self._write_passing_stage_receipts(unit_dir, snapshot)
            manifest = {"unit": "stub", "tier": "F2", "design": True, "adapter": None, "budgets": {}}

            receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, None, False, 30)

            self.assertEqual("n/a", receipt["stages"]["replay"]["status"])
            self.assertEqual("pass", receipt["verdict"])
            self.assertIn("n/a-design", receipt["certifies"])

    def test_when_a_non_design_unit_has_zero_anchors_the_anchors_stage_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, _snapshot = self._stub_unit(tmp)
            receipt = audit_mod.run_stage_anchors(unit_dir, workspace, design=False)
            self.assertFalse(receipt["ok"])
            self.assertEqual("no anchors", receipt.get("error"))

    def test_when_a_design_unit_has_zero_anchors_the_anchors_stage_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, _snapshot = self._stub_unit(tmp)
            receipt = audit_mod.run_stage_anchors(unit_dir, workspace, design=True)
            self.assertTrue(receipt["ok"])

    def test_run_stage_mutate_treats_wrong_killer_as_not_ok(self) -> None:
        with mock.patch.object(
            audit_mod.exe_mod,
            "mutate",
            return_value={
                "kind": "mutate",
                "control": {"ok": True, "violations": []},
                "mutants": [{"name": "M1", "status": "wrong-killer", "killed_by": ["Px"], "expected": ["P1"]}],
            },
        ):
            receipt = audit_mod.run_stage_mutate(Path("/tmp"), {"budgets": {}}, timeout=30)
        self.assertFalse(receipt["ok"])

    def test_run_stage_replay_uses_the_manifest_max_traces_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp) / "unit"
            (unit_dir / "traces").mkdir(parents=True)
            manifest = {
                "adapter": {"cmd": "true", "cwd": "unit"},
                "budgets": {"max_traces": 42, "max_states": 777, "max_depth": 9},
            }
            captured: dict[str, Any] = {}

            def fake_traces(
                _unit_dir: Path,
                _mode: str,
                max_n: int | None,
                timeout: float | None = None,
                max_states: int | None = None,
                max_depth: int | None = None,
            ) -> str:
                captured["max_n"] = max_n
                captured["max_states"] = max_states
                captured["max_depth"] = max_depth
                return ""

            with (
                mock.patch.object(audit_mod.exe_mod, "traces", fake_traces),
                mock.patch.object(
                    audit_mod.replay_mod,
                    "run_replay",
                    lambda *a, **k: {"kind": "replay", "ok": True, "total": 0, "passed": 0, "results": []},
                ),
            ):
                audit_mod.run_stage_replay(unit_dir, Path(tmp), manifest, timeout=30)

            self.assertEqual(42, captured["max_n"])
            # F12: trace generation must forward the same explore/mutate state-space budgets,
            # not only the replay-cover cap -- the pre-fix code always ran `traces` at the
            # Lean exe's own defaults regardless of MANIFEST.budgets.
            self.assertEqual(777, captured["max_states"])
            self.assertEqual(9, captured["max_depth"])

    def test_conformance_summary_reports_capped_vs_complete_cover(self) -> None:
        capped = audit_mod._conformance_summary(
            "pass", {"total": 5, "passed": 5}, {"kind": "explore", "ok": True, "states": 10, "bounded": False}, 5
        )
        self.assertIn("cover capped at 5", capped)
        self.assertIn("10 reachable states", capped)

        complete = audit_mod._conformance_summary(
            "pass", {"total": 3, "passed": 3}, {"kind": "explore", "ok": True, "states": 3, "bounded": False}, 500
        )
        self.assertIn("complete cover", complete)
        self.assertNotIn("capped", complete)

    def test_when_an_untracked_anchored_file_changes_the_cached_receipt_is_not_reused(self) -> None:
        """The old anchor-scoped diff never saw untracked files at all, so an untracked
        anchored file's content changing would leave the snapshot id -- and the cached
        receipt directory -- unchanged. It must now produce a fresh snapshot."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "stub", "tier": "F2"})
            anchored_file = workspace / "untracked.txt"
            anchored_file.write_text("v1\n", encoding="utf-8")
            anchors = [
                {"id": "A1", "path": "untracked.txt", "start": 1, "end": 1, "snippet": "v1"},
            ]
            write_json(unit_dir / manifest_mod.ANCHORS_NAME, {"anchors": anchors})

            snapshot1 = manifest_mod.snapshot_id(workspace, unit_dir)
            self._write_passing_stage_receipts(unit_dir, snapshot1)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}
            receipt1 = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot1, None, True, 30)
            self.assertEqual("pass", receipt1["verdict"])

            anchored_file.write_text("v2\n", encoding="utf-8")
            snapshot2 = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertNotEqual(snapshot1, snapshot2)
            self.assertFalse(audit_mod.stage_receipt_path(unit_dir, snapshot2, "anchors").exists())


class TestAuditEnvironmentFailures(unittest.TestCase):
    """WHEN a stage's own subprocess fails for an environment reason (missing tool, timeout,
    spawn failure), not a genuine check result (F3)."""

    def _stub_unit(self, tmp: Path) -> tuple[Path, Path, str]:
        workspace = Path(tmp) / "workspace"
        init_git_repo(workspace)
        unit_dir = Path(tmp) / "unit"
        unit_dir.mkdir()
        write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "stub", "tier": "F2"})
        snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
        return workspace, unit_dir, snapshot

    def test_lake_build_classifies_a_127_exit_as_an_environment_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            with mock.patch.object(
                build_mod, "run", return_value=subprocess.CompletedProcess(["lake", "build"], 127, "", "not found")
            ):
                receipt = build_mod.lake_build(unit_dir, proofs=False, timeout=5)
            self.assertFalse(receipt["ok"])
            self.assertTrue(receipt.get("environment_error"))

    def test_when_lake_is_missing_audit_refuses_before_any_stage_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}

            with mock.patch.object(audit_mod.shutil, "which", return_value=None):
                with self.assertRaises(CliError) as ctx:
                    audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, None, False, 30)

            self.assertEqual(2, ctx.exception.code)
            self.assertFalse((unit_dir / "receipts" / snapshot).exists())

    def test_when_build_hits_an_environment_error_the_stage_is_error_and_never_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}
            env_receipt = {
                "kind": "build",
                "ok": False,
                "environment_error": True,
                "error_count": 0,
                "warning_count": 0,
                "errors": [],
                "message": "lake build environment failure (exit 124)",
            }

            with mock.patch.object(audit_mod, "run_stage_build", return_value=env_receipt):
                receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, "anchors,build", False, 30)

            self.assertEqual("error", receipt["stages"]["build"]["status"])
            self.assertIsNone(receipt["stages"]["build"]["receipt"])
            self.assertFalse(audit_mod.stage_receipt_path(unit_dir, snapshot, "build").exists())

    def test_when_a_replay_stage_raises_an_environment_cli_error_it_is_caught_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": {"cmd": "true"}, "budgets": {}}
            write_json(
                audit_mod.stage_receipt_path(unit_dir, snapshot, "anchors"),
                {"kind": "anchors", "ok": True, "anchors": []},
            )
            write_json(
                audit_mod.stage_receipt_path(unit_dir, snapshot, "build"),
                {"kind": "build", "ok": True, "error_count": 0, "warning_count": 0, "errors": []},
            )

            with mock.patch.object(
                audit_mod, "run_stage_replay", side_effect=CliError("timed out", code=2, environment_error=True)
            ):
                receipt = audit_mod.run_audit(
                    unit_dir, workspace, manifest, snapshot, "anchors,build,replay", False, 30
                )

            self.assertEqual("error", receipt["stages"]["replay"]["status"])
            self.assertTrue(receipt["has_error"])
            self.assertFalse(audit_mod.stage_receipt_path(unit_dir, snapshot, "replay").exists())


class TestAuditUnparsedNonzeroBuildExitIsAnEnvironmentError(unittest.TestCase):
    """WHEN `lake build` exits nonzero with zero parsed diagnostics -- the elan proxy always
    makes `shutil.which("lake")` true, so a missing/offline pinned toolchain is never caught by
    the earlier `shutil.which` guard and instead surfaces this way (Q2.3): classify it as an
    environment error (stage `error`, `has_error: True`, never persisted), not an ordinary model
    build failure."""

    def _stub_unit(self, tmp: Path) -> tuple[Path, Path, str]:
        workspace = Path(tmp) / "workspace"
        init_git_repo(workspace)
        unit_dir = Path(tmp) / "unit"
        unit_dir.mkdir()
        write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "stub", "tier": "F2"})
        snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
        return workspace, unit_dir, snapshot

    def test_a_nonzero_lake_build_exit_with_no_diagnostics_is_reclassified_as_an_environment_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}

            with mock.patch.object(
                build_mod, "run", return_value=subprocess.CompletedProcess(["lake", "build"], 1, "", "")
            ):
                receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, "anchors,build", False, 30)

            self.assertEqual("error", receipt["stages"]["build"]["status"])
            self.assertIsNone(receipt["stages"]["build"]["receipt"])
            self.assertTrue(receipt["has_error"])
            self.assertFalse(audit_mod.stage_receipt_path(unit_dir, snapshot, "build").exists())

    def test_a_real_compile_failure_with_parsed_diagnostics_is_never_reclassified(self) -> None:
        """Control: a genuine compile failure always produces at least one parsed diagnostic
        line, so it must still classify as an ordinary `fail`, not `error`."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}
            diag_output = "Unit/Step.lean:3:0: error: unknown identifier 'foo'\n"

            with mock.patch.object(
                build_mod, "run", return_value=subprocess.CompletedProcess(["lake", "build"], 1, diag_output, "")
            ):
                receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, "anchors,build", False, 30)

            self.assertEqual("fail", receipt["stages"]["build"]["status"])
            self.assertFalse(receipt["has_error"])
            self.assertTrue(audit_mod.stage_receipt_path(unit_dir, snapshot, "build").exists())


class TestAuditReplayFailureRecovery(unittest.TestCase):
    """WHEN the replay stage's own producer raises instead of returning (F5): an adapter crash,
    a `lake exe` failure, or zero traces must never abort the whole audit before `audit.json` is
    written or before a later required stage (F3's `prove`) gets to run."""

    def _stub_unit(self, tmp: Path, tier: str = "F3") -> tuple[Path, Path, str]:
        workspace = Path(tmp) / "workspace"
        init_git_repo(workspace)
        unit_dir = Path(tmp) / "unit"
        unit_dir.mkdir()
        write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "stub", "tier": tier})
        snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
        return workspace, unit_dir, snapshot

    def test_when_replay_raises_a_check_failure_prove_still_runs_and_audit_json_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            manifest = {"unit": "stub", "tier": "F3", "design": False, "adapter": {"cmd": "true"}, "budgets": {}}
            write_json(
                audit_mod.stage_receipt_path(unit_dir, snapshot, "anchors"),
                {"kind": "anchors", "ok": True, "anchors": []},
            )
            write_json(
                audit_mod.stage_receipt_path(unit_dir, snapshot, "build"),
                {"kind": "build", "ok": True, "error_count": 0, "warning_count": 0, "errors": [], "proofs": True},
            )
            write_json(
                audit_mod.stage_receipt_path(unit_dir, snapshot, "prove"),
                {"kind": "prove", "ok": True, "build_ok": True, "forbidden_tokens": [], "theorem_count": 1},
            )

            with mock.patch.object(audit_mod, "run_stage_replay", side_effect=CliError("adapter crashed", code=1)):
                receipt = audit_mod.run_audit(
                    unit_dir, workspace, manifest, snapshot, "anchors,build,replay,prove", False, 30
                )

            self.assertEqual("fail", receipt["stages"]["replay"]["status"])
            self.assertEqual("pass", receipt["stages"]["prove"]["status"])
            self.assertTrue((unit_dir / "receipts" / snapshot / "audit.json").exists())
            self.assertEqual("fail", receipt["verdict"])


class TestAuditVacuousChecks(unittest.TestCase):
    """WHEN explore/mutate would otherwise pass vacuously (F8)."""

    def test_zero_properties_fails_explore(self) -> None:
        with mock.patch.object(
            audit_mod.exe_mod,
            "explore",
            return_value={"kind": "explore", "states": 1, "transitions": 0, "depth": 0, "bounded": False, "props": []},
        ):
            receipt = audit_mod.run_stage_explore(Path("/tmp"), {"budgets": {}}, timeout=30)
        self.assertFalse(receipt["ok"])
        self.assertEqual("no properties", receipt.get("error"))

    def test_zero_mutants_fails_mutate(self) -> None:
        with mock.patch.object(
            audit_mod.exe_mod,
            "mutate",
            return_value={"kind": "mutate", "control": {"ok": True, "violations": []}, "mutants": []},
        ):
            receipt = audit_mod.run_stage_mutate(Path("/tmp"), {"budgets": {}}, timeout=30)
        self.assertFalse(receipt["ok"])
        self.assertEqual("no mutants", receipt.get("error"))

    def test_a_mutant_with_an_empty_expected_killer_list_fails_mutate(self) -> None:
        with mock.patch.object(
            audit_mod.exe_mod,
            "mutate",
            return_value={
                "kind": "mutate",
                "control": {"ok": True, "violations": []},
                "mutants": [{"name": "M1", "status": "survived", "killed_by": [], "expected": []}],
            },
        ):
            receipt = audit_mod.run_stage_mutate(Path("/tmp"), {"budgets": {}}, timeout=30)
        self.assertFalse(receipt["ok"])
        self.assertIn("vacuous", receipt.get("error", ""))


class TestAuditRequireProveImpliesBuild(unittest.TestCase):
    """WHEN `--require` names `prove` without `build` (A9): `build` must still run first, so
    `prove` is never computed against (or cached from) a synthesized `{}` build receipt."""

    def test_required_stages_prepends_build_when_prove_is_requested_alone(self) -> None:
        self.assertEqual(["build", "prove"], audit_mod.required_stages("F2", "prove"))

    def test_required_stages_does_not_duplicate_an_explicitly_named_build(self) -> None:
        self.assertEqual(["build", "prove"], audit_mod.required_stages("F2", "build,prove"))

    def test_required_stages_moves_an_explicit_build_ahead_of_prove(self) -> None:
        self.assertEqual(["build", "prove"], audit_mod.required_stages("F2", "prove,build"))

    def test_required_stages_preserves_build_before_intervening_dependents(self) -> None:
        self.assertEqual(["build", "replay", "prove"], audit_mod.required_stages("F3", "build,replay,prove"))

    def test_failed_early_build_blocks_replay_before_prove(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            manifest = {"unit": "stub", "tier": "F3", "design": False, "adapter": None, "budgets": {}}
            failed_build = {"kind": "build", "ok": False, "proofs": True, "errors": [{"message": "proof failed"}]}
            with mock.patch.object(audit_mod, "run_stage_build", return_value=failed_build):
                with mock.patch.object(
                    audit_mod,
                    "run_stage_replay",
                    return_value={"kind": "replay", "ok": True, "passed": 1, "total": 1},
                ):
                    receipt = audit_mod.run_audit(
                        unit_dir, workspace, manifest, snapshot, "build,replay,prove", False, 30
                    )
            self.assertEqual("fail", receipt["stages"]["replay"]["status"])
            replay_receipt = json.loads(audit_mod.stage_receipt_path(unit_dir, snapshot, "replay").read_text())
            self.assertIn("build", replay_receipt["note"])

    def test_required_stages_is_unaffected_when_prove_is_not_requested(self) -> None:
        self.assertEqual(["anchors", "build"], audit_mod.required_stages("F2", "anchors,build"))

    def test_required_stages_rejects_an_empty_require_string(self) -> None:
        with self.assertRaises(CliError) as ctx:
            audit_mod.required_stages("F2", "")
        self.assertEqual(2, ctx.exception.code)

    def test_required_stages_rejects_a_require_string_of_only_commas_and_blanks(self) -> None:
        with self.assertRaises(CliError) as ctx:
            audit_mod.required_stages("F2", " , ,")
        self.assertEqual(2, ctx.exception.code)

    def test_required_stages_with_require_omitted_entirely_still_uses_the_tier_default(self) -> None:
        self.assertEqual(list(audit_mod.F2_STAGES), audit_mod.required_stages("F2", None))

    def _stub_unit(self, tmp: Path) -> tuple[Path, Path, str]:
        workspace = Path(tmp) / "workspace"
        init_git_repo(workspace)
        unit_dir = Path(tmp) / "unit"
        unit_dir.mkdir()
        write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "stub", "tier": "F2"})
        snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
        return workspace, unit_dir, snapshot

    def test_audit_runs_build_before_prove_and_prove_sees_the_real_build_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}
            real_build_receipt = {"kind": "build", "ok": True, "error_count": 0, "warning_count": 0, "errors": []}
            seen_build_receipts = []

            def fake_prove(unit_dir, build_receipt, timeout=None):
                seen_build_receipts.append(build_receipt)
                return {"kind": "prove", "ok": True, "build_ok": True, "forbidden_tokens": [], "theorem_count": 1}

            with mock.patch.object(audit_mod, "run_stage_build", return_value=real_build_receipt):
                with mock.patch.object(audit_mod, "run_stage_prove", side_effect=fake_prove):
                    receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, "prove,build", False, 30)

            self.assertEqual(["build", "prove"], list(receipt["stages"].keys()))
            self.assertEqual("pass", receipt["stages"]["build"]["status"])
            self.assertEqual("pass", receipt["stages"]["prove"]["status"])
            self.assertEqual([real_build_receipt], seen_build_receipts)

    def test_defensive_guard_when_build_never_ran_at_all(self) -> None:
        """Simulates a required-stage list that somehow still omits `build` ahead of `prove`
        (`required_stages` itself is bypassed here) -- confirms the second-layer guard raises
        instead of ever computing (and caching) a prove receipt from a synthesized `{}` build
        receipt."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}

            with mock.patch.object(audit_mod, "required_stages", return_value=["prove"]):
                with self.assertRaises(CliError) as ctx:
                    audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, "prove", False, 30)

            self.assertEqual(2, ctx.exception.code)
            self.assertFalse(audit_mod.stage_receipt_path(unit_dir, snapshot, "prove").exists())


class TestAuditConformanceNotRun(unittest.TestCase):
    """WHEN `--require` excludes `replay` entirely for a non-design unit (F14): distinct from a
    design unit's real, permanent `n/a-design` skip."""

    def test_a_non_design_unit_with_replay_excluded_reports_not_run(self) -> None:
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
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}

            receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, "anchors,build", False, 30)

            self.assertNotIn("replay", receipt["stages"])
            self.assertIn("conformance: not-run", receipt["certifies"])
            self.assertNotIn("n/a-design", receipt["certifies"])


class TestAuditCertifiesCoverUnknownWhenExploreDidNotRun(unittest.TestCase):
    """WHEN `certifies` reports conformance cover but `explore` never ran in this audit and no
    cached receipt exists for this snapshot (A10): never claim "(complete cover)" -- there is no
    reachable-state count to compare `total` against."""

    def test_conformance_summary_reports_cover_unknown_without_an_explore_receipt(self) -> None:
        replay_receipt = {"kind": "replay", "ok": True, "passed": 3, "total": 3, "results": []}

        summary = audit_mod._conformance_summary("pass", replay_receipt, None, 500)

        self.assertIn("cover unknown", summary)
        self.assertNotIn("complete cover", summary)

    def test_conformance_summary_still_reports_complete_cover_when_explore_succeeded_unbounded(self) -> None:
        replay_receipt = {"kind": "replay", "ok": True, "passed": 3, "total": 3, "results": []}
        explore_receipt = {"kind": "explore", "ok": True, "states": 3, "bounded": False, "props": []}

        summary = audit_mod._conformance_summary("pass", replay_receipt, explore_receipt, 500)

        self.assertIn("complete cover", summary)

    def test_conformance_summary_reports_cover_unknown_for_a_skipped_explore_receipt(self) -> None:
        replay_receipt = {"kind": "replay", "ok": True, "passed": 3, "total": 3, "results": []}
        skipped_explore = {"kind": "explore", "ok": False, "note": "skipped: build failed"}

        summary = audit_mod._conformance_summary("pass", replay_receipt, skipped_explore, 500)

        self.assertIn("cover unknown", summary)
        self.assertNotIn("complete cover", summary)

    def test_conformance_summary_reports_cover_unknown_for_malformed_success_metadata(self) -> None:
        replay_receipt = {"kind": "replay", "ok": True, "passed": 3, "total": 3, "results": []}

        for malformed in (
            {"kind": "explore", "ok": True, "states": 3},
            {"kind": "explore", "ok": True, "states": "3", "bounded": False},
            {"kind": "explore", "ok": False, "states": 3, "bounded": False},
        ):
            with self.subTest(explore_receipt=malformed):
                summary = audit_mod._conformance_summary("pass", replay_receipt, malformed, 500)
                self.assertIn("cover unknown", summary)
                self.assertNotIn("complete cover", summary)

    def test_audit_certifies_never_claims_complete_cover_when_require_excludes_explore(self) -> None:
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
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": {"cmd": "true"}, "budgets": {}}

            with mock.patch.object(
                audit_mod,
                "run_stage_replay",
                return_value={"kind": "replay", "ok": True, "passed": 2, "total": 2, "results": []},
            ):
                receipt = audit_mod.run_audit(
                    unit_dir, workspace, manifest, snapshot, "anchors,build,replay", False, 30
                )

            self.assertNotIn("complete cover", receipt["certifies"])
            self.assertIn("cover unknown", receipt["certifies"])


class TestAuditBuildFailureCascade(unittest.TestCase):
    """WHEN the build stage fails, every later required stage must record `fail` with a
    skip note (never raise), `audit.json` must still be written, and `,formal audit` must exit 1,
    never 2, for a model build failure. Requires `lake` on PATH; fails (does not skip) when
    missing, per the worker contract."""

    def setUp(self) -> None:
        if shutil.which("lake") is None:
            self.fail(
                "`lake` is required for this ,formal audit test and was not found on PATH. "
                "Install the pinned Lean toolchain (see `,formal doctor --install` or "
                "`brew install elan-init`) before running."
            )

    def test_when_step_lean_is_broken_later_stages_are_skipped_and_audit_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "src.txt").write_text("line one\n", encoding="utf-8")
            commit_all(workspace, "add src")

            run_formal(workspace, formal_home, "init", "broken", "--tier", "F3", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "broken", "src.txt:1-1", check=True)

            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("broken")
            step_path = unit_dir / "Unit" / "Step.lean"
            step_path.write_text(
                step_path.read_text(encoding="utf-8") + '\ndef _typeErrorMarker : Nat := "not a nat"\n',
                encoding="utf-8",
            )

            audit_result = run_formal(workspace, formal_home, "audit", "broken", "--json")

            self.assertEqual(1, audit_result.returncode, audit_result.stdout + audit_result.stderr)
            payload = json.loads(audit_result.stdout)
            self.assertEqual("fail", payload["stages"]["build"]["status"])
            # A13: the real Lake 4.34.1 diagnostic line for this type error is wrapped
            # severity-first (`error: file:line:col: msg`) -- the build receipt's own
            # `error_count`/`errors` must reflect the real failure, not read as 0 errors.
            # r5/U2.1: a `✖ [..] Building Unit.Step` job-failure marker now also becomes its own
            # positionless diagnostic ahead of the positioned one, so the real (file, line) pair
            # is no longer necessarily `errors[0]` -- check every reported error, not just the
            # first, for the one that actually carries them.
            build_receipt = json.loads(Path(payload["stages"]["build"]["receipt"]).read_text(encoding="utf-8"))
            self.assertGreaterEqual(build_receipt["error_count"], 1)
            positioned = [e for e in build_receipt["errors"] if (e["file"] or "").endswith("Step.lean")]
            self.assertTrue(positioned)
            self.assertGreater(positioned[0]["line"], 0)
            for stage in ("explore", "mutate", "replay", "prove"):
                self.assertEqual("fail", payload["stages"][stage]["status"], stage)
                receipt_path = payload["stages"][stage]["receipt"]
                receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
                self.assertEqual("skipped: build failed", receipt.get("note"))
            self.assertNotIn("(complete cover)", payload["certifies"])
            audit_path = unit_dir / "receipts" / payload["snapshot"] / "audit.json"
            self.assertTrue(audit_path.exists())


class TestAuditBadImportBuildFailureIsNotAnEnvironmentError(unittest.TestCase):
    """WHEN a bad import breaks the build, Lake 4.34.1 reports it with no `file:line:col:`
    position at all (`error: Unit/Step.lean: bad import 'Unit.Nope'`) -- S3.2: before
    `parse_diagnostics` recognized this form, `build.py` reported `error_count: 0` with an empty
    `errors` list for a real compile failure, and `run_audit`'s reclassification then
    misdiagnosed it as an environment error (exit 2) instead of an ordinary build fail (exit 1).
    Requires `lake` on PATH; fails (does not skip) when missing, per the worker contract."""

    def setUp(self) -> None:
        if shutil.which("lake") is None:
            self.fail(
                "`lake` is required for this ,formal audit test and was not found on PATH. "
                "Install the pinned Lean toolchain (see `,formal doctor --install` or "
                "`brew install elan-init`) before running."
            )

    def test_a_bad_import_fails_build_with_a_diagnostic_and_audit_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "src.txt").write_text("line one\n", encoding="utf-8")
            commit_all(workspace, "add src")

            run_formal(workspace, formal_home, "init", "badimport", "--tier", "F2", check=True)

            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("badimport")
            step_path = unit_dir / "Unit" / "Step.lean"
            step_path.write_text(
                step_path.read_text(encoding="utf-8").replace("import Unit.Model", "import Unit.Nope", 1),
                encoding="utf-8",
            )

            build_result = run_formal(workspace, formal_home, "build", "badimport", "--json")

            self.assertEqual(1, build_result.returncode, build_result.stdout + build_result.stderr)
            build_payload = json.loads(build_result.stdout)
            self.assertNotIn("environment_error", build_payload)
            self.assertGreaterEqual(build_payload["error_count"], 1)

            audit_result = run_formal(workspace, formal_home, "audit", "badimport", "--require", "build", "--json")

            self.assertEqual(1, audit_result.returncode, audit_result.stdout + audit_result.stderr)
            audit_payload = json.loads(audit_result.stdout)
            self.assertFalse(audit_payload["has_error"])
            self.assertEqual("fail", audit_payload["stages"]["build"]["status"])
            self.assertIsNotNone(audit_payload["stages"]["build"]["receipt"])


class TestAuditRealBuildFailuresAreNeverEnvironmentErrors(unittest.TestCase):
    """WHEN a real Lean/Lake build failure has no `file:line:col:` diagnostic at all (r5/U2.1):
    a self-import build cycle, a non-UTF-8 source file, and a crashed Lean subprocess must each
    still classify as an ordinary `fail` (>= 1 diagnostic, cached, `,formal audit` exit 1), never
    as an environment error -- `parse_diagnostics`'s generic `error: ...`/job-failure-marker rules
    (not per-shape enumeration) are what make this possible. Requires `lake` on PATH; fails (does
    not skip) when missing, per the worker contract."""

    def setUp(self) -> None:
        if shutil.which("lake") is None:
            self.fail(
                "`lake` is required for this ,formal audit test and was not found on PATH. "
                "Install the pinned Lean toolchain (see `,formal doctor --install` or "
                "`brew install elan-init`) before running."
            )

    def _init_unit(self, name: str) -> tuple[Path, Path, Path]:
        tmp = tempfile.mkdtemp()
        home_tmp = tempfile.mkdtemp()
        workspace = Path(tmp)
        formal_home = Path(home_tmp)
        init_git_repo(workspace)
        (workspace / "src.txt").write_text("line one\n", encoding="utf-8")
        commit_all(workspace, "add src")
        run_formal(workspace, formal_home, "init", name, "--tier", "F2", check=True)
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
        return workspace, formal_home, layout.work_dir(name)

    def test_a_module_that_imports_itself_fails_build_with_a_diagnostic_and_audit_exits_1(self) -> None:
        """Verbatim shape (r5-fixes `prf` evidence): a self-imported module reports both
        `error: <file>: module imports itself` and a `build cycle detected:` line, neither of
        which carries a `file:line:col:` position."""
        workspace, formal_home, unit_dir = self._init_unit("selfimp")
        model_path = unit_dir / "Unit" / "Model.lean"
        model_path.write_text("import Unit.Model\n\n" + model_path.read_text(encoding="utf-8"), encoding="utf-8")

        build_result = run_formal(workspace, formal_home, "build", "selfimp", "--json")
        self.assertEqual(1, build_result.returncode, build_result.stdout + build_result.stderr)
        build_payload = json.loads(build_result.stdout)
        self.assertNotIn("environment_error", build_payload)
        self.assertGreaterEqual(build_payload["error_count"], 1)
        messages = " ".join(e["message"] for e in build_payload["errors"])
        self.assertIn("module imports itself", messages)
        self.assertIn("build cycle detected", messages)

        audit_result = run_formal(workspace, formal_home, "audit", "selfimp", "--require", "build", "--json")
        self.assertEqual(1, audit_result.returncode, audit_result.stdout + audit_result.stderr)
        audit_payload = json.loads(audit_result.stdout)
        self.assertFalse(audit_payload["has_error"])
        self.assertEqual("fail", audit_payload["stages"]["build"]["status"])
        receipt_path = audit_payload["stages"]["build"]["receipt"]
        self.assertIsNotNone(receipt_path)
        self.assertTrue(Path(receipt_path).exists())

    def test_a_non_utf8_main_lean_fails_build_with_a_diagnostic_and_audit_exits_1(self) -> None:
        """Verbatim shape (r5-fixes `exemainutf` evidence): `error: Tried to read file '...'
        containing non UTF-8 data.` names the file inline, with no `file:line:col:` position."""
        workspace, formal_home, unit_dir = self._init_unit("utf8main")
        main_path = unit_dir / "Main.lean"
        main_path.write_bytes(main_path.read_bytes() + b"\n-- \xff\xfe bad utf8\n")

        build_result = run_formal(workspace, formal_home, "build", "utf8main", "--json")
        self.assertEqual(1, build_result.returncode, build_result.stdout + build_result.stderr)
        build_payload = json.loads(build_result.stdout)
        self.assertNotIn("environment_error", build_payload)
        self.assertGreaterEqual(build_payload["error_count"], 1)
        messages = " ".join(e["message"] for e in build_payload["errors"])
        self.assertIn("non UTF-8 data", messages)

        audit_result = run_formal(workspace, formal_home, "audit", "utf8main", "--require", "build", "--json")
        self.assertEqual(1, audit_result.returncode, audit_result.stdout + audit_result.stderr)
        audit_payload = json.loads(audit_result.stdout)
        self.assertFalse(audit_payload["has_error"])
        self.assertEqual("fail", audit_payload["stages"]["build"]["status"])
        receipt_path = audit_payload["stages"]["build"]["receipt"]
        self.assertIsNotNone(receipt_path)
        self.assertTrue(Path(receipt_path).exists())

    def test_a_crashed_lean_subprocess_fails_build_with_a_diagnostic_and_audit_exits_1(self) -> None:
        """Verbatim shape (r5-fixes `so.out` deep-recursion-crash evidence): a `partial def`
        without a decreasing argument, forced through `#eval`, exhausts the interpreter's
        recursion guard -- `error: Lean exited with code 134` and no `file:line:col:` position at
        all, only a `✖ [..] Building <module>` job-failure marker ahead of it."""
        workspace, formal_home, unit_dir = self._init_unit("crashu")
        model_path = unit_dir / "Unit" / "Model.lean"
        model_path.write_text(
            model_path.read_text(encoding="utf-8")
            + "\npartial def formalBoom (n : Nat) : Nat := formalBoom (n + 1) + 1\n#eval formalBoom 0\n",
            encoding="utf-8",
        )

        build_result = run_formal(workspace, formal_home, "build", "crashu", "--json")
        self.assertEqual(1, build_result.returncode, build_result.stdout + build_result.stderr)
        build_payload = json.loads(build_result.stdout)
        self.assertNotIn("environment_error", build_payload)
        self.assertGreaterEqual(build_payload["error_count"], 1)
        messages = " ".join(e["message"] for e in build_payload["errors"])
        self.assertIn("Lean exited with code", messages)

        audit_result = run_formal(workspace, formal_home, "audit", "crashu", "--require", "build", "--json")
        self.assertEqual(1, audit_result.returncode, audit_result.stdout + audit_result.stderr)
        audit_payload = json.loads(audit_result.stdout)
        self.assertFalse(audit_payload["has_error"])
        self.assertEqual("fail", audit_payload["stages"]["build"]["status"])
        receipt_path = audit_payload["stages"]["build"]["receipt"]
        self.assertIsNotNone(receipt_path)
        self.assertTrue(Path(receipt_path).exists())


class TestAuditSimulatedToolchainMissingIsAnEnvironmentError(unittest.TestCase):
    """WHEN elan itself cannot provision the pinned toolchain (mocked -- the exact stderr text
    captured from a real elan 4.2.4 run against an unresolvable `lean-toolchain` pin,
    /tmp/converge-fix-r5-U2/toolchain-missing/): `,formal audit` must classify the `build` stage
    `error` (never cached, `has_error: True`), not an ordinary `fail`."""

    def _stub_unit(self, tmp: Path) -> tuple[Path, Path, str]:
        workspace = Path(tmp) / "workspace"
        init_git_repo(workspace)
        unit_dir = Path(tmp) / "unit"
        unit_dir.mkdir()
        write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "stub", "tier": "F2"})
        snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
        return workspace, unit_dir, snapshot

    def test_a_simulated_unresolvable_toolchain_pin_is_an_environment_error_not_a_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, unit_dir, snapshot = self._stub_unit(tmp)
            manifest = {"unit": "stub", "tier": "F2", "design": False, "adapter": None, "budgets": {}}

            with mock.patch.object(
                build_mod,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["lake", "build"], 1, "", "error: no such release: 'v9.99.99-nonexistent'\n"
                ),
            ):
                receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, "anchors,build", False, 30)

            self.assertEqual("error", receipt["stages"]["build"]["status"])
            self.assertIsNone(receipt["stages"]["build"]["receipt"])
            self.assertTrue(receipt["has_error"])
            self.assertFalse(audit_mod.stage_receipt_path(unit_dir, snapshot, "build").exists())


class TestAuditBuildAlwaysCompilesProofsWhenProveIsRequired(unittest.TestCase):
    """WHEN `--require` names `prove` for an F2 unit (P2.1): `build` must compile
    `Unit.Proofs` too (not only for F3), so `prove`'s `formalcheck` step can never import a
    stale `Unit.Proofs` `.olean` left over from an earlier, proofs-off build. Requires `lake` on
    PATH; fails (does not skip) when missing, per the worker contract."""

    def setUp(self) -> None:
        if shutil.which("lake") is None:
            self.fail(
                "`lake` is required for this ,formal audit test and was not found on PATH. "
                "Install the pinned Lean toolchain (see `,formal doctor --install` or "
                "`brew install elan-init`) before running."
            )

    def test_a_pre_existing_stale_proofs_olean_is_never_reused_because_build_recompiles_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "src.txt").write_text("line one\n", encoding="utf-8")
            commit_all(workspace, "add src")

            run_formal(workspace, formal_home, "init", "provef2", "--tier", "F2", check=True)

            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("provef2")
            proofs_path = unit_dir / "Unit" / "Proofs.lean"
            proofs_path.write_text(
                "namespace Unit\n\ntheorem ok_theorem : True := trivial\n\nend Unit\n", encoding="utf-8"
            )

            # Pre-build a valid `Unit.Proofs` .olean directly (bypassing `,formal` entirely), so a
            # stale artifact exists on disk *before* the source below is broken -- reproducing the
            # exact staleness the F2 (`proofs=False`) build path used to leave behind.
            subprocess.run(["lake", "build", "Unit.Proofs"], cwd=unit_dir, check=True, capture_output=True, text=True)

            # A type error, not a forbidden token: `prove`'s own source-text scan
            # (`scan_forbidden_tokens`) never sees this, so only a real recompile of
            # `Unit.Proofs` (not a reused stale `.olean`) can catch it.
            proofs_path.write_text(
                'namespace Unit\n\ntheorem ok_theorem : True := "not a proof"\n\nend Unit\n', encoding="utf-8"
            )

            result = run_formal(workspace, formal_home, "audit", "provef2", "--require", "prove", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("fail", payload["stages"]["build"]["status"])
            self.assertEqual("fail", payload["stages"]["prove"]["status"])
            build_receipt = json.loads(Path(payload["stages"]["build"]["receipt"]).read_text(encoding="utf-8"))
            self.assertFalse(build_receipt["ok"])
            self.assertTrue(any((e["file"] or "").endswith("Proofs.lean") for e in build_receipt["errors"]))


class TestAuditCachedBuildWithoutProofsIsAMissWhenProofsAreNeeded(unittest.TestCase):
    """WHEN an earlier `--require build` run cached a `build` receipt that never compiled
    `Unit.Proofs` (F2, proofs off), a later `--require prove` run for the *same snapshot* must
    never reuse it: it never validated `Unit.Proofs` at all, so `prove`'s axiom check would run
    against a build receipt whose `ok: True` says nothing about whether `Unit.Proofs` even
    compiles (Q2.1). Requires `lake` on PATH; fails (does not skip) when missing, per the worker
    contract."""

    def setUp(self) -> None:
        if shutil.which("lake") is None:
            self.fail(
                "`lake` is required for this ,formal audit test and was not found on PATH. "
                "Install the pinned Lean toolchain (see `,formal doctor --install` or "
                "`brew install elan-init`) before running."
            )

    def test_prove_after_a_build_only_run_recomputes_the_build_and_catches_a_broken_proofs_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "src.txt").write_text("line one\n", encoding="utf-8")
            commit_all(workspace, "add src")

            run_formal(workspace, formal_home, "init", "cachef2", "--tier", "F2", check=True)

            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("cachef2")
            proofs_path = unit_dir / "Unit" / "Proofs.lean"
            proofs_path.write_text(
                'namespace Unit\n\ntheorem ok_theorem : True := "not a proof"\n\nend Unit\n', encoding="utf-8"
            )

            # First run only requires `build` (no `prove`) -- caches a successful `build` receipt
            # with `proofs: False`; the already-broken `Unit.Proofs` is deliberately not compiled.
            first = run_formal(workspace, formal_home, "audit", "cachef2", "--require", "build", "--json")
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            first_payload = json.loads(first.stdout)
            build_receipt_path = Path(first_payload["stages"]["build"]["receipt"])
            self.assertFalse(json.loads(build_receipt_path.read_text(encoding="utf-8"))["proofs"])

            # Do not modify the unit between invocations: the prove run must encounter and upgrade
            # the proofs-off receipt in the exact same snapshot directory.
            second = run_formal(workspace, formal_home, "audit", "cachef2", "--require", "prove", "--json")

            self.assertEqual(1, second.returncode, second.stdout + second.stderr)
            second_payload = json.loads(second.stdout)
            self.assertEqual(first_payload["snapshot"], second_payload["snapshot"])
            self.assertEqual(build_receipt_path, Path(second_payload["stages"]["build"]["receipt"]))
            # The cached, proofs-off receipt must be treated as a miss: `build` is recomputed
            # (with `proofs=True`) and fails on the now-broken `Unit.Proofs`, rather than being
            # reused as a stale `ok: True` that lets `prove` run unguarded.
            self.assertEqual("fail", second_payload["stages"]["build"]["status"])
            second_build_receipt = json.loads(
                Path(second_payload["stages"]["build"]["receipt"]).read_text(encoding="utf-8")
            )
            self.assertTrue(second_build_receipt["proofs"])
            self.assertTrue(any((e["file"] or "").endswith("Proofs.lean") for e in second_build_receipt["errors"]))
            self.assertEqual("fail", second_payload["stages"]["prove"]["status"])


class TestAuditProveForbiddenTokenNeverRaises(unittest.TestCase):
    """WHEN a forbidden token (`sorry`) short-circuits the prove stage, `,formal audit` must
    still finish and write `audit.json` instead of crashing before it -- S3.1:
    `_prove_summary`'s old `", ".join(receipt["forbidden_tokens"])` joined the hit dicts
    themselves (not token strings) and raised `TypeError`. Requires `lake` on PATH; fails (does
    not skip) when missing, per the worker contract."""

    def setUp(self) -> None:
        if shutil.which("lake") is None:
            self.fail(
                "`lake` is required for this ,formal audit test and was not found on PATH. "
                "Install the pinned Lean toolchain (see `,formal doctor --install` or "
                "`brew install elan-init`) before running."
            )

    def test_a_sorry_in_proofs_lean_fails_prove_and_audit_json_is_still_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "src.txt").write_text("line one\n", encoding="utf-8")
            commit_all(workspace, "add src")

            run_formal(workspace, formal_home, "init", "sorryunit", "--tier", "F3", check=True)

            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("sorryunit")
            proofs_path = unit_dir / "Unit" / "Proofs.lean"
            proofs_path.write_text(
                "namespace Unit\n\ntheorem ok_theorem : True := sorry\n\nend Unit\n", encoding="utf-8"
            )

            result = run_formal(workspace, formal_home, "audit", "sorryunit", "--require", "build,prove", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("fail", payload["stages"]["prove"]["status"])
            prove_receipt = json.loads(Path(payload["stages"]["prove"]["receipt"]).read_text(encoding="utf-8"))
            self.assertTrue(any(hit["token"] == "sorry" for hit in prove_receipt["forbidden_tokens"]))
            self.assertIn("sorry@Unit/Proofs.lean", payload["certifies"])
            audit_path = unit_dir / "receipts" / payload["snapshot"] / "audit.json"
            self.assertTrue(audit_path.exists())


class TestAuditCertifiesWording(unittest.TestCase):
    """WHEN `certifies` describes explore/conformance/prove results (test-integrity group
    "certifies wording")."""

    def test_explore_summary_appends_within_budget_only_when_bounded(self) -> None:
        bounded = {"props": [{"expect": "holds", "status": "holds"}], "bounded": True}
        unbounded = {"props": [{"expect": "holds", "status": "holds"}], "bounded": False}

        self.assertIn("within budget", audit_mod._explore_summary(bounded))
        self.assertNotIn("within budget", audit_mod._explore_summary(unbounded))

    def test_explore_summary_is_n_a_for_a_missing_receipt(self) -> None:
        self.assertEqual("n/a", audit_mod._explore_summary(None))

    def test_conformance_summary_reports_complete_cover_at_the_exact_reachable_boundary(self) -> None:
        replay_receipt = {"total": 5, "passed": 5}
        explore_receipt = {"kind": "explore", "ok": True, "states": 5, "bounded": False}

        summary = audit_mod._conformance_summary("pass", replay_receipt, explore_receipt, max_traces=5)

        self.assertIn("complete cover", summary)
        self.assertNotIn("capped", summary)

    def test_prove_summary_reports_clean_vs_dirty_axioms(self) -> None:
        clean = audit_mod._prove_summary(
            "pass", {"theorem_count": 7, "user_written_count": 2, "axioms": {"disallowed_axioms": []}}
        )
        dirty = audit_mod._prove_summary(
            "pass", {"theorem_count": 1, "axioms": {"disallowed_axioms": ["myCustomAxiom"]}}
        )

        self.assertIn("axioms clean", clean)
        self.assertIn("proofs: 2 theorems (7 constants axiom-checked)", clean)
        self.assertIn("axioms dirty: myCustomAxiom", dirty)

    def test_prove_summary_never_says_axioms_clean_when_a_scope_violation_exists_elsewhere(self) -> None:
        # `Unit.Proofs`'s own axioms (`disallowed_axioms`) are clean, but a `Model.lean` constant
        # (e.g. `decide +native`) has a `disallowed_axiom` scope violation -- `run_prove` fails
        # this receipt overall, so the summary must never claim "axioms clean" (repro
        # /tmp/converge-refute-r6-claims/probe_summary.py).
        summary = audit_mod._prove_summary(
            "fail",
            {
                "theorem_count": 1,
                "user_written_count": 1,
                "axioms": {"disallowed_axioms": []},
                "scope_violations": [{"name": "helper", "kind": "disallowed_axiom"}],
            },
        )
        self.assertNotIn("axioms clean", summary)
        self.assertIn("scope violation(s): helper (disallowed_axiom)", summary)

    def test_prove_summary_reports_axioms_dirty_when_a_proofs_theorem_also_trips_scope_violations(
        self,
    ) -> None:
        # Real `formalcheck` receipt shape (/tmp/converge-refute-r7-claims/out-native.json): a
        # `Unit.Proofs` theorem proved with `decide +native` makes both `axioms.disallowed_axioms`
        # (from the `theorems` array) AND `scope_violations` (from `violationsFor`, which walks
        # every constant including `Unit.Proofs`'s own) non-empty at once -- the axiom-dirty
        # branch must win, never the generic "scope violation(s)" line.
        summary = audit_mod._prove_summary(
            "fail",
            {
                "theorem_count": 1,
                "user_written_count": 1,
                "axioms": {
                    "disallowed_axioms": ["Unit.t1._native.decide.ax_1_1"],
                    "axioms_used": ["Unit.t1._native.decide.ax_1_1"],
                },
                "scope_violations": [
                    {
                        "name": "Unit.t1",
                        "kind": "disallowed_axiom",
                        "axioms": ["Unit.t1._native.decide.ax_1_1"],
                    },
                    {"name": "Unit.t1._native.decide.ax_1_1", "kind": "axiom_declaration"},
                    {
                        "name": "Unit.t1._native.decide.ax_1_1",
                        "kind": "disallowed_axiom",
                        "axioms": ["Unit.t1._native.decide.ax_1_1"],
                    },
                ],
            },
        )
        self.assertIn("axioms dirty: Unit.t1._native.decide.ax_1_1", summary)
        self.assertNotIn("scope violation(s)", summary)

    def test_prove_summary_caps_scope_violation_names_at_five(self) -> None:
        violations = [{"name": f"c{i}", "kind": "unsafe"} for i in range(7)]
        summary = audit_mod._prove_summary(
            "fail",
            {
                "theorem_count": 1,
                "user_written_count": 1,
                "axioms": {"disallowed_axioms": []},
                "scope_violations": violations,
            },
        )
        self.assertIn("c0 (unsafe)", summary)
        self.assertIn("c4 (unsafe)", summary)
        self.assertNotIn("c5 (unsafe)", summary)
        self.assertNotIn("c6 (unsafe)", summary)

    def test_prove_summary_never_says_axioms_clean_when_the_kernel_recheck_failed(self) -> None:
        # `kernel_check` only runs after every earlier check already passed, so `axioms` and
        # `scope_violations` are both clean here -- the summary must still surface the kernel
        # re-check failure instead of "axioms clean".
        summary = audit_mod._prove_summary(
            "fail",
            {
                "theorem_count": 1,
                "user_written_count": 1,
                "axioms": {"disallowed_axioms": []},
                "scope_violations": [],
                "kernel_check": {"ok": False, "message": "kernel re-check (leanchecker) rejected the built modules"},
            },
        )
        self.assertNotIn("axioms clean", summary)
        self.assertIn("kernel re-check failed: kernel re-check (leanchecker) rejected the built modules", summary)

    def test_prove_summary_reports_axioms_clean_when_kernel_check_passed(self) -> None:
        # A passing `kernel_check` (present on the receipt but `ok: True`) must not be mistaken
        # for a failure -- the clean receipt still reports "axioms clean".
        summary = audit_mod._prove_summary(
            "pass",
            {
                "theorem_count": 1,
                "user_written_count": 1,
                "axioms": {"disallowed_axioms": []},
                "scope_violations": [],
                "kernel_check": {"ok": True, "exit_code": 0},
            },
        )
        self.assertIn("axioms clean", summary)

    def test_prove_summary_is_n_a_for_a_missing_receipt(self) -> None:
        self.assertEqual("proofs: n/a", audit_mod._prove_summary("pass", None))

    def test_prove_summary_never_says_axioms_clean_when_a_forbidden_token_short_circuited_it(self) -> None:
        # `forbidden_tokens` entries are dicts (`{"file", "line", "token"}` from
        # `prove.scan_forbidden_tokens`), never bare token strings.
        summary = audit_mod._prove_summary(
            "fail",
            {
                "ok": False,
                "build_ok": True,
                "forbidden_tokens": [{"file": "Unit/Proofs.lean", "line": 5, "token": "sorry"}],
                "axioms": None,
            },
        )
        self.assertNotIn("axioms clean", summary)
        self.assertIn("axioms not checked", summary)
        self.assertIn("sorry@Unit/Proofs.lean:5", summary)

    def test_prove_summary_never_says_axioms_clean_when_the_build_failed_first(self) -> None:
        summary = audit_mod._prove_summary(
            "fail", {"ok": False, "build_ok": False, "forbidden_tokens": [], "axioms": None}
        )
        self.assertNotIn("axioms clean", summary)
        self.assertIn("axioms not checked", summary)
        self.assertIn("build failed", summary)

    def test_prove_summary_never_says_axioms_clean_when_lean_output_could_not_be_parsed(self) -> None:
        summary = audit_mod._prove_summary(
            "fail",
            {"ok": False, "build_ok": True, "forbidden_tokens": [], "axioms": None, "error": "could not parse JSON"},
        )
        self.assertNotIn("axioms clean", summary)
        self.assertIn("axioms not checked", summary)
        self.assertIn("could not parse JSON", summary)


class TestAuditHasErrorFalseOnCleanPass(unittest.TestCase):
    """WHEN every stage passes, `has_error` must be False, not merely absent or truthy by
    accident (F12 / test-integrity group "has_error")."""

    def test_a_fully_passing_audit_reports_has_error_false(self) -> None:
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
            write_json(
                audit_mod.stage_receipt_path(unit_dir, snapshot, "explore"),
                {
                    "kind": "explore",
                    "ok": True,
                    "states": 1,
                    "transitions": 0,
                    "depth": 0,
                    "bounded": False,
                    "props": [],
                },
            )
            write_json(
                audit_mod.stage_receipt_path(unit_dir, snapshot, "mutate"),
                {"kind": "mutate", "ok": True, "control": {"ok": True, "violations": []}, "mutants": []},
            )
            manifest = {"unit": "stub", "tier": "F2", "design": True, "adapter": None, "budgets": {}}

            receipt = audit_mod.run_audit(unit_dir, workspace, manifest, snapshot, None, False, 30)

            self.assertEqual("pass", receipt["verdict"])
            self.assertFalse(receipt["has_error"])


if __name__ == "__main__":
    unittest.main()
