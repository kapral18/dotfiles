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
parser: direct Git invocations and recognized shell/direct-execution wrappers are classified to their actual Git subcommand. `$(...)` and backtick substitution bodies are classified recursively as their own command lines. Unrecognized Git options, ambiguous wrappers, and unparseable quoting fail closed. Non-Git arguments, including `.git` paths and inert quoted text mentioning Git, are allowed.

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
_SEPARATOR_CHARS = frozenset("".join(SEPARATORS))
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
GIT_WORD = re.compile(r"\bgit\b", re.IGNORECASE)
ENV_OPTS_WITH_VALUE = {"-a", "-C", "-P", "-u", "--argv0", "--chdir", "--unset"}
ENV_SPLIT_OPTS = {"-S", "--split-string"}
ENV_TERMINAL_OPTS = {"--help", "--version"}
INERT_TEXT_COMMANDS = {"cat", "echo", "egrep", "fgrep", "grep", "head", "printf", "rg", "tail", "wc"}
SHELL_COMMAND_WRAPPERS = {"bash", "dash", "fish", "ksh", "sh", "zsh"}
DIRECT_EXECUTION_WRAPPERS = {"command", "doas", "env", "nohup", "sudo", "time"}
WRAPPER_FLAGS = {
    "command": {"-p", "-v", "-V"},
    "doas": {"-n", "-s"},
    "nohup": set(),
    "sudo": {"-A", "-b", "-E", "-e", "-H", "-i", "-k", "-K", "-l", "-n", "-s", "-S", "-U", "-V", "-v"},
    "time": {"-p", "--portability"},
}
WRAPPER_OPTS_WITH_VALUE = {
    "doas": {"-C", "-u"},
    "sudo": {
        "-C",
        "-g",
        "-h",
        "-p",
        "-r",
        "-t",
        "-u",
        "--chdir",
        "--group",
        "--host",
        "--other-user",
        "--prompt",
        "--role",
        "--type",
        "--user",
    },
    "time": {"-f", "-o", "--format", "--output"},
}


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
    lexer.commenters = ""
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    return list(lexer)


def _read_heredoc_word(command_line: str, start: int) -> tuple[str, int] | None:
    """Read a here-doc delimiter word with shell quoting removed."""
    i = start
    while i < len(command_line) and command_line[i] in " \t":
        i += 1
    if i >= len(command_line):
        return None

    chars: list[str] = []
    quote = ""
    while i < len(command_line):
        char = command_line[i]
        if quote == "'":
            if char == "'":
                quote = ""
            else:
                chars.append(char)
            i += 1
            continue
        if quote == '"':
            if char == '"':
                quote = ""
            elif char == "\\" and i + 1 < len(command_line):
                i += 1
                chars.append(command_line[i])
            else:
                chars.append(char)
            i += 1
            continue
        if char == "\\" and i + 1 < len(command_line):
            i += 1
            chars.append(command_line[i])
        elif char in {"'", '"'}:
            quote = char
        elif char.isspace() or char in "();<>|&":
            break
        else:
            chars.append(char)
        i += 1

    delimiter = "".join(chars)
    return (delimiter, i) if delimiter else None


def _is_shell_comment_start(command_line: str, index: int) -> bool:
    if command_line[index] != "#":
        return False
    return index == 0 or command_line[index - 1].isspace() or command_line[index - 1] in "();<>|&"


def _strip_shell_comments(command: str) -> str:
    """Remove shell comments while preserving line boundaries."""
    output: list[str] = []
    quote = ""
    i = 0
    while i < len(command):
        char = command[i]
        if quote == "'":
            output.append(char)
            quote = "" if char == "'" else quote
            i += 1
            continue
        if quote == '"':
            output.append(char)
            if char == "\\" and i + 1 < len(command):
                i += 1
                output.append(command[i])
            else:
                quote = "" if char == '"' else quote
            i += 1
            continue
        if char == "\\" and i + 1 < len(command):
            output.extend([char, command[i + 1]])
            i += 2
            continue
        if char in {"'", '"'}:
            quote = char
            output.append(char)
            i += 1
            continue
        if _is_shell_comment_start(command, i):
            while i < len(command) and command[i] not in "\r\n":
                i += 1
            # Keep a separator so a comment never glues the preceding
            # metacharacter to the following newline (`;#c\ngit push`).
            output.append(" ")
            continue
        output.append(char)
        i += 1
    return "".join(output)


