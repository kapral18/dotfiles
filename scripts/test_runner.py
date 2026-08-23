#!/usr/bin/env python3
"""File-sharded parallel runner for the repo's Python unittest suite.

Each ``test_*.py`` file runs in its own subprocess (one per file, N workers),
so files execute concurrently instead of in one serial ``unittest discover``
process. ``make test`` calls this in place of ``unittest discover``.

Isolation: every file subprocess gets an ``AGENT_MEMORY_SPEC_ROOT`` namespaced
by the file stem (``agent-hook-specs-<stem>`` under TMPDIR), so parallel files
never share the mutable spec root (queue dirs, worklogs) that the default
``agent-hook-specs`` would force them into. Env (including
``AI_KB_RECALL_TIMEOUT``) is inherited verbatim so load-sensitive timeouts keep
their relaxing floor.

Usage:
    python3 scripts/test_runner.py            # run all shards, stream results
    python3 scripts/test_runner.py --list     # print the shard plan, run nothing
    python3 scripts/test_runner.py tests/test_foo.py test_bar.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
# The runner matches test_*.py but is not a unittest module.
NOT_TEST_FILES = frozenset({"test_runner.py", "test_bin_commands.py"})
UNIT_SHARDED_FILES = frozenset(
    {
        "test_ai_kb.py",
        "tests/test_gh_picker_dispatch_state.py",
        "tests/test_llama_cpp_lifecycle.py",
        "tests/test_plain_session_removal.py",
        "tests/test_proof_cli.py",
        "tests/test_recall_worklog.py",
        "tests/test_session_github_cache.py",
        "tests/test_tmux_handoff_lifecycle.py",
        "tests/test_wh.py",
        "tests/test_worktree_delete_boundaries.py",
    }
)


@dataclass(frozen=True)
class Shard:
    path: Path
    target: str
    label: str
    spec_stem: str


def discover_files() -> list[Path]:
    files = sorted(SCRIPTS.glob("test_*.py"))
    files += sorted((SCRIPTS / "tests").glob("test_*.py"))
    return [path for path in files if path.name not in NOT_TEST_FILES]


# Shard subprocesses run with PYTHONDONTWRITEBYTECODE from check.py, so tests
# that inspect the working tree do not need a serial lead phase.
LEAD_FILES = frozenset()


def _split_lead(files: list[Path]) -> tuple[list[Path], list[Path]]:
    lead = [f for f in files if f.name in LEAD_FILES]
    shards = [f for f in files if f.name not in LEAD_FILES]
    return lead, shards


def module_name(path: Path) -> str:
    rel = path.relative_to(SCRIPTS).with_suffix("")
    return ".".join(rel.parts)


def _safe_stem(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)[:120]


def shard_spec_root(shard: Shard, tmpdir: str) -> str:
    return str(Path(tmpdir) / f"agent-hook-specs-{_safe_stem(shard.spec_stem)}")


def _flatten_suite(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten_suite(item)
        else:
            yield item


def expand_shards(files: list[Path]) -> list[Shard]:
    shards: list[Shard] = []
    for path in files:
        module = module_name(path)
        rel = path.relative_to(SCRIPTS).as_posix()
        if rel in UNIT_SHARDED_FILES:
            suite = unittest.defaultTestLoader.loadTestsFromName(module)
            for test in _flatten_suite(suite):
                target = test.id()
                shards.append(Shard(path=path, target=target, label=target, spec_stem=target))
        else:
            shards.append(Shard(path=path, target=module, label=module, spec_stem=path.stem))
    return shards


def run_shard(shard: Shard, tmpdir: str) -> tuple[Shard, int, float, str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
    env["AGENT_MEMORY_SPEC_ROOT"] = shard_spec_root(shard, tmpdir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", shard.target],
        cwd=str(SCRIPTS),
        env=env,
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - start
    return shard, proc.returncode, elapsed, proc.stdout, proc.stderr


def resolve_files(names: list[str]) -> list[Path]:
    if not names:
        return discover_files()
    resolved: list[Path] = []
    for name in names:
        path = Path(name)
        if not path.is_absolute():
            candidate = SCRIPTS / path
            path = candidate if candidate.exists() else path
        if path.name in NOT_TEST_FILES:
            continue
        resolved.append(path)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print shard plan and exit")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    parser.add_argument("files", nargs="*", help="test files relative to scripts/ (default: all shards)")
    args = parser.parse_args()

    files = resolve_files(args.files)
    shards = expand_shards(files)
    if args.list:
        for shard in shards:
            print(shard.label)
        return 0

    tmpdir = tempfile.gettempdir()
    total = 0
    failed: list[str] = []
    started = time.monotonic()

    def report(shard: Shard, rc: int, elapsed: float, out: str, err: str) -> None:
        nonlocal total
        ran = _parse_ran(err) or _parse_ran(out)
        total += ran
        status = "ok" if rc == 0 else "FAIL"
        print(f"[{status}] {shard.label} ({ran} tests, {elapsed:.1f}s)")
        if rc != 0:
            failed.append(shard.label)
            sys.stdout.write(out)
            sys.stderr.write(err)

    # Lead-phase files walk the working tree (git-status census) and must not
    # race the __pycache__/.pyc files that sibling shard subprocesses create on
    # import. Run them alone in the lead process before the parallel fan-out.
    lead_paths, _ = _split_lead(files)
    lead = [shard for shard in shards if shard.path in lead_paths]
    parallel = [shard for shard in shards if shard.path not in lead_paths]
    for shard in lead:
        _, rc, elapsed, out, err = run_shard(shard, tmpdir)
        report(shard, rc, elapsed, out, err)

    # Threads (not processes) for the pool: each unit of work is itself a
    # subprocess, so the GIL is irrelevant and ThreadPoolExecutor avoids a
    # pickling boundary for the file payloads.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_shard, shard, tmpdir): shard for shard in parallel}
        for future in as_completed(futures):
            shard, rc, elapsed, out, err = future.result()
            report(shard, rc, elapsed, out, err)

    wall = time.monotonic() - started
    print(f"\nRan {total} tests across {len(files)} files/{len(shards)} shards in {wall:.1f}s ({args.workers} workers)")
    if failed:
        print(f"FAILED ({len(failed)} shard(s)): {', '.join(failed)}")
        return 1
    print("OK")
    return 0


def _parse_ran(text: str) -> int:
    # Matches "Ran N test(s)" and the verbose form "Ran N test(s) in X.XXXs".
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Ran ") and " test" in line:
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
