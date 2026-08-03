#!/usr/bin/env python3
"""Parse the model registry under ``home/.chezmoidata/ai_models/`` without external dependencies.

Callers pass the registry directory, not a file: the sections are split across three files for
navigation (chezmoi merges them back into one flat data namespace) and ``SECTION_FILES`` is the
only place that knows which file owns which section. Only handles the list-of-dicts and block-map
structures this project actually writes.
"""

import re
from pathlib import Path

from yaml_parser import parse_scalar

SECTION_FILES = {
    "cursor_models": "harness-catalogs.yaml",
    "pi_extra_models": "harness-catalogs.yaml",
    "copilot_models": "harness-catalogs.yaml",
    "provider_models": "provider-routes.yaml",
    "agent_review_models": "tiering.yaml",
    "agent_categories": "tiering.yaml",
    "agent_bindings": "tiering.yaml",
    "model_bands": "tiering.yaml",
}


def section_path(registry, section_key):
    """Return the file inside ``registry`` that owns ``section_key``."""
    try:
        return Path(registry) / SECTION_FILES[section_key]
    except KeyError:
        raise ValueError(f"unknown registry section {section_key}") from None


def _section_lines(registry, section_key):
    path = section_path(registry, section_key)
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as f:
        return f.readlines()


def load_cursor_models(registry):
    return _load_section(registry, "cursor_models", required=True)


def load_pi_extra_models(registry):
    return _load_section(registry, "pi_extra_models")


def load_provider_models(registry):
    return _load_section(registry, "provider_models")


def load_copilot_models(registry):
    return _load_section(registry, "copilot_models")


def load_agent_review_models(registry):
    """Load the harness -> lane/verifier mapping from ``agent_review_models``."""
    return _load_block_map(registry, "agent_review_models")


def load_model_bands(registry):
    """Load the harness -> band -> model pick mapping from ``model_bands``.

    A ``max`` band may nest a ``counter`` map holding the cross-family refuter for that
    harness; its absence means the harness cannot field a second family.
    """
    return _load_block_map(registry, "model_bands")


def load_agent_categories(registry):
    """Load the portable category -> ``{band, family}`` table from ``agent_categories``."""
    return _load_block_map(registry, "agent_categories")


def load_agent_bindings(registry):
    """Load the agent-name -> category mapping from ``agent_bindings``."""
    return _load_block_map(registry, "agent_bindings")


_BLOCK_ENTRY_RE = re.compile(r"^([\w.@-]+):\s*(.*?)(?:\s+#.*)?$")


def _load_block_map(registry, section_key):
    """Load an arbitrarily nested block mapping under ``section_key``.

    Indentation alone defines nesting: a key with no value opens a child map, a key with a
    value is a scalar leaf. Flow maps are not accepted, so a stray one-liner surfaces as a
    parse miss here rather than as a silently half-read band.
    """
    result = {}
    stack = [(-1, result)]
    in_section = False
    for line in _section_lines(registry, section_key):
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if stripped == f"{section_key}:":
            in_section = True
            continue
        if not in_section:
            continue
        if not line.startswith(" "):
            break

        match = _BLOCK_ENTRY_RE.match(stripped.strip())
        if not match:
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        while indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        key, raw = match.group(1), match.group(2).strip()
        if raw == "":
            child = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = parse_scalar(raw)

    return result


def resolve_agent_model(registry, harness, agent):
    """Resolve the model pick a harness should run ``agent`` on, or ``None`` if unbound.

    Returns the band map plus the resolved ``category``/``band``/``family``. A ``counter``
    family falls back to the primary ``max`` pick when the harness has no counter model,
    which is the degraded-refutation case callers must report rather than silently accept.
    """
    categories = load_agent_categories(registry)
    bindings = load_agent_bindings(registry)
    bands = load_model_bands(registry)

    category = bindings.get(agent)
    if category is None or category not in categories or harness not in bands:
        return None

    spec = categories[category]
    pick = dict(bands[harness][spec["band"]])
    counter = pick.pop("counter", None)
    degraded = spec["family"] == "counter" and not counter
    if spec["family"] == "counter" and counter:
        pick = dict(counter)
    return dict(pick, category=category, band=spec["band"], family=spec["family"], degraded=degraded)


def _load_section(registry, section_key, *, required=False):
    """Load a list-of-dicts section with up to one level of nested dicts."""
    lines = _section_lines(registry, section_key)

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
