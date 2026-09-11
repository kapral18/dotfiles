"""Protocol translation between Anthropic Messages and OpenAI Responses."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from itertools import chain
from pathlib import Path
from typing import Any, Iterable, Iterator

from client import UpstreamError
from state import OpaqueReasoningStore

CODEX_REQUEST_FIELDS = {
    "model",
    "instructions",
    "input",
    "tools",
    "tool_choice",
    "parallel_tool_calls",
    "reasoning",
    "store",
    "stream",
    "stream_options",
    "include",
    "service_tier",
    "prompt_cache_key",
    "text",
    "client_metadata",
}


def load_lane_routes(harness: str) -> dict[str, dict[str, str]]:
    """Read exact model/effort pairs once per adapter launch, without provider calls."""
    path = Path(os.environ.get("AGENT_BANDS_FILE", Path.home() / ".config/ai/agent-bands.v1.json"))
    try:
        agents = json.loads(path.read_text(encoding="utf-8"))["harnesses"][harness]["agents"]
        if not isinstance(agents, dict) or not agents:
            raise ValueError("empty agent map")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid subscription lane projection for {harness}: {path}") from error
    routes = {}
    for name, pick in agents.items():
        if not isinstance(pick, dict):
            raise ValueError(f"invalid subscription lane {harness}/{name}")
        model, effort = pick.get("model"), pick.get("effort")
        if not isinstance(model, str) or not model or not isinstance(effort, str) or not effort:
            raise ValueError(f"invalid subscription lane {harness}/{name}")
        routes[f"{model}@lane-{effort}"] = {"model": model, "effort": effort}
    return routes


def subscription_lane(requested: object, routes: dict[str, dict[str, str]]) -> dict[str, str] | None:
    """Only an explicit wire selector chooses lane controls; raw model IDs never imply a role."""
    if not isinstance(requested, str):
        return None
    requested = requested.removesuffix("[1m]")
    if "@lane-" not in requested:
        return None
    if requested not in routes:
        raise ValueError(f"unregistered subscription lane: {requested}")
    return routes.get(requested)


def iter_sse_json(source: Iterable[bytes]) -> Iterator[dict[str, Any]]:
    """Yield complete JSON objects from an SSE byte stream."""

    data_lines: list[str] = []
    for raw_line in source:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            if data_lines:
                yield _decode_sse_data("\n".join(data_lines))
                data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        yield _decode_sse_data("\n".join(data_lines))


def _decode_sse_data(data: str) -> dict[str, Any]:
    if data == "[DONE]":
        return {"type": "response.done"}
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as error:
        raise UpstreamError(502, "upstream_protocol_error", "Codex backend returned invalid SSE JSON") from error
    if not isinstance(payload, dict):
        raise UpstreamError(502, "upstream_protocol_error", "Codex backend returned a non-object SSE event")
    return payload


def encode_sse(event: dict[str, Any]) -> bytes:
    event_type = event.get("type", "message")
    data = json.dumps(event, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data}\n\n".encode()


def prepare_responses_request(
    body: dict[str, Any],
    *,
    model_override: str | None,
    effort_override: str | None,
) -> dict[str, Any]:
    """Force the stream-only Codex wire contract and apply wrapper overrides."""

    payload = {key: deepcopy(value) for key, value in body.items() if key in CODEX_REQUEST_FIELDS}
    payload["stream"] = True
    payload["store"] = False
    if model_override is not None:
        payload["model"] = model_override
    if effort_override is not None:
        reasoning = payload.get("reasoning")
        if not isinstance(reasoning, dict):
            reasoning = {}
            payload["reasoning"] = reasoning
        reasoning["effort"] = effort_override
    include = payload.get("include")
    if not isinstance(include, list):
        include = []
        payload["include"] = include
    if "reasoning.encrypted_content" not in include:
        include.append("reasoning.encrypted_content")
    return payload


def aggregate_responses(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Rebuild a non-streaming Responses object from terminal SSE events."""

    output: list[dict[str, Any]] = []
    output_ids: set[str] = set()
    completed: dict[str, Any] | None = None
    for event in events:
        event_type = event.get("type")
        if event_type == "response.output_item.done":
            item = event.get("item")
            if isinstance(item, dict):
                item_id = item.get("id")
                if not isinstance(item_id, str) or item_id not in output_ids:
                    output.append(deepcopy(item))
                    if isinstance(item_id, str):
                        output_ids.add(item_id)
        elif event_type == "response.completed":
            response = event.get("response")
            if isinstance(response, dict):
                completed = deepcopy(response)
        elif event_type in {"response.failed", "response.incomplete", "error"}:
            raise _event_error(event)
    if completed is None:
        raise UpstreamError(
            502,
            "upstream_protocol_error",
            "Codex backend stream ended without response.completed",
        )
    completed["output"] = output
    return completed


