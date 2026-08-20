"""Model metadata used by Gemini/Claude protocol translators."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """Transport capabilities for one Gemini Chat or Claude Messages backend."""

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
