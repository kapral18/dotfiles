#!/usr/bin/env python3
"""Tests for the lifecycle-managed Ralph handoff context copy.

Exercises the deployed core CLI
``home/dot_config/exact_tmux/exact_scripts/pickers/lib/executable_handoff_namespace.py``
``retain-context`` verb and the real
``home/dot_config/exact_tmux/exact_scripts/pickers/lib/executable_handoff_to_ralph_apply.sh``
helper against a private ``XDG_CACHE_HOME`` fake cache with a stub ``tmux`` on
``PATH``. No live tmux is used.

The retained-context lifecycle replaces the former retained-dead-namespace
workaround: ``retain-context`` copies the active namespace's
``gh_picker_ralph_pin.context.md`` sibling to a secure 0600 file under a
``retained-context`` directory in the handoff root, removes the source, and
prints the retained path. That copy outlives its namespace (which gh_popup now
always ends normally) and is reaped only after a long 7-day TTL with no early
cap deletion.

Compatibility impact: removed (requested). The retained-dead-namespace path and
its ``_gh_popup_retain`` flag are gone; these tests assert the copy survives a
normal namespace ``end`` and that gh_popup cleanup is unconditional.
"""

from __future__ import annotations

import os
import re
import shutil
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
APPLY_HELPER = TMUX_PICKERS / "lib/executable_handoff_to_ralph_apply.sh"
GH_POPUP = TMUX_PICKERS / "github/executable_gh_popup.sh"

TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
RETAINED_NAME_RE = re.compile(r"^[0-9a-f]{32}\.md$")
RETAINED_DIR = "retained-context"
RALPH_CONTEXT_NAME = "gh_picker_ralph_pin.context.md"
RETAINED_CONTEXT_TTL_SECONDS = 7 * 24 * 60 * 60
ENV_TOKEN = "TMUX_PICKER_HANDOFF_TOKEN"


