#!/usr/bin/env python3
"""Repo-external proof ledger for freeform agent work."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "0.2.0"
APP = "agent-proof"
STATE_FILE = "proof.json"
EVIDENCE_DIR = "evidence"
REPORTS_DIR = "reports"
LOCK_FILE = ".lock"
SUPPORTED_EVIDENCE_TYPES = {
    "test",
    "build",
    "lint",
    "typecheck",
    "diff",
    "screenshot",
    "browser",
    "log",
    "file-read",
    "manual-user-confirmation",
}
COMMAND_LIKE_TYPES = {"test", "build", "lint", "typecheck"}
PROVENANCE_REQUIRED_TYPES = {"diff", "browser", "file-read"}
WEAK_TYPES = {"log", "manual-user-confirmation"}
REVIEW_VERDICTS = {"supports", "does-not-support", "unclear"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"}
TEXT_PREVIEW_BYTES = 8192
TEXT_PREVIEW_LINES = 40
EXECUTED_PROVENANCE = "executed"
ATTACHED_PROVENANCE = "attached"
PROVENANCE_VALUES = {EXECUTED_PROVENANCE, ATTACHED_PROVENANCE}
SEAL_FIELDS = ("criteria", "evidence", "reviews", "blockers")
SECRET_SCAN_BYTES = 1024 * 1024
SECRET_PATTERNS = (
    ("PEM_PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.I)),
    ("GITHUB_TOKEN", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("AWS_ACCESS_KEY_ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("SLACK_TOKEN", re.compile(r"xox[baprs]-")),
    (
        "GENERIC_SECRET_ASSIGNMENT",
        re.compile(r"(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}", re.I),
    ),
)


class SecretScanError(RuntimeError):
    def __init__(self, pattern_name: str) -> None:
        super().__init__(pattern_name)
        self.pattern_name = pattern_name


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_name(value: str | None, default: str = "current") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip(".-")
    return cleaned[:80] if cleaned else default


def state_root() -> Path:
    explicit = os.environ.get("AGENT_PROOF_HOME")
    if explicit:
        return Path(explicit).expanduser()
    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state).expanduser() / APP
    return Path.home() / ".local" / "state" / APP


def run_text(argv: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def workspace_root(workspace_arg: str | None) -> Path:
    start = Path(workspace_arg).expanduser() if workspace_arg else Path.cwd()
    start = start.resolve()
    git_root = run_text(["git", "rev-parse", "--show-toplevel"], start)
    return Path(git_root).resolve() if git_root else start


def active_topic() -> str:
    explicit = os.environ.get("AGENT_PROOF_TOPIC") or os.environ.get("PROOF_TOPIC")
    if explicit:
        return safe_name(explicit)
    return "current"


def context(args: argparse.Namespace) -> dict[str, str]:
    workspace = workspace_root(getattr(args, "workspace", None))
    topic = safe_name(getattr(args, "topic", None) or active_topic())
    workspace_hash = hashlib.sha256(str(workspace).encode()).hexdigest()[:16]
    proof_dir = state_root() / workspace_hash / topic
    if proof_dir.resolve().is_relative_to(workspace.resolve()) and workspace.resolve() != Path.home().resolve():
        raise SystemExit(
            "Proof state must stay outside the selected workspace. "
            "Set AGENT_PROOF_HOME or XDG_STATE_HOME to a repo-external directory."
        )
    return {
        "workspace": str(workspace),
        "workspace_hash": workspace_hash,
        "topic": topic,
        "proof_dir": str(proof_dir),
    }


def proof_file(proof_dir: Path) -> Path:
    return proof_dir / STATE_FILE


def require_state_file(ctx: dict[str, str]) -> None:
    path = proof_file(Path(ctx["proof_dir"]))
    if not path.exists():
        raise SystemExit(f"No proof ledger found. Run `,proof start` first: {path}")


def default_state(ctx: dict[str, str], goal: str = "") -> dict[str, Any]:
    now = utc_now()
    return {
        "version": VERSION,
        "workspace": ctx["workspace"],
        "workspace_hash": ctx["workspace_hash"],
        "topic": ctx["topic"],
        "goal": goal,
        "created_at": now,
        "updated_at": now,
        "criteria": [],
        "evidence": [],
        "reviews": [],
        "blockers": [],
        "reopen_history": [],
    }


@contextmanager
def proof_lock(ctx: dict[str, str], exclusive: bool = True) -> Any:
    proof_dir = Path(ctx["proof_dir"])
    proof_dir.mkdir(parents=True, exist_ok=True)
    lock_path = proof_dir / LOCK_FILE
    with lock_path.open("a", encoding="utf-8") as handle:
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(handle.fileno(), mode)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_state(ctx: dict[str, str], create: bool = True) -> dict[str, Any]:
    path = proof_file(Path(ctx["proof_dir"]))
    if not path.exists():
        if not create:
            raise SystemExit(f"No proof ledger found. Run `,proof start` first: {path}")
        state = default_state(ctx)
        save_state(ctx, state)
        return state
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid proof ledger JSON in {path}: {exc}") from exc
    for key, value in default_state(ctx).items():
        state.setdefault(key, value)
    backfill_provenance(state)
    return state


def load_state_read_only(ctx: dict[str, str], state_file: Path) -> dict[str, Any]:
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid proof ledger JSON in {state_file}: {exc}") from exc
    normalized = copy.deepcopy(state)
    for key, value in default_state(ctx).items():
        normalized.setdefault(key, value)
    backfill_provenance(normalized)
    return normalized


def save_state(ctx: dict[str, str], state: dict[str, Any]) -> None:
    proof_dir = Path(ctx["proof_dir"])
    proof_dir.mkdir(parents=True, exist_ok=True)
    (proof_dir / EVIDENCE_DIR).mkdir(exist_ok=True)
    (proof_dir / REPORTS_DIR).mkdir(exist_ok=True)
    state["updated_at"] = utc_now()
    content = json.dumps(state, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=proof_dir, prefix=".proof.", delete=False) as handle:
        handle.write(content)
        tmp_path = Path(handle.name)
    os.replace(tmp_path, proof_file(proof_dir))


def evidence_provenance(args: argparse.Namespace) -> str:
    cli_executed = (
        args.type in COMMAND_LIKE_TYPES and args.command and args.exit_code is None and not args.artifact_path
    )
    return EXECUTED_PROVENANCE if cli_executed else ATTACHED_PROVENANCE


def legacy_provenance(record: dict[str, Any]) -> str:
    return EXECUTED_PROVENANCE if record.get("type") in COMMAND_LIKE_TYPES else ATTACHED_PROVENANCE


def backfill_provenance(state: dict[str, Any]) -> None:
    for record in state.get("evidence", []):
        if record.get("provenance") not in PROVENANCE_VALUES:
            record["provenance"] = legacy_provenance(record)


def canonical_ledger_json(state: dict[str, Any]) -> str:
    payload = {field: state.get(field, []) for field in SEAL_FIELDS}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def compute_seal(state: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_ledger_json(state).encode("utf-8")).hexdigest()


def finalized(state: dict[str, Any]) -> bool:
    return bool(state.get("finalized_at") or state.get("seal"))


def seal_issue(state: dict[str, Any]) -> str | None:
    if not finalized(state):
        return None
    stored = str(state.get("seal") or "")
    if not stored:
        return "seal broken: finalized ledger is missing a seal"
    if stored != compute_seal(state):
        return "seal broken: ledger contents do not match the stored seal"
    return None


def seal_status(state: dict[str, Any]) -> str:
    if not finalized(state):
        return "not finalized"
    return "seal broken" if seal_issue(state) else "ok"


def refuse_finalized() -> int:
    print("Proof ledger is finalized; run `,proof reopen` before mutating it.", file=sys.stderr)
    return 2


def next_id(prefix: str, items: list[dict[str, Any]]) -> str:
    highest = 0
    for item in items:
        value = str(item.get("id", ""))
        if not value.startswith(prefix + "-"):
            continue
        try:
            highest = max(highest, int(value.split("-", 1)[1]))
        except ValueError:
            continue
    return f"{prefix}-{highest + 1:03d}"


def criterion_by_id(state: dict[str, Any], criterion_id: str) -> dict[str, Any] | None:
    for item in state.get("criteria", []):
        if str(item.get("id")) == criterion_id:
            return item
    return None


def evidence_by_id(state: dict[str, Any], evidence_id: str) -> dict[str, Any] | None:
    for record in state.get("evidence", []):
        if str(record.get("id")) == evidence_id:
            return record
    return None


def blocker_by_id(state: dict[str, Any], blocker_id: str) -> dict[str, Any] | None:
    for blocker in state.get("blockers", []):
        if str(blocker.get("id")) == blocker_id:
            return blocker
    return None


def artifact_path(ctx: dict[str, str], record: dict[str, Any]) -> Path | None:
    raw = record.get("artifact_path")
    if not raw:
        return None
    return Path(ctx["proof_dir"]) / str(raw)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def secret_pattern_name(text: str) -> str | None:
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return name
    return None


def scan_text_for_secrets(text: str | None) -> str | None:
    if not text:
        return None
    return secret_pattern_name(text)


def scannable_file_text(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            data = handle.read(SECRET_SCAN_BYTES + 1)
    except OSError:
        return None
    if b"\x00" in data:
        return None
    scan = data[:SECRET_SCAN_BYTES]
    try:
        return scan.decode("utf-8")
    except UnicodeDecodeError as err:
        # Tolerate only a multibyte character split by the scan bound: without
        # this, a >1 MiB UTF-8 artifact whose bound lands mid-character would
        # skip scanning entirely. Anything else is genuinely non-UTF-8 text
        # and stays unscannable.
        if len(data) > SECRET_SCAN_BYTES and err.start >= SECRET_SCAN_BYTES - 3:
            try:
                return scan[: err.start].decode("utf-8")
            except UnicodeDecodeError:
                return None
        return None


def scan_artifact_for_secrets(path: Path) -> str | None:
    return scan_text_for_secrets(scannable_file_text(path))


def secret_scan_failed(pattern_name: str, allow_secrets: bool) -> bool:
    if allow_secrets:
        print(f"Warning: allowing secret-like content matching {pattern_name}.", file=sys.stderr)
        return False
    print(f"Secret-like content refused: {pattern_name}. Pass --allow-secrets to override.", file=sys.stderr)
    return True


def artifact_metadata(path: Path) -> dict[str, Any]:
    mime_type, _encoding = mimetypes.guess_type(str(path))
    return {
        "artifact_sha256": file_sha256(path),
        "artifact_size": path.stat().st_size,
        "artifact_mime_type": mime_type or "application/octet-stream",
        "artifact_captured_at": utc_now(),
    }


def artifact_status(ctx: dict[str, str], record: dict[str, Any]) -> str:
    path = artifact_path(ctx, record)
    if not path:
        return "has no artifact_path"
    if not path.exists():
        return f"artifact is missing: {record.get('artifact_path')}"
    if not path.is_file():
        return f"artifact is not a file: {record.get('artifact_path')}"
    expected_size = record.get("artifact_size")
    expected_hash = record.get("artifact_sha256")
    if expected_size is None or not expected_hash:
        return "legacy unverified: missing artifact hash/size metadata"
    if int(expected_size) != path.stat().st_size:
        return f"tampered: artifact size changed from {expected_size} to {path.stat().st_size}"
    if str(expected_hash) != file_sha256(path):
        return "tampered: artifact hash mismatch"
    return "ok"


def image_like(path: Path) -> bool:
    try:
        header = path.read_bytes()[:4096]
    except OSError:
        return False
    trimmed = header.lstrip()
    return any(
        [
            header.startswith(b"\x89PNG\r\n\x1a\n"),
            header.startswith(b"\xff\xd8\xff"),
            header.startswith(b"GIF87a"),
            header.startswith(b"GIF89a"),
            header.startswith(b"RIFF") and header[8:12] == b"WEBP",
            header.startswith(b"BM"),
            header.startswith(b"II*\x00"),
            header.startswith(b"MM\x00*"),
            re.match(rb"(?:<\?xml[^>]*>\s*)?(?:<!--.*?-->\s*)*<svg(?:\s|>)", trimmed, re.I | re.S) is not None,
        ]
    )


def evidence_strength(evidence_type: str | None) -> str:
    return "weak" if evidence_type in WEAK_TYPES else "strong"


def input_policy_issue(evidence_type: str, has_command: bool, has_artifact: bool) -> str | None:
    if evidence_type in COMMAND_LIKE_TYPES and not has_command:
        return f"{evidence_type} evidence requires command provenance. Pass --command."
    if evidence_type == "screenshot" and not has_artifact:
        return "screenshot evidence requires --artifact-path with an image artifact."
    if evidence_type in PROVENANCE_REQUIRED_TYPES and not has_command and not has_artifact:
        return f"{evidence_type} evidence requires --command output or --artifact-path."
    return None


def run_evidence_command(command: str, artifact: Path, cwd: Path, allow_secrets: bool = False) -> int:
    started = utc_now()
    result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, check=False)
    ended = utc_now()
    content = [
        f"$ {command}",
        f"started_at: {started}",
        f"finished_at: {ended}",
        f"exit_code: {result.returncode}",
        "",
        "## stdout",
        result.stdout,
        "",
        "## stderr",
        result.stderr,
    ]
    text = "\n".join(content)
    secret = scan_text_for_secrets(text)
    if secret and allow_secrets:
        secret_scan_failed(secret, allow_secrets)
    elif secret:
        raise SecretScanError(secret)
    artifact.write_text(text, encoding="utf-8")
    return int(result.returncode)


def safe_artifact_name(evidence_id: str, source: Path) -> str:
    cleaned = "".join(char if char.isalnum() or char in ".-_" else "-" for char in source.name)
    return f"{evidence_id}-{cleaned.strip('.') or 'artifact'}"


def prepare_artifact(ctx: dict[str, str], evidence_id: str, source_arg: str | None) -> tuple[Path, str, str | None]:
    evidence_dir = Path(ctx["proof_dir"]) / EVIDENCE_DIR
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if not source_arg:
        path = evidence_dir / f"{evidence_id}.log"
        return path, str(path.relative_to(ctx["proof_dir"])), None
    source = Path(source_arg).expanduser()
    if not source.is_absolute():
        source = Path(ctx["workspace"]) / source
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if not source.is_file():
        raise IsADirectoryError(source)
    destination = evidence_dir / safe_artifact_name(evidence_id, source)
    if source != destination.resolve():
        shutil.copy2(source, destination)
    return destination, str(destination.relative_to(ctx["proof_dir"])), source_display(ctx, source)


def source_display(ctx: dict[str, str], source: Path) -> str:
    workspace = Path(ctx["workspace"])
    try:
        return str(source.relative_to(workspace))
    except ValueError:
        return f"<external>/{source.name}"


def review_artifact_metadata(ctx: dict[str, str], record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    status = artifact_status(ctx, record)
    if status != "ok":
        return None, status
    path = artifact_path(ctx, record)
    assert path is not None
    return {
        "artifact_path": record.get("artifact_path"),
        "artifact_sha256": file_sha256(path),
        "artifact_size": path.stat().st_size,
    }, None


def latest_review(state: dict[str, Any], criterion_id: str, evidence_id: str) -> dict[str, Any] | None:
    for review in reversed(state.get("reviews", [])):
        if str(review.get("criterion_id")) == criterion_id and str(review.get("evidence_id")) == evidence_id:
            return review
    return None


def review_issue(ctx: dict[str, str], state: dict[str, Any], criterion_id: str, record: dict[str, Any]) -> str | None:
    review = latest_review(state, criterion_id, str(record.get("id")))
    if not review:
        return "has not been reviewed against the criterion"
    if not str(review.get("notes") or "").strip():
        return f"latest review {review.get('id')} is missing notes"
    if review.get("verdict") != "supports":
        return f"latest review {review.get('id')} verdict is {review.get('verdict')}; only supports satisfies the gate"
    status = artifact_status(ctx, record)
    if status != "ok":
        return f"latest review {review.get('id')} artifact integrity failed: {status}"
    if review.get("artifact_sha256") != record.get("artifact_sha256"):
        return f"latest review {review.get('id')} artifact hash no longer matches evidence"
    if int(review.get("artifact_size", -1)) != int(record.get("artifact_size", -2)):
        return f"latest review {review.get('id')} artifact size no longer matches evidence"
    return None


def evidence_issues(ctx: dict[str, str], record: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    evidence_type = record.get("type")
    if evidence_type not in SUPPORTED_EVIDENCE_TYPES:
        return [f"unsupported evidence type: {evidence_type}"]
    if record.get("strength") != evidence_strength(evidence_type):
        issues.append(f"strength metadata mismatch: expected {evidence_strength(evidence_type)}")
    if evidence_type in COMMAND_LIKE_TYPES and not record.get("command"):
        issues.append(f"type {evidence_type} requires command provenance")
    if record.get("command") and record.get("exit_code") not in (0, "0"):
        issues.append(f"command failed with exit code {record.get('exit_code')}")
    status = artifact_status(ctx, record)
    if status != "ok":
        issues.append(status)
    path = artifact_path(ctx, record)
    if evidence_type == "screenshot" and path and path.exists() and not image_like(path):
        issues.append("type screenshot requires an image artifact")
    return issues


def evaluate(ctx: dict[str, str], state: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    passing = 0
    criteria = state.get("criteria", [])
    by_id = {str(record.get("id")): record for record in state.get("evidence", [])}
    current_seal_issue = seal_issue(state)
    if current_seal_issue:
        issues.append(current_seal_issue)
    if not criteria:
        issues.append("No criteria are defined.")
    for item in criteria:
        item_issues = criterion_issues(ctx, state, item, by_id)
        if item_issues:
            item["status"] = "pending"
            issues.extend(item_issues)
        else:
            item["status"] = "passed"
            passing += 1
    for blocker in state.get("blockers", []):
        if not blocker.get("resolved"):
            issues.append(f"Unresolved blocker {blocker.get('id')}: {blocker.get('description')}")
    return {
        "allowed": not issues and bool(criteria),
        "verdict": "PROOF RECORDED"
        if not issues and criteria
        else ("PARTIALLY RECORDED" if passing else "NOT RECORDED"),
        "issues": issues,
        "passing_criteria": passing,
        "total_criteria": len(criteria),
        "criteria": criteria,
        "blockers": [b for b in state.get("blockers", []) if not b.get("resolved")],
    }


def criterion_issues(
    ctx: dict[str, str],
    state: dict[str, Any],
    criterion: dict[str, Any],
    evidence_records: dict[str, dict[str, Any]],
) -> list[str]:
    criterion_id = str(criterion.get("id", "<missing-id>"))
    issues: list[str] = []
    records = []
    for evidence_id in criterion.get("evidence", []):
        record = evidence_records.get(str(evidence_id))
        if not record:
            issues.append(f"{criterion_id} references unknown evidence: {evidence_id}.")
            continue
        if str(record.get("criterion_id")) != criterion_id:
            issues.append(f"{criterion_id} references evidence {evidence_id} owned by {record.get('criterion_id')}.")
            continue
        records.append(record)
    for record in records:
        evidence_id = record.get("id")
        issues.extend(f"{criterion_id} evidence {evidence_id} {issue}." for issue in evidence_issues(ctx, record))
        review = review_issue(ctx, state, criterion_id, record)
        if review:
            issues.append(f"{criterion_id} evidence {evidence_id} {review}.")
    for required in criterion.get("evidence_required", []):
        if not any(record_satisfies(ctx, state, criterion_id, record, required) for record in records):
            issues.append(f"{criterion_id} is missing required evidence type: {required}.")
    return issues


def record_satisfies(
    ctx: dict[str, str],
    state: dict[str, Any],
    criterion_id: str,
    record: dict[str, Any],
    required: str,
) -> bool:
    return (
        record.get("type") == required
        and not evidence_issues(ctx, record)
        and review_issue(ctx, state, criterion_id, record) is None
    )


def evidence_records_for_criterion(state: dict[str, Any], criterion: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {str(record.get("id")): record for record in state.get("evidence", [])}
    records = []
    for evidence_id in criterion.get("evidence", []):
        record = by_id.get(str(evidence_id))
        if record:
            records.append(record)
    return records


def provenance_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {EXECUTED_PROVENANCE: 0, ATTACHED_PROVENANCE: 0}
    for record in records:
        provenance = record.get("provenance")
        if provenance not in PROVENANCE_VALUES:
            provenance = legacy_provenance(record)
        counts[str(provenance)] += 1
    return counts


def criterion_provenance_counts(state: dict[str, Any], criterion: dict[str, Any]) -> dict[str, int]:
    return provenance_counts(evidence_records_for_criterion(state, criterion))


def format_provenance_counts(counts: dict[str, int]) -> str:
    return f"{counts[EXECUTED_PROVENANCE]} executed / {counts[ATTACHED_PROVENANCE]} attached"


def command_start(args: argparse.Namespace) -> int:
    ctx = context(args)
    goal = " ".join(args.goal).strip()
    path = proof_file(Path(ctx["proof_dir"]))
    with proof_lock(ctx):
        if path.exists():
            state = load_state(ctx)
            if finalized(state):
                return refuse_finalized()
            if not args.force:
                existing_goal = str(state.get("goal") or "").strip()
                if goal and existing_goal and goal != existing_goal:
                    print(
                        f"Proof topic {ctx['topic']!r} already belongs to a different goal.\n"
                        f"Existing goal: {existing_goal}\n"
                        f"Requested goal: {goal}\n"
                        "Use a new --topic, or pass --force only when intentionally replacing this ledger.",
                        file=sys.stderr,
                    )
                    return 2
                if goal and not existing_goal:
                    state["goal"] = goal
                    save_state(ctx, state)
                print(f"Proof ledger already exists: {path}")
                return 0
            for managed_dir in (EVIDENCE_DIR, REPORTS_DIR):
                managed_path = Path(ctx["proof_dir"]) / managed_dir
                if managed_path.exists():
                    shutil.rmtree(managed_path)
        state = default_state(ctx, goal=goal)
        save_state(ctx, state)
    print(f"Proof ledger: {path}")
    return 0


def command_path(args: argparse.Namespace) -> int:
    ctx = context(args)
    print(ctx["proof_dir"])
    return 0


def command_add_criterion(args: argparse.Namespace) -> int:
    ctx = context(args)
    require_state_file(ctx)
    with proof_lock(ctx):
        state = load_state(ctx, create=False)
        if finalized(state):
            return refuse_finalized()
        description = " ".join(args.description).strip()
        if not description:
            print("Criterion description is required.", file=sys.stderr)
            return 2
        required = [item.strip() for value in args.requires for item in value.split(",") if item.strip()]
        if not required:
            print(
                "At least one --requires evidence type is required (options: "
                f"{', '.join(sorted(SUPPORTED_EVIDENCE_TYPES))}).",
                file=sys.stderr,
            )
            return 2
        invalid = sorted(set(required) - SUPPORTED_EVIDENCE_TYPES)
        if invalid:
            print(f"Unsupported evidence type(s): {', '.join(invalid)}", file=sys.stderr)
            return 2
        criterion_id = args.id or next_id("AC", state.get("criteria", []))
        if criterion_by_id(state, criterion_id):
            print(f"Criterion already exists: {criterion_id}", file=sys.stderr)
            return 2
        state.setdefault("criteria", []).append(
            {
                "id": criterion_id,
                "description": description,
                "evidence_required": required,
                "evidence": [],
                "status": "pending",
            }
        )
        save_state(ctx, state)
    print(f"Added criterion {criterion_id}")
    return 0


def evidence_request_issue(state: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any] | None, str | None]:
    criterion = criterion_by_id(state, args.criterion)
    if not criterion:
        return None, f"Unknown criterion: {args.criterion}"
    if args.type not in SUPPORTED_EVIDENCE_TYPES:
        return None, f"Unsupported evidence type: {args.type}"
    policy_issue = input_policy_issue(args.type, bool(args.command), bool(args.artifact_path))
    if policy_issue:
        return None, policy_issue
    if args.command and args.artifact_path and args.exit_code is None:
        return None, "Externally captured command evidence requires --exit-code."
    if args.command and args.exit_code is not None and not args.artifact_path:
        return None, "Externally captured command evidence requires --artifact-path."
    return criterion, None


def command_add_evidence(args: argparse.Namespace) -> int:
    ctx = context(args)
    require_state_file(ctx)
    with proof_lock(ctx):
        state = load_state(ctx, create=False)
        if finalized(state):
            return refuse_finalized()
        criterion, issue = evidence_request_issue(state, args)
        if issue:
            print(issue, file=sys.stderr)
            return 2
        assert criterion is not None
        summary_secret = scan_text_for_secrets(args.summary)
        if summary_secret and secret_scan_failed(summary_secret, args.allow_secrets):
            return 2
        evidence_id = next_id("EV", state.get("evidence", []))
        try:
            artifact, artifact_rel, source = prepare_artifact(ctx, evidence_id, args.artifact_path)
        except (FileNotFoundError, IsADirectoryError) as exc:
            print(f"Invalid artifact path: {exc}", file=sys.stderr)
            return 2
        try:
            exit_code = capture_evidence_artifact(ctx, args, artifact)
        except SecretScanError as exc:
            artifact.unlink(missing_ok=True)
            print(
                f"Secret-like content refused: {exc.pattern_name}. Pass --allow-secrets to override.",
                file=sys.stderr,
            )
            return 2
        artifact_secret = scan_artifact_for_secrets(artifact) if args.artifact_path else None
        if artifact_secret and secret_scan_failed(artifact_secret, args.allow_secrets):
            artifact.unlink(missing_ok=True)
            return 2
        if args.type == "screenshot" and not image_like(artifact):
            artifact.unlink(missing_ok=True)
            print("screenshot evidence requires a real image artifact.", file=sys.stderr)
            return 2
        record = evidence_record(args, evidence_id, artifact_rel, source, exit_code)
        record.update(artifact_metadata(artifact))
        state.setdefault("evidence", []).append(record)
        criterion.setdefault("evidence", []).append(evidence_id)
        evaluation = evaluate(ctx, state)
        save_state(ctx, state)
    print(f"Added evidence {evidence_id} for {args.criterion}: {artifact_rel}")
    if args.command:
        print(f"Command exit code: {exit_code}")
    return 0 if exit_code in (0, None) and not evaluation.get("internal_error") else 1


def capture_evidence_artifact(ctx: dict[str, str], args: argparse.Namespace, artifact: Path) -> int | None:
    if args.command and args.exit_code is None and not args.artifact_path:
        return run_evidence_command(args.command, artifact, Path(ctx["workspace"]), args.allow_secrets)
    if not args.command and not args.artifact_path:
        artifact.write_text(args.summary or "Weak evidence recorded.\n", encoding="utf-8")
    return args.exit_code


def evidence_record(
    args: argparse.Namespace,
    evidence_id: str,
    artifact_rel: str,
    source: str | None,
    exit_code: int | None,
) -> dict[str, Any]:
    record = {
        "id": evidence_id,
        "criterion_id": args.criterion,
        "type": args.type,
        "strength": evidence_strength(args.type),
        "command": args.command,
        "exit_code": exit_code,
        "provenance": evidence_provenance(args),
        "artifact_path": artifact_rel,
        "summary": args.summary or evidence_summary(args.type, args.command, exit_code),
        "created_at": utc_now(),
    }
    if source:
        record["source_path"] = source
    return record


def evidence_summary(evidence_type: str, command: str | None, exit_code: int | None) -> str:
    if command:
        return f"{evidence_type} command exited {exit_code}"
    if evidence_type in WEAK_TYPES:
        return f"{evidence_type} recorded as weak evidence"
    return f"{evidence_type} artifact recorded"


def command_review(args: argparse.Namespace) -> int:
    ctx = context(args)
    require_state_file(ctx)
    with proof_lock(ctx):
        state = load_state(ctx, create=False)
        if finalized(state):
            return refuse_finalized()
        criterion = criterion_by_id(state, args.criterion)
        record = evidence_by_id(state, args.evidence)
        notes = str(args.notes or "").strip()
        if not notes:
            print("Review notes are required.", file=sys.stderr)
            return 2
        if not criterion:
            print(f"Unknown criterion: {args.criterion}", file=sys.stderr)
            return 2
        if not record:
            print(f"Unknown evidence: {args.evidence}", file=sys.stderr)
            return 2
        if str(record.get("criterion_id")) != args.criterion:
            print(
                f"Evidence {args.evidence} belongs to {record.get('criterion_id')}, not {args.criterion}.",
                file=sys.stderr,
            )
            return 2
        if args.evidence not in [str(item) for item in criterion.get("evidence", [])]:
            print(f"Evidence {args.evidence} is not attached to {args.criterion}.", file=sys.stderr)
            return 2
        metadata, issue = review_artifact_metadata(ctx, record)
        if issue:
            print(f"Cannot review evidence {args.evidence}: {issue}.", file=sys.stderr)
            return 2
        review_id = next_id("RV", state.get("reviews", []))
        review = {
            "id": review_id,
            "criterion_id": args.criterion,
            "evidence_id": args.evidence,
            "verdict": args.verdict,
            "notes": notes,
            "reviewed_at": utc_now(),
            "reviewer": args.reviewer or os.environ.get("USER") or "unknown",
        }
        assert metadata is not None
        review.update(metadata)
        state.setdefault("reviews", []).append(review)
        evaluate(ctx, state)
        save_state(ctx, state)
    print(f"Recorded review {review_id} for {args.criterion} / {args.evidence}: {args.verdict}")
    return 0


def command_block(args: argparse.Namespace) -> int:
    ctx = context(args)
    require_state_file(ctx)
    with proof_lock(ctx):
        state = load_state(ctx, create=False)
        if finalized(state):
            return refuse_finalized()
        description = " ".join(args.description).strip()
        if not description:
            print("Blocker description is required.", file=sys.stderr)
            return 2
        blocker_id = next_id("B", state.get("blockers", []))
        state.setdefault("blockers", []).append(
            {"id": blocker_id, "description": description, "resolved": False, "created_at": utc_now()}
        )
        save_state(ctx, state)
    print(f"Recorded blocker {blocker_id}")
    return 0


def command_resolve_blocker(args: argparse.Namespace) -> int:
    ctx = context(args)
    require_state_file(ctx)
    with proof_lock(ctx):
        state = load_state(ctx, create=False)
        if finalized(state):
            return refuse_finalized()
        blocker = blocker_by_id(state, args.blocker_id)
        if not blocker:
            print(f"Unknown blocker: {args.blocker_id}", file=sys.stderr)
            return 2
        blocker["resolved"] = True
        blocker["resolved_at"] = utc_now()
        save_state(ctx, state)
    print(f"Resolved blocker {args.blocker_id}")
    return 0


def command_finalize(args: argparse.Namespace) -> int:
    ctx = context(args)
    require_state_file(ctx)
    with proof_lock(ctx):
        state = load_state(ctx, create=False)
        if finalized(state):
            issue = seal_issue(state)
            if issue:
                print(f"Cannot finalize: {issue}.", file=sys.stderr)
                return 1
            print(f"Proof ledger already finalized: {state.get('seal')}")
            return 0
        evaluation = evaluate(ctx, state)
        if not evaluation["allowed"] and not args.allow_failing:
            print("Cannot finalize: proof check fails. Pass --allow-failing to seal anyway.", file=sys.stderr)
            for issue in evaluation["issues"]:
                print(f"- {issue}", file=sys.stderr)
            return 1
        state["finalized_at"] = utc_now()
        state["seal"] = compute_seal(state)
        save_state(ctx, state)
    print(f"Finalized proof ledger: {state['seal']}")
    return 0


def command_reopen(args: argparse.Namespace) -> int:
    ctx = context(args)
    require_state_file(ctx)
    with proof_lock(ctx):
        state = load_state(ctx, create=False)
        previous_seal = state.get("seal")
        if not finalized(state):
            print("Proof ledger is not finalized.", file=sys.stderr)
            return 2
        state.pop("finalized_at", None)
        state.pop("seal", None)
        state.setdefault("reopen_history", []).append({"reopened_at": utc_now(), "previous_seal": previous_seal})
        save_state(ctx, state)
    print("Reopened proof ledger.")
    return 0


def prune_candidates(root: Path, older_than_days: int) -> list[Path]:
    cutoff = datetime.now(timezone.utc).timestamp() - older_than_days * 86400
    candidates = []
    if not root.exists():
        return candidates
    for state_file in sorted(root.glob("*/*/" + STATE_FILE)):
        if state_file.stat().st_mtime < cutoff:
            candidates.append(state_file.parent)
    return candidates


def command_prune(args: argparse.Namespace) -> int:
    if args.older_than < 1:
        print("--older-than must be at least 1 day.", file=sys.stderr)
        return 2
    root = state_root()
    candidates = prune_candidates(root, args.older_than)
    action = "Would remove" if args.dry_run else "Removed"
    for topic_dir in candidates:
        if not args.dry_run:
            shutil.rmtree(topic_dir)
        print(f"{action}: {topic_dir}")
    if not candidates:
        print("No proof ledgers matched.")
    return 0


def list_state_files(args: argparse.Namespace) -> list[Path]:
    root = state_root()
    if args.all_workspaces:
        return sorted(root.glob("*/*/" + STATE_FILE)) if root.exists() else []
    ctx = context(args)
    workspace_dir = root / ctx["workspace_hash"]
    return sorted(workspace_dir.glob("*/" + STATE_FILE)) if workspace_dir.exists() else []


def list_context(state_file: Path, state: dict[str, Any]) -> dict[str, str]:
    workspace_hash = state_file.parent.parent.name
    topic = state_file.parent.name
    workspace = str(state.get("workspace") or "")
    return {
        "workspace": workspace,
        "workspace_hash": workspace_hash,
        "topic": str(state.get("topic") or topic),
        "proof_dir": str(state_file.parent),
    }


def truncated_text(value: Any, limit: int = 80) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def list_seal_status(state: dict[str, Any]) -> str | None:
    if not finalized(state):
        return None
    return "broken" if seal_issue(state) else "ok"


def ledger_row(state_file: Path) -> dict[str, Any]:
    try:
        raw_state = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid proof ledger JSON in {state_file}: {exc}") from exc
    ctx = list_context(state_file, raw_state)
    state = load_state_read_only(ctx, state_file)
    evaluation = evaluate(ctx, state)
    stat = state_file.stat()
    is_finalized = finalized(state)
    return {
        "workspace_hash": ctx["workspace_hash"],
        "workspace": ctx["workspace"] if ctx["workspace"] and Path(ctx["workspace"]).exists() else None,
        "topic": ctx["topic"],
        "goal": truncated_text(state.get("goal")),
        "criteria": f"{evaluation['passing_criteria']}/{evaluation['total_criteria']}",
        "finalized": is_finalized,
        "seal": state.get("seal") if is_finalized else None,
        "seal_status": list_seal_status(state),
        "blockers": len(evaluation["blockers"]),
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat(),
    }


def print_ledger_rows(rows: list[dict[str, Any]], all_workspaces: bool) -> None:
    if not rows:
        print("No proof ledgers found.")
        return
    headers = ["TOPIC", "CRITERIA", "FINALIZED", "SEAL", "BLOCKERS", "MTIME", "GOAL"]
    if all_workspaces:
        headers.insert(0, "WORKSPACE_HASH")
    print("\t".join(headers))
    for row in rows:
        values = [
            str(row["topic"]),
            str(row["criteria"]),
            "yes" if row["finalized"] else "no",
            str(row["seal_status"] or ""),
            str(row["blockers"]),
            str(row["mtime"]),
            str(row["goal"]),
        ]
        if all_workspaces:
            values.insert(0, str(row["workspace_hash"]))
        print("\t".join(values))


def command_list(args: argparse.Namespace) -> int:
    rows = [ledger_row(state_file) for state_file in list_state_files(args)]
    if args.json:
        json.dump(rows, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print_ledger_rows(rows, args.all_workspaces)
    return 0


def command_status(args: argparse.Namespace) -> int:
    ctx = context(args)
    state = load_state(ctx, create=False)
    evaluation = evaluate(ctx, state)
    if args.json:
        json.dump(status_payload(ctx, state, evaluation), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    print(f"Goal: {state.get('goal') or '(not set)'}")
    print(f"Topic: {ctx['topic']}")
    print(f"Proof dir: {ctx['proof_dir']}")
    print(f"Criteria: {evaluation['passing_criteria']}/{evaluation['total_criteria']} passing")
    print(f"Completion allowed: {'yes' if evaluation['allowed'] else 'no'}")
    print(f"Finalized: {state.get('finalized_at') or 'no'}")
    print(f"Seal: {seal_status(state)}")
    for criterion in evaluation["criteria"]:
        counts = criterion_provenance_counts(state, criterion)
        print(f"- {criterion.get('id')}: {format_provenance_counts(counts)}")
    if args.verbose:
        for issue in evaluation["issues"]:
            print(f"- {issue}")
    return 0


def command_check(args: argparse.Namespace) -> int:
    ctx = context(args)
    state = load_state(ctx, create=False)
    evaluation = evaluate(ctx, state)
    if args.json:
        json.dump(status_payload(ctx, state, evaluation), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    elif evaluation["allowed"]:
        print("PASS")
        print("Evidence gate passes: every criterion has reviewed current evidence.")
        if finalized(state):
            print("Receipt sealed: yes")
        else:
            print("Receipt sealed: no (run `,proof finalize` before handoff)")
    else:
        print("FAIL")
        for issue in evaluation["issues"]:
            print(f"- {issue}")
        print("Completion allowed: no")
    return 0 if evaluation["allowed"] else 1


def status_payload(ctx: dict[str, str], state: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    return {
        "allowed": evaluation["allowed"],
        "verdict": evaluation["verdict"],
        "goal": state.get("goal", ""),
        "workspace": ctx["workspace"],
        "topic": ctx["topic"],
        "proof_dir": ctx["proof_dir"],
        "passing_criteria": evaluation["passing_criteria"],
        "total_criteria": evaluation["total_criteria"],
        "finalized_at": state.get("finalized_at"),
        "seal": state.get("seal"),
        "seal_status": seal_status(state),
        "issues": evaluation["issues"],
        "blockers": evaluation["blockers"],
        "criteria": [
            {
                "id": item.get("id"),
                "status": item.get("status"),
                "description": item.get("description"),
                "evidence_required": item.get("evidence_required", []),
                "evidence": item.get("evidence", []),
                "provenance": criterion_provenance_counts(state, item),
            }
            for item in evaluation["criteria"]
        ],
    }


def command_report(args: argparse.Namespace) -> int:
    ctx = context(args)
    state = load_state(ctx, create=False)
    if not finalized(state):
        print("Cannot report: proof ledger is not finalized. Run `,proof finalize` first.", file=sys.stderr)
        return 1
    issue = seal_issue(state)
    if issue:
        print(f"Cannot report: {issue}.", file=sys.stderr)
        return 1
    evaluation = evaluate(ctx, state)
    report_path = (
        Path(ctx["proof_dir"]) / REPORTS_DIR / f"report-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_content(ctx, state, evaluation), encoding="utf-8")
    print(report_path)
    print(f"Final verdict: {evaluation['verdict']}")
    return 0


def report_content(ctx: dict[str, str], state: dict[str, Any], evaluation: dict[str, Any]) -> str:
    rows = []
    for criterion in state.get("criteria", []):
        rows.append(
            [
                criterion.get("id", ""),
                criterion.get("description", ""),
                criterion.get("status", ""),
                ", ".join(criterion.get("evidence_required", [])),
                ", ".join(criterion.get("evidence", [])),
                format_provenance_counts(criterion_provenance_counts(state, criterion)),
            ]
        )
    evidence_rows = [
        [
            record.get("id", ""),
            record.get("criterion_id", ""),
            record.get("type", ""),
            record.get("strength", ""),
            record.get("provenance", legacy_provenance(record)),
            str(record.get("exit_code", "")),
            record.get("artifact_path", ""),
            str(record.get("artifact_size", "")),
            record.get("artifact_sha256", ""),
            artifact_status(ctx, record),
            record.get("summary", ""),
        ]
        for record in state.get("evidence", [])
    ]
    review_rows = [
        [
            review.get("id", ""),
            review.get("criterion_id", ""),
            review.get("evidence_id", ""),
            review.get("verdict", ""),
            review.get("notes", ""),
            review.get("artifact_sha256", ""),
        ]
        for review in state.get("reviews", [])
    ]
    return "\n".join(
        [
            "# Proof Report",
            "",
            f"Generated: {utc_now()}",
            f"Final verdict: {evaluation['verdict']}",
            f"Workspace: {ctx['workspace']}",
            f"Topic: {ctx['topic']}",
            f"Finalized: {state.get('finalized_at') or 'no'}",
            f"Seal: {seal_status(state)}",
            "",
            "## Goal",
            "",
            state.get("goal") or "(not set)",
            "",
            "## Criteria",
            "",
            markdown_table(["ID", "Description", "Status", "Required Evidence", "Evidence", "Provenance"], rows),
            "",
            "## Evidence",
            "",
            markdown_table(
                [
                    "ID",
                    "Criterion",
                    "Type",
                    "Strength",
                    "Provenance",
                    "Exit",
                    "Artifact",
                    "Size",
                    "SHA-256",
                    "Integrity",
                    "Summary",
                ],
                evidence_rows,
            ),
            "",
            "## Reviews",
            "",
            markdown_table(["ID", "Criterion", "Evidence", "Verdict", "Notes", "Artifact SHA-256"], review_rows),
            "",
            "## Issues",
            "",
            "\n".join(f"- {issue}" for issue in evaluation["issues"]) or "- none",
            "",
        ]
    )


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    table = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    if not rows:
        rows = [["" for _ in headers]]
    for row in rows:
        escaped = [" ".join(str(cell).replace("|", "\\|").splitlines()) for cell in row]
        table.append("| " + " | ".join(escaped) + " |")
    return "\n".join(table)


def artifact_preview(path: Path) -> str:
    if image_like(path):
        return f"Image artifact: {path}"
    data = path.read_bytes()[: TEXT_PREVIEW_BYTES + 1]
    if b"\x00" in data:
        return "Binary artifact preview unavailable."
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "Non-UTF-8 artifact preview unavailable."
    lines = text.splitlines()[:TEXT_PREVIEW_LINES]
    if len(data) > TEXT_PREVIEW_BYTES:
        lines.append("[preview truncated]")
    return "\n".join(lines) or "(empty artifact)"


def command_show(args: argparse.Namespace) -> int:
    ctx = context(args)
    state = load_state(ctx, create=False)
    record = evidence_by_id(state, args.evidence_id)
    if not record:
        print(f"Unknown evidence: {args.evidence_id}", file=sys.stderr)
        return 2
    path = artifact_path(ctx, record)
    print(f"Evidence: {record.get('id')}")
    print(f"Criterion: {record.get('criterion_id')}")
    print(f"Type: {record.get('type')}")
    print(f"Strength: {record.get('strength')}")
    print(f"Provenance: {record.get('provenance', legacy_provenance(record))}")
    print(f"Summary: {record.get('summary')}")
    print(f"Command: {record.get('command') or ''}")
    print(f"Exit code: {record.get('exit_code')}")
    print(f"Artifact: {record.get('artifact_path')}")
    print(f"Integrity: {artifact_status(ctx, record)}")
    print(f"Seal: {seal_status(state)}")
    print()
    if path and path.exists():
        print(artifact_preview(path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=",proof", description="Repo-external durable receipts for qualifying freeform work."
    )
    parser.add_argument("--version", action="version", version=f",proof {VERSION}")
    parser.add_argument("--workspace", help="Workspace path. Defaults to the current git root or cwd.")
    parser.add_argument("--topic", help="Proof topic. Defaults to AGENT_PROOF_TOPIC, PROOF_TOPIC, or current.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--workspace", default=argparse.SUPPRESS, help="Workspace path. Defaults to the current git root or cwd."
    )
    parent.add_argument(
        "--topic",
        default=argparse.SUPPRESS,
        help="Proof topic. Defaults to AGENT_PROOF_TOPIC, PROOF_TOPIC, or current.",
    )

    start = subcommands.add_parser("start", parents=[parent], help="Create or confirm the current proof ledger.")
    start.add_argument("--force", action="store_true", help="Replace the current proof ledger.")
    start.add_argument("goal", nargs="*", help="Goal text.")
    start.set_defaults(func=command_start)

    subcommands.add_parser("path", parents=[parent], help="Print the proof directory path.").set_defaults(
        func=command_path
    )

    ledger_list = subcommands.add_parser("list", parents=[parent], help="List proof ledgers.")
    ledger_list.add_argument("--json", action="store_true", help="Print JSON ledger rows.")
    ledger_list.add_argument("--all-workspaces", action="store_true", help="List ledgers from every workspace hash.")
    ledger_list.set_defaults(func=command_list)

    criterion = subcommands.add_parser("add-criterion", parents=[parent], help="Add an acceptance criterion.")
    criterion.add_argument("--id", help="Explicit criterion id, such as AC-001.")
    criterion.add_argument(
        "--requires",
        action="append",
        default=[],
        required=True,
        help="Required evidence type(s), comma-separated or repeated.",
    )
    criterion.add_argument("description", nargs="+", help="Observable criterion text.")
    criterion.set_defaults(func=command_add_criterion)

    evidence = subcommands.add_parser("add-evidence", parents=[parent], help="Attach command or artifact evidence.")
    evidence.add_argument("--criterion", "-c", required=True, help="Criterion id.")
    evidence.add_argument("--type", "-t", required=True, choices=sorted(SUPPORTED_EVIDENCE_TYPES))
    evidence.add_argument("--command", help="Command to run and capture as evidence.")
    evidence.add_argument("--artifact-path", help="Existing artifact to copy into proof state.")
    evidence.add_argument("--exit-code", type=int, help="Exit code for externally captured command evidence.")
    evidence.add_argument("--summary", help="Short evidence summary.")
    evidence.add_argument("--allow-secrets", action="store_true", help="Allow secret-like content with a warning.")
    evidence.set_defaults(func=command_add_evidence)

    show = subcommands.add_parser("show", parents=[parent], help="Show evidence metadata and preview.")
    show.add_argument("evidence_id", help="Evidence id, such as EV-001.")
    show.set_defaults(func=command_show)

    review = subcommands.add_parser("review", parents=[parent], help="Record a review verdict for evidence.")
    review.add_argument("--criterion", "-c", required=True, help="Criterion id.")
    review.add_argument("--evidence", "-e", required=True, help="Evidence id.")
    review.add_argument("--verdict", "-v", required=True, choices=sorted(REVIEW_VERDICTS))
    review.add_argument("--notes", "-n", required=True, help="Review notes explaining the verdict.")
    review.add_argument("--reviewer", help="Reviewer name.")
    review.set_defaults(func=command_review)

    block = subcommands.add_parser("block", parents=[parent], help="Record an unresolved blocker.")
    block.add_argument("description", nargs="+", help="Blocker description.")
    block.set_defaults(func=command_block)

    resolve = subcommands.add_parser("resolve-blocker", parents=[parent], help="Mark a blocker resolved.")
    resolve.add_argument("blocker_id", help="Blocker id, such as B-001.")
    resolve.set_defaults(func=command_resolve_blocker)

    finalize = subcommands.add_parser("finalize", parents=[parent], help="Seal the proof ledger.")
    finalize.add_argument("--allow-failing", action="store_true", help="Seal even when check currently fails.")
    finalize.set_defaults(func=command_finalize)

    subcommands.add_parser(
        "reopen", parents=[parent], help="Clear the finalized seal and record audit history."
    ).set_defaults(func=command_reopen)

    prune = subcommands.add_parser("prune", parents=[parent], help="Remove old proof topic directories.")
    prune.add_argument("--older-than", type=int, required=True, metavar="DAYS", help="Remove ledgers older than DAYS.")
    prune.add_argument("--dry-run", action="store_true", help="Print removals without deleting.")
    prune.set_defaults(func=command_prune)

    status = subcommands.add_parser("status", parents=[parent], help="Show proof status.")
    status.add_argument("--json", action="store_true", help="Print JSON status.")
    status.add_argument("--verbose", "-v", action="store_true", help="Print gate issues.")
    status.set_defaults(func=command_status)

    check = subcommands.add_parser("check", parents=[parent], help="Run the completion gate.")
    check.add_argument("--json", action="store_true", help="Print JSON gate output.")
    check.set_defaults(func=command_check)

    subcommands.add_parser("report", parents=[parent], help="Write a finalized Markdown proof receipt.").set_defaults(
        func=command_report
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
