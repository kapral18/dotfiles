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
        for name in ("bash_utils_lib.sh", "worktree_lib.sh"):
            shutil.copy2(SHARED_SRC / name, self.shared / name)
        self.remove_sh = self.w_dir / "remove.sh"
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        tmux = self.bin_dir / "tmux"
        tmux.write_text("#!/bin/sh\nexit 1\n")
        tmux.chmod(0o755)

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
        )

    def run_remove(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self.run_remove_in(self.main, *args)

    def run_remove_in(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(self.root / "home")
        Path(env["HOME"]).mkdir(exist_ok=True)
        env["PATH"] = f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}"
        return subprocess.run(
            ["bash", str(self.remove_sh), *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            env=env,
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


if __name__ == "__main__":
    unittest.main()
