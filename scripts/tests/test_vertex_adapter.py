#!/usr/bin/env python3
"""Behavioral tests for the repo-owned Vertex harness adapter."""

from __future__ import annotations

import io
import json
import os
import signal
import stat
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401
from _test_support import REPO

ADAPTER = REPO / "home/exact_lib/exact_,vertex-adapter"
sys.path.insert(0, str(ADAPTER))

import auth  # noqa: E402
import main  # noqa: E402
from models import ModelRegistry, ModelSpec  # noqa: E402
from protocols import parse_request, to_claude_payload, to_gemini_payload  # noqa: E402
from server import AdapterContext, start_server  # noqa: E402
from state import OpaqueContextStore  # noqa: E402
from streaming import canonical_events, collect_response, render_anthropic, render_chat, render_responses  # noqa: E402
from vertex import VertexClient  # noqa: E402


def model(
    model_id: str = "gemini-3.6-flash",
    backend: str = "gemini-chat",
    efforts: tuple[str, ...] = ("minimal", "low", "medium", "high"),
    supports_no_thinking: bool = False,
    adapter_default: bool = True,
) -> ModelSpec:
    return ModelSpec(
        model_id=model_id,
        backend=backend,
        wire_model=f"google/{model_id}" if backend == "gemini-chat" else model_id,
        efforts=efforts,
        default_effort="medium" if backend == "gemini-chat" else "none",
        thinking_default="high",
        supports_no_thinking=supports_no_thinking,
        adapter_default=adapter_default,
        context_window=1_000_000,
        max_output_tokens=65_536,
    )


def sse_payloads(raw: bytes) -> list[dict]:
    payloads = []
    for block in raw.decode().split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: ") and line != "data: [DONE]":
                payloads.append(json.loads(line.removeprefix("data: ")))
    return payloads


class TestRegistryAndArguments(unittest.TestCase):
    """WHEN selecting curated models and normalized adapter controls."""

    def test_SHOULD_apply_one_default_and_validate_model_specific_effort(self):
        registry = ModelRegistry(
            [
                model(),
                model(
                    "claude-opus-4-7",
                    "claude-raw",
                    ("low", "medium", "high", "xhigh", "max"),
                    True,
                    False,
                ),
            ]
        )

        self.assertEqual(registry.get(None).model_id, "gemini-3.6-flash")
        self.assertEqual(
            registry.resolve_effort(
                registry.get("gemini-3.6-flash"),
                None,
                thinking=False,
                no_thinking=False,
            ),
            "medium",
        )
        self.assertEqual(
            registry.resolve_effort(
                registry.get("claude-opus-4-7"),
                None,
                thinking=False,
                no_thinking=False,
            ),
            "none",
        )
        self.assertEqual(
            registry.resolve_effort(
                registry.get("claude-opus-4-7"),
                "xhigh",
                thinking=False,
                no_thinking=False,
            ),
            "xhigh",
        )
        self.assertEqual(
            registry.resolve_effort(
                registry.get("claude-opus-4-7"),
                None,
                thinking=False,
                no_thinking=True,
            ),
            "none",
        )
        with self.assertRaisesRegex(ValueError, "cannot disable thinking"):
            registry.resolve_effort(
                registry.get("gemini-3.6-flash"),
                None,
                thinking=False,
                no_thinking=True,
            )

    def test_SHOULD_consume_adapter_flags_and_preserve_harness_arguments(self):
        options = main.parse_args(
            [
                "exec",
                "--model",
                "claude-opus-4-7",
                "--thinking=xhigh",
                "--",
                "--model",
                "underlying",
            ]
        )

        self.assertEqual(options.model_id, "claude-opus-4-7")
        self.assertEqual(options.effort, "xhigh")
        self.assertEqual(options.forwarded, ["exec", "--model", "underlying"])

    def test_SHOULD_render_runtime_registry_from_the_canonical_provider_section(self):
        import ai_models

        entries = ai_models.load_provider_models(REPO / "home/.chezmoidata/ai_models.yaml")
        vertex = [entry for entry in entries if entry.get("provider") == "vertex"]

        self.assertEqual(
            [entry["id"] for entry in vertex],
            [
                "gemini-3.6-flash",
                "gemini-3.1-pro-preview",
                "claude-opus-4-6",
                "claude-opus-4-7",
            ],
        )
        self.assertEqual(sum(entry.get("adapter_default") is True for entry in vertex), 1)


