"""Reuse the deployed subscription adapters' protocol translators."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import BinaryIO

from copilot_auth import ModelSpec

ANTHROPIC = "/v1/messages"
CHAT = "/chat/completions"
RESPONSES = "/responses"
SUPPORTED_ENDPOINTS = frozenset({ANTHROPIC, CHAT, RESPONSES})


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load protocol module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_sibling_modules(directory: Path, names: tuple[str, ...], prefix: str) -> dict[str, ModuleType]:
    previous = {name: sys.modules.get(name) for name in names}
    loaded = {}
    try:
        for name in names:
            module = _load_module(name, directory / f"{name}.py")
            loaded[name] = module
            sys.modules[f"{prefix}.{name}"] = module
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    return loaded


_LIBRARY_ROOT = Path(__file__).resolve().parent.parent


def _sibling(name: str) -> Path:
    for candidate in (_LIBRARY_ROOT / name, _LIBRARY_ROOT / f"exact_{name}"):
        if candidate.is_dir():
            return candidate
    raise RuntimeError(f"required sibling protocol adapter {name} is not installed")


_CODEX = _load_sibling_modules(
    _sibling(",codex-adapter"),
    ("auth", "client", "state", "protocols"),
    "_copilot_codex_wire",
)
# Local Gemini Chat / Claude Messages translators (formerly vertex-adapter).
_GC = _load_sibling_modules(
    Path(__file__).resolve().parent,
    ("models", "state", "protocols", "streaming"),
    "_copilot_gc_wire",
)


@dataclass(frozen=True)
class PreparedRequest:
    body: bytes
    stream: bool
    tool_kinds: dict[str, str]


def _normalize_copilot_responses(events: Iterable[dict[str, object]]) -> Iterable[dict[str, object]]:
    function_items: dict[int, str] = {}
    for event in events:
        event_type = event.get("type")
        output_index = event.get("output_index")
        item = event.get("item")
        if (
            event_type == "response.output_item.added"
            and isinstance(output_index, int)
            and isinstance(item, dict)
            and item.get("type") == "function_call"
            and isinstance(item.get("id"), str)
        ):
            function_items[output_index] = item["id"]
        elif (
            event_type == "response.function_call_arguments.delta"
            and isinstance(output_index, int)
            and output_index in function_items
        ):
            event = {**event, "item_id": function_items[output_index]}
        elif (
            event_type == "response.output_item.done"
            and isinstance(output_index, int)
            and output_index in function_items
            and isinstance(item, dict)
            and item.get("type") == "function_call"
        ):
            event = {**event, "item": {**item, "id": function_items[output_index]}}
        yield event


class _SessionContextStore:
    """Keep provider-owned tool context bounded to one adapter process."""

    def __init__(self) -> None:
        self._store = _CODEX["state"].OpaqueReasoningStore()

    def get(self, call_id: str) -> dict[str, object] | None:
        return self._store.get(call_id)

    def save(self, call_id: str, value: dict[str, object]) -> None:
        self._store.put(call_id, value)


class WireTranslator:
    """Translate one native harness protocol to one Copilot model protocol."""

    def __init__(self) -> None:
        self._reasoning = _CODEX["state"].OpaqueReasoningStore()
        self._context = _SessionContextStore()

    @staticmethod
    def _gc_model(model: ModelSpec, backend: str) -> object:
        efforts = tuple(sorted(model.efforts))
        return _GC["models"].ModelSpec(
            model_id=model.model_id,
            backend=backend,
            wire_model=model.model_id,
            efforts=efforts,
            default_effort="medium" if "medium" in efforts else (efforts[0] if efforts else "none"),
            thinking_default="adaptive",
            supports_no_thinking="none" in efforts,
            adapter_default=False,
            context_window=model.context_window,
            max_output_tokens=model.max_output_tokens,
        )

    def prepare(
        self,
        frontend: str,
        backend: str,
        body: bytes,
        model: ModelSpec,
        effort: str | None = None,
        thinking: str | None = None,
    ) -> PreparedRequest:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("request body is not valid JSON") from error
        if not isinstance(payload, dict):
            raise TypeError("request body must be a JSON object")

        if frontend == ANTHROPIC and backend == RESPONSES:
            wants_stream = payload.get("stream") is True
            translated = _CODEX["protocols"].anthropic_to_responses(
                payload,
                model_override=model.model_id,
                effort_override=effort,
                store=self._reasoning,
            )
            return PreparedRequest(json.dumps(translated, separators=(",", ":")).encode(), wants_stream, {})

        if frontend == CHAT and backend == RESPONSES:
            wants_stream = payload.get("stream") is True
            translated = _CODEX["protocols"].chat_to_responses(
                payload,
                model_override=model.model_id,
                effort_override=effort,
                store=self._reasoning,
            )
            return PreparedRequest(json.dumps(translated, separators=(",", ":")).encode(), wants_stream, {})

        frontend_name = "anthropic" if frontend == ANTHROPIC else "chat" if frontend == CHAT else "responses"
        conversation = _GC["protocols"].parse_request(frontend_name, payload)
        gc_model = self._gc_model(model, "gemini-chat" if backend == CHAT else "claude")
        if backend == CHAT:
            translated = _GC["protocols"].to_gemini_payload(
                conversation,
                gc_model,
                effort,
                self._context,
            )
        elif backend == ANTHROPIC:
            translated = _GC["protocols"].to_claude_payload(
                conversation,
                gc_model,
                effort,
                thinking,
                self._context,
            )
            translated.pop("anthropic_version", None)
            translated["model"] = model.model_id
        else:
            raise ValueError(f"unsupported protocol translation: {frontend} -> {backend}")
        return PreparedRequest(
            json.dumps(translated, separators=(",", ":")).encode(),
            conversation.stream,
            conversation.tool_kinds,
        )

    def render(
        self,
        frontend: str,
        backend: str,
        upstream: BinaryIO,
        model: ModelSpec,
        prepared: PreparedRequest,
    ) -> bytes | Iterable[bytes]:
        if frontend == ANTHROPIC and backend == RESPONSES:
            events = _normalize_copilot_responses(_CODEX["protocols"].iter_sse_json(upstream))
            events = _CODEX["protocols"].responses_to_anthropic_events(
                events,
                model.model_id,
                self._reasoning,
            )
            if prepared.stream:
                return (_CODEX["protocols"].encode_sse(event) for event in events)
            payload = _CODEX["protocols"].collect_anthropic_message(events)
            return json.dumps(payload, separators=(",", ":")).encode()

        if frontend == CHAT and backend == RESPONSES:
            events = _normalize_copilot_responses(_CODEX["protocols"].iter_sse_json(upstream))
            if prepared.stream:
                return _CODEX["protocols"].responses_to_chat_events(events, model.model_id, self._reasoning)
            payload = _CODEX["protocols"].collect_chat_completion(events, model.model_id, self._reasoning)
            return json.dumps(payload, separators=(",", ":")).encode()

        backend_name = "gemini-chat" if backend == CHAT else "claude"
        gc_model = self._gc_model(model, backend_name)
        events = _GC["streaming"].canonical_events(
            backend_name,
            upstream,
            stream=prepared.stream,
            store=self._context,
        )
        frontend_name = "anthropic" if frontend == ANTHROPIC else "chat" if frontend == CHAT else "responses"
        if prepared.stream:
            if frontend == ANTHROPIC:
                return _GC["streaming"].render_anthropic(events, gc_model)
            if frontend == CHAT:
                return _GC["streaming"].render_chat(events, gc_model)
            return _GC["streaming"].render_responses(events, gc_model, prepared.tool_kinds)
        result = _GC["streaming"].collect_response(events)
        payload = _GC["streaming"].render_json(
            frontend_name,
            result,
            gc_model,
            prepared.tool_kinds,
        )
        return json.dumps(payload, separators=(",", ":")).encode()


def backend_endpoint(frontend: str, model: ModelSpec) -> str:
    if frontend in model.endpoints:
        return frontend
    for endpoint in (RESPONSES, ANTHROPIC, CHAT):
        if endpoint in model.endpoints:
            return endpoint
    raise ValueError(f"Copilot model {model.model_id!r} does not expose a supported completion endpoint")
