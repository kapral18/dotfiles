#!/usr/bin/env python3
"""Run Codex with local llama.cpp model metadata injected when needed.

MCP auth needs no launch-time work: hosted OAuth servers (slack, scsi-main)
run as ",mcp-token <server> --bridge" stdio bridges declared in the
chezmoi-rendered ~/.codex/config.toml, injecting a fresh bearer per request.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REAL_CODEX = "/opt/homebrew/bin/codex"
LOCAL_MODELS = {"local", "local-max"}


def _uses_llama_cpp_model(argv: list[str]) -> bool:
    previous = ""
    for arg in argv:
        if previous in {"-m", "--model"} and arg in LOCAL_MODELS:
            return True
        if arg.startswith("--model=") and arg.split("=", 1)[1] in LOCAL_MODELS:
            return True
        previous = arg
    return False


def main(argv: list[str]) -> int:
    real_codex = os.environ.get("CODEX_REAL_BIN", REAL_CODEX)
    if not os.access(real_codex, os.X_OK):
        print(f"Error: real Codex binary not found at {real_codex}.", file=sys.stderr)
        return 127

    exec_args = [real_codex]
    catalog = os.environ.get(
        "CODEX_LLAMA_CPP_MODEL_CATALOG",
        str(Path.home() / ".codex/llama-cpp-model-catalog.json"),
    )
    if _uses_llama_cpp_model(argv) and Path(catalog).is_file():
        exec_args.extend(["-c", f'model_catalog_json="{catalog}"'])
    exec_args.extend(argv)
    os.execv(real_codex, exec_args)
    return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
