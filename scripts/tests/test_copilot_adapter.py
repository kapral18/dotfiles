#!/usr/bin/env python3
"""Behavioral tests for the GitHub Copilot subscription adapter."""

from __future__ import annotations

import contextlib
import io
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from unittest import mock

import _test_support  # noqa: F401
from _test_support import REPO

ADAPTER = REPO / "home/exact_lib/exact_,copilot-adapter"
sys.path.insert(0, str(ADAPTER))

import copilot_auth
import copilot_server
import copilot_wire
import main
from codex_lanes import leaf_profile


def model(
    model_id: str,
    endpoints: tuple[str, ...],
    efforts: tuple[str, ...] = ("low", "medium", "high"),
    context_windows: dict[str, int] | None = None,
    prompt_limits: dict[str, int] | None = None,
) -> copilot_auth.ModelSpec:
    context_windows = context_windows or {"default": 264_000}
    prompt_limits = prompt_limits or {tier: window - 64_000 for tier, window in context_windows.items()}
    return copilot_auth.ModelSpec(
        model_id=model_id,
        endpoints=frozenset(endpoints),
        efforts=frozenset(efforts),
        context_window=context_windows["default"],
        max_output_tokens=64_000,
        context_windows=context_windows,
        prompt_limit=prompt_limits["default"],
        prompt_limits=prompt_limits,
    )


class TestArgumentsAndModels(unittest.TestCase):
    """WHEN resolving wrapper controls against the live model catalog."""

    def test_SHOULD_consume_adapter_flags_and_preserve_harness_arguments(self) -> None:
        options = main.parse_args(
            [
                "--model",
                "claude-sonnet-5",
                "--reasoning-effort=high",
                "--thinking",
                "off",
                "--context",
                "long_context",
                "-p",
                "hello",
                "--",
                "--model",
                "underlying",
            ]
        )

        self.assertEqual(options.model_id, "claude-sonnet-5")
        self.assertEqual(options.effort, "high")
        self.assertEqual(options.thinking, "off")
        self.assertEqual(options.context_tier, "long_context")
        self.assertEqual(options.forwarded, ["-p", "hello", "--model", "underlying"])
        self.assertEqual(main.parse_args(["--no-thinking"]).thinking, "off")
        with self.assertRaisesRegex(ValueError, "choose: auto, on, off"):
            main.parse_args(["--thinking", "maybe"])

    def test_SHOULD_accept_every_completion_capable_model_in_both_harnesses(self) -> None:
        models = {
            "claude-sonnet-5": model("claude-sonnet-5", ("/v1/messages",), ("low", "high")),
            "gpt-5.3-codex": model("gpt-5.3-codex", ("/responses",), ("low", "high")),
            "gemini-3.5-flash": model("gemini-3.5-flash", ("/chat/completions",), ("low", "high")),
        }

        cases = (
            ("claude", "claude-sonnet-5"),
            ("claude", "gpt-5.3-codex"),
            ("claude", "gemini-3.5-flash"),
            ("codex", "claude-sonnet-5"),
            ("codex", "gpt-5.3-codex"),
            ("codex", "gemini-3.5-flash"),
        )
        for harness, model_id in cases:
            with self.subTest(harness=harness, model=model_id):
                resolved = main.resolve_model(
                    harness,
                    main.parse_args(["--model", model_id, "--effort", "high"]),
                    models,
                )
                self.assertEqual(resolved.model_id, model_id)

        with self.assertRaisesRegex(ValueError, "does not expose a supported completion endpoint"):
            main.resolve_model(
                "codex",
                main.parse_args(["--model", "embedding-only"]),
                {**models, "embedding-only": model("embedding-only", ("/embeddings",))},
            )
        with self.assertRaisesRegex(ValueError, "does not support effort"):
            main.resolve_model(
                "codex",
                main.parse_args(["--effort", "medium"]),
                models,
            )

    def test_SHOULD_render_only_live_completion_capabilities(self) -> None:
        models = {
            "gpt-5.3-codex": model(
                "gpt-5.3-codex",
                ("/responses",),
                ("low", "high"),
                {"default": 264_000, "long_context": 1_000_000},
            ),
            "embedding-only": model("embedding-only", ("/embeddings",)),
        }

        self.assertEqual(main.completion_rows(models), ["gpt-5.3-codex\thigh,low\tdefault,long_context"])

    def test_SHOULD_select_only_context_tiers_advertised_for_the_model(self) -> None:
        models = {
            "claude-sonnet-5": model(
                "claude-sonnet-5",
                ("/v1/messages",),
                context_windows={"default": 264_000, "long_context": 1_000_000},
            ),
            "gpt-5.3-codex": model("gpt-5.3-codex", ("/responses",)),
        }

        selected = main.resolve_model(
            "claude",
            main.parse_args(["--context", "long_context"]),
            models,
        )
        self.assertEqual(selected.context_window, 1_000_000)
        self.assertEqual(selected.prompt_limit, 936_000)

        with self.assertRaisesRegex(ValueError, "does not support context tier"):
            main.resolve_model(
                "codex",
                main.parse_args(["--context", "long_context"]),
                models,
            )
        with self.assertRaisesRegex(ValueError, "choose: default, long_context"):
            main.parse_args(["--context", "oversized"])

    def test_SHOULD_keep_claude_compaction_inside_the_billed_prompt_limit(self) -> None:
        # Copilot bills long context by prompt size; Claude compacts on the previous response, so one turn of
        # headroom stays below the tier limit and the [1m] marker only lifts Claude's 200k cap when needed.
        astra = model(
            "gpt-6-astra",
            ("/responses",),
            context_windows={"default": 400_000, "long_context": 1_000_000},
            prompt_limits={"default": 272_000, "long_context": 872_000},
        )
        sonnet = model(
            "claude-sonnet-5",
            ("/v1/messages",),
            context_windows={"default": 264_000, "long_context": 1_000_000},
            prompt_limits={"default": 200_000, "long_context": 936_000},
        )
        small = model(
            "gpt-5-mini", ("/responses",), context_windows={"default": 192_000}, prompt_limits={"default": 128_000}
        )
        models = {"gpt-6-astra": astra, "claude-sonnet-5": sonnet, "gpt-5-mini": small}

        selected = main.resolve_model("claude", main.parse_args(["--model", "gpt-6-astra"]), models)
        self.assertEqual(main.claude_compact_window(selected), 240_000)
        self.assertEqual(main.claude_frontend_model(selected), "gpt-6-astra[1m]")

        selected = main.resolve_model(
            "claude", main.parse_args(["--model", "gpt-6-astra", "--context", "long_context"]), models
        )
        self.assertEqual(main.claude_compact_window(selected), 840_000)
        self.assertEqual(main.claude_frontend_model(selected), "gpt-6-astra[1m]")

        selected = main.resolve_model("claude", main.parse_args([]), models)
        self.assertEqual(main.claude_compact_window(selected), 168_000)
        self.assertEqual(main.claude_frontend_model(selected), "claude-sonnet-5")

        selected = main.resolve_model("claude", main.parse_args(["--model", "gpt-5-mini"]), models)
        self.assertEqual(main.claude_compact_window(selected), 100_000)
        self.assertEqual(main.claude_frontend_model(selected), "gpt-5-mini")

    def test_SHOULD_cap_claude_global_compaction_and_context_for_reachable_small_lanes(self) -> None:
        root = model(
            "gpt-6-astra",
            ("/responses",),
            context_windows={"default": 400_000},
            prompt_limits={"default": 272_000},
        )
        small = model(
            "gpt-5-mini",
            ("/responses",),
            context_windows={"default": 192_000},
            prompt_limits={"default": 128_000},
        )

        self.assertEqual(main.claude_global_limits(root, [small]), (100_000, 128_000))
        self.assertEqual(main.claude_global_limits(root, [root]), (240_000, None))

    def test_SHOULD_project_selected_prompt_budgets_to_codex_context_metadata(self) -> None:
        # Context capacity includes output tokens. Codex's display and auto-compaction need the selected prompt
        # budget, so its limits remain below the provider's billed prompt ceiling.
        astra = replace(
            model(
                "gpt-6-astra",
                ("/responses",),
                context_windows={"default": 400_000, "long_context": 1_000_000},
                prompt_limits={"default": 272_000, "long_context": 872_000},
            ),
            max_output_tokens=128_000,
        )
        small = model(
            "gpt-5-mini", ("/responses",), context_windows={"default": 192_000}, prompt_limits={"default": 128_000}
        )
        models = {astra.model_id: astra, small.model_id: small}
        cases = (
            ("default Astra", ["--model", "gpt-6-astra"], 272_000, 244_800),
            ("explicit default", ["--model", "gpt-6-astra", "--context", "default"], 272_000, 244_800),
            ("long context", ["--model", "gpt-6-astra", "--context", "long_context"], 872_000, 784_800),
            ("short model", ["--model", "gpt-5-mini"], 128_000, 115_200),
        )

        for name, argv, expected_prompt_budget, expected_usable_budget in cases:
            with self.subTest(name=name):
                selected = main.resolve_model("codex", main.parse_args(argv), models)
                info = copilot_auth.codex_model_info(selected)

                self.assertEqual(info["context_window"], expected_prompt_budget)
                self.assertEqual(info["max_context_window"], expected_prompt_budget)
                self.assertEqual(info["effective_context_window_percent"], 90)
                self.assertEqual(info["auto_compact_token_limit"], expected_usable_budget)
                self.assertLess(info["auto_compact_token_limit"], selected.prompt_limit)

    def test_SHOULD_project_selected_default_long_and_small_tiers_to_cursor_metadata(self) -> None:
        long = replace(
            model(
                "gpt-6-astra",
                ("/responses",),
                context_windows={"default": 400_000, "long_context": 1_000_000},
                prompt_limits={"default": 272_000, "long_context": 872_000},
            ),
            max_output_tokens=128_000,
        )
        small = model(
            "gpt-5-mini",
            ("/responses",),
            context_windows={"default": 192_000},
            prompt_limits={"default": 128_000},
        )
        models = {long.model_id: long, small.model_id: small}
        cases = (
            (["--model", long.model_id], 272_000, 128_000),
            (["--model", long.model_id, "--context", "long_context"], 872_000, 128_000),
            (["--model", small.model_id], 128_000, 64_000),
        )
        for argv, expected_context, expected_output in cases:
            with self.subTest(argv=argv):
                selected = main.resolve_model("cursor", main.parse_args(argv), models)
                row = copilot_server.cursor_model_info(selected)
                self.assertEqual(row["api_types"], ["openai_chat"])
                self.assertEqual(
                    row["capabilities"],
                    {
                        "context_length": expected_context,
                        "max_output_tokens": expected_output,
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                        "supports_tool_use": True,
                        "supports_streaming": True,
                        "supports_reasoning": True,
                        "supports_vision": False,
                    },
                )

    def test_SHOULD_parse_the_copilot_model_contract(self) -> None:
        parsed = copilot_auth.parse_models(
            {
                "data": [
                    {
                        "id": "gpt-test",
                        "supported_endpoints": ["/responses"],
                        "capabilities": {
                            "type": "chat",
                            "limits": {
                                "max_context_window_tokens": 1_000_000,
                                "max_prompt_tokens": 872_000,
                                "max_output_tokens": 128_000,
                            },
                            "supports": {"reasoning_effort": ["low", "high"]},
                        },
                        "billing": {
                            "token_prices": {
                                "default": {"max_prompt_tokens": 272_000},
                                "long_context": {"max_prompt_tokens": 872_000},
                            }
                        },
                    },
                    {
                        "id": "untiered",
                        "supported_endpoints": ["/v1/messages"],
                        "capabilities": {
                            "type": "chat",
                            "limits": {
                                "max_context_window_tokens": 200_000,
                                "max_prompt_tokens": 136_000,
                                "max_output_tokens": 64_000,
                            },
                            "supports": {},
                        },
                    },
                ]
            }
        )

        self.assertEqual(parsed["untiered"].context_windows, {"default": 200_000})
        self.assertEqual(parsed["untiered"].prompt_limits, {"default": 136_000})

        self.assertEqual(parsed["gpt-test"].context_window, 400_000)
        self.assertEqual(
            parsed["gpt-test"].context_windows,
            {"default": 400_000, "long_context": 1_000_000},
        )
        self.assertEqual(parsed["gpt-test"].prompt_limit, 272_000)
        self.assertEqual(
            parsed["gpt-test"].prompt_limits,
            {"default": 272_000, "long_context": 872_000},
        )
        self.assertEqual(parsed["gpt-test"].endpoints, {"/responses"})
        self.assertEqual(parsed["gpt-test"].efforts, {"low", "high"})

    def test_SHOULD_cap_billing_tiers_at_the_model_prompt_capacity(self) -> None:
        # Live Grok catalog: long-context pricing extends to 500K, but input capacity is 372K.
        for explicit_prompt_limit in (True, False):
            with self.subTest(explicit_prompt_limit=explicit_prompt_limit):
                limits = {"max_context_window_tokens": 500_000, "max_output_tokens": 128_000}
                if explicit_prompt_limit:
                    limits["max_prompt_tokens"] = 372_000
                parsed = copilot_auth.parse_models(
                    {
                        "data": [
                            {
                                "id": "grok-test",
                                "supported_endpoints": ["/chat/completions"],
                                "capabilities": {"type": "chat", "limits": limits},
                                "billing": {
                                    "token_prices": {
                                        "default": {"max_prompt_tokens": 200_000},
                                        "long_context": {"max_prompt_tokens": 500_000},
                                    }
                                },
                            }
                        ]
                    }
                )["grok-test"]
                self.assertEqual(parsed.prompt_limits, {"default": 200_000, "long_context": 372_000})
                self.assertEqual(parsed.context_windows, {"default": 328_000, "long_context": 500_000})
                self.assertEqual(parsed.max_output_tokens, 128_000)

    def test_SHOULD_project_models_without_reasoning_effort_for_codex(self) -> None:
        info = copilot_auth.codex_model_info(model("claude-haiku-4.5", ("/v1/messages",), ()))

        self.assertEqual(info["default_reasoning_level"], "none")
        self.assertEqual(info["supported_reasoning_levels"], [])

    def test_SHOULD_not_allow_the_environment_to_redirect_github_credentials(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"COPILOT_SUBSCRIPTION_BASE_URL": "https://credential-capture.invalid"},
        ):
            self.assertEqual(copilot_auth.api_url(), copilot_auth.DEFAULT_API_URL)


