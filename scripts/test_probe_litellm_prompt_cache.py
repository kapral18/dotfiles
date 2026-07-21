#!/usr/bin/env python3
"""Tests for LiteLLM prompt-cache probe request sequencing."""

from __future__ import annotations

import unittest
from unittest import mock

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
import probe_litellm_prompt_cache


class TestPromptCacheProbe(unittest.TestCase):
    """WHEN probing repeated prompts and tool-schema changes."""

    @mock.patch("probe_litellm_prompt_cache.time.sleep")
    @mock.patch("probe_litellm_prompt_cache.http_json")
    def test_SHOULD_preserve_the_default_repeated_prompt_sequence(self, http_json, _sleep):
        http_json.side_effect = [
            {"usage": {"prompt_tokens": 100}},
            {"usage": {"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": 80}}},
        ]

        result = probe_litellm_prompt_cache.probe_model("https://litellm.test", "key", "model-a", 2, 0, False)

        self.assertEqual(result["mode"], "repeated_prompt")
        self.assertEqual([call["label"] for call in result["calls"]], ["baseline", "repeat-1"])
        payloads = [call.args[2] for call in http_json.call_args_list]
        self.assertNotIn("tools", payloads[0])
        self.assertEqual(payloads[0], payloads[1])
        self.assertTrue(result["cache_signal_detected"])

    @mock.patch("probe_litellm_prompt_cache.time.sleep")
    @mock.patch("probe_litellm_prompt_cache.http_json")
    def test_SHOULD_change_only_the_tool_schema_in_the_four_call_sequence(self, http_json, _sleep):
        http_json.side_effect = [{"usage": {"prompt_tokens": 100}} for _ in range(4)]

        result = probe_litellm_prompt_cache.probe_model("https://litellm.test", "key", "model-a", 2, 0, True)

        self.assertEqual(result["mode"], "tool_schema_change")
        self.assertEqual(
            [call["label"] for call in result["calls"]],
            ["baseline", "baseline-repeat", "changed-schema", "changed-schema-repeat"],
        )
        payloads = [call.args[2] for call in http_json.call_args_list]
        self.assertEqual(payloads[0]["tools"], payloads[1]["tools"])
        self.assertNotEqual(payloads[1]["tools"], payloads[2]["tools"])
        self.assertEqual(payloads[2]["tools"], payloads[3]["tools"])
        for payload in payloads:
            without_tools = {key: value for key, value in payload.items() if key != "tools"}
            baseline_without_tools = {key: value for key, value in payloads[0].items() if key != "tools"}
            self.assertEqual(without_tools, baseline_without_tools)
        self.assertFalse(result["cache_signal_detected"])


if __name__ == "__main__":
    unittest.main()
