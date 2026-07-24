#!/usr/bin/env python3
"""Behavioral tests for the Codex subscription harness adapter."""

from __future__ import annotations

import io
import json
import os
import queue
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401
from _test_support import REPO

ADAPTER = REPO / "home/exact_lib/exact_,codex-adapter"
sys.path.insert(0, str(ADAPTER))

import auth  # noqa: E402
import client  # noqa: E402
import main  # noqa: E402
from protocols import (  # noqa: E402
    aggregate_responses,
    anthropic_to_responses,
    collect_anthropic_message,
    iter_sse_json,
    prepare_responses_request,
    responses_to_anthropic_events,
)
from server import AdapterContext, start_server  # noqa: E402
from state import OpaqueReasoningStore  # noqa: E402


def sse_response(*events: dict[str, object]) -> io.BytesIO:
    body = "".join(f"event: {event.get('type', 'message')}\ndata: {json.dumps(event)}\n\n" for event in events)
    response = io.BytesIO(body.encode())
    response.status = 200  # type: ignore[attr-defined]
    response.headers = {"Content-Type": "text/event-stream"}  # type: ignore[attr-defined]
    return response


def completed_text_events(text: str = "hello") -> list[dict[str, object]]:
    item = {
        "id": "msg_1",
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }
    return [
        {
            "type": "response.created",
            "response": {
                "id": "resp_1",
                "model": "gpt-5.6-sol",
                "status": "in_progress",
                "output": [],
            },
        },
        {
            "type": "response.output_text.delta",
            "item_id": "msg_1",
            "output_index": 0,
            "content_index": 0,
            "delta": text,
        },
        {"type": "response.output_item.done", "output_index": 0, "item": item},
        {
            "type": "response.completed",
            "response": {
                "id": "resp_1",
                "model": "gpt-5.6-sol",
                "status": "completed",
                "output": [],
                "usage": {
                    "input_tokens": 9,
                    "output_tokens": 2,
                    "total_tokens": 11,
                },
            },
        },
    ]


