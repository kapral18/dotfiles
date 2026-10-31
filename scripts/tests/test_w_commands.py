#!/usr/bin/env python3
"""Behavior tests for ,w add, ,w issue matching and ,w mv over real git repos."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
W_SRC = REPO / "home/exact_lib/exact_,w"
SHARED_SRC = REPO / "home/exact_lib/exact_shared"


class _WCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        lib = self.root / "lib"
        shutil.copytree(W_SRC, lib / ",w")
        shutil.copytree(SHARED_SRC, lib / "shared")
        self.w = lib / ",w"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.tmux_log = self.root / "tmux.log"
        self.stub("zoxide", "exit 0")
        self.stub(
            "tmux",
            f'echo "$*" >> {self.tmux_log}\ncase "$1" in has-session|list-sessions|display-message) exit 1;; esac\nexit 0',
        )
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
        self.env.pop("TMUX", None)
        (self.root / "home").mkdir()

    def stub(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)

    def git(self, cwd: Path, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, env=self.env, check=True, text=True, capture_output=True
        ).stdout.strip()

    def commit(self, repo: Path, name: str) -> str:
        (repo / name).write_text(name)
        self.git(repo, "add", name)
        self.git(repo, "commit", "-qm", name)
        return self.git(repo, "rev-parse", "HEAD")

    def run_w(self, script: str, cwd: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(self.w / script), *args], cwd=cwd, env={**self.env, **env}, text=True, capture_output=True
        )


class WAddStartPointTests(_WCase):
    """WHEN ,w add remote/branch names a remote whose branch differs from origin's."""

    def test_worktree_starts_at_the_fetched_remote_branch(self) -> None:
        seed = self.root / "seed"
        seed.mkdir()
        self.git(seed, "init", "-q", "-b", "main")
        self.commit(seed, "base")
        for name in ("origin.git", "upstream.git"):
            self.git(self.root, "clone", "-q", "--bare", str(seed), name)
        self.git(seed, "switch", "-q", "-c", "foo")
        stale = self.commit(seed, "stale")
        self.git(seed, "push", "-q", str(self.root / "origin.git"), "foo")
        self.git(seed, "reset", "-q", "--hard", "main")
        fresh = self.commit(seed, "fresh")
        self.git(seed, "push", "-q", str(self.root / "upstream.git"), "foo")
        self.assertNotEqual(stale, fresh)

        wrapper = self.root / "repo"
        wrapper.mkdir()
        main = wrapper / "main"
        self.git(self.root, "clone", "-q", str(self.root / "origin.git"), str(main))
        self.git(main, "remote", "add", "upstream", str(self.root / "upstream.git"))
        self.git(main, "fetch", "-q", "origin")

        result = self.run_w("add.sh", main, "upstream/foo")

        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.git(main, "worktree", "list", "--porcelain").split("worktree ")[-1].splitlines()[0]
        self.assertEqual(self.git(Path(path), "rev-parse", "HEAD"), fresh)


class WIssueMatchTests(_WCase):
    """WHEN ,w issue looks for an existing worktree for an issue number."""

    def setUp(self) -> None:
        super().setUp()
        self.main = self.root / "main"
        self.main.mkdir()
        self.git(self.main, "init", "-q", "-b", "main")
        self.commit(self.main, "base")

    def find(self, number: str) -> str:
        script = f'source "{self.w}/../shared/bash_utils_lib.sh"; source "{self.w}/issue_lib.sh"; _comma_w_issue_find_by_heuristics {number} || true'
        return subprocess.run(
            ["bash", "-c", script], cwd=self.main, env=self.env, text=True, capture_output=True
        ).stdout.strip()

    def test_unrelated_digit_groups_do_not_match(self) -> None:
        self.git(self.main, "worktree", "add", "-q", "-b", "backport/8.12/pr-555", str(self.root / "wt-12"))
        self.assertEqual(self.find("12"), "")

    def test_branch_ending_in_the_issue_number_matches(self) -> None:
        self.git(self.main, "worktree", "add", "-q", "-b", "fix-thing-12", str(self.root / "fix"))
        self.assertEqual(self.find("12"), str(self.root / "fix"))


