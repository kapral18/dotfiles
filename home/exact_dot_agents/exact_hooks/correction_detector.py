"""Precision-first user-correction detector for per-turn hook prompts.

A missed correction costs one lost mistake note; a false fire injects a wasted
directive into an innocent turn. Keep patterns narrow and agent-conduct-shaped.
Borderline or generic utterances such as "why is X", "not showing", "wtf" alone,
"try again", bare "are you sure?", curiosity questions like "why did you choose
X?", and mid-sentence "stop"/"don't" verbs are deliberately excluded.

Every check is bounded: input is capped at DETECT_MAX_CHARS (a correction cue
that far into a pasted wall of text is not worth a multi-second regex scan on
every turn), and conjunction cues must sit near their anchor match.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

MIN_PROMPT_CHARS = 12
DETECT_MAX_CHARS = 20000
CONJUNCTION_WINDOW_CHARS = 160

# Probe-budget signal tuning. The `,probe` helper appends one line per recorded probe
# to a session-scoped ledger next to the active topic spec. Agents record only failed
# probes (prefix.txt), so the ledger is a failure log, not a pass/fail ratio: the
# per-turn hook counts recent failures and, when enough landed within a short window
# and the user's prompt is *not* a correction, surfaces a "expectation may be wrong" hint.
# Counted as a per-turn signal, never a block: same fail-open shape as premise_nudge.
PROBE_LEDGER_REL_PATH = ".probe-ledger.jsonl"
# `,probe` cannot see the hook payload's session id from a plain shell, so most
# ledgers land under the `ad-hoc` key. The reader accepts that ledger as a
# fallback; the ad-hoc file is shared by every session in the workspace, and the
# recency window below is what keeps yesterday's failures from firing the hint on
# today's first turn.
PROBE_AD_HOC_KEY = "ad-hoc"
PROBE_BUDGET_WINDOW = 8  # rolling window of ledger rows evaluated by the budget check
PROBE_BUDGET_FAILURE_THRESHOLD = 3  # 3+ failures in the window => hint
# A fails-only ledger would otherwise fire forever after the third failure of a long
# session, and the shared ad-hoc ledger would carry other sessions' failures: only
# failures recorded within this many seconds count toward the threshold.
PROBE_RECENT_WINDOW_SECONDS = 30 * 60
PROBE_BUDGET_NOTE = (
    "Probe-budget hint: the prior turn ran several probes that returned `fail` (expectation "
    "contradicted reality). Before the next probe, re-read the source the probe was meant to "
    "exercise — regex/regex-flag arithmetic, `,gh-prw` semantics, and lint-tool option names "
    "have all been the offender in past sessions. The fix is rarely another probe; it is usually "
    "a one-character rewrite of the expected value."
)

UNREQUESTED_ACTION_NEGATION_RE = re.compile(r"\b(?:never|do\s+not|i\s+didn['’]?t\s+ask|undo|revert)\b", re.IGNORECASE)

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "unrequested-action",
        re.compile(r"\bi\s+didn['’]?t\s+ask\s+(?:you\s+)?(?:to|for)\b|\bi\s+never\s+asked\b", re.IGNORECASE),
    ),
    (
        "omission-correction",
        re.compile(r"\bwhy\s+did(?:n['’]?t|\s+not)\s+you\b|\bwhy\s+did\s+you\s+not\b", re.IGNORECASE),
    ),
    (
        "unverified-claim",
        re.compile(r"\bdid\s+you\s+(?:really|actually)\s+(?:measure|test|verify|check|run|try)\b", re.IGNORECASE),
    ),
    ("unverified-claim", re.compile(r"\bhallucinat\w*\b", re.IGNORECASE)),
    (
        "guessed-not-tested",
        re.compile(
            r"\b(?:you\s+guessed|did\s+you\s+guess|was\s+that\s+a\s+guess|or\s+(?:did\s+)?you\s+guess)\b", re.IGNORECASE
        ),
    ),
    (
        "guessed-not-tested",
        re.compile(r"\binstead\s+of\s+(?:testing|verifying|measuring|checking|proving)\b", re.IGNORECASE),
    ),
    (
        "unrequested-action",
        re.compile(
            r"\b(?:never|don['’]?t|do\s+not)\s+(?:commit|push|delete|force|do\s+(?:that|this)\s+again)\b", re.IGNORECASE
        ),
    ),
    (
        "repeat-failure",
        re.compile(r"\b(?:still|again)\s+(?:broken|wrong|failing|not\s+working|doesn['’]?t\s+work)\b", re.IGNORECASE),
    ),
    (
        "repeat-failure",
        re.compile(
            r"\b(?:that['’]?s|this\s+is|it['’]?s)\s+(?:still\s+)?(?:wrong|incorrect|not\s+what\s+i\s+asked)\b",
            re.IGNORECASE,
        ),
    ),
)

WHY_DID_YOU_RE = re.compile(r"\bwhy\s+(?:the\s+(?:fuck|hell)\s+)?(?:did|would)\s+you\b", re.IGNORECASE)

ARE_YOU_SURE_RE = re.compile(r"\bare\s+you\s+sure\b", re.IGNORECASE)
SURE_FOLLOWUP_RE = re.compile(
    r"\bhave\s+you\s+(?:tried|tested|verified|checked)\b|\bor\b[\s\S]{0,200}?\bguess", re.IGNORECASE
)


def _probe_ledger_for(spec_dir: Path | None, session_key_value: str) -> Path | None:
    """Ledger lives next to the active topic spec, scoped per session.

    Mirrors session_context's `.recall-seen-<key>.json` storage shape so existing
    cleanup and inspection tooling sees the same artifact family.
    """
    if not session_key_value or spec_dir is None:
        return None
    return spec_dir / f"{session_key_value}{PROBE_LEDGER_REL_PATH}"


def _read_ledger(path: Path | None) -> list[str]:
    if path is None:
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [line for line in content.splitlines() if line.strip()]


def _parse_rows(lines: list[str]) -> list[dict]:
    rows = []
    for raw in lines:
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _is_fresh(row: dict, now: datetime, max_age_seconds: int) -> bool:
    ts = row.get("ts")
    if not isinstance(ts, str):
        return False
    try:
        recorded = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    age = (now - recorded).total_seconds()
    return 0 <= age <= max_age_seconds


def probe_budget_signal(spec_dir: Path | None, session_key_value: str) -> str | None:
    """Return the `probe-budget-exhausted` signal iff the prior turn spent too many probes.

    Reads the most recent PROBE_BUDGET_WINDOW entries from the session-scoped
    ledger and counts only failures recorded within PROBE_RECENT_WINDOW_SECONDS,
    so a fails-only ledger from a long session does not fire on every turn. When that ledger
    is missing or empty (the common case: `,probe` runs in a shell that has no
    harness session id and writes under the `ad-hoc` key), falls back to the
    workspace's shared `ad-hoc` ledger; the same recency window keeps another
    session's stale failures from firing the hint. Returns None when neither
    ledger yields entries.
    """
    if spec_dir is None:
        return None
    now = datetime.now(timezone.utc)
    rows = _parse_rows(_read_ledger(_probe_ledger_for(spec_dir, session_key_value)))
    if not rows and session_key_value != PROBE_AD_HOC_KEY:
        rows = _parse_rows(_read_ledger(_probe_ledger_for(spec_dir, PROBE_AD_HOC_KEY)))
    failures = sum(
        1
        for row in rows[-PROBE_BUDGET_WINDOW:]
        if row.get("result") == "fail" and _is_fresh(row, now, PROBE_RECENT_WINDOW_SECONDS)
    )
    if failures < PROBE_BUDGET_FAILURE_THRESHOLD:
        return None
    return "probe-budget-exhausted"


def detect(prompt: str, *, probe_budget_signal_value: str | None = None) -> str | None:
    """Return the first precision-first correction signal for `prompt`, if any.

    Pass `probe_budget_signal_value=probe_budget_signal(spec_dir, key)` from the per-turn
    caller so this detector can also surface "expectation may be wrong" without
    taking a dependency on the spec dir layout. Returns the probe-budget signal
    only when no higher-priority correction signal already matched.
    """
    text = str(prompt or "").strip()
    if len(text) < MIN_PROMPT_CHARS:
        return None
    text = text[:DETECT_MAX_CHARS]

    first_signal, first_pattern = PATTERNS[0]
    if first_pattern.search(text):
        return first_signal

    why_match = WHY_DID_YOU_RE.search(text)
    if why_match:
        window_start = max(0, why_match.start() - CONJUNCTION_WINDOW_CHARS)
        window = text[window_start : why_match.end() + CONJUNCTION_WINDOW_CHARS]
        if UNREQUESTED_ACTION_NEGATION_RE.search(window):
            return "unrequested-action"

    sure_match = ARE_YOU_SURE_RE.search(text)
    if sure_match and SURE_FOLLOWUP_RE.search(text[sure_match.end() : sure_match.end() + 400]):
        return "guessed-not-tested"

    for signal, pattern in PATTERNS[1:]:
        if pattern.search(text):
            return signal

    if probe_budget_signal_value:
        return probe_budget_signal_value

    return None
