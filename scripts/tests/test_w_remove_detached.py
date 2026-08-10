#!/usr/bin/env python3
"""Regression tests for ,w remove --paths on detached HEAD worktrees.

Locks the bash TSV parse that used to collapse an empty branch_ref field
(``path\\t\\t1\\t0`` → branch_ref=1, detached=0) and the preflight path that
hardcoded detached=0, both of which made alt-x in the session picker hide a
detached worktree row and then resurrect it.
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


class WRemoveDetachedTests(unittest.TestCase):
    """WHEN ,w remove --paths targets a detached HEAD worktree."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
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

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
        )

    def run_remove(self, *extra: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(self.root / "home")
        Path(env["HOME"]).mkdir(exist_ok=True)
        return subprocess.run(
            ["bash", str(self.remove_sh), "--paths", str(self.detached), *extra],
            cwd=self.main,
            text=True,
            capture_output=True,
            env=env,
        )

    def test_preflight_does_not_flag_clean_detached_worktree(self) -> None:
        result = self.run_remove("--preflight")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_paths_removes_detached_worktree(self) -> None:
        result = self.run_remove()
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertNotIn("Skipping (not a local branch worktree)", combined)
        self.assertIn("Removing detached worktree:", combined)
        self.assertFalse(self.detached.exists(), "detached worktree directory should be gone")
        listed = self.git(self.main, "worktree", "list", "--porcelain").stdout
        self.assertNotIn(str(self.detached), listed)

    def test_tsv_assign_preserves_empty_branch_field(self) -> None:
        extract = r"""
set -euo pipefail
eval "$(sed -n '/^_tsv_assign()/,/^}/p' "$1")"
rec=$'/tmp/detached\t\t1\t0'
_tsv_assign "$rec" p_found branch_ref detached locked
printf '%s|%s|%s|%s\n' "$p_found" "$branch_ref" "$detached" "$locked"
"""
        result = subprocess.run(
            ["bash", "-c", extract, "_", str(self.remove_sh)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "/tmp/detached||1|0")


if __name__ == "__main__":
    unittest.main()
