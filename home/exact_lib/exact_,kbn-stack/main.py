#!/usr/bin/env python3
"""Spin up an isolated ES + Kibana dev stack for the current Kibana worktree.

Replaces the fixed ,start-main-kbn / ,start-feat-kbn scripts. Each worktree gets
an auto-allocated slot; the slot derives a unique Kibana port, Elasticsearch
HTTP/transport ports, security cookie name, and saved-objects encryption key, so
any number of worktrees can run in parallel on plain http://localhost:<port>
without /etc/hosts hostname aliases (Kibana session cookies are host-scoped, not
port-scoped, so two instances on the same host need distinct cookie names).

Kibana always runs from the worktree source (``yarn start``); there is no
prebuilt image for an arbitrary branch. Elasticsearch can be the stateful
snapshot build (default, native JVM) or serverless (Docker).

Snapshot stacks are fully parallel (one per worktree, isolated by slot).
Serverless is single-instance per host: kbn-es runs fixed es01/es02 containers
with no per-instance name, so a serverless start pins to slot 0, auto-stops
agent-owned serverless stacks, refuses to stop user-owned serverless stacks from
agent mode, and refuses to start over a snapshot stack holding the conflicting
low ES port band (slots 0-1).

The resolved stack is recorded in a registry at
``~/.cache/kbn-stack/registry.json`` keyed by worktree path, which the
live-ui-review contract reads to resolve the base/head browser URLs and
teardown ownership.

Usage:
    ,kbn-stack [--es snapshot|serverless] [--project-type es|security|oblt]
               [--data NAME] [--slot N] [--detach]
               [-E key=value ...] [-K key=value ...]
    ,kbn-stack --stop        # tear down this worktree's registered stack
    ,kbn-stack --stop-all    # tear down registered detached/serverless stacks

``-E key=value`` passes an extra Elasticsearch setting through to the snapshot
backend; ``-K key=value`` passes an extra Kibana CLI setting through to
``yarn start`` as ``--key=value`` (repeatable). Use ``-K`` to start a stack with
the runtime config a change under review needs in one shot, e.g.
``-K xpack.index_management.dev.enableSemanticField=true``, instead of starting a
default stack and restarting Kibana afterwards.

Run it from within a Kibana git worktree.

Interactive (default): runs ES in the current tmux pane and auto-launches Kibana
in a second pane once ES finishes setup (splitting the window if only one pane
exists). Outside tmux it prints the Kibana command to run.

Agent (``--detach``): starts ES and Kibana in the background (no tmux), waits
until Kibana answers ``/api/status``, records ``ready: true`` plus the process
pids in the registry, then returns. Intended for agentic sessions that then read
the registry to resolve live URLs. Registry entries record ``started_by`` as
``agent`` for detached starts and ``user`` for interactive starts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

TRIGGER_STRING = "succ kbn/es setup complete"
REGISTRY_PATH = Path.home() / ".cache" / "kbn-stack" / "registry.json"
ES_DATA_ROOT = Path.home() / "work" / "kibana" / "es_data"
ELASTIC_AUTH = ("elastic", "changeme")

# Slot -> port/cookie/key derivation. Slot 0 reproduces the historical defaults
# (Kibana 5601, ES 9200/9300). Each slot bumps Kibana by 1 and ES by 2 (HTTP +
# transport) so neighbouring slots never collide.
KBN_PORT_BASE = 5601
ES_HTTP_BASE = 9200
ES_TRANSPORT_BASE = 9300

PROJECT_TYPES = ("es", "security", "oblt")
BACKENDS = ("snapshot", "serverless")
STARTED_BY_AGENT = "agent"
STARTED_BY_USER = "user"


def fail(message: str) -> "None":
    print(f",kbn-stack: {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=",kbn-stack",
        description="Spin up an isolated ES + Kibana dev stack for the current worktree.",
    )
    parser.add_argument(
        "--es",
        choices=BACKENDS,
        default="snapshot",
        help="Elasticsearch backend: snapshot (stateful JVM, default) or serverless (Docker).",
    )
    parser.add_argument(
        "--project-type",
        choices=PROJECT_TYPES,
        default="es",
        help="Serverless project type (serverless backend only). Default: es.",
    )
    parser.add_argument(
        "--data",
        metavar="NAME",
        default=None,
        help="ES data folder name under ~/work/kibana/es_data (default: sanitized branch name).",
    )
    parser.add_argument(
        "--slot",
        type=int,
        default=None,
        help="Force a specific slot number instead of auto-allocating one.",
    )
    parser.add_argument(
        "--detach",
        action="store_true",
        help=(
            "Agent mode: start ES and Kibana in the background (no tmux), wait until "
            "Kibana answers /api/status, mark the stack ready and started_by=agent "
            "in the registry, then return. Use this from agentic sessions; omit it "
            "for interactive tmux dev."
        ),
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help=(
            "Tear down the stack for the current worktree when recorded processes "
            "are available, then drop its registry entry. User-owned interactive "
            "tmux stacks must be stopped from tmux."
        ),
    )
    parser.add_argument(
        "--stop-all",
        action="store_true",
        help=(
            "Tear down every registered detached/serverless stack. Interactive tmux "
            "stacks without recorded processes are left in the registry."
        ),
    )
    parser.add_argument(
        "-E",
        dest="es_flags",
        action="append",
        default=[],
        metavar="key=value",
        help="Extra Elasticsearch setting passed through to the snapshot backend (repeatable).",
    )
    parser.add_argument(
        "-K",
        "--kbn",
        dest="kbn_flags",
        action="append",
        default=[],
        metavar="key=value",
        help=(
            "Extra Kibana setting passed to `yarn start` as --key=value (repeatable). "
            "Use it to start a stack with the runtime config a change under review "
            "needs, e.g. -K xpack.index_management.dev.enableSemanticField=true."
        ),
    )
    return parser.parse_args(argv)


def git_output(args: list[str]) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def resolve_worktree() -> str:
    top = git_output(["rev-parse", "--show-toplevel"])
    if not top:
        fail("not inside a git worktree (run from a Kibana checkout)")
    return str(Path(top).resolve())


def current_branch() -> str:
    branch = git_output(["rev-parse", "--abbrev-ref", "HEAD"])
    return branch or "detached"


def sanitize(name: str) -> str:
    """Make a branch name safe for a directory / cookie suffix."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "stack"