def _event_error(event: dict[str, Any]) -> UpstreamError:
    detail = event.get("error")
    if not isinstance(detail, dict):
        response = event.get("response")
        if isinstance(response, dict):
            detail = response.get("error")
    if not isinstance(detail, dict):
        detail = {}
    message = detail.get("message")
    code = detail.get("code") or detail.get("type")
    return UpstreamError(
        502,
        str(code) if isinstance(code, str) and code else "api_error",
        str(message) if isinstance(message, str) and message else "Codex backend response failed",
    )


def _text_blocks(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return ""
    return "\n".join(
        block["text"]
        for block in value
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    )


def _content_blocks(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        return [{"type": "text", "text": value}]
    if not isinstance(value, list):
        raise ValueError("Anthropic message content must be a string or array")
    if not all(isinstance(block, dict) for block in value):
        raise ValueError("Anthropic content blocks must be objects")
    return value


def _image_content(block: dict[str, Any]) -> dict[str, Any]:
    source = block.get("source")
    if not isinstance(source, dict):
        raise ValueError("Anthropic image block has no source")
    source_type = source.get("type")
    if source_type == "base64":
        media_type = source.get("media_type")
        data = source.get("data")
        if not isinstance(media_type, str) or not isinstance(data, str):
            raise ValueError("Anthropic base64 image source is incomplete")
        image_url = f"data:{media_type};base64,{data}"
    elif source_type == "url":
        image_url = source.get("url")
        if not isinstance(image_url, str) or not image_url:
            raise ValueError("Anthropic URL image source is incomplete")
    else:
        raise ValueError(f"unsupported Anthropic image source: {source_type!r}")
    return {"type": "input_image", "image_url": image_url}


def _tool_result_output(block: dict[str, Any]) -> str | list[dict[str, Any]]:
    content = block.get("content", "")
    if isinstance(content, str):
        value: str | list[dict[str, Any]] = content
    else:
        rendered: list[dict[str, Any]] = []
        for item in _content_blocks(content):
            item_type = item.get("type")
            if item_type == "text" and isinstance(item.get("text"), str):
                rendered.append({"type": "input_text", "text": item["text"]})
            elif item_type == "image":
                rendered.append(_image_content(item))
            else:
                raise ValueError(f"unsupported Anthropic tool result block: {item_type!r}")
        value = rendered
    if block.get("is_error"):
        if isinstance(value, str):
            return f"Tool error: {value}"
        value.insert(0, {"type": "input_text", "text": "Tool error:"})
    return value


def _message_items(
    role: str,
    content: Any,
    store: OpaqueReasoningStore,
) -> list[dict[str, Any]]:
    if role not in {"user", "assistant"}:
        raise ValueError(f"unsupported Anthropic message role: {role!r}")
    items: list[dict[str, Any]] = []
    message_content: list[dict[str, Any]] = []

    def flush_message() -> None:
        if message_content:
            items.append({"type": "message", "role": role, "content": list(message_content)})
            message_content.clear()

    for block in _content_blocks(content):
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if not isinstance(text, str):
                raise ValueError("Anthropic text block has no text")
            message_content.append({"type": "input_text" if role == "user" else "output_text", "text": text})
        elif block_type == "image" and role == "user":
            message_content.append(_image_content(block))
        elif block_type == "tool_use" and role == "assistant":
            flush_message()
            call_id = block.get("id")
            name = block.get("name")
            arguments = block.get("input", {})
            if not isinstance(call_id, str) or not isinstance(name, str) or not isinstance(arguments, dict):
                raise ValueError("Anthropic tool_use block is incomplete")
            reasoning = store.get(call_id)
            if reasoning is not None:
                items.append(reasoning)
            items.append(
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": name,
                    "arguments": json.dumps(arguments, separators=(",", ":")),
                }
            )
        elif block_type == "tool_result" and role == "user":
            flush_message()
            call_id = block.get("tool_use_id")
            if not isinstance(call_id, str):
                raise ValueError("Anthropic tool_result block has no tool_use_id")
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": _tool_result_output(block),
                }
            )
        elif block_type in {"thinking", "redacted_thinking"} and role == "assistant":
            continue
        else:
            raise ValueError(f"unsupported Anthropic content block: {block_type!r}")
    flush_message()
    return items


