from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

from tests.formal_support import (
    CliError,
    anchors_mod,
    catalog_mod,
    commit_all,
    init_git_repo,
    leankit_mod,
    manifest_mod,
    paths_mod,
    read_json,
    run_formal,
    write_json,
    write_json_atomic,
)


class TestCatalog(unittest.TestCase):
    """WHEN units move through init/anchors/save/resolve/checkout/stale/uncovered."""

    def _init_unit_with_anchor(self, workspace: Path, formal_home: Path, unit: str, file_name: str) -> None:
        content = f"def {unit}():\n    return 1\n"
        (workspace / file_name).write_text(content, encoding="utf-8")
        commit_all(workspace, f"add {file_name}")
        run_formal(workspace, formal_home, "init", unit, "--design", check=True)
        run_formal(workspace, formal_home, "anchors", "add", unit, f"{file_name}:1-2", check=True)

    def test_when_saving_without_a_passing_audit_it_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")

            result = run_formal(workspace, formal_home, "catalog", "save", "u1")

            self.assertEqual(1, result.returncode)
            self.assertIn("No passing audit", result.stderr)

    def test_when_allow_unverified_is_passed_save_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")

            result = run_formal(workspace, formal_home, "catalog", "save", "u1", "--allow-unverified", "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["verified"])
            self.assertTrue(payload["id"])

    def test_when_resolving_from_a_different_branch_the_version_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            initial_branch = init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            run_formal(workspace, formal_home, "catalog", "save", "u1", "--allow-unverified", check=True)

            subprocess.run(["git", "checkout", "-q", "-b", "other-branch"], cwd=workspace, check=True)

            result = run_formal(workspace, formal_home, "catalog", "resolve", "u1", "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(initial_branch, payload["branch"])

            storage_key = paths_mod.branch_slug(workspace)
            display = run_formal(workspace, formal_home, "catalog", "resolve", "u1")
            self.assertIn(initial_branch, display.stdout)
            self.assertNotIn(storage_key, display.stdout)

    def test_when_a_squash_style_commit_keeps_anchored_text_the_version_still_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            run_formal(workspace, formal_home, "catalog", "save", "u1", "--allow-unverified", check=True)

            (workspace / "unrelated.py").write_text("x = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=workspace, check=True)
            subprocess.run(["git", "commit", "--amend", "-q", "--no-edit"], cwd=workspace, check=True)

            result = run_formal(workspace, formal_home, "catalog", "resolve", "u1", "--json")

            self.assertEqual(0, result.returncode, result.stderr)

    def test_when_checkout_materializes_a_resolved_version_it_writes_the_work_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            run_formal(workspace, formal_home, "catalog", "save", "u1", "--allow-unverified", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            self.assertTrue(layout.work_dir("u1").is_relative_to(formal_home.resolve()))
            shutil.rmtree(layout.work_dir("u1"))

            result = run_formal(workspace, formal_home, "catalog", "checkout", "u1", "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((layout.work_dir("u1") / manifest_mod.MANIFEST_NAME).exists())

    def test_when_base_is_passed_stale_only_reports_units_whose_anchored_files_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            self._init_unit_with_anchor(workspace, formal_home, "u2", "u2.py")
            base_sha = commit_all(workspace, "both units anchored")

            (workspace / "u1.py").write_text("def u1():\n    return 999\n", encoding="utf-8")
            commit_all(workspace, "break u1 only")

            result = run_formal(workspace, formal_home, "catalog", "stale", "--base", base_sha, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            stale_units = {entry["unit"] for entry in payload["units"]}
            self.assertEqual({"u1"}, stale_units)

    def test_when_a_hunk_is_outside_every_anchor_uncovered_reports_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            base_sha = commit_all(workspace, "anchor u1")

            (workspace / "u1.py").write_text(
                "def u1():\n    return 1\n\n\ndef unrelated():\n    return 2\n", encoding="utf-8"
            )
            commit_all(workspace, "add unrelated hunk")

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["hunks"])
            self.assertTrue(all(h["start"] >= 3 for h in payload["hunks"]))  # anchor covers lines 1-2

    def test_when_the_current_reference_is_a_saved_version_stale_still_finds_it(self) -> None:
        """catalog stale/status/uncovered's "current reference" for a unit is the branch work
        dir when present, else the newest saved version on *any* branch -- not only a version
        whose anchors are still valid. Repro from the review: save u1 on the initial branch
        anchored at u1.py:1-2, then edit that line on a second branch; `stale --base <initial>`
        must list u1 even though the initial branch's resolve_version() would now be invalid."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            initial_branch = init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            run_formal(workspace, formal_home, "catalog", "save", "u1", "--allow-unverified", check=True)

            subprocess.run(["git", "checkout", "-q", "-b", "feat"], cwd=workspace, check=True)
            (workspace / "u1.py").write_text("def u1():\n    return 999\n", encoding="utf-8")
            commit_all(workspace, "edit u1 on feat")

            result = run_formal(workspace, formal_home, "catalog", "stale", "--base", initial_branch, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("u1", {entry["unit"] for entry in payload["units"]})

    def test_when_a_file_is_untracked_uncovered_reports_it_as_a_whole_file_hunk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            base_sha = init_git_repo(workspace)
            (workspace / "new_untracked.py").write_text("def x():\n    return 1\n", encoding="utf-8")

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            hunk = next(h for h in payload["hunks"] if h["path"] == "new_untracked.py")
            self.assertEqual(1, hunk["start"])
            self.assertEqual(2, hunk["end"])

    def test_when_an_anchor_relocates_uncovered_uses_the_relocated_range_not_the_stored_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            base_sha = commit_all(workspace, "anchor u1 at lines 1-2")

            # Prepend two lines: the anchored text (still intact) relocates to lines 3-4, and a
            # genuinely new hunk lands at line 1. The stored anchor range (1-2) would wrongly
            # "cover" that new hunk; the relocated range (3-4) correctly leaves it uncovered.
            (workspace / "u1.py").write_text(
                "# new line one\n# new line two\ndef u1():\n    return 1\n", encoding="utf-8"
            )
            commit_all(workspace, "prepend lines")

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(any(h["path"] == "u1.py" and h["start"] <= 2 for h in payload["hunks"]))

    def test_when_the_audit_receipt_is_pass_only_via_allow_unverified_conformance_save_still_refuses(self) -> None:
        """save's own --allow-unverified gate must not be satisfied by the *audit's* own
        --allow-unverified-conformance leniency: a receipt with verdict "pass" but a required
        stage at status "unverified" (not "pass") is not "every required stage passed"."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "u1.py").write_text("def u1():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add u1.py")
            run_formal(workspace, formal_home, "init", "u1", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u1", "u1.py:1-2", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
            stages = {name: {"status": "pass", "receipt": None} for name in ("anchors", "build", "explore", "mutate")}
            stages["replay"] = {"status": "unverified", "receipt": None}
            write_json(
                unit_dir / "receipts" / snapshot / "audit.json",
                {
                    "unit": "u1",
                    "snapshot": snapshot,
                    "tier": "F2",
                    "stages": stages,
                    "verdict": "pass",
                    "certifies": "x",
                },
            )

            result = run_formal(workspace, formal_home, "catalog", "save", "u1")

            self.assertEqual(1, result.returncode)
            self.assertIn("No passing audit", result.stderr)

    def test_when_a_kit_is_used_by_another_repo_gc_keeps_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            kit_hash = manifest_mod.load_manifest(unit_dir)["kit_hash"]
            (layout.root / "_kit" / kit_hash).mkdir(parents=True, exist_ok=True)
            other_unit_dir = formal_home / "other-repo-id" / "work" / "main" / "u2"
            other_unit_dir.mkdir(parents=True)
            write_json(other_unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u2", "kit_hash": kit_hash})
            # Drop this repo's own reference so only the "other repo" dir keeps the kit live.
            shutil.rmtree(unit_dir)

            result = run_formal(workspace, formal_home, "catalog", "gc", "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertNotIn(kit_hash, payload["removed_kits"])
            self.assertTrue((layout.root / "_kit" / kit_hash).exists())

    def test_when_no_valid_version_exists_checkout_names_the_newest_version_and_init_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            saved = run_formal(
                workspace, formal_home, "catalog", "save", "u1", "--allow-unverified", "--json", check=True
            )
            version_id = json.loads(saved.stdout)["id"]
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            shutil.rmtree(layout.work_dir("u1"))
            # Break the anchor so resolve_version() (anchor-valid only) finds nothing, forcing
            # checkout onto the "no resolvable version" error path.
            (workspace / "u1.py").write_text("def u1():\n    return 999\n", encoding="utf-8")

            result = run_formal(workspace, formal_home, "catalog", "checkout", "u1")

            self.assertEqual(1, result.returncode)
            self.assertIn(version_id, result.stderr)
            self.assertIn(f"init u1 --from-version {version_id}", result.stderr)

    def test_when_checking_out_the_work_dir_contents_are_replaced_but_dot_lake_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            run_formal(workspace, formal_home, "catalog", "save", "u1", "--allow-unverified", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            (unit_dir / ".lake").mkdir(exist_ok=True)
            (unit_dir / ".lake" / "marker").write_text("keep\n", encoding="utf-8")
            (unit_dir / "stray.txt").write_text("drop me\n", encoding="utf-8")
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=workspace, check=True, capture_output=True, text=True
            ).stdout.strip()

            # `stray.txt` is an unsaved local difference from the saved version -- `checkout`
            # now refuses that by default (see TestCatalogCheckoutDirtyGuard); `--force`
            # preserves this test's original intent of checking the `.lake` preservation.
            result = run_formal(workspace, formal_home, "catalog", "checkout", "u1", "--force", "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((unit_dir / ".lake" / "marker").exists())
            self.assertFalse((unit_dir / "stray.txt").exists())
            manifest = manifest_mod.load_manifest(unit_dir)
            self.assertEqual(head, manifest["source_commit"])


class TestCatalogVersionOrderingBySeq(unittest.TestCase):
    """WHEN two versions are saved within the same wall-clock second (A6): `created`'s
    display timestamp cannot order them -- resolve/newest/gc must sort by the monotonically
    increasing per-unit `seq` assigned at save time instead."""

    def _init_unit_with_anchor(self, workspace: Path, formal_home: Path, unit: str, file_name: str) -> None:
        content = f"def {unit}():\n    return 1\n"
        (workspace / file_name).write_text(content, encoding="utf-8")
        commit_all(workspace, f"add {file_name}")
        run_formal(workspace, formal_home, "init", unit, "--design", check=True)
        run_formal(workspace, formal_home, "anchors", "add", unit, f"{file_name}:1-2", check=True)

    def test_two_saves_frozen_at_the_same_instant_the_newer_seq_wins_everywhere(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u1", "u1.py")
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")

            frozen_now = datetime(2024, 1, 1, tzinfo=timezone.utc)

            class _FrozenDatetime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return frozen_now

            with mock.patch.object(catalog_mod, "datetime", _FrozenDatetime):
                v1 = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)
                step_path = unit_dir / "Unit" / "Step.lean"
                step_path.write_text("-- extra\n" + step_path.read_text(encoding="utf-8"), encoding="utf-8")
                v2 = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)

            self.assertEqual(v1["created"], v2["created"])
            self.assertNotEqual(v1["id"], v2["id"])
            self.assertEqual(1, v1["seq"])
            self.assertEqual(2, v2["seq"])

            resolved = catalog_mod.resolve_version(layout, "u1")
            self.assertEqual(v2["id"], resolved["id"])
            self.assertEqual(v2["id"], catalog_mod.newest_version(layout, "u1")["id"])

            gc_result = catalog_mod.gc(layout, keep=1)
            self.assertEqual([{"unit": "u1", "id": v1["id"]}], gc_result["removed_versions"])


class TestCatalogSaveTransactions(unittest.TestCase):
    """WHEN immutable versions are republished, publication, metadata, and GC stay coherent."""

    def _layout_and_unit(self, workspace: Path, formal_home: Path) -> tuple[Any, Path]:
        init_git_repo(workspace)
        (workspace / "u1.py").write_text("def u1():\n    return 1\n", encoding="utf-8")
        commit_all(workspace, "add u1.py")
        run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
        run_formal(workspace, formal_home, "anchors", "add", "u1", "u1.py:1-2", check=True)
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
        return layout, layout.work_dir("u1")

    def test_force_checkout_refuses_work_alias_to_immutable_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout, unit_dir = self._layout_and_unit(Path(tmp), Path(home_tmp))
            record = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)
            saved = layout.version_dir("u1", record["id"])
            before = {str(path.relative_to(saved)): path.read_bytes() for path in saved.rglob("*") if path.is_file()}
            index_before = layout.index_json().read_bytes()
            shutil.rmtree(unit_dir)
            unit_dir.symlink_to(saved, target_is_directory=True)

            with self.assertRaises(CliError):
                catalog_mod.checkout_version(layout, "u1", force=True)

            after = {str(path.relative_to(saved)): path.read_bytes() for path in saved.rglob("*") if path.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(index_before, layout.index_json().read_bytes())

    def test_resaving_an_old_version_interleaved_with_gc_republishes_a_complete_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout, unit_dir = self._layout_and_unit(Path(tmp), Path(home_tmp))
            older = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)
            step = unit_dir / "Unit" / "Step.lean"
            step.write_text("-- newer\n" + step.read_text(encoding="utf-8"), encoding="utf-8")
            catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)
            catalog_mod._replace_work_dir_contents(unit_dir, layout.version_dir("u1", older["id"]))

            real_copytree = shutil.copytree
            gc_ran = False

            def copy_then_gc(source: Any, destination: Any, *args: Any, **kwargs: Any) -> Any:
                nonlocal gc_ran
                result = real_copytree(source, destination, *args, **kwargs)
                if Path(source) == unit_dir and not gc_ran:
                    gc_ran = True
                    catalog_mod.gc(layout, keep=1)
                return result

            with mock.patch.object(catalog_mod.shutil, "copytree", side_effect=copy_then_gc):
                republished = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)

            self.assertEqual(older["id"], republished["id"])
            self.assertTrue((layout.version_dir("u1", older["id"]) / manifest_mod.MANIFEST_NAME).exists())
            self.assertIn(older["id"], {version["id"] for version in catalog_mod.list_versions(layout, "u1")})

    def test_same_id_save_failure_preserves_the_existing_directory_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout, unit_dir = self._layout_and_unit(Path(tmp), Path(home_tmp))
            saved = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)
            destination = layout.version_dir("u1", saved["id"])
            before_index = catalog_mod.load_index(layout)
            before_manifest = (destination / manifest_mod.MANIFEST_NAME).read_bytes()

            with mock.patch.object(catalog_mod, "save_index", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)

            self.assertEqual(before_index, catalog_mod.load_index(layout))
            self.assertEqual(before_manifest, (destination / manifest_mod.MANIFEST_NAME).read_bytes())
            self.assertEqual([], list(destination.parent.glob(f".{saved['id']}.tmp.*")))

    def test_partial_copy_failure_removes_stage_and_its_spurious_kit_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout, unit_dir = self._layout_and_unit(Path(tmp), Path(home_tmp))
            version_id = manifest_mod.version_id_for_unit(unit_dir)

            def fail_after_partial_copy(source: Any, destination: Any, *args: Any, **kwargs: Any) -> Any:
                staged = Path(destination)
                staged.mkdir()
                (staged / "lakefile.toml").write_text(
                    f'path = "{layout.kit_dir("deadbeef")}"\n',
                    encoding="utf-8",
                )
                raise OSError("source disappeared")

            with mock.patch.object(catalog_mod.shutil, "copytree", side_effect=fail_after_partial_copy):
                with self.assertRaises(OSError):
                    catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)

            self.assertEqual([], list(layout.unit_versions_dir("u1").glob(f".{version_id}.tmp.*")))
            self.assertNotIn("deadbeef", catalog_mod._live_kit_hashes(layout.root))
            self.assertFalse(layout.version_dir("u1", version_id).exists())

    def test_metadata_preparation_failure_removes_the_complete_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout, unit_dir = self._layout_and_unit(Path(tmp), Path(home_tmp))
            version_id = manifest_mod.version_id_for_unit(unit_dir)

            with mock.patch.object(catalog_mod, "ensure_repo_json", side_effect=OSError("metadata unavailable")):
                with self.assertRaises(OSError):
                    catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)

            self.assertEqual([], list(layout.unit_versions_dir("u1").glob(f".{version_id}.tmp.*")))
            self.assertFalse(layout.version_dir("u1", version_id).exists())

    def test_resave_rejects_malformed_branch_membership_without_rewriting_the_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout, unit_dir = self._layout_and_unit(Path(tmp), Path(home_tmp))
            saved = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)
            malformed_index = catalog_mod.load_index(layout)
            malformed_record = next(
                version for version in malformed_index["units"]["u1"]["versions"] if version["id"] == saved["id"]
            )
            malformed_record["branches"] = {"opaque-a": "not-a-sequence"}
            catalog_mod.save_index(layout, malformed_index)

            with self.assertRaises(CliError) as ctx:
                catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)

            self.assertEqual(2, ctx.exception.code)
            self.assertEqual(malformed_index, catalog_mod.load_index(layout))
            self.assertTrue(layout.version_dir("u1", saved["id"]).exists())

    def test_resaving_shared_content_retains_each_branch_save_sequence_and_display_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout, unit_dir = self._layout_and_unit(Path(tmp), Path(home_tmp))
            with (
                mock.patch.object(paths_mod, "branch_slug", return_value="opaque-a"),
                mock.patch.object(paths_mod, "current_branch", return_value="branch-a"),
            ):
                first = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)
                step = unit_dir / "Unit" / "Step.lean"
                step.write_text("-- v2\n" + step.read_text(encoding="utf-8"), encoding="utf-8")
                shared = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)
            with (
                mock.patch.object(paths_mod, "branch_slug", return_value="opaque-b"),
                mock.patch.object(paths_mod, "current_branch", return_value="branch-b"),
            ):
                catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)

            shared_record = next(v for v in catalog_mod.list_versions(layout, "u1") if v["id"] == shared["id"])
            self.assertEqual({"opaque-a": 2, "opaque-b": 3}, shared_record["branches"])
            self.assertEqual("branch-b", shared_record["branch"])
            with mock.patch.object(paths_mod, "branch_slug", return_value="opaque-a"):
                resolved = catalog_mod.resolve_version(layout, "u1")
            self.assertEqual(shared["id"], resolved["id"])
            self.assertNotEqual(first["id"], resolved["id"])

    def test_another_branch_resaving_v1_does_not_roll_back_branch_as_v2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout, unit_dir = self._layout_and_unit(Path(tmp), Path(home_tmp))
            with (
                mock.patch.object(paths_mod, "branch_slug", return_value="opaque-a"),
                mock.patch.object(paths_mod, "current_branch", return_value="branch-a"),
            ):
                v1 = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)
                step = unit_dir / "Unit" / "Step.lean"
                step.write_text("-- v2\n" + step.read_text(encoding="utf-8"), encoding="utf-8")
                v2 = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)

            catalog_mod._replace_work_dir_contents(unit_dir, layout.version_dir("u1", v1["id"]))
            with (
                mock.patch.object(paths_mod, "branch_slug", return_value="opaque-b"),
                mock.patch.object(paths_mod, "current_branch", return_value="branch-b"),
            ):
                resaved_v1 = catalog_mod.save_version(layout, "u1", unit_dir, allow_unverified=True)

            with mock.patch.object(paths_mod, "branch_slug", return_value="opaque-a"):
                resolved_a = catalog_mod.resolve_version(layout, "u1")
            self.assertEqual(v2["id"], resolved_a["id"])
            self.assertEqual({"opaque-a": 1, "opaque-b": 3}, resaved_v1["branches"])
            self.assertEqual(v1["id"], catalog_mod.newest_version(layout, "u1")["id"])


