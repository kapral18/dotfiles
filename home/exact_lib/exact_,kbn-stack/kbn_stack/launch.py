"""Starting ES and Kibana: command lines, tmux pane selection, interactive/detached start paths.

Interactive (default): runs ES in the current tmux pane and auto-launches Kibana
in a second pane once ES finishes setup (splitting the window if only one pane
exists). Outside tmux it prints the Kibana command to run. When the ES is
shared, it runs detached (it must outlive this pane) and the current pane
follows its log instead; Ctrl-C detaches from the log without stopping ES.

Agent (``--detach``): starts ES and Kibana in the background (no tmux), waits
until Kibana answers ``/api/status``, records ``ready: true`` plus the process
pids in the registry, then returns. Intended for agentic sessions that then read
the registry to resolve live URLs.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from kbn_stack import checkout, cli, config, es_log, lifecycle, procs, shared_es, store, trial_license


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


def kibana_command(args: argparse.Namespace, cfg: dict, pm: str) -> str:
    parts = [
        pm,
        "start",
        "--no-base-path",
        f"--port={cfg['kbn_port']}",
        f"--elasticsearch.hosts={cfg['es_url']}",
        f"--xpack.security.cookieName={cfg['cookie_name']}",
        f"--xpack.encryptedSavedObjects.encryptionKey={cfg['encryption_key']}",
    ]
    if args.es == "serverless":
        parts.append(f"--serverless={args.project_type}")
    for flag in cli.resolved_kbn_flags(args):
        parts.append(f"--{flag}")
    return " ".join(shlex.quote(p) for p in parts)


def es_command(args: argparse.Namespace, cfg: dict, data_path: Path, pm: str) -> list[str]:
    if args.es == "serverless":
        return [
            pm,
            "es",
            "serverless",
            "--projectType",
            config.ES_PROJECT_TYPE_FROM_KBN[args.project_type],
            "--port",
            str(cfg["es_http"]),
            "--basePath",
            str(data_path.parent),
            "--dataPath",
            data_path.name,
            "--waitForReady",
            "--kill",
        ]
    cmd = [
        pm,
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
        config.MERGE_DISK_WATERMARK,
    ]
    for flag in args.es_flags:
        cmd += ["-E", flag]
    return cmd


def wrapped_kibana_command(kbn_cmd: str, worktree: str) -> str:
    """Wrap the Kibana start command so its exit triggers silent registry pruning.

    ``KBN_STACK_WORKTREE`` lets the wrapper record itself as the entry's
    ``kbn_pid``: it outlives every dev-mode server restart, so a Kibana
    rebooting on a file save still counts as a shared-ES client while its port
    is unbound.
    """
    return shlex.join(
        [
            "env",
            f"KBN_STACK_WORKTREE={worktree}",
            sys.executable,
            str(config.ENTRYPOINT),
            "--run-with-prune",
            *shlex.split(kbn_cmd),
        ]
    )


def start_kibana_on_trigger(
    logfile: Path,
    es_url: str,
    kbn_cmd: str,
    target_pane: str | None,
    worktree: str,
    kbn_url: str,
    backend: str,
    data_path: Path | None = None,
) -> None:
    """Wait for the ES setup trigger, ensure trial license, then launch Kibana.

    When Kibana is launched into a tmux pane, poll its /api/status afterwards and
    flip the registry ``ready`` flag so an agent running ``/k-deep-review`` from the
    same worktree can discover the interactively-started stack. The poll runs in
    this background thread, so it never blocks the foreground ES log stream.
    """
    trigger = config.setup_trigger(backend)
    # The caller clears the log before ES starts. Read from byte zero so the
    # trigger remains visible if ES writes it before this thread is scheduled.
    # An expired-trial respawn truncates the log again; LogFollower rewinds.
    with es_log.LogFollower(logfile) as log:
        while True:
            line = log.readline()
            if not line:
                time.sleep(0.5)
                continue
            if trigger in line:
                if backend == "snapshot":
                    trial_license.ensure_trial_license(es_url, data_path)
                kbn_cmd = wrapped_kibana_command(kbn_cmd, worktree)
                if target_pane:
                    send_to_pane(target_pane, kbn_cmd)
                    if kibana_ready(kbn_url, timeout=config.KIBANA_READY_TIMEOUT):
                        store.mark_ready(worktree, True)
                else:
                    print(
                        f"\n,kbn-stack: Elasticsearch ready. Start Kibana with:\n  {kbn_cmd}\n",
                        flush=True,
                    )
                return


def send_to_pane(target_pane: str, command: str) -> None:
    """Type ``command`` into a tmux pane and press Enter."""
    subprocess.run(["tmux", "send-keys", "-t", target_pane, command, "C-m"], check=False)


def announce_es(verb: str, es_pid: int, logfile: Path) -> None:
    print(f",kbn-stack: Elasticsearch {verb} (pid {es_pid}) -> {logfile}", flush=True)


def kibana_ready(kbn_url: str, timeout: float) -> bool:
    """Poll Kibana's /api/status until it answers 200 (serving), or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = subprocess.run(
            ["curl", "-fsS", "-m5", "-u", config.ELASTIC_BASIC_AUTH, f"{kbn_url}/api/status"],
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
    handle.write(es_log.boot_marker())
    handle.flush()
    proc = subprocess.Popen(
        cmd,
        stdout=handle,
        stderr=subprocess.STDOUT,
        cwd=worktree,
        start_new_session=True,
        env=env,
    )
    return proc.pid


