"""Live-state classification of registry entries from process and port evidence."""

from __future__ import annotations

from kbn_stack import config, procs, slots, store


def es_instance_state(instance: dict) -> str:
    """Classify a shared ES instance: ready, starting, or stale.

    Ready requires the recorded ``es_pid``'s process tree to own the port
    listener. ``es_pid`` is registered in the statement after spawn, while the
    JVM still needs seconds to bind, so a listener with no ``es_pid`` or
    outside that tree is treated as a foreign process that grabbed the port
    (e.g. after ES died) and must not be attached to as if it were the
    shared ES.
    """
    port = instance.get("es_http")
    es_pid = instance.get("es_pid")
    if isinstance(port, int) and isinstance(es_pid, int) and procs.listener_identity_ok(port, es_pid)[0]:
        return "ready"
    if any(procs.pid_alive(instance.get(key)) for key in ("es_pid", "starting_pid")):
        return "starting"
    return "stale"


def slot_liveness(entry: dict) -> tuple[bool, bool]:
    """Return (kbn_alive, es_alive) for a snapshot stack's tandem ports."""
    kbn_port, es_http = slots.entry_ports(entry)
    kbn_alive = bool(procs.port_listener_pids(kbn_port)) if kbn_port is not None else False
    es_alive = bool(procs.port_listener_pids(es_http)) if es_http is not None else False
    return kbn_alive, es_alive


def band_listener_owned(registry: dict, slot: int, port: int) -> bool:
    """True when the ``port`` listener is identity-verified as another stack's.

    Only a registered non-serverless stack or shared instance on the same
    ``slot`` whose recorded pid's process tree owns the listener explains it
    away. Owner liveness alone is not enough: a bootstrapping launcher on the
    slot has not bound anything yet, so a listener there is still a surviving
    serverless container.
    """
    for _, entry in store.worktree_entries(registry):
        if entry.get("backend") == "serverless" or entry.get("es_key") is not None:
            continue
        if entry.get("slot") != slot:
            continue
        for key in ("es_pid", "started_by_pid"):
            pid = entry.get(key)
            if isinstance(pid, int) and procs.listener_identity_ok(port, pid)[0]:
                return True
    for instance in store.es_instances(registry).values():
        if instance.get("slot") != slot:
            continue
        es_pid = instance.get("es_pid")
        if isinstance(es_pid, int) and procs.listener_identity_ok(port, es_pid)[0]:
            return True
    return False


def serverless_band_alive(registry: dict) -> bool:
    """True while a serverless container port (es01/es02, HTTP or transport) has a listener.

    A band listener is ignored only when ``band_listener_owned`` ties it to a
    registered non-serverless stack on that slot: an isolated snapshot
    legitimately holds slot 1 (9202/9302) once the containers are dead.
    Unattributable listeners block, which fails safe toward not orphaning a
    surviving es02 container.
    """
    for slot in config.SERVERLESS_SNAPSHOT_CONFLICT_SLOTS:
        cfg = slots.derive(slot)
        for port in (cfg["es_http"], cfg["es_transport"]):
            if not procs.port_listener_pids(port):
                continue
            if band_listener_owned(registry, slot, port):
                continue
            return True
    return False


def ensure_ports_free(cfg: dict, *, check_kbn: bool = True, check_es: bool = True) -> None:
    """Fail fast when a foreign process already holds the slot's ports.

    A leftover/orphaned stack (e.g. a Kibana whose registry entry was dropped)
    keeps the port bound: the new Kibana then FATALs with "Port ... is already
    in use" while the orphan keeps answering ``/api/status`` with stale code,
    so the failure surfaces late and looks like a ready stack serving old
    bundles. Name the owner up front instead of starting into that state.

    A shared-ES attachee binds only its Kibana port (``check_es=False``); a new
    shared ES instance binds only its ES ports (``check_kbn=False``).
    """
    checks = []
    if check_kbn:
        checks.append(("Kibana", cfg["kbn_port"]))
    if check_es:
        checks.append(("Elasticsearch", cfg["es_http"]))
    conflicts: list[str] = []
    for label, port in checks:
        for pid in procs.port_listener_pids(port):
            conflicts.append(f"  {label} port {port}: pid {pid} ({procs.describe_pid(pid)})")
    if conflicts:
        detail = "\n".join(conflicts)
        config.fail(
            f"slot {cfg['slot']} ports are already in use:\n{detail}\n"
            "Stop that stack (,kbn-stack --stop from its worktree) or kill the pid, then rerun."
        )


