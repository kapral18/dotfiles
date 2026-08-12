#!/usr/bin/env python3
"""Launch Claude Code, Codex, or Cursor through the current GitHub Copilot subscription."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from copilot_auth import CLAUDE_EXTENDED_CONTEXT_SUFFIX, CopilotError, ModelSpec, TokenProvider, fetch_models
from copilot_server import AdapterContext, start_server
from copilot_wire import SUPPORTED_ENDPOINTS

DEFAULT_MODELS = {
    "claude": "claude-sonnet-5",
    "codex": "gpt-5.3-codex",
    "cursor": "gpt-5.3-codex",
}
DEFAULT_EFFORTS = {
    "claude": None,
    "codex": "medium",
    "cursor": "medium",
}
CLAUDE_DEFAULT_CONTEXT_WINDOW = 200_000
CURSOR_PINNED_OPTIONS = {"--base-url", "--local-agent-api-key", "--authless", "--model", "-m"}


@dataclass(frozen=True)
class LaunchOptions:
    model_id: str | None
    effort: str | None
    context_tier: str
    forwarded: list[str]
    help: bool


def usage(harness: str) -> str:
    default = DEFAULT_MODELS[harness]
    if DEFAULT_EFFORTS[harness] is not None:
        default = f"{default} with {DEFAULT_EFFORTS[harness]} effort"
    return f"""Usage: ,{harness}-copilot [adapter options] [harness arguments]

Launch {harness} through an authenticated loopback backed by the current
GitHub Copilot subscription.

Adapter options:
  -m, --model ID             Select a model from the live Copilot catalog
      --effort LEVEL         Set provider reasoning effort
      --reasoning-effort L   Alias for --effort
      --context TIER         Select default or long_context
  -h, --help                 Show this wrapper help