def _tools(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Anthropic tools must be an array")
    result: list[dict[str, Any]] = []
    for tool in value:
        if not isinstance(tool, dict):
            raise ValueError("Anthropic tools must be objects")
        name = tool.get("name")
        schema = tool.get("input_schema")
        if not isinstance(name, str) or not isinstance(schema, dict):
            raise ValueError("Anthropic tool definition is incomplete")
        translated = {
            "type": "function",
            "name": name,
            "parameters": deepcopy(schema),
            "strict": False,
        }
        description = tool.get("description")
        if isinstance(description, str):
            translated["description"] = description
        result.append(translated)
    return result


def _tool_choice(value: Any) -> tuple[str, bool, str | None]:
    if value is None:
        return "auto", True, None
    if not isinstance(value, dict):
        raise ValueError("Anthropic tool_choice must be an object")
    choice_type = value.get("type", "auto")
    if choice_type == "auto":
        translated = "auto"
        selected = None
    elif choice_type == "any":
        translated = "required"
        selected = None
    elif choice_type == "none":
        translated = "none"
        selected = None
    elif choice_type == "tool":
        name = value.get("name")
        if not isinstance(name, str):
            raise ValueError("Anthropic tool_choice type=tool requires a name")
        translated = "required"
        selected = name
    else:
        raise ValueError(f"unsupported Anthropic tool_choice: {choice_type!r}")
    return translated, not bool(value.get("disable_parallel_tool_use")), selected


def anthropic_to_responses(
    body: dict[str, Any],
    *,
    model_override: str | None,
    effort_override: str | None,
    store: OpaqueReasoningStore,
) -> dict[str, Any]:
    """Translate one Anthropic Messages request to the Codex Responses wire shape."""

    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Anthropic messages must be an array")
    inputs: list[dict[str, Any]] = []
    instruction_parts = [part for part in [_text_blocks(body.get("system"))] if part]
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Anthropic messages must be objects")
        role = message.get("role")
        if not isinstance(role, str):
            raise ValueError("Anthropic message has no role")
        if role == "system":
            system_message = _text_blocks(message.get("content"))
            if system_message:
                instruction_parts.append(system_message)
            continue
        inputs.extend(_message_items(role, message.get("content", ""), store))
    model = model_override if model_override is not None else body.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("Anthropic request has no model")
    payload: dict[str, Any] = {
        "model": model,
        "input": inputs,
        "stream": True,
        "store": False,
        "include": ["reasoning.encrypted_content"],
    }
    if instruction_parts:
        payload["instructions"] = "\n\n".join(instruction_parts)
    tools = _tools(body.get("tools"))
    if tools:
        tool_choice, parallel, selected_tool = _tool_choice(body.get("tool_choice"))
        if selected_tool is not None:
            tools = [tool for tool in tools if tool["name"] == selected_tool]
            if not tools:
                raise ValueError(f"Anthropic tool_choice names unknown tool {selected_tool!r}")
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
        payload["parallel_tool_calls"] = parallel
    output_config = body.get("output_config")
    if not isinstance(output_config, dict):
        output_config = {}
    effort = effort_override if effort_override is not None else output_config.get("effort")
    if isinstance(effort, str) and effort:
        payload["reasoning"] = {"effort": effort}
    output_format = output_config.get("format")
    if isinstance(output_format, dict) and output_format.get("type") == "json_schema":
        schema = output_format.get("schema")
        if not isinstance(schema, dict):
            raise ValueError("Anthropic json_schema output format has no schema")
        payload["text"] = {
            "format": {
                "type": "json_schema",
                "name": "claude_output",
                "strict": True,
                "schema": deepcopy(schema),
            }
        }
    return payload


def chat_to_responses(
    body: dict[str, Any],
    *,
    model_override: str | None,
    effort_override: str | None,
    store: OpaqueReasoningStore,
) -> dict[str, Any]:
    """Translate OpenAI Chat Completions requests through the Messages converter."""

    raw_messages = body.get("messages")
    if not isinstance(raw_messages, list):
        raise ValueError("Chat Completions messages must be an array")
    system: list[dict[str, str]] = []
    messages: list[dict[str, Any]] = []
    for message in raw_messages:
        if not isinstance(message, dict):
            raise ValueError("Chat Completions messages must be objects")
        role = message.get("role")
        content = message.get("content")
        text = _text_blocks(content)
        if role in {"system", "developer"}:
            if text:
                system.append({"type": "text", "text": text})
            continue
        if role == "tool":
            call_id = message.get("tool_call_id")
            if not isinstance(call_id, str) or not call_id:
                raise ValueError("Chat Completions tool message has no tool_call_id")
            messages.append(
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call_id, "content": text}]}
            )
            continue
        if role not in {"user", "assistant"}:
            raise ValueError(f"unsupported Chat Completions message role: {role!r}")
        blocks: list[dict[str, Any]] = []
        if text:
            blocks.append({"type": "text", "text": text})
        if role == "assistant":
            calls = message.get("tool_calls", [])
            if not isinstance(calls, list):
                raise ValueError("Chat Completions tool_calls must be an array")
            for call in calls:
                function = call.get("function") if isinstance(call, dict) else None
                call_id = call.get("id") if isinstance(call, dict) else None
                name = function.get("name") if isinstance(function, dict) else None
                arguments = function.get("arguments", "{}") if isinstance(function, dict) else "{}"
                if not isinstance(call_id, str) or not isinstance(name, str) or not isinstance(arguments, str):
                    raise ValueError("Chat Completions tool call is incomplete")
                try:
                    parsed = json.loads(arguments or "{}")
                except json.JSONDecodeError as error:
                    raise ValueError("Chat Completions tool arguments are not valid JSON") from error
                if not isinstance(parsed, dict):
                    raise ValueError("Chat Completions tool arguments must be an object")
                blocks.append({"type": "tool_use", "id": call_id, "name": name, "input": parsed})
        messages.append({"role": role, "content": blocks})
    tools = []
    for tool in body.get("tools", []):
        function = tool.get("function") if isinstance(tool, dict) else None
        if not isinstance(function, dict) or tool.get("type") != "function":
            raise ValueError("Chat Completions tools must be function definitions")
        name = function.get("name")
        if not isinstance(name, str):
            raise ValueError("Chat Completions tool has no name")
        tools.append(
            {
                "name": name,
                "description": function.get("description", ""),
                "input_schema": function.get("parameters", {}),
            }
        )
    choice = body.get("tool_choice")
    anthropic_choice: dict[str, Any] | None = None
    if choice == "required":
        anthropic_choice = {"type": "any"}
    elif choice == "none":
        anthropic_choice = {"type": "none"}
    elif isinstance(choice, dict):
        function = choice.get("function")
        name = function.get("name") if isinstance(function, dict) else None
        if not isinstance(name, str):
            raise ValueError("Chat Completions tool_choice function has no name")
        anthropic_choice = {"type": "tool", "name": name}
    translated: dict[str, Any] = {
        "model": body.get("model"),
        "system": system,
        "messages": messages,
        "tools": tools,
        "max_tokens": body.get("max_completion_tokens", body.get("max_tokens", 32768)),
        "stream": body.get("stream") is True,
    }
    if anthropic_choice is not None:
        translated["tool_choice"] = anthropic_choice
    effort = body.get("reasoning_effort")
    if isinstance(effort, str):
        translated["output_config"] = {"effort": effort}
    payload = anthropic_to_responses(
        translated, model_override=model_override, effort_override=effort_override, store=store
    )
    # The Codex Responses endpoint accepts this caller-owned cache identity.
    # Do not invent an identity from prompts or translate unsupported TTL controls.
    if "prompt_cache_key" in body:
        payload["prompt_cache_key"] = deepcopy(body["prompt_cache_key"])
    return payload


