#!/usr/bin/env python3
"""Pi runtime install-consistency probe for `,doctor`.

`pi` is a pnpm shim whose `cmd-shim-target` line names one pnpm global store
directory (`~/.local/share/pnpm/global/v11/<hash>/...`). A global upgrade or
prune can remove that directory while the shim (and any Pi process launched
from it) still names it. pi-subagents resolves the host package from the running
process's entry path, so every background child then fails before
initialization with "Background children require the host npm package ... does
not provide ...". This probe reports that state, plus a host root that exists
but no longer carries the peers pi-subagents aliases.

Usage: pi_runtime.py [--shim PATH]
Prints one JSON object: {"status": "pass"|"warn"|"skip", "detail": str, "hint": str}.
Standard library only; never raises for a missing install (reports "skip").
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HOST_PACKAGE = "@earendil-works/pi-coding-agent"
# Mirrors HOST_PEER_ALIASES + CHORD_PEER_ALIASES in pi-subagents
# src/runs/background/runner-aliases.ts (package names only; subpaths are the runner's concern).
HOST_PEERS = (
    "@earendil-works/pi-coding-agent",
    "@earendil-works/pi-agent-core",
    "@earendil-works/pi-tui",
    "@earendil-works/pi-ai",
    "typebox",
    "@earendil-works/chord",
)
SHIM_TARGET_RE = re.compile(r"^#\s*cmd-shim-target=(?P<path>\S+)")
REINSTALL_HINT = "pnpm add -g @earendil-works/pi-coding-agent; restart running Pi sessions"


def shim_target(shim: Path) -> Path | None:
    try:
        for line in shim.read_text(encoding="utf-8", errors="replace").splitlines():
            match = SHIM_TARGET_RE.match(line)
            if match:
                return Path(match.group("path"))
    except OSError:
        return None
    return None


def package_root(entry: Path) -> Path | None:
    """Nearest ancestor of the shim's cli.js that is the host package directory."""
    for ancestor in entry.parents:
        if ancestor.name == HOST_PACKAGE.split("/")[1] and ancestor.parent.name == HOST_PACKAGE.split("/")[0]:
            return ancestor
    return None


def find_peer(package_root_dir: Path, pkg: str) -> bool:
    """Same candidate walk and manifest-name check as pi-subagents' findPeerPackageDir."""
    candidates = [package_root_dir / "node_modules" / pkg]
    current = package_root_dir
    while True:
        parent = current.parent
        if parent == current:
            break
        if parent.name == "node_modules" or parent.parent.name == "node_modules":
            modules_root = parent if parent.name == "node_modules" else parent.parent
            candidates.append(modules_root / pkg)
        candidates.append(parent / "node_modules" / pkg)
        current = parent
    return any(manifest_name(candidate) == pkg for candidate in candidates)


def manifest_name(package_dir: Path) -> str | None:
    try:
        manifest = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    name = manifest.get("name") if isinstance(manifest, dict) else None
    return name if isinstance(name, str) else None


def probe(shim: Path | None) -> dict[str, str]:
    if shim is None or not shim.exists():
        return {"status": "skip", "detail": "pi shim not installed", "hint": ""}
    target = shim_target(shim)
    if target is None:
        return {"status": "skip", "detail": f"{shim} carries no cmd-shim-target line", "hint": ""}
    if not target.exists():
        return {
            "status": "warn",
            "detail": f"pi shim targets a removed install: {target}",
            "hint": REINSTALL_HINT,
        }
    root = package_root(target.resolve())
    if root is None:
        return {"status": "skip", "detail": f"{target} is not inside a {HOST_PACKAGE} package", "hint": ""}
    missing = [pkg for pkg in HOST_PEERS if not find_peer(root, pkg)]
    if missing:
        return {
            "status": "warn",
            "detail": f"pi host install {root} lacks subagent peers: {', '.join(missing)}",
            "hint": REINSTALL_HINT,
        }
    store = next((part for part in root.parts if re.fullmatch(r"[0-9a-f]{4}-[0-9a-f]+-\d+|[0-9a-f]{64}", part)), None)
    label = f"pnpm store {store[:12]}" if store else str(root)
    return {"status": "pass", "detail": f"pi shim install ({label}) carries every subagent host peer", "hint": ""}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shim", type=Path, default=None, help="pi shim path (default: `command -v pi`)")
    args = parser.parse_args(argv)
    shim = args.shim
    if shim is None:
        found = shutil.which("pi")
        shim = Path(found) if found else None
    print(json.dumps(probe(shim)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
