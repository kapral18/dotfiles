#!/usr/bin/env python3
"""Gate git commit/push to prevent rushing, shared by Cursor and Gemini CLI.

Cursor's `beforeShellExecution` payload carries the raw command as a
top-level `command` string. Gemini CLI's `BeforeTool` payload carries it as
`tool_input.command` alongside `tool_name == "run_shell_command"` (see
https://github.com/google-gemini/gemini-cli `docs/hooks/reference.md`). The
harness is identified from this shape, not guessed, so a malformed/ambiguous
payload fails closed instead of silently defaulting to one harness.

The command line is tokenized with `shlex` (respecting quotes, splitting on
`;`, `&&`, `||`, `|`, `&`, `(`, `)`, and newline) so the actual git
subcommand can be found after global options (`git -C . commit`,
`env X=1 git -c foo=bar push`). This is intentionally not a full shell
parser: any segment that mentions the word "git" but cannot be safely
classified as a direct, fully-recognized git invocation (unrecognized global
option, nested/quoted sub-shell such as `bash -c "git commit"`, unparseable
quoting) is treated as unclassifiable and denied. Only segments that are
definitely not git, or definitely a non-commit/non-push git subcommand, are
allowed.

Gemini CLI blocks a tool ONLY on exit code 2 (stderr becomes the reason);
any other non-zero exit is treated as a non-fatal warning and the tool still
runs. So on JSON-parse or shape failure we must not merely raise/exit(1); we
explicitly emit the reason on stderr and exit(2) to fail closed under both
harnesses (Cursor's `failClosed: true` also blocks on invalid/missing JSON
output).
"""

from __future__ import annotations

import json
import re
import shlex
import sys

MUTATING_SUBCOMMANDS = {"commit", "push"}

# Global options that consume a separate following token as their value
# (`-C <path>`, `-c <key>=<value>`, ...). Options passed as `--opt=value`
# are handled separately since they carry their value inline.
GIT_GLOBAL_OPTS_WITH_VALUE = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--super-prefix",
    "--exec-path",
    "--config-env",
}

# Global options that never take a value.
GIT_GLOBAL_OPTS_NO_VALUE = {
    "-p",
    "--paginate",
    "--no-pager",
    "--no-replace-objects",
    "--bare",
    "--literal-pathspecs",
    "--no-optional-locks",
    "--no-advice",
    "--version",
    "--help",
    "-v",
    "--html-path",
    "--man-path",
    "--info-path",
    "--list-cmds",
}

SEPARATORS = {";", "&&", "||", "&", "|", "(", ")", "\n"}
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
GIT_WORD = re.compile(r"\bgit\b")


def _looks_like_git(token: str) -> bool:
    return token == "git" or token.endswith("/git")


def _tokenize(command: str) -> list[str]:
    """Split a shell command line into shell-aware tokens.

    Raises ValueError on unbalanced quotes (caller decides how to fail closed).
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    return list(lexer)


def _split_segments(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in SEPARATORS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _classify_segment(tokens: list[str]) -> str | None:
    """Classify one top-level command segment.

    Returns "commit"/"push" for those git subcommands, "safe" for a fully
    recognized git invocation that definitely isn't commit/push,
    "unclassifiable" for a git invocation whose subcommand couldn't be
    located safely, or None if this segment isn't a direct git invocation.
    """
    i, n = 0, len(tokens)

    # Skip bare VAR=val prefixes, then an `env` wrapper and its own flags.
    while i < n and ENV_ASSIGNMENT.match(tokens[i]):
        i += 1
    if i < n and tokens[i] == "env":
        i += 1
        while i < n and (tokens[i].startswith("-") or ENV_ASSIGNMENT.match(tokens[i])):
            i += 1

    if i >= n or not _looks_like_git(tokens[i]):
        return None
    i += 1

    while i < n:
        token = tokens[i]
        if token in GIT_GLOBAL_OPTS_WITH_VALUE:
            i += 2
            continue
        head = token.split("=", 1)[0]
        if "=" in token and head in GIT_GLOBAL_OPTS_WITH_VALUE:
            i += 1
            continue
        if token in GIT_GLOBAL_OPTS_NO_VALUE:
            i += 1
            continue
        if token.startswith("-"):
            # An unrecognized global option: we can't know if it consumes a
            # following value, so the subcommand position can't be trusted.
            return "unclassifiable"
        break

    if i >= n:
        # Only recognized global options, no subcommand token at all -> this
        # definitely isn't commit/push.
        return "safe"

    subcommand = tokens[i]
    return subcommand if subcommand in MUTATING_SUBCOMMANDS else "safe"


def classify_command(command: str) -> str:
    """Return "deny" or "allow" for a raw shell command line."""
    try:
        tokens = _tokenize(command)
    except ValueError:
        # Unbalanced quoting defeats tokenization entirely.
        return "deny" if GIT_WORD.search(command) else "allow"

    for segment in _split_segments(tokens):
        verdict = _classify_segment(segment)
        if verdict in MUTATING_SUBCOMMANDS or verdict == "unclassifiable":
            return "deny"
        if verdict is None and GIT_WORD.search(" ".join(segment)):
            # Not a direct git invocation we can parse (e.g. `bash -c "git
            # commit"`, `sudo git push`), but git is mentioned in this
            # segment -> can't safely clear it.
            return "deny"

    return "allow"


WARNING = (
    "\u26a0\ufe0f GEMINI GIT WARNING: Gemini models frequently rush to commit "
    "and push without explicit permission. Stop and ask the user what to do next."
)


def _fail_closed(reason: str) -> None:
    print(reason, file=sys.stderr)
    sys.exit(2)


def _extract_command(payload: dict) -> tuple[str, bool] | None:
    """Return (command, is_gemini_cli), or None if the payload shape is unrecognized."""
    top_level_command = payload.get("command")
    if isinstance(top_level_command, str):
        return top_level_command, False

    if payload.get("tool_name") == "run_shell_command":
        tool_input = payload.get("tool_input")
        if isinstance(tool_input, dict) and isinstance(tool_input.get("command"), str):
            return tool_input["command"], True

    return None


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        _fail_closed(f"git-gate: could not parse hook input JSON ({exc}); failing closed.")
        return

    if not isinstance(payload, dict):
        _fail_closed("git-gate: hook input JSON was not an object; failing closed.")
        return

    extracted = _extract_command(payload)
    if extracted is None:
        _fail_closed("git-gate: could not identify the calling harness from hook input; failing closed.")
        return
    command, is_gemini_cli = extracted

    if classify_command(command) == "deny":
        if is_gemini_cli:
            print(json.dumps({"decision": "deny", "reason": WARNING}, sort_keys=True))
        else:
            print(
                json.dumps(
                    {
                        "permission": "ask",
                        "user_message": (
                            "\u26a0\ufe0f GEMINI GIT WARNING: Gemini models frequently rush to "
                            "commit and push without explicit permission. Did you explicitly ask "
                            "the agent to commit or push? If no, click Deny."
                        ),
                        "agent_message": (
                            "The user denied your git commit/push because you did not ask for "
                            "explicit permission first. Stop and ask the user what to do next."
                        ),
                    },
                    sort_keys=True,
                )
            )
        return

    if is_gemini_cli:
        print(json.dumps({"decision": "allow"}, sort_keys=True))
    else:
        print(json.dumps({"permission": "allow"}, sort_keys=True))


if __name__ == "__main__":
    main()
