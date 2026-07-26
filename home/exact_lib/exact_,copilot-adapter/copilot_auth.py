"""Resolve GitHub authentication and the live Copilot model catalog."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_API_URL = "https://api.githubcopilot.com"
INTEGRATION_ID = "copilot-developer-cli"
USER_AGENT = "copilot-subscription-adapter/1"
CONTEXT_TIERS = ("default", "long_context")
CLAUDE_EXTENDED_CONTEXT_SUFFIX = "[1m]"
CATALOG_SCRIPT = """
const {getAvailableModels} = await import(process.argv[1]);
const models = await getAvailableModels({
  type: "token",
  host: "https://github.com",
  token: process.env.COPILOT_ADAPTER_GITHUB_TOKEN,
});
process.stdout.write(JSON.stringify({data: models}));
"""


class CopilotError(RuntimeError):
    """An actionable GitHub Copilot authentication or protocol failure."""


class TokenProvider:
    """Read the active GitHub CLI token without persisting it."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._lock = threading.Lock()

    def get(self, *, refresh: bool = False) -> str:
        with self._lock:
            if self._token is not None and not refresh:
                return self._token
            try:
                result = subprocess.run(
                    ["gh", "auth", "token"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except FileNotFoundError as error:
                raise CopilotError("gh CLI is not installed") from error
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                raise CopilotError("GitHub authentication unavailable; run `gh auth login`") from error
            token = result.stdout.strip()
            if not token:
                raise CopilotError("gh returned an empty authentication token")
            self._token = token
            return token


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    endpoints: frozenset[str]
    efforts: frozenset[str]
    context_window: int
    max_output_tokens: int
    context_windows: dict[str, int]


def codex_model_info(model: ModelSpec) -> dict[str, object]:
    """Render one Responses-capable model using Codex's provider model schema."""

    efforts = sorted(model.efforts)
    default_effort = "medium" if "medium" in model.efforts else (efforts[0] if efforts else "none")
    return {
        "slug": model.model_id,
        "display_name": model.model_id,
        "description": "GitHub Copilot subscription model.",
        "default_reasoning_level": default_effort,
        "supported_reasoning_levels": [
            {"effort": effort, "description": f"{effort.capitalize()} reasoning effort"} for effort in efforts
        ],
        "shell_type": "shell_command",
        "visibility": "list",
        "supported_in_api": True,
        "priority": 1,
        "additional_speed_tiers": [],
        "service_tiers": [],
        "default_service_tier": None,
        "availability_nux": None,
        "upgrade": None,
        "base_instructions": (
            "You are a coding agent running in the Codex CLI, a terminal-based coding assistant. "
            "You are expected to be precise, safe, and helpful."
        ),
        "include_skills_usage_instructions": False,
        "supports_reasoning_summary_parameter": False,
        "default_reasoning_summary": "auto",
        "support_verbosity": True,
        "default_verbosity": "medium",
        "apply_patch_tool_type": "freeform",
        "web_search_tool_type": "text",
        "truncation_policy": {"mode": "tokens", "limit": 10_000},
        "supports_parallel_tool_calls": True,
        "supports_image_detail_original": True,
        "context_window": model.context_window,
        "max_context_window": model.context_window,
        "auto_compact_token_limit": model.context_window * 9 // 10,
        "effective_context_window_percent": 90,
        "experimental_supported_tools": [],
        "input_modalities": ["text", "image"],
        "supports_search_tool": False,
        "use_responses_lite": False,
    }


def api_url() -> str:
    return DEFAULT_API_URL


def upstream_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Copilot-Integration-Id": INTEGRATION_ID,
        "User-Agent": USER_AGENT,
    }


def _positive_int(value: Any, field: str, model_id: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CopilotError(f"Copilot model {model_id!r} has invalid {field}")
    return value


def _copilot_sdk_path() -> Path:
    binary = shutil.which("copilot")
    if binary is None:
        raise CopilotError("GitHub Copilot CLI is not installed")
    try:
        result = subprocess.run(
            [binary, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise CopilotError("GitHub Copilot CLI version is unavailable") from error
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", result.stdout)
    if match is None:
        raise CopilotError("GitHub Copilot CLI returned an invalid version")
    cache_root = Path.home() / "Library/Caches/copilot/pkg"
    candidates = sorted(cache_root.glob(f"*/{match.group(1)}/sdk/index.js"))
    if not candidates:
        raise CopilotError("GitHub Copilot CLI SDK is unavailable; run `copilot` once")
    return candidates[0]


def _node_path() -> str:
    candidates = [
        shutil.which("node"),
        "/opt/homebrew/opt/node@24/bin/node",
        *(
            str(path)
            for path in sorted(
                (Path.home() / ".local/share/mise/installs/node").glob("24*/bin/node"),
                reverse=True,
            )
        ),
    ]
    for candidate in candidates:
        if candidate is None or not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run(
                [candidate, "--version"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
        if result.stdout.startswith("v24."):
            return candidate
    raise CopilotError("Node.js 24 is required by the installed GitHub Copilot CLI SDK")


def _catalog_payload(token: str) -> object:
    env = dict(os.environ)
    env["COPILOT_ADAPTER_GITHUB_TOKEN"] = token
    try:
        result = subprocess.run(
            [
                _node_path(),
                "--input-type=module",
                "--eval",
                CATALOG_SCRIPT,
                _copilot_sdk_path().as_uri(),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip()[:500]
        raise CopilotError(f"Copilot model catalog failed: {detail or 'unknown SDK error'}") from error
    except (subprocess.TimeoutExpired, ValueError) as error:
        raise CopilotError(f"Copilot model catalog failed: {error}") from error


def parse_models(payload: object) -> dict[str, ModelSpec]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise CopilotError("Copilot /models returned an invalid catalog")
    models: dict[str, ModelSpec] = {}
    for item in payload["data"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        model_id = item["id"]
        capabilities = item.get("capabilities")
        limits = capabilities.get("limits") if isinstance(capabilities, dict) else None
        supports = capabilities.get("supports") if isinstance(capabilities, dict) else None
        if not isinstance(limits, dict) or capabilities.get("type") != "chat":
            continue
        endpoints = item.get("supported_endpoints")
        effort_values = supports.get("reasoning_effort", []) if isinstance(supports, dict) else []
        max_output_tokens = _positive_int(limits.get("max_output_tokens"), "output limit", model_id)
        max_context_window = _positive_int(limits.get("max_context_window_tokens"), "context limit", model_id)
        billing = item.get("billing")
        token_prices = billing.get("token_prices") if isinstance(billing, dict) else None
        context_windows: dict[str, int] = {}
        if isinstance(token_prices, dict):
            for tier in CONTEXT_TIERS:
                price = token_prices.get(tier)
                if not isinstance(price, dict) or not isinstance(price.get("max_prompt_tokens"), int):
                    continue
                prompt_tokens = _positive_int(price["max_prompt_tokens"], f"{tier} prompt limit", model_id)
                context_windows[tier] = min(max_context_window, prompt_tokens + max_output_tokens)
        if "default" not in context_windows:
            context_windows["default"] = max_context_window
        models[model_id] = ModelSpec(
            model_id=model_id,
            endpoints=frozenset(value for value in endpoints or [] if isinstance(value, str)),
            efforts=frozenset(value for value in effort_values if isinstance(value, str)),
            context_window=context_windows["default"],
            max_output_tokens=max_output_tokens,
            context_windows=context_windows,
        )
    if not models:
        raise CopilotError("Copilot /models returned no usable models")
    return models


def fetch_models(tokens: TokenProvider) -> dict[str, ModelSpec]:
    return parse_models(_catalog_payload(tokens.get()))
