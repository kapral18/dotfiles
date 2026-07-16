#!/usr/bin/env python3
"""Run Codex with managed MCP bearer-token env and local model metadata."""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REAL_CODEX = "/opt/homebrew/bin/codex"
LOCAL_MODELS = {"local", "local-max"}
MCP_TOKEN = ",mcp-token"
ADMIN_COMMANDS = {
    "app",
    "app-server",
    "apply",
    "archive",
    "completion",
    "debug",
    "delete",
    "doctor",
    "features",
    "help",
    "login",
    "logout",
    "mcp",
    "mcp-server",
    "plugin",
    "remote-control",
    "sandbox",
    "unarchive",
    "update",
}


@dataclass(frozen=True)
class TokenServer:
    name: str
    env_var: str


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def _toml_string(raw: str) -> str:
    raw = raw.strip()
    if not (raw.startswith('"') and raw.endswith('"')):
        return raw
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw[1:-1]
    return value if isinstance(value, str) else raw


def _configured_token_servers(config_path: Path) -> list[TokenServer]:
    try:
        lines = config_path.read_text().splitlines()
    except OSError:
        return []

    servers: list[TokenServer] = []
    current_name: str | None = None
    current_url: str | None = None
    current_env_var: str | None = None
    current_enabled = True

    def flush() -> None:
        nonlocal current_name, current_url, current_env_var, current_enabled
        if current_name and current_url and current_env_var and current_enabled:
            servers.append(TokenServer(current_name, current_env_var))
        current_name = None
        current_url = None
        current_env_var = None
        current_enabled = True

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        table = re.match(r"^\[mcp_servers\.([A-Za-z0-9_-]+)\]$", stripped)
        if table:
            flush()
            current_name = table.group(1)
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            flush()
            continue
        if current_name is None:
            continue
        key, sep, value = stripped.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if key == "url":
            current_url = _toml_string(value)
        elif key == "bearer_token_env_var":
            current_env_var = _toml_string(value)
        elif key == "enabled":
            current_enabled = value.split("#", 1)[0].strip().lower() != "false"

    flush()
    return servers


def _first_command(argv: list[str]) -> str | None:
    skip_next = False
    for arg in argv:
        if skip_next:
            skip_next = False
            continue
        if arg in {
            "-c",
            "--config",
            "-m",
            "--model",
            "-p",
            "--profile",
            "-s",
            "--sandbox",
            "-C",
            "--cd",
            "-a",
            "--ask-for-approval",
        }:
            skip_next = True
            continue
        if arg in {"-i", "--image", "--add-dir", "--enable", "--disable", "--remote", "--remote-auth-token-env"}:
            skip_next = True
            continue
        if arg.startswith("-"):
            continue
        return arg
    return None


def _should_refresh_mcp_tokens(argv: list[str]) -> bool:
    if any(arg in {"-h", "--help", "-V", "--version"} for arg in argv):
        return False
    command = _first_command(argv)
    return command not in ADMIN_COMMANDS


def _refresh_mcp_token_env(argv: list[str]) -> bool:
    if not _should_refresh_mcp_tokens(argv):
        return True

    servers = _configured_token_servers(_codex_home() / "config.toml")
    rotation_env = os.environ.copy()
    for server in servers:
        rotation_env.pop(server.env_var, None)
    failures: list[str] = []
    deferred: list[str] = []
    for server in servers:
        result = subprocess.run(
            [MCP_TOKEN, server.name, "--login", "--quiet", "--launch-json"],
            capture_output=True,
            text=True,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload = {}
        token = payload.get("token") if isinstance(payload, dict) else None
        rotation_due = payload.get("rotation_due") if isinstance(payload, dict) else None
        if (
            result.returncode != 0
            or not isinstance(token, str)
            or not token
            or "\n" in token
            or not isinstance(rotation_due, bool)
        ):
            failures.append(server.name)
            continue
        os.environ[server.env_var] = token
        if rotation_due:
            deferred.append(server.name)

    if failures:
        joined = ", ".join(failures)
        print(f",codex: could not refresh MCP token(s): {joined}.", file=sys.stderr)
        print(",codex: run ',mcp-token <server> --login' without --quiet to inspect the OAuth flow.", file=sys.stderr)
        return False
    for server in deferred:
        try:
            subprocess.Popen(
                [MCP_TOKEN, server, "--rotate", "--quiet"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=rotation_env,
                start_new_session=True,
            )
        except OSError:
            pass
    return True


def _uses_llama_cpp_model(argv: list[str]) -> bool:
    previous = ""
    for arg in argv:
        if previous in {"-m", "--model"} and arg in LOCAL_MODELS:
            return True
        if arg.startswith("--model=") and arg.split("=", 1)[1] in LOCAL_MODELS:
            return True
        previous = arg
    return False


def main(argv: list[str]) -> int:
    real_codex = os.environ.get("CODEX_REAL_BIN", REAL_CODEX)
    if not os.access(real_codex, os.X_OK):
        print(f"Error: real Codex binary not found at {real_codex}.", file=sys.stderr)
        return 127

    if not _refresh_mcp_token_env(argv):
        return 1

    exec_args = [real_codex]
    catalog = os.environ.get(
        "CODEX_LLAMA_CPP_MODEL_CATALOG",
        str(Path.home() / ".codex/llama-cpp-model-catalog.json"),
    )
    if _uses_llama_cpp_model(argv) and Path(catalog).is_file():
        exec_args.extend(["-c", f'model_catalog_json="{catalog}"'])
    exec_args.extend(argv)
    os.execv(real_codex, exec_args)
    return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
