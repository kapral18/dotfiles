#!/usr/bin/env python3
"""Session guardrail + strict-mode proxy for cursor-agent-local on OpenRouter.

Three duties, all enforced at the wire:

1. Model allowlist. The launcher pins one or more wire models
   for the whole session and exports it as ``CURSOR_AGENT_ALLOWED_MODEL``.
   cursor-agent-local sends ``model: this.modelId`` on every
   ``/chat/completions`` request, and subagent model resolution runs before
   that body is built, so a request whose ``model`` differs from the pin means
   a delegated agent broke out of the band — a profile's ``model`` /
   ``agent_model``, a resume of a different model, or a caller-supplied
   ``Task.model``. The shim answers 403 before the request reaches OpenRouter,
   so no costly model (e.g. a Claude-family id) is ever billed.

2. Strict-mode fix. cursor-agent-local's reasoning-model predicate is
   ``modelId.startsWith("o")``, so ``openai/*`` ids get ``strict: true`` tool
   schemas. OpenAI/Azure strict validation rejects schemas whose ``required``
   arrays omit an optional property (Cursor's bundled Shell tool declares
   ``debounce_ms`` optional but omits it from ``required``), so those ids fail
   with ``LocalProviderError: Provider returned error`` before a single token
   is produced. The shim strips the ``strict`` field from each tool object.

3. Inbound tool-name adapter. Some OpenRouter models (live: inclusionai/ling-3.0-flash)
   emit Claude-style ``Bash`` tool calls. cursor-agent-local's available set has
   ``Shell``, not ``Bash``; ``AI_NoSuchToolError`` is classified as a transport
   error and the TUI shows reconnecting. The shim rewrites ``Bash`` to ``Shell``
   on JSON and SSE ``/chat/completions`` responses. Shell already accepts
   Claude Bash's ``command``, ``timeout``, and ``description`` fields, so the
   name is the only mapping. Outbound tool lists stay Cursor-native so DeepSeek
   and other well-behaved models keep seeing ``Shell``.

The shim is a loopback HTTP proxy between the CLI and OpenRouter. It forwards
every request untouched except on ``POST /api/v1/chat/completions``: the pinned
model is enforced before forwarding, ``strict`` is removed from tool objects,
and inbound tool names are rewritten on the way back. DeepSeek/Kimi/GLM ids
never hit the strict bug, but the guardrail and the inbound rewrite still
apply to them, so the shim is always on for the pinned route; only the
wrap-level ``--no-shim`` (explicit direct OpenRouter route without a preset
family) runs without it.

Usage: shim.py <port>

Run rules (from `,cursor-openrouter`, which owns the process tree):

- Listens on 127.0.0.1 only. Its bearer is the real ``OPENROUTER_API_KEY``,
  so no other process may bind the port; the launcher picks a free port with
  an atomic bind.
- ``CURSOR_AGENT_ALLOWED_MODEL`` is the exact wire model id or comma-separated
  wire model allowlist accepted on ``/chat/completions``; when unset the
  guardrail is disabled (fail-open, so a stray env gap cannot wedge an
  interactive session).
- Upstream is ``https://openrouter.ai`` and the CLI is pointed at
  ``http://127.0.0.1:<port>/api/v1``, so path translation is a no-op.
- The key comes from the inherited ``OPENROUTER_API_KEY`` environment variable;
  it never appears in argv or logs.
- Children of the server inherit the launcher's stdio only for fatal errors;
  a ready-line is written to fd 3 when the port is listening, then the server
  runs detached from the launcher's lifetime (see the launcher for the shutdown
  contract).

Exit codes: 2 on bad usage, 1 if the upstream base URL is unreachable at
startup (fail fast; the harness would only surface a confusing local error).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

UPSTREAM = "https://openrouter.ai"
MAX_REQUEST_BYTES = 32 * 1024 * 1024
ALLOWED_MODEL_ENV = "CURSOR_AGENT_ALLOWED_MODEL"
INBOUND_TOOL_NAMES = {"Bash": "Shell"}
NO_TOOL_MODELS = {"stealth/ox-alpha", "stealth/ox-alpha:online"}
DISCOVERED_NO_TOOL_MODELS: set[str] = set()
_PIPE_ERRORS = (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)


def strip_tool_strict(tools: Any) -> None:
    """Remove the ``strict`` key from every tool object in place."""
    if not isinstance(tools, list):
        return
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function")
        if isinstance(fn, dict):
            fn.pop("strict", None)


def _base_model_id(model: str) -> str:
    return model.split("@preset/", 1)[0]


def _uses_no_tool_adapter(payload: dict[str, Any]) -> bool:
    model = payload.get("model")
    return isinstance(model, str) and _base_model_id(model) in NO_TOOL_MODELS | DISCOVERED_NO_TOOL_MODELS


def _has_tools(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("tools"), list) and bool(payload["tools"])


def _without_tools(payload: dict[str, Any]) -> dict[str, Any]:
    rewritten = dict(payload)
    rewritten.pop("tools", None)
    rewritten.pop("tool_choice", None)
    rewritten.pop("parallel_tool_calls", None)
    return rewritten


def rewrite_chat_completions(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a chat request with model-specific compatibility rewrites."""
    if _uses_no_tool_adapter(payload):
        return _without_tools(payload)
    if "tools" not in payload or not isinstance(payload.get("tools"), list):
        return payload
    tools = [dict(tool) for tool in payload["tools"]]
    for tool in tools:
        if isinstance(tool, dict) and isinstance(tool.get("function"), dict):
            tool["function"] = dict(tool["function"])
            tool["function"].pop("strict", None)
    rewritten = dict(payload)
    rewritten["tools"] = tools
    return rewritten


