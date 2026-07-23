"""Google Cloud project and bearer-token resolution."""

from __future__ import annotations

import os
import subprocess
import threading
import time

TOKEN_TTL_SECONDS = 45 * 60


def _run_gcloud(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["gcloud", *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as error:
        raise RuntimeError("gcloud is required for Vertex authentication") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("gcloud authentication command timed out") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or "gcloud command failed"
        raise RuntimeError(detail) from error
    value = completed.stdout.strip()
    if not value:
        raise RuntimeError("gcloud returned an empty value")
    return value


def resolve_project() -> str:
    """Resolve the active project without storing it in generated config."""

    project = (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
        or os.environ.get("VERTEX_PROJECT_ID")
    )
    if project:
        return project
    return _run_gcloud("config", "get-value", "project")


class TokenProvider:
    """Cache short-lived gcloud bearer tokens and support forced refresh."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token = ""
        self._expires_at = 0.0

    def get(self, *, refresh: bool = False) -> str:
        with self._lock:
            now = time.monotonic()
            if refresh or not self._token or now >= self._expires_at:
                self._token = _run_gcloud("auth", "print-access-token")
                self._expires_at = now + TOKEN_TTL_SECONDS
            return self._token
