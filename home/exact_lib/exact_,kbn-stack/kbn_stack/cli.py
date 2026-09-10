"""Argument parsing and the flag-derived settings (plugin groups, ES heap, sharing eligibility).

``-E key=value`` passes an extra Elasticsearch setting through to the snapshot
backend; ``-K key=value`` passes an extra Kibana CLI setting through to
``<pm> start`` as ``--key=value`` (repeatable). Snapshot starts also pass
``-E indices.merge.disk.watermark.high=2gb`` (absolute merge-disk floor) before
user ``-E`` flags, so a later ``-E`` of the same key overrides. Snapshot ES
also sets ``ES_JAVA_OPTS -Xms1g -Xmx1g`` (override with ``--es-heap 1536m``).
Kibana defaults to ``--groups platform`` (``plugins.allowlistPluginGroups``);
``--groups all`` loads every group. Restart the stack to change groups. Use
``-K`` to start a stack with the runtime config a change under review needs
in one shot, e.g. ``-K xpack.index_management.dev.enableSemanticField=true``,
instead of starting a default stack and restarting Kibana afterwards.
"""

from __future__ import annotations

import argparse
import os

from kbn_stack import config


def parse_plugin_groups(raw: str) -> tuple[str, ...]:
    parts = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("expected all or a comma-separated group list")
    if parts == ["all"]:
        return ()
    if "all" in parts:
        raise argparse.ArgumentTypeError("--groups all cannot be combined with named groups")
    unknown = [part for part in parts if part not in config.PLUGIN_GROUPS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown plugin group(s): {', '.join(unknown)}. Use all or: {', '.join(config.PLUGIN_GROUPS)}"
        )
    seen: list[str] = []
    for part in parts:
        if part not in seen:
            seen.append(part)
    return tuple(seen)


def parse_es_heap(raw: str) -> str:
    if not config.HEAP_SIZE_RE.fullmatch(raw):
        raise argparse.ArgumentTypeError("expected a JVM size like 1g or 1536m")
    return raw


def resolved_kbn_flags(args: argparse.Namespace) -> list[str]:
    flags = list(args.kbn_flags)
    if any(flag.startswith(config.ALLOWLIST_KEY) for flag in flags):
        return flags
    injected = [f"{config.ALLOWLIST_KEY}.{index}={group}" for index, group in enumerate(args.plugin_groups)]
    return injected + flags


def es_java_opts(heap: str, existing: str = "") -> str:
    kept = [token for token in existing.split() if not token.lower().startswith(("-xms", "-xmx"))]
    return " ".join((f"-Xms{heap}", f"-Xmx{heap}", *kept))


def snapshot_es_env(heap: str) -> dict[str, str]:
    env = os.environ.copy()
    env["ES_JAVA_OPTS"] = es_java_opts(heap, env.get("ES_JAVA_OPTS", ""))
    return env


def es_environment(args: argparse.Namespace) -> dict[str, str] | None:
    """Environment for the ES launcher: heap-pinned for snapshot, inherited for serverless."""
    return None if args.es == "serverless" else snapshot_es_env(args.es_heap)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=",kbn-stack",
        description="Spin up an ES + Kibana dev stack for the current worktree (default snapshot starts share one ES per version).",
    )
    parser.add_argument(
        "--es",
        choices=config.BACKENDS,
        default="snapshot",
        help="Elasticsearch backend: snapshot (stateful JVM, default) or serverless (Docker).",
    )
    parser.add_argument(
        "--project-type",
        choices=config.PROJECT_TYPES,
        default="es",
        help="Kibana serverless project type (translated to the Elasticsearch project type). Default: es.",
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
        "--share-es",
        dest="share_es",
        action="store_true",
        help=(
            "Attach to the shared ES even though the branch diff touches saved-object "
            "or ES-setup definitions (which otherwise starts an isolated ES)."
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
            "Kibana port), plus dead shared ES instances. Never stops a worktree stack; "
            "the only process it stops is a shared ES that has had no Kibana client for a minute."
        ),
    )
    parser.add_argument("--run-with-prune", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    parser.add_argument(
        "--reap-shared-es", dest="reap_shared_es", metavar="VERSION", default=None, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--groups",
        dest="plugin_groups",
        type=parse_plugin_groups,
        default=parse_plugin_groups(config.DEFAULT_PLUGIN_GROUPS),
        metavar="LIST",
        help=(
            "Kibana plugin groups to load (comma-separated). Default: platform. "
            "Use --groups all for every group. Named groups: "
            + ", ".join(config.PLUGIN_GROUPS)
            + ". Restart the stack to change this."
        ),
    )
    parser.add_argument(
        "--es-heap",
        dest="es_heap",
        type=parse_es_heap,
        default=config.DEFAULT_ES_HEAP,
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
            "Extra Kibana setting passed to `pnpm start`/`yarn start` as --key=value (repeatable). "
            "Use it to start a stack with the runtime config a change under review "
            "needs, e.g. -K xpack.index_management.dev.enableSemanticField=true."
        ),
    )
    args = parser.parse_args(argv)
    if args.es == "serverless" and args.es_heap != config.DEFAULT_ES_HEAP:
        config.fail("--es-heap applies to snapshot ES only; serverless docker already pins 1g")
    if args.share_es and args.isolated_es:
        config.fail("--share-es and --isolated-es are mutually exclusive")
    return args


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
        and args.es_heap == config.DEFAULT_ES_HEAP
        and args.data is None
    )


def start_mode(args: argparse.Namespace, target_pane: str | None) -> str:
    if args.detach:
        return "agent-detach"
    if target_pane:
        return "interactive-tmux"
    return "manual-command"
