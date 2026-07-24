"""Streaming client for the ChatGPT Codex Responses backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from http.client import HTTPResponse
from typing import Any, Callable

from auth import CodexAuth, Credentials

DEFAULT_BASE_URL = "https://chatgpt.com/backend-api/codex"


class UpstreamError(RuntimeError):
    def __init__(self, status: int, error_type: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.error_type = error_type
        self.message = message


def _error_from_http(error: urllib.error.HTTPError) -> UpstreamError:
    try:
        raw = error.read()
    except OSError:
        raw = b""
    message = error.reason or "Codex backend request failed"
    error_type = "api_error"
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = None
    if isinstance(payload, dict):
        detail = payload.get("error", payload)
        if isinstance(detail, dict):
            candidate = detail.get("message") or detail.get("detail")
            kind = detail.get("type") or detail.get("code")
            if isinstance(candidate, str) and candidate:
                message = candidate
            if isinstance(kind, str) and kind:
                error_type = kind
        elif isinstance(detail, str) and detail:
            message = detail
    return UpstreamError(error.code, error_type, str(message))


class CodexClient:
    """Open an upstream SSE response, refreshing once after HTTP 401."""

    def __init__(
        self,
        credentials: CodexAuth,
        *,
        base_url: str = DEFAULT_BASE_URL,
        opener: Callable[..., HTTPResponse] = urllib.request.urlopen,
        timeout: int = 300,
    ) -> None:
        self.credentials = credentials
        self.base_url = base_url.rstrip("/")
        self.opener = opener
        self.timeout = timeout

    def _request(self, payload: dict[str, Any], credentials: Credentials) -> urllib.request.Request:
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {credentials.access_token}",
            "Content-Type": "application/json",
            "User-Agent": "codex-subscription-adapter/1.0",
        }
        if credentials.account_id:
            headers["ChatGPT-Account-ID"] = credentials.account_id
        return urllib.request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers=headers,
            method="POST",
        )

    def open(self, payload: dict[str, Any]) -> HTTPResponse:
        credentials = self.credentials.get()
        for attempt in range(2):
            request = self._request(payload, credentials)
            try:
                return self.opener(request, timeout=self.timeout)
            except urllib.error.HTTPError as error:
                if error.code != 401 or attempt == 1:
                    raise _error_from_http(error) from error
                error.close()
                self.credentials.refresh()
                credentials = self.credentials.get()
            except urllib.error.URLError as error:
                raise UpstreamError(502, "api_error", f"Codex backend connection failed: {error.reason}") from error
        raise AssertionError("unreachable")
