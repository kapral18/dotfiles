#!/usr/bin/env python3
"""Append compact hook events to the active topic worklog."""

from __future__ import annotations

from hook_common import append_jsonl, bounded_text, emit, read_payload, topic_paths, utc_now

MAX_WORKLOG_LINES = 200


def command_from(payload: dict) -> str:
    command = payload.get("command")
    if isinstance(command, str):
        return command

    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or tool_input.get("path") or "")

    return ""


def main() -> None:
    payload = read_payload()
    workspace, topic, _, worklog_path = topic_paths(payload)
    entry = {
        "ts": utc_now(),
        "workspace": str(workspace),
        "topic": topic,
        "event": payload.get("hook_event_name"),
        "model": payload.get("model"),
        "tool_name": payload.get("tool_name"),
        "command": command_from(payload),
        "duration": payload.get("duration"),
        "status": payload.get("status"),
        "output": bounded_text(payload.get("output") or payload.get("tool_output"), limit=1200),
        "error": bounded_text(payload.get("error_message"), limit=600),
    }
    append_jsonl(worklog_path, {k: v for k, v in entry.items() if v not in (None, "")}, max_lines=MAX_WORKLOG_LINES)
    emit({})


if __name__ == "__main__":
    main()