def _heredoc_delimiters(command_line: str) -> list[tuple[str, bool]]:
    """Return here-doc delimiters declared by one shell command line."""
    delimiters: list[tuple[str, bool]] = []
    quote = ""
    i = 0
    while i < len(command_line):
        char = command_line[i]
        if quote == "'":
            quote = "" if char == "'" else quote
            i += 1
            continue
        if quote == '"':
            if char == "\\":
                i += 2
                continue
            quote = "" if char == '"' else quote
            i += 1
            continue
        if char == "\\":
            i += 2
            continue
        if char in {"'", '"'}:
            quote = char
            i += 1
            continue
        if _is_shell_comment_start(command_line, i):
            break
        if command_line.startswith("<<<", i):
            i += 3
            continue
        if command_line.startswith("<<", i):
            strip_tabs = command_line.startswith("<<-", i)
            word = _read_heredoc_word(command_line, i + (3 if strip_tabs else 2))
            if word is None:
                i += 2
                continue
            delimiter, i = word
            delimiters.append((delimiter, strip_tabs))
            continue
        i += 1
    return delimiters


def _extract_heredoc_bodies(command: str) -> tuple[str, list[tuple[str, str]]] | None:
    """Remove here-doc bodies and return each body with its declaring command line."""
    output_lines: list[str] = []
    bodies: list[tuple[str, str]] = []
    pending: list[tuple[str, bool, str, list[str]]] = []

    for line in command.splitlines(keepends=True):
        if pending:
            delimiter, strip_tabs, declaration, body_lines = pending[0]
            candidate = line.rstrip("\r\n")
            if strip_tabs:
                candidate = candidate.lstrip("\t")
            if candidate == delimiter:
                bodies.append((declaration, "".join(body_lines)))
                pending.pop(0)
            else:
                body_lines.append(line)
            continue

        output_lines.append(line)
        for delimiter, strip_tabs in _heredoc_delimiters(line):
            pending.append((delimiter, strip_tabs, line, []))

    return None if pending else ("".join(output_lines), bodies)


def _extract_substitution_bodies(command: str) -> list[str] | None:
    """Extract the inner text of every `$(...)` and backtick substitution.

    Returns None on unbalanced delimiters or quotes (caller decides how to fail
    closed). Backslash-escaped `\$(` and `` \` `` are literal and skipped.
    Single-quoted text is literal in the shell, so substitution-looking text
    inside single quotes is skipped; double quotes do not suppress
    substitution, so bodies there are still classified.
    """
    bodies: list[str] = []
    i = 0
    quote = ""
    while i < len(command):
        char = command[i]
        if quote == "'":
            if char == "'":
                quote = ""
            i += 1
            continue
        if char == "\\":
            i += 2
            continue
        if quote == "":
            if char == "'":
                quote = "'"
                i += 1
                continue
            if char == '"':
                quote = '"'
                i += 1
                continue
        elif char == '"':
            quote = ""
            i += 1
            continue
        if char == "`":
            j = i + 1
            while j < len(command) and command[j] != "`":
                j += 2 if command[j] == "\\" else 1
            if j >= len(command):
                return None
            bodies.append(command[i + 1 : j])
            i = j + 1
            continue
        if command.startswith("$(", i):
            # The body is a command list: quotes inside it group, so a `)`
            # inside quotes does not close the substitution, and `$(` inside
            # double quotes still nests. Single quotes suppress nesting.
            depth = 1
            j = i + 2
            inner_quote = ""
            while j < len(command) and depth > 0:
                char = command[j]
                if inner_quote == "'":
                    if char == "'":
                        inner_quote = ""
                    j += 1
                    continue
                if char == "\\":
                    j += 2
                    continue
                if inner_quote == '"':
                    if char == '"':
                        inner_quote = ""
                    elif command.startswith("$(", j):
                        depth += 1
                        j += 1
                    j += 1
                    continue
                if char == "'":
                    inner_quote = "'"
                    j += 1
                    continue
                if char == '"':
                    inner_quote = '"'
                    j += 1
                    continue
                if command.startswith("$(", j):
                    depth += 1
                    j += 2
                    continue
                if char == ")":
                    depth -= 1
                j += 1
            if depth > 0 or inner_quote:
                return None
            bodies.append(command[i + 2 : j - 1])
            i = j
            continue
        i += 1
    if quote:
        # Unbalanced quote: tokenization will also fail, so fail closed here.
        return None
    return bodies


def _wrapper_command_index(wrapper: str, tokens: list[str], start: int) -> int | None:
    """Locate a direct-execution wrapper's target command, failing closed on unknown options."""
    if wrapper == "env":
        result = _env_command_index(tokens, start, dict(os.environ))
        return None if result is None else result[0]

    flags = WRAPPER_FLAGS[wrapper]
    options_with_value = WRAPPER_OPTS_WITH_VALUE.get(wrapper, set())
    i = start
    while i < len(tokens):
        token = tokens[i]
        if token == "--":
            return i + 1 if i + 1 < len(tokens) else None
        if token in flags:
            i += 1
            continue
        if token in options_with_value:
            if i + 1 >= len(tokens):
                return None
            i += 2
            continue
        if token.startswith("-"):
            return None
        return i
    return None


