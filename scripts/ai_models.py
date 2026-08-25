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
    "review_model_overrides": "tiering.yaml",
    "agent_categories": "tiering.yaml",
    "agent_bindings": "tiering.yaml",
    "category_models": "tiering.yaml",
}

REVIEW_BAND_HARNESSES = {"claude": "claude_code"}
REVIEW_OVERRIDE_HARNESSES = {"claude_code": "claude"}

# Agents rendered through an auxiliary override slot rather than the family-derived lanes/
# verifier slot. An absent key for the aux slot falls back to the "lanes" override, then to the
# category pick, so single-vendor harnesses degrade to the standard lane model (same chain as
# review-agent-model.partial).
REVIEW_AUX_SLOTS = {"review-worker-cross": "lanes_cross"}


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


def load_review_model_overrides(registry):
    """Load sparse harness -> lane/verifier overrides from ``review_model_overrides``."""
    return _load_block_map(registry, "review_model_overrides")


def load_category_models(registry):
    """Load the harness -> category -> model pick mapping from ``category_models``.

    Each category is priced directly per harness. The ``refute`` category can carry
    ``verifier_status`` to report cross-family, reduced-independence, or degraded verification.
    """
    return _load_block_map(registry, "category_models")


def load_agent_categories(registry):
    """Load the portable category -> metadata table from ``agent_categories``."""
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

    Returns the model pick plus the resolved ``category``/``family`` metadata.
    A counter-family category reports whether the verifier is cross-family, reduced
    independence, or degraded so callers do not treat same-family refutation as fully independent.
    """
    categories = load_agent_categories(registry)
    bindings = load_agent_bindings(registry)
    category_models = load_category_models(registry)

    category = bindings.get(agent)
    if category is None or category not in categories or harness not in category_models:
        return None
    if category not in category_models[harness]:
        return None

    spec = categories[category]
    pick = dict(category_models[harness][category])
    verifier_status = pick.pop("verifier_status", None)
    degraded = spec["family"] == "counter" and verifier_status not in ("cross_family", "reduced_independence")
    if spec["family"] == "counter":
        verifier_status = verifier_status or "degraded"
    return dict(
        pick,
        category=category,
        family=spec["family"],
        degraded=degraded,
        verifier_status=verifier_status,
    )


def resolve_review_agent_model(registry, harness, agent, slot=None):
    """Resolve the review profile model for ``agent`` on ``harness``.

    Sparse ``review_model_overrides`` entries handle harness selectors that cannot be derived
    from ``category_models`` (for example Claude ``inherit`` and Antigravity ``pro``). All other
    review roles use ``agent_bindings`` / ``agent_categories`` to choose their direct category pick.

    The slot defaults to the family-derived lanes/verifier choice, then any auxiliary slot the
    agent declares (REVIEW_AUX_SLOTS). An aux slot missing from the override falls back to the
    "lanes" override, then to the category pick — the same chain review-agent-model.partial
    renders, so single-vendor harnesss degrade instead of failing. Override picks merge the
    category row underneath so effort/context stay available to consumers.
    """
    categories = load_agent_categories(registry)
    bindings = load_agent_bindings(registry)

    category = bindings.get(agent)
    if category is None or category not in categories:
        return None

    spec = categories[category]
    if slot is None:
        slot = REVIEW_AUX_SLOTS.get(agent) or ("verifier" if spec["family"] == "counter" else "lanes")
    band_harness = REVIEW_BAND_HARNESSES.get(harness, harness)
    override_harness = REVIEW_OVERRIDE_HARNESSES.get(harness, harness)

    overrides = load_review_model_overrides(registry)
    override = overrides.get(override_harness, {})

    category_models = load_category_models(registry)
    row = category_models.get(band_harness, {}).get(category)
    base = dict(row) if row else {}
    row_verifier_status = base.pop("verifier_status", None)

    model = override.get(slot)
    if model is None and slot != "lanes" and override:
        # Aux slots degrade to the standard lane override before the category pick.
        slot = "lanes"
        model = override.get("lanes")
    if model is not None:
        verifier_status = "degraded" if slot == "verifier" else None
        return dict(
            base,
            model=model,
            category=category,
            family=spec["family"],
            slot=slot,
            source="override",
            degraded=spec["family"] == "counter",
            verifier_status=verifier_status,
            harness=harness,
            band_harness=band_harness,
        )

    if row is None:
        return None

    pick = base
    verifier_status = row_verifier_status
    degraded = slot == "verifier" and verifier_status not in ("cross_family", "reduced_independence")
    if slot == "verifier":
        verifier_status = verifier_status or "degraded"
    return dict(
        pick,
        category=category,
        family=spec["family"],
        slot=slot,
        source="category_models",
        degraded=degraded,
        verifier_status=verifier_status,
        harness=harness,
        band_harness=band_harness,
    )


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