class TestCatalogRenameTracking(unittest.TestCase):
    """WHEN an anchored file is renamed (F2): `catalog stale --base` must not miss it."""

    def test_when_a_file_is_renamed_stale_base_still_finds_the_unit(self) -> None:
        """Reproduces rv-probe/p3.sh: a rename-following `git diff --name-only` reports only the
        new path, so a unit anchored to the *old* path never intersected the changed-path set."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            initial_branch = init_git_repo(workspace)
            (workspace / "m.py").write_text("x = 1\nif x:\n    y = 2\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            # Branch, then init/anchor on "feat" -- matches rv-probe/p3.sh's order exactly: the
            # unit's work dir must live under this branch for `stale`'s "current reference" to
            # find it at all.
            subprocess.run(["git", "checkout", "-q", "-b", "feat"], cwd=workspace, check=True)
            run_formal(workspace, formal_home, "init", "u", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:2-3", check=True)
            subprocess.run(["git", "mv", "m.py", "n.py"], cwd=workspace, check=True)
            commit_all(workspace, "rename m.py to n.py")

            result = run_formal(workspace, formal_home, "catalog", "stale", "--base", initial_branch, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("u", {entry["unit"] for entry in payload["units"]})


class TestCatalogCheckoutDirtyGuard(unittest.TestCase):
    """WHEN the work dir differs from the resolved version it is about to be replaced with (F4)."""

    def _init_and_save(self, workspace: Path, formal_home: Path, unit: str, file_name: str) -> None:
        (workspace / file_name).write_text(f"def {unit}():\n    return 1\n", encoding="utf-8")
        commit_all(workspace, f"add {file_name}")
        run_formal(workspace, formal_home, "init", unit, "--design", check=True)
        run_formal(workspace, formal_home, "anchors", "add", unit, f"{file_name}:1-2", check=True)
        run_formal(workspace, formal_home, "catalog", "save", unit, "--allow-unverified", check=True)

    def test_when_the_work_dir_has_an_unsaved_local_file_checkout_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_and_save(workspace, formal_home, "u1", "u1.py")
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            (unit_dir / "MYNOTES.md").write_text("do not lose this\n", encoding="utf-8")

            result = run_formal(workspace, formal_home, "catalog", "checkout", "u1")

            self.assertEqual(2, result.returncode)
            self.assertIn("MYNOTES.md", result.stderr)
            self.assertTrue((unit_dir / "MYNOTES.md").exists())

    def test_when_force_is_passed_checkout_discards_the_local_difference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_and_save(workspace, formal_home, "u1", "u1.py")
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            (unit_dir / "MYNOTES.md").write_text("disposable\n", encoding="utf-8")

            result = run_formal(workspace, formal_home, "catalog", "checkout", "u1", "--force")

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((unit_dir / "MYNOTES.md").exists())

    def test_repeated_checkout_after_a_new_commit_with_no_local_edits_succeeds(self) -> None:
        """Reproduces rv-probe p4.sh P6: checkout itself rewrites MANIFEST `branch`/
        `source_commit` on every call -- a second checkout after HEAD moves again must not
        misread that rewrite as a local edit (A5)."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_and_save(workspace, formal_home, "u1", "u1.py")
            (workspace / "other.txt").write_text("c\n", encoding="utf-8")
            commit_all(workspace, "c2")

            first = run_formal(workspace, formal_home, "catalog", "checkout", "u1")
            self.assertEqual(0, first.returncode, first.stderr)

            (workspace / "other.txt").write_text("c\nd\n", encoding="utf-8")
            commit_all(workspace, "c3")

            second = run_formal(workspace, formal_home, "catalog", "checkout", "u1")
            self.assertEqual(0, second.returncode, second.stderr)

    def test_a_manifest_edit_other_than_branch_or_source_commit_is_still_detected(self) -> None:
        """The A5 fix must ignore only the two fields checkout rewrites -- an unrelated local
        MANIFEST edit is still a real difference and must still refuse."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_and_save(workspace, formal_home, "u1", "u1.py")
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            manifest_path = unit_dir / manifest_mod.MANIFEST_NAME
            manifest = read_json(manifest_path)
            manifest["note"] = "local edit unrelated to checkout bookkeeping"
            write_json(manifest_path, manifest)

            result = run_formal(workspace, formal_home, "catalog", "checkout", "u1")

            self.assertEqual(2, result.returncode)
            self.assertIn("MANIFEST.json", result.stderr)


class TestCatalogUncoveredDeletion(unittest.TestCase):
    """WHEN a hunk is a pure deletion (new-side count 0) (F9)."""

    def test_a_pure_deletion_with_no_spanning_anchor_is_uncovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("x = 1\nif x:\n    y = 2\nz = 3\nw = 4\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            # Anchor covers only line 1 -- adjacent to, but not spanning, the deletion below.
            run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:1-1", check=True)
            base_sha = commit_all(workspace, "anchor line 1")

            (workspace / "m.py").write_text("x = 1\nz = 3\nw = 4\n", encoding="utf-8")
            commit_all(workspace, "delete the guard")

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(any(h["path"] == "m.py" and h.get("deletion") for h in payload["hunks"]))

    def test_a_pure_deletion_spanned_by_an_anchor_is_covered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("x = 1\nif x:\n    y = 2\nz = 3\nw = 4\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add m.py")

            # Delete the inner line first, THEN anchor the two lines that flank the gap in the
            # post-deletion file (current lines 2-3: "if x:" / "z = 3"). The deletion hunk is
            # computed as {start: 2, end: 3} (new-side start, +1) -- the anchor must fully contain
            # that range to count as covering it, not merely sit adjacent to it.
            (workspace / "m.py").write_text("x = 1\nif x:\nz = 3\nw = 4\n", encoding="utf-8")
            commit_all(workspace, "delete just the inner line")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:2-3", check=True)

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(any(h["path"] == "m.py" and h.get("deletion") for h in payload["hunks"]))

    def test_a_deletion_at_the_start_of_the_file_has_a_single_clamped_neighbor(self) -> None:
        """Reproduces rv-probe p4.sh P8/P10: deleting the first lines of a file (git's own
        new-side `start` is 0, "before line 1") must clamp to the single surviving neighbor line
        1 -- not the unclamped `{start: 0, end: 1}`, which no real 1-based anchor could ever
        cover (A11)."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "top.py").write_text("import os\nimport sys\ndef k():\n    return 0\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add top.py")

            (workspace / "top.py").write_text("def k():\n    return 0\n", encoding="utf-8")
            commit_all(workspace, "delete the imports")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "top.py:1-1", check=True)

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(any(h["path"] == "top.py" and h.get("deletion") for h in payload["hunks"]))

    def test_a_deletion_at_the_end_of_the_file_has_a_single_clamped_neighbor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "bottom.py").write_text("def k():\n    return 0\nimport os\nimport sys\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add bottom.py")

            (workspace / "bottom.py").write_text("def k():\n    return 0\n", encoding="utf-8")
            commit_all(workspace, "delete the trailing imports")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            # Anchor covers only line 1 -- not line 2, the file's single surviving neighbor of
            # the end-of-file deletion -- so this must still be reported as uncovered.
            run_formal(workspace, formal_home, "anchors", "add", "u", "bottom.py:1-1", check=True)

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json")

            payload = json.loads(result.stdout)
            deletion_hunks = [h for h in payload["hunks"] if h["path"] == "bottom.py" and h.get("deletion")]
            self.assertEqual(1, len(deletion_hunks))
            self.assertEqual(2, deletion_hunks[0]["start"])
            self.assertEqual(2, deletion_hunks[0]["end"])

    def test_a_whole_file_deletion_anchored_by_some_unit_is_covered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "del.py").write_text("gone = 1\nguard = 2\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add del.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "del.py:1-2", check=True)

            (workspace / "del.py").unlink()
            commit_all(workspace, "delete del.py")

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(any(h["path"] == "del.py" for h in payload["hunks"]))

    def test_a_whole_file_deletion_with_no_anchor_is_reported_under_the_old_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "del.py").write_text("gone = 1\nguard = 2\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add del.py")

            (workspace / "del.py").unlink()
            commit_all(workspace, "delete del.py")

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            matches = [h for h in payload["hunks"] if h["path"] == "del.py"]
            self.assertEqual(1, len(matches))
            self.assertTrue(matches[0].get("deleted_file"))


