from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tests.formal_support import (
    CLI,
    CliError,
    commit_all,
    init_git_repo,
    manifest_mod,
    paths_mod,
    run_formal,
    util_mod,
    write_json,
)


class TestWorkspaceGuard(unittest.TestCase):
    """WHEN the resolved catalog root lives inside the current git workspace."""

    def test_when_state_root_is_inside_workspace_it_refuses_with_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            formal_home = workspace / ".formal-state"

            result = run_formal(workspace, formal_home, "status")

            self.assertEqual(2, result.returncode)
            self.assertIn("must stay outside the git workspace", result.stderr)
            self.assertFalse(formal_home.exists())


class TestRepoIdentity(unittest.TestCase):
    """WHEN a repo has multiple worktrees, the catalog is shared by common-dir identity."""

    def test_when_a_second_worktree_is_added_the_repo_dir_is_shared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            main_repo = Path(tmp) / "main"
            init_git_repo(main_repo)
            worktree = Path(tmp) / "wt1"
            subprocess.run(
                ["git", "worktree", "add", "-q", "-b", "wt1-branch", str(worktree)], cwd=main_repo, check=True
            )
            formal_home = Path(home_tmp)

            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout_main = paths_mod.Layout(paths_mod.workspace_root(str(main_repo)))
                layout_wt = paths_mod.Layout(paths_mod.workspace_root(str(worktree)))

            self.assertEqual(layout_main.repo_id, layout_wt.repo_id)
            self.assertEqual(layout_main.repo_dir, layout_wt.repo_dir)
            # `state_root()` resolves `AGENT_FORMAL_HOME` (`Path(...).resolve()`), so compare
            # against the same resolved form -- a raw tempdir can itself be a symlink (e.g.
            # macOS's `/var` -> `/private/var`) that only the resolved side follows.
            self.assertTrue(layout_main.repo_dir.is_relative_to(formal_home.resolve()))

    def test_colliding_branch_spellings_have_distinct_branch_storage_keys(self) -> None:
        workspace = Path("/unused")
        with mock.patch.object(paths_mod, "current_branch", return_value="feature/x"):
            slash_key = paths_mod.branch_slug(workspace)
        with mock.patch.object(paths_mod, "current_branch", return_value="feature__x"):
            underscore_key = paths_mod.branch_slug(workspace)

        self.assertNotEqual(slash_key, underscore_key)
        self.assertTrue(slash_key.startswith("branch-"))
        self.assertTrue(underscore_key.startswith("branch-"))

    def test_detached_storage_key_is_in_a_distinct_namespace_from_branch_keys(self) -> None:
        workspace = Path("/unused")
        with mock.patch.object(paths_mod, "current_branch", return_value="detached-deadbeef"):
            branch_key = paths_mod.branch_slug(workspace)
        with (
            mock.patch.object(paths_mod, "current_branch", return_value=None),
            mock.patch.object(paths_mod, "_git_text", return_value="deadbeef"),
        ):
            detached_key = paths_mod.branch_slug(workspace)

        self.assertTrue(branch_key.startswith("branch-"))
        self.assertTrue(detached_key.startswith("detached-"))
        self.assertNotEqual(branch_key, detached_key)


