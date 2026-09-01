#!/usr/bin/env python3
"""Spin up an ES + Kibana dev stack for the current Kibana worktree.

Replaces the fixed ,start-main-kbn / ,start-feat-kbn scripts. Each worktree gets
an auto-allocated slot; the slot derives a unique Kibana port, Elasticsearch
HTTP/transport ports, security cookie name, and saved-objects encryption key, so
any number of worktrees can run in parallel on plain http://localhost:<port>
without /etc/hosts hostname aliases (Kibana session cookies are host-scoped, not
port-scoped, so two instances on the same host need distinct cookie names).

Kibana always runs from the worktree source (``yarn start``); there is no
prebuilt image for an arbitrary branch. Elasticsearch can be the stateful
snapshot build (default, native JVM) or serverless (Docker).

Default snapshot starts share one Elasticsearch per resolved ES version:
``yarn es snapshot`` downloads the version pinned by the worktree's
``package.json`` ``version`` field, so worktrees with the same version are
served by one background ES JVM instead of one JVM each (each extra isolated
ES costs ~1g heap and chokes the laptop when several stacks run in parallel).
Shared instances live under the reserved ``__es__`` registry key, use the data
dir ``~/work/kibana/es_data/shared-<version>``, and are refcounted: ``--stop``
kills only the worktree's Kibana and stops the shared ES only when no other
registered worktree still references it. Sharing is skipped (isolated ES, the
historical behavior) when the invocation carries any ES-level override --
``-E``, ``--data``, a non-default ``--es-heap`` -- or the explicit
``--isolated-es`` flag. Kibana-side flags (``-K``, ``--groups``) do not affect
sharing. Same-version Kibanas on one ES share the ``.kibana*`` saved-object
indices (normal HA topology); if a branch's saved-object model drifted and
migrations clash, rerun that worktree with ``--isolated-es``.

Isolated snapshot stacks are fully parallel (one per worktree, isolated by slot).
Serverless is single-instance per host: kbn-es runs fixed es01/es02 containers
with no per-instance name, so a serverless start pins to slot 0, auto-stops
agent-owned serverless stacks, refuses to stop user-owned serverless stacks from
agent mode, and refuses to start over a snapshot stack or shared ES holding the
conflicting low ES port band (slots 0-1).

The resolved stack is recorded in a registry at
``~/.cache/kbn-stack/registry.json`` keyed by worktree path, which the
live-ui-review contract reads to resolve the base/head browser URLs and
teardown ownership.

Usage:
    ,kbn-stack [--es snapshot|serverless] [--project-type es|security|oblt]
               [--data NAME] [--slot N] [--detach] [--isolated-es]
               [--groups platform|all|LIST] [--es-heap SIZE]
               [-E key=value ...] [-K key=value ...]
    ,kbn-stack --stop        # tear down this worktree's registered stack
    ,kbn-stack --stop-all    # tear down every registered stack, including interactive tmux
    ,kbn-stack --status      # list registered stacks with live-derived state
    ,kbn-stack --prune       # remove fully stale registry entries

``-E key=value`` passes an extra Elasticsearch setting through to the snapshot
backend; ``-K key=value`` passes an extra Kibana CLI setting through to
``yarn start`` as ``--key=value`` (repeatable). Snapshot starts also pass
``-E indices.merge.disk.watermark.high=2gb`` (absolute merge-disk floor) before
user ``-E`` flags, so a later ``-E`` of the same key overrides. Snapshot ES
also sets ``ES_JAVA_OPTS -Xms1g -Xmx1g`` (override with ``--es-heap 1536m``).
Kibana defaults to ``--groups platform`` (``plugins.allowlistPluginGroups``);
``--groups all`` loads every group. Restart the stack to change groups. Use
``-K`` to start a stack with the runtime config a change under review needs
in one shot, e.g. ``-K xpack.index_management.dev.enableSemanticField=true``,
instead of starting a default stack and restarting Kibana afterwards.

Run it from within a Kibana git worktree.

Interactive (default): runs ES in the current tmux pane and auto-launches Kibana
in a second pane once ES finishes setup (splitting the window if only one pane
exists). Outside tmux it prints the Kibana command to run. When the ES is
shared, it runs detached (it must outlive this pane) and the current pane
follows its log instead; Ctrl-C detaches from the log without stopping ES.

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
# After the setup trigger appears, how long an attacher waits for the shared ES
# port to be identity-verified before treating the trigger as stale evidence.
SHARED_ES_CONFIRM_TIMEOUT = 30.0
REGISTRY_PATH = Path.home() / ".cache" / "kbn-stack" / "registry.json"
ES_DATA_ROOT = Path.home() / "work" / "kibana" / "es_data"
ELASTIC_AUTH = ("elastic", "changeme")
# Reserved registry key holding shared ES instances (keyed by ES version).
# Every other top-level key remains an absolute worktree path, so existing
# per-worktree lookups (live-ui contract, skills) keep working unchanged.
ES_INSTANCES_KEY = "__es__"
SHARED_DATA_PREFIX = "shared-"
# Absolute free-space floor for Lucene merges. kbn-es already sets
# cluster.routing.allocation.disk.threshold_enabled=false, but the merge
# scheduler still uses indices.merge.disk.watermark.high=95%. On a ~1TB APFS
# volume at 96% used that budget clamps to 0 bytes despite tens of GB free,
# so overnight Kibana writes explode unmerged segments and trip the 1.5g parent breaker.
MERGE_DISK_WATERMARK = "indices.merge.disk.watermark.high=2gb"

# Kibana server plugin groups from @kbn/projects-solutions-groups KIBANA_GROUPS.
# Default platform covers Management (console, index management, stack management).
# --groups all skips the allowlist so every group loads. Restart to change groups.
PLUGIN_GROUPS = ("platform", "observability", "security", "search", "workplaceai", "vectordb")
DEFAULT_PLUGIN_GROUPS = "platform"
ALLOWLIST_KEY = "plugins.allowlistPluginGroups"

# Snapshot kbn-es otherwise pins -Xms1536m -Xmx1536m. 1g matches serverless kbn-es.
DEFAULT_ES_HEAP = "1g"
HEAP_SIZE_RE = re.compile(r"^[0-9]+[kKmMgG]$")
# SIGTERM grace before SIGKILL. Tests patch this so hang-after-unbind coverage stays fast.
KILL_GRACE_SECONDS = 5.0
KILL_POLL_SECONDS = 0.05

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


def parse_plugin_groups(raw: str) -> tuple[str, ...]:
    parts = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("expected all or a comma-separated group list")
    if parts == ["all"]:
        return ()
    if "all" in parts:
        raise argparse.ArgumentTypeError("--groups all cannot be combined with named groups")
    unknown = [part for part in parts if part not in PLUGIN_GROUPS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown plugin group(s): {', '.join(unknown)}. Use all or: {', '.join(PLUGIN_GROUPS)}"
        )
    seen: list[str] = []
    for part in parts:
        if part not in seen:
            seen.append(part)
    return tuple(seen)


def parse_es_heap(raw: str) -> str:
    if not HEAP_SIZE_RE.fullmatch(raw):
        raise argparse.ArgumentTypeError("expected a JVM size like 1g or 1536m")
    return raw


def resolved_kbn_flags(args: argparse.Namespace) -> list[str]:
    flags = list(args.kbn_flags)
    if any(flag.startswith(ALLOWLIST_KEY) for flag in flags):
        return flags
    injected = [f"{ALLOWLIST_KEY}.{index}={group}" for index, group in enumerate(args.plugin_groups)]
    return injected + flags


def es_java_opts(heap: str, existing: str = "") -> str:
    kept = [token for token in existing.split() if not token.lower().startswith(("-xms", "-xmx"))]
    return " ".join((f"-Xms{heap}", f"-Xmx{heap}", *kept))


def snapshot_es_env(heap: str) -> dict[str, str]:
    env = os.environ.copy()
    env["ES_JAVA_OPTS"] = es_java_opts(heap, env.get("ES_JAVA_OPTS", ""))
    return env


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=",kbn-stack",
        description="Spin up an ES + Kibana dev stack for the current worktree (default snapshot starts share one ES per version).",
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
        help=(
            "ES data folder name under ~/work/kibana/es_data (default: shared-<version> "
            "for a shared ES, else the sanitized branch name; passing --data disables sharing)."
        ),
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
            "Agent mode: start ES (or attach to a compatible live shared ES, starting "
            "only Kibana) in the background (no tmux), wait until Kibana answers "
            "/api/status, mark the stack ready and started_by=agent in the registry, "
            "then return. Use this from agentic sessions; omit it for interactive tmux dev."
        ),
    )
    parser.add_argument(
        "--isolated-es",
        dest="isolated_es",
        action="store_true",
        help=(
            "Give this worktree its own Elasticsearch instead of sharing/reusing a "
            "compatible one (snapshot only). Sharing is also disabled automatically "
            "by -E, --data, or a non-default --es-heap. Use this when the branch's "
            "saved-object migrations clash with the shared ES."
        ),
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help=(
            "Tear down the stack for the current worktree: kill recorded process "
            "groups and whatever still listens on the slot's Kibana/ES ports (a "
            "shared-ES attachee reclaims only its Kibana port), then drop its "
            "registry entry; the shared ES itself stops with its last attached worktree."
        ),
    )
    parser.add_argument(
        "--stop-all",
        action="store_true",
        help=(
            "Tear down every registered stack, including interactive tmux stacks "
            "with no recorded pids, then clear the registry."
        ),
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help=(
            "List every registered stack with live process and port state. "
            "Works outside a Kibana worktree and does not change the registry."
        ),
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help=(
            "Remove stale registry entries: worktree stacks with no live recorded "
            "process and no live owned port (a shared-ES attachee owns only its "
            "Kibana port), plus dead shared ES instances. Does not stop processes."
        ),
    )
    parser.add_argument("--run-with-prune", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    parser.add_argument(
        "--groups",
        dest="plugin_groups",
        type=parse_plugin_groups,
        default=parse_plugin_groups(DEFAULT_PLUGIN_GROUPS),
        metavar="LIST",
        help=(
            "Kibana plugin groups to load (comma-separated). Default: platform. "
            "Use --groups all for every group. Named groups: "
            + ", ".join(PLUGIN_GROUPS)
            + ". Restart the stack to change this."
        ),
    )
    parser.add_argument(
        "--es-heap",
        dest="es_heap",
        type=parse_es_heap,
        default=DEFAULT_ES_HEAP,
        metavar="SIZE",
        help=(
            "Snapshot ES JVM heap (sets -Xms and -Xmx). Default: 1g. "
            "Use --es-heap 1536m for the kbn-es snapshot default. Snapshot only."
        ),
    )
    parser.add_argument(
        "-E",
        dest="es_flags",
        action="append",
        default=[],
        metavar="key=value",
        help=(
            "Extra Elasticsearch setting passed through to the snapshot backend (repeatable). "
            "Snapshot starts already set indices.merge.disk.watermark.high=2gb; "
            "a later -E of the same key overrides."
        ),
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
    args = parser.parse_args(argv)
    if args.es == "serverless" and args.es_heap != DEFAULT_ES_HEAP:
        fail("--es-heap applies to snapshot ES only; serverless docker already pins 1g")
    return args


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
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    instances = data.get(ES_INSTANCES_KEY)
    if instances is not None and not isinstance(instances, dict):
        # A hand-edited registry must not crash every shared-map consumer.
        del data[ES_INSTANCES_KEY]
    elif isinstance(instances, dict):
        for version in [v for v, inst in instances.items() if not isinstance(inst, dict)]:
            del instances[version]
    return data


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


def worktree_entries(registry: dict) -> list[tuple[str, dict]]:
    """Registry items that are worktree stacks (everything except ``__es__``)."""
    return [(key, entry) for key, entry in registry.items() if key != ES_INSTANCES_KEY]


def es_instances(registry: dict) -> dict:
    """The shared ES instance map (version -> instance entry)."""
    instances = registry.get(ES_INSTANCES_KEY)
    return instances if isinstance(instances, dict) else {}


def attached_worktrees(registry: dict, es_key: str) -> list[str]:
    """Worktrees whose registered stack references the shared ES ``es_key``."""
    return [worktree for worktree, entry in worktree_entries(registry) if entry.get("es_key") == es_key]


def share_eligible(args: argparse.Namespace) -> bool:
    """True when this invocation may share/reuse a version-keyed ES.

    Any ES-level override means the caller wants a specific ES environment, so
    the stack gets its own isolated instance (the historical behavior).
    Kibana-side flags (-K, --groups) never affect ES sharing.
    """
    return (
        args.es == "snapshot"
        and not args.isolated_es
        and not args.es_flags
        and args.es_heap == DEFAULT_ES_HEAP
        and args.data is None
    )


def read_worktree_version(worktree: str) -> str | None:
    """The worktree's package.json version -- the ES version `yarn es snapshot` downloads.

    Kibana's scripts/es.js passes ``version: pkg.version`` to kbn-es, so two
    worktrees resolve to the same ES artifact exactly when this field matches.
    """
    try:
        version = json.loads((Path(worktree) / "package.json").read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    return version if isinstance(version, str) and version else None


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
    if isinstance(port, int) and isinstance(es_pid, int) and listener_identity_ok(port, es_pid)[0]:
        return "ready"
    if any(pid_alive(instance.get(key)) for key in ("es_pid", "starting_pid")):
        return "starting"
    return "stale"


def usable_es_instance(registry: dict, version: str) -> dict | None:
    """The registered shared ES for ``version`` when it is ready or still starting.

    An entry missing the endpoint/data fields the attach path dereferences
    (hand-edited or truncated registry) is unusable; it is left to go stale
    and be reclaimed rather than crash the attacher.
    """
    instance = es_instances(registry).get(version)
    if not isinstance(instance, dict):
        return None
    ints = [instance.get(key) for key in ("slot", "es_http", "es_transport")]
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in ints):
        return None
    if not all(isinstance(instance.get(key), str) and instance.get(key) for key in ("es_url", "data", "log")):
        return None
    if es_instance_state(instance) == "stale":
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
        return {"key": version, "create": False, "instance": instance}
    existing = es_instances(registry).get(version)
    if isinstance(existing, dict) and es_instance_state(existing) != "stale":
        attached = attached_worktrees(registry, version)
        if attached:
            fail(
                f"the registry entry for shared ES {version} is unusable (corrupt or incomplete) "
                f"but still referenced by: {', '.join(sorted(attached))}. Run `,kbn-stack --stop` "
                "in those worktrees or repair the registry, or rerun with --isolated-es."
            )
        # Replacing a live-but-unusable entry must not orphan its JVM.
        stop_es_instance(version, existing)
    es_slot = allocate_es_slot(registry, {exclude_slot})
    icfg = derive(es_slot)
    logfile = Path(f"/tmp/es-shared-{sanitize(version)}.log")
    logfile.write_text("", encoding="utf-8")
    instance = {
        "version": version,
        "slot": es_slot,
        "es_url": icfg["es_url"],
        "es_http": icfg["es_http"],
        "es_transport": icfg["es_transport"],
        "data": sanitize(f"{SHARED_DATA_PREFIX}{version}"),
        "log": str(logfile),
        "started_by": started_by,
        "starting_pid": os.getpid(),
        "created_from": worktree,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    instances = registry.get(ES_INSTANCES_KEY)
    if not isinstance(instances, dict):
        # A corrupt/hand-edited container must not crash the claim; replace it.
        instances = {}
        registry[ES_INSTANCES_KEY] = instances
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

    ``yarn kbn bootstrap`` takes minutes, so a parallel launcher may have
    overwritten this launcher's instance claim for the same version. Whoever
    the current registry names (live ``starting_pid``/``es_pid`` or bound port)
    creates; everyone else attaches. Returns ``(registry, shared)``.
    """
    registry = load_registry()
    instance = es_instances(registry).get(version)
    if isinstance(instance, dict) and instance.get("starting_pid") == os.getpid():
        return registry, {"key": version, "create": True, "instance": instance}
    usable = usable_es_instance(registry, version)
    if usable is not None:
        print(
            f",kbn-stack: another launcher started shared ES {version} during bootstrap; attaching to it.",
            flush=True,
        )
        return registry, {"key": version, "create": False, "instance": usable}
    return registry, claim_shared_es(registry, version, worktree, started_by, exclude_slot)


