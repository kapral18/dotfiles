from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "home" / "exact_lib" / "exact_,proof" / "main.py"


class TestProofCli(unittest.TestCase):
    """WHEN the freeform proof CLI gates completion claims."""

    def run_proof(
        self,
        cwd: Path,
        proof_home: Path,
        *args: str,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "AGENT_PROOF_HOME": str(proof_home)}
        result = subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(f",proof {' '.join(args)} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        return result

    def add_test_criterion(self, cwd: Path, proof_home: Path) -> None:
        self.run_proof(cwd, proof_home, "start", "Fix the thing", check=True)
        self.run_proof(
            cwd,
            proof_home,
            "add-criterion",
            "--requires",
            "test",
            "Relevant verification passes",
            check=True,
        )

    def complete_test_proof(self, cwd: Path, proof_home: Path) -> Path:
        self.add_test_criterion(cwd, proof_home)
        self.run_proof(
            cwd,
            proof_home,
            "add-evidence",
            "--criterion",
            "AC-001",
            "--type",
            "test",
            "--command",
            f"{sys.executable} -c 'print(\"ok\")'",
            check=True,
        )
        self.run_proof(
            cwd,
            proof_home,
            "review",
            "--criterion",
            "AC-001",
            "--evidence",
            "EV-001",
            "--verdict",
            "supports",
            "--notes",
            "The test command exited 0 and printed ok.",
            check=True,
        )
        return Path(self.run_proof(cwd, proof_home, "path", check=True).stdout.strip())

    def proof_module(self):
        spec = importlib.util.spec_from_file_location("proof_cli_main", CLI)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_when_state_is_created_it_stays_outside_the_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)

            self.run_proof(cwd, proof_home, "start", "Freeform proof", check=True)
            path = self.run_proof(cwd, proof_home, "path", check=True).stdout.strip()

            self.assertTrue(path.startswith(str(proof_home)))
            self.assertFalse((cwd / ".proof").exists())
            self.assertFalse((cwd / ".fable-verify").exists())

    def test_when_proof_home_is_inside_workspace_it_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            proof_home = cwd / ".proof-state"

            result = self.run_proof(cwd, proof_home, "start", "Bad state location")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Proof state must stay outside the selected workspace", result.stderr)
            self.assertFalse(proof_home.exists())

    def test_when_check_runs_before_start_it_does_not_create_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)

            result = self.run_proof(cwd, proof_home, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No proof ledger found", result.stderr)
            self.assertEqual([], list(proof_home.rglob("proof.json")))

    def test_when_add_criterion_runs_before_start_it_does_not_create_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)

            result = self.run_proof(
                cwd,
                proof_home,
                "add-criterion",
                "--requires",
                "test",
                "Cannot add before start",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No proof ledger found", result.stderr)
            self.assertEqual([], list(proof_home.rglob("proof.json")))

    def test_when_command_evidence_is_reviewed_check_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.add_test_criterion(cwd, proof_home)

            self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"ok\")'",
                check=True,
            )
            self.run_proof(
                cwd,
                proof_home,
                "review",
                "--criterion",
                "AC-001",
                "--evidence",
                "EV-001",
                "--verdict",
                "supports",
                "--notes",
                "The test command exited 0 and printed ok.",
                check=True,
            )

            result = self.run_proof(cwd, proof_home, "check", "--json")
            payload = json.loads(result.stdout)

            self.assertEqual(result.returncode, 0)
            self.assertTrue(payload["allowed"])
            self.assertEqual("PROOF RECORDED", payload["verdict"])

    def test_when_evidence_is_unreviewed_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.add_test_criterion(cwd, proof_home)
            self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"ok\")'",
                check=True,
            )

            result = self.run_proof(cwd, proof_home, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("has not been reviewed", result.stdout)
            self.assertIn("missing required evidence type: test", result.stdout)

    def test_when_artifact_is_tampered_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.run_proof(cwd, proof_home, "start", "Read proof", check=True)
            self.run_proof(
                cwd,
                proof_home,
                "add-criterion",
                "--requires",
                "file-read",
                "File evidence is captured",
                check=True,
            )
            source = cwd / "proof.txt"
            source.write_text("original\n", encoding="utf-8")
            self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "file-read",
                "--artifact-path",
                str(source),
                check=True,
            )
            self.run_proof(
                cwd,
                proof_home,
                "review",
                "--criterion",
                "AC-001",
                "--evidence",
                "EV-001",
                "--verdict",
                "supports",
                "--notes",
                "The copied file evidence contains the original proof.",
                check=True,
            )
            proof_dir = Path(self.run_proof(cwd, proof_home, "path", check=True).stdout.strip())
            copied = proof_dir / "evidence" / "EV-001-proof.txt"
            copied.write_text("tampered\n", encoding="utf-8")

            result = self.run_proof(cwd, proof_home, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tampered", result.stdout)

    def test_when_blocker_is_open_check_fails_until_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.add_test_criterion(cwd, proof_home)
            self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"ok\")'",
                check=True,
            )
            self.run_proof(
                cwd,
                proof_home,
                "review",
                "--criterion",
                "AC-001",
                "--evidence",
                "EV-001",
                "--verdict",
                "supports",
                "--notes",
                "The command evidence supports the criterion.",
                check=True,
            )
            self.run_proof(cwd, proof_home, "block", "Need product signoff", check=True)

            blocked = self.run_proof(cwd, proof_home, "check")
            self.run_proof(cwd, proof_home, "resolve-blocker", "B-001", check=True)
            clear = self.run_proof(cwd, proof_home, "check")

            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("Unresolved blocker B-001", blocked.stdout)
            self.assertEqual(clear.returncode, 0)

    def test_when_active_topic_exists_default_still_uses_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            spec_root = Path(os.environ.get("AGENT_MEMORY_SPEC_ROOT", proof_home / "specs"))
            spec_dir = spec_root / str(cwd.resolve()).lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "_active_topic.txt").write_text("stale-topic\n", encoding="utf-8")

            self.run_proof(cwd, proof_home, "start", "Default topic proof", check=True)
            path = self.run_proof(cwd, proof_home, "path", check=True).stdout.strip()

            self.assertTrue(path.endswith("/current"))
            self.assertFalse(path.endswith("/stale-topic"))

    def test_when_artifact_path_is_relative_it_resolves_from_workspace(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            tempfile.TemporaryDirectory() as proof_tmp,
            tempfile.TemporaryDirectory() as other_tmp,
        ):
            workspace = Path(tmp)
            proof_home = Path(proof_tmp)
            other_cwd = Path(other_tmp)
            self.run_proof(
                other_cwd, proof_home, "--workspace", str(workspace), "start", "Relative artifact proof", check=True
            )
            self.run_proof(
                other_cwd,
                proof_home,
                "--workspace",
                str(workspace),
                "add-criterion",
                "--requires",
                "file-read",
                "Workspace artifact is read",
                check=True,
            )
            (workspace / "artifact.txt").write_text("from workspace\n", encoding="utf-8")
            (other_cwd / "artifact.txt").write_text("from cwd\n", encoding="utf-8")

            self.run_proof(
                other_cwd,
                proof_home,
                "--workspace",
                str(workspace),
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "file-read",
                "--artifact-path",
                "artifact.txt",
                check=True,
            )
            proof_dir = Path(
                self.run_proof(other_cwd, proof_home, "--workspace", str(workspace), "path", check=True).stdout.strip()
            )

            self.assertEqual("from workspace\n", (proof_dir / "evidence" / "EV-001-artifact.txt").read_text())

    def test_when_external_command_evidence_omits_artifact_it_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.add_test_criterion(cwd, proof_home)

            result = self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                "external test command",
                "--exit-code",
                "0",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires --artifact-path", result.stderr)

    def test_when_latest_review_is_not_supports_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.add_test_criterion(cwd, proof_home)
            self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"ok\")'",
                check=True,
            )
            self.run_proof(
                cwd,
                proof_home,
                "review",
                "--criterion",
                "AC-001",
                "--evidence",
                "EV-001",
                "--verdict",
                "supports",
                "--notes",
                "Initial support.",
                check=True,
            )
            self.run_proof(
                cwd,
                proof_home,
                "review",
                "--criterion",
                "AC-001",
                "--evidence",
                "EV-001",
                "--verdict",
                "unclear",
                "--notes",
                "Later review is unclear.",
                check=True,
            )

            result = self.run_proof(cwd, proof_home, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("verdict is unclear", result.stdout)

    def test_when_add_criterion_has_no_evidence_types_it_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.run_proof(cwd, proof_home, "start", "Empty-requires guard", check=True)

            for empty in ("", " ", ",,", ", ,"):
                result = self.run_proof(
                    cwd,
                    proof_home,
                    "add-criterion",
                    "--requires",
                    empty,
                    "Would trivially pass without required evidence",
                )
                self.assertEqual(
                    result.returncode, 2, msg=f"--requires {empty!r} should reject; stderr={result.stderr!r}"
                )
                self.assertIn("At least one --requires evidence type is required", result.stderr)

            check = self.run_proof(cwd, proof_home, "check")
            self.assertNotEqual(check.returncode, 0)
            self.assertIn("No criteria are defined", check.stdout)

    def test_when_two_reports_run_back_to_back_neither_overwrites_the_other(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.add_test_criterion(cwd, proof_home)
            proof_dir = Path(self.run_proof(cwd, proof_home, "path", check=True).stdout.strip())

            first = self.run_proof(cwd, proof_home, "report", check=True).stdout.splitlines()[0]
            second = self.run_proof(cwd, proof_home, "report", check=True).stdout.splitlines()[0]

            self.assertNotEqual(first, second, "Report filenames must be unique within the same second")
            reports = sorted((proof_dir / "reports").iterdir())
            self.assertEqual(len(reports), 2, f"Expected two report files, got {[p.name for p in reports]}")

    def test_when_status_or_check_runs_it_does_not_bump_updated_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.add_test_criterion(cwd, proof_home)
            proof_dir = Path(self.run_proof(cwd, proof_home, "path", check=True).stdout.strip())
            state_file = proof_dir / "proof.json"
            baseline = json.loads(state_file.read_text())["updated_at"]

            self.run_proof(cwd, proof_home, "status", check=False)
            self.assertEqual(json.loads(state_file.read_text())["updated_at"], baseline)

            self.run_proof(cwd, proof_home, "check", check=False)
            self.assertEqual(json.loads(state_file.read_text())["updated_at"], baseline)

            self.run_proof(cwd, proof_home, "report", check=True)
            self.assertEqual(json.loads(state_file.read_text())["updated_at"], baseline)

    def test_when_list_runs_it_shows_current_workspace_ledgers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.add_test_criterion(cwd, proof_home)
            self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"ok\")'",
                check=True,
            )
            self.run_proof(
                cwd,
                proof_home,
                "review",
                "--criterion",
                "AC-001",
                "--evidence",
                "EV-001",
                "--verdict",
                "supports",
                "--notes",
                "The test command exited 0 and printed ok.",
                check=True,
            )
            self.run_proof(
                cwd,
                proof_home,
                "add-criterion",
                "--requires",
                "diff",
                "Scoped diff was inspected",
                check=True,
            )

            result = self.run_proof(cwd, proof_home, "list", check=True)

            self.assertIn("current", result.stdout)
            self.assertIn("Fix the thing", result.stdout)
            self.assertIn("1/2", result.stdout)
            self.assertIn("\tno\t", result.stdout)

    def test_when_list_json_runs_it_reports_finalized_seal_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            proof_dir = self.complete_test_proof(cwd, proof_home)
            self.run_proof(cwd, proof_home, "finalize", check=True)

            result = self.run_proof(cwd, proof_home, "list", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertEqual(1, len(payload))
            row = payload[0]
            self.assertEqual("current", row["topic"])
            self.assertEqual("Fix the thing", row["goal"])
            self.assertEqual("1/1", row["criteria"])
            self.assertTrue(row["finalized"])
            self.assertEqual("ok", row["seal_status"])
            self.assertEqual(
                json.loads((proof_dir / "proof.json").read_text(encoding="utf-8"))["seal"],
                row["seal"],
            )

    def test_when_list_runs_it_does_not_rewrite_legacy_ledgers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            proof_dir = self.complete_test_proof(cwd, proof_home)
            state_file = proof_dir / "proof.json"
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["evidence"][0].pop("provenance")
            state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            before = state_file.read_bytes()

            self.run_proof(cwd, proof_home, "list", "--json", check=True)

            self.assertEqual(before, state_file.read_bytes())

    def test_when_list_all_workspaces_runs_it_surfaces_other_workspace_hashes(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            tempfile.TemporaryDirectory() as proof_tmp,
            tempfile.TemporaryDirectory() as other_tmp,
        ):
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            other_cwd = Path(other_tmp)
            self.run_proof(cwd, proof_home, "--topic", "first", "start", "First workspace proof", check=True)
            self.run_proof(other_cwd, proof_home, "--topic", "second", "start", "Second workspace proof", check=True)
            other_proof_dir = Path(
                self.run_proof(other_cwd, proof_home, "--topic", "second", "path", check=True).stdout.strip()
            )

            result = self.run_proof(cwd, proof_home, "list", "--all-workspaces", check=True)

            self.assertIn(other_proof_dir.parent.name, result.stdout)
            self.assertIn("second", result.stdout)

    def test_when_passing_ledger_is_finalized_mutations_refuse_until_reopened(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            proof_dir = self.complete_test_proof(cwd, proof_home)

            finalized = self.run_proof(cwd, proof_home, "finalize", check=True)
            state = json.loads((proof_dir / "proof.json").read_text(encoding="utf-8"))
            previous_seal = state["seal"]
            mutation = self.run_proof(
                cwd,
                proof_home,
                "add-criterion",
                "--requires",
                "test",
                "Mutation should fail",
            )
            state["criteria"][0]["description"] = "Tampered after finalize"
            (proof_dir / "proof.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            broken = self.run_proof(cwd, proof_home, "check")
            reopened = self.run_proof(cwd, proof_home, "reopen", check=True)
            reopened_state = json.loads((proof_dir / "proof.json").read_text(encoding="utf-8"))
            mutable = self.run_proof(
                cwd,
                proof_home,
                "add-criterion",
                "--requires",
                "test",
                "Mutation works after reopen",
                check=True,
            )

            self.assertIn("Finalized proof ledger", finalized.stdout)
            self.assertNotEqual(mutation.returncode, 0)
            self.assertIn("finalized", mutation.stderr)
            self.assertNotEqual(broken.returncode, 0)
            self.assertIn("seal broken", broken.stdout)
            self.assertIn("Reopened proof ledger", reopened.stdout)
            self.assertEqual(0, mutable.returncode)
            self.assertNotIn("seal", reopened_state)
            self.assertEqual(previous_seal, reopened_state["reopen_history"][0]["previous_seal"])

    def test_when_failing_ledger_is_finalized_without_override_it_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.add_test_criterion(cwd, proof_home)
            proof_dir = Path(self.run_proof(cwd, proof_home, "path", check=True).stdout.strip())

            result = self.run_proof(cwd, proof_home, "finalize")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("proof check fails", result.stderr)
            state = json.loads((proof_dir / "proof.json").read_text(encoding="utf-8"))
            self.assertNotIn("seal", state)

    def test_when_evidence_provenance_is_legacy_it_is_backfilled_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.run_proof(cwd, proof_home, "start", "Provenance proof", check=True)
            self.run_proof(
                cwd,
                proof_home,
                "add-criterion",
                "--requires",
                "test,file-read",
                "Executed and attached evidence are visible",
                check=True,
            )
            self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"ok\")'",
                check=True,
            )
            source = cwd / "artifact.txt"
            source.write_text("attached proof\n", encoding="utf-8")
            self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "file-read",
                "--artifact-path",
                str(source),
                check=True,
            )
            for evidence_id in ("EV-001", "EV-002"):
                self.run_proof(
                    cwd,
                    proof_home,
                    "review",
                    "--criterion",
                    "AC-001",
                    "--evidence",
                    evidence_id,
                    "--verdict",
                    "supports",
                    "--notes",
                    f"{evidence_id} supports the criterion.",
                    check=True,
                )
            proof_dir = Path(self.run_proof(cwd, proof_home, "path", check=True).stdout.strip())
            state_file = proof_dir / "proof.json"
            state = json.loads(state_file.read_text(encoding="utf-8"))
            for record in state["evidence"]:
                record.pop("provenance", None)
            state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            check = self.run_proof(cwd, proof_home, "check", "--json", check=True)
            show = self.run_proof(cwd, proof_home, "show", "EV-001", check=True)
            status = self.run_proof(cwd, proof_home, "status", check=True)
            report = self.run_proof(cwd, proof_home, "report", check=True)
            report_path = Path(report.stdout.splitlines()[0])

            payload = json.loads(check.stdout)
            self.assertEqual({"attached": 1, "executed": 1}, payload["criteria"][0]["provenance"])
            self.assertIn("Provenance: executed", show.stdout)
            self.assertIn("1 executed / 1 attached", status.stdout)
            self.assertIn("1 executed / 1 attached", report_path.read_text(encoding="utf-8"))

    def test_when_prune_runs_it_requires_age_and_removes_only_old_topics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            old_topic = proof_home / "workspace-a" / "old-topic"
            new_topic = proof_home / "workspace-b" / "new-topic"
            old_topic.mkdir(parents=True)
            new_topic.mkdir(parents=True)
            (old_topic / "proof.json").write_text("{}\n", encoding="utf-8")
            (new_topic / "proof.json").write_text("{}\n", encoding="utf-8")
            old_time = time.time() - 10 * 86400
            os.utime(old_topic / "proof.json", (old_time, old_time))

            missing = self.run_proof(cwd, proof_home, "prune")
            too_small = self.run_proof(cwd, proof_home, "prune", "--older-than", "0")
            dry_run = self.run_proof(cwd, proof_home, "prune", "--older-than", "7", "--dry-run", check=True)
            real = self.run_proof(cwd, proof_home, "prune", "--older-than", "7", check=True)

            self.assertNotEqual(missing.returncode, 0)
            self.assertNotEqual(too_small.returncode, 0)
            self.assertIn(str(old_topic), dry_run.stdout)
            self.assertNotIn(str(new_topic), dry_run.stdout)
            self.assertIn(str(old_topic), real.stdout)
            self.assertFalse(old_topic.exists())
            self.assertTrue(new_topic.exists())

    def test_when_secret_like_evidence_is_added_it_is_refused_unless_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.run_proof(cwd, proof_home, "start", "Secret scanning proof", check=True)
            self.run_proof(
                cwd,
                proof_home,
                "add-criterion",
                "--requires",
                "file-read,log",
                "Secret-like content is not silently persisted",
                check=True,
            )
            token = "ghp_" + "A" * 24
            artifact = cwd / "secret.txt"
            artifact.write_text(f"token={token}\n", encoding="utf-8")
            artifact_result = self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "file-read",
                "--artifact-path",
                str(artifact),
            )
            summary_secret = "abcdefgh12345678"
            summary_result = self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "log",
                "--summary",
                f"api_key='{summary_secret}'",
            )
            allowed = self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "file-read",
                "--artifact-path",
                str(artifact),
                "--allow-secrets",
                check=True,
            )

            combined = artifact_result.stdout + artifact_result.stderr + summary_result.stdout + summary_result.stderr
            self.assertNotEqual(artifact_result.returncode, 0)
            self.assertNotEqual(summary_result.returncode, 0)
            self.assertIn("GITHUB_TOKEN", artifact_result.stderr)
            self.assertIn("GENERIC_SECRET_ASSIGNMENT", summary_result.stderr)
            self.assertNotIn(token, combined)
            self.assertNotIn(summary_secret, combined)
            self.assertIn("Warning: allowing secret-like content matching GITHUB_TOKEN", allowed.stderr)

    def test_when_scan_bound_splits_a_multibyte_char_the_scanned_prefix_still_catches_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            self.run_proof(cwd, proof_home, "start", "Boundary-split scan proof", check=True)
            self.run_proof(
                cwd,
                proof_home,
                "add-criterion",
                "--requires",
                "file-read",
                "A secret before the scan bound is caught in oversized artifacts",
                check=True,
            )
            token = "ghp_" + "B" * 24
            scan_bytes = self.proof_module().SECRET_SCAN_BYTES
            prefix = f"token={token}\n".encode()
            # Pad so a 2-byte UTF-8 char ("é") straddles the scan bound, then
            # keep writing past the bound: strict decode of the truncated read
            # raises, which previously skipped the scan entirely.
            padding = b"a" * (scan_bytes - len(prefix) - 1)
            artifact = cwd / "oversized.log"
            artifact.write_bytes(prefix + padding + "é".encode() + b"tail past the bound\n")
            result = self.run_proof(
                cwd,
                proof_home,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "file-read",
                "--artifact-path",
                str(artifact),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("GITHUB_TOKEN", result.stderr)
            self.assertNotIn(token, result.stdout + result.stderr)

    def test_when_lock_context_wraps_sequential_mutations_both_writes_survive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proof_tmp:
            cwd = Path(tmp)
            proof_home = Path(proof_tmp)
            module = self.proof_module()
            ctx = {
                "workspace": str(cwd),
                "workspace_hash": "lock-workspace",
                "topic": "lock-topic",
                "proof_dir": str(proof_home / "lock-workspace" / "lock-topic"),
            }
            with module.proof_lock(ctx):
                module.save_state(ctx, module.default_state(ctx, goal="Lock proof"))
            with module.proof_lock(ctx):
                state = module.load_state(ctx, create=False)
                state["criteria"].append({"id": "AC-001", "evidence": []})
                module.save_state(ctx, state)
            with module.proof_lock(ctx):
                state = module.load_state(ctx, create=False)
                state["criteria"].append({"id": "AC-002", "evidence": []})
                module.save_state(ctx, state)

            state = json.loads((Path(ctx["proof_dir"]) / "proof.json").read_text(encoding="utf-8"))
            self.assertEqual(["AC-001", "AC-002"], [item["id"] for item in state["criteria"]])
            self.assertTrue((Path(ctx["proof_dir"]) / ".lock").exists())


if __name__ == "__main__":
    unittest.main()
