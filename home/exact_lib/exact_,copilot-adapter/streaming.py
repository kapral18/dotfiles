"""Translate Vertex streams into OpenAI and Anthropic wire formats."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterable, Iterator
from typing import Any, BinaryIO

from models import ModelSpec
from state import OpaqueContextStore

Event = dict[str, Any]


def _sse_events(response: BinaryIO) -> Iterator[tuple[str, dict[str, Any]]]:
    event_name = ""
    data_lines: list[str] = []
    while True:
        raw = response.readline()
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            if data_lines:
                data = "\n".join(data_lines)
                if data == "[DONE]":
                    yield "__done__", {}
                else:
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        payload = {"type": "error", "error": {"message": data}}
                    if isinstance(payload, dict):
                        yield event_name, payload
            event_name = ""
            data_lines = []
        elif line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())


def _usage(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    aliases = {
        "input_tokens": ("input_tokens", "prompt_tokens"),
        "output_tokens": ("output_tokens", "completion_tokens"),
    }
    result = {}
    for target, keys in aliases.items():
        for key in keys:
            if isinstance(value.get(key), int):
                result[target] = int(value[key])
                break
    return result


def _gemini_stream(
    response: BinaryIO,
    store: OpaqueContextStore,
) -> Iterator[Event]:
    calls: dict[str, dict[str, Any]] = {}
    calls_by_index: dict[int, dict[str, Any]] = {}
    finish_reason = "stop"
    saw_finish = False
    saw_done = False
    usage: dict[str, int] = {}
    yield {"type": "message_start"}
    for event_name, chunk in _sse_events(response):
        if event_name == "__done__":
            saw_done = True
            continue
        if chunk.get("type") == "error" or "error" in chunk:
            yield {"type": "error", "error": chunk.get("error", chunk)}
            return
        usage.update(_usage(chunk.get("usage")))
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        choice = choices[0] if isinstance(choices[0], dict) else {}
        delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
        content = delta.get("content")
        if isinstance(content, str) and content:
            yield {"type": "text_delta", "text": content}
        tool_calls = delta.get("tool_calls")
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                call_index = int(call.get("index", len(calls)))
                call_id = str(call.get("id") or "")
                indexed = calls_by_index.get(call_index)
                if not call_id and indexed:
                    call_id = str(indexed["id"])
                if not call_id:
                    call_id = f"call_{uuid.uuid4().hex}"
                function = call.get("function") if isinstance(call.get("function"), dict) else {}
                current = calls.get(call_id)
                if current is None:
                    current = {
                        "id": call_id,
                        "index": call_index,
                        "name": str(function.get("name", "")),
                        "arguments": "",
                    }
                    calls[call_id] = current
                    calls_by_index[call_index] = current
                    yield {
                        "type": "tool_start",
                        "index": current["index"],
                        "id": call_id,
                        "name": current["name"],
                    }
                calls_by_index.setdefault(call_index, current)
                if function.get("name") and not current["name"]:
                    current["name"] = str(function["name"])
                arguments = function.get("arguments")
                if isinstance(arguments, str) and arguments:
                    current["arguments"] += arguments
                    yield {
                        "type": "tool_delta",
                        "index": current["index"],
                        "id": call_id,
                        "arguments": arguments,
                    }
                extra = call.get("extra_content")
                if isinstance(extra, dict):
                    current["extra_content"] = extra
        if choice.get("finish_reason"):
            finish_reason = str(choice["finish_reason"])
            saw_finish = True
    if not saw_finish or not saw_done:
        yield {
            "type": "error",
            "error": {
                "type": "api_error",
                "message": "Vertex Gemini stream ended before its terminal event",
            },
        }
        return
    for current in calls.values():
        extra = current.get("extra_content")
        if isinstance(extra, dict):
            store.save(current["id"], {"gemini_extra_content": extra})
        yield {
            "type": "tool_stop",
            "index": current["index"],
            "id": current["id"],
            "name": current["name"],
            "arguments": current["arguments"],
        }
    yield {"type": "finish", "reason": finish_reason, "usage": usage}


def _gemini_json(payload: dict[str, Any], store: OpaqueContextStore) -> Iterator[Event]:
    yield {"type": "message_start"}
    usage = _usage(payload.get("usage"))
    choices = payload.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    if isinstance(message.get("content"), str) and message["content"]:
        yield {"type": "text_delta", "text": message["content"]}
    for index, call in enumerate(message.get("tool_calls", [])):
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else {}
        call_id = str(call.get("id") or f"call_{uuid.uuid4().hex}")
        arguments = str(function.get("arguments", ""))
        yield {"type": "tool_start", "index": index, "id": call_id, "name": str(function.get("name", ""))}
        if arguments:
            yield {"type": "tool_delta", "index": index, "id": call_id, "arguments": arguments}
        if isinstance(call.get("extra_content"), dict):
            store.save(call_id, {"gemini_extra_content": call["extra_content"]})
        yield {
            "type": "tool_stop",
            "index": index,
            "id": call_id,
            "name": str(function.get("name", "")),
            "arguments": arguments,
        }
    yield {"type": "finish", "reason": choice.get("finish_reason", "stop"), "usage": usage}


def _claude_events(
    events: Iterable[tuple[str, dict[str, Any]]],
    store: OpaqueContextStore,
) -> Iterator[Event]:
    thinking: dict[int, dict[str, Any]] = {}
    block_types: dict[int, str] = {}
    tool_ids: list[str] = []
    usage: dict[str, int] = {}
    finish_reason = "end_turn"
    saw_message_stop = False
    for event_name, event in events:
        kind = str(event.get("type") or event_name)
        if kind == "error":
            yield {"type": "error", "error": event.get("error", event)}
            return
        if kind == "message_start":
            message = event.get("message") if isinstance(event.get("message"), dict) else {}
            usage.update(_usage(message.get("usage")))
            yield {"type": "message_start"}
        elif kind == "content_block_start":
            index = int(event.get("index", 0))
            block = event.get("content_block") if isinstance(event.get("content_block"), dict) else {}
            block_type = block.get("type")
            if isinstance(block_type, str):
                block_types[index] = block_type
            if block_type == "text":
                yield {"type": "text_start", "index": index}
                if block.get("text"):
                    yield {"type": "text_delta", "index": index, "text": str(block["text"])}
            elif block_type in {"thinking", "redacted_thinking"}:
                thinking[index] = dict(block)
                yield {"type": "thinking_start", "index": index, "block": dict(block)}
            elif block_type == "tool_use":
                call_id = str(block.get("id") or f"call_{uuid.uuid4().hex}")
                tool_ids.append(call_id)
                yield {
                    "type": "tool_start",
                    "index": index,
                    "id": call_id,
                    "name": str(block.get("name", "")),
                }
                if block.get("input"):
                    yield {
                        "type": "tool_delta",
                        "index": index,
                        "id": call_id,
                        "arguments": json.dumps(block["input"], separators=(",", ":")),
                    }
        elif kind == "content_block_delta":
            index = int(event.get("index", 0))
            delta = event.get("delta") if isinstance(event.get("delta"), dict) else {}
            delta_type = delta.get("type")
            if delta_type == "text_delta":
                yield {"type": "text_delta", "index": index, "text": str(delta.get("text", ""))}
            elif delta_type == "input_json_delta":
                yield {
                    "type": "tool_delta",
                    "index": index,
                    "arguments": str(delta.get("partial_json", "")),
                }
            elif delta_type == "thinking_delta":
                thinking.setdefault(index, {"type": "thinking", "thinking": "", "signature": ""})
                thinking[index]["thinking"] = str(thinking[index].get("thinking", "")) + str(delta.get("thinking", ""))
                yield {"type": "thinking_delta", "index": index, "thinking": str(delta.get("thinking", ""))}
            elif delta_type == "signature_delta":
                thinking.setdefault(index, {"type": "thinking", "thinking": "", "signature": ""})
                thinking[index]["signature"] = str(thinking[index].get("signature", "")) + str(
                    delta.get("signature", "")
                )
                yield {"type": "signature_delta", "index": index, "signature": str(delta.get("signature", ""))}
        elif kind == "content_block_stop":
            index = int(event.get("index", 0))
            yield {
                "type": "tool_stop" if block_types.get(index) == "tool_use" else "block_stop",
                "index": index,
                "block_kind": block_types.get(index, ""),
            }
        elif kind == "message_delta":
            delta = event.get("delta") if isinstance(event.get("delta"), dict) else {}
            finish_reason = str(delta.get("stop_reason") or finish_reason)
            usage.update(_usage(event.get("usage")))
        elif kind == "message_stop":
            saw_message_stop = True
            blocks = [thinking[index] for index in sorted(thinking)]
            if blocks:
                for call_id in tool_ids:
                    store.save(call_id, {"claude_thinking": blocks})
            yield {"type": "finish", "reason": finish_reason, "usage": usage}
    if not saw_message_stop:
        yield {
            "type": "error",
            "error": {
                "type": "api_error",
                "message": "Vertex Claude stream ended before message_stop",
            },
        }


def canonical_events(
    backend: str,
    response: BinaryIO,
    *,
    stream: bool,
    store: OpaqueContextStore,
) -> Iterator[Event]:
    if backend == "gemini-chat":
        if stream:
            yield from _gemini_stream(response, store)
        else:
            payload = json.loads(response.read().decode("utf-8"))
            yield from _gemini_json(payload, store)
        return
    if stream:
        yield from _claude_events(_sse_events(response), store)
    else:
        payload = json.loads(response.read().decode("utf-8"))
        yield from _claude_json(payload, store)


def _claude_json(payload: dict[str, Any], store: OpaqueContextStore) -> Iterator[Event]:
    synthetic: list[tuple[str, dict[str, Any]]] = [
        (
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "usage": payload.get("usage", {}),
                },
            },
        )
    ]
    for index, block in enumerate(payload.get("content", [])):
        if not isinstance(block, dict):
            continue
        synthetic.append(
            (
                "content_block_start",
                {"type": "content_block_start", "index": index, "content_block": block},
            )
        )
        synthetic.append(("content_block_stop", {"type": "content_block_stop", "index": index}))
    synthetic.extend(
        [
            (
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": payload.get("stop_reason", "end_turn")},
                    "usage": payload.get("usage", {}),
                },
            ),
            ("message_stop", {"type": "message_stop"}),
        ]
    )
    yield from _claude_events(synthetic, store)


def _sse(payload: dict[str, Any], event: str | None = None) -> bytes:
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


def _chat_finish_reason(reason: object) -> str:
    return {
        "end_turn": "stop",
        "stop_sequence": "stop",
        "max_tokens": "length",
        "tool_use": "tool_calls",
    }.get(str(reason), str(reason))


def _anthropic_stop_reason(reason: object) -> str:
    return {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
    }.get(str(reason), str(reason))


def render_chat(events: Iterable[Event], model: ModelSpec) -> Iterator[bytes]:
    response_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    started = False
    tool_indices: dict[int, int] = {}
    for event in events:
        kind = event["type"]
        delta: dict[str, Any] = {}
        finish_reason = None
        usage = None
        if not started and kind not in {"message_start", "error"}:
            delta["role"] = "assistant"
            started = True
        if kind == "text_delta":
            delta["content"] = event["text"]
        elif kind == "tool_start":
            tool_indices[event["index"]] = len(tool_indices)
            delta["tool_calls"] = [
                {
                    "index": tool_indices[event["index"]],
                    "id": event["id"],
                    "type": "function",
                    "function": {"name": event["name"], "arguments": ""},
                }
            ]
        elif kind == "tool_delta":
            mapped = tool_indices.get(event["index"])
            if mapped is None:
                continue
            delta["tool_calls"] = [
                {
                    "index": mapped,
                    "function": {"arguments": event["arguments"]},
                }
            ]
        elif kind == "finish":
            finish_reason = _chat_finish_reason(event["reason"])
            raw_usage = event.get("usage", {})
            usage = {
                "prompt_tokens": raw_usage.get("input_tokens", 0),
                "completion_tokens": raw_usage.get("output_tokens", 0),
                "total_tokens": raw_usage.get("input_tokens", 0) + raw_usage.get("output_tokens", 0),
            }
        elif kind == "error":
            yield _sse({"error": event["error"]}, "error")
            return
        else:
            continue
        chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model.model_id,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        if usage is not None:
            chunk["usage"] = usage
        yield _sse(chunk)
    yield b"data: [DONE]\n\n"


def render_responses(
    events: Iterable[Event],
    model: ModelSpec,
    tool_kinds: dict[str, str],
) -> Iterator[bytes]:
    response_id = f"resp_{uuid.uuid4().hex}"
    message_id = f"msg_{uuid.uuid4().hex}"
    text = ""
    message_started = False
    message_output_index: int | None = None
    tools: dict[int, dict[str, Any]] = {}
    tool_output_indices: dict[int, int] = {}
    next_output_index = 0
    sequence = 0
    for event in events:
        kind = event["type"]
        if kind == "text_delta":
            if not message_started:
                message_output_index = next_output_index
                next_output_index += 1
                yield _sse(
                    {
                        "type": "response.output_item.added",
                        "sequence_number": sequence,
                        "output_index": message_output_index,
                        "item": {"id": message_id, "type": "message", "role": "assistant", "content": []},
                    }
                )
                sequence += 1
                message_started = True
            text += event["text"]
            yield _sse(
                {
                    "type": "response.output_text.delta",
                    "sequence_number": sequence,
                    "output_index": message_output_index,
                    "content_index": 0,
                    "item_id": message_id,
                    "delta": event["text"],
                }
            )
            sequence += 1
        elif kind == "tool_start":
            tool_output_indices[event["index"]] = next_output_index
            next_output_index += 1
            tool_kind = tool_kinds.get(event["name"], "function")
            item = {
                "id": f"fc_{uuid.uuid4().hex}",
                "type": "custom_tool_call" if tool_kind == "custom" else "function_call",
                "call_id": event["id"],
                "name": event["name"],
                "status": "in_progress",
                **({"input": ""} if tool_kind == "custom" else {"arguments": ""}),
            }
            tools[event["index"]] = item
            yield _sse(
                {
                    "type": "response.output_item.added",
                    "sequence_number": sequence,
                    "output_index": tool_output_indices[event["index"]],
                    "item": item,
                }
            )
            sequence += 1
        elif kind == "tool_delta":
            item = tools.get(event["index"])
            if not item:
                continue
            field = "input" if item["type"] == "custom_tool_call" else "arguments"
            item[field] += event["arguments"]
        elif kind == "tool_stop":
            item = tools.get(event["index"])
            if not item:
                continue
            if item["type"] == "custom_tool_call":
                try:
                    decoded = json.loads(item["input"])
                    if isinstance(decoded, dict) and isinstance(decoded.get("input"), str):
                        item["input"] = decoded["input"]
                except json.JSONDecodeError:
                    pass
                if item["input"]:
                    yield _sse(
                        {
                            "type": "response.custom_tool_call_input.delta",
                            "sequence_number": sequence,
                            "output_index": tool_output_indices[event["index"]],
                            "item_id": item["id"],
                            "delta": item["input"],
                        }
                    )
                    sequence += 1
            item["status"] = "completed"
            yield _sse(
                {
                    "type": "response.output_item.done",
                    "sequence_number": sequence,
                    "output_index": tool_output_indices[event["index"]],
                    "item": item,
                }
            )
            sequence += 1
        elif kind == "finish":
            if message_started:
                yield _sse(
                    {
                        "type": "response.output_item.done",
                        "sequence_number": sequence,
                        "output_index": message_output_index,
                        "item": {
                            "id": message_id,
                            "type": "message",
                            "role": "assistant",
                            "status": "completed",
                            "content": [{"type": "output_text", "text": text, "annotations": []}],
                        },
                    }
                )
                sequence += 1
            raw_usage = event.get("usage", {})
            yield _sse(
                {
                    "type": "response.completed",
                    "sequence_number": sequence,
                    "response": {
                        "id": response_id,
                        "object": "response",
                        "status": "completed",
                        "model": model.model_id,
                        "output": [],
                        "usage": {
                            "input_tokens": raw_usage.get("input_tokens", 0),
                            "output_tokens": raw_usage.get("output_tokens", 0),
                            "total_tokens": raw_usage.get("input_tokens", 0) + raw_usage.get("output_tokens", 0),
                        },
                    },
                }
            )
        elif kind == "error":
            yield _sse({"type": "response.failed", "response": {"error": event["error"]}})
            return


def render_anthropic(events: Iterable[Event], model: ModelSpec) -> Iterator[bytes]:
    message_id = f"msg_{uuid.uuid4().hex}"
    index_map: dict[tuple[str, int], int] = {}
    next_index = 0
    started = False
    closed: set[int] = set()
    usage: dict[str, int] = {}

    def ensure_start() -> bytes:
        return _sse(
            {
                "type": "message_start",
                "message": {
                    "id": message_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": model.model_id,
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            },
            "message_start",
        )

    for event in events:
        kind = event["type"]
        if not started and kind != "error":
            yield ensure_start()
            started = True
        source_index = int(event.get("index", 0))
        if kind in {"text_start", "text_delta"}:
            key = ("text", source_index)
            if key not in index_map:
                index_map[key] = next_index
                next_index += 1
                yield _sse(
                    {
                        "type": "content_block_start",
                        "index": index_map[key],
                        "content_block": {"type": "text", "text": ""},
                    },
                    "content_block_start",
                )
            if kind == "text_delta":
                yield _sse(
                    {
                        "type": "content_block_delta",
                        "index": index_map[key],
                        "delta": {"type": "text_delta", "text": event["text"]},
                    },
                    "content_block_delta",
                )
        elif kind == "thinking_start":
            key = ("thinking", source_index)
            index_map[key] = next_index
            next_index += 1
            block_type = event["block"].get("type", "thinking")
            initial = {"type": block_type}
            if block_type == "thinking":
                initial.update({"thinking": "", "signature": ""})
            else:
                initial["data"] = event["block"].get("data", "")
            yield _sse(
                {"type": "content_block_start", "index": index_map[key], "content_block": initial},
                "content_block_start",
            )
        elif kind in {"thinking_delta", "signature_delta"}:
            key = ("thinking", source_index)
            if key not in index_map:
                continue
            delta = (
                {"type": "thinking_delta", "thinking": event["thinking"]}
                if kind == "thinking_delta"
                else {"type": "signature_delta", "signature": event["signature"]}
            )
            yield _sse(
                {"type": "content_block_delta", "index": index_map[key], "delta": delta},
                "content_block_delta",
            )
        elif kind == "tool_start":
            key = ("tool", source_index)
            index_map[key] = next_index
            next_index += 1
            yield _sse(
                {
                    "type": "content_block_start",
                    "index": index_map[key],
                    "content_block": {
                        "type": "tool_use",
                        "id": event["id"],
                        "name": event["name"],
                        "input": {},
                    },
                },
                "content_block_start",
            )
        elif kind == "tool_delta":
            key = ("tool", source_index)
            if key not in index_map:
                continue
            yield _sse(
                {
                    "type": "content_block_delta",
                    "index": index_map[key],
                    "delta": {"type": "input_json_delta", "partial_json": event["arguments"]},
                },
                "content_block_delta",
            )
        elif kind in {"block_stop", "tool_stop"}:
            if kind == "tool_stop":
                source_keys = [("tool", source_index)]
            else:
                block_kind = event.get("block_kind")
                mapped_kind = {
                    "thinking": "thinking",
                    "redacted_thinking": "thinking",
                    "text": "text",
                    "tool_use": "tool",
                }.get(block_kind)
                source_keys = [(mapped_kind, source_index)] if mapped_kind else []
            candidates = [index_map[key] for key in source_keys if key in index_map]
            for target_index in candidates:
                if target_index not in closed:
                    yield _sse(
                        {"type": "content_block_stop", "index": target_index},
                        "content_block_stop",
                    )
                    closed.add(target_index)
        elif kind == "finish":
            usage = event.get("usage", {})
            reason = _anthropic_stop_reason(event["reason"])
            for target_index in sorted(set(index_map.values())):
                if target_index not in closed:
                    yield _sse(
                        {"type": "content_block_stop", "index": target_index},
                        "content_block_stop",
                    )
                    closed.add(target_index)
            yield _sse(
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": reason, "stop_sequence": None},
                    "usage": {"output_tokens": usage.get("output_tokens", 0)},
                },
                "message_delta",
            )
            yield _sse({"type": "message_stop"}, "message_stop")
        elif kind == "error":
            error = event["error"]
            if not isinstance(error, dict):
                error = {"type": "api_error", "message": str(error)}
            yield _sse({"type": "error", "error": error}, "error")
            return


def collect_response(events: Iterable[Event]) -> dict[str, Any]:
    result: dict[str, Any] = {"text": "", "tools": [], "thinking": [], "reason": "stop", "usage": {}}
    tools: dict[int, dict[str, Any]] = {}
    thinking: dict[int, dict[str, Any]] = {}
    for event in events:
        kind = event["type"]
        if kind == "text_delta":
            result["text"] += event["text"]
        elif kind == "tool_start":
            tools[event["index"]] = {
                "id": event["id"],
                "name": event["name"],
                "arguments": "",
            }
        elif kind == "tool_delta" and event["index"] in tools:
            tools[event["index"]]["arguments"] += event["arguments"]
        elif kind == "thinking_start":
            thinking[event["index"]] = dict(event["block"])
        elif kind == "thinking_delta" and event["index"] in thinking:
            thinking[event["index"]]["thinking"] = str(thinking[event["index"]].get("thinking", "")) + event["thinking"]
        elif kind == "signature_delta" and event["index"] in thinking:
            thinking[event["index"]]["signature"] = (
                str(thinking[event["index"]].get("signature", "")) + event["signature"]
            )
        elif kind == "finish":
            result["reason"] = event["reason"]
            result["usage"] = event.get("usage", {})
        elif kind == "error":
            raise RuntimeError(str(event["error"]))
    result["tools"] = [tools[index] for index in sorted(tools)]
    result["thinking"] = [thinking[index] for index in sorted(thinking)]
    return result


def render_json(
    frontend: str,
    result: dict[str, Any],
    model: ModelSpec,
    tool_kinds: dict[str, str],
) -> dict[str, Any]:
    usage = result["usage"]
    if frontend == "chat":
        tool_calls = [
            {
                "id": tool["id"],
                "type": "function",
                "function": {"name": tool["name"], "arguments": tool["arguments"]},
            }
            for tool in result["tools"]
        ]
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model.model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result["text"] or None,
                        **({"tool_calls": tool_calls} if tool_calls else {}),
                    },
                    "finish_reason": "tool_calls" if tool_calls else _chat_finish_reason(result["reason"]),
                }
            ],
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
        }
    if frontend == "anthropic":
        content = [*result["thinking"]]
        if result["text"]:
            content.append({"type": "text", "text": result["text"]})
        content.extend(
            {
                "type": "tool_use",
                "id": tool["id"],
                "name": tool["name"],
                "input": _json_object(tool["arguments"]),
            }
            for tool in result["tools"]
        )
        return {
            "id": f"msg_{uuid.uuid4().hex}",
            "type": "message",
            "role": "assistant",
            "model": model.model_id,
            "content": content,
            "stop_reason": "tool_use" if result["tools"] else _anthropic_stop_reason(result["reason"]),
            "stop_sequence": None,
            "usage": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        }
    output = []
    if result["text"]:
        output.append(
            {
                "id": f"msg_{uuid.uuid4().hex}",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": result["text"], "annotations": []}],
            }
        )
    for tool in result["tools"]:
        kind = tool_kinds.get(tool["name"], "function")
        output.append(
            {
                "id": f"fc_{uuid.uuid4().hex}",
                "type": "custom_tool_call" if kind == "custom" else "function_call",
                "call_id": tool["id"],
                "name": tool["name"],
                **(
                    {"input": _custom_input(tool["arguments"])}
                    if kind == "custom"
                    else {"arguments": tool["arguments"]}
                ),
            }
        )
    return {
        "id": f"resp_{uuid.uuid4().hex}",
        "object": "response",
        "status": "completed",
        "model": model.model_id,
        "output": output,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        },
    }


def _json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {"input": value}
    return parsed if isinstance(parsed, dict) else {"input": value}


def _custom_input(value: str) -> str:
    parsed = _json_object(value)
    return parsed["input"] if isinstance(parsed.get("input"), str) else value
