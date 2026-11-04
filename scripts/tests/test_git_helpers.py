#!/usr/bin/env python3
"""Behavior tests for ,hey-branch, ,check-backport-progress and ,gh-tfork with real git and a fake gh."""

from __future__ import annotations

import base64
import json
import os
import shlex
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
        return subprocess.run(
            ["git", *args], cwd=cwd, env=self.env, check=True, text=True, capture_output=True, timeout=15
        ).stdout

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


class GitPupTests(_GitCase):
    def test_rebases_local_commits_onto_the_matching_upstream_branch(self) -> None:
        self.env.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_COUNT": "2",
                "GIT_CONFIG_KEY_0": "commit.gpgSign",
                "GIT_CONFIG_VALUE_0": "false",
                "GIT_CONFIG_KEY_1": "protocol.file.allow",
                "GIT_CONFIG_VALUE_1": "always",
            }
        )
        work = self.clone_with_origin()
        self.git(work, "remote", "rename", "origin", "upstream")
        self.git(work, "switch", "-q", "-c", "feature")
        (work / "feature").write_text("feature base\n")
        self.git(work, "add", "feature")
        self.git(work, "commit", "-qm", "feature base")
        self.git(work, "push", "-q", "-u", "upstream", "feature")
        publisher = self.root / "publisher"
        self.git(self.root, "clone", "-q", str(self.root / "origin.git"), str(publisher))
        self.git(publisher, "switch", "-q", "feature")
        (publisher / "remote").write_text("upstream feature update\n")
        self.git(publisher, "add", "remote")
        self.git(publisher, "commit", "-qm", "upstream feature update")
        self.git(publisher, "push", "-q", "origin", "feature")
        upstream_tip = self.git(publisher, "rev-parse", "HEAD").strip()
        (work / "local").write_text("local content\n")
        self.git(work, "add", "local")
        self.git(work, "commit", "-qm", "local content")
        alias_line = next(
            line
            for line in (REPO / "home/private_readonly_dot_gitconfig.tmpl").read_text().splitlines()
            if line.lstrip().startswith("pup =")
        )
        config = self.root / "pup-config"
        config.write_text(f"[alias]\n{alias_line}\n")
        self.git(work, "config", "include.path", str(config))

        result = subprocess.run(["git", "pup"], cwd=work, env=self.env, capture_output=True, text=True, timeout=15)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(work, "branch", "--show-current").strip(), "feature")
        self.assertEqual(self.git(work, "rev-parse", "HEAD^").strip(), upstream_tip)
        self.assertEqual((work / "local").read_text(), "local content\n")
        self.assertEqual((work / "remote").read_text(), "upstream feature update\n")


class WtgrabTests(_GitCase):
    def source_worktree(self, work: Path, name: str = "source") -> Path:
        self.env["TMPDIR"] = str(self.root)
        source = self.root / name
        self.git(work, "worktree", "add", "-q", "-b", "source", str(source))
        config = self.root / "aliases"
        config.write_text((REPO / "home/private_readonly_dot_gitconfig.tmpl").read_text().split("[core]", 1)[0])
        alias = self.git(work, "config", "--file", str(config), "--get", "alias.wtgrab").strip()
        self.git(work, "config", "alias.wtgrab", alias)
        helper = REPO / "home/exact_lib/exact_shared/wtgrab.py"
        if helper.exists():
            destination = self.root / "home/lib/shared/wtgrab.py"
            destination.parent.mkdir(parents=True)
            shutil.copyfile(helper, destination)
        return source

    def grab(self, work: Path, source: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "wtgrab", str(source)], cwd=work, env=self.env, capture_output=True, text=True, timeout=15
        )

    def test_moves_staged_and_unstaged_binary_additions_and_deletions_without_losing_target_edits(self) -> None:
        work = self.clone_with_origin()
        (work / "binary").write_bytes(b"base\0\n")
        for name in ("staged-delete", "unstaged-delete", "keep"):
            (work / name).write_text("base\n")
        self.git(work, "add", ".")
        self.git(work, "commit", "-qm", "tracked fixtures")
        source = self.source_worktree(work, "source with spaces")
        (source / "a").write_text("staged\n")
        (source / "binary").write_bytes(b"staged\0\n")
        (source / "new file").write_bytes(b"new\0\n")
        self.git(source, "add", "a", "binary", "new file")
        (source / "intent file").write_text("intent to add\n")
        self.git(source, "add", "--intent-to-add", "intent file")
        self.git(source, "rm", "-q", "staged-delete")
        (source / "a").write_text("unstaged\n")
        (source / "binary").write_bytes(b"unstaged\0\n")
        (source / "unstaged-delete").unlink()
        (source / "untracked").write_text("leave at source\n")
        staged = self.git(source, "diff", "--cached", "--binary")
        unstaged = self.git(source, "diff", "--binary")
        (work / "keep").write_text("local target edit\n")

        result = self.grab(work, source)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(work, "diff", "--cached", "--binary"), staged)
        self.assertEqual(
            self.git(work, "diff", "--binary", "--", "a", "binary", "intent file", "unstaged-delete"), unstaged
        )
        self.assertEqual((work / "binary").read_bytes(), b"unstaged\0\n")
        self.assertEqual((work / "keep").read_text(), "local target edit\n")
        self.assertEqual(self.git(source, "diff", "HEAD"), "")
        self.assertEqual(self.git(source, "status", "--porcelain"), "?? untracked\n")
        self.assertEqual((source / "untracked").read_text(), "leave at source\n")

    def test_unstaged_conflict_rolls_back_target_staged_patch_and_leaves_source_unchanged(self) -> None:
        work = self.clone_with_origin()
        (work / "b").write_text("base\n")
        self.git(work, "add", "b")
        self.git(work, "commit", "-qm", "second file")
        source = self.source_worktree(work)
        (source / "a").write_text("staged\n")
        self.git(source, "add", "a")
        (source / "b").write_text("source unstaged\n")
        (work / "b").write_text("target edit\n")
        source_index = self.git(source, "diff", "--cached", "--binary")
        source_work = self.git(source, "diff", "--binary")
        target_work = self.git(work, "diff", "--binary")

        result = self.grab(work, source)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(source, "diff", "--cached", "--binary"), source_index)
        self.assertEqual(self.git(source, "diff", "--binary"), source_work)
        self.assertEqual(self.git(work, "diff", "--cached"), "")
        self.assertEqual(self.git(work, "diff", "--binary"), target_work)

    def test_source_edit_during_transfer_is_preserved_and_cleanup_is_refused(self) -> None:
        work = self.clone_with_origin()
        base = [f"line {index}\n" for index in range(30)]
        (work / "a").write_text("".join(base))
        self.git(work, "commit", "-qam", "separated edit sites")
        source = self.source_worktree(work)
        captured = ["captured\n", *base[1:]]
        concurrent = [*captured[:-1], "concurrent edit\n"]
        (source / "a").write_text("".join(captured))
        self.env.update({"GRAB_SOURCE": str(source), "GRAB_TARGET": str(work), "GIT_EXEC_PATH": str(self.bin)})
        real_git = shlex.quote(shutil.which("git"))
        contents = shlex.quote("".join(concurrent))
        self.stub(
            "git",
            f'''{real_git} "$@"
status=$?
if [ "$status" = 0 ] && [ "${{1:-}}" = -C ] && [ "${{2:-}}" = "$GRAB_TARGET" ] && [ "${{3:-}}" = apply ]; then
  printf '%s' {contents} > "$GRAB_SOURCE/a"
fi
exit "$status"''',
        )

        result = self.grab(work, source)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((source / "a").read_text(), "".join(concurrent))
        self.assertEqual((work / "a").read_text(), "".join(captured))


