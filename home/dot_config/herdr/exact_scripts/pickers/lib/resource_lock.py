"""Serialize picker cache writers with each resource’s lock protocol."""

from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from picker_owner import PickerOwner, PickerOwnerError, positive_pid, resource_lock


@contextmanager
def cache_directory_lock(path: str | Path, timeout: float):
    owner = PickerOwner(Path(path), resource="index")
    owner_pid = os.getpid()
    deadline = time.monotonic() + timeout
    while True:
        result = owner.acquire(owner_pid, preemptible=False, mutex_timeout=max(0.0, deadline - time.monotonic()))
        if result.startswith("owned "):
            generation = result.removeprefix("owned ")
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"picker resource busy: {path}") from None
        time.sleep(0.02)
    try:
        yield
    finally:
        owner.release(owner_pid, generation)


def inject_sessions(path: str, rows: list[str]) -> None:
    injected = []
    paths = set()
    names = set()
    for row in reversed(rows):
        parts = row.split("\t")
        if parts[2] in paths or parts[4] in names:
            continue
        injected.append(row)
        paths.add(parts[2])
        names.add(parts[4])
    cache = Path(path)
    prior = cache.read_text(encoding="utf-8").splitlines() if cache.exists() else []
    kept = []
    for row in prior:
        parts = row.split("\t")
        if len(parts) >= 5 and (
            (parts[1] == "session" and parts[4] in names)
            or (parts[1] in ("session", "worktree", "dir") and parts[2] in paths)
        ):
            continue
        kept.append(row)
    descriptor, temporary = tempfile.mkstemp(dir=cache.parent, prefix=".session_inject.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("\n".join([*injected, *kept]) + "\n")
        os.replace(temporary, cache)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "operation",
        choices=(
            "append",
            "remove-mark",
            "pending-prune",
            "inject-sessions",
            "cache-run",
            "owner-acquire",
            "owner-release",
            "run",
        ),
    )
    parser.add_argument("resource")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.operation == "owner-acquire":
            if len(args.args) != 3:
                parser.error("owner-acquire requires OWNER_PID REFRESH_0_OR_1 PUBLISHING_GRACE_SECONDS")
            owner_pid = positive_pid(args.args[0])
            if owner_pid is None:
                parser.error("process IDs must be positive decimal PIDs")
            if args.args[1] not in ("0", "1"):
                parser.error("refresh must be 0 or 1")
            try:
                publishing_grace_seconds = float(args.args[2])
            except ValueError:
                parser.error("publishing grace must be a finite nonnegative number of seconds")
            if not math.isfinite(publishing_grace_seconds) or publishing_grace_seconds < 0:
                parser.error("publishing grace must be a finite nonnegative number of seconds")
            owner = PickerOwner(
                Path(args.resource), resource="index", publishing_grace_seconds=publishing_grace_seconds
            )
            print(owner.acquire(owner_pid, refresh=args.args[1] == "1"))
            return 0
        if args.operation == "owner-release":
            if len(args.args) < 2:
                parser.error("owner-release requires OWNER_PID GENERATION [CHILD_PID ...]")
            owner_pid = positive_pid(args.args[0])
            child_pids = tuple(positive_pid(raw_pid) for raw_pid in args.args[2:])
            if owner_pid is None or any(pid is None for pid in child_pids):
                parser.error("process IDs must be positive decimal PIDs")
            if not re.fullmatch(r"[0-9a-f]{32}", args.args[1]):
                parser.error("owner generation must be a 32-character lowercase hexadecimal token")
            owner = PickerOwner(Path(args.resource), resource="index")
            owner.release(owner_pid, args.args[1], child_pids)
            return 0
        if args.operation == "inject-sessions":
            rows = sys.stdin.read().splitlines()
            with cache_directory_lock(args.resource, args.timeout):
                inject_sessions(args.resource, rows)
            return 0
        if args.operation == "cache-run":
            with cache_directory_lock(args.resource, args.timeout):
                return subprocess.run(args.args, check=False).returncode
        with resource_lock(args.resource, args.timeout):
            if args.operation == "append":
                with open(args.resource, "a", encoding="utf-8") as handle:
                    handle.write(sys.stdin.read())
            elif args.operation == "remove-mark":
                mutations = args.args[0]
                rows = [row.partition("\t") for row in sys.stdin.read().splitlines()]
                now = int(time.time())
                with resource_lock(mutations):
                    with open(args.resource, "a", encoding="utf-8") as pending:
                        pending.writelines(f"WT\t{path}\n" for kind, _, path in rows if kind == "WT")
                    with open(mutations, "a", encoding="utf-8") as handle:
                        handle.writelines(f"{now}\tPATH_PREFIX\t{path}\n" for _, _, path in rows if path)
            elif args.operation == "pending-prune":
                path = Path(args.resource)
                if path.exists():
                    removed = {os.path.realpath(p) for p in args.args if not os.path.exists(p)}
                    rows = path.read_text(encoding="utf-8").splitlines(True)
                    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
                    try:
                        temporary.write_text(
                            "".join(row for row in rows if row.rstrip("\n").removeprefix("WT\t") not in removed),
                            encoding="utf-8",
                        )
                        os.replace(temporary, path)
                    finally:
                        temporary.unlink(missing_ok=True)
            else:
                return subprocess.run(args.args, check=False).returncode
    except (PickerOwnerError, OSError, TimeoutError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
