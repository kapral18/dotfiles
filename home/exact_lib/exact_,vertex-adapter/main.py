#!/usr/bin/env python3
"""Launch a coding harness through an isolated multi-protocol Vertex adapter."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from auth import TokenProvider, resolve_project
from models import ModelRegistry, ModelSpec, codex_model_info
from server import AdapterContext, start_server
from state import OpaqueContextStore
from vertex import VertexClient

EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}


@dataclass(frozen=True)
class LaunchOptions:
    model_id: str | None
    effort: str | None
    thinking: bool
    no_thinking: bool
    forwarded: list[str]
    help: bool


def _usage(harness: str) -> str:
    return f"""Usage: ,{harness}-vertex [adapter options] [harness arguments]

Launch {harness} through an isolated loopback adapter backed by Google Vertex AI.

Adapter options:
  -m, --model ID             Select a curated Vertex model (default: gemini-3.6-flash)
      --effort LEVEL         Set provider reasoning effort
      --reasoning-effort L   Alias for --effort
      --thinking[=LEVEL]     Enable thinking at the model default or selected level
      --no-thinking          Disable thinking (Claude models only)
  -h, --help                 Show this wrapper help

Effort levels are validated per model. Use -- before an underlying harness flag
that has the same name as an adapter option.
"""


def _required_value(argv: list[str], index: int, option: str) -> tuple[str, int]:
    if index + 1 >= len(argv):
        raise ValueError(f"{option} requires a value")
    return argv[index + 1], index + 2


def parse_args(argv: list[str]) -> LaunchOptions:
    model_id = None
    effort = None
    thinking = False
    no_thinking = False
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
        elif argument == "--thinking":
            if index + 1 < len(argv) and argv[index + 1] in EFFORTS:
                effort = argv[index + 1]
                index += 2
            else:
                thinking = True
                index += 1
        elif argument.startswith("--thinking="):
            effort = argument.split("=", 1)[1]
            index += 1
        elif argument == "--no-thinking":
            no_thinking = True
            index += 1
        else:
            forwarded.append(argument)
            index += 1
    if effort == "none":
        effort = None
        no_thinking = True
    if effort is not None and effort not in EFFORTS:
        raise ValueError(f"invalid effort {effort!r}; choose one of: {', '.join(sorted(EFFORTS))}")
    if no_thinking and thinking:
        raise ValueError("--thinking and --no-thinking cannot be combined")
    if no_thinking and effort:
        raise ValueError("--effort and --no-thinking cannot be combined")
    return LaunchOptions(model_id, effort, thinking, no_thinking, forwarded, show_help)


def _harness_binary(harness: str) -> str:
    override = os.environ.get(f"VERTEX_ADAPTER_{harness.upper()}_BIN")
    if override:
        return str(Path(override).expanduser())
    if harness in {"codex", "copilot"}:
        managed = Path.home() / "bin" / f",{harness}"
        if managed.is_file() and os.access(managed, os.X_OK):
            return str(managed)
    binary = shutil.which(harness)
    if binary:
        return binary
    raise RuntimeError(f"{harness} CLI is not installed")


def _codex_command(
    binary: str,
    base_url: str,
    model: ModelSpec,
    effort: str | None,
    catalog_path: str | None,
) -> list[str]:
    command = [
        binary,
        "-c",
        f"model_providers.vertex.base_url={json.dumps(base_url + '/v1')}",
        "-c",
        'model_providers.vertex.name="Google Vertex Adapter"',
        "-c",
        'model_providers.vertex.wire_api="responses"',
        "-c",
        'model_providers.vertex.env_key="VERTEX_ADAPTER_TOKEN"',
        "-c",
        'model_provider="vertex"',
        "--model",
        model.model_id,
    ]
    if catalog_path:
        command.extend(["-c", f"model_catalog_json={json.dumps(catalog_path)}"])
    if effort:
        command.extend(["-c", f"model_reasoning_effort={json.dumps(effort)}"])
    return command


def _child(
    harness: str,
    binary: str,
    base_url: str,
    token: str,
    model: ModelSpec,
    effort: str | None,
    forwarded: list[str],
    codex_catalog_path: str | None = None,
) -> tuple[list[str], dict[str, str]]:
    env = dict(os.environ)
    env["VERTEX_ADAPTER_TOKEN"] = token
    if harness == "codex":
        return [*_codex_command(binary, base_url, model, effort, codex_catalog_path), *forwarded], env
    if harness == "copilot":
        env.update(
            {
                "COPILOT_PROVIDER_BASE_URL": f"{base_url}/v1",
                "COPILOT_PROVIDER_TYPE": "openai",
                "COPILOT_PROVIDER_API_KEY": token,
                "COPILOT_PROVIDER_WIRE_API": "completions",
                "COPILOT_MODEL": model.model_id,
                "COPILOT_PROVIDER_MODEL_ID": model.model_id,
                "COPILOT_PROVIDER_WIRE_MODEL": model.model_id,
                "COPILOT_PROVIDER_MAX_PROMPT_TOKENS": str(model.context_window),
                "COPILOT_PROVIDER_MAX_OUTPUT_TOKENS": str(model.max_output_tokens),
            }
        )
        env.pop("COPILOT_PROVIDER_BEARER_TOKEN", None)
        command = [binary]
        if effort:
            command.extend(["--effort", effort])
        command.extend(forwarded)
        return command, env
    env.update(
        {
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_API_KEY": token,
            "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
            "ANTHROPIC_MODEL": model.model_id,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": model.model_id,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model.model_id,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model.model_id,
        }
    )
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env.pop("CLAUDE_CODE_USE_VERTEX", None)
    return [binary, "--model", model.model_id, *forwarded], env


def _run_child(command: list[str], env: dict[str, str]) -> int:
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
            print(_usage(harness))
            return 0
        registry = ModelRegistry.load()
        model = registry.get(options.model_id)
        effort = registry.resolve_effort(
            model,
            options.effort,
            thinking=options.thinking,
            no_thinking=options.no_thinking,
        )
        project = resolve_project()
        binary = _harness_binary(harness)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    token = secrets.token_urlsafe(32)
    context = AdapterContext(
        registry=registry,
        model=model,
        effort=effort,
        token=token,
        vertex=VertexClient(project, TokenProvider()),
        store=OpaqueContextStore(),
    )
    server, thread = start_server(context)
    base_url = f"http://127.0.0.1:{server.server_port}"
    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        catalog_path = None
        if harness == "codex":
            temporary = tempfile.TemporaryDirectory(prefix="vertex-adapter-")
            catalog = Path(temporary.name) / "codex-models.json"
            catalog.write_text(
                json.dumps({"models": [codex_model_info(item) for item in registry.values()]}),
                encoding="utf-8",
            )
            catalog.chmod(0o600)
            catalog_path = str(catalog)
        command, env = _child(
            harness,
            binary,
            base_url,
            token,
            model,
            effort,
            options.forwarded,
            catalog_path,
        )
        return _run_child(command, env)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if temporary is not None:
            temporary.cleanup()


def main(argv: list[str]) -> int:
    if len(argv) < 1 or argv[0] not in {"codex", "copilot", "claude"}:
        print("Usage: main.py {codex|copilot|claude} [arguments]", file=sys.stderr)
        return 2
    return launch(argv[0], argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