class WMvTests(_WCase):
    """WHEN ,w mv is refused because the destination branch already exists."""

    def test_refused_move_keeps_the_tmux_session(self) -> None:
        main = self.root / "repo" / "main"
        main.mkdir(parents=True)
        self.git(main, "init", "-q", "-b", "main")
        self.commit(main, "base")
        self.git(main, "branch", "taken")
        self.git(main, "worktree", "add", "-q", "-b", "old", str(self.root / "repo" / "old"))
        old = self.root / "repo" / "old"
        self.stub(
            "tmux",
            f'echo "$*" >> {self.tmux_log}\ncase "$1" in has-session) exit 0;; display-message) echo {old};; esac\nexit 0',
        )

        result = self.run_w("mv.sh", main, "old", "taken", TMUX="/tmp/fake,1,0")

        self.assertNotEqual(result.returncode, 0)
        log = self.tmux_log.read_text() if self.tmux_log.exists() else ""
        self.assertNotIn("kill-session", log)
        self.assertTrue((self.root / "repo" / "old").is_dir())


class WMvSelfKillTests(_WCase):
    """WHEN ,w mv runs inside the session it renames, so killing that session kills the script."""

    def test_move_finishes_before_the_old_session_dies(self) -> None:
        main = self.root / "repo" / "main"
        main.mkdir(parents=True)
        self.git(main, "init", "-q", "-b", "main")
        self.commit(main, "base")
        old = self.root / "repo" / "old"
        self.git(main, "worktree", "add", "-q", "-b", "old", str(old))
        self.stub(
            "tmux",
            f'echo "$*" >> {self.tmux_log}\n'
            f'case "$1" in has-session) exit 0;; display-message) echo {old};; kill-session) kill -TERM $PPID;; esac\nexit 0',
        )

        result = self.run_w("mv.sh", main, "old", "renamed", TMUX="/tmp/fake,1,0")
        self.assertEqual(result.returncode, -15, result.stderr)

        self.assertTrue((self.root / "repo" / "renamed").is_dir())
        self.assertEqual(self.git(self.root / "repo" / "renamed", "branch", "--show-current"), "renamed")


STATEFUL_TMUX = r"""#!/usr/bin/env bash
db="$TMUX_DB"
name() { local t="${1#=}"; printf '%s' "${t%:}"; }
target() { while [ $# -gt 0 ]; do [ "$1" = -t ] && { name "$2"; return; }; shift; done; }
case "$1" in
  has-session) grep -q "^$(target "$@")	" "$db"; exit ;;
  display-message) n="$(target "$@")"; awk -F'\t' -v n="$n" '$1 == n { print $2 }' "$db" ;;
  list-sessions) cat "$db" ;;
  new-session) shift; while [ $# -gt 0 ]; do case "$1" in -s) s="$2"; shift ;; -c) c="$2"; shift ;; esac; shift; done
    printf '%s\t%s\n' "$s" "$c" >> "$db" ;;
  rename-session) grep -q "^${!#}	" "$db" && exit 1; n="$(target "$@")"; awk -F'\t' -v OFS='\t' -v n="$n" -v m="${!#}" '$1 == n { $1 = m } 1' "$db" > "$db.new"; mv "$db.new" "$db" ;;
  kill-session) n="$(target "$@")"; grep -v "^$n	" "$db" > "$db.new" || true; mv "$db.new" "$db" ;;
esac
exit 0
"""


