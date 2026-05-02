#!/usr/bin/env python3
"""Sync GGUF models declared in the llama.cpp model manifest.

Usage:
    sync_llama_cpp_models.py <models_root>

Reads the rendered manifest from stdin (one `<hf-repo>|<hf-file>` entry per
line, `#` comments and blank lines ignored) and downloads missing GGUF files
with `hf download`.

Exit code is non-zero if any download failed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def parse_manifest(stream) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for raw in stream:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            print(f"warning: skipping malformed manifest line: {line!r}", file=sys.stderr)
            continue
        entries.append((parts[0], parts[1]))
    return entries


def is_model_complete(target: Path) -> bool:
    return target.is_file() and target.suffix == ".gguf" and target.stat().st_size > 0


def download_one(hf_repo: str, hf_file: str, models_root: Path) -> int:
    models_root.mkdir(parents=True, exist_ok=True)
    print(f"==> hf download {hf_repo} {hf_file} -> {models_root}", flush=True)
    cmd = [
        "hf",
        "download",
        hf_repo,
        hf_file,
        "--local-dir",
        str(models_root),
    ]
    try:
        result = subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print("error: `hf` CLI not found on PATH", file=sys.stderr)
        return 127
    return result.returncode


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: sync_llama_cpp_models.py <models_root>", file=sys.stderr)
        return 2

    models_root = Path(sys.argv[1]).expanduser()
    entries = parse_manifest(sys.stdin)

    if not entries:
        print("No llama.cpp models declared in manifest; nothing to do.")
        return 0

    pending: list[tuple[str, str]] = []
    for hf_repo, hf_file in entries:
        target = models_root / hf_file
        if is_model_complete(target):
            print(f"== {hf_repo}/{hf_file}: already present at {target}")
            continue
        pending.append((hf_repo, hf_file))

    if not pending:
        print("All llama.cpp models already present; nothing to download.")
        return 0

    if shutil.which("hf") is None:
        print("error: `hf` CLI not found on PATH (brew install hf)", file=sys.stderr)
        return 127

    failures = 0
    for hf_repo, hf_file in pending:
        return_code = download_one(hf_repo, hf_file, models_root)
        if return_code != 0:
            print(
                f"error: hf download failed for {hf_repo}/{hf_file} (exit {return_code})",
                file=sys.stderr,
            )
            failures += 1

    if failures:
        print(f"Completed with {failures} failure(s).", file=sys.stderr)
        return 1

    print("All llama.cpp models synced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