class GithubIdentityTests(_GitCase):
    def test_worktree_wrapper_refuses_wrong_owner_before_bootstrap_or_dispatch(self) -> None:
        work = self.clone_with_origin()
        self.git(work, "remote", "set-url", "origin", "https://credential:secret@github.com/other/tool.git")
        for command in (",w", ",gh-tfork"):
            self.stub(command, 'echo called >> "$HOME/effects"')
        command = self.lib("gh-worktree")
        for args in (("--repo-path", str(work)), ()):
            if not args:
                (self.root / "home/code").mkdir()
                (self.root / "home/code/tool").symlink_to(work, target_is_directory=True)
            result = subprocess.run(
                ["bash", str(command), "pr", "wanted/tool", "7", *args, "--print-root"],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("secret", result.stdout + result.stderr)
            self.assertFalse((self.root / "home/effects").exists())

    def test_worktree_wrapper_accepts_upstream_identity_and_passes_requested_repo(self) -> None:
        work = self.clone_with_origin()
        self.git(work, "remote", "set-url", "origin", "git@github.com:me/tool.git")
        self.git(work, "remote", "add", "upstream", "ssh://git@github.com/wanted/tool.git")
        self.stub(",w", 'printf "%s\\n" "$GH_REPO" "$*" > "$HOME/dispatch"')
        result = subprocess.run(
            [
                "bash",
                str(self.lib("gh-worktree")),
                "issue",
                "wanted/tool",
                "7",
                "--repo-path",
                str(work),
                "--branch",
                "fix",
            ],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "home/dispatch").read_text().splitlines(), ["wanted/tool", "issue -b fix 7"])

    def test_explicit_and_pr_body_issue_urls_keep_repository_until_number_projection(self) -> None:
        work = self.clone_with_origin()
        command = REPO / "home/exact_bin/executable_,gh-issuew"
        self.stub(
            "gh",
            """case "$*" in
  "repo view "*) echo current/tool ;;
  "pr view --json number"*) echo 9 ;;
  "pr view 9 --json body"*) printf 'Fixes https://github.com/other/tool/issues/42\\nCloses #8\\n' ;;
  "issue view "*) printf '%s\\n' "$*" >> "$HOME/issue-calls" ;;
esac""",
        )
        url = "https://github.com/other/tool/issues/42"
        for args, expected in ((("--url", url), url), (("--number", url), "42")):
            result = subprocess.run(
                ["bash", str(command), *args], cwd=work, env=self.env, capture_output=True, text=True, timeout=15
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), expected)
        result = subprocess.run(
            ["bash", str(command)], cwd=work, env=self.env, capture_output=True, text=True, timeout=15
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.root / "home/issue-calls").read_text().splitlines(),
            ["issue view -R current/tool -w 8", f"issue view -w {url}"],
        )


class ChangedLinesTests(_GitCase):
    def test_source_header_prefixes_stay_in_the_hunk_with_correct_paths_and_lines(self) -> None:
        work = self.clone_with_origin()
        (work / "a").write_text("-- old header\nlast\n")
        (work / "deleted").write_text("gone\n")
        (work / "binary").write_bytes(b"base\0")
        self.git(work, "add", ".")
        self.git(work, "commit", "-qm", "diff fixture")
        (work / "a").write_text("++ count;\n++ b/misleading\nlast changed\n")
        (work / "deleted").unlink()
        (work / "binary").write_bytes(b"changed\0")
        (work / "untracked").write_text("new line\n")

        result = subprocess.run(
            ["python3", str(REPO / "home/exact_bin/executable_,fzf-git-changed-lines")],
            cwd=work,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            ["a:1:1:++ count;", "a:2:1:++ b/misleading", "a:3:1:last changed", "untracked:1:1:new line"],
        )


if __name__ == "__main__":
    unittest.main()
