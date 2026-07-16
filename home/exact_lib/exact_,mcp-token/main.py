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

``--login`` delegates re-authentication to cursor, never reimplementing each
provider's OAuth here. It prefers a **silent refresh-grant rotation**: cursor
executes the provider's ``refresh_token`` grant whenever a stored access token
stops working, so ``--login`` invalidates the access token in the newest
rotatable project cache (one holding a ``refresh_token`` whose
``.workspace-trusted`` records an existing workspace directory) and runs a
bounded ``cursor-agent mcp list-tools <server>`` there; cursor writes the
freshly minted chain back in place with no browser and without revoking the
in-flight token running sessions already hold. Only when no rotatable cache
exists or rotation fails does ``cursor-agent mcp login <server>`` run the
browser flow with cursor's approved client (e.g. Slack's admin-gated workspace
app, or the SCSI Okta app); this avoids the ``k-slack`` confidential client
that the Elastic workspace has not approved.

``--login`` guarantees runway, not just validity. Header-auth consumers
(Copilot, Codex) read the token once at launch and never reload it, so a token
with only minutes left still dies mid-session; when the selected token has less
than ``MIN_TTL_SECONDS`` remaining, ``--login`` rotates silently even though
the token is technically valid (keeping the short token if rotation is
unavailable, never escalating a still-valid token to a browser). Managed
launchers use ``--launch-json`` to capture that still-valid token first and
defer proactive rotation until after launch; the final
``BLOCKING_ROTATE_TTL_SECONDS`` window, expired tokens, and revoked tokens still
rotate synchronously. ``--rotate`` performs the deferred silent rotation with
no browser fallback.

``--login`` skips even the silent rotation when it can prove the current token
still works and has runway. For JWT servers (SCSI) that is the token's ``exp``.
For opaque servers (Slack) expiry is not visible, and the local refresh ledger
can pin a token that the provider has since revoked, so ``--login`` validates
the ledger-selected token against the server's URL (read from the generated
``~/.cursor/mcp.json``) with a minimal MCP ``initialize`` probe. A ``2xx``
keeps it; a ``401``/``403`` means the token is revoked, so a silent rotation is
tried first (a fresh mint earns the full nominal window in the ledger), then
other distinct cached opaque tokens are probed newest-cache first and a live
one is adopted (repointing the ledger) without a browser. An adopted cached
alternative is trusted only for a short verification lease
(``VERIFIED_ADOPTION_TTL_SECONDS``), not the provider's full nominal lifetime,
since its true remaining life is unknown. The probe never follows redirects: a
``3xx`` is inconclusive and the bearer is never resent to the ``Location``. Only
when no live candidate exists — or on ``--force`` — does the browser flow run;
because ``cursor-agent mcp login`` exits 0 even on failure, post-login success is
confirmed only from a cache this attempt actually wrote or touched plus the same
liveness probe (never the exit code, and never a token that predates the login).
Network errors, timeouts, ``3xx``, ``5xx``, or a missing URL leave liveness
unknown, in which case the existing ledger token is preserved rather than forcing
an unnecessary browser login. Plain reads never touch the network.

Usage:
  ,mcp-token <server>                   Print the raw access token
  ,mcp-token <server> --bearer          Print "Bearer <token>" (Authorization header)
  ,mcp-token <server> --json            Print {token, source, seconds_left} as JSON
  ,mcp-token <server> --login           Ensure a fresh token (silent rotation, browser last resort)
  ,mcp-token <server> --login --launch-json
                                        Capture launch metadata; defer proactive rotation
  ,mcp-token <server> --rotate          Perform a due silent rotation without browser fallback
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
import fcntl
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Iterator, NamedTuple
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

