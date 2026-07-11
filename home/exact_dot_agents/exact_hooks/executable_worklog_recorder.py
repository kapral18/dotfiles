#!/usr/bin/env python3
"""Append compact hook events to the active topic worklog."""

from __future__ import annotations

import json
import os
import sys

from hook_common import bounded_text, emit, read_payload, session_key, topic_paths, utc_now

QUEUE_DIR_NAME = ".worklog-queue-v1"
FALLBACK_ERROR_MAX_BYTES = 64 * 1024


def command_from(payload: dict) -> str:
    command = payload.get("command")
    if isinstance(command, str):
        return command

    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or tool_input.get("path") or "")

    return ""


def _record_fallback_error(spec_dir, key: str, error: Exception) -> None:
    queue_dir = spec_dir / QUEUE_DIR_NAME / key
    queue_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = queue_dir / "dispatcher-errors.jsonl"
    try:
        if path.stat().st_size >= FALLBACK_ERROR_MAX_BYTES:
            return
    except OSError:
        pass
    line = json.dumps({"ts": utc_now(), "code": "recorder_failed", "message": str(error)[:1000]}, sort_keys=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (line + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)


def _record(spec_dir, key: str, topic: str, worklog_path, entry: dict) -> str:
    try:
        import worklog_queue

        receipt = worklog_queue.enqueue(spec_dir, key, topic, worklog_path, entry, start_worker=False)
        worklog_queue.run_worker(receipt.queue_dir)
    except Exception as err:
        try:
            import worklog_queue

            worklog_queue.record_error(spec_dir, key, "recorder_failed", str(err))
        except Exception:
            try:
                _record_fallback_error(spec_dir, key, err)
            except OSError:
                pass
        return str(err)
    return ""


def main() -> None:
    if os.environ.get("AGENT_WORKLOG_DISPATCHED") == "1":
        try:
            os.setsid()
        except OSError:
            pass
    payload = read_payload()
    workspace, topic, spec_path, worklog_path = topic_paths(payload)
    key = session_key(payload) or f"topic-{topic}"
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
        "output": bounded_text(
            payload.get("output") or payload.get("tool_output") or payload.get("tool_response"), limit=1200
        ),
        "error": bounded_text(payload.get("error_message"), limit=600),
    }
    errors = spec_path.parent / QUEUE_DIR_NAME / key / "errors.jsonl"
    if errors.exists():
        print(f"[agent-worklog] prior asynchronous worklog failure: {errors}", file=sys.stderr)
    error = _record(
        spec_path.parent,
        key,
        topic,
        worklog_path,
        {k: v for k, v in entry.items() if v not in (None, "")},
    )
    if error:
        message = f"worklog queue failed for {key}: {error}"
        print(f"[agent-worklog] {message}", file=sys.stderr)
        emit({"worklog_error": message})
        return
    emit({})


if __name__ == "__main__":
    main()