class TestLayoutIdentifierContainment(unittest.TestCase):
    """WHEN unit/version identifiers select catalog paths, invalid or escaping paths fail closed."""

    def _layout(self, workspace: Path, formal_home: Path):
        init_git_repo(workspace)
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            return paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

    def test_absolute_parent_and_separator_unit_identifiers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            root = Path(tmp)
            layout = self._layout(root / "workspace", Path(home_tmp))

            for invalid in (str(root / "outside"), "../outside", "nested/unit", r"nested\unit"):
                with self.subTest(identifier=invalid), self.assertRaises(CliError):
                    layout.work_dir(invalid)

    def test_invalid_version_identifiers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout = self._layout(Path(tmp) / "workspace", Path(home_tmp))

            for invalid in ("../version", "nested/version", str(Path(tmp) / "version")):
                with self.subTest(identifier=invalid), self.assertRaises(CliError):
                    layout.version_dir("unit", invalid)

    def test_an_existing_unit_symlink_cannot_escape_work_or_version_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            root = Path(tmp)
            layout = self._layout(root / "workspace", Path(home_tmp))
            outside = root / "outside"
            outside.mkdir()
            work_branch = layout.repo_dir / "work" / paths_mod.branch_slug(layout.workspace)
            work_branch.mkdir(parents=True)
            (work_branch / "unit").symlink_to(outside, target_is_directory=True)
            units = layout.repo_dir / "units"
            units.mkdir(parents=True)
            (units / "unit").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(CliError):
                layout.work_dir("unit")
            with self.assertRaises(CliError):
                layout.version_dir("unit", "abc123")

    def test_preexisting_repo_symlink_into_workspace_is_rejected_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "workspace"
            formal_home = Path(home_tmp)
            layout = self._layout(workspace, formal_home)
            escaped = workspace / "escaped-repo"
            escaped.mkdir()
            layout.repo_dir.symlink_to(escaped, target_is_directory=True)

            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}), self.assertRaises(CliError):
                paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

            self.assertEqual([], list(escaped.iterdir()))

    def test_preexisting_work_symlink_into_workspace_is_rejected_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "workspace"
            layout = self._layout(workspace, Path(home_tmp))
            escaped = workspace / "escaped-work"
            escaped.mkdir()
            layout.repo_dir.mkdir()
            (layout.repo_dir / "work").symlink_to(escaped, target_is_directory=True)

            with self.assertRaises(CliError):
                layout.work_dir("unit")

            self.assertEqual([], list(escaped.iterdir()))

    def test_preexisting_units_symlink_into_workspace_is_rejected_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "workspace"
            layout = self._layout(workspace, Path(home_tmp))
            escaped = workspace / "escaped-units"
            escaped.mkdir()
            layout.repo_dir.mkdir()
            (layout.repo_dir / "units").symlink_to(escaped, target_is_directory=True)

            with self.assertRaises(CliError):
                layout.version_dir("unit", "abc123")

            self.assertEqual([], list(escaped.iterdir()))

    def test_valid_unit_and_version_identifiers_keep_the_public_layout_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout = self._layout(Path(tmp) / "workspace", Path(home_tmp))

            work_dir = layout.work_dir("unit")
            version_dir = layout.version_dir("unit", "abc123")

            self.assertEqual("unit", work_dir.name)
            self.assertEqual(Path("units") / "unit" / "versions" / "abc123", version_dir.relative_to(layout.repo_dir))


class TestManifestExclusions(unittest.TestCase):
    """WHEN Lake build artifacts must not affect the unit hash or a saved version."""

    def test_lake_manifest_json_and_dot_lake_are_excluded_from_the_snapshot_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Model.lean").write_text("-- x\n", encoding="utf-8")
            entries_before = manifest_mod.unit_files_for_hash(unit_dir)

            (unit_dir / "lake-manifest.json").write_text("{}", encoding="utf-8")
            (unit_dir / ".lake" / "formal").mkdir(parents=True)
            (unit_dir / ".lake" / "formal" / "Axioms.lean").write_text("import Unit.Proofs\n", encoding="utf-8")
            entries_after = manifest_mod.unit_files_for_hash(unit_dir)

            self.assertEqual(entries_before, entries_after)

    def test_a_directory_symlink_is_rejected_before_a_unit_identity_is_produced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit_dir = root / "unit"
            target = root / "shared"
            unit_dir.mkdir()
            target.mkdir()
            (target / "Shared.lean").write_text("-- shared\n", encoding="utf-8")
            (unit_dir / "Shared").symlink_to(target, target_is_directory=True)

            with self.assertRaises(CliError) as ctx:
                manifest_mod.version_id_for_unit(unit_dir)

            self.assertIn("Symlinked directories", ctx.exception.message)


