#!/usr/bin/env python3
"""Merge desired oMLX settings into an existing ~/.omlx/settings.json.

Usage: merge_omlx_settings.py <src_path> <target_path>

Deep-merges keys from <src_path> into <target_path>, preserving keys that
only exist in the target (e.g. `auth.secret_key` which oMLX generates on
first run, `server.server_aliases` which oMLX populates from the host's
network interfaces, and anything oMLX may write in future versions).

If the target file doesn't exist yet, the merge is skipped — oMLX needs to
initialize its own defaults (including the secret key) before we layer
overrides on top. Start the service once, then re-run `chezmoi apply`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def deep_merge(target: dict, desired: dict) -> dict:
    """Return a new dict with `desired` deep-merged onto `target`.

    Nested dicts merge key-by-key; scalars and lists in `desired` replace
    the corresponding value in `target`. Keys present only in `target` are
    preserved untouched.
    """
    result = dict(target)
    for key, value in desired.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = deep_merge(existing, value)
        else:
            result[key] = value
    return result


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit("Usage: merge_omlx_settings.py <src_path> <target_path>")

    src_path = Path(sys.argv[1])
    target_path = Path(sys.argv[2])

    with src_path.open("r", encoding="utf-8") as f:
        desired = json.load(f)

    if not target_path.exists():
        print(
            f"oMLX settings not initialized yet: {target_path} does not exist.\n"
            "Start the service once (brew services start jundot/omlx/omlx) to "
            "let oMLX create defaults, then re-run `chezmoi apply` to merge.",
            file=sys.stderr,
        )
        return 0

    with target_path.open("r", encoding="utf-8") as f:
        current = json.load(f)

    merged = deep_merge(current, desired)
    if merged == current:
        return 0

    with target_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
