from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from paths import _read_json, context, ensure_session, feedback_dir, lifecycle_lock, pollers_dir, sanitize_name


def feedback_path(name: str) -> Path:
    return feedback_dir() / f"{sanitize_name(name)}.jsonl"


def delivered_feedback_dir() -> Path:
    return feedback_dir() / "delivered"


def ended_path(name: str) -> Path:
    return feedback_dir() / f"{sanitize_name(name)}.ended"


def poller_path(name: str) -> Path:
    return pollers_dir() / f"{sanitize_name(name)}.json"


def process_is_running(pid: int) -> bool:
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def command_line_for_pid(pid: int) -> str | None:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
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


def process_started_at(pid: int) -> str | None:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def poll_artifact_from_command(command: str) -> str | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    script_index = None
    for index, token in enumerate(tokens):
        token_path = Path(token)
        if token_path.name in {",artifact", "executable_,artifact"} or (
            token_path.name == "main.py" and token_path.parent.name in {",artifact", "exact_,artifact"}
        ):
            script_index = index
            break
    if script_index is None:
        return None
    try:
        poll_index = tokens.index("poll", script_index + 1)
    except ValueError:
        return None
    name = "artifact"
    index = poll_index + 1
    while index < len(tokens):
        token = tokens[index]
        if token == "--timeout":
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        name = token
        break
    return sanitize_name(name)


def record_matches_live_poller(record: dict[str, Any]) -> bool:
    pid = record.get("pid")
    artifact = record.get("artifact")
    if not isinstance(pid, int) or not isinstance(artifact, str):
        return False
    started = record.get("process_started_at")
    if not isinstance(started, str) or not started or process_started_at(pid) != started:
        return False
    if not process_is_running(pid):
        return False
    command = command_line_for_pid(pid)
    return poll_artifact_from_command(command or "") == sanitize_name(artifact)


def poller_record_from(path: Path) -> dict[str, Any] | None:
    with lifecycle_lock():
        value = _read_json(path)
        if not value:
            return None
        if not record_matches_live_poller(value):
            if process_is_running(value.get("pid")):
                value["ownership"] = "unverified"
            else:
                path.unlink(missing_ok=True)
                return None
        value["path"] = str(path)
        return value


def active_poller_records(sdir: Path | None = None) -> list[dict[str, Any]]:
    with lifecycle_lock():
        records: list[dict[str, Any]] = []
        try:
            directory = sdir / "pollers" if sdir is not None else pollers_dir()
            paths = sorted(directory.glob("*.json"))
        except FileNotFoundError:
            return records
        for path in paths:
            record = poller_record_from(path)
            if record:
                records.append(record)
        return records


def active_poller_record(name: str) -> dict[str, Any] | None:
    return poller_record_from(poller_path(name))


