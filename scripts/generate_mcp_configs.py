#!/usr/bin/env python3
"""Generate tool-specific MCP configs from the canonical mcp_servers.yaml.

Usage:
    generate_mcp_configs.py <mcp_servers_yaml> <is_work> [tool]

Output: JSON with { "mcpServers": { ... } } on stdout.
"""

from __future__ import annotations

import json
import re
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
            # The redirect URI must EXACTLY match a Login redirect URI registered
            # on the OAuth app; a mismatch is rejected with 400 invalid_request.
            # These differ per provider, so allow an explicit override:
            #   - Slack's app UI forces https://localhost:<port>/oauth/callback
            #     (also gemini-cli's default path) -> keep as the fallback.
            #   - Elastic Okta (SCSI) registers http://localhost:<port>/callback.
            override = gemini_oauth.pop("redirectUri", None)
            if override:
                gemini_oauth["redirectUri"] = override.replace("{port}", str(port))
            else:
                gemini_oauth["redirectUri"] = f"https://localhost:{port}/oauth/callback"

        if "scopes" in gemini_oauth and isinstance(gemini_oauth["scopes"], str):
            gemini_oauth["scopes"] = [s.strip() for s in gemini_oauth["scopes"].split(",") if s.strip()]

        out["oauth"] = gemini_oauth
    return out


_TOOL_TRANSFORMS["gemini"] = _transform_gemini


def _transform_pi(spec: dict[str, Any]) -> dict[str, Any]:
    """pi-mcp-adapter wants ``oauth`` with a singular space-separated ``scope``
    and explicit ``auth: "oauth"``.
    """
    out: dict[str, Any] = {"url": spec["url"]}
    oauth = spec.get("oauth")
    if oauth:
        pi_oauth = dict(oauth)
        scope = pi_oauth.pop("scope", None)
        scopes = pi_oauth.pop("scopes", None)
        if isinstance(scopes, list):
            scopes = ", ".join(scopes)
        merged_scope = scope or scopes
        if merged_scope:
            # pi sends scope verbatim; normalise to space-separated tokens.
            pi_oauth["scope"] = " ".join(s.strip() for s in str(merged_scope).split(",") if s.strip())
        out["auth"] = "oauth"
        out["oauth"] = pi_oauth
    return out


_TOOL_TRANSFORMS["pi"] = _transform_pi


def _scopes_list(oauth: dict[str, Any]) -> list[str]:
    """Normalise a ``scope``/``scopes`` value to a list of space/comma tokens."""
    raw = oauth.get("scopes") or oauth.get("scope")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return [s.strip() for s in re.split(r"[,\s]+", raw) if s.strip()]
    return []


def _transform_copilot(spec: dict[str, Any]) -> dict[str, Any]:
    """GitHub Copilot CLI (~/.copilot/mcp-config.json).

    stdio  -> { type: "local", command, args, tools: ["*"] }
    http   -> { type: "http", url, tools: ["*"], oauthClientId, auth.redirectPort, oauthScopes }

    OAuth is expressed with ``oauthClientId`` + ``auth.redirectPort`` (the
    supported keys; Copilot also auto-migrates the legacy ``oauth.clientId`` /
    ``oauth.callbackPort`` shape, but we emit the canonical form). Copilot does
    the browser ``authorization_code`` flow and discovers endpoints from the
    server's protected-resource metadata, so no client secret is stored.

    A server may instead supply ``headerAuth`` (a pre-resolved Authorization
    header value such as ``Bearer <token>``) when Copilot cannot run the
    server's OAuth flow itself. In that case the browser flow is bypassed and
    the value is emitted as ``headers.Authorization``.
    """
    if spec.get("type") != "http":
        return {
            "type": "local",
            "command": spec["command"],
            "args": spec.get("args", []),
            "tools": ["*"],
        }

    out: dict[str, Any] = {"type": "http", "url": spec["url"], "tools": ["*"]}
    oauth = spec.get("oauth")
    if oauth:
        header_auth = oauth.get("headerAuth")
        if header_auth:
            out["headers"] = {"Authorization": header_auth}
            return out
        client_id = oauth.get("clientId")
        if client_id:
            out["oauthClientId"] = client_id
        port = oauth.get("callbackPort") or oauth.get("redirectPort")
        if port is not None:
            out["auth"] = {"redirectPort": int(port)}
        scopes = _scopes_list(oauth)
        if scopes:
            out["oauthScopes"] = scopes
    return out


_TOOL_TRANSFORMS["copilot"] = _transform_copilot

# Tools whose transform must also rewrite stdio (not only http) specs.
_TRANSFORM_ALL_TYPES = {"copilot"}


def _render_servers(servers: dict[str, dict[str, Any]], tool: str | None) -> dict[str, dict[str, Any]]:
    transform = _TOOL_TRANSFORMS.get(tool)
    if not transform:
        return servers
    transform_all = tool in _TRANSFORM_ALL_TYPES
    result: dict[str, dict[str, Any]] = {}
    for name, spec in servers.items():
        if spec.get("type") == "http" or transform_all:
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
    doc: dict[str, Any] = {"mcpServers": servers}
    # pi only: auto-run OAuth+reconnect on first tool call to a needs-auth
    # server (still opens the browser interactively).
    if tool == "pi":
        doc["settings"] = {"autoAuth": True}
    print(json.dumps(doc, indent=2))


if __name__ == "__main__":
    main()
