#!/usr/bin/env python3
"""Loopback shim that injects `allowed_openai_params` for Copilot -> LiteLLM.

Copilot CLI's Background compaction sends `tool_choice` on every request. When
LiteLLM's Azure AI backend rejects it (400 UnsupportedParamsError), compaction
retries in a loop and the session becomes unusable. LiteLLM's own error
suggests the client-side escape hatch:

    send allowed_openai_params=['tool_choice'] in your request

Copilot's compiled binary exposes no extra-body knob, so we run a tiny local
HTTP forwarder that:

  - Listens on 127.0.0.1:<ephemeral>.
  - For /chat/completions (and /v1/chat/completions), parses the JSON body and
    merges `tool_choice` into `allowed_openai_params` when `tool_choice` is set
    but not already listed.
  - Forwards everything else verbatim.
  - Streams the upstream response through unchanged (SSE and non-SSE).

Run as `python3 main.py <upstream_base_url>`; prints `PORT=<n>` on stdout, then
serves until SIGTERM. The upstream base URL must NOT include `/v1` (the shim
preserves whatever path the client sends).
"""

from __future__ import annotations

import json
import signal
import ssl
import sys
import threading
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable
from urllib.parse import urlsplit

MAX_REQUEST_BYTES = 32 * 1024 * 1024
STREAM_CHUNK = 64 * 1024
# RFC 7230 §6.1 hop-by-hop headers. `content-length` is end-to-end; we only
# recompute it when we rewrite the body, which happens on request bodies (see
# `_forward`) but never on response bodies (streamed through unchanged).
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
)
# Additionally stripped when forwarding a request whose body we rewrote: the
# recomputed Content-Length is added by the caller after the strip.
REQUEST_LENGTH_HEADERS = frozenset({"content-length"})


def _is_chat_completions(path: str) -> bool:
    parsed = urlsplit(path)
    return parsed.path.rstrip("/").endswith("/chat/completions")


def _inject_allowed_params(body: bytes) -> bytes:
    """Add `tool_choice` to `allowed_openai_params` when the request sets it."""
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return body
    if not isinstance(payload, dict) or "tool_choice" not in payload:
        return body
    existing = payload.get("allowed_openai_params")
    if isinstance(existing, list):
        if "tool_choice" in existing:
            return body
        payload["allowed_openai_params"] = [*existing, "tool_choice"]
    else:
        payload["allowed_openai_params"] = ["tool_choice"]
    return json.dumps(payload, separators=(",", ":")).encode()


class ShimServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: object, client_address: object) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)

    def __init__(self, address: tuple[str, int], upstream: str) -> None:
        self.upstream = upstream.rstrip("/")
        super().__init__(address, ShimHandler)


class ShimHandler(BaseHTTPRequestHandler):
    server: ShimServer
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _forward(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_REQUEST_BYTES:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        body = self.rfile.read(length) if length > 0 else b""
        if body and _is_chat_completions(self.path):
            body = _inject_allowed_params(body)

        headers = {
            k: v
            for k, v in self.headers.items()
            if k.lower() not in HOP_BY_HOP and k.lower() not in REQUEST_LENGTH_HEADERS
        }
        if body:
            headers["Content-Length"] = str(len(body))

        url = f"{self.server.upstream}{self.path}"
        req = urllib.request.Request(url, data=body if body else None, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                self._pipe_response(resp)
        except urllib.error.HTTPError as exc:
            self._pipe_response(exc)
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionError) as exc:
            if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
                return
            payload = {"error": {"type": "upstream_unreachable", "message": str(exc)}}
            data = json.dumps(payload).encode()
            try:
                self.send_response(HTTPStatus.BAD_GATEWAY)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                return

    def _pipe_response(self, resp: object) -> None:
        status = resp.status if hasattr(resp, "status") else resp.code  # type: ignore[attr-defined]
        transfer_encoding = resp.headers.get("Transfer-Encoding", "")  # type: ignore[attr-defined]
        chunked = "chunked" in {value.strip().lower() for value in transfer_encoding.split(",")}
        content_length = resp.headers.get("Content-Length")  # type: ignore[attr-defined]
        try:
            self.send_response(status)
            for key, value in resp.headers.items():  # type: ignore[attr-defined]
                if key.lower() in HOP_BY_HOP or (chunked and key.lower() == "content-length"):
                    continue
                self.send_header(key, value)
            if chunked:
                self.send_header("Transfer-Encoding", "chunked")
            elif content_length is None:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            while True:
                chunk = resp.read1(STREAM_CHUNK)  # type: ignore[attr-defined]
                if not chunk:
                    break
                if chunked:
                    self.wfile.write(f"{len(chunk):X}\r\n".encode())
                    self.wfile.write(chunk)
                    self.wfile.write(b"\r\n")
                else:
                    self.wfile.write(chunk)
                self.wfile.flush()
            if chunked:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self) -> None:
        self._forward("GET")

    def do_POST(self) -> None:
        self._forward("POST")

    def do_PUT(self) -> None:
        self._forward("PUT")

    def do_DELETE(self) -> None:
        self._forward("DELETE")

    def do_PATCH(self) -> None:
        self._forward("PATCH")


def _run(upstream: str, ready_fh) -> None:
    server = ShimServer(("127.0.0.1", 0), upstream)
    port = server.server_address[1]
    print(f"PORT={port}", file=ready_fh, flush=True)

    def _shutdown(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main(argv: Iterable[str]) -> int:
    args = list(argv)
    if len(args) != 1:
        print("usage: main.py <upstream_base_url>", file=sys.stderr)
        return 2
    upstream = args[0]
    if not upstream.startswith(("http://", "https://")):
        print(f"error: upstream must be http(s) URL, got: {upstream}", file=sys.stderr)
        return 2
    _run(upstream, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