def load_registry() -> dict:
    if not REGISTRY_PATH.is_file():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_registry(registry: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stack_started_by(entry: dict) -> str:
    """Return the stack ownership marker, inferring safe legacy defaults."""
    started_by = entry.get("started_by")
    if started_by in (STARTED_BY_AGENT, STARTED_BY_USER):
        return started_by
    if entry.get("start_mode") == "agent-detach":
        return STARTED_BY_AGENT
    if any(isinstance(entry.get(key), int) for key in ("kbn_pid", "es_pid")):
        return STARTED_BY_AGENT
    return STARTED_BY_USER


def start_mode(args: argparse.Namespace, target_pane: str | None) -> str:
    if args.detach:
        return "agent-detach"
    if target_pane:
        return "interactive-tmux"
    return "manual-command"


def port_listener_pids(port: int) -> list[int]:
    """Return the pids listening on TCP ``port`` (loopback dev stacks).

    Uses ``lsof`` (present on macOS at /usr/sbin/lsof and on Linux) because it
    reports the owning pid, which the registry does not store for interactive
    tmux stacks. ``-t`` prints one pid per line; empty output means nothing is
    listening, so the port is free. Any lsof failure is treated as "no listener"
    so a missing/edge-case probe never blocks slot reuse.
    """
    if not isinstance(port, int):
        return []
    result = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: list[int] = []
    for line in result.stdout.split():
        try:
            pids.append(int(line))
        except ValueError:
            continue
    return pids


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


def slot_liveness(entry: dict) -> tuple[bool, bool]:
    """Return (kbn_alive, es_alive) for a snapshot stack's tandem ports."""
    kbn_port, es_http = entry_ports(entry)
    kbn_alive = bool(port_listener_pids(kbn_port)) if kbn_port is not None else False
    es_alive = bool(port_listener_pids(es_http)) if es_http is not None else False
    return kbn_alive, es_alive


def kill_port_listeners(port: int | None) -> bool:
    """SIGTERM then SIGKILL whatever is listening on ``port``. Returns True if it acted.

    Interactive stacks are not our children, so their process groups are not
    ours to signal by recorded pid; the port owner is killed directly instead.
    """
    if port is None:
        return False
    pids = port_listener_pids(port)
    if not pids:
        return False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            continue
    for _ in range(20):
        if not port_listener_pids(port):
            return True
        time.sleep(0.25)
    for pid in port_listener_pids(port):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            continue
    return True


def pid_alive(pid: object) -> bool:
    """True when ``pid`` refers to a live process (signal 0 probe).

    PermissionError means the pid exists but belongs to another user, so it
    counts as alive. Pid reuse can make a stale entry look alive; that only
    leaves a slot occupied (the next worktree takes a higher slot), which is a
    safe failure mode compared to reclaiming a live stack.
    """
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OverflowError):
        return False
    except PermissionError:
        return True
    return True


