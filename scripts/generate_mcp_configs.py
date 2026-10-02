#!/usr/bin/env python3
"""Generate tool-specific MCP configs from the canonical mcp_servers.yaml.

Usage:
    generate_mcp_configs.py <mcp_servers_yaml> <is_work> [tool]

Output: JSON with { "mcpServers": { ... } } on stdout.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from mcp_registry import load_servers

# Tool-specific HTTP server spec transformations.
# The registry emits a normalised shape:
#   { "type": "http", "url": "…", "oauth": { "clientId": "…", … } }
# Some tools expect a different wire format.
_TOOL_TRANSFORMS: dict[str | None, Any] = {}


def _transform_omp(spec: dict[str, Any]) -> dict[str, Any]:
    """Emit OMP's native MCP server shape, which names the transport explicitly."""
    if spec.get("type") != "http":
        return {
            "type": "stdio",
            "command": spec["command"],
            "args": spec.get("args", []),
        }
    return {"type": "http", "url": spec["url"]}


_TOOL_TRANSFORMS["omp"] = _transform_omp


def _transform_gemini(spec: dict[str, Any]) -> dict[str, Any]:
    """Emit Antigravity's ``mcp_config.json`` shape: remote servers use the ``serverUrl`` SSE field."""
    return {"serverUrl": spec["url"]}


_TOOL_TRANSFORMS["gemini"] = _transform_gemini


def _transform_pi(spec: dict[str, Any]) -> dict[str, Any]:
    """Pi's built-in MCP wants ``oauth`` with a singular space-separated ``scope``."""
    oauth = spec.get("oauth")
    out: dict[str, Any] = {"url": spec["url"]}
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
        out["oauth"] = pi_oauth
    return out


_TOOL_TRANSFORMS["pi"] = _transform_pi


# Tools whose transform must also rewrite stdio (not only http) specs.
_TRANSFORM_ALL_TYPES = {"omp"}


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


def render_document(yaml_path: str, is_work: bool, tool: str | None) -> dict[str, Any]:
    servers = load_servers(yaml_path, is_work, tool=tool)
    servers = _render_servers(servers, tool)
    document: dict[str, Any] = {"mcpServers": servers}
    if tool == "omp":
        document["$schema"] = (
            "https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/src/config/mcp-schema.json"
        )
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
