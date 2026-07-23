"""Restricted persistence for provider-owned tool-call context."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

RETENTION_SECONDS = 30 * 24 * 60 * 60


def default_state_path() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()
    return base / "vertex-adapter" / "opaque-tool-context.json"


class OpaqueContextStore:
    """Persist only signatures/thinking blocks required by provider tool loops."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or os.environ.get("VERTEX_ADAPTER_STATE", "") or default_state_path())
        self.lock_path = self.path.with_suffix(".lock")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            with os.fdopen(descriptor, "r+") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                yield
        finally:
            pass

    def _read(self) -> dict[str, dict[str, object]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, TypeError, ValueError):
            return {}
        if not isinstance(payload, dict):
            return {}
        now = time.time()
        return {
            key: value
            for key, value in payload.items()
            if isinstance(key, str)
            and isinstance(value, dict)
            and now - float(value.get("saved_at", 0)) <= RETENTION_SECONDS
        }

    def _write(self, payload: dict[str, dict[str, object]]) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=".opaque-", dir=self.path.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(payload, output, separators=(",", ":"), sort_keys=True)
                output.write("\n")
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def get(self, call_id: str) -> dict[str, object] | None:
        with self._locked():
            entry = self._read().get(call_id)
        if not entry:
            return None
        value = entry.get("value")
        return value if isinstance(value, dict) else None

    def save(self, call_id: str, value: dict[str, object]) -> None:
        if not call_id or not value:
            return
        with self._locked():
            payload = self._read()
            payload[call_id] = {"saved_at": time.time(), "value": value}
            self._write(payload)
