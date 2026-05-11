#!/usr/bin/env python3
"""Inject active topic context at the start of Cursor/Claude sessions."""

from __future__ import annotations

import os
from pathlib import Path

from hook_common import emit, read_payload, topic_paths, transcript_tail

MAX_SPEC_CHARS = 2500
MAX_WORKLOG_CHARS = 3000
MAX_WORKLOG_LINES = 12
DISABLE_CONTEXT_ENV = "AGENT_HOOK_CONTEXT"
DISABLE_CONTEXT_VALUES = {"0", "false", "no", "off", "disabled"}
REVIEW_CONCLUSION_HEADINGS = (
    "verified facts",
    "findings",
    "verdict",
    "inline comments",
    "pending review draft",
    "things checked",
    "net",
)


def context_disabled(spec_path: Path, topic: str) -> bool:
    env_value = os.environ.get(DISABLE_CONTEXT_ENV, "").strip().lower()
    if env_value in DISABLE_CONTEXT_VALUES:
        return True

    spec_dir = spec_path.parent
    return (spec_dir / "_no_session_context").exists() or (spec_dir / f"{topic}.no_context").exists()


def is_review_topic(topic: str, text: str) -> bool:
    return topic.startswith("review") or "\ntarget: PR " in f"\n{text}"


def neutral_review_spec(text: str, spec_path: Path) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        normalized = line.strip().rstrip(":").lower()
        if normalized in REVIEW_CONCLUSION_HEADINGS:
            break
        lines.append(line)

    body = "\n".join(lines).strip()
    if not body:
        body = f"Review topic spec exists at `{spec_path}`."

    return (
        body + "\n\n[review clean-room mode: prior findings, verdicts, verified-facts blocks, "
        f"and worklog tails are omitted from startup context. Read `{spec_path}` manually "
        "only if you intentionally want prior-session conclusions.]"
    )


def spec_context(spec_path: Path, topic: str) -> str:
    text = spec_path.read_text(errors="replace").strip()
    if is_review_topic(topic, text):
        return neutral_review_spec(text, spec_path)

    if len(text) <= MAX_SPEC_CHARS:
        return text

    return (
        f"Active topic spec omitted because it is {len(text)} characters, "
        f"exceeding the {MAX_SPEC_CHARS}-character injection limit. "
        f"Read `{spec_path}` before relying on prior session context."
    )


def main() -> None:
    payload = read_payload()
    workspace, topic, spec_path, worklog_path = topic_paths(payload)

    if context_disabled(spec_path, topic):
        emit({})
        return

    parts = [
        "## Agent Hook Context",
        f"- Workspace: `{workspace}`",
        f"- Active topic: `{topic}`",
    ]

    is_review = False
    if spec_path.exists():
        spec_text_source = spec_path.read_text(errors="replace")
        is_review = is_review_topic(topic, spec_text_source)
        spec_text = spec_context(spec_path, topic)
        if spec_text:
            parts.extend(["", "### Active Topic Spec", spec_text])

    worklog = "" if is_review else transcript_tail(worklog_path, lines=MAX_WORKLOG_LINES, limit=MAX_WORKLOG_CHARS)
    if worklog:
        parts.extend(["", "### Recent Hook Worklog", worklog])

    if len(parts) <= 3:
        emit({})
        return

    context = "\n".join(parts)
    emit(
        {
            "additional_context": context,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            },
        }
    )


if __name__ == "__main__":
    main()
