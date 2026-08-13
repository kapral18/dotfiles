#!/usr/bin/env python3
"""Sync GGUF models declared in the llama.cpp model manifest.

Usage:
    sync_llama_cpp_models.py <models_root>

Reads the rendered manifest from stdin (one `<hf-repo>|<hf-file>` or
`<hf-repo>|<hf-file>|<dest-basename>` entry per line, `#` comments and blank
lines ignored) and downloads missing GGUF files with `hf download`.

The optional third field is the basename written under models_root. Use it when
two Hugging Face files share a name (for example `mmproj-F16.gguf`). When dest
differs from hf-file, the download lands in a temp directory and is renamed so
the Hugging Face name never overwrites a sibling in models_root.

Exit code is non-zero if any download failed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def parse_manifest(stream) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for raw in stream:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 2:
            hf_repo, hf_file = parts
            dest = hf_file
        elif len(parts) == 3:
            hf_repo, hf_file, dest = parts
        else:
            print(f"warning: skipping malformed manifest line: {line!r}", file=sys.stderr)
            continue
        if not hf_repo or not hf_file or not dest or Path(dest).name != dest:
            print(f"warning: skipping malformed manifest line: {line!r}", file=sys.stderr)
            continue
        entries.append((hf_repo, hf_file, dest))
    return entries


def is_model_complete(target: Path) -> bool:
    return target.is_file() and target.suffix == ".gguf" and target.stat().st_size > 0


def download_one(hf_repo: str, hf_file: str, dest: str, models_root: Path) -> int:
    models_root.mkdir(parents=True, exist_ok=True)
    dest_path = models_root / dest
    staged_root: Path | None = None
    local_dir = models_root
    if dest != hf_file:
        staged_root = models_root / ".hf-download" / dest
        if staged_root.exists():
            shutil.rmtree(staged_root)
        staged_root.mkdir(parents=True, exist_ok=True)
        local_dir = staged_root
    print(f"==> hf download {hf_repo} {hf_file} -> {local_dir}", flush=True)
    cmd = [
        "hf",
        "download",
        hf_repo,
        hf_file,
        "--local-dir",
        str(local_dir),
    ]
    try:
        try:
            result = subprocess.run(cmd, check=False)
        except FileNotFoundError:
            print("error: `hf` CLI not found on PATH", file=sys.stderr)
            return 127
        if result.returncode != 0:
            return result.returncode
        if dest != hf_file:
            src = local_dir / hf_file
            if not src.is_file():
                print(
                    f"error: hf download did not produce {src}",
                    file=sys.stderr,
                )
                return 1
            src.replace(dest_path)
        return 0
    finally:
        if staged_root is not None:
            shutil.rmtree(staged_root, ignore_errors=True)
            parent = models_root / ".hf-download"
            try:
                parent.rmdir()
            except OSError:
                pass


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: sync_llama_cpp_models.py <models_root>", file=sys.stderr)
        return 2

    models_root = Path(sys.argv[1]).expanduser()
    entries = parse_manifest(sys.stdin)

    if not entries:
        print("No llama.cpp models declared in manifest; nothing to do.")
        return 0

    pending: list[tuple[str, str, str]] = []
    for hf_repo, hf_file, dest in entries:
        target = models_root / dest
        if is_model_complete(target):
            print(f"== {hf_repo}/{hf_file}: already present at {target}")
            continue
        pending.append((hf_repo, hf_file, dest))

    if not pending:
        print("All llama.cpp models already present; nothing to download.")
        return 0

    if shutil.which("hf") is None:
        print("error: `hf` CLI not found on PATH (brew install hf)", file=sys.stderr)
        return 127

    failures = 0
    for hf_repo, hf_file, dest in pending:
        return_code = download_one(hf_repo, hf_file, dest, models_root)
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
