#!/usr/bin/env python3
"""Serve Cursor metadata and transparently proxy one llama.cpp Cursor child."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from shim import cursor_model_rows

RESERVE_OUTPUT_TOKENS = 32_000
MAX_REQUEST_BYTES = 32 * 1024 * 1024
HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "content-length",
        "host",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


class ProxyError(RuntimeError):
    """The local metadata proxy cannot safely start."""


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def load_selected_budget(catalog_path: Path, model_id: str) -> dict[str, int]:
    """Read the deployed Codex catalog instead of inferring a machine profile."""
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProxyError(
            f"llama.cpp Cursor metadata catalog is missing: {catalog_path}; run chezmoi apply before launching"
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise ProxyError(f"llama.cpp Cursor metadata catalog is invalid: {catalog_path}") from error
    models = catalog.get("models") if isinstance(catalog, dict) else None
    selected = (
        next(
            (entry for entry in models if isinstance(entry, dict) and entry.get("slug") == model_id),
            None,
        )
        if isinstance(models, list)
        else None
    )
    if not isinstance(selected, dict):
        raise ProxyError(
            f"llama.cpp Cursor model {model_id!r} has no configured context in {catalog_path}; choose a deployed router model"
        )
    raw_context = _positive_int(selected.get("context_window"))
    if raw_context is None:
        raise ProxyError(f"llama.cpp Cursor model {model_id!r} has no positive context_window in {catalog_path}")
    reserved_context = raw_context - RESERVE_OUTPUT_TOKENS
    if reserved_context <= 0:
        raise ProxyError(
            f"llama.cpp Cursor model {model_id!r} context_window must exceed the {RESERVE_OUTPUT_TOKENS}-token output reserve"
        )
    existing_usable = _positive_int(selected.get("auto_compact_token_limit"))
    return {
        "context_length": min(reserved_context, existing_usable) if existing_usable is not None else reserved_context,
        "max_output_tokens": min(RESERVE_OUTPUT_TOKENS, raw_context),
    }


class LlamaProxyServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], upstream: str, catalog: dict[str, dict[str, int]]) -> None:
        self.upstream = upstream.rstrip("/")
        self.catalog = catalog
        super().__init__(address, LlamaProxyHandler)


class LlamaProxyHandler(BaseHTTPRequestHandler):
    server: LlamaProxyServer
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:
        if urlsplit(self.path).path.rstrip("/") == "/v1/models":
            self._write_json({"data": cursor_model_rows(self.server.catalog)})
            return
        self._forward(None)

    def do_POST(self) -> None:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "invalid Content-Length")
            return
        if size < 0 or size > MAX_REQUEST_BYTES:
            self.send_error(413, "request too large")
            return
        self._forward(self.rfile.read(size))

    def _request_headers(self, body: bytes | None) -> dict[str, str]:
        headers = {name: value for name, value in self.headers.items() if name.lower() not in HOP_BY_HOP_HEADERS}
        if body is not None:
            headers["Content-Length"] = str(len(body))
        return headers

    def _forward(self, body: bytes | None) -> None:
        request = urllib.request.Request(
            self.server.upstream + self.path,
            data=body,
            headers=self._request_headers(body),
            method=self.command,
        )
        try:
            upstream = urllib.request.urlopen(request, timeout=300)
        except urllib.error.HTTPError as error:
            upstream = error
        except OSError:
            self.send_error(502, "llama.cpp upstream request failed")
            return
        try:
            self.send_response(getattr(upstream, "status", 502))
            for name, value in upstream.headers.items():
                if name.lower() not in HOP_BY_HOP_HEADERS:
                    self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()
            while chunk := upstream.read1(64 * 1024):
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            upstream.close()
            self.close_connection = True

    def _write_json(self, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args(argv: list[str]) -> tuple[str, Path, str, list[str]]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    options = parser.parse_args(argv)
    command = options.command[1:] if options.command[:1] == ["--"] else options.command
    if not command:
        parser.error("a Cursor child command is required after --")
    parsed = urlsplit(options.upstream)
    if parsed.scheme != "http" or not parsed.netloc or parsed.path not in {"", "/"}:
        parser.error("--upstream must be an http host and optional port")
    return options.upstream, options.catalog, options.model, command


def run(argv: list[str]) -> int:
    upstream, catalog_path, model_id, command = parse_args(argv)
    budget = load_selected_budget(catalog_path, model_id)
    server = LlamaProxyServer(("127.0.0.1", 0), upstream, {model_id: budget})
    thread = threading.Thread(target=server.serve_forever, name="cursor-llama-cpp-proxy", daemon=True)
    thread.start()
    child_env = dict(os.environ)
    child_env["CURSOR_LOCAL_AGENT_BASE_URL"] = f"http://127.0.0.1:{server.server_port}/v1"
    child = subprocess.Popen(command, env=child_env, start_new_session=True)

    def forward(signum: int, _frame: object) -> None:
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    previous = {signum: signal.signal(signum, forward) for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        returncode = child.wait()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return 128 - returncode if returncode < 0 else returncode


def main(argv: list[str]) -> int:
    try:
        return run(argv)
    except ProxyError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
