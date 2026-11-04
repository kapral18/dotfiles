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
        (bin_dir / "gh").write_text("""#!/bin/sh
case "$1 $2" in
  "pr view")
    branch="pr$3"
    sha=$(git --git-dir "$PR_REMOTE" rev-parse "refs/heads/$branch") || exit
    metadata=$(jq -n --arg branch "$branch" --arg sha "$sha" --arg pr "$3" \
      '{headRefName: $branch, headRefOid: $sha, headRepository: {name: "repo"}, headRepositoryOwner: {login: "head"}, url: ("https://github.com/base/repo/pull/" + $pr)}')
    shift 3
    expression='.'
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --jq | -q) expression="$2"; shift 2 ;;
        --json) shift 2 ;;
        *) shift ;;
      esac
    done
    printf '%s\\n' "$metadata" | jq -r "$expression"
    ;;
  "config get") printf 'https\\n' ;;
esac
""")
        (bin_dir / "gh").chmod(0o755)
        self.env = {
            **os.environ,
            "HOME": str(self.root),
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "TMPDIR": str(self.root),
        }
        origin = self.root / "origin.git"
        self.origin = origin
        self.env["PR_REMOTE"] = str(origin)
        self.git(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        self.work = self.root / "work"
        self.git(self.root, "clone", "-q", str(origin), str(self.work))
        self.git(self.work, "config", f"url.{origin}.insteadOf", "https://github.com/head/repo.git")
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
            timeout=20,
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
            self.assertEqual(self.git(self.root, "--git-dir", str(self.origin), "show", f"{pr}:new.txt"), "new\n")

    def test_fork_head_wins_over_colliding_origin_and_local_branch_names(self) -> None:
        fork = self.root / "fork.git"
        self.git(self.root, "clone", "-q", "--bare", str(self.origin), str(fork))
        fork_work = self.root / "fork-work"
        self.git(self.root, "clone", "-q", str(fork), str(fork_work))
        self.git(fork_work, "switch", "-q", "pr1")
        (fork_work / "a.txt").write_text("fork base\n")
        self.git(fork_work, "commit", "-qam", "fork-only change")
        self.git(fork_work, "push", "-q", "origin", "pr1")
        (fork_work / "new.txt").write_text("fork patch\n")
        self.git(fork_work, "add", "--intent-to-add", "new.txt")
        self.patch.write_text(self.git(fork_work, "diff"))
        self.git(self.work, "switch", "-q", "-c", "pr1")
        self.git(self.work, "branch", "--set-upstream-to=origin/pr1", "pr1")
        (self.work / "a.txt").write_text("local collision\n")
        self.git(self.work, "commit", "-qam", "local-only work")
        local_head = self.git(self.work, "rev-parse", "pr1")
        origin_head = self.git(self.root, "--git-dir", str(self.origin), "rev-parse", "pr1")
        self.git(self.work, "switch", "-q", "main")
        (self.work / "untracked").write_text("keep\n")
        self.git(self.work, "config", "--unset-all", f"url.{self.origin}.insteadOf")
        self.git(self.work, "config", f"url.{fork}.insteadOf", "https://github.com/head/repo.git")
        self.env["PR_REMOTE"] = str(fork)

        result = self.run_cmd("1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(self.root, "--git-dir", str(fork), "show", "pr1:a.txt"), "fork base\n")
        self.assertEqual(self.git(self.root, "--git-dir", str(fork), "show", "pr1:new.txt"), "fork patch\n")
        self.assertEqual(self.git(self.root, "--git-dir", str(self.origin), "rev-parse", "pr1"), origin_head)
        self.assertEqual(self.git(self.work, "rev-parse", "pr1"), local_head)
        self.assertEqual(self.git(self.work, "branch", "--show-current").strip(), "main")
        self.assertEqual((self.work / "untracked").read_text(), "keep\n")

    def test_rejected_push_keeps_patch_commit_on_recovery_branch_and_restores_checkout(self) -> None:
        hook = self.origin / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)

        result = self.run_cmd("1")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.work, "branch", "--show-current").strip(), "main")
        self.assertEqual(self.git(self.work, "status", "--porcelain"), "")
        branches = self.git(
            self.work, "for-each-ref", "--format=%(refname:short)", "refs/heads/patch-pr-1-*"
        ).splitlines()
        self.assertEqual(len(branches), 1, result.stderr)
        self.assertEqual(self.git(self.work, "show", f"{branches[0]}:a.txt"), "two\n")
        self.assertIn(branches[0], result.stderr)


if __name__ == "__main__":
    unittest.main()
