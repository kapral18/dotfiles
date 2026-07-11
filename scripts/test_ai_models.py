#!/usr/bin/env python3
"""Tests for ai_models.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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

    def test_load_model_mirror_policy_sections(self):
        from ai_models import (
            load_agent_review_models,
            load_cursor_models,
            load_pi_extra_models,
            load_provider_models,
        )

        path = FIXTURES / "ai_models.yaml"
        cursor = load_cursor_models(path)
        pi = load_pi_extra_models(path)
        providers = load_provider_models(path)
        review = load_agent_review_models(path)

        assert cursor == [
            {"id": "cursor-model-a", "recommended": True},
            {"id": "cursor-model-b"},
        ]
        assert pi == [{"id": "openrouter/model-a", "recommended": True}]
        assert providers == [{"provider": "openrouter", "id": "provider-model-a", "recommended": True}]
        assert review["cursor"] == {"lanes": "cursor-model-a", "verifier": "cursor-model-b"}
        assert review["copilot"] == {"lanes": "gpt-model", "verifier": "claude-model"}

    def test_cursor_policy_fails_closed_when_missing_empty_or_unrecognized(self):
        from ai_models import load_cursor_models

        cases = {
            "missing": "litellm_models:\n  - id: model-a\n",
            "empty": "cursor_models:\nlitellm_models:\n",
            "unrecognized": "cursor_models:\n  models: cursor-model-a\n",
        }
        for name, contents in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "ai_models.yaml"
                path.write_text(contents)
                with self.assertRaisesRegex(ValueError, "cursor_models"):
                    load_cursor_models(path)


if __name__ == "__main__":
    unittest.main()
