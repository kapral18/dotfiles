"""Owner-authenticated loopback gateway for the Codex subscription backend."""

from __future__ import annotations

import hmac
import json
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterable
from urllib.parse import urlsplit

from client import CodexClient, UpstreamError
from protocols import (
    aggregate_responses,
    anthropic_to_responses,
    collect_anthropic_message,
    encode_sse,
    iter_sse_json,
    prepare_responses_request,
    responses_to_anthropic_events,
)
from state import OpaqueReasoningStore

MAX_REQUEST_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class AdapterContext:
    model: str
    effort: str | None
    token: str
    codex: CodexClient
    store: OpaqueReasoningStore


class AdapterServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], context: AdapterContext) -> None:
        self.context = context
        super().__init__(address, AdapterHandler)


class AdapterHandler(BaseHTTPRequestHandler):
    server: AdapterServer
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    @property
    def context(self) -> AdapterContext:
        return self.server.context

    def _authorized(self) -> bool:
        token = self.context.token
        return hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}") or hmac.compare_digest(
            self.headers.get("x-api-key", ""), token
        )

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, frontend: str, status: int, error_type: str, message: str) -> None:
        if frontend == "anthropic":
            payload = {"type": "error", "error": {"type": error_type, "message": message}}
        else:
            payload = {
                "error": {
                    "type": error_type,
                    "message": message,
                    "param": None,
                    "code": None,
                }
            }
        self._json(status, payload)

    def _read_body(self) -> dict[str, Any]:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if size <= 0 or size > MAX_REQUEST_BYTES:
            raise ValueError("request body is empty or exceeds 16 MiB")
        try:
            payload = json.loads(self.rfile.read(size))
        except json.JSONDecodeError as error:
            raise ValueError("request body is not valid JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def do_GET(self) -> None:
        path = urlsplit(self.path).path.rstrip("/")
        if not self._authorized():
            self._error("anthropic", HTTPStatus.UNAUTHORIZED, "authentication_error", "invalid adapter token")
            return
        if path == "/healthz":
            self._json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/v1/models":
            self._json(
                HTTPStatus.OK,
                {
                    "data": [
                        {
                            "type": "model",
                            "id": self.context.model,
                            "display_name": self.context.model,
                            "created_at": "1970-01-01T00:00:00Z",
                        }
                    ],
                    "has_more": False,
                    "first_id": self.context.model,
                    "last_id": self.context.model,
                },
            )
            return
        self._error("anthropic", HTTPStatus.NOT_FOUND, "not_found_error", "unknown adapter endpoint")

    def do_POST(self) -> None:
        path = urlsplit(self.path).path.rstrip("/")
        frontend = "responses" if path == "/v1/responses" else "anthropic"
        if not self._authorized():
            self._error(frontend, HTTPStatus.UNAUTHORIZED, "authentication_error", "invalid adapter token")
            return
        if path == "/v1/messages/count_tokens":
            self._count_tokens()
            return
        if path not in {"/v1/responses", "/v1/messages"}:
            self._error(frontend, HTTPStatus.NOT_FOUND, "not_found_error", "unknown adapter endpoint")
            return
        try:
            body = self._read_body()
            if path == "/v1/responses":
                self._responses(body)
            else:
                self._anthropic(body)
        except ValueError as error:
            self._error(frontend, HTTPStatus.BAD_REQUEST, "invalid_request_error", str(error))
        except UpstreamError as error:
            self._error(frontend, error.status, error.error_type, error.message)
        except (OSError, RuntimeError) as error:
            self._error(frontend, HTTPStatus.BAD_GATEWAY, "api_error", str(error))

    def _count_tokens(self) -> None:
        try:
            body = self._read_body()
        except ValueError as error:
            self._error("anthropic", HTTPStatus.BAD_REQUEST, "invalid_request_error", str(error))
            return
        serialized = json.dumps(
            {
                "system": body.get("system"),
                "messages": body.get("messages"),
                "tools": body.get("tools"),
            },
            separators=(",", ":"),
        )
        self._json(
            HTTPStatus.OK,
            {"input_tokens": max(1, (len(serialized.encode("utf-8")) + 3) // 4)},
        )

    def _responses(self, body: dict[str, Any]) -> None:
        wants_stream = body.get("stream") is True
        payload = prepare_responses_request(
            body,
            model_override=self.context.model,
            effort_override=self.context.effort,
        )
        upstream = self.context.codex.open(payload)
        try:
            events = iter_sse_json(upstream)
            if wants_stream:
                self._stream_responses(events)
            else:
                self._json(HTTPStatus.OK, aggregate_responses(events))
        finally:
            upstream.close()

    def _anthropic(self, body: dict[str, Any]) -> None:
        wants_stream = body.get("stream") is True
        payload = anthropic_to_responses(
            body,
            model_override=self.context.model,
            effort_override=self.context.effort,
            store=self.context.store,
        )
        upstream = self.context.codex.open(payload)
        try:
            events = responses_to_anthropic_events(
                iter_sse_json(upstream),
                self.context.model,
                self.context.store,
            )
            if wants_stream:
                self._stream_anthropic(events)
            else:
                self._json(HTTPStatus.OK, collect_anthropic_message(events))
        finally:
            upstream.close()

    def _stream_headers(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def _write_stream(self, chunks: Iterable[bytes]) -> None:
        try:
            for chunk in chunks:
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        finally:
            self.close_connection = True

    def _stream_responses(self, events: Iterable[dict[str, Any]]) -> None:
        self._stream_headers()

        def chunks() -> Iterable[bytes]:
            try:
                for event in events:
                    yield encode_sse(event)
            except UpstreamError as error:
                yield encode_sse(
                    {
                        "type": "error",
                        "error": {"type": error.error_type, "message": error.message},
                    }
                )

        self._write_stream(chunks())

    def _stream_anthropic(self, events: Iterable[dict[str, Any]]) -> None:
        self._stream_headers()

        def chunks() -> Iterable[bytes]:
            try:
                for event in events:
                    yield encode_sse(event)
            except UpstreamError as error:
                yield encode_sse(
                    {
                        "type": "error",
                        "error": {"type": error.error_type, "message": error.message},
                    }
                )

        self._write_stream(chunks())


def start_server(context: AdapterContext) -> tuple[AdapterServer, threading.Thread]:
    server = AdapterServer(("127.0.0.1", 0), context)
    thread = threading.Thread(target=server.serve_forever, name="codex-adapter", daemon=True)
    thread.start()
    return server, thread
