#!/usr/bin/env python3
"""Rank session-picker queries by relevance without crossing kind tiers.

Motivation: sorting and reloading on every keystroke visibly flickers, while an
fzf `change:transform:<sh>` binding adds a shell fork to the input path.
Debouncing off-screen ranking in this daemon keeps typing fzf-native and makes
each settled query produce at most one list reorder.

Contract:
- The empty picker preserves its grouped/frecency source order.
- A non-empty query uses fzf's own score order within each kind tier.
- Kind tiers remain strict: session, then worktree, then directory.

Approach:
- Wait for the socket path to appear.
- Poll the fzf state over its Unix socket without forking per keystroke.
- After the query settles, run fzf filter mode off-screen against the complete
  source rows and stable-partition its ranked matches by kind.
- Atomically write that order and `reload-sync` it once; interactive sorting
  remains disabled throughout.
- Restore the grouped source rows when the query is cleared.
- Exit quietly on repeated connection failures (fzf is gone).
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

SOCK_WAIT_TIMEOUT_S = 5.0
POLL_INTERVAL_S = 0.02
DEBOUNCE_S = 0.12
MAX_CONSECUTIVE_FAILURES = 25
HTTP_TIMEOUT_S = 0.5
KIND_TIER = {"session": 0, "worktree": 1, "dir": 2}


def row_identity(line: str) -> str:
    parts = line.split("\t")
    if len(parts) > 2 and parts[1] and parts[2]:
        return f"{parts[1]}\t{parts[2]}"
    return line


def rank_rows_by_kind(source_rows: list[str], fzf_matches: list[str]) -> list[str]:
    """Keep kind tiers strict while preserving fzf relevance within each tier."""
    match_rank: dict[str, int] = {}
    for rank, line in enumerate(fzf_matches):
        match_rank.setdefault(row_identity(line), rank)
    unmatched_base = len(fzf_matches)

    def key(item: tuple[int, str]) -> tuple[int, int, int]:
        source_rank, line = item
        parts = line.split("\t")
        kind = parts[1] if len(parts) > 1 else ""
        tier = KIND_TIER.get(kind, 3)
        relevance_rank = match_rank.get(row_identity(line), unmatched_base + source_rank)
        return tier, relevance_rank, source_rank

    return [line for _source_rank, line in sorted(enumerate(source_rows), key=key)]


def file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def read_rows(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def write_rows_atomic(path: Path, rows: list[str]) -> None:
    tmp = path.with_name(f"{path.name}.new.{os.getpid()}")
    tmp.write_text("".join(f"{line}\n" for line in rows), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def reload_action(path: Path) -> bytes:
    return f"reload-sync(cat {shlex.quote(str(path))})+first".encode()


def fzf_ranked_matches(fzf_path: str, source_rows: list[str], query: str) -> list[str]:
    env = os.environ.copy()
    env["FZF_DEFAULT_OPTS"] = ""
    result = subprocess.run(
        [
            fzf_path,
            f"--filter={query}",
            "--ansi",
            "--scheme=path",
            "--tiebreak=begin,length,index",
            "--delimiter=\t",
            "--nth=1",
        ],
        input="".join(f"{line}\n" for line in source_rows),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(f"fzf filter failed with exit code {result.returncode}")
    return result.stdout.splitlines()


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


def run(sock_path: str, source_path: Path, ranked_path: Path, fzf_path: str) -> int:
    if not wait_for_socket(sock_path, SOCK_WAIT_TIMEOUT_S):
        return 1

    failures = 0
    pending_query = ""
    pending_source_signature: tuple[int, int] | None = None
    pending_since = time.monotonic()
    ranked_query = ""
    ranked_source_signature: tuple[int, int] | None = None
    input_is_ranked = False

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
        source_signature = file_signature(source_path)
        if source_signature is None or bool(data.get("reading", False)):
            time.sleep(POLL_INTERVAL_S)
            continue

        now = time.monotonic()
        if query != pending_query or source_signature != pending_source_signature:
            pending_query = query
            pending_source_signature = source_signature
            pending_since = now

        if sort_on:
            try:
                http_post_action(sock_path, b"toggle-sort")
            except OSError:
                pass
            time.sleep(POLL_INTERVAL_S)
            continue

        if not query:
            ranked_query = ""
            ranked_source_signature = None
            if input_is_ranked:
                try:
                    code = http_post_action(sock_path, reload_action(source_path))
                    if code == 200:
                        input_is_ranked = False
                except OSError:
                    pass
            time.sleep(POLL_INTERVAL_S)
            continue

        same_ranked_input = input_is_ranked and query == ranked_query and source_signature == ranked_source_signature
        if same_ranked_input:
            time.sleep(POLL_INTERVAL_S)
            continue

        if now - pending_since < DEBOUNCE_S:
            time.sleep(POLL_INTERVAL_S)
            continue

        try:
            source_rows = read_rows(source_path)
            fzf_matches = fzf_ranked_matches(fzf_path, source_rows, query)
            status, body = http_get(sock_path, "/?limit=0")
            if status != 200:
                time.sleep(POLL_INTERVAL_S)
                continue
            current_state = json.loads(body.decode(errors="replace") or "{}")
            if (
                (current_state.get("query", "") or "") != query
                or bool(current_state.get("sort", False))
                or bool(current_state.get("reading", False))
                or file_signature(source_path) != source_signature
            ):
                time.sleep(POLL_INTERVAL_S)
                continue

            write_rows_atomic(ranked_path, rank_rows_by_kind(source_rows, fzf_matches))
            code = http_post_action(sock_path, reload_action(ranked_path))
            if code == 200:
                ranked_query = query
                ranked_source_signature = source_signature
                input_is_ranked = True
        except (OSError, RuntimeError, ValueError):
            pass

        time.sleep(POLL_INTERVAL_S)


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: sort_toggle_daemon.py <socket-path> <source-path> <ranked-path>", file=sys.stderr)
        return 2
    fzf_path = shutil.which("fzf")
    if not fzf_path:
        return 1
    try:
        return run(argv[1], Path(argv[2]), Path(argv[3]), fzf_path)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
