#!/usr/bin/env python3
"""Unit tests for session picker GitHub cache update semantics."""

from __future__ import annotations

import ast
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _test_support import PICKERS

INDEX_MAIN = PICKERS / "session/lib/index_main.py"
# The loader below copies index_main.py's imports but not its sys.path.insert, so add that dir here.
sys.path.insert(0, str(PICKERS / "lib"))


def _load_session_cache_symbols() -> dict[str, object]:
    source = INDEX_MAIN.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(INDEX_MAIN))

    wanted_functions = {
        "_gh_cache_save",
        "_gh_cache_load",
        "_apply_gh_lookup_result",
    }
    optional_functions = {"_gh_cache_matches_identity"}
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
        if isinstance(node, ast.FunctionDef) and node.name in wanted_functions | optional_functions:
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
        scratch = tempfile.TemporaryDirectory(prefix="session-github-cache-")
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)

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

    def test_inconclusive_lookup_preserves_matching_entry_and_badges(self):
        for status in (self.lookup_failure, "unknown"):
            with self.subTest(status=status):
                wt_path = "/repo/wt"
                entries = {wt_path: self._base_entry()}
                before = json.loads(json.dumps(entries[wt_path]))
                wt_gh_info: dict[str, dict] = {}
                lookup = {"status": status, "pr": None, "issue": None}

                self.apply_lookup(entries, wt_gh_info, wt_path, "old-branch", "owner/repo", 1234.0, lookup)

                self.assertEqual(entries[wt_path], before)
                self.assertEqual(wt_gh_info[wt_path]["pr"], before["pr"])
                self.assertEqual(wt_gh_info[wt_path]["issue"], before["issue"])

    def test_inconclusive_lookup_keeps_other_identity_on_disk_without_badges(self):
        for status in (self.lookup_failure, "unknown"):
            for branch, nwo in (("feature/new", "owner/repo"), ("old-branch", "owner/other")):
                with self.subTest(status=status, branch=branch, nwo=nwo):
                    wt_path = "/repo/wt"
                    entries = {wt_path: self._base_entry()}
                    before = json.loads(json.dumps(entries[wt_path]))
                    wt_gh_info: dict[str, dict] = {}
                    lookup = {"status": status, "pr": None, "issue": None}

                    self.apply_lookup(entries, wt_gh_info, wt_path, branch, nwo, 1234.0, lookup)

                    self.assertEqual(entries[wt_path], before)
                    self.assertNotIn(wt_path, wt_gh_info)

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
            self.cache_save(
                {"/repo/wt": {"pr": {"number": 99}}},
                {"/repo/wt": {"pr": {"number": 7}}},
            )

        self.assertEqual(
            cache_file.read_text(encoding="utf-8"),
            '{"version":1,"entries":{"/repo/wt":{"pr":{"number":7}}}}',
        )
        tmp_files = list(cache_file.parent.glob("*.tmp"))
        self.assertEqual(tmp_files, [])


