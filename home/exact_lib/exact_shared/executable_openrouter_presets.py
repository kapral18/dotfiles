#!/usr/bin/env python3
"""Ensure OpenRouter wrapper preflight state and resolve model context windows."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Optional

BASE_URL = "https://openrouter.ai/api/v1"
REQUEST_TIMEOUT_SECONDS = 15
CONTEXT_TIERS = {"short", "long"}


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


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _base_model_id(model_id: str) -> str:
    return model_id.split("@preset/", 1)[0]


def _model_catalog_entry(model_id: str, api_key: str) -> dict:
    model_id = _base_model_id(model_id)
    try:
        with _request("GET", "/models", api_key) as response:
            payload = _read_json_object(response, "GET", "/models")
    except urllib.error.HTTPError as error:
        raise PresetError(f"GET /models returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise PresetError(f"GET /models failed: {error.reason}") from error
    except OSError as error:
        raise PresetError("GET /models request failed") from error

    models = payload.get("data")
    if not isinstance(models, list):
        raise PresetError("GET /models returned an unexpected JSON shape")
    for model in models:
        if isinstance(model, dict) and model.get("id") == model_id:
            return model
    raise PresetError(f"OpenRouter model {model_id!r} was not found in /models")


def _endpoint_context_window(model_id: str, api_key: str) -> int | None:
    model_id = _base_model_id(model_id)
    endpoint_path = f"/models/{urllib.parse.quote(model_id, safe='/')}/endpoints"
    try:
        with _request("GET", endpoint_path, api_key) as response:
            payload = _read_json_object(response, "GET", endpoint_path)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise PresetError(f"GET {endpoint_path} returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise PresetError(f"GET {endpoint_path} failed: {error.reason}") from error
    except OSError as error:
        raise PresetError(f"GET {endpoint_path} request failed") from error

    data = payload.get("data")
    if not isinstance(data, dict):
        raise PresetError(f"GET {endpoint_path} returned an unexpected JSON shape")
    candidates = [_positive_int(data.get("context_length"))]
    top_provider = data.get("top_provider")
    if isinstance(top_provider, dict):
        candidates.append(_positive_int(top_provider.get("context_length")))
    endpoints = data.get("endpoints")
    if isinstance(endpoints, list):
        candidates.extend(
            _positive_int(endpoint.get("context_length")) for endpoint in endpoints if isinstance(endpoint, dict)
        )
    return max((candidate for candidate in candidates if candidate is not None), default=None)


@dataclass(frozen=True)
class ModelBudget:
    """A provider's paired context, completion, and usable-prompt limits."""

    context_limit: int
    max_output_tokens: int
    prompt_limit: int
    pricing_threshold: int | None = None


def _paired_capacity(source: dict) -> tuple[int, int] | None:
    context_limit = _positive_int(source.get("context_length"))
    max_output_tokens = _positive_int(source.get("max_completion_tokens"))
    if context_limit is None or max_output_tokens is None:
        return None
    return context_limit, max_output_tokens


