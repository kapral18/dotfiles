#!/usr/bin/env python3
"""Behavior tests for ,hey-branch, ,check-backport-progress and ,gh-tfork with real git and a fake gh."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class _GitCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {
            **os.environ,
            "HOME": str(self.root / "home"),
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
        }
        (self.root / "home").mkdir()

    def stub(self, name: str, body: str) -> None:
        (self.bin / name).write_text(f"#!/bin/sh\n{body}\n")
        (self.bin / name).chmod(0o755)

    def git(self, cwd: Path, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True, text=True, capture_output=True).stdout

    def clone_with_origin(self) -> Path:
        origin = self.root / "origin.git"
        self.git(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        work = self.root / "work"
        self.git(self.root, "clone", "-q", str(origin), str(work))
        (work / "a").write_text("a\n")
        self.git(work, "add", "a")
        self.git(work, "commit", "-qm", "base")
        self.git(work, "push", "-q", "origin", "main")
        return work

    def lib(self, name: str) -> Path:
        shutil.copytree(REPO / f"home/exact_lib/exact_,{name}", self.root / f"lib/{name}")
        if not (self.root / "lib/shared").exists():
            shutil.copytree(REPO / "home/exact_lib/exact_shared", self.root / "lib/shared")
        return self.root / f"lib/{name}/main.sh"


class HeyBranchTests(_GitCase):
    """WHEN the tracked remote branch was deleted."""

    def test_reports_the_missing_branch_instead_of_exiting(self) -> None:
        work = self.clone_with_origin()
        self.git(work, "switch", "-q", "-c", "feat")
        self.git(work, "push", "-q", "-u", "origin", "feat")
        self.git(work, "push", "-q", "origin", "--delete", "feat")
        result = subprocess.run(
            ["bash", str(self.lib("hey-branch"))], cwd=work, env=self.env, text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Tracked Branch Exists: No", result.stdout)


class CheckBackportProgressTests(_GitCase):
    """WHEN merged PRs are checked against backport branches."""

    def run_check(self, work: Path, pr_number: int) -> subprocess.CompletedProcess[str]:
        row = base64.b64encode(
            json.dumps({"number": pr_number, "url": f"https://x/pull/{pr_number}"}).encode()
        ).decode()
        self.stub("gh", f'case "$*" in *merged*) echo {row} ;; esac')
        return subprocess.run(
            [
                "bash",
                str(REPO / "home/exact_bin/executable_,check-backport-progress"),
                "--merged-label",
                "fix",
                "--required-labels",
                "b",
                "--branches",
                "main",
                "--upstream",
                "origin",
            ],
            cwd=work,
            env=self.env,
            text=True,
            capture_output=True,
        )

    def test_longer_pr_number_does_not_count_and_a_miss_fails(self) -> None:
        work = self.clone_with_origin()
        (work / "b").write_text("b\n")
        self.git(work, "add", "b")
        self.git(work, "commit", "-qm", "backport (#123)")
        self.git(work, "push", "-q", "origin", "main")
        result = self.run_check(work, 12)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("has not been backported", result.stdout)

    def test_exact_pr_number_passes(self) -> None:
        work = self.clone_with_origin()
        (work / "b").write_text("b\n")
        self.git(work, "add", "b")
        self.git(work, "commit", "-qm", "backport (#12)")
        self.git(work, "push", "-q", "origin", "main")
        result = self.run_check(work, 12)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class GhTforkTests(_GitCase):
    """WHEN the user already owns a repo with the requested name."""

    def test_unrelated_same_name_repo_is_refused_before_cloning(self) -> None:
        # The fake gh evaluates the fork-parent jq expression as "false": a same-name repo that is not this fork.
        self.stub(
            "gh",
            'case "$*" in "api user --jq .login") echo me ;; "config get git_protocol") echo https ;; *repos/me/tool*--jq*) echo false ;; *) exit 0 ;; esac',
        )
        self.stub("git", 'echo "git $*" >> "$HOME/git.log"')
        result = subprocess.run(
            ["bash", str(self.lib("gh-tfork")), "upstream/tool"], env=self.env, text=True, capture_output=True
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a fork of upstream/tool", result.stderr)
        self.assertFalse((self.root / "home/git.log").exists())


if __name__ == "__main__":
    unittest.main()