class TestVersionIdExcludesCheckoutRewrittenFields(unittest.TestCase):
    """WHEN two otherwise-identical unit dirs differ only in MANIFEST.json's `branch`/
    `source_commit` (the two fields `init_unit`/`checkout_version` overwrite on every
    init/checkout) (P4.3): `version_id_for_unit` must produce the same id for both, using the
    same normalization as `catalog.checkout_version`'s dirty guard."""

    def _unit_dir(self, tmp: Path, branch: str, source_commit: str) -> Path:
        unit_dir = tmp / branch
        unit_dir.mkdir()
        write_json(
            unit_dir / manifest_mod.MANIFEST_NAME,
            {"unit": "u", "tier": "F2", "branch": branch, "source_commit": source_commit},
        )
        (unit_dir / "Unit.lean").write_text("-- same content\n", encoding="utf-8")
        return unit_dir

    def test_identical_content_on_different_branches_and_commits_shares_a_version_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            unit_dir_a = self._unit_dir(tmp_path, "branch-a", "commit-a")
            unit_dir_b = self._unit_dir(tmp_path, "branch-b", "commit-b")

            self.assertEqual(manifest_mod.version_id_for_unit(unit_dir_a), manifest_mod.version_id_for_unit(unit_dir_b))

    def test_a_real_content_difference_still_changes_the_version_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            unit_dir_a = self._unit_dir(tmp_path, "branch-a", "commit-a")
            unit_dir_b = self._unit_dir(tmp_path, "branch-b", "commit-b")
            (unit_dir_b / "Unit.lean").write_text("-- different content\n", encoding="utf-8")

            self.assertNotEqual(
                manifest_mod.version_id_for_unit(unit_dir_a), manifest_mod.version_id_for_unit(unit_dir_b)
            )

    def test_manifest_digest_excluding_checkout_fields_drops_only_the_two_named_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / manifest_mod.MANIFEST_NAME
            write_json(path, {"unit": "u", "tier": "F2", "branch": "b1", "source_commit": "c1"})
            other_path = Path(tmp) / "other.json"
            write_json(other_path, {"unit": "u", "tier": "F2", "branch": "b2", "source_commit": "c2"})

            self.assertEqual(
                manifest_mod.manifest_digest_excluding_checkout_fields(path),
                manifest_mod.manifest_digest_excluding_checkout_fields(other_path),
            )


class TestManifestSnapshot(unittest.TestCase):
    """WHEN the snapshot id must invalidate on any repo change, tracked or not."""

    def test_when_an_untracked_file_changes_the_snapshot_id_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})
            (workspace / "untracked.txt").write_text("v1\n", encoding="utf-8")

            snapshot1 = manifest_mod.snapshot_id(workspace, unit_dir)
            (workspace / "untracked.txt").write_text("v2\n", encoding="utf-8")
            snapshot2 = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertNotEqual(snapshot1, snapshot2)

    def test_distinct_untracked_file_records_cannot_share_a_snapshot_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            init_git_repo(workspace)
            unit_dir = root / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})
            (workspace / "a").write_bytes(b"X\0b\0Y")
            one_file_snapshot = manifest_mod.snapshot_id(workspace, unit_dir)
            (workspace / "a").write_bytes(b"X")
            (workspace / "b").write_bytes(b"Y")

            two_file_snapshot = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertNotEqual(one_file_snapshot, two_file_snapshot)

    def test_when_nothing_changes_the_snapshot_id_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})

            self.assertEqual(
                manifest_mod.snapshot_id(workspace, unit_dir), manifest_mod.snapshot_id(workspace, unit_dir)
            )

    def test_when_diff_external_is_configured_the_snapshot_id_still_changes_on_edit(self) -> None:
        """Q4.3: a repo-local `diff.external` command substitutes its own (here, constant)
        output for git's real diff text unless `--no-ext-diff` suppresses it. Comparing a
        pre-edit snapshot against a post-edit one (as the previous version of this test did) is
        vacuous: an empty (no working-tree changes yet) diff always differs from a non-empty one
        -- constant or real -- regardless of whether `--no-ext-diff` actually works, so that
        comparison alone can never catch a missing flag. Editing twice and comparing the two
        *post-edit* snapshots is the real test: with the flag missing, `diff.external`'s constant
        output would make both edits look identical to `snapshot_id`, and it would incorrectly
        stay the same across the second edit below."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            (workspace / "tracked.txt").write_text("v1\n", encoding="utf-8")
            commit_all(workspace, "add tracked.txt")
            ext_diff = Path(tmp) / "ext-diff.sh"
            ext_diff.write_text("#!/bin/sh\necho CONSTANT-DIFF-OUTPUT\n", encoding="utf-8")
            ext_diff.chmod(0o755)
            subprocess.run(["git", "config", "diff.external", str(ext_diff)], cwd=workspace, check=True)
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})

            (workspace / "tracked.txt").write_text("v2\n", encoding="utf-8")
            snapshot2 = manifest_mod.snapshot_id(workspace, unit_dir)
            (workspace / "tracked.txt").write_text("v3\n", encoding="utf-8")
            snapshot3 = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertNotEqual(snapshot2, snapshot3)

    def test_when_a_textconv_driver_is_configured_the_snapshot_id_still_changes_on_a_second_edit(self) -> None:
        """A repo-local `diff.<driver>.textconv` (wired via `.git/info/attributes`) substitutes
        its own (here, constant) rendering of *both* sides of the diff for a matched path unless
        `--no-textconv` suppresses it -- with the flag missing, git reports no difference at all
        for that path (both the committed and working-tree content render to the same constant),
        so two different post-edit snapshots would incorrectly collide."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            (workspace / "tracked.txt").write_text("v1\n", encoding="utf-8")
            commit_all(workspace, "add tracked.txt")
            (workspace / ".git" / "info").mkdir(parents=True, exist_ok=True)
            (workspace / ".git" / "info" / "attributes").write_text("tracked.txt diff=mydrv\n", encoding="utf-8")
            textconv = Path(tmp) / "textconv.sh"
            textconv.write_text("#!/bin/sh\necho CONSTANT-TEXTCONV-OUTPUT\n", encoding="utf-8")
            textconv.chmod(0o755)
            subprocess.run(["git", "config", "diff.mydrv.textconv", str(textconv)], cwd=workspace, check=True)
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})

            (workspace / "tracked.txt").write_text("v2\n", encoding="utf-8")
            snapshot2 = manifest_mod.snapshot_id(workspace, unit_dir)
            (workspace / "tracked.txt").write_text("v3\n", encoding="utf-8")
            snapshot3 = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertNotEqual(snapshot2, snapshot3)