def describe_pid(pid: int) -> str:
    """Best-effort command line for ``pid`` (diagnostics only)."""
    result = subprocess.run(
        ["ps", "-o", "command=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown command"


def pid_ancestors(pid: int, limit: int = 20) -> set[int]:
    """Return the ancestor pids of ``pid`` via repeated ``ps -o ppid=`` walks."""
    ancestors: set[int] = set()
    current = pid
    for _ in range(limit):
        result = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(current)],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            parent = int(result.stdout.strip())
        except ValueError:
            break
        if parent <= 1 or parent in ancestors:
            break
        ancestors.add(parent)
        current = parent
    return ancestors


def ensure_ports_free(cfg: dict) -> None:
    """Fail fast when a foreign process already holds the slot's ports.

    A leftover/orphaned stack (e.g. a Kibana whose registry entry was dropped)
    keeps the port bound: the new Kibana then FATALs with "Port ... is already
    in use" while the orphan keeps answering ``/api/status`` with stale code,
    so the failure surfaces late and looks like a ready stack serving old
    bundles. Name the owner up front instead of starting into that state.
    """
    conflicts: list[str] = []
    for label, port in (("Kibana", cfg["kbn_port"]), ("Elasticsearch", cfg["es_http"])):
        for pid in port_listener_pids(port):
            conflicts.append(f"  {label} port {port}: pid {pid} ({describe_pid(pid)})")
    if conflicts:
        detail = "\n".join(conflicts)
        fail(
            f"slot {cfg['slot']} ports are already in use:\n{detail}\n"
            "Stop that stack (,kbn-stack --stop from its worktree) or kill the pid, then rerun."
        )


def listener_identity_ok(port: int, owner_pid: int) -> tuple[bool, list[int]]:
    """Check the ``port`` listener belongs to the process tree led by ``owner_pid``.

    A 200 from ``/api/status`` alone does not prove the spawned Kibana is the
    process answering: an orphan from another worktree can hold the port while
    the spawned Kibana already FATALed on bind. Accept a listener in
    ``owner_pid``'s process group (spawn uses ``start_new_session=True``) or
    with ``owner_pid`` among its ancestors; anything else is a squatter.
    Returns (ok, listener_pids).
    """
    listeners = port_listener_pids(port)
    if not listeners:
        return False, []
    try:
        owner_pgid = os.getpgid(owner_pid)
    except (ProcessLookupError, PermissionError):
        owner_pgid = None
    for listener in listeners:
        if listener == owner_pid or owner_pid in pid_ancestors(listener):
            return True, listeners
        if owner_pgid is not None:
            try:
                if os.getpgid(listener) == owner_pgid:
                    return True, listeners
            except (ProcessLookupError, PermissionError):
                continue
    return False, listeners


def entry_has_live_processes(entry: dict) -> bool:
    """True when any process recorded for this stack is still running.

    ``started_by_pid`` is the ,kbn-stack launcher: for interactive stacks it
    streams ES logs for the stack's whole lifetime, and for detached stacks it
    lives through the entire bootstrap (yarn kbn bootstrap + ES setup + Kibana
    readiness poll). ``kbn_pid``/``es_pid`` cover detached stacks after the
    launcher has returned. Any of them alive means the stack is active or still
    bootstrapping, so its ports being closed is not evidence of death.
    """
    return any(pid_alive(entry.get(key)) for key in ("started_by_pid", "kbn_pid", "es_pid"))


def reclaim_dead_slots(registry: dict, current_worktree: str) -> bool:
    """Free slots held by snapshot stacks whose ES+Kibana pair is not both alive.

    A worktree's slot is only genuinely occupied while *both* its Kibana and
    Elasticsearch ports are live (they run in tandem). If either half died, the
    registry entry is stale and was reserving the slot against new worktrees, so:

    - kill any surviving half (so the reused slot's ports are clean), and
    - drop the stale entry, returning its slot to the lowest-slot search.

    Port liveness alone cannot distinguish a dead stack from one still
    bootstrapping (yarn kbn bootstrap + ES snapshot setup take minutes before
    any port binds), so entries whose launcher or recorded stack processes are
    still running are skipped: reclaiming them would hand their slot (ports,
    log file, cookie) to another worktree and couple the two stacks.

    Serverless entries are left untouched: they are exclusive/single-instance and
    governed by ``stop_existing_serverless``, not by per-slot port reclamation.
    The current worktree is never reclaimed here (its own slot is sticky).
    Returns True when the registry changed.
    """
    changed = False
    for worktree, entry in list(registry.items()):
        if worktree == current_worktree:
            continue
        if entry.get("backend") == "serverless":
            continue
        if not isinstance(entry.get("slot"), int):
            continue
        if entry_has_live_processes(entry):
            continue
        kbn_alive, es_alive = slot_liveness(entry)
        if kbn_alive and es_alive:
            continue
        kbn_port, es_http = entry_ports(entry)
        if kbn_alive or es_alive:
            print(
                f",kbn-stack: reclaiming slot {entry['slot']} ({worktree}): "
                f"Kibana {'up' if kbn_alive else 'down'}, ES {'up' if es_alive else 'down'}; "
                "killing the surviving half so the slot is free.",
                flush=True,
            )
            if kbn_alive:
                kill_port_listeners(kbn_port)
            if es_alive:
                kill_port_listeners(es_http)
        else:
            print(
                f",kbn-stack: reclaiming slot {entry['slot']} ({worktree}): "
                "no live Kibana/ES; dropping stale registry entry.",
                flush=True,
            )
        del registry[worktree]
        changed = True
    if changed:
        save_registry(registry)
    return changed


def allocate_slot(registry: dict, worktree: str, forced: int | None) -> int:
    if forced is not None:
        if forced < 0:
            fail("--slot must be >= 0")
        return forced
    existing = registry.get(worktree)
    if existing and isinstance(existing.get("slot"), int):
        return existing["slot"]
    taken = {entry["slot"] for key, entry in registry.items() if key != worktree and isinstance(entry.get("slot"), int)}
    slot = 0
    while slot in taken:
        slot += 1
    return slot


def encryption_key_for(slot: int) -> str:
    """Stable 32+ char key derived from the slot so saved objects survive restarts."""
    digest = hashlib.sha256(f"kbn-stack-slot-{slot}".encode("utf-8")).hexdigest()
    return digest[:48]


def derive(slot: int) -> dict:
    kbn_port = KBN_PORT_BASE + slot
    es_http = ES_HTTP_BASE + slot * 2
    es_transport = ES_TRANSPORT_BASE + slot * 2
    return {
        "kbn_port": kbn_port,
        "es_http": es_http,
        "es_transport": es_transport,
        "kbn_url": f"http://localhost:{kbn_port}",
        "es_url": f"http://localhost:{es_http}",
        "cookie_name": f"sid-{slot}",
        "encryption_key": encryption_key_for(slot),
    }


def tmux_target_pane(worktree: str) -> str | None:
    """Pick the pane that should run Kibana, creating a split if needed.

    When another pane already exists in the current window, target the next one
    (matching the previous start scripts' behavior, so an existing 2-pane layout
    is reused). When the window has only this pane, split it and target the new
    pane, so a single ``,kbn-stack`` call sets up the whole ES + Kibana layout.
    Returns None when not in tmux (the caller then prints the command instead).
    """
    if not os.environ.get("TMUX"):
        return None

    def tmux(args: list[str]) -> str:
        result = subprocess.run(["tmux", *args], capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else ""

    current_pane = tmux(["display-message", "-p", "#{pane_id}"])
    current_index_raw = tmux(["display-message", "-p", "#{pane_index}"])
    panes_raw = tmux(["list-panes", "-F", "#{pane_index} #{pane_id}"])

    panes: list[tuple[int, str]] = []
    for line in panes_raw.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit():
            panes.append((int(parts[0]), parts[1]))

    try:
        current_index = int(current_index_raw)
    except ValueError:
        current_index = -1

    after = sorted((idx, pid) for idx, pid in panes if idx > current_index)
    if after:
        return after[0][1]
    other = [pid for idx, pid in panes if idx != current_index]
    if other:
        return other[0]

    # Only this pane exists: create a second pane for Kibana, keep focus here so
    # Elasticsearch logs stay in the foreground pane the user invoked from.
    new_pane = tmux(["split-window", "-h", "-d", "-c", worktree, "-P", "-F", "#{pane_id}"])
    return new_pane or current_pane or None


def ensure_trial_license(es_url: str) -> None:
    """Activate a trial license once ES is reachable.

    SAML (mock IdP dev login) requires a trial license; a basic license makes the
    SAML realm non-compliant and Kibana login loops on /security/reset_session.
    start_trial is idempotent: it no-ops once the cluster is already on trial.
    """
    user, password = ELASTIC_AUTH
    auth = f"{user}:{password}"
    for _ in range(60):
        health = subprocess.run(
            ["curl", "-fsS", "-m5", "-u", auth, f"{es_url}/_cluster/health"],
            capture_output=True,
            check=False,
        )
        if health.returncode == 0:
            subprocess.run(
                ["curl", "-fsS", "-m10", "-u", auth, "-X", "POST", f"{es_url}/_license/start_trial?acknowledge=true"],
                capture_output=True,
                check=False,
            )
            return
        time.sleep(2)


def kibana_command(args: argparse.Namespace, cfg: dict) -> str:
    parts = [
        "yarn",
        "start",
        "--no-base-path",
        f"--port={cfg['kbn_port']}",
        f"--elasticsearch.hosts={cfg['es_url']}",
        f"--xpack.security.cookieName={cfg['cookie_name']}",
        f"--xpack.encryptedSavedObjects.encryptionKey={cfg['encryption_key']}",
    ]
    if args.es == "serverless":
        parts.append(f"--serverless={args.project_type}")
    for flag in args.kbn_flags:
        parts.append(f"--{flag}")
    return " ".join(shlex.quote(p) for p in parts)


def es_command(args: argparse.Namespace, cfg: dict, data_path: Path) -> list[str]:
    if args.es == "serverless":
        return [
            "yarn",
            "es",
            "serverless",
            "--projectType",
            args.project_type,
            "--port",
            str(cfg["es_http"]),
            "--dataPath",
            str(data_path),
            "--kill",
        ]
    cmd = [
        "yarn",
        "es",
        "snapshot",
        "-E",
        f"node.name=slot{cfg['slot']}",
        "-E",
        f"http.port={cfg['es_http']}",
        "-E",
        f"transport.port={cfg['es_transport']}",
        "-E",
        "discovery.type=single-node",
        "-E",
        f"path.data={data_path}",
    ]
    for flag in args.es_flags:
        cmd += ["-E", flag]
    return cmd


def mark_ready(worktree: str, ready: bool) -> None:
    """Reload the registry and set the ready flag for one worktree, preserving other fields."""
    registry = load_registry()
    entry = registry.get(worktree)
    if entry is None:
        return
    entry["ready"] = ready
    save_registry(registry)


def start_kibana_on_trigger(
    logfile: Path,
    es_url: str,
    kbn_cmd: str,
    target_pane: str | None,
    worktree: str,
    kbn_url: str,
) -> None:
    """Wait for the ES setup trigger, ensure trial license, then launch Kibana.

    When Kibana is launched into a tmux pane, poll its /api/status afterwards and
    flip the registry ``ready`` flag so an agent running ``/k-agent-review`` from the
    same worktree can discover the interactively-started stack. The poll runs in
    this background thread, so it never blocks the foreground ES log stream.
    """
    # The caller clears the log before ES starts. Read from byte zero so the
    # trigger remains visible if ES writes it before this thread is scheduled.
    with logfile.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            line = handle.readline()
            if not line:
                time.sleep(0.5)
                continue
            if TRIGGER_STRING in line:
                ensure_trial_license(es_url)
                if target_pane:
                    subprocess.run(
                        ["tmux", "send-keys", "-t", target_pane, kbn_cmd, "C-m"],
                        check=False,
                    )
                    if kibana_ready(kbn_url, timeout=600):
                        mark_ready(worktree, True)
                else:
                    print(
                        f"\n,kbn-stack: Elasticsearch ready. Start Kibana with:\n  {kbn_cmd}\n",
                        flush=True,
                    )
                return


def wait_for_trigger(logfile: Path, timeout: float) -> bool:
    """Block until the ES setup trigger appears in the log, or timeout elapses."""
    deadline = time.monotonic() + timeout
    # spawn_background truncates the log before launching ES. Reading from byte
    # zero also detects a trigger written before this reader opens the file.
    with logfile.open("r", encoding="utf-8", errors="replace") as handle:
        while time.monotonic() < deadline:
            line = handle.readline()
            if not line:
                time.sleep(0.5)
                continue
            if TRIGGER_STRING in line:
                return True
    return False


def kibana_ready(kbn_url: str, timeout: float) -> bool:
    """Poll Kibana's /api/status until it answers 200 (serving), or timeout."""
    user, password = ELASTIC_AUTH
    auth = f"{user}:{password}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = subprocess.run(
            ["curl", "-fsS", "-m5", "-u", auth, f"{kbn_url}/api/status"],
            capture_output=True,
            check=False,
        )
        if probe.returncode == 0:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(3, remaining))
    return False


