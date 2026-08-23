#!/usr/bin/env python3
"""Ensure an effort preset exists in the active OpenRouter account."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

BASE_URL = "https://openrouter.ai/api/v1"
REQUEST_TIMEOUT_SECONDS = 15


class PresetError(RuntimeError):
    """Raised when preset preflight cannot establish the required state."""


class RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep the bearer on the configured OpenRouter origin."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


URL_OPENER = urllib.request.build_opener(RejectRedirectHandler())


def _request(method: str, path: str, api_key: str, body: Optional[dict] = None):
    encoded_body = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=encoded_body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    return URL_OPENER.open(request, timeout=REQUEST_TIMEOUT_SECONDS)


def _read_json_object(response, method: str, path: str) -> dict:
    try:
        payload = json.load(response)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise PresetError(f"{method} {path} returned invalid JSON") from error
    except OSError as error:
        raise PresetError(f"{method} {path} response read failed") from error
    if not isinstance(payload, dict):
        raise PresetError(f"{method} {path} returned an unexpected JSON shape")
    return payload


def _preset_exists(preset_path: str, expected_slug: str, api_key: str) -> bool:
    try:
        with _request("GET", preset_path, api_key) as response:
            payload = _read_json_object(response, "GET", preset_path)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise PresetError(f"GET {preset_path} returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise PresetError(f"GET {preset_path} failed: {error.reason}") from error
    except OSError as error:
        raise PresetError(f"GET {preset_path} request failed") from error

    data = payload.get("data")
    actual_slug = data.get("slug") if isinstance(data, dict) else None
    if actual_slug != expected_slug:
        raise PresetError(f"GET {preset_path} returned unexpected preset slug: {actual_slug!r}")
    return True


def ensure_preset(effort: str, api_key: str) -> None:
    """Create the account-local effort preset when its slug is absent."""
    if not effort:
        raise PresetError("reasoning effort must not be empty")
    if not api_key:
        raise PresetError("OPENROUTER_API_KEY must not be empty")

    slug = f"effort-{effort}"
    encoded_slug = urllib.parse.quote(slug, safe="")
    preset_path = f"/presets/{encoded_slug}"
    if _preset_exists(preset_path, slug, api_key):
        return

    expected_config = {"reasoning": {"effort": effort}}
    capture_path = f"{preset_path}/chat/completions"
    try:
        with _request("POST", capture_path, api_key, expected_config) as response:
            payload = _read_json_object(response, "POST", capture_path)
    except urllib.error.HTTPError as error:
        if error.code == 409 and _preset_exists(preset_path, slug, api_key):
            return
        raise PresetError(f"POST {capture_path} returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise PresetError(f"POST {capture_path} failed: {error.reason}") from error
    except OSError as error:
        raise PresetError(f"POST {capture_path} request failed") from error

    data = payload.get("data") if isinstance(payload, dict) else None
    designated_version = data.get("designated_version") if isinstance(data, dict) else None
    actual_config = designated_version.get("config") if isinstance(designated_version, dict) else None
    actual_reasoning = actual_config.get("reasoning") if isinstance(actual_config, dict) else None
    actual_effort = actual_reasoning.get("effort") if isinstance(actual_reasoning, dict) else None
    if actual_effort != effort:
        raise PresetError(f"POST {capture_path} returned unexpected reasoning effort: {actual_effort!r}")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: openrouter_presets.py EFFORT", file=sys.stderr)
        return 2

    try:
        ensure_preset(argv[0], os.environ.get("OPENROUTER_API_KEY", "").strip())
    except PresetError as error:
        print(f"Error: OpenRouter preset preflight failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
