#!/usr/bin/env python3

from __future__ import annotations

import re
import subprocess
import sys
from urllib.parse import urlsplit


def github_repository(url: str) -> str | None:
    if "://" in url:
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "http", "ssh", "git"} or parsed.hostname != "github.com":
            return None
        path = parsed.path.lstrip("/")
    else:
        match = re.fullmatch(r"(?:[^/@]+@)?github\.com:(.+)", url, re.IGNORECASE)
        if not match:
            return None
        path = match.group(1)
    path = path.rstrip("/").removesuffix(".git")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", path):
        return path.casefold()
    return None


def main() -> int:
    root, requested = sys.argv[1:]
    for remote in ("upstream", "origin"):
        result = subprocess.run(["git", "-C", root, "remote", "get-url", remote], capture_output=True, text=True)
        if result.returncode:
            continue
        for url in result.stdout.splitlines():
            try:
                if github_repository(url) == requested.casefold():
                    return 0
            except ValueError:
                continue
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
