#!/usr/bin/env python3
"""Disposable state-machine and latency harness for recall/worklog changes."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO.parent / "baseline"
SCRIPTS = REPO / "scripts"
HOOKS = REPO / "home" / "exact_dot_agents" / "exact_hooks"


def _env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["AGENT_MEMORY_SPEC_ROOT"] = str(root / "specs")
    env["PYTHONPATH"] = f"{SCRIPTS}{os.pathsep}{env.get('PYTHONPATH', '')}"
    return env


def _copy_shared_hooks(source: Path, target: Path, *, patch_spec_root: bool = False) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for source_name, target_name in (
        ("hook_common.py", "hook_common.py"),
        ("executable_session_context.py", "session_context.py"),
        ("executable_perturn_recall.py", "perturn_recall.py"),
        ("executable_worklog_recorder.py", "worklog_recorder.py"),
        ("executable_worklog_dispatcher.sh", "worklog_dispatcher.sh"),
    ):
        path = source / source_name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if patch_spec_root:
            text = re.sub(
                r"^SPEC_ROOT = Path\(.*\)$",
                'SPEC_ROOT = Path(os.environ["AGENT_MEMORY_SPEC_ROOT"])',
                text,
                flags=re.MULTILINE,
            )
        copied = target / target_name
        copied.write_text(text, encoding="utf-8")
        copied.chmod(0o755)


def _search_stub(root: Path, workspace: Path, delay: float) -> Path:
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "id": f"fixture-{index}",
            "title": f"Fixture capsule {index}",
            "body": "bounded fixture body " * 30,
            "kind": "fact",
            "scope": "project",
            "workspace_path": str(workspace),
            "cosine_score": 0.9,
        }
        for index in range(12)
    ]
    stub = bindir / ",ai-kb"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys, time\n"
        "query = sys.stdin.read()\n"
        f"time.sleep({delay!r})\n"
        "with open(os.environ['SEARCH_LOG'], 'a', encoding='utf-8') as stream:\n"
        "    stream.write(json.dumps({'args': sys.argv[1:], 'query': query, "
        "'connect_only': os.environ.get('AI_EMBED_CONNECT_ONLY')}) + '\\n')\n"
        f"print({json.dumps(rows)!r})\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return bindir


def _run_recall_benchmark(root: Path) -> dict:
    hooks = root / "hooks"
    _copy_shared_hooks(HOOKS, hooks)
    workspace = (root / "workspace").resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    bindir = _search_stub(root, workspace, 0.08)
    results: dict[str, dict] = {}
    for depth in ("unset", "fast", "balanced", "deep"):
        durations: list[float] = []
        search_log = root / f"{depth}-search.jsonl"
        for index in range(7):
            env = _env(root / depth)
            env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
            env["SEARCH_LOG"] = str(search_log)
            if depth == "unset":
                env.pop("AI_AGENT_DEPTH", None)
            else:
                env["AI_AGENT_DEPTH"] = depth
            payload = {
                "hook_event_name": "UserPromptSubmit",
                "workspace_roots": [str(workspace)],
                "session_id": f"{depth}-{index}",
                "prompt": "depth benchmark automatic recall with deterministic retrieval latency",
            }
            started = time.perf_counter()
            completed = subprocess.run(
                [sys.executable, str(hooks / "perturn_recall.py")],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env=env,
                check=True,
            )
            durations.append((time.perf_counter() - started) * 1000)
            if depth == "fast" and json.loads(completed.stdout or "{}") != {}:
                raise AssertionError("fast recall emitted context")
        searches = [json.loads(line) for line in search_log.read_text().splitlines()] if search_log.exists() else []
        results[depth] = {
            "median_ms": round(statistics.median(durations), 3),
            "min_ms": round(min(durations), 3),
            "max_ms": round(max(durations), 3),
            "searches": len(searches),
            "search_args": searches[0]["args"] if searches else [],
        }
    if results["unset"]["search_args"][:6] != results["balanced"]["search_args"][:6]:
        raise AssertionError("unset recall does not match balanced search profile")
    if results["fast"]["searches"] != 0:
        raise AssertionError("fast recall executed retrieval")
    if results["deep"]["search_args"][3] != "12":
        raise AssertionError("deep recall is not bounded at fetch=12")
    if results["fast"]["median_ms"] >= results["balanced"]["median_ms"] * 0.65:
        raise AssertionError("fast recall did not materially reduce deterministic fixture latency")
    return results


def _run_hook(path: Path, payload: dict, env: dict[str, str]) -> float:
    started = time.perf_counter()
    command = [sys.executable, str(path)] if path.suffix == ".py" else ["/bin/sh", str(path)]
    result = subprocess.run(
        command,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
        check=True,
    )
    if json.loads(result.stdout or "{}").get("worklog_error"):
        raise AssertionError(result.stdout)
    return (time.perf_counter() - started) * 1000


def _seed_saturated_worklog(spec_root: Path, workspace: Path) -> Path:
    worklog = spec_root / str(workspace).lstrip(os.sep) / "current.worklog.jsonl"
    worklog.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"ts": f"2026-07-11T12:00:{index % 60:02d}+00:00", "output": "x" * 1200}) for index in range(200)
    ]
    worklog.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return worklog


def _run_worklog_benchmark(root: Path) -> dict:
    baseline_hooks = root / "baseline-hooks"
    work_hooks = root / "work-hooks"
    _copy_shared_hooks(BASELINE / "home" / "exact_dot_agents" / "exact_hooks", baseline_hooks, patch_spec_root=True)
    _copy_shared_hooks(HOOKS, work_hooks)
    workspace = (root / "workspace").resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    payload = {
        "hook_event_name": "postToolUse",
        "workspace_roots": [str(workspace)],
        "session_id": "latency-session",
        "tool_name": "Shell",
        "tool_input": {"command": "printf benchmark"},
        "tool_output": "x" * 1800,
    }
    durations: dict[str, list[float]] = {"baseline": [], "queued": []}
    baseline_root = root / "baseline-state"
    queued_root = root / "queued-state"
    _seed_saturated_worklog(baseline_root / "specs", workspace)
    _seed_saturated_worklog(queued_root / "specs", workspace)
    baseline_env = _env(baseline_root)
    queued_env = _env(queued_root)
    for _ in range(15):
        durations["baseline"].append(_run_hook(baseline_hooks / "worklog_recorder.py", payload, baseline_env))
        durations["queued"].append(_run_hook(work_hooks / "worklog_dispatcher.sh", payload, queued_env))
    import worklog_queue

    queued_spec_dir = queued_root / "specs" / str(workspace).lstrip(os.sep)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        flush = worklog_queue.flush_spec_dir(queued_spec_dir)
        worklog = queued_spec_dir / "current.worklog.jsonl"
        if worklog.exists() and '"session_key": "latency-session"' in worklog.read_text(encoding="utf-8"):
            break
        time.sleep(0.02)
    else:
        raise AssertionError("asynchronous worklog dispatch did not become durable")
    if flush.errors or flush.pending:
        raise AssertionError(f"queued benchmark flush incomplete: {flush}")
    result = {
        key: {
            "median_ms": round(statistics.median(values), 3),
            "min_ms": round(min(values), 3),
            "max_ms": round(max(values), 3),
        }
        for key, values in durations.items()
    }
    result["improvement_pct"] = round(
        (1 - result["queued"]["median_ms"] / result["baseline"]["median_ms"]) * 100,
        1,
    )
    if result["queued"]["median_ms"] >= result["baseline"]["median_ms"] * 0.85:
        raise AssertionError(f"queued worklog hot path did not improve materially: {result}")
    return result


def _enqueue_concurrent(args: tuple[str, str, str, int]) -> None:
    import worklog_queue

    spec_dir, session_key, worklog, index = args
    worklog_queue.enqueue(
        Path(spec_dir),
        session_key,
        "current",
        Path(worklog),
        {"command": f"command-{index}", "event": "postToolUse"},
        start_worker=False,
    )


def _run_queue_state_machine(root: Path) -> list[dict]:
    import worklog_queue

    spec_dir = root / "specs" / "workspace"
    worklog = spec_dir / "current.worklog.jsonl"
    spec_dir.mkdir(parents=True)
    transitions: list[dict] = [{"from": "EMPTY", "input": "inspect", "to": "EMPTY", "pending": 0}]
    receipts = [
        worklog_queue.enqueue(
            spec_dir,
            "state-session",
            "current",
            worklog,
            {"command": f"ordered-{index}", "event": "postToolUse"},
            start_worker=False,
        )
        for index in range(3)
    ]
    transitions.append({"from": "EMPTY", "input": "enqueue x3", "to": "PENDING", "pending": 3})
    first = worklog_queue.read_queue_record(receipts[0].path)
    committed = {
        **first["entry"],
        "worklog_id": first["id"],
        "session_key": first["session_key"],
        "worklog_seq": first["seq"],
    }
    worklog.write_text(json.dumps(committed, sort_keys=True) + "\n", encoding="utf-8")
    flush = worklog_queue.flush_session(receipts[0].queue_dir)
    entries = [json.loads(line) for line in worklog.read_text().splitlines()]
    if [entry["command"] for entry in entries] != ["ordered-0", "ordered-1", "ordered-2"]:
        raise AssertionError("crash replay changed queue order")
    transitions.append(
        {
            "from": "CRASH_AFTER_COMMIT",
            "input": "replay",
            "to": "COMMITTED",
            "duplicates": flush.duplicates,
            "pending": flush.pending,
        }
    )
    concurrent_worklog = spec_dir / "concurrent.worklog.jsonl"
    jobs = [(str(spec_dir), f"session-{index % 4}", str(concurrent_worklog), index) for index in range(40)]
    with ProcessPoolExecutor(max_workers=8) as pool:
        list(pool.map(_enqueue_concurrent, jobs))
    concurrent = worklog_queue.flush_spec_dir(spec_dir)
    concurrent_entries = [json.loads(line) for line in concurrent_worklog.read_text().splitlines()]
    if len({entry["worklog_id"] for entry in concurrent_entries}) != 40:
        raise AssertionError("concurrent flush lost or duplicated events")
    transitions.append(
        {
            "from": "CONCURRENT_PENDING",
            "input": "flush",
            "to": "ORDERED_COMMITTED",
            "events": len(concurrent_entries),
            "pending": concurrent.pending,
        }
    )
    config = worklog_queue.QueueConfig(max_pending=2, max_bytes=64 * 1024)
    bounded_dir = root / "bounded-specs" / "workspace"
    bounded_log = bounded_dir / "current.worklog.jsonl"
    bounded_dir.mkdir(parents=True)
    for index in range(2):
        worklog_queue.enqueue(
            bounded_dir,
            "bounded",
            "current",
            bounded_log,
            {"command": f"bounded-{index}"},
            config=config,
            start_worker=False,
        )
    try:
        worklog_queue.enqueue(
            bounded_dir,
            "bounded",
            "current",
            bounded_log,
            {"command": "overflow"},
            config=config,
            start_worker=False,
        )
    except worklog_queue.QueueFullError:
        pass
    else:
        raise AssertionError("bounded queue accepted overflow")
    queue_dir = worklog_queue.session_queue_dir(bounded_dir, "bounded")
    transitions.append(
        {
            "from": "SATURATED",
            "input": "enqueue",
            "to": "REJECTED_VISIBLE",
            "pending": len(list(queue_dir.glob("*.json"))),
            "error_log": str(worklog_queue.error_log_path(queue_dir)),
        }
    )
    visible = worklog_queue.flush_spec_dir(bounded_dir, config=config)
    if not visible.errors:
        raise AssertionError("recorded queue failure was reported as success")
    transitions.append(
        {
            "from": "REJECTED_VISIBLE",
            "input": "flush",
            "to": "ERROR_REPORTED",
            "pending": visible.pending,
            "errors": visible.errors,
        }
    )
    old = time.time() - 8 * 24 * 60 * 60
    for path in queue_dir.iterdir():
        os.utime(path, (old, old))
    os.utime(queue_dir, (old, old))
    removed = worklog_queue.cleanup_spec_dir(
        bounded_dir,
        config=worklog_queue.QueueConfig(cleanup_age_seconds=7 * 24 * 60 * 60),
    )
    if removed != 1 or queue_dir.exists():
        raise AssertionError("stale drained queue was not cleaned up")
    transitions.append(
        {
            "from": "ERROR_REPORTED",
            "input": "cleanup after seven days",
            "to": "CLEANED",
            "removed": removed,
        }
    )
    return transitions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    manifest = {
        "worktree": str(REPO),
        "baseline": str(BASELINE),
        "topic": "legion-recall-worklog",
        "slug": "depth-recall-worklog-queue",
        "target_files": [
            "home/exact_dot_agents/exact_hooks/executable_perturn_recall.py",
            "home/dot_pi/agent/extensions/ai-kb-recall.ts",
            "scripts/worklog_queue.py",
            "home/exact_dot_agents/exact_hooks/executable_worklog_recorder.py",
            "home/exact_dot_agents/exact_hooks/executable_worklog_dispatcher.sh",
        ],
        "requested_behavior": "depth-aware bounded recall and asynchronous crash-safe worklog flush",
        "compatibility_intent": "preserve unset/balanced behavior",
        "target_symbols": [
            "agent_depth",
            "RECALL_PROFILES",
            "enqueue",
            "flush_session",
            "flush_spec_dir",
            "run_worker",
            "cleanup_spec_dir",
        ],
        "states": [
            "EMPTY",
            "PENDING",
            "CRASH_AFTER_COMMIT",
            "COMMITTED",
            "CONCURRENT_PENDING",
            "ORDERED_COMMITTED",
            "SATURATED",
            "REJECTED_VISIBLE",
            "ERROR_REPORTED",
            "CLEANED",
        ],
        "inputs": [
            "AI_AGENT_DEPTH unset/fast/balanced/deep",
            "ordered session events",
            "concurrent session events sharing one target",
            "crash replay after target commit before queue acknowledgement",
            "queue overflow",
            "seven-day cleanup",
        ],
        "terminal_actions": [
            "recall context emitted or deliberately omitted",
            "worklog record committed",
            "queue failure reported",
            "drained state cleaned",
        ],
        "boundaries": {
            "pending_events_per_session": 256,
            "pending_bytes_per_session": 1048576,
            "worklog_lines": 200,
            "worker_idle_seconds": 0.08,
            "worker_max_seconds": 2.0,
            "cleanup_age_seconds": 604800,
        },
        "malformed_inputs": [
            "unsupported depth resolves to balanced (unit matrix)",
            "invalid queue records remain pending with a bounded error ledger",
        ],
        "regression_sensitive_cases": [
            "scope and relevance gates",
            "canonical session dedupe",
            "query stdin secrecy",
            "connect-only no-spawn recall",
            "cross-session chronological harvest order",
            "fail-open adapters with visible queue errors",
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    results = {
        "recall_latency": _run_recall_benchmark(root / "recall"),
        "worklog_latency": _run_worklog_benchmark(root / "worklog"),
        "queue_transitions": _run_queue_state_machine(root / "queue"),
    }
    (root / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