CURSOR_CACHE_GLOB = os.path.expanduser("~/.cursor/projects/*/mcp-auth.json")
CURSOR_MCP_CONFIG = os.path.expanduser("~/.cursor/mcp.json")
OPAQUE_REFRESH_STATE = os.path.expanduser("~/.cache/mcp-token/opaque-refresh.json")
ROTATION_LOCK = os.path.expanduser("~/.cache/mcp-token/rotation.lock")
# Treat a token as stale this many seconds before its nominal expiry, so a
# token that would die mid-session is skipped in favour of a fresher one.
EXPIRY_SKEW_SECONDS = 300
# A provider-verified cached alternative (a token another cache holds that the
# server just answered 2xx for) is trusted only for a short verification lease,
# never for the provider's full nominal lifetime: its real remaining life is
# unknown (the ledger issue time isn't ours). The lease must outlast the
# wrapper's immediate follow-up plain read / config re-bake (> EXPIRY_SKEW_SECONDS)
# yet stay far below a fresh token's ``expires_in``. Recorded as ``valid_until``.
VERIFIED_ADOPTION_TTL_SECONDS = 600
# Minimum remaining validity ``--login`` guarantees before letting a wrapper
# launch with the selected token. Copilot/Codex read the Authorization value
# once at launch and never reload it, so a technically-valid token with only
# minutes left still dies mid-session; below this floor ``--login`` first
# attempts a silent refresh-grant rotation (no browser).
MIN_TTL_SECONDS = 2700
# Launchers may use a still-valid token while rotating proactively after they
# have captured it. Inside this final window they keep rotation synchronous so
# a failed background refresh cannot leave a newly launched session with only
# moments of token life.
BLOCKING_ROTATE_TTL_SECONDS = 600
# Placeholder written over a cache's ``access_token`` to force cursor's next
# connection to run the provider's refresh grant. Never printed, and never a
# selectable candidate: it is not a JWT and can never match the opaque ledger.
ROTATION_SENTINEL = "mcp-token-rotation-pending"
# Bound for the cursor-agent invocation that executes the refresh grant.
ROTATE_TIMEOUT_SECONDS = 60
# MCP protocol version sent in the liveness ``initialize`` probe. A revoked
# opaque token is rejected at the auth layer (401/403) before protocol
# negotiation, so the exact value only matters for the live 2xx path.
MCP_PROTOCOL_VERSION = "2025-06-18"
# Liveness probes must be quick and never hang a wrapper's pre-launch refresh.
PROBE_TIMEOUT_SECONDS = 5.0

# Liveness verdicts for an opaque token probed against its MCP server URL.
LIVE = "live"
REVOKED = "revoked"
UNKNOWN = "unknown"


class LoginResult(NamedTuple):
    success: bool
    rotation_due: bool = False


class _NoRedirectHandler(HTTPRedirectHandler):
    """Refuse to auto-follow 3xx during a liveness probe.

    urllib's default redirect handler carries the ``Authorization`` header to the
    ``Location`` target, so a server answering the probe with a redirect could
    forward the bearer to another origin whose ``2xx`` would be misread as LIVE.
    Returning ``None`` leaves any 3xx unhandled, so it surfaces as an ``HTTPError``
    that :func:`_probe_liveness` classifies as UNKNOWN — the bearer is never sent
    to the ``Location``.
    """

    def redirect_request(self, *args, **kwargs):  # noqa: D401 - see class docstring
        return None


# Opener that classifies redirects as errors instead of following them.
_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


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


def _record_opaque_refresh(
    server: str,
    access_token: str,
    source: str,
    refreshed_at: float,
    *,
    valid_until: float | None = None,
) -> None:
    """Pin *server*'s opaque token in the local refresh ledger.

    A freshly minted (browser-login) token records only ``refreshed_at`` and is
    trusted for its full ``expires_in``. A provider-verified cached *alternative*
    also records ``valid_until`` — an absolute conservative lease deadline — which
    :func:`_opaque_seconds_left` prefers over the nominal lifetime, so adopting an
    already-aged token never claims a full fresh window.
    """
    state = _load_opaque_refresh_state()
    entry: dict[str, object] = {
        "source": source,
        "token_sha256": _token_hash(access_token),
        "refreshed_at": refreshed_at,
    }
    if valid_until is not None:
        entry["valid_until"] = valid_until
    state[server] = entry
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
    state = _load_opaque_refresh_state().get(server)
    matched = (
        isinstance(state, dict)
        and state.get("source") == source
        and state.get("token_sha256") == _token_hash(access_token)
    )
    if matched:
        valid_until = state.get("valid_until")  # type: ignore[union-attr]
        if isinstance(valid_until, (int, float)):
            # Provider-verified cached alternative: a conservative lease, not the
            # provider's full nominal lifetime.
            return float(valid_until) - now
    if not isinstance(expires_in, (int, float)):
        return float("inf")
    if not matched:
        return None
    refreshed_at = state.get("refreshed_at")  # type: ignore[union-attr]
    if not isinstance(refreshed_at, (int, float)):
        return None
    return float(refreshed_at) + float(expires_in) - now


