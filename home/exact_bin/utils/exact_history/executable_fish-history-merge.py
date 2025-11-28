#!/usr/bin/env python3
"""
Fish history merger - merges two fish history files chronologically
Usage: fish-history-merge.py <local_history> <remote_history> <output_file>
"""
from __future__ import annotations

import sys


def parse_fish_history(
    file_path: str,
) -> dict[str, dict[str, str | int | list[str]]]:
    """Parse a fish history file and return a dict of commands with metadata"""
    entries: dict[str, dict[str, str | int | list[str]]] = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split by entry markers, but keep the marker
        entry_parts = content.split("- cmd: ")

        for part in entry_parts[1:]:  # Skip first empty part
            lines = part.strip().split("\n")
            if not lines:
                continue

            # First line is the command (after "- cmd: " was removed)
            cmd = lines[0]
            current_entry: dict[str, str | int | list[str]] = {"cmd": cmd}

            i = 1
            while i < len(lines):
                line = lines[i]
                if line.startswith("  when: "):
                    current_entry["when"] = int(line[8:])
                elif line.startswith("  paths:"):
                    current_entry["paths"] = []
                    i += 1
                    # Collect all path entries
                    while i < len(lines) and lines[i].startswith("    - "):
                        current_entry["paths"].append(lines[i][6:])  # Remove "    - "
                        i += 1
                    continue  # Don't increment i again
                i += 1

            # Store entry, keeping most recent for duplicate commands
            if "cmd" in current_entry:
                cmd_str = str(current_entry["cmd"])
                when_value = current_entry.get("when", 0)
                timestamp = int(when_value) if isinstance(when_value, (int, str)) else 0

                if cmd_str not in entries:
                    entries[cmd_str] = current_entry
                else:
                    existing_when = entries[cmd_str].get("when", 0)
                    existing_timestamp = (
                        int(existing_when)
                        if isinstance(existing_when, (int, str))
                        else 0
                    )
                    if timestamp > existing_timestamp:
                        entries[cmd_str] = current_entry

    except Exception as e:
        print(f"Error parsing {file_path}: {e}", file=sys.stderr)
        return {}

    return entries


def merge_histories(local_file: str, remote_file: str, output_file: str) -> bool:
    """Merge two fish history files chronologically"""
    # Parse both files
    local_entries = parse_fish_history(local_file)
    remote_entries = parse_fish_history(remote_file)

    # Merge keeping the most recent version of each command
    all_entries = dict(local_entries)  # Start with local entries

    # Add remote entries, but only if they're newer or don't exist locally
    for cmd, remote_entry in remote_entries.items():
        if cmd not in all_entries:
            # Command doesn't exist locally, add it
            all_entries[cmd] = remote_entry
        else:
            # Command exists in both, keep the most recent one
            local_when = all_entries[cmd].get("when", 0)
            remote_when = remote_entry.get("when", 0)

            local_timestamp = (
                int(local_when) if isinstance(local_when, (int, str)) else 0
            )
            remote_timestamp = (
                int(remote_when) if isinstance(remote_when, (int, str)) else 0
            )

            if remote_timestamp > local_timestamp:
                all_entries[cmd] = remote_entry

    # Sort by timestamp and write
    try:

        def get_timestamp(entry_dict: dict[str, str | int | list[str]]) -> int:
            when_val = entry_dict.get("when", 0)
            return int(when_val) if isinstance(when_val, (int, str)) else 0

        with open(output_file, "w", encoding="utf-8") as f:
            for _, entry in sorted(
                all_entries.items(), key=lambda x: get_timestamp(x[1])
            ):
                _ = f.write(f"- cmd: {entry['cmd']}\n")
                if "when" in entry:
                    _ = f.write(f"  when: {entry['when']}\n")
                if "paths" in entry and isinstance(entry["paths"], list):
                    _ = f.write("  paths:\n")
                    for path in entry["paths"]:
                        _ = f.write(f"    - {path}\n")
        return True
    except Exception as e:
        print(f"Error writing merged history: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Usage: fish-history-merge.py <local_history> <remote_history> <output_file>"
        )
        sys.exit(1)

    local_file, remote_file, output_file = sys.argv[1:4]

    if merge_histories(local_file, remote_file, output_file):
        sys.exit(0)
    else:
        sys.exit(1)
