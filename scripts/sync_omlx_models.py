#!/usr/bin/env python3
"""Sync MLX models declared in the oMLX model manifest into ~/.omlx/models/.

Usage:
    sync_omlx_models.py <models_root>

Reads the already-rendered manifest from stdin (one `<hf-repo>|<local-dir>`
entry per line, `#` comments and blank lines ignored) and for each entry
shells out to `hf download` unless the target directory already looks
complete (has a `config.json` and at least one `*.safetensors` shard).

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
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            print(f"warning: skipping malformed manifest line: {line!r}", file=sys.stderr)
            continue
        entries.append((parts[0], parts[1]))
    return entries


def is_model_complete(target: Path) -> bool:
    """A model dir is treated as complete if it has config.json and at least
    one safetensors shard. This avoids re-downloading a tokenizer-only stub.
    """
    if not target.is_dir():
        return False
    if not (target / "config.json").is_file():
        return False
    return any(target.glob("*.safetensors"))


def download_one(hf_repo: str, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"==> hf download {hf_repo} -> {target}", flush=True)
    cmd = [
        "hf",
        "download",
        hf_repo,
        "--local-dir",
        str(target),
    ]
    try:
        result = subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print("error: `hf` CLI not found on PATH", file=sys.stderr)
        return 127
    return result.returncode


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: sync_omlx_models.py <models_root>", file=sys.stderr)
        return 2

    models_root = Path(sys.argv[1]).expanduser()
    entries = parse_manifest(sys.stdin)

    if not entries:
        print("No oMLX models declared in manifest; nothing to do.")
        return 0

    pending: list[tuple[str, Path]] = []
    for hf_repo, local_dir in entries:
        target = models_root / local_dir
        if is_model_complete(target):
            print(f"== {hf_repo}: already present at {target}")
            continue
        pending.append((hf_repo, target))

    if not pending:
        print("All oMLX models already present; nothing to download.")
        return 0

    if shutil.which("hf") is None:
        print("error: `hf` CLI not found on PATH (brew install hf)", file=sys.stderr)
        return 127

    failures = 0
    for hf_repo, target in pending:
        rc = download_one(hf_repo, target)
        if rc != 0:
            print(f"error: hf download failed for {hf_repo} (exit {rc})", file=sys.stderr)
            failures += 1

    if failures:
        print(f"Completed with {failures} failure(s).", file=sys.stderr)
        return 1

    print("All oMLX models synced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
