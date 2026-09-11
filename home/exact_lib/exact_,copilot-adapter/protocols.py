"""Request normalization and Vertex backend payload construction."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from models import ModelSpec
from state import OpaqueContextStore


@dataclass
class Tool:
    name: str
    description: str
    schema: dict[str, Any]
    kind: str = "function"
    namespace: str | None = None


@dataclass
class Conversation:
    system: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)
    max_tokens: int | None = None
    stream: bool = True
    original_thinking: dict[str, Any] | None = None
    original_output_config: dict[str, Any] | None = None
    requested_effort: str | None = None
    cache_options: dict[str, Any] = field(default_factory=dict)
    automatic_cache: bool = False

    @property
    def tool_kinds(self) -> dict[str, str]:
        return {tool.name: tool.kind for tool in self.tools}

    @property
    def has_cache_breakpoints(self) -> bool:
        return any(
            "prompt_cache_breakpoint" in part
            for turn in self.messages
            for block in turn["blocks"]
            for part in [block, *block.get("content_blocks", [])]
        )


def _text_blocks(content: object) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if not isinstance(content, list):
        return []
    blocks = []
    for item in content:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind in {"text", "input_text", "output_text"}:
            block = {"type": "text", "text": str(item.get("text", ""))}
            marker = item.get("prompt_cache_breakpoint")
            if marker is not None:
                if not isinstance(marker, dict) or marker.get("mode") != "explicit":
                    raise ValueError("prompt_cache_breakpoint must specify explicit mode")
                block["prompt_cache_breakpoint"] = deepcopy(marker)
            blocks.append(block)
    return blocks


def _tool_output_text(output: object) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return "\n".join(block["text"] for block in _text_blocks(output))
    return json.dumps(output, separators=(",", ":"))


def _parse_tools(tools: object, frontend: str, namespace: str | None = None) -> list[Tool]:
    if not isinstance(tools, list):
        return []
    parsed = []
    for item in tools:
        if not isinstance(item, dict):
            continue
        if frontend == "responses" and item.get("type") == "namespace":
            name = item.get("name")
            if (
                namespace is not None
                or not isinstance(name, str)
                or not name
                or not isinstance(item.get("tools"), list)
            ):
                raise ValueError("Responses tool namespace must have a name and tools, without nesting")
            children = _parse_tools(item["tools"], frontend, name)
            for child in children:
                child.description = "\n\n".join(
                    text for text in (str(item.get("description", "")), child.description) if text
                )
            parsed.extend(children)
            continue
        if frontend == "chat":
            function = item.get("function")
            if item.get("type") != "function" or not isinstance(function, dict):
                continue
            parsed.append(
                Tool(
                    name=str(function.get("name", "")),
                    description=str(function.get("description", "")),
                    schema=function.get("parameters") if isinstance(function.get("parameters"), dict) else {},
                )
            )
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        kind = "custom" if item.get("type") == "custom" else "function"
        description = str(item.get("description", ""))
        schema = item.get("parameters") if frontend == "responses" else item.get("input_schema")
        if kind == "custom":
            format_spec = item.get("format")
            if (
                isinstance(format_spec, dict)
                and format_spec.get("type") == "grammar"
                and isinstance(format_spec.get("definition"), str)
                and format_spec["definition"]
            ):
                syntax = str(format_spec.get("syntax", "grammar"))
                description = f"{description}\n\nInput grammar ({syntax}):\n{format_spec['definition']}"
            schema = {
                "type": "object",
                "properties": {"input": {"type": "string"}},
                "required": ["input"],
            }
        elif not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        elif "type" not in schema:
            schema = {**schema, "type": "object"}
        parsed.append(
            Tool(
                name=name,
                description=description,
                schema=schema,
                kind=kind,
                namespace=namespace,
            )
        )
    return parsed


def _parse_responses(body: dict[str, Any]) -> Conversation:
    conversation = Conversation(
        system=str(body.get("instructions", "")),
        tools=_parse_tools(body.get("tools"), "responses"),
        max_tokens=body.get("max_output_tokens") if isinstance(body.get("max_output_tokens"), int) else None,
        stream=bool(body.get("stream", True)),
    )
    reasoning = body.get("reasoning")
    if isinstance(reasoning, dict) and isinstance(reasoning.get("effort"), str):
        conversation.requested_effort = reasoning["effort"]
    items = body.get("input", [])
    if isinstance(items, str):
        items = [{"type": "message", "role": "user", "content": items}]
    if not isinstance(items, list):
        return conversation
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind == "message" or (kind is None and "role" in item):
            conversation.messages.append(
                {"role": str(item.get("role", "user")), "blocks": _text_blocks(item.get("content"))}
            )
        elif kind in {"function_call", "custom_tool_call"}:
            arguments = item.get("arguments") if kind == "function_call" else item.get("input")
            conversation.messages.append(
                {
                    "role": "assistant",
                    "blocks": [
                        {
                            "type": "tool_call",
                            "id": str(item.get("call_id", "")),
                            "name": str(item.get("name", "")),
                            "namespace": item.get("namespace"),
                            "arguments": str(arguments or ""),
                            "kind": "custom" if kind == "custom_tool_call" else "function",
                        }
                    ],
                }
            )
        elif kind in {"function_call_output", "custom_tool_call_output"}:
            conversation.messages.append(
                {
                    "role": "user",
                    "blocks": [
                        {
                            "type": "tool_result",
                            "id": str(item.get("call_id", "")),
                            "content": _tool_output_text(item.get("output", "")),
                            "content_blocks": _text_blocks(item.get("output", "")),
                            "is_error": False,
                        }
                    ],
                }
            )
    return conversation


def _parse_chat(body: dict[str, Any]) -> Conversation:
    conversation = Conversation(
        tools=_parse_tools(body.get("tools"), "chat"),
        max_tokens=next(
            (value for value in (body.get("max_completion_tokens"), body.get("max_tokens")) if isinstance(value, int)),
            None,
        ),
        stream=bool(body.get("stream", False)),
        requested_effort=body.get("reasoning_effort") if isinstance(body.get("reasoning_effort"), str) else None,
    )
    for message in body.get("messages", []):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "user"))
        blocks = _text_blocks(message.get("content"))
        for call in message.get("tool_calls", []) if isinstance(message.get("tool_calls"), list) else []:
            function = call.get("function") if isinstance(call, dict) else None
            if isinstance(function, dict):
                blocks.append(
                    {
                        "type": "tool_call",
                        "id": str(call.get("id", "")),
                        "name": str(function.get("name", "")),
                        "arguments": str(function.get("arguments", "")),
                        "kind": "function",
                    }
                )
        if role == "tool":
            blocks = [
                {
                    "type": "tool_result",
                    "id": str(message.get("tool_call_id", "")),
                    "content": _tool_output_text(message.get("content", "")),
                    "content_blocks": _text_blocks(message.get("content", "")),
                    "is_error": False,
                }
            ]
            role = "user"
        conversation.messages.append({"role": role, "blocks": blocks})
    return conversation


def _parse_anthropic(body: dict[str, Any]) -> Conversation:
    conversation = Conversation(
        system=_tool_output_text(body.get("system", "")),
        tools=_parse_tools(body.get("tools"), "anthropic"),
        max_tokens=body.get("max_tokens") if isinstance(body.get("max_tokens"), int) else None,
        stream=bool(body.get("stream", False)),
        original_thinking=body.get("thinking") if isinstance(body.get("thinking"), dict) else None,
        original_output_config=body.get("output_config") if isinstance(body.get("output_config"), dict) else None,
    )
    if conversation.original_output_config and isinstance(conversation.original_output_config.get("effort"), str):
        conversation.requested_effort = conversation.original_output_config["effort"]
    for message in body.get("messages", []):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "user"))
        content = message.get("content")
        blocks = _text_blocks(content)
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                kind = block.get("type")
                if kind == "tool_use":
                    blocks.append(
                        {
                            "type": "tool_call",
                            "id": str(block.get("id", "")),
                            "name": str(block.get("name", "")),
                            "arguments": json.dumps(block.get("input", {}), separators=(",", ":")),
                            "kind": "function",
                        }
                    )
                elif kind == "tool_result":
                    blocks.append(
                        {
                            "type": "tool_result",
                            "id": str(block.get("tool_use_id", "")),
                            "content": _tool_output_text(block.get("content", "")),
                            "is_error": bool(block.get("is_error", False)),
                        }
                    )
                elif kind in {"thinking", "redacted_thinking"}:
                    blocks.append(dict(block))
        conversation.messages.append({"role": role, "blocks": blocks})
    return conversation


def parse_request(frontend: str, body: dict[str, Any]) -> Conversation:
    if frontend == "responses":
        conversation = _parse_responses(body)
    elif frontend == "chat":
        conversation = _parse_chat(body)
    elif frontend == "anthropic":
        return _parse_anthropic(body)
    else:
        raise ValueError(f"unsupported frontend: {frontend}")
    conversation.cache_options = {
        key: deepcopy(body[key])
        for key in ("prompt_cache_key", "prompt_cache_options", "prompt_cache_retention")
        if key in body
    }
    options = body.get("prompt_cache_options")
    if options is not None and (
        not isinstance(options, dict) or options.get("mode") not in (None, "implicit", "explicit")
    ):
        raise ValueError("prompt_cache_options must specify implicit or explicit mode")
    conversation.automatic_cache = not isinstance(options, dict) or options.get("mode") != "explicit"
    return conversation


def encode_tool_names(conversation: Conversation) -> dict[str, dict[str, str]]:
    """Flatten Responses namespaces with request-local, collision-checked wire identities."""
    calls = [block for turn in conversation.messages for block in turn["blocks"] if block.get("type") == "tool_call"]
    identities = {(tool.namespace, tool.name) for tool in conversation.tools}
    identities.update((call.get("namespace"), call["name"]) for call in calls)
    if any(ns is not None and (not isinstance(ns, str) or not ns) for ns, _ in identities):
        raise ValueError("Responses tool call namespace must be a nonempty string")
    reserved = {name for ns, name in identities if ns is None}
    encoded = {}
    names = {}
    for namespace, name in sorted((ns, name) for ns, name in identities if ns is not None):
        digest = hashlib.sha256(json.dumps([namespace, name], ensure_ascii=True).encode()).hexdigest()
        wire = f"ns_{digest[:56]}"
        suffix = 0
        while wire in reserved:
            suffix += 1
            wire = f"ns_{digest[:56]}_{suffix}"
        if len(wire) > 64:
            raise ValueError("Cannot allocate an unambiguous tool wire name")
        reserved.add(wire)
        encoded[(namespace, name)] = wire
        names[wire] = {"namespace": namespace, "name": name}
    for tool in conversation.tools:
        tool.name = encoded.get((tool.namespace, tool.name), tool.name)
    for call in calls:
        call["name"] = encoded.get((call.get("namespace"), call["name"]), call["name"])
    return names


def _chat_content(blocks: list[dict[str, Any]], fallback: str) -> str | list[dict[str, Any]]:
    return [dict(block) for block in blocks] if any("prompt_cache_breakpoint" in b for b in blocks) else fallback


def _claude_text(block: dict[str, Any]) -> dict[str, Any]:
    result = {"type": "text", "text": block["text"]}
    if "prompt_cache_breakpoint" in block:
        result["cache_control"] = {"type": "ephemeral"}
    return result


def _claude_result(result: dict[str, Any]) -> dict[str, Any]:
    blocks = result.get("content_blocks", [])
    return {
        "type": "tool_result",
        "tool_use_id": result["id"],
        "content": [_claude_text(block) for block in blocks]
        if any("prompt_cache_breakpoint" in b for b in blocks)
        else result["content"],
        "is_error": result["is_error"],
    }


def _apply_claude_cache(payload: dict[str, Any], conversation: Conversation) -> None:
    """Only translate representable text boundaries; OpenAI lifetimes and keys have no exact equivalent."""
    markers = []
    for block in payload.get("system", []) if isinstance(payload.get("system"), list) else []:
        if "cache_control" in block:
            markers.append(block)
    for message in payload["messages"]:
        for block in message["content"]:
            if block["type"] == "tool_result" and isinstance(block["content"], list):
                markers.extend(child for child in block["content"] if "cache_control" in child)
            if "cache_control" in block:
                markers.append(block)
    limit = 3 if conversation.automatic_cache else 4
    for block in markers[:-limit]:
        block.pop("cache_control")
    if conversation.automatic_cache:
        payload["cache_control"] = {"type": "ephemeral"}


def responses_cache_input(conversation: Conversation, store: OpaqueContextStore) -> list[dict[str, Any]]:
    """Retain Chat text-part boundaries when the caller supplied explicit OpenAI markers."""
    items = []
    for turn in conversation.messages:
        text = []
        for block in turn["blocks"]:
            kind = block["type"]
            if kind == "text":
                text.append({**block, "type": "input_text"})
        if text:
            items.append({"type": "message", "role": turn["role"], "content": text})
        for block in turn["blocks"]:
            if block["type"] == "tool_call":
                reasoning = store.get(block["id"])
                if reasoning is not None:
                    items.append(reasoning)
                items.append(
                    {
                        "type": "function_call",
                        "call_id": block["id"],
                        "name": block["name"],
                        "arguments": block["arguments"],
                    }
                )
            elif block["type"] == "tool_result":
                content = _chat_content(block.get("content_blocks", []), block["content"])
                if isinstance(content, list):
                    content = [{**part, "type": "input_text"} for part in content]
                items.append({"type": "function_call_output", "call_id": block["id"], "output": content})
    return items


def apply_claude_thinking(
    payload: dict[str, Any],
    effort: str | None,
    thinking: str | None,
    original_thinking: dict[str, Any] | None = None,
    original_output_config: dict[str, Any] | None = None,
) -> None:
    """Apply the Copilot Claude backend's separate thinking and effort controls."""
    if thinking == "off":
        payload["thinking"] = {"type": "disabled"}
        if effort and effort != "none":
            payload["output_config"] = {"effort": effort}
        return
    if effort == "none":
        payload["thinking"] = {"type": "disabled"}
        return
    if thinking == "on":
        payload["thinking"] = {"type": "adaptive"}
        if effort:
            payload["output_config"] = {"effort": effort}
        return
    if effort:
        payload["thinking"] = {"type": "adaptive"}
        payload["output_config"] = {"effort": effort}
        return
    if original_thinking:
        payload["thinking"] = original_thinking
        if original_output_config:
            payload["output_config"] = original_output_config