class TestUnquoteGitPath(unittest.TestCase):
    """WHEN a git diff header path is C-style quoted (A4): decode it back to the real path."""

    def test_a_plain_unquoted_path_passes_through(self) -> None:
        self.assertEqual("plain/path.py", catalog_mod._unquote_git_path("plain/path.py"))

    def test_a_quoted_octal_escaped_non_ascii_path_decodes(self) -> None:
        self.assertEqual("b/\u00e9.py", catalog_mod._unquote_git_path('"b/\\303\\251.py"'))

    def test_a_quoted_embedded_double_quote_decodes(self) -> None:
        self.assertEqual('b/weird"name.py', catalog_mod._unquote_git_path('"b/weird\\"name.py"'))


class TestCatalogStaleNonAsciiAndUntrackedPaths(unittest.TestCase):
    """WHEN `catalog stale --base` must recognize a changed anchored file whose path is
    non-ASCII (git C-quotes it by default) or untracked (never appears in a tracked diff) -- A4."""

    def test_a_changed_non_ascii_tracked_path_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            initial_branch = init_git_repo(workspace)
            (workspace / "\u00e9.py").write_text(
                "def h(x):\n    if x:\n        return 1\n    return 2\n", encoding="utf-8"
            )
            commit_all(workspace, "add unicode file")
            subprocess.run(["git", "checkout", "-q", "-b", "feat"], cwd=workspace, check=True)
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "\u00e9.py:2-3", check=True)
            (workspace / "\u00e9.py").write_text(
                "def h(x):\n    if x:\n        return 99\n    return 2\n", encoding="utf-8"
            )

            result = run_formal(
                workspace, formal_home, "catalog", "stale", "--base", initial_branch, "--json", check=True
            )

            payload = json.loads(result.stdout)
            self.assertIn("u", {entry["unit"] for entry in payload["units"]})

    def test_an_edited_untracked_anchored_file_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            initial_branch = init_git_repo(workspace)
            subprocess.run(["git", "checkout", "-q", "-b", "feat"], cwd=workspace, check=True)
            (workspace / "new.py").write_text(
                "def g(x):\n    if x:\n        return 1\n    return 2\n", encoding="utf-8"
            )
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "new.py:2-3", check=True)
            (workspace / "new.py").write_text(
                "def g(x):\n    if x:\n        return 99\n    return 2\n", encoding="utf-8"
            )

            result = run_formal(
                workspace, formal_home, "catalog", "stale", "--base", initial_branch, "--json", check=True
            )

            payload = json.loads(result.stdout)
            self.assertIn("u", {entry["unit"] for entry in payload["units"]})


