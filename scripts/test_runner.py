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
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def discover_files() -> list[Path]:
    files = sorted(SCRIPTS.glob("test_*.py"))
    files += sorted((SCRIPTS / "tests").glob("test_*.py"))
    return files


# Files whose tests snapshot the working tree (git-status file census) and so
# cannot run concurrently with the import-time __pycache__/.pyc churn that
# sibling shard subprocesses create. They run in the lead phase instead.
LEAD_FILES = frozenset({"test_verify_mermaids.py"})


def _split_lead(files: list[Path]) -> tuple[list[Path], list[Path]]:
    lead = [f for f in files if f.name in LEAD_FILES]
    shards = [f for f in files if f.name not in LEAD_FILES]
    return lead, shards


def module_name(path: Path) -> str:
    rel = path.relative_to(SCRIPTS).with_suffix("")
    return ".".join(rel.parts)


def shard_spec_root(path: Path, tmpdir: str) -> str:
    return str(Path(tmpdir) / f"agent-hook-specs-{path.stem}")


def run_file(path: Path, tmpdir: str) -> tuple[Path, int, float, str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
    env["AGENT_MEMORY_SPEC_ROOT"] = shard_spec_root(path, tmpdir)
    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", module_name(path)],
        cwd=str(SCRIPTS),
        env=env,
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - start
    return path, proc.returncode, elapsed, proc.stdout, proc.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print shard plan and exit")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    args = parser.parse_args()

    files = discover_files()
    if args.list:
        for f in files:
            print(module_name(f))
        return 0

    tmpdir = tempfile.gettempdir()
    total = 0
    failed: list[Path] = []
    started = time.monotonic()

    def report(path: Path, rc: int, elapsed: float, out: str, err: str) -> None:
        nonlocal total
        ran = _parse_ran(err) or _parse_ran(out)
        total += ran
        status = "ok" if rc == 0 else "FAIL"
        print(f"[{status}] {module_name(path)} ({ran} tests, {elapsed:.1f}s)")
        if rc != 0:
            failed.append(path)
            sys.stdout.write(out)
            sys.stderr.write(err)

    # Lead-phase files walk the working tree (git-status census) and must not
    # race the __pycache__/.pyc files that sibling shard subprocesses create on
    # import. Run them alone in the lead process before the parallel fan-out.
    lead, shards = _split_lead(files)
    for path in lead:
        _, rc, elapsed, out, err = run_file(path, tmpdir)
        report(path, rc, elapsed, out, err)

    # Threads (not processes) for the pool: each unit of work is itself a
    # subprocess, so the GIL is irrelevant and ThreadPoolExecutor avoids a
    # pickling boundary for the file payloads.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_file, f, tmpdir): f for f in shards}
        for future in as_completed(futures):
            path, rc, elapsed, out, err = future.result()
            report(path, rc, elapsed, out, err)

    wall = time.monotonic() - started
    print(f"\nRan {total} tests across {len(files)} files in {wall:.1f}s ({args.workers} workers)")
    if failed:
        print(f"FAILED ({len(failed)} file(s)): {', '.join(module_name(f) for f in failed)}")
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