The default is {default}. Use -- before an underlying harness
flag that has the same name as an adapter option.
"""


def _required_value(argv: list[str], index: int, option: str) -> tuple[str, int]:
    if index + 1 >= len(argv):
        raise ValueError(f"{option} requires a value")
    return argv[index + 1], index + 2


def parse_args(argv: list[str]) -> LaunchOptions:
    model_id = None
    effort = None
    context_tier = "default"
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
        elif argument.startswith(("--effort=", "--reasoning-effort=")):
            effort = argument.split("=", 1)[1]
            index += 1
        elif argument == "--context":
            context_tier, index = _required_value(argv, index, argument)
        elif argument.startswith("--context="):
            context_tier = argument.split("=", 1)[1]
            index += 1
        else:
            forwarded.append(argument)
            index += 1
    if model_id == "":
        raise ValueError("--model requires a non-empty value")
    if effort == "":
        raise ValueError("--effort requires a non-empty value")
    if context_tier not in {"default", "long_context"}:
        raise ValueError(f"unsupported context tier {context_tier!r}; choose: default, long_context")
    return LaunchOptions(model_id, effort, context_tier, forwarded, show_help)


def resolve_model(harness: str, options: LaunchOptions, models: dict[str, ModelSpec]) -> ModelSpec:
    model_id = options.model_id or DEFAULT_MODELS[harness]
    try:
        model = models[model_id]
    except KeyError as error:
        raise ValueError(f"model {model_id!r} is not available through this Copilot subscription") from error
    if model.endpoints.isdisjoint(SUPPORTED_ENDPOINTS):
        raise ValueError(f"Copilot model {model_id!r} does not expose a supported completion endpoint")
    if options.effort is not None and options.effort not in model.efforts:
        choices = ", ".join(sorted(model.efforts)) or "none"
        raise ValueError(f"model {model_id!r} does not support effort {options.effort!r}; choose: {choices}")
    if options.context_tier not in model.context_windows:
        choices = ", ".join(model.context_windows)
        raise ValueError(
            f"model {model_id!r} does not support context tier {options.context_tier!r}; choose: {choices}"
        )
    return replace(model, context_window=model.context_windows[options.context_tier])


def completion_rows(models: dict[str, ModelSpec]) -> list[str]:
    """Render the live catalog for shell completion without making it a launcher contract."""
    rows = []
    for model in sorted(models.values(), key=lambda item: item.model_id):
        if not model.endpoints.isdisjoint(SUPPORTED_ENDPOINTS):
            rows.append("\t".join((model.model_id, ",".join(sorted(model.efforts)), ",".join(model.context_windows))))
    return rows


def complete(argv: list[str]) -> int:
    if argv != ["models"]:
        print("Usage: main.py __complete models", file=sys.stderr)
        return 2
    try:
        for row in completion_rows(fetch_models(TokenProvider())):
            print(row)
    except CopilotError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


def harness_binary(harness: str) -> str:
    if harness == "cursor":
        cursor = shutil.which("cursor-agent")
        if cursor is None:
            raise RuntimeError("cursor-agent CLI is not installed")
        version = subprocess.run([cursor, "--version"], check=True, capture_output=True, text=True).stdout.strip()
        binary = Path.home() / ".local/share/cursor-agent-local/versions" / version / "cursor-agent-local"
        if not binary.is_file() or not os.access(binary, os.X_OK):
            installer = Path.home() / "lib/,cursor-agent-local/install.sh"
            if not installer.is_file():
                raise RuntimeError(f"Cursor local-agent installer was not found at {installer}")
            subprocess.run(["bash", str(installer), version], check=True)
        if binary.is_file() and os.access(binary, os.X_OK):
            return str(binary)
        raise RuntimeError("Cursor local-agent installation did not provide an executable")
    binary = shutil.which(harness)
    if binary is None:
        raise RuntimeError(f"{harness} CLI is not installed")
    return binary


def validate_cursor_forwarded(argv: list[str]) -> None:
    for argument in argv:
        if argument in CURSOR_PINNED_OPTIONS or any(
            argument.startswith(f"{option}=") for option in CURSOR_PINNED_OPTIONS
        ):
            raise ValueError(f"{argument} cannot override the Cursor loopback adapter")


def claude_frontend_model(model: ModelSpec) -> str:
    if model.context_window > CLAUDE_DEFAULT_CONTEXT_WINDOW:
        return f"{model.model_id}{CLAUDE_EXTENDED_CONTEXT_SUFFIX}"
    return model.model_id


def child_command(
    harness: str,
    binary: str,
    base_url: str,
    loopback_token: str,
    model: ModelSpec,
    effort: str | None,
    forwarded: list[str],
) -> tuple[list[str], dict[str, str]]:
    env = dict(os.environ)
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_CUSTOM_HEADERS",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "OPENAI_API_KEY",
        "COPILOT_GITHUB_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
    ):
        env.pop(key, None)
    if harness == "claude":
        frontend_model = claude_frontend_model(model)
        env.update(
            {
                "ANTHROPIC_BASE_URL": base_url,
                "ANTHROPIC_AUTH_TOKEN": loopback_token,
                "ANTHROPIC_MODEL": frontend_model,
                "ANTHROPIC_DEFAULT_OPUS_MODEL": frontend_model,
                "ANTHROPIC_DEFAULT_SONNET_MODEL": frontend_model,
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": frontend_model,
                "ANTHROPIC_DEFAULT_FABLE_MODEL": frontend_model,
                "CLAUDE_CODE_AUTO_COMPACT_WINDOW": str(model.context_window),
            }
        )
        command = [binary, "--model", frontend_model]
        if effort is not None:
            command.extend(["--effort", effort])
        command.extend(forwarded)
        return command, env
    if harness == "cursor":
        for key in (
            "CURSOR_LOCAL_AGENT_BASE_URL",
            "CURSOR_LOCAL_AGENT_API_KEY",
            "CURSOR_API_ENDPOINT",
            "CURSOR_API_KEY",
            "ANTHROPIC_BASE_URL",
            "ANTHROPIC_AUTH_TOKEN",
        ):
            env.pop(key, None)
        env.update({"CURSOR_LOCAL_AGENT_BASE_URL": f"{base_url}/v1", "CURSOR_LOCAL_AGENT_API_KEY": loopback_token})
        return [binary, "--model", model.model_id, *forwarded], env
    env["COPILOT_ADAPTER_TOKEN"] = loopback_token
    provider = "copilot_subscription"
    command = [
        binary,
        "-c",
        f"model_providers.{provider}.base_url={json.dumps(base_url + '/v1')}",
        "-c",
        f'model_providers.{provider}.name="GitHub Copilot Subscription"',
        "-c",
        f'model_providers.{provider}.wire_api="responses"',
        "-c",
        f'model_providers.{provider}.env_key="COPILOT_ADAPTER_TOKEN"',
        "-c",
        f"model_provider={json.dumps(provider)}",
        "--model",
        model.model_id,
    ]
    if effort is not None:
        command.extend(["-c", f"model_reasoning_effort={json.dumps(effort)}"])
    command.extend(forwarded)
    return command, env


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
        if harness == "cursor":
            validate_cursor_forwarded(options.forwarded)
        tokens = TokenProvider()
        models = fetch_models(tokens)
        if options.effort is None:
            default_effort = DEFAULT_EFFORTS[harness]
            model_id = options.model_id or DEFAULT_MODELS[harness]
            model = models.get(model_id)
            if default_effort is not None and model is not None and default_effort in model.efforts:
                options = replace(options, effort=default_effort)
        model = resolve_model(harness, options, models)
        binary = harness_binary(harness)
    except (CopilotError, OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    loopback_token = secrets.token_urlsafe(32)
    effective_models = dict(models)
    effective_models[model.model_id] = model
    server, thread = start_server(AdapterContext(loopback_token, tokens, effective_models))
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        command, env = child_command(
            harness,
            binary,
            base_url,
            loopback_token,
            model,
            options.effort,
            options.forwarded,
        )
        return run_child(command, env)
    finally:
        previous_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        finally:
            signal.signal(signal.SIGINT, previous_sigint)


def main(argv: list[str]) -> int:
    if argv and argv[0] == "__complete":
        return complete(argv[1:])
    if len(argv) < 1 or argv[0] not in DEFAULT_MODELS:
        print("Usage: main.py {claude|codex|cursor} [arguments]", file=sys.stderr)
        return 2
    return launch(argv[0], argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