class TestChildIsolation(unittest.TestCase):
    """WHEN launching native harnesses through the owner-authenticated loopback."""

    def test_SHOULD_keep_github_credentials_out_of_both_children(self) -> None:
        inherited = {
            "PATH": "/usr/bin",
            "GH_TOKEN": "real-github-token",
            "GITHUB_TOKEN": "other-token",
            "ANTHROPIC_API_KEY": "real-anthropic-key",
            "ANTHROPIC_BASE_URL": "https://outside.example",
            "ANTHROPIC_AUTH_TOKEN": "outside-token",
            "OPENAI_API_KEY": "real-openai-key",
            "CURSOR_LOCAL_AGENT_BASE_URL": "https://outside.example",
            "CURSOR_LOCAL_AGENT_API_KEY": "outside-key",
            "CURSOR_API_ENDPOINT": "https://outside.example",
            "CURSOR_API_KEY": "outside-key",
        }
        claude_model = model(
            "claude-sonnet-5",
            ("/v1/messages",),
            context_windows={"default": 336_000},
            prompt_limits={"default": 272_000},
        )
        codex_model = model("gpt-5.3-codex", ("/responses",), ("low", "high"))
        with mock.patch.dict(os.environ, inherited, clear=True):
            claude_command, claude_env = main.child_command(
                "claude",
                "/usr/bin/claude",
                "http://127.0.0.1:3210",
                "local-token",
                claude_model,
                "high",
                "off",
                ["-p", "hello"],
            )
            codex_command, codex_env = main.child_command(
                "codex",
                "/usr/bin/codex",
                "http://127.0.0.1:3210",
                "local-token",
                codex_model,
                "high",
                None,
                ["exec", "hello"],
            )
            cursor_command, cursor_env = main.child_command(
                "cursor",
                "/usr/bin/cursor-agent-local",
                "http://127.0.0.1:3210",
                "local-token",
                codex_model,
                "high",
                None,
                ["-p", "hello"],
            )

        self.assertEqual(
            claude_command,
            ["/usr/bin/claude", "--model", "claude-sonnet-5[1m]", "--effort", "high", "-p", "hello"],
        )
        self.assertEqual(claude_env["ANTHROPIC_AUTH_TOKEN"], "local-token")
        self.assertEqual(claude_env["ANTHROPIC_MODEL"], "claude-sonnet-5[1m]")
        self.assertEqual(claude_env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], "240000")
        self.assertEqual(claude_env["CLAUDE_CODE_DISABLE_THINKING"], "1")
        self.assertNotIn("GH_TOKEN", claude_env)
        self.assertNotIn("GITHUB_TOKEN", claude_env)
        self.assertNotIn("ANTHROPIC_API_KEY", claude_env)

        self.assertIn('model_provider="copilot_subscription"', codex_command)
        self.assertIn('model_reasoning_effort="high"', codex_command)
        self.assertEqual(codex_env["COPILOT_ADAPTER_TOKEN"], "local-token")
        self.assertNotIn("GH_TOKEN", codex_env)
        self.assertNotIn("GITHUB_TOKEN", codex_env)
        self.assertNotIn("OPENAI_API_KEY", codex_env)

        self.assertEqual(cursor_command, ["/usr/bin/cursor-agent-local", "--model", "gpt-5.3-codex", "-p", "hello"])
        self.assertEqual(cursor_env["CURSOR_LOCAL_AGENT_BASE_URL"], "http://127.0.0.1:3210/v1")
        self.assertEqual(cursor_env["CURSOR_LOCAL_AGENT_API_KEY"], "local-token")
        self.assertNotIn("ANTHROPIC_BASE_URL", cursor_env)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", cursor_env)
        self.assertNotIn("CURSOR_API_ENDPOINT", cursor_env)
        self.assertNotIn("CURSOR_API_KEY", cursor_env)

    def test_SHOULD_apply_global_claude_lane_limits_without_changing_root_only_launches(self) -> None:
        root = model(
            "gpt-6-astra",
            ("/responses",),
            context_windows={"default": 400_000},
            prompt_limits={"default": 272_000},
        )
        compact, max_context = main.claude_global_limits(
            root,
            [
                model(
                    "gpt-5-mini",
                    ("/responses",),
                    context_windows={"default": 192_000},
                    prompt_limits={"default": 64_000},
                )
            ],
        )
        _, env = main.child_command(
            "claude",
            "/usr/bin/claude",
            "http://127.0.0.1:3210",
            "local-token",
            root,
            None,
            None,
            [],
            compact,
            max_context,
        )

        self.assertEqual(env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], "64000")
        self.assertEqual(env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"], "64000")
        self.assertEqual(env["ANTHROPIC_MODEL"], "gpt-6-astra")

    def test_SHOULD_reject_cursor_flags_that_can_bypass_loopback(self) -> None:
        for option in ("--base-url", "--base-url=https://outside.example", "--model", "-m"):
            with self.subTest(option=option):
                with self.assertRaises(ValueError):
                    main.validate_cursor_forwarded([option])

    def test_SHOULD_suppress_tracebacks_when_clients_reset_before_request_line(self) -> None:
        server = copilot_server.AdapterServer(
            ("127.0.0.1", 0),
            copilot_server.AdapterContext("local-token", copilot_auth.TokenProvider(), {}),
        )
        stderr = io.StringIO()
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)

        try:
            with contextlib.redirect_stderr(stderr):
                thread.start()
                for _ in range(5):
                    client = socket.create_connection(("127.0.0.1", server.server_port))
                    client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                    client.close()
                time.sleep(0.2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

        self.assertNotIn("Exception occurred during processing of request", stderr.getvalue())
        self.assertNotIn("ConnectionResetError", stderr.getvalue())


class TestCodexLaneConfiguration(unittest.TestCase):
    """WHEN a Codex frontend consumes Copilot lane metadata and managed leaf profiles."""

    def test_SHOULD_remove_native_model_overrides_without_losing_leaf_instructions(self) -> None:
        source = '''name = "worker"
description = "Settled implementation"
model = "native-wrong-provider"
model_reasoning_effort = "low"
service_tier = "default"
features = { multi_agent = true }
developer_instructions = """
Keep these exact instructions.
model = "this is prompt text, not TOML"
"""
'''
        result = leaf_profile(source)
        header, body = result.split('developer_instructions = """', 1)
        self.assertNotIn("model =", header)
        self.assertNotIn("model_reasoning_effort", header)
        self.assertIn("features = { multi_agent = false }", header)
        self.assertIn('service_tier = "default"', header)
        self.assertEqual(body, source.split('developer_instructions = """', 1)[1])
        with self.assertRaisesRegex(ValueError, "unsupported"):
            leaf_profile(source.replace('service_tier = "default"', 'model_provider = "outside"'))

    def test_SHOULD_freeze_only_available_lanes_and_preserve_root_metadata(self) -> None:
        raw = model("shared-model", ("/responses",), ("low", "high", "xhigh"))
        routes = {
            "shared-model@lane-xhigh": {"model": "shared-model", "effort": "xhigh"},
            "shared-model@lane-low": {"model": "shared-model", "effort": "low"},
            "missing@lane-high": {"model": "missing", "effort": "high"},
            "shared-model@lane-max": {"model": "shared-model", "effort": "max"},
        }
        lanes = main.codex_lane_models({raw.model_id: raw}, routes)
        self.assertEqual(set(lanes), {"shared-model@lane-xhigh", "shared-model@lane-low"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "agents").mkdir()
            original = '''name = "explorer"
model = "old-native-model"
model_reasoning_effort = "high"
developer_instructions = """
Only research the packet. Never delegate.
"""
'''
            (root / "agents/explorer.toml").write_text(original)
            projection = root / "bands.json"
            projection.write_text(
                json.dumps(
                    {
                        "harnesses": {
                            "copilot": {
                                "agents": {
                                    "explorer": {"model": raw.model_id, "effort": "xhigh"},
                                    "worker": {"model": raw.model_id, "effort": "low"},
                                    "unavailable": {"model": "missing", "effort": "high"},
                                }
                            }
                        }
                    }
                )
            )
            output = root / "output"
            output.mkdir()
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(root), "AGENT_BANDS_FILE": str(projection)}):
                args, env = main.codex_lane_configuration(output, {raw.model_id: raw}, lanes)
            self.assertEqual(json.loads(env["AGENT_BAND_CODEX_ROUTES"]), {"explorer": "shared-model@lane-xhigh"})
            self.assertIn(f"agents.explorer.config_file={json.dumps(str(output / 'explorer.toml'))}", args)
            self.assertEqual((root / "agents/explorer.toml").read_text(), original)
            self.assertNotIn("old-native-model", (output / "explorer.toml").read_text())
            catalog = json.loads((output / "models.json").read_text())["models"]
            self.assertEqual({item["slug"] for item in catalog}, {raw.model_id, *lanes})
            self.assertTrue(all(item["context_window"] == raw.prompt_limit for item in catalog))