class TestLauncherOptions(unittest.TestCase):
    """The wrapper owns model/effort flags and preserves harness arguments."""

    def test_SHOULD_parse_model_effort_aliases_and_passthrough_boundary(self) -> None:
        options = main.parse_args(
            [
                "-m",
                "gpt-test",
                "--reasoning-effort=xhigh",
                "-p",
                "hello",
                "--",
                "--model",
                "harness-model",
                "--effort",
                "low",
            ]
        )

        self.assertEqual(options.model_id, "gpt-test")
        self.assertEqual(options.effort, "xhigh")
        self.assertEqual(
            options.forwarded,
            ["-p", "hello", "--model", "harness-model", "--effort", "low"],
        )
        self.assertEqual(main.parse_args(["--effort", "ultra"]).effort, "ultra")

    def test_SHOULD_reject_unknown_effort_and_missing_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid effort"):
            main.parse_args(["--effort", "turbo"])
        with self.assertRaisesRegex(ValueError, "requires a value"):
            main.parse_args(["--model"])

    def test_SHOULD_read_default_model_from_active_codex_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.toml"
            config.write_text('model = "gpt-configured"\n', encoding="utf-8")
            self.assertEqual(main.resolve_default_model(config), "gpt-configured")

            config.write_text("[features]\nweb_search = true\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "does not set model"):
                main.resolve_default_model(config)

    def test_SHOULD_resolve_maximum_context_window_from_codex_model_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "models_cache.json"
            cache.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "slug": "gpt-long",
                                "context_window": 272_000,
                                "max_context_window": 1_000_000,
                            },
                            {
                                "slug": "gpt-short",
                                "context_window": 128_000,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(main.resolve_model_context_window("gpt-long", cache), 1_000_000)
            self.assertEqual(main.resolve_model_context_window("gpt-short", cache), 128_000)
            self.assertIsNone(main.resolve_model_context_window("gpt-unknown", cache))

    def test_SHOULD_isolate_real_credentials_and_configure_each_harness(self) -> None:
        inherited = {
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "real-anthropic-key",
            "CLAUDE_CODE_USE_VERTEX": "1",
            "COPILOT_PROVIDER_API_KEY": "real-copilot-key",
            "COPILOT_PROVIDER_BEARER_TOKEN": "real-copilot-bearer",
            "OPENAI_API_KEY": "real-openai-key",
        }
        with mock.patch.dict(os.environ, inherited, clear=True):
            claude_command, claude_env = main.child_command(
                "claude",
                "/usr/bin/claude",
                "http://127.0.0.1:3210",
                "local-token",
                "gpt-selected",
                ["-p", "hello"],
                1_000_000,
            )
            copilot_command, copilot_env = main.child_command(
                "copilot",
                "/usr/bin/copilot",
                "http://127.0.0.1:3210",
                "local-token",
                "gpt-selected",
                ["-p", "hello"],
                1_000_000,
            )

        self.assertEqual(
            claude_command,
            ["/usr/bin/claude", "--model", "gpt-selected[1m]", "-p", "hello"],
        )
        self.assertEqual(claude_env["ANTHROPIC_AUTH_TOKEN"], "local-token")
        self.assertEqual(claude_env["ANTHROPIC_BASE_URL"], "http://127.0.0.1:3210")
        self.assertEqual(claude_env["ANTHROPIC_MODEL"], "gpt-selected[1m]")
        self.assertEqual(claude_env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], "1000000")
        self.assertNotIn("ANTHROPIC_API_KEY", claude_env)
        self.assertNotIn("CLAUDE_CODE_USE_VERTEX", claude_env)
        self.assertNotIn("OPENAI_API_KEY", claude_env)

        self.assertEqual(copilot_command, ["/usr/bin/copilot", "-p", "hello"])
        self.assertEqual(copilot_env["COPILOT_PROVIDER_BEARER_TOKEN"], "local-token")
        self.assertEqual(copilot_env["COPILOT_PROVIDER_WIRE_API"], "responses")
        self.assertEqual(copilot_env["COPILOT_PROVIDER_TRANSPORT"], "http")
        self.assertEqual(copilot_env["COPILOT_PROVIDER_MODEL_ID"], "gpt-selected")
        self.assertNotIn("COPILOT_PROVIDER_API_KEY", copilot_env)
        self.assertNotIn("OPENAI_API_KEY", copilot_env)

    def test_SHOULD_cap_claude_compaction_at_each_backend_context_window(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            medium_command, medium_env = main.child_command(
                "claude",
                "/usr/bin/claude",
                "http://127.0.0.1:3210",
                "local-token",
                "gpt-medium",
                [],
                272_000,
            )
            short_command, short_env = main.child_command(
                "claude",
                "/usr/bin/claude",
                "http://127.0.0.1:3210",
                "local-token",
                "gpt-short",
                [],
                128_000,
            )

        self.assertEqual(medium_command, ["/usr/bin/claude", "--model", "gpt-medium[1m]"])
        self.assertEqual(medium_env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], "272000")
        self.assertEqual(short_command, ["/usr/bin/claude", "--model", "gpt-short"])
        self.assertEqual(short_env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], "128000")


