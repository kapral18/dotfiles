"""Process and port primitives: listener lookup, pid liveness/identity, process-group teardown."""

from __future__ import annotations

import os
import signal
import subprocess
import time

from kbn_stack import config


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


def kill_port_listeners(port: int | None) -> bool:
    """SIGTERM then SIGKILL the process group of each listener on ``port``.

    Interactive stacks are not our children, so recorded pids are missing; the
    port owner is the inner Kibana, a group *member*. Signaling that pid alone
    lets Kibana close the port, log "All plugins stopped", and hang while pnpm/yarn
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


def stop_es_process(es_pid: int) -> None:
    """Stop a spawned ES launcher group and wait until it is gone (bounded)."""
    kill_pid_group(es_pid)
    deadline = time.monotonic() + config.KILL_GRACE_SECONDS
    while pid_alive(es_pid) and time.monotonic() < deadline:
        time.sleep(config.KILL_POLL_SECONDS)


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


def _kill_process_tree(root: int, pgid: int) -> None:
    """SIGTERM then SIGKILL ``root`` and its live descendants within ``pgid``, never this process."""
    me = os.getpid()

    def targets() -> list[int]:
        return [
            member
            for member in _live_group_members(pgid)
            if member != me and (member == root or root in pid_ancestors(member))
        ]

    for member in targets():
        _signal_pid(member, signal.SIGTERM)
    deadline = time.monotonic() + config.KILL_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not targets():
            return
        time.sleep(config.KILL_POLL_SECONDS)
    for member in targets():
        _signal_pid(member, signal.SIGKILL)


def _term_then_kill(pid: int) -> None:
    """Fallback when the process group is not ours to signal: SIGTERM the pid, then SIGKILL it."""
    _signal_pid(pid, signal.SIGTERM)
    time.sleep(min(config.KILL_GRACE_SECONDS, 0.2))
    _signal_pid(pid, signal.SIGKILL)


def kill_pid_group(pid: int) -> None:
    """SIGTERM then SIGKILL the process group of ``pid``.

    Detached stacks start with start_new_session=True, so the recorded pid is the
    group leader. Interactive stacks are stopped via a port listener which is a
    group member (the inner Kibana); getpgid still names the pnpm|yarn/python group.
    After SIGTERM, wait for live (non-zombie) members, then SIGKILL the group and
    any survivors. A Kibana that closes its port and hangs still dies.
    """
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    except PermissionError:
        _term_then_kill(pid)
        return
    if pgid == os.getpgid(0):
        # The target shares this process's group (an interactive ES spawned into
        # the launcher's pane): killpg would take the launcher down with it, so
        # signal only the target and its descendants.
        _kill_process_tree(pid, pgid)
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        _term_then_kill(pid)
        return
    deadline = time.monotonic() + config.KILL_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not _live_group_members(pgid):
            return
        time.sleep(config.KILL_POLL_SECONDS)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    for member in _live_group_members(pgid):
        _signal_pid(member, signal.SIGKILL)


def docker_kill_serverless() -> None:
    """Remove the fixed ES and UIAM containers owned by the exclusive serverless stack."""
    for name in ("es01", "es02", "uiam", "uiam-cosmosdb"):
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True,
            check=False,
        )
