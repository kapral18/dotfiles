"""Authenticated loopback HTTP server for the Vertex adapter."""

from __future__ import annotations

import hmac
import json
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from models import ModelRegistry, ModelSpec, codex_model_info
from protocols import parse_request, to_claude_payload, to_gemini_payload
from state import OpaqueContextStore
from streaming import (
    canonical_events,
    collect_response,
    render_anthropic,
    render_chat,
    render_json,
    render_responses,
)
from vertex import UpstreamError, VertexClient

MAX_REQUEST_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class AdapterContext:
    registry: ModelRegistry
    model: ModelSpec
    effort: str | None
    token: str
    vertex: VertexClient
    store: OpaqueContextStore


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
        return hmac.compare_digest(
            self.headers.get("Authorization", ""), f"Bearer {token}"
        ) or hmac.compare_digest(self.headers.get("x-api-key", ""), token)

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

    def _route(self) -> str | None:
        path = urlsplit(self.path).path.rstrip("/")
        return {
            "/v1/responses": "responses",
            "/v1/chat/completions": "chat",
            "/v1/messages": "anthropic",
        }.get(path)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path.rstrip("/")
        if path == "/healthz":
            self._json(HTTPStatus.OK, {"status": "ok"})
            return
        if not self._authorized():
            self._error("anthropic", HTTPStatus.UNAUTHORIZED, "authentication_error", "invalid adapter token")
            return
        if path == "/v1/models":
            if "client_version" in parse_qs(urlsplit(self.path).query):
                self._json(
                    HTTPStatus.OK,
                    {"models": [codex_model_info(model) for model in self.context.registry.values()]},
                )
                return
            self._json(
                HTTPStatus.OK,
                {"data": [self._model_info(model) for model in self.context.registry.values()]},
            )
            return
        if path.startswith("/v1/models/"):
            model_id = path.removeprefix("/v1/models/")
            try:
                model = self.context.registry.get(model_id)
            except ValueError as error:
                self._error("anthropic", HTTPStatus.NOT_FOUND, "not_found_error", str(error))
                return
            self._json(HTTPStatus.OK, self._model_info(model))
            return
        self._error("anthropic", HTTPStatus.NOT_FOUND, "not_found_error", "unknown adapter endpoint")

    @staticmethod
    def _model_info(model: ModelSpec) -> dict[str, Any]:
        effort = {level: {"supported": True} for level in model.efforts}
        return {
            "id": model.model_id,
            "type": "model",
            "display_name": model.model_id,
            "max_input_tokens": model.context_window,
            "max_tokens": model.max_output_tokens,
            "capabilities": {
                "thinking": {
                    "supported": True,
                    "types": {
                        "adaptive": {"supported": True},
                        "enabled": {"supported": model.backend == "gemini-chat"},
                    },
                },
                "effort": {"supported": True, **effort},
            },
        }

    def do_POST(self) -> None:
        path = urlsplit(self.path).path.rstrip("/")
        frontend = self._route()
        if not self._authorized():
            self._error(
                frontend or "anthropic", HTTPStatus.UNAUTHORIZED, "authentication_error", "invalid adapter token"
            )
            return
        if path == "/v1/messages/count_tokens":
            self._count_tokens()
            return
        if frontend is None:
            self._error("anthropic", HTTPStatus.NOT_FOUND, "not_found_error", "unknown adapter endpoint")
            return
        try:
            self._handle_completion(frontend)
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
            {"system": body.get("system"), "messages": body.get("messages"), "tools": body.get("tools")},
            separators=(",", ":"),
        )
        self._json(HTTPStatus.OK, {"input_tokens": max(1, len(serialized.encode("utf-8")) // 4)})

    def _handle_completion(self, frontend: str) -> None:
        body = self._read_body()
        conversation = parse_request(frontend, body)
        model = self.context.model
        if model.backend == "gemini-chat":
            payload = to_gemini_payload(conversation, model, self.context.effort, self.context.store)
        else:
            payload = to_claude_payload(conversation, model, self.context.effort, self.context.store)
        upstream = self.context.vertex.open(model, payload, stream=conversation.stream)
        try:
            events = canonical_events(
                model.backend,
                upstream,
                stream=conversation.stream,
                store=self.context.store,
            )
            if conversation.stream:
                self._stream(frontend, events, model, conversation.tool_kinds)
            else:
                result = collect_response(events)
                self._json(HTTPStatus.OK, render_json(frontend, result, model, conversation.tool_kinds))
        finally:
            upstream.close()

    def _stream(
        self,
        frontend: str,
        events: Any,
        model: ModelSpec,
        tool_kinds: dict[str, str],
    ) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        if frontend == "responses":
            output = render_responses(events, model, tool_kinds)
        elif frontend == "chat":
            output = render_chat(events, model)
        else:
            output = render_anthropic(events, model)
        try:
            for chunk in output:
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        finally:
            self.close_connection = True


def start_server(context: AdapterContext) -> tuple[AdapterServer, threading.Thread]:
    server = AdapterServer(("127.0.0.1", 0), context)
    thread = threading.Thread(target=server.serve_forever, name="vertex-adapter", daemon=True)
    thread.start()
    return server, thread
