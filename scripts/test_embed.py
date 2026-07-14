#!/usr/bin/env python3
"""Tests for embed.py helper behavior."""

from __future__ import annotations

import concurrent.futures
import contextlib
import fcntl
import json
import os
import shutil
import socket
import stat
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import _test_support  # noqa: F401  (puts scripts/ on sys.path)

FAKE_FASTEMBED_WORKER = """#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
import sys
import types

module = types.ModuleType("fastembed")

class TextEmbedding:
    def __init__(self, model_name):
        self.model_name = model_name

    def embed(self, texts):
        for text in texts:
            value = float((sum(text.encode()) % 9) + 1) / 10.0
            yield [value] * 384

module.TextEmbedding = TextEmbedding
sys.modules["fastembed"] = module

from embed_worker import main

raise SystemExit(main())
"""


@contextlib.contextmanager
def short_runtime_directory():
    root = Path(".embed-test-tmp")
    root.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            yield tmp
    finally:
        try:
            root.rmdir()
        except OSError:
            pass


class TestEmbedModuleHelpers(unittest.TestCase):
    """Small unit tests for the embed module helpers that don't need
    the runner: pack/unpack, cosine math, default constants."""

    def test_pack_unpack_roundtrip(self):
        import embed

        v = [0.1, -0.5, 1.234, 0.0, -1e-3]
        blob = embed.pack_vector(v)
        assert len(blob) == len(v) * 4
        out = embed.unpack_vector(blob)
        assert len(out) == len(v)
        for a, b in zip(v, out):
            assert abs(a - b) < 1e-6

    def test_unpack_handles_none_and_empty(self):
        import embed

        assert embed.unpack_vector(None) == []
        assert embed.unpack_vector(b"") == []

    def test_cosine_basic_math(self):
        import embed

        assert embed.cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
        assert abs(embed.cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9
        assert embed.cosine([], [1.0]) == 0.0
        assert embed.cosine([1.0], [1.0, 2.0]) == 0.0  # length mismatch


class TestResidentEmbedRuntime(unittest.TestCase):
    """WHEN interactive recall opts into the resident connect-only lane."""

    def test_generation_identity_covers_protocol_worker_model_and_dimension(self):
        import embed_client

        with short_runtime_directory() as tmp:
            root = Path(tmp)
            worker_a = root / "worker-a.py"
            worker_b = root / "worker-b.py"
            worker_a.write_text("# dependency-v1\n")
            worker_b.write_text("# dependency-v2\n")
            base = embed_client.RuntimeSpec(runtime_dir=root / "runtime", worker=worker_a)
            changed_worker = embed_client.RuntimeSpec(runtime_dir=root / "runtime", worker=worker_b)
            changed_protocol = embed_client.RuntimeSpec(
                runtime_dir=root / "runtime", worker=worker_a, protocol_version="2"
            )
            changed_model = embed_client.RuntimeSpec(runtime_dir=root / "runtime", worker=worker_a, model="other")
            changed_dimension = embed_client.RuntimeSpec(runtime_dir=root / "runtime", worker=worker_a, dimension=768)

        self.assertEqual(
            len(
                {
                    base.generation,
                    changed_worker.generation,
                    changed_protocol.generation,
                    changed_model.generation,
                    changed_dimension.generation,
                }
            ),
            5,
        )

    def test_runtime_root_and_replacement_socket_are_fail_closed(self):
        import embed_client
        import embed_worker

        with short_runtime_directory() as tmp:
            root = Path(tmp)
            worker = root / "worker.py"
            worker.write_text("# worker\n")
            runtime = root / "runtime"
            spec = embed_client.RuntimeSpec(runtime_dir=runtime, worker=worker)
            embed_client.secure_runtime_root(spec)
            self.assertEqual(stat.S_IMODE(runtime.stat().st_mode), 0o700)

            replacement = mock.Mock()
            replacement.lstat.return_value = SimpleNamespace(
                st_mode=stat.S_IFSOCK | 0o600,
                st_uid=os.getuid(),
                st_dev=2,
                st_ino=2,
            )
            embed_worker._unlink_owned_socket(replacement, (1, 1))
            replacement.unlink.assert_not_called()

    def test_concurrent_cold_callers_create_one_private_runtime_root(self):
        import embed_client

        with short_runtime_directory() as tmp:
            spec = embed_client.RuntimeSpec(runtime_dir=Path(tmp) / "runtime")
            barrier = threading.Barrier(32)

            def secure_root() -> None:
                barrier.wait()
                embed_client.secure_runtime_root(spec)

            with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
                futures = [pool.submit(secure_root) for _ in range(32)]
            for future in futures:
                future.result()

            self.assertEqual(stat.S_IMODE(spec.runtime_dir.stat().st_mode), 0o700)

    def test_timed_out_startup_marker_prevents_duplicate_launch(self):
        import embed_client

        with short_runtime_directory() as tmp:
            root = Path(tmp)
            worker = root / "worker.py"
            worker.write_text("# worker\n")
            spec = embed_client.RuntimeSpec(runtime_dir=root / "runtime", worker=worker)

            def mark_starting(_command: list[str], starting_spec: embed_client.RuntimeSpec) -> None:
                starting_spec.start_marker_path.write_text(
                    json.dumps(embed_client._startup_marker_payload(starting_spec, os.getpid()))
                )
                os.chmod(starting_spec.start_marker_path, 0o600)

            with (
                mock.patch.object(embed_client, "_probe", return_value=("stale", None)),
                mock.patch.object(embed_client, "_spawn_detached", side_effect=mark_starting) as spawn,
                mock.patch.object(embed_client, "_process_matches_start", return_value=True),
                mock.patch.object(embed_client.shutil, "which", return_value="/usr/bin/uv"),
            ):
                with self.assertRaisesRegex(RuntimeError, "did not become ready"):
                    embed_client.ensure(spec, timeout=0.01)
                with self.assertRaisesRegex(RuntimeError, "did not become ready"):
                    embed_client.ensure(spec, timeout=0.01)

            spawn.assert_called_once()

    def test_ensure_lock_contention_is_bounded_by_one_absolute_deadline(self):
        import embed_client

        with short_runtime_directory() as tmp:
            root = Path(tmp)
            worker = root / "worker.py"
            worker.write_text("# worker\n")
            spec = embed_client.RuntimeSpec(runtime_dir=root / "runtime", worker=worker)
            embed_client.secure_runtime_root(spec)

            holder = os.open(spec.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(holder, fcntl.LOCK_EX)
                started = time.monotonic()
                with self.assertRaisesRegex(RuntimeError, "did not become ready"):
                    embed_client.ensure(spec, timeout=0.2)
                self.assertLess(time.monotonic() - started, 2.0)
            finally:
                os.close(holder)

    def test_malformed_owned_startup_marker_is_retired(self):
        import embed_client

        with short_runtime_directory() as tmp:
            root = Path(tmp)
            worker = root / "worker.py"
            worker.write_text("# worker\n")
            spec = embed_client.RuntimeSpec(runtime_dir=root / "runtime", worker=worker)
            embed_client.secure_runtime_root(spec)
            spec.start_marker_path.write_bytes(b'{"pid":')
            os.chmod(spec.start_marker_path, 0o600)

            self.assertIsNone(embed_client._active_start_pid(spec))
            self.assertFalse(spec.start_marker_path.exists())

    def test_inaccessible_reused_pid_marker_is_retired(self):
        import embed_client

        with short_runtime_directory() as tmp:
            root = Path(tmp)
            worker = root / "worker.py"
            worker.write_text("# worker\n")
            spec = embed_client.RuntimeSpec(runtime_dir=root / "runtime", worker=worker)
            embed_client.secure_runtime_root(spec)
            spec.start_marker_path.write_text(json.dumps(embed_client._startup_marker_payload(spec, 1)))
            os.chmod(spec.start_marker_path, 0o600)

            with (
                mock.patch.object(embed_client.os, "kill", side_effect=PermissionError),
                mock.patch.object(embed_client, "_process_matches_start", return_value=False) as identity,
            ):
                self.assertIsNone(embed_client._active_start_pid(spec))

            identity.assert_called_once_with(1, spec)
            self.assertFalse(spec.start_marker_path.exists())

    def test_ready_worker_reuse_does_not_require_uv_on_path(self):
        import embed_client

        with short_runtime_directory() as tmp:
            root = Path(tmp)
            worker = root / "worker.py"
            worker.write_text("# worker\n")
            spec = embed_client.RuntimeSpec(runtime_dir=root / "runtime", worker=worker)
            ready = {
                "ok": True,
                "status": "ready",
                "generation": spec.generation,
                "model": spec.model,
                "pid": 42,
            }
            with (
                mock.patch.object(embed_client, "_probe", return_value=("ready", ready)),
                mock.patch.object(embed_client.shutil, "which", return_value=None),
            ):
                self.assertEqual(embed_client.ensure(spec), ready)

    def test_connect_only_never_ensures_and_rejects_malformed_vectors(self):
        import embed_client

        with short_runtime_directory() as tmp:
            worker = Path(tmp) / "worker.py"
            worker.write_text("# worker\n")
            spec = embed_client.RuntimeSpec(runtime_dir=Path(tmp) / "runtime", worker=worker)
            with mock.patch.object(embed_client, "ensure", side_effect=AssertionError("must not spawn")):
                unavailable = embed_client.embed(spec, ["substantive prompt"], connect_only=True)
            self.assertEqual(unavailable["available"], False)
            self.assertFalse(embed_client._valid_vectors([[0.0] * 383 + [float("nan")]], count=1, dimension=384))
            self.assertFalse(embed_client._valid_vectors([[True] * 384], count=1, dimension=384))
            malformed_response = {
                "ok": True,
                "generation": spec.generation,
                "model": spec.model,
                "dim": spec.dimension,
                "vectors": [[0.0] * (spec.dimension - 1)],
            }
            with mock.patch.object(embed_client, "request", return_value=malformed_response):
                rejected = embed_client.embed(spec, ["malformed response"], connect_only=True)
            self.assertEqual(rejected["reason"], "invalid_response")

    def test_connect_only_never_discloses_text_to_an_insecure_socket(self):
        import embed_client

        secret = "SENSITIVE_CONNECT_ONLY_CANARY"
        for root_mode, socket_mode in ((0o755, 0o600), (0o700, 0o644)):
            with self.subTest(root_mode=oct(root_mode), socket_mode=oct(socket_mode)):
                with short_runtime_directory() as tmp:
                    root = Path(tmp) / "runtime"
                    root.mkdir(mode=root_mode)
                    os.chmod(root, root_mode)
                    worker = Path(tmp) / "worker.py"
                    worker.write_text("# worker\n")
                    spec = embed_client.RuntimeSpec(runtime_dir=root, worker=worker)
                    received = bytearray()
                    ready = threading.Event()

                    def capture_request() -> None:
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                            server.bind(str(spec.socket_path))
                            os.chmod(spec.socket_path, socket_mode)
                            server.listen(1)
                            server.settimeout(0.3)
                            ready.set()
                            try:
                                conn, _ = server.accept()
                            except socket.timeout:
                                return
                            with conn:
                                received.extend(conn.recv(65536))

                    thread = threading.Thread(target=capture_request)
                    thread.start()
                    self.assertTrue(ready.wait(timeout=1))
                    response = embed_client.embed(spec, [secret], connect_only=True)
                    thread.join(timeout=1)

                    self.assertFalse(response.get("available", True))
                    self.assertNotIn(secret.encode(), bytes(received))

    def test_connect_only_hung_worker_fails_open_under_hot_path_budget(self):
        import embed_client

        with short_runtime_directory() as tmp:
            root = Path(tmp) / "runtime"
            root.mkdir(mode=0o700)
            worker = Path(tmp) / "worker.py"
            worker.write_text("# worker\n")
            spec = embed_client.RuntimeSpec(runtime_dir=root, worker=worker)
            ready = threading.Event()

            def hang_after_accept() -> None:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                    server.bind(str(spec.socket_path))
                    os.chmod(spec.socket_path, 0o600)
                    server.listen(1)
                    ready.set()
                    conn, _ = server.accept()
                    with conn:
                        conn.recv(65536)
                        time.sleep(0.4)

            thread = threading.Thread(target=hang_after_accept)
            thread.start()
            self.assertTrue(ready.wait(timeout=1))
            started = time.perf_counter()
            response = embed_client.embed(spec, ["bounded hung worker"], connect_only=True)
            elapsed = time.perf_counter() - started
            thread.join(timeout=1)

            self.assertFalse(response.get("available", True))
            self.assertLessEqual(elapsed, 0.2)

    def test_connect_only_progressive_response_uses_one_absolute_deadline(self):
        import embed_client

        with short_runtime_directory() as tmp:
            root = Path(tmp) / "runtime"
            root.mkdir(mode=0o700)
            worker = Path(tmp) / "worker.py"
            worker.write_text("# worker\n")
            spec = embed_client.RuntimeSpec(runtime_dir=root, worker=worker)
            ready = threading.Event()
            response = (
                json.dumps(
                    {
                        "ok": True,
                        "generation": spec.generation,
                        "model": spec.model,
                        "dim": spec.dimension,
                        "vectors": [[0.0] * spec.dimension],
                    }
                ).encode()
                + b"\n"
            )

            def drip_response() -> None:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                    server.bind(str(spec.socket_path))
                    os.chmod(spec.socket_path, 0o600)
                    server.listen(1)
                    ready.set()
                    conn, _ = server.accept()
                    with conn:
                        conn.recv(65536)
                        chunk_size = max(1, len(response) // 6)
                        for offset in range(0, len(response), chunk_size):
                            try:
                                conn.sendall(response[offset : offset + chunk_size])
                            except BrokenPipeError:
                                return
                            time.sleep(0.05)

            thread = threading.Thread(target=drip_response)
            thread.start()
            self.assertTrue(ready.wait(timeout=1))
            started = time.perf_counter()
            result = embed_client.embed(spec, ["progressive response"], connect_only=True)
            elapsed = time.perf_counter() - started
            thread.join(timeout=1)

            self.assertFalse(result.get("available", True))
            self.assertLessEqual(elapsed, 0.2)

    def test_startup_polling_caps_each_probe_to_the_remaining_deadline(self):
        import embed_client

        with short_runtime_directory() as tmp:
            worker = Path(tmp) / "worker.py"
            worker.write_text("# worker\n")
            spec = embed_client.RuntimeSpec(runtime_dir=Path(tmp) / "runtime", worker=worker)

            def slow_probe(_spec: embed_client.RuntimeSpec, *, timeout: float):
                time.sleep(timeout)
                return "starting", None

            started = time.perf_counter()
            with (
                mock.patch.object(embed_client, "_probe", side_effect=slow_probe),
                self.assertRaisesRegex(RuntimeError, "deadline"),
            ):
                embed_client._wait_until_ready(spec, time.monotonic() + 0.01)
            elapsed = time.perf_counter() - started

        self.assertLessEqual(elapsed, 0.05)

    def test_worker_receive_line_uses_one_absolute_deadline(self):
        import embed_worker

        receiver, sender = socket.socketpair()

        def drip_request() -> None:
            with sender:
                for byte in b'{"op":"ping"}\n':
                    try:
                        sender.send(bytes([byte]))
                    except BrokenPipeError:
                        return
                    time.sleep(0.03)

        thread = threading.Thread(target=drip_request)
        thread.start()
        started = time.perf_counter()
        with receiver, self.assertRaises(socket.timeout):
            embed_worker.receive_line(receiver, timeout=0.1)
        elapsed = time.perf_counter() - started
        thread.join(timeout=1)

        self.assertLessEqual(elapsed, 0.15)

    def test_embedder_selects_resident_only_for_explicit_connect_only_mode(self):
        import embed
        import embed_client

        response = {
            "ok": True,
            "generation": "test",
            "model": embed.DEFAULT_MODEL,
            "dim": embed.DEFAULT_DIM,
            "vectors": [[0.0] * embed.DEFAULT_DIM],
        }
        with mock.patch.dict(os.environ, {"AI_EMBED_CONNECT_ONLY": "1"}, clear=False):
            with (
                mock.patch.object(
                    embed_client,
                    "discover_ready_spec",
                    return_value=SimpleNamespace(),
                ) as discover,
                mock.patch.object(embed_client, "embed", return_value=response) as resident,
            ):
                embedder = embed.Embedder()
                self.assertTrue(embedder.is_available())
                vector = embedder.embed_one("resident prompt")
        self.assertEqual(len(vector), embed.DEFAULT_DIM)
        discover.assert_called_once_with(model=embed.DEFAULT_MODEL)
        resident.assert_called_once()
        self.assertTrue(resident.call_args.kwargs["connect_only"])

    def test_discovery_uses_one_absolute_hot_path_deadline(self):
        import embed_client

        with short_runtime_directory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime"
            worker = root / "worker.py"
            worker.write_text("# worker\n")
            model = "custom-model"
            current = embed_client.RuntimeSpec(runtime_dir=runtime, worker=worker, model=model)
            stale = embed_client.RuntimeSpec(
                runtime_dir=runtime,
                worker=worker,
                model=model,
                protocol_version="stale",
            )
            embed_client.secure_runtime_root(current)
            sockets: list[socket.socket] = []
            try:
                for spec in (current, stale):
                    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    server.bind(str(spec.socket_path))
                    os.chmod(spec.socket_path, 0o600)
                    sockets.append(server)
                os.utime(stale.socket_path, None)

                def hung_request(_runtime: Path, socket_path: Path, _payload: dict, *, timeout: float):
                    self.assertEqual(socket_path, stale.socket_path)
                    time.sleep(timeout)
                    raise socket.timeout

                started = time.perf_counter()
                with mock.patch.object(embed_client, "_request_socket", side_effect=hung_request) as request:
                    self.assertIsNone(
                        embed_client.discover_ready_spec(
                            model=model,
                            runtime_dir=runtime,
                            worker=worker,
                        )
                    )
                elapsed = time.perf_counter() - started
            finally:
                for server in sockets:
                    server.close()

        request.assert_called_once()
        self.assertLessEqual(elapsed, 0.08)

    def test_model_metadata_lookup_matches_fastembed_case_insensitively(self):
        import embed_worker

        fake = types.ModuleType("fastembed")
        fake.TextEmbedding = SimpleNamespace(
            list_supported_models=lambda: [{"model": "BAAI/bge-small-en-v1.5", "dim": 384}]
        )
        with mock.patch.dict("sys.modules", {"fastembed": fake}):
            self.assertEqual(embed_worker._describe_model("baai/BGE-small-en-v1.5"), 384)

    def test_model_override_warmup_and_connect_only_discovery_share_generation(self):
        import embed_client

        custom_model = "BAAI/bge-base-en-v1.5"
        with short_runtime_directory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime"
            worker = root / "worker.py"
            worker.write_text("# worker\n")
            with (
                mock.patch.dict(os.environ, {"AI_KB_EMBED_MODEL": custom_model}, clear=False),
                mock.patch.object(embed_client, "_probe_model_dimension", return_value=768),
            ):
                warm_spec = embed_client.resolve_start_spec(runtime_dir=runtime, worker=worker)
            embed_client.secure_runtime_root(warm_spec)

            ready = threading.Event()

            def serve_ping() -> None:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                    server.bind(str(warm_spec.socket_path))
                    os.chmod(warm_spec.socket_path, 0o600)
                    server.listen(1)
                    ready.set()
                    conn, _ = server.accept()
                    with conn:
                        conn.recv(4096)
                        conn.sendall(
                            json.dumps(
                                {
                                    "ok": True,
                                    "status": "ready",
                                    "generation": warm_spec.generation,
                                    "model": custom_model,
                                    "dim": 768,
                                    "pid": os.getpid(),
                                }
                            ).encode()
                            + b"\n"
                        )

            thread = threading.Thread(target=serve_ping)
            thread.start()
            self.assertTrue(ready.wait(timeout=1))
            discovered = embed_client.discover_ready_spec(
                model=custom_model,
                runtime_dir=runtime,
                worker=worker,
            )
            thread.join(timeout=1)

            self.assertIsNotNone(discovered)
            self.assertEqual(discovered.generation, warm_spec.generation)
            self.assertEqual(discovered.dimension, 768)

    @unittest.skipUnless(shutil.which("uv"), "uv is required for the live resident protocol test")
    def test_live_worker_protocol_generations_concurrency_and_idle_exit(self):
        import embed_client

        with short_runtime_directory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime"
            worker_a = root / "worker-a.py"
            worker_b = root / "worker-b.py"
            worker_idle = root / "worker-idle.py"
            worker_a.write_text(FAKE_FASTEMBED_WORKER + "\n# generation-a\n")
            worker_b.write_text(FAKE_FASTEMBED_WORKER + "\n# generation-b\n")
            worker_idle.write_text(FAKE_FASTEMBED_WORKER + "\n# generation-idle\n")
            spec_a = embed_client.RuntimeSpec(runtime_dir=runtime, worker=worker_a, idle_seconds=5)
            spec_b = embed_client.RuntimeSpec(runtime_dir=runtime, worker=worker_b, idle_seconds=5)
            spec_idle = embed_client.RuntimeSpec(runtime_dir=runtime, worker=worker_idle, idle_seconds=0.2)
            env = {
                "PYTHONPATH": str(Path(__file__).parent),
                "UV_CACHE_DIR": str(root / "uv-cache"),
            }

            embed_client.secure_runtime_root(spec_a)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stale:
                stale.bind(str(spec_a.socket_path))
                os.chmod(spec_a.socket_path, 0o600)

            with mock.patch.dict(os.environ, env, clear=False):
                started: list[embed_client.RuntimeSpec] = []
                try:
                    ready_a = embed_client.ensure(spec_a, timeout=5)
                    started.append(spec_a)
                    self.assertNotEqual(ready_a["pid"], 0)
                    self.assertEqual(stat.S_IMODE(spec_a.lock_path.stat().st_mode), 0o600)
                    self.assertEqual(stat.S_IMODE(spec_a.socket_path.stat().st_mode), 0o600)
                    self.assertFalse(spec_a.start_marker_path.exists())

                    ready_b = embed_client.ensure(spec_b, timeout=5)
                    started.append(spec_b)
                    self.assertNotEqual(ready_a["pid"], ready_b["pid"])
                    self.assertFalse(spec_b.start_marker_path.exists())
                    self.assertEqual(embed_client.ping(spec_a)["pid"], ready_a["pid"])
                    self.assertEqual(embed_client.ping(spec_b)["pid"], ready_b["pid"])

                    def raw_request(spec: embed_client.RuntimeSpec, payload: bytes) -> dict:
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                            client.settimeout(1)
                            client.connect(str(spec.socket_path))
                            client.sendall(payload + b"\n")
                            return json.loads(client.recv(4096).split(b"\n", 1)[0])

                    canary = b"PROTOCOL_SECRET_CANARY"
                    malformed = raw_request(spec_a, b'{"op":' + canary)
                    self.assertEqual(malformed, {"error": "invalid_request"})
                    self.assertNotIn(canary.decode(), json.dumps(malformed))
                    oversized = raw_request(spec_a, b"x" * (embed_client.MAX_REQUEST_BYTES + 1))
                    self.assertEqual(oversized, {"error": "request_too_large"})
                    wrong_generation = raw_request(
                        spec_a,
                        json.dumps({"op": "embed", "generation": "wrong", "texts": [canary.decode()]}).encode(),
                    )
                    self.assertEqual(wrong_generation, {"error": "generation_mismatch"})
                    self.assertIsNotNone(embed_client.ping(spec_a))

                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                        responses = list(
                            pool.map(
                                lambda index: embed_client.embed(
                                    spec_a,
                                    [f"parallel request {index}"],
                                    connect_only=True,
                                ),
                                range(8),
                            )
                        )
                    self.assertTrue(all(row.get("ok") is True for row in responses), responses)

                    self.assertTrue(embed_client.shutdown(spec_a).get("ok"))
                    started.remove(spec_a)
                    unavailable = embed_client.embed(spec_a, ["must not restart"], connect_only=True)
                    self.assertFalse(unavailable.get("available", True))
                    self.assertFalse(spec_a.socket_path.exists())

                    embed_client.ensure(spec_idle, timeout=5)
                    started.append(spec_idle)
                    deadline = time.monotonic() + 2
                    while spec_idle.socket_path.exists() and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertFalse(spec_idle.socket_path.exists())
                    started.remove(spec_idle)
                finally:
                    for spec in started:
                        embed_client.shutdown(spec)


if __name__ == "__main__":
    unittest.main()
