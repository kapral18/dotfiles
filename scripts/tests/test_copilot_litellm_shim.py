#!/usr/bin/env python3
"""Tests for the ,copilot-litellm loopback shim."""

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

SHIM_MAIN = REPO / "home/exact_lib/exact_,copilot-litellm/main.py"


def _load_shim():
    loader = SourceFileLoader("copilot_litellm_shim", str(SHIM_MAIN))
    spec = importlib.util.spec_from_loader("copilot_litellm_shim", loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InjectAllowedParamsTests(unittest.TestCase):
    """Unit-test the pure body-rewrite: no HTTP, no forwarding."""

    def setUp(self) -> None:
        self.shim = _load_shim()

    def test_adds_tool_choice_when_present(self) -> None:
        body = json.dumps({"model": "x", "tool_choice": "auto"}).encode()
        out = json.loads(self.shim._inject_allowed_params(body))
        self.assertEqual(out["allowed_openai_params"], ["tool_choice"])

    def test_appends_when_list_missing_tool_choice(self) -> None:
        body = json.dumps({"tool_choice": "auto", "allowed_openai_params": ["other"]}).encode()
        out = json.loads(self.shim._inject_allowed_params(body))
        self.assertEqual(out["allowed_openai_params"], ["other", "tool_choice"])

    def test_leaves_list_alone_when_already_present(self) -> None:
        body = json.dumps({"tool_choice": "auto", "allowed_openai_params": ["tool_choice"]}).encode()
        out = json.loads(self.shim._inject_allowed_params(body))
        self.assertEqual(out["allowed_openai_params"], ["tool_choice"])

    def test_noop_when_tool_choice_absent(self) -> None:
        body = json.dumps({"model": "x"}).encode()
        self.assertEqual(self.shim._inject_allowed_params(body), body)

    def test_noop_on_invalid_json(self) -> None:
        body = b"not json"
        self.assertIs(self.shim._inject_allowed_params(body), body)

    def test_only_chat_completions_path(self) -> None:
        self.assertTrue(self.shim._is_chat_completions("/chat/completions"))
        self.assertTrue(self.shim._is_chat_completions("/v1/chat/completions"))
        self.assertTrue(self.shim._is_chat_completions("/v1/chat/completions?foo=bar"))
        self.assertFalse(self.shim._is_chat_completions("/v1/messages"))
        self.assertFalse(self.shim._is_chat_completions("/v1/models"))


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
def _shim(upstream_url: str):
    """Spawn the shim as a subprocess; yield its base URL. Cleans up on exit."""
    proc = subprocess.Popen(
        [sys.executable, str(SHIM_MAIN), upstream_url],
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

    def test_injects_on_chat_completions(self) -> None:
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
                self.assertEqual(json.loads(resp.read()), {"id": "ok"})
            self.assertEqual(len(handler.captured), 1)
            fwd = handler.captured[0]
            self.assertEqual(fwd["path"], "/v1/chat/completions")
            self.assertEqual(fwd["authorization"], "Bearer test")
            self.assertEqual(fwd["body_json"]["allowed_openai_params"], ["tool_choice"])

    def test_passes_through_when_tool_choice_absent(self) -> None:
        with _upstream() as (upstream_url, handler), _shim(upstream_url) as shim_url:
            payload = {"model": "x", "messages": [{"role": "user", "content": "hi"}]}
            body = json.dumps(payload).encode()
            req = Request(
                f"{shim_url}/v1/chat/completions",
                data=body,
                headers={"Authorization": "Bearer test", "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
            fwd = handler.captured[0]
            self.assertNotIn("allowed_openai_params", fwd["body_json"])

    def test_forwards_non_chat_paths_verbatim(self) -> None:
        with _upstream() as (upstream_url, handler), _shim(upstream_url) as shim_url:
            payload = {"model": "x", "tool_choice": "auto", "input": "hi"}
            req = Request(
                f"{shim_url}/v1/responses",
                data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer test", "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
            fwd = handler.captured[0]
            self.assertEqual(fwd["path"], "/v1/responses")
            # Non-chat paths must not gain allowed_openai_params.
            self.assertNotIn("allowed_openai_params", fwd["body_json"])

    def test_forwards_upstream_error_status(self) -> None:
        with _upstream() as (upstream_url, handler), _shim(upstream_url) as shim_url:
            handler.response_status = 400
            handler.response_body = b'{"error":{"message":"bad"}}'
            payload = {"model": "x", "tool_choice": "auto"}
            req = Request(
                f"{shim_url}/v1/chat/completions",
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
            payload = {"model": "x", "messages": [{"role": "user", "content": "hi"}]}
            req = Request(
                f"{shim_url}/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.headers.get("Transfer-Encoding"), "chunked")
                self.assertEqual(resp.read(), b'{"id":"ok"}')


if __name__ == "__main__":
    unittest.main()
