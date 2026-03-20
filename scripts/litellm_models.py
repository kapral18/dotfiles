#!/usr/bin/env python3
"""Parse litellm_models.yaml without external dependencies.

Only handles the specific list-of-dicts structure used by this project.
"""

import re

from yaml_parser import parse_scalar


def load(path):
    return _load_section(path, "litellm_models")


def _load_section(path, section_key):
    """Load a list-of-dicts section with up to one level of nested dicts."""
    with open(path, "r") as f:
        lines = f.readlines()

    items = []
    current = None
    in_section = False
    nested = None
    nested_indent = None

    for line in lines:
        stripped = line.rstrip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith(f"{section_key}:"):
            in_section = True
            current = None
            nested = None
            nested_indent = None
            continue

        if not in_section:
            continue

        # Stop once we hit a new top-level key
        if stripped and not stripped.startswith(" ") and not stripped.startswith("-"):
            break

        indent = len(line) - len(line.lstrip(" "))

        m = re.match(r"^\s+-\s+(\w+):\s*(.*)", stripped)
        if m:
            current = {m.group(1): parse_scalar(m.group(2))}
            items.append(current)
            nested = None
            nested_indent = None
            continue

        m = re.match(r"^\s+(\w+):\s*(.*)", stripped)
        if not (m and current is not None):
            continue

        key = m.group(1)
        raw = m.group(2)

        if raw == "":
            nested = {}
            current[key] = nested
            nested_indent = indent + 2
            continue

        if nested is not None and nested_indent is not None and indent >= nested_indent:
            nested[key] = parse_scalar(raw)
            continue

        current[key] = parse_scalar(raw)

    return items