class TestCatalogUncoveredFailClosed(unittest.TestCase):
    """WHEN `git ls-files` cannot run at all while computing uncovered hunks (A4): fail closed
    (exit 2), matching catalog.md's git-plumbing rule, never silently report zero untracked
    hunks."""

    def test_ls_files_failure_raises_instead_of_silently_dropping_untracked_hunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)

            with mock.patch.object(
                catalog_mod,
                "run",
                return_value=subprocess.CompletedProcess(["git", "ls-files"], 128, "", "fatal: boom"),
            ):
                with self.assertRaises(CliError) as ctx:
                    catalog_mod._untracked_hunks(workspace)
            self.assertEqual(2, ctx.exception.code)

    def test_uncovered_hunks_propagates_the_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            real_run = catalog_mod.run

            def fake_run(argv, **kwargs):
                if argv[:2] == ["git", "ls-files"]:
                    return subprocess.CompletedProcess(argv, 128, "", "fatal: boom")
                return real_run(argv, **kwargs)

            with mock.patch.object(catalog_mod, "run", side_effect=fake_run):
                with self.assertRaises(CliError) as ctx:
                    catalog_mod.uncovered_hunks(layout, "HEAD")
            self.assertEqual(2, ctx.exception.code)


class TestCatalogUncoveredNonAsciiPaths(unittest.TestCase):
    """WHEN an untracked or newly-changed path contains a non-ASCII character (A4): it must be
    reported by its real path, never git's default C-quoted form."""

    def test_an_untracked_non_ascii_file_is_reported_with_its_real_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            initial_branch = init_git_repo(workspace)
            (workspace / "\u00fc.py").write_text("z = 1\n", encoding="utf-8")

            result = run_formal(
                workspace, formal_home, "catalog", "uncovered", "--base", initial_branch, "--json", check=True
            )

            payload = json.loads(result.stdout)
            paths = {hunk["path"] for hunk in payload["hunks"]}
            self.assertIn("\u00fc.py", paths)

    def test_a_changed_non_ascii_tracked_hunk_is_reported_with_its_real_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            initial_branch = init_git_repo(workspace)
            (workspace / "\u00e9.py").write_text("x = 1\n", encoding="utf-8")
            commit_all(workspace, "add unicode file")
            (workspace / "\u00e9.py").write_text("x = 2\n", encoding="utf-8")

            result = run_formal(
                workspace, formal_home, "catalog", "uncovered", "--base", initial_branch, "--json", check=True
            )

            payload = json.loads(result.stdout)
            paths = {hunk["path"] for hunk in payload["hunks"]}
            self.assertIn("\u00e9.py", paths)


class TestCatalogUncoveredPathWithSpace(unittest.TestCase):
    """WHEN a tracked path contains a space (test-integrity group P3.2): git appends one literal
    trailing tab to the `---`/`+++` header line, and `diff_hunks` must strip it before matching
    against the anchored path -- otherwise the trailing tab survives into the reported path and a
    whole-file deletion that an anchor already covers is wrongly reported as uncovered."""

    def test_a_deleted_file_anchored_under_its_space_containing_path_is_covered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "foo bar.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add foo bar.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "foo bar.py:1-2", check=True)

            (workspace / "foo bar.py").unlink()

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["hunks"])


class TestAtomicIndexWrite(unittest.TestCase):
    """WHEN `index.json` is written (F11): atomically, via a temp file + `os.replace`, under an
    exclusive lock for the read-modify-write sequence."""

    def test_write_json_atomic_leaves_no_temp_file_and_the_correct_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "index.json"
            write_json_atomic(target, {"units": {"u1": {"versions": []}}})

            self.assertEqual({"units": {"u1": {"versions": []}}}, read_json(target))
            leftovers = [p for p in Path(tmp).iterdir() if p.name != "index.json"]
            self.assertEqual([], leftovers)

    def test_update_index_persists_a_mutation_under_the_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

            def _mutate(index: dict[str, Any]) -> None:
                index.setdefault("units", {})["u1"] = {"versions": [{"id": "abc"}], "work": []}

            catalog_mod.update_index(layout, _mutate)

            self.assertEqual([{"id": "abc"}], catalog_mod.load_index(layout)["units"]["u1"]["versions"])


class TestCatalogRepoJsonWrittenOnce(unittest.TestCase):
    """WHEN `repo.json` already exists: `ensure_repo_json` must never overwrite it -- its
    `created_at` sentinel must survive a second call (test-integrity group "repo.json written
    once")."""

    def test_a_second_call_leaves_the_first_created_at_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

            catalog_mod.ensure_repo_json(layout)
            self.assertTrue(layout.repo_json().exists())
            first = read_json(layout.repo_json())

            write_json(layout.repo_json(), {**first, "created_at": "sentinel-should-survive"})
            catalog_mod.ensure_repo_json(layout)

            second = read_json(layout.repo_json())
            self.assertEqual("sentinel-should-survive", second["created_at"])


class TestCatalogNoResolvableVersion(unittest.TestCase):
    """WHEN a unit has never been saved, or has no anchors at all: `version_valid`/
    `resolve_version`/`newest_version` all report "nothing resolvable", and `catalog resolve`
    exits 1 with "No resolvable version" (test-integrity group "no resolvable version exit 1")."""

    def test_version_valid_is_false_for_a_unit_with_zero_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(home_tmp)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

            self.assertFalse(catalog_mod.version_valid(layout, "never-saved", "no-such-version"))

    def test_resolve_and_newest_version_are_none_for_a_never_saved_unit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(home_tmp)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

            self.assertIsNone(catalog_mod.resolve_version(layout, "never-saved"))
            self.assertIsNone(catalog_mod.newest_version(layout, "never-saved"))

    def test_catalog_resolve_on_a_never_saved_unit_exits_1_with_the_exact_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)

            result = run_formal(workspace, formal_home, "catalog", "resolve", "never-saved")

            self.assertEqual(1, result.returncode)
            self.assertIn("No resolvable version for unit never-saved", result.stderr)


class TestCatalogStaleBaseFilterPositive(unittest.TestCase):
    """WHEN `--base` names a commit at (or after) the point a unit's anchor was already broken:
    `catalog stale --base` must exclude it (nothing changed *since* that base) while plain
    `catalog stale` (no base at all, which never filters by diff) still reports it
    (test-integrity group "stale --base filter", F6)."""

    def _init_unit_with_anchor(self, workspace: Path, formal_home: Path, unit: str, file_name: str) -> None:
        content = f"def {unit}():\n    return 1\n"
        (workspace / file_name).write_text(content, encoding="utf-8")
        commit_all(workspace, f"add {file_name}")
        run_formal(workspace, formal_home, "init", unit, "--design", check=True)
        run_formal(workspace, formal_home, "anchors", "add", unit, f"{file_name}:1-2", check=True)

    def test_base_at_the_breaking_commit_excludes_it_but_plain_stale_still_includes_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            self._init_unit_with_anchor(workspace, formal_home, "u2", "u2.py")

            (workspace / "u2.py").write_text("def u2():\n    return 999\n", encoding="utf-8")
            breaking_commit = commit_all(workspace, "break u2's anchor")

            filtered = run_formal(
                workspace, formal_home, "catalog", "stale", "--base", breaking_commit, "--json", check=True
            )
            plain = run_formal(workspace, formal_home, "catalog", "stale", "--json", check=True)

            filtered_units = {entry["unit"] for entry in json.loads(filtered.stdout)["units"]}
            plain_units = {entry["unit"] for entry in json.loads(plain.stdout)["units"]}
            self.assertNotIn("u2", filtered_units)
            self.assertIn("u2", plain_units)


