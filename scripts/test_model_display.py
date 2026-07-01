#!/usr/bin/env python3
"""Tests for model_display.py."""

from __future__ import annotations

import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)


class TestModelDisplay(unittest.TestCase):
    """WHEN formatting model display names."""

    def test_reasoning_model_with_cost(self):
        from model_display import format_display_name

        m = {"id": "test", "name": "Test", "reasoning": True, "cost": {"input": 5, "output": 25}}
        assert format_display_name(m) == "Test \U0001f9e0 ($5in/$25out)"

    def test_non_reasoning_model_with_float_cost(self):
        from model_display import format_display_name

        m = {"id": "test", "name": "Test", "reasoning": False, "cost": {"input": 0.5, "output": 1.5}}
        assert format_display_name(m) == "Test ($0.5in/$1.5out)"

    def test_model_without_cost(self):
        from model_display import format_display_name

        m = {"id": "test", "name": "Test"}
        assert format_display_name(m) == "Test"


if __name__ == "__main__":
    unittest.main()