def _candidates(server: str) -> list[tuple[float, str, str, bool, object]]:
    """Return candidate token records, newest-validity first.

    A candidate's remaining validity comes only from a JWT ``exp`` or the opaque
    refresh ledger — never from a cache file's mtime, which is not a safe
    per-token issue time (cursor stores several servers in one file).
    """
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
            seconds_left = _opaque_seconds_left(server, access_token, path, expires_in, now)
            if seconds_left is None:
                continue
        out.append((seconds_left, access_token, path, is_opaque, expires_in))
    out.sort(key=lambda c: c[0], reverse=True)
    return out


def _pick_record(server: str) -> tuple[float, str, str, bool, object] | None:
    for record in _candidates(server):
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


def _server_url(server: str) -> str | None:
    """Return *server*'s HTTP(S) URL from the generated ``~/.cursor/mcp.json``.

    This is the canonical server→URL registry the command already depends on; a
    stdio server (no ``url``) or a missing/malformed config yields ``None``.
    """
    try:
        with open(CURSOR_MCP_CONFIG) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return None
    entry = servers.get(server)
    if not isinstance(entry, dict):
        return None
    url = entry.get("url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return url
    return None


def _probe_liveness(url: str, access_token: str) -> str:
    """Classify *access_token* against *url* with a minimal MCP ``initialize``.

    Returns ``LIVE`` (2xx), ``REVOKED`` (401/403), or ``UNKNOWN`` (network error,
    timeout, 3xx redirect, 5xx, or any other status). Redirects are never
    followed, so the bearer is never resent to a ``Location`` on another origin.
    Only the HTTP status is inspected; the response body is never read or logged,
    and neither the token nor the body is printed anywhere.
    """
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcp-token-liveness", "version": "1"},
            },
        }
    ).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {access_token}",
        },
    )
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=PROBE_TIMEOUT_SECONDS) as response:
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except (URLError, OSError, ValueError):
        return UNKNOWN
    if 200 <= status < 300:
        return LIVE
    if status in (401, 403):
        return REVOKED
    # 3xx (redirect refused above), 5xx, and any other status are inconclusive.
    return UNKNOWN


def _opaque_cache_candidates(server: str) -> list[tuple[str, str]]:
    """Return distinct opaque cached tokens for *server*, newest-cache first.

    Deduplicated by token (keeping the newest cache that holds it). File mtime is
    used only for ordering, never as proof of validity; JWT tokens are excluded.
    """
    now = time.time()
    newest: dict[str, tuple[float, str]] = {}
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
        if _jwt_seconds_left(access_token, now) is not None:
            continue
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        current = newest.get(access_token)
        if current is None or mtime > current[0]:
            newest[access_token] = (mtime, path)
    ordered = sorted(newest.items(), key=lambda item: item[1][0], reverse=True)
    return [(token, source) for token, (_, source) in ordered]


def _post_login_candidates(server: str, login_started_at: float) -> list[tuple[str, str, bool, object]]:
    """Return tokens from caches written/touched during this login attempt.

    Post-login success may rest only on a cache this attempt actually wrote or
    touched (mtime at/after *login_started_at*); pre-login caches and the refresh
    ledger are ignored, so a stale live token can never make a failed browser
    login look successful. Returns ``(token, source, is_opaque, expires_in)``,
    newest-cache first. mtime is the write signal only, never proof of validity —
    the exact token is still probed (opaque) or exp-checked (JWT) by the caller.
    """
    now = time.time()
    out: list[tuple[float, str, str, bool, object]] = []
    for path in glob.glob(CURSOR_CACHE_GLOB):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime < login_started_at - 2:
            continue
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
        is_opaque = _jwt_seconds_left(access_token, now) is None
        out.append((mtime, access_token, path, is_opaque, tokens.get("expires_in")))
    out.sort(key=lambda c: c[0], reverse=True)
    return [(token, source, is_opaque, expires_in) for _, token, source, is_opaque, expires_in in out]


def _trusted_workspace(project_dir: str) -> str | None:
    """Return the project cache's recorded workspace directory when it exists.

    cursor keys its OAuth caches by a project slug derived from the workspace
    path; the slug is not reversible, but every trusted project records its
    real path in ``.workspace-trusted``. That path is where cursor-agent must
    run for it to read (and rotate) this cache.
    """
    try:
        with open(os.path.join(project_dir, ".workspace-trusted")) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    workspace = data.get("workspacePath") if isinstance(data, dict) else None
    if isinstance(workspace, str) and os.path.isdir(workspace):
        return workspace
    return None


