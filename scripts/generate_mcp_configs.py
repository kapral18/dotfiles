#!/usr/bin/env python3
"""Generate tool-specific MCP configs from the canonical mcp_servers.yaml.

Usage:
    generate_mcp_configs.py <mcp_servers_yaml> <is_work>

Output: JSON with { "mcpServers": { ... } } on stdout.
"""

import json
import sys

from mcp_registry import load_servers


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
