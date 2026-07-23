#!/usr/bin/env python3
"""Generate tool-specific MCP configs from the canonical mcp_servers.yaml.

Usage:
    generate_mcp_configs.py <mcp_servers_yaml> <is_work> [tool]

Output: JSON with { "mcpServers": { ... } } on stdout.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from mcp_registry import TOKEN_BRIDGE_COMMAND, load_servers, token_bridge_args

# Tool-specific HTTP server spec transformations.
# The registry emits a normalised shape:
#   { "type": "http", "url": "…", "oauth": { "clientId": "…", … } }
# Some tools expect a different wire format.
_TOOL_TRANSFORMS: dict[str | None, Any] = {}


def _cursor_oauth_http(spec: dict[str, Any]) -> dict[str, Any]:
    """Emit Cursor's OAuth HTTP wire shape (IDE ``auth`` + CLI ``oauth``).

    Used for the mint-workspace config and for any Cursor HTTP server that does
    not opt into ``tokenBridge``.
    """
    out: dict[str, Any] = {"url": spec["url"]}
    oauth = spec.get("oauth")
    if oauth:
        cursor_oauth = dict(oauth)
        cursor_oauth.pop("tokenBridge", None)
        cursor_oauth.pop("retryConnectTimeouts", None)

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


def _transform_cursor(spec: dict[str, Any]) -> dict[str, Any]:
    """Cursor user ``~/.cursor/mcp.json`` runtime config.

    ``tokenBridge`` servers become the shared ``,mcp-token --bridge`` stdio
    transport (mid-session bearer refresh). OAuth HTTP shapes for those servers
    are emitted separately as ``cursor-oauth-mint`` for the mint workspace.
    """
    oauth = spec.get("oauth")
    if isinstance(oauth, dict) and oauth.get("tokenBridge"):
        return {
            "command": TOKEN_BRIDGE_COMMAND,
            "args": token_bridge_args(str(spec.get("url")), spec),
        }
    return _cursor_oauth_http(spec)


def _transform_cursor_oauth_mint(spec: dict[str, Any]) -> dict[str, Any]:
    """OAuth-only Cursor shapes for the mint workspace (no bridges, no stdio)."""
    return _cursor_oauth_http(spec)


_TOOL_TRANSFORMS["cursor"] = _transform_cursor
_TOOL_TRANSFORMS["cursor-oauth-mint"] = _transform_cursor_oauth_mint


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

    A server may instead supply ``tokenBridge`` (a ,mcp-token token source)
    when Copilot cannot run the server's OAuth flow itself. The server is then
    emitted as a *local* stdio bridge (",mcp-token <source> --bridge --url
    <url>") that injects a freshly selected bearer per request, so the session
    never depends on a launch-time token capture.
    """
    if spec.get("type") != "http":
        return {
            "type": "local",
            "command": spec["command"],
            "args": spec.get("args", []),
            "tools": ["*"],
        }

    oauth = spec.get("oauth")
    if isinstance(oauth, dict) and oauth.get("tokenBridge"):
        return {
            "type": "local",
            "command": TOKEN_BRIDGE_COMMAND,
            "args": token_bridge_args(str(spec.get("url")), spec),
            "tools": ["*"],
        }
    out: dict[str, Any] = {"type": "http", "url": spec["url"], "tools": ["*"]}
    if oauth:
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
    # Mint workspace only needs OAuth HTTP servers (bridges are the user runtime).
    http_only = tool == "cursor-oauth-mint"
    result: dict[str, dict[str, Any]] = {}
    for name, spec in servers.items():
        if http_only and spec.get("type") != "http":
            continue
        if spec.get("type") == "http" or transform_all:
            result[name] = transform(spec)
        else:
            result[name] = spec
    return result


def render_document(yaml_path: str, is_work: bool, tool: str | None) -> dict[str, Any]:
    # cursor-oauth-mint reuses the cursor oauth_by_tool block (client ids, scopes)
    # then strips tokenBridge in the transform.
    load_tool = "cursor" if tool == "cursor-oauth-mint" else tool
    servers = load_servers(yaml_path, is_work, tool=load_tool)
    servers = _render_servers(servers, tool)
    document: dict[str, Any] = {"mcpServers": servers}
    if tool == "pi":
        document["settings"] = {"autoAuth": True}
    return document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        usage="generate_mcp_configs.py <mcp_servers_yaml> <is_work> [tool]",
        description=__doc__,
    )
    parser.add_argument("mcp_servers_yaml")
    parser.add_argument("is_work")
    parser.add_argument("tool", nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    is_work = args.is_work == "true"
    document = render_document(args.mcp_servers_yaml, is_work, args.tool)
    print(json.dumps(document, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as err:
        raise SystemExit(f"Error: {err}") from err
