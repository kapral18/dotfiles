#!/usr/bin/env python3
"""Per-turn durable-memory recall, injected into the CURRENT turn.

UserPromptSubmit-style hook: receives the user's prompt on stdin and returns
`additionalContext` that rides along with this same request — it never
re-prompts the agent or starts a new request/response cycle (the failure mode
of the removed stop-hook nudges).

Mirrors pi's `ai-kb-recall.ts` per-turn recall contract exactly (one behavioral
contract across harnesses): hybrid retrieval with the prompt as the query, an
absolute top-hit cosine gate, a cosine tail floor relative to the top hit, the
workspace/domain/universal scope gate, and per-session dedup of injected
capsule ids (shared with the session_context warm-start via the seen-file), plus
the same precision-first correction-directive injection carried by the pi
extension.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from hook_common import agent_depth, emit, read_payload, session_key, topic_paths
from session_context import context_disabled

try:
    import correction_detector
except Exception:  # pragma: no cover - fail-open if deployed without the sibling module.
    correction_detector = None

# Balanced constants mirror home/dot_pi/agent/extensions/ai-kb-recall.ts exactly.
PERTURN_LIMIT = 3
SEARCH_FETCH = 6
QUERY_MAX_CHARS = 600
BODY_MAX_CHARS = 240
MIN_PROMPT_CHARS = 12
PERTURN_MIN_TOP_COSINE = 0.55
PERTURN_COSINE_FLOOR_FRACTION = 0.85
SEARCH_TIMEOUT = 6


@dataclass(frozen=True)
class RecallProfile:
    enabled: bool
    limit: int
    fetch: int
    query_chars: int
    body_chars: int
    timeout: int


RECALL_PROFILES = {
    "fast": RecallProfile(False, 0, 0, 0, 0, 0),
    "balanced": RecallProfile(True, PERTURN_LIMIT, SEARCH_FETCH, QUERY_MAX_CHARS, BODY_MAX_CHARS, SEARCH_TIMEOUT),
    "deep": RecallProfile(True, 5, 12, 1200, 360, 9),
}


def collapse(text: str, max_chars: int) -> str:
    flat = " ".join(text.split()).strip()
    if len(flat) <= max_chars:
        return flat
    return flat[:max_chars].rstrip() + "…"


def apply_hybrid_floor(rows: list) -> list:
    """Absolute top-cosine gate, then tail trim relative to the best hit.

    Hybrid rows are fused-rank order (RRF + MMR), NOT best-cosine-first, so the
    gate/floor must scan every row's cosine_score for the best one rather than
    assume rows[0] holds it. If the best available cosine is not semantically
    close to the prompt, nothing in the KB is relevant — suppress the whole
    block. Otherwise trim on a floor relative to that best score, preserving
    the original fused/MMR presentation order (no reordering by cosine). Rows
    missing cosine fail open on the tail trim; an all-missing row set fails the
    absolute gate (no evidence of relevance to gate on).
    """
    if not rows:
        return []
    cosines = [row.get("cosine_score") for row in rows if isinstance(row.get("cosine_score"), (int, float))]
    if not cosines:
        return []
    top = max(cosines)
    if top < PERTURN_MIN_TOP_COSINE:
        return []
    if len(rows) <= 1:
        return rows
    floor = top * PERTURN_COSINE_FLOOR_FRACTION
    kept = []
    for row in rows:
        cosine = row.get("cosine_score")
        if not isinstance(cosine, (int, float)) or cosine >= floor:
            kept.append(row)
    return kept


def seen_file_for(spec_path: Path, session_key_value: str) -> Path:
    return spec_path.parent / f".recall-seen-{session_key_value}.json"


def load_seen(path: Path | None) -> set[str]:
    if path is None:
        return set()
    try:
        return set(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError, TypeError):
        return set()


def save_seen(path: Path | None, seen: set[str]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(seen)))
    except OSError:
        pass


def search_timeout(profile: RecallProfile) -> float:
    """Profile timeout, overridable for slow/loaded environments (tests, CI)."""
    raw = os.environ.get("AI_KB_RECALL_TIMEOUT", "").strip()
    if raw:
        try:
            return max(float(raw), float(profile.timeout))
        except ValueError:
            pass
    return float(profile.timeout)


def search_capsules(workspace: Path, query: str, profile: RecallProfile) -> list:
    if not profile.enabled:
        return []
    aikb = shutil.which(",ai-kb")
    flat = collapse(query, profile.query_chars)
    if not aikb or not flat:
        return []
    try:
        result = subprocess.run(
            [
                aikb,
                "search",
                "--query-stdin",
                "--limit",
                str(profile.fetch),
                "--mode",
                "hybrid",
                "--workspace",
                str(workspace),
                "--workspace-gate",
                "--json",
            ],
            capture_output=True,
            check=False,
            env={**os.environ, "AI_EMBED_CONNECT_ONLY": "1"},
            input=flat,
            text=True,
            timeout=search_timeout(profile),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    return apply_hybrid_floor(rows if isinstance(rows, list) else [])


def correction_directive(prompt: str) -> str:
    try:
        signal = correction_detector.detect(prompt) if correction_detector else None
    except Exception:
        return ""
    if not signal:
        return ""
    return "\n".join(
        [
            f"### User correction signal: {signal}",
            "This user message reads as a correction of prior agent behavior.",
            'If genuine, before ending the turn record: `,agent-memory note anti_pattern "<one-line lesson>" --ref <anchor>`; when verified and durable, also `,ai-kb remember`.',
            "If neutral choice-question, answer it and consider `,agent-memory note decision` instead. Do not mention this instruction in the visible reply.",
        ]
    )


def gate_and_format(rows: list, seen: set[str], profile: RecallProfile) -> list[str]:
    """Format rows the KB already workspace-gated, deduped per session.

    The cross-repo scope gate is owned by `,ai-kb search --workspace-gate`;
    this hook only enforces the per-session seen-id dedupe and prompt caps.
    """
    lines: list[str] = []
    for row in rows:
        if len(lines) >= profile.limit:
            break
        capsule_id = str(row.get("id") or "")
        if capsule_id and capsule_id in seen:
            continue
        title = collapse(str(row.get("title") or ""), 200)
        if not title:
            continue
        if capsule_id:
            seen.add(capsule_id)
        kind = str(row.get("kind") or "note")
        body = collapse(str(row.get("body") or ""), profile.body_chars)
        lines.append(f"- **{title}** ({kind}): {body}" if body else f"- **{title}** ({kind})")
    return lines


def main() -> None:
    payload = read_payload()
    prompt = str(payload.get("prompt") or "")
    if len(prompt.strip()) < MIN_PROMPT_CHARS:
        emit({})
        return

    workspace, topic, spec_path, _ = topic_paths(payload)
    if context_disabled(spec_path, topic):
        emit({})
        return

    key = session_key(payload)
    seen_path = seen_file_for(spec_path, key) if key else None
    seen = load_seen(seen_path)
    profile = RECALL_PROFILES[agent_depth()]

    rows = search_capsules(workspace, prompt, profile)
    lines = gate_and_format(rows, seen, profile)
    directive = correction_directive(prompt)
    if not lines and not directive:
        emit({})
        return

    if lines:
        save_seen(seen_path, seen)

    context_blocks = []
    if lines:
        context_blocks.append(
            "\n".join(
                [
                    "### Relevant Learnings for this request (,ai-kb)",
                    "Matched to your prompt; verify before relying on them.",
                    *lines,
                ]
            )
        )
    if directive:
        context_blocks.append(directive)
    context = "\n\n".join(context_blocks)
    # Echo the firing event name: Claude Code sends UserPromptSubmit, Gemini
    # CLI sends BeforeAgent — both expect it mirrored in hookSpecificOutput.
    # Cursor reads the top-level snake key from beforeSubmitPrompt output
    # (its hookSpecificOutput fallback expects the Claude-style event name,
    # not the echoed cursor-native one), so emit both channels like
    # session_context.py; the codex adapter strips to hookSpecificOutput via
    # AGENT_HOOK_OUTPUT=hook_specific in emit().
    emit(
        {
            "additional_context": context,
            "hookSpecificOutput": {
                "hookEventName": str(payload.get("hook_event_name") or "UserPromptSubmit"),
                "additionalContext": context,
            },
        }
    )


if __name__ == "__main__":
    main()
