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
    """Cursor IDE uses ``auth.CLIENT_ID`` instead of ``oauth.clientId``.
    However, cursor-cli expects the standard ``oauth`` shape with redirectUri.
    We emit both if ideClientId is provided.
    """
    out: dict[str, Any] = {"url": spec["url"]}
    oauth = spec.get("oauth")
    if oauth:
        cursor_oauth = dict(oauth)

        # 1. Output auth block for cursor-ide
        if "ideClientId" in cursor_oauth:
            out["auth"] = {"CLIENT_ID": cursor_oauth.pop("ideClientId")}
        elif "clientId" in cursor_oauth:
            out["auth"] = {"CLIENT_ID": cursor_oauth["clientId"]}

        # 2. Output oauth block for cursor-cli
        if "callbackPort" in cursor_oauth:
            port = cursor_oauth.pop("callbackPort")
            # cursor-cli expects http://localhost:port/callback but Slack forces https
            cursor_oauth["redirectUri"] = f"https://localhost:{port}/callback"

        if "scopes" in cursor_oauth and isinstance(cursor_oauth["scopes"], str):
            cursor_oauth["scopes"] = [s.strip() for s in cursor_oauth["scopes"].split(",") if s.strip()]

        # Only attach oauth if we have a clientId (some cases might only have ideClientId)
        if "clientId" in cursor_oauth:
            out["oauth"] = cursor_oauth

    return out


_TOOL_TRANSFORMS["cursor"] = _transform_cursor


def _transform_gemini(spec: dict[str, Any]) -> dict[str, Any]:
    """Gemini CLI expects 'url' (infers SSE from it) and uses 'redirectUri'
    instead of 'callbackPort' for OAuth.
    """
    out: dict[str, Any] = {"url": spec["url"]}
    oauth = spec.get("oauth")
    if oauth:
        gemini_oauth = dict(oauth)
        if "callbackPort" in gemini_oauth:
            port = gemini_oauth.pop("callbackPort")
            # Slack UI forces us to use https:// even for localhost
            gemini_oauth["redirectUri"] = f"https://localhost:{port}/oauth/callback"

        if "scopes" in gemini_oauth and isinstance(gemini_oauth["scopes"], str):
            gemini_oauth["scopes"] = [s.strip() for s in gemini_oauth["scopes"].split(",") if s.strip()]

        out["oauth"] = gemini_oauth
    return out


_TOOL_TRANSFORMS["gemini"] = _transform_gemini


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
