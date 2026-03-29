#!/usr/bin/env python3
"""Generate tool-specific MCP configs from the canonical mcp_servers.yaml.

Usage:
    generate_mcp_configs.py <mcp_servers_yaml> <is_work> [tool]

Output: JSON with { "mcpServers": { ... } } on stdout.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from mcp_registry import load_servers

# Tool-specific HTTP server spec transformations.
# The registry emits a normalised shape:
#   { "type": "http", "url": "…", "oauth": { "clientId": "…", … } }
# Some tools expect a different wire format.
_TOOL_TRANSFORMS: dict[str | None, Any] = {}


def _transform_cursor(spec: dict[str, Any]) -> dict[str, Any]:
    """Cursor uses ``auth.CLIENT_ID`` instead of ``oauth.clientId``."""
    out: dict[str, Any] = {"url": spec["url"]}
    oauth = spec.get("oauth")
    if oauth:
        auth: dict[str, Any] = {}
        if "clientId" in oauth:
            auth["CLIENT_ID"] = oauth["clientId"]
        if auth:
            out["auth"] = auth
    return out


_TOOL_TRANSFORMS["cursor"] = _transform_cursor


def _render_servers(servers: dict[str, dict[str, Any]], tool: str | None) -> dict[str, dict[str, Any]]:
    transform = _TOOL_TRANSFORMS.get(tool)
    if not transform:
        return servers
    result: dict[str, dict[str, Any]] = {}
    for name, spec in servers.items():
        if spec.get("type") == "http":
            result[name] = transform(spec)
        else:
            result[name] = spec
    return result


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit("Usage: generate_mcp_configs.py <mcp_servers_yaml> <is_work> [tool]")

    yaml_path = sys.argv[1]
    is_work = sys.argv[2] == "true"
    tool = sys.argv[3] if len(sys.argv) == 4 else None

    servers = load_servers(yaml_path, is_work, tool=tool)
    servers = _render_servers(servers, tool)
    doc = {"mcpServers": servers}
    print(json.dumps(doc, indent=2))


if __name__ == "__main__":
    main()