class TestManifestSnapshotFailClosed(unittest.TestCase):
    """WHEN the git plumbing `snapshot_id` depends on cannot run at all (F6): fail closed
    (exit 2), never silently compute a snapshot as if nothing had changed."""

    def test_when_git_diff_fails_snapshot_id_raises_instead_of_reading_no_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})

            with mock.patch.object(
                manifest_mod,
                "run_raw",
                return_value=subprocess.CompletedProcess(["git", "diff"], 128, b"", b"fatal: boom"),
            ):
                with self.assertRaises(CliError) as ctx:
                    manifest_mod.snapshot_id(workspace, unit_dir)
            self.assertEqual(2, ctx.exception.code)

    def test_when_an_untracked_file_has_non_utf8_bytes_snapshot_id_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            (workspace / "l.py").write_bytes(b"caf\xe9 = 1\n")
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})

            snapshot = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertTrue(snapshot)


class TestSnapshotIdOnUnbornHead(unittest.TestCase):
    """WHEN the workspace has no commits yet (an unborn `HEAD`) (V3.1, repro
    `/tmp/converge-refute-r6-env/ws-unborn`): `git diff HEAD` exits 128, so `snapshot_id` must
    fall back to diffing against the empty tree (`_diff_target`) instead of raising a misleading
    "incomplete diff" `CliError`."""

    def _unborn_workspace(self, tmp: Path) -> Path:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
        return workspace

    def test_snapshot_id_does_not_raise_with_no_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._unborn_workspace(tmp)
            (workspace / "untracked.txt").write_text("v1\n", encoding="utf-8")
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})

            snapshot = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertTrue(snapshot)

    def test_snapshot_id_changes_when_a_file_changes_with_no_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._unborn_workspace(tmp)
            (workspace / "untracked.txt").write_text("v1\n", encoding="utf-8")
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})

            snapshot1 = manifest_mod.snapshot_id(workspace, unit_dir)
            (workspace / "untracked.txt").write_text("v2\n", encoding="utf-8")
            snapshot2 = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertNotEqual(snapshot1, snapshot2)

    def test_diff_target_returns_head_when_head_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)

            self.assertEqual("HEAD", manifest_mod._diff_target(workspace))

    def test_diff_target_falls_back_to_the_empty_tree_with_no_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._unborn_workspace(tmp)

            target = manifest_mod._diff_target(workspace)

            self.assertNotEqual("HEAD", target)
            expected = subprocess.run(
                ["git", "hash-object", "-t", "tree", "/dev/null"],
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(expected, target)

    def test_diff_target_fails_closed_when_the_empty_tree_fallback_also_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._unborn_workspace(tmp)
            head_unresolved = subprocess.CompletedProcess(["git", "rev-parse"], 1, b"", b"")
            hash_object_failure = subprocess.CompletedProcess(["git", "hash-object"], 127, b"", b"no git")

            with mock.patch.object(manifest_mod, "run_raw", side_effect=[head_unresolved, hash_object_failure]):
                with self.assertRaises(CliError) as ctx:
                    manifest_mod._diff_target(workspace)
            self.assertEqual(2, ctx.exception.code)


class TestCopytreeIgnoreTopLevelOnly(unittest.TestCase):
    """WHEN a saved version is copied (F16): the exclusion must apply at the same depth as the
    unit hash (`EXCLUDED_DIRS` top-level only), never at every recursion depth."""

    def test_a_nested_dir_sharing_an_excluded_name_is_kept_but_the_top_level_one_is_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp) / "unit"
            (unit_dir / "tmp").mkdir(parents=True)
            (unit_dir / "tmp" / "scratch.txt").write_text("drop me\n", encoding="utf-8")
            (unit_dir / "Unit" / "tmp").mkdir(parents=True)
            (unit_dir / "Unit" / "tmp" / "keep.lean").write_text("-- real content\n", encoding="utf-8")
            dest = Path(tmp) / "dest"

            shutil.copytree(unit_dir, dest, ignore=manifest_mod.copytree_ignore(unit_dir))

            self.assertFalse((dest / "tmp").exists())
            self.assertTrue((dest / "Unit" / "tmp" / "keep.lean").exists())
            # Matches `unit_files_for_hash`'s own top-level-only exclusion exactly.
            hashed = {rel for rel, _ in manifest_mod.unit_files_for_hash(unit_dir)}
            self.assertIn(str(Path("Unit") / "tmp" / "keep.lean"), hashed)
            self.assertNotIn(str(Path("tmp") / "scratch.txt"), hashed)