def start_es_and_wait(
    spawn: Callable[[], int],
    record_pid: Callable[[int], None],
    logfile: Path,
    data_path: Path,
    trigger: str,
) -> int:
    """Spawn ES and block until setup completes; return the launcher pid.

    Rotates a data dir whose recorded trial expiry has passed before the first
    spawn, and once more (then respawns) when the log proves an expired trial
    the sidecar did not know about. Any other non-trigger verdict fails the
    start immediately with a log excerpt.
    """
    trial_license.settle_expired_data_dir(data_path)
    es_pid = spawn()
    record_pid(es_pid)
    announce_es("starting", es_pid, logfile)
    verdict = es_log.wait_for_trigger(logfile, timeout=config.ES_SETUP_TIMEOUT, trigger=trigger, es_pid=es_pid)
    if verdict == config.WAIT_EXPIRED:
        procs.stop_es_process(es_pid)
        trial_license.rotate_expired_data_dir(
            data_path, f"Elasticsearch log {logfile} reports an expired trial license"
        )
        es_pid = spawn()
        record_pid(es_pid)
        announce_es("restarting", es_pid, logfile)
        verdict = es_log.wait_for_trigger(logfile, timeout=config.ES_SETUP_TIMEOUT, trigger=trigger, es_pid=es_pid)
    if verdict != config.WAIT_TRIGGER:
        config.fail(es_log.setup_failure_message(verdict, logfile))
    return es_pid