def reclaim_dead_es_instances(registry: dict) -> bool:
    """Drop shared ES entries whose process and port are both gone.

    A live shared ES with zero attached worktrees is intentionally kept: it is
    exactly what the next compatible start reuses. Returns True on change.
    """
    changed = False
    instances = es_instances(registry)
    for version, instance in list(instances.items()):
        if es_instance_state(instance) != "stale":
            continue
        print(
            f",kbn-stack: reclaiming shared ES {version} (slot {instance.get('slot')}): no live process or port listener.",
            flush=True,
        )
        del instances[version]
        changed = True
    if changed:
        save_registry(registry)
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
    kbn_alive, es_alive = slot_liveness(entry)
    owned = kbn_alive or entry_has_live_processes(entry)
    if entry.get("backend") == "serverless":
        # slot_liveness sees only slot 0's HTTP port; a half-dead serverless
        # stack may keep es02 alive on the rest of the band.
        if owned or serverless_band_alive(registry):
            fail("this worktree's previous serverless stack is still running; stop it first with `,kbn-stack --stop`.")
        return
    if owned:
        # Owned outranks port liveness: a bootstrapping stack (launcher alive,
        # nothing bound yet) must not be overwritten and orphaned.
        # No --isolated-es hint: an isolated rerun reuses this worktree's slot
        # and would fail the ES-port preflight against this same stack.
        fail(
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
        kill_pid_group(es_pid)
    _, es_http = entry_ports(entry)
    kill_port_listeners(es_http)


def stop_es_instance(version: str, instance: dict) -> None:
    """Kill a shared ES instance's process group and port listeners."""
    print(f",kbn-stack: stopping shared ES {version} (slot {instance.get('slot')})", flush=True)
    es_pid = instance.get("es_pid")
    if isinstance(es_pid, int):
        kill_pid_group(es_pid)
    es_http = instance.get("es_http")
    if isinstance(es_http, int):
        kill_port_listeners(es_http)


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


def band_listener_owned(registry: dict, slot: int, port: int) -> bool:
    """True when the ``port`` listener is identity-verified as another stack's.

    Only a registered non-serverless stack or shared instance on the same
    ``slot`` whose recorded pid's process tree owns the listener explains it
    away. Owner liveness alone is not enough: a bootstrapping launcher on the
    slot has not bound anything yet, so a listener there is still a surviving
    serverless container.
    """
    for _, entry in worktree_entries(registry):
        if entry.get("backend") == "serverless" or entry.get("es_key") is not None:
            continue
        if entry.get("slot") != slot:
            continue
        for key in ("es_pid", "started_by_pid"):
            pid = entry.get(key)
            if isinstance(pid, int) and listener_identity_ok(port, pid)[0]:
                return True
    for instance in es_instances(registry).values():
        if instance.get("slot") != slot:
            continue
        es_pid = instance.get("es_pid")
        if isinstance(es_pid, int) and listener_identity_ok(port, es_pid)[0]:
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
    for slot in SERVERLESS_SNAPSHOT_CONFLICT_SLOTS:
        cfg = derive(slot)
        for port in (cfg["es_http"], cfg["es_transport"]):
            if not port_listener_pids(port):
                continue
            if band_listener_owned(registry, slot, port):
                continue
            return True
    return False


def kill_port_listeners(port: int | None) -> bool:
    """SIGTERM then SIGKILL the process group of each listener on ``port``.

    Interactive stacks are not our children, so recorded pids are missing; the
    port owner is the inner Kibana, a group *member*. Signaling that pid alone
    lets Kibana close the port, log "All plugins stopped", and hang while yarn
    and the rspack worker stay up. Killing the listener's process group reaps
    the whole tree. Returns True if it found a listener.
    """
    if port is None:
        return False
    pids: list[int] = []
    seen_pids: set[int] = set()
    for pid in port_listener_pids(port):
        if pid in seen_pids:
            continue
        seen_pids.add(pid)
        pids.append(pid)
    if not pids:
        return False
    seen_pgids: set[int] = set()
    for pid in pids:
        try:
            pgid = os.getpgid(pid)
        except (ProcessLookupError, PermissionError):
            kill_pid_group(pid)
            continue
        if pgid in seen_pgids:
            continue
        seen_pgids.add(pgid)
        kill_pid_group(pid)
    return True


def pid_is_zombie(pid: int) -> bool:
    """True when ``ps`` reports ``pid`` in state Z (defunct)."""
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip().startswith("Z")


def pid_alive(pid: object) -> bool:
    """True when ``pid`` refers to a live, non-zombie process (signal 0 probe).

    PermissionError means the pid exists but belongs to another user, so it
    counts as alive. Pid reuse can make a stale entry look alive; that only
    leaves a slot occupied (the next worktree takes a higher slot), which is a
    safe failure mode compared to reclaiming a live stack. Zombies are not
    alive: they cannot hold ports and must not block SIGKILL wait loops.
    """
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OverflowError):
        return False
    except PermissionError:
        return True
    return not pid_is_zombie(pid)


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


