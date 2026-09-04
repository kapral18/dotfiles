#!/usr/bin/env python3
"""Tests for deterministic model/provider mirrors and opt-in live drift."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import FIXTURES, REPO

MIRROR_PATH = REPO / "home/dot_config/ai/readonly_model-mirrors.v1.json"
PROBE_CASES = json.loads((FIXTURES / "model_probe_cases.json").read_text())


def render_chezmoi_template(path, *, is_work):
    if shutil.which("chezmoi") is None:
        raise unittest.SkipTest("chezmoi is required to render templates")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml") as config:
        config.write(f"[data]\nisWork = {str(is_work).lower()}\n")
        config.flush()
        result = subprocess.run(
            ["chezmoi", "--source", str(REPO), "--config", config.name, "execute-template"],
            input=path.read_text(),
            capture_output=True,
            text=True,
            check=True,
            cwd=str(REPO),
        )
    return result.stdout


def parse_ini_settings(block):
    settings = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip()] = value.strip()
    return settings


def effective_ini_settings(text, section):
    defaults = parse_ini_settings(text.split("[*]", 1)[1].split("\n[", 1)[0])
    section_block = text.split(f"[{section}]", 1)[1].split("\n[", 1)[0]
    return defaults | parse_ini_settings(section_block)


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
                "llama-cpp",
                "openrouter",
            },
        )
        model_mirrors.validate_mirror(mirror)

    def test_SHOULD_keep_llama_cpp_model_ids_aligned_across_consumers(self):
        import model_mirrors

        pi_work = json.loads((REPO / "home/dot_pi/agent/readonly_models.json").read_text())
        expected = {model["id"] for model in pi_work["providers"]["llama-cpp"]["models"]}
        self.assertEqual(
            expected,
            {
                "nemotron-3.5",
                "qwen3.5-9b",
                "qwen3.8-27b",
                "qwen3.8-27b-instruct",
            },
        )

        pi_personal = json.loads((REPO / "home/dot_pi/agent/readonly_models.personal.json").read_text())
        self.assertEqual(
            {model["id"] for model in pi_personal["providers"]["llama-cpp"]["models"]},
            expected,
        )
        pi_work_context = {model["id"]: model["contextWindow"] for model in pi_work["providers"]["llama-cpp"]["models"]}
        pi_personal_context = {
            model["id"]: model["contextWindow"] for model in pi_personal["providers"]["llama-cpp"]["models"]
        }
        preserved_262k_models = ("nemotron-3.5", "qwen3.5-9b")
        for model_id in preserved_262k_models:
            with self.subTest(consumer="pi", model=model_id):
                self.assertEqual(262144, pi_work_context[model_id])
                self.assertEqual(262144, pi_personal_context[model_id])
        self.assertEqual(131072, pi_work_context["qwen3.8-27b"])
        self.assertEqual(131072, pi_work_context["qwen3.8-27b-instruct"])
        self.assertEqual(262144, pi_personal_context["qwen3.8-27b"])
        self.assertEqual(262144, pi_personal_context["qwen3.8-27b-instruct"])

        for profile in ("work", "personal"):
            config = model_mirrors._read_jsonc(REPO / f"home/dot_config/opencode/readonly_opencode.{profile}.jsonc")
            self.assertEqual(set(config["provider"]["llama-cpp"]["models"]), expected)

        codex_template = REPO / "home/dot_codex/readonly_llama-cpp-model-catalog.json.tmpl"
        codex_work = json.loads(render_chezmoi_template(codex_template, is_work=True))
        codex_personal = json.loads(render_chezmoi_template(codex_template, is_work=False))
        self.assertEqual({model["slug"] for model in codex_work["models"]}, expected)
        self.assertEqual({model["slug"] for model in codex_personal["models"]}, expected)
        codex_work_context = {model["slug"]: model["context_window"] for model in codex_work["models"]}
        codex_personal_context = {model["slug"]: model["context_window"] for model in codex_personal["models"]}
        codex_work_max_context = {model["slug"]: model["max_context_window"] for model in codex_work["models"]}
        codex_personal_max_context = {model["slug"]: model["max_context_window"] for model in codex_personal["models"]}
        codex_work_compact = {model["slug"]: model["auto_compact_token_limit"] for model in codex_work["models"]}
        codex_personal_compact = {
            model["slug"]: model["auto_compact_token_limit"] for model in codex_personal["models"]
        }
        for model_id in preserved_262k_models:
            with self.subTest(consumer="codex", model=model_id):
                self.assertEqual(262144, codex_work_context[model_id])
                self.assertEqual(262144, codex_personal_context[model_id])
                self.assertEqual(262144, codex_work_max_context[model_id])
                self.assertEqual(262144, codex_personal_max_context[model_id])
                self.assertEqual(200000, codex_work_compact[model_id])
                self.assertEqual(200000, codex_personal_compact[model_id])
        self.assertEqual(131072, codex_work_context["qwen3.8-27b"])
        self.assertEqual(131072, codex_work_context["qwen3.8-27b-instruct"])
        self.assertEqual(131072, codex_work_max_context["qwen3.8-27b"])
        self.assertEqual(131072, codex_work_max_context["qwen3.8-27b-instruct"])
        self.assertEqual(100000, codex_work_compact["qwen3.8-27b"])
        self.assertEqual(100000, codex_work_compact["qwen3.8-27b-instruct"])
        self.assertEqual(262144, codex_personal_context["qwen3.8-27b"])
        self.assertEqual(262144, codex_personal_context["qwen3.8-27b-instruct"])
        self.assertEqual(262144, codex_personal_max_context["qwen3.8-27b"])
        self.assertEqual(262144, codex_personal_max_context["qwen3.8-27b-instruct"])
        self.assertEqual(200000, codex_personal_compact["qwen3.8-27b"])
        self.assertEqual(200000, codex_personal_compact["qwen3.8-27b-instruct"])

        router_text = (REPO / "home/dot_config/llama.cpp/models.ini.tmpl").read_text()
        router_work = render_chezmoi_template(REPO / "home/dot_config/llama.cpp/models.ini.tmpl", is_work=True)
        router_personal = render_chezmoi_template(REPO / "home/dot_config/llama.cpp/models.ini.tmpl", is_work=False)
        router_ids = set(re.findall(r"^\[([^*][^]]*)\]$", router_text, flags=re.MULTILINE))
        self.assertEqual(router_ids, expected)
        for model_id in preserved_262k_models:
            with self.subTest(consumer="router", model=model_id):
                self.assertEqual("262144", effective_ini_settings(router_work, model_id).get("ctx-size"))
                self.assertEqual("262144", effective_ini_settings(router_work, model_id).get("n-predict"))
                self.assertEqual("262144", effective_ini_settings(router_personal, model_id).get("ctx-size"))
                self.assertEqual("262144", effective_ini_settings(router_personal, model_id).get("n-predict"))

        manifest = (REPO / "home/readonly_dot_default-llama-cpp-models.tmpl").read_text()
        self.assertIn(
            "unsloth/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF|NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_XL.gguf",
            manifest,
        )
        self.assertNotIn("ggml-org/", manifest)
        self.assertIn("unsloth/Qwen3.5-9B-GGUF|Qwen3.5-9B-UD-Q4_K_XL.gguf", manifest)
        self.assertIn(
            "unsloth/Qwen3.5-9B-GGUF|mmproj-F16.gguf|Qwen3.5-9B-mmproj-F16.gguf",
            manifest,
        )
        self.assertIn("unsloth/Qwen3.8-27B-GGUF|Qwen3.8-27B-UD-Q4_K_XL.gguf", manifest)
        self.assertIn(
            "unsloth/Qwen3.8-27B-GGUF|mmproj-F16.gguf|Qwen3.8-27B-mmproj-F16.gguf",
            manifest,
        )
        # The upstream external MTP draft must stay out of the download entries (comment-only mention is fine).
        self.assertNotIn("|MTP/", manifest)
        self.assertNotIn("unsloth/Qwen3.6-27B-MTP-GGUF|", manifest)
        self.assertNotIn("unsloth/Qwen3.6-27B-GGUF|", manifest)
        self.assertNotIn("deepreinforce-ai/", manifest)
        self.assertNotIn("LiquidAI/", manifest)
        self.assertNotIn("[local]", router_text)
        self.assertNotIn("[local-max]", router_text)
        self.assertIn("spec-type = draft-mtp", router_text)
        self.assertIn("temp = 0.6", router_text)
        self.assertIn("top-k = 20", router_text)
        self.assertIn("min-p = 0.00", router_text)
        self.assertNotIn("reasoning-preserve = true", router_text)
        self.assertNotIn("[qwen3.6-27b]", router_text)
        nemotron_block = router_text.split("[qwen3.5-9b]", 1)[0]
        self.assertIn("spec-type = draft-mtp", nemotron_block)
        self.assertIn("spec-draft-n-max = 2", nemotron_block)
        self.assertNotIn("reasoning = on", nemotron_block)
        self.assertIn("temp = 0.6", nemotron_block)
        self.assertIn("top-p = 0.95", nemotron_block)
        self.assertIn("min-p = 0.01", nemotron_block)
        qwen35_block = router_text.split("[qwen3.5-9b]", 1)[1].split("[qwen3.8-27b]", 1)[0]
        self.assertIn("reasoning = on", qwen35_block)
        self.assertNotIn("spec-type = draft-mtp", qwen35_block)
        self.assertIn("temp = 0.6", qwen35_block)
        self.assertIn("top-k = 20", qwen35_block)
        self.assertIn("min-p = 0.00", qwen35_block)
        # Hybrid thinking (on by default): [*] reasoning=auto stands, unsloth thinking-mode sampling.
        qwen38_block = router_text.split("[qwen3.8-27b]", 1)[1].split("[qwen3.8-27b-instruct]", 1)[0]
        self.assertNotIn("reasoning = on", qwen38_block)
        self.assertNotIn("reasoning = off", qwen38_block)
        self.assertNotIn("spec-type = draft-mtp", qwen38_block)
        self.assertNotIn("presence-penalty", qwen38_block)
        self.assertIn("Qwen3.8-27B-UD-Q4_K_XL.gguf", qwen38_block)
        self.assertIn("Qwen3.8-27B-mmproj-F16.gguf", qwen38_block)
        self.assertIn("temp = 1.0", qwen38_block)
        self.assertIn("top-p = 0.95", qwen38_block)
        self.assertIn("top-k = 20", qwen38_block)
        self.assertIn("min-p = 0.00", qwen38_block)
        qwen38_work_settings = effective_ini_settings(router_work, "qwen3.8-27b")
        qwen38_personal_settings = effective_ini_settings(router_personal, "qwen3.8-27b")
        self.assertEqual("131072", qwen38_work_settings.get("ctx-size"))
        self.assertEqual("131072", qwen38_work_settings.get("n-predict"))
        self.assertEqual("262144", qwen38_personal_settings.get("ctx-size"))
        self.assertEqual("262144", qwen38_personal_settings.get("n-predict"))
        # Instruct profile: same weights, thinking forced off, unsloth instruct-mode sampling.
        qwen38_instruct_block = router_text.split("[qwen3.8-27b-instruct]", 1)[1]
        self.assertIn("Qwen3.8-27B-UD-Q4_K_XL.gguf", qwen38_instruct_block)
        self.assertIn("reasoning = off", qwen38_instruct_block)
        self.assertIn("temp = 0.7", qwen38_instruct_block)
        self.assertIn("top-p = 0.80", qwen38_instruct_block)
        self.assertIn("top-k = 20", qwen38_instruct_block)
        self.assertIn("min-p = 0.00", qwen38_instruct_block)
        self.assertIn("presence-penalty = 1.5", qwen38_instruct_block)
        qwen38_instruct_work_settings = effective_ini_settings(router_work, "qwen3.8-27b-instruct")
        qwen38_instruct_personal_settings = effective_ini_settings(router_personal, "qwen3.8-27b-instruct")
        self.assertEqual("131072", qwen38_instruct_work_settings.get("ctx-size"))
        self.assertEqual("131072", qwen38_instruct_work_settings.get("n-predict"))
        self.assertEqual("262144", qwen38_instruct_personal_settings.get("ctx-size"))
        self.assertEqual("262144", qwen38_instruct_personal_settings.get("n-predict"))

        ini_ggufs = set(re.findall(r"/([^/\s]+\.gguf)$", router_text, flags=re.MULTILINE))
        manifest_files = {
            line.split("|")[-1].strip()
            for line in manifest.splitlines()
            if "|" in line and not line.lstrip().startswith("#")
        }
        self.assertTrue(
            ini_ggufs <= manifest_files, f"models.ini GGUFs missing from manifest: {ini_ggufs - manifest_files}"
        )

        spec = importlib.util.spec_from_file_location(
            "codex_llama_cpp_catalog",
            REPO / "home/exact_lib/exact_,codex/main.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        self.assertEqual(module.LOCAL_MODELS, expected)

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
        pi_recommended = mirror["harnesses"]["pi"]["recommended"]["models"]

        self.assertLess(
            set(cursor["recommended"]["models"]),
            set(cursor["curated"]["models"]),
        )
        self.assertGreater(
            set(gemini["available"]["models"]),
            set(gemini["curated"]["models"]),
        )
        self.assertNotIn("new-live", cursor["curated"]["models"])
        self.assertEqual(["openrouter/openai/gpt-5.5"], pi_recommended)

    def test_SHOULD_encode_unknown_and_error_without_empty_success(self):
        import model_mirrors

        mirror = model_mirrors.build_static_mirror(REPO)
        for harness in ("codex",):
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
        registry = REPO / "home/.chezmoidata/ai_models"
        pi_ids = {model["id"] for model in ai_models.load_pi_extra_models(registry)}
        openrouter_ids = {
            model["id"] for model in ai_models.load_provider_models(registry) if model["provider"] == "openrouter"
        }

        self.assertTrue(pi_ids)
        self.assertTrue(openrouter_ids)
        self.assertLessEqual(pi_ids, set(mirror["harnesses"]["pi"]["curated"]["models"]))
        self.assertLessEqual(openrouter_ids, set(mirror["providers"]["openrouter"]["curated"]["models"]))

    def test_SHOULD_keep_pi_review_policy_pins_in_pi_catalogs(self):
        import ai_models
        import model_mirrors

        registry = REPO / "home/.chezmoidata/ai_models"
        mirror = model_mirrors.build_static_mirror(REPO)
        pi_curated = set(mirror["harnesses"]["pi"]["curated"]["models"])
        openrouter_curated = set(mirror["providers"]["openrouter"]["curated"]["models"])

        def catalog_id(model: str) -> str:
            head, separator, suffix = model.rpartition(":")
            if separator and suffix in {"minimal", "none", "low", "medium", "high", "xhigh", "max"}:
                return head
            return model

        pins = [
            ai_models.resolve_review_agent_model(registry, "pi", "k-agent-reviewer")["model"],
            ai_models.resolve_review_agent_model(registry, "pi", "k-agent-adversarial-verifier")["model"],
        ]
        for row in ai_models.load_category_models(registry)["pi"].values():
            pins.append(row["model"])

        for model in {catalog_id(pin) for pin in pins}:
            with self.subTest(model=model):
                self.assertIn(model, pi_curated)
                if model.startswith("openrouter/"):
                    self.assertIn(model.removeprefix("openrouter/"), openrouter_curated)

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
            "known_but_unrouted": [{"id": "real-model", "provider": "llama-cpp"}],
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

        # Provenance names the split file that actually holds the section, not the registry dir.
        def registry(section: str) -> tuple[str, str]:
            owner = {
                "pi_extra_models": "harness-catalogs.yaml",
                "copilot_models": "harness-catalogs.yaml",
                "agent_bindings": "tiering.yaml",
                "agent_categories": "tiering.yaml",
                "category_models": "tiering.yaml",
                "review_model_overrides": "tiering.yaml",
            }[section]
            return (f"home/.chezmoidata/ai_models/{owner}", section)

        copilot_policy_sources = {
            registry("agent_bindings"),
            registry("agent_categories"),
            registry("category_models"),
            registry("review_model_overrides"),
        }
        self.assertEqual(sources("copilot", "curated"), copilot_policy_sources)
        self.assertEqual(sources("copilot", "recommended"), copilot_policy_sources)
        self.assertEqual(
            sources("copilot", "available"),
            {registry("copilot_models")},
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
            },
            "pi": {registry("pi_extra_models")},
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
        for provider in ("openrouter",):
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
            "provider:llama-cpp": lambda value: {"data": [{"id": "valid-model"}, {"id": value}]},
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
            mirror["providers"]["openrouter"]["live_probe"]["max_response_bytes"],
            model_mirrors.MAX_HTTP_RESPONSE_BYTES,
        )
        fetch = mock.Mock(side_effect=RuntimeError("transport leaked SENSITIVE-FIXTURE-TEXT"))
        with mock.patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "SENSITIVE-FIXTURE-TEXT",
            },
            clear=False,
        ):
            result = model_mirrors.probe_target(
                mirror,
                "provider:openrouter",
                fetch_json=fetch,
            )

        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("SENSITIVE-FIXTURE-TEXT", json.dumps(result))
        args, _kwargs = fetch.call_args
        self.assertEqual(args[0], "https://openrouter.ai/api/v1/models")
        self.assertLessEqual(args[2], 10)

        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"x" * (model_mirrors.MAX_HTTP_RESPONSE_BYTES + 1)
        with mock.patch("urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "byte limit"):
                model_mirrors._fetch_json("https://catalog.invalid/models", {}, 1)
        response.__enter__.return_value.read.assert_called_once_with(model_mirrors.MAX_HTTP_RESPONSE_BYTES + 1)


if __name__ == "__main__":
    unittest.main()
