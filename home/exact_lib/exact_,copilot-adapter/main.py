#!/usr/bin/env python3
"""Launch Claude Code, Codex, or Cursor through the current GitHub Copilot subscription."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from copilot_auth import (
    CLAUDE_EXTENDED_CONTEXT_SUFFIX,
    CopilotError,
    ModelSpec,
    TokenProvider,
    codex_model_info,
    fetch_models,
)
from copilot_server import AdapterContext, start_server
from copilot_wire import SUPPORTED_ENDPOINTS, claude_lane_environment, load_lane_routes

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
# Copilot bills the long-context tier by prompt size above the default tier's prompt limit. Claude Code compacts
# on the previous response's usage, so the request that crosses the limit is billed before compaction runs.
# Keep one turn of headroom below the billed limit; Claude itself fires 13k below the window it is given.
CLAUDE_COMPACT_HEADROOM_TOKENS = 32_000
CLAUDE_MIN_COMPACT_WINDOW = 100_000
CURSOR_PINNED_OPTIONS = {"--base-url", "--local-agent-api-key", "--authless", "--model", "-m"}


@dataclass(frozen=True)
class LaunchOptions:
    model_id: str | None
    effort: str | None
    thinking: str | None
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
  -m, --model ID             Select a root model from the live Copilot catalog
      --effort LEVEL         Set root reasoning effort; explicit lane tags keep theirs
      --reasoning-effort L   Alias for --effort
      --thinking MODE        Set Claude backend thinking: auto, on, off
      --no-thinking          Alias for --thinking off
      --context TIER         Select default or long_context
  -h, --help                 Show this wrapper help

The default is {default}. Use -- before an underlying harness
flag that has the same name as an adapter option.
Delegation uses Claude aliases or session-scoped Codex leaf profiles and lane metadata.
Cursor child transport remains disabled. Native harness routes are unaffected.
"""


def _required_value(argv: list[str], index: int, option: str) -> tuple[str, int]:
    if index + 1 >= len(argv):
        raise ValueError(f"{option} requires a value")
    return argv[index + 1], index + 2


def parse_args(argv: list[str]) -> LaunchOptions:
    model_id = None
    effort = None
    thinking = None
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
        elif argument == "--thinking":
            thinking, index = _required_value(argv, index, argument)
        elif argument.startswith("--thinking="):
            thinking = argument.split("=", 1)[1]
            index += 1
        elif argument == "--no-thinking":
            thinking = "off"
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
    if thinking == "":
        raise ValueError("--thinking requires a non-empty value")
    if thinking not in {None, "auto", "on", "off"}:
        raise ValueError(f"unsupported thinking mode {thinking!r}; choose: auto, on, off")
    if context_tier not in {"default", "long_context"}:
        raise ValueError(f"unsupported context tier {context_tier!r}; choose: default, long_context")
    return LaunchOptions(model_id, effort, thinking, context_tier, forwarded, show_help)


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
    return replace(
        model,
        context_window=model.context_windows[options.context_tier],
        prompt_limit=model.prompt_limits[options.context_tier],
    )


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


def claude_compact_window(model: ModelSpec) -> int:
    """Reserve compaction headroom below the selected Copilot prompt budget."""
    floor = min(model.prompt_limit, CLAUDE_MIN_COMPACT_WINDOW)
    return max(model.prompt_limit - CLAUDE_COMPACT_HEADROOM_TOKENS, floor)


def claude_frontend_model(model: ModelSpec) -> str:
    """Claude caps a custom model id at 200k unless the id carries the [1m] frontend marker."""
    if claude_compact_window(model) > CLAUDE_DEFAULT_CONTEXT_WINDOW:
        return f"{model.model_id}{CLAUDE_EXTENDED_CONTEXT_SUFFIX}"
    return model.model_id


def claude_global_limits(root: ModelSpec, lane_models: list[ModelSpec]) -> tuple[int, int | None]:
    """Return Claude's single safe compaction limit and an optional small-model ceiling."""
    reachable = [root, *lane_models]
    compact_window = min(claude_compact_window(model) for model in reachable)
    context_window = min(model.prompt_limit for model in reachable)
    return compact_window, context_window if context_window <= CLAUDE_DEFAULT_CONTEXT_WINDOW else None


def child_command(
    harness: str,
    binary: str,
    base_url: str,
    loopback_token: str,
    model: ModelSpec,
    effort: str | None,
    thinking: str | None,
    forwarded: list[str],
    claude_auto_compact_window: int | None = None,
    claude_max_context_tokens: int | None = None,
) -> tuple[list[str], dict[str, str]]:
    env = dict(os.environ)
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_CUSTOM_HEADERS",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_DISABLE_THINKING",
        "OPENAI_API_KEY",
        "COPILOT_GITHUB_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
    ):
        env.pop(key, None)
    if harness == "claude":
        frontend_model = claude_frontend_model(model)
        if claude_max_context_tokens is not None:
            frontend_model = model.model_id
        env.update(
            {
                "ANTHROPIC_BASE_URL": base_url,
                "ANTHROPIC_AUTH_TOKEN": loopback_token,
                "ANTHROPIC_MODEL": frontend_model,
                "ANTHROPIC_DEFAULT_OPUS_MODEL": frontend_model,
                "ANTHROPIC_DEFAULT_SONNET_MODEL": frontend_model,
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": frontend_model,
                "ANTHROPIC_DEFAULT_FABLE_MODEL": frontend_model,
                "CLAUDE_CODE_AUTO_COMPACT_WINDOW": str(claude_auto_compact_window or claude_compact_window(model)),
            }
        )
        if claude_max_context_tokens is not None:
            env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(claude_max_context_tokens)
        command = [binary, "--model", frontend_model]
        if effort is not None:
            command.extend(["--effort", effort])
        if thinking == "off":
            env["CLAUDE_CODE_DISABLE_THINKING"] = "1"
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