def entry_has_live_processes(entry: dict, ignored_pid: int | None = None) -> bool:
    """True when any process recorded for this stack is still running.

    ``started_by_pid`` is the ,kbn-stack launcher: for interactive stacks it
    streams ES logs for the stack's whole lifetime, and for detached stacks it
    lives through the entire bootstrap (yarn kbn bootstrap + ES setup + Kibana
    readiness poll). ``kbn_pid``/``es_pid`` cover detached stacks after the
    launcher has returned. Any of them alive means the stack is active or still
    bootstrapping, so its ports being closed is not evidence of death.
    """
    for key in ("started_by_pid", "kbn_pid", "es_pid"):
        pid = entry.get(key)
        if pid != ignored_pid and pid_alive(pid):
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
    instance = es_instances(registry).get(es_key)
    shared_alive = isinstance(instance, dict) and es_instance_state(instance) == "ready"
    if entry.get("ready") is True and kbn_alive and shared_alive:
        return "ready"
    if entry.get("ready") is not True and process_alive:
        return "starting"
    if process_alive or kbn_alive:
        return "degraded"
    return "stale"


def run_status(registry: dict) -> int:
    """Print every registered stack without mutating registry state."""
    stacks = worktree_entries(registry)
    instances = es_instances(registry)
    if not stacks and not instances:
        print(",kbn-stack: no registered stacks.", flush=True)
        return 0

    rows = []
    sort_key = lambda item: (item[1].get("slot") if isinstance(item[1].get("slot"), int) else sys.maxsize, item[0])
    for worktree, entry in sorted(stacks, key=sort_key):
        kbn_alive, es_alive = slot_liveness(entry)
        process_alive = entry_has_live_processes(entry)
        state = entry_state(registry, entry, process_alive, kbn_alive, es_alive)
        es_key = entry.get("es_key")
        if es_key is not None:
            instance = instances.get(es_key)
            shared_alive = isinstance(instance, dict) and es_instance_state(instance) == "ready"
            es_cell = f"shared:{'up' if shared_alive else 'down'}"
        else:
            es_cell = "up" if es_alive else "down"
        rows.append(
            (
                state,
                str(entry.get("slot", "-")),
                str(entry.get("backend", "unknown")),
                stack_started_by(entry),
                "up" if kbn_alive else "down",
                es_cell,
                str(entry.get("branch", "unknown")),
                worktree,
            )
        )
    for version, instance in sorted(instances.items(), key=sort_key):
        state = es_instance_state(instance)
        attached = attached_worktrees(registry, version)
        rows.append(
            (
                state,
                str(instance.get("slot", "-")),
                "shared-es",
                stack_started_by(instance),
                "-",
                "up" if state == "ready" else "down",
                f"v{version}",
                f"({len(attached)} attached)",
            )
        )

    headers = ("STATE", "SLOT", "BACKEND", "OWNER", "KIBANA", "ES", "BRANCH", "WORKTREE")
    widths = [max(len(str(value)) for value in column) for column in zip(headers, *rows)]
    for row in (headers, *rows):
        print("  ".join(str(value).ljust(width) for value, width in zip(row, widths)).rstrip(), flush=True)
    return 0


