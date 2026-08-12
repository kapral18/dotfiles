"""Authenticated loopback proxy for the GitHub Copilot subscription API."""

from __future__ import annotations

import hmac
import json
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from copilot_auth import (
    CLAUDE_EXTENDED_CONTEXT_SUFFIX,
    CopilotError,
    ModelSpec,
    TokenProvider,
    api_url,
    codex_model_info,
    upstream_headers,
)
from copilot_wire import ANTHROPIC, CHAT, RESPONSES, PreparedRequest, WireTranslator, backend_endpoint

MAX_REQUEST_BYTES = 32 * 1024 * 1024
STREAM_CHUNK = 64 * 1024
MODEL_FIELD = re.compile(rb'("model"\s*:\s*")(?P<model>[^"\\]+)(")')
UNSUPPORTED_ANTHROPIC_BETAS = frozenset({"advisor-tool-2026-03-01"})
REQUEST_HEADER_DENYLIST = frozenset(
    {
        "authorization",
        "connection",
        "content-length",
        "host",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "x-api-key",
    }
)
RESPONSE_HEADER_DENYLIST = frozenset(
    {
        "connection",
        "content-length",
        "keep-alive",
        "proxy-authenticate",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


@dataclass(frozen=True)
class AdapterContext:
    loopback_token: str
    tokens: TokenProvider
    models: dict[str, ModelSpec]
    translator: WireTranslator = field(default_factory=WireTranslator)


class AdapterServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: object, client_address: object) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)

    def __init__(self, address: tuple[str, int], context: AdapterContext) -> None:
        self.context = context
        super().__init__(address, AdapterHandler)


def _frontend_endpoint(path: str) -> str | None:
    route = urlsplit(path)
    normalized = route.path.rstrip("/")
    return {
        "/v1/messages": ANTHROPIC,
        "/v1/chat/completions": CHAT,
        "/v1/responses": RESPONSES,
    }.get(normalized)


def _upstream_path(endpoint: str, query: str = "") -> str:
    mapped = {
        ANTHROPIC: "/v1/messages",
        CHAT: "/chat/completions",
        RESPONSES: "/responses",
    }[endpoint]
    return mapped + (f"?{query}" if query else "")


def _filter_anthropic_betas(value: str) -> str:
    return ",".join(
        beta.strip() for beta in value.split(",") if beta.strip() and beta.strip() not in UNSUPPORTED_ANTHROPIC_BETAS
    )


def _strip_claude_context_suffix(body: bytes | None, models: dict[str, ModelSpec]) -> bytes | None:
    if body is None:
        return None
    match = MODEL_FIELD.search(body)
    if match is None:
        return body
    frontend_model = match.group("model").decode("ascii", errors="ignore")
    if not frontend_model.endswith(CLAUDE_EXTENDED_CONTEXT_SUFFIX):
        return body
    upstream_model = frontend_model[: -len(CLAUDE_EXTENDED_CONTEXT_SUFFIX)]
    if upstream_model not in models:
        return body
    return body[: match.start("model")] + upstream_model.encode() + body[match.end("model") :]


def _request_model(body: bytes, models: dict[str, ModelSpec]) -> ModelSpec:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("request body is not valid JSON") from error
    model_id = payload.get("model") if isinstance(payload, dict) else None
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("request body has no model")
    try:
        return models[model_id]
    except KeyError as error:
        raise ValueError(f"model {model_id!r} is not available through this Copilot subscription") from error


def _translation_error_event(frontend: str, message: str) -> bytes:
    error = {"type": "api_error", "message": message}
    if frontend == ANTHROPIC:
        payload = {"type": "error", "error": error}
    else:
        payload = {"type": "response.failed", "response": {"error": error}}
    event_type = payload["type"]
    data = json.dumps(payload, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data}\n\n".encode()