class TestManifestSnapshotIdRunRawOrderedFailures(unittest.TestCase):
    """WHEN `snapshot_id`'s two sequential git-plumbing calls (diff, then ls-files) can each
    fail independently: either order of [ok, failing] must still raise (test-integrity group
    "git plumbing fails closed", the `manifest.py` half not already covered by
    `TestManifestSnapshotFailClosed`)."""

    def test_diff_ok_then_ls_files_failing_still_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})
            # `snapshot_id` now issues `git rev-parse --verify -q HEAD` (via `_diff_target`)
            # before the diff itself; `init_git_repo` commits, so that resolves ok.
            rev_parse_ok = subprocess.CompletedProcess(["git", "rev-parse"], 0, b"", b"")
            ok = subprocess.CompletedProcess(["git", "diff"], 0, b"", b"")
            ls_files_failure = subprocess.CompletedProcess(["git", "ls-files"], 128, b"", b"fatal: boom")

            with mock.patch.object(manifest_mod, "run_raw", side_effect=[rev_parse_ok, ok, ls_files_failure]):
                with self.assertRaises(CliError) as ctx:
                    manifest_mod.snapshot_id(workspace, unit_dir)
            self.assertEqual(2, ctx.exception.code)

    def test_diff_failing_first_raises_before_ls_files_is_even_reached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})
            # First call is `_diff_target`'s HEAD-resolution check (ok, `init_git_repo` commits);
            # the second is the diff itself, which fails and must raise before ls-files (a third
            # call) is ever reached.
            rev_parse_ok = subprocess.CompletedProcess(["git", "rev-parse"], 0, b"", b"")
            diff_failure = subprocess.CompletedProcess(["git", "diff"], 128, b"", b"fatal: boom")

            with mock.patch.object(manifest_mod, "run_raw", side_effect=[rev_parse_ok, diff_failure]) as run_raw_mock:
                with self.assertRaises(CliError) as ctx:
                    manifest_mod.snapshot_id(workspace, unit_dir)
            self.assertEqual(2, ctx.exception.code)
            self.assertEqual(2, run_raw_mock.call_count)


