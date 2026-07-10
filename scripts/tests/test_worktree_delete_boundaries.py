#!/usr/bin/env python3
"""Deletion-boundary tests for the session picker's remove_all_worktrees.sh.

These lock in the allowlist policy of ``safe_rm_rf``: a resolved deletion
target is removed only when it is a STRICT descendant of an approved root
(``HOME`` or a configured ``PICK_SESSION_SCAN_ROOTS`` entry). Everything else —
the roots themselves, empty/slash, paths outside every approved root, and
symlinks that resolve outside — must be refused WITHOUT ``rm`` ever being
invoked for the target.

The production script carries no test hooks. To observe a single boundary
decision, each test generates an INSTRUMENTED temporary copy of the real
script: it splices a probe (``safe_rm_rf "$2"`` → print allow/refuse, then
exit) immediately before the script's main ``cd "$root_wt_dir"`` marker, so the
probe runs against the script's own resolved functions and populated
``approved_roots`` with nothing patched but the entrypoint. A negative control
swaps in the pre-hardening blocklist ``safe_rm_rf`` to prove the tests detect
the behavior change, and one end-to-end test drives the real script over real
git worktrees.

Runnable both via ``make test`` (unittest discovery) and directly via
``python3 -m unittest scripts.tests.test_worktree_delete_boundaries``.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Ensure scripts/ is importable regardless of how this module is loaded
# (discovery already does this; the module-path invocation does not).
_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _test_support  # noqa: E402,F401  (puts scripts/ on sys.path)
from _test_support import TMUX_PICKERS, modern_bash  # noqa: E402

REMOVE_SCRIPT = TMUX_PICKERS / "session/executable_remove_all_worktrees.sh"
ACTION_SCRIPT = TMUX_PICKERS / "session/executable_action_remove_worktrees.sh"

# The script's main entrypoint; the probe is spliced in just before it so all
# function definitions and approved_roots setup have already run.
_MARKER = 'cd "$root_wt_dir" 2> /dev/null || exit 0'

# Probe: evaluate the real safe_rm_rf for the target passed as $2 (so rm runs
# only on allow), report the decision, and exit before the destructive flow.
_PROBE = "if safe_rm_rf \"$2\"; then\n  printf 'allow\\n'\nelse\n  printf 'refuse\\n'\nfi\nexit 0\n\n"

# Verbatim pre-hardening blocklist policy (refused only ""/"/"/HOME). Used as a
# negative control so an accepted-outside-target regression is observable.
_OLD_SAFE_RM_RF = (
    "safe_rm_rf() {\n"
    '  local target="$1"\n'
    '  target="$(realpath_or_self "$target")"\n'
    '  case "$target" in\n'
    '    "" | "/") return 1 ;;\n'
    "  esac\n"
    '  if [ -n "${HOME:-}" ] && [ "$target" = "$(realpath_or_self "$HOME")" ]; then\n'
    "    return 1\n"
    "  fi\n"
    '  rm -rf "$target"\n'
    "}\n"
)

_SAFE_RM_RF_RE = re.compile(r"safe_rm_rf\(\) \{\n.*?\n\}\n", re.DOTALL)


def _wait_for(predicate, *, timeout=5.0, interval=0.05):
    """Poll until predicate() is truthy (background remover launches are async)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _instrument(text: str, *, old_policy: bool = False) -> str:
    """Return the script text with a boundary probe spliced before the marker.

    When ``old_policy`` is set, the hardened ``safe_rm_rf`` is first replaced by
    the pre-hardening blocklist implementation.
    """
    if old_policy:
        text, n = _SAFE_RM_RF_RE.subn(lambda _m: _OLD_SAFE_RM_RF, text, count=1)
        assert n == 1, "expected exactly one safe_rm_rf definition to swap"
    assert text.count(_MARKER) == 1, "expected exactly one cd marker"
    return text.replace(_MARKER, _PROBE + _MARKER, 1)


