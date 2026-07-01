#!/usr/bin/env python3
"""Tests for tmux picker shell helper behavior."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
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

    def test_send_command_passes_cache_target_to_shared_naming(self):
        action = TMUX_PICKERS / "session/executable_action_send_command.sh"
        text = action.read_text()

        assert 'read -r kind path meta target <<< "$_entry"' in text
        assert 'session_name_for_entry "$kind" "$path" "$meta" "$target"' in text


if __name__ == "__main__":
    unittest.main()