class TestCatalogUncoveredOverlapBoundaries(unittest.TestCase):
    """WHEN a hunk touches either edge of an anchor's range, and when an edited anchor must
    contribute no coverage at all (test-integrity group "uncovered overlap")."""

    class _FakeLayout:
        def __init__(self, workspace: Path) -> None:
            self.workspace = workspace

    def test_hunks_touching_either_edge_of_the_anchor_range_both_count_as_covered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            layout = self._FakeLayout(Path(tmp))
            hunks = [{"path": "f.py", "start": 1, "end": 3}, {"path": "f.py", "start": 4, "end": 6}]
            with (
                mock.patch.object(catalog_mod, "diff_hunks", return_value=hunks),
                mock.patch.object(catalog_mod, "all_known_units", return_value={"u"}),
                mock.patch.object(
                    catalog_mod,
                    "current_reference_anchors",
                    return_value=[{"id": "A1", "path": "f.py", "start": 3, "end": 4}],
                ),
                mock.patch.object(
                    anchors_mod, "check_anchor", return_value={"status": "unchanged", "start": 3, "end": 4}
                ),
            ):
                result = catalog_mod.uncovered_hunks(layout, "HEAD")

            self.assertEqual([], result)

    def test_an_edited_anchor_contributes_no_coverage_at_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            layout = self._FakeLayout(Path(tmp))
            hunks = [{"path": "f.py", "start": 1, "end": 3}, {"path": "f.py", "start": 4, "end": 6}]
            with (
                mock.patch.object(catalog_mod, "diff_hunks", return_value=hunks),
                mock.patch.object(catalog_mod, "all_known_units", return_value={"u"}),
                mock.patch.object(
                    catalog_mod,
                    "current_reference_anchors",
                    return_value=[{"id": "A1", "path": "f.py", "start": 3, "end": 4}],
                ),
                mock.patch.object(anchors_mod, "check_anchor", return_value={"status": "edited"}),
            ):
                result = catalog_mod.uncovered_hunks(layout, "HEAD")

            self.assertEqual(2, len(result))

    def test_a_deletion_hunk_needs_the_anchor_to_fully_straddle_it_not_merely_overlap(self) -> None:
        """The deletion-specific containment check (`r_start <= hunk.start and r_end >=
        hunk.end`) is strictly stronger than the ordinary overlap check above: an anchor
        exactly matching the deletion's neighbor range covers it, but an anchor that only
        reaches one of the two boundary lines does not."""
        with tempfile.TemporaryDirectory() as tmp:
            layout = self._FakeLayout(Path(tmp))
            deletion_hunk = [{"path": "f.py", "start": 3, "end": 4, "deletion": True}]
            with (
                mock.patch.object(catalog_mod, "diff_hunks", return_value=deletion_hunk),
                mock.patch.object(catalog_mod, "all_known_units", return_value={"u"}),
                mock.patch.object(
                    catalog_mod,
                    "current_reference_anchors",
                    return_value=[{"id": "A1", "path": "f.py", "start": 3, "end": 4}],
                ),
            ):
                # Exactly matching the deletion's own {start, end}: covered.
                with mock.patch.object(
                    anchors_mod, "check_anchor", return_value={"status": "unchanged", "start": 3, "end": 4}
                ):
                    self.assertEqual([], catalog_mod.uncovered_hunks(layout, "HEAD"))

                # Relocated to {start: 4, end: 4}: no longer reaches line 3 -- uncovered.
                with mock.patch.object(
                    anchors_mod, "check_anchor", return_value={"status": "unchanged", "start": 4, "end": 4}
                ):
                    self.assertEqual(deletion_hunk, catalog_mod.uncovered_hunks(layout, "HEAD"))

                # Relocated to {start: 3, end: 3}: no longer reaches line 4 -- uncovered.
                with mock.patch.object(
                    anchors_mod, "check_anchor", return_value={"status": "unchanged", "start": 3, "end": 3}
                ):
                    self.assertEqual(deletion_hunk, catalog_mod.uncovered_hunks(layout, "HEAD"))


class TestEveryRequiredStagePassedTable(unittest.TestCase):
    """WHEN `_every_required_stage_passed` decides `catalog save`'s own verified gate
    (test-integrity group "save verified gate positive", F5)."""

    def test_f2_all_stages_pass_is_true(self) -> None:
        manifest = {"tier": "F2", "design": False}
        receipt = {"stages": {name: {"status": "pass"} for name in ("anchors", "build", "explore", "mutate", "replay")}}
        self.assertTrue(catalog_mod._every_required_stage_passed(manifest, receipt))

    def test_design_unit_with_replay_n_a_is_true(self) -> None:
        manifest = {"tier": "F2", "design": True}
        stages = {name: {"status": "pass"} for name in ("anchors", "build", "explore", "mutate")}
        stages["replay"] = {"status": "n/a"}
        self.assertTrue(catalog_mod._every_required_stage_passed(manifest, {"stages": stages}))

    def test_design_unit_with_replay_fail_instead_of_n_a_is_false(self) -> None:
        manifest = {"tier": "F2", "design": True}
        stages = {name: {"status": "pass"} for name in ("anchors", "build", "explore", "mutate")}
        stages["replay"] = {"status": "fail"}
        self.assertFalse(catalog_mod._every_required_stage_passed(manifest, {"stages": stages}))

    def test_a_non_replay_stage_short_of_pass_is_false(self) -> None:
        """Isolates the general `status != "pass"` branch (distinct from the replay/design
        special-case above): a plain `build` stage at `fail` must fail the gate too."""
        manifest = {"tier": "F2", "design": False}
        stages = {name: {"status": "pass"} for name in ("anchors", "explore", "mutate", "replay")}
        stages["build"] = {"status": "fail"}
        self.assertFalse(catalog_mod._every_required_stage_passed(manifest, {"stages": stages}))


class TestCatalogIndexWorkList(unittest.TestCase):
    """WHEN a unit is saved, the index work list uses its opaque branch storage key."""

    def test_after_save_catalog_list_reports_the_storage_key_and_readable_display_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            branch = init_git_repo(workspace)
            storage_key = paths_mod.branch_slug(workspace)
            (workspace / "u1.py").write_text("def u1():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add u1.py")
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u1", "u1.py:1-2", check=True)
            run_formal(workspace, formal_home, "catalog", "save", "u1", "--allow-unverified", check=True)

            result = run_formal(workspace, formal_home, "catalog", "list", "--json", check=True)

            payload = json.loads(result.stdout)
            unit = payload["units"]["u1"]
            self.assertEqual([storage_key], unit["work"])
            self.assertEqual(branch, unit["versions"][0]["branch"])


