#!/usr/bin/env python3
"""Tests for deterministic model/provider mirrors and opt-in live drift."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import FIXTURES, REPO

MIRROR_PATH = REPO / "home/dot_config/ai/readonly_model-mirrors.v1.json"
PROBE_CASES = json.loads((FIXTURES / "model_probe_cases.json").read_text())


class TestStaticModelMirrors(unittest.TestCase):
    """WHEN building the static mirror from registries, configs, and capability data."""

    def test_SHOULD_cover_all_harnesses_and_configured_provider_routes(self):
        import model_mirrors

        mirror = model_mirrors.build_static_mirror(REPO)

        self.assertEqual(
            set(mirror["harnesses"]),
            {"cursor", "claude", "codex", "gemini", "opencode", "pi", "copilot"},
        )
        self.assertEqual(
            set(mirror["providers"]),
            {
                "azure-foundry",
                "cloudflare-openai",
                "cloudflare-workers-ai",
                "litellm",
                "litellm-anthropic",
                "llama-cpp",
                "openrouter",
            },
        )
        model_mirrors.validate_mirror(mirror)

    def test_SHOULD_generate_deterministic_network_free_bytes(self):
        import model_mirrors

        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("static generation used network")):
            first = model_mirrors.render_static_mirror(REPO)
            second = model_mirrors.render_static_mirror(REPO)

        self.assertEqual(first, second)
        self.assertEqual(first, MIRROR_PATH.read_text())

    def test_SHOULD_keep_available_curated_and_recommended_distinct(self):
        import model_mirrors

        mirror = model_mirrors.build_static_mirror(REPO)
        cursor = mirror["harnesses"]["cursor"]
        gemini = mirror["harnesses"]["gemini"]

        self.assertLess(
            set(cursor["recommended"]["models"]),
            set(cursor["curated"]["models"]),
        )
        self.assertGreater(
            set(gemini["available"]["models"]),
            set(gemini["curated"]["models"]),
        )
        self.assertNotIn("new-live", cursor["curated"]["models"])

    def test_SHOULD_encode_unknown_and_error_without_empty_success(self):
        import model_mirrors

        mirror = model_mirrors.build_static_mirror(REPO)
        for harness in ("codex", "copilot"):
            state = mirror["harnesses"][harness]["available"]
            self.assertEqual(state["status"], "unknown")
            self.assertEqual(state["models"], [])
            self.assertTrue(state["reason"])
            self.assertIsNone(state["complete"])

        invalid = copy.deepcopy(mirror)
        invalid["harnesses"]["codex"]["available"]["models"] = ["not-allowed"]
        with self.assertRaisesRegex(ValueError, "unknown.*models"):
            model_mirrors.validate_mirror(invalid)

        valid_error = copy.deepcopy(mirror)
        valid_error["harnesses"]["codex"]["available"] = {
            "complete": None,
            "models": [],
            "provenance": [{"kind": "installed-harness", "source": "fixture"}],
            "reason": "catalog command failed during capability capture",
            "status": "error",
        }
        model_mirrors.validate_mirror(valid_error)

        invalid = copy.deepcopy(mirror)
        invalid["harnesses"]["codex"]["available"] = {
            "complete": None,
            "models": [],
            "provenance": [],
            "reason": None,
            "status": "error",
        }
        with self.assertRaisesRegex(ValueError, "reason"):
            model_mirrors.validate_mirror(invalid)

    def test_SHOULD_keep_canonical_registry_ids_in_generated_consumers(self):
        import ai_models
        import model_mirrors

        mirror = model_mirrors.build_static_mirror(REPO)
        litellm_ids = {model["id"] for model in ai_models.load_litellm(REPO / "home/.chezmoidata/ai_models.yaml")}

        self.assertTrue(litellm_ids)
        self.assertLessEqual(litellm_ids, set(mirror["providers"]["litellm"]["curated"]["models"]))
        self.assertLessEqual(litellm_ids, set(mirror["harnesses"]["pi"]["curated"]["models"]))

    def test_SHOULD_fail_generation_for_invalid_cursor_policy(self):
        import model_mirrors

        cases = {
            "empty": [],
            "missing_id": [{"recommended": True}],
            "invalid_id": [{"id": "not a model id"}],
            "non_string_id": [{"id": 42}],
        }
        for name, policy in cases.items():
            with (
                self.subTest(name=name),
                mock.patch.object(model_mirrors.ai_models, "load_cursor_models", return_value=policy),
                self.assertRaisesRegex(ValueError, "cursor_models"),
            ):
                model_mirrors.build_static_mirror(REPO)

    def test_SHOULD_fail_generation_for_unsupported_provider_models_provider(self):
        import model_mirrors

        cases = {
            "typo": [{"id": "real-model", "provider": "openrouterr"}],
            "missing_provider": [{"id": "real-model"}],
            "known_but_unrouted": [{"id": "real-model", "provider": "litellm"}],
        }
        for name, policy in cases.items():
            with (
                self.subTest(name=name),
                mock.patch.object(model_mirrors.ai_models, "load_provider_models", return_value=policy),
                self.assertRaisesRegex(ValueError, "provider_models"),
            ):
                model_mirrors.build_static_mirror(REPO)

    def test_SHOULD_record_every_canonical_catalog_source(self):
        import model_mirrors

        mirror = model_mirrors.build_static_mirror(REPO)

        def sources(harness: str, set_name: str) -> set[tuple[str, str | None]]:
            return {
                (item["source"], item.get("section"))
                for item in mirror["harnesses"][harness][set_name]["provenance"]
                if item["kind"] in {"config", "registry"}
            }

        registry = "home/.chezmoidata/ai_models.yaml"
        self.assertEqual(
            sources("copilot", "curated"),
            {(registry, "agent_review_models")},
        )
        self.assertEqual(
            sources("copilot", "recommended"),
            {(registry, "agent_review_models")},
        )

        expected = {
            "claude": {
                ("home/dot_claude/settings.work.json", None),
                ("home/dot_claude/settings.personal.json", None),
            },
            "codex": {
                ("home/dot_codex/private_config.work.toml", None),
                ("home/dot_codex/private_config.personal.toml", None),
            },
            "opencode": {
                ("home/dot_config/opencode/readonly_opencode.work.jsonc", None),
                ("home/dot_config/opencode/readonly_opencode.personal.jsonc", None),
                (registry, "litellm_models"),
                (registry, "azure_models"),
            },
            "pi": {
                (registry, "litellm_models"),
                (registry, "pi_extra_models"),
            },
        }
        for harness, expected_sources in expected.items():
            with self.subTest(harness=harness):
                self.assertEqual(sources(harness, "curated"), expected_sources)
                self.assertLessEqual(expected_sources, sources(harness, "available"))

    def test_SHOULD_match_committed_json_and_generated_go_outputs(self):
        import model_mirrors

        mirror = model_mirrors.build_static_mirror(REPO)

        self.assertEqual(json.loads(MIRROR_PATH.read_text()), mirror)

    def test_SHOULD_remove_manual_consumer_and_provider_fallback_lists(self):
        mirror = json.loads(MIRROR_PATH.read_text())
        fish_source = (REPO / "home/dot_config/fish/functions/readonly___comma_provider_models.fish").read_text()

        self.assertIn("model-mirrors.v1.json", fish_source)
        for provider in ("openrouter", "cloudflare-workers-ai", "cloudflare-openai"):
            for model in mirror["providers"][provider]["curated"]["models"]:
                self.assertNotIn(model, fish_source)


class TestModelMirrorAdapters(unittest.TestCase):
    """WHEN consumers request a stable view of the generated mirror."""

    def test_SHOULD_expose_launcher_contract_without_choosing_policy(self):
        import model_mirrors

        mirror = model_mirrors.load_mirror(MIRROR_PATH)
        view = model_mirrors.consumer_view(
            mirror,
            "launcher",
            "gemini",
            set_name="available",
        )

        self.assertEqual(view["schema_version"], "1.0.0")
        self.assertEqual(view["consumer"], "launcher")
        self.assertEqual(view["harness"], "gemini")
        self.assertEqual(view["set"], "available")
        self.assertEqual(view["status"], "known")
        self.assertTrue(view["models"])

        completed = subprocess.run(
            [
                "python3",
                str(REPO / "scripts/model_mirrors.py"),
                "adapt",
                "--mirror",
                str(MIRROR_PATH),
                "--consumer",
                "launcher",
                "--harness",
                "gemini",
                "--set",
                "available",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(completed.stdout), view)


class TestLiveModelMirrorDrift(unittest.TestCase):
    """WHEN an operator explicitly probes a live harness/provider catalog."""

    @staticmethod
    def _fixture(name: str) -> dict:
        return copy.deepcopy(PROBE_CASES[name])

    def test_SHOULD_report_stale_curated_and_new_live_ids_without_promotion(self):
        import model_mirrors

        mirror = model_mirrors.synthetic_mirror(
            target="harness:cursor",
            curated=["curated-stable", "curated-missing"],
            recommended=["curated-stable"],
        )
        curated_before = list(mirror["harnesses"]["cursor"]["curated"]["models"])

        result = model_mirrors.probe_target(
            mirror,
            "harness:cursor",
            fixture=self._fixture("cursor_success"),
        )

        self.assertEqual(result["status"], "drift")
        self.assertEqual(result["stale_curated"], ["curated-missing"])
        self.assertEqual(result["new_available"], ["curated-stale", "new-live"])
        self.assertEqual(
            mirror["harnesses"]["cursor"]["curated"]["models"],
            curated_before,
            "live availability must never mutate or promote curated policy",
        )

    def test_SHOULD_report_unknown_for_failure_empty_or_unparseable_catalogs(self):
        import model_mirrors

        mirror = model_mirrors.synthetic_mirror(
            target="harness:cursor",
            curated=["curated-stable"],
            recommended=["curated-stable"],
        )
        cases = [
            self._fixture("cursor_command_failure"),
            {"target": "harness:cursor", "returncode": 0, "stdout": "", "stderr": ""},
            self._fixture("cursor_unparseable"),
            {"target": "harness:cursor", "state": "unknown", "reason": "timeout"},
            {"target": "harness:cursor", "state": "error", "reason": "malformed response"},
        ]

        for fixture in cases:
            with self.subTest(fixture=fixture):
                result = model_mirrors.probe_target(mirror, "harness:cursor", fixture=fixture)
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["live"]["models"], [])
                self.assertTrue(result["reason"])
                self.assertNotIn("SENSITIVE-FIXTURE-TEXT", json.dumps(result))

    def test_SHOULD_parse_verified_command_and_provider_fixtures(self):
        import model_mirrors

        mirror = model_mirrors.synthetic_mirror(
            target="harness:pi",
            curated=["openrouter/curated-stable"],
            recommended=["openrouter/curated-stable"],
        )
        pi = model_mirrors.probe_target(mirror, "harness:pi", fixture=self._fixture("pi_success"))
        self.assertEqual(
            pi["live"]["models"],
            [
                "openrouter/curated-stable",
                "openrouter/new-live",
                "openrouter/~anthropic/claude-opus-latest",
            ],
        )

        opencode_mirror = model_mirrors.synthetic_mirror(
            target="harness:opencode",
            curated=["openrouter/curated-stable"],
            recommended=["openrouter/curated-stable"],
        )
        opencode = model_mirrors.probe_target(
            opencode_mirror,
            "harness:opencode",
            fixture=self._fixture("opencode_success"),
        )
        self.assertEqual(
            opencode["live"]["models"],
            ["openrouter/curated-stable", "openrouter/new-live"],
        )

        provider_mirror = model_mirrors.synthetic_mirror(
            target="provider:openrouter",
            curated=["curated-stable"],
            recommended=["curated-stable"],
        )
        openrouter = model_mirrors.probe_target(
            provider_mirror,
            "provider:openrouter",
            fixture=self._fixture("openrouter_success"),
        )
        self.assertEqual(openrouter["live"]["models"], ["curated-stable", "new-live"])

        malformed = model_mirrors.probe_target(
            provider_mirror,
            "provider:openrouter",
            fixture={"target": "provider:openrouter", "payload": []},
        )
        self.assertEqual(malformed["status"], "unknown")
        self.assertEqual(malformed["reason"], "unparseable_output")

    def test_SHOULD_reject_any_invalid_http_provider_model_id(self):
        import model_mirrors

        mirror = model_mirrors.build_static_mirror(REPO)
        payloads = {
            "provider:openrouter": lambda value: {
                "data": [
                    {
                        "id": "valid-model",
                        "architecture": {
                            "input_modalities": ["text"],
                            "output_modalities": ["text"],
                        },
                    },
                    {
                        "id": value,
                        "architecture": {
                            "input_modalities": ["text"],
                            "output_modalities": ["text"],
                        },
                    },
                ]
            },
            "provider:litellm": lambda value: {"data": [{"id": "valid-model"}, {"id": value}]},
            "provider:cloudflare-openai": lambda value: {"data": [{"id": "valid-model"}, {"id": value}]},
            "provider:llama-cpp": lambda value: {"data": [{"id": "valid-model"}, {"id": value}]},
            "provider:cloudflare-workers-ai": lambda value: {"result": [{"name": "@cf/valid-model"}, {"name": value}]},
        }
        for target, payload in payloads.items():
            for invalid_id in ("not a model id", 42):
                with self.subTest(target=target, invalid_id=invalid_id):
                    result = model_mirrors.probe_target(
                        mirror,
                        target,
                        fixture={"target": target, "payload": payload(invalid_id)},
                    )
                    self.assertEqual(result["status"], "unknown")
                    self.assertEqual(result["live"]["models"], [])
                    self.assertEqual(result["reason"], "unparseable_output")

    def test_SHOULD_run_cli_fixtures_without_falling_through_to_live_probe(self):
        result = subprocess.run(
            [
                "python3",
                str(REPO / "scripts/model_mirrors.py"),
                "probe",
                "--mirror",
                str(MIRROR_PATH),
                "--target",
                "provider:openrouter",
                "--fixture",
                str(FIXTURES / "model_probe_cases.json"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(payload["kind"], "ai.model-mirror-drift")
        self.assertEqual(payload["results"][0]["target"], "provider:openrouter")
        self.assertEqual(
            payload["results"][0]["live"]["models"],
            ["curated-stable", "new-live"],
        )

    def test_SHOULD_bound_real_probe_commands_and_redact_failures(self):
        import model_mirrors

        with mock.patch.object(model_mirrors, "MAX_COMMAND_OUTPUT_BYTES", 1024):
            with self.assertRaises(model_mirrors.CommandOutputTooLarge):
                model_mirrors.run_bounded_command(
                    [sys.executable, "-c", "print('x' * 2048)"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
        with self.assertRaises(subprocess.TimeoutExpired):
            model_mirrors.run_bounded_command(
                [sys.executable, "-c", "import time; time.sleep(1)"],
                capture_output=True,
                text=True,
                timeout=0.01,
            )

        mirror = model_mirrors.synthetic_mirror(
            target="harness:cursor",
            curated=["curated-stable"],
            recommended=["curated-stable"],
        )
        completed = subprocess.CompletedProcess(
            ["cursor-agent", "--list-models"],
            1,
            "",
            "Authorization failed: SENSITIVE-FIXTURE-TEXT",
        )
        runner = mock.Mock(return_value=completed)

        result = model_mirrors.probe_target(
            mirror,
            "harness:cursor",
            runner=runner,
            which=lambda _name: "/verified/cursor-agent",
        )

        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("SENSITIVE-FIXTURE-TEXT", json.dumps(result))
        args, kwargs = runner.call_args
        self.assertEqual(args[0], ["/verified/cursor-agent", "--list-models"])
        self.assertLessEqual(kwargs["timeout"], 20)
        self.assertTrue(kwargs["capture_output"])

        oversized = subprocess.CompletedProcess(
            ["cursor-agent", "--list-models"],
            0,
            "x" * (model_mirrors.MAX_COMMAND_OUTPUT_BYTES + 1),
            "",
        )
        result = model_mirrors.probe_target(
            mirror,
            "harness:cursor",
            runner=mock.Mock(return_value=oversized),
            which=lambda _name: "/verified/cursor-agent",
        )
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "output_too_large")

    def test_SHOULD_use_provider_credentials_without_exposing_failures(self):
        import model_mirrors

        mirror = model_mirrors.build_static_mirror(REPO)
        self.assertEqual(
            mirror["providers"]["litellm"]["live_probe"]["max_response_bytes"],
            model_mirrors.MAX_HTTP_RESPONSE_BYTES,
        )
        fetch = mock.Mock(side_effect=RuntimeError("transport leaked SENSITIVE-FIXTURE-TEXT"))
        with mock.patch.dict(
            os.environ,
            {
                "LITELLM_API_BASE": "https://litellm.invalid/v1",
                "LITELLM_PROXY_KEY": "SENSITIVE-FIXTURE-TEXT",
            },
            clear=False,
        ):
            result = model_mirrors.probe_target(
                mirror,
                "provider:litellm",
                fetch_json=fetch,
            )

        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("SENSITIVE-FIXTURE-TEXT", json.dumps(result))
        args, _kwargs = fetch.call_args
        self.assertEqual(args[0], "https://litellm.invalid/v1/models")
        self.assertEqual(args[1]["Authorization"], "Bearer SENSITIVE-FIXTURE-TEXT")
        self.assertLessEqual(args[2], 10)

        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"x" * (model_mirrors.MAX_HTTP_RESPONSE_BYTES + 1)
        with mock.patch("urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "byte limit"):
                model_mirrors._fetch_json("https://catalog.invalid/models", {}, 1)
        response.__enter__.return_value.read.assert_called_once_with(model_mirrors.MAX_HTTP_RESPONSE_BYTES + 1)


if __name__ == "__main__":
    unittest.main()
