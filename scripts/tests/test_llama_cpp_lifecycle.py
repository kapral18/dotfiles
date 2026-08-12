#!/usr/bin/env python3
"""Tests for shared llama.cpp router lifecycle ownership."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO

LIFECYCLE = REPO / "home/exact_lib/exact_,llama-cpp/lifecycle.py"


def _load_lifecycle_module():
    spec = importlib.util.spec_from_file_location("llama_cpp_lifecycle_under_test", LIFECYCLE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {LIFECYCLE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LIFECYCLE_MODULE = _load_lifecycle_module()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for(predicate, message: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError(message)


def _router_reachable(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/models", timeout=0.2) as response:
            return response.status == 200
    except OSError:
        return False


def _write_fake_server(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import http.server
import json
import os
import signal
import sys

host = "127.0.0.1"
port = 8080
for index, value in enumerate(sys.argv):
    if value == "--host":
        host = sys.argv[index + 1]
    elif value == "--port":
        port = int(sys.argv[index + 1])

log = os.environ["FAKE_LLAMA_SERVER_LOG"]
with open(log, "a", encoding="utf-8") as handle:
    handle.write(f"start {os.getpid()}\\n")

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/models":
            self.send_error(404)
            return
        body = json.dumps({"data": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass

def stop(_signum, _frame):
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(f"term {os.getpid()}\\n")
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop)
http.server.ThreadingHTTPServer((host, port), Handler).serve_forever()
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    process.wait(timeout=10)


class TestLlamaCppLifecycle(unittest.TestCase):
    """WHEN harnesses share the local llama.cpp router."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.server = self.root / "llama-server"
        self.server_log = self.root / "server.log"
        self.state = self.root / "state"
        self.preset = self.root / "models.ini"
        self.preset.write_text("[*]\n", encoding="utf-8")
        _write_fake_server(self.server)

    def env(self, port: int) -> dict[str, str]:
        return {
            **os.environ,
            "FAKE_LLAMA_SERVER_LOG": str(self.server_log),
            "LLAMA_CPP_HOST": "127.0.0.1",
            "LLAMA_CPP_PORT": str(port),
            "LLAMA_CPP_MODELS_PRESET": str(self.preset),
            "LLAMA_CPP_SERVER_BIN": str(self.server),
            "LLAMA_CPP_LIFECYCLE_DIR": str(self.state),
            "LLAMA_CPP_GRACE_SECONDS": "0",
        }

    def lifecycle_command(self, port: int, *command: str) -> list[str]:
        return [sys.executable, str(LIFECYCLE), "run", "--", *command]

    def stop_command(self, *args: str) -> list[str]:
        return [sys.executable, str(LIFECYCLE), "stop", *args]

    def test_SHOULD_default_to_a_ten_minute_grace_period(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LLAMA_CPP_GRACE_SECONDS", None)
            config = LIFECYCLE_MODULE.Config.from_environment()

        self.assertEqual(600, config.grace_seconds)

    def test_SHOULD_stop_an_owned_router_after_its_only_consumer_exits(self) -> None:
        port = _free_port()
        result = subprocess.run(
            self.lifecycle_command(port, sys.executable, "-c", "print('consumer-ok')"),
            env=self.env(port),
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("consumer-ok\n", result.stdout)
        self.assertEqual(2, len(self.server_log.read_text().splitlines()))
        self.assertFalse(_router_reachable(port))

    def test_SHOULD_preserve_the_consumer_exit_status_after_cleanup(self) -> None:
        port = _free_port()
        result = subprocess.run(
            self.lifecycle_command(port, sys.executable, "-c", "raise SystemExit(23)"),
            env=self.env(port),
            capture_output=True,
            text=True,
        )

        self.assertEqual(23, result.returncode, result.stderr)
        self.assertEqual(2, len(self.server_log.read_text().splitlines()))
        self.assertFalse(_router_reachable(port))

    def test_SHOULD_keep_an_owned_router_until_its_grace_period_expires(self) -> None:
        port = _free_port()
        environment = self.env(port)
        environment["LLAMA_CPP_GRACE_SECONDS"] = "1"
        result = subprocess.run(
            self.lifecycle_command(port, sys.executable, "-c", "pass"),
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        shutdown_path = next(self.state.rglob("shutdown.json"))
        marker = json.loads(shutdown_path.read_text())
        self.assertGreater(marker["deadline_epoch"], time.time())
        self.assertTrue(_router_reachable(port))
        _wait_for(lambda: not _router_reachable(port), "grace expiry did not stop owned router")
        _wait_for(lambda: not shutdown_path.exists(), "grace shutdown marker was not cleared")
        self.assertFalse(shutdown_path.exists())
        self.assertFalse(shutdown_path.with_name("owner.json").exists())
        self.assertEqual(2, len(self.server_log.read_text().splitlines()))

    def test_SHOULD_cancel_grace_and_reuse_the_owned_router(self) -> None:
        port = _free_port()
        environment = self.env(port)
        environment["LLAMA_CPP_GRACE_SECONDS"] = "1"
        first = subprocess.run(
            self.lifecycle_command(port, sys.executable, "-c", "pass"),
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, first.returncode, first.stderr)
        shutdown_path = next(self.state.rglob("shutdown.json"))
        first_deadline = float(json.loads(shutdown_path.read_text())["deadline_epoch"])

        gate = self.root / "grace-consumer.done"
        waiter = "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]);\nwhile not p.exists(): time.sleep(0.02)"
        consumer = subprocess.Popen(
            self.lifecycle_command(port, sys.executable, "-c", waiter, str(gate)),
            env=environment,
        )
        self.addCleanup(_stop_process, consumer)
        _wait_for(lambda: len(list(self.state.rglob("lease-*.lock"))) == 1, "grace consumer lease missing")
        self.assertFalse(shutdown_path.exists())
        _wait_for(lambda: time.time() > first_deadline + 0.2, "prior grace deadline did not pass")
        self.assertTrue(_router_reachable(port))
        self.assertEqual(1, len(self.server_log.read_text().splitlines()))

        gate.touch()
        self.assertEqual(0, consumer.wait(timeout=10))
        _wait_for(lambda: not _router_reachable(port), "renewed grace did not stop owned router")
        self.assertEqual(2, len(self.server_log.read_text().splitlines()))

    def test_SHOULD_stop_an_owned_router_during_grace_from_the_cli(self) -> None:
        port = _free_port()
        environment = self.env(port)
        environment["LLAMA_CPP_GRACE_SECONDS"] = "60"
        consumer = subprocess.run(
            self.lifecycle_command(port, sys.executable, "-c", "pass"),
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, consumer.returncode, consumer.stderr)
        shutdown_path = next(self.state.rglob("shutdown.json"))
        self.assertTrue(_router_reachable(port))

        stopped = subprocess.run(self.stop_command(), env=environment, capture_output=True, text=True)

        self.assertEqual(0, stopped.returncode, stopped.stderr)
        self.assertEqual("Stopped lifecycle-owned llama.cpp router.\n", stopped.stdout)
        self.assertFalse(_router_reachable(port))
        self.assertFalse(shutdown_path.exists())
        self.assertFalse(shutdown_path.with_name("owner.json").exists())

    def test_SHOULD_require_force_to_stop_with_an_active_consumer(self) -> None:
        port = _free_port()
        gate = self.root / "active-consumer.done"
        waiter = "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]);\nwhile not p.exists(): time.sleep(0.02)"
        consumer = subprocess.Popen(
            self.lifecycle_command(port, sys.executable, "-c", waiter, str(gate)),
            env=self.env(port),
        )
        self.addCleanup(_stop_process, consumer)
        _wait_for(lambda: _router_reachable(port), "owned router did not start")

        refused = subprocess.run(self.stop_command(), env=self.env(port), capture_output=True, text=True)
        self.assertEqual(1, refused.returncode)
        self.assertIn("active llama.cpp consumer(s)", refused.stderr)
        self.assertTrue(_router_reachable(port))

        forced = subprocess.run(self.stop_command("--force"), env=self.env(port), capture_output=True, text=True)
        self.assertEqual(0, forced.returncode, forced.stderr)
        self.assertEqual("Stopped lifecycle-owned llama.cpp router.\n", forced.stdout)
        self.assertFalse(_router_reachable(port))
        gate.touch()
        self.assertEqual(0, consumer.wait(timeout=10))

    def test_SHOULD_reject_a_negative_grace_period(self) -> None:
        port = _free_port()
        environment = self.env(port)
        environment["LLAMA_CPP_GRACE_SECONDS"] = "-1"
        result = subprocess.run(
            self.lifecycle_command(port, sys.executable, "-c", "pass"),
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("LLAMA_CPP_GRACE_SECONDS must be a non-negative integer", result.stderr)
        self.assertFalse(self.server_log.exists())

    def test_SHOULD_not_start_a_missing_non_loopback_router(self) -> None:
        port = _free_port()
        environment = self.env(port)
        environment["LLAMA_CPP_HOST"] = "192.0.2.1"
        result = subprocess.run(
            self.lifecycle_command(port, sys.executable, "-c", "pass"),
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("automatic startup is limited to loopback hosts", result.stderr)
        self.assertFalse(self.server_log.exists())

    def test_SHOULD_leave_a_manually_started_router_running(self) -> None:
        port = _free_port()
        external = subprocess.Popen(
            [str(self.server), "--host", "127.0.0.1", "--port", str(port)],
            env=self.env(port),
        )
        self.addCleanup(_stop_process, external)
        _wait_for(lambda: _router_reachable(port), "external router did not start")

        result = subprocess.run(
            self.lifecycle_command(port, sys.executable, "-c", "pass"),
            env=self.env(port),
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIsNone(external.poll())
        self.assertEqual(1, len(self.server_log.read_text().splitlines()))

        stopped = subprocess.run(self.stop_command(), env=self.env(port), capture_output=True, text=True)
        self.assertEqual(0, stopped.returncode, stopped.stderr)
        self.assertEqual("No lifecycle-owned llama.cpp router is running.\n", stopped.stdout)
        self.assertIsNone(external.poll())

    def test_SHOULD_stop_only_after_the_last_overlapping_consumer_exits(self) -> None:
        port = _free_port()
        first_gate = self.root / "first.done"
        second_gate = self.root / "second.done"
        waiter = "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]);\nwhile not p.exists(): time.sleep(0.02)"
        first = subprocess.Popen(
            self.lifecycle_command(port, sys.executable, "-c", waiter, str(first_gate)),
            env=self.env(port),
        )
        second = None
        self.addCleanup(_stop_process, first)
        _wait_for(lambda: _router_reachable(port), "owned router did not start")
        second = subprocess.Popen(
            self.lifecycle_command(port, sys.executable, "-c", waiter, str(second_gate)),
            env=self.env(port),
        )
        self.addCleanup(_stop_process, second)
        _wait_for(lambda: len(list(self.state.rglob("lease-*.lock"))) == 2, "two leases were not published")

        first_gate.touch()
        self.assertEqual(0, first.wait(timeout=10))
        self.assertTrue(_router_reachable(port))

        second_gate.touch()
        self.assertEqual(0, second.wait(timeout=10))
        _wait_for(lambda: not _router_reachable(port), "last consumer did not stop owned router")
        self.assertEqual(2, len(self.server_log.read_text().splitlines()))

    def test_SHOULD_refuse_to_signal_an_owned_pid_with_a_different_start_identity(self) -> None:
        port = _free_port()
        gate = self.root / "consumer.done"
        waiter = "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]);\nwhile not p.exists(): time.sleep(0.02)"
        consumer = subprocess.Popen(
            self.lifecycle_command(port, sys.executable, "-c", waiter, str(gate)),
            env=self.env(port),
        )
        self.addCleanup(_stop_process, consumer)
        _wait_for(lambda: _router_reachable(port), "owned router did not start")
        owner_path = next(self.state.rglob("owner.json"))
        owner = json.loads(owner_path.read_text())
        owner["start_identity"] = "different-process-start"
        owner_path.write_text(json.dumps(owner), encoding="utf-8")

        gate.touch()
        self.assertEqual(0, consumer.wait(timeout=10))
        self.assertTrue(_router_reachable(port))
        os.kill(int(owner["pid"]), 15)
        _wait_for(lambda: not _router_reachable(port), "fixture router did not stop")


if __name__ == "__main__":
    unittest.main()