def register_poller(name: str, timeout: float | None) -> None:
    with lifecycle_lock():
        existing = active_poller_record(name)
        if existing and existing.get("pid") != os.getpid():
            raise SystemExit(f"ERROR: poller already running for {sanitize_name(name)} (pid {existing['pid']})")
        pollers_dir().mkdir(parents=True, exist_ok=True)
        ctx = context()
        poller_path(name).write_text(
            json.dumps(
                {
                    "artifact": sanitize_name(name),
                    "pid": os.getpid(),
                    "process_started_at": process_started_at(os.getpid()),
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "timeout": timeout,
                    "session_dir": ctx["session_dir"],
                    "root": ctx["root"],
                    "workspace_key": ctx["workspace_key"],
                    "workspace_name": ctx["workspace_name"],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


def unregister_poller(name: str) -> None:
    with lifecycle_lock():
        path = poller_path(name)
        record = _read_json(path)
        if record and (
            record.get("pid") != os.getpid() or record.get("process_started_at") != process_started_at(os.getpid())
        ):
            return
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def stop_poller_record(record: dict[str, Any]) -> None:
    with lifecycle_lock():
        raw_path = record.get("path")
        path = Path(raw_path) if isinstance(raw_path, str) else None
        if path is not None:
            current = _read_json(path)
            if current is None or any(
                current.get(key) != record.get(key) for key in ("pid", "process_started_at", "artifact")
            ):
                return
        if record_matches_live_poller(record):
            try:
                os.kill(record["pid"], signal.SIGTERM)
            except ProcessLookupError:
                pass
        elif process_is_running(record.get("pid")):
            raise SystemExit(f"ERROR: cannot verify active poller PID {record['pid']}; metadata preserved")
        if path is not None:
            path.unlink(missing_ok=True)


def clear_ended(name: str) -> None:
    try:
        ended_path(name).unlink()
    except FileNotFoundError:
        pass


def archive_feedback_path(name: str) -> Path:
    delivered_feedback_dir().mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest = hashlib.sha256(f"{stamp}:{name}:{time.time_ns()}".encode()).hexdigest()[:8]
    return delivered_feedback_dir() / f"{sanitize_name(name)}.{stamp}.{digest}.jsonl"


@contextlib.contextmanager
def feedback_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def append_feedback(directory: Path, name: str, batch: dict[str, Any]) -> None:
    path = directory / f"{sanitize_name(name)}.jsonl"
    with feedback_lock(path):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(batch) + "\n")


def read_and_archive_feedback(name: str) -> tuple[list[dict[str, Any]], Path | None]:
    path = feedback_path(name)
    with feedback_lock(path):
        try:
            if path.stat().st_size == 0:
                path.unlink()
                return [], None
        except FileNotFoundError:
            return [], None
        archive = archive_feedback_path(name)
        path.replace(archive)
    lines = archive.read_text(encoding="utf-8").splitlines()
    prompts = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            prompts.append(value)
    return prompts, archive


FEEDBACK_ITEM_FIELDS = (
    "prompt",
    "selection",
    "selector",
    "text",
    "note",
    "url",
    "title",
    "artifact_id",
    "entity_id",
    "entity_kind",
    "entity_label",
    "entity_summary",
    "entity",
    "entity_ancestors",
    "relations",
    "role",
    "label",
    "rect",
    "ancestors",
    "source",
    "targets",
)


def feedback_item_from(raw_item: dict[str, Any]) -> dict[str, Any] | None:
    prompt = str(raw_item.get("prompt") or "").strip()
    if not prompt:
        return None
    item: dict[str, Any] = {"prompt": prompt}
    for field in FEEDBACK_ITEM_FIELDS:
        if field == "prompt" or field not in raw_item:
            continue
        value = raw_item.get(field)
        if field in {"entity", "entity_ancestors", "relations", "rect", "ancestors", "targets"}:
            if value:
                item[field] = value
        else:
            item[field] = str(value or "")
    return item


def flatten_feedback_batches(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    for record in records:
        items = record.get("items")
        if isinstance(items, list):
            batch_id = str(record.get("batch_id") or "")
            submitted_at = str(record.get("submitted_at") or "")
            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    continue
                normalized = feedback_item_from(item)
                if normalized is None:
                    continue
                normalized["batch_id"] = batch_id
                normalized["item_index"] = index
                normalized["submitted_at"] = submitted_at
                prompts.append(normalized)
        else:
            normalized = feedback_item_from(record)
            if normalized is not None:
                prompts.append(normalized)
    return prompts


def normalize_feedback_batch(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return None
    items: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        item = feedback_item_from(raw_item)
        if item is None:
            continue
        items.append(item)
    if not items:
        return None
    submitted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "batch_id": hashlib.sha256(f"{submitted_at}:{json.dumps(items, sort_keys=True)}".encode()).hexdigest()[:12],
        "submitted_at": submitted_at,
        "items": items,
    }


def poll_feedback(args: argparse.Namespace) -> None:
    ensure_session()
    name = sanitize_name(args.name)
    deadline = None if args.timeout is None else time.time() + args.timeout
    register_poller(name, args.timeout)
    print(f"[,artifact] waiting for feedback on {name}; leave this running.", file=sys.stderr)
    try:
        while True:
            prompts, archive = read_and_archive_feedback(name)
            if prompts:
                print(
                    json.dumps(
                        {
                            "status": "feedback",
                            "artifact": name,
                            "archive": str(archive) if archive else "",
                            "batches": prompts,
                            "prompts": flatten_feedback_batches(prompts),
                        },
                        indent=2,
                    )
                )
                return
            if ended_path(name).exists():
                print(json.dumps({"status": "ended", "artifact": name}, indent=2))
                return
            if deadline is not None and time.time() >= deadline:
                print(json.dumps({"status": "waiting", "artifact": name}, indent=2))
                return
            time.sleep(1)
    finally:
        unregister_poller(name)
