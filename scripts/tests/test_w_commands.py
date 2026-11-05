#!/usr/bin/env python3
"""Behavior tests for ,w add, ,w issue matching and ,w mv over real git repos."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _test_support import install_fake_herdr

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
        self.herdr_log = self.root / "herdr.log"
        self.db = self.root / "workspaces.tsv"
        self.stub("zoxide", "exit 0")
        install_fake_herdr(self.bin)
        self.env = {
            **{k: v for k, v in os.environ.items() if not k.startswith("HERDR_")},
            "HOME": str(self.root / "home"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "HERDR_LOG": str(self.herdr_log),
            "HERDR_DB": str(self.db),
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
        }
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
        script = f'source "{self.w}/../shared/bash_utils_lib.sh"; source "{self.w}/issue_lib.sh"; _comma_w_issue_find_by_heuristics {number} owner/repo || true'
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

    def test_refused_move_keeps_the_workspace(self) -> None:
        main = self.root / "repo" / "main"
        main.mkdir(parents=True)
        self.git(main, "init", "-q", "-b", "main")
        self.commit(main, "base")
        self.git(main, "branch", "taken")
        old = self.root / "repo" / "old"
        self.git(main, "worktree", "add", "-q", "-b", "old", str(old))
        self.db.write_text(f"w1\trepo|old\t{old}\n")

        result = self.run_w("mv.sh", main, "old", "taken", HERDR_SOCKET_PATH="/tmp/fake.sock")

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("workspace close", self.herdr_log.read_text() if self.herdr_log.exists() else "")
        self.assertTrue(old.is_dir())


class WMvSelfKillTests(_WCase):
    """WHEN ,w mv runs inside the workspace it replaces, so closing that workspace ends the script."""

    def test_move_finishes_before_the_old_workspace_closes(self) -> None:
        main = self.root / "repo" / "main"
        main.mkdir(parents=True)
        self.git(main, "init", "-q", "-b", "main")
        self.commit(main, "base")
        old = self.root / "repo" / "old"
        self.git(main, "worktree", "add", "-q", "-b", "old", str(old))
        self.db.write_text(f"w1\trepo|old\t{old}\n")

        result = self.run_w(
            "mv.sh", main, "old", "renamed", HERDR_SOCKET_PATH="/tmp/fake.sock", HERDR_FAKE_CLOSE_KILLS="1"
        )
        self.assertEqual(result.returncode, -15, result.stderr)

        self.assertTrue((self.root / "repo" / "renamed").is_dir())
        self.assertEqual(self.git(self.root / "repo" / "renamed", "branch", "--show-current"), "renamed")


class WMvSessionTests(_WCase):
    """WHEN ,w mv replaces a worktree's workspace while herdr tracks which workspaces exist."""

    def setUp(self) -> None:
        super().setUp()
        self.main = self.root / "repo" / "main"
        self.main.mkdir(parents=True)
        self.git(self.main, "init", "-q", "-b", "main")
        self.commit(self.main, "base")
        self.old = self.root / "repo" / "old"
        self.git(self.main, "worktree", "add", "-q", "-b", "old", str(self.old))
        self.db.write_text(f"w1\trepo|old\t{self.old}\n")

    def add(self, label: str, path: Path) -> None:
        with self.db.open("a") as db:
            db.write(f"w{len(self.db.read_text().splitlines()) + 1}\t{label}\t{path}\n")

    def workspaces(self) -> list[list[str]]:
        return sorted(line.split("\t")[1:] for line in self.db.read_text().splitlines())

    def move(self, *args: str, inside: bool = True) -> list[list[str]]:
        env = {"HERDR_SOCKET_PATH": "/tmp/fake.sock"} if inside else {}
        result = self.run_w("mv.sh", self.main, *args, **env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.workspaces()

    def test_keep_path_rename_renames_only_the_old_named_workspace(self) -> None:
        self.add("scratch", self.old)
        self.assertEqual(
            self.move("--keep-path", "old", "renamed"),
            [["repo|renamed", str(self.old)], ["scratch", str(self.old)]],
        )

    def test_same_branch_path_move_reopens_its_workspace_in_the_new_directory(self) -> None:
        moved = self.root / "repo" / "moved"
        self.assertEqual(self.move("--path", str(moved), "old", "old"), [["repo|old", str(moved)]])

    def test_same_branch_move_ignores_a_leftover_aside_workspace(self) -> None:
        self.add("repo|old~moved", self.root / "gone")
        moved = self.root / "repo" / "moved"
        self.assertIn(["repo|old", str(moved)], self.move("--path", str(moved), "old", "old"))

    def test_failed_branch_rename_moves_the_worktree_back(self) -> None:
        git_dir = Path(self.git(self.main, "rev-parse", "--absolute-git-dir"))
        (git_dir / "refs/heads/renamed.lock").write_text("")
        result = self.run_w("mv.sh", self.main, "old", "renamed", HERDR_SOCKET_PATH="/tmp/fake.sock")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.old.is_dir())
        self.assertFalse((self.root / "repo" / "renamed").exists())
        self.assertEqual(self.workspaces(), [["repo|old", str(self.old)]])

    def test_move_outside_herdr_leaves_workspaces_alone(self) -> None:
        moved = self.root / "repo" / "moved"
        self.assertEqual(self.move("--path", str(moved), "old", "old", inside=False), [["repo|old", str(self.old)]])

    def test_existing_destination_is_refused_before_any_change(self) -> None:
        taken = self.root / "repo" / "taken"
        taken.mkdir()
        result = self.run_w("mv.sh", self.main, "--path", str(taken), "old", "new", HERDR_SOCKET_PATH="/tmp/fake.sock")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.workspaces(), [["repo|old", str(self.old)]])
        self.assertTrue(self.old.is_dir())
        self.assertEqual(self.git(self.old, "branch", "--show-current"), "old")