def _decode_arguments(arguments: str) -> dict[str, Any]:
    try:
        value = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {"input": arguments}
    return value if isinstance(value, dict) else {"input": arguments}


def _append_chat_message(messages: list[dict[str, Any]], message: dict[str, Any]) -> None:
    if (
        messages
        and message.get("role") == "assistant"
        and messages[-1].get("role") == "assistant"
        and (message.get("tool_calls") or messages[-1].get("tool_calls"))
    ):
        previous = messages[-1]
        if message.get("content"):
            if previous.get("content"):
                left, right = previous["content"], message["content"]
                previous["content"] = [*_text_blocks(left), *_text_blocks(right)]
            else:
                previous["content"] = message["content"]
        previous.setdefault("tool_calls", []).extend(message.get("tool_calls", []))
        return
    messages.append(message)


def to_gemini_payload(
    conversation: Conversation,
    model: ModelSpec,
    effort: str | None,
    store: OpaqueContextStore,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    if conversation.system:
        messages.append({"role": "system", "content": conversation.system})
    for turn in conversation.messages:
        role = turn["role"]
        text_blocks = [block for block in turn["blocks"] if block.get("type") == "text"]
        text = "".join(block["text"] for block in text_blocks)
        calls = []
        for block in turn["blocks"]:
            if block.get("type") != "tool_call":
                continue
            arguments = block["arguments"]
            if block.get("kind") == "custom":
                arguments = json.dumps({"input": arguments}, separators=(",", ":"))
            call = {
                "id": block["id"],
                "type": "function",
                "function": {"name": block["name"], "arguments": arguments},
            }
            context = store.get(block["id"])
            if context and isinstance(context.get("gemini_extra_content"), dict):
                call["extra_content"] = context["gemini_extra_content"]
            calls.append(call)
        if calls or text:
            _append_chat_message(
                messages,
                {
                    "role": role,
                    "content": _chat_content(text_blocks, text) or None,
                    **({"tool_calls": calls} if calls else {}),
                },
            )
        for block in turn["blocks"]:
            if block.get("type") == "tool_result":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": block["id"],
                        "content": _chat_content(block.get("content_blocks", []), block["content"]),
                    }
                )
    payload: dict[str, Any] = {
        "model": model.wire_model,
        "messages": messages,
        "stream": conversation.stream,
        **conversation.cache_options,
    }
    if conversation.stream:
        payload["stream_options"] = {"include_usage": True}
    if conversation.tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.schema,
                },
            }
            for tool in conversation.tools
        ]
    selected_effort = conversation.requested_effort or effort
    if selected_effort in model.efforts:
        payload["reasoning_effort"] = selected_effort
    if conversation.max_tokens:
        payload["max_tokens"] = min(conversation.max_tokens, model.max_output_tokens)
    return payload


