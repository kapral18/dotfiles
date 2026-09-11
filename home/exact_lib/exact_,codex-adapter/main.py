#!/usr/bin/env python3
"""Launch Claude Code, Copilot CLI, or Cursor through the Codex subscription adapter."""

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
from protocols import claude_lane_environment, load_lane_routes
from server import AdapterContext, start_server
from state import OpaqueReasoningStore

CLAUDE_DEFAULT_CONTEXT_WINDOW = 200_000
CLAUDE_EXTENDED_CONTEXT_SUFFIX = "[1m]"
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
CURSOR_PINNED_OPTIONS = {"--base-url", "--local-agent-api-key", "--authless", "--model", "-m"}


@dataclass(frozen=True)
class LaunchOptions:
    model_id: str | None
    effort: str | None
    forwarded: list[str]
    help: bool


@dataclass(frozen=True)
class ContextBudget:
    """The selected Codex window and the distinct limits derived from it."""

    active_context_window: int
    usable_input_tokens: int
    auto_compact_token_limit: int


def usage(harness: str) -> str:
    return f"""Usage: ,{harness}-codex [adapter options] [harness arguments]

Launch {harness} through an owner-authenticated loopback adapter backed by the
current Codex ChatGPT subscription.

Adapter options:
  -m, --model ID             Select the root Codex backend model
      --effort LEVEL         Set root reasoning effort; explicit lane tags keep theirs
      --reasoning-effort L   Alias for --effort
  -h, --help                 Show this wrapper help

Effort levels: none, minimal, low, medium, high, xhigh, max, ultra.
Without --model, the wrapper reads model from the active Codex config.
Without --effort, the harness-generated effort is preserved. Use -- before an
underlying harness flag that has the same name as an adapter option.
Delegation requires verified child-lane transport: supported through Claude aliases;
disabled on the Cursor and Copilot frontends. Native harness routes are unaffected.
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


def validate_cursor_forwarded(argv: list[str]) -> None:
    for argument in argv:
        if argument in CURSOR_PINNED_OPTIONS or any(
            argument.startswith(f"{option}=") for option in CURSOR_PINNED_OPTIONS
        ):
            raise ValueError(f"{argument} cannot override the Cursor loopback adapter")


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


def _positive_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _context_config(config_path: Path | None = None) -> tuple[int | None, int | None]:
    path = config_path or default_config_path()
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, None
    except OSError as error:
        raise RuntimeError(f"Codex config at {path} is unreadable") from error
    payload: dict[str, int] = {}
    for line in content.splitlines():
        if line.strip().startswith("["):
            break
        match = re.fullmatch(
            r"\s*(model_context_window|model_auto_compact_token_limit)\s*=\s*([+-]?[0-9][0-9_]*)\s*(?:#.*)?",
            line,
        )
        if match:
            payload[match[1]] = int(match[2].replace("_", ""))
    return (
        _positive_int(payload.get("model_context_window")),
        _nonnegative_int(payload.get("model_auto_compact_token_limit")),
    )


def resolve_model_budget(
    model_id: str,
    cache_path: Path | None = None,
    config_path: Path | None = None,
) -> ContextBudget:
    """Resolve Codex's active window, usable input, and compaction threshold."""
    configured_window, configured_compaction = _context_config(config_path)
    path = cache_path or default_models_cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        payload = None
    models = payload.get("models") if isinstance(payload, dict) else None
    selected = (
        next(
            (model for model in models if isinstance(model, dict) and model.get("slug") == model_id),
            None,
        )
        if isinstance(models, list)
        else None
    )
    if not isinstance(selected, dict):
        if configured_window is None:
            raise RuntimeError(
                f"Codex model metadata for {model_id!r} is unavailable; refresh the native Codex catalog and try again, "
                "or set model_context_window in the active Codex config"
            )
        active_context_window = configured_window
        effective_percent = 95
        model_compaction = None
    else:
        model_window = _positive_int(selected.get("context_window"))
        if model_window is None and configured_window is None:
            raise RuntimeError(
                f"Codex model metadata for {model_id!r} has no context_window; refresh the native Codex catalog and try again, "
                "or set model_context_window in the active Codex config"
            )
        active_context_window = configured_window if configured_window is not None else model_window
        assert active_context_window is not None
        maximum_window = _positive_int(selected.get("max_context_window"))
        if configured_window is not None and maximum_window is not None:
            active_context_window = min(active_context_window, maximum_window)
        effective_percent = _positive_int(selected.get("effective_context_window_percent")) or 95
        model_compaction = _nonnegative_int(selected.get("auto_compact_token_limit"))

    usable_input_tokens = active_context_window * effective_percent // 100
    default_compaction = active_context_window * 9 // 10
    requested_compaction = (
        configured_compaction
        if configured_compaction is not None
        else model_compaction
        if model_compaction is not None
        else default_compaction
    )
    auto_compact_token_limit = min(requested_compaction, default_compaction)
    return ContextBudget(active_context_window, usable_input_tokens, auto_compact_token_limit)


