#!/usr/bin/env python3
"""stdio <-> streamable-HTTP MCP bridge with per-request bearer injection.

``,mcp-token <server> --bridge --url <url>`` runs this bridge. The agent
(Copilot, Codex) speaks newline-delimited JSON-RPC on stdio as if the bridge
were a local MCP server; every client message is forwarded as an HTTP POST to
the real streamable-HTTP endpoint with a **freshly selected** bearer token.
This decouples an agent session's lifetime from any single token's lifetime:
launch-time capture is gone, and rotation happens behind the seam whenever a
request finds the current token short, missing, or rejected.

Behavior, per client message:

- Requests are POSTed and answered. A ``application/json`` response body is
  emitted as one JSON-RPC message; a ``text/event-stream`` body is parsed as
  SSE and every ``data:`` event is emitted in order (progress notifications,
  server-initiated requests, then the response).
- Notifications and client responses are POSTed; their bodies are ignored.
- ``Mcp-Session-Id`` from the ``initialize`` response is captured and echoed
  on every subsequent request; stdin EOF sends a best-effort DELETE.
- A ``401``/``403`` re-acquires a token (rotating if the store can) and
  retries once, only when the retry would use a *different* token; the store
  deduplicates concurrent rejected workers so one refresh grant serves all.
- A ``404`` after a session was established re-plays the cached ``initialize``
  handshake (new session id, response suppressed) and retries once, so
  server-side session expiry never kills the agent session. Resurrection is
  single-flight: concurrent losers wait, observe the new session id, and
  retry instead of failing.
- When explicitly enabled by the registry, an Envoy ``503`` that states the
  upstream connection timed out before headers is retried once with the same
  token. This is opt-in because generic MCP tools may have side effects.
- Failures surface as JSON-RPC ``-32603`` errors for requests and are dropped
  for notifications; the bridge itself only exits on stdin EOF.

The bridge owns no token policy: it asks an injected ``acquire`` callable for
a send-ready token (passing the rejected token after an auth rejection) and
posts through an injected redirect-refusing opener, so the bearer is never
resent to another origin. Token selection, rotation, throttling, and ledger
rules stay in ``main.py``.
"""

from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import IO, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import OpenerDirector, Request

# Generous per-request ceiling: tool calls (semantic search, Slack queries) may
# legitimately run for minutes, while a hung socket must not pin a worker forever.
REQUEST_TIMEOUT_SECONDS = 600.0
DELETE_TIMEOUT_SECONDS = 5.0
# Concurrent in-flight client requests (agents issue parallel tool calls).
MAX_WORKERS = 8
JSONRPC_INTERNAL_ERROR = -32603
CONNECT_TIMEOUT_STATUS = 503
CONNECT_TIMEOUT_MARKERS = (
    "upstream connect error or disconnect/reset before headers",
    "reset reason: connection timeout",
)

AcquireToken = Callable[[Optional[str]], Optional[str]]