class TestLifecycle(unittest.TestCase):
    """WHEN the child exits after an interactive interrupt."""

    def setUp(self) -> None:
        patcher = mock.patch("main.load_lane_routes", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch("main.codex_lane_configuration", return_value=([], {"AGENT_BAND_CODEX_ROUTES": "{}"}))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_SHOULD_ignore_unreachable_claude_lanes_when_resolving_context(self) -> None:
        selected = model("claude-sonnet-5", ("/v1/messages",))
        routes = {
            "claude-sonnet-5@lane-high": {"model": "claude-sonnet-5", "effort": "high"},
            "unavailable@lane-high": {"model": "unavailable", "effort": "high"},
        }
        with (
            mock.patch("main.fetch_models", return_value={selected.model_id: selected}),
            mock.patch("main.load_lane_routes", return_value=routes),
            mock.patch(
                "main.claude_profiles",
                return_value=(
                    [],
                    {
                        "AGENT_BAND_CLAUDE_ROUTES": json.dumps({"k-agent-smol": "claude-sonnet-5@lane-high"}),
                    },
                ),
            ),
            mock.patch("main.harness_binary", return_value="/usr/bin/claude"),
            mock.patch("main.start_server", return_value=(mock.Mock(server_port=3210), mock.Mock())),
            mock.patch("main.run_child", return_value=0) as child,
        ):
            self.assertEqual(main.launch("claude", []), 0)
        self.assertEqual(child.call_args.args[1]["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], "168000")

    def test_SHOULD_default_codex_effort_to_medium_when_unspecified(self) -> None:
        selected = model("gpt-5.3-codex", ("/responses",), ("low", "medium", "high"))
        adapter = mock.Mock(server_port=3210)
        thread = mock.Mock()
        captured: dict[str, list[str]] = {}

        def fake_run_child(command: list[str], _env: dict[str, str]) -> int:
            self.assertEqual(_env["AGENT_BAND_SUBSCRIPTION"], "copilot")
            self.assertEqual(_env["AGENT_BAND_SCHEMA_HARNESS"], "copilot")
            self.assertNotIn("AGENT_BAND_MODEL_OVERRIDE", _env)
            self.assertNotIn("AGENT_BAND_MODEL_FORMAT", _env)
            captured["command"] = command
            return 0

        with (
            mock.patch("main.fetch_models", return_value={selected.model_id: selected}),
            mock.patch("main.harness_binary", return_value="/usr/bin/codex"),
            mock.patch("main.start_server", return_value=(adapter, thread)),
            mock.patch("main.run_child", side_effect=fake_run_child),
        ):
            result = main.launch("codex", [])

        self.assertEqual(result, 0)
        self.assertIn('model_reasoning_effort="medium"', captured["command"])

    def test_SHOULD_not_force_default_effort_for_models_that_do_not_support_it(self) -> None:
        selected = model("claude-haiku-4.5", ("/v1/messages",), ())
        adapter = mock.Mock(server_port=3210)
        thread = mock.Mock()
        captured: dict[str, list[str]] = {}

        def fake_run_child(command: list[str], _env: dict[str, str]) -> int:
            captured["command"] = command
            return 0

        with (
            mock.patch("main.fetch_models", return_value={selected.model_id: selected}),
            mock.patch("main.harness_binary", return_value="/usr/bin/codex"),
            mock.patch("main.start_server", return_value=(adapter, thread)),
            mock.patch("main.run_child", side_effect=fake_run_child),
        ):
            result = main.launch("codex", ["--model", "claude-haiku-4.5"])

        self.assertEqual(result, 0)
        self.assertFalse(any("model_reasoning_effort" in item for item in captured["command"]))

    def test_SHOULD_not_raise_when_sigint_arrives_during_loopback_shutdown(self) -> None:
        selected = model("gpt-5.3-codex", ("/responses",))
        for child_status in (0, 130):
            with self.subTest(child_status=child_status):
                adapter = mock.Mock(server_port=3210)
                adapter.shutdown.side_effect = lambda: os.kill(os.getpid(), signal.SIGINT)
                thread = mock.Mock()
                previous = signal.signal(signal.SIGINT, signal.default_int_handler)
                try:
                    with (
                        mock.patch("main.fetch_models", return_value={selected.model_id: selected}),
                        mock.patch("main.harness_binary", return_value="/usr/bin/codex"),
                        mock.patch("main.start_server", return_value=(adapter, thread)),
                        mock.patch("main.run_child", return_value=child_status),
                    ):
                        try:
                            result = main.launch("codex", [])
                        except KeyboardInterrupt:
                            self.fail("SIGINT during loopback shutdown escaped as KeyboardInterrupt")
                finally:
                    signal.signal(signal.SIGINT, previous)

                self.assertEqual(result, child_status)
                adapter.server_close.assert_called_once_with()
                thread.join.assert_called_once_with(timeout=5)


class TestWireTranslator(unittest.TestCase):
    """WHEN retaining provider-owned context for a translated tool loop."""

    def test_SHOULD_keep_opaque_tool_context_in_process_memory_only(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch("copilot_wire.Path.home", return_value=Path(directory)),
            mock.patch.dict(
                os.environ,
                {
                    "XDG_STATE_HOME": directory,
                },
            ),
        ):
            translator = copilot_wire.WireTranslator()
            rendered = translator.render(
                copilot_wire.ANTHROPIC,
                copilot_wire.CHAT,
                io.BytesIO(
                    b'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,'
                    b'"id":"call_1","function":{"name":"Bash","arguments":"{}"},'
                    b'"extra_content":{"thought_signature":"opaque"}}]},"finish_reason":"tool_calls"}]}\n\n'
                    b"data: [DONE]\n\n"
                ),
                model("gemini-3.5-flash", ("/chat/completions",)),
                copilot_wire.PreparedRequest(b"{}", True, {"Bash": "function"}),
            )
            b"".join(rendered)

            persisted = [path for path in Path(directory).rglob("*") if path.is_file()]
            self.assertEqual(persisted, [])


class TestTranslatedCacheRequests(unittest.TestCase):
    """WHEN protocols differ, only representable caller controls cross the wire."""

    def setUp(self) -> None:
        self.translator = copilot_wire.WireTranslator()
        self.marker = {"prompt_cache_breakpoint": {"mode": "explicit"}}
        self.controls = {
            "prompt_cache_key": "fixture-session",
            "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
            "prompt_cache_retention": "in_memory",
        }

    def prepare(self, frontend, backend, body):
        return json.loads(
            self.translator.prepare(
                frontend,
                backend,
                json.dumps(body).encode(),
                model("fixture", (backend,)),
            ).body
        )

    def messages(self):
        return [
            {"role": "system", "content": [{"type": "text", "text": "system", **self.marker}]},
            {"role": "developer", "content": [{"type": "text", "text": "developer", **self.marker}]},
            {"role": "user", "content": [{"type": "text", "text": "question", **self.marker}]},
            {
                "role": "assistant",
                "content": "working",
                "tool_calls": [
                    {"id": "call_old", "type": "function", "function": {"name": "lookup", "arguments": "{}"}},
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_old",
                "content": [
                    {"type": "text", "text": "result", **self.marker},
                    {"type": "text", "text": "tail"},
                ],
            },
        ]

    def test_SHOULD_preserve_openai_controls_and_exact_text_boundaries_in_both_directions(self):
        body = {"messages": self.messages(), "stream": True, **self.controls}
        response = self.prepare(copilot_wire.CHAT, copilot_wire.RESPONSES, body)
        self.assertNotIn("instructions", response)
        self.assertNotIn("stream_options", response)
        self.assertEqual(
            [item.get("role") for item in response["input"][:4]], ["system", "developer", "user", "assistant"]
        )
        self.assertEqual(response["input"][0]["content"], [{"type": "input_text", "text": "system", **self.marker}])
        self.assertEqual(
            response["input"][-1]["output"],
            [
                {"type": "input_text", "text": "result", **self.marker},
                {"type": "input_text", "text": "tail"},
            ],
        )
        chat = self.prepare(copilot_wire.RESPONSES, copilot_wire.CHAT, response)
        for key, value in self.controls.items():
            self.assertEqual(response[key], value)
            self.assertEqual(chat[key], value)
        self.assertEqual(chat["stream_options"], {"include_usage": True})
        self.assertEqual(chat["messages"], self.messages())

    def test_SHOULD_keep_unmarked_chat_instructions_and_opaque_reasoning(self):
        unmarked = self.prepare(
            copilot_wire.CHAT,
            copilot_wire.RESPONSES,
            {
                "messages": [{"role": "system", "content": "system"}, {"role": "user", "content": "hi"}],
            },
        )
        self.assertEqual(unmarked["instructions"], "system")
        self.assertNotIn("prompt_cache_options", unmarked)
        reasoning = {"type": "reasoning", "id": "rs", "encrypted_content": "opaque"}
        self.translator._reasoning.put("call_old", reasoning)
        marked = self.prepare(copilot_wire.CHAT, copilot_wire.RESPONSES, {"messages": self.messages()})
        call = next(i for i, item in enumerate(marked["input"]) if item["type"] == "function_call")
        self.assertEqual(marked["input"][call - 1], reasoning)

    def test_SHOULD_map_openai_text_markers_but_not_keys_or_lifetimes_to_anthropic(self):
        body = {"messages": self.messages(), "stream": False, **self.controls}
        for frontend in (copilot_wire.CHAT, copilot_wire.RESPONSES):
            with self.subTest(frontend=frontend):
                source = body if frontend == copilot_wire.CHAT else self.prepare(copilot_wire.CHAT, frontend, body)
                translated = self.prepare(frontend, copilot_wire.ANTHROPIC, source)
                self.assertNotIn("cache_control", translated)
                for key in self.controls:
                    self.assertNotIn(key, translated)
                self.assertEqual(
                    translated["system"],
                    [
                        {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}
                        for text in ("system", "developer")
                    ],
                )
                result = translated["messages"][-1]["content"][0]
                self.assertEqual(result["type"], "tool_result")
                self.assertEqual(
                    result["content"],
                    [
                        {"type": "text", "text": "result", "cache_control": {"type": "ephemeral"}},
                        {"type": "text", "text": "tail"},
                    ],
                )

    def test_SHOULD_preserve_explicit_no_cache_and_bound_automatic_marker_placement(self):
        for frontend in (copilot_wire.CHAT, copilot_wire.RESPONSES):
            for mode in ("explicit", "implicit", None):
                for marked in (False, True):
                    with self.subTest(frontend=frontend, mode=mode, marked=marked):
                        blocks = [{"type": "text", "text": str(i), **(self.marker if marked else {})} for i in range(6)]
                        source = {"stream": True, "messages": [{"role": "user", "content": blocks}]}
                        if mode:
                            source["prompt_cache_options"] = {"mode": mode}
                        if frontend == copilot_wire.RESPONSES:
                            source = self.prepare(copilot_wire.CHAT, frontend, source)
                        translated = self.prepare(frontend, copilot_wire.ANTHROPIC, source)
                        self.assertEqual("cache_control" in translated, mode != "explicit")
                        marked_text = [b["text"] for b in translated["messages"][0]["content"] if "cache_control" in b]
                        self.assertEqual(
                            marked_text,
                            (["2", "3", "4", "5"] if mode == "explicit" else ["3", "4", "5"]) if marked else [],
                        )

    def test_SHOULD_omit_unsupported_anthropic_cache_synthesis_without_target_capability(self):
        body = {
            "model": "fixture",
            "stream": True,
            "system": [{"type": "text", "text": "system", "cache_control": {"type": "ephemeral"}}],
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
            "tools": [{"name": "lookup", "input_schema": {"type": "object"}, "cache_control": {"type": "ephemeral"}}],
            "messages": [
                {"role": "user", "content": "question"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "old",
                            "name": "lookup",
                            "input": {},
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "old",
                            "content": "answer",
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                },
            ],
        }
        for backend in (copilot_wire.CHAT, copilot_wire.RESPONSES):
            translated = self.prepare(copilot_wire.ANTHROPIC, backend, body)
            for key in ("prompt_cache_options", "prompt_cache_breakpoint", "cache_control"):
                self.assertNotIn(key, json.dumps(translated))
            self.assertEqual(
                translated.get("stream_options"), {"include_usage": True} if backend == copilot_wire.CHAT else None
            )

    def test_SHOULD_reject_malformed_cache_intent_before_synthesizing_controls(self):
        for options in ("explicit", {"mode": "disabled"}, {"mode": 1}):
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, "prompt_cache_options"):
                self.prepare(
                    copilot_wire.CHAT,
                    copilot_wire.ANTHROPIC,
                    {
                        "messages": [{"role": "user", "content": "question"}],
                        "prompt_cache_options": options,
                    },
                )
        for marker in ("explicit", {}, {"mode": "implicit"}):
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError, "prompt_cache_breakpoint"):
                self.prepare(
                    copilot_wire.RESPONSES,
                    copilot_wire.ANTHROPIC,
                    {
                        "input": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "input_text", "text": "question", "prompt_cache_breakpoint": marker}
                                ],
                            }
                        ],
                    },
                )

    def test_SHOULD_not_invent_a_system_block_when_no_instructions_were_supplied(self):
        translated = self.prepare(
            copilot_wire.CHAT,
            copilot_wire.ANTHROPIC,
            {
                "messages": [{"role": "user", "content": "question"}],
            },
        )
        self.assertNotIn("system", translated)