def _chat_sse(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


def responses_to_chat_events(
    events: Iterable[dict[str, Any]], model: str, store: OpaqueReasoningStore
) -> Iterator[bytes]:
    """Render Responses SSE objects as Chat Completions chunks."""

    response_id = "chatcmpl_codex"
    tool_indices: dict[int, int] = {}
    saw_tool = False
    for event in responses_to_anthropic_events(events, model, store):
        kind = event["type"]
        if kind == "message_start":
            message = event.get("message", {})
            if isinstance(message, dict) and isinstance(message.get("id"), str):
                response_id = message["id"].removeprefix("msg_")
            yield _chat_sse(
                {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                }
            )
        elif kind == "content_block_delta":
            delta = event.get("delta", {})
            index = event.get("index")
            if not isinstance(delta, dict) or not isinstance(index, int):
                continue
            if delta.get("type") == "text_delta":
                value = delta.get("text", "")
                yield _chat_sse(
                    {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [{"index": 0, "delta": {"content": value}, "finish_reason": None}],
                    }
                )
            elif delta.get("type") == "input_json_delta" and index in tool_indices:
                yield _chat_sse(
                    {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": tool_indices[index],
                                            "function": {"arguments": delta.get("partial_json", "")},
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                )
        elif kind == "content_block_start":
            block = event.get("content_block", {})
            index = event.get("index")
            if isinstance(block, dict) and isinstance(index, int) and block.get("type") == "tool_use":
                position = len(tool_indices)
                tool_indices[index] = position
                saw_tool = True
                yield _chat_sse(
                    {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": position,
                                            "id": block.get("id"),
                                            "type": "function",
                                            "function": {"name": block.get("name"), "arguments": ""},
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                )
        elif kind == "message_delta":
            usage = event.get("usage", {})
            yield _chat_sse(
                {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls" if saw_tool else "stop"}],
                    "usage": _chat_usage(usage),
                }
            )
        elif kind == "message_stop":
            yield b"data: [DONE]\n\n"


def collect_chat_completion(
    events: Iterable[dict[str, Any]], model: str, store: OpaqueReasoningStore
) -> dict[str, Any]:
    chunks = responses_to_chat_events(events, model, store)
    text = ""
    tools: dict[int, dict[str, Any]] = {}
    finish = "stop"
    usage: dict[str, int] = {}
    response_id = "chatcmpl_codex"
    for raw in chunks:
        if raw == b"data: [DONE]\n\n":
            continue
        payload = json.loads(raw.decode().removeprefix("data: "))
        response_id = payload["id"]
        choice = payload["choices"][0]
        delta = choice["delta"]
        text += delta.get("content", "") or ""
        for call in delta.get("tool_calls", []):
            index = call["index"]
            current = tools.setdefault(
                index, {"id": call.get("id"), "type": "function", "function": {"name": None, "arguments": ""}}
            )
            function = call.get("function", {})
            current["function"]["name"] = function.get("name", current["function"]["name"])
            current["function"]["arguments"] += function.get("arguments", "")
        if choice.get("finish_reason") is not None:
            finish = choice["finish_reason"]
        usage = payload.get("usage", usage)
    return {
        "id": response_id,
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text or None,
                    **({"tool_calls": list(tools.values())} if tools else {}),
                },
                "finish_reason": finish,
            }
        ],
        "usage": usage,
    }


