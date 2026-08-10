#!/usr/bin/env python3
"""Tests immutable GH picker dispatch state in batch worktree completion."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import TMUX_PICKERS, modern_bash


class TestGhPickerDispatchState(unittest.TestCase):
    """WHEN background batch worktree updates picker cache/reload state."""

    def _write_executable(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o755)

    def _run_background_batch(
        self, script: Path, selection_file: Path, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [modern_bash(), str(script), str(selection_file), "--background"],
            capture_output=True,
            text=True,
            env=env,
        )

    def _setup_fixture(self, tmp_path: Path) -> dict[str, Path]:
        home = tmp_path / "home"
        cache_home = tmp_path / "cache"
        cache_dir = cache_home / "tmux"
        cache_dir.mkdir(parents=True)
        (home / "bin").mkdir(parents=True)

        patcher = home / ".config/tmux/scripts/pickers/github/lib/gh_patch_picker_cache.py"
        self._write_executable(
            patcher,
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import argparse
                import os

                parser = argparse.ArgumentParser()
                parser.add_argument("--cache-file", required=True)
                parser.add_argument("--kind", required=True)
                parser.add_argument("--repo", required=True)
                parser.add_argument("--num", required=True)
                parser.add_argument("--state", required=True)
                args = parser.parse_args()

                with open(os.environ["PATCH_LOG"], "a", encoding="utf-8") as fh:
                    fh.write(
                        f"{args.cache_file}\\t{args.kind}\\t{args.repo}\\t{args.num}\\t{args.state}\\n"
                    )
                """
            ),
        )

        self._write_executable(
            home / "bin/,gh-worktree",
            "#!/usr/bin/env bash\nexit 0\n",
        )

        self._write_executable(
            home / "bin/curl",
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                printf '%s\\n' "$*" >> "$CURL_LOG"
                exit 0
                """
            ),
        )

        selection_file = tmp_path / "selection.tsv"
        selection_file.write_text("PR 123\tpr\towner/repo\t123\thttps://example.test/pr/123\n")

        work_cache = cache_dir / "gh_picker_work.tsv"
        home_cache = cache_dir / "gh_picker_home.tsv"
        work_cache.write_text("work-cache\n")
        home_cache.write_text("home-cache\n")

        return {
            "home": home,
            "cache_home": cache_home,
            "cache_dir": cache_dir,
            "selection_file": selection_file,
            "work_cache": work_cache,
            "home_cache": home_cache,
            "patch_log": tmp_path / "patch.log",
            "curl_log": tmp_path / "curl.log",
        }

    def test_background_completion_targets_origin_dispatch_not_latest_global_picker(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            cache_dir = fixture["cache_dir"]
            (cache_dir / "gh_picker_mode").write_text("home")
            (cache_dir / "gh_picker_scope").write_text("focus")
            (cache_dir / "gh_picker_port").write_text("5151")

            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = self._run_background_batch(script, fixture["selection_file"], env)
            assert result.returncode == 0, result.stderr

            patch_log = fixture["patch_log"].read_text()
            assert str(fixture["work_cache"]) in patch_log
            assert str(fixture["home_cache"]) not in patch_log

            curl_log = fixture["curl_log"].read_text()
            assert "127.0.0.1:4141" in curl_log
            assert "127.0.0.1:5151" not in curl_log
            assert "GH_PICKER_MODE=work" in curl_log
            assert "GH_PICKER_SCOPE=all" in curl_log
            assert "GH_PICKER_MODE=home" not in curl_log
            assert "GH_PICKER_SCOPE=focus" not in curl_log

    def test_single_picker_fallback_still_uses_shared_global_state_when_dispatch_missing(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            cache_dir = fixture["cache_dir"]
            (cache_dir / "gh_picker_mode").write_text("home")
            (cache_dir / "gh_picker_scope").write_text("focus")
            (cache_dir / "gh_picker_port").write_text("5151")

            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }
            # Parent shells may export dispatch overrides from prior probes; the
            # fallback path must see a clean env so it reads the shared globals.
            for key in (
                "GH_PICKER_DISPATCH_MODE",
                "GH_PICKER_DISPATCH_SCOPE",
                "GH_PICKER_DISPATCH_PORT",
                "GH_PICKER_DISPATCH_CACHE_FILE",
                "FZF_PORT",
                "FZF_SOCK",
            ):
                env.pop(key, None)

            result = self._run_background_batch(script, fixture["selection_file"], env)
            assert result.returncode == 0, result.stderr

            patch_log = fixture["patch_log"].read_text()
            assert str(fixture["home_cache"]) in patch_log
            assert str(fixture["work_cache"]) not in patch_log

            curl_log = fixture["curl_log"].read_text()
            assert "127.0.0.1:5151" in curl_log
            assert "GH_PICKER_MODE=home" in curl_log
            assert "GH_PICKER_SCOPE=focus" in curl_log

    def test_foreground_dispatch_uses_nohup_not_run_shell_b(self):
        script = (TMUX_PICKERS / "github/executable_gh_batch_worktree.sh").read_text()
        assert "_dispatch_background" in script
        assert "nohup env -u TMUX -u TMUX_PANE" in script
        # Detached batch must not rely on pane-scoped run-shell -b (dies on popup close).
        assert 'tmux run-shell -b "$(printf %q "$0")' not in script

    def test_foreground_dispatch_preserves_current_tmux_socket(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            nohup_log = Path(tmp) / "nohup.log"
            self._write_executable(
                fixture["home"] / "bin/nohup",
                '#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" > "$NOHUP_LOG"\n',
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "NOHUP_LOG": str(nohup_log),
                "TMUX": "/private/tmp/tmux-fixture/default,123,0",
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }
            env.pop("OUTER_TMUX_SOCKET", None)

            result = subprocess.run(
                [modern_bash(), str(script), str(fixture["selection_file"])],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0, result.stderr
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and not nohup_log.exists():
                time.sleep(0.02)
            assert nohup_log.exists(), "foreground dispatch never invoked nohup"
            assert "OUTER_TMUX_SOCKET=/private/tmp/tmux-fixture/default" in nohup_log.read_text()

    def test_foreground_dispatch_preserves_explicit_outer_tmux_socket(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            nohup_log = Path(tmp) / "nohup.log"
            self._write_executable(
                fixture["home"] / "bin/nohup",
                '#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" > "$NOHUP_LOG"\n',
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "NOHUP_LOG": str(nohup_log),
                "TMUX": "/private/tmp/nested/default,123,0",
                "OUTER_TMUX_SOCKET": "/private/tmp/outer/default",
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = subprocess.run(
                [modern_bash(), str(script), str(fixture["selection_file"])],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0, result.stderr
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and not nohup_log.exists():
                time.sleep(0.02)
            assert nohup_log.exists(), "foreground dispatch never invoked nohup"
            assert "OUTER_TMUX_SOCKET=/private/tmp/outer/default" in nohup_log.read_text()

    def test_branch_agent_uses_deepseek_max_effort(self):
        script = (TMUX_PICKERS / "github/executable_gh_batch_worktree.sh").read_text()
        assert (
            'exec ,cursor-openrouter --model deepseek/deepseek-v4-flash-0731 --effort max -- "$(cat "$1")"'
        ) in script

    def test_foreground_issue_editor_exit_dispatches_every_worktree(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            worktree_log = Path(tmp) / "worktree.log"
            editor = fixture["home"] / "bin/fake-editor"
            self._write_executable(
                editor,
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    file="$1"
                    tmp="${file}.edited"
                    awk '/^#/ { print; next } /\\|$/ { print $0 "fix/test/generated"; next } { print }' "$file" > "$tmp"
                    mv "$tmp" "$file"
                    """
                ),
            )
            self._write_executable(
                fixture["home"] / "bin/gh",
                "#!/usr/bin/env bash\nprintf 'fixture issue title\\n'\n",
            )
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    printf '%s\\n' "$*" >> "$WORKTREE_LOG"
                    if [[ "$*" == *--print-root* ]]; then
                      printf '/tmp/fixture-root\\n'
                    fi
                    """
                ),
            )
            selection = fixture["selection_file"]
            selection.write_text(
                "Issue A\tissue\towner/repo-a\t1\thttps://example.test/a/1\n"
                "Issue B\tissue\towner/repo-b\t1\thttps://example.test/b/1\n"
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "WORKTREE_LOG": str(worktree_log),
                "EDITOR": str(editor),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:/opt/homebrew/bin:/usr/bin:/bin:{os.environ['PATH']}",
            }

            result = subprocess.run(
                [modern_bash(), str(script), str(selection)],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0, result.stderr

            deadline = time.monotonic() + 5
            calls: list[str] = []
            while time.monotonic() < deadline:
                if worktree_log.exists():
                    calls = worktree_log.read_text().splitlines()
                    if len(calls) >= 4 and not selection.exists():
                        break
                time.sleep(0.05)

            assert sorted((call.split()[1], call.split()[2]) for call in calls if "--print-root" in call) == [
                ("owner/repo-a", "1"),
                ("owner/repo-b", "1"),
            ], calls
            assert sorted((call.split()[1], call.split()[2]) for call in calls if "--quiet" in call) == [
                ("owner/repo-a", "1"),
                ("owner/repo-b", "1"),
            ], calls
            assert not selection.exists(), "detached batch never consumed the picker snapshot"

    def test_detached_batch_has_timeout_and_ledger_recovery(self):
        script = (TMUX_PICKERS / "github/executable_gh_batch_worktree.sh").read_text()
        assert "GH_BATCH_ITEM_TIMEOUT_SECS" in script
        assert "GH_BATCH_TOTAL_TIMEOUT_SECS" in script
        assert "--kill-after=10s" in script
        assert "gh_batch_worktree_jobs" in script
        assert "_reap_stale_batch_jobs" in script
        assert "_finalize_batch_jobs" in script
        assert "_wait_for_creates" in script
        assert 'for i in "${!prs[@]}"; do\n  _batch_can_launch || break' in script
        assert (
            'for entry in "${issue_branches[@]+"${issue_branches[@]}"}"; do\n  _batch_can_launch || break'
        ) in script
        reap_source = script.split("_reap_ledger_file() {", 1)[1].split("\n}", 1)[0]
        assert '_ledger_lock_acquire "$ledger"' in reap_source
        assert '_ledger_lock_release "$ledger"' in reap_source

    def test_background_serializes_worktree_creates(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            timing_log = Path(tmp) / "timing.log"
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    if {{ : <&9; }} 2>/dev/null; then
                      printf 'fd-open\\n' >> {shlex.quote(str(timing_log))}
                      exit 99
                    fi
                    if [[ "$*" == *--print-root* ]]; then
                      exit 0
                    fi
                    printf 'start %s\\n' "$$" >> {shlex.quote(str(timing_log))}
                    sleep 0.35
                    printf 'end %s\\n' "$$" >> {shlex.quote(str(timing_log))}
                    exit 0
                    """
                ),
            )
            selection = fixture["selection_file"]
            selection.write_text(
                "PR 1\tpr\towner/repo\t1\thttps://example.test/1\nPR 2\tpr\towner/repo\t2\thttps://example.test/2\n"
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = self._run_background_batch(script, selection, env)
            assert result.returncode == 0, result.stderr

            lines = timing_log.read_text().splitlines()
            starts = [line for line in lines if line.startswith("start ")]
            ends = [line for line in lines if line.startswith("end ")]
            assert len(starts) == 2
            assert len(ends) == 2
            assert [line.split()[0] for line in lines] == ["start", "end", "start", "end"], lines

    def test_background_reload_closes_cross_batch_lock_fd(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            curl_fd_log = Path(tmp) / "curl-fd.log"
            self._write_executable(
                fixture["home"] / "bin/curl",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    if {{ : <&9; }} 2>/dev/null; then
                      printf 'fd-open\n' >> {shlex.quote(str(curl_fd_log))}
                    else
                      printf 'fd-closed\n' >> {shlex.quote(str(curl_fd_log))}
                    fi
                    sleep 0.2
                    """
                ),
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = self._run_background_batch(script, fixture["selection_file"], env)
            assert result.returncode == 0, result.stderr
            deadline = time.monotonic() + 2
            states: list[str] = []
            while time.monotonic() < deadline:
                if curl_fd_log.exists():
                    states = curl_fd_log.read_text().splitlines()
                    if len(states) >= 2:
                        break
                time.sleep(0.02)

            assert len(states) >= 2, states
            assert set(states) == {"fd-closed"}, states

    def test_loading_spinner_closes_cross_batch_lock_fd(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            spinner_fd_log = Path(tmp) / "spinner-fd.log"
            row_loader = fixture["home"] / ".config/tmux/scripts/pickers/github/lib/gh_row_loader.sh"
            self._write_executable(
                row_loader,
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    gh_row_loader_start_item() {
                      (
                        if { : <&9; } 2>/dev/null; then
                          printf 'fd-open\n' >> "$SPINNER_FD_LOG"
                        else
                          printf 'fd-closed\n' >> "$SPINNER_FD_LOG"
                        fi
                        sleep 5
                      ) &
                      gh_row_loader_last_pid=$!
                    }
                    gh_row_loader_stop_spinner() {
                      kill "${1:-}" 2>/dev/null || true
                      wait "${1:-}" 2>/dev/null || true
                    }
                    """
                ),
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "SPINNER_FD_LOG": str(spinner_fd_log),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = self._run_background_batch(script, fixture["selection_file"], env)
            assert result.returncode == 0, result.stderr
            assert spinner_fd_log.read_text().splitlines() == ["fd-closed"]

    def test_background_serializes_issue_worktree_creates(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            timing_log = Path(tmp) / "timing.log"
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    if {{ : <&9; }} 2>/dev/null; then
                      printf 'fd-open\\n' >> {shlex.quote(str(timing_log))}
                      exit 99
                    fi
                    if [[ "$*" == *--print-root* ]]; then
                      exit 0
                    fi
                    printf 'start %s\\n' "${{3}}" >> {shlex.quote(str(timing_log))}
                    sleep 0.35
                    printf 'end %s\\n' "${{3}}" >> {shlex.quote(str(timing_log))}
                    """
                ),
            )
            selection = fixture["selection_file"]
            selection.write_text(
                "Issue 1\tissue\towner/repo\t1\thttps://example.test/1\n"
                "Issue 2\tissue\towner/repo\t2\thttps://example.test/2\n"
            )
            branches = Path(tmp) / "branches.conf"
            branches.write_text("owner/repo#1|fix/one\nowner/repo#2|fix/two\n")
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = subprocess.run(
                [modern_bash(), str(script), str(selection), "--background", "--branches-file", str(branches)],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0, result.stderr
            assert [line.split()[0] for line in timing_log.read_text().splitlines()] == [
                "start",
                "end",
                "start",
                "end",
            ]

    def test_total_deadline_is_shared_and_stops_later_launches(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            timing_log = Path(tmp) / "timing.log"
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    if [[ "$*" == *--print-root* ]]; then
                      exit 0
                    fi
                    printf 'start %s\\n' "${{3}}" >> {shlex.quote(str(timing_log))}
                    if [[ "${{3}}" == 1 ]]; then
                      sleep 2
                    else
                      sleep 3
                    fi
                    printf 'end %s\\n' "${{3}}" >> {shlex.quote(str(timing_log))}
                    """
                ),
            )
            selection = fixture["selection_file"]
            selection.write_text(
                "".join(f"PR {n}\tpr\towner/repo\t{n}\thttps://example.test/{n}\n" for n in range(1, 4))
                + "Issue 4\tissue\towner/repo\t4\thttps://example.test/4\n"
            )
            branches = Path(tmp) / "branches.conf"
            branches.write_text("owner/repo#4|fix/four\n")
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "GH_BATCH_ITEM_TIMEOUT_SECS": "10",
                "GH_BATCH_TOTAL_TIMEOUT_SECS": "4",
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = subprocess.run(
                [modern_bash(), str(script), str(selection), "--background", "--branches-file", str(branches)],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0, result.stderr
            lines = timing_log.read_text().splitlines()
            assert "start 1" in lines
            assert "end 1" in lines
            assert "start 2" in lines
            assert "end 2" not in lines
            assert "start 3" not in lines
            assert "start 4" not in lines

    def test_wait_marks_timeout_when_last_child_exits_on_deadline(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"
        probe = r"""
set -euo pipefail
eval "$(sed -n '/^_wait_for_creates()/,/^}/p' "$1")"
pids=()
batch_deadline=5
batch_timed_out=0
SECONDS=5
_wait_for_creates
printf '%s\n' "$batch_timed_out"
"""
        result = subprocess.run(
            [modern_bash(), "-c", probe, "fixture", str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "1"

    def test_batch_launch_guard_rechecks_deadline(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"
        probe = r"""
set -euo pipefail
eval "$(sed -n '/^_batch_can_launch()/,/^}/p' "$1")"
batch_deadline=5
batch_timed_out=0
SECONDS=5
if _batch_can_launch; then
  printf 'launched\n'
else
  printf '%s\n' "$batch_timed_out"
fi
"""
        result = subprocess.run(
            [modern_bash(), "-c", probe, "fixture", str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "1"

    def test_pid_start_identity_fails_open_when_ps_is_unavailable(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"
        with tempfile.TemporaryDirectory() as tmp:
            fake_ps = Path(tmp) / "ps"
            self._write_executable(fake_ps, "#!/usr/bin/env bash\nexit 1\n")
            probe = r"""
set -euo pipefail
eval "$(sed -n '/^_pid_start_identity()/,/^}/p' "$1")"
_pid_start_identity 12345
printf 'survived\n'
"""
            result = subprocess.run(
                [modern_bash(), "-c", probe, "fixture", str(script)],
                capture_output=True,
                text=True,
                env={**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}"},
            )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "survived"

    def test_active_ledger_records_process_start_identity(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            self._write_executable(
                fixture["home"] / "bin/ps",
                "#!/usr/bin/env bash\n"
                "if [[ \"$*\" == *lstart=* ]]; then printf 'fixture-start\\n'; exit 0; fi\n"
                'exec /bin/ps "$@"\n',
            )
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                '#!/usr/bin/env bash\nif [[ "$*" == *--print-root* ]]; then exit 0; fi\nsleep 1\n',
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }
            proc = subprocess.Popen(
                [modern_bash(), str(script), str(fixture["selection_file"]), "--background"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            ledger_row = ""
            deadline = time.monotonic() + 2
            ledger_dir = fixture["cache_dir"] / "gh_batch_worktree_jobs"
            while time.monotonic() < deadline:
                ledgers = list(ledger_dir.glob("*.tsv"))
                if ledgers:
                    ledger_row = ledgers[0].read_text().rstrip("\n")
                    if ledger_row:
                        break
                time.sleep(0.02)
            stdout, stderr = proc.communicate(timeout=5)
            assert proc.returncode == 0, (stdout, stderr)

        fields = ledger_row.split("\t")
        assert len(fields) == 7, ledger_row
        assert fields[4] == "fixture-start", ledger_row

    def test_parent_death_during_ledger_publication_keeps_next_batch_locked(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            publication_log = Path(tmp) / "publication.log"
            release_publication = Path(tmp) / "release-publication"
            worktree_log = Path(tmp) / "worktree.log"
            self._write_executable(
                fixture["home"] / "bin/ps",
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    if [[ "$*" == *lstart=* ]]; then
                      printf '%s\n' "$PPID" >> "$PUBLICATION_LOG"
                      while [ ! -f "$RELEASE_PUBLICATION" ]; do sleep 0.02; done
                      printf 'fixture-start\n'
                      exit 0
                    fi
                    exec /bin/ps "$@"
                    """
                ),
            )
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    if [[ "$*" == *--print-root* ]]; then exit 0; fi
                    printf 'start %s\n' "${3:-}" >> "$WORKTREE_LOG"
                    sleep 0.4
                    printf 'end %s\n' "${3:-}" >> "$WORKTREE_LOG"
                    """
                ),
            )
            first = fixture["selection_file"]
            first.write_text("PR 1\tpr\towner/repo\t1\thttps://example.test/1\n")
            second = Path(tmp) / "selection-second.tsv"
            second.write_text("PR 2\tpr\towner/repo\t2\thttps://example.test/2\n")
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "PUBLICATION_LOG": str(publication_log),
                "RELEASE_PUBLICATION": str(release_publication),
                "WORKTREE_LOG": str(worktree_log),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "GH_BATCH_TOTAL_TIMEOUT_SECS": "10",
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }
            first_proc = subprocess.Popen(
                [modern_bash(), str(script), str(first), "--background"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            second_proc: subprocess.Popen[str] | None = None
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if publication_log.exists() and publication_log.read_text().splitlines():
                        break
                    time.sleep(0.02)
                assert publication_log.exists(), "first create never reached ledger publication"
                assert len(publication_log.read_text().splitlines()) == 1

                first_proc.kill()
                first_proc.communicate(timeout=3)
                second_proc = subprocess.Popen(
                    [modern_bash(), str(script), str(second), "--background"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                )
                time.sleep(0.35)
                assert len(publication_log.read_text().splitlines()) == 1, (
                    "second batch passed the global lock before the orphan's ledger row was durable"
                )

                release_publication.touch()
                stdout, stderr = second_proc.communicate(timeout=10)
                assert second_proc.returncode == 0, (stdout, stderr)
            finally:
                release_publication.touch()
                if first_proc.poll() is None:
                    first_proc.kill()
                    first_proc.communicate(timeout=3)
                if second_proc is not None and second_proc.poll() is None:
                    second_proc.kill()
                    second_proc.communicate(timeout=3)

    def test_parent_death_during_ledger_drop_keeps_next_batch_locked(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            drop_started = Path(tmp) / "drop-started"
            release_drop = Path(tmp) / "release-drop"
            worktree_log = Path(tmp) / "worktree.log"
            self._write_executable(
                fixture["home"] / "bin/mv",
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    target="${@: -1}"
                    if [[ "$target" == */gh_batch_worktree_jobs/*.tsv ]] && [ ! -f "$RELEASE_DROP" ]; then
                      : > "$DROP_STARTED"
                      while [ ! -f "$RELEASE_DROP" ]; do sleep 0.02; done
                    fi
                    exec /bin/mv "$@"
                    """
                ),
            )
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    if [[ "$*" == *--print-root* ]]; then exit 0; fi
                    printf 'start %s\n' "${3:-}" >> "$WORKTREE_LOG"
                    """
                ),
            )
            first = fixture["selection_file"]
            first.write_text("PR 1\tpr\towner/repo\t1\thttps://example.test/1\n")
            second = Path(tmp) / "selection-second.tsv"
            second.write_text("PR 2\tpr\towner/repo\t2\thttps://example.test/2\n")
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "DROP_STARTED": str(drop_started),
                "RELEASE_DROP": str(release_drop),
                "WORKTREE_LOG": str(worktree_log),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "GH_BATCH_TOTAL_TIMEOUT_SECS": "10",
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }
            first_proc = subprocess.Popen(
                [modern_bash(), str(script), str(first), "--background"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            second_proc: subprocess.Popen[str] | None = None
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and not drop_started.exists():
                    time.sleep(0.02)
                assert drop_started.exists(), "first create never reached ledger drop"

                first_proc.kill()
                first_proc.communicate(timeout=3)
                second_proc = subprocess.Popen(
                    [modern_bash(), str(script), str(second), "--background"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                )
                time.sleep(0.35)
                assert worktree_log.read_text().splitlines() == ["start 1"], (
                    "second batch passed the global lock while the orphan was dropping its ledger"
                )

                release_drop.touch()
                stdout, stderr = second_proc.communicate(timeout=10)
                assert second_proc.returncode == 0, (stdout, stderr)
                assert worktree_log.read_text().splitlines() == ["start 1", "start 2"]
            finally:
                release_drop.touch()
                if first_proc.poll() is None:
                    first_proc.kill()
                    first_proc.communicate(timeout=3)
                if second_proc is not None and second_proc.poll() is None:
                    second_proc.kill()
                    second_proc.communicate(timeout=3)

    def test_ledgerless_lockdir_for_reused_batch_pid_is_reaped(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            worktree_log = Path(tmp) / "worktree.log"
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                '#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> "$WORKTREE_LOG"\n',
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "WORKTREE_LOG": str(worktree_log),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }
            launcher = "\n".join(
                (
                    "set -euo pipefail",
                    'ledger_dir="$XDG_CACHE_HOME/tmux/gh_batch_worktree_jobs"',
                    'mkdir -p "$ledger_dir/$$.tsv.lockdir"',
                    f"exec {shlex.quote(modern_bash())} {shlex.quote(str(script))} "
                    f"{shlex.quote(str(fixture['selection_file']))} --background",
                )
            )
            result = subprocess.run(
                [modern_bash(), "-c", launcher],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            assert result.returncode == 0, result.stderr
            assert any("--quiet" in call for call in worktree_log.read_text().splitlines())
            ledger_dir = fixture["cache_dir"] / "gh_batch_worktree_jobs"
            assert not list(ledger_dir.glob("*.lockdir")), list(ledger_dir.glob("*.lockdir"))

    def test_separate_background_batches_share_one_create_lock(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            timing_log = Path(tmp) / "timing.log"
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    if [[ "$*" == *--print-root* ]]; then
                      exit 0
                    fi
                    printf 'start %s\\n' "${{3}}" >> {shlex.quote(str(timing_log))}
                    sleep 0.6
                    printf 'end %s\\n' "${{3}}" >> {shlex.quote(str(timing_log))}
                    """
                ),
            )
            first = fixture["selection_file"]
            first.write_text("PR 1\tpr\towner/repo\t1\thttps://example.test/1\n")
            second = Path(tmp) / "selection-second.tsv"
            second.write_text("PR 2\tpr\towner/repo\t2\thttps://example.test/2\n")
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }
            first_proc = subprocess.Popen(
                [modern_bash(), str(script), str(first), "--background"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            time.sleep(0.05)
            second_proc = subprocess.Popen(
                [modern_bash(), str(script), str(second), "--background"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            first_stdout, first_stderr = first_proc.communicate(timeout=10)
            second_stdout, second_stderr = second_proc.communicate(timeout=10)
            assert first_proc.returncode == 0, (first_stdout, first_stderr)
            assert second_proc.returncode == 0, (second_stdout, second_stderr)
            assert [line.split()[0] for line in timing_log.read_text().splitlines()] == [
                "start",
                "end",
                "start",
                "end",
            ]

    def test_queued_batch_wait_counts_against_total_deadline(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            timing_log = Path(tmp) / "timing.log"
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    if [[ "$*" == *--print-root* ]]; then
                      exit 0
                    fi
                    printf 'start %s\\n' "${{3}}" >> {shlex.quote(str(timing_log))}
                    sleep 3
                    printf 'end %s\\n' "${{3}}" >> {shlex.quote(str(timing_log))}
                    """
                ),
            )
            first = fixture["selection_file"]
            first.write_text("PR 1\tpr\towner/repo\t1\thttps://example.test/1\n")
            second = Path(tmp) / "selection-second.tsv"
            second.write_text("PR 2\tpr\towner/repo\t2\thttps://example.test/2\n")
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "GH_BATCH_ITEM_TIMEOUT_SECS": "10",
                "GH_BATCH_TOTAL_TIMEOUT_SECS": "10",
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }
            first_proc = subprocess.Popen(
                [modern_bash(), str(script), str(first), "--background"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if timing_log.exists() and "start 1" in timing_log.read_text().splitlines():
                    break
                time.sleep(0.02)
            else:
                first_proc.kill()
                first_proc.communicate(timeout=2)
                self.fail("first batch never acquired the create lock")

            second_env = {**env, "GH_BATCH_TOTAL_TIMEOUT_SECS": "1"}
            second_result = self._run_background_batch(script, second, second_env)
            try:
                assert second_result.returncode == 0, second_result.stderr
                assert first_proc.poll() is None, "queued batch outlived the batch holding the lock"
                assert "start 2" not in timing_log.read_text().splitlines()
            finally:
                first_stdout, first_stderr = first_proc.communicate(timeout=10)
                assert first_proc.returncode == 0, (first_stdout, first_stderr)

    def test_multiple_creates_never_clear_done_markers(self):
        # Every successful item must retain its done marker after finalization.
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    if [[ "$*" == *--print-root* ]]; then
                      exit 0
                    fi
                    sleep 0.2
                    exit 0
                    """
                ),
            )
            selection = fixture["selection_file"]
            selection.write_text(
                "".join(f"PR {n}\tpr\towner/repo\t{n}\thttps://example.test/{n}\n" for n in range(1, 6))
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = self._run_background_batch(script, selection, env)
            assert result.returncode == 0, result.stderr

            patch_log = fixture["patch_log"].read_text().splitlines()
            done = [line for line in patch_log if line.endswith("\tdone")]
            cleared = [line for line in patch_log if line.endswith("\tclear")]
            assert len(done) == 5, patch_log
            assert cleared == [], patch_log

    def test_failed_create_does_not_cancel_siblings_or_next_batch(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    if [[ "$*" == *--print-root* ]]; then
                      exit 0
                    fi
                    if [[ ${3:-} == 2 ]]; then
                      exit 1
                    fi
                    exit 0
                    """
                ),
            )
            first = fixture["selection_file"]
            first.write_text("".join(f"PR {n}\tpr\towner/repo\t{n}\thttps://example.test/{n}\n" for n in range(1, 4)))
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:{os.environ['PATH']}",
            }

            result = self._run_background_batch(script, first, env)
            assert result.returncode == 0, result.stderr

            second = Path(tmp) / "selection-next.tsv"
            second.write_text("PR 4\tpr\towner/repo\t4\thttps://example.test/4\n")
            result = self._run_background_batch(script, second, env)
            assert result.returncode == 0, result.stderr

            patch_log = fixture["patch_log"].read_text().splitlines()
            done_nums = sorted(line.split("\t")[3] for line in patch_log if line.endswith("\tdone"))
            clear_nums = sorted(line.split("\t")[3] for line in patch_log if line.endswith("\tclear"))
            assert done_nums == ["1", "3", "4"], patch_log
            assert clear_nums == ["2"], patch_log
            ledger_dir = fixture["cache_dir"] / "gh_batch_worktree_jobs"
            assert not list(ledger_dir.glob("*.tsv")), list(ledger_dir.glob("*.tsv"))

    def test_item_timeout_clears_loading_marker_and_exits(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"
        timeout_bin = next(
            (
                p
                for p in ("/opt/homebrew/bin/timeout", "/usr/bin/timeout", "timeout")
                if Path(p).exists() or p == "timeout"
            ),
            None,
        )
        if timeout_bin is None:
            self.skipTest("timeout binary unavailable")

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            hang_log = Path(tmp) / "hang.log"
            self._write_executable(
                fixture["home"] / "bin/,gh-worktree",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    printf 'call %s\\n' "$*" >> {shlex.quote(str(hang_log))}
                    if [[ "$*" == *--print-root* ]]; then
                      exit 0
                    fi
                    printf 'hang\\n' >> {shlex.quote(str(hang_log))}
                    while :; do sleep 60; done
                    """
                ),
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                # Keep short enough to prove timeout recovery, long enough that a
                # loaded parallel test worker can still finish --print-root first.
                "GH_BATCH_ITEM_TIMEOUT_SECS": "2",
                "GH_BATCH_TOTAL_TIMEOUT_SECS": "8",
                "PATH": f"{fixture['home'] / 'bin'}:/opt/homebrew/bin:/usr/bin:/bin:{os.environ['PATH']}",
            }

            result = self._run_background_batch(script, fixture["selection_file"], env)
            assert result.returncode == 0, result.stderr
            assert hang_log.exists(), "stub ,gh-worktree never ran"
            assert "hang" in hang_log.read_text(), hang_log.read_text()
            patch_log = fixture["patch_log"].read_text().splitlines()
            assert any(line.endswith("\tclear") for line in patch_log), patch_log
            assert not any(line.endswith("\tdone") for line in patch_log), patch_log
            ledger_dir = fixture["cache_dir"] / "gh_batch_worktree_jobs"
            assert not list(ledger_dir.glob("*.tsv")), list(ledger_dir.glob("*.tsv"))

    def test_stale_job_ledger_reaped_when_batch_pid_dead(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            ledger_dir = fixture["cache_dir"] / "gh_batch_worktree_jobs"
            ledger_dir.mkdir(parents=True)
            # PID 1 is not our batch; kill -0 succeeds for init, so pick a pid that
            # is guaranteed dead: allocate and free a subprocess pid.
            dead = subprocess.Popen(["bash", "-c", "exit 0"])
            dead.wait(timeout=2)
            dead_pid = dead.pid
            (ledger_dir / f"{dead_pid}.tsv").write_text(
                self._ledger_row(dead_pid, "pr", "owner/repo", "123", "dead-start"), encoding="utf-8"
            )
            env = {
                **os.environ,
                "HOME": str(fixture["home"]),
                "XDG_CACHE_HOME": str(fixture["cache_home"]),
                "PATCH_LOG": str(fixture["patch_log"]),
                "CURL_LOG": str(fixture["curl_log"]),
                "GH_PICKER_DISPATCH_MODE": "work",
                "GH_PICKER_DISPATCH_SCOPE": "all",
                "GH_PICKER_DISPATCH_PORT": "4141",
                "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
                "PATH": f"{fixture['home'] / 'bin'}:/opt/homebrew/bin:/usr/bin:/bin:{os.environ['PATH']}",
            }

            result = self._run_background_batch(script, fixture["selection_file"], env)
            assert result.returncode == 0, result.stderr
            assert not (ledger_dir / f"{dead_pid}.tsv").exists()
            patch_log = fixture["patch_log"].read_text()
            assert "owner/repo\t123\tclear" in patch_log

    def _stale_ledger_env(self, fixture: dict[str, Path]) -> dict[str, str]:
        return {
            **os.environ,
            "HOME": str(fixture["home"]),
            "XDG_CACHE_HOME": str(fixture["cache_home"]),
            "PATCH_LOG": str(fixture["patch_log"]),
            "CURL_LOG": str(fixture["curl_log"]),
            "GH_PICKER_DISPATCH_MODE": "work",
            "GH_PICKER_DISPATCH_SCOPE": "all",
            "GH_PICKER_DISPATCH_PORT": "4141",
            "GH_PICKER_DISPATCH_CACHE_FILE": str(fixture["work_cache"]),
            "PATH": f"{fixture['home'] / 'bin'}:/opt/homebrew/bin:/usr/bin:/bin:{os.environ['PATH']}",
        }

    def _dead_pid(self) -> int:
        proc = subprocess.Popen(["bash", "-c", "exit 0"])
        proc.wait(timeout=2)
        return proc.pid

    def _ledger_row(
        self,
        create_pid: int,
        kind: str,
        repo: str,
        num: str,
        create_start: str,
        spinner_pid: str = "",
        spinner_start: str = "",
    ) -> str:
        return f"{create_pid}\t{kind}\t{repo}\t{num}\t{create_start}\t{spinner_pid}\t{spinner_start}\n"

    def _write_ps_identity_fixture(
        self, fixture: dict[str, Path], pid: int, start: str, args: str = "bash gh_batch_worktree.sh sel --background"
    ) -> None:
        self._write_executable(
            fixture["home"] / "bin/ps",
            textwrap.dedent(
                f"""\
                #!/usr/bin/env bash
                if [[ "$*" == *"-p {pid}"* ]]; then
                  if [[ "$*" == *"lstart="* ]]; then
                    printf '%s\\n' {shlex.quote(start)}
                  else
                    printf '%s\\n' {shlex.quote(args)}
                  fi
                  exit 0
                fi
                exec /bin/ps "$@"
                """
            ),
        )

    def test_stale_ledger_does_not_kill_pid_reused_by_innocent(self):
        # A stale ledger outlives its batch, so a recorded pid may belong to an
        # unrelated process by reap time. The reap must clear the marker but
        # leave processes whose argv is not a detached batch alone.
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            ledger_dir = fixture["cache_dir"] / "gh_batch_worktree_jobs"
            ledger_dir.mkdir(parents=True)
            innocent = subprocess.Popen(["sleep", "30"])
            try:
                (ledger_dir / f"{self._dead_pid()}.tsv").write_text(
                    self._ledger_row(innocent.pid, "pr", "owner/repo", "123", "stale-start"), encoding="utf-8"
                )
                result = self._run_background_batch(script, fixture["selection_file"], self._stale_ledger_env(fixture))
                assert result.returncode == 0, result.stderr
                assert innocent.poll() is None, "stale reap killed a pid-reused innocent process"
            finally:
                innocent.kill()
                innocent.wait(timeout=2)
            assert not list(ledger_dir.glob("*.tsv"))
            assert "owner/repo\t123\tclear" in fixture["patch_log"].read_text()

    def test_live_innocent_pid_in_ledger_filename_does_not_suppress_reap(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            ledger_dir = fixture["cache_dir"] / "gh_batch_worktree_jobs"
            ledger_dir.mkdir(parents=True)
            innocent = subprocess.Popen(["sleep", "30"])
            try:
                dead_pid = self._dead_pid()
                ledger = ledger_dir / f"{innocent.pid}.tsv"
                ledger.write_text(self._ledger_row(dead_pid, "pr", "owner/repo", "321", "dead-start"), encoding="utf-8")
                result = self._run_background_batch(script, fixture["selection_file"], self._stale_ledger_env(fixture))
                assert result.returncode == 0, result.stderr
                assert innocent.poll() is None, "reap killed the unrelated ledger-filename process"
                assert not ledger.exists(), "reused batch pid suppressed stale-ledger cleanup"
                assert "owner/repo\t321\tclear" in fixture["patch_log"].read_text()
            finally:
                innocent.kill()
                innocent.wait(timeout=2)

    def test_stale_ledger_kills_leftover_batch_lookalike(self):
        # The flip side: a live process that IS a detached batch subshell must
        # still be reaped, otherwise hung creates survive the recovery path.
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            ledger_dir = fixture["cache_dir"] / "gh_batch_worktree_jobs"
            ledger_dir.mkdir(parents=True)
            # `sleep 30 & wait` keeps bash alive; a bare `bash -c 'sleep 30'`
            # execs sleep and loses the marker argv the reap matches on.
            lookalike = subprocess.Popen(
                ["bash", "-c", "sleep 30 & wait", "gh_batch_worktree.sh", "sel", "--background"]
            )
            try:
                self._write_ps_identity_fixture(fixture, lookalike.pid, "fixture-start")
                (ledger_dir / f"{self._dead_pid()}.tsv").write_text(
                    self._ledger_row(lookalike.pid, "pr", "owner/repo", "123", "fixture-start"), encoding="utf-8"
                )
                env = self._stale_ledger_env(fixture)
                result = self._run_background_batch(script, fixture["selection_file"], env)
                assert result.returncode == 0, result.stderr
                lookalike.wait(timeout=5)
                assert lookalike.returncode is not None, "batch lookalike survived the stale reap"
            finally:
                if lookalike.poll() is None:
                    lookalike.kill()
                    lookalike.wait(timeout=2)

    def test_stale_ledger_does_not_kill_matching_argv_with_different_start(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            ledger_dir = fixture["cache_dir"] / "gh_batch_worktree_jobs"
            ledger_dir.mkdir(parents=True)
            lookalike = subprocess.Popen(
                ["bash", "-c", "sleep 30 & wait", "gh_batch_worktree.sh", "sel", "--background"]
            )
            try:
                self._write_ps_identity_fixture(fixture, lookalike.pid, "new-start")
                (ledger_dir / f"{self._dead_pid()}.tsv").write_text(
                    self._ledger_row(lookalike.pid, "pr", "owner/repo", "123", "old-start"), encoding="utf-8"
                )
                result = self._run_background_batch(script, fixture["selection_file"], self._stale_ledger_env(fixture))
                assert result.returncode == 0, result.stderr
                assert lookalike.poll() is None, "stale reap killed a same-argv process from a different start"
            finally:
                lookalike.kill()
                lookalike.wait(timeout=2)
            assert not list(ledger_dir.glob("*.tsv"))
            assert "owner/repo\t123\tclear" in fixture["patch_log"].read_text()

    def test_old_ledger_still_kills_identity_matching_leftover(self):
        script = TMUX_PICKERS / "github/executable_gh_batch_worktree.sh"

        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            ledger_dir = fixture["cache_dir"] / "gh_batch_worktree_jobs"
            ledger_dir.mkdir(parents=True)
            lookalike = subprocess.Popen(
                ["bash", "-c", "sleep 30 & wait", "gh_batch_worktree.sh", "sel", "--background"]
            )
            try:
                self._write_ps_identity_fixture(fixture, lookalike.pid, "fixture-start")
                ledger = ledger_dir / f"{self._dead_pid()}.tsv"
                ledger.write_text(
                    self._ledger_row(lookalike.pid, "pr", "owner/repo", "123", "fixture-start"), encoding="utf-8"
                )
                ancient = time.time() - (1800 + 600 + 300 + 60)
                os.utime(ledger, (ancient, ancient))
                env = self._stale_ledger_env(fixture)
                env["GH_BATCH_ITEM_TIMEOUT_SECS"] = "1"
                env["GH_BATCH_TOTAL_TIMEOUT_SECS"] = "1"
                result = self._run_background_batch(script, fixture["selection_file"], env)
                assert result.returncode == 0, result.stderr
                lookalike.wait(timeout=5)
                assert lookalike.returncode is not None, "old matching leftover survived stale reap"
            finally:
                if lookalike.poll() is None:
                    lookalike.kill()
                    lookalike.wait(timeout=2)
            assert not list(ledger_dir.glob("*.tsv"))
            assert "owner/repo\t123\tclear" in fixture["patch_log"].read_text()


if __name__ == "__main__":
    unittest.main()
