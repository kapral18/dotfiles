#!/usr/bin/env python3
"""Behavioral tests for the GitHub Copilot subscription adapter."""

from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
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


def model(
    model_id: str,
    endpoints: tuple[str, ...],
    efforts: tuple[str, ...] = ("low", "medium", "high"),
    context_windows: dict[str, int] | None = None,
) -> copilot_auth.ModelSpec:
    return copilot_auth.ModelSpec(
        model_id=model_id,
        endpoints=frozenset(endpoints),
        efforts=frozenset(efforts),
        context_window=264_000,
        max_output_tokens=64_000,
        context_windows=context_windows or {"default": 264_000},
    )


class TestArgumentsAndModels(unittest.TestCase):
    """WHEN resolving wrapper controls against the live model catalog."""

    def test_SHOULD_consume_adapter_flags_and_preserve_harness_arguments(self) -> None:
        options = main.parse_args(
            [
                "--model",
                "claude-sonnet-5",
                "--reasoning-effort=high",
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
        self.assertEqual(options.context_tier, "long_context")
        self.assertEqual(options.forwarded, ["-p", "hello", "--model", "underlying"])

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

        with self.assertRaisesRegex(ValueError, "does not support context tier"):
            main.resolve_model(
                "codex",
                main.parse_args(["--context", "long_context"]),
                models,
            )
        with self.assertRaisesRegex(ValueError, "choose: default, long_context"):
            main.parse_args(["--context", "oversized"])

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
                                "max_prompt_tokens": 272_000,
                                "max_output_tokens": 128_000,
                            },
                            "supports": {"reasoning_effort": ["low", "high"]},
                        },
                        "billing": {
                            "token_prices": {
                                "default": {"max_prompt_tokens": 272_000},
                                "long_context": {"max_prompt_tokens": 936_000},
                            }
                        },
                    }
                ]
            }
        )

        self.assertEqual(parsed["gpt-test"].context_window, 400_000)
        self.assertEqual(
            parsed["gpt-test"].context_windows,
            {"default": 400_000, "long_context": 1_000_000},
        )
        self.assertEqual(parsed["gpt-test"].endpoints, {"/responses"})
        self.assertEqual(parsed["gpt-test"].efforts, {"low", "high"})

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
            "OPENAI_API_KEY": "real-openai-key",
        }
        claude_model = model("claude-sonnet-5", ("/v1/messages",))
        codex_model = model("gpt-5.3-codex", ("/responses",), ("low", "high"))
        with mock.patch.dict(os.environ, inherited, clear=True):
            claude_command, claude_env = main.child_command(
                "claude",
                "/usr/bin/claude",
                "http://127.0.0.1:3210",
                "local-token",
                claude_model,
                "high",
                ["-p", "hello"],
            )
            codex_command, codex_env = main.child_command(
                "codex",
                "/usr/bin/codex",
                "http://127.0.0.1:3210",
                "local-token",
                codex_model,
                "high",
                ["exec", "hello"],
            )

        self.assertEqual(
            claude_command,
            ["/usr/bin/claude", "--model", "claude-sonnet-5[1m]", "--effort", "high", "-p", "hello"],
        )
        self.assertEqual(claude_env["ANTHROPIC_AUTH_TOKEN"], "local-token")
        self.assertEqual(claude_env["ANTHROPIC_MODEL"], "claude-sonnet-5[1m]")
        self.assertEqual(claude_env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], "264000")
        self.assertNotIn("GH_TOKEN", claude_env)
        self.assertNotIn("GITHUB_TOKEN", claude_env)
        self.assertNotIn("ANTHROPIC_API_KEY", claude_env)

        self.assertIn('model_provider="copilot_subscription"', codex_command)
        self.assertIn('model_reasoning_effort="high"', codex_command)
        self.assertEqual(codex_env["COPILOT_ADAPTER_TOKEN"], "local-token")
        self.assertNotIn("GH_TOKEN", codex_env)
        self.assertNotIn("GITHUB_TOKEN", codex_env)
        self.assertNotIn("OPENAI_API_KEY", codex_env)


class TestLifecycle(unittest.TestCase):
    """WHEN the child exits after an interactive interrupt."""

    def test_SHOULD_default_codex_effort_to_high_when_unspecified(self) -> None:
        selected = model("gpt-5.3-codex", ("/responses",), ("low", "high"))
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
            result = main.launch("codex", [])

        self.assertEqual(result, 0)
        self.assertIn('model_reasoning_effort="high"', captured["command"])

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
                    "VERTEX_ADAPTER_STATE": str(Path(directory, "vertex-state.json")),
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


class TestFishCompletions(unittest.TestCase):
    """WHEN completing adapter-owned option values in Fish."""

    def test_SHOULD_not_mix_filesystem_candidates_with_models_or_efforts(self) -> None:
        cases = {
            "claude-copilot": {
                "--model": {"claude-sonnet-5", "gpt-5.3-codex", "gemini-3.5-flash"},
                "-m": {"claude-sonnet-5", "gpt-5.3-codex", "gemini-3.5-flash"},
                "--effort": {"medium"},
                "--reasoning-effort": {"medium"},
                "--context": {"default", "long_context"},
            },
            "codex-copilot": {
                "--model": {"claude-sonnet-5", "gpt-5.3-codex", "gemini-3.5-flash"},
                "-m": {"claude-sonnet-5", "gpt-5.3-codex", "gemini-3.5-flash"},
                "--effort": {"medium"},
                "--reasoning-effort": {"medium"},
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

    def test_SHOULD_map_messages_and_strip_only_the_unsupported_claude_beta(self) -> None:
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
        self.assertEqual(self.upstream.request_body, b'{"model":"claude-sonnet-5","stream":true}')
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


if __name__ == "__main__":
    unittest.main()