class TestFormalLibDirAssetResolution(unittest.TestCase):
    """WHEN `FORMAL_LIB_DIR` points somewhere with no `lean/FormalKit` kit source: `init` must
    fail closed (exit 2, naming what is missing), never silently fall back to the real deployed
    kit (test-integrity group "lib dir / asset resolution")."""

    def test_an_empty_formal_lib_dir_makes_init_exit_2_naming_the_missing_kit(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            tempfile.TemporaryDirectory() as home_tmp,
            tempfile.TemporaryDirectory() as lib_tmp,
        ):
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            env = {
                **os.environ,
                "AGENT_FORMAL_HOME": str(formal_home),
                "FORMAL_LIB_DIR": str(lib_tmp),
            }

            result = subprocess.run(
                [sys.executable, str(CLI), "init", "u"],
                cwd=workspace,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            self.assertIn("not found", result.stderr)

    def test_lib_dir_honors_the_explicit_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as lib_tmp:
            with mock.patch.dict(os.environ, {"FORMAL_LIB_DIR": lib_tmp}):
                self.assertEqual(Path(lib_tmp).resolve(), paths_mod.lib_dir())


class TestInitGuardsAndFromVersion(unittest.TestCase):
    """WHEN a unit's work dir already exists and is non-empty (re-init refuses), and when
    `--from-version` restores a saved unit's anchors, or names a version that was never saved
    (test-integrity group "init guards / --from-version")."""

    def test_reinitializing_a_non_empty_work_dir_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            result = run_formal(workspace, formal_home, "init", "u", "--design")

            self.assertEqual(2, result.returncode)
            self.assertIn("already exists", result.stderr)

    def test_init_with_an_absolute_unit_identifier_refuses_without_creating_that_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            outside = root / "outside-unit"
            init_git_repo(workspace)

            result = run_formal(workspace, Path(home_tmp), "init", str(outside), "--design")

            self.assertEqual(2, result.returncode)
            self.assertIn("Invalid unit identifier", result.stderr)
            self.assertFalse(outside.exists())

    def test_from_version_with_a_bogus_id_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)

            result = run_formal(workspace, formal_home, "init", "u", "--from-version", "no-such-version")

            self.assertEqual(2, result.returncode)
            self.assertIn("No saved version", result.stderr)

    def test_from_version_restores_the_saved_anchors_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "u1.py").write_text("def u1():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add u1.py")
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u1", "u1.py:1-2", "--id", "A1", check=True)
            saved = run_formal(
                workspace, formal_home, "catalog", "save", "u1", "--allow-unverified", "--json", check=True
            )
            version_id = json.loads(saved.stdout)["id"]
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            shutil.rmtree(layout.work_dir("u1"))

            run_formal(workspace, formal_home, "init", "u1", "--from-version", version_id, check=True)

            restored = manifest_mod.load_anchors(layout.work_dir("u1"))
            self.assertEqual(["A1"], [a["id"] for a in restored])


class TestInitKeepsTemplateManifestBudgets(unittest.TestCase):
    """WHEN a unit is initialized from the template: the template's own MANIFEST.json budgets
    survive `init_unit`'s `setdefault`, not the hardcoded fallback (test-integrity group "init
    keeps template manifest")."""

    def test_max_states_after_init_is_the_templates_200000_not_the_hardcoded_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

            manifest = manifest_mod.load_manifest(layout.work_dir("u"))

            self.assertEqual(200000, manifest["budgets"]["max_states"])