def spawn_background(cmd: list[str], logfile: Path, worktree: str) -> int:
    """Start a detached process writing combined output to logfile; return its pid."""
    handle = logfile.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=handle,
        stderr=subprocess.STDOUT,
        cwd=worktree,
        start_new_session=True,
    )
    return proc.pid


def run_detached(
    args: argparse.Namespace,
    cfg: dict,
    worktree: str,
    data_path: Path,
    es_logfile: Path,
    kbn_cmd: str,
    registry: dict,
) -> int:
    """Agent mode: background ES + Kibana, wait until ready, record readiness, return."""
    kbn_logfile = Path(f"/tmp/kbn-slot{cfg['slot']}.log")

    es_pid = spawn_background(es_command(args, cfg, data_path), es_logfile, worktree)
    print(f",kbn-stack: Elasticsearch starting (pid {es_pid}) -> {es_logfile}", flush=True)

    if not wait_for_trigger(es_logfile, timeout=600):
        registry[worktree]["es_pid"] = es_pid
        save_registry(registry)
        fail(f"Elasticsearch did not finish setup within 600s (see {es_logfile})")

    ensure_trial_license(cfg["es_url"])

    kbn_pid = spawn_background(shlex.split(kbn_cmd), kbn_logfile, worktree)
    print(f",kbn-stack: Kibana starting (pid {kbn_pid}) -> {kbn_logfile}", flush=True)

    ready = kibana_ready(cfg["kbn_url"], timeout=600)
    identity_ok, squatters = (False, [])
    if ready:
        identity_ok, squatters = listener_identity_ok(cfg["kbn_port"], kbn_pid)
    registry[worktree]["es_pid"] = es_pid
    registry[worktree]["kbn_pid"] = kbn_pid
    registry[worktree]["kbn_log"] = str(kbn_logfile)
    registry[worktree]["ready"] = ready and identity_ok
    save_registry(registry)

    if not ready:
        fail(f"Kibana did not answer /api/status within 600s (see {kbn_logfile})")
    if not identity_ok:
        detail = ", ".join(f"pid {pid} ({describe_pid(pid)})" for pid in squatters) or "no listener found"
        fail(
            f"Kibana answered /api/status on port {cfg['kbn_port']}, but the listener is not the Kibana"
            f" spawned by this start (pid {kbn_pid}): {detail}.\n"
            f"An orphan stack is squatting the port and serving stale code; the spawned Kibana likely"
            f" FATALed on bind (see {kbn_logfile}). Kill the squatter, then rerun."
        )

    print(
        f",kbn-stack: ready. Kibana -> {cfg['kbn_url']} (cookie {cfg['cookie_name']}), ES -> {cfg['es_url']}",
        flush=True,
    )
    return 0


