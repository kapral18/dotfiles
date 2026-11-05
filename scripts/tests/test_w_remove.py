#!/usr/bin/env python3
"""Regression tests for ,w remove.

Detached cases lock the bash TSV parse that used to collapse an empty
branch_ref field and the preflight path that hardcoded detached=0. Main
worktree cases lock that a non-bare clone's main checkout is never deleted:
git refuses to remove it, and the rm -rf fallback used to delete it anyway.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _test_support import install_fake_herdr

REPO = Path(__file__).resolve().parents[2]
REMOVE_SRC = REPO / "home/exact_lib/exact_,w/remove.sh"
SHARED_SRC = REPO / "home/exact_lib/exact_shared"


class _WRemoveCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.lib = self.root / "lib"
        self.w_dir = self.lib / ",w"
        self.shared = self.lib / "shared"
        self.w_dir.mkdir(parents=True)
        self.shared.mkdir(parents=True)
        shutil.copy2(REMOVE_SRC, self.w_dir / "remove.sh")
        for name in ("bash_utils_lib.sh", "worktree_lib.sh", "worktree_nested_git.py"):
            shutil.copy2(SHARED_SRC / name, self.shared / name)
        self.remove_sh = self.w_dir / "remove.sh"
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        install_fake_herdr(self.bin_dir)

        self.main = self.root / "main"
        self.detached = self.root / "detached"
        self.main.mkdir()
        self.git(self.main, "init", "-q")
        self.git(self.main, "config", "user.name", "W Remove Test")
        self.git(self.main, "config", "user.email", "w-remove-test@example.invalid")
        self.git(self.main, "config", "commit.gpgsign", "false")
        (self.main / "README").write_text("base\n", encoding="utf-8")
        self.git(self.main, "add", "README")
        self.git(self.main, "commit", "-qm", "base")
        (self.main / "README").write_text("base\nnext\n", encoding="utf-8")
        self.git(self.main, "add", "README")
        self.git(self.main, "commit", "-qm", "next")
        self.git(self.main, "worktree", "add", "--detach", str(self.detached), "HEAD~1")

    def git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "HOME": str(self.root / "home"),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_AUTHOR_NAME": "W Remove Test",
                "GIT_AUTHOR_EMAIL": "w-remove-test@example.invalid",
                "GIT_COMMITTER_NAME": "W Remove Test",
                "GIT_COMMITTER_EMAIL": "w-remove-test@example.invalid",
            },
            timeout=5,
        )

    def run_remove(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self.run_remove_in(self.main, *args)

    def run_remove_in(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(self.root / "home")
        Path(env["HOME"]).mkdir(exist_ok=True)
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_SYSTEM"] = os.devnull
        for key in [k for k in env if k.startswith("HERDR_")]:
            env.pop(key)
        env["PATH"] = f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}"
        return subprocess.run(
            ["bash", str(self.remove_sh), *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            env=env,
            timeout=10,
        )


class WRemoveDetachedTests(_WRemoveCase):
    """WHEN ,w remove --paths targets a detached HEAD worktree."""

    def test_preflight_does_not_flag_clean_detached_worktree(self) -> None:
        result = self.run_remove("--paths", str(self.detached), "--preflight")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_paths_removes_detached_worktree(self) -> None:
        result = self.run_remove("--paths", str(self.detached))
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertFalse(self.detached.exists(), "detached worktree directory should be gone")
        listed = self.git(self.main, "worktree", "list", "--porcelain").stdout
        self.assertNotIn(str(self.detached), listed)


class WRemoveMainWorktreeTests(_WRemoveCase):
    """WHEN the main checkout of a non-bare clone is on a non-default branch."""

    def setUp(self) -> None:
        super().setUp()
        self.git(self.main, "switch", "-q", "-c", "feature")
        fzf = self.bin_dir / "fzf"
        fzf.write_text("#!/bin/sh\ncat\n")
        fzf.chmod(0o755)

    def assert_main_intact(self) -> None:
        self.assertTrue((self.main / ".git").is_dir(), "main checkout must survive")
        self.assertTrue((self.main / "README").is_file())

    def test_paths_mode_skips_main_worktree(self) -> None:
        self.run_remove("--force", "--paths", str(self.main))
        self.assert_main_intact()

    def test_interactive_mode_never_offers_main_worktree(self) -> None:
        self.git(self.main, "worktree", "add", "-q", "-b", "other", str(self.root / "other"))
        result = self.run_remove("--force")
        self.assert_main_intact()
        self.assertFalse((self.root / "other").exists(), result.stdout + result.stderr)


class WRemoveSeparateGitDirTests(_WRemoveCase):
    """WHEN the main worktree's git dir lives outside the checkout."""

    def test_paths_mode_skips_separate_git_dir(self) -> None:
        checkout = self.root / "sep"
        gitdir = self.root / "sep.git"
        self.git(self.root, "clone", "-q", "--separate-git-dir", str(gitdir), str(self.main), str(checkout))
        self.git(checkout, "switch", "-q", "-c", "feature")
        main_entry = self.git(checkout, "worktree", "list", "--porcelain").stdout.splitlines()[0].split(" ", 1)[1]
        self.run_remove_in(checkout, "--force", "--paths", main_entry)
        self.assertTrue((gitdir / "HEAD").is_file(), "separate git dir must survive")
        self.assertTrue((checkout / "README").is_file())


