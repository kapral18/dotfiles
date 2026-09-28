"""FormalKit copy-on-init and the unit template stamp.

The kit source and the unit template are owned by other packets
(``lean/FormalKit/**`` and ``templates/unit/**`` next to this package); this
module only copies them and substitutes the placeholders documented in
``templates/unit/PLACEHOLDERS.md``: ``@@KIT_PATH@@ @@UNIT@@ @@TIER@@
@@REPO_ID@@ @@BRANCH@@ @@SOURCE_COMMIT@@ @@KIT_HASH@@``.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import IO, Iterator

from . import paths
from .util import CliError, sha256_hex, short_hash

_KIT_MARKER = ".kit-complete"


def templates_dir() -> Path:
    return paths.lib_dir() / "templates" / "unit"


def kit_source_dir() -> Path:
    return paths.lib_dir() / "lean" / "FormalKit"


def kit_hash() -> str:
    """Content hash of the FormalKit source tree, used to key the copied kit."""
    source = kit_source_dir()
    if not source.exists():
        raise CliError(f"FormalKit source not found: {source}", code=2)
    entries = [
        f"{path.relative_to(source)}:{sha256_hex(path.read_bytes())}"
        for path in sorted(source.rglob("*"))
        if path.is_file()
    ]
    return short_hash("\n".join(entries).encode("utf-8"))


def kit_lock_path(dest: Path) -> Path:
    """Per-kit-hash lock file living next to the kit dirs under ``_kit/`` (``dest.parent``).

    Shared with ``catalog.gc``, which takes the same lock (non-blocking) before removing an
    unreferenced kit dir, and reads the pending-owner set ``ensure_kit`` records in it (see
    ``_record_owner``) to decide whether any process that touched this kit hash is still running."""
    return dest.parent / f".{dest.name}.lock"


@contextlib.contextmanager
def kit_lock(dest: Path, *, blocking: bool = True) -> Iterator[IO[str] | None]:
    """Exclusive ``flock`` serializing ``ensure_kit`` (and ``catalog.gc``'s removal check) for one
    kit hash. Yields the open lock-file handle once the lock is held (write to it under the lock
    to record ownership, as ``ensure_kit`` does; a reader that also holds the lock -- as
    ``catalog.gc`` does before removing anything -- is guaranteed never to see a torn write), or
    ``None`` immediately when ``blocking=False`` and another process (an in-flight ``ensure_kit``)
    already holds it -- the caller must treat that as "still in use" and skip, not error.

    Opened read/write (``O_RDWR | O_CREAT``), never append (``a+``): an append-mode file always
    writes at end-of-file regardless of any prior ``seek(0)``, so ``_record_owner``'s
    seek-then-write-then-truncate would accumulate every pid ever recorded instead of holding
    exactly one. A blocking acquisition (``blocking=True``) that still raises ``OSError`` (e.g. an
    unsupported filesystem) is an environment error, not "another process holds it" -- that
    condition is only meaningful for the non-blocking, "still in use" contract, so it is re-raised
    as ``CliError`` (code 2) instead of yielding ``None`` into ``_record_owner``."""
    lock_path = kit_lock_path(dest)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    handle = os.fdopen(fd, "r+", encoding="utf-8")
    try:
        flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        try:
            fcntl.flock(handle.fileno(), flags)
        except OSError as exc:
            if blocking:
                raise CliError(f"failed to acquire kit lock {lock_path}: {exc}", code=2) from exc
            yield None
            return
        try:
            yield handle
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def pending_owner_pids(handle: IO[str]) -> list[int]:
    """Read the pending-owner set from its JSON object representation."""
    handle.seek(0)
    raw = handle.read().strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError("Invalid kit lock owner state: expected a JSON object.", code=2) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("owners"), list):
        raise CliError("Invalid kit lock owner state: owners must be an array.", code=2)
    owners = payload["owners"]
    if any(isinstance(owner, bool) or not isinstance(owner, int) or owner <= 0 for owner in owners):
        raise CliError("Invalid kit lock owner state: owners must contain positive integer PIDs.", code=2)
    return list(dict.fromkeys(owners))


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, OverflowError):
        return False
    return True


def _record_owner(handle: IO[str]) -> None:
    """Add this process to the live pending-owner set under the held kit lock."""
    owners = [pid for pid in pending_owner_pids(handle) if _pid_alive(pid)]
    pid = os.getpid()
    if pid not in owners:
        owners.append(pid)
    handle.seek(0)
    json.dump({"owners": sorted(owners)}, handle, separators=(",", ":"))
    handle.truncate()
    handle.flush()


def ensure_kit(layout: paths.Layout) -> str:
    """Copy FormalKit into ``<state>/_kit/<kit-hash>/`` if not already present.

    Copies into a temp sibling first, then ``os.replace``s it into place under an exclusive
    per-kit-hash lock (``kit_lock``), so two concurrent ``ensure_kit`` calls for the same kit hash
    (e.g. two agents starting at once) never observe a partially-copied kit, and neither one ever
    deletes the *other's* finished copy: unlike a bare pre-lock ``dest.exists()`` read (stale the
    instant another process finishes between that read and a subsequent ``rmtree``), the marker's
    presence is re-checked once the lock is held, immediately before any ``rmtree`` of an unmarked
    ``dest`` -- an unmarked ``dest`` is replaced only under the lock, after that re-check.
    ``_KIT_MARKER`` is written last, inside the temp copy, before the rename, so a `dest` that
    exists without the marker can only be a partial copy left behind by a process that was
    killed mid-copy (this scheme's atomic rename never produces an unmarked `dest`) -- that is
    treated as incomplete and replaced rather than trusted.

    Every return path -- the fast marker-already-there path included -- adds this process to the
    kit lock file's pending-owner set (``_record_owner``) before returning. The caller
    (``manifest.init_unit``, outside this module) writes its own unit's lakefile.toml (via
    ``copy_template``) and MANIFEST.json referencing this kit hash immediately afterward, but
    that write is not visible to ``catalog.gc`` (a possibly different process) until it lands on
    disk. Retaining every still-live caller here, rather than only the most recent caller or the
    lock itself (released right below), lets ``catalog.gc`` distinguish pending publication from
    a genuinely orphaned kit without requiring cooperation from ``manifest.py``.

    Never builds or writes under the deployed ``~/lib/,formal`` source tree:
    the copy under the state root is where ``lake build`` is allowed to run.
    """
    kh = kit_hash()
    dest = layout.kit_dir(kh)
    if (dest / _KIT_MARKER).exists():
        with kit_lock(dest) as handle:
            if (dest / _KIT_MARKER).exists():
                _record_owner(handle)
                return kh
            # The marker vanished between this unlocked fast-path check and taking the lock (e.g.
            # a concurrent `catalog.gc` removed an unreferenced `dest`) -- fall through to the
            # copy path below instead of trusting the stale check.
    with kit_lock(dest) as handle:
        pending_owner_pids(handle)
        if (dest / _KIT_MARKER).exists():
            _record_owner(handle)
            return kh
        if dest.exists():
            shutil.rmtree(dest)
        tmp_dest = dest.parent / f".{dest.name}.tmp.{uuid.uuid4().hex}"
        shutil.copytree(kit_source_dir(), tmp_dest)
        (tmp_dest / _KIT_MARKER).write_text("", encoding="utf-8")
        try:
            os.replace(tmp_dest, dest)
        except OSError:
            # Another process's `ensure_kit` already won the race and produced a complete `dest`
            # first -- our own copy is redundant, not an error. Under `kit_lock` this can only
            # happen for a reason unrelated to the marker race (e.g. a cross-device rename); if
            # `dest` still has no marker, this really is a genuine failure and must propagate.
            shutil.rmtree(tmp_dest, ignore_errors=True)
            if not (dest / _KIT_MARKER).exists():
                raise
        _record_owner(handle)
    return kh


def substitute(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace(f"@@{key}@@", value)
    return text


def _toml_basic_string(value: str) -> str:
    escaped: list[str] = []
    named = {"\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r", '"': '\\"', "\\": "\\\\"}
    for char in value:
        codepoint = ord(char)
        if char in named:
            escaped.append(named[char])
        elif codepoint <= 0x1F or codepoint == 0x7F:
            escaped.append(f"\\u{codepoint:04X}")
        else:
            escaped.append(char)
    return "".join(escaped)


def _serialized_template_values(path: Path, values: dict[str, str]) -> dict[str, str]:
    if path.suffix == ".json":
        return {key: json.dumps(value, ensure_ascii=False)[1:-1] for key, value in values.items()}
    if path.suffix == ".toml":
        return {key: _toml_basic_string(value) for key, value in values.items()}
    return values


def copy_template(destination: Path, values: dict[str, str]) -> None:
    source = templates_dir()
    if not source.exists():
        raise CliError(f"Unit template not found: {source}", code=2)
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        target = destination / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(path, target)
            continue
        target.write_text(substitute(text, _serialized_template_values(path, values)), encoding="utf-8")
