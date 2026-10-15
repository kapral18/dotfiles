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

# _test_support.py lives in scripts/, so SCRIPTS is its parent directory.
SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent
FIXTURES = SCRIPTS / "tests" / "fixtures"
TMUX_PICKERS = REPO / "home/dot_config/exact_tmux/exact_scripts/pickers"
ARTIFACT_COMMAND = REPO / "home/exact_lib/exact_,artifact/main.py"
CODEX_COMMAND = REPO / "home/exact_lib/exact_,codex/main.py"

# Belt-and-suspenders: ensure scripts/ is importable even when a test file is run
# directly (python3 scripts/test_x.py) rather than via discover.
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


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
    raise unittest.SkipTest("bash 4+ is required for tmux picker shell helper tests")


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
