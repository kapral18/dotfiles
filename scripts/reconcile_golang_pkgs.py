#!/usr/bin/env python3
"""Reconcile globally `go install`-ed tool binaries against the desired list.

Usage:
    reconcile_golang_pkgs.py <desired_file> <gobin_dir> <state_file>

- <desired_file>: rendered default-golang-pkgs list (module paths, one per
  line; `#` comments and blank lines ignored).
- <gobin_dir>: directory where `go install` drops binaries (GOBIN, or
  $(go env GOPATH)/bin).
- <state_file>: newline-delimited record of the module paths this tooling has
  installed. Created if missing.

Why a state file instead of "remove everything in GOBIN not in the list":
`go install` does not track which binaries came from this dotfiles list, and
GOBIN may legitimately contain binaries a user installed by hand. We must only
ever remove binaries we ourselves installed. The state file is that ledger.

This script does NOT install anything (the shell hook runs `go install`). It:
  1. derives the binary name for each module path,
  2. removes managed binaries whose module is no longer desired,
  3. rewrites the state file to the current desired set.

Binary name = last path segment, skipping a trailing major-version segment
(`/v2`, `/v10`, ...) and any `@version` suffix. This matches `go install`.

Prints one line per removal to stdout. Exit code is always 0 for reconcile
outcomes; only bad arguments cause a non-zero exit.
"""

from __future__ import annotations

import sys
from pathlib import Path


def binary_name(module_path: str) -> str:
    path = module_path.split("@", 1)[0].rstrip("/")
    if not path:
        return ""
    segs = path.split("/")
    last = segs[-1]
    # A trailing pure major-version segment ("v2", "v10") is not the binary
    # name; the segment before it is. Guard against a real name like "v2tool".
    if len(segs) >= 2 and len(last) >= 2 and last[0] == "v" and last[1:].isdigit():
        last = segs[-2]
    return last


def load_modules(path: Path) -> list[str]:
    if not path.exists():
        return []
    modules: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Defensive: the list format is "module" but tolerate trailing fields.
        modules.append(line.split()[0])
    return modules


def main() -> int:
    if len(sys.argv) != 4:
        sys.stderr.write("usage: reconcile_golang_pkgs.py <desired_file> <gobin_dir> <state_file>\n")
        return 2

    desired_file = Path(sys.argv[1])
    gobin_dir = Path(sys.argv[2])
    state_file = Path(sys.argv[3])

    desired = load_modules(desired_file)
    previously_managed = load_modules(state_file)

    desired_set = set(desired)
    # Modules we installed before but that are no longer wanted.
    to_remove = [m for m in previously_managed if m not in desired_set]

    for module in to_remove:
        name = binary_name(module)
        if not name:
            continue
        binary = gobin_dir / name
        # Only remove a binary whose name is not also produced by a still-desired
        # module (avoid deleting a binary another desired package owns).
        if any(binary_name(d) == name for d in desired):
            continue
        if binary.exists() or binary.is_symlink():
            try:
                binary.unlink()
                print(f"removed go binary: {name} ({module})")
            except OSError as exc:
                sys.stderr.write(f"warning: failed to remove {binary}: {exc}\n")

    # Rewrite the ledger to exactly the current desired set.
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("".join(f"{m}\n" for m in desired), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
