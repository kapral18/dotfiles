#!/usr/bin/env python3
"""Inject generated MCP servers into an OpenCode JSONC config.

We keep the canonical MCP registry in mcp_servers.yaml and generate OpenCode's
`mcp` section from it.

The base JSONC config must contain a placeholder property value:
  "mcp": "__MCP_SERVERS__",
which this script replaces with:
  "mcp": { ... },

Usage:
  inject_mcp_into_opencode_jsonc.py <mcp_servers_yaml> <is_work>

Input:  JSONC on stdin
Output: JSONC on stdout
"""

from __future__ import annotations

import sys

from jsonc_dump import dump_jsonc
from mcp_registry import load_servers

PLACEHOLDER = '"__MCP_SERVERS__"'


def _render_mcp_value(mcp_yaml: str, is_work: bool, tool: str | None = None) -> str:
    servers = load_servers(mcp_yaml, is_work, tool=tool)
    mcp_obj = {}
    for name, spec in servers.items():
        if spec.get("type") == "http":
            continue
        mcp_obj[name] = {
            "type": "local",
            "command": [spec["command"], *spec["args"]],
            "enabled": True,
        }

    raw = dump_jsonc(mcp_obj, indent=2)
    lines = raw.splitlines()
    if len(lines) == 1:
        return lines[0]

    # Indent lines after the first by 2 spaces so it aligns under `"mcp": {`.
    return "\n".join([lines[0], *[f"  {line}" for line in lines[1:]]])


def main() -> None:
    if len(sys.argv) not in (3, 4):
        sys.exit("Usage: inject_mcp_into_opencode_jsonc.py <mcp_servers_yaml> <is_work> [tool]")

    mcp_yaml = sys.argv[1]
    is_work = sys.argv[2] == "true"
    tool = sys.argv[3] if len(sys.argv) == 4 else None

    base = sys.stdin.read()
    if PLACEHOLDER not in base:
        sys.exit('Missing placeholder in JSONC: "mcp": "__MCP_SERVERS__"')

    rendered = _render_mcp_value(mcp_yaml, is_work, tool=tool)
    sys.stdout.write(base.replace(PLACEHOLDER, rendered, 1))


if __name__ == "__main__":
    main()