def _anthropic_usage(usage: object, *, output: bool = False) -> dict[str, int]:
    """Translate Responses usage into Anthropic Messages usage without losing cache accounting.

    Responses `input_tokens` counts every prompt token including the cached ones, with the
    cached share reported under `input_tokens_details.cached_tokens` and writes under
    `cache_write_tokens` (observed live from the ChatGPT Codex backend on 2026-09-06:
    `{"input_tokens": 2815, "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0}}`;
    Copilot's chat shape spells the write field `cache_creation_tokens`). Anthropic `input_tokens` is the fresh share
    only, with cache reads and writes as separate fields, so the frontend can add the three
    without double counting. Missing detail fields translate to zero fresh-cache split, never
    to an invented number.
    """
    if not isinstance(usage, dict):
        usage = {}
    details = usage.get("input_tokens_details")
    if not isinstance(details, dict):
        details = {}
    total = int(usage.get("input_tokens") or 0)
    cached = int(details.get("cached_tokens") or 0)
    written = int(details.get("cache_write_tokens") or details.get("cache_creation_tokens") or 0)
    translated = {
        "input_tokens": max(0, total - cached - written),
        "cache_read_input_tokens": cached,
        "cache_creation_input_tokens": written,
        "output_tokens": int(usage.get("output_tokens") or 0) if output else 0,
    }
    return translated


