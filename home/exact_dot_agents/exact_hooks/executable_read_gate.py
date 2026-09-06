#!/usr/bin/env python3
"""Hash-gated re-reads: never pay twice for bytes that are already in this context.

Whole-file reads are the right default (an edit decided on a stale or partial view costs
more than the read), so this gate never touches a first read or a targeted one. It only
refuses a *second* whole-file read of the same path when the bytes are byte-identical to
what an earlier read in the same context returned, and points at the earlier read instead.
When the file changed, the read is allowed and a one-line "changed since your read" note
rides along, which is the freshness signal that used to depend on memory.

PreToolUse decides; PostToolUse records. The ledger lives next to the topic spec as
`.reads-<context>.json`, keyed by the child `agent_id` when the call comes from a subagent
(its own context) and by the session otherwise, so a child never inherits the parent's ledger. Every failure path allows the
read: a wrong refusal costs a wasted turn, a wrong allowance costs a cached re-read.

A ledger entry only proves a read happened. Before refusing, the gate re-opens the
transcript, finds that read's recorded result, and checks it reproduces the file on disk
(Claude Code: `toolUseResult.file.content` for Read, `toolUseResult.stdout` for Bash; a
`persistedOutputPath` means the context only holds a preview). Missing, truncated, or
garbled history allows the read silently (the reason is kept in the ledger entry). Compaction empties the context, so
the ledger also carries the reinforcement module's compaction epoch; entries from an
earlier epoch never block.

Escape hatches: `Read` with offset/limit, `sed -n`/`head`/`tail` in Bash, or
`AGENT_READ_GATE=off`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from hook_common import emit, read_payload, session_key, topic_paths

try:
    import reinforcement
except ImportError:  # pragma: no cover - deployed alongside; without it there is no epoch
    reinforcement = None

DISABLE_ENV = "AGENT_READ_GATE"
HARNESS_ENV = "AGENT_HOOK_HARNESS"
# Cursor names its events after the moment, not the tool; beforeReadFile fires after the read
# succeeded and gates delivery, so it is both the record and the decision point.
CURSOR_EVENTS = {"beforeReadFile", "beforeShellExecution", "afterShellExecution", "stop"}
COMPACTION_SHRINK_RATIO = 0.75
DISABLE_VALUES = {"0", "false", "no", "off", "disabled"}
READ_TOOLS = {"Read", "read", "view", "read_file", "view_file", "ReadFile"}
TARGETED_READ_KEYS = ("offset", "limit", "view_range", "start_line", "end_line", "StartLine", "EndLine", "range")
SHELL_TOOLS = {"Bash", "shell", "exec_command", "Shell", "bash", "run_terminal_cmd"}
MAX_HASH_BYTES = 32 * 1024 * 1024
LEDGER_MAX_ENTRIES = 400
# A whole-file shell read: one command, one path, no pipes, redirects, or chaining.
WHOLE_SHELL_READ = re.compile(r"^\s*(?:cat|nl\s+-ba|nl)\s+(?:-[A-Za-z]+\s+)*(['\"]?)([^\s|;&<>'\"]+)\1\s*$")


def disabled() -> bool:
    return os.environ.get(DISABLE_ENV, "").strip().lower() in DISABLE_VALUES


def context_key(payload: dict[str, Any]) -> str:
    """Ledger key for the context whose bytes are at stake.

    Claude Code passes `agent_id` only for a child agent's tool calls (probed 2026-09-06: the
    child's `transcript_path` is still the parent's file), so a child gets its own ledger and
    never inherits what the parent has read. "" disables gating.
    """
    agent_id = payload.get("agent_id")
    if isinstance(agent_id, str) and agent_id:
        return f"agent-{agent_id}"
    key = session_key(payload)
    return f"session-{key}" if key else ""


def whole_read_target(payload: dict[str, Any]) -> str | None:
    tool = str(payload.get("tool_name") or payload.get("tool") or "")
    tool_input = payload.get("tool_input") or payload.get("arguments") or {}
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except ValueError:
            return None
    if not isinstance(tool_input, dict):
        return None
    if tool in READ_TOOLS:
        # Any ranged read is targeted: Claude offset/limit, Copilot view_range, Antigravity
        # StartLine/EndLine, generic start/end line keys.
        if any(tool_input.get(key) for key in TARGETED_READ_KEYS):
            return None
        path = tool_input.get("file_path") or tool_input.get("path")
        return str(path) if isinstance(path, str) and path else None
    if tool in SHELL_TOOLS or not tool:
        command = tool_input.get("command") or tool_input.get("cmd") or tool_input.get("CommandLine") or ""
        if isinstance(command, list):
            command = " ".join(str(part) for part in command)
        match = WHOLE_SHELL_READ.match(str(command))
        if not match:
            return None
        return os.path.expanduser(match.group(2))
    return None


def file_hash(path: str) -> str | None:
    try:
        target = Path(path)
        if not target.is_file() or target.stat().st_size > MAX_HASH_BYTES:
            return None
        return hashlib.sha256(target.read_bytes()).hexdigest()
    except OSError:
        return None


def ledger_path(spec_dir: Path, key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", key)[:80]
    return spec_dir / f".reads-{safe}.json"


def load_ledger(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_ledger(path: Path, ledger: dict[str, dict[str, Any]]) -> None:
    if len(ledger) > LEDGER_MAX_ENTRIES:
        oldest = sorted(ledger.items(), key=lambda item: item[1].get("ts", 0))[: len(ledger) - LEDGER_MAX_ENTRIES]
        for key, _ in oldest:
            ledger.pop(key, None)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def compaction_epoch(spec_dir: Path, payload: dict[str, Any]) -> int:
    if reinforcement is None:
        return 0
    key = session_key(payload)
    if not key:
        return 0
    state = reinforcement.load_state(spec_dir, key)
    return int(state.get("compactions", 0) or 0)


def _allow(event: str, note: str = "") -> dict[str, Any]:
    if not note:
        return {}
    return {
        "additional_context": note,
        "hookSpecificOutput": {"hookEventName": event, "additionalContext": note},
    }


def _block(reason: str) -> dict[str, Any]:
    # Claude Code honours either shape; Codex reads hookSpecificOutput.permissionDecision.
    return {
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }


def _disk_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _same_text(recorded: object, disk: str) -> bool:
    if not isinstance(recorded, str):
        return False
    return recorded.rstrip("\n") == disk.rstrip("\n")


_NUMBERED_LINE = re.compile(r"^\s*\d+(?:\t|→|:)")
_OMP_HEADER = re.compile(r"^\[[^\]\n]*#[0-9a-f]+\]\n")


def _strip_line_numbers(text: str) -> str:
    """Undo read-tool decoration: Claude/Cursor `N\t`, `N→`, OMP `N:` line numbers (only when
    every non-empty line carries one, so real `10:30` content survives) and OMP's `[path#hash]`
    header line."""
    text = _OMP_HEADER.sub("", text, count=1)
    lines = text.split("\n")
    body = [line for line in lines if line.strip()]
    if body and all(_NUMBERED_LINE.match(line) for line in body):
        return "\n".join(_NUMBERED_LINE.sub("", line, count=1) for line in lines)
    return text


def response_reproduces_file(response: object, path: str) -> bool:
    """Does a PostToolUse `tool_response` hold the whole file? Unknown shapes count as yes;
    the transcript check at the next read is the authority."""
    disk = _disk_text(path)
    if disk is None:
        return False
    if isinstance(response, dict):
        if response.get("persistedOutputPath"):
            return False
        file_block = response.get("file")
        if isinstance(file_block, dict) and isinstance(file_block.get("content"), str):
            return _same_text(_strip_line_numbers(file_block["content"]), disk)
        if isinstance(response.get("stdout"), str):
            return _same_text(response["stdout"], disk)
        return True
    if isinstance(response, str):
        if response.startswith("<persisted-output>"):
            return False
        stripped = _strip_line_numbers(response)
        # Shell wrappers (Codex exec output) frame the file text with headers.
        return _same_text(stripped, disk) or disk.rstrip("\n") in stripped
    return True


def transcript_candidates(payload: dict[str, Any]) -> list[Path]:
    transcript = payload.get("transcript_path")
    conversation = payload.get("conversation_id")
    if (
        isinstance(conversation, str)
        and conversation
        and not (isinstance(transcript, str) and transcript.endswith(".db"))
    ):
        # Cursor keeps tool results in a per-conversation sqlite store, not in the transcript
        # jsonl it names (probed 2026-09-06 with a sentinel read).
        config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        stores = sorted(Path(config_home).glob(f"cursor/chats/*/{conversation}/store.db"))
        if stores:
            return stores + ([Path(transcript)] if isinstance(transcript, str) and transcript else [])
    if not isinstance(transcript, str) or not transcript:
        return []
    parent = Path(transcript)
    agent_id = payload.get("agent_id")
    if isinstance(agent_id, str) and agent_id:
        # Claude Code passes the parent's transcript for a child call; the child's own file
        # sits beside it under <session>/subagents/agent-<id>.jsonl.
        return [parent.with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl", parent]
    return [parent]


def _result_text_from_row(row: dict[str, Any], tool_use_id: str) -> tuple[bool, str | None]:
    """(found, text) for the tool result with `tool_use_id` in one transcript row; text None = incomplete."""
    result = row.get("toolUseResult")
    content = (row.get("message") or {}).get("content")
    blocks = content if isinstance(content, list) else []
    matched = any(
        isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") == tool_use_id for b in blocks
    )
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    if (
        not matched
        and payload.get("type") in ("function_call_output", "custom_tool_call_output")
        and payload.get("call_id") == tool_use_id
    ):
        texts = _texts_from_output(payload.get("output"))
        return True, "\n".join(texts) if texts else None
    message = row.get("message") if isinstance(row.get("message"), dict) else {}
    if not matched and message.get("role") == "toolResult" and message.get("toolCallId") == tool_use_id:
        # Pi / OMP session rows: raw file text (read) or stdout (bash) in text blocks.
        texts = [
            b.get("text", "") for b in (message.get("content") or []) if isinstance(b, dict) and b.get("type") == "text"
        ]
        return True, "\n".join(texts) if texts else None
    if not matched:
        return False, None
    if isinstance(result, dict):
        if result.get("persistedOutputPath"):
            return True, None
        file_block = result.get("file")
        if isinstance(file_block, dict) and isinstance(file_block.get("content"), str):
            return True, file_block["content"]
        if isinstance(result.get("stdout"), str):
            return True, result["stdout"]
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") == tool_use_id:
            raw = b.get("content")
            text = (
                raw
                if isinstance(raw, str)
                else "".join(x.get("text", "") for x in raw if isinstance(x, dict))
                if isinstance(raw, list)
                else ""
            )
            if text.startswith("<persisted-output>"):
                return True, None
            return True, text
    return True, None


def _texts_from_output(output: object) -> list[str]:
    """Flatten a recorded tool output to plain text. Codex code mode wraps the command's
    stdout in a JSON object inside an input_text block, so JSON-looking blocks are unwrapped."""
    if isinstance(output, str):
        blocks: list[object] = [output]
    elif isinstance(output, dict):
        blocks = [output.get("output")]
    elif isinstance(output, list):
        blocks = [b.get("text") if isinstance(b, dict) else b for b in output]
    else:
        return []
    texts: list[str] = []
    for block in blocks:
        if not isinstance(block, str):
            continue
        candidate = block.strip()
        if candidate.startswith("{"):
            try:
                parsed = json.loads(candidate)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict) and isinstance(parsed.get("output"), str):
                texts.append(parsed["output"])
                continue
        texts.append(block)
    return texts


def _row_output_texts(row: dict[str, Any]) -> list[str]:
    """Every tool-output text in one transcript row, whatever the harness shape."""
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    if payload.get("type") in ("function_call_output", "custom_tool_call_output"):
        return _texts_from_output(payload.get("output"))
    data = row.get("data") if isinstance(row.get("data"), dict) else {}
    if row.get("type") == "tool.execution_complete":
        # Copilot session events: the tool result content, verbatim (probed 2026-09-06).
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        return [t for t in (result.get("content"), result.get("detailedContent")) if isinstance(t, str)]
    result = row.get("toolUseResult")
    texts: list[str] = []
    message = row.get("message") if isinstance(row.get("message"), dict) else {}
    if message.get("role") == "toolResult":
        texts.extend(
            b.get("text", "") for b in (message.get("content") or []) if isinstance(b, dict) and b.get("type") == "text"
        )
    if isinstance(result, dict) and not result.get("persistedOutputPath"):
        file_block = result.get("file")
        if isinstance(file_block, dict) and isinstance(file_block.get("content"), str):
            texts.append(file_block["content"])
        if isinstance(result.get("stdout"), str):
            texts.append(result["stdout"])
    return texts


def _row_ts(row: dict[str, Any]) -> float | None:
    value = row.get("timestamp")
    if isinstance(value, (int, float)):
        return float(value) / (1000.0 if value > 1e12 else 1.0)
    if isinstance(value, str):
        try:
            from datetime import datetime

            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def history_contains(payload: dict[str, Any], path: str, since: float) -> bool:
    """Content fallback: some tool output recorded at/after `since` reproduces the file.

    Codex code mode hands hooks an inner `exec-…` id while the rollout stores the outer
    `call_…`, so id matching fails there; the file text itself is the evidence."""
    disk = _disk_text(path)
    if disk is None:
        return False
    needle = disk.rstrip("\n")
    if not needle:
        return False
    for transcript in transcript_candidates(payload):
        if transcript.suffix == ".db":
            if _store_db_contains(transcript, needle):
                return True
            continue
        found = False
        try:
            with transcript.open(encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if "compaction_complete" in line:
                        try:
                            row = json.loads(line)
                        except ValueError:
                            continue
                        ts = _row_ts(row)
                        if "compaction_complete" in str(row.get("type")) and (ts is None or ts >= since - 5):
                            # Copilot compacted after that read: the bytes left the live context.
                            return False
                        continue
                    if not any(marker in line for marker in _RESULT_LINE_MARKERS):
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    ts = _row_ts(row)
                    if ts is not None and ts < since - 5:
                        continue
                    for text in _row_output_texts(row):
                        if needle in _strip_line_numbers(text):
                            found = True
        except OSError:
            continue
        if found:
            return True
    return False


# Cheap pre-filter before JSON parsing: Claude, Codex, Pi/OMP, and Copilot result rows.
_RESULT_LINE_MARKERS = ("output", "toolUseResult", "toolResult", "execution_complete")


def _store_db_contains(path: Path, needle: str) -> bool:
    """Cursor `store.db`: JSON blobs carry {role: "tool", content: [{type: "tool-result",
    result: "<verbatim file>"}]}; the rest are protobuf, so raw bytes are the fallback."""
    import sqlite3

    raw = needle.encode("utf-8")
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            for (data,) in conn.execute("select data from blobs"):
                if not isinstance(data, (bytes, bytearray)):
                    continue
                if data[:1] == b"{":
                    try:
                        obj = json.loads(data.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        obj = None
                    if isinstance(obj, dict) and obj.get("role") == "tool":
                        for block in obj.get("content") or []:
                            if isinstance(block, dict) and isinstance(block.get("result"), str):
                                if needle in _strip_line_numbers(block["result"]):
                                    return True
                        continue
                if raw in data:
                    return True
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    return False


def history_intact(payload: dict[str, Any], tool_use_id: str, path: str) -> tuple[bool, str]:
    """Is the earlier read's recorded result present in history and equal to the file on disk?"""
    if not tool_use_id:
        return False, "the earlier read left no tool id to verify"
    disk = _disk_text(path)
    if disk is None:
        return False, "the file is unreadable"
    for transcript in transcript_candidates(payload):
        try:
            with transcript.open(encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if tool_use_id not in line:
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    found, text = _result_text_from_row(row, tool_use_id)
                    if not found:
                        continue
                    if text is None:
                        return False, "history holds only a truncated preview of that read"
                    stripped = _strip_line_numbers(text)
                    if _same_text(stripped, disk) or disk.rstrip("\n") in stripped:
                        return True, ""
                    return False, "the copy in history does not match the file"
        except OSError:
            continue
    return False, "that read is no longer found in history"


def decide(ledger: dict[str, dict[str, Any]], path: str, digest: str, epoch: int, now: float) -> tuple[str, str]:
    """Pure decision: ("block"|"allow"|"changed", detail)."""
    entry = ledger.get(path)
    if not isinstance(entry, dict) or not entry.get("sha256"):
        return "allow", ""
    if int(entry.get("epoch", 0) or 0) != epoch:
        return "allow", ""
    when = time.strftime("%H:%M", time.localtime(float(entry.get("ts", now))))
    if entry["sha256"] == digest:
        return "block", when
    return "changed", when


def handle_pre(payload: dict[str, Any], event: str) -> dict[str, Any]:
    key = context_key(payload)
    path = whole_read_target(payload)
    if not key or not path:
        return {}
    digest = file_hash(path)
    if digest is None:
        return {}
    _, _, spec_path, _ = topic_paths(payload)
    ledger = load_ledger(ledger_path(spec_path.parent, key))
    verdict, when = decide(ledger, path, digest, compaction_epoch(spec_path.parent, payload), time.time())
    if verdict == "block":
        entry = ledger.get(path, {})
        intact, why = history_intact(payload, str(entry.get("tool_use_id") or ""), path)
        if not intact and history_contains(payload, path, float(entry.get("ts", 0) or 0)):
            intact, why = True, ""
        if not intact:
            # Silent: the read goes ahead and the model gets the file, so a note would only
            # cost tokens. The reason stays in the ledger for anyone auditing the gate.
            ledger[path] = {"sha256": "", "ts": time.time(), "epoch": 0, "dropped": why}
            save_ledger(ledger_path(spec_path.parent, key), ledger)
            return {}
        return _block(
            f"{path} is byte-identical to your read at {when} (sha256 {digest[:12]}); those bytes are already in "
            "this context, so re-read from there. To load it again anyway, read with offset/limit "
            "(or `sed -n`), or set AGENT_READ_GATE=off."
        )
    if verdict == "changed":
        return _allow(event, f"Note: {path} changed since your read at {when}; the copy in context is stale.")
    return {}


def handle_post(payload: dict[str, Any]) -> dict[str, Any]:
    key = context_key(payload)
    path = whole_read_target(payload)
    if not key or not path:
        return {}
    digest = file_hash(path)
    if digest is None:
        return {}
    _, _, spec_path, _ = topic_paths(payload)
    ledger_file = ledger_path(spec_path.parent, key)
    ledger = load_ledger(ledger_file)
    if not response_reproduces_file(payload.get("tool_response"), path):
        # The context holds a preview or a mismatch, not the file: never block on this read.
        ledger.pop(path, None)
        save_ledger(ledger_file, ledger)
        return {}
    ledger[path] = {
        "sha256": digest,
        "ts": time.time(),
        "epoch": compaction_epoch(spec_path.parent, payload),
        "tool_use_id": str(payload.get("tool_use_id") or payload.get("call_id") or ""),
    }
    save_ledger(ledger_file, ledger)
    return {}


def _cursor_shape(result: dict[str, Any]) -> dict[str, Any]:
    """Cursor permission events answer with permission/user_message; deny text reaches the model."""
    if result.get("decision") == "block":
        return {"permission": "deny", "user_message": result.get("reason", "")}
    return {"permission": "allow"}


def observe_context_tokens(spec_dir: Path, key: str, tokens: int) -> None:
    """Cursor's `stop` hook reports per-turn token counts; a large shrink is a compaction."""
    if reinforcement is None or not key or tokens <= 0:
        return
    state = reinforcement.load_state(spec_dir, key)
    last = state.get("last_tokens")
    if isinstance(last, (int, float)) and tokens < last * COMPACTION_SHRINK_RATIO:
        state["compactions"] = int(state.get("compactions", 0) or 0) + 1
    state["last_tokens"] = int(tokens)
    reinforcement.save_state(spec_dir, key, state)


def handle_cursor(payload: dict[str, Any], event: str) -> dict[str, Any]:
    _, _, spec_path, _ = topic_paths(payload)
    if event == "stop":
        tokens = sum(_int_field(payload, name) for name in ("input_tokens", "cache_read_tokens", "cache_write_tokens"))
        observe_context_tokens(spec_path.parent, session_key(payload), tokens)
        return {}
    if event == "beforeReadFile":
        path = payload.get("file_path")
        if not isinstance(path, str) or not path:
            return {"permission": "allow"}
        probe = {**payload, "tool_name": "Read", "tool_input": {"file_path": path}}
        verdict = handle_pre(probe, "PreToolUse")
        if verdict.get("decision") == "block":
            return _cursor_shape(verdict)
        handle_post({**probe, "tool_response": payload.get("content")})
        return {"permission": "allow"}
    if event == "beforeShellExecution":
        probe = {**payload, "tool_name": "Bash", "tool_input": {"command": payload.get("command", "")}}
        return _cursor_shape(handle_pre(probe, "PreToolUse"))
    if event == "afterShellExecution":
        probe = {**payload, "tool_name": "Bash", "tool_input": {"command": payload.get("command", "")}}
        handle_post({**probe, "tool_response": payload.get("output")})
        return {}
    return {}


def _int_field(payload: dict[str, Any], name: str) -> int:
    value = payload.get(name)
    return int(value) if isinstance(value, (int, float)) else 0


def main() -> int:
    try:
        payload = read_payload()
    except (ValueError, json.JSONDecodeError):
        emit({})
        return 0
    if not isinstance(payload, dict) or disabled():
        emit({})
        return 0
    event = str(payload.get("hook_event_name") or os.environ.get("AGENT_HOOK_EVENT") or "PreToolUse")
    try:
        if event in CURSOR_EVENTS or os.environ.get(HARNESS_ENV) == "cursor":
            emit(handle_cursor(payload, event))
        elif event.lower().startswith("pre"):
            emit(handle_pre(payload, event))
        elif event.lower().startswith("post"):
            emit(handle_post(payload))
        else:
            emit({})
    except Exception:  # noqa: BLE001 - a wrong refusal is worse than a cached re-read
        emit({"permission": "allow"} if event in CURSOR_EVENTS else {})
    return 0


if __name__ == "__main__":
    sys.exit(main())
