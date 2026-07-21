#!/usr/bin/env python3
"""Parse ai_models.yaml without external dependencies.

Only handles the specific list-of-dicts structure used by this project.
"""

import re

from yaml_parser import parse_scalar


def load_litellm(path):
    return _load_section(path, "litellm_models")


def load_azure(path):
    return _load_section(path, "azure_models")


def load_cursor_models(path):
    return _load_section(path, "cursor_models", required=True)


def load_pi_extra_models(path):
    return _load_section(path, "pi_extra_models")


def load_provider_models(path):
    return _load_section(path, "provider_models")


def load_copilot_models(path):
    return _load_section(path, "copilot_models")


def load_agent_review_models(path):
    """Load the harness -> lane/verifier mapping from ``agent_review_models``."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    result = {}
    in_section = False
    current_harness = None
    for line in lines:
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if stripped == "agent_review_models:":
            in_section = True
            continue
        if not in_section:
            continue
        if not line.startswith(" "):
            break

        harness_match = re.match(r"^  ([\w-]+):\s*$", stripped)
        if harness_match:
            current_harness = harness_match.group(1)
            result[current_harness] = {}
            continue

        value_match = re.match(r"^    (\w+):\s*(.*?)(?:\s+#.*)?$", stripped)
        if value_match and current_harness is not None:
            result[current_harness][value_match.group(1)] = parse_scalar(value_match.group(2))

    return result


def _load_section(path, section_key, *, required=False):
    """Load a list-of-dicts section with up to one level of nested dicts."""
    with open(path, "r") as f:
        lines = f.readlines()

    items = []
    current = None
    found_section = False
    in_section = False
    nested = None
    nested_indent = None

    for line in lines:
        stripped = line.rstrip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith(f"{section_key}:"):
            found_section = True
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

    if required and not found_section:
        raise ValueError(f"missing required {section_key} section")
    if required and not items:
        raise ValueError(f"{section_key} must contain at least one recognized model entry")
    return items
