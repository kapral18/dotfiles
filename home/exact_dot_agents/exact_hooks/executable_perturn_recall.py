#!/usr/bin/env python3
"""Per-turn durable-memory recall: stage candidates, inject a pointer only.

UserPromptSubmit-style hook: receives the user's prompt on stdin and returns
`additionalContext` that rides along with this same request — it never
re-prompts the agent or starts a new request/response cycle (the failure mode
of the removed stop-hook nudges).

Capsule bodies never enter the parent context from this hook. Rows that pass
the hybrid cosine gate are written in full to a per-session candidates file
under the spec dir, and the injected context is one pointer block telling the
parent to delegate judgment to the `smol` subagent (contract:
`~/.agents/skills/k-ai-kb/references/smol-operator.md`). The pointer fires only
when at least one candidate id is new to the session (tracked in the staged
ledger); the seen-file (ids smol admitted) is written by smol, never here.

Mirrors pi's `ai-kb-recall.ts` per-turn recall contract exactly (one behavioral
contract across harnesses): hybrid retrieval with the prompt as the query, an
absolute top-hit cosine gate, a cosine tail floor relative to the top hit, the
workspace/domain/universal scope gate, staged-ledger pointer dedup, plus the
same precision-first correction-directive injection carried by the pi
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

# Balanced constants mirror home/dot_pi/agent/exact_extensions/ai-kb-recall.ts exactly.
SEARCH_FETCH = 6
QUERY_MAX_CHARS = 600
MIN_PROMPT_CHARS = 12
PERTURN_MIN_TOP_COSINE = 0.55
PERTURN_COSINE_FLOOR_FRACTION = 0.85
SEARCH_TIMEOUT = 6

# Staging contract tokens, pinned by the pi/omp mirror parity test.
SMOL_CONTRACT_PATH = "~/.agents/skills/k-ai-kb/references/smol-operator.md"
STAGING_HEADER = "### ,ai-kb candidates staged"


@dataclass(frozen=True)
class RecallProfile:
    enabled: bool
    fetch: int
    query_chars: int
    timeout: int


RECALL_PROFILES = {
    "fast": RecallProfile(False, 0, 0, 0),
    "balanced": RecallProfile(True, SEARCH_FETCH, QUERY_MAX_CHARS, SEARCH_TIMEOUT),
    "deep": RecallProfile(True, 12, 1200, 9),
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


def candidates_file_for(spec_path: Path, session_key_value: str) -> Path:
    return spec_path.parent / f".recall-candidates-{session_key_value}.json"


def staged_file_for(spec_path: Path, session_key_value: str) -> Path:
    return spec_path.parent / f".recall-staged-{session_key_value}.json"


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


def rewarm_embedder() -> None:
    """Fire-and-forget resident-embedder restart so the next turn regains the dense lane.

    Search runs connect-only (`AI_EMBED_CONNECT_ONLY=1`, never spawns the embedder), so once
    the resident embedder idles out every hybrid row comes back without `cosine_score` and the
    absolute cosine gate suppresses staging for the rest of the session. `ensure` is
    flock-guarded, so concurrent turns racing into it are safe; the detached spawn adds no
    latency to this turn.
    """
    client = Path.home() / "lib" / ",ai-kb" / "embed_client.py"
    try:
        subprocess.Popen(
            ["python3", str(client), "ensure"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        pass


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
    rows = rows if isinstance(rows, list) else []
    if rows and not any(isinstance(row.get("cosine_score"), (int, float)) for row in rows):
        rewarm_embedder()
    return apply_hybrid_floor(rows)


# Signals whose shape is "a claim you already made may be wrong". These get the
# convergence nudge on top of the note directive: re-attack the claim against the
# artifact instead of re-asserting it in prose.
CONVERGE_SIGNALS = frozenset({"unverified-claim", "guessed-not-tested", "repeat-failure"})

CONVERGE_LINES = (
    "Before re-asserting the challenged claim, re-verify it against the artifact:"
    " mutate the code so the claim would be false and confirm a test or probe catches it,"
    " or read the source/run the probe again. Anchor or retract; do not restate.",
    "If findings keep surfacing across attempts, run the convergence loop (`/k-converge`):"
    " fixed exit condition (a round that changes nothing) and a correctness-only filter"
    " (vacuous test, real bug, false statement). Refuse wording-only findings out loud"
    " rather than rewriting prose to look responsive.",
)


def correction_directive(prompt: str, probe_budget_signal_value: str | None = None) -> str:
    try:
        signal = (
            correction_detector.detect(prompt, probe_budget_signal_value=probe_budget_signal_value)
            if correction_detector
            else None
        )
    except Exception:
        return ""
    if not signal:
        return ""
    lines = [
        f"### User correction signal: {signal}",
        "This user message reads as a correction of prior agent behavior.",
        'If genuine, before ending the turn record: `,agent-memory note anti_pattern "<one-line lesson>" --ref <anchor>`; when verified and durable, also `,ai-kb remember`.',
        "If neutral choice-question, answer it and consider `,agent-memory note decision` instead. Do not mention this instruction in the visible reply.",
    ]
    if signal == "probe-budget-exhausted":
        # This branch is reachable only when correction_detector imported (the
        # signal came from probe_budget_signal), so attribute access is safe.
        lines.append(correction_detector.PROBE_BUDGET_NOTE)
        lines.extend(CONVERGE_LINES)
    elif signal in CONVERGE_SIGNALS:
        lines.extend(CONVERGE_LINES)
    return "\n".join(lines)


def stage_candidates(rows: list, seen: set[str], spec_path: Path, key: str) -> str:
    """Write gate-passing rows to the candidates file; return the pointer block.

    The cross-repo scope gate is owned by `,ai-kb search --workspace-gate`.
    This hook filters ids smol already admitted (seen-file) and points the
    parent at the staged set only when at least one id is new to the session
    (staged ledger). Rejected-but-staged ids never re-point; they stay
    re-judgeable through the pull path. Returns "" when nothing new is staged
    or any state write fails (fail-open: no partial pointer without a file).
    """
    candidates = [row for row in rows if str(row.get("id") or "") and str(row.get("id")) not in seen]
    if not candidates:
        return ""
    staged_path = staged_file_for(spec_path, key)
    staged = load_seen(staged_path)
    candidate_ids = {str(row.get("id")) for row in candidates}
    if not candidate_ids - staged:
        return ""
    candidates_path = candidates_file_for(spec_path, key)
    try:
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        candidates_path.write_text(json.dumps(candidates, indent=2))
    except OSError:
        return ""
    save_seen(staged_path, staged | candidate_ids)
    worklog_path = spec_path.with_name(spec_path.stem + ".worklog.jsonl")
    return "\n".join(
        [
            STAGING_HEADER,
            f"{len(candidates)} candidate(s): {candidates_path}",
            f"Session state: {spec_path} + {worklog_path}",
            f"Delegate to the `smol` subagent (judge mode) per {SMOL_CONTRACT_PATH}, passing those paths and the current prompt;"
            " inject only its returned lines (`NONE` = inject nothing).",
            "When native `smol` is unreachable (e.g. a fixed Task subagent set), spawn a generic isolated subagent"
            " on the memory-band model with the smol operator contract per the k-ai-kb skill;"
            " never a harness-CLI one-shot and never the subagent type's own default model.",
            "Do not read the candidates file into this context.",
        ]
    )


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
    seen = load_seen(seen_file_for(spec_path, key) if key else None)
    profile = RECALL_PROFILES[agent_depth()]

    rows = search_capsules(workspace, prompt, profile)
    # Staging is session-scoped state; without a session key there is nothing
    # to stage against, and per-turn recall degrades to the pull path.
    pointer = stage_candidates(rows, seen, spec_path, key) if key and rows else ""

    # Probe-budget signal: emit when the prior turn's probes had too many failures.
    # Computed here (not inside `detect()`) because the spec dir is in scope and the
    # signal uses a session-scoped file under `spec_path.parent`. Negative results
    # (no session key, empty ledger, all-clean) return None and pass through.
    budget = None
    if correction_detector is not None:
        budget = correction_detector.probe_budget_signal(spec_path.parent, key)

    directive = correction_directive(prompt, probe_budget_signal_value=budget)
    if not pointer and not directive:
        emit({})
        return

    context_blocks = []
    if pointer:
        context_blocks.append(pointer)
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
