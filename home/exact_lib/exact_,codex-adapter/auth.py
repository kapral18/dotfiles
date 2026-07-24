"""Codex ChatGPT OAuth credential loading and refresh."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Credentials:
    access_token: str
    account_id: str | None


def default_auth_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return (Path(codex_home).expanduser() if codex_home else Path.home() / ".codex") / "auth.json"


def load_credentials(path: Path) -> Credentials:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"Codex authentication state was not found at {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Codex authentication state at {path} is unreadable") from error
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        raise RuntimeError("Codex is not signed in with a ChatGPT subscription")
    access_token = tokens.get("access_token")
    account_id = tokens.get("account_id")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("Codex authentication state has no ChatGPT access token")
    if account_id is not None and not isinstance(account_id, str):
        raise RuntimeError("Codex authentication state has an invalid account ID")
    return Credentials(access_token, account_id or None)


def refresh_via_app_server(codex_binary: str, *, timeout: int = 30) -> None:
    try:
        process = subprocess.Popen(
            [codex_binary, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as error:
        raise RuntimeError("Codex CLI is required to refresh ChatGPT authentication") from error
    except OSError as error:
        raise RuntimeError("Codex authentication refresh could not start") from error
    if process.stdin is None or process.stdout is None:
        process.terminate()
        raise RuntimeError("Codex authentication refresh has no app-server pipes")

    messages: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def read_messages() -> None:
        try:
            for line in process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(message, dict):
                    messages.put(message)
        finally:
            messages.put(None)

    reader = threading.Thread(target=read_messages, name="codex-auth-refresh", daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout

    def send(message: dict[str, Any]) -> None:
        process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def receive(expected_id: int) -> dict[str, Any]:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Codex authentication refresh timed out")
            try:
                message = messages.get(timeout=remaining)
            except queue.Empty as error:
                raise RuntimeError("Codex authentication refresh timed out") from error
            if message is None:
                raise RuntimeError("Codex authentication refresh ended before account/read completed")
            if message.get("id") == expected_id:
                return message

    try:
        send(
            {
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": "codex-subscription-adapter",
                        "title": "Codex subscription adapter",
                        "version": "1.0.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            },
        )
        initialized = receive(1)
        if "error" in initialized:
            raise RuntimeError("Codex authentication refresh initialization was rejected")
        send({"method": "initialized", "params": {}})
        send({"id": 2, "method": "account/read", "params": {"refreshToken": True}})
        result = receive(2)
        if "error" in result:
            raise RuntimeError("Codex authentication refresh was rejected")
    finally:
        process.stdin.close()
        remaining = max(1.0, deadline - time.monotonic())
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
            returncode = process.returncode
        reader.join(timeout=1)
    if returncode != 0:
        raise RuntimeError("Codex authentication refresh failed")


class CodexAuth:
    """Read current Codex credentials and serialize refresh attempts."""

    def __init__(self, auth_path: Path | None = None, codex_binary: str = "codex") -> None:
        self.auth_path = auth_path or default_auth_path()
        self.codex_binary = codex_binary
        self._lock = threading.Lock()

    def get(self) -> Credentials:
        return load_credentials(self.auth_path)

    def refresh(self) -> Credentials:
        with self._lock:
            refresh_via_app_server(self.codex_binary)
            return load_credentials(self.auth_path)
