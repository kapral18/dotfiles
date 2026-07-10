#!/usr/bin/env python3
"""Regression tests for plain-directory session removal identity handling.

`executable_action_remove_worktrees.sh` routes some selected rows (sessions
with no git-backed worktree, orphaned/stale worktree dirs, and bare `dir`
zoxide rows) to `executable_remove_plain_dir.sh` in the background, with
`TMUX`/`TMUX_PANE` unset. Before the fix, `remove_plain_dir.sh` located the
session to kill by scanning `tmux list-sessions` gated on `[ -n "${TMUX:-}" ]`
-- a check that can never pass once TMUX is unset, so the matching session
was silently left running. The fix has the caller resolve explicit session
identities *before* unsetting TMUX and pass them through as an extra
argument. Distinct sessions can share one plain-dir path, so each selected
row's session name is carried in a parallel array aligned by index with
`pending_plain_dirs` -- not a path-keyed map (loses all but one name per
path) or a space-separated set (corrupts session names containing spaces).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import TMUX_PICKERS, modern_bash

ACTION_SCRIPT = TMUX_PICKERS / "session/executable_action_remove_worktrees.sh"

# Mock `tmux` used across this module: logs every `kill-session -t <name>`
# attempt to $KILL_LOG (one name per line) so tests can assert exactly which
# sessions were targeted, then simulates "no such session" for any name other
# than `alive-session` (mirroring a stale/already-gone session) without ever
# failing the caller (every real call site guards with `|| true`).
MOCK_TMUX = """#!/usr/bin/env bash
case "$1" in
  kill-session)
    name="$3"
    printf '%s\\n' "$name" >> "$KILL_LOG"
    case "$name" in
      alive-session) exit 0 ;;
      *) exit 1 ;;
    esac
    ;;
  display-message)
    exit 0
    ;;
  list-sessions)
    exit 1
    ;;
