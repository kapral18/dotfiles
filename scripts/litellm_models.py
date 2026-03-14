#!/usr/bin/env python3
"""Parse litellm_models.yaml without external dependencies.

Only handles the specific flat-list-of-dicts structure used by this project.
"""

import re


def load(path):
    with open(path, "r") as f:
        lines = f.readlines()

    models = []
    current = None

    for line in lines:
        stripped = line.rstrip()
        if not stripped or stripped.startswith("litellm_models:"):
            continue

        m = re.match(r"^\s+-\s+(\w+):\s*(.*)", stripped)
        if m:
            current = {m.group(1): _parse_value(m.group(2))}
            models.append(current)
            continue

        m = re.match(r"^\s+(\w+):\s*(.*)", stripped)
        if m and current is not None:
            current[m.group(1)] = _parse_value(m.group(2))

    return models


def _parse_value(raw):
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw
