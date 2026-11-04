#!/usr/bin/env python3
"""Regression tests for exact GitHub-picker review-request roles."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

from _test_support import REPO

MODULE = REPO / "home/dot_config/exact_tmux/exact_scripts/pickers/github/lib/gh_items_main.py"


def _load_module():
    loader = SourceFileLoader("gh_items_review_requests_test", str(MODULE))
    spec = importlib.util.spec_from_loader("gh_items_review_requests_test", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load gh picker items module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestReviewRequestActors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_module()

    def test_direct_request_does_not_match_team_only_pr(self):
        actors = self.module._review_request_actor_keys(
            {
                "reviewRequests": {
                    "nodes": [
                        {
                            "requestedReviewer": {
                                "__typename": "Team",
                                "slug": "cloud-ui",
                                "organization": {"login": "elastic"},
                            }
                        }
                    ]
                }
            }
        )

        self.assertEqual(actors, {"team:elastic/cloud-ui"})

    def test_direct_request_stays_visible_when_teams_are_also_requested(self):
        actors = self.module._review_request_actor_keys(
            {
                "reviewRequests": {
                    "nodes": [
                        {
                            "requestedReviewer": {
                                "__typename": "User",
                                "login": "kapral18",
                            }
                        },
                        {
                            "requestedReviewer": {
                                "__typename": "Team",
                                "slug": "cloud-ui",
                                "organization": {"login": "elastic"},
                            }
                        },
                    ]
                }
            }
        )

        self.assertIn("user:kapral18", actors)
        self.assertIn("team:elastic/cloud-ui", actors)

    def test_graphql_item_matches_picker_filters(self):
        item = self.module._graphql_review_request_item(
            {
                "number": 42,
                "title": "Direct review",
                "url": "https://github.com/elastic/kibana/pull/42",
                "isDraft": False,
                "state": "OPEN",
                "createdAt": "2026-07-28T00:00:00Z",
                "updatedAt": "2026-07-28T00:00:00Z",
                "repository": {"nameWithOwner": "elastic/kibana"},
                "author": {"login": "someone"},
                "assignees": {"nodes": []},
                "labels": {"nodes": []},
                "comments": {"totalCount": 0},
            },
            "pr",
        )

        self.assertTrue(
            self.module._matches_current_search_filters(
                item,
                "pr",
                "is:open is:pr review-requested:@me org:elastic -is:draft -author:@me",
                "kapral18",
            )
        )

    def test_team_queue_reason_is_not_personal_review(self):
        filters = "is:open is:pr review-requested:@me org:elastic -is:draft -author:@me"

        self.assertEqual(
            self.module._section_reason(filters, "review-requested-team:elastic/cloud-ui"),
            "team review queue",
        )
        self.assertEqual(
            self.module._section_reason(filters, "review-requested-direct"),
            "needs my review",
        )


class TestLocalIssueIdentity(unittest.TestCase):
    def test_foreign_issue_metadata_blocks_number_markers_and_suffix_fallback_but_keeps_pr_branch(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            repo = root / "repo"
            repo.mkdir()
            env = {
                **os.environ,
                "HOME": str(home),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_AUTHOR_NAME": "Fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "Fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            }

            def git(*args):
                return subprocess.run(
                    ["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True
                ).stdout

            git("init", "-q", "-b", "main")
            (repo / "README").write_text("fixture\n")
            git("add", "README")
            git("commit", "-qm", "fixture")
            git("remote", "add", "origin", "https://github.com/wanted/repo.git")
            git("config", "extensions.worktreeConfig", "true")
            for branch, owner, number in (
                ("fix-42", "other/repo", "42"),
                ("fix-43", "WANTED/Repo", "43"),
                ("legacy-44", "", ""),
                ("legacy-metadata", "", "45"),
            ):
                worktree = root / branch
                git("worktree", "add", "-q", "-b", branch, str(worktree))
                if owner:
                    git("-C", str(worktree), "config", "--worktree", "comma.w.issue.repo", owner)
                if number:
                    git("-C", str(worktree), "config", "--worktree", "comma.w.issue.number", number)

            with mock.patch.dict(os.environ, env, clear=True):
                numbers, branches, suffix_sources = module._scan_local_worktrees("wanted/repo", str(repo))

            self.assertEqual(numbers, {43, 44, 45})
            self.assertIn("fix-42", branches)
            self.assertEqual(suffix_sources, {43: "fix-43", 44: "legacy-44"})


if __name__ == "__main__":
    unittest.main()
