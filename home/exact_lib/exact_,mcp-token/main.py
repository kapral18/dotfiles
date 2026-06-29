#!/usr/bin/env python3
"""
,mcp-token <server>

Print a currently-valid MCP access token for an OAuth HTTP server, for use as a
bearer header by clients that cannot run the server's browser OAuth flow
themselves (notably GitHub Copilot CLI, whose hardcoded redirect URI the SCSI
Okta app and Slack client reject).

Tokens are sourced from cursor-cli's per-project OAuth caches
(``~/.cursor/projects/*/mcp-auth.json``). cursor performs each server's OAuth
flow with its own approved client and refreshes the token in place; this command
just reads whatever cursor most recently minted, picking the cache with the most
remaining validity.

``--login`` delegates to ``cursor-agent mcp login <server>``, which runs the
browser flow using cursor's approved client (e.g. Slack's admin-gated workspace
app, or the SCSI Okta app) and writes the refreshed token back into cursor's
cache. This is the supported way to (re)authenticate without reimplementing each
provider's OAuth here, and avoids the ``k-slack`` confidential client that the
Elastic workspace has not approved. ``--login`` is a no-op when the cached token
is still valid (``cursor-agent mcp login`` always re-runs the full browser flow
with no already-fresh short-circuit); pass ``--force`` to re-authenticate
anyway. ``cursor-agent mcp login`` exits 0 even on failure, so success is
determined by re-reading the cache afterwards.

Usage:
  ,mcp-token <server>                   Print the raw access token
  ,mcp-token <server> --bearer          Print "Bearer <token>" (Authorization header)
  ,mcp-token <server> --json            Print {token, source, seconds_left} as JSON
  ,mcp-token <server> --login           Refresh via cursor if stale, then print the token
  ,mcp-token <server> --login --quiet   Refresh without streaming auth helper output
  ,mcp-token <server> --login --force   Re-authenticate even if the token is still valid

Examples:
  ,mcp-token slack --bearer
  ,mcp-token scsi-main --login

Exit codes:
  0  a valid token was found and printed
  1  no valid token in any cursor cache (re-run with --login)
"""

from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

CURSOR_CACHE_GLOB = os.path.expanduser("~/.cursor/projects/*/mcp-auth.json")
OPAQUE_REFRESH_STATE = os.path.expanduser("~/.cache/mcp-token/opaque-refresh.json")
# Treat a token as stale this many seconds before its nominal expiry, so a
# token that would die mid-session is skipped in favour of a fresher one.
EXPIRY_SKEW_SECONDS = 300


def _jwt_seconds_left(access_token: str, now: float) -> float | None:
    """Return seconds until JWT ``exp`` when *access_token* is a JWT."""
    parts = access_token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        decoded = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, TypeError):
        return None
    exp = decoded.get("exp")
    if isinstance(exp, (int, float)):
        return float(exp) - now
    return None


def _token_hash(access_token: str) -> str:
    return hashlib.sha256(access_token.encode("utf-8")).hexdigest()


