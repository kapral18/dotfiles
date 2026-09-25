#!/usr/bin/env python3
"""Set the Codex root `developer_instructions` from the canonical SOP file.

Codex passes the global `~/.codex/AGENTS.md` to every spawned subagent (codex 0.157.0
`thread_manager.rs`: non-root agents inherit the parent's user instructions). Each managed
child role already sets its own `developer_instructions`, which replaces a top-level value
in its role layer, so carrying the SOP here reaches the root session only.

Usage:
  inject_codex_instructions.py <sop_path>    TOML on stdin, TOML with the key set on stdout

The key is inserted before the first table header (a TOML top-level key must precede tables).
An existing top-level `developer_instructions` in the input is an error: the SOP is the only source.
"""

from __future__ import annotations

import re
import sys

KEY = "developer_instructions"


def _toml_string(text: str) -> str:
    if "'''" not in text:
        # Multi-line literal string: no escapes; a newline right after the opener is trimmed.
        return "'''\n" + text + "'''"
    escaped = text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return '"""\n' + escaped + '"""'


def inject(toml_text: str, instructions: str) -> str:
    lines = toml_text.splitlines(keepends=True)
    first_table = next((i for i, line in enumerate(lines) if re.match(r"\s*\[", line)), len(lines))
    if any(re.match(rf"\s*{KEY}\s*=", line) for line in lines[:first_table]):
        raise ValueError(f"base config already sets top-level {KEY}")
    body = instructions if instructions.endswith("\n") else instructions + "\n"
    entry = f"{KEY} = {_toml_string(body)}\n\n"
    return "".join(lines[:first_table]) + entry + "".join(lines[first_table:])


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        instructions = handle.read()
    try:
        sys.stdout.write(inject(sys.stdin.read(), instructions))
    except ValueError as error:
        print(f"inject_codex_instructions: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
