#!/usr/bin/env python3
"""Read stable consumer views from the generated AI model mirror."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VALID_STATUSES = {"known", "unknown", "error"}


def _catalog_view(
    mirror: dict[str, Any],
    consumer: str,
    harness: str,
    selected_set: str,
) -> dict[str, Any]:
    try:
        catalog = mirror["harnesses"][harness][selected_set]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"model mirror has no {harness!r} {selected_set!r} catalog") from exc
    if not isinstance(catalog, dict):
        raise ValueError(f"model mirror {harness!r} {selected_set!r} catalog must be an object")

    status = catalog.get("status")
    complete = catalog.get("complete")
    models = catalog.get("models")
    reason = catalog.get("reason")
    provenance = catalog.get("provenance")
    if status not in VALID_STATUSES:
        raise ValueError(f"model mirror {harness!r} {selected_set!r} status is invalid")
    if complete is not None and not isinstance(complete, bool):
        raise ValueError(f"model mirror {harness!r} {selected_set!r} completeness is invalid")
    if not isinstance(models, list) or any(not isinstance(model, str) for model in models):
        raise ValueError(f"model mirror {harness!r} {selected_set!r} models are invalid")
    if reason is not None and not isinstance(reason, str):
        raise ValueError(f"model mirror {harness!r} {selected_set!r} reason is invalid")
    if not isinstance(provenance, list) or any(not isinstance(item, dict) for item in provenance):
        raise ValueError(f"model mirror {harness!r} {selected_set!r} provenance is invalid")
    if status == "known" and complete is None:
        raise ValueError(f"known model mirror {harness!r} {selected_set!r} catalog needs completeness")
    if status != "known" and (models or complete is not None or not reason):
        raise ValueError(f"{status} model mirror {harness!r} {selected_set!r} catalog is success-shaped")

    return {
        "complete": complete,
        "consumer": consumer,
        "harness": harness,
        "models": list(models),
        "provenance": [dict(item) for item in provenance],
        "reason": reason,
        "schema_version": mirror["schema_version"],
        "set": selected_set,
        "status": status,
    }


def consumer_view(
    mirror: dict[str, Any],
    consumer: str,
    harness: str,
    *,
    set_name: str | None = None,
) -> dict[str, Any]:
    """Return the stable consumer_view.v1 projection for one harness catalog."""
    if not isinstance(mirror, dict) or not isinstance(mirror.get("schema_version"), str):
        raise ValueError("model mirror schema_version is missing or invalid")
    harnesses = mirror.get("harnesses")
    if not isinstance(harnesses, dict) or harness not in harnesses:
        raise ValueError(f"unknown harness: {harness}")

    adapters = mirror.get("adapters")
    if not isinstance(adapters, dict):
        raise ValueError("model mirror adapters are missing or invalid")
    if consumer == "launcher":
        launcher = adapters.get("launcher")
        if not isinstance(launcher, dict) or launcher.get("output") != "consumer_view.v1":
            raise ValueError("launcher model mirror adapter is missing consumer_view.v1")
        allowed_sets = launcher.get("allowed_sets")
        if not isinstance(allowed_sets, list) or any(not isinstance(item, str) for item in allowed_sets):
            raise ValueError("launcher model mirror allowed_sets are invalid")
        selected_set = set_name or launcher.get("default_set")
        if selected_set not in allowed_sets:
            raise ValueError(f"launcher set is not supported: {selected_set}")
    else:
        try:
            selected_set = adapters[consumer]["harnesses"][harness]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"consumer {consumer!r} does not support harness {harness!r}") from exc
    if not isinstance(selected_set, str):
        raise ValueError(f"consumer {consumer!r} selected an invalid catalog")
    return _catalog_view(mirror, consumer, harness, selected_set)


def load_consumer_view(
    path: str | Path,
    consumer: str,
    harness: str,
    *,
    set_name: str | None = None,
) -> dict[str, Any]:
    """Load one model mirror and return a validated consumer view."""
    source = Path(path)
    try:
        mirror = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {source}: {exc.strerror or exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {source} at line {exc.lineno}, column {exc.colno}") from exc
    return consumer_view(mirror, consumer, harness, set_name=set_name)
