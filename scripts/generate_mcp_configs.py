#!/usr/bin/env python3
"""Generate tool-specific MCP configs from the canonical mcp_servers.yaml.

Usage:
    generate_mcp_configs.py <mcp_servers_yaml> <is_work>

Output: JSON with { "mcpServers": { ... } } on stdout.
"""

import json
import re
import sys


def _parse_scalar(raw):
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1].replace('\\"', '"')
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    if raw == "true":
        return True
    if raw == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    return raw


def load_servers(path, is_work):
    with open(path, "r") as f:
        lines = f.readlines()

    servers = []
    current = None
    in_args = False
    args_indent = 0

    for line in lines:
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if stripped.lstrip() == "mcp_servers:":
            continue

        indent = len(line) - len(line.lstrip())

        new_entry = re.match(r"^\s+-\s+(\w[\w_]*):\s*(.*)", stripped)
        if new_entry:
            in_args = False
            current = {"name": None, "work_only": False, "command": None, "args": []}
            servers.append(current)
            key, val = new_entry.group(1), new_entry.group(2).strip()
            current[key] = _parse_scalar(val)
            continue

        if in_args:
            item = re.match(r"^\s+-\s+(.*)", stripped)
            if item and indent >= args_indent:
                current["args"].append(_parse_scalar(item.group(1)))
                continue
            else:
                in_args = False

        kv = re.match(r"^\s+(\w[\w_]*):\s*(.*)", stripped)
        if kv and current is not None:
            key, val = kv.group(1), kv.group(2).strip()
            if key == "args" and not val:
                in_args = True
                args_indent = indent + 2
            else:
                current[key] = _parse_scalar(val)

    result = {}
    for s in servers:
        if s.get("work_only") and not is_work:
            continue
        result[s["name"]] = {"command": s["command"], "args": s["args"]}
    return result


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: generate_mcp_configs.py <mcp_servers_yaml> <is_work>")

    yaml_path = sys.argv[1]
    is_work = sys.argv[2] == "true"

    servers = load_servers(yaml_path, is_work)
    doc = {"mcpServers": servers}
    print(json.dumps(doc, indent=2))


if __name__ == "__main__":
    main()
