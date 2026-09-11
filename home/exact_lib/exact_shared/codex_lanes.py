"""Session-local Codex leaf profiles for cross-provider model routing.

Native role settings override spawn arguments. Both subscription and OpenRouter
launchers must remove those model pins without changing the managed leaf body.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path


def leaf_profile(source: str) -> str:
    """Keep the supported managed profile format, with native nesting disabled."""
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


def project_roles(directory: Path, selectors: dict[str, str], available: set[str]) -> tuple[list[str], dict[str, str]]:
    """Copy only available managed roles; return native config and the admission map."""
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    roles = {}
    args = []
    for name, selector in selectors.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("invalid Codex lane role name")
        source = codex_home / "agents" / f"{name}.toml"
        if not source.is_file() or selector not in available:
            continue
        target = directory / f"{name}.toml"
        target.write_text(leaf_profile(source.read_text()))
        args.extend(["-c", f"agents.{name}.config_file={json.dumps(str(target))}"])
        roles[name] = selector
    return args, {"AGENT_BAND_CODEX_ROUTES": json.dumps(roles)}


def openrouter_roles(directory: Path, catalog_path: Path) -> tuple[list[str], dict[str, str]]:
    projection = Path(os.environ.get("AGENT_BANDS_FILE", Path.home() / ".config/ai/agent-bands.v1.json"))
    agents = json.loads(projection.read_text())["harnesses"]["pi"]["agents"]
    selectors = {}
    for name, pick in agents.items():
        model, separator, effort = pick["model"].rpartition(":")
        if not separator or not effort or effort != pick.get("effort"):
            raise ValueError(f"invalid OpenRouter lane pair for {name}")
        selectors[name] = f"{model.removeprefix('openrouter/')}@preset/effort-{effort}"
    catalog = json.loads(catalog_path.read_text())
    available = {row["slug"] for row in catalog["models"]}
    return project_roles(directory, selectors, available)


def main(argv: list[str]) -> int:
    """Run one native process while its generated role files remain available."""
    if len(argv) < 3 or argv[1] != "--":
        print("Usage: codex_lanes.py CATALOG -- CODEX [ARGS...]", file=sys.stderr)
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix="codex-openrouter-lanes-") as directory:
            args, route_env = openrouter_roles(Path(directory), Path(argv[0]))
            return run_child([argv[2], *args, *argv[3:]], {**os.environ, **route_env})
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"Error: cannot project Codex OpenRouter lanes: {error}", file=sys.stderr)
        return 2


def run_child(command: list[str], env: dict[str, str]) -> int:
    """Keep profiles alive while the native TUI handles interrupts and resizes."""
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
        result = child.wait()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return 128 - result if result < 0 else result


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
