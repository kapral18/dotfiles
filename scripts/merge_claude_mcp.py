#!/usr/bin/env python3
import json
import sys


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: merge_claude_mcp.py <src_path> <target_path>")

    src_path, target_path = sys.argv[1], sys.argv[2]

    with open(src_path, "r") as f:
        desired = json.load(f).get("mcpServers", {})

    try:
        with open(target_path, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    current = data.get("mcpServers", {})
    if current == desired:
        sys.exit(0)

    data["mcpServers"] = desired
    with open(target_path, "w") as f:
        f.write(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
