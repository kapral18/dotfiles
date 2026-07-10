#!/usr/bin/env python3
"""Tests for the namespaced tmux picker handoff protocol.

Covers the deployed core CLI
``home/dot_config/exact_tmux/exact_scripts/pickers/lib/executable_handoff_namespace.py``
(``begin``/``path``/``retain-context``/``end``/``sweep``) plus the wiring
contract the GitHub and session pickers rely on. Every check drives the *real*
core binary or the real
``pin_session_first.sh`` helper against a private ``XDG_CACHE_HOME`` fake cache,
so the assertions exercise the implemented directory protocol rather than a
model. Static-source assertions guard the shell wrappers' handoff contract
(token propagation, owner-checked ``end``, secure Ralph context retention,
standalone begin, no top-level legacy reads/writes).

Compatibility impact: removed (requested). The former global pin/sentinel
mailbox is gone; these tests assert that poisoned legacy top-level files are
never read or written by the protocol.
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

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import TMUX_PICKERS, modern_bash

CORE = TMUX_PICKERS / "lib/executable_handoff_namespace.py"
PIN_SESSION_FIRST = TMUX_PICKERS / "lib/executable_pin_session_first.sh"
GH_POPUP = TMUX_PICKERS / "github/executable_gh_popup.sh"
GH_PICKER = TMUX_PICKERS / "github/executable_gh_picker.sh"
GH_CREATE = TMUX_PICKERS / "github/executable_gh_create.sh"
SESSION_POPUP = TMUX_PICKERS / "session/executable_popup.sh"
PICK_SESSION = TMUX_PICKERS / "session/executable_pick_session.sh"
RALPH_APPLY = TMUX_PICKERS / "lib/executable_handoff_to_ralph_apply.sh"

TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
DEAD_OWNER_TTL_SECONDS = 6 * 60 * 60
DEAD_OWNER_CAP = 64
STAGING_GRACE_SECONDS = 5 * 60
DEAD_PID = 999_999_999  # far above macOS PID_MAX; os.kill -> ESRCH -> dead
ENV_TOKEN = "TMUX_PICKER_HANDOFF_TOKEN"

# Every public slot the core allows, plus the derived Ralph context sibling.
ALLOWED_SLOTS = (
    "gh_picker_pin",
    "pick_session_pin",
    "gh_picker_create_pin",
    "gh_picker_ralph_pin",
    "gh_picker_switch_sessions",
    "pick_session_switch_gh",
)
# Legacy top-level mailbox files the removed global protocol used. Production
# must never read or write these; tests poison them and assert byte-stability.
LEGACY_TOP_LEVEL = ALLOWED_SLOTS

WIRED_FILES = (GH_POPUP, GH_PICKER, GH_CREATE, SESSION_POPUP, PICK_SESSION, PIN_SESSION_FIRST, RALPH_APPLY)


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

        # No unpublished staging directory survives a successful begin.
        self.assertFalse([p for p in self.root.iterdir() if p.name.startswith(".new-")])

    def test_begin_owner_metadata_schema(self):
        token = self.begin(role="popup-loop", entry="session-popup")
        owner = json.loads((self.root / token / "owner.json").read_text())
        self.assertEqual(owner["version"], 1)
        self.assertEqual(owner["token"], token)
        self.assertEqual(owner["owner_pid"], os.getpid())
        self.assertTrue(owner["owner_start"])
        self.assertTrue(owner["owner_command"])
        self.assertEqual(owner["owner_role"], "popup-loop")
        self.assertEqual(owner["entry"], "session-popup")
        self.assertIsInstance(owner["created_at_unix_ns"], int)
        self.assertGreater(owner["created_at_unix_ns"], 0)

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
        # No PID-derived fallback namespace was minted.
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
        # A different but live PID cannot end another owner's namespace.
        other = self.spawn_owner()
        mismatch = self.core("end", "--owner-pid", str(other.pid), "--token", token)
        self.assertEqual(mismatch.returncode, 1)
        self.assertTrue((self.root / token).is_dir())
        # The true owner removes it, and a repeat end is a success no-op.
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


class TestHandoffProtocolWiring(HandoffTestBase):
    """WHEN modelling the picker wiring flows against the real core."""

    def _write_slot(self, token: str, slot: str, content: str) -> Path:
        target = Path(self.path(slot, token))
        target.write_text(content, encoding="utf-8")
        return target

    def test_two_concurrent_namespaces_never_cross_consume(self):
        token_a = self.begin(entry="gh-popup")
        token_b = self.begin(entry="gh-popup")
        self.assertNotEqual(token_a, token_b)

        pin_a = self._write_slot(token_a, "gh_picker_pin", "pr\towner/alpha\t201\n")
        pin_b = self._write_slot(token_b, "gh_picker_pin", "pr\towner/beta\t202\n")

        self.assertEqual(Path(self.path("gh_picker_pin", token_a)).read_text(), "pr\towner/alpha\t201\n")
        self.assertEqual(Path(self.path("gh_picker_pin", token_b)).read_text(), "pr\towner/beta\t202\n")

        # A consuming its own pin never touches B's.
        pin_a.unlink()
        self.assertFalse(pin_a.exists())
        self.assertTrue(pin_b.exists())
        self.assertEqual(pin_b.read_text(), "pr\towner/beta\t202\n")

    def test_gh_session_gh_keeps_one_stable_token(self):
        # gh_popup begins the loop; every pivot reuses the same token so the
        # GH -> session -> GH files all resolve to one namespace.
        token = self.begin(role="popup-loop", entry="gh-popup")

        # GH alt-g: handoff_to_sessions writes pick_session_pin; sentinel touched.
        self._write_slot(token, "pick_session_pin", "pr\towner/repo\t42\tgh-popup\n")
        self._write_slot(token, "gh_picker_switch_sessions", "1\n")
        # session picker consumes its pin (same token).
        pin = Path(self.path("pick_session_pin", token))
        self.assertEqual(pin.read_text(), "pr\towner/repo\t42\tgh-popup\n")
        pin.unlink()
        Path(self.path("gh_picker_switch_sessions", token)).unlink()

        # Session alt-g back to GH: handoff_to_gh writes gh_picker_pin.
        self._write_slot(token, "gh_picker_pin", "pr\towner/repo\t42\tsession-popup\n")
        self._write_slot(token, "pick_session_switch_gh", "1\n")
        gh_pin = Path(self.path("gh_picker_pin", token))
        self.assertEqual(gh_pin.read_text(), "pr\towner/repo\t42\tsession-popup\n")

        # Every slot lived under the single namespace directory.
        namespace = self.root / token
        for slot in ("pick_session_pin", "gh_picker_pin", "gh_picker_switch_sessions", "pick_session_switch_gh"):
            self.assertEqual(Path(self.path(slot, token)).parent, namespace)

    def test_create_pin_consumed_exactly_once(self):
        token = self.begin(entry="gh-popup")
        create = self._write_slot(token, "gh_picker_create_pin", "issue\towner/repo\t7\thttps://x/7\n")
        # gh_picker exit reads and removes the create pin, routing checkout once.
        self.assertTrue(create.exists())
        payload = create.read_text()
        create.unlink()
        self.assertTrue(payload.startswith("issue\towner/repo\t7\t"))
        # A second consume misses -> checkout cannot run twice.
        self.assertFalse(Path(self.path("gh_picker_create_pin", token)).exists())

    def test_ralph_context_lives_in_namespace_and_end_removes_it(self):
        token = self.begin(role="popup-loop", entry="gh-popup")
        pin = Path(self.path("gh_picker_ralph_pin", token))
        pin.write_text("pr\towner/repo\t9\turl\ttitle\t/wt\t\tseed\t1\n", encoding="utf-8")
        context = pin.with_suffix(pin.suffix + ".context.md")
        context.write_text("RICH RALPH CONTEXT\n", encoding="utf-8")
        self.assertTrue(context.is_file())
        # Normal owner end removes the whole namespace, context sibling included.
        result = self.core("end", "--owner-pid", str(os.getpid()), "--token", token)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / token).exists())
        self.assertFalse(context.exists())

    def test_ralph_retained_context_copy_survives_normal_namespace_end(self):
        token = self.begin(role="popup-loop", entry="gh-popup")
        pin = Path(self.path("gh_picker_ralph_pin", token))
        pin.write_text("pr\towner/repo\t9\turl\ttitle\t/wt\t\tseed\t1\n", encoding="utf-8")
        context = pin.with_suffix(pin.suffix + ".context.md")
        context.write_text("RICH RALPH CONTEXT\n", encoding="utf-8")

        retained_result = self.core("retain-context", str(context), "--token", token)
        self.assertEqual(retained_result.returncode, 0, retained_result.stderr)
        retained = Path(retained_result.stdout.strip())
        self.assertEqual(stat.S_IMODE(retained.stat().st_mode), 0o600)
        self.assertEqual(retained.read_text(), "RICH RALPH CONTEXT\n")
        self.assertFalse(context.exists())

        end = self.core("end", "--owner-pid", str(os.getpid()), "--token", token)
        self.assertEqual(end.returncode, 0, end.stderr)
        self.assertFalse((self.root / token).exists())
        self.assertTrue(retained.is_file())

    def test_standalone_begin_end_leaves_no_namespace_or_legacy_residue(self):
        # Poison the legacy top-level mailbox first.
        cache_tmux = self.cache / "tmux"
        cache_tmux.mkdir(parents=True)
        for name in LEGACY_TOP_LEVEL:
            (cache_tmux / name).write_text(f"legacy {name}\n", encoding="utf-8")

        token = self.begin(role="standalone-picker", entry="gh-picker")
        self._write_slot(token, "gh_picker_pin", "pr\towner/repo\t1\n")
        result = self.core("end", "--owner-pid", str(os.getpid()), "--token", token)
        self.assertEqual(result.returncode, 0, result.stderr)

        # No namespace directory and no top-level residue introduced.
        self.assertEqual(self.namespace_names(), set())
        top_level = {p.name for p in cache_tmux.iterdir()} - {"handoff-v1"}
        self.assertEqual(top_level, set(LEGACY_TOP_LEVEL))

    def test_poisoned_legacy_top_level_files_are_untouched(self):
        cache_tmux = self.cache / "tmux"
        cache_tmux.mkdir(parents=True)
        poisoned = {}
        for name in LEGACY_TOP_LEVEL:
            payload = f"POISON {name} do-not-read-or-write\n"
            (cache_tmux / name).write_text(payload, encoding="utf-8")
            poisoned[name] = payload

        # Run a full protocol lifecycle end to end.
        token = self.begin(entry="gh-popup")
        for slot in ALLOWED_SLOTS:
            Path(self.path(slot, token)).write_text("x\n", encoding="utf-8")
        self.assertEqual(self.core("sweep").returncode, 0)
        self.assertEqual(self.core("end", "--owner-pid", str(os.getpid()), "--token", token).returncode, 0)

        for name, payload in poisoned.items():
            self.assertEqual((cache_tmux / name).read_text(), payload, f"legacy {name} was mutated")


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


class TestWiredSourceContract(unittest.TestCase):
    """WHEN inspecting the deployed picker sources for the handoff contract."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.src = {path: path.read_text(encoding="utf-8") for path in WIRED_FILES}

    def test_no_top_level_legacy_handoff_paths(self):
        legacy = re.compile(
            r"(cache_dir[}\"/]*/?|tmux/)(gh_picker_pin|pick_session_pin|gh_picker_create_pin"
            r"|gh_picker_ralph_pin|gh_picker_switch_sessions|pick_session_switch_gh)\b"
        )
        for path, text in self.src.items():
            self.assertNotRegex(text, legacy, f"{path.name} references a legacy top-level handoff path")

    def test_every_slot_resolves_through_the_namespace_core(self):
        for path, text in self.src.items():
            if path in (GH_CREATE, PIN_SESSION_FIRST):
                continue
            for slot in ("gh_picker_pin", "pick_session_pin", "gh_picker_ralph_pin"):
                if slot in text:
                    self.assertRegex(
                        text,
                        rf'(path {slot}\b|path "\$slot"|handoff_slot_path|resolve_handoff_slot)',
                        f"{path.name} uses {slot} without the namespace core",
                    )

    def test_wrappers_inject_token_with_display_popup_e(self):
        for wrapper in (GH_POPUP, SESSION_POPUP):
            text = self.src[wrapper]
            self.assertIn("display-popup", text)
            self.assertRegex(
                text,
                r'-e "TMUX_PICKER_HANDOFF_TOKEN=',
                f"{wrapper.name} must inject the token with display-popup -e",
            )

    def test_wrappers_begin_popup_loop_and_end_on_exit(self):
        for wrapper in (GH_POPUP, SESSION_POPUP):
            text = self.src[wrapper]
            self.assertRegex(
                text, r"begin .*--owner-role popup-loop", f"{wrapper.name} must begin a popup-loop namespace"
            )
            self.assertRegex(text, r"export TMUX_PICKER_HANDOFF_TOKEN=", f"{wrapper.name} must export the token")
            self.assertIn("trap", text)
            self.assertRegex(text, r"\bend --owner-pid", f"{wrapper.name} must end the namespace by owner pid")

    def test_gh_popup_ends_namespace_after_secure_ralph_context_copy(self):
        popup = self.src[GH_POPUP]
        apply_helper = self.src[RALPH_APPLY]
        core = CORE.read_text(encoding="utf-8")

        # Every popup exit performs the same owner-checked namespace end.
        self.assertNotIn("_gh_popup_retain", popup)
        self.assertRegex(popup, r"_gh_popup_cleanup\(\)\s*\{")
        self.assertRegex(popup, r'end --owner-pid "\$\$" --token "\$TMUX_PICKER_HANDOFF_TOKEN"')
        self.assertIn("trap _gh_popup_cleanup EXIT", popup)

        # Ralph context is copied securely before the asynchronous prompt is queued.
        retain_at = apply_helper.index('retain-context "$context_file"')
        prompt_at = apply_helper.index("tmux command-prompt")
        self.assertLess(retain_at, prompt_at)
        self.assertIn(
            'retained_context="$("$handoff_namespace" retain-context "$context_file")" || exit 0', apply_helper
        )
        self.assertIn('[ -n "$retained_context" ] || exit 0', apply_helper)
        self.assertIn('RETAINED_DIR = "retained-context"', core)
        self.assertIn("RETAINED_FILE_MODE = 0o600", core)

    def test_pickers_begin_standalone_when_token_absent(self):
        for picker in (GH_PICKER, PICK_SESSION):
            text = self.src[picker]
            self.assertRegex(
                text,
                r"begin .*--owner-role standalone-picker",
                f"{picker.name} must begin a standalone namespace when unseeded",
            )
            self.assertIn("TMUX_PICKER_HANDOFF_TOKEN", text)
            self.assertRegex(
                text,
                r'\[ -z "\$\{?(TMUX_PICKER_HANDOFF_TOKEN|handoff_token)',
                f"{picker.name} must gate the standalone begin on an absent token",
            )
            self.assertRegex(text, r"\bend --owner-pid", f"{picker.name} must end its standalone namespace")

    def test_gh_create_keeps_five_args_and_namespaced_create_pin(self):
        text = self.src[GH_CREATE]
        # Five positional arguments preserved.
        for pos in (
            'kind="${1:-}"',
            'default_repo="${2:-}"',
            'mode_file="${3:-}"',
            'scope_file="${4:-}"',
            'items_cmd="${5:-}"',
        ):
            self.assertIn(pos, text)
        # Create pin resolves through the inherited token and fails closed.
        self.assertRegex(text, r"path gh_picker_create_pin")
        self.assertRegex(text, r"die .*handoff namespace unavailable")


if __name__ == "__main__":
    unittest.main()
