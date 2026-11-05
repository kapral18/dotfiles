#!/usr/bin/env python3
"""Focused tests for w issue."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestWIssueCommand(unittest.TestCase):
    """WHEN creating an issue worktree through the deployed read-only command library."""

    def test_foreign_issue_associations_are_never_retagged_or_focused_by_any_reuse_route(self):
        cases = (
            ("heuristic", "foreign-42", "legacy", "other/tool", "42"),
            ("manual", "selected", "selected", "other/tool", "42"),
            ("suffixed", "fix-42", "fix", "other/tool", "42"),
            ("different-number", "selected", "selected", "current/tool", "99"),
        )
        for route, foreign_branch, requested_branch, stored_repo, stored_number in cases:
            with self.subTest(route=route), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                home = root / "home"
                bin_dir = home / "bin"
                bin_dir.mkdir(parents=True)
                w_dir = home / "lib/,w"
                shutil.copytree(REPO / "home/exact_lib/exact_,w", w_dir)
                shutil.copytree(REPO / "home/exact_lib/exact_shared", home / "lib/shared")
                gh = bin_dir / "gh"
                gh.write_text("#!/bin/sh\nprintf 'current/tool\\n'\n")
                gh.chmod(0o755)
                herdr_log = root / "herdr.log"
                herdr_db = root / "workspaces.tsv"
                herdr_db.write_text("")
                install_fake_herdr(bin_dir)
                repo = root / "repo"
                repo.mkdir()
                env = {
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_AUTHOR_NAME": "Fixture",
                    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                    "GIT_COMMITTER_NAME": "Fixture",
                    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                    "COMMA_W_PRUNE": "0",
                    "XDG_CACHE_HOME": str(root / "cache"),
                    "HERDR_SOCKET_PATH": str(root / "herdr.sock"),
                    "HERDR_LOG": str(herdr_log),
                    "HERDR_DB": str(herdr_db),
                }

                def git(*args):
                    return subprocess.run(
                        ["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True
                    ).stdout

                git("init", "-q", "-b", "main")
                (repo / "README").write_text("fixture\n")
                git("add", "README")
                git("commit", "-qm", "fixture")
                foreign = root / "foreign"
                git("worktree", "add", "-q", "-b", foreign_branch, str(foreign))
                legacy = root / "legacy"
                if route == "heuristic":
                    git("worktree", "add", "-q", "-b", "legacy", str(legacy))
                git("config", "extensions.worktreeConfig", "true")
                git("-C", str(foreign), "config", "--worktree", "comma.w.issue.repo", stored_repo)
                git("-C", str(foreign), "config", "--worktree", "comma.w.issue.number", stored_number)

                result = subprocess.run(
                    [modern_bash(), str(w_dir / "issue.sh"), "-q", "--focus", "-b", requested_branch, "42"],
                    cwd=repo,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                self.assertEqual(
                    git("-C", str(foreign), "config", "--worktree", "--get", "comma.w.issue.repo").strip(), stored_repo
                )
                self.assertEqual(
                    git("-C", str(foreign), "config", "--worktree", "--get", "comma.w.issue.number").strip(),
                    stored_number,
                )
                log = herdr_log.read_text() if herdr_log.exists() else ""
                self.assertNotIn(str(foreign), log)
                if route == "heuristic":
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(
                        git("-C", str(legacy), "config", "--worktree", "--get", "comma.w.issue.repo").strip(),
                        "current/tool",
                    )
                    self.assertIn(str(legacy), log)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("worktree is associated with another issue", result.stderr)
                    self.assertEqual(log, "")

    def test_foreign_issue_url_is_refused_before_worktree_or_git_config_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            bin_dir = home / "bin"
            bin_dir.mkdir()
            w_dir = home / "lib/,w"
            shutil.copytree(REPO / "home/exact_lib/exact_,w", w_dir)
            shutil.copytree(REPO / "home/exact_lib/exact_shared", home / "lib/shared")
            gh = bin_dir / "gh"
            gh.write_text("#!/bin/sh\nprintf 'current/tool\\n'\n")
            gh.chmod(0o755)
            repo = root / "repo"
            repo.mkdir()
            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "COMMA_W_PRUNE": "0",
            }
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, env=env, check=True, capture_output=True)
            config_before = (repo / ".git/config").read_bytes()

            result = subprocess.run(
                [modern_bash(), str(w_dir / "issue.sh"), "-q", "-b", "fix", "https://github.com/other/tool/issues/42"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("issue URL belongs to other/tool; current repository is current/tool", result.stderr)
            self.assertEqual((repo / ".git/config").read_bytes(), config_before)
            self.assertFalse((repo / ".git/worktrees").exists())

    def test_should_create_and_focus_inside_herdr_with_read_only_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bin_dir = home / "bin"
            w_dir = home / "lib/,w"
            shared_dir = home / "lib/shared"
            repo = root / "repo"
            for path in (bin_dir, w_dir, shared_dir, repo):
                path.mkdir(parents=True)

            for name in ("issue.sh", "issue_lib.sh", "add.sh", "open.sh", "switch.sh", "ls.sh"):
                shutil.copyfile(REPO / "home/exact_lib/exact_,w" / name, w_dir / name)
                (w_dir / name).chmod(0o444)
            for name in ("bash_utils_lib.sh", "worktree_lib.sh"):
                shutil.copyfile(REPO / "home/exact_lib/exact_shared" / name, shared_dir / name)
                (shared_dir / name).chmod(0o444)

            gh = bin_dir / "gh"
            gh.write_text(
                "#!/usr/bin/env bash\nif [[ ${1:-} == repo && ${2:-} == view ]]; then printf 'owner/repo\\n'; fi\n"
            )
            gh.chmod(0o755)
            zoxide = bin_dir / "zoxide"
            zoxide.write_text("#!/usr/bin/env bash\nexit 0\n")
            zoxide.chmod(0o755)
            install_fake_herdr(bin_dir)
            herdr_log = root / "herdr.log"
            herdr_db = root / "workspaces.tsv"
            herdr_db.write_text("")

            for args in (
                ["init", "-b", "main"],
                ["config", "user.name", "Fixture"],
                ["config", "user.email", "fixture@example.test"],
                ["config", "commit.gpgSign", "false"],
            ):
                subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
            (repo / "README").write_text("fixture\n")
            subprocess.run(["git", "add", "README"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)

            env = {
                **{k: v for k, v in os.environ.items() if not k.startswith("HERDR_")},
                "HOME": str(home),
                "PATH": f"{bin_dir}:/opt/homebrew/bin:/usr/bin:/bin",
                "COMMA_W_PRUNE": "0",
                "XDG_CACHE_HOME": str(root / "cache"),
                "HERDR_SOCKET_PATH": str(root / "herdr.sock"),
                "HERDR_LOG": str(herdr_log),
                "HERDR_DB": str(herdr_db),
            }
            result = subprocess.run(
                [modern_bash(), str(w_dir / "issue.sh"), "--focus", "-q", "-b", "fix/test/create", "123"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            worktrees = subprocess.run(
                ["git", "worktree", "list", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True
            ).stdout
            self.assertIn("branch refs/heads/fix/test/create-123", worktrees)
            rows = [line.split("\t") for line in herdr_db.read_text().splitlines()]
            self.assertEqual(len(rows), 1, herdr_log.read_text())
            self.assertIn(f"workspace focus {rows[0][0]}", herdr_log.read_text())

    def test_workspace_create_and_focus_use_exact_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            install_fake_herdr(bin_dir)
            herdr_log = root / "herdr.log"
            herdr_db = root / "workspaces.tsv"
            worktree_path = root / "worktree"
            worktree_path.mkdir()
            herdr_db.write_text(f"w1\trepo|fix-long\t{worktree_path}\n")
            probe = subprocess.run(
                [
                    modern_bash(),
                    "-c",
                    'source "$1"; _add_worktree_workspace 1 repo fix "$2"; _comma_w_focus_workspace 1 "repo|fix" "$2"',
                    "fixture",
                    str(REPO / "home/exact_lib/exact_shared/worktree_lib.sh"),
                    str(worktree_path),
                ],
                env={
                    **{k: v for k, v in os.environ.items() if not k.startswith("HERDR_")},
                    "HOME": str(root),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "XDG_CACHE_HOME": str(root / "cache"),
                    "HERDR_SOCKET_PATH": str(root / "herdr.sock"),
                    "HERDR_LOG": str(herdr_log),
                    "HERDR_DB": str(herdr_db),
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertEqual(
                [r.split("\t")[1] for r in herdr_db.read_text().splitlines()], ["repo|fix-long", "repo|fix"]
            )
            self.assertIn("workspace focus w2", herdr_log.read_text())

    def test_pr_retry_repairs_workspace_after_create_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bin_dir = home / "bin"
            w_dir = home / "lib/,w"
            shared_dir = home / "lib/shared"
            repo = root / "repo"
            remote = root / "remote.git"
            for path in (bin_dir, w_dir, shared_dir, repo):
                path.mkdir(parents=True)

            for name in ("prs.sh", "mv.sh"):
                shutil.copyfile(REPO / "home/exact_lib/exact_,w" / name, w_dir / name)
                (w_dir / name).chmod(0o444)
            for name in ("bash_utils_lib.sh", "worktree_lib.sh"):
                shutil.copyfile(REPO / "home/exact_lib/exact_shared" / name, shared_dir / name)
                (shared_dir / name).chmod(0o444)

            gh = bin_dir / "gh"
            gh.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ ${1:-} == repo && ${2:-} == view ]]; then\n"
                "  printf 'owner\\trepo\\n'\n"
                "elif [[ ${1:-} == pr && ${2:-} == view ]]; then\n"
                "  printf 'feature/pr\\trepo\\towner\\n'\n"
                "fi\n"
            )
            gh.chmod(0o755)
            zoxide = bin_dir / "zoxide"
            zoxide.write_text("#!/usr/bin/env bash\nexit 0\n")
            zoxide.chmod(0o755)
            install_fake_herdr(bin_dir)
            herdr_db = root / "workspaces.tsv"
            herdr_db.write_text("")
            fail_once = root / "create-fails-once"

            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            for args in (
                ["init", "-b", "main"],
                ["config", "user.name", "Fixture"],
                ["config", "user.email", "fixture@example.test"],
                ["config", "commit.gpgSign", "false"],
            ):
                subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
            (repo / "README").write_text("fixture\n")
            subprocess.run(["git", "add", "README"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "switch", "-c", "feature/pr"], cwd=repo, check=True, capture_output=True)
            (repo / "PR").write_text("pr\n")
            subprocess.run(["git", "add", "PR"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "pr"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", "feature/pr"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "switch", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "branch", "-D", "feature/pr"], cwd=repo, check=True, capture_output=True)

            env = {
                **{k: v for k, v in os.environ.items() if not k.startswith("HERDR_")},
                "HOME": str(home),
                "PATH": f"{bin_dir}:/opt/homebrew/bin:/usr/bin:/bin",
                "COMMA_W_PRUNE": "0",
                "XDG_CACHE_HOME": str(root / "cache"),
                "HERDR_SOCKET_PATH": str(root / "herdr.sock"),
                "HERDR_DB": str(herdr_db),
                "HERDR_FAKE_CREATE_FAILS_ONCE": str(fail_once),
            }
            fail_once.write_text("fail\n")

            def prs():
                return subprocess.run(
                    [modern_bash(), str(w_dir / "prs.sh"), "-q", "123"],
                    cwd=repo,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

            first = prs()
            self.assertNotEqual(first.returncode, 0, first.stderr)
            self.assertEqual(herdr_db.read_text(), "", "failed PR workspace create was reported as success")

            retry = prs()
            self.assertEqual(retry.returncode, 0, retry.stderr)
            self.assertNotEqual(herdr_db.read_text(), "", "existing PR worktree did not retry workspace creation")

            original_worktrees = subprocess.check_output(
                ["git", "worktree", "list", "--porcelain"], cwd=repo, text=True
            )
            feature = next(
                Path(block.splitlines()[0].removeprefix("worktree "))
                for block in original_worktrees.strip().split("\n\n")
                if "branch refs/heads/feature/pr" in block.splitlines()
            )
            (feature / "keep-local-change").write_text("uncommitted work\n")
            legacy = root / "pr-123"
            subprocess.run(["git", "-C", str(feature), "branch", "-m", "pr-123"], check=True, capture_output=True)
            subprocess.run(
                ["git", "worktree", "move", str(feature), str(legacy)], cwd=repo, check=True, capture_output=True
            )
            herdr_db.write_text("")

            migrated = prs()
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            self.assertFalse(legacy.exists())
            self.assertEqual((feature / "keep-local-change").read_text(), "uncommitted work\n")
            self.assertEqual(
                subprocess.check_output(["git", "worktree", "list", "--porcelain"], cwd=repo, text=True),
                original_worktrees,
            )
            self.assertNotEqual(herdr_db.read_text(), "")


if __name__ == "__main__":
    unittest.main()
