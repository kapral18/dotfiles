#!/usr/bin/env python3
"""Tests for yaml_parser.py (colocated). Split from the former test_scripts.py."""

from __future__ import annotations

import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)


class TestYamlParser(unittest.TestCase):
    """WHEN parsing YAML scalars."""

    def test_parse_scalar_types(self):
        from yaml_parser import parse_scalar

        assert parse_scalar("true") is True
        assert parse_scalar("false") is False
        assert parse_scalar("42") == 42
        assert parse_scalar("3.14") == 3.14
        assert parse_scalar('"hello"') == "hello"
        assert parse_scalar("'world'") == "world"
        assert parse_scalar("bare") == "bare"


if __name__ == "__main__":
    unittest.main()
