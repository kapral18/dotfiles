#!/usr/bin/env python3
"""Loopback shim that makes Codex tool turns work through LiteLLM -> Azure AI.

Codex talks to LiteLLM over the Responses API (`wire_api="responses"`). Two
independent problems have to be solved for tool-using turns against the
gpt-5.x azure_ai deployments, which have no native Responses adapter (LiteLLM
bridges `/responses` down to chat-completions):

1. Codex only attaches its built-in tool set (exec_command, apply_patch, ...)
   when the `--model` slug resolves to a Codex-FAMILY model. The gateway slug
   `llm-gateway/gpt-5.6-sol` (and bare `gpt-5.6-sol`) attach ZERO tools, so the
   model reports "no shell tool available"; the slug `gpt-5.2-codex` attaches
   the full tool set even through a custom `model_provider`. So the wrapper
   launches Codex with a Codex-family client slug and this shim rewrites the
   `model` field on the wire to the real gateway target. (A `model_catalog_json`
   entry for the sol slug is NOT usable: any catalog entry makes Codex reset the
   provider to the built-in `openai` one and 400 with "not supported when using
   Codex with a ChatGPT account".)

2. The Codex-family tool set and turn shape break the azure_ai bridge unless
   rewritten. `_rewrite_responses_body` applies, all verified against the live
   gpt-5.x deployment:

   - `model` -> the configured gateway target (arg 2), so the family slug Codex
     needs for tools never reaches the gateway.
   - `drop_params: true` when `tool_choice` is present (LiteLLM otherwise 400s
     with UnsupportedParamsError; it forwards a real tool call anyway).
   - remove `client_metadata` (a Codex field azure_ai rejects, uncaught by
     `drop_params`).
   - remove `reasoning` when `tools` is present (bridged chat-completions
     rejects function tools + reasoning_effort together, even effort="none").
   - clamp `reasoning.effort` down to the per-model ceiling (arg 3) on the
     tool-free turns where `reasoning` survives. sol/terra/luna and gpt-5.2 cap
     at `high` and 400 above it; the native gpt-5.2-codex accepts `xhigh`.
     Codex's picker offers `xhigh`, so this keeps it usable everywhere.
   - force `text.verbosity` to the value in arg 4 when set. gpt-5.2-codex
     accepts only `medium` and 400s on Codex's default; the wrapper passes
     `medium` for that target and nothing (leave untouched) for the others.
   - coerce every `tools[]` entry of `type:"custom"` (the freeform apply_patch
     tool) into a `type:"function"` tool taking a single `input` string; the
     bridge 400s on `custom` tools, and the model still emits a proper
     `*** Begin Patch` payload in `input`.
   - drop `tools[]` entries whose `type` is not `function`/`custom`
     (`namespace`, `tool_search`, `web_search`); the bridge 400s with
     "Supported values are: 'function' and 'custom'".
   - reorder `input` so each `function_call_output` immediately follows its
     matching `function_call` (by `call_id`), and synthesize a stub output for
     any `function_call` that has none. Codex interleaves an assistant
     `message` between a call and its output (and between the calls/outputs of a
     parallel batch), and can leave a call unanswered when it is interrupted,
     rejected at an approval prompt, or the turn is aborted. Either detaches a
     `tool_call` from its response, 400ing with "An assistant message with
     'tool_calls' must be followed by tool messages responding to each
     'tool_call_id'".

Everything else is forwarded verbatim and the upstream response is streamed
through unchanged (SSE and non-SSE). Once the gateway gains a native Responses
adapter these rewrites become no-ops and reasoning-on-tool-turns returns.

Run as `python3 main.py <upstream_base_url> [<target_model>] [<effort_ceiling>]
[<verbosity>]`; prints `PORT=<n>` on stdout, then serves until SIGTERM. The
upstream base URL must NOT include `/v1` (the shim preserves whatever path the
client sends). When `<target_model>` is given, the shim rewrites the
`/responses` `model` field to it; otherwise the client's `model` is left
unchanged. `<effort_ceiling>` (default `high`) is the highest reasoning effort
the target accepts; higher efforts are clamped down to it. `<verbosity>`, when
given, forces `text.verbosity` (used only for gpt-5.2-codex, which requires
`medium`); when empty, `text` is left untouched.
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


def _is_responses(path: str) -> bool:
    parsed = urlsplit(path)
    return parsed.path.rstrip("/").endswith("/responses")


# Responses-API tool types the azure_ai chat-completions bridge accepts. Any
# other type (namespace, tool_search, web_search, ...) is dropped; `custom` is
# coerced to `function` rather than dropped so apply_patch survives.
_BRIDGE_SAFE_TOOL_TYPES = frozenset({"function"})
# Reasoning-effort scale, low to high. A request's effort is clamped down to the
# per-model ceiling passed on the command line (arg 3): the azure_ai deployments
# (sol/terra/luna, gpt-5.2) reject `xhigh`/`max` and cap at `high`, while the
# native Responses model gpt-5.2-codex accepts `xhigh`. `minimal` is dropped
# from the scale because those deployments reject it too; Codex does not emit it.
_EFFORT_ORDER = ("none", "low", "medium", "high", "xhigh", "max")
_DEFAULT_EFFORT_CEILING = "high"


def _clamp_effort(effort: str, ceiling: str) -> str:
    """Return `effort` capped at `ceiling` on the _EFFORT_ORDER scale.

    Unknown values (either side) are returned unchanged — the shim only rewrites
    what it recognizes, leaving anything novel for the gateway to accept/reject.
    """
    if effort not in _EFFORT_ORDER or ceiling not in _EFFORT_ORDER:
        return effort
    if _EFFORT_ORDER.index(effort) <= _EFFORT_ORDER.index(ceiling):
        return effort
    return ceiling


def _coerce_tool(tool: object) -> dict | None:
    """Return a bridge-safe tool, or None to drop it.

    `type:"function"` passes through. `type:"custom"` (Codex's freeform
    apply_patch tool) becomes a function taking one `input` string — the bridge
    400s on `custom`, and the model still emits a full `*** Begin Patch` payload
    in `input`. Every other type is dropped (the bridge only accepts
    function/custom, and custom is what we just rewrote away).
    """
    if not isinstance(tool, dict):
        return None
    tool_type = tool.get("type")
    if tool_type in _BRIDGE_SAFE_TOOL_TYPES:
        return tool
    if tool_type == "custom":
        return {
            "type": "function",
            "name": tool.get("name"),
            "description": tool.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": {"input": {"type": "string"}},
                "required": ["input"],
                "additionalProperties": False,
            },
        }
    return None


_UNANSWERED_CALL_OUTPUT = "[no output: tool call was interrupted or not completed]"


def _reorder_tool_outputs(items: list) -> list:
    """Place each `function_call_output` right after its `function_call`.

    The azure_ai bridge maps each `function_call` to an assistant `tool_calls`
    message that must be immediately followed by a `tool` message answering
    every `tool_call_id`. Two Codex behaviours violate that and 400 with
    "An assistant message with 'tool_calls' must be followed by tool messages":

    - Codex interleaves an assistant `message` (preamble/reasoning) between a
      call and its output, or between the calls and outputs of a parallel
      batch. Re-pairing each output next to its call by `call_id` restores the
      required adjacency.
    - A `function_call` can have NO matching output at all — the call was
      interrupted, rejected at an approval prompt, or the turn was aborted
      (common in interactive sessions and under the MDM approval policy). An
      unanswered `tool_call` fails the same check, so we synthesize a stub
      output for every call that lacks one.

    Outputs with no matching call are appended at the end, unchanged.
    """
    outputs: dict[object, list] = {}
    for item in items:
        if isinstance(item, dict) and item.get("type") == "function_call_output":
            outputs.setdefault(item.get("call_id"), []).append(item)

    result: list = []
    for item in items:
        if isinstance(item, dict) and item.get("type") == "function_call_output":
            continue  # emitted next to its call below
        result.append(item)
        if isinstance(item, dict) and item.get("type") == "function_call":
            call_id = item.get("call_id")
            matched = outputs.pop(call_id, [])
            if matched:
                result.extend(matched)
            else:
                result.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": _UNANSWERED_CALL_OUTPUT,
                    }
                )
    for orphan in outputs.values():
        result.extend(orphan)
    return result


def _rewrite_responses_body(
    body: bytes,
    target_model: str | None = None,
    effort_ceiling: str = _DEFAULT_EFFORT_CEILING,
    verbosity: str | None = None,
) -> bytes:
    """Make a Codex /responses body acceptable to LiteLLM's azure_ai bridge.

    See the module docstring for the full verified rationale. When `verbosity`
    is set, `text.verbosity` is forced to it (gpt-5.2-codex accepts only
    `medium` and 400s on Codex's default). Returns the original bytes unchanged
    when nothing needs rewriting.
    """
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return body
    if not isinstance(payload, dict):
        return body

    changed = False
    if target_model and payload.get("model") != target_model:
        payload["model"] = target_model
        changed = True
    if "tool_choice" in payload and not payload.get("drop_params"):
        payload["drop_params"] = True
        changed = True
    if "client_metadata" in payload:
        del payload["client_metadata"]
        changed = True
    if payload.get("tools") and "reasoning" in payload:
        del payload["reasoning"]
        changed = True
    reasoning = payload.get("reasoning")
    if isinstance(reasoning, dict) and isinstance(reasoning.get("effort"), str):
        # Clamp effort to the per-model ceiling so tool-free turns — the ones
        # where `reasoning` survives — do not 400 on an unsupported effort.
        # Codex's picker offers xhigh; this makes that selection usable on models
        # that cap at high, and preserves it on models that accept it.
        clamped = _clamp_effort(reasoning["effort"], effort_ceiling)
        if clamped != reasoning["effort"]:
            reasoning["effort"] = clamped
            changed = True
    if verbosity:
        # gpt-5.2-codex accepts only text.verbosity="medium" (400s on Codex's
        # default of low/none/high). Force it when the wrapper configures an
        # override for the target; other models leave `text` untouched.
        text = payload.get("text")
        if not isinstance(text, dict):
            text = {}
        if text.get("verbosity") != verbosity:
            text["verbosity"] = verbosity
            payload["text"] = text
            changed = True
    if isinstance(payload.get("tools"), list):
        coerced = [t for t in (_coerce_tool(t) for t in payload["tools"]) if t is not None]
        if coerced != payload["tools"]:
            payload["tools"] = coerced
            changed = True
    if isinstance(payload.get("input"), list):
        reordered = _reorder_tool_outputs(payload["input"])
        if reordered != payload["input"]:
            payload["input"] = reordered
            changed = True

    if not changed:
        return body
    return json.dumps(payload, separators=(",", ":")).encode()


class ShimServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: object, client_address: object) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)

    def __init__(
        self,
        address: tuple[str, int],
        upstream: str,
        target_model: str | None,
        effort_ceiling: str,
        verbosity: str | None,
    ) -> None:
        self.upstream = upstream.rstrip("/")
        self.target_model = target_model
        self.effort_ceiling = effort_ceiling
        self.verbosity = verbosity
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
        if body and _is_responses(self.path):
            body = _rewrite_responses_body(
                body,
                self.server.target_model,
                self.server.effort_ceiling,
                self.server.verbosity,
            )

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


def _run(
    upstream: str,
    ready_fh,
    target_model: str | None = None,
    effort_ceiling: str = _DEFAULT_EFFORT_CEILING,
    verbosity: str | None = None,
) -> None:
    server = ShimServer(("127.0.0.1", 0), upstream, target_model, effort_ceiling, verbosity)
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
    if not 1 <= len(args) <= 4:
        print(
            "usage: main.py <upstream_base_url> [<target_model>] [<effort_ceiling>] [<verbosity>]",
            file=sys.stderr,
        )
        return 2
    upstream = args[0]
    if not upstream.startswith(("http://", "https://")):
        print(f"error: upstream must be http(s) URL, got: {upstream}", file=sys.stderr)
        return 2
    target_model = args[1] if len(args) >= 2 and args[1] else None
    effort_ceiling = args[2] if len(args) >= 3 and args[2] else _DEFAULT_EFFORT_CEILING
    verbosity = args[3] if len(args) >= 4 and args[3] else None
    _run(upstream, sys.stdout, target_model, effort_ceiling, verbosity)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