def run_prune(registry: dict, *, ignored_pid: int | None = None, quiet: bool = False) -> int:
    """Remove only entries whose recorded processes and owned ports are all dead."""
    stale_worktrees = []
    for worktree, entry in worktree_entries(registry):
        kbn_alive, es_alive = slot_liveness(entry)
        process_alive = entry_has_live_processes(entry, ignored_pid=ignored_pid)
        if entry_state(registry, entry, process_alive, kbn_alive, es_alive) == "stale":
            stale_worktrees.append(worktree)

    for worktree in stale_worktrees:
        del registry[worktree]

    instances = es_instances(registry)
    stale_instances = [version for version, instance in instances.items() if es_instance_state(instance) == "stale"]
    for version in stale_instances:
        del instances[version]

    if stale_worktrees or stale_instances:
        save_registry(registry)

    if not quiet:
        if stale_worktrees or stale_instances:
            print(f",kbn-stack: pruned {len(stale_worktrees) + len(stale_instances)} stale stack(s):", flush=True)
            for worktree in sorted(stale_worktrees):
                print(f"  {worktree}", flush=True)
            for version in sorted(stale_instances):
                print(f"  shared ES {version}", flush=True)
        else:
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
    for worktree, entry in worktree_entries(registry):
        if worktree == current_worktree:
            continue
        if entry.get("backend") == "serverless":
            continue
        if not isinstance(entry.get("slot"), int):
            continue
        if entry_has_live_processes(entry):
            continue
        if entry.get("es_key") is not None:
            # A shared attachee owns only its Kibana half; the shared ES has its
            # own reclaim path. Drop the entry only when the Kibana is gone too.
            kbn_alive, _ = slot_liveness(entry)
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