def _allowed_models(allowed: str) -> set[str]:
    return {part.strip() for part in allowed.split(",") if part.strip()}


def enforce_allowed_model(payload: dict[str, Any], allowed: str) -> str | None:
    """Return an error message when the request model is not one of the pinned ids.

    ``payload["model"]`` must equal one allowed id exactly. A bare provider
    model (no preset suffix) is rejected too: the launcher pins preset-suffixed
    wire ids, and only those ids carry their provider routing policy, so a bare
    id that happens to share the provider prefix is not an allowed session model.
    """
    model = payload.get("model")
    if not isinstance(model, str) or not model:
        return "missing model field"
    allowed_models = _allowed_models(allowed)
    if model not in allowed_models:
        return f"model {model!r} is not in the pinned session allowlist {sorted(allowed_models)!r}"
    return None


def _rewrite_tool_calls(calls: Any) -> None:
    if not isinstance(calls, list):
        return
    for call in calls:
        if not isinstance(call, dict):
            continue
        fn = call.get("function")
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if isinstance(name, str) and name in INBOUND_TOOL_NAMES:
            fn["name"] = INBOUND_TOOL_NAMES[name]


def rewrite_inbound_tool_names(payload: dict[str, Any]) -> dict[str, Any]:
    """Map Claude-style tool names in a chat completion to Cursor names."""
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return payload
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if isinstance(message, dict):
            _rewrite_tool_calls(message.get("tool_calls"))
        delta = choice.get("delta")
        if isinstance(delta, dict):
            _rewrite_tool_calls(delta.get("tool_calls"))
    return payload


def _rewrite_sse_line(line: bytes) -> bytes:
    if line.endswith(b"\r\n"):
        ending = b"\r\n"
        body = line[:-2]
    elif line.endswith(b"\n"):
        ending = b"\n"
        body = line[:-1]
    else:
        ending = b""
        body = line
    if not body.startswith(b"data:"):
        return line
    payload_bytes = body[5:]
    if payload_bytes.startswith(b" "):
        payload_bytes = payload_bytes[1:]
    if payload_bytes in (b"", b"[DONE]"):
        return line
    try:
        payload = json.loads(payload_bytes)
    except ValueError:
        return line
    if not isinstance(payload, dict):
        return line
    rewrite_inbound_tool_names(payload)
    return b"data: " + json.dumps(payload, separators=(",", ":")).encode() + ending


