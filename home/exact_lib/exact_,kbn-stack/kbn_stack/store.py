"""The ~/.cache/kbn-stack/registry.json store: load/save, entry shape, reload-and-merge updates.

The resolved stack is recorded keyed by worktree path (plus the reserved
``__es__`` key for shared ES instances); the live-ui-review contract reads it to
resolve the base/head browser URLs and teardown ownership. Entries record
``started_by`` as ``agent`` for detached starts and ``user`` for interactive
starts.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from kbn_stack import cli, config


def load_registry() -> dict:
    if not config.REGISTRY_PATH.is_file():
        return {}
    try:
        data = json.loads(config.REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    instances = data.get(config.ES_INSTANCES_KEY)
    if instances is not None and not isinstance(instances, dict):
        # A hand-edited registry must not crash every shared-map consumer.
        del data[config.ES_INSTANCES_KEY]
    elif isinstance(instances, dict):
        for version in [v for v, inst in instances.items() if not isinstance(inst, dict)]:
            del instances[version]
    return data


def save_registry(registry: dict) -> None:
    config.REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.REGISTRY_PATH.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stack_started_by(entry: dict) -> str:
    """Return the stack ownership marker, inferring safe legacy defaults."""
    started_by = entry.get("started_by")
    if started_by in (config.STARTED_BY_AGENT, config.STARTED_BY_USER):
        return started_by
    if entry.get("start_mode") == "agent-detach":
        return config.STARTED_BY_AGENT
    if any(isinstance(entry.get(key), int) for key in ("kbn_pid", "es_pid")):
        return config.STARTED_BY_AGENT
    return config.STARTED_BY_USER


def worktree_entries(registry: dict) -> list[tuple[str, dict]]:
    """Registry items that are worktree stacks (everything except ``__es__``)."""
    return [(key, entry) for key, entry in registry.items() if key != config.ES_INSTANCES_KEY]


def es_instances(registry: dict) -> dict:
    """The shared ES instance map (version -> instance entry)."""
    instances = registry.get(config.ES_INSTANCES_KEY)
    return instances if isinstance(instances, dict) else {}


def attached_worktrees(registry: dict, es_key: str) -> list[str]:
    """Worktrees whose registered stack references the shared ES ``es_key``."""
    return [worktree for worktree, entry in worktree_entries(registry) if entry.get("es_key") == es_key]


def update_worktree_entry(worktree: str, **fields: object) -> None:
    """Reload the registry, merge ``fields`` into one worktree entry, and save.

    Detached starts wait minutes between registry writes, so saving the
    launcher's in-memory snapshot would overwrite entries a parallel launcher
    added meanwhile. A shared-ES attachee whose entry vanishes that way drops
    out of the refcount, and the next ``--stop`` kills the ES under its live
    Kibana. An entry that is already gone (pruned or stopped) is left gone.
    """
    registry = load_registry()
    entry = registry.get(worktree)
    if entry is None:
        return
    entry.update(fields)
    save_registry(registry)


def update_es_instance(es_key: str, **fields: object) -> None:
    """Reload the registry, merge ``fields`` into one shared ES instance, and save."""
    registry = load_registry()
    instance = es_instances(registry).get(es_key)
    if instance is None:
        return
    instance.update(fields)
    save_registry(registry)


def mark_ready(worktree: str, ready: bool) -> None:
    update_worktree_entry(worktree, ready=ready)


def build_worktree_entry(
    args: argparse.Namespace,
    cfg: dict,
    branch: str,
    data_name: str,
    logfile: Path,
    started_by: str,
    mode: str,
    es_key: str | None,
) -> dict:
    """The registry entry for one worktree stack (``es_key`` marks a shared ES)."""
    entry = {
        "slot": cfg["slot"],
        "branch": branch,
        "backend": args.es,
        "project_type": args.project_type if args.es == "serverless" else None,
        "exclusive": args.es == "serverless",
        "kbn_url": cfg["kbn_url"],
        "es_url": cfg["es_url"],
        "cookie_name": cfg["cookie_name"],
        "data": data_name,
        "kbn_flags": cli.resolved_kbn_flags(args),
        "log": str(logfile),
        "ready": False,
        "started_by": started_by,
        "start_mode": mode,
        "started_by_pid": os.getpid(),
        "started_by_ppid": os.getppid(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if es_key is not None:
        entry["es_key"] = es_key
    return entry
