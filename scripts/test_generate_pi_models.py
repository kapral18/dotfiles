#!/usr/bin/env python3
"""Tests for generate_pi_models.py."""

from __future__ import annotations

import json
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import (
    FIXTURES,
    REPO,
    run_script,
)


class TestGeneratePiModels(unittest.TestCase):
    """WHEN generating Pi models JSON."""

    def test_golden(self):
        actual = run_script(
            [
                "generate_pi_models.py",
                str(REPO / "home/dot_pi/agent/readonly_models.json"),
                str(FIXTURES / "ai_models.yaml"),
                "http://localhost:4000/v1",
                "https://test-resource.services.ai.azure.com/openai/v1",
            ]
        )
        expected = (FIXTURES / "golden_pi_models.json").read_text()
        assert json.loads(actual) == json.loads(expected)


if __name__ == "__main__":
    unittest.main()
