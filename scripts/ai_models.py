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
    "cursor_task_base_models": "harness-catalogs.yaml",
    "pi_extra_models": "harness-catalogs.yaml",
    "provider_models": "provider-routes.yaml",
    "session_models": "tiering.yaml",
    "agent_categories": "tiering.yaml",
    "agent_bindings": "tiering.yaml",
    "category_models": "tiering.yaml",
    "binding_fallbacks": "tiering.yaml",
    "pi_model_profiles": "tiering.yaml",
}

REVIEW_BAND_HARNESSES = {"claude": "claude_code"}

#: Reserved profile name: the ``session_models.pi`` / ``category_models.pi`` rows themselves.
DEFAULT_PI_PROFILE = "default"


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


def load_cursor_task_base_models(registry):
    return _load_section(registry, "cursor_task_base_models", required=True)


def load_pi_extra_models(registry):
    return _load_section(registry, "pi_extra_models")


def load_provider_models(registry):
    return _load_section(registry, "provider_models")


def load_session_models(registry):
    """Load the harness -> root session pick mapping from ``session_models``.

    The session row is the model the user talks to. It is never a delegation target.
    """
    return _load_block_map(registry, "session_models")


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


def load_pi_model_profiles(registry):
    """Load the alternate whole Pi pricings from ``pi_model_profiles``.

    Each profile carries a full ``session`` row plus a full ``categories`` map, so a profile is
    never a sparse overlay on the default rows. ``default`` is reserved for those default rows
    and must not appear as a key.
    """
    profiles = _load_block_map(registry, "pi_model_profiles")
    if DEFAULT_PI_PROFILE in profiles:
        raise ValueError(f"pi_model_profiles must not define the reserved {DEFAULT_PI_PROFILE!r} name")
    return profiles


def resolve_pi_profile(registry, name=DEFAULT_PI_PROFILE):
    """Resolve one Pi profile name to its ``{"session": ..., "categories": ...}`` rows.

    ``default`` reads ``session_models.pi`` / ``category_models.pi`` directly; any other name must
    exist in ``pi_model_profiles``. An unknown name raises rather than falling back, because a
    silent fallback would quietly restore rows whose provider the profile exists to avoid.
    """
    if name == DEFAULT_PI_PROFILE:
        return {
            "session": load_session_models(registry)["pi"],
            "categories": load_category_models(registry)["pi"],
        }
    profiles = load_pi_model_profiles(registry)
    if name not in profiles:
        valid = ", ".join([DEFAULT_PI_PROFILE, *sorted(profiles)])
        raise ValueError(f"unknown pi model profile {name!r} (valid: {valid})")
    profile = profiles[name]
    return {"session": profile["session"], "categories": profile["categories"]}


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


def _category_models_for(registry, profile):
    """Category rows for one profile: the registry's own, or a named Pi profile's replacements."""
    category_models = load_category_models(registry)
    if profile == DEFAULT_PI_PROFILE:
        return category_models
    return dict(category_models, pi=resolve_pi_profile(registry, profile)["categories"])


def resolve_agent_model(registry, harness, agent, profile=DEFAULT_PI_PROFILE):
    """Resolve the model pick a harness should run ``agent`` on, or ``None`` if unbound.

    Returns the model pick plus the resolved ``category``/``family`` metadata.
    A counter-family category reports whether the verifier is cross-family, reduced
    independence, or degraded so callers do not treat same-family refutation as fully independent.
    ``profile`` names a ``pi_model_profiles`` entry and only substitutes the ``pi`` rows; every
    generator resolves ``default``, and only tests and the picker ask for another name.
    """
    categories = load_agent_categories(registry)
    bindings = load_agent_bindings(registry)
    category_models = _category_models_for(registry, profile)

    category = bindings.get(agent)
    if category is None:
        return None
    if category not in categories:
        raise ValueError(f"agent {agent!r} binds to unknown category {category!r}")
    if harness not in category_models or category not in category_models[harness]:
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


def resolve_review_agent_model(registry, harness, agent, slot=None, profile=DEFAULT_PI_PROFILE):
    """Resolve the review profile model for ``agent`` on ``harness``.

    Review roles use ``agent_bindings`` / ``agent_categories`` to choose their direct category
    pick, exactly like every other delegable agent; the ``slot`` (``verifier`` for counter-family
    categories, ``lanes`` otherwise) is reported so callers can tell a refute pick from a lane pick.
    ``harness`` accepts the review alias ``claude`` for the ``claude_code`` category key.
    ``profile`` behaves as in ``resolve_agent_model``: it only substitutes the ``pi`` rows.
    """
    categories = load_agent_categories(registry)
    bindings = load_agent_bindings(registry)

    category = bindings.get(agent)
    if category is None or category not in categories:
        return None

    spec = categories[category]
    if slot is None:
        slot = "verifier" if spec["family"] == "counter" else "lanes"
    band_harness = REVIEW_BAND_HARNESSES.get(harness, harness)

    category_models = _category_models_for(registry, profile)
    row = category_models.get(band_harness, {}).get(category)
    if row is None:
        return None
    pick = dict(row)
    row_verifier_status = pick.pop("verifier_status", None)

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