class WRemoveUnsavedCommitTests(_WRemoveCase):
    def test_detached_unique_commit_survives_until_force(self) -> None:
        self.git(self.detached, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "detached-only")
        commit = self.git(self.detached, "rev-parse", "HEAD").stdout.strip()

        preflight = self.run_remove("--preflight", "--paths", str(self.detached))
        self.assertEqual(preflight.stdout.strip(), str(self.detached))
        self.run_remove("--paths", str(self.detached))
        self.assertTrue(self.detached.exists())
        self.assertEqual(self.git(self.detached, "rev-parse", "HEAD").stdout.strip(), commit)
        forced = self.run_remove("--force", "--paths", str(self.detached))
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertFalse(self.detached.exists())

    def test_branch_without_remote_keeps_unique_commit_and_allows_retained_commits(self) -> None:
        checkout = self.root / "feature"
        self.git(self.main, "worktree", "add", "-q", "-b", "feature", str(checkout))
        self.git(checkout, "commit", "--allow-empty", "-qm", "feature-only")
        self.run_remove("--paths", str(checkout))
        self.assertTrue(checkout.exists())
        self.git(self.main, "tag", "saved-feature", "feature")

        result = self.run_remove("--paths", str(checkout))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(checkout.exists())
        self.git(self.main, "rev-parse", "saved-feature")

    def test_root_preflight_preserves_stashes_and_notes_until_published(self) -> None:
        for kind, ref in (("stash", "refs/stash"), ("notes", "refs/notes/commits")):
            with self.subTest(kind=kind):
                checkout = self.root / f"root-{kind}"
                self.git(self.root, "clone", "-q", str(self.main), str(checkout))
                published = self.git(checkout, "rev-parse", "HEAD").stdout.strip()
                clean = self.run_remove_in(checkout, "--preflight", "--paths", str(checkout))
                self.assertEqual(clean.returncode, 0, clean.stderr)
                self.assertEqual(clean.stdout.strip(), "")
                if kind == "stash":
                    (checkout / "README").write_text("private stashed work\n")
                    self.git(checkout, "stash", "push", "-qm", "private work")
                else:
                    self.git(checkout, "notes", "add", "-m", "private note", "HEAD")
                unique = self.git(checkout, "rev-parse", ref).stdout.strip()
                self.assertEqual(self.git(checkout, "status", "--porcelain").stdout.strip(), "")
                self.assertEqual(self.git(checkout, "rev-parse", "HEAD").stdout.strip(), published)

                unsafe = self.run_remove_in(checkout, "--preflight", "--paths", str(checkout))

                self.assertEqual(unsafe.returncode, 0, unsafe.stderr)
                self.assertEqual(unsafe.stdout.strip(), str(checkout))
                self.assertEqual(self.git(checkout, "cat-file", "-t", unique).stdout.strip(), "commit")
                self.git(checkout, "update-ref", "refs/remotes/origin/saved", unique)
                saved = self.run_remove_in(checkout, "--preflight", "--paths", str(checkout))
                self.assertEqual(saved.returncode, 0, saved.stderr)
                self.assertEqual(saved.stdout.strip(), "")

    def test_missing_and_nested_paths_fail_preflight(self) -> None:
        nested = self.detached / "subdir"
        nested.mkdir()
        missing = self.root / "missing worktree"

        result = self.run_remove("--preflight", "--paths", str(missing), str(nested))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(missing), str(nested)])

    def test_external_worktree_removal_does_not_bag_its_ancestors(self) -> None:
        external_parent = self.root / "outside"
        external_parent.mkdir()
        notes = external_parent / "notes.txt"
        notes.write_text("keep here\n")
        wrapper = self.root / "repo"
        wrapper.mkdir()
        main = wrapper / "main"
        self.git(self.root, "clone", "-q", str(self.main), str(main))
        checkout = external_parent / "linked"
        self.git(main, "worktree", "add", "-q", "-b", "external", str(checkout))

        result = self.run_remove_in(main, "--paths", str(checkout))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(checkout.exists())
        self.assertEqual(notes.read_text(), "keep here\n")

    def test_newline_leftover_keeps_invoking_checkout_file_in_place(self) -> None:
        wrapper = self.root / "newline-wrapper"
        wrapper.mkdir()
        main = wrapper / "main"
        self.git(self.root, "clone", "-q", str(self.main), str(main))
        checkout = wrapper / "feature/selected"
        self.git(main, "worktree", "add", "-q", "-b", "selected", str(checkout))
        original = (main / "README").read_bytes()
        filenames = ("note\nREADME", ".DS_Store\n")
        for filename in filenames:
            (checkout.parent / filename).write_text("preserve exact filename")
        (checkout.parent / ".DS_Store").write_text("ignorable metadata")

        result = self.run_remove_in(main, "--force", "--paths", str(checkout))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(checkout.exists())
        self.assertTrue((main / "README").exists(), "archive cleanup must not move a relative CWD fragment")
        self.assertEqual((main / "README").read_bytes(), original)
        bag = self.root / ".bag/worktree_remove/newline-wrapper"
        for filename in filenames:
            archived = list(bag.rglob(filename))
            self.assertEqual([path.read_text() for path in archived], ["preserve exact filename"])
        self.assertEqual(list(bag.rglob(".DS_Store")), [])

    def test_repeated_removal_preserves_both_archived_payloads(self) -> None:
        wrapper = self.root / "wrapper"
        wrapper.mkdir()
        main = wrapper / "main"
        self.git(self.root, "clone", "-q", str(self.main), str(main))
        checkout = wrapper / "feature/selected"
        date = self.bin_dir / "date"
        date.write_text("#!/bin/sh\nprintf '20261103-120000\\n'\n")
        date.chmod(0o755)

        for payload in ("first saved payload", "second payload"):
            self.git(main, "worktree", "add", "-q", "-b", "selected", str(checkout))
            (checkout.parent / "note.txt").write_text(payload)

            result = self.run_remove_in(main, "--force", "--paths", str(checkout))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(checkout.exists())
            self.assertTrue((main / ".git").exists())

        archived = self.root / ".bag/worktree_remove/wrapper"
        self.assertEqual(
            sorted(path.read_text() for path in archived.rglob("note.txt")),
            ["first saved payload", "second payload"],
        )

    def test_removing_nested_worktree_keeps_deeply_nested_sibling_in_place(self) -> None:
        wrapper = self.root / "wrapper"
        wrapper.mkdir()
        main = wrapper / "main"
        self.git(self.root, "clone", "-q", str(self.main), str(main))
        checkout = wrapper / "feature/selected"
        sibling = wrapper / "feature/one/two/three/four/five/six/seven/retained"
        self.git(main, "worktree", "add", "-q", "-b", "selected", str(checkout))
        self.git(main, "worktree", "add", "-q", "-b", "retained", str(sibling))
        (sibling / "README").write_text("keep nested checkout\n")

        result = self.run_remove_in(main, "--paths", str(checkout))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(checkout.exists())
        self.assertTrue((sibling / ".git").is_file())
        self.assertEqual((sibling / "README").read_text(), "keep nested checkout\n")
        listed = self.git(main, "worktree", "list", "--porcelain").stdout.splitlines()
        self.assertIn(f"worktree {sibling.resolve()}", listed)
        self.assertNotIn(f"worktree {checkout.resolve()}", listed)

    @unittest.skipIf(os.geteuid() == 0, "root can inspect permission-restricted directories")
    def test_parent_scan_failure_keeps_uninspected_content_in_place(self) -> None:
        wrapper = self.root / "wrapper"
        wrapper.mkdir()
        main = wrapper / "main"
        self.git(self.root, "clone", "-q", str(self.main), str(main))
        checkout = wrapper / "feature/selected"
        self.git(main, "worktree", "add", "-q", "-b", "selected", str(checkout))
        unreadable = checkout.parent / "unreadable"
        unreadable.mkdir()
        (unreadable / "notes").write_text("keep uninspected content\n")
        notes = checkout.parent / "keep.txt"
        notes.write_text("keep inspected content\n")
        unreadable.chmod(0)
        try:
            result = self.run_remove_in(main, "--paths", str(checkout))
        finally:
            for path in [unreadable, *self.root.glob(".bag/worktree_remove/wrapper/*/feature/unreadable")]:
                if path.exists():
                    path.chmod(0o700)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(checkout.exists())
        self.assertEqual((unreadable / "notes").read_text(), "keep uninspected content\n")
        self.assertEqual(notes.read_text(), "keep inspected content\n")
        self.assertFalse((self.root / ".bag").exists())


