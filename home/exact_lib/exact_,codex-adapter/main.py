#!/usr/bin/env python3
"""Launch Claude Code or Copilot CLI through the Codex subscription adapter."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from auth import CodexAuth
from client import CodexClient
from server import AdapterContext, start_server
from state import OpaqueReasoningStore

CLAUDE_DEFAULT_CONTEXT_WINDOW = 200_000
CLAUDE_EXTENDED_CONTEXT_SUFFIX = "[1m]"
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}


@dataclass(frozen=True)
class LaunchOptions:
    model_id: str | None
    effort: str | None
    forwarded: list[str]
    help: bool


def usage(harness: str) -> str:
    return f"""Usage: ,{harness}-codex [adapter options] [harness arguments]

Launch {harness} through an owner-authenticated loopback adapter backed by the
current Codex ChatGPT subscription.

Adapter options:
  -m, --model ID             Override the model sent to the Codex backend
      --effort LEVEL         Override reasoning effort
      --reasoning-effort L   Alias for --effort
  -h, --help                 Show this wrapper help

Effort levels: none, minimal, low, medium, high, xhigh, max, ultra.
Without --model, the wrapper reads model from the active Codex config.
Without --effort, the harness-generated effort is preserved. Use -- before an
underlying harness flag that has the same name as an adapter option.
"""


def _required_value(argv: list[str], index: int, option: str) -> tuple[str, int]:
    if index + 1 >= len(argv):
        raise ValueError(f"{option} requires a value")
    return argv[index + 1], index + 2


def parse_args(argv: list[str]) -> LaunchOptions:
    model_id = None
    effort = None
    forwarded: list[str] = []
    show_help = False
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--":
            forwarded.extend(argv[index + 1 :])
            break
        if argument in {"-h", "--help"}:
            show_help = True
            index += 1
        elif argument in {"-m", "--model"}:
            model_id, index = _required_value(argv, index, argument)
        elif argument.startswith("--model="):
            model_id = argument.split("=", 1)[1]
            index += 1
        elif argument in {"--effort", "--reasoning-effort"}:
            effort, index = _required_value(argv, index, argument)
        elif argument.startswith("--effort=") or argument.startswith("--reasoning-effort="):
            effort = argument.split("=", 1)[1]
            index += 1
        else:
            forwarded.append(argument)
            index += 1
    if effort is not None and effort not in EFFORTS:
        raise ValueError(f"invalid effort {effort!r}; choose one of: {', '.join(sorted(EFFORTS))}")
    if model_id == "":
        raise ValueError("--model requires a non-empty value")
    return LaunchOptions(model_id, effort, forwarded, show_help)


def default_config_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return (Path(codex_home).expanduser() if codex_home else Path.home() / ".codex") / "config.toml"


def default_models_cache_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return (Path(codex_home).expanduser() if codex_home else Path.home() / ".codex") / "models_cache.json"


def resolve_default_model(config_path: Path | None = None) -> str:
    path = config_path or default_config_path()
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RuntimeError(f"Codex config was not found at {path}") from error
    except OSError as error:
        raise RuntimeError(f"Codex config at {path} is unreadable") from error
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            break
        match = re.fullmatch(r"""model\s*=\s*(["'])(.*?)\1\s*(?:#.*)?""", stripped)
        if match:
            value = match.group(2)
            if value:
                return value
    raise RuntimeError(f"Codex config at {path} does not set model")


def resolve_model_context_window(model_id: str, cache_path: Path | None = None) -> int | None:
    path = cache_path or default_models_cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return None
    for model in models:
        if not isinstance(model, dict) or model.get("slug") != model_id:
            continue
        for field in ("max_context_window", "context_window"):
            value = model.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                return value
        return None
    return None


def claude_frontend_model(model: str, context_window: int | None) -> str:
    if context_window is not None and context_window > CLAUDE_DEFAULT_CONTEXT_WINDOW:
        return f"{model}{CLAUDE_EXTENDED_CONTEXT_SUFFIX}"
    return model


def harness_binary(harness: str) -> str:
    if harness == "copilot":
        managed = Path.home() / "bin" / ",copilot"
        if managed.is_file() and os.access(managed, os.X_OK):
            return str(managed)
    binary = shutil.which(harness)
    if binary:
        return binary
    raise RuntimeError(f"{harness} CLI is not installed")


def codex_binary() -> str:
    binary = shutil.which("codex")
    if binary:
        return binary
    raise RuntimeError("Codex CLI is not installed")


def child_command(
    harness: str,
    binary: str,
    base_url: str,
    token: str,
    model: str,
    forwarded: list[str],
    context_window: int | None,
) -> tuple[list[str], dict[str, str]]:
    env = dict(os.environ)
    for key in (
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        "ANTHROPIC_API_KEY",
        "COPILOT_PROVIDER_API_KEY",
        "COPILOT_PROVIDER_BEARER_TOKEN",
    ):
        env.pop(key, None)
    if harness == "copilot":
        env.update(
            {
                "COPILOT_PROVIDER_BASE_URL": f"{base_url}/v1",
                "COPILOT_PROVIDER_TYPE": "openai",
                "COPILOT_PROVIDER_BEARER_TOKEN": token,
                "COPILOT_PROVIDER_WIRE_API": "responses",
                "COPILOT_PROVIDER_TRANSPORT": "http",
                "COPILOT_MODEL": model,
                "COPILOT_PROVIDER_MODEL_ID": model,
                "COPILOT_PROVIDER_WIRE_MODEL": model,
            }
        )
        return [binary, *forwarded], env
    for key in (
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_FOUNDRY",
        "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY",
    ):
        env.pop(key, None)
    frontend_model = claude_frontend_model(model, context_window)
    env.update(
        {
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_AUTH_TOKEN": token,
            "ANTHROPIC_MODEL": frontend_model,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": frontend_model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": frontend_model,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": frontend_model,
        }
    )
    if context_window is not None:
        env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = str(context_window)
    return [binary, "--model", frontend_model, *forwarded], env


def run_child(command: list[str], env: dict[str, str]) -> int:
    child = subprocess.Popen(command, env=env, start_new_session=True)

    def forward(signum: int, _frame: object) -> None:
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    previous = {
        signum: signal.signal(signum, forward)
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGWINCH)
    }
    try:
        returncode = child.wait()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return 128 - returncode if returncode < 0 else returncode


def launch(harness: str, argv: list[str]) -> int:
    try:
        options = parse_args(argv)
        if options.help:
            print(usage(harness))
            return 0
        model = options.model_id or resolve_default_model()
        context_window = resolve_model_context_window(model) if harness == "claude" else None
        binary = harness_binary(harness)
        refresh_binary = codex_binary()
        credentials = CodexAuth(codex_binary=refresh_binary)
        credentials.get()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    token = secrets.token_urlsafe(32)
    context = AdapterContext(
        model=model,
        effort=options.effort,
        token=token,
        codex=CodexClient(credentials),
        store=OpaqueReasoningStore(),
    )
    server, thread = start_server(context)
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        command, env = child_command(
            harness,
            binary,
            base_url,
            token,
            model,
            options.forwarded,
            context_window,
        )
        return run_child(command, env)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main(argv: list[str]) -> int:
    if len(argv) < 1 or argv[0] not in {"claude", "copilot"}:
        print("Usage: main.py {claude|copilot} [arguments]", file=sys.stderr)
        return 2
    return launch(argv[0], argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