class TestCodexAuthentication(unittest.TestCase):
    """OAuth state stays in the adapter and refreshes only after a rejected request."""

    def test_SHOULD_load_access_token_and_optional_account_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "auth.json"
            path.write_text(
                json.dumps(
                    {
                        "auth_mode": "chatgpt",
                        "tokens": {
                            "access_token": "secret-access",
                            "account_id": "account-1",
                        },
                    }
                ),
                encoding="utf-8",
            )
            credentials = auth.load_credentials(path)

        self.assertEqual(credentials.access_token, "secret-access")
        self.assertEqual(credentials.account_id, "account-1")

    def test_SHOULD_refresh_via_current_app_server_account_read_method(self) -> None:
        responses: queue.Queue[str | None] = queue.Queue()
        writes: list[dict[str, object]] = []

        class FakeStdout:
            def __iter__(self) -> FakeStdout:
                return self

            def __next__(self) -> str:
                line = responses.get(timeout=2)
                if line is None:
                    raise StopIteration
                return line

        class FakeStdin:
            def write(self, wire: str) -> int:
                message = json.loads(wire)
                writes.append(message)
                if message.get("id") == 1:
                    responses.put('{"id":1,"result":{"userAgent":"test"}}\n')
                elif message.get("id") == 2:
                    responses.put('{"id":2,"result":{"account":{"type":"chatgpt"}}}\n')
                return len(wire)

            def flush(self) -> None:
                return

            def close(self) -> None:
                responses.put(None)

        process = mock.Mock()
        process.stdin = FakeStdin()
        process.stdout = FakeStdout()
        process.wait.return_value = 0
        process.poll.return_value = None
        with mock.patch("auth.subprocess.Popen", return_value=process) as popen:
            auth.refresh_via_app_server("/usr/bin/codex")

        popen.assert_called_once()
        self.assertEqual([message.get("method") for message in writes], ["initialize", "initialized", "account/read"])
        self.assertEqual(writes[-1]["params"], {"refreshToken": True})
        self.assertNotIn("getAuthStatus", json.dumps(writes))

    def test_SHOULD_retry_once_with_reloaded_credentials_after_401(self) -> None:
        provider = mock.Mock()
        provider.get.side_effect = [
            auth.Credentials("expired", "account-1"),
            auth.Credentials("fresh", "account-1"),
        ]
        rejected = urllib.error.HTTPError(
            "https://example.invalid/responses",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":{"message":"expired"}}'),
        )
        accepted = sse_response(*completed_text_events())
        opener = mock.Mock(side_effect=[rejected, accepted])
        codex = client.CodexClient(
            provider,
            base_url="https://example.invalid",
            opener=opener,
        )

        response = codex.open({"model": "gpt-test", "input": "hello", "stream": True})

        self.assertIs(response, accepted)
        provider.refresh.assert_called_once_with()
        self.assertEqual(opener.call_count, 2)
        first = opener.call_args_list[0].args[0]
        second = opener.call_args_list[1].args[0]
        self.assertEqual(first.get_header("Authorization"), "Bearer expired")
        self.assertEqual(second.get_header("Authorization"), "Bearer fresh")
        self.assertEqual(second.get_header("Chatgpt-account-id"), "account-1")

    def test_SHOULD_not_refresh_or_retry_non_authentication_failures(self) -> None:
        provider = mock.Mock()
        provider.get.return_value = auth.Credentials("token", None)
        rejected = urllib.error.HTTPError(
            "https://example.invalid/responses",
            400,
            "Bad Request",
            {},
            io.BytesIO(b'{"error":{"message":"bad input","type":"invalid_request_error"}}'),
        )
        opener = mock.Mock(side_effect=rejected)
        codex = client.CodexClient(provider, base_url="https://example.invalid", opener=opener)

        with self.assertRaisesRegex(client.UpstreamError, "bad input"):
            codex.open({"model": "gpt-test", "input": "hello", "stream": True})

        provider.refresh.assert_not_called()
        self.assertEqual(opener.call_count, 1)


