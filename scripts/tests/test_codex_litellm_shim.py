#!/usr/bin/env python3
"""Tests for the ,codex-litellm loopback shim."""

from __future__ import annotations

import contextlib
import http.server
import importlib.util
import json
import socket
import subprocess
import sys
import threading
import time
import unittest
from importlib.machinery import SourceFileLoader
from urllib.request import Request, urlopen

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO

SHIM_MAIN = REPO / "home/exact_lib/exact_,codex-litellm/main.py"


def _load_shim():
    loader = SourceFileLoader("codex_litellm_shim", str(SHIM_MAIN))
    spec = importlib.util.spec_from_loader("codex_litellm_shim", loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RewriteResponsesBodyTests(unittest.TestCase):
    """Unit-test the pure body-rewrite: no HTTP, no forwarding."""

    def setUp(self) -> None:
        self.shim = _load_shim()

    def test_adds_drop_params_when_tool_choice_present(self) -> None:
        body = json.dumps({"model": "x", "tool_choice": "auto"}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        self.assertIs(out["drop_params"], True)

    def test_drop_params_idempotent_when_already_true(self) -> None:
        body = json.dumps({"tool_choice": "auto", "drop_params": True}).encode()
        self.assertEqual(self.shim._rewrite_responses_body(body), body)

    def test_removes_client_metadata_always(self) -> None:
        body = json.dumps({"model": "x", "client_metadata": {"a": "b"}}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        self.assertNotIn("client_metadata", out)

    def test_removes_reasoning_when_tools_present(self) -> None:
        body = json.dumps({"tools": [{"type": "function", "name": "f"}], "reasoning": {"effort": "medium"}}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        self.assertNotIn("reasoning", out)

    def test_keeps_reasoning_when_no_tools(self) -> None:
        body = json.dumps({"model": "x", "reasoning": {"effort": "medium"}}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        self.assertEqual(out["reasoning"], {"effort": "medium"})

    def test_clamps_xhigh_effort_to_default_high_ceiling(self) -> None:
        body = json.dumps({"model": "x", "reasoning": {"effort": "xhigh"}}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        self.assertEqual(out["reasoning"]["effort"], "high")

    def test_clamps_max_effort_to_default_high_ceiling(self) -> None:
        body = json.dumps({"model": "x", "reasoning": {"effort": "max"}}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        self.assertEqual(out["reasoning"]["effort"], "high")

    def test_preserves_xhigh_under_xhigh_ceiling(self) -> None:
        # gpt-5.2-codex accepts xhigh, so a ceiling of "xhigh" leaves it alone.
        body = json.dumps({"model": "x", "reasoning": {"effort": "xhigh"}}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body, None, "xhigh"))
        self.assertEqual(out["reasoning"]["effort"], "xhigh")

    def test_clamps_max_to_xhigh_ceiling(self) -> None:
        body = json.dumps({"model": "x", "reasoning": {"effort": "max"}}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body, None, "xhigh"))
        self.assertEqual(out["reasoning"]["effort"], "xhigh")

    def test_keeps_high_and_lower_efforts(self) -> None:
        for eff in ("none", "low", "medium", "high"):
            body = json.dumps({"model": "x", "reasoning": {"effort": eff}}).encode()
            out = json.loads(self.shim._rewrite_responses_body(body))
            self.assertEqual(out["reasoning"]["effort"], eff)

    def test_forces_verbosity_when_configured(self) -> None:
        body = json.dumps({"model": "x", "text": {"verbosity": "low"}}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body, None, "high", "medium"))
        self.assertEqual(out["text"]["verbosity"], "medium")

    def test_adds_text_verbosity_when_absent(self) -> None:
        body = json.dumps({"model": "x"}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body, None, "high", "medium"))
        self.assertEqual(out["text"]["verbosity"], "medium")

    def test_leaves_verbosity_untouched_when_not_configured(self) -> None:
        body = json.dumps({"model": "x", "text": {"verbosity": "low"}}).encode()
        out = self.shim._rewrite_responses_body(body)
        self.assertEqual(json.loads(out)["text"]["verbosity"], "low")
        self.assertEqual(out, body)

    def test_remaps_model_to_target(self) -> None:
        body = json.dumps({"model": "gpt-5.2-codex", "input": "hi"}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body, "llm-gateway/gpt-5.6-sol"))
        self.assertEqual(out["model"], "llm-gateway/gpt-5.6-sol")

    def test_no_model_remap_without_target(self) -> None:
        body = json.dumps({"model": "gpt-5.2-codex", "input": "hi"}).encode()
        self.assertEqual(self.shim._rewrite_responses_body(body), body)

    def test_coerces_custom_tool_to_function(self) -> None:
        body = json.dumps(
            {"tools": [{"type": "custom", "name": "apply_patch", "description": "d", "format": {}}]}
        ).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        tool = out["tools"][0]
        self.assertEqual(tool["type"], "function")
        self.assertEqual(tool["name"], "apply_patch")
        self.assertEqual(tool["parameters"]["properties"]["input"], {"type": "string"})
        self.assertEqual(tool["parameters"]["required"], ["input"])

    def test_drops_unbridgeable_tool_types(self) -> None:
        body = json.dumps(
            {
                "tools": [
                    {"type": "function", "name": "exec_command"},
                    {"type": "namespace", "name": "ns"},
                    {"type": "tool_search"},
                    {"type": "web_search"},
                ]
            }
        ).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        self.assertEqual([t["name"] for t in out["tools"]], ["exec_command"])

    def test_reorders_function_call_output_after_its_call(self) -> None:
        body = json.dumps(
            {
                "input": [
                    {"type": "message", "role": "user"},
                    {"type": "function_call", "call_id": "c1", "name": "f"},
                    {"type": "message", "role": "assistant"},
                    {"type": "function_call_output", "call_id": "c1", "output": "ok"},
                ]
            }
        ).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        kinds = [i.get("type") for i in out["input"]]
        self.assertEqual(kinds, ["message", "function_call", "function_call_output", "message"])

    def test_orphan_output_kept_at_end(self) -> None:
        body = json.dumps({"input": [{"type": "function_call_output", "call_id": "x", "output": "o"}]}).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        self.assertEqual(out["input"][0]["type"], "function_call_output")

    def test_synthesizes_output_for_unanswered_call(self) -> None:
        # An interrupted/rejected call with no matching output must still get a
        # tool response or the bridge 400s.
        body = json.dumps(
            {
                "input": [
                    {"type": "function_call", "call_id": "c1", "name": "f"},
                    {"type": "function_call", "call_id": "c2", "name": "f"},
                    {"type": "function_call_output", "call_id": "c1", "output": "ok"},
                ]
            }
        ).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        kinds = [(i.get("type"), i.get("call_id")) for i in out["input"]]
        self.assertEqual(
            kinds,
            [
                ("function_call", "c1"),
                ("function_call_output", "c1"),
                ("function_call", "c2"),
                ("function_call_output", "c2"),
            ],
        )
        synthetic = out["input"][3]
        self.assertEqual(synthetic["call_id"], "c2")
        self.assertIn("interrupted", synthetic["output"])

    def test_parallel_batch_with_one_unanswered_call(self) -> None:
        # Three parallel calls, an interleaved assistant message, only two
        # outputs: reorder pairs the two and synthesizes the third.
        body = json.dumps(
            {
                "input": [
                    {"type": "function_call", "call_id": "a", "name": "f"},
                    {"type": "function_call", "call_id": "b", "name": "f"},
                    {"type": "function_call", "call_id": "c", "name": "f"},
                    {"type": "message", "role": "assistant"},
                    {"type": "function_call_output", "call_id": "a", "output": "1"},
                    {"type": "function_call_output", "call_id": "c", "output": "3"},
                ]
            }
        ).encode()
        out = json.loads(self.shim._rewrite_responses_body(body))
        kinds = [(i.get("type"), i.get("call_id") or i.get("role")) for i in out["input"]]
        self.assertEqual(
            kinds,
            [
                ("function_call", "a"),
                ("function_call_output", "a"),
                ("function_call", "b"),
                ("function_call_output", "b"),
                ("function_call", "c"),
                ("function_call_output", "c"),
                ("message", "assistant"),
            ],
        )

    def test_noop_when_nothing_matches(self) -> None:
        body = json.dumps({"model": "x", "input": "hi"}).encode()
        self.assertEqual(self.shim._rewrite_responses_body(body), body)

    def test_noop_on_invalid_json(self) -> None:
        body = b"not json"
        self.assertIs(self.shim._rewrite_responses_body(body), body)

    def test_only_responses_path(self) -> None:
        self.assertTrue(self.shim._is_responses("/responses"))
        self.assertTrue(self.shim._is_responses("/v1/responses"))
        self.assertTrue(self.shim._is_responses("/v1/responses?foo=bar"))
        self.assertFalse(self.shim._is_responses("/v1/chat/completions"))
        self.assertFalse(self.shim._is_responses("/v1/models"))


class _CapturingUpstream(http.server.BaseHTTPRequestHandler):
    captured: list[dict[str, object]] = []
    response_body: bytes = b'{"id":"ok"}'
    response_status: int = 200
    response_chunked: bool = False
    response_chunks: list[bytes] | None = None
    first_chunk_sent: threading.Event | None = None
    release_chunks: threading.Event | None = None

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        type(self).captured.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization", ""),
                "content_type": self.headers.get("Content-Type", ""),
                "body_raw": body,
                "body_json": json.loads(body) if body else None,
            }
        )
        self.send_response(type(self).response_status)
        self.send_header("Content-Type", "application/json")
        if type(self).response_chunked:
            self.send_header("Transfer-Encoding", "chunked")
        else:
            self.send_header("Content-Length", str(len(type(self).response_body)))
        self.end_headers()
        if type(self).response_chunked:
            chunks = type(self).response_chunks or [type(self).response_body]
            for index, chunk in enumerate(chunks):
                self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                self.wfile.flush()
                if index == 0 and type(self).first_chunk_sent is not None:
                    type(self).first_chunk_sent.set()
                    assert type(self).release_chunks is not None
                    type(self).release_chunks.wait(timeout=5)
            self.wfile.write(b"0\r\n\r\n")
        else:
            self.wfile.write(type(self).response_body)

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"data":[]}')

    def log_message(self, *_args: object) -> None:  # silence access logging
        return