def taken_slots(registry: dict, *, exclude_worktree: str | None = None) -> set[int]:
    """Slots reserved by worktree stacks and shared ES instances."""
    taken = {
        entry["slot"]
        for key, entry in worktree_entries(registry)
        if key != exclude_worktree and isinstance(entry.get("slot"), int)
    }
    taken |= {instance["slot"] for instance in es_instances(registry).values() if isinstance(instance.get("slot"), int)}
    return taken


def allocate_slot(registry: dict, worktree: str, forced: int | None) -> int:
    if forced is not None:
        if forced < 0:
            fail("--slot must be >= 0")
        return forced
    existing = registry.get(worktree)
    if existing and isinstance(existing.get("slot"), int):
        return existing["slot"]
    taken = taken_slots(registry, exclude_worktree=worktree)
    slot = 0
    while slot in taken:
        slot += 1
    return slot


def allocate_es_slot(registry: dict, extra_taken: set[int]) -> int:
    """Lowest free slot for a new shared ES instance (only its ES ports are used).

    While a serverless stack is registered its containers own the low ES port
    band, so the serverless-conflict slots are excluded up front: the instance
    preflight probes only the ES HTTP port and would miss a transport collision.
    """
    taken = taken_slots(registry) | extra_taken
    if any(entry.get("backend") == "serverless" for _, entry in worktree_entries(registry)):
        taken |= set(SERVERLESS_SNAPSHOT_CONFLICT_SLOTS)
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
    for flag in resolved_kbn_flags(args):
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
        f"node.name=slot{cfg.get('es_slot', cfg['slot'])}",
        "-E",
        f"http.port={cfg['es_http']}",
        "-E",
        f"transport.port={cfg['es_transport']}",
        "-E",
        "discovery.type=single-node",
        "-E",
        f"path.data={data_path}",
        "-E",
        MERGE_DISK_WATERMARK,
    ]
    for flag in args.es_flags:
        cmd += ["-E", flag]
    return cmd


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


def wrapped_kibana_command(kbn_cmd: str) -> str:
    """Wrap the yarn start command so its exit triggers silent registry pruning."""
    return shlex.join([sys.executable, str(Path(__file__).resolve()), "--run-with-prune", *shlex.split(kbn_cmd)])


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
    flip the registry ``ready`` flag so an agent running ``/k-deep-review`` from the
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
                kbn_cmd = wrapped_kibana_command(kbn_cmd)
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


def spawn_background(cmd: list[str], logfile: Path, worktree: str, env: dict[str, str] | None = None) -> int:
    """Start a detached process writing combined output to logfile; return its pid."""
    handle = logfile.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=handle,
        stderr=subprocess.STDOUT,
        cwd=worktree,
        start_new_session=True,
        env=env,
    )
    return proc.pid


