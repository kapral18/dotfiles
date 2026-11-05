#!/usr/bin/env python3
"""Shared test support for the colocated script tests.

The former monolithic ``scripts/tests/test_scripts.py`` was split into
per-module ``scripts/test_<name>.py`` files colocated with their source. Every
split file imports the shared helpers/paths from here (``import _test_support``)
so path math and the subprocess runner stay in one place.

``make test`` runs ``python3 -m unittest discover -s scripts -t scripts``; that
puts ``scripts/`` on ``sys.path``, so both ``import _test_support`` and
``import <source_module>`` work with no per-file boilerplate.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import struct
import subprocess
import sys
import unittest
import zlib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent
FIXTURES = SCRIPTS / "tests" / "fixtures"
PICKERS = REPO / "home/dot_config/herdr/exact_scripts/pickers"
ARTIFACT_COMMAND = REPO / "home/exact_lib/exact_,artifact/main.py"
CODEX_COMMAND = REPO / "home/exact_lib/exact_,codex/main.py"

# Belt-and-suspenders: ensure scripts/ is importable even when a test file is run
# directly (python3 scripts/test_x.py) rather than via discover.
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


# Stateful stand-in for the herdr CLI. Workspaces live in $HERDR_DB as
# "<id>\t<label>\t<cwd>" rows; every call is appended to $HERDR_LOG. The server
# is up when $HERDR_DB exists, or (without $HERDR_DB) inside herdr, with no workspaces.
# HERDR_FAKE_CLOSE_KILLS=1 makes any workspace close SIGTERM the caller, the way
# closing the workspace a script runs in ends that script.
# HERDR_FAKE_CREATE_FAILS_ONCE=<file>: while <file> exists, the next create fails and removes it.
# HERDR_FAKE_PANE_COMMAND / _AGENT / _TEXT: a pane's foreground process, detected agent, and screen.
FAKE_HERDR = r"""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
log = os.environ.get("HERDR_LOG")
db = Path(os.environ["HERDR_DB"]) if os.environ.get("HERDR_DB") else None
if log:
    with open(log, "a") as f:
        f.write(" ".join(args) + "\n")
if not (db.exists() if db else os.environ.get("HERDR_SOCKET_PATH")):
    print(json.dumps({"error": {"code": "server_not_running"}}), file=sys.stderr)
    sys.exit(1)
rows = [line.split("\t") for line in db.read_text().splitlines() if line] if db else []

def opt(name, default=""):
    return args[args.index(name) + 1] if name in args else default

def save():
    if db:
        db.write_text("".join("\t".join(r) + "\n" for r in rows))

def ws(r):
    return {"workspace_id": r[0], "label": r[1], "focused": False}

def ok(result):
    print(json.dumps({"id": "fake", "result": result}))

cmd = " ".join(args[:2])
if cmd == "workspace list":
    ok({"workspaces": [ws(r) for r in rows]})
elif cmd == "pane list":
    want = opt("--workspace")
    ok({"panes": [{"pane_id": r[0] + ":p1", "workspace_id": r[0], "cwd": r[2]} for r in rows if not want or r[0] == want]})
elif cmd == "workspace create":
    once = os.environ.get("HERDR_FAKE_CREATE_FAILS_ONCE")
    if once and os.path.exists(once):
        os.remove(once)
        sys.exit(1)
    new_id = "w%d" % (max([int(r[0][1:]) for r in rows] + [0]) + 1)
    rows.append([new_id, opt("--label", new_id), opt("--cwd", os.getcwd())])
    save()
    ok({"workspace": ws(rows[-1]), "tab": {"tab_id": new_id + ":t1"}, "root_pane": {"pane_id": new_id + ":p1"}})
elif cmd == "workspace close":
    gone = [r for r in rows if r[0] == args[2]]
    rows = [r for r in rows if r[0] != args[2]]
    save()
    if gone and os.environ.get("HERDR_FAKE_CLOSE_KILLS") == "1":
        os.kill(os.getppid(), 15)
    ok({})
