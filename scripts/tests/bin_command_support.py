#!/usr/bin/env python3
"""Shared fixtures for deployed bin command tests."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import http.server
import importlib.util
import io
import json
import os
import pkgutil
import queue
import re
import shlex
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock
from urllib.request import Request, urlopen

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
import ai_models
from _test_support import (
    ARTIFACT_COMMAND,
    CODEX_COMMAND,
    KBN_STACK_COMMAND,
    REPO,
    modern_bash,
)

# Every OpenRouter wrapper defaults to this route; model and effort remain selectable.
OPENROUTER_PIN = "xiaomi/mimo-v2.6-pro"
OPENROUTER_WIRE_PIN = f"{OPENROUTER_PIN}@preset/effort-high"


def _load_artifact_command():
    loader = SourceFileLoader("artifact_command", str(ARTIFACT_COMMAND))
    spec = importlib.util.spec_from_loader("artifact_command", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load ,artifact command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_format_md_command():
    source = REPO / "home/exact_bin/executable_,format-md"
    loader = SourceFileLoader("format_md_command", str(source))
    spec = importlib.util.spec_from_loader("format_md_command", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load format-md command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_openrouter_presets_module():
    source = REPO / "home/exact_lib/exact_shared/executable_openrouter_presets.py"
    loader = SourceFileLoader("openrouter_presets", str(source))
    spec = importlib.util.spec_from_loader("openrouter_presets", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load OpenRouter preset helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _es_dash_e_settings(cmd: list[str]) -> list[str]:
    settings: list[str] = []
    index = 0
    while index < len(cmd):
        if cmd[index] == "-E" and index + 1 < len(cmd):
            settings.append(cmd[index + 1])
            index += 2
            continue
        index += 1
    return settings


def _load_kbn_stack_command():
    """Load the ,kbn-stack entrypoint together with its ``kbn_stack`` package modules.

    ``main.py`` puts its directory on ``sys.path`` and imports the package, so the
    returned namespace exposes ``main``/``__file__`` from the entrypoint plus every
    package module (``procs``, ``store``, ...) as the attribute to patch or call.
    """
    loader = SourceFileLoader("kbn_stack_command", str(KBN_STACK_COMMAND))
    spec = importlib.util.spec_from_loader("kbn_stack_command", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load ,kbn-stack command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package = importlib.import_module("kbn_stack")
    modules = {
        info.name: importlib.import_module(f"kbn_stack.{info.name}") for info in pkgutil.iter_modules(package.__path__)
    }
    return types.SimpleNamespace(main=module.main, __file__=module.__file__, **modules)


@contextlib.contextmanager
def _patched_ports(kbn_stack, alive_slots: dict[int, tuple[bool, bool]], squatted_ports: frozenset = frozenset()):
    """Make ,kbn-stack port liveness deterministic for slot-reclamation tests.

    ``alive_slots`` maps slot -> (kbn_alive, es_alive). port_listener_pids reports
    a synthetic pid for ports whose half is alive; kill_port_listeners records the
    port and clears it; save_registry is captured instead of writing to disk.
    listener_identity_ok accepts any live port except those in ``squatted_ports``,
    whose listener is treated as a foreign process outside the owner's tree.
    kill_pid_group is recorded in ``killed_groups`` so no test path under the
    fixture ever signals a real process group.
    """
    alive_ports: set[int] = set()
    for slot, (kbn_alive, es_alive) in alive_slots.items():
        cfg = kbn_stack.slots.derive(slot)
        if kbn_alive:
            alive_ports.add(cfg["kbn_port"])
        if es_alive:
            alive_ports.add(cfg["es_http"])

    state: dict = {"killed": [], "saved": [], "killed_groups": []}
    original_listeners = kbn_stack.procs.port_listener_pids
    original_kill = kbn_stack.procs.kill_port_listeners
    original_save = kbn_stack.store.save_registry
    original_identity = kbn_stack.procs.listener_identity_ok
    original_kill_group = kbn_stack.procs.kill_pid_group

    def fake_listeners(port):
        return [10000 + port] if port in alive_ports else []

    def fake_kill(port):
        if port is None or port not in alive_ports:
            return False
        alive_ports.discard(port)
        state["killed"].append(port)
        return True

    def fake_identity(port, owner_pid):
        listeners = fake_listeners(port)
        return bool(listeners) and port not in squatted_ports, listeners

    kbn_stack.procs.port_listener_pids = fake_listeners
    kbn_stack.procs.kill_port_listeners = fake_kill
    kbn_stack.store.save_registry = lambda reg: state["saved"].append({k: dict(v) for k, v in reg.items()})
    kbn_stack.procs.listener_identity_ok = fake_identity
    kbn_stack.procs.kill_pid_group = state["killed_groups"].append
    try:
        yield state
    finally:
        kbn_stack.procs.port_listener_pids = original_listeners
        kbn_stack.procs.kill_port_listeners = original_kill
        kbn_stack.store.save_registry = original_save
        kbn_stack.procs.listener_identity_ok = original_identity
        kbn_stack.procs.kill_pid_group = original_kill_group


_HANG_AFTER_UNBIND_SERVER = """\
import os
import signal
import socket
import sys
import time

port = int(sys.argv[1])
role = sys.argv[2]
if role == "worker":
    signal.signal(signal.SIGTERM, lambda *_: None)
    while True:
        time.sleep(60)

sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("127.0.0.1", port))
sock.listen(1)


def hang(_signum, _frame):
    try:
        sock.close()
    except OSError:
        pass
    while True:
        time.sleep(60)


signal.signal(signal.SIGTERM, hang)
print(f"ready {os.getpid()}", flush=True)
while True:
    time.sleep(60)
"""


def _spawn_hang_after_unbind_group(script: Path) -> tuple[int, int, list[int]]:
    """Start a session: leader + listener that hangs after closing the port + worker.

    Returns ``(port, pgid, member_pids)``.
    """
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    leader = os.fork()
    if leader == 0:
        os.setsid()
        if os.fork() == 0:
            os.execv(sys.executable, [sys.executable, str(script), str(port), "listener"])
        if os.fork() == 0:
            os.execv(sys.executable, [sys.executable, str(script), str(port), "worker"])
        while True:
            try:
                os.wait()
            except ChildProcessError:
                time.sleep(60)
    deadline = time.monotonic() + 5
    listeners: list[int] = []
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
        )
        listeners = [int(tok) for tok in result.stdout.split() if tok.isdigit()]
        if listeners:
            break
        time.sleep(0.05)
    if not listeners:
        try:
            os.killpg(os.getpgid(leader), signal.SIGKILL)
        except OSError:
            pass
        raise AssertionError("hang-after-unbind harness failed to bind")
    pgid = os.getpgid(listeners[0])
    ps = subprocess.run(["ps", "-axo", "pid=,pgid="], capture_output=True, text=True, check=False)
    members = []
    for line in ps.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == str(pgid):
            members.append(int(parts[0]))
    return port, pgid, members


def _reap_group(pgid: int, leader: int | None = None) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass
    if leader is not None:
        try:
            os.waitpid(leader, 0)
        except ChildProcessError:
            pass


def _capture_stop_existing_serverless(kbn_stack, registry: dict, new_started_by: str):
    stopped: list[tuple[str, bool]] = []
    saved: list[dict] = []
    original_stop_entry = kbn_stack.lifecycle.stop_entry
    original_save_registry = kbn_stack.store.save_registry

    def fake_stop_entry(worktree, entry, *, allow_user_owned=True):
        stopped.append((worktree, allow_user_owned))
        return True

    kbn_stack.lifecycle.stop_entry = fake_stop_entry
    kbn_stack.store.save_registry = lambda updated: saved.append(json.loads(json.dumps(updated)))
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                kbn_stack.lifecycle.stop_existing_serverless(registry, "/current", new_started_by)
            except SystemExit:
                blocked = True
            else:
                blocked = False
    finally:
        kbn_stack.lifecycle.stop_entry = original_stop_entry
        kbn_stack.store.save_registry = original_save_registry

    return blocked, stopped, saved


def _lane_wires() -> list[str]:
    """The live `--lane-wire-models` list, so preset stubs track the `category_models.openrouter` rows instead of a copy."""
    module = _load_openrouter_presets_module()
    with mock.patch.dict(os.environ, {"CHEZMOI_SOURCE_DIR": str(REPO)}):
        return module._lane_wire_models()


def _lane_wire_echo(indent: str = "") -> str:
    """Shell `echo` lines that print the live OpenRouter lane wires, one per line."""
    return "".join(f'{indent}echo "{wire}"\n' for wire in _lane_wires())


def _install_openrouter_preset_stub(home: Path) -> None:
    preset_helper = home / "lib" / "shared" / "openrouter_presets.py"
    preset_helper.parent.mkdir(parents=True, exist_ok=True)
    preset_helper.write_text(
        """#!/usr/bin/env bash
if [[ "$1" == "--context-window" ]]; then
  case "$3" in
  short) echo 200000 ;;
  long) echo 1048576 ;;
  *) exit 1 ;;
  esac
  exit 0
fi
if [[ "$1" == "--session-budget-env" ]]; then
  echo "CONTEXT_LIMIT=1048576"
  echo "MAX_OUTPUT_TOKENS=131072"
  echo "PROMPT_LIMIT=200000"
  exit 0
fi
if [[ "$1" == "--codex-model-catalog" ]]; then
  echo '{"models":[]}'
  exit 0
fi
if [[ "$1" == "--lane-wire-models" ]]; then
"""
        + _lane_wire_echo("  ")
        + """  exit 0
fi
exit 0
""",
        encoding="utf-8",
    )
    preset_helper.chmod(0o755)
    (preset_helper.parent / "codex_lanes.py").write_bytes(
        (REPO / "home/exact_lib/exact_shared/codex_lanes.py").read_bytes()
    )
    bands = home / ".config/ai/agent-bands.v1.json"
    bands.parent.mkdir(parents=True, exist_ok=True)
    bands.write_bytes((REPO / "home/dot_config/ai/readonly_agent-bands.v1.json").read_bytes())
    (preset_helper.parent / "claude_lanes.py").write_bytes(
        (REPO / "home/exact_lib/exact_shared/claude_lanes.py").read_bytes()
    )
    for role in json.loads(bands.read_text())["harnesses"]["openrouter"]["agents"]:
        profile = home / ".claude/agents" / f"{role}.md"
        profile.parent.mkdir(parents=True, exist_ok=True)
        if profile.exists():
            continue
        profile.write_text(
            f"---\nname: {role}\ndescription: Fixture leaf\nmodel: inherit\ntools: Read, Agent\n---\nKeep this body.\n"
        )