class TestSnapshotIdCoversGitignoredAnchoredAndAdapterFiles(unittest.TestCase):
    """WHEN an anchored file or the adapter script is gitignored: `snapshot_id` must still
    notice a content edit to it (via `_extra_snapshot_entries`, not the git diff/untracked
    halves), and a missing anchored file must never crash it (test-integrity group "gitignored
    anchored/adapter files in snapshot")."""

    def test_editing_a_gitignored_anchored_file_changes_the_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            (workspace / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
            commit_all(workspace, "add gitignore")
            (workspace / "ignored.py").write_text("v1\n", encoding="utf-8")
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})
            write_json(
                unit_dir / manifest_mod.ANCHORS_NAME,
                {"anchors": [{"id": "A1", "path": "ignored.py", "start": 1, "end": 1, "snippet": "v1"}]},
            )

            snapshot1 = manifest_mod.snapshot_id(workspace, unit_dir)
            (workspace / "ignored.py").write_text("v2\n", encoding="utf-8")
            snapshot2 = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertNotEqual(snapshot1, snapshot2)

    def test_editing_a_gitignored_adapter_script_changes_the_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            (workspace / ".gitignore").write_text("adapter.py\n", encoding="utf-8")
            commit_all(workspace, "add gitignore")
            (workspace / "adapter.py").write_text("v1\n", encoding="utf-8")
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(
                unit_dir / manifest_mod.MANIFEST_NAME,
                {"unit": "u", "tier": "F2", "adapter": {"cmd": "python3 adapter.py", "cwd": "repo"}},
            )

            snapshot1 = manifest_mod.snapshot_id(workspace, unit_dir)
            (workspace / "adapter.py").write_text("v2\n", encoding="utf-8")
            snapshot2 = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertNotEqual(snapshot1, snapshot2)

    def test_a_missing_anchored_file_does_not_crash_snapshot_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            init_git_repo(workspace)
            unit_dir = Path(tmp) / "unit"
            unit_dir.mkdir()
            write_json(unit_dir / manifest_mod.MANIFEST_NAME, {"unit": "u", "tier": "F2"})
            write_json(
                unit_dir / manifest_mod.ANCHORS_NAME,
                {"anchors": [{"id": "A1", "path": "does-not-exist.py", "start": 1, "end": 1, "snippet": "x"}]},
            )

            snapshot = manifest_mod.snapshot_id(workspace, unit_dir)

            self.assertTrue(snapshot)


class TestStateRootPrecedence(unittest.TestCase):
    """WHEN resolving the catalog state root: `AGENT_FORMAL_HOME` > `XDG_STATE_HOME/agent-formal`
    > `~/.local/state/agent-formal` (test-integrity group "state-root precedence")."""

    def test_xdg_state_home_is_used_when_agent_formal_home_is_unset(self) -> None:
        with tempfile.TemporaryDirectory() as xdg_tmp:
            env = dict(os.environ)
            env.pop("AGENT_FORMAL_HOME", None)
            env["XDG_STATE_HOME"] = xdg_tmp
            with mock.patch.dict(os.environ, env, clear=True):
                # `state_root()` resolves this branch too (a raw tempdir can itself be a symlink,
                # e.g. macOS's `/var` -> `/private/var`), so compare against the resolved form.
                self.assertEqual((Path(xdg_tmp) / "agent-formal").resolve(), paths_mod.state_root())

    def test_a_relative_agent_formal_home_still_yields_an_absolute_kit_path_lakefile(self) -> None:
        """A relative `AGENT_FORMAL_HOME` must not survive into `init_unit`'s written
        `KIT_PATH` (`lakefile.toml`'s `[[require]] path`): `lake build` later resolves that path
        against the *unit dir* it runs in (`build.lake_build`'s `cwd=unit_dir`), not whatever
        directory was current when the relative value was first read at `init` time (U3.3,
        mock-level: no real `lake`/Lean invocation)."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            workspace = base / "ws"
            init_git_repo(workspace)
            relative_state_name = "relative-formal-state"

            cwd_before = Path.cwd()
            os.chdir(base)
            try:
                with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": relative_state_name}):
                    layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
                    unit_dir = manifest_mod.init_unit(layout, "u", "F2", True, None)
            finally:
                os.chdir(cwd_before)

            self.assertTrue(layout.root.is_absolute(), layout.root)
            lakefile = (unit_dir / "lakefile.toml").read_text(encoding="utf-8")
            kit_path_str = lakefile.split('path = "', 1)[1].split('"', 1)[0]
            kit_path = Path(kit_path_str)
            self.assertTrue(kit_path.is_absolute(), lakefile)
            manifest = manifest_mod.load_manifest(unit_dir)
            self.assertEqual(layout.kit_dir(manifest["kit_hash"]), kit_path)
            # `lake build` runs with cwd=unit_dir: resolving the baked path against that same
            # directory (not against `base`, the directory that was current at `init` time) must
            # still land on the real on-disk kit copy -- this is "build finds the kit".
            self.assertTrue((unit_dir / kit_path).resolve().is_dir())

    def test_falls_back_to_dot_local_state_when_neither_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as home_tmp:
            env = dict(os.environ)
            env.pop("AGENT_FORMAL_HOME", None)
            env.pop("XDG_STATE_HOME", None)
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch("pathlib.Path.home", return_value=Path(home_tmp)):
                    self.assertEqual(Path(home_tmp) / ".local" / "state" / "agent-formal", paths_mod.state_root())


class TestWorkspaceAndRepoResolution(unittest.TestCase):
    """WHEN resolving the workspace root, the git common-dir identity, an unborn HEAD's commit,
    and the state-root guard's `$HOME` exemption (test-integrity group "workspace/repo
    resolution")."""

    def test_a_non_git_directory_raises_not_a_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CliError) as ctx:
                paths_mod.git_common_dir(Path(tmp))
            self.assertEqual(2, ctx.exception.code)
            self.assertIn("Not a git repository", ctx.exception.message)

    def test_a_subdirectory_resolves_to_the_repo_toplevel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            subdir = workspace / "a" / "b"
            subdir.mkdir(parents=True)

            self.assertEqual(workspace.resolve(), paths_mod.workspace_root(str(subdir)))

    def test_an_unborn_head_reports_no_commit_as_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            workspace.mkdir(exist_ok=True)
            subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)

            self.assertIsNone(paths_mod.head_commit(workspace))

    def test_the_home_directory_workspace_is_exempt_from_the_outside_workspace_guard(self) -> None:
        with tempfile.TemporaryDirectory() as home_tmp:
            home_path = Path(home_tmp)
            env = dict(os.environ)
            env.pop("AGENT_FORMAL_HOME", None)
            env.pop("XDG_STATE_HOME", None)
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch("pathlib.Path.home", return_value=home_path):
                    # No CliError even though the default state root nests under this exact
                    # workspace -- the $HOME fallback-workspace exemption.
                    paths_mod.guard_state_root_outside_workspace(paths_mod.state_root(), home_path)


