#!/usr/bin/env python3
"""Merge desired Claude Code settings into an existing settings.json.

Usage: merge_claude_settings.py <src_path> <target_path>

Reads the desired key/value pairs from <src_path> and merges them into
<target_path>, preserving any keys that only exist in the target (e.g.
keys written by Claude Code itself at runtime).
"""
import json
import sys


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: merge_claude_settings.py <src_path> <target_path>")

    src_path, target_path = sys.argv[1], sys.argv[2]

    with open(src_path, "r") as f:
        desired = json.load(f)

    try:
        with open(target_path, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    changed = False
    for key, value in desired.items():
        if data.get(key) != value:
            changed = True
        data[key] = value

    if not changed:
        sys.exit(0)

    with open(target_path, "w") as f:
        f.write(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
