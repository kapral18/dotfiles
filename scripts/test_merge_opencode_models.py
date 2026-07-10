#!/usr/bin/env python3
"""Tests for merge_opencode_models.py."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import (
    FIXTURES,
    REPO,
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

    def test_when_litellm_model_disables_effort_should_strip_provider_option(self):
        plugin = REPO / "home/dot_config/opencode/plugins/litellm-compat.ts.tmpl"
        rendered = subprocess.run(
            ["chezmoi", "execute-template"],
            input=plugin.read_text(),
            capture_output=True,
            text=True,
            cwd=REPO,
        )
        assert rendered.returncode == 0, rendered.stderr
        with tempfile.TemporaryDirectory() as directory:
            rendered_plugin = f"{directory}/litellm-compat.ts"
            with open(rendered_plugin, "w") as f:
                f.write(rendered.stdout)

            script = f"""
const {{ LitellmCompatPlugin }} = await import({json.dumps(f"file://{rendered_plugin}")})
const hooks = await LitellmCompatPlugin()
const flagged = {{ options: {{ reasoningEffort: "medium", reasoning_effort: "high", textVerbosity: "low" }} }}
await hooks["chat.params"](
  {{ model: {{ providerID: "litellm", api: {{ id: "llm-gateway/gpt-5.6-luna" }} }} }},
  flagged,
)
const control = {{ options: {{ reasoningEffort: "medium", textVerbosity: "low" }} }}
await hooks["chat.params"](
  {{ model: {{ providerID: "litellm", api: {{ id: "llm-gateway/gemini-3.5-flash" }} }} }},
  control,
)
console.log(JSON.stringify({{ flagged, control }}))
"""
            result = subprocess.run(
                ["node", "--no-warnings", "--input-type=module", "-e", script],
                capture_output=True,
                text=True,
            )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {
            "flagged": {"options": {"textVerbosity": "low", "drop_params": True}},
            "control": {"options": {"reasoningEffort": "medium", "textVerbosity": "low"}},
        }


if __name__ == "__main__":
    unittest.main()
