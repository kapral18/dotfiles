#!/usr/bin/env python3
"""Behavior tests for ,add-patch-to-prs over real git repos and a fake gh."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "home/exact_lib"


class AddPatchToPrsTests(unittest.TestCase):
    """WHEN a patch is applied across PR branches."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        shutil.copytree(LIB / "exact_,add-patch-to-prs", self.root / "lib/cmd")
        shutil.copytree(LIB / "exact_shared", self.root / "lib/shared")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text('#!/bin/sh\n[ "$1 $2" = "pr view" ] && echo "pr$3"\n')
        (bin_dir / "gh").chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
        }
        origin = self.root / "origin.git"
        self.git(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        self.work = self.root / "work"
        self.git(self.root, "clone", "-q", str(origin), str(self.work))
        (self.work / "a.txt").write_text("one\n")
        (self.work / "b.txt").write_text("b\n")
        self.git(self.work, "add", ".")
        self.git(self.work, "commit", "-qm", "base")
        self.git(self.work, "push", "-q", "origin", "main")
        for name in ("pr1", "pr2"):
            self.git(self.work, "push", "-q", "origin", f"main:{name}")
        self.patch = self.root / "fix.patch"
        (self.work / "a.txt").write_text("two\n")
        self.patch.write_text(self.git(self.work, "diff"))
        self.git(self.work, "checkout", "-q", "a.txt")

    def git(self, cwd: Path, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True, text=True, capture_output=True).stdout

    def run_cmd(self, *prs: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(self.root / "lib/cmd/main.sh"), str(self.patch), *prs],
            cwd=self.work,
            env=self.env,
            input="\n\n",
            text=True,
            capture_output=True,
        )

    def test_dirty_tree_is_refused_before_touching_any_branch(self) -> None:
        (self.work / "b.txt").write_text("secret edit\n")
        result = self.run_cmd("1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.work, "branch", "--show-current").strip(), "main")
        self.assertEqual(
            self.git(self.work, "ls-remote", "origin", "pr1").split()[0],
            self.git(self.work, "rev-parse", "main").strip(),
        )

    def test_failed_commit_returns_to_the_start_branch_clean_and_fails(self) -> None:
        hook = self.work / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        result = self.run_cmd("1", "2")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.work, "branch", "--show-current").strip(), "main")
        self.assertEqual(self.git(self.work, "status", "--porcelain"), "")
        self.assertIn("Failed PRs: 1 2", result.stderr)

    def test_patch_that_adds_a_file_commits_it_on_every_pr(self) -> None:
        (self.work / "new.txt").write_text("new\n")
        self.git(self.work, "add", "-N", "new.txt")
        self.patch.write_text(self.git(self.work, "diff"))
        self.git(self.work, "rm", "-q", "--cached", "new.txt")
        (self.work / "new.txt").unlink()

        result = self.run_cmd("1", "2")

        self.assertEqual(result.returncode, 0, result.stderr)
        for pr in ("pr1", "pr2"):
            self.assertEqual(self.git(self.work, "show", f"origin/{pr}:new.txt"), "new\n")


if __name__ == "__main__":
    unittest.main()