class TestTranslatedToolIdentity(unittest.TestCase):
    """WHEN Responses tools have namespaces, wire aliases must roundtrip without collisions."""

    def prepare(self, body, backend):
        translator = copilot_wire.WireTranslator()
        selected = model("fixture", (backend,))
        prepared = translator.prepare(copilot_wire.RESPONSES, backend, json.dumps(body).encode(), selected)
        return translator, selected, prepared, json.loads(prepared.body)

    @staticmethod
    def upstream(backend, stream, name, arguments):
        if backend == copilot_wire.CHAT:
            call = {"id": "new_call", "type": "function", "function": {"name": name, "arguments": arguments}}
            if not stream:
                return io.BytesIO(
                    json.dumps(
                        {"choices": [{"message": {"tool_calls": [call]}, "finish_reason": "tool_calls"}]}
                    ).encode()
                )
            events = [{"choices": [{"delta": {"tool_calls": [{"index": 0, **call}]}, "finish_reason": "tool_calls"}]}]
            return io.BytesIO(
                b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events) + b"data: [DONE]\n\n"
            )
        block = {"type": "tool_use", "id": "new_call", "name": name, "input": json.loads(arguments)}
        if not stream:
            return io.BytesIO(json.dumps({"content": [block], "stop_reason": "tool_use"}).encode())
        events = [
            {"type": "message_start", "message": {"id": "msg"}},
            {"type": "content_block_start", "index": 0, "content_block": block},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta", "delta": {"stop_reason": "tool_use"}},
            {"type": "message_stop"},
        ]
        return io.BytesIO(b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events))

    def test_SHOULD_roundtrip_function_and_custom_namespaces_in_json_and_streams(self):
        for backend in (copilot_wire.CHAT, copilot_wire.ANTHROPIC):
            for stream in (False, True):
                for kind in ("function", "custom"):
                    with self.subTest(backend=backend, stream=stream, kind=kind):
                        argument = "{}" if kind == "function" else '{"arbitrary":"raw custom input"}'
                        body = {
                            "stream": stream,
                            "tools": [
                                {
                                    "type": "namespace",
                                    "name": "functions",
                                    "description": "namespace guidance",
                                    "tools": [
                                        {
                                            "type": kind,
                                            "name": "execute",
                                            "description": "tool guidance",
                                            "parameters": {"type": "object"},
                                        },
                                    ],
                                },
                                {"type": "function", "name": "execute", "parameters": {"type": "object"}},
                            ],
                            "input": [
                                {
                                    "type": "custom_tool_call" if kind == "custom" else "function_call",
                                    "namespace": "functions",
                                    "name": "execute",
                                    "call_id": "old_call",
                                    "input" if kind == "custom" else "arguments": argument,
                                },
                                {
                                    "type": "custom_tool_call_output" if kind == "custom" else "function_call_output",
                                    "call_id": "old_call",
                                    "output": "done",
                                },
                            ],
                        }
                        translator, selected, prepared, wire = self.prepare(body, backend)
                        (alias,) = prepared.tool_names
                        definitions = [t["function"] if backend == copilot_wire.CHAT else t for t in wire["tools"]]
                        self.assertEqual([t["name"] for t in definitions], [alias, "execute"])
                        self.assertIn("namespace guidance", definitions[0]["description"])
                        self.assertRegex(alias, r"^[a-zA-Z0-9_-]{1,64}$")
                        expected_arguments = {"input": argument} if kind == "custom" else {}
                        historical = wire["messages"][0]
                        if backend == copilot_wire.CHAT:
                            self.assertEqual(
                                historical["tool_calls"][0]["function"],
                                {"name": alias, "arguments": json.dumps(expected_arguments, separators=(",", ":"))},
                            )
                        else:
                            self.assertEqual(historical["content"][0]["name"], alias)
                            self.assertEqual(historical["content"][0]["input"], expected_arguments)
                        rendered = translator.render(
                            copilot_wire.RESPONSES,
                            backend,
                            self.upstream(backend, stream, alias, json.dumps(expected_arguments)),
                            selected,
                            prepared,
                        )
                        if stream:
                            events = [
                                json.loads(line[6:])
                                for line in b"".join(rendered).splitlines()
                                if line.startswith(b"data: ")
                            ]
                            items = [
                                e["item"]
                                for e in events
                                if e["type"] in ("response.output_item.added", "response.output_item.done")
                            ]
                            self.assertEqual(len(items), 2)
                        else:
                            items = json.loads(rendered)["output"]
                        for item in items:
                            self.assertEqual((item["namespace"], item["name"]), ("functions", "execute"))
                        self.assertEqual(
                            items[-1]["input" if kind == "custom" else "arguments"],
                            argument if kind == "custom" else "{}",
                        )

    def test_SHOULD_reserve_plain_names_and_include_historical_only_identities(self):
        body = {
            "stream": False,
            "tools": [{"type": "namespace", "name": "a", "tools": [{"type": "function", "name": "b"}]}],
            "input": [
                {"type": "function_call", "namespace": "retired", "name": "b", "call_id": "old", "arguments": "{}"}
            ],
        }
        _, _, first, _ = self.prepare(body, copilot_wire.CHAT)
        collision = next(name for name, identity in first.tool_names.items() if identity["namespace"] == "a")
        body["tools"].append({"type": "function", "name": collision})
        _, _, second, wire = self.prepare(body, copilot_wire.CHAT)
        self.assertNotIn(collision, second.tool_names)
        self.assertEqual(len({t["function"]["name"] for t in wire["tools"]}), 2)
        history = wire["messages"][0]["tool_calls"][0]["function"]["name"]
        self.assertEqual(second.tool_names[history], {"namespace": "retired", "name": "b"})
        body["tools"].reverse()
        _, _, reordered, _ = self.prepare(body, copilot_wire.CHAT)
        self.assertEqual(second.tool_names, reordered.tool_names)

    def test_SHOULD_reject_malformed_namespaces_instead_of_dropping_their_tools(self):
        for namespace in ("", None, 12):
            with self.subTest(namespace=namespace), self.assertRaisesRegex(ValueError, "namespace"):
                self.prepare({"tools": [{"type": "namespace", "name": namespace, "tools": []}]}, copilot_wire.CHAT)
        with self.assertRaisesRegex(ValueError, "without nesting"):
            self.prepare(
                {
                    "tools": [
                        {
                            "type": "namespace",
                            "name": "a",
                            "tools": [
                                {"type": "namespace", "name": "b", "tools": []},
                            ],
                        }
                    ]
                },
                copilot_wire.ANTHROPIC,
            )