class TestProtocolRequests(unittest.TestCase):
    """WHEN normalizing harness histories into a Vertex backend request."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = OpaqueContextStore(Path(self.temporary.name) / "state.json")

    def test_SHOULD_translate_responses_custom_tools_and_restore_gemini_signature(self):
        self.store.save(
            "call-1",
            {"gemini_extra_content": {"google": {"thought_signature": "signed"}}},
        )
        conversation = parse_request(
            "responses",
            {
                "instructions": "system",
                "input": [
                    {"type": "message", "role": "user", "content": "edit it"},
                    {"type": "message", "role": "assistant", "content": "I will patch it."},
                    {
                        "type": "custom_tool_call",
                        "call_id": "call-1",
                        "name": "apply_patch",
                        "input": "*** Begin Patch\n*** End Patch",
                    },
                    {
                        "type": "custom_tool_call_output",
                        "call_id": "call-1",
                        "output": "Done",
                    },
                ],
                "tools": [
                    {
                        "type": "custom",
                        "name": "apply_patch",
                        "description": "Patch files",
                        "format": {
                            "type": "grammar",
                            "syntax": "lark",
                            "definition": 'begin_patch: "*** Begin Patch"',
                        },
                    },
                    {"type": "namespace", "name": "custom", "description": "Deferred tools"},
                ],
            },
        )
        payload = to_gemini_payload(conversation, model(), "high", self.store)

        tool = payload["tools"][0]["function"]
        self.assertIn('begin_patch: "*** Begin Patch"', tool["description"])
        self.assertEqual(tool["parameters"]["required"], ["input"])
        self.assertEqual(payload["tools"][1]["function"]["parameters"]["type"], "object")
        assistant = next(message for message in payload["messages"] if message["role"] == "assistant")
        self.assertIsNone(assistant["content"])
        self.assertEqual(
            json.loads(assistant["tool_calls"][0]["function"]["arguments"]),
            {"input": "*** Begin Patch\n*** End Patch"},
        )
        self.assertEqual(
            assistant["tool_calls"][0]["extra_content"]["google"]["thought_signature"],
            "signed",
        )
        self.assertEqual(payload["reasoning_effort"], "high")

    def test_SHOULD_restore_claude_thinking_before_a_translated_tool_call(self):
        thinking = {"type": "thinking", "thinking": "private", "signature": "signed"}
        self.store.save("tool-1", {"claude_thinking": [thinking]})
        conversation = parse_request(
            "chat",
            {
                "messages": [
                    {"role": "user", "content": "run it"},
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "tool-1",
                                "type": "function",
                                "function": {"name": "bash", "arguments": '{"command":"pwd"}'},
                            }
                        ],
                    },
                    {"role": "tool", "tool_call_id": "tool-1", "content": "/tmp"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "bash",
                            "description": "Run shell",
                            "parameters": {"type": "object"},
                        },
                    }
                ],
            },
        )
        payload = to_claude_payload(
            conversation,
            model("claude-opus-4-7", "claude-raw", ("low", "medium", "high", "xhigh", "max"), True),
            "xhigh",
            self.store,
        )

        assistant = next(message for message in payload["messages"] if message["role"] == "assistant")
        self.assertEqual(assistant["content"][0], thinking)
        self.assertEqual(assistant["content"][1]["type"], "tool_use")
        self.assertNotIn("model", payload)
        self.assertEqual(payload["thinking"], {"type": "adaptive"})
        self.assertEqual(payload["output_config"], {"effort": "xhigh"})


class TestStreamingProtocols(unittest.TestCase):
    """WHEN Vertex streams text, thinking, and tool calls."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state_path = Path(self.temporary.name) / "state.json"
        self.store = OpaqueContextStore(self.state_path)

    def test_SHOULD_emit_codex_custom_tool_events_and_persist_gemini_signature(self):
        chunks = [
            {
                "id": "chat-1",
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {"name": "apply_patch", "arguments": ""},
                                    "extra_content": {"google": {"thought_signature": "signed"}},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chat-1",
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": '{"input":"*** Begin Patch\\n*** End Patch"}'},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            },
        ]
        raw = b"".join(f"data: {json.dumps(chunk)}\n\n".encode() for chunk in chunks) + b"data: [DONE]\n\n"
        events = canonical_events("gemini-chat", io.BytesIO(raw), stream=True, store=self.store)
        output = b"".join(render_responses(events, model(), {"apply_patch": "custom"}))
        payloads = sse_payloads(output)

        done = next(
            payload
            for payload in payloads
            if payload["type"] == "response.output_item.done" and payload["item"]["type"] == "custom_tool_call"
        )
        self.assertEqual(done["item"]["input"], "*** Begin Patch\n*** End Patch")
        added = next(
            payload
            for payload in payloads
            if payload["type"] == "response.output_item.added" and payload["item"]["type"] == "custom_tool_call"
        )
        input_deltas = [
            payload["delta"] for payload in payloads if payload["type"] == "response.custom_tool_call_input.delta"
        ]
        self.assertEqual(added["output_index"], done["output_index"])
        self.assertEqual("".join(input_deltas), "*** Begin Patch\n*** End Patch")
        self.assertEqual(
            OpaqueContextStore(self.state_path).get("call-1")["gemini_extra_content"],
            {"google": {"thought_signature": "signed"}},
        )
        self.assertEqual(payloads[-1]["type"], "response.completed")

    def test_SHOULD_allocate_unique_fallback_tool_ids_across_responses(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {"name": "bash", "arguments": '{"command":"pwd"}'},
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

        call_ids = []
        for _ in range(2):
            events = canonical_events(
                "gemini-chat",
                io.BytesIO(json.dumps(payload).encode()),
                stream=False,
                store=self.store,
            )
            call_ids.append(collect_response(events)["tools"][0]["id"])

        self.assertNotEqual(call_ids[0], call_ids[1])

    def test_SHOULD_translate_claude_thinking_and_tool_stream_to_openai_state(self):
        events = [
            ("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 4}}}),
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "thinking", "thinking": "", "signature": ""},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "thinking_delta", "thinking": "reason"},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "signature_delta", "signature": "signed"},
                },
            ),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 1,
                    "content_block": {"type": "tool_use", "id": "tool-1", "name": "bash", "input": {}},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 1,
                    "delta": {"type": "input_json_delta", "partial_json": '{"command":"pwd"}'},
                },
            ),
            ("content_block_stop", {"type": "content_block_stop", "index": 1}),
            (
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "tool_use"},
                    "usage": {"output_tokens": 8},
                },
            ),
            ("message_stop", {"type": "message_stop"}),
        ]
        raw = b"".join(f"event: {name}\ndata: {json.dumps(payload)}\n\n".encode() for name, payload in events)
        canonical = list(canonical_events("claude-raw", io.BytesIO(raw), stream=True, store=self.store))
        result = collect_response(canonical)
        chat_payloads = sse_payloads(b"".join(render_chat(canonical, model())))
        responses_payloads = sse_payloads(b"".join(render_responses(canonical, model(), {"bash": "function"})))
        tool_chunk = next(payload for payload in chat_payloads if payload["choices"][0]["delta"].get("tool_calls"))
        tool_done = next(
            payload
            for payload in responses_payloads
            if payload["type"] == "response.output_item.done" and payload["item"]["type"] == "function_call"
        )

        self.assertEqual(result["tools"][0]["arguments"], '{"command":"pwd"}')
        self.assertEqual(tool_chunk["choices"][0]["delta"]["tool_calls"][0]["index"], 0)
        self.assertEqual(tool_done["item"]["arguments"], '{"command":"pwd"}')
        self.assertEqual(
            OpaqueContextStore(self.state_path).get("tool-1")["claude_thinking"],
            [{"type": "thinking", "thinking": "reason", "signature": "signed"}],
        )

    def test_SHOULD_emit_index_disciplined_anthropic_stream(self):
        canonical = [
            {"type": "message_start"},
            {"type": "text_delta", "index": 0, "text": "hello"},
            {"type": "tool_start", "index": 1, "id": "tool-1", "name": "bash"},
            {"type": "tool_delta", "index": 1, "arguments": '{"command":"pwd"}'},
            {"type": "tool_stop", "index": 1, "id": "tool-1", "name": "bash", "arguments": ""},
            {"type": "finish", "reason": "tool_calls", "usage": {"output_tokens": 4}},
        ]
        payloads = sse_payloads(b"".join(render_anthropic(canonical, model())))

        self.assertEqual(payloads[0]["type"], "message_start")
        starts = [payload for payload in payloads if payload["type"] == "content_block_start"]
        stops = [payload for payload in payloads if payload["type"] == "content_block_stop"]
        self.assertEqual([payload["index"] for payload in starts], [0, 1])
        self.assertEqual([payload["index"] for payload in stops], [1, 0])
        self.assertEqual(payloads[-2]["delta"]["stop_reason"], "tool_use")
        self.assertEqual(payloads[-1]["type"], "message_stop")

    def test_SHOULD_map_backend_finish_reasons_to_each_frontend_protocol(self):
        chat_payloads = sse_payloads(
            b"".join(
                render_chat(
                    [
                        {"type": "message_start"},
                        {"type": "text_delta", "text": "done"},
                        {"type": "finish", "reason": "end_turn", "usage": {}},
                    ],
                    model(),
                )
            )
        )
        anthropic_payloads = sse_payloads(
            b"".join(
                render_anthropic(
                    [
                        {"type": "message_start"},
                        {"type": "text_delta", "index": 0, "text": "done"},
                        {"type": "finish", "reason": "stop", "usage": {}},
                    ],
                    model(),
                )
            )
        )

        self.assertEqual(chat_payloads[-1]["choices"][0]["finish_reason"], "stop")
        self.assertEqual(anthropic_payloads[-2]["delta"]["stop_reason"], "end_turn")

    def test_SHOULD_fail_closed_when_an_upstream_stream_has_no_terminal_event(self):
        gemini = io.BytesIO(b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":"stop"}]}\n\n')
        claude = io.BytesIO(b'event: message_start\ndata: {"type":"message_start","message":{"usage":{}}}\n\n')

        for backend, response in (("gemini-chat", gemini), ("claude-raw", claude)):
            with self.subTest(backend=backend):
                events = list(canonical_events(backend, response, stream=True, store=self.store))
                self.assertEqual(events[-1]["type"], "error")


class FakeVertex:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    def open(self, model_spec, payload, *, stream):
        self.calls.append((model_spec, payload, stream))
        return io.BytesIO(json.dumps(self.payload).encode())


class TestLoopbackServerAndLaunchers(unittest.TestCase):
    """WHEN wrappers launch a harness against the authenticated local server."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.registry = ModelRegistry([model()])

    def test_SHOULD_require_auth_and_return_a_nonstream_chat_completion(self):
        fake = FakeVertex(
            {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "OK"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            }
        )
        context = AdapterContext(
            registry=self.registry,
            model=model(),
            effort="medium",
            token="secret",
            vertex=fake,
            store=OpaqueContextStore(Path(self.temporary.name) / "state.json"),
        )
        server, thread = start_server(context)
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base_url = f"http://127.0.0.1:{server.server_port}/v1"
        url = f"{base_url}/chat/completions"
        body = json.dumps({"model": "ignored", "messages": [{"role": "user", "content": "hi"}]}).encode()

        with self.assertRaises(urllib.error.HTTPError) as unauthorized:
            urllib.request.urlopen(
                urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}),
                timeout=2,
            )
        self.assertEqual(unauthorized.exception.code, 401)
        api_key_request = urllib.request.Request(
            url,
            data=body,
            headers={"x-api-key": "secret", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(api_key_request, timeout=2) as response:
            self.assertEqual(json.load(response)["choices"][0]["message"]["content"], "OK")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.load(response)
        self.assertEqual(payload["choices"][0]["message"]["content"], "OK")
        self.assertEqual(fake.calls[1][1]["model"], "google/gemini-3.6-flash")
        codex_models = urllib.request.Request(
            f"{base_url}/models?client_version=0.145.0",
            headers={"Authorization": "Bearer secret"},
        )
        claude_models = urllib.request.Request(
            f"{base_url}/models?limit=1000",
            headers={"x-api-key": "secret"},
        )
        with urllib.request.urlopen(codex_models, timeout=2) as response:
            codex_catalog = json.load(response)
        with urllib.request.urlopen(claude_models, timeout=2) as response:
            self.assertEqual(len(json.load(response)["data"]), 1)
        self.assertEqual(codex_catalog["models"][0]["slug"], "gemini-3.6-flash")
        self.assertEqual(codex_catalog["models"][0]["default_reasoning_level"], "medium")
        self.assertEqual(codex_catalog["models"][0]["shell_type"], "shell_command")
        self.assertEqual(codex_catalog["models"][0]["apply_patch_tool_type"], "freeform")
        self.assertEqual(codex_catalog["models"][0]["context_window"], 1_000_000)

    def test_SHOULD_wire_each_harness_without_leaking_adapter_flags(self):
        selected = model()
        codex, codex_env = main._child(
            "codex",
            "/bin/codex",
            "http://127.0.0.1:1",
            "secret",
            selected,
            "high",
            ["exec", "hi"],
            "/tmp/codex-models.json",
        )
        copilot, copilot_env = main._child(
            "copilot", "/bin/copilot", "http://127.0.0.1:1", "secret", selected, "high", ["-p", "hi"]
        )
        claude, claude_env = main._child(
            "claude", "/bin/claude", "http://127.0.0.1:1", "secret", selected, "high", ["-p", "hi"]
        )

        self.assertIn('model_provider="vertex"', codex)
        self.assertIn('model_catalog_json="/tmp/codex-models.json"', codex)
        self.assertEqual(codex[-2:], ["exec", "hi"])
        self.assertEqual(codex_env["VERTEX_ADAPTER_TOKEN"], "secret")
        self.assertEqual(copilot, ["/bin/copilot", "--effort", "high", "-p", "hi"])
        self.assertEqual(copilot_env["COPILOT_PROVIDER_WIRE_API"], "completions")
        # effort=None must not inject --effort into the copilot command
        no_effort_cmd, _ = main._child(
            "copilot", "/bin/copilot", "http://127.0.0.1:1", "secret", selected, None, ["-p", "hi"]
        )
        self.assertEqual(no_effort_cmd, ["/bin/copilot", "-p", "hi"])
        self.assertEqual(claude[:3], ["/bin/claude", "--model", "gemini-3.6-flash"])
        self.assertEqual(claude_env["ANTHROPIC_BASE_URL"], "http://127.0.0.1:1")

    def test_SHOULD_remove_the_per_session_codex_catalog_after_exit(self):
        server = mock.Mock(server_port=1234)
        thread = mock.Mock()
        catalog_paths = []

        def child(_harness, _binary, _base_url, _token, _model, _effort, _forwarded, catalog_path):
            path = Path(catalog_path)
            catalog_paths.append(path)
            self.assertEqual(json.loads(path.read_text())["models"][0]["slug"], "gemini-3.6-flash")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            return ["/bin/true"], {}

        with (
            mock.patch.object(main.ModelRegistry, "load", return_value=self.registry),
            mock.patch.object(main, "resolve_project", return_value="project"),
            mock.patch.object(main, "_harness_binary", return_value="/bin/codex"),
            mock.patch.object(main, "start_server", return_value=(server, thread)),
            mock.patch.object(main, "_child", side_effect=child),
            mock.patch.object(main, "_run_child", return_value=0),
        ):
            self.assertEqual(main.launch("codex", []), 0)

        self.assertEqual(len(catalog_paths), 1)
        self.assertFalse(catalog_paths[0].exists())
        server.shutdown.assert_called_once_with()
        server.server_close.assert_called_once_with()
        thread.join.assert_called_once_with(timeout=5)

    def test_SHOULD_forward_termination_to_the_harness_process_group(self):
        handlers = {}
        previous = {signum: object() for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGWINCH)}

        def install_handler(signum, handler):
            if callable(handler):
                handlers[signum] = handler
            return previous[signum]

        child = mock.Mock(pid=4242)

        def wait():
            handlers[signal.SIGWINCH](signal.SIGWINCH, None)
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            return -signal.SIGTERM

        child.wait.side_effect = wait
        with (
            mock.patch.object(main.subprocess, "Popen", return_value=child) as popen,
            mock.patch.object(main.signal, "signal", side_effect=install_handler),
            mock.patch.object(main.os, "killpg") as killpg,
        ):
            status = main._run_child(["harness"], {"KEY": "value"})

        self.assertEqual(status, 128 + signal.SIGTERM)
        popen.assert_called_once_with(["harness"], env={"KEY": "value"}, start_new_session=True)
        self.assertEqual(
            killpg.call_args_list,
            [mock.call(4242, signal.SIGWINCH), mock.call(4242, signal.SIGTERM)],
        )

    def test_SHOULD_persist_opaque_state_with_owner_only_permissions(self):
        path = Path(self.temporary.name) / "nested" / "state.json"
        OpaqueContextStore(path).save("call-1", {"gemini_extra_content": {"signature": "x"}})

        self.assertEqual(
            OpaqueContextStore(path).get("call-1"),
            {"gemini_extra_content": {"signature": "x"}},
        )
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_SHOULD_refresh_gcloud_tokens_only_when_requested_or_expired(self):
        provider = auth.TokenProvider()
        with mock.patch.object(auth, "_run_gcloud", side_effect=["first", "second"]) as run:
            self.assertEqual(provider.get(), "first")
            self.assertEqual(provider.get(), "first")
            self.assertEqual(provider.get(refresh=True), "second")
        self.assertEqual(run.call_count, 2)

    def test_SHOULD_retry_vertex_once_after_an_authentication_failure(self):
        class Tokens:
            def __init__(self):
                self.refreshes = []

            def get(self, *, refresh=False):
                self.refreshes.append(refresh)
                return "token"

        tokens = Tokens()
        error = urllib.error.HTTPError(
            "https://vertex.invalid",
            401,
            "unauthorized",
            {},
            io.BytesIO(b'{"error":{"message":"expired"}}'),
        )
        response = io.BytesIO(b"{}")
        with mock.patch("urllib.request.urlopen", side_effect=[error, response]) as open_url:
            returned = VertexClient("project", tokens).open(model(), {}, stream=False)

        self.assertIs(returned, response)
        self.assertEqual(tokens.refreshes, [False, True])
        self.assertEqual(open_url.call_count, 2)


if __name__ == "__main__":
    unittest.main()
