#!/usr/bin/env python3
"""Sync fzf sort state with pathy-query intent over a Unix socket --listen.

Motivation: emitting `toggle-sort` from an fzf `change:transform:<sh>` binding
forks a new shell on every keystroke (~10ms each on macOS bash), which makes
holding backspace visibly laggy. Shifting that work into a background daemon
that talks to fzf via its `--listen` Unix socket keeps every keystroke on the
fzf-native fast path (`change:first`) while still reacting correctly to every
pathy-mode transition.

Contract:
- fzf starts with `--no-sort` so sessions-first ordering is preserved.
- When the current query contains `/`, fzf sort must be ON so path scoring
  surfaces the narrowest matching path first.
- When it does not, fzf sort must be OFF.

Approach:
- Wait for the socket path to appear.
- Poll `GET /?limit=0` at a short interval. fzf returns JSON including both
  the live `query` and the current `sort` boolean.
- Compare the desired sort state (derived from query) to the actual sort state
  (from the response). If they disagree, `POST toggle-sort`.
- Exit quietly on repeated connection failures (fzf is gone).

Reading actual sort state (instead of tracking last-known intent locally) makes
the daemon self-healing: a dropped toggle or a manual `alt-s` flip is observed
on the next poll and corrected if it conflicts with the query. `alt-s` pressed
in plain mode (off -> on while no `/`) is still honored briefly but will be
reverted on the next poll; for manual override use `alt-s` while in path mode
instead.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time

SOCK_WAIT_TIMEOUT_S = 5.0
POLL_INTERVAL_S = 0.02
MAX_CONSECUTIVE_FAILURES = 25
HTTP_TIMEOUT_S = 0.5


def _recv_all(conn: socket.socket) -> bytes:
    buf = b""
    while True:
        try:
            chunk = conn.recv(4096)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
    return buf


def _split_http_response(raw: bytes) -> tuple[int, bytes]:
    if not raw:
        return 0, b""
    head_end = raw.find(b"\r\n\r\n")
    if head_end < 0:
        return 0, b""
    status_line, _, _ = raw.partition(b"\r\n")
    status_code = 0
    parts = status_line.split(b" ", 2)
    if len(parts) >= 2:
        try:
            status_code = int(parts[1])
        except ValueError:
            status_code = 0
    return status_code, raw[head_end + 4 :]


def _connect(sock_path: str) -> socket.socket:
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(HTTP_TIMEOUT_S)
    s.connect(sock_path)
    return s


def http_get(sock_path: str, path: str) -> tuple[int, bytes]:
    s = _connect(sock_path)
    try:
        # fzf accepts HTTP/1.0 request lines without a Host header and without
        # a Content-Length (GET). Its server closes the connection after the
        # response, so a single recv loop drains everything.
        s.sendall(f"GET {path} HTTP/1.0\r\n\r\n".encode())
        raw = _recv_all(s)
    finally:
        s.close()
    return _split_http_response(raw)


def http_post_action(sock_path: str, action: bytes) -> int:
    s = _connect(sock_path)
    try:
        req = b"POST / HTTP/1.1\r\nContent-Length: " + str(len(action)).encode() + b"\r\n\r\n" + action
        s.sendall(req)
        raw = _recv_all(s)
    finally:
        s.close()
    code, _ = _split_http_response(raw)
    return code


def wait_for_socket(sock_path: str, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if os.path.exists(sock_path):
            return True
        time.sleep(0.01)
    return False


def is_pathy(query: str) -> bool:
    return "/" in (query or "")


def run(sock_path: str) -> int:
    if not wait_for_socket(sock_path, SOCK_WAIT_TIMEOUT_S):
        return 1

    failures = 0
    while True:
        try:
            status, body = http_get(sock_path, "/?limit=0")
            if status != 200:
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    return 0
                time.sleep(POLL_INTERVAL_S)
                continue
            data = json.loads(body.decode(errors="replace") or "{}")
        except (OSError, ValueError):
            failures += 1
            if failures >= MAX_CONSECUTIVE_FAILURES:
                return 0
            time.sleep(POLL_INTERVAL_S)
            continue

        failures = 0
        query = data.get("query", "") or ""
        sort_on = bool(data.get("sort", False))
        want_sort = is_pathy(query)

        if want_sort != sort_on:
            try:
                code = http_post_action(sock_path, b"toggle-sort")
                if code != 200:
                    # Treat non-200 as a transient failure; next poll will retry.
                    pass
            except OSError:
                pass

        time.sleep(POLL_INTERVAL_S)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: sort_toggle_daemon.py <socket-path>", file=sys.stderr)
        return 2
    sock_path = argv[1]
    try:
        return run(sock_path)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