def _load_opaque_refresh_state() -> dict[str, dict[str, object]]:
    try:
        with open(OPAQUE_REFRESH_STATE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _record_opaque_refresh(server: str, access_token: str, source: str, refreshed_at: float) -> None:
    state = _load_opaque_refresh_state()
    state[server] = {
        "source": source,
        "token_sha256": _token_hash(access_token),
        "refreshed_at": refreshed_at,
    }
    state_dir = os.path.dirname(OPAQUE_REFRESH_STATE)
    os.makedirs(state_dir, mode=0o700, exist_ok=True)
    os.chmod(state_dir, 0o700)
    tmp = f"{OPAQUE_REFRESH_STATE}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, OPAQUE_REFRESH_STATE)
    os.chmod(OPAQUE_REFRESH_STATE, 0o600)


def _opaque_seconds_left(server: str, access_token: str, source: str, expires_in: object, now: float) -> float | None:
    if not isinstance(expires_in, (int, float)):
        return float("inf")
    state = _load_opaque_refresh_state().get(server)
    if not isinstance(state, dict):
        return None
    if state.get("source") != source or state.get("token_sha256") != _token_hash(access_token):
        return None
    refreshed_at = state.get("refreshed_at")
    if not isinstance(refreshed_at, (int, float)):
        return None
    return float(refreshed_at) + float(expires_in) - now


def _candidates(
    server: str,
    *,
    login_started_at: float | None = None,
) -> list[tuple[float, str, str, bool, object]]:
    """Return candidate token records, newest-validity first."""
    now = time.time()
    out: list[tuple[float, str, str, bool, object]] = []
    for path in glob.glob(CURSOR_CACHE_GLOB):
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        tokens = data.get(server, {}).get("tokens")
        if not isinstance(tokens, dict):
            continue
        access_token = tokens.get("access_token")
        if not access_token:
            continue
        expires_in = tokens.get("expires_in")
        is_opaque = False
        seconds_left = _jwt_seconds_left(access_token, now)
        if seconds_left is None:
            is_opaque = True
            # Cursor stores multiple servers in one cache file. Its file mtime
            # is therefore not a safe per-token issue time for opaque tokens.
            # Use our per-server sidecar, or a just-touched cache only in the
            # immediate post-login verification path.
            seconds_left = _opaque_seconds_left(server, access_token, path, expires_in, now)
            if seconds_left is None and login_started_at is not None:
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                if mtime >= login_started_at - 2 and isinstance(expires_in, (int, float)):
                    seconds_left = (mtime + float(expires_in)) - now
            if seconds_left is None:
                continue
        out.append((seconds_left, access_token, path, is_opaque, expires_in))
    out.sort(key=lambda c: c[0], reverse=True)
    return out


def _pick_record(
    server: str,
    *,
    login_started_at: float | None = None,
) -> tuple[float, str, str, bool, object] | None:
    for record in _candidates(server, login_started_at=login_started_at):
        if record[0] > EXPIRY_SKEW_SECONDS:
            return record
    return None


def _pick(server: str) -> tuple[str, str, float] | None:
    """Pick the freshest still-valid token. Returns (token, source, seconds_left)."""
    record = _pick_record(server)
    if record is None:
        return None
    seconds_left, token, source, _, _ = record
    return token, source, seconds_left


def _login(server: str, *, force: bool = False, quiet: bool = False) -> bool:
    """Run cursor's browser OAuth flow for *server*, refreshing cursor's cache.

    No-op when the cached token is still valid, unless *force* is set, since
    cursor-agent mcp login always re-runs the full browser flow with no
    already-fresh short-circuit. cursor-agent mcp login exits 0 even on failure,
    so callers must verify the cache afterwards rather than trusting the return
    code.
    """
    if not force and _pick(server) is not None:
        if not quiet:
            print(
                f",mcp-token: {server} token still valid; skipping login (use --force to re-authenticate anyway).",
                file=sys.stderr,
            )
        return True
    if not quiet:
        print(f",mcp-token: running cursor-agent mcp login {server} …", file=sys.stderr)
    login_started_at = time.time()
    try:
        subprocess.run(
            ["cursor-agent", "mcp", "login", server],
            check=False,
            stdout=subprocess.DEVNULL if quiet else None,
            stderr=subprocess.DEVNULL if quiet else None,
        )
    except FileNotFoundError:
        if not quiet:
            print(",mcp-token: cursor-agent not found; cannot run MCP login flow.", file=sys.stderr)
        return False
    record = _pick_record(server, login_started_at=login_started_at)
    if record is None:
        return False
    _, token, source, is_opaque, expires_in = record
    if is_opaque and isinstance(expires_in, (int, float)):
        _record_opaque_refresh(server, token, source, login_started_at)
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog=",mcp-token",
        description="Print a valid MCP access token from cursor's OAuth cache.",
    )
    parser.add_argument(
        "server",
        help="MCP server name as it appears in cursor's cache (e.g. slack, scsi-main)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--bearer",
        action="store_true",
        help='Print "Bearer <token>" for an Authorization header',
    )
    group.add_argument(
        "--json",
        action="store_true",
        help="Print {token, source, seconds_left} as JSON",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Run cursor's browser OAuth flow (cursor-agent mcp login) if the token is stale",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --login, re-authenticate even if the cached token is still valid",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="With --login, suppress status and delegated auth helper output",
    )
    args = parser.parse_args(argv)

    if args.login:
        if not _login(args.server, force=args.force, quiet=args.quiet):
            return 1
    elif args.force:
        parser.error("--force requires --login")
    elif args.quiet:
        parser.error("--quiet requires --login")

    picked = _pick(args.server)
    if picked is None:
        print(
            f",mcp-token: no valid {args.server} token in cursor cache (run: ,mcp-token {args.server} --login).",
            file=sys.stderr,
        )
        return 1

    token, source, seconds_left = picked
    if args.json:
        left = None if seconds_left == float("inf") else int(seconds_left)
        print(json.dumps({"token": token, "source": source, "seconds_left": left}))
    elif args.bearer:
        print(f"Bearer {token}")
    else:
        print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
