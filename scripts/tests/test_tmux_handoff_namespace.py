#!/usr/bin/env python3
"""Tests for the namespaced tmux picker handoff protocol.

Exercises the deployed begin/path/end/sweep CLI and pin_session_first.sh
against private cache directories.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _test_support import TMUX_PICKERS, modern_bash

CORE = TMUX_PICKERS / "lib/executable_handoff_namespace.py"
PIN_SESSION_FIRST = TMUX_PICKERS / "lib/executable_pin_session_first.sh"

TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
DEAD_OWNER_TTL_SECONDS = 6 * 60 * 60
DEAD_OWNER_CAP = 64
STAGING_GRACE_SECONDS = 5 * 60
DEAD_PID = 999_999_999  # far above macOS PID_MAX; os.kill -> ESRCH -> dead
ENV_TOKEN = "TMUX_PICKER_HANDOFF_TOKEN"


class HandoffTestBase(unittest.TestCase):
    """Shared fake-cache fixture and core-invocation helpers."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.cache = self.tmp / "cache"
        self.cache.mkdir()
        self.root = self.cache / "tmux" / "handoff-v1"
        self._children: list[subprocess.Popen] = []
        self.addCleanup(self._reap_children)

    def _reap_children(self) -> None:
        for child in self._children:
            try:
                child.terminate()
                child.wait(timeout=5)
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass

    def spawn_owner(self) -> subprocess.Popen:
        """A long-lived child usable as a live namespace owner."""
        child = subprocess.Popen(["sleep", "120"])
        self._children.append(child)
        return child

    def core(self, *args: str, token: str | None = None, use_env_token: bool = False):
        env = {k: v for k, v in os.environ.items() if k != ENV_TOKEN}
        env["XDG_CACHE_HOME"] = str(self.cache)
        if use_env_token and token is not None:
            env[ENV_TOKEN] = token
        return subprocess.run(
            [sys.executable, str(CORE), *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def begin(self, pid: int | None = None, role: str = "popup-loop", entry: str = "gh-popup") -> str:
        result = self.core(
            "begin",
            "--owner-pid",
            str(os.getpid() if pid is None else pid),
            "--owner-role",
            role,
            "--entry",
            entry,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        token = result.stdout.strip()
        self.assertRegex(token, TOKEN_RE)
        return token

    def path(self, slot: str, token: str) -> str:
        result = self.core("path", slot, "--token", token)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def make_root(self, mode: int = 0o700) -> None:
        self.root.mkdir(parents=True)
        os.chmod(self.root, mode)

    def craft_namespace(
        self,
        *,
        pid: int,
        age_seconds: float = 0.0,
        role: str = "popup-loop",
        entry: str = "gh-popup",
        owner_start: str = "Fri Jul 10 00:00:00 2026",
        owner_command: str = "/bin/sleep 999",
        staging: bool = False,
    ) -> Path:
        """Write a hand-crafted namespace matching the core's owner schema."""
        import secrets

        token = secrets.token_hex(16)
        name = (".new-" + token) if staging else token
        namespace = self.root / name
        namespace.mkdir(mode=0o700)
        os.chmod(namespace, 0o700)
        if not staging:
            owner = {
                "version": 1,
                "token": token,
                "owner_pid": pid,
                "owner_start": owner_start,
                "owner_command": owner_command,
                "owner_role": role,
                "entry": entry,
                "created_at_unix_ns": time.time_ns(),
            }
            owner_path = namespace / "owner.json"
            fd = os.open(owner_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(owner, handle)
        if age_seconds:
            stamp = time.time() - age_seconds
            os.utime(namespace, (stamp, stamp))
        return namespace

    def namespace_names(self) -> set[str]:
        return {p.name for p in self.root.iterdir()}


class TestHandoffNamespaceCore(HandoffTestBase):
    """WHEN driving the handoff namespace core CLI directly."""

    def test_begin_publishes_unique_tokens_with_secured_owner_file(self):
        token_a = self.begin(role="popup-loop", entry="gh-popup")
        token_b = self.begin(role="standalone-picker", entry="gh-picker")
        self.assertNotEqual(token_a, token_b)

        for token in (token_a, token_b):
            namespace = self.root / token
            self.assertTrue(namespace.is_dir())
            owner_path = namespace / "owner.json"
            self.assertTrue(owner_path.is_file())
            self.assertEqual(stat.S_IMODE(owner_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(namespace.stat().st_mode), 0o700)

        self.assertFalse([p for p in self.root.iterdir() if p.name.startswith(".new-")])

    def test_path_resolves_slot_inside_namespace(self):
        token = self.begin()
        resolved = self.path("gh_picker_pin", token)
        self.assertEqual(resolved, str(self.root / token / "gh_picker_pin"))

    def test_path_token_precedence_env_fallback(self):
        token = self.begin()
        result = self.core("path", "gh_picker_pin", token=token, use_env_token=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.root / token / "gh_picker_pin"))

    def test_path_rejects_missing_token(self):
        self.begin()  # ensure a valid root exists
        result = self.core("path", "gh_picker_pin")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")

    def test_path_rejects_malformed_token(self):
        self.begin()
        result = self.core("path", "gh_picker_pin", "--token", "NOT-HEX")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")

    def test_path_rejects_unknown_slot(self):
        token = self.begin()
        result = self.core("path", "totally_bogus_slot", "--token", token)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")

    def test_path_rejects_traversal_slot(self):
        token = self.begin()
        result = self.core("path", "../escape", "--token", token)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")

    def test_path_rejects_missing_namespace(self):
        self.begin()
        result = self.core("path", "gh_picker_pin", "--token", "0" * 32)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")

    def test_begin_fails_closed_on_symlinked_root(self):
        (self.cache / "tmux").mkdir(parents=True)
        target = self.cache / "elsewhere"
        target.mkdir()
        os.symlink(target, self.root)
        result = self.core(
            "begin", "--owner-pid", str(os.getpid()), "--owner-role", "popup-loop", "--entry", "gh-popup"
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((target / "owner.json").exists())
        self.assertFalse(list(target.iterdir()))

    def test_begin_fails_closed_on_insecure_root_mode(self):
        self.make_root(mode=0o777)
        result = self.core(
            "begin", "--owner-pid", str(os.getpid()), "--owner-role", "popup-loop", "--entry", "gh-popup"
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(self.namespace_names(), set())

    def test_end_is_owner_checked_and_idempotent(self):
        token = self.begin()
        other = self.spawn_owner()
        mismatch = self.core("end", "--owner-pid", str(other.pid), "--token", token)
        self.assertEqual(mismatch.returncode, 1)
        self.assertTrue((self.root / token).is_dir())
        ok = self.core("end", "--owner-pid", str(os.getpid()), "--token", token)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertFalse((self.root / token).exists())
        again = self.core("end", "--owner-pid", str(os.getpid()), "--token", token)
        self.assertEqual(again.returncode, 0, again.stderr)

    def test_end_dead_owner_pid_fails_and_preserves(self):
        token = self.begin()
        result = self.core("end", "--owner-pid", str(DEAD_PID), "--token", token)
        self.assertEqual(result.returncode, 1)
        self.assertTrue((self.root / token).is_dir())

    def test_sweep_preserves_old_live_namespace(self):
        owner = self.spawn_owner()
        token = self.begin(pid=owner.pid)
        stamp = time.time() - (DEAD_OWNER_TTL_SECONDS + 3600)
        os.utime(self.root / token, (stamp, stamp))
        result = self.core("sweep")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / token).is_dir())

    def test_sweep_preserves_liveness_unknown_owner(self):
        # PID 1 is un-signalable for a normal uid (EPERM) -> liveness unknown ->
        # always preserved, even past the dead TTL.
        self.make_root()
        namespace = self.craft_namespace(pid=1, age_seconds=DEAD_OWNER_TTL_SECONDS + 3600)
        result = self.core("sweep")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(namespace.is_dir())

    def test_sweep_removes_dead_after_ttl_and_keeps_fresh_dead(self):
        self.make_root()
        dead_old = self.craft_namespace(pid=DEAD_PID, age_seconds=DEAD_OWNER_TTL_SECONDS + 3600)
        dead_fresh = self.craft_namespace(pid=DEAD_PID, age_seconds=60)
        result = self.core("sweep")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(dead_old.exists())
        self.assertTrue(dead_fresh.is_dir())

    def test_sweep_caps_dead_namespaces_and_preserves_live(self):
        self.make_root()
        owner = self.spawn_owner()
        live_token = self.begin(pid=owner.pid)
        # 70 positively dead namespaces, all fresh (within TTL) so only the cap
        # can act; ages differ so oldest-first removal is deterministic.
        dead = [self.craft_namespace(pid=DEAD_PID, age_seconds=100 + i) for i in range(70)]
        result = self.core("sweep")
        self.assertEqual(result.returncode, 0, result.stderr)
        surviving_dead = [ns for ns in dead if ns.exists()]
        self.assertEqual(len(surviving_dead), DEAD_OWNER_CAP)
        self.assertTrue((self.root / live_token).is_dir())

    def test_sweep_classifies_pid_reuse_as_dead(self):
        self.make_root()
        # Same live PID, but the stored start/command fingerprint mismatches the
        # real process -> reused PID -> dead. A correctly-fingerprinted live
        # namespace is preserved as a control.
        reused = self.craft_namespace(
            pid=os.getpid(),
            age_seconds=DEAD_OWNER_TTL_SECONDS + 3600,
            owner_start="Mon Jan 01 00:00:00 2001",
            owner_command="/bin/false definitely-not-this-process",
        )
        owner = self.spawn_owner()
        control_token = self.begin(pid=owner.pid)
        stamp = time.time() - (DEAD_OWNER_TTL_SECONDS + 3600)
        os.utime(self.root / control_token, (stamp, stamp))
        result = self.core("sweep")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(reused.exists())
        self.assertTrue((self.root / control_token).is_dir())

    def test_sweep_removes_stale_staging_keeps_fresh_staging(self):
        self.make_root()
        stale = self.craft_namespace(pid=DEAD_PID, age_seconds=STAGING_GRACE_SECONDS + 120, staging=True)
        fresh = self.craft_namespace(pid=DEAD_PID, age_seconds=1, staging=True)
        result = self.core("sweep")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.is_dir())


class TestPinSessionFirstExactRepo(HandoffTestBase):
    """WHEN ordering session rows by an incoming GH pin (real helper)."""

    def _pin(self, rows: str, kind: str, repo: str, num: str) -> list[str]:
        result = subprocess.run(
            [modern_bash(), str(PIN_SESSION_FIRST), kind, repo, num],
            input=rows,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.split("\t", 1)[0] for line in result.stdout.splitlines() if line]

    def test_exact_repo_wins_when_number_is_shared(self):
        rows = (
            "alpha row\tsession\t/p/a\tpr=123:OPEN:APPROVED:PASS:https://github.com/owner/alpha/pull/123\t/p/a\tmk\n"
            "beta row\tsession\t/p/b\tpr=123:OPEN:APPROVED:PASS:https://github.com/owner/beta/pull/123\t/p/b\tmk\n"
            "other\tsession\t/p/c\tpr=999:OPEN:::https://github.com/owner/gamma/pull/999\t/p/c\tmk\n"
        )
        ordered = self._pin(rows, "pr", "owner/beta", "123")
        self.assertEqual(ordered[0], "beta row")
        self.assertNotEqual(ordered[1], "beta row")

    def test_exact_repo_issue_url_match(self):
        rows = (
            "alpha\tsession\t/p/a\tissue=55:OPEN:https://github.com/owner/alpha/issues/55\t/p/a\tmk\n"
            "beta\tworktree\t/p/b\tissue=55:OPEN:https://github.com/owner/beta/issues/55\t/p/b\tmk\n"
        )
        ordered = self._pin(rows, "issue", "owner/beta", "55")
        self.assertEqual(ordered[0], "beta")

    def test_number_only_fallback_when_repo_empty(self):
        rows = (
            "other\tsession\t/p/c\tpr=999:OPEN:::https://github.com/owner/gamma/pull/999\t/p/c\tmk\n"
            "alpha row\tsession\t/p/a\tpr=123:OPEN:APPROVED:PASS:https://github.com/owner/alpha/pull/123\t/p/a\tmk\n"
            "beta row\tsession\t/p/b\tpr=123:OPEN:APPROVED:PASS:https://github.com/owner/beta/pull/123\t/p/b\tmk\n"
        )
        ordered = self._pin(rows, "pr", "", "123")
        self.assertEqual(ordered[:2], ["alpha row", "beta row"])
        self.assertEqual(ordered[2], "other")
        self.assertNotEqual(ordered, ["other", "alpha row", "beta row"])


if __name__ == "__main__":
    unittest.main()