def _wrapped_command_can_run_mutating_git(tokens: list[str]) -> bool:
    """Return whether a recognized wrapper can hide a gated Git command."""
    i = 0
    while i < len(tokens) and ENV_ASSIGNMENT.match(tokens[i]):
        i += 1
    if i >= len(tokens):
        return False

    wrapper = _command_name(tokens[i])
    arguments = tokens[i + 1 :]
    if wrapper in SHELL_COMMAND_WRAPPERS:
        for index, argument in enumerate(arguments):
            if argument == "--":
                return False
            if argument.startswith("-") and not argument.startswith("--") and "c" in argument[1:]:
                return index + 1 < len(arguments) and classify_command(arguments[index + 1]) == "deny"
        return False
    if wrapper not in DIRECT_EXECUTION_WRAPPERS:
        return False

    target = _wrapper_command_index(wrapper, tokens, i + 1)
    if target is None:
        return bool(GIT_WORD.search(" ".join(arguments)))
    verdict = _classify_segment(tokens[target:])
    if verdict in MUTATING_SUBCOMMANDS or verdict == "unclassifiable":
        return True
    return verdict is None and _wrapped_command_can_run_mutating_git(tokens[target:])


def _split_segments(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = [[]]
    for token in tokens:
        # shlex merges adjacent punctuation into one token (e.g. `)\n`, `;\n`),
        # so treat any all-separator token as a separator.
        if token in SEPARATORS or (token and all(char in _SEPARATOR_CHARS for char in token)):
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _tokens_without_redirections(tokens: list[str]) -> list[str]:
    command_tokens: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.isdigit() and i + 1 < len(tokens) and any(char in tokens[i + 1] for char in "<>"):
            i += 1
            continue
        if "<" in token or ">" in token:
            i += 1
            if i < len(tokens):
                i += 1
            continue
        command_tokens.append(token)
        i += 1
    return command_tokens


def _tokens_resolve_to_shell(tokens: list[str]) -> bool:
    i = 0
    while i < len(tokens) and ENV_ASSIGNMENT.match(tokens[i]):
        i += 1
    if i >= len(tokens):
        return False

    command = _command_name(tokens[i])
    if command in SHELL_COMMAND_WRAPPERS:
        return True
    if command not in DIRECT_EXECUTION_WRAPPERS:
        return False

    target = _wrapper_command_index(command, tokens, i + 1)
    if target is None:
        return any(_command_name(token) in SHELL_COMMAND_WRAPPERS for token in tokens[i + 1 :])
    return _tokens_resolve_to_shell(tokens[target:])


def _heredoc_declaration_runs_shell(declaration: str) -> bool:
    try:
        segments = _split_segments(_tokenize(_strip_shell_comments(declaration)))
    except ValueError:
        return bool(GIT_WORD.search(declaration))
    return any(_tokens_resolve_to_shell(_tokens_without_redirections(segment)) for segment in segments)


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
    extracted = _extract_heredoc_bodies(re.sub(r"\\\r?\n", "", command))
    if extracted is None:
        return "deny"
    heredoc_stripped, heredoc_bodies = extracted
    for declaration, body in heredoc_bodies:
        if _heredoc_declaration_runs_shell(declaration) and classify_command(body) == "deny":
            return "deny"
    command = _strip_shell_comments(heredoc_stripped)
    # Substitution bodies are executable code: classify each as its own
    # command line instead of denying on a co-occurring inert "git" mention.
    substitutions = _extract_substitution_bodies(command)
    if substitutions is None:
        return "deny" if GIT_WORD.search(command) else "allow"
    if any(classify_command(body) == "deny" for body in substitutions):
        return "deny"
    try:
        tokens = _tokenize(command)
    except ValueError:
        # Unbalanced quoting defeats tokenization entirely.
        return "deny" if GIT_WORD.search(command) else "allow"

    for segment in _split_segments(tokens):
        verdict = _classify_segment(segment)
        if verdict in MUTATING_SUBCOMMANDS or verdict == "unclassifiable":
            return "deny"
        if verdict is None and _wrapped_command_can_run_mutating_git(segment):
            # Shell and direct-execution wrappers can hide the real executable.
            # Arbitrary argv text such as a `.git` path cannot.
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

    try:
        verdict = classify_command(command)
    except RecursionError:
        # Deeply nested substitutions/heredocs can exhaust the recursion
        # budget; an unclassified command must fail closed, not warn.
        _fail_closed("git-gate: command nesting exceeded parser limits; failing closed.")
        return

    if verdict == "deny":
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