class WSessionHintTests(_WCase):
    """WHEN a removed worktree's workspace is looked up by its hinted name."""

    def remove_workspace(self, workspace_path: Path | str, cwd: Path | None = None) -> str:
        real = self.root / "real"
        real.mkdir(exist_ok=True)
        (self.root / "link").symlink_to(real)
        # Like macOS realpath, and unlike GNU's, fail on a path whose last component is gone.
        self.stub("realpath", '[ -d "$1" ] || exit 1; cd "$1" && pwd -P')
        self.db.write_text(f"w1\twt\t{workspace_path}\n")
        script = f'source "{self.w}/../shared/worktree_lib.sh"; _remove_worktree_workspace 1 "{self.root}/link/wt" wt'
        subprocess.run(
            ["bash", "-c", script],
            cwd=cwd,
            env={**self.env, "HERDR_SOCKET_PATH": "/tmp/fake.sock"},
            text=True,
            capture_output=True,
        )
        return self.herdr_log.read_text()

    def test_workspace_at_the_real_path_is_closed(self) -> None:
        self.assertIn("workspace close w1", self.remove_workspace(self.root / "real/wt"))

    def test_workspace_elsewhere_is_kept(self) -> None:
        self.assertNotIn("workspace close", self.remove_workspace(self.root / "other"))

    def test_failed_path_lookup_keeps_the_workspace(self) -> None:
        inside = self.root / "real/wt/sub"
        inside.mkdir(parents=True)
        self.assertNotIn("workspace close", self.remove_workspace("", cwd=inside))


class WorkspaceRegistryTests(_WCase):
    """WHEN a workspace's panes cd away from the directory it was opened for."""

    def lib(self, snippet: str) -> str:
        return subprocess.run(
            ["bash", "-c", f'source "{self.w.parent}/shared/worktree_lib.sh"; {snippet}'],
            env={**self.env, "HERDR_SOCKET_PATH": str(self.root / "sock")},
            check=True,
            text=True,
            capture_output=True,
        ).stdout

    def test_path_stays_the_opened_directory_only_while_the_label_matches(self) -> None:
        wt, other = self.root / "wt", self.root / "other"
        self.db.write_text("")
        self.lib(f"_comma_w_create_workspace 'repo|wt' '{wt}'; _comma_w_create_workspace other '{other}'")
        self.db.write_text(self.db.read_text().replace(str(wt), str(other)))

        self.assertIn(f"repo|wt\t{wt}\t", self.lib("_comma_w_workspace_list"))
        self.assertEqual(self.lib(f"_comma_w_workspace_ids_at_path '{wt}'").split(), ["w1"])

        self.db.write_text(self.db.read_text().replace("repo|wt", "renamed"))
        self.assertEqual(self.lib(f"_comma_w_workspace_ids_at_path '{wt}'"), "")
        self.assertIn(f"renamed\t{other}\t", self.lib("_comma_w_workspace_list"))

    def test_a_rename_keeps_the_opened_directory(self) -> None:
        wt, other = self.root / "wt", self.root / "other"
        self.db.write_text("")
        self.lib(f"_comma_w_create_workspace 'repo|wt' '{wt}'")
        self.db.write_text(f"w1\trenamed\t{other}\n")
        self.lib("_comma_w_relabel_workspace w1")

        self.assertIn(f"renamed\t{wt}\tw1", self.lib("_comma_w_workspace_list"))

    def test_concurrent_writers_keep_every_row(self) -> None:
        self.db.write_text("".join(f"w{i}\tl{i}\t/x\n" for i in range(1, 21)))
        self.lib('for i in $(seq 1 20); do _comma_w_record_workspace_path "w$i" "l$i" "/d$i" & done; wait')

        self.assertEqual(len(self.lib("_comma_w_workspace_list registered").splitlines()), 20)

    def test_a_reissued_id_does_not_inherit_a_closed_workspace_directory(self) -> None:
        wt, other = self.root / "wt", self.root / "other"
        self.db.write_text("")
        self.lib(f"_comma_w_create_workspace 'repo|wt' '{wt}'")
        self.db.write_text("")
        self.lib("_comma_w_prune_workspace_registry")
        self.db.write_text(f"w1\trepo|wt\t{other}\n")

        self.assertEqual(self.lib(f"_comma_w_workspace_ids_at_path '{wt}'"), "")


class WHelpTests(_WCase):
    def test_add_and_remove_help_do_not_run_git_commands(self) -> None:
        calls = self.root / "git-calls"
        self.stub("git", f'printf "%s\\n" "$*" >> "{calls}"\nexit 1')
        self.stub(",w", f'printf "%s\\n" "$*" >> "{calls}"\nexit 1')

        for command in ("add.sh", "remove.sh"):
            with self.subTest(command=command):
                result = self.run_w(command, self.root, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(calls.exists(), result.stdout)


if __name__ == "__main__":
    unittest.main()