class TestResponsesProtocol(unittest.TestCase):
    """Copilot receives its requested Responses shape over a stream-only backend."""

    def test_SHOULD_force_streaming_and_apply_only_explicit_overrides(self) -> None:
        original = {
            "model": "harness-model",
            "input": "hello",
            "stream": False,
            "initiator": "copilot-cli",
            "max_output_tokens": 4096,
            "reasoning": {"effort": "low", "summary": "auto"},
            "include": ["file_search_call.results"],
        }

        overridden = prepare_responses_request(
            original,
            model_override="wrapper-model",
            effort_override="xhigh",
        )
        preserved = prepare_responses_request(
            original,
            model_override=None,
            effort_override=None,
        )

        self.assertTrue(overridden["stream"])
        self.assertFalse(overridden["store"])
        self.assertEqual(overridden["model"], "wrapper-model")
        self.assertEqual(overridden["reasoning"]["effort"], "xhigh")
        self.assertIn("reasoning.encrypted_content", overridden["include"])
        self.assertNotIn("initiator", overridden)
        self.assertNotIn("max_output_tokens", overridden)
        self.assertEqual(preserved["model"], "harness-model")
        self.assertEqual(preserved["reasoning"]["effort"], "low")
        self.assertEqual(original["stream"], False)

    def test_SHOULD_aggregate_completed_output_items_missing_from_final_event(self) -> None:
        response = aggregate_responses(completed_text_events("assembled"))

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["output"][0]["content"][0]["text"], "assembled")
        self.assertEqual(response["usage"]["total_tokens"], 11)

    def test_SHOULD_parse_complete_SSE_artifact_and_reject_incomplete_stream(self) -> None:
        parsed = list(iter_sse_json(sse_response(*completed_text_events("parsed"))))
        self.assertEqual(parsed[-1]["type"], "response.completed")
        with self.assertRaisesRegex(client.UpstreamError, "without response.completed"):
            aggregate_responses(parsed[:-1])


class TestAnthropicRequestTranslation(unittest.TestCase):
    """Claude messages, tool turns, images, and output controls map to Responses."""

    def test_SHOULD_translate_messages_tools_images_and_structured_output(self) -> None:
        store = OpaqueReasoningStore()
        store.put(
            "toolu_1",
            {
                "id": "rs_1",
                "type": "reasoning",
                "encrypted_content": "opaque",
                "summary": [],
            },
        )
        body = {
            "model": "harness-model",
            "system": [{"type": "text", "text": "Be exact."}],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Inspect this"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": "aGVsbG8=",
                            },
                        },
                    ],
                },
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "I will inspect it."},
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "Read",
                            "input": {"file_path": "/tmp/example"},
                        },
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_1",
                            "content": [{"type": "text", "text": "contents"}],
                        }
                    ],
                },
            ],
            "tools": [
                {
                    "name": "Read",
                    "description": "Read a file",
                    "input_schema": {
                        "type": "object",
                        "properties": {"file_path": {"type": "string"}},
                        "required": ["file_path"],
                    },
                },
                {
                    "name": "Write",
                    "description": "Write a file",
                    "input_schema": {"type": "object", "properties": {}},
                },
            ],
            "tool_choice": {"type": "tool", "name": "Read", "disable_parallel_tool_use": True},
            "max_tokens": 2048,
            "output_config": {
                "effort": "high",
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {"title": {"type": "string"}},
                        "required": ["title"],
                        "additionalProperties": False,
                    },
                },
            },
        }

        payload = anthropic_to_responses(
            body,
            model_override="wrapper-model",
            effort_override="xhigh",
            store=store,
        )

        self.assertEqual(payload["model"], "wrapper-model")
        self.assertEqual(payload["instructions"], "Be exact.")
        self.assertEqual(payload["reasoning"]["effort"], "xhigh")
        self.assertNotIn("max_output_tokens", payload)
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertEqual(payload["tool_choice"], "required")
        self.assertEqual([tool["name"] for tool in payload["tools"]], ["Read"])
        self.assertEqual(payload["tools"][0]["name"], "Read")
        self.assertEqual(payload["tools"][0]["parameters"]["required"], ["file_path"])
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertEqual(payload["text"]["format"]["name"], "claude_output")
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertTrue(payload["stream"])
        self.assertFalse(payload["store"])

        serialized = json.dumps(payload)
        self.assertIn("data:image/png;base64,aGVsbG8=", serialized)
        self.assertIn('"type": "function_call_output"', serialized)
        self.assertIn('"encrypted_content": "opaque"', serialized)
        reasoning_index = next(index for index, item in enumerate(payload["input"]) if item.get("type") == "reasoning")
        call_index = next(index for index, item in enumerate(payload["input"]) if item.get("type") == "function_call")
        self.assertLess(reasoning_index, call_index)

    def test_SHOULD_preserve_harness_model_and_effort_when_not_overridden(self) -> None:
        payload = anthropic_to_responses(
            {
                "model": "claude-generated-model",
                "system": [{"type": "text", "text": "Base instructions."}],
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "system", "content": "Runtime instructions."},
                ],
                "output_config": {"effort": "minimal"},
            },
            model_override=None,
            effort_override=None,
            store=OpaqueReasoningStore(),
        )
        self.assertEqual(payload["model"], "claude-generated-model")
        self.assertEqual(payload["reasoning"]["effort"], "minimal")
        self.assertEqual(
            payload["instructions"],
            "Base instructions.\n\nRuntime instructions.",
        )

    def test_SHOULD_reject_malformed_or_unsupported_content(self) -> None:
        with self.assertRaisesRegex(ValueError, "messages"):
            anthropic_to_responses(
                {"model": "gpt-test", "messages": "not-a-list"},
                model_override=None,
                effort_override=None,
                store=OpaqueReasoningStore(),
            )
        with self.assertRaisesRegex(ValueError, "unsupported Anthropic content block"):
            anthropic_to_responses(
                {
                    "model": "gpt-test",
                    "messages": [{"role": "user", "content": [{"type": "document", "source": {}}]}],
                },
                model_override=None,
                effort_override=None,
                store=OpaqueReasoningStore(),
            )