def _endpoint_capacity(model_id: str, api_key: str) -> tuple[int, int] | None:
    model_id = _base_model_id(model_id)
    endpoint_path = f"/models/{urllib.parse.quote(model_id, safe='/')}/endpoints"
    try:
        with _request("GET", endpoint_path, api_key) as response:
            payload = _read_json_object(response, "GET", endpoint_path)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise PresetError(f"GET {endpoint_path} returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise PresetError(f"GET {endpoint_path} failed: {error.reason}") from error
    except OSError as error:
        raise PresetError(f"GET {endpoint_path} request failed") from error

    data = payload.get("data")
    if not isinstance(data, dict):
        raise PresetError(f"GET {endpoint_path} returned an unexpected JSON shape")
    top_provider = data.get("top_provider")
    if isinstance(top_provider, dict):
        capacity = _paired_capacity(top_provider)
        if capacity is not None:
            return capacity
    capacity = _paired_capacity(data)
    if capacity is not None:
        return capacity
    endpoints = data.get("endpoints")
    if isinstance(endpoints, list):
        for endpoint in endpoints:
            if isinstance(endpoint, dict):
                capacity = _paired_capacity(endpoint)
                if capacity is not None:
                    return capacity
    return None


def _pricing_threshold(model: dict) -> int | None:
    pricing = model.get("pricing")
    overrides = pricing.get("overrides") if isinstance(pricing, dict) else None
    thresholds = []
    if isinstance(overrides, list):
        for override in overrides:
            if isinstance(override, dict):
                threshold = _positive_int(override.get("min_prompt_tokens"))
                if threshold is not None:
                    thresholds.append(threshold)
    return min(thresholds, default=None)


def _capacity_for_model(model_id: str, model: dict, api_key: str) -> tuple[int, int]:
    """Resolve one capacity pair without mixing values from different providers."""

    catalog_capacity = _paired_capacity(model)
    top_provider = model.get("top_provider")
    top_capacity = _paired_capacity(top_provider) if isinstance(top_provider, dict) else None
    # OpenRouter selects the top provider for automatic routing. If it publishes a
    # different complete pair, that pair is the conservative executable capacity.
    capacity = top_capacity or catalog_capacity or _endpoint_capacity(model_id, api_key)
    if capacity is None:
        raise PresetError(
            f"OpenRouter model {_base_model_id(model_id)!r} must publish positive context_length and max_completion_tokens"
        )
    context_limit, max_output_tokens = capacity
    if max_output_tokens >= context_limit:
        raise PresetError(
            f"OpenRouter model {_base_model_id(model_id)!r} has max_completion_tokens "
            f"{max_output_tokens} outside context_length {context_limit}"
        )
    return capacity


def resolve_budget(model_id: str, tier: str, api_key: str) -> ModelBudget:
    """Return a paired, provider-backed budget for one OpenRouter model."""
    if tier not in CONTEXT_TIERS:
        raise PresetError(f"unsupported context tier {tier!r}; choose: short, long")
    if not api_key:
        raise PresetError("OPENROUTER_API_KEY must not be empty")

    model = _model_catalog_entry(model_id, api_key)
    context_limit, max_output_tokens = _capacity_for_model(model_id, model, api_key)
    long_prompt_limit = context_limit - max_output_tokens
    threshold = _pricing_threshold(model)
    if tier == "short" and threshold is not None:
        prompt_limit = min(long_prompt_limit, threshold - 1)
        if prompt_limit <= 0:
            raise PresetError(
                f"OpenRouter model {_base_model_id(model_id)!r} has min_prompt_tokens {threshold}, "
                "which leaves no positive short-tier prompt budget"
            )
    else:
        prompt_limit = long_prompt_limit
    return ModelBudget(context_limit, max_output_tokens, prompt_limit, threshold)


def resolve_context_window(model_id: str, tier: str, api_key: str) -> int:
    """Return the resolved prompt limit for older direct helper callers."""

    return resolve_budget(model_id, tier, api_key).prompt_limit


def resolve_session_budget(model_ids: list[str], tier: str, api_key: str) -> ModelBudget:
    """Use the smallest safe values for a process that can reach several models."""

    if not model_ids:
        raise PresetError("at least one OpenRouter model is required")
    budgets = [resolve_budget(model_id, tier, api_key) for model_id in dict.fromkeys(model_ids)]
    context_limit = min(budget.context_limit for budget in budgets)
    max_output_tokens = min(budget.max_output_tokens for budget in budgets)
    prompt_limit = min(budget.prompt_limit for budget in budgets)
    prompt_limit = min(prompt_limit, context_limit - max_output_tokens)
    if prompt_limit <= 0:
        raise PresetError("reachable OpenRouter models have no shared positive prompt budget")
    return ModelBudget(context_limit, max_output_tokens, prompt_limit)


def _codex_catalog(tier: str, model_ids: list[str], api_key: str) -> dict:
    models = []
    for model_id in dict.fromkeys(_base_model_id(model_id) for model_id in model_ids):
        budget = resolve_budget(model_id, tier, api_key)
        models.append(
            {
                "slug": model_id,
                "display_name": model_id,
                "description": "OpenRouter model with wrapper-resolved prompt capacity.",
                "supported_reasoning_levels": [],
                "shell_type": "shell_command",
                "visibility": "list",
                "supported_in_api": True,
                "priority": 1,
                "additional_speed_tiers": [],
                "availability_nux": None,
                "upgrade": None,
                "base_instructions": "You are a coding agent running in the Codex CLI.",
                "supports_reasoning_summaries": False,
                "default_reasoning_summary": "auto",
                "support_verbosity": True,
                "default_verbosity": "medium",
                "apply_patch_tool_type": "freeform",
                "web_search_tool_type": "text",
                "truncation_policy": {"mode": "tokens", "limit": 10000},
                "supports_parallel_tool_calls": True,
                "supports_image_detail_original": True,
                "context_window": budget.prompt_limit,
                "max_context_window": budget.prompt_limit,
                "auto_compact_token_limit": budget.prompt_limit * 9 // 10,
                "effective_context_window_percent": 100,
                "experimental_supported_tools": [],
                "input_modalities": ["text", "image"],
                "supports_search_tool": False,
            }
        )
    return {"models": models}


def _cursor_catalog(tier: str, wire_models: list[str], api_key: str) -> dict:
    return {
        wire_model: {
            "context_length": budget.prompt_limit,
            "max_output_tokens": budget.max_output_tokens,
        }
        for wire_model, budget in (
            (wire_model, resolve_budget(wire_model, tier, api_key)) for wire_model in dict.fromkeys(wire_models)
        )
    }


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "--context-window":
        try:
            print(resolve_context_window(argv[1], argv[2], os.environ.get("OPENROUTER_API_KEY", "").strip()))
        except PresetError as error:
            print(f"Error: OpenRouter context preflight failed: {error}", file=sys.stderr)
            return 1
        return 0
    if len(argv) >= 4 and argv[0] == "--session-budget-env":
        try:
            budget = resolve_session_budget(argv[2:], argv[1], os.environ.get("OPENROUTER_API_KEY", "").strip())
            for key, value in asdict(budget).items():
                if value is not None:
                    print(f"{key.upper()}={value}")
        except PresetError as error:
            print(f"Error: OpenRouter context preflight failed: {error}", file=sys.stderr)
            return 1
        return 0
    if len(argv) >= 4 and argv[0] == "--codex-model-catalog":
        try:
            print(json.dumps(_codex_catalog(argv[1], argv[2:], os.environ.get("OPENROUTER_API_KEY", "").strip())))
        except PresetError as error:
            print(f"Error: OpenRouter context preflight failed: {error}", file=sys.stderr)
            return 1
        return 0
    if len(argv) >= 4 and argv[0] == "--cursor-model-catalog":
        try:
            print(json.dumps(_cursor_catalog(argv[1], argv[2:], os.environ.get("OPENROUTER_API_KEY", "").strip())))
        except PresetError as error:
            print(f"Error: OpenRouter context preflight failed: {error}", file=sys.stderr)
            return 1
        return 0
    if len(argv) != 1:
        print(
            "Usage: openrouter_presets.py EFFORT | --context-window MODEL short|long | "
            "--session-budget-env short|long MODEL... | --codex-model-catalog short|long MODEL... | "
            "--cursor-model-catalog short|long WIRE_MODEL...",
            file=sys.stderr,
        )
        return 2

    try:
        ensure_preset(argv[0], os.environ.get("OPENROUTER_API_KEY", "").strip())
    except PresetError as error:
        print(f"Error: OpenRouter preset preflight failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
