#!/usr/bin/env python3
"""Inject generated Codex MCP servers into a base TOML config.

This keeps mcp server definitions single-sourced in mcp_servers.yaml while
allowing Codex's TOML config to stay as a mostly-static file.

Preferred pattern: base config contains a marker line:
  # __MCP_SERVERS__
which is replaced with generated TOML sections.

Usage:
  inject_mcp_into_codex_toml.py <base_toml_path> <mcp_servers_yaml> <is_work>

Output: merged TOML to stdout.
"""

from __future__ import annotations

import sys

from mcp_registry import load_servers

MARKER = "# __MCP_SERVERS__"


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render_codex_mcp_toml(mcp_yaml: str, is_work: bool) -> str:
    servers = load_servers(mcp_yaml, is_work)
    out_lines: list[str] = []
    for name, spec in servers.items():
        out_lines.append(f"[mcp_servers.{name}]")
        out_lines.append(f"command = {_toml_string(spec['command'])}")
        out_lines.append("args = [")
        for arg in spec["args"]:
            out_lines.append(f"  {_toml_string(str(arg))},")
        out_lines.append("]")
        out_lines.append("")
    return "\n".join(out_lines).rstrip() + "\n"


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit("Usage: inject_mcp_into_codex_toml.py <base_toml_path> <mcp_servers_yaml> <is_work>")

    base_path, mcp_yaml, is_work_raw = sys.argv[1], sys.argv[2], sys.argv[3]
    is_work = is_work_raw == "true"

    with open(base_path, "r") as f:
        base = f.read()

    snippet = _render_codex_mcp_toml(mcp_yaml, is_work)

    if MARKER in base:
        before, after = base.split(MARKER, 1)
        # Drop the marker line itself (including a trailing newline if present).
        if after.startswith("\n"):
            after = after[1:]
        sys.stdout.write(before.rstrip() + "\n\n" + snippet + "\n" + after.lstrip())
        return

    # Fallback: strip any existing [mcp_servers.*] blocks and append snippet.
    lines = base.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        if line.startswith("[mcp_servers.") and line.rstrip().endswith("]"):
            skipping = True
            continue
        if skipping:
            if line.startswith("[") and line.rstrip().endswith("]"):
                skipping = False
                out.append(line)
            else:
                continue
        else:
            out.append(line)

    sys.stdout.write("".join(out).rstrip() + "\n\n" + snippet)


if __name__ == "__main__":
    main()
