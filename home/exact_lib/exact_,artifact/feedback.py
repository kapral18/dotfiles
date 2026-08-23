from __future__ import annotations

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

from paths import _read_json, context, ensure_session, feedback_dir, pollers_dir, sanitize_name


def feedback_path(name: str) -> Path:
    return feedback_dir() / f"{sanitize_name(name)}.jsonl"


def delivered_feedback_dir() -> Path:
    return feedback_dir() / "delivered"


def ended_path(name: str) -> Path:
    return feedback_dir() / f"{sanitize_name(name)}.ended"


def poller_path(name: str) -> Path:
    return pollers_dir() / f"{sanitize_name(name)}.json"


def process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
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
    if not process_is_running(pid):
        return False
    command = command_line_for_pid(pid)
    return poll_artifact_from_command(command or "") == sanitize_name(artifact)


def poller_record_from(path: Path) -> dict[str, Any] | None:
    value = _read_json(path)
    if not value:
        return None
    if not record_matches_live_poller(value):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return None
    value["path"] = str(path)
    return value


def active_poller_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        paths = sorted(pollers_dir().glob("*.json"))
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
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "timeout": timeout,
                "session_dir": ctx["session_dir"],
                "root": ctx["root"],
                "tmux_key": ctx["tmux_key"],
                "tmux_name": ctx["tmux_name"],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def unregister_poller(name: str) -> None:
    path = poller_path(name)
    record = _read_json(path)
    if record and record.get("pid") not in {None, os.getpid()}:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def stop_poller_record(record: dict[str, Any]) -> None:
    if not record_matches_live_poller(record):
        path = record.get("path")
        if isinstance(path, str):
            try:
                Path(path).unlink()
            except FileNotFoundError:
                pass
        return
    pid = record.get("pid")
    if isinstance(pid, int):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    path = record.get("path")
    if isinstance(path, str):
        try:
            Path(path).unlink()
        except FileNotFoundError:
            pass


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


def read_and_archive_feedback(name: str) -> tuple[list[dict[str, Any]], Path | None]:
    path = feedback_path(name)
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