def _rotation_candidate(server: str) -> tuple[str, str] | None:
    """Return ``(cache_path, workspace)`` for the newest rotatable cache.

    A cache is rotatable when it holds a ``refresh_token`` for *server* and its
    project records an existing trusted workspace directory. Newest cache mtime
    first: providers with rotating (single-use) refresh tokens keep only the
    most recently written chain alive, so older caches are strictly worse bets.
    mtime orders attempts only; it never proves validity — the rotation result
    is re-read and verified before being trusted.
    """
    best: list[tuple[float, str, str]] = []
    for path in glob.glob(CURSOR_CACHE_GLOB):
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        tokens = data.get(server, {}).get("tokens")
        if not isinstance(tokens, dict):
            continue
        if not tokens.get("refresh_token") or not tokens.get("access_token"):
            continue
        workspace = _trusted_workspace(os.path.dirname(path))
        if workspace is None:
            continue
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        best.append((mtime, path, workspace))
    if not best:
        return None
    best.sort(reverse=True)
    return best[0][1], best[0][2]


def _rewrite_cache(path: str, data: dict) -> bool:
    """Atomically rewrite *path* with *data*, preserving its file mode."""
    try:
        mode = os.stat(path).st_mode & 0o777
        tmp = f"{path}.{os.getpid()}.mcp-token.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except OSError:
        return False
    return True


def _read_cache_tokens(path: str, server: str) -> dict | None:
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    tokens = data.get(server, {}).get("tokens")
    return tokens if isinstance(tokens, dict) else None


