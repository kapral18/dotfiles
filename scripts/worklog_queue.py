#!/usr/bin/env python3
"""Crash-safe session-keyed queue for agent hook worklog events."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

QUEUE_DIR_NAME = ".worklog-queue-v1"
LOCK_DIR_NAME = ".worklog-locks-v1"
EVENT_SUFFIX = ".json"
ERROR_LOG_NAME = "errors.jsonl"
MAX_ERROR_LINES = 50
DEFAULT_MAX_PENDING = 256
DEFAULT_MAX_BYTES = 1024 * 1024
DEFAULT_MAX_WORKLOG_LINES = 200
DEFAULT_WORKER_IDLE_SECONDS = 0.08
DEFAULT_WORKER_MAX_SECONDS = 2.0
DEFAULT_CLEANUP_AGE_SECONDS = 7 * 24 * 60 * 60
STALE_STATE_GLOBS = ("session-*.worklog.jsonl", ".recall-seen-*.json")
MAX_STALE_REMOVALS_PER_PASS = 64


class QueueError(RuntimeError):
    """Base queue failure."""


class QueueFullError(QueueError):
    """The bounded pending queue cannot accept another event."""


@dataclass(frozen=True)
class QueueConfig:
    max_pending: int = DEFAULT_MAX_PENDING
    max_bytes: int = DEFAULT_MAX_BYTES
    max_worklog_lines: int = DEFAULT_MAX_WORKLOG_LINES
    worker_idle_seconds: float = DEFAULT_WORKER_IDLE_SECONDS
    worker_max_seconds: float = DEFAULT_WORKER_MAX_SECONDS
    cleanup_age_seconds: float = DEFAULT_CLEANUP_AGE_SECONDS


@dataclass(frozen=True)
class QueueReceipt:
    queue_dir: Path
    path: Path
    event_id: str
    seq: int
    worker_pid: int | None


@dataclass(frozen=True)
class FlushResult:
    flushed: int = 0
    duplicates: int = 0
    pending: int = 0
    errors: int = 0

    def add(self, other: "FlushResult") -> "FlushResult":
        return FlushResult(
            flushed=self.flushed + other.flushed,
            duplicates=self.duplicates + other.duplicates,
            pending=other.pending,
            errors=self.errors + other.errors,
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str, fallback: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip(".-")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}", safe):
        return safe
    return fallback


def queue_root(spec_dir: Path) -> Path:
    return spec_dir / QUEUE_DIR_NAME


def session_queue_dir(spec_dir: Path, session_key: str) -> Path:
    return queue_root(spec_dir) / _safe_name(session_key, "unknown-session")


def error_log_path(queue_dir: Path) -> Path:
    return queue_dir / ERROR_LOG_NAME


def record_error(spec_dir: Path, session_key: str, code: str, message: str) -> None:
    spec_dir = spec_dir.resolve()
    safe_session = _safe_name(session_key, "unknown-session")
    with _locked(_spec_activity_lock(spec_dir), shared=True):
        with _locked(_session_lifecycle_lock(spec_dir, safe_session)):
            _append_error(session_queue_dir(spec_dir, safe_session), code, message)


def _event_paths(queue_dir: Path) -> list[Path]:
    return sorted(path for path in queue_dir.glob(f"*{EVENT_SUFFIX}") if path.name[:1].isdigit())


def _pending_state(queue_dir: Path) -> tuple[int, int]:
    paths = _event_paths(queue_dir)
    total = 0
    for path in paths:
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return len(paths), total


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise QueueError(f"queue directory is not private and owned: {path}")
    if stat.S_IMODE(info.st_mode) != 0o700:
        os.chmod(path, 0o700)


@contextmanager
def _locked(path: Path, *, blocking: bool = True, shared: bool = False) -> Iterator[bool]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a+", encoding="utf-8") as stream:
        flags = (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(stream.fileno(), flags)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        os.chmod(path, mode)
        _fsync_dir(path.parent)
    except Exception:
        try:
            temp.unlink()
        except OSError:
            pass
        raise


def _append_error(queue_dir: Path, code: str, message: str) -> None:
    _ensure_private_dir(queue_dir)
    path = error_log_path(queue_dir)
    with _locked(queue_dir / "errors.lock"):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        lines.append(json.dumps({"ts": utc_now(), "code": code, "message": message[:1000]}, sort_keys=True))
        _atomic_write(path, "\n".join(lines[-MAX_ERROR_LINES:]) + "\n")


def _next_sequence(queue_dir: Path) -> int:
    sequence_path = queue_dir / "sequence"
    values = [0]
    try:
        values.append(int(sequence_path.read_text(encoding="utf-8").strip()))
    except (OSError, ValueError):
        pass
    for path in _event_paths(queue_dir):
        try:
            values.append(int(path.stem))
        except ValueError:
            continue
    return max(values) + 1


def _validate_target(spec_dir: Path, worklog_path: Path) -> str:
    spec_dir = spec_dir.resolve()
    target = worklog_path.resolve()
    if target.parent != spec_dir or not target.name.endswith(".worklog.jsonl"):
        raise QueueError(f"worklog target escapes spec directory: {worklog_path}")
    return target.name


def enqueue(
    spec_dir: Path,
    session_key: str,
    topic: str,
    worklog_path: Path,
    entry: dict,
    *,
    config: QueueConfig = QueueConfig(),
    start_worker: bool = True,
) -> QueueReceipt:
    """Durably enqueue one event, then optionally start a short-lived flusher."""
    spec_dir = spec_dir.resolve()
    safe_session = _safe_name(session_key, "unknown-session")
    safe_topic = _safe_name(topic, "current")
    queue_dir = session_queue_dir(spec_dir, safe_session)
    with _locked(_spec_activity_lock(spec_dir), shared=True):
        with _locked(_session_lifecycle_lock(spec_dir, safe_session)):
            _ensure_private_dir(queue_dir)
            target_name = _validate_target(spec_dir, worklog_path)
            with _locked(queue_dir / "enqueue.lock"):
                seq = _next_sequence(queue_dir)
                event_id = f"{safe_session}:{seq:020d}:{uuid.uuid4().hex}"
                record = {
                    "version": 1,
                    "id": event_id,
                    "seq": seq,
                    "session_key": safe_session,
                    "topic": safe_topic,
                    "worklog": target_name,
                    "enqueued_at": utc_now(),
                    "entry": entry,
                }
                encoded = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                pending, pending_bytes = _pending_state(queue_dir)
                if pending >= config.max_pending or pending_bytes + len(encoded.encode()) > config.max_bytes:
                    _append_error(queue_dir, "queue_full", f"pending={pending} bytes={pending_bytes}")
                    raise QueueFullError(f"worklog queue full for session {safe_session}")
                path = queue_dir / f"{seq:020d}{EVENT_SUFFIX}"
                _atomic_write(path, encoded)
                _atomic_write(queue_dir / "sequence", f"{seq}\n")
    worker_pid = start_flush_worker(queue_dir, config=config) if start_worker else None
    return QueueReceipt(queue_dir=queue_dir, path=path, event_id=event_id, seq=seq, worker_pid=worker_pid)


def read_queue_record(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    record = json.loads(raw)
    valid = (
        isinstance(record, dict)
        and record.get("version") == 1
        and isinstance(record.get("id"), str)
        and bool(record.get("id"))
        and isinstance(record.get("seq"), int)
        and record["seq"] > 0
        and isinstance(record.get("session_key"), str)
        and bool(record.get("session_key"))
        and isinstance(record.get("worklog"), str)
        and bool(record.get("worklog"))
        and isinstance(record.get("entry"), dict)
    )
    if not valid:
        raise QueueError(f"invalid queue record: {path}")
    return record


def _target_lock_path(spec_dir: Path, target_name: str) -> Path:
    digest = hashlib.sha256(target_name.encode()).hexdigest()[:20]
    return spec_dir / LOCK_DIR_NAME / f"{digest}.lock"


def _session_lifecycle_lock(spec_dir: Path, session_key: str) -> Path:
    digest = hashlib.sha256(session_key.encode()).hexdigest()[:20]
    return spec_dir / LOCK_DIR_NAME / f"session-{digest}.lock"


def _spec_activity_lock(spec_dir: Path) -> Path:
    return spec_dir / LOCK_DIR_NAME / "spec-activity.lock"


@contextmanager
def _active_worker_lock(queue_dir: Path) -> Iterator[bool]:
    spec_dir = queue_dir.parent.parent
    flush_lock = None
    acquired = False
    with _locked(_session_lifecycle_lock(spec_dir, queue_dir.name), blocking=False) as lifecycle:
        if lifecycle and queue_dir.is_dir():
            flush_lock = _locked(queue_dir / "flush.lock", blocking=False)
            acquired = flush_lock.__enter__()
    try:
        yield acquired
    finally:
        if flush_lock is not None:
            flush_lock.__exit__(None, None, None)


def _load_worklog(path: Path) -> tuple[list[str], set[str]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [], set()
    ids: set[str] = set()
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("worklog_id"):
            ids.add(str(value["worklog_id"]))
    return lines, ids


def _chronological_lines(lines: list[str]) -> list[str]:
    ordered: list[tuple[str, str, int, int, str]] = []
    for index, line in enumerate(lines):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            return lines
        timestamp = value.get("ts") if isinstance(value, dict) else None
        if not isinstance(timestamp, str) or not timestamp:
            return lines
        sequence = value.get("worklog_seq", 0)
        ordered.append(
            (
                timestamp,
                str(value.get("session_key") or ""),
                sequence if isinstance(sequence, int) else 0,
                index,
                line,
            )
        )
    return [item[-1] for item in sorted(ordered)]


def _flush_target(
    spec_dir: Path, target_name: str, records: list[tuple[Path, dict]], max_lines: int
) -> tuple[int, int]:
    target = spec_dir / target_name
    flushed = 0
    duplicates = 0
    with _locked(_target_lock_path(spec_dir, target_name)):
        lines, existing_ids = _load_worklog(target)
        for _, record in records:
            event_id = str(record["id"])
            if event_id in existing_ids:
                duplicates += 1
                continue
            entry = {
                **record["entry"],
                "worklog_id": event_id,
                "session_key": record["session_key"],
                "worklog_seq": record["seq"],
            }
            lines.append(json.dumps(entry, sort_keys=True))
            existing_ids.add(event_id)
            flushed += 1
        if flushed:
            lines = _chronological_lines(lines)
            _atomic_write(target, "\n".join(lines[-max_lines:]) + "\n")
    for path, _ in records:
        path.unlink()
    _fsync_dir(records[0][0].parent)
    return flushed, duplicates


def _flush_locked(queue_dir: Path, config: QueueConfig) -> FlushResult:
    paths = _event_paths(queue_dir)
    if not paths:
        return FlushResult()
    spec_dir = queue_dir.parent.parent
    by_target: dict[str, list[tuple[Path, dict]]] = {}
    errors = 0
    for path in paths:
        try:
            record = read_queue_record(path)
            target_name = str(record.get("worklog") or "")
            _validate_target(spec_dir, spec_dir / target_name)
            by_target.setdefault(target_name, []).append((path, record))
        except (OSError, ValueError, json.JSONDecodeError, QueueError) as err:
            errors += 1
            _append_error(queue_dir, "invalid_record", f"{path.name}: {err}")
    flushed = 0
    duplicates = 0
    for target_name, records in by_target.items():
        try:
            added, replayed = _flush_target(spec_dir, target_name, records, config.max_worklog_lines)
            flushed += added
            duplicates += replayed
        except OSError as err:
            errors += 1
            _append_error(queue_dir, "flush_failed", f"{target_name}: {err}")
    return FlushResult(flushed=flushed, duplicates=duplicates, pending=len(_event_paths(queue_dir)), errors=errors)


def flush_session(queue_dir: Path, *, config: QueueConfig = QueueConfig()) -> FlushResult:
    queue_dir = queue_dir.resolve()
    spec_dir = queue_dir.parent.parent
    with _locked(_session_lifecycle_lock(spec_dir, queue_dir.name)):
        if not queue_dir.is_dir():
            return FlushResult()
        with _locked(queue_dir / "flush.lock"):
            return _flush_locked(queue_dir, config)


def flush_spec_dir(spec_dir: Path, *, config: QueueConfig = QueueConfig()) -> FlushResult:
    spec_dir = spec_dir.resolve()
    root = queue_root(spec_dir)
    if not root.is_dir():
        return FlushResult()
    with _locked(_spec_activity_lock(spec_dir)):
        if not root.is_dir():
            return FlushResult()
        queue_dirs = sorted(path for path in root.iterdir() if path.is_dir())
        result = FlushResult()
        for queue_dir in queue_dirs:
            result = result.add(flush_session(queue_dir, config=config))
        recorded_errors = 0
        for queue_dir in queue_dirs:
            for error_path in (queue_dir / ERROR_LOG_NAME, queue_dir / "dispatcher-errors.jsonl"):
                try:
                    recorded_errors += len(error_path.read_text(encoding="utf-8", errors="replace").splitlines())
                except OSError:
                    pass
        final = FlushResult(
            flushed=result.flushed,
            duplicates=result.duplicates,
            pending=sum(_pending_state(path)[0] for path in queue_dirs),
            errors=max(result.errors, recorded_errors),
        )
    cleanup_spec_dir(spec_dir, config=config)
    cleanup_stale_state(spec_dir, config=config)
    return final


def run_worker(queue_dir: Path, *, config: QueueConfig = QueueConfig()) -> FlushResult:
    queue_dir = queue_dir.resolve()
    spec_dir = queue_dir.parent.parent
    result = FlushResult()
    with _active_worker_lock(queue_dir) as acquired:
        if not acquired:
            return FlushResult(pending=_pending_state(queue_dir)[0])
        started = time.monotonic()
        idle_since: float | None = None
        aggregate = FlushResult()
        while time.monotonic() - started < config.worker_max_seconds:
            current = _flush_locked(queue_dir, config)
            aggregate = aggregate.add(current)
            if current.errors or current.pending:
                if current.errors:
                    break
                idle_since = None
                continue
            if idle_since is None:
                idle_since = time.monotonic()
            elif time.monotonic() - idle_since >= config.worker_idle_seconds:
                break
            time.sleep(min(0.02, config.worker_idle_seconds))
        result = FlushResult(
            flushed=aggregate.flushed,
            duplicates=aggregate.duplicates,
            pending=_pending_state(queue_dir)[0],
            errors=aggregate.errors,
        )
    cleanup_spec_dir(spec_dir, config=config)
    cleanup_stale_state(spec_dir, config=config)
    return result


def start_flush_worker(queue_dir: Path, *, config: QueueConfig = QueueConfig()) -> int | None:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "worker",
        "--queue-dir",
        str(queue_dir),
        "--max-lines",
        str(config.max_worklog_lines),
        "--idle-seconds",
        str(config.worker_idle_seconds),
        "--max-seconds",
        str(config.worker_max_seconds),
    ]
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as err:
        record_error(queue_dir.parent.parent, queue_dir.name, "worker_spawn_failed", str(err))
        return None
    return process.pid


def migrate_worklog(spec_dir: Path, source_name: str, target_name: str, *, config: QueueConfig = QueueConfig()) -> int:
    """Merge one worklog file into another and remove the source.

    Bind-time seam for `,agent-memory select`: folds a session's pre-bind
    `session-*` fallback worklog into the bound topic's worklog so the trail
    is not split across buckets. Takes both per-target locks in deterministic
    order, dedupes by `worklog_id`, rewrites the target chronologically under
    the shared line cap, and unlinks the source. Returns migrated line count.
    """
    spec_dir = spec_dir.resolve()
    source_name = _validate_target(spec_dir, spec_dir / source_name)
    target_name = _validate_target(spec_dir, spec_dir / target_name)
    if source_name == target_name:
        return 0
    first, second = sorted((source_name, target_name))
    with _locked(_target_lock_path(spec_dir, first)):
        with _locked(_target_lock_path(spec_dir, second)):
            source = spec_dir / source_name
            if not source.exists():
                return 0
            source_lines, _ = _load_worklog(source)
            target = spec_dir / target_name
            lines, existing_ids = _load_worklog(target)
            migrated = 0
            for line in source_lines:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                worklog_id = str(value.get("worklog_id") or "") if isinstance(value, dict) else ""
                if worklog_id and worklog_id in existing_ids:
                    continue
                if worklog_id:
                    existing_ids.add(worklog_id)
                lines.append(line)
                migrated += 1
            if migrated:
                lines = _chronological_lines(lines)
                _atomic_write(target, "\n".join(lines[-config.max_worklog_lines :]) + "\n")
            source.unlink()
            return migrated


def cleanup_stale_state(spec_dir: Path, *, config: QueueConfig = QueueConfig()) -> int:
    """Age-gated sweep of per-session state nothing will read again.

    Removes `session-*` fallback worklogs and `.recall-seen-*` dedupe files
    whose mtime is older than `cleanup_age_seconds` (same policy as drained
    queue dirs). Named-topic worklogs are never candidates: the `session-`
    prefix is reserved for per-session fallback buckets. Fallback worklog
    removal takes the same per-target lock as flush and re-checks the mtime
    under the lock; oldest files go first, bounded per pass.
    """
    spec_dir = spec_dir.resolve()
    now = time.time()

    def mtime_of(path: Path) -> float | None:
        try:
            return path.stat().st_mtime
        except OSError:
            return None

    stale: list[tuple[float, Path]] = []
    for pattern in STALE_STATE_GLOBS:
        for path in spec_dir.glob(pattern):
            mtime = mtime_of(path)
            if mtime is not None and now - mtime >= config.cleanup_age_seconds:
                stale.append((mtime, path))

    removed = 0
    for _, path in sorted(stale)[:MAX_STALE_REMOVALS_PER_PASS]:
        if path.name.endswith(".worklog.jsonl"):
            with _locked(_target_lock_path(spec_dir, path.name), blocking=False) as acquired:
                if not acquired:
                    continue
                mtime = mtime_of(path)
                if mtime is None or now - mtime < config.cleanup_age_seconds:
                    continue
                try:
                    path.unlink()
                except OSError:
                    continue
                removed += 1
        else:
            try:
                path.unlink()
            except OSError:
                continue
            removed += 1
    return removed


def cleanup_spec_dir(spec_dir: Path, *, config: QueueConfig = QueueConfig()) -> int:
    root = queue_root(spec_dir.resolve())
    if not root.is_dir():
        return 0
    now = time.time()
    removed = 0

    def age_key(path: Path) -> tuple[float, str]:
        try:
            return path.stat().st_mtime, path.name
        except OSError:
            return float("inf"), path.name

    queue_dirs = sorted((path for path in root.iterdir() if path.is_dir()), key=age_key)[:64]
    for queue_dir in queue_dirs:
        spec_dir = root.parent
        with _locked(_session_lifecycle_lock(spec_dir, queue_dir.name), blocking=False) as acquired:
            if not acquired:
                continue
            try:
                age = now - queue_dir.stat().st_mtime
            except OSError:
                continue
            if age < config.cleanup_age_seconds:
                continue
            with _locked(queue_dir / "enqueue.lock", blocking=False) as enqueue_idle:
                if not enqueue_idle:
                    continue
                with _locked(queue_dir / "flush.lock", blocking=False) as flush_idle:
                    if not flush_idle or _pending_state(queue_dir)[0]:
                        continue
                    for path in queue_dir.iterdir():
                        try:
                            path.unlink()
                        except OSError:
                            break
                    else:
                        queue_dir.rmdir()
                        removed += 1
    return removed


def _config_from_args(args: argparse.Namespace) -> QueueConfig:
    return QueueConfig(
        max_worklog_lines=args.max_lines,
        worker_idle_seconds=args.idle_seconds,
        worker_max_seconds=args.max_seconds,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("worker", "flush-session"):
        command = sub.add_parser(name)
        command.add_argument("--queue-dir", type=Path, required=True)
        command.add_argument("--max-lines", type=int, default=DEFAULT_MAX_WORKLOG_LINES)
        command.add_argument("--idle-seconds", type=float, default=DEFAULT_WORKER_IDLE_SECONDS)
        command.add_argument("--max-seconds", type=float, default=DEFAULT_WORKER_MAX_SECONDS)
    flush_all = sub.add_parser("flush-spec-dir")
    flush_all.add_argument("--spec-dir", type=Path, required=True)
    flush_all.add_argument("--max-lines", type=int, default=DEFAULT_MAX_WORKLOG_LINES)
    flush_all.add_argument("--idle-seconds", type=float, default=DEFAULT_WORKER_IDLE_SECONDS)
    flush_all.add_argument("--max-seconds", type=float, default=DEFAULT_WORKER_MAX_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = _config_from_args(args)
    if args.command == "worker":
        result = run_worker(args.queue_dir, config=config)
    elif args.command == "flush-session":
        result = flush_session(args.queue_dir, config=config)
    else:
        result = flush_spec_dir(args.spec_dir, config=config)
    if args.command != "worker":
        print(json.dumps(result.__dict__, sort_keys=True))
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
