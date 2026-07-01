#!/usr/bin/env python3
"""Tests for ai_models.py."""

from __future__ import annotations

import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import FIXTURES


class TestAiModels(unittest.TestCase):
    """WHEN loading AI models from YAML."""

    def test_load_litellm_models(self):
        from ai_models import load_litellm

        models = load_litellm(str(FIXTURES / "ai_models.yaml"))
        assert len(models) == 2
        assert models[0]["id"] == "llm-gateway/model-a"
        assert models[0]["reasoning"] is True
        assert models[0]["cost"]["input"] == 5
        assert models[1]["reasoning"] is False
        assert models[1]["cost"]["input"] == 0.5

    def test_load_azure_models_empty(self):
        from ai_models import load_azure

        models = load_azure(str(FIXTURES / "ai_models.yaml"))
        assert len(models) == 0


if __name__ == "__main__":
    unittest.main()
