#!/usr/bin/env python3
"""Bounded retry hook for unsupported factual/runtime claims.

This is intentionally a ledger, not just a final-answer regex. Agent thoughts and
responses can introduce claims; tool/probe events are recorded as evidence, but
visible response text must still carry its own anchors or Unknown demotions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from hook_common import append_jsonl, emit, read_payload, topic_paths, utc_now

MAX_RETRIES = 1
MAX_DECISION_LOG_LINES = 200

CLAIM_PATTERN = re.compile(
    r"\b("
    r"is|are|was|were|has|have|does|doesn't|do not|works?|worked|"
    r"configured|installed|deployed|applied|verified|confirmed|shows?|"
    r"contains?|uses?|loads?|fires?|writes?|reads?|passes?|fails?|ready"
    r")\b",
    re.I,
)

HARD_EVIDENCE_PATTERN = re.compile(
    r"("
    r"\b(verified|evidence|ran|command|output|test(?:s)?|source|docs?|"
    r"fetched|probe|observed|exit code|passed|failed)\s*:"
    r"|https?://"
    r"|(?:^|\s)`?(?:/|~/|\.\.?/|[A-Za-z0-9_.-]+/)[A-Za-z0-9_./-]+`?"
    r"|`[^`]*(?:python|pytest|npm|pnpm|yarn|go|cargo|chezmoi|git|rg|cursor-agent|claude)[^`]*`"
    r"|```"
    r")",
    re.I | re.M,
)

UNKNOWN_PATTERN = re.compile(
    r"("
    r"\bUnknown\b.{0,180}\b(because|not locally verifiable|cannot be verified|"
    r"not available|requires external|requires live|no local|no access)\b"
    r"|\b(because|not locally verifiable|cannot be verified|not available|"
    r"requires external|requires live|no local|no access)\b.{0,180}\bUnknown\b"
    r")",
    re.I | re.M,
)


def state_path(payload: dict) -> Path:
    _, topic, _, worklog_path = topic_paths(payload)
    return worklog_path.with_name(f"{topic}.evidence_state.json")


def decision_log_path(payload: dict) -> Path:
    _, topic, _, worklog_path = topic_paths(payload)
    return worklog_path.with_name(f"{topic}.evidence_decisions.jsonl")


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def reset_for_generation(state: dict, payload: dict) -> dict:
    generation_id = payload.get("generation_id")
    if state.get("generation_id") == generation_id:
        return state
    return {
        "conversation_id": payload.get("conversation_id"),
        "generation_id": generation_id,
        "retry_count": 0,
        "unresolved_claims": [],
        "evidence_events": [],
    }


def has_claims(text: str) -> bool:
    if len(text.strip()) < 40:
        return False
    return bool(CLAIM_PATTERN.search(text))


def has_hard_anchor(text: str) -> bool:
    return bool(HARD_EVIDENCE_PATTERN.search(text))


def has_unknown_demotion(text: str) -> bool:
    return bool(UNKNOWN_PATTERN.search(text))


def is_response_event(event: str) -> bool:
    return event in {"afterAgentResponse", "AgentResponse"}


def event_text(payload: dict) -> str:
    for key in ("text", "thought", "message", "content"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def claim_units(text: str) -> list[str]:
    units = [unit.strip() for unit in re.split(r"\n\s*\n|(?m)^(?=\s*(?:[-*]|\d+\.)\s+)", text) if unit.strip()]
    return [unit for unit in units if has_claims(unit)]


def unanchored_claim_units(text: str) -> list[str]:
    return [unit for unit in claim_units(text) if not (has_hard_anchor(unit) or has_unknown_demotion(unit))]


def log_decision(payload: dict, decision: str, reason: str, state: dict | None = None) -> None:
    entry = {
        "decision": decision,
        "event": payload.get("hook_event_name"),
        "generation_id": payload.get("generation_id"),
        "reason": reason,
        "ts": utc_now(),
    }
    if state is not None:
        entry["unresolved_count"] = len(state.get("unresolved_claims") or [])
        entry["last_resolution"] = state.get("last_resolution")
    append_jsonl(decision_log_path(payload), entry, max_lines=MAX_DECISION_LOG_LINES)


def event_has_evidence(payload: dict) -> bool:
    text_parts: list[str] = []
    for key in ("command", "output", "tool_output", "error_message"):
        value = payload.get(key)
        if value:
            text_parts.append(str(value))

    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        text_parts.append(json.dumps(tool_input, sort_keys=True))

    tool_name = str(payload.get("tool_name") or "")
    if tool_name in {"Read", "Grep", "Shell", "MCP: ReadFile", "MCP: rg"}:
        text_parts.append(f"tool:{tool_name}")

    text = "\n".join(text_parts)
    return bool(text.strip()) and (has_hard_anchor(text) or bool(tool_name))


def record_text_event(payload: dict) -> None:
    text = event_text(payload)
    event = str(payload.get("hook_event_name") or "")
    units = claim_units(text)
    unanchored = unanchored_claim_units(text)
    path = state_path(payload)
    state = reset_for_generation(load_state(path), payload)
    state["updated_at"] = utc_now()
    state["last_text"] = text
    state["last_event"] = event

    if not units:
        save_state(path, state)
        log_decision(payload, "allow", "no_claim_units", state)
        emit({})
        return

    if not unanchored:
        if is_response_event(event):
            state["unresolved_claims"] = []
            state["retry_count"] = 0
            state["last_resolution"] = "visible_response_anchored"
        else:
            state["last_resolution"] = "thought_anchored"
        save_state(path, state)
        log_decision(payload, "allow", "claim_units_anchored", state)
        emit({})
        return

    unresolved = list(state.get("unresolved_claims") or [])
    if is_response_event(event):
        unresolved = []
    for unit in unanchored:
        unresolved.append(
            {
                "event": event,
                "ts": utc_now(),
                "excerpt": unit.strip()[:500],
            }
        )
    state["unresolved_claims"] = unresolved[-5:]
    state["last_resolution"] = "unanchored_claim_units"
    save_state(path, state)
    log_decision(payload, "track", "unanchored_claim_units", state)
    emit({})


def record_evidence_event(payload: dict) -> None:
    path = state_path(payload)
    state = reset_for_generation(load_state(path), payload)
    if event_has_evidence(payload):
        evidence_events = list(state.get("evidence_events") or [])
        evidence_events.append(
            {
                "event": payload.get("hook_event_name"),
                "tool_name": payload.get("tool_name"),
                "ts": utc_now(),
            }
        )
        state["evidence_events"] = evidence_events[-10:]
        state["last_resolution"] = "evidence_seen_no_global_clear"
    state["updated_at"] = utc_now()
    save_state(path, state)
    log_decision(payload, "record", "evidence_event", state)
    emit({})


def stop(payload: dict) -> None:
    path = state_path(payload)
    state = reset_for_generation(load_state(path), payload)
    unresolved = state.get("unresolved_claims") or []
    if not unresolved:
        log_decision(payload, "allow", "no_unresolved_claims", state)
        emit({})
        return

    retry_count = int(state.get("retry_count") or 0)
    if retry_count >= MAX_RETRIES:
        log_decision(payload, "allow", "retry_limit_reached", state)
        emit({})
        return

    retry_count += 1
    state["retry_count"] = retry_count
    state["updated_at"] = utc_now()
    save_state(path, state)

    reason = (
        "During this turn you made factual, setup, state, or behavior claims "
        "that were not later resolved under the SOP verified-or-Unknown rule. "
        "Retry: identify the unresolved claim, "
        "verify them from local files, command/probe output, tests, or freshly "
        "fetched docs, then continue with those anchors visible. If a claim "
        "cannot be verified from available sources, explicitly label it Unknown "
        "and include the reason. Unresolved excerpt: "
        + " | ".join(str(item.get("excerpt", ""))[:180] for item in unresolved[:1])
    )
    log_decision(payload, "followup", f"retry_{retry_count}", state)
    emit(
        {
            "followup_message": reason,
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "decision": "block",
                "reason": reason,
            },
        }
    )


def main() -> None:
    payload = read_payload()
    event = str(payload.get("hook_event_name") or "")
    if event in {"afterAgentResponse", "afterAgentThought", "AgentResponse", "AgentThought"}:
        record_text_event(payload)
        return
    if event in {"afterShellExecution", "postToolUse", "postToolUseFailure"}:
        record_evidence_event(payload)
        return
    if event in {"stop", "Stop"}:
        stop(payload)
        return
    emit({})


if __name__ == "__main__":
    main()