def entry_has_live_processes(entry: dict, ignored_pid: int | None = None) -> bool:
    """True when any process recorded for this stack is still running.

    ``started_by_pid`` is the ,kbn-stack launcher: for interactive stacks it
    streams ES logs for the stack's whole lifetime, and for detached stacks it
    lives through the entire bootstrap (<pm> kbn bootstrap + ES setup + Kibana
    readiness poll). ``kbn_pid``/``es_pid`` cover detached stacks after the
    launcher has returned. Any of them alive means the stack is active or still
    bootstrapping, so its ports being closed is not evidence of death.
    """
    for key in ("started_by_pid", "kbn_pid", "es_pid"):
        pid = entry.get(key)
        if pid != ignored_pid and procs.pid_alive(pid):
            return True
    return False


def status_state(entry: dict, process_alive: bool, kbn_alive: bool, es_alive: bool) -> str:
    """Classify one registry entry from recorded readiness and current liveness."""
    if entry.get("ready") is True and kbn_alive and es_alive:
        return "ready"
    if entry.get("ready") is not True and process_alive:
        return "starting"
    if process_alive or kbn_alive or es_alive:
        return "degraded"
    return "stale"


def shared_es_ready(registry: dict, es_key: str) -> bool:
    """True when the shared ES ``es_key`` is registered and identity-verified ready."""
    instance = store.es_instances(registry).get(es_key)
    return isinstance(instance, dict) and es_instance_state(instance) == "ready"


def shared_es_clients(registry: dict, es_key: str) -> list[str]:
    """Worktrees attached to ``es_key`` that still have a Kibana client.

    A client is a Kibana listening on its slot port, a recorded Kibana process
    (``kbn_pid``) that is still alive (Kibana runs with ``--no-base-path``, so a
    dev-mode server restart unbinds the port for as long as the reboot takes), or
    a start that has not reached readiness while its launcher or recorded
    processes are alive (the minutes of bootstrap before Kibana binds). A
    worktree whose Kibana is gone no longer counts, even if its interactive
    launcher still follows the ES log.
    """
    clients: list[str] = []
    for worktree in store.attached_worktrees(registry, es_key):
        entry = registry[worktree]
        kbn_alive, _ = slot_liveness(entry)
        if (
            kbn_alive
            or procs.pid_alive(entry.get("kbn_pid"))
            or (entry.get("ready") is not True and entry_has_live_processes(entry))
        ):
            clients.append(worktree)
    return clients


def entry_state(registry: dict, entry: dict, process_alive: bool, kbn_alive: bool, es_alive: bool) -> str:
    """Classify a worktree entry, resolving its ES half through the shared map.

    An isolated stack owns both halves of its slot (tandem semantics). A shared
    attachee owns only its Kibana half: the shared ES liveness gates readiness,
    but a dead shared ES must not keep a dead attachee entry alive (the shared
    instance has its own lifecycle and reclaim path).
    """
    es_key = entry.get("es_key")
    if es_key is None:
        return status_state(entry, process_alive, kbn_alive, es_alive)
    if entry.get("ready") is True and kbn_alive and shared_es_ready(registry, es_key):
        return "ready"
    if entry.get("ready") is not True and process_alive:
        return "starting"
    if process_alive or kbn_alive:
        return "degraded"
    return "stale"
