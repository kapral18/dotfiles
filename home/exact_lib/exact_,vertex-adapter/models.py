"""Vertex adapter model registry loading and reasoning validation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path("~/.config/vertex-adapter/models.json")


@dataclass(frozen=True)
class ModelSpec:
    """One curated Vertex model and its transport capabilities."""

    model_id: str
    backend: str
    wire_model: str
    efforts: tuple[str, ...]
    default_effort: str
    thinking_default: str
    supports_no_thinking: bool
    adapter_default: bool
    context_window: int
    max_output_tokens: int

    @classmethod
    def from_entry(cls, entry: dict[str, object]) -> "ModelSpec":
        efforts = tuple(part for part in str(entry.get("efforts", "")).split(",") if part)
        return cls(
            model_id=str(entry["id"]),
            backend=str(entry["backend"]),
            wire_model=str(entry["wire_model"]),
            efforts=efforts,
            default_effort=str(entry["default_effort"]),
            thinking_default=str(entry["thinking_default"]),
            supports_no_thinking=bool(entry["supports_no_thinking"]),
            adapter_default=bool(entry.get("adapter_default", False)),
            context_window=int(entry["context_window"]),
            max_output_tokens=int(entry["max_output_tokens"]),
        )


def codex_model_info(model: ModelSpec) -> dict[str, object]:
    """Render one model using Codex's provider-owned /models schema."""

    return {
        "slug": model.model_id,
        "display_name": model.model_id,
        "description": f"Curated Google Vertex AI model ({model.backend}).",
        "default_reasoning_level": model.default_effort,
        "supported_reasoning_levels": [
            {"effort": effort, "description": f"{effort.capitalize()} reasoning effort"} for effort in model.efforts
        ],
        "shell_type": "shell_command",
        "visibility": "list",
        "supported_in_api": True,
        "priority": 0 if model.adapter_default else 1,
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
        "support_verbosity": False,
        "default_verbosity": None,
        "apply_patch_tool_type": "freeform",
        "web_search_tool_type": "text",
        "truncation_policy": {"mode": "bytes", "limit": 10000},
        "supports_parallel_tool_calls": True,
        "supports_image_detail_original": False,
        "context_window": model.context_window,
        "max_context_window": model.context_window,
        "auto_compact_token_limit": model.context_window * 9 // 10,
        "effective_context_window_percent": 90,
        "experimental_supported_tools": [],
        "input_modalities": ["text"],
        "supports_search_tool": False,
        "use_responses_lite": False,
    }


class ModelRegistry:
    """Validated model policy consumed by every Vertex wrapper."""

    def __init__(self, models: list[ModelSpec]) -> None:
        if not models:
            raise ValueError("Vertex model registry is empty")
        by_id = {model.model_id: model for model in models}
        if len(by_id) != len(models):
            raise ValueError("Vertex model registry contains duplicate ids")
        defaults = [model for model in models if model.adapter_default]
        if len(defaults) != 1:
            raise ValueError("Vertex model registry must have exactly one adapter_default")
        self._models = by_id
        self.default_model = defaults[0]

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ModelRegistry":
        config_path = Path(path or os.environ.get("VERTEX_ADAPTER_MODEL_CONFIG", "") or DEFAULT_CONFIG).expanduser()
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            entries = payload["provider_models"]
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise ValueError(f"cannot load Vertex model config {config_path}: {error}") from error
        if payload.get("schema_version") != "1.0.0" or not isinstance(entries, list):
            raise ValueError(f"unsupported Vertex model config: {config_path}")
        models = [
            ModelSpec.from_entry(entry)
            for entry in entries
            if isinstance(entry, dict) and entry.get("provider") == "vertex"
        ]
        return cls(models)

    def get(self, model_id: str | None) -> ModelSpec:
        selected = model_id or self.default_model.model_id
        try:
            return self._models[selected]
        except KeyError as error:
            choices = ", ".join(self.ids())
            raise ValueError(f"unsupported Vertex model {selected!r}; choose one of: {choices}") from error

    def ids(self) -> list[str]:
        return list(self._models)

    def values(self) -> list[ModelSpec]:
        return list(self._models.values())

    def resolve_effort(
        self,
        model: ModelSpec,
        requested: str | None,
        *,
        thinking: bool,
        no_thinking: bool,
    ) -> str | None:
        if no_thinking:
            if not model.supports_no_thinking:
                raise ValueError(
                    f"{model.model_id} cannot disable thinking; use its lowest supported "
                    f"effort ({model.efforts[0]}) instead"
                )
            return "none"
        effort = requested
        if thinking and effort is None:
            effort = model.thinking_default
        if effort is None:
            effort = model.default_effort
        if effort == "none" and model.supports_no_thinking:
            return effort
        if effort not in model.efforts:
            choices = ", ".join(model.efforts)
            raise ValueError(f"{model.model_id} does not support effort {effort!r}; choose: {choices}")
        return effort
