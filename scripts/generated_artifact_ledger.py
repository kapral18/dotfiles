#!/usr/bin/env python3
"""Record and inspect ownership-aware generated AI artifacts.

The runtime ledger is machine-local state. It stores paths, hashes, ownership
metadata, and consumer probes, but never generated config contents or secrets.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
LEDGER_NAME = "generated_artifacts.v1.json"
MISSING = {"$generated_artifact_missing": True}
SUPPORTED_ADAPTERS = {
    "whole-file",
    "json-selectors",
    "json-declared",
    "toml-line-excludes",
}


def default_ledger_path() -> Path:
    override = os.environ.get("CHEZMOI_ARTIFACT_LEDGER")
    if override:
        return Path(override).expanduser()
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return state_home / "chezmoi" / LEDGER_NAME


def _empty_ledger() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "artifacts": {}}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _file_hash(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"artifact dependency is not a file: {path}")
    return _sha256_bytes(path.read_bytes())


def _validate_artifact_id(artifact_id: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", artifact_id):
        raise ValueError(f"invalid artifact id: {artifact_id!r}")


def _validate_ledger(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("ledger root must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported ledger schema: {payload.get('schema_version')!r}")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("ledger artifacts must be an object")
    for artifact_id, row in artifacts.items():
        _validate_artifact_id(str(artifact_id))
        if not isinstance(row, dict) or row.get("artifact_id") != artifact_id:
            raise ValueError(f"invalid artifact row: {artifact_id!r}")
    return payload


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _empty_ledger()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ValueError(f"ledger is not valid JSON: {err}") from err
    return _validate_ledger(payload)


def _serialize(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _atomic_replace(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f"{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise


def _write_if_changed(path: Path, payload: dict[str, Any]) -> bool:
    content = _serialize(payload)
    if path.is_file() and path.read_bytes() == content:
        return False
    _atomic_replace(path, content)
    return True


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _json_value(content: bytes) -> object:
    try:
        return json.loads(content)
    except json.JSONDecodeError as err:
        raise ValueError(f"target is not valid JSON at line {err.lineno}, column {err.colno}") from err


def _selector_parts(selector: str) -> list[str]:
    parts = [part for part in selector.split(".") if part]
    if not parts:
        raise ValueError(f"invalid empty selector: {selector!r}")
    return parts


def _select_path(value: object, selector: str) -> object:
    current = value
    for part in _selector_parts(selector):
        if not isinstance(current, dict) or part not in current:
            return copy.deepcopy(MISSING)
        current = current[part]
    return copy.deepcopy(current)


def _set_path(target: dict[str, Any], selector: str, value: object) -> None:
    current = target
    parts = _selector_parts(selector)
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = copy.deepcopy(value)


def _json_selector_projection(value: object, selectors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("JSON selector projection requires an object root")
    projected: dict[str, Any] = {}
    for selector in selectors:
        _set_path(projected, selector, _select_path(value, selector))
    return projected


def _is_exact_path(path: tuple[str, ...], exact_selectors: set[tuple[str, ...]]) -> bool:
    return path in exact_selectors


def _declared_projection(
    live: object,
    baseline: object,
    exact_selectors: set[tuple[str, ...]],
    path: tuple[str, ...] = (),
) -> object:
    if _is_exact_path(path, exact_selectors):
        return copy.deepcopy(live)
    if isinstance(baseline, dict):
        if not isinstance(live, dict):
            return copy.deepcopy(MISSING)
        return {
            key: _declared_projection(
                live.get(key, MISSING),
                declared,
                exact_selectors,
                (*path, str(key)),
            )
            for key, declared in baseline.items()
        }
    return copy.deepcopy(live)


def _ownership_baseline(ownership: dict[str, Any]) -> object:
    if "baseline" in ownership:
        return ownership["baseline"]
    baseline_path = ownership.get("baseline_path")
    if not isinstance(baseline_path, str):
        raise ValueError("json-declared ownership requires baseline_path")
    return _json_value(Path(baseline_path).read_bytes())


def _parse_toml_section(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return None
    return stripped.lstrip("[").rstrip("]").strip()


def _parse_toml_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    return stripped.split("=", 1)[0].strip().strip('"')


def _toml_line_projection(content: bytes, ownership: dict[str, Any]) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ValueError("TOML target is not UTF-8") from err
    section_patterns = [re.compile(pattern) for pattern in ownership.get("exclude_sections", [])]
    key_patterns: list[tuple[re.Pattern[str], re.Pattern[str]]] = []
    for item in ownership.get("exclude_keys", []):
        if not isinstance(item, dict):
            raise ValueError("TOML exclude_keys entries must be objects")
        key_patterns.append((re.compile(str(item["section"])), re.compile(str(item["key"]))))

    output: list[str] = []
    current_section = ""
    skip_section = False
    for line in text.splitlines():
        section = _parse_toml_section(line)
        if section is not None:
            current_section = section
            skip_section = any(pattern.search(section) for pattern in section_patterns)
            if skip_section:
                continue
        elif skip_section:
            continue
        key = _parse_toml_key(line)
        if key is not None and any(
            section_pattern.search(current_section) and key_pattern.search(key)
            for section_pattern, key_pattern in key_patterns
        ):
            continue
        normalized = line.rstrip()
        if not normalized:
            if output and output[-1]:
                output.append("")
            continue
        output.append(normalized)
    while output and not output[-1]:
        output.pop()
    return ("\n".join(output) + "\n").encode()


def semantic_hash(content: bytes, ownership: dict[str, Any]) -> str:
    adapter = ownership.get("adapter")
    if adapter not in SUPPORTED_ADAPTERS:
        raise ValueError(f"unsupported ownership adapter: {adapter!r}")
    if adapter == "whole-file":
        projected = content
    elif adapter == "json-selectors":
        selectors = ownership.get("selectors")
        if not isinstance(selectors, list) or not selectors:
            raise ValueError("json-selectors requires selectors")
        projected = _canonical_json(_json_selector_projection(_json_value(content), [str(v) for v in selectors]))
    elif adapter == "json-declared":
        exact = {tuple(_selector_parts(str(selector))) for selector in ownership.get("exact_selectors", [])}
        projected = _canonical_json(
            _declared_projection(
                _json_value(content),
                _ownership_baseline(ownership),
                exact,
            )
        )
    else:
        projected = _toml_line_projection(content, ownership)
    return _sha256_bytes(projected)


def _normalize_paths(values: object, label: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{label} must be a non-empty list")
    paths = [os.fspath(Path(str(value)).expanduser()) for value in values]
    if len(paths) != len(set(paths)):
        raise ValueError(f"{label} must not contain duplicates")
    return paths


def _normalize_references(values: object) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("references must be a list")
    references = [str(value).strip() for value in values]
    if any(not value for value in references) or len(references) != len(set(references)):
        raise ValueError("references must be non-empty and unique")
    return references


def _normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    artifact_id = str(spec.get("artifact_id", ""))
    _validate_artifact_id(artifact_id)
    profile = spec.get("profile")
    if profile not in {"work", "personal"}:
        raise ValueError("profile must be work or personal")
    target = os.fspath(Path(str(spec.get("target", ""))).expanduser())
    if not target:
        raise ValueError("target path must not be empty")
    producer = str(spec.get("producer", "")).strip()
    if not producer:
        raise ValueError("producer must not be empty")
    ownership = copy.deepcopy(spec.get("ownership"))
    if not isinstance(ownership, dict):
        raise ValueError("ownership must be an object")
    consumer = copy.deepcopy(spec.get("consumer"))
    if not isinstance(consumer, dict) or not consumer.get("id"):
        raise ValueError("consumer must name an id")
    command = consumer.get("command")
    if not isinstance(command, list) or not command:
        command = [str(consumer["id"])]
        consumer["command"] = command
    live_probe = copy.deepcopy(spec.get("live_probe"))
    if not isinstance(live_probe, dict):
        live_probe = {"kind": "command", "argv": [str(consumer["id"]), "--version"]}
    argv = live_probe.get("argv")
    if live_probe.get("kind") != "command" or not isinstance(argv, list) or not argv:
        raise ValueError("live_probe must be a non-empty command argv")
    return {
        "artifact_id": artifact_id,
        "producer": producer,
        "profile": profile,
        "target": target,
        "inputs": _normalize_paths(spec.get("inputs"), "inputs"),
        "transforms": _normalize_paths(spec.get("transforms"), "transforms"),
        "references": _normalize_references(spec.get("references")),
        "ownership": ownership,
        "consumer": consumer,
        "live_probe": live_probe,
    }


def record_artifact(ledger: Path, spec: dict[str, Any]) -> bool:
    normalized = _normalize_spec(spec)
    target = Path(normalized["target"])
    if not target.is_file():
        raise ValueError(f"artifact target is not a file: {target}")
    row = {
        **normalized,
        "input_hashes": {path: _file_hash(Path(path)) for path in normalized["inputs"]},
        "transform_hashes": {path: _file_hash(Path(path)) for path in normalized["transforms"]},
        "expected_semantic_hash": semantic_hash(target.read_bytes(), normalized["ownership"]),
    }
    payload = load_ledger(ledger)
    artifacts = copy.deepcopy(payload["artifacts"])
    existing = artifacts.get(normalized["artifact_id"])
    if isinstance(existing, dict):
        comparable = {key: value for key, value in existing.items() if key != "recorded_at"}
        if comparable == row:
            return False
    row["recorded_at"] = _utc_now()
    artifacts[normalized["artifact_id"]] = row
    return _write_if_changed(
        ledger,
        {
            "schema_version": SCHEMA_VERSION,
            "artifacts": dict(sorted(artifacts.items())),
        },
    )


def forget_artifact(ledger: Path, artifact_id: str) -> bool:
    _validate_artifact_id(artifact_id)
    payload = load_ledger(ledger)
    artifacts = copy.deepcopy(payload["artifacts"])
    if artifact_id not in artifacts:
        return False
    artifacts.pop(artifact_id)
    return _write_if_changed(
        ledger,
        {
            "schema_version": SCHEMA_VERSION,
            "artifacts": dict(sorted(artifacts.items())),
        },
    )


def _current_hash(path: str) -> str | None:
    target = Path(path)
    return _sha256_bytes(target.read_bytes()) if target.is_file() else None


def _consumer_exists(consumer: dict[str, Any]) -> bool:
    command = consumer.get("command")
    if not isinstance(command, list) or not command:
        return False
    executable = str(command[0])
    if os.path.isabs(executable):
        return os.access(executable, os.X_OK)
    return shutil.which(executable) is not None


def evaluate_artifact(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    input_current = {path: _current_hash(path) for path in row["inputs"]}
    transform_current = {path: _current_hash(path) for path in row["transforms"]}
    if input_current != row["input_hashes"]:
        reasons.append("input-drift")
    if transform_current != row["transform_hashes"]:
        reasons.append("transform-drift")
    target = Path(row["target"])
    current_semantic_hash: str | None = None
    if not target.is_file():
        reasons.append("target-missing")
    else:
        try:
            current_semantic_hash = semantic_hash(target.read_bytes(), row["ownership"])
        except (OSError, ValueError):
            reasons.append("target-invalid")
        else:
            if current_semantic_hash != row["expected_semantic_hash"]:
                reasons.append("owned-drift")
    if not _consumer_exists(row["consumer"]):
        reasons.append("consumer-missing")
    return {
        "artifact_id": row["artifact_id"],
        "status": reasons[0] if reasons else "ok",
        "reasons": reasons,
        "recorded_at": row.get("recorded_at"),
        "expected_semantic_hash": row["expected_semantic_hash"],
        "current_semantic_hash": current_semantic_hash,
        "trace": {
            "declaration": [
                {
                    "path": path,
                    "recorded_sha256": row["input_hashes"][path],
                    "current_sha256": input_current[path],
                }
                for path in row["inputs"]
            ]
            + [{"reference": reference, "sensitive": True} for reference in row.get("references", [])],
            "transform": [
                {
                    "path": path,
                    "recorded_sha256": row["transform_hashes"][path],
                    "current_sha256": transform_current[path],
                }
                for path in row["transforms"]
            ],
            "profile": row["profile"],
            "target": row["target"],
            "ownership": row["ownership"],
            "consumer": row["consumer"],
            "live_probe": row["live_probe"],
        },
        "live_probe": {"status": "not-run"},
    }


def _run_probe(argv: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        return {"status": "failed", "exit_code": None, "detail": str(err)[:200]}
    output = (result.stdout or result.stderr).strip().splitlines()
    return {
        "status": "ok" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "detail": output[0][:200] if output else "",
    }


def report_payload(ledger: Path, *, live: bool) -> dict[str, Any]:
    payload = load_ledger(ledger)
    rows = [evaluate_artifact(row) for row in payload["artifacts"].values()]
    probe_results: dict[tuple[str, ...], dict[str, Any]] = {}
    if live:
        for row in rows:
            argv = tuple(str(value) for value in row["trace"]["live_probe"]["argv"])
            if argv not in probe_results:
                probe_results[argv] = _run_probe(list(argv))
            row["live_probe"] = probe_results[argv]
    ok = bool(rows) and all(row["status"] == "ok" and (not live or row["live_probe"]["status"] == "ok") for row in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger": str(ledger),
        "ok": ok,
        "artifacts": rows,
        "summary": {
            "artifacts": len(rows),
            "current": sum(row["status"] == "ok" for row in rows),
            "non_current": sum(row["status"] != "ok" for row in rows),
            "probes_run": len(probe_results),
            "probes_failed": sum(result["status"] != "ok" for result in probe_results.values()),
        },
    }


def _human_report(payload: dict[str, Any], *, quiet: bool, verbose: bool) -> str:
    lines = [",doctor ai — generated AI effective state"]
    for row in payload["artifacts"]:
        if quiet and row["status"] == "ok" and row["live_probe"]["status"] in {"not-run", "ok"}:
            continue
        icon = "✓" if row["status"] == "ok" else "✗"
        probe = row["live_probe"]["status"]
        lines.append(f"  {icon} {row['artifact_id']}: {row['status']}  target={row['trace']['target']}  probe={probe}")
        if verbose:
            lines.append(
                f"      declaration={len(row['trace']['declaration'])} "
                f"transform={len(row['trace']['transform'])} "
                f"profile={row['trace']['profile']} "
                f"consumer={row['trace']['consumer']['id']}"
            )
            if row["reasons"]:
                lines.append(f"      reasons={','.join(row['reasons'])}")
    summary = payload["summary"]
    lines.append(
        f"  summary: {summary['current']}/{summary['artifacts']} current, "
        f"{summary['probes_run']} probe(s), {summary['probes_failed']} failed"
    )
    return "\n".join(lines)


def _ownership_from_args(args: argparse.Namespace) -> dict[str, Any]:
    ownership: dict[str, Any] = {"adapter": args.ownership_adapter}
    if args.selector:
        ownership["selectors"] = args.selector
    if args.baseline:
        ownership["baseline_path"] = os.fspath(Path(args.baseline).expanduser())
    if args.exact_selector:
        ownership["exact_selectors"] = args.exact_selector
    if args.exclude_section:
        ownership["exclude_sections"] = args.exclude_section
    if args.exclude_key:
        parsed = []
        for raw in args.exclude_key:
            if "::" not in raw:
                raise ValueError("--exclude-key requires SECTION_REGEX::KEY_REGEX")
            section, key = raw.split("::", 1)
            parsed.append({"section": section, "key": key})
        ownership["exclude_keys"] = parsed
    return ownership


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=default_ledger_path())
    subcommands = parser.add_subparsers(dest="command", required=True)

    record = subcommands.add_parser("record")
    record.add_argument("--id", required=True, dest="artifact_id")
    record.add_argument("--producer", required=True)
    record.add_argument("--profile", required=True, choices=("work", "personal"))
    record.add_argument("--target", required=True)
    record.add_argument("--input", action="append", required=True, dest="inputs")
    record.add_argument("--transform", action="append", required=True, dest="transforms")
    record.add_argument("--reference", action="append", dest="references")
    record.add_argument("--ownership-adapter", required=True, choices=sorted(SUPPORTED_ADAPTERS))
    record.add_argument("--selector", action="append")
    record.add_argument("--baseline")
    record.add_argument("--exact-selector", action="append")
    record.add_argument("--exclude-section", action="append")
    record.add_argument("--exclude-key", action="append")
    record.add_argument("--consumer", required=True)

    forget = subcommands.add_parser("forget")
    forget.add_argument("--id", required=True, dest="artifact_id")

    report = subcommands.add_parser("report")
    report.add_argument("--json", action="store_true")
    report.add_argument("--live", action="store_true")
    report.add_argument("-q", "--quiet", action="store_true")
    report.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            ownership = _ownership_from_args(args)
            if ownership["adapter"] == "json-declared" and not args.baseline:
                raise ValueError("json-declared requires --baseline")
            record_artifact(
                args.ledger,
                {
                    "artifact_id": args.artifact_id,
                    "producer": args.producer,
                    "profile": args.profile,
                    "target": args.target,
                    "inputs": args.inputs,
                    "transforms": args.transforms,
                    "references": args.references or [],
                    "ownership": ownership,
                    "consumer": {"id": args.consumer, "command": [args.consumer]},
                    "live_probe": {"kind": "command", "argv": [args.consumer, "--version"]},
                },
            )
            return 0
        if args.command == "forget":
            forget_artifact(args.ledger, args.artifact_id)
            return 0
        payload = report_payload(args.ledger, live=args.live)
    except (OSError, ValueError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(_human_report(payload, quiet=args.quiet, verbose=args.verbose))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
