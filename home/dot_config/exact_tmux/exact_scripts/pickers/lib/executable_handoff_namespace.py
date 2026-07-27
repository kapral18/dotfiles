#!/usr/bin/env python3
"""Per-invocation namespace bus for tmux picker handoff (begin/path/end/sweep).

Each picker popup loop owns exactly one random 128-bit namespace directory under a
secure per-user cache root. Pins and sentinels live only inside that namespace, so
two concurrent popups can never read, clear, or consume each other's handoff state.

The namespace is published atomically with immutable owner metadata (PID plus the
owner's process start time and full command) and is reclaimed only for owners that
are *positively* dead. A live owner, or an owner whose liveness cannot be
determined, is always preserved.

Contract (fail-closed; empty stdout on any failure):

  begin --owner-pid PID --owner-role ROLE --entry ENTRY   -> prints one hex token
  path  SLOT [--token TOKEN]                               -> prints one absolute path
  end   --owner-pid PID [--token TOKEN]                    -> no output
  sweep                                                    -> no output

Token precedence is ``--token`` then ``TMUX_PICKER_HANDOFF_TOKEN``. Missing or
malformed tokens fail closed. There is no PID fallback and no legacy global path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import time
from pathlib import Path

ROOT_SUBPATH = ("tmux", "handoff-v1")
TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
STAGING_PREFIX = ".new-"
OWNER_FILE = "owner.json"
OWNER_VERSION = 1
OWNER_FILE_MODE = 0o600
TOKEN_BYTES = 16

DEAD_OWNER_TTL_SECONDS = 6 * 60 * 60
DEAD_OWNER_CAP = 64
STAGING_GRACE_SECONDS = 5 * 60

ENV_TOKEN = "TMUX_PICKER_HANDOFF_TOKEN"

ALLOWED_SLOTS = frozenset(
    {
        "gh_picker_pin",
        "pick_session_pin",
        "gh_picker_create_pin",
        "gh_picker_switch_sessions",
        "pick_session_switch_gh",
    }
)


OWNER_ROLES = ("popup-loop", "standalone-picker")
ENTRIES = ("gh-popup", "session-popup", "gh-picker", "session-picker")

LIVE = "live"
DEAD = "dead"
UNKNOWN = "unknown"


class HandoffError(Exception):
    """A fail-closed error: report to stderr, exit non-zero, print nothing to stdout."""


# --------------------------------------------------------------------------- #
# Secure root                                                                  #
# --------------------------------------------------------------------------- #


def root_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return Path(os.path.abspath(base)).joinpath(*ROOT_SUBPATH)


def _validate_secure_dir(path: Path) -> None:
    """Require ``path`` to be a real directory owned by us with mode 0700."""
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise HandoffError(f"cannot stat {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise HandoffError(f"refusing symlinked path: {path}")
    if not stat.S_ISDIR(info.st_mode):
        raise HandoffError(f"not a directory: {path}")
    if info.st_uid != os.getuid():
        raise HandoffError(f"path not owned by current uid: {path}")
    mode = stat.S_IMODE(info.st_mode)
    if mode != 0o700:
        raise HandoffError(f"insecure mode {oct(mode)} on {path}")


def secure_root() -> Path:
    """Create if needed and validate the handoff root; fatal on any insecurity."""
    root = root_path()
    try:
        root.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HandoffError(f"cannot create cache parent {root.parent}: {exc}") from exc
    created = False
    if not os.path.lexists(root):
        try:
            os.mkdir(root, 0o700)
            created = True
        except FileExistsError:
            created = False
        except OSError as exc:
            raise HandoffError(f"cannot create root {root}: {exc}") from exc
    if created:
        try:
            os.chmod(root, 0o700)
        except OSError as exc:
            raise HandoffError(f"cannot secure root {root}: {exc}") from exc
    _validate_secure_dir(root)
    return root


def inspect_root() -> "Path | None":
    """Return a validated root for sweeping, or None when nothing exists yet."""
    root = root_path()
    if not os.path.lexists(root):
        return None
    _validate_secure_dir(root)
    return root


def require_root() -> Path:
    """Return a validated, already-published root; never create it."""
    root = root_path()
    if not os.path.lexists(root):
        raise HandoffError(f"handoff root missing: {root}")
    _validate_secure_dir(root)
    return root


# --------------------------------------------------------------------------- #
# Owner identity and liveness                                                  #
# --------------------------------------------------------------------------- #


def _ps_field(pid: int, field: str) -> "str | None":
    try:
        proc = subprocess.run(
            ["ps", "-o", field + "=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def capture_identity(pid: int) -> "tuple[str, str]":
    """Read the (start, command) fingerprint for a live PID; fatal if unreadable."""
    if pid <= 0:
        raise HandoffError(f"invalid owner pid: {pid}")
    start = _ps_field(pid, "lstart")
    command = _ps_field(pid, "command")
    if start is None or command is None:
        raise HandoffError(f"cannot capture identity for pid {pid}")
    return start, command


def probe_owner(pid: int, expected_start: str, expected_command: str) -> str:
    """Classify an owner as LIVE, DEAD, or UNKNOWN (unknown is always preserved)."""
    if pid <= 0:
        return UNKNOWN
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return DEAD
    except PermissionError:
        return UNKNOWN
    except OSError:
        return UNKNOWN
    state = _ps_field(pid, "state")
    if state is None:
        return UNKNOWN
    if state.startswith("Z"):
        return DEAD
    start = _ps_field(pid, "lstart")
    command = _ps_field(pid, "command")
    if start is None or command is None:
        return UNKNOWN
    if start == expected_start and command == expected_command:
        return LIVE
    return DEAD


# --------------------------------------------------------------------------- #
# Owner metadata                                                               #
# --------------------------------------------------------------------------- #


def _valid_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _valid_choice(value: object, allowed: tuple[str, ...]) -> bool:
    return isinstance(value, str) and value in allowed


def _valid_owner_for_namespace(data: object, expected_token: "str | None") -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("version") != OWNER_VERSION:
        return False
    token = data.get("token")
    if not isinstance(token, str) or not TOKEN_RE.match(token):
        return False
    if expected_token is not None and token != expected_token:
        return False
    if not _valid_positive_int(data.get("owner_pid")):
        return False
    for key in ("owner_start", "owner_command"):
        value = data.get(key)
        if not isinstance(value, str) or not value:
            return False
    if not _valid_choice(data.get("owner_role"), OWNER_ROLES):
        return False
    if not _valid_choice(data.get("entry"), ENTRIES):
        return False
    if not _valid_positive_int(data.get("created_at_unix_ns")):
        return False
    return True


def _validate_owner_file_info(path: Path, info: os.stat_result) -> None:
    if stat.S_ISLNK(info.st_mode):
        raise HandoffError(f"refusing symlinked owner metadata: {path}")
    if not stat.S_ISREG(info.st_mode):
        raise HandoffError(f"owner metadata is not a regular file: {path}")
    if info.st_uid != os.getuid():
        raise HandoffError(f"owner metadata not owned by current uid: {path}")
    mode = stat.S_IMODE(info.st_mode)
    if mode != OWNER_FILE_MODE:
        raise HandoffError(f"insecure mode {oct(mode)} on owner metadata: {path}")


def load_owner(namespace: Path) -> dict:
    owner_path = namespace / OWNER_FILE
    try:
        initial = os.lstat(owner_path)
    except OSError as exc:
        raise HandoffError(f"cannot stat owner metadata: {owner_path}") from exc
    _validate_owner_file_info(owner_path, initial)
    fd = -1
    try:
        fd = os.open(owner_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        current = os.fstat(fd)
        _validate_owner_file_info(owner_path, current)
        if (current.st_dev, current.st_ino) != (initial.st_dev, initial.st_ino):
            raise HandoffError(f"owner metadata changed while reading: {owner_path}")
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            fd = -1
            data = json.load(handle)
    except HandoffError:
        raise
    except json.JSONDecodeError as exc:
        raise HandoffError(f"corrupt owner metadata: {owner_path}") from exc
    except OSError as exc:
        raise HandoffError(f"cannot read owner metadata: {owner_path}") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    if not _valid_owner_for_namespace(data, namespace.name):
        raise HandoffError(f"invalid owner metadata: {owner_path}")
    return data


def _try_owner(namespace: Path) -> "dict | None":
    """Load owner metadata, or None when it is missing/corrupt (liveness unknown)."""
    try:
        return load_owner(namespace)
    except HandoffError:
        return None


def _write_owner(owner_path: Path, owner: dict) -> None:
    fd = -1
    try:
        fd = os.open(
            owner_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            OWNER_FILE_MODE,
        )
        os.fchmod(fd, OWNER_FILE_MODE)
        info = os.fstat(fd)
        _validate_owner_file_info(owner_path, info)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            json.dump(owner, handle)
            handle.flush()
            os.fsync(handle.fileno())
    except HandoffError:
        raise
    except FileExistsError as exc:
        raise HandoffError(f"owner metadata already exists: {owner_path}") from exc
    except OSError as exc:
        raise HandoffError(f"cannot write owner metadata: {owner_path}") from exc
    finally:
        if fd >= 0:
            os.close(fd)


# --------------------------------------------------------------------------- #
# Cleanup                                                                      #
# --------------------------------------------------------------------------- #


def _remove_path(path: Path) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise HandoffError(f"cannot stat cleanup path: {path}") from exc
    if stat.S_ISDIR(info.st_mode):
        _remove_tree(path)
        return
    try:
        os.unlink(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise HandoffError(f"cannot remove {path}: {exc.strerror or exc}") from exc


def _remove_tree(path: Path) -> None:
    """Remove a namespace tree, tolerating only concurrent removal."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise HandoffError(f"cannot stat cleanup path: {path}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise HandoffError(f"refusing to remove symlinked path: {path}")
    if not stat.S_ISDIR(info.st_mode):
        raise HandoffError(f"refusing to remove non-directory path: {path}")
    try:
        with os.scandir(path) as entries:
            children = [Path(entry.path) for entry in entries]
    except FileNotFoundError:
        return
    except OSError as exc:
        raise HandoffError(f"cannot scan {path}: {exc.strerror or exc}") from exc
    for child in children:
        _remove_path(child)
    try:
        os.rmdir(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise HandoffError(f"cannot remove {path}: {exc.strerror or exc}") from exc


def _sweep_staging(entry: os.DirEntry, now: float) -> None:
    try:
        info = entry.stat(follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise HandoffError(f"cannot stat staging entry: {entry.path}") from exc
    if now - info.st_mtime <= STAGING_GRACE_SECONDS:
        return
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise HandoffError(f"refusing stale non-directory staging entry: {entry.path}")
    _remove_tree(Path(entry.path))


def _reap_dead(dead: list, now: float) -> None:
    survivors = []
    for mtime, namespace in dead:
        if now - mtime >= DEAD_OWNER_TTL_SECONDS:
            _remove_tree(namespace)
        else:
            survivors.append((mtime, namespace))
    if len(survivors) <= DEAD_OWNER_CAP:
        return
    survivors.sort(key=lambda item: item[0])
    for _mtime, namespace in survivors[: len(survivors) - DEAD_OWNER_CAP]:
        _remove_tree(namespace)


def sweep_root(root: Path) -> None:
    """Reap positively dead namespaces (TTL then cap) and stale staging dirs."""
    now = time.time()
    try:
        entries = list(os.scandir(root))
    except OSError as exc:
        raise HandoffError(f"cannot inspect root {root}: {exc}") from exc
    dead = []
    for entry in entries:
        name = entry.name
        if name.startswith(STAGING_PREFIX):
            _sweep_staging(entry, now)
            continue
        if not TOKEN_RE.match(name):
            continue
        try:
            info = entry.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise HandoffError(f"cannot stat namespace entry: {entry.path}") from exc
        if not stat.S_ISDIR(info.st_mode):
            continue
        namespace = Path(entry.path)
        owner = _try_owner(namespace)
        if owner is None:
            continue
        if probe_owner(owner["owner_pid"], owner["owner_start"], owner["owner_command"]) != DEAD:
            continue
        dead.append((info.st_mtime, namespace))
    _reap_dead(dead, now)


# --------------------------------------------------------------------------- #
# Token resolution                                                             #
# --------------------------------------------------------------------------- #


def resolve_token(explicit: "str | None") -> str:
    token = explicit if explicit else os.environ.get(ENV_TOKEN)
    if not token:
        raise HandoffError("no handoff token provided")
    if not TOKEN_RE.match(token):
        raise HandoffError("malformed handoff token")
    return token


# --------------------------------------------------------------------------- #
# Verbs                                                                        #
# --------------------------------------------------------------------------- #


def cmd_begin(args: argparse.Namespace) -> int:
    if args.owner_pid <= 0:
        raise HandoffError(f"invalid owner pid: {args.owner_pid}")
    root = secure_root()
    sweep_root(root)
    start, command = capture_identity(args.owner_pid)
    token = secrets.token_hex(TOKEN_BYTES)
    staging = root / (STAGING_PREFIX + token)
    try:
        os.mkdir(staging, 0o700)
    except OSError as exc:
        raise HandoffError(f"cannot create staging dir: {exc}") from exc
    try:
        os.chmod(staging, 0o700)
    except OSError as exc:
        _remove_tree(staging)
        raise HandoffError(f"cannot secure staging dir: {exc}") from exc
    owner = {
        "version": OWNER_VERSION,
        "token": token,
        "owner_pid": args.owner_pid,
        "owner_start": start,
        "owner_command": command,
        "owner_role": args.owner_role,
        "entry": args.entry,
        "created_at_unix_ns": time.time_ns(),
    }
    try:
        _write_owner(staging / OWNER_FILE, owner)
    except HandoffError:
        _remove_tree(staging)
        raise
    final = root / token
    try:
        os.rename(staging, final)
    except OSError as exc:
        _remove_tree(staging)
        raise HandoffError(f"cannot publish namespace: {exc}") from exc
    sys.stdout.write(token + "\n")
    return 0


def cmd_path(args: argparse.Namespace) -> int:
    token = resolve_token(args.token)
    if args.slot not in ALLOWED_SLOTS:
        raise HandoffError(f"unknown slot: {args.slot}")
    root = require_root()
    namespace = root / token
    if not os.path.lexists(namespace):
        raise HandoffError(f"namespace not found: {token}")
    _validate_secure_dir(namespace)
    load_owner(namespace)
    try:
        os.utime(namespace, None)
    except OSError as exc:
        raise HandoffError(f"cannot refresh namespace mtime: {exc}") from exc
    sys.stdout.write(str(namespace / args.slot) + "\n")
    return 0


def cmd_end(args: argparse.Namespace) -> int:
    if args.owner_pid <= 0:
        raise HandoffError(f"invalid owner pid: {args.owner_pid}")
    token = resolve_token(args.token)
    root = root_path()
    if not os.path.lexists(root):
        return 0
    _validate_secure_dir(root)
    namespace = root / token
    if not os.path.lexists(namespace):
        sweep_root(root)
        return 0
    _validate_secure_dir(namespace)
    owner = load_owner(namespace)
    start, command = capture_identity(args.owner_pid)
    if owner["owner_pid"] != args.owner_pid or owner["owner_start"] != start or owner["owner_command"] != command:
        raise HandoffError("owner fingerprint mismatch; refusing to end namespace")
    _remove_tree(namespace)
    sweep_root(root)
    return 0


def cmd_sweep(_args: argparse.Namespace) -> int:
    root = inspect_root()
    if root is None:
        return 0
    sweep_root(root)
    return 0


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="handoff_namespace.py", description="tmux picker handoff namespace bus")
    sub = parser.add_subparsers(dest="command", required=True)

    begin = sub.add_parser("begin", help="publish a new namespace; prints its token")
    begin.add_argument("--owner-pid", type=int, required=True)
    begin.add_argument("--owner-role", choices=OWNER_ROLES, required=True)
    begin.add_argument("--entry", choices=ENTRIES, required=True)
    begin.set_defaults(func=cmd_begin)

    path = sub.add_parser("path", help="print the absolute path of a slot in a namespace")
    path.add_argument("slot")
    path.add_argument("--token", default=None)
    path.set_defaults(func=cmd_path)

    end = sub.add_parser("end", help="remove the caller's namespace when it owns it")
    end.add_argument("--owner-pid", type=int, required=True)
    end.add_argument("--token", default=None)
    end.set_defaults(func=cmd_end)

    sweep = sub.add_parser("sweep", help="reap dead namespaces and stale staging dirs")
    sweep.set_defaults(func=cmd_sweep)

    return parser


def main(argv: "list[str] | None" = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except HandoffError as exc:
        print(f"handoff_namespace: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
