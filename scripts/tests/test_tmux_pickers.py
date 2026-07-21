#!/usr/bin/env python3
"""Tests for tmux picker shell helper behavior."""

from __future__ import annotations

import json
import os
import runpy
import shlex
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import (
    TMUX_PICKERS,
    modern_bash,
    run_bash,
)


class TestTmuxPickerShellHelpers(unittest.TestCase):
    """WHEN validating tmux picker shell helper contracts."""

    def test_snapshot_filters_headers_into_unique_cache_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            selection = tmp_path / "selection.tsv"
            selection.write_text(
                "Header\theader\t\t\t\t\n"
                "PR 1\tpr\t/path/one\t\turl-1\tmatch-one\n"
                "Issue 2\tissue\t/path/two\t\turl-2\tmatch-two\n"
            )
            env = {**os.environ, "XDG_CACHE_HOME": str(tmp_path / "cache")}
            script = TMUX_PICKERS / "lib/executable_snapshot_fzf_selection.sh"

            snapshots: list[Path] = []
            for _ in range(2):
                result = subprocess.run(
                    [modern_bash(), str(script), "--filter-awk", '$2 != "header"', str(selection)],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                assert result.returncode == 0, result.stderr
                snapshots.append(Path(result.stdout.strip()))

            assert snapshots[0] != snapshots[1]
            for snapshot in snapshots:
                assert snapshot.parent == tmp_path / "cache/tmux"
                assert snapshot.read_text() == (
                    "PR 1\tpr\t/path/one\t\turl-1\tmatch-one\nIssue 2\tissue\t/path/two\t\turl-2\tmatch-two\n"
                )

    def test_session_name_for_entry_uses_worktree_target_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = home / "repo"
            worktree = home / "repo-linked"
            (root / ".git/worktrees/linked").mkdir(parents=True)
            worktree.mkdir(parents=True)
            lib = TMUX_PICKERS / "session/lib/session_naming.sh"

            out = run_bash(
                "\n".join(
                    [
                        f". {shlex.quote(str(lib))}",
                        (
                            "session_name_for_entry worktree "
                            f"{shlex.quote(str(worktree))} "
                            "'wt:|repo=elastic/kibana' "
                            f"{shlex.quote(str(root))} "
                            "directory"
                        ),
                    ]
                ),
                env={"HOME": str(home)},
            )

            assert out == "elastic/kibana\n"

    def test_session_name_for_entry_matches_directory_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            project = home / "src/My Project"
            project.mkdir(parents=True)
            lib = TMUX_PICKERS / "session/lib/session_naming.sh"

            out = run_bash(
                "\n".join(
                    [
                        f". {shlex.quote(str(lib))}",
                        (f"session_name_for_entry dir {shlex.quote(str(project))} '' '' directory"),
                    ]
                ),
                env={"HOME": str(home)},
            )

            assert out == "my-project\n"

    def test_bag_rename_if_needed_moves_bagged_holder_aside(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            mock_bin = tmp_path / "bin"
            mock_bin.mkdir()
            rename_log = tmp_path / "rename.log"
            tmux = mock_bin / "tmux"
            tmux.write_text(
                """#!/usr/bin/env bash
case "$1" in
  has-session)
    case "${3#=}" in
      repo|repo@bag) exit 0 ;;
      *) exit 1 ;;
    esac
    ;;
  rename-session)
    printf '%s\t%s\n' "${3#=}" "$4" > "$TMUX_RENAME_LOG"
    exit 0
    ;;
  list-sessions)
    exit 0
    ;;
esac
exit 1
"""
            )
            tmux.chmod(0o755)
            lib = TMUX_PICKERS / "session/lib/session_naming.sh"

            out = run_bash(
                "\n".join(
                    [
                        f". {shlex.quote(str(lib))}",
                        'bag_rename_if_needed repo "$HOME/work/repo" "$HOME/.bag/worktree_remove/repo"',
                    ]
                ),
                env={
                    "HOME": str(home),
                    "PATH": f"{mock_bin}:{os.environ['PATH']}",
                    "TMUX_RENAME_LOG": str(rename_log),
                },
            )

            assert out == "repo\trepo@bag2\n"
            assert rename_log.read_text() == "repo\trepo@bag2\n"

    def test_remove_all_worktrees_keeps_independent_sibling_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = home / "work/kibana/main"
            sibling = home / "work/kibana/sibling-repo"
            notes = home / "work/kibana/notes"
            root.mkdir(parents=True)
            sibling.mkdir(parents=True)
            notes.mkdir()
            (notes / "keep.txt").write_text("keep\n")

            subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(root), "remote", "add", "origin", "git@github.com:elastic/kibana.git"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(["git", "init", str(sibling)], check=True, capture_output=True, text=True)

            script = TMUX_PICKERS / "session/executable_remove_all_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), str(root)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                },
            )

            assert result.returncode == 0, result.stderr
            assert not root.exists()
            assert (sibling / ".git").exists()
            assert (notes / "keep.txt").exists()
            assert not (home / "work/.bag/pickers/session/kibana").exists()

    def test_remove_all_worktrees_bags_leftovers_when_wrapper_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = home / "work/kibana/main"
            notes = home / "work/kibana/notes"
            root.mkdir(parents=True)
            notes.mkdir()
            (notes / "keep.txt").write_text("keep\n")

            subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(root), "remote", "add", "origin", "git@github.com:elastic/kibana.git"],
                check=True,
                capture_output=True,
                text=True,
            )

            script = TMUX_PICKERS / "session/executable_remove_all_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), str(root)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                },
            )

            assert result.returncode == 0, result.stderr
            assert not (home / "work/kibana").exists()
            bag_root = home / "work/.bag/pickers/session/kibana"
            bagged_notes = list(bag_root.glob("*/notes/keep.txt"))
            assert len(bagged_notes) == 1
            assert bagged_notes[0].read_text() == "keep\n"

    def test_action_remove_root_selection_tombstones_worktrees_not_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = home / "work/kibana/main"
            wrapper = home / "work/kibana"
            cache_dir = home / ".cache/tmux"
            cache_dir.mkdir(parents=True)
            root.mkdir(parents=True)
            root_rp = root.resolve()
            wrapper_rp = wrapper.resolve()

            subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(root), "remote", "add", "origin", "git@github.com:elastic/kibana.git"],
                check=True,
                capture_output=True,
                text=True,
            )

            selection = Path(tmp) / "selection.tsv"
            selection.write_text(f"main\tworktree\t{root}\twt_root:main\t{root}\n")

            script = TMUX_PICKERS / "session/executable_action_remove_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), str(selection)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "TMUX": "",
                },
            )

            assert result.returncode == 0, result.stderr
            pending = (cache_dir / "pick_session_pending.tsv").read_text()
            mutations = (cache_dir / "pick_session_mutations.tsv").read_text()
            assert f"WT\t{root_rp}\n" in pending
            assert f"WT\t{wrapper_rp}\n" not in pending
            assert f"\tPATH_PREFIX\t{root_rp}\n" in mutations
            assert f"\tPATH_PREFIX\t{wrapper_rp}\n" not in mutations

    def test_send_command_passes_cache_target_to_shared_naming(self):
        action = TMUX_PICKERS / "session/executable_action_send_command.sh"
        text = action.read_text()

        assert 'read -r kind path meta target <<< "$_entry"' in text
        assert 'session_name_for_entry "$kind" "$path" "$meta" "$target"' in text

    def test_when_tmux_restore_finishes_should_schedule_full_session_picker_reindex(self):
        plugins_conf = _test_support.REPO / "home/dot_config/exact_tmux/exact_conf.d/readonly_90-plugins.conf"
        text = plugins_conf.read_text()
        hook_line = next(line for line in text.splitlines() if "@resurrect-hook-post-restore-all" in line)
        fast_scan = "index_update.sh --force --quiet --skip-dirty --skip-gh"

        assert hook_line.startswith("set -g @resurrect-hook-post-restore-all ")
        assert "tmux run-shell -b" in hook_line
        assert hook_line.index("sleep 1;") < hook_line.index(fast_scan)
        assert hook_line.index(fast_scan) < hook_line.index("PICK_SESSION_THREADS=1")
        assert "--quick-only" not in hook_line

    def test_when_tmux_session_enumeration_fails_should_preserve_existing_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            cache_dir = root / "cache/tmux"
            session_scripts = home / ".config/tmux/scripts/pickers/session"
            fake_bin.mkdir()
            cache_dir.mkdir(parents=True)
            session_scripts.mkdir(parents=True)

            (session_scripts / "index.sh").symlink_to(TMUX_PICKERS / "session/executable_index.sh")
            (session_scripts / "lib").symlink_to(TMUX_PICKERS / "session/lib", target_is_directory=True)
            (home / ".config/tmux/pick_session_dir_exclude.txt").write_text("")

            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text("#!/usr/bin/env bash\nexit 1\n")
            fake_tmux.chmod(0o755)

            cache = cache_dir / "pick_session_items.tsv"
            original = (
                "existing-session\tsession\t/existing-session\t\texisting-session\n"
                "existing-worktree\tworktree\t/existing-worktree\t\texisting-worktree\n"
            )
            cache.write_text(original)
            result = subprocess.run(
                [
                    str(TMUX_PICKERS / "session/executable_index_update.sh"),
                    "--force",
                    "--quiet",
                    "--skip-dirty",
                    "--skip-gh",
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(root / "cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "unavailable",
                },
            )

            assert result.returncode != 0
            assert cache.read_text() == original

    def test_when_rehydrate_cannot_enumerate_sessions_should_keep_cached_session_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "bin"
            cache_dir = root / "cache/tmux"
            session_path = root / "live-session"
            fake_bin.mkdir()
            cache_dir.mkdir(parents=True)
            session_path.mkdir()

            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text("#!/usr/bin/env bash\nexit 1\n")
            fake_tmux.chmod(0o755)

            cache = cache_dir / "pick_session_items.tsv"
            cache.write_text(
                f"live-session\tsession\t{session_path}\t\tlive-session\tlive-session\n"
                "other-worktree\tworktree\t/other-worktree\t\t/other-worktree\tother-worktree\n"
            )
            (cache_dir / "pick_session_pending.tsv").write_text("WT\t/pending-removal\n")
            result = subprocess.run(
                [modern_bash(), str(TMUX_PICKERS / "session/executable_items.sh")],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "XDG_CACHE_HOME": str(root / "cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "unavailable",
                },
            )
            kinds = [line.split("\t")[1] for line in result.stdout.splitlines()]

            assert result.returncode == 0
            assert "session" in kinds

    def test_when_cache_changes_during_ordering_should_discard_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            session_scripts = home / ".config/tmux/scripts/pickers/session"
            cache_dir = root / "cache/tmux"
            session_scripts.mkdir(parents=True)
            cache_dir.mkdir(parents=True)

            captured = root / "captured.tsv"
            started = root / "started"
            release = root / "release"
            filter_script = session_scripts / "filter.sh"
            filter_script.write_text(
                "#!/usr/bin/env bash\n"
                'cp "$XDG_CACHE_HOME/tmux/pick_session_items.tsv" "$CAPTURED"\n'
                'touch "$STARTED"\n'
                'while [ ! -f "$RELEASE" ]; do sleep 0.01; done\n'
                'cat "$CAPTURED"\n'
            )
            filter_script.chmod(0o755)

            cache = cache_dir / "pick_session_items.tsv"
            cache.write_text("stale-worktree\tworktree\t/stale\t\t/stale\n")
            env = {
                **os.environ,
                "HOME": str(home),
                "XDG_CACHE_HOME": str(root / "cache"),
                "CAPTURED": str(captured),
                "STARTED": str(started),
                "RELEASE": str(release),
                "TMUX": "",
            }
            updater = subprocess.Popen(
                [
                    modern_bash(),
                    str(TMUX_PICKERS / "session/executable_ordered_cache_update.sh"),
                    "--quiet",
                ],
                env=env,
            )
            deadline = time.monotonic() + 2
            while not started.exists() and time.monotonic() < deadline:
                time.sleep(0.005)
            assert started.exists()

            cache.write_text(
                "live-session\tsession\t/live\t\tlive-session\nstale-worktree\tworktree\t/stale\t\t/stale\n"
            )
            release.touch()
            assert updater.wait(timeout=2) == 0
            assert not (cache_dir / "pick_session_items_ordered.tsv").exists()

    def test_when_query_settles_should_reload_one_offscreen_ranked_result(self):
        daemon = runpy.run_path(str(TMUX_PICKERS / "session/lib/sort_toggle_daemon.py"))
        runtime = daemon["run"].__globals__
        session = "ilm-session\tsession\t/session\t\t/session"
        directory = "ilm\tdir\t/directory\t\t/directory"

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.tsv"
            ranked = Path(tmp) / "ranked.tsv"
            source.write_text(f"{session}\n{directory}\n")
            actions: list[bytes] = []
            responses = iter(
                [
                    (200, json.dumps({"query": "ilm", "sort": False, "reading": False}).encode()),
                    (200, json.dumps({"query": "ilm", "sort": False, "reading": False}).encode()),
                    (200, json.dumps({"query": "ilm", "sort": False, "reading": False}).encode()),
                    (200, json.dumps({"query": "", "sort": False, "reading": False}).encode()),
                ]
            )

            class StopDaemon(BaseException):
                pass

            def http_get(_sock_path: str, _path: str) -> tuple[int, bytes]:
                try:
                    return next(responses)
                except StopIteration:
                    raise StopDaemon

            runtime["wait_for_socket"] = lambda _sock_path, _timeout_s: True
            runtime["http_get"] = http_get
            runtime["http_post_action"] = lambda _sock_path, action: actions.append(action) or 200
            runtime["fzf_ranked_matches"] = lambda _fzf_path, _source_rows, _query: [directory, session]
            runtime["DEBOUNCE_S"] = 0.0

            with self.assertRaises(StopDaemon):
                daemon["run"]("/tmp/fzf.sock", source, ranked, "/usr/bin/fzf")

            assert ranked.read_text() == f"{session}\n{directory}\n"
            assert len(actions) == 2
            assert all(action.startswith(b"reload-sync(cat ") for action in actions)
            assert all(action.endswith(b")+first") for action in actions)
            assert all(b"toggle-sort" not in action for action in actions)

    def test_when_fzf_ranks_folder_first_should_preserve_kind_priority(self):
        daemon = runpy.run_path(str(TMUX_PICKERS / "session/lib/sort_toggle_daemon.py"))
        session_weak = "i___l___m\tsession\t/session-weak\t\t/session-weak"
        session_strong = "\x1b[1;38;5;81milm-session\x1b[0m\tsession\t/session-strong\t\t/session-strong"
        session_strong_match = "ilm-session\tsession\t/session-strong\t\t/session-strong"
        session_nonmatch = "other\tsession\t/session-other\t\t/session-other"
        worktree = "ilm-worktree\tworktree\t/worktree\t\t/worktree"
        directory = "ilm\tdir\t/directory\t\t/directory"
        source_rows = [session_weak, session_strong, session_nonmatch, worktree, directory]
        fzf_matches = [directory, session_strong_match, worktree, session_weak]

        ranked = daemon["rank_rows_by_kind"](source_rows, fzf_matches)

        assert ranked == [session_strong, session_weak, session_nonmatch, worktree, directory]


if __name__ == "__main__":
    unittest.main()