class TestTranslatedResponseTextLifecycle(unittest.TestCase):
    """WHEN text and tools alternate, each text delta must target the native active item."""

    def render(self, source, tool_kind="function"):
        streaming = copilot_wire._GC["streaming"]
        selected = copilot_wire.WireTranslator._gc_model(model("fixture", (copilot_wire.ANTHROPIC,)), "claude")
        frames = streaming.render_responses(
            source, selected, {"execute": tool_kind}, {"execute": {"namespace": "functions", "name": "execute"}}
        )
        active = None
        added = {}
        done = {}
        events = []
        for frame in frames:
            event = json.loads(frame.decode().split("data: ", 1)[1])
            if "sequence_number" in event:
                self.assertEqual(event["sequence_number"], len(events))
            events.append(event)
            if event["type"] == "response.output_item.added":
                # Match Codex's single active_item, rather than accepting any previously seen ID.
                if active is not None:
                    self.assertNotEqual(added[active][1], "message", "text remained active across another item")
                active = event["item"]["id"]
                self.assertNotIn(active, added)
                self.assertEqual(event["output_index"], len(added))
                added[active] = (event["output_index"], event["item"]["type"])
            elif event["type"] == "response.output_text.delta":
                self.assertEqual(event["item_id"], active, "text delta has no matching native active item")
                self.assertEqual(added[active], (event["output_index"], "message"))
            elif event["type"] == "response.output_item.done":
                item = event["item"]
                self.assertNotIn(item["id"], done)
                self.assertEqual(added[item["id"]], (event["output_index"], item["type"]))
                done[item["id"]] = item
                active = None
        return list(done.values()), events

    @staticmethod
    def tool(index, tool_kind="function"):
        return [
            {"type": "tool_start", "index": index, "id": f"call_{index}", "name": "execute"},
            {
                "type": "tool_delta",
                "index": index,
                "arguments": '{"input":"raw custom text"}' if tool_kind == "custom" else '{"value":1}',
            },
            {"type": "tool_stop", "index": index},
        ]

    def test_SHOULD_preserve_interleaved_text_and_tool_order_at_each_block_boundary(self):
        for tool_kind in ("function", "custom"):
            for count in (0, 1, 10, 100):
                with self.subTest(tool_kind=tool_kind, count=count):
                    source = []
                    for index in range(count):
                        source.extend(
                            [
                                {"type": "text_delta", "text": f"before {index} "},
                                {"type": "text_delta", "text": "✓"},
                                {"type": "block_stop", "index": index * 2, "block_kind": "text"},
                                *self.tool(index * 2 + 1, tool_kind),
                            ]
                        )
                    source.extend([{"type": "text_delta", "text": "final"}, {"type": "finish", "reason": "end_turn"}])
                    items, events = self.render(source, tool_kind)
                    self.assertEqual(len(items), 2 * count + 1)
                    for index in range(count):
                        self.assertEqual(items[2 * index]["content"][0]["text"], f"before {index} ✓")
                        call = items[2 * index + 1]
                        self.assertEqual(call["namespace"], "functions")
                        self.assertEqual(call["name"], "execute")
                        self.assertEqual(call["call_id"], f"call_{2 * index + 1}")
                        if tool_kind == "custom":
                            self.assertEqual(call["input"], "raw custom text")
                        else:
                            self.assertEqual(json.loads(call["arguments"]), {"value": 1})
                    self.assertEqual(items[-1]["content"][0]["text"], "final")
                    self.assertEqual(events[-1]["type"], "response.completed")

    def test_SHOULD_close_text_around_chat_tools_without_explicit_text_block_stops(self):
        source = [
            {"type": "text_delta", "text": "before"},
            *self.tool(0),
            {"type": "text_delta", "text": "after"},
            # Chat backends can keep a tool open across text chunks until stream completion.
            {"type": "tool_start", "index": 1, "id": "call_1", "name": "execute"},
            {"type": "tool_delta", "index": 1, "arguments": "{}"},
            {"type": "text_delta", "text": "during"},
            {"type": "tool_stop", "index": 1},
            {"type": "text_delta", "text": "final"},
            {"type": "finish", "reason": "tool_calls"},
        ]
        items, events = self.render(source)
        self.assertEqual(
            [part["text"] for item in items if item["type"] == "message" for part in item["content"]],
            ["before", "after", "during", "final"],
        )
        self.assertEqual([item["call_id"] for item in items if item["type"] == "function_call"], ["call_0", "call_1"])
        self.assertEqual(events[-1]["type"], "response.completed")

    def test_SHOULD_ignore_empty_and_nontext_stops_without_splitting_text_deltas(self):
        source = [
            {"type": "text_start", "index": 0},
            {"type": "block_stop", "index": 0, "block_kind": "text"},
            {"type": "text_delta", "text": "a"},
            {"type": "block_stop", "index": 1, "block_kind": "thinking"},
            {"type": "tool_stop", "index": 99},
            {"type": "text_delta", "text": "b"},
            {"type": "finish", "reason": "end_turn"},
        ]
        items, _ = self.render(source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["content"][0]["text"], "ab")
        items, events = self.render(source[:2] + [{"type": "finish", "reason": "end_turn"}])
        self.assertEqual(items, [])
        self.assertEqual([event["type"] for event in events], ["response.completed"])

    def test_SHOULD_not_complete_or_continue_after_upstream_error(self):
        items, events = self.render(
            [
                {"type": "text_delta", "text": "partial"},
                {"type": "error", "error": {"message": "upstream failed"}},
                {"type": "text_delta", "text": "must not appear"},
                {"type": "finish", "reason": "end_turn"},
            ]
        )
        self.assertEqual(items, [])
        self.assertEqual(events[-1]["type"], "response.failed")
        self.assertEqual([event["delta"] for event in events if "delta" in event], ["partial"])


class TestTranslatedRefusals(unittest.TestCase):
    """WHEN a Messages backend refuses, Responses clients must receive a visible failure."""

    @staticmethod
    def render(reason, stream, text="", tool=False):
        translator = copilot_wire.WireTranslator()
        selected = model("fixture", (copilot_wire.ANTHROPIC,))
        prepared = translator.prepare(
            copilot_wire.RESPONSES,
            copilot_wire.ANTHROPIC,
            json.dumps({"stream": stream, "input": "fixture"}).encode(),
            selected,
        )
        usage = {
            "input_tokens": 2,
            "cache_creation_input_tokens": 521,
            "cache_read_input_tokens": 0,
            "output_tokens": 7 if text else 0,
        }
        content = [{"type": "text", "text": text}] if text else []
        if tool:
            content.append({"type": "tool_use", "id": "call_fixture", "name": "fixture", "input": {"value": 1}})
        if stream:
            upstream_events = [{"type": "message_start", "message": {"usage": usage}}]
            for index, block in enumerate(content):
                upstream_events.extend(
                    [
                        {"type": "content_block_start", "index": index, "content_block": block},
                        {"type": "content_block_stop", "index": index},
                    ]
                )
            upstream_events.extend(
                [
                    {"type": "message_delta", "delta": {"stop_reason": reason}, "usage": usage},
                    {"type": "message_stop"},
                ]
            )
            upstream = io.BytesIO(
                b"".join(b"data: " + json.dumps(event).encode() + b"\n\n" for event in upstream_events)
            )
        else:
            upstream = io.BytesIO(json.dumps({"content": content, "stop_reason": reason, "usage": usage}).encode())
        rendered = translator.render(copilot_wire.RESPONSES, copilot_wire.ANTHROPIC, upstream, selected, prepared)
        if not stream:
            response = json.loads(rendered)
            return response, response["output"], []
        events = [json.loads(line[6:]) for line in b"".join(rendered).splitlines() if line.startswith(b"data: ")]
        return (
            events[-1]["response"],
            [event["item"] for event in events if event["type"] == "response.output_item.done"],
            events,
        )

    def test_SHOULD_fail_refusals_without_losing_partial_text_or_cache_usage(self):
        for stream in (False, True):
            for text in ("", "Already emitted text."):
                with self.subTest(stream=stream, text=text):
                    response, items, events = self.render("refusal", stream, text)
                    self.assertEqual(response["status"], "failed")
                    # Codex 0.154.0's Responses parser treats invalid_prompt as InvalidRequest.
                    self.assertEqual(response["error"]["code"], "invalid_prompt")
                    self.assertIn("stop_reason=refusal", response["error"]["message"])
                    self.assertEqual(response["usage"]["input_tokens"], 523)
                    self.assertEqual(
                        response["usage"]["input_tokens_details"], {"cached_tokens": 0, "cache_write_tokens": 521}
                    )
                    self.assertEqual(response["usage"]["output_tokens"], 7 if text else 0)
                    self.assertEqual("".join(part["text"] for item in items for part in item["content"]), text)
                    if stream:
                        self.assertEqual(events[-1]["type"], "response.failed")
                        self.assertNotIn("response.completed", [event["type"] for event in events])

    def test_SHOULD_preserve_tool_output_before_refusal(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                response, items, _ = self.render("refusal", stream, tool=True)
                self.assertEqual(response["status"], "failed")
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["type"], "function_call")
                self.assertEqual(items[0]["call_id"], "call_fixture")
                self.assertEqual(items[0]["name"], "fixture")
                self.assertEqual(json.loads(items[0]["arguments"]), {"value": 1})

    def test_SHOULD_preserve_other_stop_reasons_in_both_response_modes(self):
        for stream in (False, True):
            for reason in ("end_turn", "tool_use", "max_tokens", "stop_sequence", "Refusal", "refusal ", None):
                with self.subTest(stream=stream, reason=reason):
                    response, items, events = self.render(reason, stream, "Ordinary output.")
                    self.assertEqual(response["status"], "completed")
                    self.assertNotIn("error", response)
                    self.assertEqual(items[0]["content"][0]["text"], "Ordinary output.")
                    if stream:
                        self.assertEqual(events[-1]["type"], "response.completed")

    def test_SHOULD_stop_the_refused_stream_before_any_trailing_events(self):
        streaming = copilot_wire._GC["streaming"]
        selected = copilot_wire.WireTranslator._gc_model(model("fixture", (copilot_wire.ANTHROPIC,)), "claude")
        frames = b"".join(
            streaming.render_responses(
                [
                    {"type": "finish", "reason": "refusal", "usage": {}},
                    {"type": "text_delta", "text": "Must not appear after refusal."},
                ],
                selected,
                {},
            )
        )
        events = [json.loads(line[6:]) for line in frames.splitlines() if line.startswith(b"data: ")]
        self.assertEqual([event["type"] for event in events], ["response.failed"])