class TestUtilTimeouts(unittest.TestCase):
    """WHEN a subprocess exceeds its timeout, each helper preserves its output contract and
    stops descendants before returning."""

    def test_run_on_a_slow_command_returns_124_with_str_output_and_a_timed_out_message(self) -> None:
        result = util_mod.run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)

        self.assertEqual(124, result.returncode)
        self.assertIsInstance(result.stdout, str)
        self.assertIsInstance(result.stderr, str)
        self.assertIn("timed out", result.stderr)

    def test_run_shell_on_a_slow_command_returns_124_with_str_output_and_a_timed_out_message(self) -> None:
        result = util_mod.run_shell(f"{sys.executable} -c 'import time; time.sleep(5)'", timeout=0.2)

        self.assertEqual(124, result.returncode)
        self.assertIsInstance(result.stdout, str)
        self.assertIsInstance(result.stderr, str)
        self.assertIn("timed out", result.stderr)

    def test_every_timeout_helper_stops_descendants_before_they_can_continue_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinels = [root / name for name in ("run", "shell", "raw")]

            def parent_code(sentinel: Path) -> str:
                child = (
                    f"import time; from pathlib import Path; time.sleep(1); Path({str(sentinel)!r}).write_text('alive')"
                )
                return f"import subprocess, sys; subprocess.run([sys.executable, '-c', {child!r}], check=False)"

            commands = (
                lambda: util_mod.run([sys.executable, "-c", parent_code(sentinels[0])], timeout=0.2),
                lambda: util_mod.run_shell(
                    f"{shlex.quote(sys.executable)} -c {shlex.quote(parent_code(sentinels[1]))}; :",
                    timeout=0.2,
                ),
                lambda: util_mod.run_raw([sys.executable, "-c", parent_code(sentinels[2])], timeout=0.2),
            )

            results = [command() for command in commands]
            time.sleep(1.1)

            self.assertEqual([124, 124, 124], [result.returncode for result in results])
            self.assertFalse(any(sentinel.exists() for sentinel in sentinels))

    def test_run_raw_on_a_slow_command_returns_124_with_bytes_output_and_a_timed_out_message(self) -> None:
        result = util_mod.run_raw([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)

        self.assertEqual(124, result.returncode)
        self.assertIsInstance(result.stdout, bytes)
        self.assertIsInstance(result.stderr, bytes)
        self.assertIn(b"timed out", result.stderr)


if __name__ == "__main__":
    unittest.main()