def _chat_usage(usage: object) -> dict[str, Any]:
    """Chat Completions usage from Anthropic-shaped usage: prompt_tokens includes cache."""
    if not isinstance(usage, dict):
        usage = {}
    fresh = int(usage.get("input_tokens") or 0)
    cached = int(usage.get("cache_read_input_tokens") or 0)
    written = int(usage.get("cache_creation_input_tokens") or 0)
    output = int(usage.get("output_tokens") or 0)
    prompt = fresh + cached + written
    rendered: dict[str, Any] = {
        "prompt_tokens": prompt,
        "completion_tokens": output,
        "total_tokens": prompt + output,
    }
    if cached or written:
        rendered["prompt_tokens_details"] = {"cached_tokens": cached, "cache_creation_tokens": written}
    return rendered


def _message_start(response: dict[str, Any], model: str) -> dict[str, Any]:
    response_id = response.get("id")
    usage = response.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    return {
        "type": "message_start",
        "message": {
            "id": f"msg_{response_id}" if isinstance(response_id, str) else "msg_codex",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": _anthropic_usage(usage),
        },
    }


def responses_to_anthropic_events(
    events: Iterable[dict[str, Any]],
    model: str,
    store: OpaqueReasoningStore,
) -> Iterator[dict[str, Any]]:
    """Render canonical Responses SSE objects as Anthropic Messages SSE objects."""

    iterator = iter(events)
    try:
        first = next(iterator)
    except StopIteration as error:
        raise UpstreamError(502, "upstream_protocol_error", "Codex backend returned an empty stream") from error
    if first.get("type") in {"response.failed", "response.incomplete", "error"}:
        raise _event_error(first)
    first_response = first.get("response")
    if not isinstance(first_response, dict):
        first_response = {}
    yield _message_start(first_response, model)

    next_index = 0
    text_index: int | None = None
    open_blocks: set[int] = set()
    tool_blocks: dict[str, int] = {}
    tool_arguments: dict[str, str] = {}
    pending_reasoning: dict[str, Any] | None = None
    saw_tool = False
    completed = False

    def start_text() -> tuple[int, dict[str, Any] | None]:
        nonlocal next_index, text_index
        if text_index is not None:
            return text_index, None
        text_index = next_index
        next_index += 1
        open_blocks.add(text_index)
        return text_index, {
            "type": "content_block_start",
            "index": text_index,
            "content_block": {"type": "text", "text": ""},
        }

    def start_tool(item: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
        nonlocal next_index, text_index, saw_tool, pending_reasoning
        emitted: list[dict[str, Any]] = []
        if text_index is not None and text_index in open_blocks:
            emitted.append({"type": "content_block_stop", "index": text_index})
            open_blocks.remove(text_index)
            text_index = None
        item_id = item.get("id")
        call_id = item.get("call_id")
        name = item.get("name")
        if not isinstance(item_id, str) or not isinstance(call_id, str) or not isinstance(name, str):
            raise UpstreamError(502, "upstream_protocol_error", "Codex function call item is incomplete")
        if item_id in tool_blocks:
            return tool_blocks[item_id], emitted
        index = next_index
        next_index += 1
        tool_blocks[item_id] = index
        tool_arguments[item_id] = ""
        open_blocks.add(index)
        saw_tool = True
        if pending_reasoning is not None:
            store.put(call_id, pending_reasoning)
            pending_reasoning = None
        emitted.append(
            {
                "type": "content_block_start",
                "index": index,
                "content_block": {"type": "tool_use", "id": call_id, "name": name, "input": {}},
            }
        )
        return index, emitted

    for event in chain([first], iterator):
        event_type = event.get("type")
        if event_type in {"response.created", "response.in_progress"}:
            continue
        if event_type == "response.output_text.delta":
            delta = event.get("delta")
            if not isinstance(delta, str):
                continue
            index, start = start_text()
            if start is not None:
                yield start
            yield {
                "type": "content_block_delta",
                "index": index,
                "delta": {"type": "text_delta", "text": delta},
            }
            continue
        if event_type == "response.output_item.added":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "function_call":
                _, emitted = start_tool(item)
                yield from emitted
            continue
        if event_type == "response.function_call_arguments.delta":
            item_id = event.get("item_id")
            delta = event.get("delta")
            if not isinstance(item_id, str) or not isinstance(delta, str):
                continue
            if item_id not in tool_blocks:
                raise UpstreamError(
                    502,
                    "upstream_protocol_error",
                    "Codex emitted function arguments before the function call item",
                )
            tool_arguments[item_id] += delta
            yield {
                "type": "content_block_delta",
                "index": tool_blocks[item_id],
                "delta": {"type": "input_json_delta", "partial_json": delta},
            }
            continue
        if event_type == "response.output_item.done":
            item = event.get("item")
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "reasoning":
                pending_reasoning = deepcopy(item)
            elif item_type == "function_call":
                item_id = item.get("id")
                if not isinstance(item_id, str):
                    raise UpstreamError(502, "upstream_protocol_error", "Codex function call has no item ID")
                if item_id not in tool_blocks:
                    _, emitted = start_tool(item)
                    yield from emitted
                final_arguments = item.get("arguments")
                if isinstance(final_arguments, str) and not tool_arguments[item_id]:
                    tool_arguments[item_id] = final_arguments
                    if final_arguments:
                        yield {
                            "type": "content_block_delta",
                            "index": tool_blocks[item_id],
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": final_arguments,
                            },
                        }
                index = tool_blocks[item_id]
                if index in open_blocks:
                    yield {"type": "content_block_stop", "index": index}
                    open_blocks.remove(index)
            continue
        if event_type == "response.completed":
            for index in sorted(open_blocks):
                yield {"type": "content_block_stop", "index": index}
            open_blocks.clear()
            response = event.get("response")
            if not isinstance(response, dict):
                response = {}
            usage = response.get("usage")
            if not isinstance(usage, dict):
                usage = {}
            yield {
                "type": "message_delta",
                "delta": {
                    "stop_reason": "tool_use" if saw_tool else "end_turn",
                    "stop_sequence": None,
                },
                "usage": _anthropic_usage(usage, output=True),
            }
            yield {"type": "message_stop"}
            completed = True
            continue
        if event_type in {"response.failed", "response.incomplete", "error"}:
            raise _event_error(event)
    if not completed:
        raise UpstreamError(
            502,
            "upstream_protocol_error",
            "Codex backend stream ended without response.completed",
        )


