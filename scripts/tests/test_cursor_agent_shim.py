#!/usr/bin/env python3
"""Behavioral tests for the cursor-openrouter loopback shim."""

from __future__ import annotations

import http.server
import importlib.util
import json
import threading
import unittest
from importlib.machinery import SourceFileLoader
from urllib.request import Request, urlopen

import _test_support  # noqa: F401
from _test_support import REPO

SHIM_PATH = REPO / "home/exact_lib/exact_,cursor-agent-shim/shim.py"


def _load_shim():
    loader = SourceFileLoader("cursor_agent_shim_rewrite", str(SHIM_PATH))
    spec = importlib.util.spec_from_loader("cursor_agent_shim_rewrite", loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tool_call(name: str, arguments: str = '{"command":"git status"}') -> dict:
    return {"id": "call_1", "type": "function", "function": {"name": name, "arguments": arguments}}


def _completion(*, name: str, streamed: bool = False) -> dict:
    call = _tool_call(name)
    if streamed:
        return {"choices": [{"index": 0, "delta": {"tool_calls": [call]}}]}
    return {"choices": [{"index": 0, "message": {"role": "assistant", "tool_calls": [call]}}]}


def _sse_line(payload: dict) -> bytes:
    return b"data: " + json.dumps(payload, separators=(",", ":")).encode() + b"\n\n"


class TestInboundToolNameRewrite(unittest.TestCase):
    """WHEN a completion names a Claude-style tool Cursor does not expose."""

    def setUp(self):
        self.shim = _load_shim()

    def test_SHOULD_map_bash_to_shell_on_a_json_message(self):
        rewritten = self.shim.rewrite_inbound_tool_names(_completion(name="Bash"))
        name = rewritten["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
        self.assertEqual(name, "Shell")

    def test_SHOULD_map_bash_to_shell_on_a_stream_delta(self):
        rewritten = self.shim.rewrite_inbound_tool_names(_completion(name="Bash", streamed=True))
        name = rewritten["choices"][0]["delta"]["tool_calls"][0]["function"]["name"]
        self.assertEqual(name, "Shell")

    def test_SHOULD_leave_shell_and_unknown_names_unchanged(self):
        for name in ("Shell", "Read", "Edit"):
            rewritten = self.shim.rewrite_inbound_tool_names(_completion(name=name))
            got = rewritten["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
            self.assertEqual(got, name)

    def test_SHOULD_preserve_arguments_when_renaming(self):
        payload = _completion(name="Bash")
        payload["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = (
            '{"command":"git diff --stat HEAD","timeout":30000,"description":"diff"}'
        )
        rewritten = self.shim.rewrite_inbound_tool_names(payload)
        fn = rewritten["choices"][0]["message"]["tool_calls"][0]["function"]
        self.assertEqual(fn["name"], "Shell")
        self.assertEqual(
            fn["arguments"],
            '{"command":"git diff --stat HEAD","timeout":30000,"description":"diff"}',
        )


class TestSseRewrite(unittest.TestCase):
    """WHEN OpenRouter streams chat completions as SSE."""

    def setUp(self):
        self.shim = _load_shim()

    def test_SHOULD_rewrite_a_complete_data_line(self):
        raw = _sse_line(_completion(name="Bash", streamed=True)) + b"data: [DONE]\n\n"
        out, rest = self.shim.rewrite_sse_chunk(raw)
        self.assertEqual(rest, b"")
        self.assertIn(b'"name":"Shell"', out)
        self.assertNotIn(b'"name":"Bash"', out)
        self.assertIn(b"data: [DONE]", out)

    def test_SHOULD_hold_an_incomplete_line_until_the_next_chunk(self):
        payload = _completion(name="Bash", streamed=True)
        full = _sse_line(payload)
        split_at = full.find(b"Bash") + 2
        first, second = full[:split_at], full[split_at:]
        out1, rest = self.shim.rewrite_sse_chunk(first)
        self.assertEqual(out1, b"")
        self.assertTrue(rest)
        out2, rest2 = self.shim.rewrite_sse_chunk(rest + second)
        self.assertEqual(rest2, b"")
        self.assertIn(b'"name":"Shell"', out2)
        self.assertNotIn(b'"name":"Bash"', out2)

    def test_SHOULD_pass_through_non_json_data_lines(self):
        raw = b"data: not-json\n\nevent: ping\n\n"
        out, rest = self.shim.rewrite_sse_chunk(raw)
        self.assertEqual(rest, b"")
        self.assertEqual(out, raw)


class TestShimForwardsRewrittenNames(unittest.TestCase):
    """WHEN the shim proxies /chat/completions from a fake OpenRouter."""

    def setUp(self):
        self.shim = _load_shim()

    def _serve(self, handler_cls):
        upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        upstream.daemon_threads = True
        thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        thread.start()
        self.shim.UPSTREAM = f"http://127.0.0.1:{upstream.server_address[1]}"
        self.shim.API_KEY = "fixture-key"
        self.shim.ALLOWED_MODEL = ""
        shim_server = self.shim.ShimServer(("127.0.0.1", 0), self.shim.ShimHandler)
        shim_server.daemon_threads = True
        shim_thread = threading.Thread(target=shim_server.serve_forever, daemon=True)
        shim_thread.start()
        self.addCleanup(lambda: (shim_server.shutdown(), shim_server.server_close(), shim_thread.join(timeout=5)))
        self.addCleanup(lambda: (upstream.shutdown(), upstream.server_close(), thread.join(timeout=5)))
        return shim_server.server_address[1]

    def test_SHOULD_rewrite_bash_in_a_json_completion_body(self):
        body = json.dumps(_completion(name="Bash")).encode()

        class _Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, _fmt, *_args):
                return

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        port = self._serve(_Handler)
        req = Request(
            f"http://127.0.0.1:{port}/api/v1/chat/completions",
            data=b'{"model":"inclusionai/ling-3.0-flash@preset/effort-max","messages":[]}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read())
        self.assertEqual(payload["choices"][0]["message"]["tool_calls"][0]["function"]["name"], "Shell")

    def test_SHOULD_rewrite_bash_in_a_split_sse_stream(self):
        event = _sse_line(_completion(name="Bash", streamed=True)) + b"data: [DONE]\n\n"
        split_at = event.find(b"Bash") + 2

        class _Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, _fmt, *_args):
                return

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(event[:split_at])
                self.wfile.flush()
                self.wfile.write(event[split_at:])

        port = self._serve(_Handler)
        req = Request(
            f"http://127.0.0.1:{port}/api/v1/chat/completions",
            data=b'{"model":"inclusionai/ling-3.0-flash@preset/effort-max","messages":[],"stream":true}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            raw = resp.read()
        self.assertIn(b'"name":"Shell"', raw)
        self.assertNotIn(b'"name":"Bash"', raw)
        self.assertIn(b"data: [DONE]", raw)


if __name__ == "__main__":
    unittest.main()
