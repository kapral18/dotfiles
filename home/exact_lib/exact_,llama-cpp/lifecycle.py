#!/usr/bin/env python3
"""Run a command while holding a shared llama.cpp router lease."""

from __future__ import annotations

import fcntl
import hashlib
import ipaddress
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class LifecycleError(RuntimeError):
    """A safe router lifecycle operation could not be completed."""


class Terminated(Exception):
    """The lifecycle process received a terminating signal."""

    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


@dataclass(frozen=True)
class Config:
    """Resolved lifecycle configuration."""

    host: str
    port: int
    api_key: str
    preset: Path
    server_bin: str
    root: Path
    grace_seconds: int

    @classmethod
    def from_environment(cls) -> Config:
        try:
            port = int(os.environ.get("LLAMA_CPP_PORT", "8080"))
        except ValueError as error:
            raise LifecycleError("LLAMA_CPP_PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise LifecycleError("LLAMA_CPP_PORT must be between 1 and 65535")
        try:
            grace_seconds = int(os.environ.get("LLAMA_CPP_GRACE_SECONDS", "600"))
        except ValueError as error:
            raise LifecycleError("LLAMA_CPP_GRACE_SECONDS must be a non-negative integer") from error
        if grace_seconds < 0:
            raise LifecycleError("LLAMA_CPP_GRACE_SECONDS must be a non-negative integer")

        home = Path.home()
        return cls(
            host=os.environ.get("LLAMA_CPP_HOST", "127.0.0.1"),
            port=port,
            api_key=os.environ.get("LLAMA_CPP_API_KEY", ""),
            preset=Path(
                os.environ.get(
                    "LLAMA_CPP_MODELS_PRESET",
                    str(home / ".config/llama.cpp/models.ini"),
                )
            ).expanduser(),
            server_bin=os.environ.get("LLAMA_CPP_SERVER_BIN", "llama-server"),
            root=Path(
                os.environ.get(
                    "LLAMA_CPP_LIFECYCLE_DIR",
                    str(home / ".local/state/llama-cpp/lifecycle"),
                )
            ).expanduser(),
            grace_seconds=grace_seconds,
        )

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def namespace(self) -> Path:
        endpoint = f"{self.host}:{self.port}"
        digest = hashlib.sha256(endpoint.encode()).hexdigest()[:16]
        return self.root / digest


@dataclass
class Lease:
    """A held advisory lock representing one live consumer."""

    path: Path
    descriptor: int

    @classmethod
    def create(cls, namespace: Path) -> Lease:
        path = namespace / f"lease-{os.getpid()}-{uuid.uuid4().hex}.lock"
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return cls(path=path, descriptor=descriptor)

    def close(self) -> None:
        if self.descriptor < 0:
            return
        fcntl.flock(self.descriptor, fcntl.LOCK_UN)
        os.close(self.descriptor)
        self.descriptor = -1
        self.path.unlink(missing_ok=True)


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    """Serialize acquire and last-release decisions for one endpoint."""

    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def ensure_namespace(config: Config) -> None:
    config.namespace.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(config.namespace, 0o700)


def router_reachable(config: Config) -> bool:
    headers = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    request = urllib.request.Request(f"{config.base_url}/models", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=0.5) as response:
            payload = json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return False
    return response.status == 200 and isinstance(payload, dict) and isinstance(payload.get("data"), list)


def is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def process_start_identity(pid: int) -> str | None:
    result = subprocess.run(
        ["/bin/ps", "-o", "lstart=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    identity = result.stdout.strip()
    return identity if result.returncode == 0 and identity else None


def read_owner(path: Path) -> dict[str, object] | None:
    try:
        owner = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return owner if isinstance(owner, dict) else None


def owner_process_matches(owner: dict[str, object]) -> bool:
    try:
        pid = int(owner["pid"])
        expected = str(owner["start_identity"])
    except (KeyError, TypeError, ValueError):
        return False
    return process_start_identity(pid) == expected


def write_state(path: Path, state: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(state, handle, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def prune_and_count_leases(namespace: Path) -> int:
    active = 0
    for path in namespace.glob("lease-*.lock"):
        try:
            descriptor = os.open(path, os.O_RDWR)
        except FileNotFoundError:
            continue
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                active += 1
            else:
                path.unlink(missing_ok=True)
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
    return active


def resolved_server_binary(config: Config) -> str:
    if os.path.sep in config.server_bin:
        binary = Path(config.server_bin).expanduser()
        if binary.is_file() and os.access(binary, os.X_OK):
            return str(binary)
    else:
        found = shutil.which(config.server_bin)
        if found:
            return found
    raise LifecycleError(f"llama-server executable not found: {config.server_bin}")


def signal_exact_owner(owner: dict[str, object], signum: int) -> bool:
    if not owner_process_matches(owner):
        return False
    os.kill(int(owner["pid"]), signum)
    return True


def stop_owned_router(owner: dict[str, object]) -> bool:
    if not signal_exact_owner(owner, signal.SIGTERM):
        return False
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if not owner_process_matches(owner):
            return True
        time.sleep(0.05)
    return signal_exact_owner(owner, signal.SIGKILL)


def start_owned_router(config: Config, owner_path: Path) -> None:
    if not config.preset.is_file():
        raise LifecycleError(f"llama.cpp models preset not found: {config.preset}")

    command = [
        resolved_server_binary(config),
        "--host",
        config.host,
        "--port",
        str(config.port),
        "--models-preset",
        str(config.preset),
    ]
    if config.api_key:
        command.extend(["--api-key", config.api_key])

    log_path = config.namespace / "router.log"
    with log_path.open("ab", buffering=0) as log:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    start_identity = None
    identity_deadline = time.monotonic() + 2.0
    while time.monotonic() < identity_deadline and process.poll() is None:
        start_identity = process_start_identity(process.pid)
        if start_identity:
            break
        time.sleep(0.02)
    if not start_identity:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise LifecycleError("llama-server exited before its process identity could be recorded")

    owner: dict[str, object] = {
        "host": config.host,
        "port": config.port,
        "pid": process.pid,
        "preset": str(config.preset),
        "start_identity": start_identity,
    }
    write_state(owner_path, owner)

    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if router_reachable(config):
            return
        return_code = process.poll()
        if return_code is not None:
            owner_path.unlink(missing_ok=True)
            raise LifecycleError(f"llama-server exited with status {return_code}; see {log_path}")
        time.sleep(0.05)

    stop_owned_router(owner)
    owner_path.unlink(missing_ok=True)
    raise LifecycleError(f"llama-server did not become ready; see {log_path}")


def acquire(config: Config) -> Lease:
    ensure_namespace(config)
    owner_path = config.namespace / "owner.json"
    shutdown_path = config.namespace / "shutdown.json"
    with exclusive_lock(config.namespace / "lifecycle.lock"):
        prune_and_count_leases(config.namespace)
        shutdown_path.unlink(missing_ok=True)
        lease = Lease.create(config.namespace)
        if router_reachable(config):
            return lease
        if not is_loopback(config.host):
            lease.close()
            raise LifecycleError(
                f"llama.cpp router is not reachable at {config.base_url}; "
                "automatic startup is limited to loopback hosts"
            )
        try:
            start_owned_router(config, owner_path)
        except Exception:
            lease.close()
            raise
        return lease


def marker_matches_owner(marker: dict[str, object], owner: dict[str, object]) -> bool:
    return marker.get("pid") == owner.get("pid") and marker.get("start_identity") == owner.get("start_identity")


def reap_if_current(config: Config, token: str) -> bool:
    """Stop the scheduled owned router only if the grace state is still current."""

    owner_path = config.namespace / "owner.json"
    shutdown_path = config.namespace / "shutdown.json"
    with exclusive_lock(config.namespace / "lifecycle.lock"):
        marker = read_owner(shutdown_path)
        if marker is None or marker.get("token") != token:
            return False
        if prune_and_count_leases(config.namespace) != 0:
            shutdown_path.unlink(missing_ok=True)
            return False
        owner = read_owner(owner_path)
        if owner is None or not marker_matches_owner(marker, owner):
            shutdown_path.unlink(missing_ok=True)
            return False
        stop_owned_router(owner)
        owner_path.unlink(missing_ok=True)
        shutdown_path.unlink(missing_ok=True)
        return True


def wait_and_reap(config: Config, token: str) -> int:
    """Wait for the grace deadline, exiting early when acquisition cancels it."""

    shutdown_path = config.namespace / "shutdown.json"
    while True:
        marker = read_owner(shutdown_path)
        if marker is None or marker.get("token") != token:
            return 0
        try:
            remaining = float(marker["deadline_epoch"]) - time.time()
        except (KeyError, TypeError, ValueError):
            return 0
        if remaining <= 0:
            break
        time.sleep(min(1.0, remaining))
    reap_if_current(config, token)
    return 0


def schedule_shutdown(config: Config, owner: dict[str, object]) -> None:
    shutdown_path = config.namespace / "shutdown.json"
    token = uuid.uuid4().hex
    marker: dict[str, object] = {
        "deadline_epoch": time.time() + config.grace_seconds,
        "pid": owner.get("pid"),
        "start_identity": owner.get("start_identity"),
        "token": token,
    }
    write_state(shutdown_path, marker)
    try:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "reap", token],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        shutdown_path.unlink(missing_ok=True)
        stop_owned_router(owner)
        (config.namespace / "owner.json").unlink(missing_ok=True)


def release(config: Config, lease: Lease) -> None:
    owner_path = config.namespace / "owner.json"
    shutdown_path = config.namespace / "shutdown.json"
    with exclusive_lock(config.namespace / "lifecycle.lock"):
        lease.close()
        if prune_and_count_leases(config.namespace) != 0:
            return
        owner = read_owner(owner_path)
        if owner is None:
            shutdown_path.unlink(missing_ok=True)
            return
        if config.grace_seconds > 0:
            schedule_shutdown(config, owner)
            return
        stop_owned_router(owner)
        owner_path.unlink(missing_ok=True)
        shutdown_path.unlink(missing_ok=True)


def stop(config: Config, force: bool) -> int:
    """Stop only the exact lifecycle-owned router for this endpoint."""

    ensure_namespace(config)
    owner_path = config.namespace / "owner.json"
    shutdown_path = config.namespace / "shutdown.json"
    with exclusive_lock(config.namespace / "lifecycle.lock"):
        active = prune_and_count_leases(config.namespace)
        if active and not force:
            raise LifecycleError(
                f"{active} active llama.cpp consumer(s); use ',llama-cpp stop --force' to interrupt them"
            )
        owner = read_owner(owner_path)
        if owner is None:
            shutdown_path.unlink(missing_ok=True)
            print("No lifecycle-owned llama.cpp router is running.")
            return 0
        stopped = stop_owned_router(owner)
        owner_path.unlink(missing_ok=True)
        shutdown_path.unlink(missing_ok=True)
        if stopped:
            print("Stopped lifecycle-owned llama.cpp router.")
        else:
            print("No live process matched the lifecycle owner record.")
        return 0


def run(config: Config, command: list[str]) -> int:
    if not command:
        raise LifecycleError("run requires a command after --")
    lease = acquire(config)
    child: subprocess.Popen[bytes] | None = None

    def terminate(signum: int, _frame: object) -> None:
        raise Terminated(signum)

    previous_term = signal.signal(signal.SIGTERM, terminate)
    try:
        try:
            child = subprocess.Popen(command)
            return child.wait()
        except OSError as error:
            raise LifecycleError(f"failed to start command {command[0]}: {error}") from error
        except KeyboardInterrupt:
            if child is not None and child.poll() is None:
                child.send_signal(signal.SIGINT)
                child.wait()
            return 128 + signal.SIGINT
        except Terminated as termination:
            if child is not None and child.poll() is None:
                child.send_signal(termination.signum)
                child.wait()
            return 128 + termination.signum
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        release(config, lease)


def main(argv: list[str]) -> int:
    try:
        config = Config.from_environment()
        if argv and argv[0] == "reap" and len(argv) == 2:
            return wait_and_reap(config, argv[1])
        if argv and argv[0] == "stop":
            if argv[1:] not in ([], ["--force"]):
                raise LifecycleError("stop accepts only --force")
            return stop(config, argv[1:] == ["--force"])
        if not argv or argv[0] != "run":
            print("Usage: lifecycle.py {run -- <command> [args...]|stop [--force]}", file=sys.stderr)
            return 2
        command = argv[1:]
        if command and command[0] == "--":
            command = command[1:]
        return run(config, command)
    except LifecycleError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