def _write_rm_shim(bin_dir: Path, log: Path) -> None:
    """Install a PATH ``rm`` that records each call and deletes nothing."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "rm"
    shim.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {log}\nexit 0\n")
    shim.chmod(0o755)


def _run_git(args: list[str], *, cwd: Path | None = None, home: Path) -> None:
    subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        env={
            **os.environ,
            "HOME": str(home),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )


class TestWorktreeDeleteBoundaries(unittest.TestCase):
    """WHEN remove_all_worktrees.sh decides whether a path may be deleted."""

    def _probe(
        self,
        target: str,
        *,
        tmp: Path,
        home: Path,
        scan_roots: list[Path] | None = None,
        old_policy: bool = False,
    ) -> tuple[str, list[str]]:
        """Run one boundary decision via an instrumented copy of the script.

        Returns ``(decision, rm_calls)`` where decision is ``allow``/``refuse``
        and rm_calls is the list of ``rm`` argument-lines the probe produced.
        """
        copy = tmp / "remove_all_worktrees_instrumented.sh"
        copy.write_text(_instrument(REMOVE_SCRIPT.read_text(), old_policy=old_policy))
        bin_dir = tmp / "binshim"
        rm_log = tmp / "rm.log"
        if rm_log.exists():
            rm_log.unlink()
        _write_rm_shim(bin_dir, rm_log)

        env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
            "HOME": str(home),
        }
        if scan_roots:
            env["PICK_SESSION_SCAN_ROOTS"] = ",".join(str(r) for r in scan_roots)
        else:
            env.pop("PICK_SESSION_SCAN_ROOTS", None)

        result = subprocess.run(
            [modern_bash(), str(copy), ".", target],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        rm_calls = rm_log.read_text().splitlines() if rm_log.exists() else []
        return result.stdout.strip(), rm_calls

    def test_allows_strict_descendant_of_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            target = home / "work" / "repo" / "wt"
            target.mkdir(parents=True)

            decision, rm_calls = self._probe(str(target), tmp=tmp, home=home)

            assert decision == "allow"
            assert any(str(target.resolve()) in call for call in rm_calls), rm_calls

    def test_allows_strict_descendant_of_scan_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            home.mkdir()
            scan_root = tmp / "elsewhere" / "code"
            target = scan_root / "repo" / "wt"
            target.mkdir(parents=True)

            decision, rm_calls = self._probe(str(target), tmp=tmp, home=home, scan_roots=[scan_root])

            assert decision == "allow"
            assert any(str(target.resolve()) in call for call in rm_calls), rm_calls

    def test_refuses_home_root_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            home.mkdir()

            decision, rm_calls = self._probe(str(home), tmp=tmp, home=home)

            assert decision == "refuse"
            assert rm_calls == []

    def test_refuses_scan_root_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            home.mkdir()
            scan_root = tmp / "elsewhere" / "code"
            scan_root.mkdir(parents=True)

            decision, rm_calls = self._probe(str(scan_root), tmp=tmp, home=home, scan_roots=[scan_root])

            assert decision == "refuse"
            assert rm_calls == []

    def test_refuses_path_outside_all_approved_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            home.mkdir()
            outside = tmp / "outside" / "repo"
            outside.mkdir(parents=True)

            decision, rm_calls = self._probe(str(outside), tmp=tmp, home=home)

            assert decision == "refuse"
            assert rm_calls == []

    def test_refuses_symlink_that_escapes_approved_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            (home / "work").mkdir(parents=True)
            outside = tmp / "outside" / "secret"
            outside.mkdir(parents=True)
            escape = home / "work" / "escape"
            escape.symlink_to(outside)

            decision, rm_calls = self._probe(str(escape), tmp=tmp, home=home)

            assert decision == "refuse"
            assert rm_calls == []
            assert outside.exists()

    def test_refuses_empty_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            home.mkdir()

            decision, rm_calls = self._probe("", tmp=tmp, home=home)

            assert decision == "refuse"
            assert rm_calls == []

    def test_refuses_filesystem_root_slash(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            home.mkdir()

            decision, rm_calls = self._probe("/", tmp=tmp, home=home)

            assert decision == "refuse"
            assert rm_calls == []

    def test_action_forwards_exact_scan_roots_raw_and_allows_external_root_delete(self):
        """Caller-level: configured raw roots survive through async dispatch."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            home.mkdir()
            scan_root = tmp / "elsewhere" / "code"
            root = scan_root / "repo" / "main"
            root.mkdir(parents=True)
            linked = scan_root / "repo" / "feature"

            _run_git(["init", str(root)], home=home)
            _run_git(["commit", "--allow-empty", "-m", "init"], cwd=root, home=home)
            _run_git(["worktree", "add", str(linked)], cwd=root, home=home)

            deployed_dir = home / ".config/tmux/scripts/pickers/session"
            deployed_dir.mkdir(parents=True)
            scan_log = tmp / "scan_roots.log"
            deployed_remove_all = deployed_dir / "remove_all_worktrees.sh"
            deployed_remove_all.write_text(
                "#!/usr/bin/env bash\n"
                f"printf '%s\\n' \"$PICK_SESSION_SCAN_ROOTS\" >> {shlex.quote(str(scan_log))}\n"
                f'exec /bin/bash {shlex.quote(str(REMOVE_SCRIPT))} "$@"\n'
            )
            deployed_remove_all.chmod(0o755)

            mock_bin = tmp / "bin"
            mock_bin.mkdir()
            tmux_mock = mock_bin / "tmux"
            tmux_mock.write_text(
                "#!/usr/bin/env bash\n"
                'case "$1" in\n'
                "  display-message)\n"
                '    if [ "$2" = "-p" ]; then\n'
                "      printf '%s\\n' \"${TMUX_SESSION_NAME:-current}\"\n"
                "    fi\n"
                "    exit 0\n"
                "    ;;\n"
                "  show-option)\n"
                '    if [ "$2" = "-gqv" ] && [ "$3" = "@pick_session_worktree_scan_roots" ]; then\n'
                "      printf '%s\\n' \"${TMUX_SCAN_ROOTS_RAW:-}\"\n"
                "    fi\n"
                "    exit 0\n"
                "    ;;\n"
                "  list-sessions)\n"
                "    exit 0\n"
                "    ;;\n"
                "esac\n"
                "exit 0\n"
            )
            tmux_mock.chmod(0o755)

            selection = tmp / "selection.tsv"
            selection.write_text(f"row\tworktree\t{root}\twt_root:repo\t{root}\n")
            scan_roots_raw = f"  {scan_root.parent},{scan_root},  ~/scratch  "

            result = subprocess.run(
                [modern_bash(), str(ACTION_SCRIPT), str(selection)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "PATH": f"{mock_bin}:{os.environ.get('PATH', '')}",
                    "TMUX": "mock,1,0",
                    "TMUX_SESSION_NAME": "current",
                    "TMUX_SCAN_ROOTS_RAW": scan_roots_raw,
                },
            )
            assert result.returncode == 0, result.stderr

            assert _wait_for(lambda: scan_log.exists() and not root.exists() and not linked.exists())
            forwarded = scan_log.read_text().splitlines()
            assert forwarded, "remove_all_worktrees.sh was not launched"
            assert forwarded[-1] == scan_roots_raw
            assert not root.exists()
            assert not linked.exists()

    def test_old_blocklist_policy_accepts_outside_target(self):
        """Negative control: the pre-hardening policy deletes an outside path.

        The same outside target the allowlist refuses (no rm) is accepted by
        the old blocklist (rm called), proving these tests detect the change.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            home.mkdir()
            outside = tmp / "outside" / "repo"
            outside.mkdir(parents=True)

            new_decision, new_rm = self._probe(str(outside), tmp=tmp, home=home)
            old_decision, old_rm = self._probe(str(outside), tmp=tmp, home=home, old_policy=True)

            assert new_decision == "refuse"
            assert new_rm == []
            assert old_decision == "allow"
            assert any(str(outside.resolve()) in call for call in old_rm), old_rm

    def test_outside_git_worktree_is_refused_but_home_worktree_deleted(self):
        """End-to-end on the real script: outside worktree survives.

        A real git worktree living outside every approved root is refused (and
        rm is never asked to remove it) while the in-HOME main worktree is
        still removed — the pre-existing valid deletion behavior.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            home = tmp / "home"
            root = home / "proj" / "main"
            root.mkdir(parents=True)
            outside = tmp / "outside" / "linked"
            outside.parent.mkdir(parents=True)

            _run_git(["init", str(root)], home=home)
            _run_git(["commit", "--allow-empty", "-m", "init"], cwd=root, home=home)
            _run_git(["worktree", "add", str(outside)], cwd=root, home=home)
            (outside / "keep.txt").write_text("keep\n")

            bin_dir = tmp / "binshim"
            rm_log = tmp / "rm.log"
            # Log every rm call, then perform the real deletion so the script's
            # in-HOME cleanup matches production.
            bin_dir.mkdir(parents=True, exist_ok=True)
            shim = bin_dir / "rm"
            shim.write_text(f'#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> {rm_log}\nexec /bin/rm "$@"\n')
            shim.chmod(0o755)

            result = subprocess.run(
                [modern_bash(), str(REMOVE_SCRIPT), str(root)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "TMUX": "",
                },
            )

            assert result.returncode == 0, result.stderr
            # Outside worktree refused and untouched.
            assert outside.exists()
            assert (outside / "keep.txt").read_text() == "keep\n"
            # In-HOME main worktree really removed (valid behavior preserved).
            assert not root.exists()
            # rm was never asked to remove the outside target.
            rm_calls = rm_log.read_text() if rm_log.exists() else ""
            assert str(outside.resolve()) not in rm_calls, rm_calls


if __name__ == "__main__":
    unittest.main()
