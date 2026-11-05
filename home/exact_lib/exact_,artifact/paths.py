from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

APP = "agent-artifacts"
HOST = "127.0.0.1"
NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_LIFECYCLE_MUTEX = threading.RLock()
_lifecycle_locked = False


def cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    return Path(base).expanduser() / APP if base else Path.home() / ".cache" / APP


@contextlib.contextmanager
def lifecycle_lock():
    global _lifecycle_locked
    with _LIFECYCLE_MUTEX:
        if _lifecycle_locked:
            yield
            return
        root = cache_root()
        root.parent.mkdir(parents=True, exist_ok=True)
        with root.with_name(f".{root.name}.lifecycle.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            _lifecycle_locked = True
            try:
                yield
            finally:
                _lifecycle_locked = False
                fcntl.flock(lock, fcntl.LOCK_UN)


def run_text(argv: list[str], cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def canonical_context_path(cwd: Path) -> Path:
    git_root = run_text(["git", "rev-parse", "--show-toplevel"], cwd)
    return Path(git_root).resolve() if git_root else cwd.resolve()


def workspace_identity() -> tuple[str, str]:
    raw_id = os.environ.get("HERDR_WORKSPACE_ID", "")
    if not raw_id:
        return "no-herdr", "no-herdr"
    name = raw_id
    workspace = run_text(["herdr", "workspace", "get", raw_id])
    if workspace:
        try:
            name = json.loads(workspace)["result"]["workspace"]["label"] or raw_id
        except (ValueError, KeyError, TypeError):
            pass
    key = NAME_RE.sub("-", raw_id).strip("-") or "herdr"
    return key, name


def context() -> dict[str, str]:
    cwd = Path.cwd().resolve()
    root = canonical_context_path(cwd)
    workspace_key, workspace_name = workspace_identity()
    root_hash = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    session_dir = cache_root() / "sessions" / workspace_key / root_hash
    return {
        "cwd": str(cwd),
        "root": str(root),
        "root_hash": root_hash,
        "workspace_key": workspace_key,
        "workspace_name": workspace_name,
        "session_dir": str(session_dir),
    }


def session_dir() -> Path:
    return Path(context()["session_dir"]).resolve()


def artifacts_dir() -> Path:
    return session_dir() / "artifacts"


def feedback_dir() -> Path:
    return session_dir() / "feedback"


def pollers_dir() -> Path:
    return session_dir() / "pollers"


def sanitize_name(name: str | None) -> str:
    raw = (name or "artifact").strip()
    if not raw:
        raw = "artifact"
    stem = NAME_RE.sub("-", raw).strip(".-") or "artifact"
    if not stem.lower().endswith((".html", ".htm")):
        stem += ".html"
    return stem


def sanitize_asset_name(name: str) -> str:
    return NAME_RE.sub("-", name.strip()).strip(".-")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def artifact_path(name: str | None) -> Path:
    return artifacts_dir() / sanitize_name(name)


def ensure_session() -> Path:
    sdir = session_dir()
    artifacts_dir().mkdir(parents=True, exist_ok=True)
    feedback_dir().mkdir(parents=True, exist_ok=True)
    meta = context()
    meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (sdir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return sdir