class TestTranslatedChatUsage(unittest.TestCase):
    """WHEN Chat requests streaming usage, the terminal usage-only chunk carries the full split."""

    def test_SHOULD_honor_include_usage_for_both_translated_backends(self):
        for backend in (copilot_wire.ANTHROPIC, copilot_wire.RESPONSES):
            for include in (False, True, None):
                with self.subTest(backend=backend, include=include):
                    translator = copilot_wire.WireTranslator()
                    selected = model("fixture", (backend,))
                    body = {"stream": True, "messages": [{"role": "user", "content": "hello"}]}
                    if include is not None:
                        body["stream_options"] = {"include_usage": include}
                    prepared = translator.prepare(copilot_wire.CHAT, backend, json.dumps(body).encode(), selected)
                    self.assertNotIn("stream_options", json.loads(prepared.body))
                    if backend == copilot_wire.ANTHROPIC:
                        events = [
                            {
                                "type": "message_start",
                                "message": {
                                    "usage": {
                                        "input_tokens": 6,
                                        "cache_read_input_tokens": 90,
                                        "cache_creation_input_tokens": 4,
                                    }
                                },
                            },
                            {
                                "type": "message_delta",
                                "delta": {"stop_reason": "end_turn"},
                                "usage": {"output_tokens": 5},
                            },
                            {"type": "message_stop"},
                        ]
                    else:
                        events = [
                            {"type": "response.created", "response": {"id": "resp"}},
                            {
                                "type": "response.completed",
                                "response": {
                                    "usage": {
                                        "input_tokens": 100,
                                        "output_tokens": 5,
                                        "input_tokens_details": {"cached_tokens": 90, "cache_write_tokens": 4},
                                    }
                                },
                            },
                        ]
                    upstream = io.BytesIO(b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events))
                    frames = b"".join(translator.render(copilot_wire.CHAT, backend, upstream, selected, prepared))
                    chunks = [json.loads(line[6:]) for line in frames.splitlines() if line.startswith(b"data: {")]
                    usage_chunks = [chunk for chunk in chunks if isinstance(chunk.get("usage"), dict)]
                    self.assertEqual(len(usage_chunks), int(bool(include)))
                    if include:
                        self.assertEqual(usage_chunks[0]["choices"], [])
                        self.assertEqual(
                            usage_chunks[0]["usage"],
                            {
                                "prompt_tokens": 100,
                                "completion_tokens": 5,
                                "total_tokens": 105,
                                "prompt_tokens_details": {"cached_tokens": 90, "cache_creation_tokens": 4},
                            },
                        )
                        self.assertTrue(all(chunk["usage"] is None for chunk in chunks[:-1]))
                    else:
                        self.assertTrue(all("usage" not in chunk for chunk in chunks))
                    self.assertTrue(frames.endswith(b"data: [DONE]\n\n"))


