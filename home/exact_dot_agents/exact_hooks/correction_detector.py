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

import re

MIN_PROMPT_CHARS = 12
DETECT_MAX_CHARS = 20000
CONJUNCTION_WINDOW_CHARS = 160

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


def detect(prompt: str) -> str | None:
    """Return the first precision-first correction signal for `prompt`, if any."""
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

    return None