def codex_lane_models(models: dict[str, ModelSpec], routes: dict[str, dict[str, str]]) -> dict[str, ModelSpec]:
    """Expose only entitled, exact lane pairs to Codex's spawn-model validator."""
    return {
        selector: replace(models[lane["model"]], model_id=selector)
        for selector, lane in routes.items()
        if lane["model"] in models
        and lane["effort"] in models[lane["model"]].efforts
        and not models[lane["model"]].endpoints.isdisjoint(SUPPORTED_ENDPOINTS)
    }


def codex_leaf_profile(source: str) -> str:
    """Keep the managed leaf body; let the hook, not native role overrides, pick its lane.

    Codex applies role settings AFTER spawn arguments. These generated profiles therefore
    omit model/effort settings and explicitly retain the native no-orchestration feature.
    Restrict projection to the managed scalar-header/multiline-instructions format.
    """
    header, separator, instructions = source.partition('developer_instructions = """')
    if not separator or not instructions.rstrip().endswith('"""'):
        raise ValueError("unsupported Codex leaf profile format")
    allowed = {"name", "description", "model", "model_reasoning_effort", "service_tier", "features"}
    kept = []
    for line in header.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([a-z_]+)\s*=\s*(.+)", line)
        if not match or match[1] not in allowed:
            raise ValueError("unsupported Codex leaf profile setting")
        if match[1] not in {"model", "model_reasoning_effort", "features"}:
            kept.append(line)
    return "\n".join([*kept, "features = { multi_agent = false }", separator + instructions])


def codex_lane_configuration(
    directory: Path, models: dict[str, ModelSpec], lane_models: dict[str, ModelSpec]
) -> tuple[list[str], dict[str, str]]:
    """Freeze the provider catalog and managed role set for one Codex process."""
    projection = Path(os.environ.get("AGENT_BANDS_FILE", Path.home() / ".config/ai/agent-bands.v1.json"))
    agents = json.loads(projection.read_text())["harnesses"]["copilot"]["agents"]
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    roles = {}
    args = []
    for name, pick in agents.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("invalid Codex lane role name")
        source = codex_home / "agents" / f"{name}.toml"
        selector = f"{pick['model']}@lane-{pick.get('effort')}"
        if not source.is_file() or selector not in lane_models:
            continue
        target = directory / f"{name}.toml"
        target.write_text(codex_leaf_profile(source.read_text()))
        args.extend(["-c", f"agents.{name}.config_file={json.dumps(str(target))}"])
        roles[name] = selector
    catalog = directory / "models.json"
    catalog.write_text(
        json.dumps({"models": [codex_model_info(model) for model in [*models.values(), *lane_models.values()]]})
    )
    args.extend(["-c", f"model_catalog_json={json.dumps(str(catalog))}"])
    return args, {"AGENT_BAND_CODEX_ROUTES": json.dumps(roles)}


def run_routed_child(
    harness: str, command: list[str], env: dict[str, str], models: dict[str, ModelSpec], lanes: dict[str, ModelSpec]
) -> int:
    env.pop("AGENT_BAND_CODEX_ROUTES", None)
    if harness != "codex":
        return run_child(command, env)
    with tempfile.TemporaryDirectory(prefix="codex-copilot-lanes-") as directory:
        args, route_env = codex_lane_configuration(Path(directory), models, lanes)
        env.update(route_env)
        # Put the route configuration before the native subcommand and after provider defaults.
        return run_child([command[0], *args, *command[1:]], env)


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
        lane_routes = load_lane_routes("copilot")
        lane_env = claude_lane_environment("copilot", lane_routes) if harness == "claude" else {}
        claude_auto_compact_window = None
        claude_max_context_tokens = None
        if harness == "claude":
            reachable_selectors = set(json.loads(lane_env["AGENT_BAND_CLAUDE_ROUTES"]))
            try:
                lane_models = [
                    models[lane["model"]] for selector, lane in lane_routes.items() if selector in reachable_selectors
                ]
            except KeyError as error:
                raise ValueError(
                    f"Copilot Claude lane model {error.args[0]!r} is not available through this subscription"
                ) from error
            claude_auto_compact_window, claude_max_context_tokens = claude_global_limits(model, lane_models)
        binary = harness_binary(harness)
    except (CopilotError, OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    loopback_token = secrets.token_urlsafe(32)
    effective_models = dict(models)
    effective_models[model.model_id] = model
    server, thread = start_server(
        AdapterContext(
            loopback_token,
            tokens,
            effective_models,
            effort=options.effort,
            thinking=options.thinking,
            lane_routes=lane_routes,
        )
    )
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        command, env = child_command(
            harness,
            binary,
            base_url,
            loopback_token,
            model,
            options.effort,
            options.thinking,
            options.forwarded,
            claude_auto_compact_window,
            claude_max_context_tokens,
        )
        env.update(lane_env)
        env["AGENT_BAND_SCHEMA_HARNESS"] = "copilot"
        env["AGENT_BAND_SUBSCRIPTION"] = "copilot"
        env.pop("AGENT_BAND_MODEL_FORMAT", None)
        env.pop("AGENT_BAND_MODEL_OVERRIDE", None)
        env.pop("AGENT_BAND_EFFORT_OVERRIDE", None)
        if not lane_env:
            env.pop("AGENT_BAND_CLAUDE_ROUTES", None)
        if lane_env:
            env.pop("CLAUDE_CODE_SUBAGENT_MODEL", None)
        return run_routed_child(harness, command, env, effective_models, codex_lane_models(models, lane_routes))
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
