#!/usr/bin/env python3
"""Shared fixtures for deployed bin command tests."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import http.server
import importlib.util
import io
import json
import os
import queue
import re
import shlex
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock
from urllib.request import Request, urlopen

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
import ai_models
from _test_support import (
    ARTIFACT_COMMAND,
    CODEX_COMMAND,
    COPILOT_COMMAND,
    KBN_STACK_COMMAND,
    MCP_TOKEN_COMMAND,
    REPO,
    modern_bash,
)

# Every OpenRouter wrapper defaults to this route; model and effort remain selectable.
OPENROUTER_PIN = "deepseek/deepseek-v4-flash-0731"
OPENROUTER_WIRE_PIN = f"{OPENROUTER_PIN}@preset/effort-max"


def _load_artifact_command():
    loader = SourceFileLoader("artifact_command", str(ARTIFACT_COMMAND))
    spec = importlib.util.spec_from_loader("artifact_command", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load ,artifact command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_unwrap_md_command():
    source = REPO / "home/exact_bin/executable_,unwrap-md"
    loader = SourceFileLoader("unwrap_md_command", str(source))
    spec = importlib.util.spec_from_loader("unwrap_md_command", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load unwrap-md command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_openrouter_presets_module():
    source = REPO / "home/exact_lib/exact_shared/executable_openrouter_presets.py"
    loader = SourceFileLoader("openrouter_presets", str(source))
    spec = importlib.util.spec_from_loader("openrouter_presets", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load OpenRouter preset helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_mcp_token_module():
    loader = SourceFileLoader("mcp_token_main", str(MCP_TOKEN_COMMAND))
    spec = importlib.util.spec_from_loader("mcp_token_main", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load ,mcp-token command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _es_dash_e_settings(cmd: list[str]) -> list[str]:
    settings: list[str] = []
    index = 0
    while index < len(cmd):
        if cmd[index] == "-E" and index + 1 < len(cmd):
            settings.append(cmd[index + 1])
            index += 2
            continue
        index += 1
    return settings


def _load_kbn_stack_command():
    loader = SourceFileLoader("kbn_stack_command", str(KBN_STACK_COMMAND))
    spec = importlib.util.spec_from_loader("kbn_stack_command", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load ,kbn-stack command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def _patched_ports(kbn_stack, alive_slots: dict[int, tuple[bool, bool]]):
    """Make ,kbn-stack port liveness deterministic for slot-reclamation tests.

    ``alive_slots`` maps slot -> (kbn_alive, es_alive). port_listener_pids reports
    a synthetic pid for ports whose half is alive; kill_port_listeners records the
    port and clears it; save_registry is captured instead of writing to disk.
    """
    alive_ports: set[int] = set()
    for slot, (kbn_alive, es_alive) in alive_slots.items():
        cfg = kbn_stack.derive(slot)
        if kbn_alive:
            alive_ports.add(cfg["kbn_port"])
        if es_alive:
            alive_ports.add(cfg["es_http"])

    state: dict = {"killed": [], "saved": []}
    original_listeners = kbn_stack.port_listener_pids
    original_kill = kbn_stack.kill_port_listeners
    original_save = kbn_stack.save_registry

    def fake_listeners(port):
        return [10000 + port] if port in alive_ports else []

    def fake_kill(port):
        if port is None or port not in alive_ports:
            return False
        alive_ports.discard(port)
        state["killed"].append(port)
        return True

    kbn_stack.port_listener_pids = fake_listeners
    kbn_stack.kill_port_listeners = fake_kill
    kbn_stack.save_registry = lambda reg: state["saved"].append({k: dict(v) for k, v in reg.items()})
    try:
        yield state
    finally:
        kbn_stack.port_listener_pids = original_listeners
        kbn_stack.kill_port_listeners = original_kill
        kbn_stack.save_registry = original_save


_HANG_AFTER_UNBIND_SERVER = """\
import os
import signal
import socket
import sys
import time

port = int(sys.argv[1])
role = sys.argv[2]
if role == "worker":
    signal.signal(signal.SIGTERM, lambda *_: None)
    while True:
        time.sleep(60)

sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("127.0.0.1", port))
sock.listen(1)


def hang(_signum, _frame):
    try:
        sock.close()
    except OSError:
        pass
    while True:
        time.sleep(60)


signal.signal(signal.SIGTERM, hang)
print(f"ready {os.getpid()}", flush=True)
while True:
    time.sleep(60)
