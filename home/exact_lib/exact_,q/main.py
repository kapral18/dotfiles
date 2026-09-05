#!/usr/bin/env python3
"""One-shot OpenRouter pi agent with tools and a short system prompt."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TextIO

OPENROUTER_PROVIDER = "openrouter"
Q_MODEL = "inclusionai/ling-3.0-flash"
# Non-empty: Pi treats "" as missing and rebuilds the coding-assistant default.
# Empty append skips ~/.pi/agent/APPEND_SYSTEM.md discovery. Pi still appends cwd.
Q_SYSTEM_PROMPT = "Be brief. Use tools when the question needs them."
Q_APPEND_SYSTEM_PROMPT = ""
Q_LITERAL_TEMPLATE = Path(__file__).with_name("q_literal.md")
Q_LITERAL_TEMPLATE_TEXT = "---\ntitle: Literal prompt transport\n---\n\n$1\n"


class PlanError(ValueError):
    """A user-visible invocation resolution error."""


class LauncherArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports failures through the launcher's error path."""

    def error(self, message: str) -> None:
        raise PlanError(message)


@dataclass(frozen=True)
class QCommand:
    prompt: str
    dry_run: bool


def _parser() -> argparse.ArgumentParser:
    parser = LauncherArgumentParser(
        prog=",q",
        description=(
            "One-shot OpenRouter pi agent with tools. Uses a short system prompt "
            "and skips APPEND_SYSTEM.md, skills, context files, extensions, "
            "themes, and discovered prompt templates. Prompt text is passed literally."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--dry-run", action="store_true", help="Emit the pi argv JSON; execute nothing")
    parser.add_argument("prompt", nargs="*", help="User prompt; omit to read stdin")
    return parser


def parse_q(
    argv: Sequence[str],
    *,
    stdin: TextIO | None = None,
    stdin_is_tty: bool | None = None,
) -> QCommand:
    """Parse `,q` arguments. Prompt comes from remaining words, else stdin."""

    args = _parser().parse_args(list(argv))
    prompt = " ".join(args.prompt)
    if not prompt:
        stream = sys.stdin if stdin is None else stdin
        is_tty = stream.isatty() if stdin_is_tty is None else stdin_is_tty
        if is_tty:
            raise PlanError("q requires a prompt argument or stdin")
        prompt = stream.read()
    if not prompt.strip():
        raise PlanError("q prompt is empty")
    return QCommand(prompt=prompt, dry_run=args.dry_run)


def leaf_argv(prompt: str) -> tuple[str, ...]:
    """Return the pi argv for a one-shot OpenRouter agent with discovery flags off."""

    try:
        template = Q_LITERAL_TEMPLATE.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PlanError(f"cannot read literal prompt template: {Q_LITERAL_TEMPLATE}") from error
    if template != Q_LITERAL_TEMPLATE_TEXT:
        raise PlanError(f"invalid literal prompt template: {Q_LITERAL_TEMPLATE}")
    if "\0" in prompt:
        raise PlanError("q prompt contains a NUL character")

    return (
        "pi",
        "--provider",
        OPENROUTER_PROVIDER,
        "--model",
        Q_MODEL,
        "--system-prompt",
        Q_SYSTEM_PROMPT,
        "--append-system-prompt",
        Q_APPEND_SYSTEM_PROMPT,
        "--no-session",
        "--thinking",
        "off",
        "--offline",
        "--no-skills",
        "--no-themes",
        "--no-context-files",
        "--no-prompt-templates",
        "--prompt-template",
        str(Q_LITERAL_TEMPLATE),
        "--no-extensions",
        "-p",
        f"/q_literal {shlex.quote(prompt)}",
    )


def execute(command: QCommand) -> int:
    argv = leaf_argv(command.prompt)
    if command.dry_run:
        print(
            json.dumps(
                {"q": True, "model": Q_MODEL, "argv": list(argv)},
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    try:
        os.execvpe(argv[0], list(argv), dict(os.environ))
    except FileNotFoundError:
        print(f",q: leaf command not found: {argv[0]}", file=sys.stderr)
        return 127
    except PermissionError:
        print(f",q: leaf command is not executable: {argv[0]}", file=sys.stderr)
        return 126
    return 127


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        return execute(parse_q(raw))
    except PlanError as error:
        print(f",q: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