def rewrite_sse_chunk(buffer: bytes) -> tuple[bytes, bytes]:
    """Rewrite complete SSE lines; return (emittable, remainder)."""
    last_nl = buffer.rfind(b"\n")
    if last_nl < 0:
        return b"", buffer
    complete = buffer[: last_nl + 1]
    rest = buffer[last_nl + 1 :]
    out = bytearray()
    for line in complete.splitlines(keepends=True):
        out.extend(_rewrite_sse_line(line))
    return bytes(out), rest


def rewrite_json_response(raw: bytes) -> bytes:
    try:
        payload = json.loads(raw)
    except ValueError:
        return raw
    if not isinstance(payload, dict):
        return raw
    rewrite_inbound_tool_names(payload)
    return json.dumps(payload, separators=(",", ":")).encode()


def _content_has_text(content: Any) -> bool:
    if isinstance(content, str):
        return bool(content)
    if isinstance(content, list):
        return bool(content)
    return content is not None


def _message_has_assistant_payload(message: Any) -> bool:
    if not isinstance(message, dict):
        return False
    if _content_has_text(message.get("content")):
        return True
    return bool(message.get("tool_calls") or message.get("function_call"))


def response_has_assistant_payload(raw: bytes, *, is_sse: bool) -> bool:
    """Return whether a chat response contains content or tool calls Cursor can consume."""
    payloads: list[dict[str, Any]] = []
    if is_sse:
        for line in raw.splitlines():
            if not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data in (b"", b"[DONE]"):
                continue
            try:
                payload = json.loads(data)
            except ValueError:
                continue
            if isinstance(payload, dict):
                payloads.append(payload)
    else:
        try:
            payload = json.loads(raw)
        except ValueError:
            return True
        if isinstance(payload, dict):
            payloads.append(payload)
    for payload in payloads:
        choices = payload.get("choices")
        if not isinstance(choices, list):
            continue
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            if _message_has_assistant_payload(choice.get("message")) or _message_has_assistant_payload(
                choice.get("delta")
            ):
                return True
    return False


class ShimServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: object, client_address: object) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, _PIPE_ERRORS):
            return
        super().handle_error(request, client_address)