@contextlib.contextmanager
def _upstream():
    """Run a fake upstream on 127.0.0.1; yield (url, HandlerClass)."""

    class Handler(_CapturingUpstream):
        pass

    Handler.captured = []
    Handler.response_body = b'{"id":"ok"}'
    Handler.response_status = 200
    Handler.response_chunked = False
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", Handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@contextlib.contextmanager
def _shim(upstream_url: str, target_model: str | None = None):
    """Spawn the shim as a subprocess; yield its base URL. Cleans up on exit."""
    cmd = [sys.executable, str(SHIM_MAIN), upstream_url]
    if target_model is not None:
        cmd.append(target_model)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        port: int | None = None
        deadline = time.time() + 10.0
        while time.time() < deadline:
            line = proc.stdout.readline() if proc.stdout else ""
            if line.startswith("PORT="):
                port = int(line[len("PORT=") :].strip())
                break
            if proc.poll() is not None:
                raise RuntimeError(
                    f"shim exited early rc={proc.returncode} stderr={proc.stderr.read() if proc.stderr else ''}"
                )
        if port is None:
            raise RuntimeError("shim did not announce a port in time")
        # Confirm the port is actually accepting connections
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()


class ShimForwardingTests(unittest.TestCase):
    """End-to-end: spawn the shim, hit it, verify upstream saw the rewrite."""

    def test_injects_on_responses(self) -> None:
        with _upstream() as (upstream_url, handler), _shim(upstream_url, "llm-gateway/gpt-5.6-sol") as shim_url:
            payload = {
                "model": "gpt-5.2-codex",
                "tool_choice": "auto",
                "tools": [
                    {"type": "function", "name": "exec_command"},
                    {"type": "custom", "name": "apply_patch", "format": {}},
                    {"type": "web_search"},
                ],
                "reasoning": {"effort": "medium"},
                "client_metadata": {"a": "b"},
                "input": "hi",
            }
            req = Request(
                f"{shim_url}/v1/responses",
                data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer test", "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(json.loads(resp.read()), {"id": "ok"})
            self.assertEqual(len(handler.captured), 1)
            fwd = handler.captured[0]
            self.assertEqual(fwd["path"], "/v1/responses")
            self.assertEqual(fwd["authorization"], "Bearer test")
            body = fwd["body_json"]
            # model remapped to the gateway target.
            self.assertEqual(body["model"], "llm-gateway/gpt-5.6-sol")
            # drop_params added; client_metadata + reasoning (tools present) removed.
            self.assertIs(body["drop_params"], True)
            self.assertNotIn("client_metadata", body)
            self.assertNotIn("reasoning", body)
            # custom coerced to function, web_search dropped.
            self.assertEqual(
                [(t["type"], t["name"]) for t in body["tools"]],
                [("function", "exec_command"), ("function", "apply_patch")],
            )

    def test_passes_through_when_tool_choice_absent(self) -> None:
        with _upstream() as (upstream_url, handler), _shim(upstream_url) as shim_url:
            payload = {"model": "x", "input": "hi"}
            req = Request(
                f"{shim_url}/v1/responses",
                data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer test", "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
            fwd = handler.captured[0]
            self.assertNotIn("drop_params", fwd["body_json"])

    def test_forwards_non_responses_paths_verbatim(self) -> None:
        with _upstream() as (upstream_url, handler), _shim(upstream_url) as shim_url:
            payload = {"model": "x", "tool_choice": "auto", "messages": [{"role": "user", "content": "hi"}]}
            req = Request(
                f"{shim_url}/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer test", "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
            fwd = handler.captured[0]
            self.assertEqual(fwd["path"], "/v1/chat/completions")
            # Non-responses paths must not gain drop_params.
            self.assertNotIn("drop_params", fwd["body_json"])

    def test_forwards_upstream_error_status(self) -> None:
        with _upstream() as (upstream_url, handler), _shim(upstream_url) as shim_url:
            handler.response_status = 400
            handler.response_body = b'{"error":{"message":"bad"}}'
            payload = {"model": "x", "tool_choice": "auto", "input": "hi"}
            req = Request(
                f"{shim_url}/v1/responses",
                data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer test", "Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(Exception) as ctx:
                urlopen(req, timeout=5)
            # urlopen raises HTTPError on 4xx; confirm status matches upstream.
            self.assertEqual(getattr(ctx.exception, "code", None), 400)

    def test_reframes_chunked_upstream_response(self) -> None:
        with _upstream() as (upstream_url, handler), _shim(upstream_url) as shim_url:
            handler.response_chunked = True
            payload = {"model": "x", "input": "hi"}
            req = Request(
                f"{shim_url}/v1/responses",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.headers.get("Transfer-Encoding"), "chunked")
                self.assertEqual(resp.read(), b'{"id":"ok"}')


if __name__ == "__main__":
    unittest.main()