def kill_pid_group(pid: int) -> None:
    """SIGTERM then SIGKILL the process group led by pid (a stack child started
    with start_new_session=True, so pid is the group leader). No-op if already gone."""
    try:
        pgid = os.getpgid(pid)
    except (ProcessLookupError, PermissionError):
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    for _ in range(20):
        try:
            os.killpg(pgid, 0)
        except (ProcessLookupError, PermissionError):
            return
        time.sleep(0.25)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return


def docker_kill_serverless() -> None:
    """Remove the serverless ES containers (es01/es02).

    kbn-es runs serverless Elasticsearch in Docker containers named es01/es02 on
    the shared `elastic` network, with no per-instance name (verified: `yarn es
    serverless` exposes no --name flag). Because ,kbn-stack treats serverless as
    single-instance (exclusive), these fixed names are unambiguous here.
    """
    for name in ("es01", "es02"):
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True,
            check=False,
        )


def stop_entry(worktree: str, entry: dict, *, allow_user_owned: bool = True, reclaim_ports: bool = False) -> bool:
    """Tear down one registered stack: kill recorded Kibana then ES processes.

    Snapshot stacks run as our own children (pids recorded), so killing their
    process groups stops the yarn/node and JVM trees. Serverless stacks run their
    Elasticsearch in Docker containers (es01/es02); ,kbn-stack treats serverless
    as single-instance, so those fixed names are removed directly.

    Interactive tmux stacks have no recorded process groups. With
    ``reclaim_ports`` set (an explicit single-worktree ``--stop``), fall back to
    killing whatever still listens on this slot's Kibana/ES ports so the stack is
    actually torn down and its registry entry can be removed. Without it (bulk
    ``--stop-all`` and serverless preflight), such entries are left intact rather
    than claiming they were stopped.
    """
    slot = entry.get("slot")
    started_by = stack_started_by(entry)
    if started_by == STARTED_BY_USER and not allow_user_owned:
        print(f",kbn-stack: leaving user-owned slot {slot} ({worktree}) running.", flush=True)
        return False
    print(f",kbn-stack: stopping slot {slot} ({worktree}, started_by={started_by})", flush=True)
    stopped = False
    for key in ("kbn_pid", "es_pid"):
        pid = entry.get(key)
        if isinstance(pid, int):
            kill_pid_group(pid)
            stopped = True
    if entry.get("backend") == "serverless":
        docker_kill_serverless()
        stopped = True
    if not stopped and reclaim_ports and entry.get("backend") != "serverless":
        kbn_port, es_http = entry_ports(entry)
        if kill_port_listeners(kbn_port):
            stopped = True
        if kill_port_listeners(es_http):
            stopped = True
        if stopped:
            print(
                f",kbn-stack: stopped interactive slot {slot} by killing its Kibana/ES port owners.",
                flush=True,
            )
    if not stopped:
        print(
            ",kbn-stack: no recorded detached/serverless processes; leaving registry entry intact.",
            flush=True,
        )
    return stopped