def collect_anthropic_message(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Collect Anthropic streaming events into one Messages response."""

    message: dict[str, Any] | None = None
    content: dict[int, dict[str, Any]] = {}
    arguments: dict[int, str] = {}
    stopped = False
    for event in events:
        event_type = event.get("type")
        if event_type == "message_start":
            started = event.get("message")
            if isinstance(started, dict):
                message = deepcopy(started)
                message["content"] = []
        elif event_type == "content_block_start":
            index = event.get("index")
            block = event.get("content_block")
            if not isinstance(index, int) or not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                content[index] = {"type": "text", "text": ""}
            elif block.get("type") == "tool_use":
                content[index] = {
                    "type": "tool_use",
                    "id": block.get("id"),
                    "name": block.get("name"),
                    "input": {},
                }
                arguments[index] = ""
        elif event_type == "content_block_delta":
            index = event.get("index")
            delta = event.get("delta")
            if not isinstance(index, int) or not isinstance(delta, dict) or index not in content:
                continue
            if delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
                content[index]["text"] += delta["text"]
            elif delta.get("type") == "input_json_delta" and isinstance(delta.get("partial_json"), str):
                arguments[index] = arguments.get(index, "") + delta["partial_json"]
        elif event_type == "content_block_stop":
            index = event.get("index")
            if isinstance(index, int) and index in arguments:
                try:
                    parsed = json.loads(arguments[index] or "{}")
                except json.JSONDecodeError as error:
                    raise UpstreamError(
                        502,
                        "upstream_protocol_error",
                        "Codex returned invalid function call arguments",
                    ) from error
                content[index]["input"] = parsed
        elif event_type == "message_delta":
            if message is None:
                continue
            delta = event.get("delta")
            usage = event.get("usage")
            if isinstance(delta, dict):
                message["stop_reason"] = delta.get("stop_reason")
                message["stop_sequence"] = delta.get("stop_sequence")
            if isinstance(usage, dict):
                message.setdefault("usage", {}).update(usage)
        elif event_type == "message_stop":
            stopped = True
        elif event_type == "error":
            raise _event_error(event)
    if message is None or not stopped:
        raise UpstreamError(502, "upstream_protocol_error", "Anthropic stream did not complete")
    message["content"] = [content[index] for index in sorted(content)]
    message["type"] = "message"
    return message
