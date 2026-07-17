#!/usr/bin/env python3
"""Inject generated Codex MCP servers into a base TOML config.

This keeps mcp server definitions single-sourced in mcp_servers.yaml while
allowing Codex's TOML config to stay as a mostly-static file.

Preferred pattern: base config contains a marker line:
  # __MCP_SERVERS__
which is replaced with generated TOML sections.

Usage:
  inject_mcp_into_codex_toml.py <base_toml_path> <mcp_servers_yaml> <is_work> [tool] [existing_toml_path]

When an existing config is supplied, only explicit Codex runtime-owned state is
reattached: MCP approval modes, hook trust hashes, project trust levels, and
TUI model-availability counters. The profile base and generated MCP transport
remain authoritative.

Output: merged TOML to stdout.
"""

from __future__ import annotations

import json
import re
import sys

from mcp_registry import load_servers

MARKER = "# __MCP_SERVERS__"
# Deployed launcher for per-request bearer-injecting stdio bridges.
TOKEN_BRIDGE_COMMAND = ",mcp-token"
VALID_APPROVAL_MODES = {"approve", "auto", "prompt"}
VALID_PROJECT_TRUST_LEVELS = {"trusted", "untrusted"}
MAX_U32 = 2**32 - 1
BARE_TOML_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")
TOML_DECIMAL_INTEGER_RE = re.compile(r"^\+?(?:0|[1-9](?:_?[0-9])*)$")


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_key(value: str) -> str:
    return value if BARE_TOML_KEY_RE.match(value) else _toml_string(value)


def _valid_approval_mode(value: object) -> bool:
    return isinstance(value, str) and value in VALID_APPROVAL_MODES