def run_stop(worktree: str, registry: dict) -> int:
    entry = registry.get(worktree)
    if entry is None:
        fail(f"no registered stack for this worktree ({worktree})")
    if not stop_entry(worktree, entry, reclaim_ports=True):
        # Nothing recorded and nothing listening on this slot's ports: the stack
        # is already gone. Drop the stale entry so the slot is freed.
        del registry[worktree]
        save_registry(registry)
        print(",kbn-stack: no live stack found; removed stale registry entry.", flush=True)
        return 0
    del registry[worktree]
    save_registry(registry)
    print(",kbn-stack: stopped and removed registry entry.", flush=True)
    return 0


def run_stop_all(registry: dict) -> int:
    if not registry:
        print(",kbn-stack: no registered stacks.", flush=True)
        return 0
    remaining = {}
    stopped_count = 0
    for worktree, entry in list(registry.items()):
        if stop_entry(worktree, entry):
            stopped_count += 1
        else:
            remaining[worktree] = entry
    save_registry(remaining)
    if remaining:
        print(
            f",kbn-stack: stopped {stopped_count} stack(s); left {len(remaining)} "
            "interactive stack(s) in the registry because they have no recorded processes.",
            flush=True,
        )
    else:
        print(f",kbn-stack: stopped {stopped_count} stack(s) and cleared the registry.", flush=True)
    return 0


