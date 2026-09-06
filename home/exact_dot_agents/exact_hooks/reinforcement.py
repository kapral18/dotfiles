"""Per-prompt SOP reinforcement: re-inject the verified `prefix.txt` excerpt only when it helps.

The SOP sits at the top of every session. As tool output and conversation history
accumulate, top-of-context rules dilute, so the shared discipline core is re-injected
close to the current prompt, but only after material context growth or a compaction.
This mirrors `PREFIX_REINJECT_DELTA_PCT` in the pi/omp `ai-kb-recall.ts` extensions
(20 points of fill there; 200k tokens here, the same distance on the 1M windows in use);
those harnesses keep their native mechanism and read the same file.

Fill signal, in order of preference:
1. `transcript_path` in the hook payload: Claude Code JSONL (`message.usage`, input plus
   cache read/creation of the newest API call) or a Codex rollout (`token_count` events).
2. A Codex rollout located by `session_id` under `~/.codex/sessions/`.
3. No usage signal (Cursor, Copilot): a prompt-count interval. This is a proxy for growth,
   documented as such, and the interval is tunable.

State is one small JSON file per session next to the topic spec. Every failure path is
fail-open: a broken transcript, missing file, or bad state yields no injection, never an
error, because a missing reminder is cheaper than a broken prompt hook.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PREFIX_REL_PATH = "tmux/agent_prompts/prefix.txt"
# Pinned equal to PREFIX_MAX_CHARS in the pi/omp extensions by the parity test.
MAX_PREFIX_CHARS = 6000
# Re-inject once the context grew by this many tokens since the last injection (or the
# first observation). Dilution is a function of the absolute distance between the rules at
# the top and the current prompt, not of the window size, so growth is measured in tokens.
# 200k is 20 points of the 1M windows the configured models run (the pi/omp extensions use
# the same 20 points in percent); agents routinely churn through hundreds of thousands of
# tokens, so anything smaller re-injects far more often than dilution warrants.
REINJECT_DELTA_TOKENS = 200_000
DELTA_TOKENS_ENV = "AGENT_REINFORCE_DELTA_TOKENS"
# A context shrinking to this fraction of the last observation reads as a compaction: the
# prior injection was summarized away, so force one now.
COMPACTION_SHRINK_RATIO = 0.75
# Harnesses that expose no usage signal: re-inject every N prompts after the first.
FALLBACK_PROMPT_INTERVAL = 10
PROMPT_INTERVAL_ENV = "AGENT_REINFORCE_PROMPTS"
DISABLE_ENV = "AGENT_REINFORCE"
DISABLE_VALUES = {"0", "false", "no", "off", "disabled"}
STATE_SUFFIX = ".reinforce.json"
# Only the transcript tail is read; the newest usage row is what matters.
TAIL_BYTES = 256 * 1024
FRAMING = "Apply the discipline above to this and later prompts; it restates the SOP already in context."


def prefix_text() -> str:
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(config_home) / PREFIX_REL_PATH
    try:
        text = path.read_text(errors="replace").strip()
    except OSError:
        return ""
    return text[:MAX_PREFIX_CHARS]


def state_path(spec_dir: Path, key: str) -> Path:
    return spec_dir / f"{key}{STATE_SUFFIX}"


def load_state(spec_dir: Path, key: str) -> dict[str, Any]:
    try:
        data = json.loads(state_path(spec_dir, key).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(spec_dir: Path, key: str, state: dict[str, Any]) -> None:
    try:
        spec_dir.mkdir(parents=True, exist_ok=True)
        state_path(spec_dir, key).write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def mark_compaction(spec_dir: Path, key: str) -> None:
    """Session-start after a compaction: the next prompt must re-inject regardless of fill."""
    if not key:
        return
    state = load_state(spec_dir, key)
    state["force"] = True
    # Epoch consumers (read_gate.py) treat everything recorded before a compaction as gone.
    state["compactions"] = int(state.get("compactions", 0) or 0) + 1
    save_state(spec_dir, key, state)


def _tail_lines(path: Path) -> list[str]:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > TAIL_BYTES:
                handle.seek(size - TAIL_BYTES)
                handle.readline()  # drop the partial first line
            data = handle.read()
    except OSError:
        return []
    return data.decode("utf-8", errors="replace").splitlines()


def _usage_from_row(row: dict[str, Any]) -> int | None:
    """Return the context tokens of the API call recorded by one transcript row, or None."""
    message = row.get("message")
    if isinstance(message, dict) and isinstance(message.get("usage"), dict):
        usage = message["usage"]
        tokens = 0
        for field in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            value = usage.get(field)
            if isinstance(value, (int, float)):
                tokens += int(value)
        if tokens > 0:
            return tokens
    payload = row.get("payload")
    if row.get("type") == "event_msg" and isinstance(payload, dict) and payload.get("type") == "token_count":
        info = payload.get("info") or {}
        tokens = (info.get("last_token_usage") or {}).get("input_tokens")
        if isinstance(tokens, (int, float)) and tokens > 0:
            return int(tokens)
    return None


def tokens_from_transcript(path: Path) -> int | None:
    for line in reversed(_tail_lines(path)):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        tokens = _usage_from_row(row)
        if tokens:
            return tokens
    return None


def _codex_rollout(session_id: str) -> Path | None:
    root = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "sessions"
    if not session_id or not root.is_dir():
        return None
    matches = sorted(root.glob(f"*/*/*/rollout-*-{session_id}.jsonl"))
    return matches[-1] if matches else None


def context_tokens(payload: dict[str, Any]) -> int | None:
    transcript = payload.get("transcript_path")
    if isinstance(transcript, str) and transcript:
        tokens = tokens_from_transcript(Path(transcript).expanduser())
        if tokens is not None:
            return tokens
    rollout = _codex_rollout(str(payload.get("session_id") or ""))
    if rollout is not None:
        return tokens_from_transcript(rollout)
    return None


def _delta_tokens() -> int:
    raw = os.environ.get(DELTA_TOKENS_ENV, "")
    try:
        value = int(raw)
    except ValueError:
        return REINJECT_DELTA_TOKENS
    return value if value > 0 else REINJECT_DELTA_TOKENS


def _prompt_interval() -> int:
    raw = os.environ.get(PROMPT_INTERVAL_ENV, "")
    try:
        value = int(raw)
    except ValueError:
        return FALLBACK_PROMPT_INTERVAL
    return value if value > 0 else FALLBACK_PROMPT_INTERVAL


def decide(state: dict[str, Any], tokens: int | None) -> tuple[bool, str]:
    """Pure decision: (inject, reason). Updates `state` in place; never touches disk.

    On an injection the baseline moves to the current observation, so the next one is
    due only after another `REINJECT_DELTA_TOKENS` of growth (or another compaction).
    """
    state["prompts"] = int(state.get("prompts", 0)) + 1
    inject, reason = False, "steady"
    if state.get("force"):
        inject, reason = True, "compaction"
    elif tokens is not None:
        last = state.get("last_tokens")
        if not isinstance(last, (int, float)):
            reason = "baseline"
        elif tokens < last * COMPACTION_SHRINK_RATIO:
            inject, reason = True, "compaction"
            state["compactions"] = int(state.get("compactions", 0) or 0) + 1
        elif tokens - last >= _delta_tokens():
            inject, reason = True, "growth"
    else:
        last_prompt = state.get("last_prompt")
        if not isinstance(last_prompt, int):
            reason = "baseline"
        elif state["prompts"] - last_prompt >= _prompt_interval():
            inject, reason = True, "prompt-count"
    if inject or reason == "baseline":
        state["force"] = False
        state["last_prompt"] = state["prompts"]
        if tokens is not None:
            state["last_tokens"] = int(tokens)
    if inject:
        state["reinjections"] = int(state.get("reinjections", 0)) + 1
        state["last_reason"] = reason
    return inject, reason


def block(payload: dict[str, Any], spec_dir: Path, key: str) -> str:
    """Return the reinforcement block for this prompt, or "" when none is due."""
    if not key or os.environ.get(DISABLE_ENV, "").strip().lower() in DISABLE_VALUES:
        return ""
    state = load_state(spec_dir, key)
    inject, _reason = decide(state, context_tokens(payload))
    save_state(spec_dir, key, state)
    if not inject:
        return ""
    text = prefix_text()
    return f"{text}\n\n{FRAMING}" if text else ""