esac
exit 1
"""


def _wait_for(predicate, *, timeout=5.0, interval=0.05):
    """Poll `predicate` until truthy; the removal dispatch runs in the
    background (nohup'd, detached from the parent script), so callers must
    wait for its side effects rather than assume they land synchronously."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class TestPlainSessionRemoval(unittest.TestCase):
    """WHEN pick_session removes plain-directory rows backed by a tmux session."""

    def _run_removal(self, tmp: Path, home: Path, selection_lines: list[str]):
        cache_dir = home / ".cache/tmux"
        cache_dir.mkdir(parents=True)
        mock_bin = tmp / "bin"
        mock_bin.mkdir()
        kill_log = tmp / "kill.log"

        # `action_remove_worktrees.sh` dispatches plain-dir removal via a
        # hardcoded deployed path ($HOME/.config/tmux/scripts/...), matching
        # how it (and the sibling remove_all_worktrees.sh dispatch) run in
        # production. Reproduce that deployment shape for the real
        # (source-of-truth) remove_plain_dir.sh: chezmoi's `executable_`
        # prefix carries no `+x` bit in the source tree itself (git stores it
        # as 100644; chezmoi sets +x only when applying to $HOME), so a plain
        # symlink to the source file would not be runnable via its shebang.
        deployed_dir = home / ".config/tmux/scripts/pickers/session"
        deployed_dir.mkdir(parents=True)
        deployed_script = deployed_dir / "remove_plain_dir.sh"
        deployed_script.write_text((TMUX_PICKERS / "session/executable_remove_plain_dir.sh").read_text())
        deployed_script.chmod(0o755)

        tmux_mock = mock_bin / "tmux"
        tmux_mock.write_text(MOCK_TMUX)
        tmux_mock.chmod(0o755)

        selection = tmp / "selection.tsv"
        selection.write_text("".join(selection_lines))

        env = {
            **os.environ,
            "HOME": str(home),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "PATH": f"{mock_bin}:{os.environ['PATH']}",
            "KILL_LOG": str(kill_log),
            # Non-empty: the script only dispatches background removal when
            # it believes it's running inside an attached tmux client.
            "TMUX": "/tmp/mock-tmux-socket,1,0",
        }

        result = subprocess.run(
            [modern_bash(), str(ACTION_SCRIPT), str(selection)],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        return cache_dir, kill_log

    def test_matching_session_removed_and_unrelated_sessions_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            # Selected: a plain (non-git-backed) directory whose row carries an
            # explicit, currently-alive tmux session identity.
            target_dir = home / "plain/target-dir"
            target_dir.mkdir(parents=True)

            # Not selected at all: represents an unrelated, still-running
            # session/directory that must never be touched.
            untouched_dir = home / "plain/untouched-dir"
            untouched_dir.mkdir(parents=True)

            selection_lines = [
                f"row\tsession\t{target_dir}\tplain\talive-session\n",
            ]

            cache_dir, kill_log = self._run_removal(tmp_path, home, selection_lines)

            _wait_for(lambda: not target_dir.exists())

            assert not target_dir.exists(), "matching plain dir should be removed"
            assert untouched_dir.exists(), "unrelated dir/session must survive"

            kill_names = kill_log.read_text().splitlines() if kill_log.exists() else []
            assert kill_names == ["alive-session"], kill_names
            assert "unrelated-still-running" not in kill_names

    def test_missing_session_is_harmless_and_directory_still_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            ghost_dir = home / "plain/ghost-dir"
            ghost_dir.mkdir(parents=True)

            selection_lines = [
                f"row\tsession\t{ghost_dir}\tplain\tghost-session\n",
            ]

            cache_dir, kill_log = self._run_removal(tmp_path, home, selection_lines)

            _wait_for(lambda: not ghost_dir.exists())

            assert not ghost_dir.exists(), "dir removal must proceed even if the session is already gone"
            kill_names = kill_log.read_text().splitlines() if kill_log.exists() else []
            assert kill_names == ["ghost-session"]

    def test_plain_dir_row_without_session_identity_skips_kill_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            bare_dir = home / "plain/bare-dir"
            bare_dir.mkdir(parents=True)

            selection_lines = [
                f"row\tdir\t{bare_dir}\t\t\n",
            ]

            cache_dir, kill_log = self._run_removal(tmp_path, home, selection_lines)

            _wait_for(lambda: not bare_dir.exists())

            assert not bare_dir.exists()
            assert not kill_log.exists() or kill_log.read_text() == ""

    def test_two_selected_sessions_sharing_one_plain_dir_are_both_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            # Two distinct live tmux sessions can share the same cwd, so both
            # rows select the same plain dir under two different session names.
            shared_dir = home / "plain/shared-dir"
            shared_dir.mkdir(parents=True)

            # Not selected: an unrelated session/dir that must survive untouched.
            unrelated_dir = home / "plain/unrelated-dir"
            unrelated_dir.mkdir(parents=True)

            selection_lines = [
                f"row1\tsession\t{shared_dir}\tplain\tsession-a\n",
                f"row2\tsession\t{shared_dir}\tplain\tsession-b\n",
            ]

            cache_dir, kill_log = self._run_removal(tmp_path, home, selection_lines)

            _wait_for(lambda: not shared_dir.exists())

            assert not shared_dir.exists(), "matching plain dir should be removed"
            assert unrelated_dir.exists(), "unrelated dir/session must survive"

            kill_names = kill_log.read_text().splitlines() if kill_log.exists() else []
            assert sorted(kill_names) == ["session-a", "session-b"], kill_names
            assert kill_names.count("session-a") == 1
            assert kill_names.count("session-b") == 1
            assert "unrelated-still-running" not in kill_names

    def test_session_name_with_spaces_is_killed_as_one_exact_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            # tmux session names may contain spaces; a word-splitting (or
            # space-separated set) scheme would corrupt this into multiple
            # bogus kill-session calls instead of one exact name.
            spaced_dir = home / "plain/spaced-session-dir"
            spaced_dir.mkdir(parents=True)
            session_name = "feature branch session"

            selection_lines = [
                f"row\tsession\t{spaced_dir}\tplain\t{session_name}\n",
            ]

            cache_dir, kill_log = self._run_removal(tmp_path, home, selection_lines)

            _wait_for(lambda: not spaced_dir.exists())

            assert not spaced_dir.exists(), "matching plain dir should be removed"
            kill_names = kill_log.read_text().splitlines() if kill_log.exists() else []
            assert kill_names == [session_name], kill_names

    def test_directory_tombstone_path_remains_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            target_dir = home / "plain/target-dir"
            target_dir.mkdir(parents=True)
            # Plain-dir rows routed through the "no matching worktree" branch
            # record the literal selection path verbatim (only the eventual
            # `rm -rf` target inside remove_plain_dir.sh is realpath'd), so the
            # tombstone assertion below must match the exact string handed in.
            target_literal = str(target_dir)

            selection_lines = [
                f"row\tsession\t{target_dir}\tplain\talive-session\n",
            ]

            cache_dir, kill_log = self._run_removal(tmp_path, home, selection_lines)
            mutations = cache_dir / "pick_session_mutations.tsv"

            assert _wait_for(
                lambda: mutations.exists() and f"\tPATH_PREFIX\t{target_literal}\n" in mutations.read_text()
            )
            assert f"\tPATH_PREFIX\t{target_literal}\n" in mutations.read_text()


if __name__ == "__main__":
    unittest.main()