class TestAnthropicResponseTranslation(unittest.TestCase):
    """Responses text, tool calls, usage, and failures render as Anthropic events."""

    def test_SHOULD_stream_text_and_tool_calls_with_anthropic_event_order(self) -> None:
        events = [
            {
                "type": "response.created",
                "response": {"id": "resp_1", "model": "gpt-test", "output": []},
            },
            {
                "type": "response.output_text.delta",
                "item_id": "msg_1",
                "output_index": 0,
                "content_index": 0,
                "delta": "Checking.",
            },
            {
                "type": "response.output_item.done",
                "item": {
                    "id": "rs_1",
                    "type": "reasoning",
                    "encrypted_content": "opaque",
                    "summary": [],
                },
            },
            {
                "type": "response.output_item.added",
                "output_index": 1,
                "item": {
                    "id": "fc_1",
                    "type": "function_call",
                    "call_id": "toolu_1",
                    "name": "Read",
                    "arguments": "",
                },
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "fc_1",
                "output_index": 1,
                "delta": '{"file_path":',
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "fc_1",
                "output_index": 1,
                "delta": '"/tmp/example"}',
            },
            {
                "type": "response.output_item.done",
                "output_index": 1,
                "item": {
                    "id": "fc_1",
                    "type": "function_call",
                    "call_id": "toolu_1",
                    "name": "Read",
                    "arguments": '{"file_path":"/tmp/example"}',
                },
            },
            {
                "type": "response.completed",
                "response": {
                    "id": "resp_1",
                    "model": "gpt-test",
                    "status": "completed",
                    "output": [],
                    "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                },
            },
        ]
        store = OpaqueReasoningStore()

        rendered = list(responses_to_anthropic_events(events, "wrapper-model", store))

        types = [event["type"] for event in rendered]
        self.assertEqual(types[0], "message_start")
        self.assertEqual(types[-2:], ["message_delta", "message_stop"])
        starts = [event for event in rendered if event["type"] == "content_block_start"]
        self.assertEqual(starts[0]["content_block"]["type"], "text")
        self.assertEqual(starts[1]["content_block"]["type"], "tool_use")
        self.assertEqual(starts[1]["content_block"]["id"], "toolu_1")
        deltas = [event for event in rendered if event["type"] == "content_block_delta"]
        self.assertEqual(deltas[0]["delta"]["text"], "Checking.")
        self.assertEqual(
            "".join(event["delta"]["partial_json"] for event in deltas if event["delta"]["type"] == "input_json_delta"),
            '{"file_path":"/tmp/example"}',
        )
        self.assertEqual(rendered[-2]["delta"]["stop_reason"], "tool_use")
        self.assertEqual(rendered[-2]["usage"]["output_tokens"], 5)
        self.assertEqual(store.get("toolu_1")["encrypted_content"], "opaque")

    def test_SHOULD_collect_a_non_streaming_anthropic_message(self) -> None:
        events = responses_to_anthropic_events(
            completed_text_events("collected"),
            "wrapper-model",
            OpaqueReasoningStore(),
        )
        message = collect_anthropic_message(events)

        self.assertEqual(message["type"], "message")
        self.assertEqual(message["model"], "wrapper-model")
        self.assertEqual(message["content"], [{"type": "text", "text": "collected"}])
        self.assertEqual(message["stop_reason"], "end_turn")

    def test_SHOULD_surface_failed_responses_as_anthropic_errors(self) -> None:
        events = [
            {
                "type": "response.failed",
                "response": {
                    "id": "resp_failed",
                    "error": {"code": "server_error", "message": "backend failed"},
                },
            }
        ]
        with self.assertRaisesRegex(client.UpstreamError, "backend failed"):
            list(
                responses_to_anthropic_events(
                    events,
                    "wrapper-model",
                    OpaqueReasoningStore(),
                )
            )


class TestLoopbackServer(unittest.TestCase):
    """The gateway requires its random local token and exposes Claude token counting."""

    def setUp(self) -> None:
        self.fake_client = mock.Mock()
        self.context = AdapterContext(
            model="gpt-test",
            effort="high",
            token="local-secret",
            codex=self.fake_client,
            store=OpaqueReasoningStore(),
        )
        self.server, self.thread = start_server(self.context)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(
        self,
        path: str,
        body: dict[str, object],
        *,
        token: str | None = "local-secret",
    ) -> urllib.response.addinfourl:
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
        return urllib.request.urlopen(request, timeout=5)

    def test_SHOULD_reject_missing_or_wrong_local_credentials(self) -> None:
        for token in (None, "wrong"):
            with self.subTest(token=token):
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    self.request(
                        "/v1/responses",
                        {"model": "gpt-test", "input": "hello"},
                        token=token,
                    )
                self.assertEqual(raised.exception.code, 401)

        self.fake_client.open.assert_not_called()

    def test_SHOULD_require_local_credentials_for_health_checks(self) -> None:
        request = urllib.request.Request(self.base_url + "/healthz")
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(raised.exception.code, 401)

    def test_SHOULD_count_claude_request_tokens_without_upstream_auth(self) -> None:
        with self.request(
            "/v1/messages/count_tokens",
            {
                "model": "gpt-test",
                "system": "Be concise.",
                "messages": [{"role": "user", "content": "hello"}],
                "tools": [],
            },
        ) as response:
            payload = json.load(response)

        self.assertGreater(payload["input_tokens"], 0)
        self.fake_client.open.assert_not_called()

    def test_SHOULD_aggregate_non_streaming_copilot_request(self) -> None:
        self.fake_client.open.return_value = sse_response(*completed_text_events("server"))

        with self.request(
            "/v1/responses",
            {"model": "harness-model", "input": "hello", "stream": False},
        ) as response:
            payload = json.load(response)

        self.assertEqual(payload["output"][0]["content"][0]["text"], "server")
        sent = self.fake_client.open.call_args.args[0]
        self.assertEqual(sent["model"], "gpt-test")
        self.assertEqual(sent["reasoning"]["effort"], "high")
        self.assertTrue(sent["stream"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
