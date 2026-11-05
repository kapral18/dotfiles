#!/usr/bin/env python3
"""Regression tests for plain-directory workspace removal identity handling.

`executable_action_remove_worktrees.sh` closes every selected workspace row by
its exact label, then removes plain-directory rows (workspaces with no
git-backed worktree, orphaned/stale worktree dirs, and bare `dir` zoxide rows)
in the background with `executable_remove_plain_dir.sh`. Distinct workspaces
can share one plain-dir path, and labels may contain spaces.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from _test_support import PICKERS, deploy_herdr_libs, install_fake_herdr, modern_bash

ACTION_SCRIPT = PICKERS / "session/executable_action_remove_worktrees.sh"


def _wait_for(predicate, *, timeout=5.0, interval=0.05):
    """Poll `predicate` until truthy; the removal dispatch runs in the
    background (detached into its own session), so callers must
    wait for its side effects rather than assume they land synchronously."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class TestPlainSessionRemoval(unittest.TestCase):
    """WHEN pick_session removes plain-directory rows backed by a herdr workspace."""

    def _run_removal(
        self, tmp: Path, home: Path, selection_lines: list[str], args=("--force",), expect: int = 0, workspaces=()
    ):
        cache_dir = home / ".cache/herdr-pickers"
        cache_dir.mkdir(parents=True, exist_ok=True)
        mock_bin = tmp / "bin"
        mock_bin.mkdir(exist_ok=True)
        install_fake_herdr(mock_bin)
        deploy_herdr_libs(home)
        self.herdr_log = tmp / "herdr.log"
        db = tmp / "workspaces.tsv"
        self.labels = {f"w{i}": label for i, (label, _) in enumerate(workspaces, 1)}
        db.write_text("".join(f"w{i}\t{label}\t{path}\n" for i, (label, path) in enumerate(workspaces, 1)))

        # The action dispatches via the deployed path, and source `executable_` files lack +x.
        deployed_dir = home / ".config/herdr/scripts/pickers/session"
        deployed_dir.mkdir(parents=True, exist_ok=True)
        deployed_script = deployed_dir / "remove_plain_dir.sh"
        deployed_script.write_text((PICKERS / "session/executable_remove_plain_dir.sh").read_text())
        deployed_script.chmod(0o755)

        selection = tmp / "selection.tsv"
        selection.write_text("".join(selection_lines))

        env = {
            **{k: v for k, v in os.environ.items() if not k.startswith("HERDR_")},
            "HOME": str(home),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "PATH": f"{mock_bin}:{os.environ['PATH']}",
            # The script dispatches background removal only inside herdr.
            "HERDR_SOCKET_PATH": str(tmp / "herdr.sock"),
            "HERDR_DB": str(db),
            "HERDR_LOG": str(self.herdr_log),
        }

        result = subprocess.run(
            [modern_bash(), str(ACTION_SCRIPT), *args, str(selection)],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == expect, result.stderr
        return cache_dir

    def closed(self) -> list[str]:
        log = self.herdr_log.read_text().splitlines() if self.herdr_log.exists() else []
        return [self.labels[line.split()[2]] for line in log if line.startswith("workspace close ")]

    def test_plain_dir_delete_requires_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            repo = home / "code/repo"
            repo.mkdir(parents=True)
            (repo / "notes.txt").write_text("only copy\n")
            selection_lines = [f"row\tdir\t{home / 'code'}\t\t\n"]

            self._run_removal(tmp_path, home, selection_lines, ("--check",), expect=3)
            self._run_removal(tmp_path, home, selection_lines, ())

            assert (repo / "notes.txt").exists()
            assert not (home / ".cache/herdr-pickers/pick_session_mutations.tsv").exists()

    def test_matching_session_removed_and_unrelated_sessions_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            target_dir = home / "plain/target-dir"
            target_dir.mkdir(parents=True)

            untouched_dir = home / "plain/untouched-dir"
            untouched_dir.mkdir(parents=True)

            selection_lines = [
                f"row\tsession\t{target_dir}\tplain\talive-session\n",
            ]

            self._run_removal(
                tmp_path,
                home,
                selection_lines,
                workspaces=[("alive-session", target_dir), ("other", untouched_dir)],
            )

            _wait_for(lambda: not target_dir.exists() and self.closed())

            assert not target_dir.exists(), "matching plain dir should be removed"
            assert untouched_dir.exists(), "unrelated dir/workspace must survive"
            assert self.closed() == ["alive-session"], self.closed()

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

            self._run_removal(tmp_path, home, selection_lines)

            _wait_for(lambda: not ghost_dir.exists())

            assert not ghost_dir.exists(), "dir removal must proceed even if the workspace is already gone"
            assert self.closed() == []

    def test_plain_dir_row_without_session_identity_closes_no_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            bare_dir = home / "plain/bare-dir"
            bare_dir.mkdir(parents=True)

            selection_lines = [
                f"row\tdir\t{bare_dir}\t\t\n",
            ]

            self._run_removal(tmp_path, home, selection_lines, workspaces=[("elsewhere", home / "plain")])

            _wait_for(lambda: not bare_dir.exists())

            assert not bare_dir.exists()
            assert self.closed() == []

    def test_two_selected_sessions_sharing_one_plain_dir_are_both_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            # Two distinct workspaces can share the same directory, so both
            # rows select the same plain dir under two different names.
            shared_dir = home / "plain/shared-dir"
            shared_dir.mkdir(parents=True)

            unrelated_dir = home / "plain/unrelated-dir"
            unrelated_dir.mkdir(parents=True)

            selection_lines = [
                f"row1\tsession\t{shared_dir}\tplain\tsession-a\n",
                f"row2\tsession\t{shared_dir}\tplain\tsession-b\n",
            ]

            self._run_removal(
                tmp_path,
                home,
                selection_lines,
                workspaces=[("session-a", shared_dir), ("session-b", shared_dir), ("other", unrelated_dir)],
            )

            _wait_for(lambda: not shared_dir.exists() and len(self.closed()) == 2)

            assert not shared_dir.exists(), "matching plain dir should be removed"
            assert unrelated_dir.exists(), "unrelated dir/workspace must survive"
            assert sorted(self.closed()) == ["session-a", "session-b"], self.closed()

    def test_session_name_with_spaces_is_killed_as_one_exact_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            # Workspace names may contain spaces; a word-splitting (or
            # space-separated set) scheme would corrupt this into multiple
            # bogus close calls instead of one exact name.
            spaced_dir = home / "plain/spaced-session-dir"
            spaced_dir.mkdir(parents=True)
            session_name = "feature branch session"

            selection_lines = [
                f"row\tsession\t{spaced_dir}\tplain\t{session_name}\n",
            ]

            self._run_removal(tmp_path, home, selection_lines, workspaces=[(session_name, spaced_dir)])

            _wait_for(lambda: not spaced_dir.exists() and self.closed())

            assert not spaced_dir.exists(), "matching plain dir should be removed"
            assert self.closed() == [session_name], self.closed()

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

            cache_dir = self._run_removal(tmp_path, home, selection_lines, workspaces=[("alive-session", target_dir)])
            mutations = cache_dir / "pick_session_mutations.tsv"

            assert _wait_for(
                lambda: mutations.exists() and f"\tPATH_PREFIX\t{target_literal}\n" in mutations.read_text()
            )
            assert f"\tPATH_PREFIX\t{target_literal}\n" in mutations.read_text()


if __name__ == "__main__":
    unittest.main()
