#!/usr/bin/env python3
"""Regression tests for the GitHub picker fetch-lock publication race."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from _test_support import REPO, modern_bash

SCRIPT = REPO / "home/dot_config/exact_tmux/exact_scripts/pickers/github/executable_gh_items.sh"


def _find_dead_pid() -> int:
    """Return a PID that was recently alive and is guaranteed dead now."""
    child = subprocess.Popen(["true"])
    child.wait()
    return child.pid


def _wait_for(predicate, *, timeout: float = 10.0, poll: float = 0.01) -> None:
    """Poll ``predicate`` until it returns truthy or ``timeout`` elapses.

    The poll interval is a synchronization affordance, not a timing dependency:
    every test that uses this helper also has a hard deadline enforced by the
    subprocess ``timeout=`` and asserts the predicate before releasing owners.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(poll)
    raise AssertionError("timed out waiting for predicate")


class TestLockLoopEndToEnd(unittest.TestCase):
    """Integration tests that run the full ``gh_items.sh`` against stubs."""

    def _make_env(self, base: Path):
        """Materialize a self-contained script tree under ``base``.

        The real script uses ``script_dir="$(cd "$(dirname "$0")" && pwd)"``,
        so copying it to a scratch directory relocates every relative path
        (``lib/gh_items_main.py``, ``gh-picker.yml``) automatically.
        """
        script_copy = base / "gh_items.sh"
        shutil.copy(SCRIPT, script_copy)
        script_copy.chmod(0o755)
        (base / "gh-picker.yml").write_text("# stub config\n")

        lib = base / "lib"
        lib.mkdir()
        counter_file = base / "counter"
        counter_file.write_text("0")

        stub = lib / "gh_items_main.py"
        stub.write_text(
            textwrap.dedent(
                f"""
                #!/usr/bin/env python3
                # Test stub for gh_items_main.py.
                import argparse, os, sys, time
                p = argparse.ArgumentParser()
                p.add_argument("--config")
                p.add_argument("--cache-file")
                p.add_argument("--scope")
                p.add_argument("--refresh", action="store_true")
                p.add_argument("--filter-cache", action="store_true")
                args, _ = p.parse_known_args()
                if not args.filter_cache:
                    counter = {str(counter_file)!r}
                    try:
                        with open(counter) as fh:
                            n = int((fh.read() or "0").strip() or "0")
                    except FileNotFoundError:
                        n = 0
                    with open(counter, "w") as fh:
                        fh.write(str(n + 1))
                block = os.environ.get("STUB_BLOCK")
                if block and not args.filter_cache:
                    deadline = time.time() + 30
                    while not os.path.exists(block) and time.time() < deadline:
                        time.sleep(0.005)
                if args.cache_file:
                    os.makedirs(os.path.dirname(args.cache_file), exist_ok=True)
                    with open(args.cache_file, "w") as fh:
                        fh.write("stub_row\\n")
                sys.exit(0)
                """
            ).lstrip()
        )
        stub.chmod(0o755)

        # Stub `gh` and `yq` so the pre-python `command -v` check passes on
        # any host without depending on the developer's real toolchain.
        bin_dir = base / "bin"
        bin_dir.mkdir()
        for name in ("gh", "yq"):
            path = bin_dir / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)

        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "XDG_CACHE_HOME": str(base / "cache"),
        }
        env.pop("STUB_BLOCK", None)

        cache_file = base / "cache" / "tmux" / "gh_picker.tsv"
        lock_dir = Path(f"{cache_file}.lock")
        return script_copy, env, counter_file, cache_file, lock_dir

    def _read_counter(self, path: Path) -> int:
        return int((path.read_text() or "0").strip() or "0")

    def test_dead_owner_lock_is_recovered_and_fetch_runs(self):
        """A pre-existing lock owned by a dead pid must be reaped so the new
        invocation can fetch — this is the stale-owner recovery path."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            script, env, counter, cache_file, lock_dir = self._make_env(base)
            (base / "cache" / "tmux").mkdir(parents=True)
            lock_dir.mkdir()
            (lock_dir / "pid").write_text(f"{_find_dead_pid()}\n")

            r = subprocess.run(
                [modern_bash(), str(script)],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self._read_counter(counter), 1)
            self.assertTrue(cache_file.exists())
            self.assertFalse(lock_dir.exists(), "lock leaked after dead-owner recovery")

    def test_orphaned_lock_beyond_grace_is_recovered(self):
        """A lock with no pid file, older than the fixed 2s publish grace, is
        reaped. Backdate mtime by an hour so the age check is unambiguous."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            script, env, counter, cache_file, lock_dir = self._make_env(base)
            (base / "cache" / "tmux").mkdir(parents=True)
            lock_dir.mkdir()
            past = time.time() - 3600
            os.utime(lock_dir, (past, past))

            r = subprocess.run(
                [modern_bash(), str(script)],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self._read_counter(counter), 1)
            self.assertFalse(lock_dir.exists())

    def test_waiter_with_alive_owner_does_not_refetch(self):
        """One-fetch invariant: a waiter that finds an alive owner must NOT
        run gh_items_main.py — it must emit from the existing cache and exit."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            script, env, counter, cache_file, lock_dir = self._make_env(base)
            block = base / "unblock"
            env["STUB_BLOCK"] = str(block)

            owner = subprocess.Popen(
                [modern_bash(), str(script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
            )
            try:
                # Wait until the owner has both taken the lock AND started the
                # fetch — after this point any waiter will observe 'alive <pid>'.
                _wait_for(lambda: (lock_dir / "pid").exists() and (lock_dir / "pid").read_text().strip())
                _wait_for(lambda: self._read_counter(counter) == 1)
                fetch_count_after_owner = self._read_counter(counter)

                waiter_env = dict(env)
                waiter_env.pop("STUB_BLOCK", None)  # emit_cache path must not block
                waiters = [
                    subprocess.Popen(
                        [modern_bash(), str(script)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=waiter_env,
                        text=True,
                    )
                    for _ in range(3)
                ]
                for w in waiters:
                    rc = w.wait(timeout=15)
                    stderr = w.stderr.read() if w.stderr else ""
                    if w.stdout:
                        w.stdout.close()
                    if w.stderr:
                        w.stderr.close()
                    self.assertEqual(rc, 0, stderr)

                self.assertEqual(self._read_counter(counter), fetch_count_after_owner)

                block.touch()  # release owner
                self.assertEqual(owner.wait(timeout=15), 0)
                self.assertFalse(lock_dir.exists(), "owner lock leaked after exit")
            finally:
                block.touch()
                if owner.poll() is None:
                    owner.kill()
                if owner.stdout:
                    owner.stdout.close()
                if owner.stderr:
                    owner.stderr.close()

    def test_fresh_lock_without_pid_is_not_reaped_by_waiter(self):
        """Core regression: a lockdir freshly created by an owner but not yet
        carrying a pid file must NOT be reaped by a competing waiter. Without
        the fix, the waiter races through mkdir and runs a second fetch.

        The fixed script's publish grace is 2s and its retry backoff is 0.1s,
        so this test's ~0.3s observation window (spanning multiple retries)
        and prompt pid publication all fit well inside the grace."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            script, env, counter, cache_file, lock_dir = self._make_env(base)

            (base / "cache" / "tmux").mkdir(parents=True)
            cache_file.write_text("preexisting_row\n")

            # Simulate the tiny window between mkdir and pid publication:
            # lock exists (mtime=now) with no pid file.
            lock_dir.mkdir()
            mkdir_at = time.monotonic()

            placeholder = subprocess.Popen(["sleep", "30"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            waiter = subprocess.Popen(
                [modern_bash(), str(script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
            )
            try:
                # Three retry cycles (0.1s backoff), well inside the 2s publish grace.
                with contextlib.suppress(AssertionError):
                    _wait_for(lambda: waiter.poll() is not None, timeout=0.3, poll=0.02)
                self.assertIsNone(waiter.poll(), "waiter exited during publish window — fresh lock was reaped")
                self.assertTrue(lock_dir.exists(), "fresh lock was reaped by waiter")
                self.assertEqual(
                    self._read_counter(counter),
                    0,
                    "waiter ran a second fetch instead of waiting for publication",
                )

                # Publish pid well inside the fixed 2s grace — the waiter's
                # next status query will observe 'alive <pid>' and take the
                # emit_cache path.
                elapsed = time.monotonic() - mkdir_at
                self.assertLess(
                    elapsed,
                    1.5,
                    "test setup consumed the publish grace; would race the fix",
                )
                (lock_dir / "pid").write_text(f"{placeholder.pid}\n")

                self.assertEqual(waiter.wait(timeout=10), 0)
                self.assertEqual(self._read_counter(counter), 0)
            finally:
                if waiter is not None and waiter.poll() is None:
                    waiter.kill()
                    waiter.wait(timeout=5)
                if waiter is not None:
                    if waiter.stdout:
                        waiter.stdout.close()
                    if waiter.stderr:
                        waiter.stderr.close()
                placeholder.kill()
                placeholder.wait(timeout=5)
                # Our test owns this lock; the waiter's cleanup trap only
                # rmdirs when the pid file names $$, so we must clean up.
                shutil.rmtree(lock_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