class ShimHandler(BaseHTTPRequestHandler):
    server: ShimServer
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # /api/v1/models
        self._forward(b"")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_REQUEST_BYTES:
            self.send_error(413, "request too large")
            return
        raw = self.rfile.read(length)
        retry_without_tools: bytes | None = None
        retry_model: str | None = None
        if self.path.endswith("/chat/completions") and raw:
            try:
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    self.send_error(400, "invalid JSON request body")
                    return
                allowed = ALLOWED_MODEL
                if allowed:
                    violation = enforce_allowed_model(payload, allowed)
                    if violation:
                        self.send_error(
                            403,
                            f"model guardrail: {violation} "
                            "(a subagent tried to run on a different model; the session is pinned "
                            "to the model selected at launch)",
                        )
                        return
                model = payload.get("model")
                if isinstance(model, str) and _has_tools(payload) and not _uses_no_tool_adapter(payload):
                    retry_without_tools = json.dumps(_without_tools(payload)).encode()
                    retry_model = _base_model_id(model)
                raw = json.dumps(rewrite_chat_completions(payload)).encode()
            except (ValueError, TypeError):
                self.send_error(400, "invalid JSON request body")
                return
        self._forward(raw, retry_without_tools=retry_without_tools, retry_model=retry_model)

    def _open_upstream(self, body: bytes) -> tuple[int, Any, Any] | None:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }
        request = urllib.request.Request(
            UPSTREAM + self.path,
            data=body or None,
            method=self.command,
            headers=headers,
        )
        try:
            upstream_response = urllib.request.urlopen(request, timeout=180)
            status = upstream_response.status
            resp_headers = upstream_response.headers
            resp_body = upstream_response
        except urllib.error.HTTPError as error:
            status = error.code
            resp_headers = error.headers
            resp_body = error
        except Exception:
            self.send_error(502, "upstream request failed")
            return None
        return status, resp_headers, resp_body

    def _forward(
        self, body: bytes, *, retry_without_tools: bytes | None = None, retry_model: str | None = None
    ) -> None:
        opened = self._open_upstream(body)
        if opened is None:
            return
        status, resp_headers, resp_body = opened
        is_chat = self.path.endswith("/chat/completions")
        content_type = resp_headers.get("Content-Type") or ""
        try:
            if is_chat and "text/event-stream" in content_type.lower():
                if retry_without_tools is not None:
                    self._write_rewritten_sse_with_retry(
                        status,
                        content_type,
                        resp_body,
                        retry_without_tools=retry_without_tools,
                        retry_model=retry_model,
                    )
                else:
                    self._write_rewritten_sse(status, content_type, resp_body)
            elif is_chat:
                if retry_without_tools is not None:
                    raw = resp_body.read()
                    rewritten = rewrite_json_response(raw)
                    if status == 200 and not response_has_assistant_payload(rewritten, is_sse=False):
                        if retry_model is not None:
                            DISCOVERED_NO_TOOL_MODELS.add(retry_model)
                        self._retry_without_tools(retry_without_tools)
                        return
                    self._write_json_bytes(status, content_type, rewritten)
                else:
                    self._write_rewritten_json(status, content_type, resp_body)
            else:
                self._write_passthrough(status, resp_headers, resp_body)
        finally:
            try:
                resp_body.close()
            except Exception:
                pass

    def _retry_without_tools(self, body: bytes) -> None:
        opened = self._open_upstream(body)
        if opened is None:
            return
        status, resp_headers, resp_body = opened
        content_type = resp_headers.get("Content-Type") or ""
        try:
            if self.path.endswith("/chat/completions") and "text/event-stream" in content_type.lower():
                self._write_rewritten_sse(status, content_type, resp_body)
            elif self.path.endswith("/chat/completions"):
                self._write_rewritten_json(status, content_type, resp_body)
            else:
                self._write_passthrough(status, resp_headers, resp_body)
        finally:
            try:
                resp_body.close()
            except Exception:
                pass

    def _write_rewritten_sse(self, status: int, content_type: str, resp_body: Any) -> None:
        self._send_sse_headers(status, content_type)
        self._stream_rewritten_sse_body(resp_body)

    def _write_rewritten_sse_with_retry(
        self,
        status: int,
        content_type: str,
        resp_body: Any,
        *,
        retry_without_tools: bytes,
        retry_model: str | None,
    ) -> None:
        if status != 200:
            self._write_rewritten_sse(status, content_type, resp_body)
            return
        pending = b""
        buffered = bytearray()
        try:
            while True:
                chunk = resp_body.read(65536)
                if not chunk:
                    if pending:
                        out, _ = rewrite_sse_chunk(pending + b"\n")
                        buffered.extend(out)
                    break
                out, pending = rewrite_sse_chunk(pending + chunk)
                buffered.extend(out)
                if response_has_assistant_payload(bytes(buffered), is_sse=True):
                    self._send_sse_headers(status, content_type)
                    if buffered:
                        self.wfile.write(buffered)
                    self._stream_rewritten_sse_body(resp_body, pending=pending)
                    return
            if response_has_assistant_payload(bytes(buffered), is_sse=True):
                self._write_sse_bytes(status, content_type, bytes(buffered))
                return
            if retry_model is not None:
                DISCOVERED_NO_TOOL_MODELS.add(retry_model)
            self._retry_without_tools(retry_without_tools)
        except _PIPE_ERRORS:
            pass

    def _send_sse_headers(self, status: int, content_type: str) -> None:
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.close_connection = True
        self.send_header("Connection", "close")
        self.end_headers()

    def _stream_rewritten_sse_body(self, resp_body: Any, *, pending: bytes = b"") -> None:
        try:
            while True:
                chunk = resp_body.read(65536)
                if not chunk:
                    if pending:
                        out, _ = rewrite_sse_chunk(pending + b"\n")
                        if out:
                            self.wfile.write(out)
                    break
                out, pending = rewrite_sse_chunk(pending + chunk)
                if out:
                    self.wfile.write(out)
        except _PIPE_ERRORS:
            pass

    def _read_rewritten_sse(self, resp_body: Any) -> bytes:
        rewritten = bytearray()
        pending = b""
        while True:
            chunk = resp_body.read(65536)
            if not chunk:
                if pending:
                    out, _ = rewrite_sse_chunk(pending + b"\n")
                    rewritten.extend(out)
                break
            out, pending = rewrite_sse_chunk(pending + chunk)
            rewritten.extend(out)
        return bytes(rewritten)

    def _write_sse_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.close_connection = True
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            if body:
                self.wfile.write(body)
        except _PIPE_ERRORS:
            pass

    def _write_rewritten_json(self, status: int, content_type: str, resp_body: Any) -> None:
        raw = resp_body.read()
        rewritten = rewrite_json_response(raw)
        self._write_json_bytes(status, content_type, rewritten)

    def _write_json_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except _PIPE_ERRORS:
            pass

    def _write_passthrough(self, status: int, resp_headers: Any, resp_body: Any) -> None:
        self.send_response(status)
        content_type = resp_headers.get("Content-Type")
        if content_type:
            self.send_header("Content-Type", content_type)
        content_length = resp_headers.get("Content-Length")
        if content_length is not None:
            self.send_header("Content-Length", content_length)
        else:
            self.close_connection = True
            self.send_header("Connection", "close")
        self.end_headers()
        try:
            while True:
                chunk = resp_body.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except _PIPE_ERRORS:
            pass


