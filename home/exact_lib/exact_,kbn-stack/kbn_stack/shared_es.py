"""Version-keyed shared Elasticsearch instances: claim, attach, reconfirm, reclaim, release.

Default snapshot starts share one Elasticsearch per resolved ES version:
``<pm> es snapshot`` downloads the version pinned by the worktree's
``package.json`` ``version`` field, so worktrees with the same version are
served by one background ES JVM instead of one JVM each (each extra isolated
ES costs ~1g heap and chokes the laptop when several stacks run in parallel).
Shared instances live under the reserved ``__es__`` registry key, use the data
dir ``~/work/kibana/es_data/shared-<version>``, and are refcounted: ``--stop``
kills only the worktree's Kibana and stops the shared ES only when no other
registered worktree still references it. Sharing is skipped (isolated ES, the
historical behavior) when the invocation carries any ES-level override --
``-E``, ``--data``, a non-default ``--es-heap`` -- or the explicit
``--isolated-es`` flag (see ``cli.share_eligible``). Kibana-side flags (``-K``,
``--groups``) do not affect sharing. Same-version Kibanas on one ES share the
``.kibana*`` saved-object indices (normal HA topology); if a branch's
saved-object model drifted and migrations clash, rerun that worktree with
``--isolated-es``. Isolated snapshot stacks stay fully parallel (one per
worktree, isolated by slot).

A shared ES with no live Kibana client is stopped after ``SHARED_ES_IDLE_TIMEOUT``
by its reaper watchdog (``run_reap_shared_es``), started with the instance and
re-armed on every attach; registry settles are the fallback.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from kbn_stack import checkout, config, es_log, liveness, procs, slots, store


def usable_es_instance(registry: dict, version: str) -> dict | None:
    """The registered shared ES for ``version`` when it is ready or still starting.

    An entry missing the endpoint/data fields the attach path dereferences
    (hand-edited or truncated registry) is unusable; it is left to go stale
    and be reclaimed rather than crash the attacher.
    """
    instance = store.es_instances(registry).get(version)
    if not isinstance(instance, dict):
        return None
    ints = [instance.get(key) for key in ("slot", "es_http", "es_transport")]
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in ints):
        return None
    if not all(isinstance(instance.get(key), str) and instance.get(key) for key in ("es_url", "data", "log")):
        return None
    if liveness.es_instance_state(instance) == "stale":
        return None
    return instance


def claim_shared_es(registry: dict, version: str, worktree: str, started_by: str, exclude_slot: int) -> dict:
    """Attach to the live shared ES for ``version`` or claim a new instance.

    A new claim allocates its own slot (only the ES port pair of that slot is
    used), truncates the instance log immediately so a parallel attacher never
    reads a stale setup trigger from a previous boot, and records
    ``starting_pid`` so other launchers can tell a booting instance from a dead
    one. Returns ``{"key", "create", "instance"}``.
    """
    instance = usable_es_instance(registry, version)
    if instance is not None:
        instance.pop("unattached_since", None)
        return {"key": version, "create": False, "instance": instance}
    existing = store.es_instances(registry).get(version)
    if isinstance(existing, dict) and liveness.es_instance_state(existing) != "stale":
        attached = store.attached_worktrees(registry, version)
        if attached:
            config.fail(
                f"the registry entry for shared ES {version} is unusable (corrupt or incomplete) "
                f"but still referenced by: {', '.join(sorted(attached))}. Run `,kbn-stack --stop` "
                "in those worktrees or repair the registry, or rerun with --isolated-es."
            )
        # Replacing a live-but-unusable entry must not orphan its JVM.
        stop_es_instance(version, existing)
    es_slot = slots.allocate_es_slot(registry, {exclude_slot})
    icfg = slots.derive(es_slot)
    logfile = config.shared_es_log(checkout.sanitize(version))
    logfile.write_text("", encoding="utf-8")
    instance = {
        "version": version,
        "slot": es_slot,
        "es_url": icfg["es_url"],
        "es_http": icfg["es_http"],
        "es_transport": icfg["es_transport"],
        "data": checkout.sanitize(f"{config.SHARED_DATA_PREFIX}{version}"),
        "log": str(logfile),
        "started_by": started_by,
        "starting_pid": os.getpid(),
        "created_from": worktree,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    instances = registry.get(config.ES_INSTANCES_KEY)
    if not isinstance(instances, dict):
        # A corrupt/hand-edited container must not crash the claim; replace it.
        instances = {}
        registry[config.ES_INSTANCES_KEY] = instances
    instances[version] = instance
    return {"key": version, "create": True, "instance": instance}


def apply_shared_es(cfg: dict, instance: dict) -> None:
    """Point a worktree's slot config at the shared ES instance's endpoints."""
    cfg["es_url"] = instance["es_url"]
    cfg["es_http"] = instance["es_http"]
    cfg["es_transport"] = instance["es_transport"]
    cfg["es_slot"] = instance["slot"]


def reconfirm_shared_claim(version: str, worktree: str, started_by: str, exclude_slot: int) -> tuple[dict, dict]:
    """Re-read the registry after the long bootstrap and settle the create race.

    ``<pm> kbn bootstrap`` takes minutes, so a parallel launcher may have
    overwritten this launcher's instance claim for the same version. Whoever
    the current registry names (live ``starting_pid``/``es_pid`` or bound port)
    creates; everyone else attaches. Returns ``(registry, shared)``.
    """
    registry = store.load_registry()
    instance = store.es_instances(registry).get(version)
    if isinstance(instance, dict) and instance.get("starting_pid") == os.getpid():
        return registry, {"key": version, "create": True, "instance": instance}
    usable = usable_es_instance(registry, version)
    if usable is not None:
        print(
            f",kbn-stack: another launcher started shared ES {version} during bootstrap; attaching to it.",
            flush=True,
        )
        usable.pop("unattached_since", None)
        return registry, {"key": version, "create": False, "instance": usable}
    return registry, claim_shared_es(registry, version, worktree, started_by, exclude_slot)


def reclaim_dead_es_instances(registry: dict) -> bool:
    """Drop shared ES entries whose process and port are both gone.

    A live shared ES with zero attached worktrees is left alone here: the idle
    reaper (``settle_idle_es_instances``) stops it after the grace period, and
    until then it is what the next compatible start reuses. Returns True on change.
    """
    changed = False
    instances = store.es_instances(registry)
    for version, instance in list(instances.items()):
        if liveness.es_instance_state(instance) != "stale":
            continue
        print(
            f",kbn-stack: reclaiming shared ES {version} (slot {instance.get('slot')}): no live process or port listener.",
            flush=True,
        )
        del instances[version]
        changed = True
    if changed:
        store.save_registry(registry)
    return changed


def settle_idle_es_instances(
    registry: dict, *, keep: str | None = None, only: str | None = None, now: float | None = None
) -> bool:
    """Stop shared ES instances without a live Kibana client for ``SHARED_ES_IDLE_TIMEOUT``.

    An instance whose attached worktrees have no Kibana listening and no start
    in progress (``liveness.shared_es_clients``) is stamped ``unattached_since``;
    an observation past the grace stops it and drops the entry. A client
    appearing clears the stamp. The instance's reaper watchdog
    (``run_reap_shared_es``) observes every few seconds, so the ES dies about a
    minute after its last Kibana; starts, ``--prune``, and interactive-exit
    pruning settle too, as a fallback when no reaper is alive. ``keep`` names a
    version the caller is about to attach to; ``only`` restricts the pass to one
    version. Returns True on change; the caller saves.
    """
    now = time.time() if now is None else now
    changed = False
    instances = store.es_instances(registry)
    for version, instance in list(instances.items()):
        if only is not None and version != only:
            continue
        if version == keep or liveness.shared_es_clients(registry, version):
            if instance.pop("unattached_since", None) is not None:
                changed = True
            continue
        if liveness.es_instance_state(instance) == "stale":
            continue
        since = instance.get("unattached_since")
        if not isinstance(since, (int, float)) or isinstance(since, bool):
            instance["unattached_since"] = int(now)
            changed = True
            continue
        if now - since < config.SHARED_ES_IDLE_TIMEOUT:
            continue
        print(
            f",kbn-stack: shared ES {version} has had no Kibana client for {int(now - since)}s; "
            "stopping it to free its heap (a compatible start creates a fresh one).",
            flush=True,
        )
        stop_es_instance(version, instance)
        del instances[version]
        changed = True
    return changed


def clear_previous_stack_for_shared_es(registry: dict, worktree: str) -> None:
    """Settle this worktree's previous non-shared stack before a shared attach.

    A share-eligible start skips the slot's ES-port preflight (``check_es=False``)
    and overwrites the entry with a shared-ES one whose ``--stop`` never touches
    those ports or containers, so anything still running there would leak
    untracked forever. Two cases:

    - any recorded process alive, a live Kibana, or a live ES on a serverless
      entry means the previous stack is still owned (possibly mid-restart) ->
      fail fast and name it instead of killing or silently orphaning it;
    - a dead pair whose isolated ES half survived is an orphan -> kill it
      (tandem semantics, as in ``reclaim_dead_slots``).
    """
    entry = registry.get(worktree)
    if not isinstance(entry, dict) or entry.get("es_key") is not None:
        return
    if not isinstance(entry.get("slot"), int):
        return
    kbn_alive, es_alive = liveness.slot_liveness(entry)
    owned = kbn_alive or liveness.entry_has_live_processes(entry)
    if entry.get("backend") == "serverless":
        # slot_liveness sees only slot 0's HTTP port; a half-dead serverless
        # stack may keep es02 alive on the rest of the band.
        if owned or liveness.serverless_band_alive(registry):
            config.fail(
                "this worktree's previous serverless stack is still running; stop it first with `,kbn-stack --stop`."
            )
        return
    if owned:
        # Owned outranks port liveness: a bootstrapping stack (launcher alive,
        # nothing bound yet) must not be overwritten and orphaned.
        # No --isolated-es hint: an isolated rerun reuses this worktree's slot
        # and would fail the ES-port preflight against this same stack.
        config.fail(
            f"this worktree's previous isolated stack still holds slot {entry['slot']}; "
            "stop it first with `,kbn-stack --stop`."
        )
    if not es_alive:
        return
    print(
        f",kbn-stack: stopping this worktree's previous isolated ES (slot {entry['slot']}) "
        "before switching to the shared ES.",
        flush=True,
    )
    es_pid = entry.get("es_pid")
    if isinstance(es_pid, int):
        procs.kill_pid_group(es_pid)
    _, es_http = slots.entry_ports(entry)
    procs.kill_port_listeners(es_http)


def stop_es_instance(version: str, instance: dict) -> None:
    """Kill a shared ES instance's process group, port listeners, and reaper watchdog."""
    print(f",kbn-stack: stopping shared ES {version} (slot {instance.get('slot')})", flush=True)
    es_pid = instance.get("es_pid")
    if isinstance(es_pid, int):
        procs.kill_pid_group(es_pid)
    es_http = instance.get("es_http")
    if isinstance(es_http, int):
        procs.kill_port_listeners(es_http)
    reaper_pid = instance.get("reaper_pid")
    # The reaper stopping its own instance must survive to save the registry; it exits on its own.
    if isinstance(reaper_pid, int) and reaper_pid != os.getpid():
        procs.kill_pid_group(reaper_pid)


