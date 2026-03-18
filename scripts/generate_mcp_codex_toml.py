#!/usr/bin/env python3
"""Generate Codex TOML mcp_servers blocks from the canonical MCP registry.

Usage:
  generate_mcp_codex_toml.py <mcp_servers_yaml> <is_work>

Output: TOML snippet (multiple [mcp_servers.<name>] sections) to stdout.
"""

from __future__ import annotations

import sys

from mcp_registry import load_servers


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("Usage: generate_mcp_codex_toml.py <mcp_servers_yaml> <is_work>")

    yaml_path = sys.argv[1]
    is_work = sys.argv[2] == "true"

    servers = load_servers(yaml_path, is_work)

    out_lines: list[str] = []
    for name, spec in servers.items():
        out_lines.append(f"[mcp_servers.{name}]")
        out_lines.append(f"command = {_toml_string(spec['command'])}")
        out_lines.append("args = [")
        for arg in spec["args"]:
            out_lines.append(f"  {_toml_string(str(arg))},")
        out_lines.append("]")
        out_lines.append("")

    sys.stdout.write("\n".join(out_lines).rstrip() + "\n")


if __name__ == "__main__":
    main()
