"""Vertex HTTP transport with token refresh and bounded errors."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, BinaryIO

from auth import TokenProvider
from models import ModelSpec

MAX_ERROR_BYTES = 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 600


@dataclass
class UpstreamError(RuntimeError):
    status: int
    message: str
    error_type: str = "api_error"

    def __str__(self) -> str:
        return self.message


def _error_message(raw: bytes, fallback: str) -> str:
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except (TypeError, ValueError):
        return fallback
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    if isinstance(payload, dict) and isinstance(payload.get("message"), str):
        return payload["message"]
    return fallback


class VertexClient:
    """Issue Gemini and Anthropic publisher-model requests."""

    def __init__(self, project: str, tokens: TokenProvider) -> None:
        self.project = project
        self.tokens = tokens

    def _url(self, model: ModelSpec, stream: bool) -> str:
        project = urllib.parse.quote(self.project, safe="")
        if model.backend == "gemini-chat":
            return (
                "https://aiplatform.googleapis.com/v1beta1/"
                f"projects/{project}/locations/global/endpoints/openapi/chat/completions"
            )
        wire_model = urllib.parse.quote(model.wire_model, safe="")
        method = "streamRawPredict" if stream else "rawPredict"
        return (
            "https://aiplatform.googleapis.com/v1/"
            f"projects/{project}/locations/global/publishers/anthropic/models/"
            f"{wire_model}:{method}"
        )

    def open(
        self,
        model: ModelSpec,
        payload: dict[str, Any],
        *,
        stream: bool,
    ) -> BinaryIO:
        body = json.dumps(payload, separators=(",", ":")).encode()
        for attempt in range(2):
            request = urllib.request.Request(
                self._url(model, stream),
                data=body,
                headers={
                    "Accept": "text/event-stream" if stream else "application/json",
                    "Authorization": f"Bearer {self.tokens.get(refresh=attempt == 1)}",
                    "Content-Type": "application/json; charset=utf-8",
                    "X-Goog-User-Project": self.project,
                },
                method="POST",
            )
            try:
                return urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS)
            except urllib.error.HTTPError as error:
                raw = error.read(MAX_ERROR_BYTES)
                if error.code == 401 and attempt == 0:
                    continue
                error_type = {
                    400: "invalid_request_error",
                    401: "authentication_error",
                    403: "permission_error",
                    404: "not_found_error",
                    429: "rate_limit_error",
                    503: "overloaded_error",
                }.get(error.code, "api_error")
                raise UpstreamError(
                    error.code,
                    _error_message(raw, error.reason or f"Vertex HTTP {error.code}"),
                    error_type,
                ) from error
            except urllib.error.URLError as error:
                raise UpstreamError(502, f"cannot reach Vertex: {error.reason}") from error
        raise UpstreamError(401, "Vertex authentication failed", "authentication_error")
