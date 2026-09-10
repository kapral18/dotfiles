"""Slot allocation and the slot -> port/cookie/key derivation.

Each worktree gets an auto-allocated slot; the slot derives a unique Kibana port,
Elasticsearch HTTP/transport ports, security cookie name, and saved-objects
encryption key, so any number of worktrees can run in parallel on plain
http://localhost:<port> without /etc/hosts hostname aliases (Kibana session
cookies are host-scoped, not port-scoped, so two instances on the same host need
distinct cookie names). Slot 0 reproduces the historical defaults (5601, 9200/9300).
"""

from __future__ import annotations

import hashlib

from kbn_stack import config, store


def entry_ports(entry: dict) -> tuple[int | None, int | None]:
    """Resolve (kbn_port, es_http) for a registry entry, deriving from slot.

    Newer entries carry kbn_url/es_url; deriving from the slot covers older
    entries and keeps the two consistent with ``derive``.
    """
    slot = entry.get("slot")
    if isinstance(slot, int):
        cfg = derive(slot)
        return cfg["kbn_port"], cfg["es_http"]
    return None, None


def taken_slots(registry: dict, *, exclude_worktree: str | None = None) -> set[int]:
    """Slots reserved by worktree stacks and shared ES instances."""
    taken = {
        entry["slot"]
        for key, entry in store.worktree_entries(registry)
        if key != exclude_worktree and isinstance(entry.get("slot"), int)
    }
    taken |= {
        instance["slot"] for instance in store.es_instances(registry).values() if isinstance(instance.get("slot"), int)
    }
    return taken


def lowest_free_slot(taken: set[int]) -> int:
    slot = 0
    while slot in taken:
        slot += 1
    return slot


def allocate_slot(registry: dict, worktree: str, forced: int | None) -> int:
    if forced is not None:
        if forced < 0:
            config.fail("--slot must be >= 0")
        return forced
    existing = registry.get(worktree)
    if existing and isinstance(existing.get("slot"), int):
        return existing["slot"]
    return lowest_free_slot(taken_slots(registry, exclude_worktree=worktree))


def allocate_es_slot(registry: dict, extra_taken: set[int]) -> int:
    """Lowest free slot for a new shared ES instance (only its ES ports are used).

    While a serverless stack is registered its containers own the low ES port
    band, so the serverless-conflict slots are excluded up front: the instance
    preflight probes only the ES HTTP port and would miss a transport collision.
    """
    taken = taken_slots(registry) | extra_taken
    if any(entry.get("backend") == "serverless" for _, entry in store.worktree_entries(registry)):
        taken |= set(config.SERVERLESS_SNAPSHOT_CONFLICT_SLOTS)
    return lowest_free_slot(taken)


def encryption_key_for(slot: int) -> str:
    """Stable 32+ char key derived from the slot so saved objects survive restarts."""
    digest = hashlib.sha256(f"kbn-stack-slot-{slot}".encode("utf-8")).hexdigest()
    return digest[:48]


def derive(slot: int) -> dict:
    kbn_port = config.KBN_PORT_BASE + slot
    es_http = config.ES_HTTP_BASE + slot * 2
    es_transport = config.ES_TRANSPORT_BASE + slot * 2
    return {
        "kbn_port": kbn_port,
        "es_http": es_http,
        "es_transport": es_transport,
        "kbn_url": f"http://localhost:{kbn_port}",
        "es_url": f"http://localhost:{es_http}",
        "cookie_name": f"sid-{slot}",
        "encryption_key": encryption_key_for(slot),
    }
