#!/usr/bin/env python3
"""Unit tests for session picker GitHub cache update semantics."""

from __future__ import annotations

import ast
import json
import shutil
import sys
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


if __name__ == "__main__":
    unittest.main()