class TestFishCompletions(unittest.TestCase):
    """WHEN completing adapter-owned option values in Fish."""

    def test_SHOULD_not_mix_filesystem_candidates_with_models_or_efforts(self) -> None:
        cases = {
            "claude-copilot": {
                "--model": {"claude-sonnet-5", "gpt-5.3-codex", "gemini-3.5-flash"},
                "-m": {"claude-sonnet-5", "gpt-5.3-codex", "gemini-3.5-flash"},
                "--effort": {"medium"},
                "--reasoning-effort": {"medium"},
                "--thinking": {"auto", "on", "off"},
                "--context": {"default", "long_context"},
            },
            "codex-copilot": {
                "--model": {"claude-sonnet-5", "gpt-5.3-codex", "gemini-3.5-flash"},
                "-m": {"claude-sonnet-5", "gpt-5.3-codex", "gemini-3.5-flash"},
                "--effort": {"medium"},
                "--reasoning-effort": {"medium"},
                "--thinking": {"auto", "on", "off"},
                "--context": {"default", "long_context"},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "filesystem-decoy").touch()
            for command, flags in cases.items():
                completion = REPO / f"home/dot_config/fish/completions/readonly_,{command}.fish"
                for flag, expected in flags.items():
                    result = subprocess.run(
                        [
                            "fish",
                            "-c",
                            f'complete -e -c ,{command}; source $COMPLETION_FILE; complete -C ",{command} {flag} "',
                        ],
                        cwd=directory,
                        check=True,
                        capture_output=True,
                        text=True,
                        env={**os.environ, "COMPLETION_FILE": str(completion)},
                    )
                    candidates = {line.split("\t", 1)[0] for line in result.stdout.splitlines()}

                    self.assertLessEqual(expected, candidates)
                    self.assertNotIn("filesystem-decoy", candidates)


class RecordingUpstream(ThreadingHTTPServer):
    request_path = ""
    request_headers: ClassVar[dict[str, str]] = {}
    request_body = b""
    request_count = 0
    fail_first = False
    response_body = b'data: {"type":"response.completed"}\n\n'


class RecordingHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_POST(self) -> None:
        size = int(self.headers.get("Content-Length", "0"))
        self.server.request_count += 1  # type: ignore[attr-defined]
        self.server.request_path = self.path  # type: ignore[attr-defined]
        self.server.request_headers = dict(self.headers.items())  # type: ignore[attr-defined]
        self.server.request_body = self.rfile.read(size)  # type: ignore[attr-defined]
        if self.server.fail_first and self.server.request_count == 1:  # type: ignore[attr-defined]
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        payload = self.server.response_body  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class TestLoopbackProxy(unittest.TestCase):
    """WHEN forwarding native harness requests to Copilot."""

    def setUp(self) -> None:
        self.upstream = RecordingUpstream(("127.0.0.1", 0), RecordingHandler)
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.upstream_thread.start()
        self.upstream.response_body = b'data: {"type":"response.completed"}\n\n'
        self.tokens = mock.Mock()
        self.tokens.get.return_value = "github-token"
        self.adapter, self.adapter_thread = copilot_server.start_server(
            copilot_server.AdapterContext(
                "local-token",
                self.tokens,
                {
                    "claude-sonnet-5": model("claude-sonnet-5", ("/v1/messages",)),
                    "gpt-5.3-codex": model("gpt-5.3-codex", ("/responses",)),
                    "gemini-3.5-flash": model("gemini-3.5-flash", ("/chat/completions",)),
                },
            )
        )

    def tearDown(self) -> None:
        self.adapter.shutdown()
        self.adapter.server_close()
        self.adapter_thread.join(timeout=5)
        self.upstream.shutdown()
        self.upstream.server_close()
        self.upstream_thread.join(timeout=5)

    def test_SHOULD_map_responses_without_forwarding_local_auth(self) -> None:
        body = b'{"model":"gpt-5.3-codex","stream":true}'
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/responses",
            data=body,
            headers={
                "Authorization": "Bearer local-token",
                "Content-Type": "application/json",
            },
        )
        with (
            mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
            urllib.request.urlopen(request, timeout=5) as response,
        ):
            self.assertEqual(response.read(), b'data: {"type":"response.completed"}\n\n')

        self.assertEqual(self.upstream.request_path, "/responses")
        self.assertEqual(self.upstream.request_body, body)
        self.assertEqual(self.upstream.request_headers["Authorization"], "Bearer github-token")
        self.assertEqual(self.upstream.request_headers["Copilot-Integration-Id"], "copilot-developer-cli")

    def test_SHOULD_include_cursor_extended_metadata_without_changing_legacy_models_response(self) -> None:
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/models",
            headers={"Authorization": "Bearer local-token"},
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read())

        self.assertEqual(
            [model["slug"] for model in payload["models"]],
            [
                "claude-sonnet-5",
                "gpt-5.3-codex",
                "gemini-3.5-flash",
            ],
        )
        self.assertEqual(
            payload["data"],
            [copilot_server.cursor_model_info(model) for model in self.adapter.context.models.values()],
        )

    def test_SHOULD_preserve_registered_child_effort_without_root_thinking(self) -> None:
        object.__setattr__(self.adapter.context, "effort", "low")
        object.__setattr__(self.adapter.context, "thinking", "off")
        self.adapter.context.lane_routes.update(
            {
                "gpt-5.3-codex@lane-high": {"model": "gpt-5.3-codex", "effort": "high"},
                "claude-sonnet-5@lane-high": {"model": "claude-sonnet-5", "effort": "high"},
            }
        )
        cases = (
            ("/v1/responses", "gpt-5.3-codex@lane-high", "reasoning"),
            ("/v1/messages", "claude-sonnet-5@lane-high", "output_config"),
        )
        for path, requested, effort_key in cases:
            with self.subTest(path=path):
                request = urllib.request.Request(
                    f"http://127.0.0.1:{self.adapter.server_port}{path}",
                    data=json.dumps({"model": requested, "stream": True}).encode(),
                    headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
                )
                with (
                    mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
                    urllib.request.urlopen(request, timeout=5) as response,
                ):
                    response.read()
                sent = json.loads(self.upstream.request_body)
                self.assertEqual(sent["model"], requested.split("@lane-")[0])
                self.assertEqual(sent[effort_key]["effort"], "high")
                self.assertNotEqual(sent.get("thinking", {}).get("type"), "disabled")

    def test_SHOULD_reject_unknown_lane_tags_without_upstream_requests(self) -> None:
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/responses",
            data=b'{"model":"gpt-5.3-codex@lane-invented","stream":true}',
            headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
        )
        with mock.patch("copilot_server.api_url") as upstream, self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 502)
        upstream.assert_not_called()

    def test_SHOULD_preserve_root_effort_when_raw_model_matches_a_different_lane(self) -> None:
        object.__setattr__(self.adapter.context, "effort", "low")
        self.adapter.context.lane_routes.update(
            {
                "gpt-5.3-codex@lane-high": {"model": "gpt-5.3-codex", "effort": "high"},
                "claude-sonnet-5@lane-high": {"model": "claude-sonnet-5", "effort": "high"},
            }
        )
        for path, selected, effort_key in (
            ("/v1/responses", "gpt-5.3-codex", "reasoning"),
            ("/v1/messages", "claude-sonnet-5", "output_config"),
        ):
            with self.subTest(path=path):
                object.__setattr__(self.adapter.context, "thinking", "off" if path == "/v1/messages" else None)
                request = urllib.request.Request(
                    f"http://127.0.0.1:{self.adapter.server_port}{path}",
                    data=json.dumps({"model": selected, "stream": True}).encode(),
                    headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
                )
                with (
                    mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
                    urllib.request.urlopen(request, timeout=5) as response,
                ):
                    response.read()
                sent = json.loads(self.upstream.request_body)
                self.assertEqual(sent["model"], selected)
                self.assertEqual(sent[effort_key]["effort"], "low")
                if path == "/v1/messages":
                    self.assertEqual(sent["thinking"]["type"], "disabled")

    def test_SHOULD_map_messages_and_strip_only_the_unsupported_claude_beta(self) -> None:
        object.__setattr__(self.adapter.context, "effort", "high")
        object.__setattr__(self.adapter.context, "thinking", "off")
        body = b'{"model":"claude-sonnet-5[1m]","stream":true}'
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/messages?beta=true",
            data=body,
            headers={
                "Authorization": "Bearer local-token",
                "Content-Type": "application/json",
                "Anthropic-Beta": "prompt-caching-2024-07-31,advisor-tool-2026-03-01",
            },
        )
        with (
            mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
            urllib.request.urlopen(request, timeout=5) as response,
        ):
            self.assertEqual(response.read(), b'data: {"type":"response.completed"}\n\n')

        self.assertEqual(self.upstream.request_path, "/v1/messages?beta=true")
        upstream_body = json.loads(self.upstream.request_body)
        self.assertEqual(upstream_body["model"], "claude-sonnet-5")
        self.assertEqual(upstream_body["thinking"], {"type": "disabled"})
        self.assertEqual(upstream_body["output_config"], {"effort": "high"})
        self.assertEqual(
            self.upstream.request_headers["Anthropic-Beta"],
            "prompt-caching-2024-07-31",
        )

    def test_SHOULD_preserve_native_claude_count_tokens_route(self) -> None:
        self.upstream.response_body = b'{"input_tokens":8}'
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/messages/count_tokens?beta=true",
            data=b'{"model":"claude-sonnet-5","messages":[{"role":"user","content":"hello"}]}',
            headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
        )

        with (
            mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
            urllib.request.urlopen(request, timeout=5) as response,
        ):
            self.assertEqual(json.loads(response.read()), {"input_tokens": 8})

        self.assertEqual(self.upstream.request_path, "/v1/messages/count_tokens?beta=true")

    def test_SHOULD_estimate_count_tokens_without_contacting_a_non_messages_backend(self) -> None:
        self.upstream.request_path = ""
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/messages/count_tokens",
            data=b'{"model":"gpt-5.3-codex","messages":[{"role":"user","content":"hello"}]}',
            headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read())

        self.assertGreater(payload["input_tokens"], 0)
        self.assertEqual(self.upstream.request_path, "")

    def test_SHOULD_translate_messages_to_responses_for_a_gpt_model(self) -> None:
        self.upstream.response_body = (
            b'data: {"type":"response.created","response":{"id":"resp_test","usage":{"input_tokens":3}}}\n\n'
            b'data: {"type":"response.output_text.delta","delta":"GPT_OK"}\n\n'
            b'data: {"type":"response.completed","response":{"usage":{"input_tokens":3,"output_tokens":2}}}\n\n'
        )
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/messages",
            data=(
                b'{"model":"gpt-5.3-codex","max_tokens":32,"stream":true,'
                b'"messages":[{"role":"user","content":"reply"}]}'
            ),
            headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
        )

        with (
            mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
            urllib.request.urlopen(request, timeout=5) as response,
        ):
            translated = response.read()

        upstream_body = json.loads(self.upstream.request_body)
        self.assertEqual(self.upstream.request_path, "/responses")
        self.assertEqual(upstream_body["model"], "gpt-5.3-codex")
        self.assertEqual(upstream_body["input"][0]["role"], "user")
        self.assertIn(b'"type":"text_delta","text":"GPT_OK"', translated)
        self.assertIn(b'"type":"message_stop"', translated)

    def test_SHOULD_translate_cursor_chat_to_responses_for_the_default_model(self) -> None:
        self.upstream.response_body = (
            b'data: {"type":"response.created","response":{"id":"resp_test"}}\n\n'
            b'data: {"type":"response.output_text.delta","delta":"CURSOR_OK"}\n\n'
            b'data: {"type":"response.completed","response":{"usage":{"input_tokens":3,"output_tokens":2}}}\n\n'
        )
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/chat/completions",
            data=b'{"model":"gpt-5.3-codex","stream":false,"messages":[{"role":"user","content":"reply"}]}',
            headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
        )

        with (
            mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
            urllib.request.urlopen(request, timeout=5) as response,
        ):
            translated = json.loads(response.read())

        upstream_body = json.loads(self.upstream.request_body)
        self.assertEqual(self.upstream.request_path, "/responses")
        self.assertEqual(upstream_body["input"][0]["role"], "user")
        self.assertEqual(translated["choices"][0]["message"]["content"], "CURSOR_OK")

    def test_SHOULD_return_json_for_non_stream_messages_translated_to_responses(self) -> None:
        self.upstream.response_body = (
            b'data: {"type":"response.created","response":{"id":"resp_test","usage":{"input_tokens":3}}}\n\n'
            b'data: {"type":"response.output_text.delta","delta":"GPT_OK"}\n\n'
            b'data: {"type":"response.completed","response":{"usage":{"input_tokens":3,"output_tokens":2}}}\n\n'
        )
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/messages",
            data=(
                b'{"model":"gpt-5.3-codex","max_tokens":32,"stream":false,'
                b'"messages":[{"role":"user","content":"reply"}]}'
            ),
            headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
        )

        with (
            mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
            urllib.request.urlopen(request, timeout=5) as response,
        ):
            content_type = response.headers["Content-Type"]
            translated = json.loads(response.read())

        self.assertEqual(content_type, "application/json")
        self.assertEqual(translated["type"], "message")
        self.assertEqual(translated["content"], [{"type": "text", "text": "GPT_OK"}])

    def test_SHOULD_emit_a_frontend_error_when_a_translated_stream_ends_early(self) -> None:
        self.upstream.response_body = (
            b'data: {"type":"response.created","response":{"id":"resp_test","usage":{"input_tokens":3}}}\n\n'
        )
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/messages",
            data=(
                b'{"model":"gpt-5.3-codex","max_tokens":32,"stream":true,'
                b'"messages":[{"role":"user","content":"reply"}]}'
            ),
            headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
        )

        with (
            mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
            urllib.request.urlopen(request, timeout=5) as response,
        ):
            translated = response.read()

        self.assertNotIn(b"HTTP/1.1 502", translated)
        self.assertIn(b'"type":"error"', translated)
        self.assertIn(b"stream ended without response.completed", translated)

    def test_SHOULD_normalize_copilot_obfuscated_function_argument_item_ids(self) -> None:
        self.upstream.response_body = (
            b'data: {"type":"response.created","response":{"id":"resp_test","usage":{"input_tokens":3}}}\n\n'
            b'data: {"type":"response.output_item.added","output_index":0,"item":'
            b'{"id":"stable-item","type":"function_call","call_id":"call_1","name":"Bash","arguments":""}}\n\n'
            b'data: {"type":"response.function_call_arguments.delta","output_index":0,'
            b'"item_id":"obfuscated-delta-item","delta":"{\\"command\\":\\"pwd\\"}"}\n\n'
            b'data: {"type":"response.output_item.done","output_index":0,"item":'
            b'{"id":"stable-item","type":"function_call","call_id":"call_1","name":"Bash",'
            b'"arguments":"{\\"command\\":\\"pwd\\"}"}}\n\n'
            b'data: {"type":"response.completed","response":{"usage":{"input_tokens":3,"output_tokens":2}}}\n\n'
        )
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/messages",
            data=(
                b'{"model":"gpt-5.3-codex","max_tokens":32,"stream":true,'
                b'"messages":[{"role":"user","content":"use Bash"}],'
                b'"tools":[{"name":"Bash","description":"run command","input_schema":{"type":"object"}}]}'
            ),
            headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
        )

        with (
            mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
            urllib.request.urlopen(request, timeout=5) as response,
        ):
            translated = response.read()

        self.assertIn(b'"type":"tool_use","id":"call_1","name":"Bash"', translated)
        self.assertIn(b'"partial_json":"{\\"command\\":\\"pwd\\"}"', translated)
        self.assertIn(b'"type":"message_stop"', translated)

    def test_SHOULD_translate_responses_to_messages_for_a_claude_model(self) -> None:
        object.__setattr__(self.adapter.context, "effort", "high")
        object.__setattr__(self.adapter.context, "thinking", "off")
        self.upstream.response_body = (
            b"event: message_start\n"
            b'data: {"type":"message_start","message":{"usage":{"input_tokens":3}}}\n\n'
            b"event: content_block_start\n"
            b'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n'
            b"event: content_block_delta\n"
            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"CLAUDE_OK"}}\n\n'
            b"event: content_block_stop\n"
            b'data: {"type":"content_block_stop","index":0}\n\n'
            b"event: message_delta\n"
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}\n\n'
            b"event: message_stop\n"
            b'data: {"type":"message_stop"}\n\n'
        )
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/responses",
            data=(
                b'{"model":"claude-sonnet-5","stream":true,'
                b'"input":[{"type":"message","role":"user","content":"reply"}]}'
            ),
            headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
        )

        with (
            mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
            urllib.request.urlopen(request, timeout=5) as response,
        ):
            translated = response.read()

        upstream_body = json.loads(self.upstream.request_body)
        self.assertEqual(self.upstream.request_path, "/v1/messages")
        self.assertEqual(upstream_body["model"], "claude-sonnet-5")
        self.assertEqual(upstream_body["thinking"], {"type": "disabled"})
        self.assertEqual(upstream_body["output_config"], {"effort": "high"})
        self.assertEqual(upstream_body["messages"][0]["role"], "user")
        self.assertIn(b'"type":"response.output_text.delta"', translated)
        self.assertIn(b'"delta":"CLAUDE_OK"', translated)
        self.assertIn(b'"type":"response.completed"', translated)

    def test_SHOULD_translate_both_harness_protocols_to_chat_for_gemini(self) -> None:
        requests = (
            (
                "/v1/messages",
                (
                    b'{"model":"gemini-3.5-flash","max_tokens":32,"stream":true,'
                    b'"messages":[{"role":"user","content":"reply"}]}'
                ),
                b'"type":"message_stop"',
            ),
            (
                "/v1/responses",
                (
                    b'{"model":"gemini-3.5-flash","stream":true,'
                    b'"input":[{"type":"message","role":"user","content":"reply"}]}'
                ),
                b'"type":"response.completed"',
            ),
            (
                "/v1/chat/completions",
                b'{"model":"gemini-3.5-flash","stream":true,"messages":[{"role":"user","content":"reply"}]}',
                b"[DONE]",
            ),
        )
        for frontend, body, terminal in requests:
            with self.subTest(frontend=frontend):
                self.upstream.response_body = (
                    b'data: {"id":"chat_test","choices":[{"index":0,"delta":'
                    b'{"role":"assistant","content":"GEMINI_OK"},"finish_reason":null}]}\n\n'
                    b'data: {"id":"chat_test","choices":[{"index":0,"delta":{},'
                    b'"finish_reason":"stop"}],"usage":{"prompt_tokens":3,"completion_tokens":2}}\n\n'
                    b"data: [DONE]\n\n"
                )
                request = urllib.request.Request(
                    f"http://127.0.0.1:{self.adapter.server_port}{frontend}",
                    data=body,
                    headers={"Authorization": "Bearer local-token", "Content-Type": "application/json"},
                )
                with (
                    mock.patch(
                        "copilot_server.api_url",
                        return_value=f"http://127.0.0.1:{self.upstream.server_port}",
                    ),
                    urllib.request.urlopen(request, timeout=5) as response,
                ):
                    translated = response.read()

                upstream_body = json.loads(self.upstream.request_body)
                self.assertEqual(self.upstream.request_path, "/chat/completions")
                self.assertEqual(upstream_body["model"], "gemini-3.5-flash")
                self.assertEqual(upstream_body["messages"][-1]["role"], "user")
                self.assertIn(b"GEMINI_OK", translated)
                self.assertIn(terminal, translated)

    def test_SHOULD_reject_a_wrong_loopback_token_without_contacting_upstream(self) -> None:
        self.upstream.request_path = ""
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/messages",
            data=b"{}",
            headers={"Authorization": "Bearer wrong"},
        )

        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request, timeout=5)

        self.assertEqual(raised.exception.code, 401)
        self.assertEqual(self.upstream.request_path, "")

    def test_SHOULD_reload_the_github_token_once_after_an_upstream_401(self) -> None:
        self.upstream.fail_first = True
        self.upstream.request_count = 0
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.adapter.server_port}/v1/responses",
            data=b'{"model":"gpt-5.3-codex","stream":true}',
            headers={"Authorization": "Bearer local-token"},
        )

        with (
            mock.patch("copilot_server.api_url", return_value=f"http://127.0.0.1:{self.upstream.server_port}"),
            urllib.request.urlopen(request, timeout=5) as response,
        ):
            self.assertEqual(response.status, 200)

        self.assertEqual(self.upstream.request_count, 2)
        self.assertEqual(
            self.tokens.get.call_args_list,
            [mock.call(refresh=False), mock.call(refresh=True)],
        )