class TestSessionPickerPrStyling(unittest.TestCase):
    """WHEN quick session refresh finds PR metadata after session discovery."""

    @staticmethod
    def _write_fake_sessions(home: Path, body: str | None = None) -> None:
        """Stand in for the picker's herdr session source (herdr_sessions.sh)."""
        sessions = home / ".config/herdr/scripts/pickers/lib/herdr_sessions.sh"
        sessions.parent.mkdir(parents=True, exist_ok=True)
        sessions.write_text(
            body
            or (
                "#!/bin/sh\n"
                'if [ "$1" = current ]; then\n'
                "  printf '%s\\n' review-session\n"
                'elif [ "$1" = list ]; then\n'
                '  [ -n "${PICK_SESSION_TEST_WORKTREE:-}" ] && printf \'%s\\t%s\\n\' review-session "$PICK_SESSION_TEST_WORKTREE"\n'
                "fi\n"
                "exit 0\n"
            ),
            encoding="utf-8",
        )
        sessions.chmod(0o755)

    def _run_quick_session_index(
        self,
        *,
        state: str,
        author: str,
        seed_unrelated_cache_entry: bool = False,
        cached_entry: dict[str, object] | None = None,
        skip_gh: bool = False,
        lookup_failure: bool = False,
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

            self._write_fake_sessions(home)
            git = fake_bin / "git"
            git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            gh = fake_bin / "gh"
            gh.write_text(
                "#!/bin/sh\n"
                'if [ "$PICK_SESSION_TEST_LOOKUP_FAILURE" = 1 ]; then exit 1; fi\n'
                'if [ "$1" = pr ]; then\n  printf \'%s\\n\' "$PICK_SESSION_TEST_PR_JSON"\nfi\n',
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
            gh_cache_file = cache_home / "herdr-pickers" / "pick_session_gh.json"
            if seed_unrelated_cache_entry or cached_entry is not None:
                entries = {}
                if seed_unrelated_cache_entry:
                    entries["/unrelated/worktree"] = {
                        "pr": {"number": 99, "state": "OPEN"},
                        "issue": None,
                        "branch": "unrelated",
                        "nwo": "elastic/kibana",
                        "ts": 1,
                    }
                if cached_entry is not None:
                    entries[str(worktree.resolve())] = cached_entry
                gh_cache_file.parent.mkdir(parents=True)
                gh_cache_file.write_text(json.dumps({"version": 1, "entries": entries}), encoding="utf-8")
            env = {
                **os.environ,
                "HOME": str(home),
                "XDG_CACHE_HOME": str(cache_home),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                "PICK_SESSION_GITHUB_LOGIN": "me",
                "PICK_SESSION_QUICK": "1",
                "PICK_SESSION_SESSIONS_ONLY": "1",
                "PICK_SESSION_SKIP_DIRTY": "1",
                "PICK_SESSION_SKIP_GH": "1" if skip_gh else "0",
                "PICK_SESSION_SCAN_ROOTS": str(home / "work"),
                "PICK_SESSION_SCAN_DEPTH": "6",
                "PICK_SESSION_THREADS": "1",
                "PICK_SESSION_TEST_WORKTREE": str(worktree),
                "PICK_SESSION_TEST_PR_JSON": json.dumps(payload),
                "PICK_SESSION_TEST_LOOKUP_FAILURE": "1" if lookup_failure else "0",
            }
            result = subprocess.run(
                [sys.executable, str(INDEX_MAIN)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
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
            self._write_fake_sessions(home)
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
        rehydrate = PICKERS / "session/lib/items_full_rehydrate.py"
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
            self._write_fake_sessions(home)
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
                "XDG_CACHE_HOME": str(root / "cache"),
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

    def test_stale_metadata_is_rendered_only_for_matching_worktree_identity(self):
        for skip_gh in (False, True):
            for identity in ("same", "branch", "repository", "legacy"):
                with self.subTest(skip_gh=skip_gh, identity=identity):
                    cached_entry = {
                        "pr": {
                            "number": 7,
                            "state": "OPEN",
                            "review": "CHANGES_REQUESTED",
                            "ci": "FAILURE",
                            "url": "https://github.com/owner/repo/pull/7",
                            "author": "contributor",
                        },
                        "issue": {
                            "number": 15,
                            "state": "CLOSED",
                            "url": "https://github.com/owner/repo/issues/15",
                        },
                        "branch": "old-branch" if identity == "branch" else "review/branch",
                        "nwo": "owner/other" if identity == "repository" else "",
                        "ts": 1,
                    }
                    if identity == "legacy":
                        cached_entry.pop("nwo")

                    row, worktree, entries = self._run_quick_session_index(
                        state="OPEN",
                        author="contributor",
                        cached_entry=cached_entry,
                        skip_gh=skip_gh,
                        lookup_failure=True,
                    )

                    display, _, _, meta, *_ = row.split("\t")
                    self.assertEqual(entries[worktree], cached_entry)
                    if identity == "same":
                        self.assertIn("pr=7:OPEN:CHANGES_REQUESTED:FAILURE:https://github.com/owner/repo/pull/7", meta)
                        self.assertIn("issue=15:CLOSED:https://github.com/owner/repo/issues/15", meta)
                        self.assertIn("", display)
                        self.assertIn("", display)
                    else:
                        self.assertNotIn("pr=", meta)
                        self.assertNotIn("issue=", meta)
                        self.assertNotIn("prrole=", meta)
                        self.assertNotIn("github.com/owner/repo", row)
                        self.assertNotIn("", display)
                        self.assertNotIn("", display)

    def test_late_quick_lookup_preserves_full_metadata_and_live_worktrees(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = root / "home"
            fake_bin = root / "bin"
            fake_bin.mkdir()
            worktrees = [home / "work" / name for name in ("review", "discovered", "newly-active", "cached")]
            for worktree in worktrees:
                gitdir = root / "gitdirs" / worktree.name
                worktree.mkdir(parents=True)
                gitdir.mkdir(parents=True)
                (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
                (gitdir / "HEAD").write_text("ref: refs/heads/review/branch\n", encoding="utf-8")

            self._write_fake_sessions(
                home,
                "#!/bin/sh\n"
                'if [ "$1" = list ]; then\n'
                "  printf 'review-session\\t%s\\n' \"$PICK_SESSION_TEST_WORKTREE\"\n"
                '  if [ "$PICK_SESSION_QUICK" = 1 ]; then\n'
                "    printf 'active-session\\t%s\\n' \"$PICK_SESSION_TEST_ACTIVE_WORKTREE\"\n"
                "  fi\n"
                "fi\n"
                "exit 0\n",
            )
            for name, contents in {
                "git": "#!/bin/sh\nexit 0\n",
                "fd": "#!/bin/sh\nprintf '%s\\n' \"$PICK_SESSION_TEST_GIT_MARKERS\"\n",
                "gh": (
                    f"#!{sys.executable}\n"
                    "import json, os, re, sys\n"
                    "if sys.argv[1] != 'pr':\n"
                    "    query = next(arg[6:] for arg in sys.argv if arg.startswith('query='))\n"
                    "    result = {'pullRequest': {'reviewDecision': 'APPROVED', 'commits': {'nodes': [\n"
                    "        {'commit': {'statusCheckRollup': {'state': 'SUCCESS'}}}]}}}\n"
                    "    print(json.dumps({'data': {alias: result for alias in re.findall(r'(\\w+): repository', query)}}))\n"
                    "    raise SystemExit(0)\n"
                    "quick = os.environ['PICK_SESSION_QUICK'] == '1'\n"
                    "if quick and os.getcwd().endswith('/review'):\n"
                    "    with open(os.environ['PICK_SESSION_TEST_READY'], 'w') as ready:\n"
                    "        ready.write('ready\\n')\n"
                    "    with open(os.environ['PICK_SESSION_TEST_RELEASE']) as release:\n"
                    "        release.readline()\n"
                    "number = (7 if quick else 42) if os.getcwd().endswith('/review') else (77 if quick else 99)\n"
                    "state = 'OPEN' if quick else 'MERGED'\n"
                    "print(json.dumps({'number': number, 'state': state,\n"
                    "    'url': f'https://github.com/elastic/kibana/pull/{number}',\n"
                    "    'reviewDecision': 'REVIEW_REQUIRED', 'closingIssuesReferences': [],\n"
                    "    'author': {'login': 'contributor'}}))\n"
                ),
            }.items():
                command = fake_bin / name
                command.write_text(contents, encoding="utf-8")
                command.chmod(0o755)

            cache_home = root / "cache"
            cache_file = cache_home / "herdr-pickers" / "pick_session_gh.json"
            cache_file.parent.mkdir(parents=True)
            cache_file.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": {
                            str(worktrees[0]): {"pr": {"number": 1}, "ts": 1},
                            str(worktrees[2]): {"pr": {"number": 3}, "ts": 1},
                            str(worktrees[3]): {
                                "pr": {
                                    "number": 88,
                                    "state": "OPEN",
                                    "url": "https://github.com/elastic/kibana/pull/88",
                                    "author": "contributor",
                                },
                                "branch": "review/branch",
                                "nwo": "",
                                "ts": time.time(),
                            },
                            "/obsolete/worktree": {"pr": {"number": 2}, "ts": 1},
                        },
                    }
                ),
                encoding="utf-8",
            )
            ready_fifo = root / "ready"
            release_fifo = root / "release"
            os.mkfifo(ready_fifo)
            os.mkfifo(release_fifo)
            ready_fd = os.open(ready_fifo, os.O_RDWR | os.O_NONBLOCK)
            release_fd = os.open(release_fifo, os.O_RDWR)
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
                "PICK_SESSION_TEST_WORKTREE": str(worktrees[0]),
                "PICK_SESSION_TEST_ACTIVE_WORKTREE": str(worktrees[2]),
                "PICK_SESSION_TEST_GIT_MARKERS": "\n".join(
                    str(path / ".git") for path in (worktrees[0], worktrees[1], worktrees[3])
                ),
                "PICK_SESSION_TEST_READY": str(ready_fifo),
                "PICK_SESSION_TEST_RELEASE": str(release_fifo),
            }
            quick = subprocess.Popen(
                [sys.executable, str(INDEX_MAIN)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                start_new_session=True,
            )
            try:
                ready, _, _ = select.select([ready_fd], [], [], 5)
                self.assertTrue(ready, "quick lookup did not reach the metadata barrier")
                self.assertEqual(os.read(ready_fd, 1024), b"ready\n")
                full = subprocess.run(
                    [sys.executable, str(INDEX_MAIN)],
                    check=False,
                    capture_output=True,
                    text=True,
                    env={**env, "PICK_SESSION_QUICK": "0", "PICK_SESSION_SESSIONS_ONLY": "0"},
                    timeout=10,
                )
                self.assertEqual(full.returncode, 0, full.stderr)
                os.write(release_fd, b"continue\n")
                _, quick_stderr = quick.communicate(timeout=10)
                self.assertEqual(quick.returncode, 0, quick_stderr)
            finally:
                os.write(release_fd, b"continue\n")
                if quick.poll() is None:
                    os.killpg(quick.pid, signal.SIGKILL)
                    quick.communicate(timeout=5)
                os.close(ready_fd)
                os.close(release_fd)

            entries = json.loads(cache_file.read_text(encoding="utf-8"))["entries"]
            self.assertEqual(set(entries), {str(path) for path in worktrees})
            self.assertEqual(entries[str(worktrees[0])]["pr"]["number"], 42)
            self.assertEqual(entries[str(worktrees[0])]["pr"]["state"], "MERGED")
            self.assertEqual(entries[str(worktrees[1])]["pr"]["number"], 99)
            self.assertEqual(entries[str(worktrees[2])]["pr"]["number"], 77)
            self.assertEqual(entries[str(worktrees[3])]["pr"]["number"], 88)
            self.assertEqual(entries[str(worktrees[3])]["pr"]["ci"], "SUCCESS")

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