def _append_anthropic_turn(messages: list[dict[str, Any]], role: str, blocks: list[dict[str, Any]]) -> None:
    if not blocks:
        return
    if messages and messages[-1]["role"] == role:
        messages[-1]["content"].extend(blocks)
    else:
        messages.append({"role": role, "content": blocks})


def to_claude_payload(
    conversation: Conversation,
    model: ModelSpec,
    effort: str | None,
    thinking: str | None,
    store: OpaqueContextStore,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    system_blocks = _text_blocks(conversation.system) if conversation.system else []
    for turn in conversation.messages:
        text_blocks = [_claude_text(block) for block in turn["blocks"] if block.get("type") == "text"]
        if turn["role"] in {"system", "developer"}:
            system_blocks.extend(text_blocks)
            continue
        calls = [block for block in turn["blocks"] if block.get("type") == "tool_call"]
        results = [block for block in turn["blocks"] if block.get("type") == "tool_result"]
        thinking_blocks = [
            dict(block) for block in turn["blocks"] if block.get("type") in {"thinking", "redacted_thinking"}
        ]
        if calls and not thinking_blocks:
            for call in calls:
                context = store.get(call["id"])
                stored = context.get("claude_thinking") if context else None
                if isinstance(stored, list):
                    thinking_blocks = [dict(block) for block in stored if isinstance(block, dict)]
                    break
        assistant_blocks = [*thinking_blocks, *text_blocks]
        assistant_blocks.extend(
            {
                "type": "tool_use",
                "id": call["id"],
                "name": call["name"],
                "input": {"input": call["arguments"]}
                if call.get("kind") == "custom"
                else _decode_arguments(call["arguments"]),
            }
            for call in calls
        )
        if turn["role"] == "assistant":
            _append_anthropic_turn(messages, "assistant", assistant_blocks)
        elif text_blocks:
            _append_anthropic_turn(messages, "user", text_blocks)
        if results:
            _append_anthropic_turn(
                messages,
                "user",
                [_claude_result(result) for result in results],
            )
    payload: dict[str, Any] = {
        "anthropic_version": "vertex-2023-10-16",
        "messages": messages,
        "max_tokens": min(conversation.max_tokens or 32768, model.max_output_tokens),
        "stream": conversation.stream,
    }
    if system_blocks:
        payload["system"] = (
            system_blocks
            if any("cache_control" in b for b in system_blocks)
            else "\n\n".join(b["text"] for b in system_blocks)
        )
    _apply_claude_cache(payload, conversation)
    if conversation.tools:
        payload["tools"] = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.schema,
            }
            for tool in conversation.tools
        ]
    effective = conversation.requested_effort or effort
    apply_claude_thinking(
        payload,
        effective,
        thinking,
        conversation.original_thinking,
        conversation.original_output_config,
    )
    return payload