class WRemoveSubmoduleHistoryTests(_WRemoveCase):
    def module_origin(self) -> Path:
        source = self.root / "module-source"
        source.mkdir()
        self.git(source, "init", "-q", "-b", "main")
        self.git(source, "commit", "--allow-empty", "-qm", "base")
        origin = self.root / "module.git"
        self.git(self.root, "clone", "-q", "--bare", str(source), str(origin))
        return origin

    def test_linked_checkout_keeps_old_form_submodule_history_without_force(self) -> None:
        origin = self.module_origin()
        checkout = self.root / "old-form"
        self.git(self.main, "worktree", "add", "-q", "-b", "old-form", str(checkout))
        module = checkout / "module"
        self.git(checkout, "clone", "-q", str(origin), str(module))
        self.git(module, "commit", "--allow-empty", "-qm", "local module history")
        unique = self.git(module, "rev-parse", "HEAD").stdout.strip()
        self.git(checkout, "config", "-f", ".gitmodules", "submodule.module.path", "module")
        self.git(checkout, "config", "-f", ".gitmodules", "submodule.module.url", str(origin))
        self.git(checkout, "add", ".gitmodules", "module")
        self.git(checkout, "commit", "-qm", "record old-form module")
        self.git(self.main, "tag", "saved-superproject", "old-form")
        self.assertTrue((module / ".git").is_dir())

        preflight = self.run_remove("--preflight", "--paths", str(checkout))
        removed = self.run_remove("--paths", str(checkout))

        self.assertEqual(preflight.stdout.strip(), str(checkout))
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertIn("submodule", removed.stderr)
        self.assertEqual(self.git(module, "cat-file", "-t", unique).stdout.strip(), "commit")
        forced = self.run_remove("--force", "--paths", str(checkout))
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertFalse(checkout.exists())

    def test_linked_checkout_keeps_deinitialized_module_admin_history(self) -> None:
        origin = self.module_origin()
        checkout = self.root / "deinitialized"
        self.git(self.main, "worktree", "add", "-q", "-b", "deinitialized", str(checkout))
        self.git(checkout, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(origin), "module")
        module = checkout / "module"
        self.git(module, "commit", "--allow-empty", "-qm", "local module history")
        unique = self.git(module, "rev-parse", "HEAD").stdout.strip()
        admin = Path(self.git(module, "rev-parse", "--absolute-git-dir").stdout.strip())
        self.git(checkout, "add", ".gitmodules", "module")
        self.git(checkout, "commit", "-qm", "record module")
        self.git(checkout, "submodule", "deinit", "-f", "--", "module")
        self.git(checkout, "rm", "-q", "-f", "module")
        self.git(checkout, "commit", "-qm", "remove module tracking")
        self.git(self.main, "tag", "saved-superproject", "deinitialized")

        removed = self.run_remove("--paths", str(checkout))

        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertIn("submodule history", removed.stderr)
        self.assertTrue(checkout.exists())
        self.assertEqual(
            self.git(self.main, "--git-dir", str(admin), "cat-file", "-t", unique).stdout.strip(), "commit"
        )


if __name__ == "__main__":
    unittest.main()