def _parse_toml_table_path(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("[") or not stripped.endswith("]") or stripped.startswith("[["):
        return None

    inner = stripped[1:-1].strip()
    raw_parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escape = False
    for char in inner:
        if quote is not None:
            current.append(char)
            if escape:
                escape = False
            elif quote == '"' and char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue

        if char in ('"', "'"):
            quote = char
            current.append(char)
        elif char == ".":
            raw_parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if quote is not None or escape:
        return None
    raw_parts.append("".join(current).strip())
    parts = [_parse_toml_key(part) for part in raw_parts]
    return [part for part in parts if part is not None] if all(part is not None for part in parts) else None


def _parse_toml_string_value(raw_value: str) -> str | None:
    value = raw_value.strip()
    if not value:
        return None

    if value[0] == '"':
        try:
            parsed, end = json.JSONDecoder().raw_decode(value)
        except json.JSONDecodeError:
            return None
        trailing = value[end:].strip()
        return parsed if isinstance(parsed, str) and (not trailing or trailing.startswith("#")) else None

    if value[0] != "'":
        return None
    end = value.find("'", 1)
    if end < 0:
        return None
    trailing = value[end + 1 :].strip()
    return value[1:end] if not trailing or trailing.startswith("#") else None


def _parse_toml_key(raw_key: str) -> str | None:
    key = raw_key.strip()
    if BARE_TOML_KEY_RE.fullmatch(key):
        return key
    return _parse_toml_string_value(key)


def _parse_toml_u32(raw_value: str) -> int | None:
    value = raw_value.split("#", 1)[0].strip()
    if not TOML_DECIMAL_INTEGER_RE.fullmatch(value):
        return None
    parsed = int(value.replace("_", ""), 10)
    return parsed if 0 <= parsed <= MAX_U32 else None


def _read_existing_toml_lines(existing_toml_path: str | None) -> list[str]:
    if not existing_toml_path:
        return []
    try:
        with open(existing_toml_path, "r") as f:
            return f.read().splitlines()
    except OSError:
        return []


def _load_preserved_runtime_state(
    existing_toml_path: str | None,
) -> tuple[dict[str, str], dict[str, int]]:
    projects: dict[str, str] = {}
    tui_counters: dict[str, int] = {}
    current_path: list[str] = []
    for line in _read_existing_toml_lines(existing_toml_path):
        table_path = _parse_toml_table_path(line)
        if table_path is not None:
            current_path = table_path
            continue
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        if len(current_path) == 2 and current_path[0] == "projects" and key.strip() == "trust_level":
            trust_level = _parse_toml_string_value(raw_value)
            if trust_level in VALID_PROJECT_TRUST_LEVELS:
                projects[current_path[1]] = trust_level
            continue

        if current_path == ["tui", "model_availability_nux"]:
            model_id = _parse_toml_key(key)
            counter = _parse_toml_u32(raw_value)
            if model_id is not None and counter is not None:
                tui_counters[model_id] = counter

    return projects, tui_counters


def _load_preserved_mcp_approvals(
    existing_toml_path: str | None,
    server_names: set[str],
) -> dict[str, dict[str, object]]:
    preserved: dict[str, dict[str, object]] = {}
    current_path: list[str] = []
    for line in _read_existing_toml_lines(existing_toml_path):
        table_path = _parse_toml_table_path(line)
        if table_path is not None:
            current_path = table_path
            continue

        if not current_path or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = _parse_toml_string_value(raw_value)
        if not _valid_approval_mode(value):
            continue

        if (
            len(current_path) == 2
            and current_path[0] == "mcp_servers"
            and current_path[1] in server_names
            and key == "default_tools_approval_mode"
        ):
            server_preserved = preserved.setdefault(current_path[1], {})
            server_preserved["default_tools_approval_mode"] = value
        elif (
            len(current_path) == 4
            and current_path[0] == "mcp_servers"
            and current_path[1] in server_names
            and current_path[2] == "tools"
            and key == "approval_mode"
        ):
            server_preserved = preserved.setdefault(current_path[1], {})
            tools = server_preserved.setdefault("tools", {})
            if isinstance(tools, dict):
                tools[current_path[3]] = value

    return preserved


def _load_preserved_hook_state(existing_toml_path: str | None) -> dict[str, str]:
    preserved: dict[str, str] = {}
    current_path: list[str] = []
    for line in _read_existing_toml_lines(existing_toml_path):
        table_path = _parse_toml_table_path(line)
        if table_path is not None:
            current_path = table_path
            continue

        if len(current_path) != 3 or current_path[:2] != ["hooks", "state"]:
            continue
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        if key.strip() != "trusted_hash":
            continue

        trusted_hash = _parse_toml_string_value(raw_value)
        if isinstance(trusted_hash, str) and trusted_hash.startswith("sha256:"):
            preserved[current_path[2]] = trusted_hash

    return preserved


def _append_preserved_mcp_approvals(
    out_lines: list[str],
    server_name: str,
    generated_default_mode: object,
    generated_tool_modes: object,
    preserved_approvals: dict[str, dict[str, object]],
) -> None:
    server_preserved = preserved_approvals.get(server_name, {})
    default_mode = (
        generated_default_mode
        if _valid_approval_mode(generated_default_mode)
        else server_preserved.get("default_tools_approval_mode")
    )
    if _valid_approval_mode(default_mode):
        out_lines.append(f"default_tools_approval_mode = {_toml_string(str(default_mode))}")
    out_lines.append("")

    generated_tools = generated_tool_modes if isinstance(generated_tool_modes, dict) else {}
    preserved_tools = server_preserved.get("tools")
    merged_tools: dict[str, object] = {}
    if not isinstance(preserved_tools, dict):
        preserved_tools = {}
    merged_tools.update(preserved_tools)
    merged_tools.update(generated_tools)

    for tool_name in sorted(merged_tools):
        approval_mode = merged_tools[tool_name]
        if not _valid_approval_mode(approval_mode):
            continue
        out_lines.append(f"[mcp_servers.{_toml_key(server_name)}.tools.{_toml_key(str(tool_name))}]")
        out_lines.append(f"approval_mode = {_toml_string(str(approval_mode))}")
        out_lines.append("")


def _render_codex_mcp_toml(
    mcp_yaml: str,
    is_work: bool,
    tool: str | None = None,
    existing_toml_path: str | None = None,
) -> str:
    servers = load_servers(mcp_yaml, is_work, tool=tool)
    preserved_approvals = _load_preserved_mcp_approvals(existing_toml_path, set(servers.keys()))
    out_lines: list[str] = []
    for name, spec in servers.items():
        if spec.get("type") == "http":
            # Codex reads bearer_token_env_var once at launch and never
            # reloads it, so header-auth sessions died with the captured
            # token; hosted OAuth servers instead run as local stdio bridges
            # (",mcp-token <source> --bridge --url <url>") that inject a
            # freshly selected bearer per request.
            oauth = spec.get("oauth", {})
            token_source = oauth.get("tokenBridge")
            if not token_source:
                continue
            command = TOKEN_BRIDGE_COMMAND
            args = [str(token_source), "--bridge", "--url", str(spec["url"])]
        else:
            command = spec["command"]
            args = spec["args"]
        out_lines.append(f"[mcp_servers.{_toml_key(name)}]")
        out_lines.append(f"command = {_toml_string(str(command))}")
        out_lines.append("args = [")
        for arg in args:
            out_lines.append(f"  {_toml_string(str(arg))},")
        out_lines.append("]")
        _append_preserved_mcp_approvals(
            out_lines,
            name,
            spec.get("codex_default_tools_approval_mode"),
            spec.get("codex_tool_approval_modes"),
            preserved_approvals,
        )
    body = "\n".join(out_lines).rstrip()
    return body + "\n" if body else ""


def _with_preserved_hook_state(config: str, existing_toml_path: str | None) -> str:
    preserved_hook_state = _load_preserved_hook_state(existing_toml_path)
    if not preserved_hook_state:
        return config

    lines = [config.rstrip(), ""]
    for hook_id in sorted(preserved_hook_state):
        lines.append(f"[hooks.state.{_toml_key(hook_id)}]")
        lines.append(f"trusted_hash = {_toml_string(preserved_hook_state[hook_id])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _with_preserved_runtime_state(config: str, existing_toml_path: str | None) -> str:
    output = _with_preserved_hook_state(config, existing_toml_path)
    projects, tui_counters = _load_preserved_runtime_state(existing_toml_path)
    if not projects and not tui_counters:
        return output

    source_tables = {
        tuple(table_path) for line in output.splitlines() if (table_path := _parse_toml_table_path(line)) is not None
    }
    lines = [output.rstrip()]
    for project_path, trust_level in projects.items():
        table_path = ("projects", project_path)
        if table_path in source_tables:
            continue
        lines.extend(
            [
                "",
                f"[projects.{_toml_key(project_path)}]",
                f"trust_level = {_toml_string(trust_level)}",
            ]
        )

    if tui_counters and ("tui", "model_availability_nux") not in source_tables:
        lines.extend(["", "[tui.model_availability_nux]"])
        for model_id, counter in tui_counters.items():
            lines.append(f"{_toml_string(model_id)} = {counter}")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    if len(sys.argv) not in (4, 5, 6):
        sys.exit(
            "Usage: inject_mcp_into_codex_toml.py <base_toml_path> <mcp_servers_yaml> <is_work> [tool] [existing_toml_path]"
        )

    base_path, mcp_yaml, is_work_raw = sys.argv[1], sys.argv[2], sys.argv[3]
    is_work = is_work_raw == "true"
    tool = sys.argv[4] if len(sys.argv) >= 5 else None
    existing_toml_path = sys.argv[5] if len(sys.argv) == 6 else None

    with open(base_path, "r") as f:
        base = f.read()

    snippet = _render_codex_mcp_toml(
        mcp_yaml,
        is_work,
        tool=tool,
        existing_toml_path=existing_toml_path,
    )

    if MARKER in base:
        before, after = base.split(MARKER, 1)
        # Drop the marker line itself (including a trailing newline if present).
        if after.startswith("\n"):
            after = after[1:]
        after = after.lstrip()
        if after:
            separator = "\n" if snippet else ""
            output = before.rstrip() + "\n\n" + snippet + separator + after
        else:
            output = before.rstrip() + ("\n\n" + snippet if snippet else "\n")
        sys.stdout.write(_with_preserved_runtime_state(output, existing_toml_path))
        return

    # Fallback: strip any existing [mcp_servers.*] blocks and append snippet.
    lines = base.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        if line.startswith("[mcp_servers.") and line.rstrip().endswith("]"):
            skipping = True
            continue
        if skipping:
            if line.startswith("[") and line.rstrip().endswith("]"):
                skipping = False
                out.append(line)
            else:
                continue
        else:
            out.append(line)

    output = "".join(out).rstrip() + ("\n\n" + snippet if snippet else "\n")
    sys.stdout.write(_with_preserved_runtime_state(output, existing_toml_path))


if __name__ == "__main__":
    main()