# Ports occupied by the serverless ES Docker containers (es01/es02), fixed by
# kbn-es. es01 HTTP follows --port (we pin serverless to slot 0 -> 9200); es02
# HTTP and both transports are hardcoded. Snapshot slots 0 and 1 derive into this
# band (9200/9300 and 9202/9302), so a serverless start needs those slots free.
SERVERLESS_SNAPSHOT_CONFLICT_SLOTS = (0, 1)


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
    for worktree, entry in list(registry.items()):
        if worktree == current_worktree:
            continue
        backend = entry.get("backend")
        if backend == "serverless":
            existing_started_by = stack_started_by(entry)
            if new_started_by == STARTED_BY_AGENT and existing_started_by == STARTED_BY_USER:
                blockers.append((worktree, entry.get("slot"), "user-owned serverless"))
                continue
            serverless_to_stop.append((worktree, entry))
        elif backend == "snapshot" and entry.get("slot") in SERVERLESS_SNAPSHOT_CONFLICT_SLOTS:
            blockers.append((worktree, entry.get("slot"), "snapshot port conflict"))
    if blockers:
        listed = "; ".join(f"{wt} (slot {s}, {reason})" for wt, s, reason in blockers)
        fail(
            "serverless needs the low ES port band (9200-9302), but these snapshot "
            f"or user-owned stacks occupy it: {listed}. Stop them first with "
            "`,kbn-stack --stop` from each worktree, then retry serverless."
        )
    for worktree, entry in serverless_to_stop:
        print(
            f",kbn-stack: serverless is single-instance; stopping existing serverless stack at {worktree} first.",
            flush=True,
        )
        stop_entry(worktree, entry, allow_user_owned=new_started_by == STARTED_BY_USER)
        del registry[worktree]
    save_registry(registry)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.stop and args.stop_all:
        fail("--stop and --stop-all are mutually exclusive")

    if args.stop_all:
        return run_stop_all(load_registry())

    if args.stop:
        return run_stop(resolve_worktree(), load_registry())

    worktree = resolve_worktree()
    branch = current_branch()
    data_name = sanitize(args.data) if args.data else sanitize(branch)
    started_by = STARTED_BY_AGENT if args.detach else STARTED_BY_USER

    registry = load_registry()

    if args.es == "serverless":
        stop_existing_serverless(registry, worktree, started_by)
        # Serverless is single-instance and its Docker containers (es01/es02) bind
        # fixed ports, so pin it to slot 0 for deterministic, matching ports.
        if args.slot is not None and args.slot != 0:
            fail("serverless is single-instance and always uses slot 0; --slot is not allowed with --es serverless")
        slot = 0
    else:
        # Free slots whose snapshot stack is no longer fully alive (a killed
        # session leaves a stale registry entry that would otherwise push this
        # worktree onto a higher slot/port), then allocate.
        if args.slot is None:
            reclaim_dead_slots(registry, worktree)
        slot = allocate_slot(registry, worktree, args.slot)
    cfg = derive(slot)
    cfg["slot"] = slot
    ensure_ports_free(cfg)

    data_path = ES_DATA_ROOT / data_name
    logfile = Path(f"/tmp/es-slot{slot}.log")
    kbn_cmd = kibana_command(args, cfg)
    target_pane = None if args.detach else tmux_target_pane(worktree)
    mode = start_mode(args, target_pane)

    registry[worktree] = {
        "slot": slot,
        "branch": branch,
        "backend": args.es,
        "project_type": args.project_type if args.es == "serverless" else None,
        "exclusive": args.es == "serverless",
        "kbn_url": cfg["kbn_url"],
        "es_url": cfg["es_url"],
        "cookie_name": cfg["cookie_name"],
        "data": data_name,
        "kbn_flags": list(args.kbn_flags),
        "log": str(logfile),
        "ready": False,
        "started_by": started_by,
        "start_mode": mode,
        "started_by_pid": os.getpid(),
        "started_by_ppid": os.getppid(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    save_registry(registry)

    print(
        f",kbn-stack: worktree={worktree}\n"
        f"            slot={slot} backend={args.es} data={data_name}\n"
        f"            Kibana  -> {cfg['kbn_url']}  (cookie {cfg['cookie_name']})\n"
        f"            ES      -> {cfg['es_url']}\n",
        flush=True,
    )

    subprocess.run(["yarn", "kbn", "bootstrap"], check=True)

    # Clear stale output before either trigger reader starts. Both readers begin
    # at byte zero, so they cannot miss a trigger written before they open.
    logfile.write_text("", encoding="utf-8")
    if args.detach:
        return run_detached(args, cfg, worktree, data_path, logfile, kbn_cmd, registry)

    # The log already exists so the watcher never races a missing path.
    watcher = threading.Thread(
        target=start_kibana_on_trigger,
        args=(logfile, cfg["es_url"], kbn_cmd, target_pane, worktree, cfg["kbn_url"]),
        daemon=True,
    )
    watcher.start()

    es_cmd = es_command(args, cfg, data_path)
    with logfile.open("w", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(es_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log_handle.write(line)
            log_handle.flush()
        return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