def run_foreground_es(
    es_cmd: list[str],
    logfile: Path,
    env: dict[str, str] | None = None,
    data_path: Path | None = None,
) -> int:
    """Stream interactive Elasticsearch and prune stale entries after it exits.

    With ``data_path``, an expired-trial marker in the stream stops ES, rotates
    the data dir, truncates the log (the Kibana watcher rewinds), and restarts
    ES once.
    """
    if data_path is not None:
        trial_license.settle_expired_data_dir(data_path)
    with logfile.open("w", encoding="utf-8") as log_handle:
        try:
            for attempt in (1, 2):
                log_handle.write(es_log.boot_marker())
                log_handle.flush()
                proc = subprocess.Popen(es_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
                assert proc.stdout is not None
                expired = False
                for line in proc.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    log_handle.write(line)
                    log_handle.flush()
                    if (
                        not expired
                        and attempt == 1
                        and data_path is not None
                        and trial_license.license_expired_line(line)
                    ):
                        expired = True
                        print(",kbn-stack: expired trial license detected; stopping Elasticsearch.", flush=True)
                        # Keep draining the pipe so the launcher can exit.
                        procs.kill_pid_group(proc.pid)
                status = proc.wait()
                if not expired:
                    return status
                trial_license.rotate_expired_data_dir(
                    data_path, f"Elasticsearch log {logfile} reports an expired trial license"
                )
                log_handle.seek(0)
                log_handle.truncate()
            return status
        finally:
            lifecycle.run_prune(store.load_registry(), ignored_pid=os.getpid(), quiet=True)


def follow_es_log(logfile: Path, es_pid: int, respawn: Callable[[], int] | None = None) -> int:
    """Stream a background shared ES's log in the foreground pane.

    The shared ES must outlive this pane (other worktrees may attach), so it is
    not a foreground child: Ctrl-C detaches from the log and leaves ES running.
    Returns non-zero when the ES process itself exits. With ``respawn``, an
    expired-trial marker stops ES, rotates its data dir, and respawns it once.
    """
    print(
        f",kbn-stack: shared ES runs in the background (pid {es_pid}); following {logfile}.\n"
        "            Ctrl-C detaches from the log without stopping ES; stop with `,kbn-stack --stop`.",
        flush=True,
    )
    try:
        with es_log.LogFollower(logfile) as log:
            while True:
                line = log.readline()
                if line:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    if respawn is not None and trial_license.license_expired_line(line):
                        procs.stop_es_process(es_pid)
                        es_pid = respawn()
                        respawn = None
                        announce_es("restarting", es_pid, logfile)
                    continue
                if not procs.pid_alive(es_pid):
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
        lifecycle.run_prune(store.load_registry(), ignored_pid=os.getpid(), quiet=True)


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
    shared_es.wait_for_shared_es(shared, es_logfile)
    trial_license.ensure_trial_license(cfg["es_url"], config.ES_DATA_ROOT / shared["instance"]["data"])
    launch = wrapped_kibana_command(kbn_cmd, worktree)
    if not target_pane:
        print(f"\n,kbn-stack: shared ES ready. Start Kibana with:\n  {launch}\n", flush=True)
        return 0
    send_to_pane(target_pane, launch)
    print(f",kbn-stack: Kibana starting in pane {target_pane}; waiting for {cfg['kbn_url']}/api/status", flush=True)
    if kibana_ready(cfg["kbn_url"], timeout=config.KIBANA_READY_TIMEOUT):
        store.mark_ready(worktree, True)
        print(
            f",kbn-stack: ready. Kibana -> {cfg['kbn_url']} (cookie {cfg['cookie_name']}), ES -> {cfg['es_url']}",
            flush=True,
        )
        return 0
    print(
        f",kbn-stack: Kibana did not answer /api/status within {int(config.KIBANA_READY_TIMEOUT)}s (see pane {target_pane}). "
        "If migrations clash with the shared ES, rerun with --isolated-es.",
        flush=True,
    )
    return 1


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
    kbn_logfile = config.kbn_slot_log(cfg["slot"])

    if shared is not None and not shared["create"]:
        print(f",kbn-stack: reusing shared ES {shared['key']} -> {cfg['es_url']}", flush=True)
        shared_es.wait_for_shared_es(shared, es_logfile)
        es_pid = None
    else:
        es_env = cli.es_environment(args)
        es_cmd = es_command(args, cfg, data_path, checkout.package_manager(worktree))

        def record_pid(pid: int) -> None:
            # Record the pid immediately so parallel launchers classify this
            # instance as starting rather than stale while setup runs.
            if shared is not None:
                store.update_es_instance(shared["key"], es_pid=pid)
            else:
                store.update_worktree_entry(worktree, es_pid=pid)

        trigger = config.setup_trigger(args.es)
        es_pid = start_es_and_wait(
            lambda: spawn_background(es_cmd, es_logfile, worktree, env=es_env),
            record_pid,
            es_logfile,
            data_path,
            trigger,
        )

    if args.es == "snapshot":
        trial_license.ensure_trial_license(cfg["es_url"], data_path)

    kbn_pid = spawn_background(shlex.split(kbn_cmd), kbn_logfile, worktree)
    store.update_worktree_entry(worktree, kbn_pid=kbn_pid, kbn_log=str(kbn_logfile))
    print(f",kbn-stack: Kibana starting (pid {kbn_pid}) -> {kbn_logfile}", flush=True)

    ready = kibana_ready(cfg["kbn_url"], timeout=config.KIBANA_READY_TIMEOUT)
    identity_ok, squatters = (False, [])
    if ready:
        identity_ok, squatters = procs.listener_identity_ok(cfg["kbn_port"], kbn_pid)
    fields: dict[str, object] = {"kbn_pid": kbn_pid, "kbn_log": str(kbn_logfile), "ready": ready and identity_ok}
    if shared is None and es_pid is not None:
        fields["es_pid"] = es_pid
    store.update_worktree_entry(worktree, **fields)

    if not ready:
        hint = ""
        if shared is not None:
            hint = " If the log shows saved-object migration failures against the shared ES, rerun with --isolated-es."
        config.fail(
            f"Kibana did not answer /api/status within {int(config.KIBANA_READY_TIMEOUT)}s (see {kbn_logfile}).{hint}"
        )
    if not identity_ok:
        detail = ", ".join(f"pid {pid} ({procs.describe_pid(pid)})" for pid in squatters) or "no listener found"
        config.fail(
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
