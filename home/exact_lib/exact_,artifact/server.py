from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from assets import ASSET_TYPES, asset_text, chrome_page, inject_client_script, render_asset
from feedback import clear_ended, ended_path, normalize_feedback_batch
from paths import APP, HOST, ensure_session, sanitize_asset_name, sanitize_name, session_dir

ENTRYPOINT = Path(__file__).resolve().with_name("main.py")


def server_state_path(sdir: Path) -> Path:
    return sdir / "server.json"


def read_server_state(sdir: Path) -> dict[str, Any] | None:
    try:
        return json.loads(server_state_path(sdir).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


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


def start_server(sdir: Path) -> str:
    existing = server_base_url(sdir)
    if existing:
        return existing
    log = sdir / "server.log"
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
        if child.poll() is not None:
            break
        time.sleep(0.1)
    raise SystemExit(f"ERROR: artifact server did not start; inspect {log}")


def live_info(name: str) -> dict[str, str]:
    ensure_session()
    safe_name = sanitize_name(name)
    clear_ended(safe_name)
    base_url = start_server(session_dir())
    return {
        "artifact": safe_name,
        "server_url": base_url,
        "script_url": f"{base_url}/live/{safe_name}.js",
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
    print(live_overlay_script(info["artifact"], info["server_url"]), end="")


def live_overlay_script(name: str, base_url: str) -> str:
    return render_asset(
        "live_overlay.js",
        {
            "__NAME_JSON__": json.dumps(name),
            "__BASE_URL_JSON__": json.dumps(base_url),
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
    adir.mkdir(parents=True, exist_ok=True)
    fdir.mkdir(parents=True, exist_ok=True)
    base_url = ""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *values: Any) -> None:
            return

        def send_cors_headers(self) -> None:
            self.send_header("access-control-allow-origin", "*")
            self.send_header("access-control-allow-methods", "GET, POST, OPTIONS")
            self.send_header("access-control-allow-headers", "content-type")
            self.send_header("access-control-max-age", "600")

        def send_json(self, value: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_cors_headers()
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_cors_headers()
            self.end_headers()

        def do_GET(self) -> None:
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
                name = sanitize_name(self.path.removeprefix("/live/").removesuffix(".js").split("?", 1)[0])
                body = live_overlay_script(name, base_url).encode()
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
                self.send_cors_headers()
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/session/"):
                name = sanitize_name(self.path.removeprefix("/session/").split("?", 1)[0])
                body = chrome_page(name).encode()
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_cors_headers()
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if self.path.startswith("/api/feedback/"):
                name = sanitize_name(self.path.removeprefix("/api/feedback/"))
                payload = read_request_body(self)
                batch = normalize_feedback_batch(payload)
                if not batch:
                    self.send_json({"error": "empty batch"}, 400)
                    return
                with (fdir / f"{name}.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(batch) + "\n")
                self.send_json({"status": "queued", "batch_id": batch["batch_id"], "count": len(batch["items"])})
                return
            if self.path.startswith("/api/end/"):
                name = sanitize_name(self.path.removeprefix("/api/end/"))
                (fdir / f"{name}.ended").write_text("", encoding="utf-8")
                self.send_json({"status": "ended"})
                return
            self.send_error(404)

    server = ThreadingHTTPServer((HOST, 0), Handler)
    port = int(server.server_address[1])
    base_url = f"http://{HOST}:{port}"
    server_state_path(sdir).write_text(json.dumps({"pid": os.getpid(), "port": port}) + "\n", encoding="utf-8")
    try:
        server.serve_forever()
    finally:
        try:
            server_state_path(sdir).unlink()
        except FileNotFoundError:
            pass