def run_foreground_es(es_cmd: list[str], logfile: Path, env: dict[str, str] | None = None) -> int:
    """Stream interactive Elasticsearch and prune stale entries after it exits."""
    with logfile.open("w", encoding="utf-8") as log_handle:
        try:
            proc = subprocess.Popen(es_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            assert proc.stdout is not None
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log_handle.write(line)
                log_handle.flush()
            return proc.wait()
        finally:
            run_prune(load_registry(), ignored_pid=os.getpid(), quiet=True)


def follow_es_log(logfile: Path, es_pid: int) -> int:
    """Stream a background shared ES's log in the foreground pane.

    The shared ES must outlive this pane (other worktrees may attach), so it is
    not a foreground child: Ctrl-C detaches from the log and leaves ES running.
    Returns non-zero when the ES process itself exits.
    """
    print(
        f",kbn-stack: shared ES runs in the background (pid {es_pid}); following {logfile}.\n"
        "            Ctrl-C detaches from the log without stopping ES; stop with `,kbn-stack --stop`.",
        flush=True,
    )
    try:
        with logfile.open("r", encoding="utf-8", errors="replace") as handle:
            while True:
                line = handle.readline()
                if line:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    continue
                if not pid_alive(es_pid):
                    print(f",kbn-stack: shared ES process (pid {es_pid}) exited.", flush=True)
                    return 1
                time.sleep(0.5)
    except KeyboardInterrupt:
        print(
            f"\n,kbn-stack: detached from the ES log; shared ES (pid {es_pid}) keeps running. "
            "Stop it with `,kbn-stack --stop` (last attached worktree stops it). "
            "If Kibana was not launched yet, rerun ,kbn-stack to attach.",
            flush=True,
        )
        return 0
    finally:
        run_prune(load_registry(), ignored_pid=os.getpid(), quiet=True)


def run_interactive_attach(
    cfg: dict,
    worktree: str,
    kbn_cmd: str,
    target_pane: str | None,
    es_logfile: Path,
    shared: dict,
) -> int:
    """Interactive reuse of a live shared ES: launch only this worktree's Kibana."""
    print(f",kbn-stack: reusing shared ES {shared['key']} -> {cfg['es_url']}", flush=True)
    wait_for_shared_es(shared, es_logfile)
    ensure_trial_license(cfg["es_url"])
    launch = wrapped_kibana_command(kbn_cmd)
    if not target_pane:
        print(f"\n,kbn-stack: shared ES ready. Start Kibana with:\n  {launch}\n", flush=True)
        return 0
    subprocess.run(["tmux", "send-keys", "-t", target_pane, launch, "C-m"], check=False)
    print(f",kbn-stack: Kibana starting in pane {target_pane}; waiting for {cfg['kbn_url']}/api/status", flush=True)
    if kibana_ready(cfg["kbn_url"], timeout=600):
        mark_ready(worktree, True)
        print(
            f",kbn-stack: ready. Kibana -> {cfg['kbn_url']} (cookie {cfg['cookie_name']}), ES -> {cfg['es_url']}",
            flush=True,
        )
        return 0
    print(
        f",kbn-stack: Kibana did not answer /api/status within 600s (see pane {target_pane}). "
        "If migrations clash with the shared ES, rerun with --isolated-es.",
        flush=True,
    )
    return 1


def run_with_prune(command: list[str]) -> int:
    """Run a foreground command and silently prune after normal exit or Ctrl-C."""
    if not command:
        fail("--run-with-prune requires a command")
    try:
        return subprocess.run(command, check=False).returncode
    except KeyboardInterrupt:
        return 130
    finally:
        run_prune(load_registry(), quiet=True)


def wait_for_shared_es(shared: dict, es_logfile: Path) -> None:
    """Block until an attached shared ES is identity-verified ready.

    Every exit requires ``es_instance_state(...) == "ready"``. The setup
    trigger alone is not proof: the instance log survives an ES death, so a
    stale trigger plus a foreign listener on the recorded port must fail the
    attach instead of starting Kibana against a squatter.
    """
    if es_instance_state(shared["instance"]) == "ready":
        return
    print(f",kbn-stack: waiting for shared ES {shared['key']} to finish setup -> {es_logfile}", flush=True)
    if not wait_for_trigger(es_logfile, timeout=600):
        fail(
            f"shared ES {shared['key']} did not become ready within 600s (see {es_logfile}). "
            "Rerun once it is up, or rerun with --isolated-es for a dedicated ES."
        )
    deadline = time.monotonic() + SHARED_ES_CONFIRM_TIMEOUT
    while time.monotonic() < deadline:
        instance = es_instances(load_registry()).get(shared["key"])
        if (
            isinstance(instance, dict)
            # The caller's cfg is wired to the claimed instance's endpoints; a
            # replacement on another slot being ready proves nothing for it.
            and instance.get("slot") == shared["instance"].get("slot")
            and es_instance_state(instance) == "ready"
        ):
            return
        time.sleep(1)
    fail(
        f"shared ES {shared['key']} logged setup completion but the claimed instance is not "
        "identity-verified on its port (stale trigger, foreign listener, or the instance was "
        "replaced mid-setup). Run `,kbn-stack --prune`, then rerun, or rerun with --isolated-es "
        "for a dedicated ES."
    )


def run_detached(
    args: argparse.Namespace,
    cfg: dict,
    worktree: str,
    data_path: Path,
    es_logfile: Path,
    kbn_cmd: str,
    shared: dict | None = None,
) -> int:
    """Agent mode: background ES + Kibana, wait until ready, record readiness, return.

    Every registry write here happens minutes after the launcher's snapshot was
    loaded, so all of them go through the reload-and-merge helpers.
    """
    kbn_logfile = Path(f"/tmp/kbn-slot{cfg['slot']}.log")

    if shared is not None and not shared["create"]:
        print(f",kbn-stack: reusing shared ES {shared['key']} -> {cfg['es_url']}", flush=True)
        wait_for_shared_es(shared, es_logfile)
        es_pid = None
    else:
        es_env = None if args.es == "serverless" else snapshot_es_env(args.es_heap)
        es_pid = spawn_background(es_command(args, cfg, data_path), es_logfile, worktree, env=es_env)
        print(f",kbn-stack: Elasticsearch starting (pid {es_pid}) -> {es_logfile}", flush=True)
        if shared is not None:
            # Record the pid immediately so parallel launchers classify this
            # instance as starting rather than stale while setup runs.
            update_es_instance(shared["key"], es_pid=es_pid)

        if not wait_for_trigger(es_logfile, timeout=600):
            if shared is None:
                update_worktree_entry(worktree, es_pid=es_pid)
            fail(f"Elasticsearch did not finish setup within 600s (see {es_logfile})")

    ensure_trial_license(cfg["es_url"])

    kbn_pid = spawn_background(shlex.split(kbn_cmd), kbn_logfile, worktree)
    print(f",kbn-stack: Kibana starting (pid {kbn_pid}) -> {kbn_logfile}", flush=True)

    ready = kibana_ready(cfg["kbn_url"], timeout=600)
    identity_ok, squatters = (False, [])
    if ready:
        identity_ok, squatters = listener_identity_ok(cfg["kbn_port"], kbn_pid)
    fields: dict[str, object] = {"kbn_pid": kbn_pid, "kbn_log": str(kbn_logfile), "ready": ready and identity_ok}
    if shared is None and es_pid is not None:
        fields["es_pid"] = es_pid
    update_worktree_entry(worktree, **fields)

    if not ready:
        hint = ""
        if shared is not None:
            hint = " If the log shows saved-object migration failures against the shared ES, rerun with --isolated-es."
        fail(f"Kibana did not answer /api/status within 600s (see {kbn_logfile}).{hint}")
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


def _live_group_members(pgid: int) -> list[int]:
    """Pids in ``pgid`` that are not zombies (empty if the group is gone)."""
    result = subprocess.run(
        ["ps", "-axo", "pid=,pgid=,stat="],
        capture_output=True,
        text=True,
        check=False,
    )
    members: list[int] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            group = int(parts[1])
        except ValueError:
            continue
        if group != pgid or parts[2].startswith("Z"):
            continue
        members.append(pid)
    return members


def _signal_pid(pid: int, sig: int) -> None:
    try:
        os.kill(pid, sig)
    except (ProcessLookupError, PermissionError, OverflowError):
        return


def kill_pid_group(pid: int) -> None:
    """SIGTERM then SIGKILL the process group of ``pid``.

    Detached stacks start with start_new_session=True, so the recorded pid is the
    group leader. Interactive stacks are stopped via a port listener which is a
    group member (the inner Kibana); getpgid still names the yarn/python group.
    After SIGTERM, wait for live (non-zombie) members, then SIGKILL the group and
    any survivors. A Kibana that closes its port and hangs still dies.
    """
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    except PermissionError:
        _signal_pid(pid, signal.SIGTERM)
        time.sleep(min(KILL_GRACE_SECONDS, 0.2))
        _signal_pid(pid, signal.SIGKILL)
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        _signal_pid(pid, signal.SIGTERM)
        time.sleep(min(KILL_GRACE_SECONDS, 0.2))
        _signal_pid(pid, signal.SIGKILL)
        return
    deadline = time.monotonic() + KILL_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not _live_group_members(pgid):
            return
        time.sleep(KILL_POLL_SECONDS)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    for member in _live_group_members(pgid):
        _signal_pid(member, signal.SIGKILL)


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
    ``reclaim_ports`` set (``--stop`` and ``--stop-all``), also kill whatever
    still listens on this slot's Kibana/ES ports by signaling the listener
    process group, so a Kibana that closes the port and hangs still gets SIGKILL.
    Serverless preflight leaves reclaim off so a snapshot stack on those ports is
    not killed as a side effect.
    """
    slot = entry.get("slot")
    started_by = stack_started_by(entry)
    shared = entry.get("es_key") is not None
    if started_by == STARTED_BY_USER and not allow_user_owned:
        print(f",kbn-stack: leaving user-owned slot {slot} ({worktree}) running.", flush=True)
        return False
    print(f",kbn-stack: stopping slot {slot} ({worktree}, started_by={started_by})", flush=True)
    stopped = False
    recorded = False
    for key in ("kbn_pid", "es_pid"):
        pid = entry.get(key)
        if isinstance(pid, int):
            kill_pid_group(pid)
            recorded = True
            stopped = True
    if entry.get("backend") == "serverless":
        docker_kill_serverless()
        stopped = True
    if reclaim_ports and entry.get("backend") != "serverless":
        kbn_port, es_http = entry_ports(entry)
        port_stopped = False
        if kill_port_listeners(kbn_port):
            port_stopped = True
            stopped = True
        # A shared attachee does not own its slot's ES ports (the shared ES has
        # its own slot and teardown path), so only isolated stacks reclaim them.
        if not shared and kill_port_listeners(es_http):
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


def release_shared_es(registry: dict, es_key: str | None) -> None:
    """Refcounted shared-ES teardown after a worktree entry was removed.

    The shared ES keeps running while any other registered worktree references
    it; the last detach stops it (an unreferenced ES would silently keep a JVM
    alive, which is exactly the waste sharing exists to avoid).
    """
    if es_key is None:
        return
    instance = es_instances(registry).get(es_key)
    if instance is None:
        return
    remaining = attached_worktrees(registry, es_key)
    if remaining:
        print(
            f",kbn-stack: left shared ES {es_key} running ({len(remaining)} other stack(s) attached).",
            flush=True,
        )
        return
    stop_es_instance(es_key, instance)
    del es_instances(registry)[es_key]


def run_stop(worktree: str, registry: dict) -> int:
    entry = registry.get(worktree)
    if entry is None:
        fail(f"no registered stack for this worktree ({worktree})")
    stopped = stop_entry(worktree, entry, reclaim_ports=True)
    del registry[worktree]
    release_shared_es(registry, entry.get("es_key"))
    save_registry(registry)
    if not stopped:
        # Nothing recorded and nothing listening on this slot's ports: the stack
        # is already gone. Drop the stale entry so the slot is freed.
        print(",kbn-stack: no live stack found; removed stale registry entry.", flush=True)
        return 0
    print(",kbn-stack: stopped and removed registry entry.", flush=True)
    return 0


def run_stop_all(registry: dict) -> int:
    stacks = worktree_entries(registry)
    instances = es_instances(registry)
    if not stacks and not instances:
        print(",kbn-stack: no registered stacks.", flush=True)
        return 0
    count = len(stacks) + len(instances)
    for worktree, entry in stacks:
        stop_entry(worktree, entry, reclaim_ports=True)
    for version, instance in list(instances.items()):
        stop_es_instance(version, instance)
    save_registry({})
    print(f",kbn-stack: stopped {count} stack(s) and cleared the registry.", flush=True)
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
    for worktree, entry in worktree_entries(registry):
        if worktree == current_worktree:
            continue
        backend = entry.get("backend")
        if backend == "serverless":
            existing_started_by = stack_started_by(entry)
            if new_started_by == STARTED_BY_AGENT and existing_started_by == STARTED_BY_USER:
                blockers.append((worktree, entry.get("slot"), "user-owned serverless"))
                continue
            serverless_to_stop.append((worktree, entry))
        elif (
            backend == "snapshot"
            and entry.get("es_key") is None
            and entry.get("slot") in SERVERLESS_SNAPSHOT_CONFLICT_SLOTS
        ):
            blockers.append((worktree, entry.get("slot"), "snapshot port conflict"))
    for version, instance in es_instances(registry).items():
        if instance.get("slot") in SERVERLESS_SNAPSHOT_CONFLICT_SLOTS and es_instance_state(instance) != "stale":
            blockers.append((f"shared ES {version}", instance.get("slot"), "shared ES port conflict"))
    if blockers:
        listed = "; ".join(f"{wt} (slot {s}, {reason})" for wt, s, reason in blockers)
        fail(
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
        stop_entry(worktree, entry, allow_user_owned=new_started_by == STARTED_BY_USER)
        del registry[worktree]
    save_registry(registry)


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
        "kbn_flags": resolved_kbn_flags(args),
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


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    actions = [
        flag
        for flag, enabled in (
            ("--status", args.status),
            ("--prune", args.prune),
            ("--run-with-prune", args.run_with_prune is not None),
            ("--stop", args.stop),
            ("--stop-all", args.stop_all),
        )
        if enabled
    ]
    if len(actions) > 1:
        fail(f"{', '.join(actions)} are mutually exclusive")

    if args.status:
        return run_status(load_registry())

    if args.prune:
        return run_prune(load_registry())

    if args.run_with_prune is not None:
        return run_with_prune(args.run_with_prune)

    if args.stop_all:
        return run_stop_all(load_registry())

    if args.stop:
        return run_stop(resolve_worktree(), load_registry())

    worktree = resolve_worktree()
    branch = current_branch()
    started_by = STARTED_BY_AGENT if args.detach else STARTED_BY_USER

    registry = load_registry()

    share_version = None
    if share_eligible(args):
        share_version = read_worktree_version(worktree)
        if share_version is None:
            print(",kbn-stack: cannot read this worktree's package.json version; starting an isolated ES.", flush=True)

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
            reclaim_dead_es_instances(registry)
        slot = allocate_slot(registry, worktree, args.slot)
    cfg = derive(slot)
    cfg["slot"] = slot

    shared = None
    if share_version is not None:
        clear_previous_stack_for_shared_es(registry, worktree)
        shared = claim_shared_es(registry, share_version, worktree, started_by, exclude_slot=slot)
        apply_shared_es(cfg, shared["instance"])
        ensure_ports_free(cfg, check_es=False)
        if shared["create"]:
            icfg = derive(shared["instance"]["slot"])
            icfg["slot"] = shared["instance"]["slot"]
            ensure_ports_free(icfg, check_kbn=False)
        data_name = shared["instance"]["data"]
        logfile = Path(shared["instance"]["log"])
    else:
        ensure_ports_free(cfg)
        data_name = sanitize(args.data) if args.data else sanitize(branch)
        logfile = Path(f"/tmp/es-slot{slot}.log")

    data_path = ES_DATA_ROOT / data_name
    kbn_cmd = kibana_command(args, cfg)
    target_pane = None if args.detach else tmux_target_pane(worktree)
    mode = start_mode(args, target_pane)

    registry[worktree] = build_worktree_entry(args, cfg, branch, data_name, logfile, started_by, mode, share_version)
    save_registry(registry)

    groups_label = ",".join(args.plugin_groups) or "all"
    heap_label = args.es_heap if args.es == "snapshot" else "serverless-default"
    if shared is None:
        es_label = f"{cfg['es_url']}  (isolated)" if args.es == "snapshot" else cfg["es_url"]
    else:
        es_label = f"{cfg['es_url']}  (shared {share_version}, {'new' if shared['create'] else 'reused'})"
    print(
        f",kbn-stack: worktree={worktree}\n"
        f"            slot={slot} backend={args.es} data={data_name}\n"
        f"            groups  -> {groups_label}\n"
        f"            es-heap -> {heap_label}\n"
        f"            Kibana  -> {cfg['kbn_url']}  (cookie {cfg['cookie_name']})\n"
        f"            ES      -> {es_label}\n",
        flush=True,
    )

    subprocess.run(["yarn", "kbn", "bootstrap"], check=True)

    if shared is not None and shared["create"]:
        # Bootstrap takes minutes: a parallel launcher may have won the create
        # race for this version meanwhile. Settle it and refresh the entry.
        registry, shared = reconfirm_shared_claim(share_version, worktree, started_by, slot)
        apply_shared_es(cfg, shared["instance"])
        data_name = shared["instance"]["data"]
        data_path = ES_DATA_ROOT / data_name
        logfile = Path(shared["instance"]["log"])
        kbn_cmd = kibana_command(args, cfg)
        registry[worktree] = build_worktree_entry(
            args, cfg, branch, data_name, logfile, started_by, mode, share_version
        )
        save_registry(registry)

    if shared is None:
        # Clear stale output before either trigger reader starts. Both readers
        # begin at byte zero, so they cannot miss a trigger written before they
        # open. (claim_shared_es already truncated a new shared instance's log.)
        logfile.write_text("", encoding="utf-8")

    if args.detach:
        return run_detached(args, cfg, worktree, data_path, logfile, kbn_cmd, shared=shared)

    if shared is not None and not shared["create"]:
        return run_interactive_attach(cfg, worktree, kbn_cmd, target_pane, logfile, shared)

    # The log already exists so the watcher never races a missing path.
    watcher = threading.Thread(
        target=start_kibana_on_trigger,
        args=(logfile, cfg["es_url"], kbn_cmd, target_pane, worktree, cfg["kbn_url"]),
        daemon=True,
    )
    watcher.start()

    es_env = None if args.es == "serverless" else snapshot_es_env(args.es_heap)
    if shared is not None:
        # A shared ES must outlive this pane (other worktrees attach to it), so
        # it runs detached even for interactive starts; follow its log instead.
        es_pid = spawn_background(es_command(args, cfg, data_path), logfile, worktree, env=es_env)
        update_es_instance(shared["key"], es_pid=es_pid)
        print(f",kbn-stack: Elasticsearch starting (pid {es_pid}) -> {logfile}", flush=True)
        return follow_es_log(logfile, es_pid)
    return run_foreground_es(es_command(args, cfg, data_path), logfile, env=es_env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
