"""Request normalization and Vertex backend payload construction."""

from __future__ import annotations

import json
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

    @property
    def tool_kinds(self) -> dict[str, str]:
        return {tool.name: tool.kind for tool in self.tools}


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
            blocks.append({"type": "text", "text": str(item.get("text", ""))})
    return blocks


def _tool_output_text(output: object) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return "\n".join(block["text"] for block in _text_blocks(output))
    return json.dumps(output, separators=(",", ":"))


def _parse_tools(tools: object, frontend: str) -> list[Tool]:
    if not isinstance(tools, list):
        return []
    parsed = []
    for item in tools:
        if not isinstance(item, dict):
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
        if kind == "message":
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
        if role in {"system", "developer"}:
            conversation.system = "\n\n".join(
                part for part in (conversation.system, _tool_output_text(message.get("content", ""))) if part
            )
            continue
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
        return _parse_responses(body)
    if frontend == "chat":
        return _parse_chat(body)
    if frontend == "anthropic":
        return _parse_anthropic(body)
    raise ValueError(f"unsupported frontend: {frontend}")


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
        previous["content"] = None
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
        text = "".join(block["text"] for block in turn["blocks"] if block.get("type") == "text")
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
                {"role": role, "content": None if calls else text or None, **({"tool_calls": calls} if calls else {})},
            )
        for block in turn["blocks"]:
            if block.get("type") == "tool_result":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": block["id"],
                        "content": block["content"],
                    }
                )
    payload: dict[str, Any] = {
        "model": model.wire_model,
        "messages": messages,
        "stream": conversation.stream,
    }
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
    store: OpaqueContextStore,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    for turn in conversation.messages:
        text_blocks = [
            {"type": "text", "text": block["text"]} for block in turn["blocks"] if block.get("type") == "text"
        ]
        calls = [block for block in turn["blocks"] if block.get("type") == "tool_call"]
        results = [block for block in turn["blocks"] if block.get("type") == "tool_result"]
        thinking = [dict(block) for block in turn["blocks"] if block.get("type") in {"thinking", "redacted_thinking"}]
        if calls and not thinking:
            for call in calls:
                context = store.get(call["id"])
                stored = context.get("claude_thinking") if context else None
                if isinstance(stored, list):
                    thinking = [dict(block) for block in stored if isinstance(block, dict)]
                    break
        assistant_blocks = [*thinking, *text_blocks]
        assistant_blocks.extend(
            {
                "type": "tool_use",
                "id": call["id"],
                "name": call["name"],
                "input": _decode_arguments(call["arguments"]),
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
                [
                    {
                        "type": "tool_result",
                        "tool_use_id": result["id"],
                        "content": result["content"],
                        "is_error": result["is_error"],
                    }
                    for result in results
                ],
            )
    payload: dict[str, Any] = {
        "anthropic_version": "vertex-2023-10-16",
        "messages": messages,
        "max_tokens": min(conversation.max_tokens or 32768, model.max_output_tokens),
        "stream": conversation.stream,
    }
    if conversation.system:
        payload["system"] = conversation.system
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
    if effective == "none":
        payload["thinking"] = {"type": "disabled"}
    elif effective:
        payload["thinking"] = {"type": "adaptive"}
        payload["output_config"] = {"effort": effective}
    elif conversation.original_thinking:
        payload["thinking"] = conversation.original_thinking
        if conversation.original_output_config:
            payload["output_config"] = conversation.original_output_config
    return payload