class CacheUsageTranslationTests(unittest.TestCase):
    """Cache accounting survives normalization and every rendered usage shape."""

    @classmethod
    def setUpClass(cls) -> None:
        import models as models_module
        import streaming as streaming_module

        cls.streaming = streaming_module
        cls.model = models_module.ModelSpec(
            model_id="claude-fable-5",
            backend="claude",
            wire_model="claude-fable-5",
            efforts=("high",),
            default_effort="high",
            thinking_default="off",
            supports_no_thinking=True,
            adapter_default=False,
            context_window=200_000,
            max_output_tokens=8_192,
        )

    def test_SHOULD_normalize_chat_details_by_subtracting_cache_from_prompt_tokens(self) -> None:
        # Shape observed from the Copilot backend: prompt_tokens includes cached and written tokens.
        usage = self.streaming._usage(
            {
                "prompt_tokens": 26377,
                "completion_tokens": 20,
                "total_tokens": 26397,
                "prompt_tokens_details": {"cached_tokens": 0, "cache_creation_tokens": 26375, "cache_ttl_seconds": 300},
            }
        )
        self.assertEqual(
            usage,
            {
                "input_tokens": 2,
                "output_tokens": 20,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 26375,
            },
        )

    def test_SHOULD_keep_anthropic_split_and_responses_details(self) -> None:
        anthropic = self.streaming._usage(
            {"input_tokens": 3, "output_tokens": 2, "cache_read_input_tokens": 500, "cache_creation_input_tokens": 7}
        )
        self.assertEqual(
            anthropic,
            {"input_tokens": 3, "output_tokens": 2, "cache_read_input_tokens": 500, "cache_creation_input_tokens": 7},
        )
        responses = self.streaming._usage(
            {
                "input_tokens": 100,
                "output_tokens": 5,
                "input_tokens_details": {"cached_tokens": 90, "cache_write_tokens": 4},
            }
        )
        self.assertEqual(
            responses,
            {"input_tokens": 6, "output_tokens": 5, "cache_read_input_tokens": 90, "cache_creation_input_tokens": 4},
        )
        # No cache details at all: nothing is zero-filled, "not reported" stays distinguishable.
        self.assertEqual(
            self.streaming._usage({"prompt_tokens": 3, "completion_tokens": 2}), {"input_tokens": 3, "output_tokens": 2}
        )

    def test_SHOULD_render_cache_fields_in_every_json_shape(self) -> None:
        result = {
            "text": "ok",
            "tools": [],
            "thinking": [],
            "reason": "stop",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_read_input_tokens": 90,
                "cache_creation_input_tokens": 4,
            },
        }
        anthropic = self.streaming.render_json("anthropic", result, self.model, {})["usage"]
        self.assertEqual(
            anthropic,
            {"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 4, "cache_read_input_tokens": 90},
        )
        chat = self.streaming.render_json("chat", result, self.model, {})["usage"]
        self.assertEqual(chat["prompt_tokens"], 104)
        self.assertEqual(chat["total_tokens"], 109)
        self.assertEqual(chat["prompt_tokens_details"], {"cached_tokens": 90, "cache_creation_tokens": 4})
        responses = self.streaming.render_json("responses", result, self.model, {})["usage"]
        self.assertEqual(responses["input_tokens"], 104)
        self.assertEqual(responses["input_tokens_details"], {"cached_tokens": 90, "cache_write_tokens": 4})

    def test_SHOULD_emit_the_native_codex_write_counter_in_responses_streams(self) -> None:
        """WHEN translating cache writes, Codex's ResponseCompletedInputTokensDetails must see them."""
        events = [
            {
                "type": "finish",
                "reason": "stop",
                "usage": {
                    "input_tokens": 6,
                    "output_tokens": 5,
                    "cache_read_input_tokens": 90,
                    "cache_creation_input_tokens": 4,
                },
            }
        ]
        frames = b"".join(self.streaming.render_responses(events, self.model, {})).decode()
        (completed,) = [json.loads(line[6:]) for line in frames.splitlines() if line.startswith("data: ")]
        self.assertEqual(
            completed["response"]["usage"],
            {
                "input_tokens": 100,
                "output_tokens": 5,
                "total_tokens": 105,
                "input_tokens_details": {"cached_tokens": 90, "cache_write_tokens": 4},
            },
        )

    def test_SHOULD_carry_cache_fields_through_the_streaming_anthropic_message_delta(self) -> None:
        events = [
            {"type": "text_delta", "index": 0, "text": "ok"},
            {
                "type": "finish",
                "reason": "stop",
                "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 90},
            },
        ]
        frames = b"".join(self.streaming.render_anthropic(iter(events), self.model)).decode()
        deltas = [
            json.loads(line[len("data: ") :])
            for line in frames.splitlines()
            if line.startswith("data: ") and '"message_delta"' in line
        ]
        self.assertEqual(
            deltas[-1]["usage"],
            {"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 90},
        )


if __name__ == "__main__":
    unittest.main()
