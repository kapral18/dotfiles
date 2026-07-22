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
import os
import re
import shlex
import subprocess
import sys

MUTATING_SUBCOMMANDS = {"commit", "push"}
GIT_COMMAND_LOOKUP_TIMEOUT_SECONDS = 2

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
    "-h",
    "-p",
    "-P",
    "--paginate",
    "--no-pager",
    "--no-replace-objects",
    "--no-lazy-fetch",
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
GIT_WORD = re.compile(r"\bgit\b", re.IGNORECASE)
ENV_OPTS_WITH_VALUE = {"-a", "-C", "-P", "-u", "--argv0", "--chdir", "--unset"}
ENV_SPLIT_OPTS = {"-S", "--split-string"}
ENV_TERMINAL_OPTS = {"--help", "--version"}
INERT_TEXT_COMMANDS = {"cat", "echo", "egrep", "fgrep", "grep", "head", "printf", "rg", "tail", "wc"}


def _looks_like_git(token: str) -> bool:
    return token.replace("\\", "/").rsplit("/", 1)[-1].casefold() == "git"


def _command_name(token: str) -> str:
    return token.replace("\\", "/").rsplit("/", 1)[-1].casefold()


def _has_command_substitution(tokens: list[str]) -> bool:
    return any("$(" in token or "`" in token for token in tokens)


def _apply_env_assignment(environment: dict[str, str], assignment: str) -> None:
    key, value = assignment.split("=", 1)
    environment[key] = value


def _env_command_index(
    tokens: list[str],
    start: int,
    environment: dict[str, str],
) -> tuple[int, str | None] | None:
    """Locate env's utility without letting split-string hide a Git command."""
    i = start
    cwd = None
    while i < len(tokens):
        token = tokens[i]
        if ENV_ASSIGNMENT.match(token):
            _apply_env_assignment(environment, token)
            i += 1
            continue
        if token == "--":
            return i + 1, cwd
        if token in ENV_TERMINAL_OPTS:
            return len(tokens), cwd
        head = token.split("=", 1)[0]
        if token in ENV_SPLIT_OPTS or head in ENV_SPLIT_OPTS or token.startswith("-S"):
            return None
        if token in {"-i", "--ignore-environment", "-"}:
            environment.clear()
            i += 1
            continue
        if token in {"-0", "-v", "--null", "--debug", "--list-signal-handling"}:
            i += 1
            continue
        if re.fullmatch(r"-[0iv]+", token):
            if "i" in token:
                environment.clear()
            i += 1
            continue
        if token in ENV_OPTS_WITH_VALUE:
            if i + 1 >= len(tokens):
                return None
            value = tokens[i + 1]
            option = token
            i += 2
        elif head in ENV_OPTS_WITH_VALUE and "=" in token:
            option = head
            value = token.split("=", 1)[1]
            i += 1
        elif len(token) > 2 and token[:2] in {"-a", "-C", "-P", "-u"}:
            option = token[:2]
            value = token[2:]
            i += 1
        elif token.startswith(("--block-signal", "--default-signal", "--ignore-signal")):
            i += 1
            continue
        elif token.startswith("-"):
            return None
        else:
            return i, cwd

        if option in {"-C", "--chdir"}:
            cwd = value
        elif option == "-P":
            environment["PATH"] = value
        elif option in {"-u", "--unset"}:
            environment.pop(value, None)
    return i, cwd


def _is_known_git_subcommand(
    git_prefix: list[str],
    subcommand: str,
    environment: dict[str, str],
    cwd: str | None,
) -> bool:
    """Return true only for a built-in Git subcommand.

    Git aliases and external `git-*` commands can hide commit/push behavior, so
    they require approval rather than being executed to discover their effect.
    """
    try:
        result = subprocess.run(
            [*git_prefix, "--list-cmds=builtins"],
            capture_output=True,
            text=True,
            env=environment,
            cwd=cwd,
            timeout=GIT_COMMAND_LOOKUP_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and subcommand in result.stdout.split()


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
    environment = dict(os.environ)

    # Skip bare VAR=val prefixes, then parse an `env` wrapper.
    while i < n and ENV_ASSIGNMENT.match(tokens[i]):
        _apply_env_assignment(environment, tokens[i])
        i += 1
    cwd = None
    if i < n and tokens[i] == "env":
        env_command = _env_command_index(tokens, i + 1, environment)
        if env_command is None:
            return "unclassifiable"
        i, cwd = env_command

    if i >= n:
        return None
    executable = tokens[i]
    if "$" in executable or "`" in executable:
        return "unclassifiable"
    if not _looks_like_git(executable):
        if _command_name(executable) in INERT_TEXT_COMMANDS and not _has_command_substitution(tokens[i + 1 :]):
            return "safe"
        return None
    git_prefix = [executable]
    i += 1

    while i < n:
        token = tokens[i]
        if token in GIT_GLOBAL_OPTS_WITH_VALUE:
            if i + 1 >= n:
                return "unclassifiable"
            git_prefix.extend(tokens[i : i + 2])
            i += 2
            continue
        head = token.split("=", 1)[0]
        if "=" in token and head in GIT_GLOBAL_OPTS_WITH_VALUE:
            git_prefix.append(token)
            i += 1
            continue
        if token in GIT_GLOBAL_OPTS_NO_VALUE:
            git_prefix.append(token)
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
    if "$" in subcommand or "`" in subcommand:
        return "unclassifiable"
    normalized = subcommand.casefold()
    if normalized in MUTATING_SUBCOMMANDS:
        return normalized
    return "safe" if _is_known_git_subcommand(git_prefix, subcommand, environment, cwd) else "unclassifiable"


def classify_command(command: str) -> str:
    """Return "deny" or "allow" for a raw shell command line."""
    command = re.sub(r"\\\r?\n", "", command)
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