elif cmd == "workspace rename":
    if any(r[1] == args[3] for r in rows):
        sys.exit(1)
    for r in rows:
        if r[0] == args[2]:
            r[1] = args[3]
    save()
    ok({})
elif cmd == "pane process-info":
    ok({"process_info": {"pane_id": opt("--pane"), "foreground_processes": [{"pid": 1, "name": os.environ.get("HERDR_FAKE_PANE_COMMAND", "zsh")}]}})
elif cmd == "pane get":
    agent = os.environ.get("HERDR_FAKE_PANE_AGENT")
    ok({"pane": {"pane_id": args[2], **({"agent": agent} if agent else {})}})
elif cmd == "pane read":
    sys.stdout.write(os.environ.get("HERDR_FAKE_PANE_TEXT", ""))
elif cmd == "workspace get":
    ok({"workspace": {**ws(next(r for r in rows if r[0] == args[2])), "tab_count": 1}})
else:
    ok({})
"""


def deploy_herdr_libs(home: Path) -> None:
    """Lay out the picker libraries where deployed scripts source them under HOME."""
    lib = home / ".config/herdr/scripts/pickers/lib"
    lib.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PICKERS / "lib/herdr_ws.sh", lib / "herdr_ws.sh")
    shutil.copyfile(PICKERS / "lib/executable_herdr_sessions.sh", lib / "herdr_sessions.sh")
    (lib / "herdr_sessions.sh").chmod(0o755)
    shared = home / "lib/shared"
    shared.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / "home/exact_lib/exact_shared/worktree_lib.sh", shared / "worktree_lib.sh")
    shutil.copyfile(REPO / "home/exact_lib/exact_shared/executable_detach.sh", shared / "detach.sh")
    (shared / "detach.sh").chmod(0o755)


def herdr_home(home: Path) -> str:
    """deploy_herdr_libs(home), returned as the HOME value for a subprocess env."""
    deploy_herdr_libs(home)
    return str(home)


def install_fake_herdr(bin_dir: Path) -> Path:
    path = bin_dir / "herdr"
    path.write_text(FAKE_HERDR)
    path.chmod(0o755)
    return path


def run_script(args: list[str], *, stdin: str | None = None) -> str:
    """Invoke a script under scripts/ via the current interpreter.

    Mirrors the original ``_run``: cwd is scripts/ so sibling imports resolve;
    raises AssertionError with stderr on non-zero exit.
    """
    result = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS),
        input=stdin,
    )
    if result.returncode != 0:
        raise AssertionError(f"{args[0]} failed:\n{result.stderr}")
    return result.stdout


def modern_bash() -> str:
    """Return a bash 4+ binary path, or skip the test if none is available."""
    candidates = ["/opt/homebrew/bin/bash", "/usr/local/bin/bash", shutil.which("bash")]
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            result = subprocess.run(
                [candidate, "-c", '[ "${BASH_VERSINFO[0]:-0}" -ge 4 ]'],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            continue
        if result.returncode == 0:
            return candidate
    raise unittest.SkipTest("bash 4+ is required for picker shell helper tests")


def run_bash(script: str, *, env: dict[str, str] | None = None) -> str:
    """Run a bash snippet with a modern bash, cwd=REPO; raise on failure."""
    result = subprocess.run(
        [modern_bash(), "-c", script],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env={**os.environ, **(env or {})},
    )
    if result.returncode != 0:
        raise AssertionError(f"bash helper script failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result.stdout


def load_module(name: str, path: Path):
    """Import a script that is not on sys.path (for example a ``,command/main.py``) under ``name``."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def png_with_metadata(secret: str) -> bytes:
    """Build a tiny PNG whose tEXt chunk carries ``secret``, to prove metadata stripping."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\xff\x00\x00\x00\xff\x00")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"tEXt", b"Comment\x00" + secret.encode("utf-8"))
        + chunk(b"IDAT", pixels)
        + chunk(b"IEND", b"")
    )