class TestCatalogGcRemoval(unittest.TestCase):
    """WHEN `catalog gc` drops old versions and orphan kit dirs, but must keep a kit any repo
    still references from either a MANIFEST or a lakefile.toml -- and must never scan `_exports`
    for such references (test-integrity group "gc removal", F8)."""

    def test_live_kit_hashes_is_empty_when_the_state_root_does_not_exist_at_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            nonexistent = Path(tmp) / "never-created"
            self.assertEqual(set(), catalog_mod._live_kit_hashes(nonexistent))

    def test_a_bare_manifest_kit_hash_reference_with_no_lakefile_is_still_live(self) -> None:
        """Isolates the MANIFEST-scan half of `_live_kit_hashes` from the lakefile.toml-scan
        half (a real unit's own template lakefile.toml independently re-references its kit
        path, which would otherwise mask a mutation to only this condition)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit_dir = root / "some-repo-id" / "work" / "main" / "u1"
            unit_dir.mkdir(parents=True)
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u1", "kit_hash": "deadbeef1234"})

            live = catalog_mod._live_kit_hashes(root)

            self.assertIn("deadbeef1234", live)

    def test_a_kit_still_referenced_by_its_own_units_manifest_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            kit_hash = manifest_mod.load_manifest(layout.work_dir("u1"))["kit_hash"]

            result = run_formal(workspace, formal_home, "catalog", "gc", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertNotIn(kit_hash, payload["removed_kits"])
            self.assertTrue((layout.root / "_kit" / kit_hash).exists())

    def _init_and_save(self, workspace: Path, formal_home: Path, unit: str, content: str) -> str:
        (workspace / f"{unit}.py").write_text(content, encoding="utf-8")
        commit_all(workspace, f"write {unit}.py")
        run_formal(workspace, formal_home, "anchors", "add", unit, f"{unit}.py:1-2", "--id", "A1", check=True)
        saved = run_formal(workspace, formal_home, "catalog", "save", unit, "--allow-unverified", "--json", check=True)
        return json.loads(saved.stdout)["id"]

    def test_two_versions_keep_1_removes_the_older_one_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            older_id = self._init_and_save(workspace, formal_home, "u1", "def u1():\n    return 1\n")
            newer_id = self._init_and_save(workspace, formal_home, "u1", "def u1():\n    return 2\n")
            self.assertNotEqual(older_id, newer_id)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

            result = run_formal(workspace, formal_home, "catalog", "gc", "--keep", "1", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertEqual([{"unit": "u1", "id": older_id}], payload["removed_versions"])
            self.assertFalse(layout.version_dir("u1", older_id).exists())
            self.assertTrue(layout.version_dir("u1", newer_id).exists())

    def test_an_orphan_kit_dir_with_no_referencing_manifest_or_lakefile_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            kit_hash = manifest_mod.load_manifest(unit_dir)["kit_hash"]
            shutil.rmtree(unit_dir)  # drop the only reference to this kit hash

            result = run_formal(workspace, formal_home, "catalog", "gc", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertIn(kit_hash, payload["removed_kits"])
            self.assertFalse((layout.root / "_kit" / kit_hash).exists())

    def test_a_kit_referenced_only_by_a_lakefile_toml_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            kit_hash = manifest_mod.load_manifest(unit_dir)["kit_hash"]
            shutil.rmtree(unit_dir)
            other_repo_dir = formal_home / "other-repo-id"
            other_repo_dir.mkdir(parents=True)
            (other_repo_dir / "lakefile.toml").write_text(
                f'require formalKit from "_kit/{kit_hash}"\n', encoding="utf-8"
            )

            result = run_formal(workspace, formal_home, "catalog", "gc", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertNotIn(kit_hash, payload["removed_kits"])
            self.assertTrue((layout.root / "_kit" / kit_hash).exists())

    def test_a_manifest_reference_under_exports_is_never_scanned_and_the_kit_is_still_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            kit_hash = manifest_mod.load_manifest(unit_dir)["kit_hash"]
            shutil.rmtree(unit_dir)
            exports_manifest_dir = layout.exports_dir() / "stray"
            exports_manifest_dir.mkdir(parents=True)
            write_json(exports_manifest_dir / manifest_mod.MANIFEST_NAME, {"unit": "u1", "kit_hash": kit_hash})

            result = run_formal(workspace, formal_home, "catalog", "gc", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertIn(kit_hash, payload["removed_kits"])

    def test_a_kit_dir_whose_lock_is_currently_held_is_kept(self) -> None:
        """`gc` takes the same per-kit lock (non-blocking) `leankit.ensure_kit` holds while
        installing a kit (P5.2) -- a lock currently held by another process (simulated here by
        holding it ourselves) must never be raced, even for an otherwise-orphaned kit."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            kit_hash = manifest_mod.load_manifest(unit_dir)["kit_hash"]
            shutil.rmtree(unit_dir)  # drop the only reference -- would be an orphan otherwise
            kit_dir = layout.root / "_kit" / kit_hash

            with leankit_mod.kit_lock(kit_dir) as handle:
                self.assertIsNotNone(handle)
                result = catalog_mod.gc(layout, keep=1)

            self.assertNotIn(kit_hash, result["removed_kits"])
            self.assertTrue(kit_dir.exists())

    def test_an_in_progress_tmp_kit_copy_is_never_swept(self) -> None:
        """`ensure_kit`'s own in-progress temp copy (`.<hash>.tmp.<uuid>`) must never be raced
        away by a concurrent `gc` sweep (P5.2)."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            tmp_kit = layout.root / "_kit" / ".deadbeef.tmp.abc123"
            tmp_kit.mkdir(parents=True)
            (tmp_kit / "partial.txt").write_text("mid-copy\n", encoding="utf-8")

            result = catalog_mod.gc(layout, keep=1)

            self.assertNotIn(".deadbeef.tmp.abc123", result["removed_kits"])
            self.assertTrue(tmp_kit.exists())

    def test_a_kit_dir_with_a_still_alive_owner_pid_recorded_is_kept(self) -> None:
        """Validates `_kit_owner_alive`: a kit dir with no live MANIFEST/lakefile reference, but
        whose lock file still records a pid that is currently running (here, this test process's
        own pid), is treated as still being installed -- see `catalog.gc`'s docstring for why
        this, not a wall-clock grace period, closes the window between `ensure_kit` finishing and
        its caller's own MANIFEST/lakefile write (outside this packet's ownership) landing on
        disk."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            kit_dir = layout.root / "_kit" / "deadbeef1234"
            kit_dir.mkdir(parents=True)
            (kit_dir / leankit_mod._KIT_MARKER).write_text("", encoding="utf-8")
            leankit_mod.kit_lock_path(kit_dir).write_text(json.dumps({"owners": [os.getpid()]}), encoding="utf-8")

            result = catalog_mod.gc(layout, keep=1)

            self.assertNotIn("deadbeef1234", result["removed_kits"])
            self.assertTrue(kit_dir.exists())

    def test_a_kit_dir_with_a_dead_owner_pid_recorded_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            kit_dir = layout.root / "_kit" / "deadbeef5678"
            kit_dir.mkdir(parents=True)
            (kit_dir / leankit_mod._KIT_MARKER).write_text("", encoding="utf-8")
            # A pid guaranteed dead: spawn a trivial child and wait for it to exit.
            dead_proc = subprocess.Popen([sys.executable, "-c", "pass"])
            dead_pid = dead_proc.pid
            dead_proc.wait()
            leankit_mod.kit_lock_path(kit_dir).write_text(json.dumps({"owners": [dead_pid]}), encoding="utf-8")

            result = catalog_mod.gc(layout, keep=1)

            self.assertIn("deadbeef5678", result["removed_kits"])
            self.assertFalse(kit_dir.exists())

    def test_a_kit_that_becomes_live_while_gc_holds_its_lock_is_kept(self) -> None:
        """Q5.3: liveness (manifest/lakefile references, and the owner pid) must be decided while
        holding this kit's own lock, never from a snapshot computed before the sweep loop starts.
        Simulates a concurrent `,formal init` that finishes -- writes its MANIFEST.json reference
        -- exactly as `gc` takes this kit's lock (injected via a `leankit.kit_lock` wrapper): a
        pre-loop snapshot would already have decided this kit looked orphaned before that write
        landed."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            kit_hash = manifest_mod.load_manifest(unit_dir)["kit_hash"]
            manifest_path = unit_dir / manifest_mod.MANIFEST_NAME
            manifest_payload = read_json(manifest_path)
            shutil.rmtree(unit_dir)  # drop the only reference -- looks orphaned before the race

            real_kit_lock = leankit_mod.kit_lock

            @contextlib.contextmanager
            def late_writing_kit_lock(dest: Path, *, blocking: bool = True) -> Any:
                with real_kit_lock(dest, blocking=blocking) as handle:
                    if handle is not None and dest.name == kit_hash:
                        unit_dir.mkdir(parents=True)
                        write_json(manifest_path, manifest_payload)
                    yield handle

            with mock.patch.object(leankit_mod, "kit_lock", side_effect=late_writing_kit_lock):
                result = catalog_mod.gc(layout, keep=1)

            self.assertNotIn(kit_hash, result["removed_kits"])
            self.assertTrue((layout.root / "_kit" / kit_hash).exists())

    def test_a_kit_dir_with_malformed_owner_state_is_not_silently_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            kit_dir = layout.root / "_kit" / "deadbeef9999"
            kit_dir.mkdir(parents=True)
            (kit_dir / leankit_mod._KIT_MARKER).write_text("", encoding="utf-8")
            leankit_mod.kit_lock_path(kit_dir).write_text('{"owners":"not-an-array"}', encoding="utf-8")

            with self.assertRaises(CliError) as ctx:
                catalog_mod.gc(layout, keep=1)

            self.assertEqual(2, ctx.exception.code)
            self.assertTrue(kit_dir.exists())


class TestKitOwnerAliveGaps(unittest.TestCase):
    """WHEN owner-set state is empty, malformed, or contains PIDs with unusual liveness
    results, GC must preserve the strict JSON-object storage contract."""

    def _handle(self, tmp: Path, content: str) -> Any:
        lock_path = tmp / ".lock"
        lock_path.write_text(content, encoding="utf-8")
        return open(lock_path, "r+", encoding="utf-8")  # noqa: SIM115

    def test_an_empty_lock_file_is_treated_as_dead(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handle = self._handle(Path(tmp), "")
            try:
                self.assertFalse(catalog_mod._kit_owner_alive(handle))
            finally:
                handle.close()

    def test_a_non_numeric_owner_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handle = self._handle(Path(tmp), '{"owners":["not-a-pid"]}')
            try:
                with self.assertRaises(CliError) as ctx:
                    catalog_mod._kit_owner_alive(handle)
                self.assertEqual(2, ctx.exception.code)
            finally:
                handle.close()

    def test_a_pid_we_lack_permission_to_signal_is_treated_as_alive(self) -> None:
        if hasattr(os, "getuid") and os.getuid() == 0:
            self.skipTest("running as root can signal pid 1")
        with tempfile.TemporaryDirectory() as tmp:
            handle = self._handle(Path(tmp), '{"owners":[1]}')
            try:
                self.assertTrue(catalog_mod._kit_owner_alive(handle))
            finally:
                handle.close()

    def test_an_os_error_from_kill_other_than_process_lookup_is_treated_as_dead(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handle = self._handle(Path(tmp), '{"owners":[123]}')
            try:
                with mock.patch.object(catalog_mod.os, "kill", side_effect=OSError(22, "Invalid argument")):
                    self.assertFalse(catalog_mod._kit_owner_alive(handle))
            finally:
                handle.close()

    def test_an_overflowing_pid_is_treated_as_dead(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handle = self._handle(Path(tmp), '{"owners":[9999999999999999999999999999999999999999]}')
            try:
                with mock.patch.object(
                    catalog_mod.os, "kill", side_effect=OverflowError("Python int too large to convert to C long")
                ):
                    self.assertFalse(catalog_mod._kit_owner_alive(handle))
            finally:
                handle.close()

    def test_any_live_owner_in_a_multi_owner_record_keeps_the_kit_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handle = self._handle(Path(tmp), '{"owners":[101,202]}')

            def owner_liveness(pid: int, signal: int) -> None:
                if pid == 101:
                    raise ProcessLookupError

            try:
                with mock.patch.object(catalog_mod.os, "kill", side_effect=owner_liveness):
                    self.assertTrue(catalog_mod._kit_owner_alive(handle))
            finally:
                handle.close()


class TestCatalogMergeBaseFailures(unittest.TestCase):
    """WHEN `--base` cannot be resolved to a merge-base at all, or a subsequent `git diff` call
    fails: both `catalog stale`'s `changed_paths_since` and `catalog uncovered`'s `diff_hunks`
    must fail closed (exit 2), never silently read it as "nothing changed" (test-integrity group
    "git plumbing fails closed", the `catalog.py` merge-base half; see
    `TestChangedPathsSinceFailsClosed` for `changed_paths_since`'s own diff/ls-files half)."""

    def test_stale_base_with_an_unresolvable_ref_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)

            result = run_formal(workspace, formal_home, "catalog", "stale", "--base", "nosuchref-typo")

            self.assertEqual(2, result.returncode)
            self.assertIn("Cannot resolve merge-base", result.stderr)

    def test_diff_hunks_raises_when_the_git_diff_call_itself_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            real_run = catalog_mod.run

            def fake_run(argv, **kwargs):
                if "diff" in argv and "--unified=0" in argv:
                    return subprocess.CompletedProcess(argv, 128, "", "fatal: boom")
                return real_run(argv, **kwargs)

            with mock.patch.object(catalog_mod, "run", side_effect=fake_run):
                with self.assertRaises(CliError) as ctx:
                    catalog_mod.diff_hunks(workspace, "HEAD")
            self.assertEqual(2, ctx.exception.code)