class ContextTestBase(unittest.TestCase):
    """Shared fake-cache fixture and real core/helper invocation helpers."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.cache = self.tmp / "cache"
        self.cache.mkdir()
        self.root = self.cache / "tmux" / "handoff-v1"
        self.retained_dir = self.root / RETAINED_DIR

    # -- core --------------------------------------------------------------- #

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

    def begin(self, pid: int | None = None) -> str:
        result = self.core(
            "begin",
            "--owner-pid",
            str(os.getpid() if pid is None else pid),
            "--owner-role",
            "popup-loop",
            "--entry",
            "gh-popup",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        token = result.stdout.strip()
        self.assertRegex(token, TOKEN_RE)
        return token

    def make_root(self, mode: int = 0o700) -> None:
        self.root.mkdir(parents=True)
        os.chmod(self.root, mode)

    def context_path(self, token: str) -> Path:
        return self.root / token / RALPH_CONTEXT_NAME

    def write_context(self, token: str, text: str = "RICH RALPH CONTEXT\n") -> Path:
        path = self.context_path(token)
        path.write_text(text, encoding="utf-8")
        return path

    def retain(self, source: Path, token: str, *, use_env_token: bool = False):
        if use_env_token:
            return self.core("retain-context", str(source), token=token, use_env_token=True)
        return self.core("retain-context", str(source), "--token", token)

    def retained_files(self) -> list[Path]:
        if not self.retained_dir.exists():
            return []
        return sorted(p for p in self.retained_dir.iterdir() if RETAINED_NAME_RE.match(p.name))


class TestRetainContextCore(ContextTestBase):
    """WHEN copying a Ralph context through the real core retain-context verb."""

    def test_retain_copies_source_out_and_survives_namespace_end(self):
        token = self.begin()
        source = self.write_context(token, "SURVIVE ME\n")

        result = self.retain(source, token)
        self.assertEqual(result.returncode, 0, result.stderr)
        retained = Path(result.stdout.strip())

        # Retained under the handoff root, not inside the namespace.
        self.assertEqual(retained.parent, self.retained_dir)
        self.assertRegex(retained.name, RETAINED_NAME_RE)
        self.assertEqual(retained.read_text(encoding="utf-8"), "SURVIVE ME\n")
        # Source is removed once the copy is published.
        self.assertFalse(source.exists())

        # A normal owner-checked end removes the namespace but keeps the copy.
        end = self.core("end", "--owner-pid", str(os.getpid()), "--token", token)
        self.assertEqual(end.returncode, 0, end.stderr)
        self.assertFalse((self.root / token).exists())
        self.assertTrue(retained.is_file())
        self.assertEqual(retained.read_text(encoding="utf-8"), "SURVIVE ME\n")

    def test_retained_dir_is_0700_and_file_is_0600(self):
        token = self.begin()
        source = self.write_context(token)
        result = self.retain(source, token)
        self.assertEqual(result.returncode, 0, result.stderr)
        retained = Path(result.stdout.strip())

        self.assertEqual(stat.S_IMODE(self.retained_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(retained.stat().st_mode), 0o600)

    def test_retain_via_env_token(self):
        token = self.begin()
        source = self.write_context(token, "ENV TOKEN\n")
        result = self.retain(source, token, use_env_token=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()).read_text(encoding="utf-8"), "ENV TOKEN\n")

    def test_retain_requires_published_root(self):
        # No namespace ever published -> no root -> fail closed, empty stdout.
        result = self.retain(self.tmp / "whatever.md", "0" * 32)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse(self.retained_dir.exists())

    def test_retain_fails_closed_on_insecure_root_mode(self):
        self.make_root(mode=0o777)
        # A hand-crafted namespace dir and context under the world-writable root.
        token = "a" * 32
        namespace = self.root / token
        namespace.mkdir(mode=0o700)
        source = namespace / RALPH_CONTEXT_NAME
        source.write_text("x\n", encoding="utf-8")
        result = self.retain(source, token)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse(self.retained_dir.exists())
        # Source is left untouched on failure.
        self.assertTrue(source.exists())

    def test_retain_rejects_missing_and_malformed_token(self):
        self.begin()  # publish a valid root
        missing = self.core("retain-context", str(self.tmp / "x.md"))
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(missing.stdout.strip(), "")
        malformed = self.core("retain-context", str(self.tmp / "x.md"), "--token", "NOT-HEX")
        self.assertEqual(malformed.returncode, 1)
        self.assertEqual(malformed.stdout.strip(), "")

    def test_retain_refuses_wrong_token(self):
        token = self.begin()
        source = self.write_context(token)
        wrong = self.retain(source, "0" * 32)  # a token with no namespace
        self.assertEqual(wrong.returncode, 1)
        self.assertEqual(wrong.stdout.strip(), "")
        self.assertTrue(source.exists())
        self.assertEqual(self.retained_files(), [])

    def test_retain_refuses_other_namespace_source(self):
        token_a = self.begin()
        token_b = self.begin()
        source_a = self.write_context(token_a, "A CONTEXT\n")
        # B cannot retain A's context sibling.
        cross = self.retain(source_a, token_b)
        self.assertEqual(cross.returncode, 1)
        self.assertEqual(cross.stdout.strip(), "")
        self.assertTrue(source_a.exists())
        self.assertEqual(self.retained_files(), [])

    def test_retain_refuses_non_context_source_path(self):
        token = self.begin()
        # A real file inside the namespace, but not the ralph context sibling.
        other = self.root / token / "gh_picker_ralph_pin"
        other.write_text("pin\n", encoding="utf-8")
        result = self.retain(other, token)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")
        self.assertTrue(other.exists())
        self.assertEqual(self.retained_files(), [])

    def test_retain_refuses_symlinked_source(self):
        token = self.begin()
        real = self.tmp / "real_context.md"
        real.write_text("SECRET\n", encoding="utf-8")
        source = self.context_path(token)
        os.symlink(real, source)  # namespace context is a symlink
        result = self.retain(source, token)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")
        # The symlink target is neither copied nor removed.
        self.assertTrue(real.exists())
        self.assertEqual(self.retained_files(), [])

    def test_retain_refuses_non_regular_source(self):
        token = self.begin()
        source = self.context_path(token)
        source.mkdir()  # a directory where the context file should be
        result = self.retain(source, token)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(self.retained_files(), [])

    def test_sweep_keeps_fresh_and_reaps_only_after_ttl_no_cap(self):
        token = self.begin()
        source = self.write_context(token, "FRESH\n")
        fresh = Path(self.retain(source, token).stdout.strip())
        self.assertTrue(fresh.is_file())

        # Extra fresh copies (well under the TTL) must never be cap-deleted.
        extra = []
        for idx in range(4):
            path = self.retained_dir / (f"{idx:032x}"[-32:] + ".md")
            path.write_text(f"extra {idx}\n", encoding="utf-8")
            os.chmod(path, 0o600)
            stamp = time.time() - (idx + 1) * 60
            os.utime(path, (stamp, stamp))
            extra.append(path)

        # One retained copy aged past the 7-day TTL.
        old = self.retained_dir / ("f" * 32 + ".md")
        old.write_text("OLD\n", encoding="utf-8")
        os.chmod(old, 0o600)
        stamp = time.time() - (RETAINED_CONTEXT_TTL_SECONDS + 3600)
        os.utime(old, (stamp, stamp))

        result = self.core("sweep")
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertTrue(fresh.is_file())
        for path in extra:
            self.assertTrue(path.is_file(), f"fresh retained {path.name} was cap-deleted")
        self.assertFalse(old.exists())


class TestRalphApplyHelper(ContextTestBase):
    """WHEN the real Ralph apply helper retains context before queuing tmux."""

    def _deploy(self) -> None:
        """Lay out a deploy-style lib dir plus a recording ``tmux`` stub.

        chezmoi strips the ``executable_`` prefix at apply time, so the helper
        finds its sibling core as ``handoff_namespace.py``. Mirror that here by
        copying both under one directory so the real helper drives the real core.
        """
        self.lib = self.tmp / "deploy_lib"
        self.lib.mkdir()
        self.core_copy = self.lib / "handoff_namespace.py"
        shutil.copy2(CORE, self.core_copy)
        os.chmod(self.core_copy, 0o755)
        self.helper = self.lib / "handoff_to_ralph_apply.sh"
        shutil.copy2(APPLY_HELPER, self.helper)
        os.chmod(self.helper, 0o755)

        self.stub_bin = self.tmp / "stub_bin"
        self.stub_bin.mkdir()
        self.tmux_out = self.tmp / "tmux_calls"
        tmux_stub = self.stub_bin / "tmux"
        tmux_stub.write_text(
            '#!/usr/bin/env bash\nprintf \'%s\\0\' "$@" >> "$STUB_TMUX_OUT"\n',
            encoding="utf-8",
        )
        os.chmod(tmux_stub, 0o755)

    def _run_helper(self, pin_file: Path, token: str):
        env = {k: v for k, v in os.environ.items() if k != ENV_TOKEN}
        env["XDG_CACHE_HOME"] = str(self.cache)
        env[ENV_TOKEN] = token
        env["STUB_TMUX_OUT"] = str(self.tmux_out)
        env["PATH"] = str(self.stub_bin) + os.pathsep + env.get("PATH", "")
        return subprocess.run(
            [modern_bash(), str(self.helper), str(pin_file)],
            capture_output=True,
            text=True,
            env=env,
        )

    def _tmux_args(self) -> list[str]:
        raw = self.tmux_out.read_bytes()
        return [chunk.decode("utf-8") for chunk in raw.split(b"\0") if chunk]

    def _write_pin(self, token: str, context: Path, seed: str) -> Path:
        pin = self.root / token / "gh_picker_ralph_pin"
        fields = [
            "pr",
            "owner/repo",
            "9",
            "https://example.test/9",
            "Some Title",
            "/some/worktree",
            str(context),
            seed,
            "1",
        ]
        pin.write_text("\t".join(fields) + "\n", encoding="utf-8")
        return pin

    def test_helper_retains_and_queues_the_retained_path(self):
        self._deploy()
        token = self.begin()
        context = self.write_context(token, "HELPER CONTEXT\n")
        pin = self._write_pin(token, context, "pr owner/repo#9: Some Title")

        result = self._run_helper(pin, token)
        self.assertEqual(result.returncode, 0, result.stderr)

        # tmux command-prompt was queued exactly once.
        self.assertTrue(self.tmux_out.exists(), "helper did not queue a command-prompt")
        args = self._tmux_args()
        self.assertIn("command-prompt", args)
        seed = args[args.index("-I") + 1]

        # The seed references the retained copy, never the namespace sibling.
        retained = self.retained_files()
        self.assertEqual(len(retained), 1)
        self.assertIn(str(retained[0]), seed)
        self.assertIn("retained-context", seed)
        self.assertNotIn(str(context), seed)

        # Source consumed; retained copy is the secure 0600 survivor.
        self.assertFalse(context.exists())
        self.assertEqual(stat.S_IMODE(retained[0].stat().st_mode), 0o600)
        self.assertEqual(retained[0].read_text(encoding="utf-8"), "HELPER CONTEXT\n")

        # The retained copy outlives a normal namespace end.
        end = self.core("end", "--owner-pid", str(os.getpid()), "--token", token)
        self.assertEqual(end.returncode, 0, end.stderr)
        self.assertFalse((self.root / token).exists())
        self.assertTrue(retained[0].is_file())

    def test_helper_fails_closed_when_retain_fails(self):
        self._deploy()
        # An existing context file, but no published root -> retain-context
        # fails, so the helper must NOT queue a broken command-prompt.
        context = self.tmp / "orphan.context.md"
        context.write_text("ORPHAN\n", encoding="utf-8")
        pin = self.tmp / "pin"
        fields = [
            "pr",
            "owner/repo",
            "9",
            "https://example.test/9",
            "Title",
            "/some/worktree",
            str(context),
            "seed",
            "1",
        ]
        pin.write_text("\t".join(fields) + "\n", encoding="utf-8")

        result = self._run_helper(pin, "0" * 32)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.tmux_out.exists(), "helper queued a prompt despite retain failure")


class TestGhPopupCleanupContract(unittest.TestCase):
    """WHEN inspecting gh_popup for unconditional namespace cleanup."""

    def test_gh_popup_cleanup_is_unconditional(self):
        text = GH_POPUP.read_text(encoding="utf-8")
        # The retained-dead-namespace workaround and its guard are gone.
        self.assertNotIn("_gh_popup_retain", text)
        self.assertNotIn("return 0", text)
        # A single owner-checked end runs on every EXIT.
        self.assertRegex(text, r"_gh_popup_cleanup\(\)\s*\{")
        self.assertRegex(text, r'end --owner-pid "\$\$" --token')
        self.assertIn("trap _gh_popup_cleanup EXIT", text)


if __name__ == "__main__":
    unittest.main()
