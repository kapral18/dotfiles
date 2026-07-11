#!/usr/bin/env python3
"""Launch Copilot after one locked header-auth MCP preflight batch."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping

REAL_COPILOT = "/opt/homebrew/bin/copilot"
MCP_TOKEN = ",mcp-token"
PLAN_SCHEMA = 1
NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

VALUE_OPTIONS = {
    "--add-dir",
    "--add-github-mcp-tool",
    "--add-github-mcp-toolset",
    "--additional-mcp-config",
    "--agent",
    "--attachment",
    "-C",
    "--context",
    "--disable-mcp-server",
    "--effort",
    "--reasoning-effort",
    "--extension-sdk-path",
    "-i",
    "--interactive",
    "--log-dir",
    "--log-level",
    "--max-ai-credits",
    "--max-autopilot-continues",
    "--mode",
    "--model",
    "-n",
    "--name",
    "--output-format",
    "-p",
    "--prompt",
    "--plugin-dir",
    "--session-id",
    "--stream",
}
AMBIGUOUS_OPTIONS = {
    "--allow-tool",
    "--allow-url",
    "--available-tools",
    "--bash-env",
    "--connect",
    "--deny-tool",
    "--deny-url",
    "--excluded-tools",
    "--mouse",
    "-r",
    "--resume",
    "--secret-env-vars",
    "--share",
}
BOOLEAN_OPTIONS = {
    "--acp",
    "--allow-all",
    "--allow-all-mcp-server-instructions",
    "--allow-all-paths",
    "--allow-all-tools",
    "--allow-all-urls",
    "--autopilot",
    "--banner",
    "--continue",
    "--disable-builtin-mcps",
    "--disallow-temp-dir",
    "--enable-all-github-mcp-tools",
    "--enable-memory",
    "--enable-reasoning-summaries",
    "--experimental",
    "--no-ask-user",
    "--no-auto-update",
    "--no-bash-env",
    "--no-color",
    "--no-custom-instructions",
    "--no-experimental",
    "--no-mouse",
    "--no-remote",
    "--no-remote-export",
    "--plain-diff",
    "--plan",
    "--remote",
    "--remote-export",
    "--screen-reader",
    "--share-gist",
    "-s",
    "--silent",
    "--yolo",
}
ADMIN_COMMANDS = {
    "completion",
    "help",
    "init",
    "login",
    "mcp",
    "plugin",
    "plugins",
    "skill",
    "update",
    "version",
}


class LaunchError(RuntimeError):
    """A pre-launch failure safe to report without child-process output."""


@dataclass(frozen=True)
class HeaderAuthRequirement:
    server: str
    token_source: str
    shell_command: str

    @classmethod
    def from_payload(cls, payload: object) -> HeaderAuthRequirement:
        if not isinstance(payload, dict):
            raise LaunchError("invalid MCP header-auth batch plan.")
        server = payload.get("server")
        token_source = payload.get("token_source")
        shell_command = payload.get("shell_command")
        if not all(isinstance(value, str) for value in (server, token_source, shell_command)):
            raise LaunchError("invalid MCP header-auth batch plan.")
        if not NAME_PATTERN.fullmatch(server) or not NAME_PATTERN.fullmatch(token_source):
            raise LaunchError("invalid MCP header-auth batch plan.")
        try:
            command_argv = shlex.split(shell_command)
        except ValueError as err:
            raise LaunchError("invalid MCP header-auth batch plan.") from err
        if command_argv != [MCP_TOKEN, token_source, "--bearer"]:
            raise LaunchError("invalid MCP header-auth batch plan.")
        return cls(server, token_source, shell_command)


@dataclass(frozen=True)
class SourceContext:
    source_dir: Path
    is_work: bool
    registry: Path
    generator: Path
    artifact_helper: Path
    ledger: Path

    @property
    def scripts_dir(self) -> Path:
        return self.source_dir.parent / "scripts"

    @property
    def profile(self) -> str:
        return "work" if self.is_work else "personal"


@dataclass(frozen=True)
class BatchPlan:
    source: SourceContext
    target: Path
    placeholder: str
    requirements: tuple[HeaderAuthRequirement, ...]


@dataclass(frozen=True)
class ResolvedHeaders:
    by_command: Mapping[str, str] = field(repr=False)


@dataclass(frozen=True)
class RenderedConfig:
    document: dict[str, Any] = field(repr=False)
    content: bytes = field(repr=False)


@dataclass(frozen=True)
class TargetSnapshot:
    content: bytes | None = field(repr=False)


def _option_base(argument: str) -> tuple[str, bool]:
    if argument.startswith("--") and "=" in argument:
        return argument.split("=", 1)[0], True
    if argument.startswith("--"):
        return argument, False
    if argument.startswith("-") and len(argument) > 2:
        return argument[:2], True
    return argument, False


def should_refresh(argv: list[str]) -> bool:
    """Return whether Copilot 1.0.70 may open an MCP session."""
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in {"-h", "--help", "-v", "--version"}:
            return False
        if argument.startswith("-"):
            base, has_inline_value = _option_base(argument)
            if base in AMBIGUOUS_OPTIONS:
                return True
            if base in VALUE_OPTIONS:
                index += 1 if has_inline_value else 2
                continue
            if not has_inline_value and base in BOOLEAN_OPTIONS:
                index += 1
                continue
            return True
        return argument not in ADMIN_COMMANDS
    return True


def _parse_boolean(value: str, label: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise LaunchError(f"{label} must be true or false.")


def _source_data() -> tuple[Path, bool]:
    source_override = os.environ.get("COPILOT_SOURCE_DIR")
    work_override = os.environ.get("COPILOT_IS_WORK")
    if source_override is not None or work_override is not None:
        if source_override is None or work_override is None:
            raise LaunchError("COPILOT_SOURCE_DIR and COPILOT_IS_WORK must be set together.")
        return Path(source_override).expanduser(), _parse_boolean(work_override, "COPILOT_IS_WORK")
    try:
        result = subprocess.run(
            ["chezmoi", "data", "--format", "json"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as err:
        raise LaunchError("could not read chezmoi source data.") from err
    if result.returncode != 0:
        raise LaunchError("could not read chezmoi source data.")
    try:
        payload = json.loads(result.stdout)
        source_dir = payload["chezmoi"]["sourceDir"]
        is_work = payload.get("isWork")
    except (KeyError, TypeError, json.JSONDecodeError) as err:
        raise LaunchError("could not read chezmoi source data.") from err
    if not isinstance(source_dir, str) or not source_dir or not isinstance(is_work, bool):
        raise LaunchError("could not read chezmoi source data.")
    return Path(source_dir), is_work


def _source_context() -> SourceContext:
    source_dir, is_work = _source_data()
    scripts_dir = source_dir.parent / "scripts"
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return SourceContext(
        source_dir=source_dir,
        is_work=is_work,
        registry=Path(
            os.environ.get(
                "COPILOT_MCP_REGISTRY",
                source_dir / ".chezmoidata/mcp_servers.yaml",
            )
        ),
        generator=Path(
            os.environ.get(
                "COPILOT_MCP_GENERATOR",
                scripts_dir / "generate_mcp_configs.py",
            )
        ),
        artifact_helper=Path(
            os.environ.get(
                "COPILOT_ARTIFACT_HELPER",
                scripts_dir / "generated_artifact_ledger.py",
            )
        ),
        ledger=Path(
            os.environ.get(
                "CHEZMOI_ARTIFACT_LEDGER",
                state_home / "chezmoi/generated_artifacts.v1.json",
            )
        ),
    )


def _generator_command(source: SourceContext, flag: str) -> list[str]:
    return [
        sys.executable,
        str(source.generator),
        str(source.registry),
        "true" if source.is_work else "false",
        "copilot",
        flag,
    ]


def _discover_plan(source: SourceContext, target: Path) -> BatchPlan:
    try:
        result = subprocess.run(
            _generator_command(source, "--copilot-header-auth-plan"),
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as err:
        raise LaunchError("could not build MCP header-auth batch plan.") from err
    if result.returncode != 0:
        raise LaunchError("could not build MCP header-auth batch plan.")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as err:
        raise LaunchError("could not build MCP header-auth batch plan.") from err
    return _plan_from_payload(source, target, payload)


def _plan_from_payload(source: SourceContext, target: Path, payload: object) -> BatchPlan:
    if not isinstance(payload, dict) or payload.get("schema_version") != PLAN_SCHEMA:
        raise LaunchError("invalid MCP header-auth batch plan.")
    placeholder = payload.get("refresh_placeholder")
    rows = payload.get("header_auth_servers")
    if not isinstance(placeholder, str) or not placeholder or not isinstance(rows, list):
        raise LaunchError("invalid MCP header-auth batch plan.")
    requirements = tuple(HeaderAuthRequirement.from_payload(row) for row in rows)
    server_names = [requirement.server for requirement in requirements]
    if len(server_names) != len(set(server_names)):
        raise LaunchError("invalid MCP header-auth batch plan.")
    return BatchPlan(source, target, placeholder, requirements)


def _valid_authorization(value: str) -> bool:
    return "\n" not in value and value.startswith("Bearer ") and bool(value[7:])


def _resolve_headers(plan: BatchPlan) -> ResolvedHeaders:
    grouped: dict[str, list[HeaderAuthRequirement]] = {}
    for requirement in plan.requirements:
        grouped.setdefault(requirement.token_source, []).append(requirement)
    token_binary = os.environ.get("COPILOT_MCP_TOKEN_BIN", MCP_TOKEN)
    resolved: dict[str, str] = {}
    failed_servers: list[str] = []
    for source, requirements in grouped.items():
        try:
            result = subprocess.run(
                [token_binary, source, "--login", "--quiet", "--bearer"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
                text=True,
            )
        except OSError:
            result = None
        authorization = result.stdout.strip() if result is not None and result.returncode == 0 else ""
        if not _valid_authorization(authorization):
            failed_servers.extend(requirement.server for requirement in requirements)
            continue
        resolved[source] = authorization
    if failed_servers:
        raise LaunchError(f"could not refresh MCP token(s): {', '.join(failed_servers)}.")
    by_command = {requirement.shell_command: resolved[requirement.token_source] for requirement in plan.requirements}
    return ResolvedHeaders(by_command)


def _render_config(plan: BatchPlan, headers: ResolvedHeaders) -> RenderedConfig:
    try:
        result = subprocess.run(
            _generator_command(plan.source, "--header-auth-overrides-stdin"),
            input=json.dumps(dict(headers.by_command)),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
    except OSError as err:
        raise LaunchError("could not render fresh MCP config.") from err
    if result.returncode != 0:
        raise LaunchError("could not render fresh MCP config.")
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as err:
        raise LaunchError("could not render fresh MCP config.") from err
    if not isinstance(document, dict):
        raise LaunchError("could not render fresh MCP config.")
    _validate_rendered(plan, headers, document)
    content = result.stdout.encode()
    if not content.endswith(b"\n"):
        content += b"\n"
    return RenderedConfig(document, content)


def _authorization(spec: object) -> object:
    if not isinstance(spec, dict):
        return None
    headers = spec.get("headers")
    return headers.get("Authorization") if isinstance(headers, dict) else None


def _validate_rendered(
    plan: BatchPlan,
    headers: ResolvedHeaders,
    document: dict[str, Any],
) -> None:
    servers = document.get("mcpServers")
    if not isinstance(servers, dict):
        raise LaunchError("rendered MCP config has no mcpServers object.")
    placeholders = [str(server) for server, spec in servers.items() if _authorization(spec) == plan.placeholder]
    if placeholders:
        raise LaunchError(f"MCP token refresh placeholder remains for: {', '.join(placeholders)}.")
    mismatches = [
        requirement.server
        for requirement in plan.requirements
        if _authorization(servers.get(requirement.server)) != headers.by_command[requirement.shell_command]
    ]
    if mismatches:
        raise LaunchError(f"rendered MCP Authorization mismatch for: {', '.join(mismatches)}.")


def _snapshot(path: Path) -> TargetSnapshot:
    try:
        return TargetSnapshot(path.read_bytes())
    except FileNotFoundError:
        return TargetSnapshot(None)
    except OSError as err:
        raise LaunchError(f"could not read MCP config target {path}.") from err


def _same_document(snapshot: TargetSnapshot, rendered: RenderedConfig) -> bool:
    if snapshot.content is None:
        return False
    try:
        return json.loads(snapshot.content) == rendered.document
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False


def _atomic_write(path: Path, content: bytes, mode: int = 0o600) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, mode)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise


def _restore(path: Path, snapshot: TargetSnapshot) -> None:
    if snapshot.content is None:
        path.unlink(missing_ok=True)
        return
    _atomic_write(path, snapshot.content)


def _record_artifact(plan: BatchPlan) -> None:
    source = plan.source
    arguments = [
        sys.executable,
        str(source.artifact_helper),
        "--ledger",
        str(source.ledger),
        "record",
        "--id",
        "copilot-mcp",
        "--producer",
        "07-merge-copilot-config",
        "--profile",
        source.profile,
        "--target",
        str(plan.target),
        "--ownership-adapter",
        "whole-file",
        "--input",
        str(source.registry),
        "--transform",
        str(source.generator),
        "--transform",
        str(source.scripts_dir / "mcp_registry.py"),
        "--transform",
        str(source.scripts_dir / "yaml_parser.py"),
        "--transform",
        str(source.scripts_dir / "chezmoi_lib.sh"),
        "--consumer",
        "copilot",
    ]
    try:
        result = subprocess.run(
            arguments,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError as err:
        raise LaunchError("could not update generated artifact ledger.") from err
    if result.returncode != 0:
        raise LaunchError("could not update generated artifact ledger.")


def _apply_rendered(plan: BatchPlan, rendered: RenderedConfig) -> bool:
    snapshot = _snapshot(plan.target)
    if _same_document(snapshot, rendered):
        try:
            if stat.S_IMODE(plan.target.stat().st_mode) != 0o600:
                os.chmod(plan.target, 0o600)
        except OSError as err:
            raise LaunchError(f"could not secure MCP config target {plan.target}.") from err
        return False
    try:
        _atomic_write(plan.target, rendered.content)
        _record_artifact(plan)
    except (LaunchError, OSError) as err:
        try:
            _restore(plan.target, snapshot)
        except OSError:
            pass
        if isinstance(err, LaunchError):
            raise
        raise LaunchError(f"could not update MCP config target {plan.target}.") from err
    return True


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except OSError as err:
        if descriptor is not None:
            os.close(descriptor)
        raise LaunchError(f"could not lock MCP config target {path}.") from err
    try:
        yield
    finally:
        assert descriptor is not None
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _prepare_target() -> tuple[Path, Path]:
    target = Path(
        os.environ.get(
            "COPILOT_MCP_CONFIG",
            Path.home() / ".copilot/mcp-config.json",
        )
    )
    lock = Path(os.environ.get("COPILOT_MCP_LOCK", target.with_suffix(target.suffix + ".lock")))
    try:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(target.parent, 0o700)
    except OSError as err:
        raise LaunchError(f"could not prepare MCP config directory {target.parent}.") from err
    return target, lock


def _preflight() -> None:
    target, lock = _prepare_target()
    with _exclusive_lock(lock):
        source = _source_context()
        plan = _discover_plan(source, target)
        headers = _resolve_headers(plan)
        rendered = _render_config(plan, headers)
        _apply_rendered(plan, rendered)


def main(argv: list[str]) -> int:
    real_copilot = os.environ.get("COPILOT_REAL_BIN", REAL_COPILOT)
    if not os.access(real_copilot, os.X_OK):
        print(f"Error: real copilot CLI not found at {real_copilot}.", file=sys.stderr)
        return 127
    if should_refresh(argv):
        try:
            _preflight()
        except LaunchError as err:
            print(f",copilot: {err}", file=sys.stderr)
            print(
                ",copilot: run ',mcp-token <server> --login' without --quiet to inspect the OAuth flow.",
                file=sys.stderr,
            )
            return 1
    os.execv(real_copilot, [real_copilot, *argv])
    return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