def _usage() -> str:
    return "Usage: shim.py <port>\n\nStarts the strict-mode shim on 127.0.0.1:<port>.\nAPI key is read from OPENROUTER_API_KEY."


def _probe_upstream() -> str | None:
    request = urllib.request.Request(UPSTREAM + "/api/v1/models", headers={"Authorization": f"Bearer {API_KEY}"})
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            response.read(1024)
    except Exception as error:
        return str(error)
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(_usage(), file=sys.stderr)
        return 2
    try:
        port = int(argv[0])
    except ValueError:
        print(_usage(), file=sys.stderr)
        return 2
    global API_KEY, ALLOWED_MODEL
    API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    if not API_KEY:
        print("Error: OPENROUTER_API_KEY is not set or empty", file=sys.stderr)
        return 2
    ALLOWED_MODEL = os.environ.get(ALLOWED_MODEL_ENV, "")

    upstream_error = _probe_upstream()
    if upstream_error:
        print(f"Error: cannot reach {UPSTREAM}: {upstream_error}", file=sys.stderr)
        return 1

    try:
        server = ShimServer(("127.0.0.1", port), ShimHandler)
    except OSError as error:
        print(f"Error: cannot bind 127.0.0.1:{port}: {error}", file=sys.stderr)
        return 1
    # fd 3 is the launcher's ready pipe; announce the actual bound port (which
    # differs from 0 when the launcher asked for an ephemeral port) then close
    # it so the launcher stops blocking and the harness starts.
    os.write(3, f"PORT={server.server_address[1]}\n".encode())
    os.close(3)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


API_KEY = ""
ALLOWED_MODEL = ""
if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