def _restore_access_token(path: str, server: str, expected: str, original: str) -> None:
    """Compare-and-swap *expected* back to *original*; never clobber other writers."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    tokens = data.get(server, {}).get("tokens")
    if isinstance(tokens, dict) and tokens.get("access_token") == expected:
        tokens["access_token"] = original
        _rewrite_cache(path, data)


@contextmanager
def _rotation_lock() -> Iterator[None]:
    """Serialize cache rewrites from concurrent deferred rotations."""
    state_dir = os.path.dirname(ROTATION_LOCK)
    os.makedirs(state_dir, mode=0o700, exist_ok=True)
    os.chmod(state_dir, 0o700)
    descriptor = os.open(ROTATION_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _silent_rotate_unlocked(server: str, *, quiet: bool = False) -> bool:
    """Mint a fresh token chain via cursor's refresh grant, without a browser.

    ``cursor-agent mcp login`` always runs the full browser flow, but cursor
    silently executes the provider's ``refresh_token`` grant whenever a stored
    access token stops working. This invalidates the cached access token in the
    newest rotatable project cache and runs a bounded, targeted
    ``cursor-agent mcp list-tools <server>`` in that cache's workspace, forcing
    exactly that grant; cursor writes the freshly minted chain (new access
    token, and for rotating providers a new refresh token) back in place.
    Rotation never revokes the in-flight token a running session already holds.
    On any failure the original access token is restored (compare-and-swap, so
    a concurrent legitimate writer is never clobbered) and the caller falls
    back to its existing probe/adoption/browser chain.
    """
    candidate = _rotation_candidate(server)
    if candidate is None:
        return False
    path, workspace = candidate
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return False
    tokens = data.get(server, {}).get("tokens")
    if not isinstance(tokens, dict):
        return False
    original = tokens.get("access_token")
    if not original:
        return False
    tokens["access_token"] = ROTATION_SENTINEL
    if not _rewrite_cache(path, data):
        return False
    if not quiet:
        print(f",mcp-token: rotating {server} token via cursor refresh grant …", file=sys.stderr)
    rotate_started_at = time.time()
    try:
        subprocess.run(
            ["cursor-agent", "mcp", "list-tools", server],
            cwd=workspace,
            check=False,
            timeout=ROTATE_TIMEOUT_SECONDS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    rotated = _read_cache_tokens(path, server)
    access_token = rotated.get("access_token") if rotated is not None else None
    if not isinstance(access_token, str) or not access_token or access_token == ROTATION_SENTINEL:
        _restore_access_token(path, server, ROTATION_SENTINEL, original)
        if not quiet:
            print(f",mcp-token: {server} silent rotation failed.", file=sys.stderr)
        return False
    now = time.time()
    seconds_left = _jwt_seconds_left(access_token, now)
    if seconds_left is not None:
        return seconds_left > EXPIRY_SKEW_SECONDS
    # Opaque: the provider minted this chain during this attempt, so it earns
    # the full nominal window in the ledger — unlike an adopted aged alternative.
    expires_in = rotated.get("expires_in") if rotated is not None else None
    if isinstance(expires_in, (int, float)):
        _record_opaque_refresh(server, access_token, path, rotate_started_at)
        return True
    return False


def _silent_rotate(server: str, *, quiet: bool = False) -> bool:
    with _rotation_lock():
        return _silent_rotate_unlocked(server, quiet=quiet)


def _rotate_if_due(server: str, *, quiet: bool = False) -> bool:
    """Rotate *server* only when its selected token still lacks full runway."""
    with _rotation_lock():
        current = _pick_record(server)
        if current is not None and current[0] > MIN_TTL_SECONDS:
            return True
        return _silent_rotate_unlocked(server, quiet=quiet)


def _browser_login(server: str, *, quiet: bool = False) -> bool:
    """Run cursor's browser OAuth flow and confirm it yielded a live token.

    ``cursor-agent mcp login`` exits 0 even on failure, so success is confirmed
    from a cache this attempt actually wrote or touched plus a liveness probe (for
    opaque servers with a known URL), never the exit code alone. Tokens that
    predate this login — including any the refresh ledger still pins — can never
    satisfy it, so a stale live cache cannot mask a failed browser login.
    """
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

    candidates = _post_login_candidates(server, login_started_at)
    if not candidates:
        if not quiet:
            print(f",mcp-token: {server} login produced no usable token.", file=sys.stderr)
        return False

    url = _server_url(server)
    now = time.time()
    for token, source, is_opaque, expires_in in candidates:
        if not is_opaque:
            # JWT written by this login: exp already proves validity.
            seconds_left = _jwt_seconds_left(token, now)
            if seconds_left is not None and seconds_left > EXPIRY_SKEW_SECONDS:
                return True
            continue
        if url is None:
            # No probe possible; the freshly written cache is the only evidence.
            if isinstance(expires_in, (int, float)):
                _record_opaque_refresh(server, token, source, login_started_at)
            return True
        verdict = _probe_liveness(url, token)
        if verdict == REVOKED:
            continue
        # LIVE or UNKNOWN: accept this freshly written token. UNKNOWN falls back
        # to the fresh-cache evidence, which the probe cannot refute.
        if isinstance(expires_in, (int, float)):
            _record_opaque_refresh(server, token, source, login_started_at)
        return True

    if not quiet:
        print(f",mcp-token: {server} login did not yield a live token.", file=sys.stderr)
    return False


def _login(
    server: str,
    *,
    force: bool = False,
    quiet: bool = False,
    defer_short_rotation: bool = False,
) -> LoginResult:
    """Ensure *server* has a token with real remaining runway, browser last.

    ``--force`` always runs the browser flow. Otherwise the selected token must
    keep at least ``MIN_TTL_SECONDS`` of validity: header-auth consumers
    (Copilot, Codex) read the token once at launch and never reload it, so a
    short-but-valid token still dies mid-session. Launch mode may defer a
    proactive rotation until after the caller captures that token, but keeps the
    final ``BLOCKING_ROTATE_TTL_SECONDS`` synchronous. Expired or revoked tokens
    always rotate synchronously. A live cached alternative is adopted next for
    revoked opaque tokens, and only then does the browser flow run.
    """
    if force:
        return LoginResult(_browser_login(server, quiet=quiet))

    nominal = _pick_record(server)
    if nominal is None:
        # Nothing valid in any cache: rotate silently before any browser flow.
        if _rotate_if_due(server, quiet=quiet):
            return LoginResult(True)
        return LoginResult(_browser_login(server, quiet=quiet))

    seconds_left, nominal_token, _source, is_opaque, _expires_in = nominal

    if not is_opaque:
        # JWT (or non-expiring) candidate: exp is authoritative.
        if seconds_left > MIN_TTL_SECONDS:
            if not quiet:
                print(
                    f",mcp-token: {server} token still valid; skipping login (use --force to re-authenticate anyway).",
                    file=sys.stderr,
                )
            return LoginResult(True)
        if defer_short_rotation and seconds_left > BLOCKING_ROTATE_TTL_SECONDS:
            return LoginResult(True, rotation_due=True)
        if _rotate_if_due(server, quiet=quiet):
            return LoginResult(True)
        # Still exp-valid: a short token beats an unnecessary browser flow.
        if not quiet:
            print(
                f",mcp-token: {server} token near expiry and rotation unavailable; keeping current token.",
                file=sys.stderr,
            )
        return LoginResult(True)

    rotation_due = defer_short_rotation and BLOCKING_ROTATE_TTL_SECONDS < seconds_left <= MIN_TTL_SECONDS
    rotation_failed = False
    if seconds_left <= MIN_TTL_SECONDS and not rotation_due:
        if _rotate_if_due(server, quiet=quiet):
            return LoginResult(True)
        rotation_failed = True

    url = _server_url(server)
    if url is None:
        # Cannot probe; do not force a browser login merely because liveness is
        # unknown. Preserve the existing ledger token.
        if not quiet:
            print(
                f",mcp-token: {server} token still valid; skipping login (use --force to re-authenticate anyway).",
                file=sys.stderr,
            )
        return LoginResult(True, rotation_due=rotation_due)

    verdict = _probe_liveness(url, nominal_token)
    if verdict == LIVE:
        if not quiet:
            print(f",mcp-token: {server} token verified live; skipping login.", file=sys.stderr)
        return LoginResult(True, rotation_due=rotation_due)
    if verdict == UNKNOWN:
        if not quiet:
            print(
                f",mcp-token: {server} liveness could not be verified; keeping current token (skipping login).",
                file=sys.stderr,
            )
        return LoginResult(True, rotation_due=rotation_due)

    # verdict == REVOKED: a silent rotation mints a full-life chain, which beats
    # adopting an aged cached alternative on a short verification lease.
    if (rotation_due or not rotation_failed) and _silent_rotate(server, quiet=quiet):
        return LoginResult(True)
    for token, source in _opaque_cache_candidates(server):
        if token == nominal_token:
            continue
        if _probe_liveness(url, token) == LIVE:
            now = time.time()
            # Adopting an already-cached token: its true remaining life is unknown,
            # so grant only a short verification lease, not a full fresh window.
            _record_opaque_refresh(server, token, source, now, valid_until=now + VERIFIED_ADOPTION_TTL_SECONDS)
            if not quiet:
                print(
                    f",mcp-token: {server} ledger token revoked; switched to a live cached token (skipping login).",
                    file=sys.stderr,
                )
            return LoginResult(True)

    return LoginResult(_browser_login(server, quiet=quiet))


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
    group.add_argument(
        "--launch-json",
        action="store_true",
        help="With --login, return launch-safe token metadata and defer proactive rotation",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Ensure a fresh token: silent refresh-grant rotation via cursor when short or stale, browser flow (cursor-agent mcp login) as last resort",
    )
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Silently rotate a token below the min-TTL floor without a browser fallback",
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

    if args.login and args.rotate:
        parser.error("--login and --rotate are mutually exclusive")
    if args.launch_json and not args.login:
        parser.error("--launch-json requires --login")
    if args.force and not args.login:
        parser.error("--force requires --login")
    if args.quiet and not (args.login or args.rotate):
        parser.error("--quiet requires --login or --rotate")

    login_result = LoginResult(True)
    if args.login:
        login_result = _login(
            args.server,
            force=args.force,
            quiet=args.quiet,
            defer_short_rotation=args.launch_json,
        )
        if not login_result.success:
            return 1
    elif args.rotate and not _rotate_if_due(args.server, quiet=args.quiet):
        return 1

    picked = _pick(args.server)
    if picked is None:
        print(
            f",mcp-token: no valid {args.server} token in cursor cache (run: ,mcp-token {args.server} --login).",
            file=sys.stderr,
        )
        return 1

    token, source, seconds_left = picked
    if args.launch_json:
        left = None if seconds_left == float("inf") else int(seconds_left)
        print(
            json.dumps(
                {
                    "token": token,
                    "source": source,
                    "seconds_left": left,
                    "rotation_due": login_result.rotation_due,
                }
            )
        )
    elif args.json:
        left = None if seconds_left == float("inf") else int(seconds_left)
        print(json.dumps({"token": token, "source": source, "seconds_left": left}))
    elif args.bearer:
        print(f"Bearer {token}")
    else:
        print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