class AdapterHandler(BaseHTTPRequestHandler):
    server: AdapterServer
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    @property
    def context(self) -> AdapterContext:
        return self.server.context

    def _authorized(self) -> bool:
        expected = f"Bearer {self.context.loopback_token}"
        return hmac.compare_digest(self.headers.get("Authorization", ""), expected) or hmac.compare_digest(
            self.headers.get("x-api-key", ""), self.context.loopback_token
        )

    def _write_error(self, status: int, message: str) -> None:
        payload = json.dumps({"error": {"type": "api_error", "message": message}}, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _write_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> bytes | None:
        if self.command == "GET":
            return None
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if size <= 0 or size > MAX_REQUEST_BYTES:
            raise ValueError("request body is empty or exceeds 32 MiB")
        return self.rfile.read(size)

    def _headers(self, token: str, body: bytes | None, backend: str) -> dict[str, str]:
        headers = upstream_headers(token)
        for name, value in self.headers.items():
            lowered = name.lower()
            if lowered in REQUEST_HEADER_DENYLIST:
                continue
            if lowered == "anthropic-beta":
                if backend != ANTHROPIC:
                    continue
                value = _filter_anthropic_betas(value)
                if not value:
                    continue
            headers[name] = value
        if body is not None:
            headers["Content-Length"] = str(len(body))
        return headers

    def _open(self, upstream_path: str, body: bytes | None, backend: str) -> Iterable[bytes]:
        for refresh in (False, True):
            token = self.context.tokens.get(refresh=refresh)
            request = urllib.request.Request(
                f"{api_url()}{upstream_path}",
                data=body,
                headers=self._headers(token, body, backend),
                method=self.command,
            )
            try:
                return urllib.request.urlopen(request, timeout=300)
            except urllib.error.HTTPError as error:
                if error.code == HTTPStatus.UNAUTHORIZED and not refresh:
                    error.close()
                    continue
                return error
        raise CopilotError("Copilot authentication retry failed")

    def _pipe_upstream(self, upstream: Iterable[bytes]) -> None:
        try:
            status = getattr(upstream, "status", HTTPStatus.BAD_GATEWAY)
            self.send_response(status)
            for name, value in upstream.headers.items():
                if name.lower() not in RESPONSE_HEADER_DENYLIST:
                    self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()
            while chunk := upstream.read(STREAM_CHUNK):
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        finally:
            upstream.close()
            self.close_connection = True

    def _write_translation(
        self,
        upstream: Iterable[bytes],
        frontend: str,
        backend: str,
        model: ModelSpec,
        prepared: PreparedRequest,
    ) -> None:
        status = getattr(upstream, "status", HTTPStatus.BAD_GATEWAY)
        if status >= HTTPStatus.BAD_REQUEST:
            self._pipe_upstream(upstream)
            return
        try:
            output = self.context.translator.render(frontend, backend, upstream, model, prepared)
            self.send_response(HTTPStatus.OK)
            if isinstance(output, bytes):
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(output)))
                self.end_headers()
                self.wfile.write(output)
            else:
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    for chunk in output:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
                except (CopilotError, OSError, RuntimeError, ValueError) as error:
                    self.wfile.write(_translation_error_event(frontend, str(error)))
                    self.wfile.flush()
                self.close_connection = True
        except (BrokenPipeError, ConnectionResetError):
            return
        finally:
            upstream.close()

    def _count_tokens(self, body: bytes) -> None:
        payload = json.loads(body)
        serialized = json.dumps(
            {
                "system": payload.get("system"),
                "messages": payload.get("messages"),
                "tools": payload.get("tools"),
            },
            separators=(",", ":"),
        )
        self._write_json(HTTPStatus.OK, {"input_tokens": max(1, (len(serialized.encode()) + 3) // 4)})

    def _forward(self) -> None:
        if not self._authorized():
            self._write_error(HTTPStatus.UNAUTHORIZED, "invalid adapter token")
            return
        route = urlsplit(self.path)
        is_count_tokens = route.path.rstrip("/") == "/v1/messages/count_tokens"
        frontend = ANTHROPIC if is_count_tokens else _frontend_endpoint(self.path)
        if frontend is None:
            self._write_error(HTTPStatus.NOT_FOUND, "unknown adapter endpoint")
            return
        try:
            body = self._body()
            if body is None:
                raise ValueError("request body is empty")
            if frontend == ANTHROPIC:
                body = _strip_claude_context_suffix(body, self.context.models)
            model = _request_model(body, self.context.models)
            if is_count_tokens:
                if ANTHROPIC not in model.endpoints:
                    self._count_tokens(body)
                    return
                count_path = "/v1/messages/count_tokens" + (f"?{route.query}" if route.query else "")
                upstream = self._open(count_path, body, ANTHROPIC)
                self._pipe_upstream(upstream)
                return
            backend = backend_endpoint(frontend, model)
            if frontend == backend:
                query = route.query if frontend == ANTHROPIC else ""
                upstream = self._open(_upstream_path(backend, query), body, backend)
                self._pipe_upstream(upstream)
                return
            prepared = self.context.translator.prepare(frontend, backend, body, model)
            upstream = self._open(_upstream_path(backend), prepared.body, backend)
            self._write_translation(upstream, frontend, backend, model, prepared)
        except (CopilotError, OSError, RuntimeError, ValueError) as error:
            self._write_error(HTTPStatus.BAD_GATEWAY, str(error))

    def do_GET(self) -> None:
        if not self._authorized():
            self._write_error(HTTPStatus.UNAUTHORIZED, "invalid adapter token")
            return
        if urlsplit(self.path).path.rstrip("/") == "/v1/models":
            models = [codex_model_info(model) for model in self.context.models.values()]
            self._write_json(HTTPStatus.OK, {"models": models})
            return
        self._forward()

    do_POST = _forward


def start_server(context: AdapterContext) -> tuple[AdapterServer, object]:
    import threading

    server = AdapterServer(("127.0.0.1", 0), context)
    thread = threading.Thread(target=server.serve_forever, name="copilot-adapter", daemon=True)
    thread.start()
    return server, thread
