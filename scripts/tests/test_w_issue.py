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

    def test_should_create_and_focus_on_outer_tmux_with_read_only_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bin_dir = home / "bin"
            w_dir = home / "lib/,w"
            shared_dir = home / "lib/shared"
            repo = root / "repo"
            bin_dir.mkdir(parents=True)
            w_dir.mkdir(parents=True)
            shared_dir.mkdir(parents=True)
            repo.mkdir()

            source_w = REPO / "home/exact_lib/exact_,w"
            source_shared = REPO / "home/exact_lib/exact_shared"
            for name in ("issue.sh", "issue_lib.sh", "add.sh", "open.sh", "switch.sh", "ls.sh"):
                shutil.copyfile(source_w / name, w_dir / name)
                (w_dir / name).chmod(0o444)
            for name in ("bash_utils_lib.sh", "worktree_lib.sh"):
                shutil.copyfile(source_shared / name, shared_dir / name)
                (shared_dir / name).chmod(0o444)

            gh = bin_dir / "gh"
            gh.write_text(
                "#!/usr/bin/env bash\nif [[ ${1:-} == repo && ${2:-} == view ]]; then printf 'owner/repo\\n'; fi\n"
            )
            gh.chmod(0o755)
            zoxide = bin_dir / "zoxide"
            zoxide.write_text("#!/usr/bin/env bash\nexit 0\n")
            zoxide.chmod(0o755)
            tmux_log = root / "tmux.log"
            tmux_session = root / "tmux-session"
            tmux = bin_dir / "tmux"
            tmux.write_text(
                "#!/usr/bin/env bash\n"
                'printf \'%s\\n\' "$*" >> "$TMUX_LOG"\n'
                'case " $* " in\n'
                "  *' has-session '*) [[ -f \"$TMUX_SESSION_FILE\" ]] ;;\n"
                "  *' new-session '*)\n"
                "    if [[ -n ${TMUX_FAIL_ONCE_FILE:-} && -f $TMUX_FAIL_ONCE_FILE ]]; then\n"
                '      rm -f "$TMUX_FAIL_ONCE_FILE"\n'
                "      exit 1\n"
                "    fi\n"
                '    : > "$TMUX_SESSION_FILE"\n'
                "    ;;\n"
                "  *' list-clients '*) printf 'fixture-client\\n' ;;\n"
                "  *' switch-client '*) exit 0 ;;\n"
                "esac\n"
            )
            tmux.chmod(0o755)

            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "commit.gpgSign", "false"], cwd=repo, check=True)
            (repo / "README").write_text("fixture\n")
            subprocess.run(["git", "add", "README"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)

            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bin_dir}:/opt/homebrew/bin:/usr/bin:/bin",
                "COMMA_W_PRUNE": "0",
                "TMUX_LOG": str(tmux_log),
                "TMUX_SESSION_FILE": str(tmux_session),
                "TMUX_FAIL_ONCE_FILE": str(root / "tmux-fail-once"),
            }
            for key in ("TMUX", "TMUX_PANE", "OUTER_TMUX_SOCKET", "OUTER_TMUX_CLIENT"):
                env.pop(key, None)
            env["OUTER_TMUX_SOCKET"] = str(root / "outer.sock")

            result = subprocess.run(
                [modern_bash(), str(w_dir / "issue.sh"), "--focus", "-q", "-b", "fix/test/create", "123"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, result.stderr
            worktrees = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            assert "branch refs/heads/fix/test/create-123" in worktrees
            assert tmux_session.exists(), tmux_log.read_text() if tmux_log.exists() else "tmux was never invoked"
            assert f"-S {root / 'outer.sock'} new-session -d" in tmux_log.read_text()

    def test_tmux_session_create_and_focus_use_exact_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            sessions = root / "sessions.txt"
            sessions.write_text("repo|fix-long\n")
            tmux_log = root / "tmux.log"
            tmux = bin_dir / "tmux"
            tmux.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$TMUX_LOG"
if [ "${1:-}" = "-S" ]; then shift 2; fi
command="${1:-}"
shift || true
target=""
session=""
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case "${args[i]}" in
    -t) target="${args[i + 1]}" ;;
    -s) session="${args[i + 1]}" ;;
  esac
