#!/usr/bin/env python3
"""Spin up an ES + Kibana dev stack for the current Kibana worktree.

Entrypoint only: parses flags, settles slot/shared-ES/serverless preflight, records
the registry entry, and hands off to ``kbn_stack.launch``. Each ``kbn_stack``
module documents the rules it owns. Usage: ``,kbn-stack --help``; behavior
reference: ``docs/topics/workflow/custom-commands/catalog.md`` and the
``k-kbn-stack`` skill (``~/.agents/skills/k-kbn-stack/``).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from kbn_stack import checkout, cli, config, launch, lifecycle, liveness, shared_es, slots, store, trial_license


def resolve_share_version(args: argparse.Namespace, worktree: str) -> str | None:
    """The shared-ES version this start attaches to, or None for an isolated ES.

    Flags decide first (``cli.share_eligible``); then the branch diff: a change
    to saved-object definitions, migrations, or cluster-wide ES setup would
    mutate the shared cluster under other worktrees, so it isolates unless
    ``--share-es`` insists.
    """
    if not cli.share_eligible(args):
        if args.share_es:
            print(
                ",kbn-stack: --share-es has no effect here: -E, --data, or a non-default --es-heap keeps an isolated ES.",
                flush=True,
            )
        return None
    version = checkout.read_worktree_version(worktree)
    if version is None:
        print(",kbn-stack: cannot read this worktree's package.json version; starting an isolated ES.", flush=True)
        return None
    if args.share_es:
        return version
    signals = checkout.isolation_signals(worktree)
    if not signals:
        return version
    shown = ", ".join(signals[:3]) + (f", +{len(signals) - 3} more" if len(signals) > 3 else "")
    print(
        f",kbn-stack: this branch changes saved-object/ES-setup definitions ({shown}); "
        "starting an isolated ES so the shared cluster stays untouched. Pass --share-es to attach anyway.",
        flush=True,
    )
    return None


def resolve_slot(args: argparse.Namespace, registry: dict, worktree: str, started_by: str) -> int:
    """Settle the backend's exclusivity rules and pick this worktree's slot."""
    if args.es == "serverless":
        lifecycle.stop_existing_serverless(registry, worktree, started_by)
        # Serverless is single-instance and its Docker containers (es01/es02) bind
        # fixed ports, so pin it to slot 0 for deterministic, matching ports.
        if args.slot is not None and args.slot != 0:
            config.fail(
                "serverless is single-instance and always uses slot 0; --slot is not allowed with --es serverless"
            )
        slot = 0
    else:
        # Free slots whose snapshot stack is no longer fully alive (a killed
        # session leaves a stale registry entry that would otherwise push this
        # worktree onto a higher slot/port), then allocate.
        if args.slot is None:
            lifecycle.reclaim_dead_slots(registry, worktree)
            shared_es.reclaim_dead_es_instances(registry)
        slot = slots.allocate_slot(registry, worktree, args.slot)
    return slot


def print_start_banner(
    args: argparse.Namespace,
    cfg: dict,
    worktree: str,
    slot: int,
    data_name: str,
    shared: dict | None,
    share_version: str | None,
) -> None:
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


def arm_reaper(registry: dict, shared: dict) -> None:
    """Start the idle-reaper watchdog once the claim is saved; it reads the registry from disk at once.

    The watchdog stops the ES ~1 min after its last Kibana client and exits
    immediately when the version is not registered, so arming before the save
    would leave a dead ``reaper_pid`` behind. Re-armed on every claim.
    """
    if shared_es.ensure_reaper(shared["key"], shared["instance"]):
        store.save_registry(registry)


def main(argv: list[str]) -> int:
    args = cli.parse_args(argv)

    actions = [
        flag
        for flag, enabled in (
            ("--status", args.status),
            ("--prune", args.prune),
            ("--run-with-prune", args.run_with_prune is not None),
            ("--reap-shared-es", args.reap_shared_es is not None),
            ("--stop", args.stop),
            ("--stop-all", args.stop_all),
        )
        if enabled
    ]
    if len(actions) > 1:
        config.fail(f"{', '.join(actions)} are mutually exclusive")

    if args.status:
        return lifecycle.run_status(store.load_registry())

    if args.prune:
        return lifecycle.run_prune(store.load_registry())

    if args.run_with_prune is not None:
        return lifecycle.run_with_prune(args.run_with_prune)

    if args.reap_shared_es is not None:
        return shared_es.run_reap_shared_es(args.reap_shared_es)

    if args.stop_all:
        return lifecycle.run_stop_all(store.load_registry())

    if args.stop:
        return lifecycle.run_stop(checkout.resolve_worktree(), store.load_registry())

    worktree = checkout.resolve_worktree()
    pm = checkout.package_manager(worktree)
    branch = checkout.current_branch()
    started_by = config.STARTED_BY_AGENT if args.detach else config.STARTED_BY_USER

    registry = store.load_registry()

    share_version = resolve_share_version(args, worktree)

    slot = resolve_slot(args, registry, worktree, started_by)
    if shared_es.settle_idle_es_instances(registry, keep=share_version):
        store.save_registry(registry)
    cfg = slots.derive(slot)
    cfg["slot"] = slot
    if args.es == "serverless":
        cfg["es_url"] = f"https://localhost:{cfg['es_http']}"

    shared = None
    if share_version is not None:
        shared_es.clear_previous_stack_for_shared_es(registry, worktree)
        shared = shared_es.claim_shared_es(registry, share_version, worktree, started_by, exclude_slot=slot)
        shared_es.apply_shared_es(cfg, shared["instance"])
        liveness.ensure_ports_free(cfg, check_es=False)
        if shared["create"]:
            icfg = slots.derive(shared["instance"]["slot"])
            icfg["slot"] = shared["instance"]["slot"]
            liveness.ensure_ports_free(icfg, check_kbn=False)
        data_name = shared["instance"]["data"]
        logfile = Path(shared["instance"]["log"])
    else:
        liveness.ensure_ports_free(cfg)
        data_name = checkout.sanitize(args.data) if args.data else checkout.sanitize(branch)
        logfile = config.es_slot_log(slot)

    data_path = config.ES_DATA_ROOT / data_name
    kbn_cmd = launch.kibana_command(args, cfg, pm)
    target_pane = None if args.detach else launch.tmux_target_pane(worktree)
    mode = cli.start_mode(args, target_pane)

    registry[worktree] = store.build_worktree_entry(
        args, cfg, branch, data_name, logfile, started_by, mode, share_version
    )
    store.save_registry(registry)
    if shared is not None:
        arm_reaper(registry, shared)

    print_start_banner(args, cfg, worktree, slot, data_name, shared, share_version)

    subprocess.run([pm, "kbn", "bootstrap"], check=True)

    if shared is not None and shared["create"]:
        # Bootstrap takes minutes: a parallel launcher may have won the create
        # race for this version meanwhile. Settle it and refresh the entry.
        registry, shared = shared_es.reconfirm_shared_claim(share_version, worktree, started_by, slot)
        shared_es.apply_shared_es(cfg, shared["instance"])
        data_name = shared["instance"]["data"]
        data_path = config.ES_DATA_ROOT / data_name
        logfile = Path(shared["instance"]["log"])
        kbn_cmd = launch.kibana_command(args, cfg, pm)
        registry[worktree] = store.build_worktree_entry(
            args, cfg, branch, data_name, logfile, started_by, mode, share_version
        )
        store.save_registry(registry)
        arm_reaper(registry, shared)

    if shared is None:
        # Clear stale output before either trigger reader starts. Both readers
        # begin at byte zero, so they cannot miss a trigger written before they
        # open. (claim_shared_es already truncated a new shared instance's log.)
        logfile.write_text("", encoding="utf-8")

    if args.detach:
        return launch.run_detached(args, cfg, worktree, data_path, logfile, kbn_cmd, shared=shared)

    if shared is not None and not shared["create"]:
        return launch.run_interactive_attach(cfg, worktree, kbn_cmd, target_pane, logfile, shared)

    # The log already exists so the watcher never races a missing path.
    watcher = threading.Thread(
        target=launch.start_kibana_on_trigger,
        args=(logfile, cfg["es_url"], kbn_cmd, target_pane, worktree, cfg["kbn_url"], args.es, data_path),
        daemon=True,
    )
    watcher.start()

    es_env = cli.es_environment(args)
    es_cmd = launch.es_command(args, cfg, data_path, pm)
    if shared is not None:
        # A shared ES must outlive this pane (other worktrees attach to it), so
        # it runs detached even for interactive starts; follow its log instead.
        trial_license.settle_expired_data_dir(data_path)

        def spawn_shared_es() -> int:
            pid = launch.spawn_background(es_cmd, logfile, worktree, env=es_env)
            store.update_es_instance(shared["key"], es_pid=pid)
            return pid

        def respawn_shared_es() -> int:
            trial_license.rotate_expired_data_dir(
                data_path, f"Elasticsearch log {logfile} reports an expired trial license"
            )
            return spawn_shared_es()

        es_pid = spawn_shared_es()
        launch.announce_es("starting", es_pid, logfile)
        return launch.follow_es_log(logfile, es_pid, respawn=respawn_shared_es)
    return launch.run_foreground_es(es_cmd, logfile, env=es_env, data_path=data_path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
