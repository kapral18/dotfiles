#!/usr/bin/env python3
"""Unit tests for session picker GitHub cache update semantics."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO, TMUX_PICKERS

INDEX_MAIN = TMUX_PICKERS / "session/lib/index_main.py"


def _load_session_cache_symbols() -> dict[str, object]:
    source = INDEX_MAIN.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(INDEX_MAIN))

    wanted_functions = {
        "_gh_cache_save",
        "_apply_gh_lookup_result",
    }
    wanted_assignments = {
        "GH_CACHE_FILE",
        "GH_LOOKUP_SUCCESS",
        "GH_LOOKUP_ABSENT",
        "GH_LOOKUP_FAILURE",
    }

    selected_nodes: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            selected_nodes.append(node)
            continue
        if isinstance(node, ast.Assign):
            target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(name in wanted_assignments for name in target_names):
                selected_nodes.append(node)
            continue
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in wanted_assignments:
                selected_nodes.append(node)
            continue
        if isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
            selected_nodes.append(node)

    module = ast.Module(body=selected_nodes, type_ignores=[])
    namespace: dict[str, object] = {}
    exec(compile(module, str(INDEX_MAIN), "exec"), namespace)

    missing = [name for name in [*wanted_functions, *wanted_assignments] if name not in namespace]
    if missing:
        raise AssertionError(f"missing expected symbols in index_main.py: {', '.join(sorted(missing))}")

    return namespace


class TestSessionGitHubCache(unittest.TestCase):
    """WHEN updating GitHub metadata cache rows from lookup outcomes."""

    def setUp(self):
        self.ns = _load_session_cache_symbols()
        self.apply_lookup = self.ns["_apply_gh_lookup_result"]
        self.cache_save = self.ns["_gh_cache_save"]
        self.lookup_success = self.ns["GH_LOOKUP_SUCCESS"]
        self.lookup_absent = self.ns["GH_LOOKUP_ABSENT"]
        self.lookup_failure = self.ns["GH_LOOKUP_FAILURE"]
        self.scratch = REPO / ".test-artifacts" / f"session-github-cache-{self._testMethodName}"
        shutil.rmtree(self.scratch, ignore_errors=True)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.scratch, ignore_errors=True))

    def _base_entry(self) -> dict:
        return {
            "pr": {
                "number": 7,
                "state": "OPEN",
                "review": "CHANGES_REQUESTED",
                "ci": "FAILURE",
                "url": "https://github.com/owner/repo/pull/7",
                "author": "legacy",
            },
            "issue": {"number": 15, "state": "CLOSED", "url": "https://github.com/owner/repo/issues/15"},
            "branch": "old-branch",
            "nwo": "owner/repo",
            "ts": 10,
        }

    def test_success_replaces_cached_metadata(self):
        wt_path = "/repo/wt"
        entries = {wt_path: self._base_entry()}
        wt_gh_info: dict[str, dict] = {}
        lookup = {
            "status": self.lookup_success,
            "pr": {
                "number": 42,
                "state": "OPEN",
                "review": "APPROVED",
                "ci": "SUCCESS",
                "url": "https://github.com/owner/repo/pull/42",
                "author": "new-author",
            },
            "issue": {"number": 88, "state": "OPEN", "url": "https://github.com/owner/repo/issues/88"},
        }

        self.apply_lookup(entries, wt_gh_info, wt_path, "feature/new", "owner/repo", 1234.0, lookup)

        updated = entries[wt_path]
        self.assertEqual(updated["pr"]["number"], 42)
        self.assertEqual(updated["pr"]["review"], "APPROVED")
        self.assertEqual(updated["issue"]["number"], 88)
        self.assertEqual(updated["branch"], "feature/new")
        self.assertEqual(updated["ts"], 1234.0)
        self.assertEqual(wt_gh_info[wt_path]["pr"]["number"], 42)
        self.assertEqual(wt_gh_info[wt_path]["issue"]["number"], 88)

    def test_confirmed_absence_clears_prior_metadata(self):
        wt_path = "/repo/wt"
        entries = {wt_path: self._base_entry()}
        wt_gh_info: dict[str, dict] = {}
        lookup = {"status": self.lookup_absent, "pr": None, "issue": None}

        self.apply_lookup(entries, wt_gh_info, wt_path, "feature/new", "owner/repo", 1234.0, lookup)

        updated = entries[wt_path]
        self.assertIsNone(updated["pr"])
        self.assertIsNone(updated["issue"])
        self.assertEqual(updated["branch"], "feature/new")
        self.assertNotIn(wt_path, wt_gh_info)

    def test_failure_preserves_previous_entry_and_badges(self):
        wt_path = "/repo/wt"
        entries = {wt_path: self._base_entry()}
        before = json.loads(json.dumps(entries[wt_path]))
        wt_gh_info: dict[str, dict] = {}
        lookup = {"status": self.lookup_failure, "pr": None, "issue": None}

        self.apply_lookup(entries, wt_gh_info, wt_path, "feature/new", "owner/repo", 1234.0, lookup)

        self.assertEqual(entries[wt_path], before)
        self.assertEqual(wt_gh_info[wt_path]["pr"], before["pr"])
        self.assertEqual(wt_gh_info[wt_path]["issue"], before["issue"])

    def test_first_lookup_failure_keeps_cache_empty(self):
        wt_path = "/repo/wt"
        entries: dict[str, dict] = {}
        wt_gh_info: dict[str, dict] = {}
        lookup = {"status": self.lookup_failure, "pr": None, "issue": None}

        self.apply_lookup(entries, wt_gh_info, wt_path, "feature/new", "owner/repo", 1234.0, lookup)

        self.assertEqual(entries, {})
        self.assertEqual(wt_gh_info, {})

    def test_atomic_persistence_keeps_previous_file_on_replace_failure(self):
        cache_file = self.scratch / "pick_session_gh.json"
        cache_file.write_text('{"version":1,"entries":{"/repo/wt":{"pr":{"number":7}}}}', encoding="utf-8")
        self.ns["GH_CACHE_FILE"] = cache_file

        with mock.patch.object(self.ns["os"], "replace", side_effect=OSError("replace failed")):
            self.cache_save({"version": 1, "entries": {"/repo/wt": {"pr": {"number": 99}}}})

        self.assertEqual(
            cache_file.read_text(encoding="utf-8"),
            '{"version":1,"entries":{"/repo/wt":{"pr":{"number":7}}}}',
        )
        tmp_files = list(cache_file.parent.glob("*.tmp"))
        self.assertEqual(tmp_files, [])


class TestSessionPickerPrStyling(unittest.TestCase):
    """WHEN quick session refresh finds PR metadata after session discovery."""

    @staticmethod
    def _write_fake_tmux(fake_bin: Path) -> None:
        tmux = fake_bin / "tmux"
        tmux.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = display-message ]; then\n'
            "  printf '%s\\n' review-session\n"
            'elif [ "$1" = list-sessions ]; then\n'
            '  [ -n "${PICK_SESSION_TEST_WORKTREE:-}" ] && printf \'%s\\t%s\\n\' review-session "$PICK_SESSION_TEST_WORKTREE"\n'
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        tmux.chmod(0o755)

    def _run_quick_session_index(
        self, *, state: str, author: str, seed_unrelated_cache_entry: bool = False
    ) -> tuple[str, str, dict[str, object]]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            worktree = home / "work" / "repo" / "review"
            gitdir = root / "gitdirs" / "review"
            fake_bin = root / "bin"
            cache_home = root / "cache"
            worktree.mkdir(parents=True)
            gitdir.mkdir(parents=True)
            fake_bin.mkdir()
            (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
            (gitdir / "HEAD").write_text("ref: refs/heads/review/branch\n", encoding="utf-8")

            self._write_fake_tmux(fake_bin)
            git = fake_bin / "git"
            git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            gh = fake_bin / "gh"
            gh.write_text(
                '#!/bin/sh\nif [ "$1" = pr ]; then\n  printf \'%s\\n\' "$PICK_SESSION_TEST_PR_JSON"\nfi\n',
                encoding="utf-8",
            )
            for command in (git, gh):
                command.chmod(0o755)

            payload = {
                "number": 42,
                "state": state,
                "url": "https://github.com/elastic/kibana/pull/42",
                "reviewDecision": "REVIEW_REQUIRED",
                "closingIssuesReferences": [],
                "author": {"login": author},
            }
            gh_cache_file = cache_home / "tmux" / "pick_session_gh.json"
            if seed_unrelated_cache_entry:
                gh_cache_file.parent.mkdir(parents=True)
                gh_cache_file.write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "entries": {
                                "/unrelated/worktree": {
                                    "pr": {"number": 99, "state": "OPEN"},
                                    "issue": None,
                                    "branch": "unrelated",
                                    "nwo": "elastic/kibana",
                                    "ts": 1,
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )
            env = {
                **os.environ,
                "HOME": str(home),
                "XDG_CACHE_HOME": str(cache_home),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                "PICK_SESSION_GITHUB_LOGIN": "me",
                "PICK_SESSION_QUICK": "1",
                "PICK_SESSION_SESSIONS_ONLY": "1",
                "PICK_SESSION_SKIP_DIRTY": "1",
                "PICK_SESSION_SKIP_GH": "0",
                "PICK_SESSION_SCAN_ROOTS": str(home / "work"),
                "PICK_SESSION_SCAN_DEPTH": "6",
                "PICK_SESSION_THREADS": "1",
                "PICK_SESSION_TEST_WORKTREE": str(worktree),
                "PICK_SESSION_TEST_PR_JSON": json.dumps(payload),
            }
            result = subprocess.run(
                [sys.executable, str(INDEX_MAIN)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            row = next(line for line in result.stdout.splitlines() if "\tsession\t" in line)
            cache_entries = json.loads(gh_cache_file.read_text(encoding="utf-8")).get("entries", {})
            return row, str(worktree.resolve()), cache_entries

    def _run_full_worktree_index(self, *, state: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            worktree = home / "work" / "repo" / "review"
            gitdir = root / "gitdirs" / "review"
            fake_bin = root / "bin"
            worktree.mkdir(parents=True)
            gitdir.mkdir(parents=True)
            fake_bin.mkdir()
            (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
            (gitdir / "HEAD").write_text("ref: refs/heads/review/branch\n", encoding="utf-8")
            self._write_fake_tmux(fake_bin)
            for name, contents in {
                "fd": "#!/bin/sh\nprintf '%s\\n' \"$PICK_SESSION_TEST_GIT_MARKER\"\n",
                "git": "#!/bin/sh\nexit 0\n",
                "gh": "#!/bin/sh\nprintf '%s\\n' \"$PICK_SESSION_TEST_PR_JSON\"\n",
            }.items():
                command = fake_bin / name
                command.write_text(contents, encoding="utf-8")
                command.chmod(0o755)

            payload = {
                "number": 42,
                "state": state,
                "url": "https://github.com/elastic/kibana/pull/42",
                "reviewDecision": "REVIEW_REQUIRED",
                "closingIssuesReferences": [],
                "author": {"login": "contributor"},
            }
            env = {
                **os.environ,
                "HOME": str(home),
                "XDG_CACHE_HOME": str(root / "cache"),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                "PICK_SESSION_GITHUB_LOGIN": "me",
                "PICK_SESSION_QUICK": "0",
                "PICK_SESSION_SESSIONS_ONLY": "0",
                "PICK_SESSION_SKIP_DIRTY": "1",
                "PICK_SESSION_SKIP_GH": "0",
                "PICK_SESSION_SCAN_ROOTS": str(home / "work"),
                "PICK_SESSION_SCAN_DEPTH": "6",
                "PICK_SESSION_THREADS": "1",
                "PICK_SESSION_TEST_WORKTREE": "",
                "PICK_SESSION_TEST_GIT_MARKER": str(worktree / ".git"),
                "PICK_SESSION_TEST_PR_JSON": json.dumps(payload),
            }
            result = subprocess.run(
                [sys.executable, str(INDEX_MAIN)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return next(line for line in result.stdout.splitlines() if "\tworktree\t" in line)

    def _run_full_rehydrate(self, *, state: str) -> str:
        rehydrate = TMUX_PICKERS / "session/lib/items_full_rehydrate.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            worktree = home / "work" / "repo" / "review"
            gitdir = root / "gitdirs" / "review"
            fake_bin = root / "bin"
            cache_file = root / "items.tsv"
            worktree.mkdir(parents=True)
            gitdir.mkdir(parents=True)
            fake_bin.mkdir()
            (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
            (gitdir / "HEAD").write_text("ref: refs/heads/review/branch\n", encoding="utf-8")
            self._write_fake_tmux(fake_bin)
            cache_file.write_text(
                "stale\tsession\t"
                f"{worktree}\t"
                f"sess_wt:review/branch|pr=42:{state}:REVIEW_REQUIRED::https://github.com/elastic/kibana/pull/42|prrole=review\t"
                "review-session\treview-session\n",
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                "PICK_SESSION_SCAN_ROOTS": str(home / "work"),
                "PICK_SESSION_TEST_WORKTREE": str(worktree),
            }
            result = subprocess.run(
                [sys.executable, str(rehydrate), str(cache_file)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return next(line for line in result.stdout.splitlines() if "\tsession\t" in line)

    def test_quick_session_lookup_highlights_contributor_pr(self):
        row, worktree, _ = self._run_quick_session_index(state="OPEN", author="contributor")

        display, kind, path, meta, *_ = row.split("\t")
        self.assertEqual(kind, "session")
        self.assertEqual(path, worktree)
        self.assertIn("prrole=review", meta)
        self.assertIn("\033[1;38;5;213mreview-session", display)

    def test_quick_session_lookup_dims_merged_pr(self):
        row, _, _ = self._run_quick_session_index(state="MERGED", author="contributor")

        display, _, _, meta, *_ = row.split("\t")
        self.assertIn("pr=42:MERGED", meta)
        self.assertIn("\033[2;38;5;244m", display)
        self.assertIn("\033[2;38;5;244mreview-session", display)

    def test_quick_session_lookup_keeps_open_own_pr_bright(self):
        row, _, _ = self._run_quick_session_index(state="OPEN", author="me")

        display, _, _, meta, *_ = row.split("\t")
        self.assertIn("pr=42:OPEN", meta)
        self.assertNotIn("prrole=review", meta)
        self.assertIn("\033[1;38;5;81mreview-session", display)
        self.assertNotIn("\033[2;38;5;244mreview-session", display)

    def test_quick_session_lookup_dims_closed_pr(self):
        row, _, _ = self._run_quick_session_index(state="CLOSED", author="contributor")

        display, _, _, meta, *_ = row.split("\t")
        self.assertIn("pr=42:CLOSED", meta)
        self.assertIn("prrole=review", meta)
        self.assertIn("\033[2;38;5;244m", display)
        self.assertIn("\033[2;38;5;244mreview-session", display)

    def test_quick_session_lookup_dims_closed_own_pr(self):
        row, _, _ = self._run_quick_session_index(state="CLOSED", author="me")

        display, _, _, meta, *_ = row.split("\t")
        self.assertIn("pr=42:CLOSED", meta)
        self.assertNotIn("prrole=review", meta)
        self.assertIn("\033[2;38;5;244m", display)
        self.assertIn("\033[2;38;5;244mreview-session", display)

    def test_quick_session_lookup_preserves_unseen_worktree_cache_entries(self):
        _, _, entries = self._run_quick_session_index(
            state="OPEN", author="contributor", seed_unrelated_cache_entry=True
        )

        self.assertIn("/unrelated/worktree", entries)

    def test_full_rehydrate_dims_cached_terminal_session_pr(self):
        for state in ("MERGED", "CLOSED"):
            with self.subTest(state=state):
                row = self._run_full_rehydrate(state=state)

                display, _, _, meta, *_ = row.split("\t")
                self.assertIn(f"pr=42:{state}", meta)
                self.assertIn("\033[2;38;5;244m", display)
                self.assertIn("\033[2;38;5;244mreview-session", display)

    def test_full_worktree_index_dims_terminal_pr(self):
        for state in ("MERGED", "CLOSED"):
            with self.subTest(state=state):
                row = self._run_full_worktree_index(state=state)

                display, _, _, meta, *_ = row.split("\t")
                self.assertIn(f"pr=42:{state}", meta)
                self.assertIn("prrole=review", meta)
                self.assertIn("\033[2;38;5;244m", display)


if __name__ == "__main__":
    unittest.main()
