#!/usr/bin/env python3
"""Tests for inject_mcp_into_opencode_jsonc.py."""

from __future__ import annotations

import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import (
    FIXTURES,
    run_script,
)


class TestInjectMcpIntoOpencode(unittest.TestCase):
    """WHEN injecting MCP servers into OpenCode JSONC."""

    def test_golden(self):
        base = (FIXTURES / "opencode_base.jsonc").read_text()
        actual = run_script(
            ["inject_mcp_into_opencode_jsonc.py", str(FIXTURES / "mcp_servers.yaml"), "false"],
            stdin=base,
        )
        expected = (FIXTURES / "golden_opencode_personal.jsonc").read_text()
        assert actual == expected


if __name__ == "__main__":
    unittest.main()
