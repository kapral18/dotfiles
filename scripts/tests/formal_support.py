from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
LIB_DIR = REPO / "home" / "exact_lib" / "exact_,formal"
CLI = LIB_DIR / "main.py"
FIXTURE_DIR = REPO / "scripts" / "tests" / "fixtures" / "formal" / "toy"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from formal import anchors as anchors_mod  # noqa: E402
from formal import audit as audit_mod  # noqa: E402
from formal import build as build_mod  # noqa: E402
from formal import catalog as catalog_mod  # noqa: E402
from formal import cli as cli_mod  # noqa: E402
from formal import exe as exe_mod  # noqa: E402
from formal import leankit as leankit_mod  # noqa: E402
from formal import manifest as manifest_mod  # noqa: E402
from formal import paths as paths_mod  # noqa: E402
from formal import prove as prove_mod  # noqa: E402
from formal import replay as replay_mod  # noqa: E402
from formal import util as util_mod  # noqa: E402
from formal.util import CliError, read_json, write_json, write_json_atomic  # noqa: E402


def run_formal(cwd: Path, formal_home: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "AGENT_FORMAL_HOME": str(formal_home), "FORMAL_LIB_DIR": str(LIB_DIR)}
    result = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(f",formal {' '.join(args)} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result


def init_git_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    # Local-only config so a user-global commit.gpgsign or core.hooksPath can never break these tests.
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    subprocess.run(["git", "config", "core.hooksPath", "/dev/null"], cwd=path, check=True)
    (path / ".gitkeep").write_text("keep\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def commit_all(path: Path, message: str) -> str:
    # --allow-empty: anchors and other formal state live under AGENT_FORMAL_HOME, outside this
    # workspace, so a commit meant to mark "state as of now" may have nothing staged in the repo.
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", message], cwd=path, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True
    ).stdout.strip()
