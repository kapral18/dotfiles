from __future__ import annotations

import json
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer
from typing import Any
from urllib.parse import parse_qs

from assets import ASSET_TYPES, asset_text, chrome_page, inject_client_script, render_asset
from feedback import (
    append_feedback,
    clear_ended,
    command_line_for_pid,
    normalize_feedback_batch,
    process_is_running,
    process_started_at,
)
from paths import APP, HOST, ensure_session, lifecycle_lock, sanitize_asset_name, sanitize_name, session_dir

ENTRYPOINT = Path(__file__).resolve().with_name("main.py")


class ArtifactHTTPServer(ThreadingHTTPServer):
    def server_bind(self) -> None:
        TCPServer.server_bind(self)
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]


def server_state_path(sdir: Path) -> Path:
    return sdir / "server.json"


def read_server_state(sdir: Path) -> dict[str, Any] | None:
    try:
        return json.loads(server_state_path(sdir).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def record_matches_live_server(sdir: Path, state: dict[str, Any]) -> bool:
    pid = state.get("pid")
    started = state.get("process_started_at")
    if type(pid) is not int or pid <= 0 or not isinstance(started, str) or not started:
        return False
    if process_started_at(pid) != started:
        return False
    command = command_line_for_pid(pid) or ""
    marker = f"{ENTRYPOINT} server --session-dir "
    prefix, separator, recorded_directory = command.rpartition(marker)
    if not separator or (prefix and not prefix.endswith(" ")):
        return False
    try:
        return Path(recorded_directory).resolve() == sdir.resolve()
    except (OSError, RuntimeError):
        return False


def stop_server(sdir: Path) -> None:
    with lifecycle_lock():
        state = read_server_state(sdir) or {}
        pid = state.get("pid")
        if not process_is_running(pid):
            return
        if not record_matches_live_server(sdir, state):
            raise SystemExit(f"ERROR: cannot verify active server PID {pid}; metadata preserved")
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def urlopen_json(url: str, timeout: float = 1.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None


def server_base_url(sdir: Path) -> str | None:
    state = read_server_state(sdir)
    if not state:
        return None
    port = state.get("port")
    if not isinstance(port, int):
        return None
    url = f"http://{HOST}:{port}"
    health = urlopen_json(f"{url}/health")
    if health and health.get("app") == APP and health.get("session_dir") == str(sdir):
        return url
    return None


def server_token(sdir: Path) -> str:
    state = read_server_state(sdir) or {}
    token = state.get("token")
    return token if isinstance(token, str) else ""


def start_server(sdir: Path) -> str:
    log = sdir / "server.log"
    child = None
    with lifecycle_lock():
        existing = server_base_url(sdir)
        if existing:
            return existing
        state = read_server_state(sdir) or {}
        if process_is_running(state.get("pid")):
            if not record_matches_live_server(sdir, state):
                raise SystemExit(f"ERROR: cannot verify active server PID {state['pid']}; metadata preserved")
        else:
            sdir.mkdir(parents=True, exist_ok=True)
            with log.open("ab") as log_fh:
                child = subprocess.Popen(
                    [sys.executable, str(ENTRYPOINT), "server", "--session-dir", str(sdir)],
                    stdin=subprocess.DEVNULL,
                    stdout=log_fh,
                    stderr=log_fh,
                    start_new_session=True,
                )
    deadline = time.time() + 5
    while time.time() < deadline:
        url = server_base_url(sdir)
        if url:
            return url
        if child is not None and child.poll() is not None:
            with lifecycle_lock():
                state = read_server_state(sdir) or {}
                if not process_is_running(state.get("pid")) or not record_matches_live_server(sdir, state):
                    break
        time.sleep(0.1)
    raise SystemExit(f"ERROR: artifact server did not start; inspect {log}")


def live_info(name: str) -> dict[str, str]:
    ensure_session()
    safe_name = sanitize_name(name)
    clear_ended(safe_name)
    base_url = start_server(session_dir())
    token = server_token(session_dir())
    return {
        "artifact": safe_name,
        "server_url": base_url,
        "token": token,
        "script_url": f"{base_url}/live/{safe_name}.js?token={token}",
        "feedback_url": f"{base_url}/api/feedback/{safe_name}",
        "end_url": f"{base_url}/api/end/{safe_name}",
    }


def live_start_command(args: argparse.Namespace) -> None:
    info = live_info(args.name)
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        print(info["script_url"])


def live_script_command(args: argparse.Namespace) -> None:
    info = live_info(args.name)
    print(live_overlay_script(info["artifact"], info["server_url"], info["token"]), end="")


def live_overlay_script(name: str, base_url: str, token: str) -> str:
    return render_asset(
        "live_overlay.js",
        {
            "__NAME_JSON__": json.dumps(name),
            "__BASE_URL_JSON__": json.dumps(base_url),
            "__TOKEN_JSON__": json.dumps(token),
            "__LIVE_OVERLAY_CSS_JSON__": json.dumps(asset_text("live_overlay.css")),
            "__LIVE_OVERLAY_HTML_JSON__": json.dumps(asset_text("live_overlay.html")),
        },
    )


def read_request_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("content-length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def run_server(args: argparse.Namespace) -> None:
    sdir = Path(args.session_dir).resolve()
    adir = sdir / "artifacts"
    fdir = sdir / "feedback"
    base_url = ""
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *values: Any) -> None:
            return

        def send_cors_headers(self) -> None:
            self.send_header("access-control-allow-origin", "*")
            self.send_header("access-control-allow-methods", "GET, POST, OPTIONS")
            self.send_header("access-control-allow-headers", "content-type, x-artifact-token")
            self.send_header("access-control-max-age", "600")

        def send_json(self, value: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_cors_headers()
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def foreign_host(self) -> bool:
            # A DNS-rebound page reaches this loopback port under its own host name.
            if self.headers.get("host") == base_url.removeprefix("http://"):
                return False
            self.send_error(403)
            return True

        def do_OPTIONS(self) -> None:
            if self.foreign_host():
                return
            self.send_response(204)
            self.send_cors_headers()
            self.end_headers()

        def do_GET(self) -> None:
            if self.foreign_host():
                return
            if self.path == "/health":
                self.send_json({"app": APP, "pid": os.getpid(), "session_dir": str(sdir)})
                return
            if self.path.startswith("/assets/"):
                name = sanitize_asset_name(self.path.removeprefix("/assets/").split("?", 1)[0])
                content_type = ASSET_TYPES.get(name)
                if not content_type:
                    self.send_error(404)
                    return
                body = asset_text(name).encode()
                self.send_response(200)
                self.send_header("content-type", content_type)
                self.send_cors_headers()
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/live/"):
                route, _, query = self.path.partition("?")
                if parse_qs(query).get("token") != [token]:
                    self.send_error(403)
                    return
                name = sanitize_name(route.removeprefix("/live/").removesuffix(".js"))
                body = live_overlay_script(name, base_url, token).encode()
                self.send_response(200)
                self.send_header("content-type", "application/javascript; charset=utf-8")
                self.send_cors_headers()
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/artifact/"):
                name = sanitize_name(self.path.removeprefix("/artifact/").split("?", 1)[0])
                path = adir / name
                if not path.exists():
                    self.send_error(404)
                    return
                content = path.read_text(encoding="utf-8", errors="replace")
                body = inject_client_script(content).encode()
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/session/"):
                name = sanitize_name(self.path.removeprefix("/session/").split("?", 1)[0])
                body = chrome_page(name, token).encode()
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if self.foreign_host():
                return
            if not secrets.compare_digest(self.headers.get("x-artifact-token", ""), token):
                self.send_json({"error": "forbidden"}, 403)
                return
            if self.path.startswith("/api/feedback/"):
                name = sanitize_name(self.path.removeprefix("/api/feedback/"))
                payload = read_request_body(self)
                batch = normalize_feedback_batch(payload)
                if not batch:
                    self.send_json({"error": "empty batch"}, 400)
                    return
                append_feedback(fdir, name, batch)
                self.send_json({"status": "queued", "batch_id": batch["batch_id"], "count": len(batch["items"])})
                return
            if self.path.startswith("/api/end/"):
                name = sanitize_name(self.path.removeprefix("/api/end/"))
                (fdir / f"{name}.ended").write_text("", encoding="utf-8")
                self.send_json({"status": "ended"})
                return
            self.send_error(404)

    with lifecycle_lock():
        existing = read_server_state(sdir) or {}
        if process_is_running(existing.get("pid")):
            if not record_matches_live_server(sdir, existing):
                raise SystemExit(f"ERROR: cannot verify active server PID {existing['pid']}; metadata preserved")
            return
        adir.mkdir(parents=True, exist_ok=True)
        fdir.mkdir(parents=True, exist_ok=True)
        server = ArtifactHTTPServer((HOST, 0), Handler)
        port = int(server.server_address[1])
        base_url = f"http://{HOST}:{port}"
        state = {
            "pid": os.getpid(),
            "port": port,
            "token": token,
            "process_started_at": process_started_at(os.getpid()),
        }
        server_state_path(sdir).write_text(json.dumps(state) + "\n", encoding="utf-8")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        with lifecycle_lock():
            if read_server_state(sdir) == state:
                server_state_path(sdir).unlink(missing_ok=True)