def ensure_reaper(version: str, instance: dict) -> bool:
    """Start the idle-reaper watchdog for ``instance`` unless one is alive; True when spawned.

    The watchdog is a detached ``,kbn-stack --reap-shared-es <version>`` that
    stops the ES once it has had no Kibana client for the grace period. Its pid
    is recorded on the instance (the caller saves the registry).
    """
    if procs.pid_alive(instance.get("reaper_pid")):
        return False
    log = config.shared_es_reaper_log(checkout.sanitize(version))
    with log.open("a", encoding="utf-8") as handle:
        proc = subprocess.Popen(
            [sys.executable, str(config.ENTRYPOINT), "--reap-shared-es", version],
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    instance["reaper_pid"] = proc.pid
    return True


def run_reap_shared_es(version: str, *, sleep: Callable[[float], None] = time.sleep) -> int:
    """Watchdog loop: stop shared ES ``version`` once it has no Kibana client for the grace period.

    Exits when the instance is gone from the registry, is dead, or names
    another live reaper. Each pass reloads the registry so attaches and stops
    made by other launchers are seen; only this version is settled here.
    """
    while True:
        registry = store.load_registry()
        instance = store.es_instances(registry).get(version)
        if not isinstance(instance, dict):
            return 0
        recorded = instance.get("reaper_pid")
        if isinstance(recorded, int) and recorded != os.getpid() and procs.pid_alive(recorded):
            return 0
        if liveness.es_instance_state(instance) == "stale":
            return 0
        if settle_idle_es_instances(registry, only=version):
            _persist_instance_change(registry, version)
            if version not in store.es_instances(registry):
                return 0
        sleep(config.SHARED_ES_REAPER_POLL_SECONDS)


def _persist_instance_change(settled: dict, version: str) -> None:
    """Write only this instance's settle result onto a fresh registry snapshot.

    The settle's liveness probes take seconds, and a launcher may have saved a
    new worktree entry meanwhile; saving the stale snapshot would drop it. The
    reaper owns just ``unattached_since`` and the instance's removal.
    """
    fresh = store.load_registry()
    fresh_instances = store.es_instances(fresh)
    current = store.es_instances(settled).get(version)
    if current is None:
        fresh_instances.pop(version, None)
    elif version in fresh_instances:
        if "unattached_since" in current:
            fresh_instances[version]["unattached_since"] = current["unattached_since"]
        else:
            fresh_instances[version].pop("unattached_since", None)
    store.save_registry(fresh)


def wait_for_shared_es(shared: dict, es_logfile: Path) -> None:
    """Block until an attached shared ES is identity-verified ready.

    Every exit requires ``es_instance_state(...) == "ready"``. The setup
    trigger alone is not proof: the instance log survives an ES death, so a
    stale trigger plus a foreign listener on the recorded port must fail the
    attach instead of starting Kibana against a squatter.
    """
    if liveness.es_instance_state(shared["instance"]) == "ready":
        return
    print(f",kbn-stack: waiting for shared ES {shared['key']} to finish setup -> {es_logfile}", flush=True)
    deadline = time.monotonic() + config.ES_SETUP_TIMEOUT
    verdict = config.WAIT_EXPIRED
    while verdict == config.WAIT_EXPIRED and time.monotonic() < deadline:
        # The creating launcher owns the expired-trial recovery (rotate + respawn);
        # an attacher only keeps following the log until the trigger appears.
        verdict = es_log.wait_for_trigger(es_logfile, timeout=deadline - time.monotonic())
        if verdict == config.WAIT_EXPIRED:
            time.sleep(2)
    if verdict != config.WAIT_TRIGGER:
        config.fail(
            f"shared ES {shared['key']} did not become ready within {int(config.ES_SETUP_TIMEOUT)}s (see {es_logfile}). "
            "Rerun once it is up, or rerun with --isolated-es for a dedicated ES."
        )
    deadline = time.monotonic() + config.SHARED_ES_CONFIRM_TIMEOUT
    while time.monotonic() < deadline:
        instance = store.es_instances(store.load_registry()).get(shared["key"])
        if (
            isinstance(instance, dict)
            # The caller's cfg is wired to the claimed instance's endpoints; a
            # replacement on another slot being ready proves nothing for it.
            and instance.get("slot") == shared["instance"].get("slot")
            and liveness.es_instance_state(instance) == "ready"
        ):
            return
        time.sleep(1)
    config.fail(
        f"shared ES {shared['key']} logged setup completion but the claimed instance is not "
        "identity-verified on its port (stale trigger, foreign listener, or the instance was "
        "replaced mid-setup). Run `,kbn-stack --prune`, then rerun, or rerun with --isolated-es "
        "for a dedicated ES."
    )


def release_shared_es(registry: dict, es_key: str | None) -> None:
    """Refcounted shared-ES teardown after a worktree entry was removed.

    The shared ES keeps running while any other registered worktree references
    it; the last detach stops it (an unreferenced ES would silently keep a JVM
    alive, which is exactly the waste sharing exists to avoid).
    """
    if es_key is None:
        return
    instance = store.es_instances(registry).get(es_key)
    if instance is None:
        return
    remaining = store.attached_worktrees(registry, es_key)
    if remaining:
        print(
            f",kbn-stack: left shared ES {es_key} running ({len(remaining)} other stack(s) attached).",
            flush=True,
        )
        return
    stop_es_instance(es_key, instance)
    del store.es_instances(registry)[es_key]
