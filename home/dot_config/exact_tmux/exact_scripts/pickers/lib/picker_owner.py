from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@contextmanager
def resource_lock(path: str | Path, timeout: float = 10.0):
    lock = Path(str(path) + ".flock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"picker resource busy: {path}") from None
                time.sleep(0.02)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class PickerOwnerError(Exception):
    pass


@dataclass(frozen=True)
class ProcessIdentity:
    start: str
    command_sha256: str
    parent_pid: int
    zombie: bool = field(compare=False)


def positive_pid(value: str) -> int | None:
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value):
        return None
    pid = int(value)
    return pid if pid <= 2147483647 else None


def _valid_pid(pid: object) -> bool:
    return isinstance(pid, int) and not isinstance(pid, bool) and 0 < pid <= 2147483647


def process_identity(pid: int) -> ProcessIdentity | None:
    if not _valid_pid(pid):
        return None
    try:
        result = subprocess.run(
            ["ps", "-ww", "-o", "lstart=", "-o", "ppid=", "-o", "stat=", "-o", "command=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    fields = result.stdout.strip().split(None, 7)
    if result.returncode or len(fields) != 8 or not fields[5].isdigit():
        return None
    return ProcessIdentity(
        " ".join(fields[:5]), hashlib.sha256(fields[7].encode()).hexdigest(), int(fields[5]), fields[6].startswith("Z")
    )


def process_is_dead(pid: int) -> bool:
    if not _valid_pid(pid):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (OSError, OverflowError):
        pass
    return False


class PickerOwner:
    def __init__(
        self,
        cache_file: Path,
        resource: Literal["fetch", "index"],
        *,
        publishing_grace_seconds: float | None = None,
    ):
        if resource == "fetch":
            self.directory = Path(str(cache_file) + ".fetch.lock")
            self.mutex = str(cache_file) + ".fetch"
            self.label = "GitHub fetch"
            self.publishing_grace_seconds = 2.0
        elif resource == "index":
            self.directory = Path(str(cache_file) + ".lock")
            self.mutex = str(cache_file) + ".owner"
            self.label = "session index"
            self.publishing_grace_seconds = 180.0
        else:
            raise ValueError(f"unknown picker owner resource: {resource}")
        self.resource = resource
        if publishing_grace_seconds is not None:
            self.publishing_grace_seconds = publishing_grace_seconds

    def _owner(self) -> dict | None:
        try:
            owner = json.loads((self.directory / "owner.json").read_text())
        except (OSError, ValueError):
            return None
        if not isinstance(owner, dict) or not _valid_pid(owner.get("pid")):
            return None
        if not isinstance(owner.get("start"), str) or not owner["start"]:
            return None
        for key, length in (("command_sha256", 64), ("generation", 32)):
            if not isinstance(owner.get(key), str) or not re.fullmatch(r"[0-9a-f]{" + str(length) + "}", owner[key]):
                return None
        if not isinstance(owner.get("preemptible"), bool):
            return None
        return owner

    def _inspect(self) -> tuple[str, dict | None]:
        try:
            raw_pid = (self.directory / "pid").read_text().strip()
        except FileNotFoundError:
            raw_pid = ""
        except (OSError, UnicodeError):
            return "unverified", None
        if not raw_pid:
            try:
                age = time.time() - self.directory.stat().st_mtime
            except FileNotFoundError:
                return "gone", None
            return ("publishing" if age < self.publishing_grace_seconds else "orphaned"), None
        pid = positive_pid(raw_pid)
        if pid is None:
            return "unverified", None
        identity = process_identity(pid)
        if identity is None:
            return ("dead" if process_is_dead(pid) else "unverified"), None
        if identity.zombie:
            return "dead", None
        owner = self._owner()
        if (
            owner
            and owner["pid"] == pid
            and owner["start"] == identity.start
            and owner["command_sha256"] == identity.command_sha256
        ):
            return "alive", owner
        return "unverified", None

    def _state(self, expected: dict) -> str:
        if self._owner() != expected:
            return "changed"
        state, _ = self._inspect()
        return state

    def signal_owner(self, expected: dict, sig: int) -> str:
        with resource_lock(self.mutex):
            state = self._state(expected)
            if state != "alive":
                return state
            if not expected["preemptible"]:
                return "busy"
            try:
                os.kill(expected["pid"], sig)
            except ProcessLookupError:
                return "dead"
            except OSError as error:
                raise PickerOwnerError(f"cannot signal verified {self.label} owner") from error
            return "sent"

    def _refresh_refused(self, changed: bool = False) -> bool:
        if self.resource == "index":
            return False
        reason = "changed" if changed else "is unverified"
        raise PickerOwnerError(f"{self.label} owner identity {reason}; refresh refused")

    def _preempt(self, owner: dict) -> bool:
        state = self.signal_owner(owner, signal.SIGTERM)
        if state in ("changed", "dead", "gone"):
            return True
        if state != "sent":
            return self._refresh_refused()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            with resource_lock(self.mutex):
                state = self._state(owner)
            if state in ("changed", "dead", "gone"):
                return True
            if state != "alive":
                return self._refresh_refused(changed=True)
            time.sleep(0.1)
        state = self.signal_owner(owner, signal.SIGKILL)
        if state == "unverified":
            return self._refresh_refused(changed=True)
        if state == "sent":
            time.sleep(0.1)
        return True

    def acquire(
        self,
        owner_pid: int,
        refresh: bool = False,
        preemptible: bool = True,
        *,
        mutex_timeout: float = 10.0,
    ) -> str:
        if not _valid_pid(owner_pid):
            raise PickerOwnerError("process IDs must be positive decimal PIDs")
        if not isinstance(preemptible, bool):
            raise PickerOwnerError("picker owner preemptible must be boolean")
        while True:
            with resource_lock(self.mutex, mutex_timeout):
                if not self.directory.exists():
                    identity = process_identity(owner_pid)
                    if identity is None or identity.zombie:
                        raise PickerOwnerError(f"cannot verify {self.label} owner identity")
                    owner = {
                        "pid": owner_pid,
                        "start": identity.start,
                        "command_sha256": identity.command_sha256,
                        "generation": secrets.token_hex(16),
                        "preemptible": preemptible,
                    }
                    self.directory.mkdir()
                    try:
                        (self.directory / "owner.json").write_text(json.dumps(owner) + "\n")
                        (self.directory / "pid").write_text(str(owner_pid) + "\n")
                    except OSError:
                        shutil.rmtree(self.directory)
                        raise
                    return "owned " + owner["generation"]
                state, owner = self._inspect()
                if state in ("dead", "orphaned", "gone"):
                    try:
                        shutil.rmtree(self.directory)
                    except FileNotFoundError:
                        pass
                    continue
                if state == "publishing":
                    return "publishing"
                if not refresh or (owner is not None and not owner["preemptible"]):
                    return "busy"
                if state != "alive" or owner is None:
                    self._refresh_refused()
                    return "busy"
            if not self._preempt(owner):
                return "busy"

    def _signal_child(
        self,
        owner: dict,
        pid: int,
        expected: ProcessIdentity,
        sig: int,
        parent: tuple[int, ProcessIdentity] | None = None,
    ) -> bool:
        with resource_lock(self.mutex):
            if self._state(owner) != "alive":
                return False
            if parent is None:
                if expected.parent_pid != owner["pid"]:
                    return False
            elif (
                parent[1].parent_pid != owner["pid"]
                or expected.parent_pid != parent[0]
                or process_identity(parent[0]) != parent[1]
            ):
                return False
            current = process_identity(pid)
            if current is None or current.zombie or current != expected:
                return False
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                return False
            except OSError as error:
                raise PickerOwnerError(f"cannot signal verified {self.label} child") from error
            return True

    def _stop_child(self, owner: dict, child_pid: int) -> None:
        identity = process_identity(child_pid)
        if identity is None or identity.zombie or identity.parent_pid != owner["pid"]:
            return
        try:
            result = subprocess.run(
                ["pgrep", "-P", str(child_pid)], capture_output=True, text=True, timeout=5, check=False
            )
        except (OSError, subprocess.SubprocessError):
            result = None
        descendants = []
        if result is not None:
            for raw_pid in result.stdout.split():
                pid = positive_pid(raw_pid)
                if pid is None:
                    continue
                descendant = process_identity(pid)
                if descendant is not None and not descendant.zombie and descendant.parent_pid == child_pid:
                    descendants.append((pid, descendant))
        for pid, descendant in descendants:
            self._signal_child(owner, pid, descendant, signal.SIGTERM, (child_pid, identity))
        if not self._signal_child(owner, child_pid, identity, signal.SIGTERM):
            return
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            current = process_identity(child_pid)
            if current is None or current.zombie or current != identity:
                return
            time.sleep(0.05)
        for pid, descendant in descendants:
            self._signal_child(owner, pid, descendant, signal.SIGKILL, (child_pid, identity))
        self._signal_child(owner, child_pid, identity, signal.SIGKILL)

    def release(self, owner_pid: int, generation: str, child_pids: tuple[int, ...] = ()) -> None:
        if not _valid_pid(owner_pid) or any(not _valid_pid(pid) for pid in child_pids):
            raise PickerOwnerError("process IDs must be positive decimal PIDs")
        with resource_lock(self.mutex):
            owner = self._owner()
            if owner is None or owner["pid"] != owner_pid or owner["generation"] != generation:
                return
            may_stop_children = self._state(owner) == "alive"
        if may_stop_children:
            for child_pid in child_pids:
                self._stop_child(owner, child_pid)
        with resource_lock(self.mutex):
            if self._owner() == owner:
                shutil.rmtree(self.directory)
