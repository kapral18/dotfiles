#!/usr/bin/env python3
"""Secure generation-specific client for the resident FastEmbed worker.

The per-turn path uses ``embed(..., connect_only=True)`` and never calls
``ensure``. Session-start adapters may call the bounded ``ensure`` operation.
Raw texts travel only inside a private Unix socket request.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import shutil
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_DIMENSION = 384
DEFAULT_IDLE_SECONDS = 300.0
DEFAULT_START_TIMEOUT_SECONDS = 8.0
PROTOCOL_VERSION = "1"
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_SOCKET_PATH_BYTES = 100
CONNECT_TIMEOUT_SECONDS = 0.12
REQUEST_TIMEOUT_SECONDS = 3.0
CONNECT_ONLY_REQUEST_TIMEOUT_SECONDS = 0.15
DISCOVERY_TIMEOUT_SECONDS = 0.04
MODEL_PROBE_TIMEOUT_SECONDS = 4.0
MAX_DISCOVERY_SOCKETS = 32
TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise socket.timeout("deadline exceeded")
    return remaining


def default_runtime_dir() -> Path:
    override = os.environ.get("AI_EMBED_RUNTIME_DIR")
    if override:
        return Path(override).expanduser()
    runtime_home = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_home:
        return Path(runtime_home) / "ai-embed"
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_home / "ai-embed-runtime"


def configured_model() -> str:
    """Return the model selected by the existing embedding override."""
    return os.environ.get("RALPH_EMBED_MODEL", "").strip() or DEFAULT_MODEL


def _worker_digest(worker: Path) -> str:
    return hashlib.sha256(worker.read_bytes()).hexdigest() if worker.is_file() else "missing"


def _generation(protocol_version: str, worker: Path, model: str, dimension: int) -> str:
    identity = "\0".join([protocol_version, _worker_digest(worker), model, str(dimension)]).encode()
    return hashlib.sha256(identity).hexdigest()[:20]


class RuntimeSpec:
    """Resolved worker identity and private runtime paths."""

    def __init__(
        self,
        *,
        runtime_dir: Path | str | None = None,
        model: str = DEFAULT_MODEL,
        dimension: int = DEFAULT_DIMENSION,
        idle_seconds: float | None = None,
        protocol_version: str = PROTOCOL_VERSION,
        worker: Path | str | None = None,
    ) -> None:
        self.runtime_dir = Path(runtime_dir) if runtime_dir is not None else default_runtime_dir()
        self.model = model
        self.dimension = dimension
        self.idle_seconds = (
            idle_seconds if idle_seconds is not None else _env_float("AI_EMBED_IDLE_SECONDS", DEFAULT_IDLE_SECONDS)
        )
        self.protocol_version = protocol_version
        self.worker = Path(worker) if worker is not None else Path(__file__).with_name("embed_worker.py")
        if not self.model or self.dimension <= 0 or self.idle_seconds <= 0 or not self.protocol_version:
            raise ValueError("invalid resident embed runtime specification")
        self.generation = _generation(self.protocol_version, self.worker, self.model, self.dimension)
        self.socket_path = self.runtime_dir / f"embed-{self.generation}.sock"
        self.lock_path = self.runtime_dir / f"start-{self.generation}.lock"
        self.start_marker_path = self.runtime_dir / f"starting-{self.generation}.json"


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def secure_runtime_dir(root: Path, *, create: bool = True) -> None:
    try:
        info = root.lstat()
    except FileNotFoundError:
        if not create:
            raise
        try:
            root.mkdir(parents=True, mode=0o700)
        except FileExistsError:
            pass
        info = root.lstat()
    if root.is_symlink() or not stat.S_ISDIR(info.st_mode):
        raise RuntimeError("runtime root is not a real directory")
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError("runtime root is not private and owned by this user")


def secure_runtime_root(spec: RuntimeSpec, *, create: bool = True) -> None:
    secure_runtime_dir(spec.runtime_dir, create=create)
    if len(os.fsencode(spec.socket_path)) > MAX_SOCKET_PATH_BYTES:
        raise RuntimeError("runtime socket path is too long")


def _owned_socket(path: Path) -> os.stat_result:
    info = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISSOCK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise RuntimeError("refusing a foreign or non-socket runtime path")
    return info


def _owned_start_marker(path: Path) -> os.stat_result:
    info = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise RuntimeError("refusing a foreign or invalid startup marker")
    return info


def _unlink_unchanged(path: Path, expected: os.stat_result) -> None:
    current = path.lstat()
    if (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
        raise RuntimeError("runtime marker changed during validation")
    path.unlink()


def _startup_marker_payload(spec: RuntimeSpec, pid: int) -> dict[str, object]:
    return {
        "pid": pid,
        "generation": spec.generation,
        "worker": os.fspath(spec.worker),
        "socket": os.fspath(spec.socket_path),
    }


def _process_matches_start(pid: int, spec: RuntimeSpec) -> bool:
    ps = shutil.which("ps")
    if ps is None:
        raise RuntimeError("cannot validate startup process identity")
    try:
        result = subprocess.run(
            [ps, "-o", "uid=", "-o", "command=", "-p", str(pid)],
            capture_output=True,
            check=False,
            text=True,
            timeout=0.5,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        raise RuntimeError("cannot validate startup process identity") from err
    fields = result.stdout.strip().split(maxsplit=1)
    if len(fields) != 2:
        return False
    try:
        uid = int(fields[0])
    except ValueError:
        return False
    command = fields[1]
    return (
        result.returncode == 0
        and uid == os.getuid()
        and bool(command)
        and os.fspath(spec.worker) in command
        and os.fspath(spec.socket_path) in command
        and spec.generation in command
    )


def _active_start_pid(spec: RuntimeSpec) -> int | None:
    try:
        info = _owned_start_marker(spec.start_marker_path)
    except FileNotFoundError:
        return None
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        marker_fd = os.open(spec.start_marker_path, flags)
        with os.fdopen(marker_fd, "rb") as marker:
            opened = os.fstat(marker.fileno())
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise RuntimeError("startup marker changed during validation")
            raw = marker.read(257)
        if len(raw) > 256:
            raise RuntimeError("startup marker is too large")
        payload = json.loads(raw)
    except (OSError, ValueError, json.JSONDecodeError) as err:
        _unlink_unchanged(spec.start_marker_path, info)
        return None
    pid = payload.get("pid") if isinstance(payload, dict) else None
    if (
        not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
        or payload.get("generation") != spec.generation
        or payload.get("worker") != os.fspath(spec.worker)
        or payload.get("socket") != os.fspath(spec.socket_path)
    ):
        _unlink_unchanged(spec.start_marker_path, info)
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        _unlink_unchanged(spec.start_marker_path, info)
        return None
    except PermissionError:
        pass
    if not _process_matches_start(pid, spec):
        _unlink_unchanged(spec.start_marker_path, info)
        return None
    return pid


def _request_socket(
    runtime_dir: Path,
    socket_path: Path,
    payload: dict,
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> dict:
    secure_runtime_dir(runtime_dir, create=False)
    _owned_socket(socket_path)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError("request exceeds protocol limit")
    deadline = time.monotonic() + timeout
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(_remaining_timeout(deadline))
        client.connect(os.fspath(socket_path))
        client.settimeout(_remaining_timeout(deadline))
        client.sendall(encoded)
        data = bytearray()
        while b"\n" not in data:
            if len(data) >= MAX_RESPONSE_BYTES:
                raise ValueError("response exceeds protocol limit")
            client.settimeout(_remaining_timeout(deadline))
            chunk = client.recv(min(65536, MAX_RESPONSE_BYTES - len(data)))
            if not chunk:
                break
            data.extend(chunk)
    raw = bytes(data).split(b"\n", 1)[0]
    if not raw:
        raise ValueError("empty worker response")
    response = json.loads(raw)
    if not isinstance(response, dict):
        raise ValueError("worker response is not an object")
    return response


def request(spec: RuntimeSpec, payload: dict, *, timeout: float = REQUEST_TIMEOUT_SECONDS) -> dict:
    return _request_socket(spec.runtime_dir, spec.socket_path, payload, timeout=timeout)


def discover_ready_spec(
    *,
    model: str | None = None,
    runtime_dir: Path | str | None = None,
    worker: Path | str | None = None,
    idle_seconds: float | None = None,
    protocol_version: str = PROTOCOL_VERSION,
    timeout: float = DISCOVERY_TIMEOUT_SECONDS,
) -> RuntimeSpec | None:
    """Discover one ready current-generation worker without spawning."""
    resolved_model = model or configured_model()
    resolved_runtime = Path(runtime_dir) if runtime_dir is not None else default_runtime_dir()
    resolved_worker = Path(worker) if worker is not None else Path(__file__).with_name("embed_worker.py")
    try:
        secure_runtime_dir(resolved_runtime, create=False)
    except FileNotFoundError:
        return None
    candidates = sorted(resolved_runtime.glob("embed-*.sock"))
    if len(candidates) > MAX_DISCOVERY_SOCKETS:
        return None
    preferred: Path | None = None
    if resolved_model == DEFAULT_MODEL:
        preferred = RuntimeSpec(
            runtime_dir=resolved_runtime,
            model=resolved_model,
            dimension=DEFAULT_DIMENSION,
            idle_seconds=idle_seconds,
            protocol_version=protocol_version,
            worker=resolved_worker,
        ).socket_path

    def candidate_key(path: Path) -> tuple[bool, int]:
        try:
            mtime = path.lstat().st_mtime_ns
        except OSError:
            mtime = 0
        return path != preferred, -mtime

    candidates.sort(key=candidate_key)
    matches: list[RuntimeSpec] = []
    deadline = time.monotonic() + min(DISCOVERY_TIMEOUT_SECONDS, timeout)
    for socket_path in candidates:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            response = _request_socket(
                resolved_runtime,
                socket_path,
                {"op": "ping"},
                timeout=min(CONNECT_TIMEOUT_SECONDS, remaining),
            )
        except (ConnectionError, OSError, RuntimeError, ValueError, json.JSONDecodeError, socket.timeout):
            continue
        dimension = response.get("dim")
        pid = response.get("pid")
        if (
            response.get("ok") is not True
            or response.get("status") != "ready"
            or response.get("model") != resolved_model
            or not isinstance(dimension, int)
            or isinstance(dimension, bool)
            or dimension <= 0
            or not isinstance(pid, int)
            or isinstance(pid, bool)
            or pid <= 0
        ):
            continue
        spec = RuntimeSpec(
            runtime_dir=resolved_runtime,
            model=resolved_model,
            dimension=dimension,
            idle_seconds=idle_seconds,
            protocol_version=protocol_version,
            worker=resolved_worker,
        )
        if response.get("generation") == spec.generation and socket_path == spec.socket_path:
            matches.append(spec)
    return matches[0] if len(matches) == 1 else None


def _probe_model_dimension(model: str, worker: Path, *, timeout: float = MODEL_PROBE_TIMEOUT_SECONDS) -> int:
    uv = shutil.which("uv")
    if uv is None or not worker.is_file():
        raise RuntimeError("resident embed worker dependencies are unavailable")
    try:
        result = subprocess.run(
            [
                uv,
                "run",
                "--quiet",
                "--no-project",
                "--script",
                os.fspath(worker),
                "--describe-model",
                model,
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        raise RuntimeError("resident model metadata probe failed") from err
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as err:
        raise RuntimeError("resident model metadata probe returned invalid output") from err
    dimension = payload.get("dimension")
    if (
        result.returncode != 0
        or payload.get("model") != model
        or not isinstance(dimension, int)
        or isinstance(dimension, bool)
        or dimension <= 0
    ):
        raise RuntimeError("resident model metadata is unavailable")
    return dimension


def resolve_start_spec(
    *,
    model: str | None = None,
    runtime_dir: Path | str | None = None,
    worker: Path | str | None = None,
    idle_seconds: float | None = None,
    protocol_version: str = PROTOCOL_VERSION,
    timeout: float = MODEL_PROBE_TIMEOUT_SECONDS,
) -> RuntimeSpec:
    """Resolve the exact model dimension on the warm path before spawning."""
    resolved_model = model or configured_model()
    resolved_worker = Path(worker) if worker is not None else Path(__file__).with_name("embed_worker.py")
    dimension = _probe_model_dimension(resolved_model, resolved_worker, timeout=timeout)
    return RuntimeSpec(
        runtime_dir=runtime_dir,
        model=resolved_model,
        dimension=dimension,
        idle_seconds=idle_seconds,
        protocol_version=protocol_version,
        worker=resolved_worker,
    )


def _probe(spec: RuntimeSpec, *, timeout: float = CONNECT_TIMEOUT_SECONDS) -> tuple[str, dict | None]:
    try:
        response = request(spec, {"op": "ping"}, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError):
        return "stale", None
    except socket.timeout:
        return "starting", None
    except (ConnectionError, OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return "invalid", None
    if response.get("generation") != spec.generation or response.get("model") != spec.model:
        return "invalid", response
    if response.get("ok") is True and response.get("status") == "ready":
        pid = response.get("pid")
        if isinstance(pid, int) and pid > 0:
            return "ready", response
        return "invalid", response
    if response.get("status") == "starting":
        return "starting", response
    return "invalid", response


def ping(spec: RuntimeSpec) -> dict | None:
    status_value, response = _probe(spec)
    return response if status_value == "ready" else None


def _wait_until_ready(spec: RuntimeSpec, deadline: float) -> dict:
    while True:
        try:
            remaining = _remaining_timeout(deadline)
        except socket.timeout:
            break
        status_value, response = _probe(spec, timeout=min(0.25, remaining))
        if status_value == "ready" and response is not None:
            return response
        if status_value == "invalid":
            if _active_start_pid(spec) is None:
                raise RuntimeError("worker returned an invalid identity or response")
        try:
            remaining = _remaining_timeout(deadline)
        except socket.timeout:
            break
        time.sleep(min(0.05, remaining))
    raise RuntimeError("worker did not become ready before the deadline")


def _publish_start_marker(spec: RuntimeSpec) -> None:
    temp_marker = spec.start_marker_path.with_name(f".{spec.start_marker_path.name}.{os.getpid()}.tmp")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        marker_fd = os.open(temp_marker, flags, 0o600)
        with os.fdopen(marker_fd, "wb") as marker:
            marker.write(json.dumps(_startup_marker_payload(spec, os.getpid()), separators=(",", ":")).encode() + b"\n")
            marker.flush()
            os.fsync(marker.fileno())
        os.link(temp_marker, spec.start_marker_path, follow_symlinks=False)
    finally:
        try:
            temp_marker.unlink()
        except FileNotFoundError:
            pass


def _spawn_detached(command: list[str], spec: RuntimeSpec) -> None:
    """Double-fork one worker and persist its pre-socket startup ownership."""
    child = os.fork()
    if child == 0:
        try:
            os.setsid()
            grandchild = os.fork()
            if grandchild > 0:
                os._exit(0)
            _publish_start_marker(spec)
            devnull = os.open(os.devnull, os.O_RDWR)
            for descriptor in (0, 1, 2):
                os.dup2(devnull, descriptor)
            if devnull > 2:
                os.close(devnull)
            os.execv(command[0], command)
        except BaseException:
            os._exit(127)
    _, status_value = os.waitpid(child, 0)
    if not os.WIFEXITED(status_value) or os.WEXITSTATUS(status_value) != 0:
        raise RuntimeError("worker launcher failed")


def ensure(spec: RuntimeSpec, *, timeout: float = DEFAULT_START_TIMEOUT_SECONDS) -> dict:
    """Return one ready worker, starting at most one process per generation."""
    secure_runtime_root(spec)
    if not spec.worker.is_file():
        raise RuntimeError("resident embed worker dependencies are unavailable")

    deadline = time.monotonic() + timeout
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    lock_fd = os.open(spec.lock_path, flags, 0o600)
    with os.fdopen(lock_fd, "r+") as lock:
        lock_info = os.fstat(lock.fileno())
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != os.getuid():
            raise RuntimeError("start lock is not a user-owned regular file")
        os.fchmod(lock.fileno(), 0o600)
        # Charge lock waiting to the same absolute deadline as every other blocking step.
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, InterruptedError):
                try:
                    remaining = _remaining_timeout(deadline)
                except socket.timeout as err:
                    raise RuntimeError("worker did not become ready before the deadline") from err
                time.sleep(min(0.05, remaining))
        try:
            remaining = _remaining_timeout(deadline)
        except socket.timeout as err:
            raise RuntimeError("worker did not become ready before the deadline") from err
        status_value, response = _probe(spec, timeout=min(CONNECT_TIMEOUT_SECONDS, remaining))
        if status_value == "ready" and response is not None:
            return response
        if status_value == "starting":
            return _wait_until_ready(spec, deadline)
        if status_value == "invalid":
            if _active_start_pid(spec) is not None:
                return _wait_until_ready(spec, deadline)
            raise RuntimeError("refusing an invalid live worker socket")
        if _lexists(spec.socket_path):
            _owned_socket(spec.socket_path)
            spec.socket_path.unlink()
        if _active_start_pid(spec) is not None:
            return _wait_until_ready(spec, deadline)

        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError("resident embed worker dependencies are unavailable")
        try:
            _remaining_timeout(deadline)
        except socket.timeout as err:
            raise RuntimeError("worker did not become ready before the deadline") from err
        _spawn_detached(
            [
                uv,
                "run",
                "--quiet",
                "--no-project",
                "--script",
                os.fspath(spec.worker),
                "--socket",
                os.fspath(spec.socket_path),
                "--generation",
                spec.generation,
                "--model",
                spec.model,
                "--dimension",
                str(spec.dimension),
                "--idle-seconds",
                str(spec.idle_seconds),
                "--start-marker",
                os.fspath(spec.start_marker_path),
            ],
            spec,
        )
        return _wait_until_ready(spec, deadline)


def _valid_vectors(vectors: object, *, count: int, dimension: int) -> bool:
    if not isinstance(vectors, list) or len(vectors) != count:
        return False
    for vector in vectors:
        if not isinstance(vector, list) or len(vector) != dimension:
            return False
        if not all(
            not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) for value in vector
        ):
            return False
    return True


def embed(spec: RuntimeSpec, texts: list[str], *, connect_only: bool) -> dict:
    if not texts or len(texts) > 8 or not all(isinstance(text, str) and 0 < len(text) <= 4096 for text in texts):
        return {"available": False, "vectors": [], "reason": "invalid_request"}
    if not connect_only:
        try:
            ensure(spec)
        except (OSError, RuntimeError, ValueError):
            return {"available": False, "vectors": [], "reason": "unavailable"}
    try:
        response = request(
            spec,
            {"op": "embed", "generation": spec.generation, "texts": texts},
            timeout=CONNECT_ONLY_REQUEST_TIMEOUT_SECONDS if connect_only else REQUEST_TIMEOUT_SECONDS,
        )
    except (OSError, RuntimeError, ValueError, socket.timeout, json.JSONDecodeError):
        return {"available": False, "vectors": [], "reason": "unavailable"}
    if (
        response.get("ok") is not True
        or response.get("generation") != spec.generation
        or response.get("model") != spec.model
        or response.get("dim") != spec.dimension
        or not _valid_vectors(response.get("vectors"), count=len(texts), dimension=spec.dimension)
    ):
        return {"available": False, "vectors": [], "reason": "invalid_response"}
    return response


def shutdown(spec: RuntimeSpec) -> dict:
    current = ping(spec)
    if current is None:
        return {"available": False}
    try:
        response = request(spec, {"op": "shutdown", "generation": spec.generation}, timeout=1.0)
    except (OSError, RuntimeError, ValueError, socket.timeout, json.JSONDecodeError):
        return {"available": False}
    deadline = time.monotonic() + 1.0
    while _lexists(spec.socket_path) and time.monotonic() < deadline:
        time.sleep(0.02)
    return response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the resident FastEmbed worker")
    parser.add_argument("command", choices=("ensure", "ping", "shutdown"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_START_TIMEOUT_SECONDS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "ensure":
            deadline = time.monotonic() + args.timeout
            spec = discover_ready_spec(timeout=_remaining_timeout(deadline))
            if spec is None:
                spec = resolve_start_spec(timeout=_remaining_timeout(deadline))
            output = ensure(spec, timeout=_remaining_timeout(deadline))
        else:
            spec = discover_ready_spec()
            if spec is None:
                output = {"available": False}
            elif args.command == "ping":
                output = ping(spec) or {"available": False}
            else:
                output = shutdown(spec)
    except (OSError, RuntimeError, ValueError):
        output = {"available": False, "reason": "unavailable"}
        print(json.dumps(output, sort_keys=True))
        return 1
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
