from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