class WMvSessionTests(_WCase):
    """WHEN ,w mv replaces a worktree's session while tmux tracks which sessions exist."""

    def setUp(self) -> None:
        super().setUp()
        self.main = self.root / "repo" / "main"
        self.main.mkdir(parents=True)
        self.git(self.main, "init", "-q", "-b", "main")
        self.commit(self.main, "base")
        self.old = self.root / "repo" / "old"
        self.git(self.main, "worktree", "add", "-q", "-b", "old", str(self.old))
        self.db = self.root / "sessions.tsv"
        self.db.write_text(f"repo|old\t{self.old}\n")
        (self.bin / "tmux").write_text(STATEFUL_TMUX)

    def sessions(self, *args: str, tmux: str = "/tmp/fake,1,0") -> list[list[str]]:
        result = self.run_w("mv.sh", self.main, *args, TMUX=tmux, TMUX_DB=str(self.db))
        self.assertEqual(result.returncode, 0, result.stderr)
        return sorted(line.split("\t") for line in self.db.read_text().splitlines())

    def test_keep_path_rename_replaces_only_the_old_named_session(self) -> None:
        with self.db.open("a") as db:
            db.write(f"scratch\t{self.old}\n")
        self.assertEqual(
            self.sessions("--keep-path", "old", "renamed"),
            [["repo|renamed", str(self.old)], ["scratch", str(self.old)]],
        )

    def test_same_branch_path_move_restarts_its_session_in_the_new_directory(self) -> None:
        moved = self.root / "repo" / "moved"
        self.assertEqual(self.sessions("--path", str(moved), "old", "old"), [["repo|old", str(moved)]])

    def test_same_branch_move_ignores_a_leftover_aside_session(self) -> None:
        with self.db.open("a") as db:
            db.write(f"repo|old~moved\t{self.root / 'gone'}\n")
        moved = self.root / "repo" / "moved"
        self.assertIn(["repo|old", str(moved)], self.sessions("--path", str(moved), "old", "old"))

    def test_failed_branch_rename_moves_the_worktree_back(self) -> None:
        git_dir = Path(self.git(self.main, "rev-parse", "--absolute-git-dir"))
        (git_dir / "refs/heads/renamed.lock").write_text("")
        result = self.run_w("mv.sh", self.main, "old", "renamed", TMUX="/tmp/fake,1,0", TMUX_DB=str(self.db))
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.old.is_dir())
        self.assertFalse((self.root / "repo" / "renamed").exists())
        self.assertEqual(self.db.read_text(), f"repo|old\t{self.old}\n")

    def test_move_outside_tmux_leaves_sessions_alone(self) -> None:
        moved = self.root / "repo" / "moved"
        self.assertEqual(self.sessions("--path", str(moved), "old", "old", tmux=""), [["repo|old", str(self.old)]])

    def test_existing_destination_is_refused_before_any_change(self) -> None:
        taken = self.root / "repo" / "taken"
        taken.mkdir()
        result = self.run_w(
            "mv.sh", self.main, "--path", str(taken), "old", "new", TMUX="/tmp/fake,1,0", TMUX_DB=str(self.db)
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.db.read_text(), f"repo|old\t{self.old}\n")
        self.assertTrue(self.old.is_dir())
        self.assertEqual(self.git(self.old, "branch", "--show-current"), "old")


class WSessionHintTests(_WCase):
    """WHEN a removed worktree's session is looked up by its hinted name."""

    def remove_session(self, session_path: Path | str, cwd: Path | None = None) -> str:
        real = self.root / "real"
        real.mkdir(exist_ok=True)
        (self.root / "link").symlink_to(real)
        # Like macOS realpath, and unlike GNU's, fail on a path whose last component is gone.
        self.stub("realpath", '[ -d "$1" ] || exit 1; cd "$1" && pwd -P')
        self.stub(
            "tmux",
            f'echo "$*" >> {self.tmux_log}\ncase "$1" in has-session) exit 0;; display-message) echo {session_path};; list-sessions) exit 0;; esac\nexit 0',
        )
        script = (
            f'source "{self.w}/../shared/worktree_lib.sh"; _remove_worktree_tmux_session 1 "{self.root}/link/wt" wt'
        )
        subprocess.run(
            ["bash", "-c", script], cwd=cwd, env={**self.env, "TMUX": "/tmp/fake,1,0"}, text=True, capture_output=True
        )
        return self.tmux_log.read_text()

    def test_session_at_the_real_path_is_killed(self) -> None:
        self.assertIn("kill-session -t =wt", self.remove_session(self.root / "real/wt"))

    def test_session_elsewhere_is_kept(self) -> None:
        self.assertNotIn("kill-session", self.remove_session(self.root / "other"))

    def test_failed_path_lookup_keeps_the_session(self) -> None:
        inside = self.root / "real/wt/sub"
        inside.mkdir(parents=True)
        self.assertNotIn("kill-session", self.remove_session("", cwd=inside))


if __name__ == "__main__":
    unittest.main()
