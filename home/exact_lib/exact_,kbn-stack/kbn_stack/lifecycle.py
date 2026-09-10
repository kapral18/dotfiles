"""Registered-stack lifecycle commands: --status, --prune, slot reclaim, --stop, --stop-all, serverless preflight.

Serverless is single-instance per host: kbn-es runs fixed es01/es02 containers
with no per-instance name, so a serverless start pins to slot 0, auto-stops
agent-owned serverless stacks, refuses to stop user-owned serverless stacks from
agent mode, and refuses to start over a snapshot stack or shared ES holding the
conflicting low ES port band (slots 0-1).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from kbn_stack import config, liveness, procs, shared_es, slots, store


def run_status(registry: dict) -> int:
    """Print every registered stack without mutating registry state."""
    stacks = store.worktree_entries(registry)
    instances = store.es_instances(registry)
    if not stacks and not instances:
        print(",kbn-stack: no registered stacks.", flush=True)
        return 0

    rows = []

    def sort_key(item: tuple[str, dict]) -> tuple[int, str]:
        slot = item[1].get("slot")
        return (slot if isinstance(slot, int) else sys.maxsize, item[0])

    for worktree, entry in sorted(stacks, key=sort_key):
        kbn_alive, es_alive = liveness.slot_liveness(entry)
        process_alive = liveness.entry_has_live_processes(entry)
        state = liveness.entry_state(registry, entry, process_alive, kbn_alive, es_alive)
        es_key = entry.get("es_key")
        if es_key is not None:
            es_cell = f"shared:{'up' if liveness.shared_es_ready(registry, es_key) else 'down'}"
        else:
            es_cell = "up" if es_alive else "down"
        rows.append(
            (
                state,
                str(entry.get("slot", "-")),
                str(entry.get("backend", "unknown")),
                store.stack_started_by(entry),
                "up" if kbn_alive else "down",
                es_cell,
                str(entry.get("branch", "unknown")),
                worktree,
            )
        )
    for version, instance in sorted(instances.items(), key=sort_key):
        state = liveness.es_instance_state(instance)
        attached = store.attached_worktrees(registry, version)
        rows.append(
            (
                state,
                str(instance.get("slot", "-")),
                "shared-es",
                store.stack_started_by(instance),
                "-",
                "up" if state == "ready" else "down",
                f"v{version}",
                shared_attachment_cell(instance, attached),
            )
        )

    headers = ("STATE", "SLOT", "BACKEND", "OWNER", "KIBANA", "ES", "BRANCH", "WORKTREE")
    widths = [max(len(str(value)) for value in column) for column in zip(headers, *rows)]
    for row in (headers, *rows):
        print("  ".join(str(value).ljust(width) for value, width in zip(row, widths)).rstrip(), flush=True)
    return 0


def shared_attachment_cell(instance: dict, attached: list[str]) -> str:
    """``(N attached)``, plus how long the instance has had no Kibana client."""
    since = instance.get("unattached_since")
    if not isinstance(since, (int, float)) or isinstance(since, bool):
        return f"({len(attached)} attached)"
    return f"({len(attached)} attached, no client {int(max(0.0, time.time() - since))}s)"


def run_prune(registry: dict, *, ignored_pid: int | None = None, quiet: bool = False) -> int:
    """Remove only entries whose recorded processes and owned ports are all dead."""
    stale_worktrees = []
    for worktree, entry in store.worktree_entries(registry):
        kbn_alive, es_alive = liveness.slot_liveness(entry)
        process_alive = liveness.entry_has_live_processes(entry, ignored_pid=ignored_pid)
        if liveness.entry_state(registry, entry, process_alive, kbn_alive, es_alive) == "stale":
            stale_worktrees.append(worktree)

    for worktree in stale_worktrees:
        del registry[worktree]

    instances = store.es_instances(registry)
    stale_instances = [
        version for version, instance in instances.items() if liveness.es_instance_state(instance) == "stale"
    ]
    for version in stale_instances:
        del instances[version]
    idle_settled = shared_es.settle_idle_es_instances(registry)

    if stale_worktrees or stale_instances or idle_settled:
        store.save_registry(registry)

    if not quiet:
        if stale_worktrees or stale_instances:
            print(f",kbn-stack: pruned {len(stale_worktrees) + len(stale_instances)} stale stack(s):", flush=True)
            for worktree in sorted(stale_worktrees):
                print(f"  {worktree}", flush=True)
            for version in sorted(stale_instances):
                print(f"  shared ES {version}", flush=True)
        elif not idle_settled:
            print(",kbn-stack: no stale stacks.", flush=True)
    return 0


def reclaim_dead_slots(registry: dict, current_worktree: str) -> bool:
    """Free slots held by snapshot stacks whose ES+Kibana pair is not both alive.

    A worktree's slot is only genuinely occupied while *both* its Kibana and
    Elasticsearch ports are live (they run in tandem). If either half died, the
    registry entry is stale and was reserving the slot against new worktrees, so:

    - kill any surviving half (so the reused slot's ports are clean), and
    - drop the stale entry, returning its slot to the lowest-slot search.

    Port liveness alone cannot distinguish a dead stack from one still
    bootstrapping (<pm> kbn bootstrap + ES snapshot setup take minutes before
    any port binds), so entries whose launcher or recorded stack processes are
    still running are skipped: reclaiming them would hand their slot (ports,
    log file, cookie) to another worktree and couple the two stacks.

    Serverless entries are left untouched: they are exclusive/single-instance and
    governed by ``stop_existing_serverless``, not by per-slot port reclamation.
    The current worktree is never reclaimed here (its own slot is sticky).
    Returns True when the registry changed.
    """
    changed = False
    for worktree, entry in store.worktree_entries(registry):
        if worktree == current_worktree:
            continue
        if entry.get("backend") == "serverless":
            continue
        if not isinstance(entry.get("slot"), int):
            continue
        if liveness.entry_has_live_processes(entry):
            continue
        if entry.get("es_key") is not None:
            # A shared attachee owns only its Kibana half; the shared ES has its
            # own reclaim path. Drop the entry only when the Kibana is gone too.
            kbn_alive, _ = liveness.slot_liveness(entry)
            if kbn_alive:
                continue
            print(
                f",kbn-stack: reclaiming slot {entry['slot']} ({worktree}): "
                "no live Kibana on a shared-ES stack; dropping stale registry entry.",
                flush=True,
            )
            del registry[worktree]
            changed = True
            continue
        kbn_alive, es_alive = liveness.slot_liveness(entry)
        if kbn_alive and es_alive:
            continue
        kbn_port, es_http = slots.entry_ports(entry)
        if kbn_alive or es_alive:
            print(
                f",kbn-stack: reclaiming slot {entry['slot']} ({worktree}): "
                f"Kibana {'up' if kbn_alive else 'down'}, ES {'up' if es_alive else 'down'}; "
                "killing the surviving half so the slot is free.",
                flush=True,
            )
            if kbn_alive:
                procs.kill_port_listeners(kbn_port)
            if es_alive:
                procs.kill_port_listeners(es_http)
        else:
            print(
                f",kbn-stack: reclaiming slot {entry['slot']} ({worktree}): "
                "no live Kibana/ES; dropping stale registry entry.",
                flush=True,
            )
        del registry[worktree]
        changed = True
    if changed:
        store.save_registry(registry)
    return changed


def run_with_prune(command: list[str]) -> int:
    """Run a foreground command and silently prune after normal exit or Ctrl-C."""
    if not command:
        config.fail("--run-with-prune requires a command")
    worktree = os.environ.get("KBN_STACK_WORKTREE", "")
    if worktree:
        # This wrapper outlives dev-mode server restarts; recording it keeps the
        # worktree a shared-ES client while Kibana's port is briefly unbound.
        store.update_worktree_entry(worktree, kbn_pid=os.getpid())
    try:
        return subprocess.run(command, check=False).returncode
    except KeyboardInterrupt:
        return 130
    finally:
        run_prune(store.load_registry(), quiet=True)


def stop_entry(worktree: str, entry: dict, *, allow_user_owned: bool = True, reclaim_ports: bool = False) -> bool:
    """Tear down one registered stack: kill recorded Kibana then ES processes.

    Snapshot stacks run as our own children (pids recorded), so killing their
    process groups stops the pnpm|yarn/node and JVM trees. Serverless stacks run their
    Elasticsearch in Docker containers (es01/es02); ,kbn-stack treats serverless
    as single-instance, so those fixed names are removed directly.

    Interactive tmux stacks have no recorded process groups. With
    ``reclaim_ports`` set (``--stop`` and ``--stop-all``), also kill whatever
    still listens on this slot's Kibana/ES ports by signaling the listener
    process group, so a Kibana that closes the port and hangs still gets SIGKILL.
    Serverless preflight leaves reclaim off so a snapshot stack on those ports is
    not killed as a side effect.
    """
    slot = entry.get("slot")
    started_by = store.stack_started_by(entry)
    shared = entry.get("es_key") is not None
    if started_by == config.STARTED_BY_USER and not allow_user_owned:
        print(f",kbn-stack: leaving user-owned slot {slot} ({worktree}) running.", flush=True)
        return False
    print(f",kbn-stack: stopping slot {slot} ({worktree}, started_by={started_by})", flush=True)
    stopped = False
    recorded = False
    for key in ("kbn_pid", "es_pid"):
        pid = entry.get(key)
        if isinstance(pid, int):
            procs.kill_pid_group(pid)
            recorded = True
            stopped = True
    if entry.get("backend") == "serverless":
        procs.docker_kill_serverless()
        stopped = True
    if reclaim_ports and entry.get("backend") != "serverless":
        kbn_port, es_http = slots.entry_ports(entry)
        port_stopped = False
        if procs.kill_port_listeners(kbn_port):
            port_stopped = True
            stopped = True
        # A shared attachee does not own its slot's ES ports (the shared ES has
        # its own slot and teardown path), so only isolated stacks reclaim them.
        if not shared and procs.kill_port_listeners(es_http):
            port_stopped = True
            stopped = True
        if port_stopped and not recorded:
            print(
                f",kbn-stack: stopped interactive slot {slot} by killing its Kibana/ES port owners.",
                flush=True,
            )
    if not stopped:
        print(
            ",kbn-stack: no live processes or port listeners for this entry.",
            flush=True,
        )
    return stopped


def run_stop(worktree: str, registry: dict) -> int:
    entry = registry.get(worktree)
    if entry is None:
        config.fail(f"no registered stack for this worktree ({worktree})")
    stopped = stop_entry(worktree, entry, reclaim_ports=True)
    del registry[worktree]
    shared_es.release_shared_es(registry, entry.get("es_key"))
    store.save_registry(registry)
    if not stopped:
        # Nothing recorded and nothing listening on this slot's ports: the stack
        # is already gone. Drop the stale entry so the slot is freed.
        print(",kbn-stack: no live stack found; removed stale registry entry.", flush=True)
        return 0
    print(",kbn-stack: stopped and removed registry entry.", flush=True)
    return 0


def run_stop_all(registry: dict) -> int:
    stacks = store.worktree_entries(registry)
    instances = store.es_instances(registry)
    if not stacks and not instances:
        print(",kbn-stack: no registered stacks.", flush=True)
        return 0
    count = len(stacks) + len(instances)
    for worktree, entry in stacks:
        stop_entry(worktree, entry, reclaim_ports=True)
    for version, instance in list(instances.items()):
        shared_es.stop_es_instance(version, instance)
    store.save_registry({})
    print(f",kbn-stack: stopped {count} stack(s) and cleared the registry.", flush=True)
    return 0


def stop_existing_serverless(registry: dict, current_worktree: str, new_started_by: str) -> None:
    """Prepare the registry for a single-instance serverless start.

    Serverless ES is single-instance per host (kbn-es runs fixed es01/es02 on a
    shared network with no per-instance name), and its containers bind the low
    port band that snapshot slots 0 and 1 also use. So:

    - Auto-stop any other registered agent-owned serverless stack (they are
      mutually exclusive and cannot coexist anyway).
    - Refuse to auto-stop a user-owned serverless stack from an agent start.
    - Refuse to start if a snapshot stack occupies a conflicting slot, naming it,
      rather than silently killing unrelated parallel snapshot work.
    """
    blockers = []
    serverless_to_stop = []
    for worktree, entry in store.worktree_entries(registry):
        if worktree == current_worktree:
            continue
        backend = entry.get("backend")
        if backend == "serverless":
            existing_started_by = store.stack_started_by(entry)
            if new_started_by == config.STARTED_BY_AGENT and existing_started_by == config.STARTED_BY_USER:
                blockers.append((worktree, entry.get("slot"), "user-owned serverless"))
                continue
            serverless_to_stop.append((worktree, entry))
        elif (
            backend == "snapshot"
            and entry.get("es_key") is None
            and entry.get("slot") in config.SERVERLESS_SNAPSHOT_CONFLICT_SLOTS
        ):
            blockers.append((worktree, entry.get("slot"), "snapshot port conflict"))
    for version, instance in store.es_instances(registry).items():
        if (
            instance.get("slot") in config.SERVERLESS_SNAPSHOT_CONFLICT_SLOTS
            and liveness.es_instance_state(instance) != "stale"
        ):
            blockers.append((f"shared ES {version}", instance.get("slot"), "shared ES port conflict"))
    if blockers:
        listed = "; ".join(f"{wt} (slot {s}, {reason})" for wt, s, reason in blockers)
        config.fail(
            "serverless needs the low ES port band (9200-9302), but these snapshot "
            f"or user-owned stacks occupy it: {listed}. Stop them first with "
            "`,kbn-stack --stop` from each worktree (a shared ES stops with its "
            "last attached worktree, or `,kbn-stack --stop-all`), then retry serverless."
        )
    for worktree, entry in serverless_to_stop:
        print(
            f",kbn-stack: serverless is single-instance; stopping existing serverless stack at {worktree} first.",
            flush=True,
        )
        stop_entry(worktree, entry, allow_user_owned=new_started_by == config.STARTED_BY_USER)
        del registry[worktree]
    store.save_registry(registry)
