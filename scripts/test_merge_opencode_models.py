#!/usr/bin/env python3
"""Tests for merge_opencode_models.py."""

from __future__ import annotations

import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import (
    FIXTURES,
    run_script,
)


class TestMergeOpencodeModels(unittest.TestCase):
    """WHEN merging AI models into OpenCode JSONC."""

    def test_golden(self):
        actual = run_script(
            [
                "merge_opencode_models.py",
                str(FIXTURES / "opencode_work_base.jsonc"),
                str(FIXTURES / "ai_models.yaml"),
            ]
        )
        expected = (FIXTURES / "golden_opencode_models.jsonc").read_text()
        assert actual == expected

    def test_claude_models_routed_to_litellm_anthropic(self):
        actual = run_script(
            [
                "merge_opencode_models.py",
                str(FIXTURES / "opencode_work_base.jsonc"),
                str(FIXTURES / "ai_models_with_claude.yaml"),
            ]
        )
        expected = (FIXTURES / "golden_opencode_models_with_claude.jsonc").read_text()
        assert actual == expected


if __name__ == "__main__":
    unittest.main()