class TestCatalogSaveVerifiedPositivePath(unittest.TestCase):
    """WHEN a genuinely passing audit receipt exists for the current snapshot: `catalog save`
    (with no `--allow-unverified`) must succeed and record `verified: true` -- the positive
    counterpart to the existing `--allow-unverified` tests (test-integrity group F5 "save
    verified gate positive")."""

    def test_save_without_allow_unverified_succeeds_and_records_verified_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "u1.py").write_text("def u1():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add u1.py")
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u1", "u1.py:1-2", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("u1")
            snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
            stages = {name: {"status": "pass", "receipt": None} for name in ("anchors", "build", "explore", "mutate")}
            stages["replay"] = {"status": "n/a", "receipt": None}
            write_json(
                unit_dir / "receipts" / snapshot / "audit.json",
                {
                    "unit": "u1",
                    "snapshot": snapshot,
                    "tier": "F2",
                    "stages": stages,
                    "verdict": "pass",
                    "certifies": "x",
                },
            )

            result = run_formal(workspace, formal_home, "catalog", "save", "u1", "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["verified"])


class TestCatalogAndAuditOnUnbornHeadRepo(unittest.TestCase):
    """WHEN the workspace has no commits yet (an unborn `HEAD`) (V3.1, repro
    `/tmp/converge-refute-r6-env/ws-unborn`): `catalog save --allow-unverified` and `,formal
    audit` must both reach a real result through `manifest.snapshot_id`, never the misleading
    "incomplete diff" exit-2 that `git diff HEAD` used to raise on a repo with no commits."""

    def _unborn_workspace_with_unit(self, workspace: Path, formal_home: Path, unit: str, file_name: str) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
        (workspace / file_name).write_text(f"def {unit}():\n    return 1\n", encoding="utf-8")
        run_formal(workspace, formal_home, "init", unit, "--design", check=True)
        run_formal(workspace, formal_home, "anchors", "add", unit, f"{file_name}:1-2", check=True)

    def test_catalog_save_allow_unverified_succeeds_with_no_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._unborn_workspace_with_unit(workspace, formal_home, "u1", "u1.py")

            result = run_formal(workspace, formal_home, "catalog", "save", "u1", "--allow-unverified", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["verified"])
            self.assertTrue(payload["id"])

    def test_audit_json_reaches_a_verdict_with_no_commits(self) -> None:
        """Requires `lake` on PATH; fails (does not skip) when missing, per the worker
        contract -- matches the existing real-Lean audit tests' own convention."""
        if shutil.which("lake") is None:
            self.fail(
                "`lake` is required for this ,formal audit test and was not found on PATH. "
                "Install the pinned Lean toolchain (see `,formal doctor --install` or "
                "`brew install elan-init`) before running."
            )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._unborn_workspace_with_unit(workspace, formal_home, "u1", "u1.py")

            result = run_formal(workspace, formal_home, "audit", "u1", "--require", "build", "--json")

            self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn(payload["verdict"], ("pass", "fail"))
            self.assertIn(payload["stages"]["build"]["status"], ("pass", "fail"))


class TestDiffHunksIgnoresLocalRenameConfig(unittest.TestCase):
    """WHEN the repo's local `diff.renames` config would auto-detect a rename (test-integrity
    group P3.1): `diff_hunks` must still pass `--no-renames` explicitly, so a renamed-and-edited
    file is reported as a deletion of the old path plus an addition of the new one -- never
    collapsed under a single path the way rename-following output would, which would drop the
    old path's `deleted_file` coverage entirely."""

    def test_a_rename_with_local_diff_renames_config_is_still_reported_as_delete_plus_add(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            subprocess.run(["git", "config", "diff.renames", "copies"], cwd=workspace, check=True)
            (workspace / "oldname.py").write_text(
                "def oldname():\n    return 1\n    return 2\n    return 3\n", encoding="utf-8"
            )
            base_sha = commit_all(workspace, "add oldname.py")
            subprocess.run(["git", "mv", "oldname.py", "newname.py"], cwd=workspace, check=True)
            (workspace / "newname.py").write_text(
                "def oldname():\n    return 1\n    return 2\n    return 99\n", encoding="utf-8"
            )
            commit_all(workspace, "rename and edit")

            hunks = catalog_mod.diff_hunks(workspace, base_sha)

            self.assertTrue(any(h["path"] == "oldname.py" and h.get("deleted_file") for h in hunks))
            self.assertTrue(any(h["path"] == "newname.py" for h in hunks))


class TestDiffHunksIgnoresLocalPrefixConfig(unittest.TestCase):
    """WHEN the repo's local `diff.mnemonicPrefix` or `diff.noprefix` config changes the
    `---`/`+++` header prefixes git prints (`i/`/`w/` instead of `a/`/`b/`, or no prefix at all):
    `diff_hunks` must still pass `--src-prefix=a/ --dst-prefix=b/` explicitly, so the header
    parsing below (which strips exactly `a/`/`b/`) reports the bare path either way, never a
    prefix fragment (e.g. `w/m.py`) left over from the local config."""

    def test_mnemonic_prefix_config_does_not_leak_into_the_reported_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            subprocess.run(["git", "config", "diff.mnemonicPrefix", "true"], cwd=workspace, check=True)
            (workspace / "m.py").write_text("a\nb\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add m.py")
            (workspace / "m.py").write_text("a\nB\n", encoding="utf-8")
            commit_all(workspace, "edit m.py")

            hunks = catalog_mod.diff_hunks(workspace, base_sha)

            self.assertTrue(any(h["path"] == "m.py" for h in hunks))

    def test_noprefix_config_does_not_break_path_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            subprocess.run(["git", "config", "diff.noprefix", "true"], cwd=workspace, check=True)
            (workspace / "m.py").write_text("a\nb\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add m.py")
            (workspace / "m.py").write_text("a\nB\n", encoding="utf-8")
            commit_all(workspace, "edit m.py")

            hunks = catalog_mod.diff_hunks(workspace, base_sha)

            self.assertTrue(any(h["path"] == "m.py" for h in hunks))


class TestDiffHunksHeaderParsing(unittest.TestCase):
    """WHEN a hunk body line's own added text happens to start with `+++ `/`--- ` (e.g. an added
    line whose content is literally `++ x`, printed by git as `+++ x`) (test-integrity group
    P3.2): header/file-path parsing must never mistake it for the next file's header, so a later
    real hunk in the same file keeps its correct path."""

    def test_a_body_line_that_looks_like_a_file_header_does_not_corrupt_the_next_hunks_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add m.py")
            (workspace / "m.py").write_text("a = 1\n++ x\nb = 2\nc = 3\nd = 4\nzz = 99\n", encoding="utf-8")
            commit_all(workspace, "add a decoy line plus a real edit")

            hunks = catalog_mod.diff_hunks(workspace, base_sha)

            self.assertEqual(
                [("m.py", 2, 2), ("m.py", 6, 6)],
                [(h["path"], h["start"], h["end"]) for h in hunks],
            )


class TestDiffHunksIgnoresLocalInterHunkContextConfig(unittest.TestCase):
    """WHEN the repo's local `diff.interHunkContext` config would fuse two nearby `--unified=0`
    hunks in the same file into one (test-integrity group S6.1, repro ihc.sh): `diff_hunks` must
    still pass `--inter-hunk-context=0` explicitly. A fused hunk's header `old_count`/`new_count`
    each include the fused-in context lines, but those lines are printed only once (not once per
    side) -- an unfused hunk leaking through would desync `remaining_body_lines` and corrupt
    parsing for every file that follows the fused one (here, `b.py`)."""

    def test_inter_hunk_context_config_does_not_fuse_hunks_or_corrupt_later_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            subprocess.run(["git", "config", "diff.interHunkContext", "10"], cwd=workspace, check=True)
            a_lines = [f"line{i}" for i in range(1, 13)]
            (workspace / "a.py").write_text("\n".join(a_lines) + "\n", encoding="utf-8")
            (workspace / "b.py").write_text("b1\nb2\nb3\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add a.py and b.py")
            a_lines[0] = "CHANGED1"
            a_lines[9] = "CHANGED10"
            (workspace / "a.py").write_text("\n".join(a_lines) + "\n", encoding="utf-8")
            (workspace / "b.py").write_text("b1\nB2\nb3\n", encoding="utf-8")
            commit_all(workspace, "edit both files far apart")

            hunks = catalog_mod.diff_hunks(workspace, base_sha)

            self.assertEqual(
                {("a.py", 1, 1), ("a.py", 10, 10), ("b.py", 2, 2)},
                {(h["path"], h["start"], h["end"]) for h in hunks},
            )


class TestDiffHunksIgnoresLocalTextconvConfig(unittest.TestCase):
    """WHEN a repo-local `.git/info/attributes` `diff=<driver>` assignment plus a
    `diff.<driver>.textconv` filter would rewrite the compared text before git computes line
    numbers against it (test-integrity group S6.1, repro tc.sh): `diff_hunks` must still pass
    `--no-textconv` explicitly, so the reported hunk range describes the real file's own line
    numbers, never a textconv-prepended view of it."""

    def test_textconv_driver_does_not_shift_reported_line_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            (workspace / "a.py").write_text("\n".join(f"line{i}" for i in range(1, 13)) + "\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add a.py")
            (workspace / ".git" / "info" / "attributes").write_text("*.py diff=hdr\n", encoding="utf-8")
            subprocess.run(
                ["git", "config", "diff.hdr.textconv", 'sh -c \'printf "h1\\nh2\\n"; cat "$1"\' -'],
                cwd=workspace,
                check=True,
            )
            lines = [f"line{i}" for i in range(1, 13)]
            lines[8] = "CHANGED9"
            (workspace / "a.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
            commit_all(workspace, "edit line 9")

            hunks = catalog_mod.diff_hunks(workspace, base_sha)

            self.assertEqual([("a.py", 9, 9)], [(h["path"], h["start"], h["end"]) for h in hunks])


class TestDiffHunksIgnoresLocalExtDiffConfig(unittest.TestCase):
    """WHEN the repo's local `diff.external` config would hand line-level diff computation to a
    third-party tool (test-integrity group S6.2, `--no-ext-diff` required): `diff_hunks` must
    still pass `--no-ext-diff` explicitly, so hunks always come from git's own internal diff
    machinery -- an external tool's own output format (here, one that prints nothing at all) must
    never suppress or corrupt the parsed hunk ranges."""

    def test_diff_external_config_does_not_suppress_or_corrupt_hunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            subprocess.run(["git", "config", "diff.external", "true"], cwd=workspace, check=True)
            (workspace / "m.py").write_text("a\nb\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add m.py")
            (workspace / "m.py").write_text("a\nB\n", encoding="utf-8")
            commit_all(workspace, "edit m.py")

            hunks = catalog_mod.diff_hunks(workspace, base_sha)

            self.assertEqual([("m.py", 2, 2)], [(h["path"], h["start"], h["end"]) for h in hunks])


class TestDiffHunksSplitVsSplitlines(unittest.TestCase):
    """WHEN a hunk body line contains a literal `\\x0c` form-feed byte, followed (in the same
    hunk) by a line whose own content looks like a file header (`++ y`, printed by git as
    `+++ y`) (test-integrity group S6.2, `.split("\\n")` vs `str.splitlines` killer): splitting
    `diff.stdout` on `str.splitlines` instead of a literal `"\\n"` would treat that `\\x0c` byte as
    an extra line boundary, desyncing `remaining_body_lines` by one line early -- the following
    `+++ y` line would then be misread as a real file-header line (never a body line to skip),
    stealing `current_path` away from `m.py` for the second hunk in the same file."""

    def test_a_form_feed_body_line_never_desyncs_the_next_hunks_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            crafted_diff = (
                "diff --git a/m.py b/m.py\n"
                "index aaaaaaa..bbbbbbb 100644\n"
                "--- a/m.py\n"
                "+++ b/m.py\n"
                "@@ -2,1 +2,2 @@\n"
                "-b = 2\n"
                "+l1\x0cX\n"
                "+++ y\n"
                "@@ -5 +6 @@\n"
                "-e = 5\n"
                "+zz = 99\n"
            )
            real_run = catalog_mod.run

            def fake_run(argv, **kwargs):
                if "diff" in argv and "--unified=0" in argv:
                    return subprocess.CompletedProcess(argv, 0, crafted_diff, "")
                return real_run(argv, **kwargs)

            with mock.patch.object(catalog_mod, "run", side_effect=fake_run):
                hunks = catalog_mod.diff_hunks(workspace, "HEAD")

            self.assertEqual(
                [("m.py", 2, 3), ("m.py", 6, 6)],
                [(h["path"], h["start"], h["end"]) for h in hunks],
            )


class TestUntrackedHunksLineCounting(unittest.TestCase):
    """WHEN an untracked file's content contains a literal `\\x0c` form-feed byte mid-line
    (test-integrity group P3.3): line counting must split only on `\\n` -- `str.splitlines` also
    breaks on `\\x0c`, which would overcount the file's real line count."""

    def test_a_form_feed_byte_is_not_treated_as_a_line_break(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            (workspace / "ff.py").write_text("line1\x0cstill_line1\nline2\n", encoding="utf-8")

            hunks = catalog_mod._untracked_hunks(workspace)

            hunk = next(h for h in hunks if h["path"] == "ff.py")
            self.assertEqual(1, hunk["start"])
            self.assertEqual(2, hunk["end"])


class TestChangedPathsSinceFailsClosed(unittest.TestCase):
    """WHEN a `git diff` or `git ls-files` call inside `changed_paths_since` fails or times out
    (test-integrity group P3.4): fail closed (exit-code-2 `CliError`), consistent with the rest
    of the module -- never silently treat that half of the diff as "nothing changed"."""

    def test_a_failing_git_diff_call_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            real_run = catalog_mod.run

            def fake_run(argv, **kwargs):
                if argv[:2] == ["git", "diff"]:
                    return subprocess.CompletedProcess(argv, 128, "", "fatal: boom")
                return real_run(argv, **kwargs)

            with mock.patch.object(catalog_mod, "run", side_effect=fake_run):
                with self.assertRaises(CliError) as ctx:
                    catalog_mod.changed_paths_since(workspace, "HEAD")
            self.assertEqual(2, ctx.exception.code)

    def test_a_failing_ls_files_call_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            real_run = catalog_mod.run

            def fake_run(argv, **kwargs):
                if argv[:2] == ["git", "ls-files"]:
                    return subprocess.CompletedProcess(argv, 128, "", "fatal: boom")
                return real_run(argv, **kwargs)

            with mock.patch.object(catalog_mod, "run", side_effect=fake_run):
                with self.assertRaises(CliError) as ctx:
                    catalog_mod.changed_paths_since(workspace, "HEAD")
            self.assertEqual(2, ctx.exception.code)


class TestCatalogUncoveredMergeBaseFailure(unittest.TestCase):
    """WHEN `catalog uncovered --base` names an unresolvable ref (test-integrity group P3.5,
    mutant 222): exit 2 with "Cannot resolve merge-base", matching `catalog stale`'s own
    behavior for the same failure."""

    def test_uncovered_base_with_an_unresolvable_ref_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)

            result = run_formal(workspace, formal_home, "catalog", "uncovered", "--base", "nosuchref-typo")

            self.assertEqual(2, result.returncode)
            self.assertIn("Cannot resolve merge-base", result.stderr)


class TestCatalogUncoveredSpecialUntrackedFiles(unittest.TestCase):
    """WHEN an untracked path is not a regular file (test-integrity group P3.5, mutant 230): the
    regular-file guard in `_untracked_hunks` must keep excluding it, so a symlink to a
    non-regular target (e.g. `/dev/null`) is never reported -- and, by construction, never opened
    in a way that could hang on a FIFO either."""

    def test_an_untracked_symlink_to_dev_null_is_not_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            base_sha = init_git_repo(workspace)
            (workspace / "linked").symlink_to("/dev/null")

            result = run_formal(
                workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json", check=True
            )

            payload = json.loads(result.stdout)
            paths = {hunk["path"] for hunk in payload["hunks"]}
            self.assertNotIn("linked", paths)


class TestCatalogUncoveredTruncatedFile(unittest.TestCase):
    """WHEN a tracked file is truncated to 0 bytes (test-integrity group P3.5, mutant 259): the
    deletion-hunk clamp must still report a single-line range (`start: 1, end: 1`), never an
    out-of-range or zero value no real 1-based anchor could ever cover."""

    def test_a_file_truncated_to_zero_bytes_reports_a_single_line_deletion_hunk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "trunc.py").write_text("only line\n", encoding="utf-8")
            base_sha = commit_all(workspace, "add trunc.py")

            (workspace / "trunc.py").write_text("", encoding="utf-8")
            commit_all(workspace, "truncate to empty")

            result = run_formal(
                workspace, formal_home, "catalog", "uncovered", "--base", base_sha, "--json", check=True
            )

            payload = json.loads(result.stdout)
            deletion_hunks = [h for h in payload["hunks"] if h["path"] == "trunc.py" and h.get("deletion")]
            self.assertEqual(1, len(deletion_hunks))
            self.assertEqual(1, deletion_hunks[0]["start"])
            self.assertEqual(1, deletion_hunks[0]["end"])


if __name__ == "__main__":
    unittest.main()
