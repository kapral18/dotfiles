#!/usr/bin/env python3
"""Nudge the agent to verify a premise before a command whose outcome cannot expose it.

SOP 2.1 item 8's failure mode is not a missing probe, it is an *indistinguishable* one: a command
whose "it worked" and "the premise was wrong" outcomes look identical. `git stash` on a file
whose change is already committed stashes nothing, so the suite passes vacuously and "verified
by reverting" is false. Reverting, mocking, skipping, and force-pushing all share that shape.

This hook does not block. It matches the command text against a small set of premise-carrying
verbs and rides an `additionalContext` note along with the call, so the nudge lands at the step
that depends on the premise rather than at the end of the turn. Antigravity's `PreToolUse`
contract has no context channel, so it queues the note and injects it at the next `PreInvocation`.
Antigravity requires a `decision` on every `PreToolUse` response, so silent Antigravity
`PreToolUse` paths emit `{"decision":"allow"}`; an empty `{}` denies the tool with an empty reason.
A blocked command would be worse than an unverified one: the agent would work around the gate
instead of checking its premise.

Fires on both PreToolUse (before the premise is acted on) and PostToolUse (where a no-op result
is the tell). Unknown payloads, unmatched commands, and every parse failure are silent no-ops.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from hook_common import emit, read_payload, session_key, spec_dir_for, workspace_root

try:
    import correction_detector
except Exception:  # pragma: no cover - deployed alongside; fail open without it
    correction_detector = None

# `git` accepts global options before the subcommand, so `git -C <path> clean -fd` is the same
# destructive command as `git clean -fd`. Anchoring on `git\s+<sub>` missed every such form, and
# `-C` is the norm rather than the exception in agent use (bounded probes are written that way).
#
# Enumerating the known flags proved to be the wrong shape — `--no-pager`, `-p`, `-P`,
# `--exec-path=`, and `--namespace=` each silently missed a destructive command until added. Skip
# *any* leading option token instead, plus the separate value of the ones that take one. Nothing
# here is anchored to a flag name, so a git version that adds a global option cannot reopen this.
GIT = r"\bgit\s+(?:-{1,2}[A-Za-z][\w-]*(?:=\S+)?\s+(?:(?!-)\S+\s+)?)*"

# Commands whose success is indistinguishable from their premise being false. Each entry is
# (pattern, the premise the agent is implicitly asserting by running it).
PREMISE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(GIT + r"stash\b(?!\s+list)"),
        "that the change you are stashing is uncommitted — `git stash` on an already-committed "
        "file stashes nothing and the suite then passes vacuously",
    ),
    (
        # Only the discarding forms: `git checkout -- <path>` / `git checkout HEAD <path>` /
        # `git restore <path>`. Plain `git checkout <branch>` and `-b` switch branches and carry
        # no revert premise, so they must not fire.
        re.compile(GIT + r"checkout\s+(?:--\s|HEAD\b)|" + GIT + r"restore\b|" + GIT + r"revert\b"),
        "that the revert actually reverted — confirm the working tree changed, not just that the command exited 0",
    ),
    (
        # Only the discarding forms. `git reset --soft` keeps index and working tree, and
        # `git clean -n`/`--dry-run` discards nothing by definition, so neither carries the premise.
        # The clean lookahead must stop at the next command separator: scanning the whole line let
        # a later `echo -n` suppress a real `git clean -fd`. `-n` can sit anywhere in a combined
        # cluster (`-nfd`, `-fdn`), so the cluster is matched on both sides — but only over git
        # clean's argument-less short flags. `-e` takes a pattern, so `-en` means "exclude `n`",
        # not dry-run, and really does delete; including `e` here suppressed a destructive command.
        re.compile(
            GIT + r"reset\b(?!\s+--soft)"
            r"|" + GIT + r"clean\b(?!(?:(?!\s--\s)[^;&|\n])*(?:\s-[dfiqxX]*n[dfiqxX]*\b|--dry-run\b))"
        ),
        "that you know what this discards — confirm the target state before and after",
    ),
    (
        re.compile(GIT + r"push\b.*--force(?:-with-lease)?\b"),
        "that the remote is where you think it is — a force push is not observable after the fact",
    ),
    (
        # `-` is not a word char, so `\b-k\b` never matches; anchor on whitespace instead.
        # Skip markers need the runner prefix too: bare `.skip`/`xfail` matches `rg 'xfail' tests/`,
        # which is recon *about* skips, not a run that skipped anything.
        re.compile(
            r"\b(?:pytest|jest|vitest|go\s+test|cargo\s+test)\b"
            r".*(?:\s-k\b|\s-run\b|--filter\b|\.skip\b|\bxfail\b|\bskipif\b)"
        ),
        "that the tests you filtered to are the ones that would catch this — a narrowed selection "
        "can pass while the relevant test never ran",
    ),
    (
        # Only mock *construction*, never the bare word: `rg mock src/` and `npm install mock-fs`
        # are searching for or installing mocks, and asserting a premise about them is false.
        re.compile(
            r"\b(?:monkeypatch|mocker)\.\w|\bmock\.patch\b|\bunittest\.mock\b"
            r"|\b(?:jest|vi|sinon|td)\.(?:mock|doMock|mocked|stub|replace|spyOn)\b"
            r"|\bpatch\(\s*['\"]"
        ),
        "that the mock matches the real interface — a mock that drifted from its target makes the "
        "test pass for the wrong reason",
    ),
)

# Only shell-ish tools carry a command string worth matching.
SHELL_TOOLS = {"Bash", "shell", "run_command", "run_shell_command", "runTerminalCommand", "terminal"}
ANTIGRAVITY_OUTPUT = "antigravity"
PENDING_DIR = ".premise-nudges"


def command_from(payload: dict) -> str:
    """Pull the command text out of whichever shape this harness sent."""
    command = payload.get("command")
    if isinstance(command, str) and command:
        return command

    tool_input = payload.get("tool_input") or payload.get("arguments") or {}
    # Copilot sends arguments as a JSON string; every other harness sends an object.
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except ValueError:
            return ""
    if isinstance(tool_input, dict):
        value = tool_input.get("command") or tool_input.get("cmd") or ""
        return value if isinstance(value, str) else ""
    return ""


def premises_for(command: str) -> list[str]:
    seen: list[str] = []
    for pattern, premise in PREMISE_PATTERNS:
        if pattern.search(command) and premise not in seen:
            seen.append(premise)
    return seen


def _pending_dir(payload: dict) -> Path:
    key = session_key(payload) or "default"
    return spec_dir_for(workspace_root(payload)) / PENDING_DIR / key


def _store_antigravity_nudge(payload: dict, context: str) -> None:
    pending = _pending_dir(payload)
    pending.mkdir(parents=True, exist_ok=True)
    stem = f"{time.time_ns()}-{os.getpid()}"
    temporary = pending / f".{stem}.tmp"
    temporary.write_text(context, encoding="utf-8")
    os.replace(temporary, pending / f"{stem}.txt")


def _probe_budget_note(payload: dict) -> str:
    """Antigravity has no user-prompt hook, so the probe-budget hint rides PreInvocation.

    Emits only the signal header and the note: the prompt-correction framing and the
    convergence nudge of `perturn_recall.correction_directive` presume a user prompt,
    which this event does not carry.
    """
    if correction_detector is None:
        return ""
    try:
        spec_dir = spec_dir_for(workspace_root(payload))
        signal = correction_detector.probe_budget_signal(spec_dir, session_key(payload))
    except Exception:
        return ""
    if not signal:
        return ""
    return "\n".join((f"### User correction signal: {signal}", correction_detector.PROBE_BUDGET_NOTE))


def _emit_antigravity_pending(payload: dict) -> int:
    contexts: list[str] = []
    for path in sorted(_pending_dir(payload).glob("*.txt")):
        try:
            context = path.read_text(encoding="utf-8")
            if context and context not in contexts:
                contexts.append(context)
            path.unlink()
        except OSError:
            continue
    note = _probe_budget_note(payload)
    if note and note not in contexts:
        contexts.append(note)
    emit({"additional_context": "\n\n".join(contexts)} if contexts else {})
    return 0


def _silent(antigravity: bool, event: str) -> int:
    """No-op stdout for the active harness/event shape.

    Antigravity PreToolUse requires `decision`; every other silent path stays `{}`.
    """
    if antigravity and event == "PreToolUse":
        print(json.dumps({"decision": "allow"}, sort_keys=True))
        return 0
    print("{}")
    return 0


def main() -> int:
    antigravity = os.environ.get("AGENT_HOOK_OUTPUT") == ANTIGRAVITY_OUTPUT
    event = os.environ.get("AGENT_HOOK_EVENT", "").strip() or "PreToolUse"
    try:
        payload = read_payload()
    except (ValueError, json.JSONDecodeError):
        return _silent(antigravity, event)

    if not isinstance(payload, dict):
        return _silent(antigravity, event)

    event = str(payload.get("hook_event_name") or event)
    if antigravity and event == "PreInvocation":
        return _emit_antigravity_pending(payload)

    tool = payload.get("tool_name") or payload.get("tool") or ""
    # Cursor's shell events carry the command without naming a tool.
    if tool and tool not in SHELL_TOOLS:
        return _silent(antigravity, event)

    command = command_from(payload)
    if not command:
        return _silent(antigravity, event)

    premises = premises_for(command)
    if not premises:
        return _silent(antigravity, event)

    lines = [
        "### Premise check (SOP 2.1 item 8)",
        "This command's success would look the same whether or not its premise holds. "
        "Before relying on the result, verify:",
    ]
    lines.extend(f"- {premise}" for premise in premises)
    lines.append(
        "State the falsifier you ran, not the conclusion alone. Do not mention this note in the visible reply."
    )
    context = "\n".join(lines)

    if antigravity:
        if event == "PreToolUse":
            try:
                _store_antigravity_nudge(payload, context)
            except OSError:
                pass
            return _silent(True, "PreToolUse")
        emit({})
        return 0

    emit(
        {
            "additional_context": context,
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": context,
            },
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
