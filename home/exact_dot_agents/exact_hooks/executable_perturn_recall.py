#!/usr/bin/env python3
"""Per-turn durable-memory recall, injected into the CURRENT turn.

UserPromptSubmit-style hook: receives the user's prompt on stdin and returns
`additionalContext` that rides along with this same request — it never
re-prompts the agent or starts a new request/response cycle (the failure mode
of the removed stop-hook nudges).

Mirrors pi's `ai-kb-recall.ts` per-turn contract exactly (one behavioral
contract across harnesses): hybrid retrieval with the prompt as the query, an
absolute top-hit cosine gate, a cosine tail floor relative to the top hit, the
workspace/domain/universal scope gate, and per-session dedup of injected
capsule ids (shared with the session_context warm-start via the seen-file).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from hook_common import emit, read_payload, session_key, topic_paths
from session_context import context_disabled

# Constants mirror home/dot_pi/agent/extensions/ai-kb-recall.ts — change both together.
PERTURN_LIMIT = 3
SEARCH_FETCH = 6
QUERY_MAX_CHARS = 600
BODY_MAX_CHARS = 240
MIN_PROMPT_CHARS = 12
PERTURN_MIN_TOP_COSINE = 0.55
PERTURN_COSINE_FLOOR_FRACTION = 0.85
SEARCH_TIMEOUT = 6
CROSS_PROJECT_SCOPES = {"domain", "universal"}


def collapse(text: str, max_chars: int) -> str:
    flat = " ".join(text.split()).strip()
    if len(flat) <= max_chars:
        return flat
    return flat[:max_chars].rstrip() + "…"


def apply_hybrid_floor(rows: list) -> list:
    """Absolute top-cosine gate, then tail trim relative to the top hit.

    If the best hit is not semantically close to the prompt, nothing in the KB
    is relevant — suppress the whole block. rows[0] always survives the tail
    trim; rows missing cosine fail open.
    """
    if not rows:
        return []
    top = rows[0].get("cosine_score")
    if top is None or top < PERTURN_MIN_TOP_COSINE:
        return []
    if len(rows) <= 1:
        return rows
    floor = top * PERTURN_COSINE_FLOOR_FRACTION
    kept = [rows[0]]
    for row in rows[1:]:
        cosine = row.get("cosine_score")
        if cosine is None or cosine >= floor:
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


def search_capsules(workspace: Path, query: str) -> list:
    aikb = shutil.which(",ai-kb")
    flat = collapse(query, QUERY_MAX_CHARS)
    if not aikb or not flat:
        return []
    try:
        result = subprocess.run(
            [
                aikb,
                "search",
                flat,
                "--limit",
                str(SEARCH_FETCH),
                "--mode",
                "hybrid",
                "--workspace",
                str(workspace),
                "--json",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=SEARCH_TIMEOUT,
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


def gate_and_format(rows: list, workspace: Path, seen: set[str]) -> list[str]:
    workspace_str = str(workspace)
    lines: list[str] = []
    for row in rows:
        if len(lines) >= PERTURN_LIMIT:
            break
        scope = str(row.get("scope") or "")
        same_workspace = str(row.get("workspace_path") or "") == workspace_str
        if not same_workspace and scope not in CROSS_PROJECT_SCOPES:
            continue
        capsule_id = str(row.get("id") or "")
        if capsule_id and capsule_id in seen:
            continue
        title = collapse(str(row.get("title") or ""), 200)
        if not title:
            continue
        if capsule_id:
            seen.add(capsule_id)
        kind = str(row.get("kind") or "note")
        body = collapse(str(row.get("body") or ""), BODY_MAX_CHARS)
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

    rows = search_capsules(workspace, prompt)
    lines = gate_and_format(rows, workspace, seen)
    if not lines:
        emit({})
        return

    save_seen(seen_path, seen)
    context = "\n".join(
        [
            "### Relevant Learnings for this request (,ai-kb)",
            "Matched to your prompt; verify before relying on them.",
            *lines,
        ]
    )
    # Echo the firing event name: Claude Code sends UserPromptSubmit, Gemini
    # CLI sends BeforeAgent — both expect it mirrored in hookSpecificOutput.
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": str(payload.get("hook_event_name") or "UserPromptSubmit"),
                "additionalContext": context,
            }
        }
    )


if __name__ == "__main__":
    main()