done
matches_target() {
  local requested="$1"
  if [[ "$requested" == =* ]]; then
    grep -Fxq -- "${requested#=}" "$TMUX_SESSIONS"
  else
    awk -v prefix="$requested" 'index($0, prefix) == 1 { found = 1 } END { exit !found }' "$TMUX_SESSIONS"
  fi
}
case "$command" in
  has-session) matches_target "$target" ;;
  new-session) printf '%s\n' "$session" >> "$TMUX_SESSIONS" ;;
  list-clients) printf 'fixture-client\n' ;;
  switch-client | attach-session) matches_target "$target" ;;
esac
"""
            )
            tmux.chmod(0o755)
            worktree_path = root / "worktree"
            worktree_path.mkdir()
            shared = REPO / "home/exact_lib/exact_shared/worktree_lib.sh"
            probe = subprocess.run(
                [
                    modern_bash(),
                    "-c",
                    'source "$1"; _add_worktree_tmux_session 1 repo fix "$2"; '
                    '_comma_w_focus_tmux_session 1 "repo|fix" "$2"',
                    "fixture",
                    str(shared),
                    str(worktree_path),
                ],
                env={
                    **os.environ,
                    "HOME": str(root),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "OUTER_TMUX_SOCKET": str(root / "outer.sock"),
                    "OUTER_TMUX_CLIENT": "fixture-client",
                    "TMUX_LOG": str(tmux_log),
                    "TMUX_SESSIONS": str(sessions),
                },
                capture_output=True,
                text=True,
            )
            assert probe.returncode == 0, probe.stderr
            assert sessions.read_text().splitlines() == ["repo|fix-long", "repo|fix"]
            log = tmux_log.read_text()
            assert "has-session -t =repo|fix" in log
            assert "switch-client -c fixture-client -t =repo|fix" in log

    def test_should_invoke_pr_migration_helper_through_bash(self):
        source = (REPO / "home/exact_lib/exact_,w/prs.sh").read_text()
        assert 'bash "$(dirname "$0")/mv.sh"' in source
        assert (
            '_add_worktree_tmux_session "$quiet_mode" "$parent_name" "$local_branch" "$existing_path"\n'
            '    if [ "$focus_mode" -eq 1 ]; then'
        ) in source

    def test_pr_retry_repairs_session_after_new_session_failure(self):
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

            shutil.copyfile(REPO / "home/exact_lib/exact_,w/prs.sh", w_dir / "prs.sh")
            (w_dir / "prs.sh").chmod(0o444)
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

            tmux_session = root / "tmux-session"
            fail_once = root / "tmux-fail-once"
            tmux = bin_dir / "tmux"
            tmux.write_text(
                "#!/usr/bin/env bash\n"
                'case " $* " in\n'
                "  *' has-session '*) [[ -f \"$TMUX_SESSION_FILE\" ]] ;;\n"
                "  *' new-session '*)\n"
                "    if [[ -f $TMUX_FAIL_ONCE_FILE ]]; then\n"
                '      rm -f "$TMUX_FAIL_ONCE_FILE"\n'
                "      exit 1\n"
                "    fi\n"
                '    : > "$TMUX_SESSION_FILE"\n'
                "    ;;\n"
                "esac\n"
            )
            tmux.chmod(0o755)

            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "commit.gpgSign", "false"], cwd=repo, check=True)
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
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bin_dir}:/opt/homebrew/bin:/usr/bin:/bin",
                "COMMA_W_PRUNE": "0",
                "OUTER_TMUX_SOCKET": str(root / "outer.sock"),
                "TMUX_SESSION_FILE": str(tmux_session),
                "TMUX_FAIL_ONCE_FILE": str(fail_once),
            }
            env.pop("TMUX", None)
            env.pop("TMUX_PANE", None)
            fail_once.write_text("fail\n")

            first = subprocess.run(
                [modern_bash(), str(w_dir / "prs.sh"), "-q", "123"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            assert first.returncode != 0, first.stderr
            assert not tmux_session.exists(), "failed PR new-session was reported as success"

            retry = subprocess.run(
                [modern_bash(), str(w_dir / "prs.sh"), "-q", "123"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            assert retry.returncode == 0, retry.stderr
            assert tmux_session.exists(), "existing PR worktree did not retry session creation"


if __name__ == "__main__":
    unittest.main()
