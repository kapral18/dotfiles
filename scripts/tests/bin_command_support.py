#!/usr/bin/env python3
"""Shared fixtures for deployed bin command tests."""

from __future__ import annotations

import http.server
import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock
from urllib.request import Request, urlopen

from _test_support import (
    ARTIFACT_COMMAND,
    CODEX_COMMAND,
    REPO,
    modern_bash,
)

# Every OpenRouter wrapper defaults to this route; model and effort remain selectable.
OPENROUTER_PIN = "xiaomi/mimo-v2.6-pro"
OPENROUTER_WIRE_PIN = f"{OPENROUTER_PIN}@preset/effort-high"


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
exit 0
""",
        encoding="utf-8",
    )
    preset_helper.chmod(0o755)
