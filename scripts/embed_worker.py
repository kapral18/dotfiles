#!/usr/bin/env -S uv run --quiet --no-project --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastembed>=0.3,<1.0",
# ]
# ///
"""Private line-JSON FastEmbed worker. Never logs or echoes request text."""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import stat
import threading
import time
from pathlib import Path

MAX_REQUEST_BYTES = 64 * 1024
STARTUP_TIMEOUT_SECONDS = 120.0
REQUEST_TIMEOUT_SECONDS = 3.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--describe-model")
    parser.add_argument("--socket")
    parser.add_argument("--generation")
    parser.add_argument("--model")
    parser.add_argument("--dimension", type=int)
    parser.add_argument("--idle-seconds", type=float)
    parser.add_argument("--start-marker")
    return parser.parse_args()


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _private_root(path: Path) -> None:
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(info.st_mode):
        raise RuntimeError("runtime root is not a real directory")
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError("runtime root is not private and owned by this user")


def receive_line(
    conn: socket.socket,
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> tuple[bytes | None, str | None]:
    data = bytearray()
    deadline = time.monotonic() + timeout
    while len(data) <= MAX_REQUEST_BYTES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise socket.timeout("request deadline exceeded")
        conn.settimeout(remaining)
        chunk = conn.recv(min(4096, MAX_REQUEST_BYTES + 1 - len(data)))
        if not chunk:
            return bytes(data), None
        data.extend(chunk)
        if b"\n" in data:
            return bytes(data).split(b"\n", 1)[0], None
    return None, "request_too_large"


def _send(conn: socket.socket, response: dict) -> None:
    conn.sendall(json.dumps(response, separators=(",", ":")).encode() + b"\n")


def _valid_texts(value: object) -> bool:
    return (
        isinstance(value, list)
        and 0 < len(value) <= 8
        and all(isinstance(text, str) and 0 < len(text) <= 4096 for text in value)
    )


def _unlink_owned_socket(path: Path, identity: tuple[int, int]) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid() and (info.st_dev, info.st_ino) == identity:
        path.unlink()


def _unlink_start_marker(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if (
        path.is_symlink()
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise RuntimeError("invalid startup marker")
    current = path.lstat()
    if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
        raise RuntimeError("startup marker changed during validation")
    path.unlink()


def _describe_model(model_id: str) -> int:
    from fastembed import TextEmbedding

    normalized = model_id.casefold()
    for model in TextEmbedding.list_supported_models():
        candidate = model.get("model")
        if isinstance(candidate, str) and candidate.casefold() == normalized:
            dimension = model.get("dim")
            if isinstance(dimension, int) and not isinstance(dimension, bool) and dimension > 0:
                return dimension
    raise ValueError("model metadata unavailable")


def main() -> int:
    args = parse_args()
    if args.describe_model:
        try:
            dimension = _describe_model(args.describe_model)
        except Exception:
            print(json.dumps({"error": "model_metadata_unavailable"}, separators=(",", ":")))
            return 1
        print(json.dumps({"model": args.describe_model, "dimension": dimension}, separators=(",", ":")))
        return 0
    if (
        not args.socket
        or not args.generation
        or not args.model
        or args.dimension is None
        or args.dimension <= 0
        or args.idle_seconds is None
        or args.idle_seconds <= 0
        or not args.start_marker
    ):
        return 2
    socket_path = Path(args.socket)
    start_marker = Path(args.start_marker)
    if start_marker != socket_path.parent / f"starting-{args.generation}.json":
        return 2
    _private_root(socket_path.parent)
    if _lexists(socket_path):
        return 1

    os.umask(0o077)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(os.fspath(socket_path))
    os.chmod(socket_path, 0o600)
    socket_info = socket_path.lstat()
    socket_identity = (socket_info.st_dev, socket_info.st_ino)
    server.listen(16)
    server.settimeout(0.2)
    _unlink_start_marker(start_marker)

    state: dict[str, object] = {"model": None, "error": None}
    loaded = threading.Event()

    def load_model() -> None:
        try:
            from fastembed import TextEmbedding

            state["model"] = TextEmbedding(model_name=args.model)
        except Exception:
            state["error"] = "model_load_failed"
        finally:
            loaded.set()

    threading.Thread(target=load_model, daemon=True).start()
    started_at = time.monotonic()
    last_active = started_at
    ready_observed = False
    running = True
    try:
        while running:
            now = time.monotonic()
            if not loaded.is_set() and now - started_at >= STARTUP_TIMEOUT_SECONDS:
                break
            if loaded.is_set() and state["error"] is not None:
                break
            if loaded.is_set() and not ready_observed:
                ready_observed = True
                last_active = now
            if loaded.is_set() and now - last_active >= args.idle_seconds:
                break
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            last_active = time.monotonic()
            with conn:
                try:
                    raw, framing_error = receive_line(conn)
                    if framing_error:
                        response = {"error": framing_error}
                    else:
                        request = json.loads(raw or b"")
                        if not isinstance(request, dict):
                            response = {"error": "invalid_request"}
                        elif request.get("op") == "ping":
                            response = {
                                "ok": loaded.is_set() and state["error"] is None,
                                "status": "ready" if loaded.is_set() and state["error"] is None else "starting",
                                "generation": args.generation,
                                "model": args.model,
                                "dim": args.dimension,
                                "pid": os.getpid(),
                            }
                        elif request.get("generation") != args.generation:
                            response = {"error": "generation_mismatch"}
                        elif request.get("op") == "shutdown":
                            response = {"ok": True, "pid": os.getpid()}
                            running = False
                        elif request.get("op") != "embed":
                            response = {"error": "unknown_op"}
                        elif not loaded.is_set() or state["model"] is None:
                            response = {"error": "starting"}
                        elif not _valid_texts(request.get("texts")):
                            response = {"error": "invalid_texts"}
                        else:
                            model = state["model"]
                            vectors = [list(map(float, vector)) for vector in model.embed(request["texts"])]
                            valid = all(
                                len(vector) == args.dimension and all(math.isfinite(value) for value in vector)
                                for vector in vectors
                            )
                            response = (
                                {
                                    "ok": True,
                                    "generation": args.generation,
                                    "model": args.model,
                                    "dim": args.dimension,
                                    "vectors": vectors,
                                }
                                if valid
                                else {"error": "invalid_vectors"}
                            )
                except (OSError, ValueError, json.JSONDecodeError, TypeError):
                    response = {"error": "invalid_request"}
                try:
                    _send(conn, response)
                except OSError:
                    pass
    finally:
        server.close()
        _unlink_owned_socket(socket_path, socket_identity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
