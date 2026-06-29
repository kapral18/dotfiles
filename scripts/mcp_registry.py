#!/usr/bin/env python3
"""Utilities for reading the canonical MCP registry.

The source of truth for MCP servers lives in:
  home/.chezmoidata/mcp_servers.yaml

This module intentionally avoids external dependencies (no PyYAML).
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

from yaml_parser import parse_scalar

_SHELL_SUBST = re.compile(r"^\$\((.+)\)$")
_HEADER_AUTH_REFRESH_REQUIRED = "Bearer __MCP_TOKEN_REFRESH_REQUIRED__"


def _resolve_shell(value: Any) -> Any:
    """Resolve a ``$(command)`` string by running it in a login shell.

    Only full-value substitutions are resolved (the entire string must be
    ``$(…)``).  Partial substitutions embedded in larger strings are left
    as-is — those are intended for runtime expansion (e.g. stdio server
    args executed by bash -lc).
    """
    if not isinstance(value, str):
        return value
    m = _SHELL_SUBST.match(value)
    if not m:
        return value
    result = subprocess.run(
        ["bash", "-lc", m.group(1)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"shell eval failed: {m.group(1)!r}\n{result.stderr}")
    return result.stdout.strip()


def _resolve_oauth_value(key: str, value: Any) -> Any:
    """Resolve an OAuth config value, keeping header-token refresh at launch time.

    ``headerAuth`` values often read short-lived local OAuth tokens. A stale token
    must not make ``chezmoi apply`` fail; launchers such as `,copilot` refresh and
    re-bake these headers immediately before starting the client.
    """
    try:
        return _resolve_shell(value)
    except RuntimeError as exc:
        if key == "headerAuth":
            print(
                f"Warning: headerAuth token unavailable during apply; emitting refresh placeholder ({exc})",
                file=sys.stderr,
            )
            return _HEADER_AUTH_REFRESH_REQUIRED
        raise


def load_servers(path: str, is_work: bool, tool: str | None = None) -> dict[str, dict[str, Any]]:
    """Load servers from the canonical YAML registry.

    Returns mapping:
      name -> server spec dict

    Stdio servers:  { "command": str, "args": list[str] }
    HTTP servers:   { "type": "http", "url": str, "oauth": { ... } }

    When *tool* is given, ``oauth_by_tool`` entries are resolved: only the
    matching tool's OAuth block is included (as ``oauth``). Unmatched tools
    cause the server to be omitted entirely. A plain ``oauth`` block (not per-tool)
    is always included regardless of *tool*.

    A server may also carry an ``exclude_tools`` list; when *tool* is in that
    list the server is omitted (used for non-OAuth servers that cannot express
    per-tool membership via ``oauth_by_tool``).
    """
    with open(path, "r") as f:
        lines = f.readlines()

    servers: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_args = False
    args_indent = 0
    in_list = False
    list_key = ""
    list_indent = 0
    in_oauth = False
    oauth_indent = 0
    in_kv_map = False
    kv_map_key = ""
    kv_map_indent = 0
    # oauth_by_tool nesting: level 0 = tool keys, level 1 = props of a tool
    in_oauth_by_tool = False
    obt_indent = 0
    obt_tool_name: str | None = None
    obt_tool_indent = 0

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
            in_list = False
            in_oauth = False
            in_kv_map = False
            in_oauth_by_tool = False
            obt_tool_name = None
            current = {"name": None, "work_only": False, "command": None, "args": []}
            servers.append(current)
            key, val = new_entry.group(1), new_entry.group(2).strip()
            current[key] = parse_scalar(val)
            continue

        if in_args and current is not None:
            item = re.match(r"^\s+-\s+(.*)", stripped)
            if item and indent >= args_indent:
                current["args"].append(parse_scalar(item.group(1)))
                continue
            else:
                in_args = False

        if in_list and current is not None:
            item = re.match(r"^\s+-\s+(.*)", stripped)
            if item and indent >= list_indent:
                current.setdefault(list_key, []).append(parse_scalar(item.group(1)))
                continue
            else:
                in_list = False

        if in_oauth_by_tool and current is not None:
            if indent < obt_indent:
                in_oauth_by_tool = False
                obt_tool_name = None
            else:
                # Tool-level key (e.g. "claude:") or property within a tool
                kv = re.match(r"^\s+(\w[\w_]*):\s*(.*)", stripped)
                if kv:
                    key, val = kv.group(1), kv.group(2).strip()
                    if not val:
                        # New tool sub-block
                        obt_tool_name = key
                        obt_tool_indent = indent + 2
                    elif obt_tool_name and indent >= obt_tool_indent:
                        # Property of the current tool
                        current.setdefault("oauth_by_tool", {}).setdefault(obt_tool_name, {})[key] = parse_scalar(val)
                    else:
                        # New tool sub-block at same indent as previous tool
                        # with inline value — treat as a new tool key
                        obt_tool_name = key
                        obt_tool_indent = indent + 2
                continue

        if in_oauth and current is not None:
            kv = re.match(r"^\s+(\w[\w_]*):\s*(.*)", stripped)
            if kv and indent >= oauth_indent:
                current.setdefault("oauth", {})[kv.group(1)] = parse_scalar(kv.group(2).strip())
                continue
            else:
                in_oauth = False

        if in_kv_map and current is not None:
            kv = re.match(r"^\s+(\w[\w_]*):\s*(.*)", stripped)
            if kv and indent >= kv_map_indent:
                current.setdefault(kv_map_key, {})[kv.group(1)] = parse_scalar(kv.group(2).strip())
                continue
            else:
                in_kv_map = False

        kv = re.match(r"^\s+(\w[\w_]*):\s*(.*)", stripped)
        if kv and current is not None:
            key, val = kv.group(1), kv.group(2).strip()
            if key == "args" and not val:
                in_args = True
                args_indent = indent + 2
            elif key == "exclude_tools" and not val:
                in_list = True
                list_key = key
                list_indent = indent + 2
                current.setdefault(key, [])
            elif key == "oauth" and not val:
                in_oauth = True
                oauth_indent = indent + 2
            elif key == "codex_tool_approval_modes" and not val:
                in_kv_map = True
                kv_map_key = key
                kv_map_indent = indent + 2
                current.setdefault(key, {})
            elif key == "oauth_by_tool" and not val:
                in_oauth_by_tool = True
                obt_indent = indent + 2
                obt_tool_name = None
            else:
                current[key] = parse_scalar(val)

    result: dict[str, dict[str, Any]] = {}
    for s in servers:
        if s.get("work_only") and not is_work:
            continue

        if tool and "oauth_by_tool" in s and tool not in s["oauth_by_tool"]:
            continue

        if tool and tool in s.get("exclude_tools", []):
            continue

        if s.get("type") == "http":
            spec: dict[str, Any] = {"type": "http", "url": _resolve_shell(s["url"])}
            if "oauth" in s:
                spec["oauth"] = {k: _resolve_oauth_value(k, v) for k, v in s["oauth"].items()}
            elif "oauth_by_tool" in s and tool:
                tool_oauth = s["oauth_by_tool"].get(tool)
                if tool_oauth:
                    spec["oauth"] = {k: _resolve_oauth_value(k, v) for k, v in tool_oauth.items()}
            if tool == "codex" and "codex_default_tools_approval_mode" in s:
                spec["codex_default_tools_approval_mode"] = s["codex_default_tools_approval_mode"]
            if tool == "codex" and "codex_tool_approval_modes" in s:
                spec["codex_tool_approval_modes"] = s["codex_tool_approval_modes"]
            result[s["name"]] = spec
        else:
            spec = {"command": s["command"], "args": s["args"]}
            if tool == "codex" and "codex_default_tools_approval_mode" in s:
                spec["codex_default_tools_approval_mode"] = s["codex_default_tools_approval_mode"]
            if tool == "codex" and "codex_tool_approval_modes" in s:
                spec["codex_tool_approval_modes"] = s["codex_tool_approval_modes"]
            result[s["name"]] = spec
    return result