"""


def _spawn_hang_after_unbind_group(script: Path) -> tuple[int, int, list[int]]:
    """Start a session: leader + listener that hangs after closing the port + worker.

    Returns ``(port, pgid, member_pids)``.
    """
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    leader = os.fork()
    if leader == 0:
        os.setsid()
        if os.fork() == 0:
            os.execv(sys.executable, [sys.executable, str(script), str(port), "listener"])
        if os.fork() == 0:
            os.execv(sys.executable, [sys.executable, str(script), str(port), "worker"])
        while True:
            try:
                os.wait()
            except ChildProcessError:
                time.sleep(60)
    deadline = time.monotonic() + 5
    listeners: list[int] = []
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
        )
        listeners = [int(tok) for tok in result.stdout.split() if tok.isdigit()]
        if listeners:
            break
        time.sleep(0.05)
    if not listeners:
        try:
            os.killpg(os.getpgid(leader), signal.SIGKILL)
        except OSError:
            pass
        raise AssertionError("hang-after-unbind harness failed to bind")
    pgid = os.getpgid(listeners[0])
    ps = subprocess.run(["ps", "-axo", "pid=,pgid="], capture_output=True, text=True, check=False)
    members = []
    for line in ps.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == str(pgid):
            members.append(int(parts[0]))
    return port, pgid, members


def _reap_group(pgid: int, leader: int | None = None) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass
    if leader is not None:
        try:
            os.waitpid(leader, 0)
        except ChildProcessError:
            pass


def _capture_stop_existing_serverless(kbn_stack, registry: dict, new_started_by: str):
    stopped: list[tuple[str, bool]] = []
    saved: list[dict] = []
    original_stop_entry = kbn_stack.stop_entry
    original_save_registry = kbn_stack.save_registry

    def fake_stop_entry(worktree, entry, *, allow_user_owned=True):
        stopped.append((worktree, allow_user_owned))
        return True

    kbn_stack.stop_entry = fake_stop_entry
    kbn_stack.save_registry = lambda updated: saved.append(json.loads(json.dumps(updated)))
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                kbn_stack.stop_existing_serverless(registry, "/current", new_started_by)
            except SystemExit:
                blocked = True
            else:
                blocked = False
    finally:
        kbn_stack.stop_entry = original_stop_entry
        kbn_stack.save_registry = original_save_registry

    return blocked, stopped, saved


class _LivenessHandler(http.server.BaseHTTPRequestHandler):
    """Classifies an MCP ``initialize`` POST by its bearer token.

    ``status_by_token`` maps an access token to the HTTP status the fake Slack
    MCP endpoint should return (200 live, 401/403 revoked, 500 server error).
    Unknown tokens are treated as revoked (401). Every hit is counted so tests
    can assert the plain-read / JWT paths never touch the network.
    """

    status_by_token: dict[str, int] = {}
    hits: list[str] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        self.rfile.read(length)
        auth = self.headers.get("Authorization", "")
        token = auth[len("Bearer ") :] if auth.startswith("Bearer ") else ""
        type(self).hits.append(token)
        code = type(self).status_by_token.get(token, 401)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        # A response body the command must never echo to stdout/stderr.
        self.wfile.write(b'{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"slack"}}}')

    def log_message(self, *args):  # silence access logging
        return


@contextlib.contextmanager
def _liveness_server(status_by_token: dict[str, int]):
    """Run the classifying MCP endpoint on localhost; yield (url, handler)."""

    class Handler(_LivenessHandler):
        pass

    Handler.status_by_token = dict(status_by_token)
    Handler.hits = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/mcp", Handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class _SinkHandler(http.server.BaseHTTPRequestHandler):
    """Records every request that reaches a redirect target (a second origin).

    The liveness probe must never follow a 3xx and resend the bearer here; each
    hit captures the method and Authorization header so a test can prove none of
    the token ever crossed to this origin.
    """

    hits: list[dict[str, str]] = []

    def _record(self, method: str) -> None:
        type(self).hits.append({"method": method, "authorization": self.headers.get("Authorization", "")})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"sink"}}}')

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        self.rfile.read(length)
        self._record("POST")

    def do_GET(self):  # noqa: N802
        self._record("GET")

    def log_message(self, *args):  # silence access logging
        return


@contextlib.contextmanager
def _redirecting_endpoint(status: int = 302):
    """Yield (probe_url, sink_handler); probe_url answers with a 3xx to the sink.

    ``probe_url`` is the URL the command reads from ``~/.cursor/mcp.json``. It
    responds to the probe with an HTTP *status* redirect whose ``Location`` is a
    different origin (the sink). A safe probe treats the 3xx as UNKNOWN and never
    contacts the sink; the sink's recorded hits expose a bearer-forwarding leak.
    """

    class Sink(_SinkHandler):
        pass

    Sink.hits = []
    sink = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Sink)
    sink_url = f"http://127.0.0.1:{sink.server_address[1]}/sink"

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0") or "0")
            self.rfile.read(length)
            self.send_response(status)
            self.send_header("Location", sink_url)
            self.end_headers()

        def log_message(self, *args):
            return

    redirect = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    probe_url = f"http://127.0.0.1:{redirect.server_address[1]}/mcp"
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (sink, redirect)]
    for t in threads:
        t.start()
    try:
        yield probe_url, Sink
    finally:
        for s in (sink, redirect):
            s.shutdown()
            s.server_close()
        for t in threads:
            t.join()


def _install_openrouter_preset_stub(home: Path) -> None:
    preset_helper = home / "lib" / "shared" / "openrouter_presets.py"
    preset_helper.parent.mkdir(parents=True, exist_ok=True)
    preset_helper.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    preset_helper.chmod(0o755)


def _install_shim_stub(home: Path) -> None:
    """Drop a stub shim.py into a fake HOME so the launcher's shim branch works.

    The launcher exits 1 when the shim file is missing, because the shim is the
    session guardrail now. The stub announces a port on fd 3 (the launcher's
    ready pipe) and then loops, so the launcher's poll loop advances past the
    ready check without a real HTTP server.
    """
    _install_openrouter_preset_stub(home)
    shim_dir = home / "lib" / ",cursor-agent-shim"
    shim_dir.mkdir(parents=True, exist_ok=True)
    (shim_dir / "shim.py").write_text(
        '#!/usr/bin/env python3\nimport os, time\nos.write(3, b"PORT=9876\\n")\ntime.sleep(60)\n',
        encoding="utf-8",
    )


class _BridgeMcpHandler(http.server.BaseHTTPRequestHandler):
    """Fake streamable-HTTP MCP endpoint for bridge tests.

    Accepts only tokens in ``live_tokens``; answers ``initialize`` with a JSON
    body plus ``Mcp-Session-Id``; answers requests via JSON or SSE (methods in
    ``sse_methods``); records every POST/DELETE with token and session id.
    """

    live_tokens: set[str] = set()
    sse_methods: set[str] = set()
    connect_timeouts_remaining: dict[str, int] = {}
    hits: list[tuple] = []
    lock = threading.Lock()

    def log_message(self, *args):
        pass

    def do_DELETE(self):
        with self.lock:
            self.hits.append(("DELETE", None, self.headers.get("Mcp-Session-Id")))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _reply(self, status: int, data: bytes = b"", content_type: str | None = None, session: str | None = None):
        self.send_response(status)
        if session:
            self.send_header("Mcp-Session-Id", session)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        token = self.headers.get("Authorization", "").rpartition(" ")[2]
        method = body.get("method")
        with self.lock:
            self.hits.append(("POST", method, token, self.headers.get("Mcp-Session-Id")))
            connect_timeouts_remaining = self.connect_timeouts_remaining.get(method, 0)
            if connect_timeouts_remaining:
                self.connect_timeouts_remaining[method] = connect_timeouts_remaining - 1
        if connect_timeouts_remaining:
            self._reply(
                503,
                b"upstream connect error or disconnect/reset before headers. reset reason: connection timeout",
                "text/plain",
            )
            return
        if token not in self.live_tokens:
            self._reply(401)
            return
        if method == "initialize":
            payload = {"jsonrpc": "2.0", "id": body.get("id"), "result": {"serverInfo": {"name": "fake"}}}
            self._reply(200, json.dumps(payload).encode(), "application/json", session="bridge-session")
            return
        if "id" not in body:
            self._reply(202)
            return
        if method in self.sse_methods:
            progress = {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"step": 1}}
            result = {"jsonrpc": "2.0", "id": body["id"], "result": {"via": "sse"}}
            data = (
                b"event: message\ndata: " + json.dumps(progress).encode() + b"\n\n"
                b"data: " + json.dumps(result).encode() + b"\n\n"
            )
            self._reply(200, data, "text/event-stream")
            return
        payload = {"jsonrpc": "2.0", "id": body["id"], "result": {"echo": method}}
        self._reply(200, json.dumps(payload).encode(), "application/json")


@contextlib.contextmanager
def _bridge_mcp_server(
    live_tokens: set[str],
    sse_methods: set[str] | None = None,
    connect_timeouts: dict[str, int] | None = None,
):
    _BridgeMcpHandler.live_tokens = set(live_tokens)
    _BridgeMcpHandler.sse_methods = set(sse_methods or ())
    _BridgeMcpHandler.connect_timeouts_remaining = dict(connect_timeouts or {})
    _BridgeMcpHandler.hits = []
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _BridgeMcpHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/mcp", _BridgeMcpHandler
    finally:
        httpd.shutdown()
        httpd.server_close()


class _BridgeSession:
    """Drive a ,mcp-token --bridge subprocess over stdio, one message at a time."""

    def __init__(
        self,
        home: Path,
        bindir: Path,
        server: str,
        url: str,
        *extra_args: str,
        cwd: Path | None = None,
    ):
        self.process = subprocess.Popen(
            [sys.executable, str(MCP_TOKEN_COMMAND), server, "--bridge", "--url", url, *extra_args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        self._lines: queue.Queue[bytes] = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line)

    def send(self, message: dict) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message).encode() + b"\n")
        self.process.stdin.flush()

    def recv(self, timeout: float = 10.0) -> dict:
        return json.loads(self._lines.get(timeout=timeout))

    def close(self, timeout: float = 10.0) -> int:
        assert self.process.stdin is not None
        self.process.stdin.close()
        returncode = self.process.wait(timeout=timeout)
        if self.process.stdout is not None:
            self.process.stdout.close()
        return returncode