class Bridge:
    """One stdio session bridged onto one streamable-HTTP MCP endpoint."""

    def __init__(
        self,
        url: str,
        acquire: AcquireToken,
        opener: OpenerDirector,
        stdin: IO[bytes],
        stdout: IO[bytes],
        retry_connect_timeouts: bool = False,
    ) -> None:
        self._url = url
        self._acquire = acquire
        self._opener = opener
        self._stdin = stdin
        self._stdout = stdout
        self._retry_connect_timeouts = retry_connect_timeouts
        self._emit_lock = threading.Lock()
        self._session_lock = threading.Lock()
        # Serializes session resurrection: one worker replays the handshake
        # while concurrent losers wait, observe the new session id, and retry.
        self._resurrect_lock = threading.Lock()
        self._session_id: str | None = None
        self._initialize_message: dict | None = None

    def serve(self) -> int:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            for line in self._stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except ValueError:
                    print(",mcp-token bridge: dropping non-JSON stdin line.", file=sys.stderr)
                    continue
                if not isinstance(message, dict):
                    continue
                pool.submit(self._handle, message)
        self._close_session()
        return 0

    # -- client -> server ---------------------------------------------------

    def _handle(self, message: dict) -> None:
        is_request = "method" in message and "id" in message
        try:
            self._forward(message, emit=is_request)
        except Exception as exc:  # noqa: BLE001 - a worker must never die silently
            print(f",mcp-token bridge: {exc}", file=sys.stderr)
            if is_request:
                self._emit_error(message["id"], f"bridge request failed: {exc}")

    def _forward(self, message: dict, *, emit: bool) -> None:
        is_initialize = message.get("method") == "initialize"
        if is_initialize:
            with self._session_lock:
                self._initialize_message = message
        token = self._acquire(None)
        if token is None:
            raise RuntimeError("no valid token available")
        session_before = self._current_session()
        try:
            self._post(message, token, emit=emit)
            return
        except HTTPError as error:
            if self._retry_connect_timeouts and self._is_connect_timeout(error):
                try:
                    self._post(message, token, emit=emit)
                    return
                except HTTPError as retry_error:
                    error = retry_error
            retry_token = self._recovery_token(
                error,
                token,
                failed_session=session_before,
                allow_resurrect=not is_initialize,
            )
            if retry_token is None:
                raise RuntimeError(f"HTTP {error.code}") from error
        self._post(message, retry_token, emit=emit)

    @staticmethod
    def _is_connect_timeout(error: HTTPError) -> bool:
        if error.code != CONNECT_TIMEOUT_STATUS:
            return False
        try:
            body = error.read().decode("utf-8", errors="replace").lower()
        except OSError:
            return False
        return all(marker in body for marker in CONNECT_TIMEOUT_MARKERS)

    def _recovery_token(
        self,
        error: HTTPError,
        rejected: str,
        *,
        failed_session: str | None,
        allow_resurrect: bool,
    ) -> str | None:
        """Return a token to retry with after *error*, or ``None`` to give up.

        401/403 means the bearer died mid-session: re-acquire (the store
        rotates once for all concurrent rejected workers), and retry only
        when the store produced a different token. 404 after an established
        session means the server expired the session: ensure the cached
        ``initialize`` handshake was re-played (single-flight) and retry with
        a current token.
        """
        if error.code in (401, 403):
            fresh = self._acquire(rejected)
            if fresh is None or fresh == rejected:
                return None
            return fresh
        if error.code == 404 and allow_resurrect and self._resurrect(failed_session):
            return self._acquire(None)
        return None

    def _post(self, message: dict, token: str, *, emit: bool, sessionless: bool = False) -> None:
        request = Request(
            self._url,
            data=json.dumps(message).encode("utf-8"),
            method="POST",
            headers=self._headers(token, sessionless=sessionless),
        )
        with self._opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            self._capture_session_id(response.headers.get("Mcp-Session-Id"))
            if not emit:
                return
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if content_type == "text/event-stream":
                self._emit_sse(response)
            elif content_type == "application/json":
                body = response.read()
                if body.strip():
                    self._emit(json.loads(body))

    def _headers(self, token: str, *, sessionless: bool = False) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
        }
        with self._session_lock:
            if self._session_id and not sessionless:
                headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _current_session(self) -> str | None:
        with self._session_lock:
            return self._session_id

    def _capture_session_id(self, session_id: str | None) -> None:
        if session_id:
            with self._session_lock:
                self._session_id = session_id

    # -- session resurrection -----------------------------------------------

    def _resurrect(self, failed_session: str | None) -> bool:
        """Ensure the cached ``initialize`` handshake was re-played (single-flight).

        The client believes it is initialized, so the replayed handshake's
        response is suppressed; only the new ``Mcp-Session-Id`` is kept. The
        old session id stays in place until the replay's response overwrites
        it, so concurrent requests never post sessionless: they fail with 404,
        wait here for the winner, observe the changed session id, and retry.
        """
        with self._resurrect_lock:
            with self._session_lock:
                initialize = self._initialize_message
                current = self._session_id
            if initialize is None or current is None:
                return False
            if failed_session is not None and current != failed_session:
                # Another worker already resurrected while this one waited.
                return True
            token = self._acquire(None)
            if token is None:
                return False
            try:
                self._post(initialize, token, emit=False, sessionless=True)
                self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, token, emit=False)
            except (HTTPError, URLError, OSError, ValueError):
                return False
            with self._session_lock:
                return self._session_id is not None

    def _close_session(self) -> None:
        with self._session_lock:
            session_id = self._session_id
        if not session_id:
            return
        token = self._acquire(None)
        if token is None:
            return
        request = Request(self._url, method="DELETE", headers=self._headers(token))
        try:
            with self._opener.open(request, timeout=DELETE_TIMEOUT_SECONDS):
                pass
        except (HTTPError, URLError, OSError):
            pass

    # -- server -> client ---------------------------------------------------

    def _emit_sse(self, response: IO[bytes]) -> None:
        data_lines: list[str] = []
        for raw in response:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
                continue
            if line == "" and data_lines:
                self._emit_sse_event("\n".join(data_lines))
                data_lines = []
        if data_lines:
            self._emit_sse_event("\n".join(data_lines))

    def _emit_sse_event(self, data: str) -> None:
        try:
            message = json.loads(data)
        except ValueError:
            print(",mcp-token bridge: dropping non-JSON SSE event.", file=sys.stderr)
            return
        if isinstance(message, dict):
            self._emit(message)

    def _emit(self, message: dict) -> None:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        with self._emit_lock:
            self._stdout.write(payload)
            self._stdout.flush()

    def _emit_error(self, request_id: object, text: str) -> None:
        self._emit(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": JSONRPC_INTERNAL_ERROR, "message": text},
            }
        )


def run_bridge(
    url: str,
    acquire: AcquireToken,
    opener: OpenerDirector,
    *,
    retry_connect_timeouts: bool = False,
) -> int:
    bridge = Bridge(
        url,
        acquire,
        opener,
        sys.stdin.buffer,
        sys.stdout.buffer,
        retry_connect_timeouts=retry_connect_timeouts,
    )
    return bridge.serve()
