#!/usr/bin/env python3
"""Regression tests for exact GitHub-picker review-request roles."""

from __future__ import annotations

import importlib.util
import unittest
from importlib.machinery import SourceFileLoader

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
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
        self.assertNotIn("user:kapral18", actors)

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

    def test_team_actor_uses_fully_qualified_key(self):
        actors = self.module._review_request_actor_keys(
            {
                "reviewRequests": {
                    "nodes": [
                        {
                            "requestedReviewer": {
                                "__typename": "Team",
                                "slug": "ai-guild-docs",
                                "organization": {"login": "elastic"},
                            }
                        }
                    ]
                }
            }
        )

        self.assertEqual(actors, {"team:elastic/ai-guild-docs"})

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


if __name__ == "__main__":
    unittest.main()