def claude_frontend_model(model: str, budget: ContextBudget) -> str:
    if budget.active_context_window > CLAUDE_DEFAULT_CONTEXT_WINDOW:
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


def cursor_binary() -> str:
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
    budget: ContextBudget,
    claude_auto_compact_token_limit: int | None = None,
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
        env.pop("COPILOT_PROVIDER_MAX_PROMPT_TOKENS", None)
        env.pop("COPILOT_PROVIDER_MAX_OUTPUT_TOKENS", None)
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
        env["COPILOT_PROVIDER_MAX_PROMPT_TOKENS"] = str(budget.usable_input_tokens)
        return [binary, *forwarded], env
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
        env.update({"CURSOR_LOCAL_AGENT_BASE_URL": f"{base_url}/v1", "CURSOR_LOCAL_AGENT_API_KEY": token})
        return [binary, "--model", model, *forwarded], env
    for key in (
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_FOUNDRY",
        "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
    ):
        env.pop(key, None)
    frontend_model = claude_frontend_model(model, budget)
    env.update(
        {
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_AUTH_TOKEN": token,
            "ANTHROPIC_MODEL": frontend_model,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": frontend_model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": frontend_model,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": frontend_model,
            "ANTHROPIC_DEFAULT_FABLE_MODEL": frontend_model,
        }
    )
    if budget.active_context_window <= CLAUDE_DEFAULT_CONTEXT_WINDOW:
        env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(budget.active_context_window)
    env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = str(claude_auto_compact_token_limit or budget.auto_compact_token_limit)
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
        if harness == "cursor":
            validate_cursor_forwarded(options.forwarded)
        model = options.model_id or resolve_default_model()
        budget = resolve_model_budget(model)
        lane_routes = load_lane_routes("codex")
        lane_env = claude_lane_environment("codex", lane_routes) if harness == "claude" else {}
        claude_budget = budget
        claude_auto_compact_token_limit = budget.auto_compact_token_limit
        if harness == "claude":
            reachable_selectors = set(json.loads(lane_env["AGENT_BAND_CLAUDE_ROUTES"]))
            lane_budgets = {
                lane["model"]: resolve_model_budget(lane["model"])
                for selector, lane in lane_routes.items()
                if selector in reachable_selectors
            }
            claude_auto_compact_token_limit = min(
                [
                    budget.auto_compact_token_limit,
                    *(lane_budget.auto_compact_token_limit for lane_budget in lane_budgets.values()),
                ]
            )
            claude_budget = ContextBudget(
                min([budget.active_context_window, *(item.active_context_window for item in lane_budgets.values())]),
                min([budget.usable_input_tokens, *(item.usable_input_tokens for item in lane_budgets.values())]),
                claude_auto_compact_token_limit,
            )
        binary = cursor_binary() if harness == "cursor" else harness_binary(harness)
        refresh_binary = codex_binary()
        credentials = CodexAuth(codex_binary=refresh_binary)
        credentials.get()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    token = secrets.token_urlsafe(32)
    context = AdapterContext(
        model=model,
        effort=options.effort,
        token=token,
        codex=CodexClient(credentials),
        store=OpaqueReasoningStore(),
        lane_routes=lane_routes,
        usable_input_tokens=budget.usable_input_tokens,
    )
    server, thread = start_server(context)
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        forwarded = options.forwarded
        if harness == "copilot" and options.effort is not None:
            forwarded = [*forwarded, "--effort", options.effort]
        command, env = child_command(
            harness,
            binary,
            base_url,
            token,
            model,
            forwarded,
            claude_budget if harness == "claude" else budget,
            claude_auto_compact_token_limit if harness == "claude" else None,
        )
        env.update(lane_env)
        env["AGENT_BAND_SCHEMA_HARNESS"] = "codex"
        env["AGENT_BAND_SUBSCRIPTION"] = "codex"
        env.pop("AGENT_BAND_MODEL_FORMAT", None)
        env.pop("AGENT_BAND_MODEL_OVERRIDE", None)
        env.pop("AGENT_BAND_EFFORT_OVERRIDE", None)
        if not lane_env:
            env.pop("AGENT_BAND_CLAUDE_ROUTES", None)
        if lane_env:
            env.pop("CLAUDE_CODE_SUBAGENT_MODEL", None)
        return run_child(command, env)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main(argv: list[str]) -> int:
    if len(argv) < 1 or argv[0] not in {"claude", "copilot", "cursor"}:
        print("Usage: main.py {claude|copilot|cursor} [arguments]", file=sys.stderr)
        return 2
    return launch(argv[0], argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
