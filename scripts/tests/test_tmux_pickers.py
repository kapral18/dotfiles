#!/usr/bin/env python3
"""Tests for tmux picker shell helper behavior."""

from __future__ import annotations

import json
import os
import re
import runpy
import shlex
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import (
    TMUX_PICKERS,
    modern_bash,
    run_bash,
)


class TestTmuxPickerShellHelpers(unittest.TestCase):
    """WHEN validating tmux picker shell helper contracts."""

    def test_snapshot_filters_headers_into_unique_cache_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            selection = tmp_path / "selection.tsv"
            selection.write_text(
                "Header\theader\t\t\t\t\n"
                "PR 1\tpr\t/path/one\t\turl-1\tmatch-one\n"
                "Issue 2\tissue\t/path/two\t\turl-2\tmatch-two\n"
            )
            env = {**os.environ, "XDG_CACHE_HOME": str(tmp_path / "cache")}
            script = TMUX_PICKERS / "lib/executable_snapshot_fzf_selection.sh"

            snapshots: list[Path] = []
            for _ in range(2):
                result = subprocess.run(
                    [modern_bash(), str(script), "--filter-awk", '$2 != "header"', str(selection)],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                assert result.returncode == 0, result.stderr
                snapshots.append(Path(result.stdout.strip()))

            assert snapshots[0] != snapshots[1]
            for snapshot in snapshots:
                assert snapshot.parent == tmp_path / "cache/tmux"
                assert snapshot.read_text() == (
                    "PR 1\tpr\t/path/one\t\turl-1\tmatch-one\nIssue 2\tissue\t/path/two\t\turl-2\tmatch-two\n"
                )

    def test_dispatch_async_preserves_fzf_listen_env_for_server_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            tmux_log = root / "tmux.log"
            selection = root / "selection.tsv"
            selection.write_text("row\tdir\t/path\t\t\t\n")
            deployed_lib = root / "pickers/lib"
            deployed_lib.mkdir(parents=True)
            script = deployed_lib / "dispatch_async.sh"
            snap = deployed_lib / "snapshot_fzf_selection.sh"
            script.write_text((TMUX_PICKERS / "lib/executable_dispatch_async.sh").read_text())
            snap.write_text((TMUX_PICKERS / "lib/executable_snapshot_fzf_selection.sh").read_text())
            script.chmod(0o755)
            snap.chmod(0o755)

            tmux = fake_bin / "tmux"
            tmux.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "${1:-}" = run-shell ]; then\n'
                f"  printf '%s\\n' \"$*\" > {shlex.quote(str(tmux_log))}\n"
                "  exit 0\n"
                "fi\n"
                "exit 1\n"
            )
            tmux.chmod(0o755)

            result = subprocess.run(
                [modern_bash(), str(script), "/bin/echo", str(selection)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "XDG_CACHE_HOME": str(root / "cache"),
                    "TMUX": "mock,1,0",
                    "FZF_SOCK": "/tmp/fzf.sock",
                },
            )

            assert result.returncode == 0, result.stderr
            logged = tmux_log.read_text()
            assert "FZF_SOCK=/tmp/fzf.sock" in logged

    def test_pick_session_alt_x_uses_inline_bgtransform_confirmation(self):
        script = TMUX_PICKERS / "session/executable_pick_session.sh"
        text = script.read_text()

        assert (
            '--bind "alt-x:${altx_check_cue}+bg-transform($(printf %q "$altx_cmd") $(printf %q "$rm_confirm_flag") $(printf %q "$rm_cmd") {+f} $(printf %q "$rm_pending_snap"))"'
            in text
        )
        assert '--bind "alt-x:execute(' not in text
        # esc must clear the confirm flag and the transform's run marker so a
        # cancelled flow can never turn a later alt-x into an accidental force.
        assert "esc:execute-silent(rm -f $mode_flag $wt_mode_flag $rm_confirm_flag ${rm_confirm_flag}.run)" in text

    def test_pick_session_alt_x_composes_instant_feedback_and_fast_hide(self):
        script = TMUX_PICKERS / "session/executable_pick_session.sh"
        text = script.read_text()

        # In-progress feedback comes from the binding's own prompt swap applied
        # at keypress time, never from a picker takeover or a helper-painted UI.
        assert "ALTX_CHECK_ACTIONS" not in text
        assert 'altx_check_cue="change-prompt(⏳ removing…)"' in text
        # Cancelled checks hand the cue back via this export.
        assert 'export ALTX_RESTORE_ACTIONS="$altx_visual_restore"' in text
        # The optimistic hide reloads the live row-set source file filtered by
        # the checked snapshot (no items rescan), then restores the visuals.
        assert (
            '_altx_hide_reload="$(snapshot_reload_command "${_altx_hide_matcher} ${_altx_pending_q} ${altx_src_q}")"'
            in text
        )
        for var in ("altx_safe_actions", "altx_force_actions"):
            assert f'{var}="reload(${{_altx_hide_reload}})+deselect-all+${{altx_visual_restore}}"' in text
        # The items-rescan hide path that replaced the alt-x keypress latency.
        assert "remove_reload=" not in text

    def test_altx_hide_matches_plain_projections_and_display_keeps_ansi(self):
        # fzf hands {+f} snapshots back --ansi-stripped while the item stream
        # keeps its SGR codes, so the hide compares plain projections at the
        # one comparison site and prints survivors unchanged. Display paths
        # must never strip — that bleaches every row's colors.
        pick = (TMUX_PICKERS / "session/executable_pick_session.sh").read_text()
        assert (
            '_altx_hide_awk=\'FILENAME==ARGV[1]{t=$0;gsub(/\\033\\[[0-9;]*m/,"",t);p[t]=1;next}'
            '{t=$0;gsub(/\\033\\[[0-9;]*m/,"",t);if(!(t in p))print}\'' in pick
        )
        assert (
            '_altx_hide_reload="$(snapshot_reload_command "${_altx_hide_matcher} ${_altx_pending_q} ${altx_src_q}")"'
            in pick
        )
        assert "_ansi_strip_cmd" not in pick
        assert '| tee "$sort_source_file" | SHELL="$fzf_shell" fzf' in pick
        for name in (
            "executable_live_refresh.sh",
            "executable_fzf_reload.sh",
            "executable_action_only_cycle.sh",
        ):
            text = (TMUX_PICKERS / f"session/{name}").read_text()
            assert "gsub(" not in text, f"{name} must not strip ANSI from display rows"
            assert r"\033" not in text, f"{name} must not strip ANSI from display rows"

    def test_altx_transform_safe_selection_emits_hide_without_touching_confirm_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "cache/tmux"
            picker_dir = root / ".config/tmux/scripts/pickers/session"
            lib_dir = root / ".config/tmux/scripts/pickers/lib"
            cache_dir.mkdir(parents=True)
            picker_dir.mkdir(parents=True)
            lib_dir.mkdir(parents=True)
            for name in ("executable_dispatch_async.sh",):
                (lib_dir / name.split("executable_")[1]).write_text((TMUX_PICKERS / f"lib/{name}").read_text())
            selection = root / "selection.tsv"
            selection.write_text("ctx\tworktree\t/tmp/wt\twt:|repo=r\t/tmp/root\n")
            pending_snap = cache_dir / "pending.tsv"
            confirm_flag = cache_dir / "confirm.flag"
            safe_check = picker_dir / "safe_rm.sh"
            safe_check.write_text("#!/usr/bin/env bash\nexit 0\n")  # --check always safe
            safe_check.chmod(0o755)

            # Stage a logging dispatch_async so the test observes what the safe
            # branch dispatches (helper resolves ../lib relative to its own path,
            # and we run a staged copy of the helper — see below).
            dispatch_log = root / "dispatch.log"
            lib_dir = picker_dir.parent / "lib"
            lib_dir.mkdir(exist_ok=True)
            dispatch = lib_dir / "dispatch_async.sh"
            dispatch.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {shlex.quote(str(dispatch_log))}\n")
            dispatch.chmod(0o755)
            staged_helper = picker_dir / "altx_remove_transform.sh"
            staged_helper.write_text((TMUX_PICKERS / "session/executable_altx_remove_transform.sh").read_text())
            staged_helper.chmod(0o755)

            result = subprocess.run(
                [
                    modern_bash(),
                    str(staged_helper),
                    str(confirm_flag),
                    str(safe_check),
                    str(selection),
                    str(pending_snap),
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "ALTX_SAFE_ACTIONS": "SAFE+HIDE",
                    "ALTX_CONFIRM_ACTIONS": "CONFIRM",
                    "ALTX_FORCE_ACTIONS": "FORCE",
                },
            )

            assert result.returncode == 0, result.stderr
            assert result.stdout.strip() == "SAFE+HIDE"
            assert pending_snap.read_text() == selection.read_text()
            assert not confirm_flag.exists()
            assert not (confirm_flag.parent / "confirm.flag.busy").exists()
            dispatched = dispatch_log.read_text()
            assert "--force" not in dispatched
            assert str(pending_snap) in dispatched

    def test_altx_transform_blocked_selection_enters_confirm_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "cache/tmux"
            picker_dir = root / ".config/tmux/scripts/pickers/session"
            cache_dir.mkdir(parents=True)
            picker_dir.mkdir(parents=True)
            blocked_w = picker_dir / "blocked_rm.sh"
            blocked_w.write_text('#!/usr/bin/env bash\n[ "${1:-}" = --check ] && exit 3\nexit 0\n')
            blocked_w.chmod(0o755)
            selection = root / "selection.tsv"
            selection.write_text("ctx\tworktree\t/tmp/wt\twt:|repo=r\t/tmp/root\n")
            pending_snap = cache_dir / "pending.tsv"
            confirm_flag = cache_dir / "confirm.flag"

            result = subprocess.run(
                [
                    modern_bash(),
                    str(TMUX_PICKERS / "session/executable_altx_remove_transform.sh"),
                    str(confirm_flag),
                    str(blocked_w),
                    str(selection),
                    str(pending_snap),
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "ALTX_SAFE_ACTIONS": "SAFE+HIDE",
                    "ALTX_CONFIRM_ACTIONS": "CONFIRM+SWAP",
                    "ALTX_FORCE_ACTIONS": "FORCE",
                },
            )

            assert result.returncode == 0, result.stderr
            assert result.stdout.strip() == "CONFIRM+SWAP"
            assert confirm_flag.exists()

            # Second alt-x while confirmed force-dispatches the PENDING snapshot
            # (not the live selection) through dispatch_async.sh and clears the
            # flag. The helper resolves dispatch_async.sh relative to its own
            # path, so stage a fixture copy under <fixture pickers>/session.
            dispatch_log = root / "dispatch.log"
            lib_dir = picker_dir.parent / "lib"
            lib_dir.mkdir(exist_ok=True)
            dispatch = lib_dir / "dispatch_async.sh"
            dispatch.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {shlex.quote(str(dispatch_log))}\n")
            dispatch.chmod(0o755)
            staged_helper = picker_dir / "altx_remove_transform.sh"
            staged_helper.write_text((TMUX_PICKERS / "session/executable_altx_remove_transform.sh").read_text())
            staged_helper.chmod(0o755)
            live_selection = root / "live.tsv"
            live_selection.write_text("different\trow\n")

            result2 = subprocess.run(
                [
                    modern_bash(),
                    str(staged_helper),
                    str(confirm_flag),
                    str(blocked_w),
                    str(live_selection),
                    str(pending_snap),
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "ALTX_SAFE_ACTIONS": "SAFE+HIDE",
                    "ALTX_CONFIRM_ACTIONS": "CONFIRM+SWAP",
                    "ALTX_FORCE_ACTIONS": "FORCE+RESTORE",
                },
            )

            assert result2.returncode == 0, result.stderr
            assert result2.stdout.strip() == "FORCE+RESTORE"
            assert not confirm_flag.exists()
            dispatched = dispatch_log.read_text()
            assert "--force" in dispatched
            assert str(pending_snap) in dispatched
            assert str(live_selection) not in dispatched

    def test_altx_transform_collapses_rapid_presses_with_busy_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "cache/tmux"
            picker_dir = root / ".config/tmux/scripts/pickers/session"
            cache_dir.mkdir(parents=True)
            picker_dir.mkdir(parents=True)
            slow_check = picker_dir / "slow_rm.sh"
            # Long enough for a second press to land while busy, short enough
            # that the first press completes and prints its actions.
            slow_check.write_text("#!/usr/bin/env bash\nsleep 1.5\n")
            slow_check.chmod(0o755)
            selection = root / "selection.tsv"
            selection.write_text("ctx\tworktree\t/tmp/wt\twt:|repo=r\t/tmp/root\n")
            pending_snap = cache_dir / "pending.tsv"
            confirm_flag = cache_dir / "confirm.flag"

            first = subprocess.Popen(
                [
                    modern_bash(),
                    str(TMUX_PICKERS / "session/executable_altx_remove_transform.sh"),
                    str(confirm_flag),
                    str(slow_check),
                    str(selection),
                    str(pending_snap),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "ALTX_SAFE_ACTIONS": "FIRST"},
            )
            # Wait until the busy marker exists, then fire the second press.
            busy = Path(f"{confirm_flag}.busy")
            deadline = time.time() + 10
            while not busy.exists() and time.time() < deadline:
                time.sleep(0.02)

            second = subprocess.run(
                [
                    modern_bash(),
                    str(TMUX_PICKERS / "session/executable_altx_remove_transform.sh"),
                    str(confirm_flag),
                    str(slow_check),
                    str(selection),
                    str(pending_snap),
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "ALTX_SAFE_ACTIONS": "SECOND"},
            )

            assert second.returncode == 0, second.stderr
            assert second.stdout.strip() == ""  # second press swallowed while busy

    def test_altx_transform_flashes_status_message_during_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "cache/tmux"
            picker_dir = root / ".config/tmux/scripts/pickers/session"
            picker_dir.mkdir(parents=True)
            cache_dir.mkdir(parents=True)
            check_rm = picker_dir / "check_rm.sh"
            check_rm.write_text('#!/usr/bin/env bash\nsleep 0.3\n[ "${1:-}" = --check ] && exit 3\nexit 0\n')
            check_rm.chmod(0o755)
            selection = root / "selection.tsv"
            selection.write_text("ctx\tworktree\t/tmp/wt\twt:|repo=r\t/tmp/root\n")
            pending_snap = cache_dir / "pending.tsv"
            confirm_flag = cache_dir / "confirm.flag"

            result = subprocess.run(
                [
                    modern_bash(),
                    str(TMUX_PICKERS / "session/executable_altx_remove_transform.sh"),
                    str(confirm_flag),
                    str(check_rm),
                    str(selection),
                    str(pending_snap),
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "ALTX_CONFIRM_ACTIONS": "CONFIRM+SWAP",
                },
            )

            assert result.returncode == 0, result.stderr
            assert result.stdout.strip() == "CONFIRM+SWAP"
            # Progress never depends on a tmux status message or any external
            # painter: the helper emits actions only.
            assert "display-message" not in (TMUX_PICKERS / "session/executable_altx_remove_transform.sh").read_text()

    def test_altx_transform_cancelled_check_does_not_enter_confirm_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "cache/tmux"
            picker_dir = root / ".config/tmux/scripts/pickers/session"
            picker_dir.mkdir(parents=True)
            cache_dir.mkdir(parents=True)
            slow_check = picker_dir / "slow_blocked.sh"
            slow_check.write_text('#!/usr/bin/env bash\nsleep 1.5\n[ "${1:-}" = --check ] && exit 3\nexit 0\n')
            slow_check.chmod(0o755)
            selection = root / "selection.tsv"
            selection.write_text("ctx\tworktree\t/tmp/wt\twt:|repo=r\t/tmp/root\n")
            pending_snap = cache_dir / "pending.tsv"
            confirm_flag = cache_dir / "confirm.flag"

            first = subprocess.Popen(
                [
                    modern_bash(),
                    str(TMUX_PICKERS / "session/executable_altx_remove_transform.sh"),
                    str(confirm_flag),
                    str(slow_check),
                    str(selection),
                    str(pending_snap),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={
                    **os.environ,
                    "ALTX_CONFIRM_ACTIONS": "CONFIRM+SWAP",
                    "ALTX_RESTORE_ACTIONS": "RESTORE+VISUALS",
                },
            )
            run_marker = Path(f"{confirm_flag}.run")
            deadline = time.time() + 10
            while not run_marker.exists() and time.time() < deadline:
                time.sleep(0.02)
            # The picker's esc binding removes this marker while the check is
            # still running; the helper must hand the removing… cue back by
            # echoing the restore actions instead of arming confirm mode.
            run_marker.unlink()

            out, err = first.communicate(timeout=30)

            assert first.returncode == 0, err
            assert out.strip() == "RESTORE+VISUALS"  # cue handed back, nothing armed
            assert not confirm_flag.exists()  # confirm mode never arms after cancel

    def test_session_name_for_entry_uses_worktree_target_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = home / "repo"
            worktree = home / "repo-linked"
            (root / ".git/worktrees/linked").mkdir(parents=True)
            worktree.mkdir(parents=True)
            lib = TMUX_PICKERS / "session/lib/session_naming.sh"

            out = run_bash(
                "\n".join(
                    [
                        f". {shlex.quote(str(lib))}",
                        (
                            "session_name_for_entry worktree "
                            f"{shlex.quote(str(worktree))} "
                            "'wt:|repo=elastic/kibana' "
                            f"{shlex.quote(str(root))} "
                            "directory"
                        ),
                    ]
                ),
                env={"HOME": str(home)},
            )

            assert out == "elastic/kibana\n"

    def test_session_name_for_entry_matches_directory_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            project = home / "src/My Project"
            project.mkdir(parents=True)
            lib = TMUX_PICKERS / "session/lib/session_naming.sh"

            out = run_bash(
                "\n".join(
                    [
                        f". {shlex.quote(str(lib))}",
                        (f"session_name_for_entry dir {shlex.quote(str(project))} '' '' directory"),
                    ]
                ),
                env={"HOME": str(home)},
            )

            assert out == "my-project\n"

    def test_when_session_row_has_empty_meta_should_preserve_target_column(self):
        lib = TMUX_PICKERS / "session/lib/session_naming.sh"
        row = "display\tsession\t/path\t\tcanonical\tcanonical base ~/path /path"

        out = run_bash(
            "\n".join(
                [
                    f". {shlex.quote(str(lib))}",
                    f"picker_row_parse {shlex.quote(row)}",
                    "printf '%s\\n' \"${PICKER_ROW_FIELDS[@]}\"",
                ]
            )
        )

        assert out.splitlines() == [
            "display",
            "session",
            "/path",
            "",
            "canonical",
            "canonical base ~/path /path",
        ]

    def test_bag_rename_if_needed_moves_bagged_holder_aside(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            mock_bin = tmp_path / "bin"
            mock_bin.mkdir()
            rename_log = tmp_path / "rename.log"
            tmux = mock_bin / "tmux"
            tmux.write_text(
                """#!/usr/bin/env bash
case "$1" in
  has-session)
    case "${3#=}" in
      repo|repo@bag) exit 0 ;;
      *) exit 1 ;;
    esac
    ;;
  rename-session)
    printf '%s\t%s\n' "${3#=}" "$4" > "$TMUX_RENAME_LOG"
    exit 0
    ;;
  list-sessions)
    exit 0
    ;;
esac
exit 1
"""
            )
            tmux.chmod(0o755)
            lib = TMUX_PICKERS / "session/lib/session_naming.sh"

            out = run_bash(
                "\n".join(
                    [
                        f". {shlex.quote(str(lib))}",
                        'bag_rename_if_needed repo "$HOME/work/repo" "$HOME/.bag/worktree_remove/repo"',
                    ]
                ),
                env={
                    "HOME": str(home),
                    "PATH": f"{mock_bin}:{os.environ['PATH']}",
                    "TMUX_RENAME_LOG": str(rename_log),
                },
            )

            assert out == "repo\trepo@bag2\n"
            assert rename_log.read_text() == "repo\trepo@bag2\n"

    def test_remove_all_worktrees_keeps_independent_sibling_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = home / "work/kibana/main"
            sibling = home / "work/kibana/sibling-repo"
            notes = home / "work/kibana/notes"
            root.mkdir(parents=True)
            sibling.mkdir(parents=True)
            notes.mkdir()
            (notes / "keep.txt").write_text("keep\n")

            subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(root), "remote", "add", "origin", "git@github.com:elastic/kibana.git"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(["git", "init", str(sibling)], check=True, capture_output=True, text=True)

            script = TMUX_PICKERS / "session/executable_remove_all_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), str(root)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                },
            )

            assert result.returncode == 0, result.stderr
            assert not root.exists()
            assert (sibling / ".git").exists()
            assert (notes / "keep.txt").exists()
            assert not (home / "work/.bag/pickers/session/kibana").exists()

    def test_remove_all_worktrees_bags_leftovers_when_wrapper_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = home / "work/kibana/main"
            notes = home / "work/kibana/notes"
            root.mkdir(parents=True)
            notes.mkdir()
            (notes / "keep.txt").write_text("keep\n")

            subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(root), "remote", "add", "origin", "git@github.com:elastic/kibana.git"],
                check=True,
                capture_output=True,
                text=True,
            )

            script = TMUX_PICKERS / "session/executable_remove_all_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), str(root)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                },
            )

            assert result.returncode == 0, result.stderr
            assert not (home / "work/kibana").exists()
            bag_root = home / "work/.bag/pickers/session/kibana"
            bagged_notes = list(bag_root.glob("*/notes/keep.txt"))
            assert len(bagged_notes) == 1
            assert bagged_notes[0].read_text() == "keep\n"

    def test_action_remove_root_selection_tombstones_worktrees_not_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = home / "work/kibana/main"
            wrapper = home / "work/kibana"
            cache_dir = home / ".cache/tmux"
            cache_dir.mkdir(parents=True)
            root.mkdir(parents=True)
            root_rp = root.resolve()
            wrapper_rp = wrapper.resolve()

            subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(root), "remote", "add", "origin", "git@github.com:elastic/kibana.git"],
                check=True,
                capture_output=True,
                text=True,
            )

            selection = Path(tmp) / "selection.tsv"
            selection.write_text(f"main\tworktree\t{root}\twt_root:main\t{root}\n")

            script = TMUX_PICKERS / "session/executable_action_remove_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), str(selection)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "TMUX": "",
                },
            )

            assert result.returncode == 0, result.stderr
            pending = (cache_dir / "pick_session_pending.tsv").read_text()
            mutations = (cache_dir / "pick_session_mutations.tsv").read_text()
            assert f"WT\t{root_rp}\n" in pending
            assert f"WT\t{wrapper_rp}\n" not in pending
            assert f"\tPATH_PREFIX\t{root_rp}\n" in mutations
            assert f"\tPATH_PREFIX\t{wrapper_rp}\n" not in mutations

    def test_remove_hide_keeps_preflight_blocked_selection_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            cache_dir = home / ".cache/tmux"
            picker_dir = home / ".config/tmux/scripts/pickers/session"
            worktree = home / "work/kibana/fix/context-menu"
            fake_bin.mkdir()
            cache_dir.mkdir(parents=True)
            picker_dir.mkdir(parents=True)
            worktree.mkdir(parents=True)

            row = f"ctx\tsession\t{worktree}\tsess_wt:fix/context-menu|repo=work/kibana\tctx\tctx\n"
            selection = root / "selection.tsv"
            selection.write_text(row)
            items = picker_dir / "items.sh"
            items.write_text(f"#!/usr/bin/env bash\nprintf '%s' {shlex.quote(row)}\n")
            items.chmod(0o755)

            fake_w = fake_bin / ",w"
            fake_w.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "${1:-}" = remove ] && [ "${2:-}" = --preflight ]; then\n'
                f"  printf '%s\\n' {shlex.quote(str(worktree))}\n"
                "fi\n"
            )
            fake_w.chmod(0o755)

            script = TMUX_PICKERS / "session/executable_items_hide_selected.sh"
            result = subprocess.run(
                [modern_bash(), str(script), str(selection), "remove", ""],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "",
                },
            )

            assert result.returncode == 0, result.stderr
            assert str(worktree) in result.stdout
            mutation_file = cache_dir / "pick_session_mutations.tsv"
            assert not mutation_file.exists() or str(worktree) not in mutation_file.read_text()

    def test_action_remove_check_mode_reports_blocked_with_zero_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            cache_dir = home / ".cache/tmux"
            worktree = home / "work/kibana/fix/context-menu"
            fake_bin.mkdir(parents=True)
            cache_dir.mkdir(parents=True)
            worktree.mkdir(parents=True)
            subprocess.run(["git", "init", str(worktree)], check=True, capture_output=True, text=True)

            selection = root / "selection.tsv"
            selection.write_text(f"ctx\tsession\t{worktree}\tsess_wt:fix/context-menu|repo=work/kibana\tctx\tctx\n")

            fake_w = fake_bin / ",w"
            fake_w.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "${1:-}" = remove ] && [ "${2:-}" = --preflight ]; then\n'
                f"  printf '%s\\n' {shlex.quote(str(worktree))}\n"
                "fi\n"
            )
            fake_w.chmod(0o755)

            script = TMUX_PICKERS / "session/executable_action_remove_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), "--check", str(selection)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "",
                },
            )

            assert result.returncode == 3, result.stderr
            assert not (cache_dir / "pick_session_pending.tsv").exists()
            assert not (cache_dir / "pick_session_mutations.tsv").exists()
            assert not (cache_dir / "pick_session_remove_worktrees.log").exists()

    def test_action_remove_check_mode_passes_safe_selection_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            cache_dir = home / ".cache/tmux"
            worktree = home / "work/kibana/fix/context-menu"
            fake_bin.mkdir(parents=True)
            cache_dir.mkdir(parents=True)
            worktree.mkdir(parents=True)
            subprocess.run(["git", "init", str(worktree)], check=True, capture_output=True, text=True)

            selection = root / "selection.tsv"
            selection.write_text(f"ctx\tsession\t{worktree}\tsess_wt:fix/context-menu|repo=work/kibana\tctx\tctx\n")

            # Preflight prints nothing => nothing is dirty/unpushed => safe.
            fake_w = fake_bin / ",w"
            fake_w.write_text("#!/usr/bin/env bash\nexit 0\n")
            fake_w.chmod(0o755)

            script = TMUX_PICKERS / "session/executable_action_remove_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), "--check", str(selection)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "",
                },
            )

            assert result.returncode == 0, result.stderr
            assert not (cache_dir / "pick_session_pending.tsv").exists()
            assert not (cache_dir / "pick_session_mutations.tsv").exists()
            assert not (cache_dir / "pick_session_remove_worktrees.log").exists()

    def test_action_remove_aborts_cleanly_when_async_run_hits_blocked_preflight(self):
        """Backstop: the picker gates via --check before dispatching; if state
        changes between that check and this run, this async run must abort with
        no tombstones/pending rows and surface a display-message instead of
        prompting or forcing."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            cache_dir = home / ".cache/tmux"
            tmux_log = root / "tmux.log"
            worktree = home / "work/kibana/fix/context-menu"
            fake_bin.mkdir(parents=True)
            cache_dir.mkdir(parents=True)
            worktree.mkdir(parents=True)
            subprocess.run(["git", "init", str(worktree)], check=True, capture_output=True, text=True)

            selection = root / "selection.tsv"
            selection.write_text(f"ctx\tsession\t{worktree}\tsess_wt:fix/context-menu|repo=work/kibana\tctx\tctx\n")

            fake_w = fake_bin / ",w"
            fake_w.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "${1:-}" = remove ] && [ "${2:-}" = --preflight ]; then\n'
                f"  printf '%s\\n' {shlex.quote(str(worktree))}\n"
                "fi\n"
            )
            fake_w.chmod(0o755)

            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text(
                f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {shlex.quote(str(tmux_log))}\nexit 0\n"
            )
            fake_tmux.chmod(0o755)

            script = TMUX_PICKERS / "session/executable_action_remove_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), str(selection)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "mock,1,0",
                },
            )

            assert result.returncode == 0, result.stderr
            logged = tmux_log.read_text()
            assert "blocked" in logged and "alt-x again to force" in logged
            assert not (cache_dir / "pick_session_pending.tsv").exists()
            assert not (cache_dir / "pick_session_mutations.tsv").exists()

    def test_action_remove_accepts_force_flag_trailing_the_selection(self):
        """dispatch_async appends extras after the snapshot, so `--force` may
        follow the sel path; it must still bypass the preflight."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            cache_dir = home / ".cache/tmux"
            worktree = home / "work/kibana/fix/context-menu"
            fake_bin.mkdir(parents=True)
            cache_dir.mkdir(parents=True)
            worktree.mkdir(parents=True)
            subprocess.run(["git", "init", str(worktree)], check=True, capture_output=True, text=True)

            selection = root / "selection.tsv"
            selection.write_text(f"ctx\tsession\t{worktree}\tsess_wt:fix/context-menu|repo=work/kibana\tctx\tctx\n")

            # ,w preflight would block everything; --force must never reach it.
            fake_w = fake_bin / ",w"
            fake_w.write_text(
                '#!/usr/bin/env bash\nif [ "${1:-}" = remove ] && [ "${2:-}" = --preflight ]; then\n  exit 1\nfi\n'
            )
            fake_w.chmod(0o755)
            zoxide = fake_bin / "zoxide"
            zoxide.write_text("#!/usr/bin/env bash\nexit 0\n")
            zoxide.chmod(0o755)

            script = TMUX_PICKERS / "session/executable_action_remove_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), str(selection), "--force"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "",
                },
            )

            assert result.returncode == 0, result.stderr
            mutations = (cache_dir / "pick_session_mutations.tsv").read_text()
            assert f"\tPATH_PREFIX\t{worktree.resolve()}\n" in mutations

    def test_action_remove_with_force_flag_bypasses_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            cache_dir = home / ".cache/tmux"
            worktree = home / "work/kibana/fix/context-menu"
            fake_bin.mkdir()
            cache_dir.mkdir(parents=True)
            worktree.mkdir(parents=True)
            subprocess.run(["git", "init", str(worktree)], check=True, capture_output=True, text=True)

            selection = root / "selection.tsv"
            selection.write_text(f"ctx\tsession\t{worktree}\tsess_wt:fix/context-menu|repo=work/kibana\tctx\tctx\n")

            # ,w preflight should never be called when --force is passed
            fake_w = fake_bin / ",w"
            fake_w.write_text(
                '#!/usr/bin/env bash\nif [ "${1:-}" = remove ] && [ "${2:-}" = --preflight ]; then\n  exit 1\nfi\n'
            )
            fake_w.chmod(0o755)

            zoxide = fake_bin / "zoxide"
            zoxide.write_text("#!/usr/bin/env bash\nexit 0\n")
            zoxide.chmod(0o755)

            script = TMUX_PICKERS / "session/executable_action_remove_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), "--force", str(selection)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "",
                },
            )

            assert result.returncode == 0, result.stderr
            mutations = (cache_dir / "pick_session_mutations.tsv").read_text()
            assert f"\tPATH_PREFIX\t{worktree.resolve()}\n" in mutations

    def test_action_remove_force_dispatch_places_force_before_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            cache_dir = home / ".cache/tmux"
            repo = home / "work/kibana/main"
            worktree = home / "work/kibana/fix/context-menu"
            fake_bin.mkdir()
            cache_dir.mkdir(parents=True)
            repo.mkdir(parents=True)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "--allow-empty", "-m", "init"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "worktree", "add", "-b", "fix/context-menu", str(worktree)],
                check=True,
                capture_output=True,
                text=True,
            )

            selection = root / "selection.tsv"
            selection.write_text(f"ctx\tsession\t{worktree}\tsess_wt:fix/context-menu|repo=work/kibana\tctx\tctx\n")

            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text(
                "#!/usr/bin/env bash\n"
                'case "${1:-}" in\n'
                "  display-message)\n"
                "    if [ \"${2:-}\" = -p ]; then printf 'current\\n'; fi\n"
                "    exit 0\n"
                "    ;;\n"
                "  list-sessions|show-option)\n"
                "    exit 0\n"
                "    ;;\n"
                "esac\n"
            )
            fake_tmux.chmod(0o755)
            fake_w = fake_bin / ",w"
            fake_w.write_text("#!/usr/bin/env bash\nexit 0\n")
            fake_w.chmod(0o755)

            script = TMUX_PICKERS / "session/executable_action_remove_worktrees.sh"
            result = subprocess.run(
                [modern_bash(), str(script), "--force", str(selection)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(home / ".cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "fake",
                },
            )

            assert result.returncode == 0, result.stderr
            rm_log = (cache_dir / "pick_session_remove_worktrees.log").read_text()
            assert f",w remove --force --paths {worktree.resolve()}" in rm_log
            assert ",w remove --paths --force" not in rm_log

    def test_send_command_passes_cache_target_to_shared_naming(self):
        action = TMUX_PICKERS / "session/executable_action_send_command.sh"
        text = action.read_text()

        assert 'read -r kind path meta target <<< "$_entry"' in text
        assert 'session_name_for_entry "$kind" "$path" "$meta" "$target"' in text

    def test_when_tmux_restore_finishes_should_schedule_full_session_picker_reindex(self):
        plugins_conf = _test_support.REPO / "home/dot_config/exact_tmux/exact_conf.d/readonly_90-plugins.conf"
        text = plugins_conf.read_text()
        hook_line = next(line for line in text.splitlines() if "@resurrect-hook-post-restore-all" in line)
        fast_scan = "index_update.sh --force --quiet --skip-dirty --skip-gh"

        assert hook_line.startswith("set -g @resurrect-hook-post-restore-all ")
        assert "tmux run-shell -b" in hook_line
        assert hook_line.index("sleep 1;") < hook_line.index(fast_scan)
        assert hook_line.index(fast_scan) < hook_line.index("PICK_SESSION_THREADS=1")
        assert "--quick-only" not in hook_line

    def test_when_tmux_session_enumeration_fails_should_preserve_existing_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            cache_dir = root / "cache/tmux"
            session_scripts = home / ".config/tmux/scripts/pickers/session"
            fake_bin.mkdir()
            cache_dir.mkdir(parents=True)
            session_scripts.mkdir(parents=True)

            (session_scripts / "index.sh").symlink_to(TMUX_PICKERS / "session/executable_index.sh")
            (session_scripts / "lib").symlink_to(TMUX_PICKERS / "session/lib", target_is_directory=True)
            (home / ".config/tmux/pick_session_dir_exclude.txt").write_text("")

            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text("#!/usr/bin/env bash\nexit 1\n")
            fake_tmux.chmod(0o755)

            cache = cache_dir / "pick_session_items.tsv"
            original = (
                "existing-session\tsession\t/existing-session\t\texisting-session\n"
                "existing-worktree\tworktree\t/existing-worktree\t\texisting-worktree\n"
            )
            cache.write_text(original)
            result = subprocess.run(
                [
                    str(TMUX_PICKERS / "session/executable_index_update.sh"),
                    "--force",
                    "--quiet",
                    "--skip-dirty",
                    "--skip-gh",
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(root / "cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "unavailable",
                },
            )

            assert result.returncode != 0
            assert cache.read_text() == original

    def test_when_quick_only_refresh_runs_should_keep_cached_worktree_and_dir_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            cache_dir = root / "cache/tmux"
            session_scripts = home / ".config/tmux/scripts/pickers/session"
            fake_bin.mkdir()
            cache_dir.mkdir(parents=True)
            session_scripts.mkdir(parents=True)

            fake_index = session_scripts / "index.sh"
            fake_index.write_text("#!/usr/bin/env bash\nprintf '%s\\n' $'sess\\tsession\\t/sess\\t\\tsess\\tsess'\n")
            fake_index.chmod(0o755)
            (session_scripts / "lib").mkdir()
            (home / ".config/tmux/pick_session_dir_exclude.txt").write_text("")

            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text("#!/usr/bin/env bash\nexit 0\n")
            fake_tmux.chmod(0o755)

            cache = cache_dir / "pick_session_items.tsv"
            original = (
                "old-sess\tsession\t/old-sess\t\told-sess\told-sess\n"
                "wt\tworktree\t/wt\t\t/wt\twt\n"
                "dir\tdir\t/dir\t\t\tdir\n"
            )
            cache.write_text(original)

            result = subprocess.run(
                [
                    modern_bash(),
                    str(TMUX_PICKERS / "session/executable_index_update.sh"),
                    "--force",
                    "--quiet",
                    "--quick-only",
                    "--skip-dirty",
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(root / "cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "",
                },
            )

            kinds = {line.split("\t")[1] for line in cache.read_text().splitlines() if line.strip()}
            assert result.returncode == 0, result.stderr
            assert "worktree" in kinds
            assert "dir" in kinds
            assert "session" in kinds

    def test_when_session_create_hook_runs_should_defer_if_updater_busy(self):
        hook = TMUX_PICKERS / "session/executable_index_update_hook.sh"
        text = hook.read_text()
        assert "--quick-only" in text
        assert "--defer-if-busy" in text
        assert "--force" in text

    def test_when_open_items_writes_ordered_meta_should_use_numeric_mtime_under_gnubin_stat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "cache/tmux"
            session_scripts = root / "config/tmux/scripts/pickers/session"
            fake_bin = root / "bin"
            gnubin = fake_bin / "gnubin"
            cache_dir.mkdir(parents=True)
            session_scripts.mkdir(parents=True)
            gnubin.mkdir(parents=True)

            ordered = cache_dir / "pick_session_items_ordered.tsv"
            cache_tsv = cache_dir / "pick_session_items.tsv"
            row = "row\tsession\t/path\t\tname\tname\nwt\tworktree\t/wt\t\t/wt\twt\n"
            # Write cache first, then ordered, so ordered is not older than cache
            # (open_items treats cache -nt ordered as stale).
            cache_tsv.write_text(row)
            ordered.write_text(row)
            # GNU-shaped `stat`: -c works; -f is --file-system (multi-line dump).
            gnu_stat = gnubin / "stat"
            gnu_stat.write_text(
                """#!/usr/bin/env bash
if [[ "$1" == -c ]]; then
  fmt="$2"; shift 2
  f="$1"
  case "$fmt" in
    %Y) /usr/bin/stat -f %m "$f" ;;
    %s) /usr/bin/stat -f %z "$f" ;;
    *) exit 1 ;;
  esac
  exit $?
fi
if [[ "$1" == -f ]]; then
  echo "stat: cannot read file system information for '$2'" >&2
  echo "  File: \\"$3\\""
  echo "    ID: bogus Type: apfs"
  exit 1
fi
exit 1
"""
            )
            gnu_stat.chmod(0o755)

            open_items = session_scripts / "open_items.sh"
            open_items.write_text(
                (TMUX_PICKERS / "session/executable_open_items.sh")
                .read_text()
                .replace(
                    "$HOME/.config/tmux/scripts/pickers/session/",
                    str(session_scripts) + "/",
                )
            )
            open_items.chmod(0o755)
            (session_scripts / "lib").symlink_to(TMUX_PICKERS / "session/lib", target_is_directory=True)
            # Minimal stubs so open_items can exec filter/items if needed.
            for name in ("items.sh", "filter.sh", "ordered_cache_update.sh"):
                stub = session_scripts / name
                stub.write_text("#!/usr/bin/env bash\nexit 0\n")
                stub.chmod(0o755)

            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text(
                '#!/usr/bin/env bash\nif [[ "$1" == display-message ]]; then echo test-session; exit 0; fi\nexit 0\n'
            )
            fake_tmux.chmod(0o755)

            result = subprocess.run(
                [modern_bash(), str(open_items)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(root / "home"),
                    "XDG_CACHE_HOME": str(root / "cache"),
                    "PATH": f"{gnubin}:{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "dummy",
                },
            )
            meta = (cache_dir / "pick_session_items_ordered.current.tsv.meta").read_text().splitlines()
            assert result.returncode == 0, result.stderr
            assert len(meta) >= 3
            assert meta[0] == "test-session"
            assert meta[1].isdigit(), meta
            assert meta[2].isdigit(), meta
            assert "File:" not in meta[1]

    def test_when_rehydrate_cannot_enumerate_sessions_should_keep_cached_session_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "bin"
            cache_dir = root / "cache/tmux"
            session_path = root / "live-session"
            fake_bin.mkdir()
            cache_dir.mkdir(parents=True)
            session_path.mkdir()

            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text("#!/usr/bin/env bash\nexit 1\n")
            fake_tmux.chmod(0o755)

            cache = cache_dir / "pick_session_items.tsv"
            cache.write_text(
                f"live-session\tsession\t{session_path}\t\tlive-session\tlive-session\n"
                "other-worktree\tworktree\t/other-worktree\t\t/other-worktree\tother-worktree\n"
            )
            (cache_dir / "pick_session_pending.tsv").write_text("WT\t/pending-removal\n")
            result = subprocess.run(
                [modern_bash(), str(TMUX_PICKERS / "session/executable_items.sh")],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "XDG_CACHE_HOME": str(root / "cache"),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "unavailable",
                },
            )
            kinds = [line.split("\t")[1] for line in result.stdout.splitlines()]

            assert result.returncode == 0
            assert "session" in kinds

    def test_when_cache_changes_during_ordering_should_discard_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            session_scripts = home / ".config/tmux/scripts/pickers/session"
            cache_dir = root / "cache/tmux"
            session_scripts.mkdir(parents=True)
            cache_dir.mkdir(parents=True)

            captured = root / "captured.tsv"
            started = root / "started"
            release = root / "release"
            filter_script = session_scripts / "filter.sh"
            filter_script.write_text(
                "#!/usr/bin/env bash\n"
                'cp "$XDG_CACHE_HOME/tmux/pick_session_items.tsv" "$CAPTURED"\n'
                'touch "$STARTED"\n'
                'while [ ! -f "$RELEASE" ]; do sleep 0.01; done\n'
                'cat "$CAPTURED"\n'
            )
            filter_script.chmod(0o755)

            cache = cache_dir / "pick_session_items.tsv"
            cache.write_text("stale-worktree\tworktree\t/stale\t\t/stale\n")
            env = {
                **os.environ,
                "HOME": str(home),
                "XDG_CACHE_HOME": str(root / "cache"),
                "CAPTURED": str(captured),
                "STARTED": str(started),
                "RELEASE": str(release),
                "TMUX": "",
            }
            updater = subprocess.Popen(
                [
                    modern_bash(),
                    str(TMUX_PICKERS / "session/executable_ordered_cache_update.sh"),
                    "--quiet",
                ],
                env=env,
            )
            deadline = time.monotonic() + 2
            while not started.exists() and time.monotonic() < deadline:
                time.sleep(0.005)
            assert started.exists()

            cache.write_text(
                "live-session\tsession\t/live\t\tlive-session\nstale-worktree\tworktree\t/stale\t\t/stale\n"
            )
            release.touch()
            assert updater.wait(timeout=2) == 0
            assert not (cache_dir / "pick_session_items_ordered.tsv").exists()

    def test_when_query_settles_should_reload_one_offscreen_ranked_result(self):
        daemon = runpy.run_path(str(TMUX_PICKERS / "session/lib/sort_toggle_daemon.py"))
        runtime = daemon["run"].__globals__
        session = "ilm-session\tsession\t/session\t\t/session"
        directory = "ilm\tdir\t/directory\t\t/directory"

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.tsv"
            ranked = Path(tmp) / "ranked.tsv"
            source.write_text(f"{session}\n{directory}\n")
            actions: list[bytes] = []
            responses = iter(
                [
                    (200, json.dumps({"query": "ilm", "sort": False, "reading": False}).encode()),
                    (200, json.dumps({"query": "ilm", "sort": False, "reading": False}).encode()),
                    (200, json.dumps({"query": "ilm", "sort": False, "reading": False}).encode()),
                    (200, json.dumps({"query": "", "sort": False, "reading": False}).encode()),
                ]
            )

            class StopDaemon(BaseException):
                pass

            def http_get(_sock_path: str, _path: str) -> tuple[int, bytes]:
                try:
                    return next(responses)
                except StopIteration:
                    raise StopDaemon

            runtime["wait_for_socket"] = lambda _sock_path, _timeout_s: True
            runtime["http_get"] = http_get
            runtime["http_post_action"] = lambda _sock_path, action: actions.append(action) or 200
            runtime["fzf_ranked_matches"] = lambda _fzf_path, _source_rows, _query: [directory, session]
            runtime["DEBOUNCE_S"] = 0.0

            with self.assertRaises(StopDaemon):
                daemon["run"]("/tmp/fzf.sock", source, ranked, "/usr/bin/fzf")

            assert ranked.read_text() == f"{session}\n{directory}\n"
            assert len(actions) == 2
            assert all(action.startswith(b"reload-sync(cat ") for action in actions)
            assert all(action.endswith(b")+first") for action in actions)
            assert all(b"toggle-sort" not in action for action in actions)

    def test_when_two_sessions_share_a_path_should_keep_both_visible(self):
        grouping = runpy.run_path(str(TMUX_PICKERS / "session/lib/pick_session_grouping.py"))
        path = "/work/kibana/fix/thing"
        stray = f"ftr-console\tsession\t{path}\tsess_wt:fix/thing|repo=work/kibana\tftr-console\tm"
        named = f"work/kibana|fix/thing\tsession\t{path}\tsess_wt:fix/thing|repo=work/kibana\twork/kibana|fix/thing\tm"
        worktree = f"fix/thing\tworktree\t{path}\twt:fix/thing\t/work/kibana/main\tm"
        rows = [stray, named, named, worktree]

        deduped = grouping["dedup_best"](rows, grouping["simple_resolve"], set())

        assert deduped == [stray, named]

        ordered = grouping["grouped_output"](rows, [], grouping["simple_resolve"])
        session_names = [line.split("\t")[4] for line in ordered if line.split("\t")[1] == "session"]
        assert sorted(session_names) == ["ftr-console", "work/kibana|fix/thing"]

    def test_when_fzf_ranks_folder_first_should_preserve_kind_priority(self):
        daemon = runpy.run_path(str(TMUX_PICKERS / "session/lib/sort_toggle_daemon.py"))
        session_weak = "i___l___m\tsession\t/session-weak\t\t/session-weak"
        session_strong = "\x1b[1;38;5;81milm-session\x1b[0m\tsession\t/session-strong\t\t/session-strong"
        session_strong_match = "ilm-session\tsession\t/session-strong\t\t/session-strong"
        session_nonmatch = "other\tsession\t/session-other\t\t/session-other"
        worktree = "ilm-worktree\tworktree\t/worktree\t\t/worktree"
        directory = "ilm\tdir\t/directory\t\t/directory"
        source_rows = [session_weak, session_strong, session_nonmatch, worktree, directory]
        fzf_matches = [directory, session_strong_match, worktree, session_weak]

        ranked = daemon["rank_rows_by_kind"](source_rows, fzf_matches)

        assert ranked == [session_strong, session_weak, session_nonmatch, worktree, directory]

    def test_session_preview_classifies_antigravity_as_agent_activity(self):
        preview = TMUX_PICKERS / "session/executable_preview.sh"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bindir = tmp_path / "bin"
            bindir.mkdir()
            tmux = bindir / "tmux"
            tmux.write_text(
                "#!/bin/sh\n"
                'case "$1" in\n'
                "  display-message) printf 'agy\\t%s\\t1\\n' \"$HOME\" ;;\n"
                "  capture-pane) exit 0 ;;\n"
                "esac\n"
            )
            tmux.chmod(0o755)

            result = subprocess.run(
                [
                    modern_bash(),
                    str(preview),
                    "--kind=session",
                    f"--path={tmp_path}",
                    "--target=antigravity",
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(tmp_path), "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"},
            )

            assert result.returncode == 0, result.stderr
            plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
            assert "status  agent (agy)" in plain
            assert "busy (agy)" not in plain

    def test_pick_url_strip_cr_preserves_osc8_target_and_cleans_noise(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        hidden_target = "https://github.com/elastic/kibana/pull/281311"
        visible_url = "https://github.com/elastic/kibana/pull/281299"
        wrapped_target = "https://github.com/elastic/kibana/pull/281312"
        href_split_target = "https://github.com/elastic/kibana/pull/28131\n3"
        href_split_normalized = "https://github.com/elastic/kibana/pull/281313"
        href_escaped_target = "https://github.com/elastic/kibana/pull/28131\\n4"
        href_escaped_normalized = "https://github.com/elastic/kibana/pull/281314"
        href_repeated_escape_target = "https://github.com/elastic/kibana/pull/28131\\\\\\\\n5"
        href_repeated_escape_normalized = "https://github.com/elastic/kibana/pull/281315"
        bare_repeated_escape = "https://github.com/elastic/kibana/pull/28131\\\\\\\\n6"
        bare_repeated_escape_normalized = "https://github.com/elastic/kibana/pull/281316"
        payload = (
            f"\x1b]8;;{hidden_target}\x1b\\review\x1b]8;;\x1b\\\n"
            f"\x1b]8;;{visible_url}\x1b\\{visible_url}\x1b]8;;\x1b\\\n"
            f"\x1b]8;;{wrapped_target}\x1b\\https://github.com/elastic/kibana/pull/28131\n2\x1b]8;;\x1b\\\n"
            f"\x1b]8;;{href_split_target}\x1b\\href-split\x1b]8;;\x1b\\\n"
            f"\x1b]8;;{href_escaped_target}\x1b\\href-escaped\x1b]8;;\x1b\\\n"
            f"\x1b]8;;{href_repeated_escape_target}\x1b\\href-repeated-escape\x1b]8;;\x1b\\\n"
            f"{bare_repeated_escape}\n"
            "\x1b[31mcolor\x1b[0m\n"
            "progress 1\rprogress 2\n"
            "https://github.com/elastic/kibana/pull/281298\u200b8\n"
        )
        result = subprocess.run(["python3", str(strip_cr)], input=payload, capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert "\x1b" not in result.stdout
        assert "]8;;" not in result.stdout
        assert [line.rstrip() for line in result.stdout.splitlines()] == [
            hidden_target,
            visible_url,
            wrapped_target,
            href_split_normalized,
            href_escaped_normalized,
            href_repeated_escape_normalized,
            # Visible text keeps its literal escapes; only the extracted
            # candidate is normalized (asserted below).
            bare_repeated_escape,
            "color",
            "progress 2",
            "https://github.com/elastic/kibana/pull/2812988",
        ]

        candidates = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert candidates.returncode == 0, candidates.stderr
        assert bare_repeated_escape_normalized in candidates.stdout.splitlines()

    def test_pick_url_strip_cr_joins_wrapped_url_continuations(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        blob_url = (
            "https://github.com/elastic/kibana/blob/68b7d8f46562cd075e5e3a566dd666c3626cee5d/"
            "src/platform/plugins/shared/console/server/routes/api/console/proxy/validation_config.ts#L35"
        )

        def extract_url_candidates(text: str) -> list[str]:
            candidates = [
                match.group(0).rstrip(r"""])>}"'.,;:!?""")
                for match in re.finditer(r"(?:https?|ftp|file)://[^\s]+", text)
            ]
            unique = sorted(candidate for candidate in set(candidates) if candidate)
            pruned: list[str] = []
            for index, candidate in enumerate(unique):
                drop = False
                for next_candidate in unique[index + 1 :]:
                    if not next_candidate.startswith(candidate):
                        break
                    if len(next_candidate) > len(candidate) and (
                        candidate.endswith("/") or next_candidate[len(candidate)] == "/"
                    ):
                        drop = True
                        break
                if not drop:
                    pruned.append(candidate)
            return pruned

        slash_wrapped_url = "https://github.com/elastic/kibana/blob/main/src/plugins/validation_config.ts#L35"
        payload = (
            "│ [`path`](https://github.com/elastic/kibana/blob/68b7d8f46562cd075e5e3a566dd666c3626cee5d/src/platform/ │\n"
            "│ plugins/shared/console/server/routes/api/console/proxy/validation_config.ts#L35)? It comes straight │\n"
            "│ https://github.com/elastic/kibana/blob/main/src/plugins/ │\n"
            "│ validation_config.ts#L35 │\n"
        )

        result = subprocess.run(["python3", str(strip_cr)], input=payload, capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert extract_url_candidates(result.stdout) == [blob_url, slash_wrapped_url]
        assert (
            "https://github.com/elastic/kibana/blob/68b7d8f46562cd075e5e3a566dd666c3626cee5d/src/platform/ │"
            not in result.stdout
        )

    def test_pick_url_joins_url_wrapped_across_three_lines(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        expected = (
            "https://github.com/elastic/elasticsearch/blob/"
            "b29b887de18091afa054ada3536e2fd076aa228b/x-pack/plugin/transform/src/main/java/org/"
            "elasticsearch/xpack/transform/action/TransformPrivilegeChecker.java#L160-L183"
        )
        # The third segment (`va#L160-L183.`) carries no `/`, `?`, or `#` of its
        # own beyond the anchor, so a continuation guard keyed on those
        # characters stops after the second segment and yields a truncated URL.
        payload = (
            "  │ patterns were satisfied and only the dest were missing. See TransformPrivilegeChecker:\n"
            "  │ https://github.com/elastic/elasticsearch/blob/b29b887de18091afa054ada3536e2fd076aa228b/x-pack/plu\n"
            "  │ gin/transform/src/main/java/org/elasticsearch/xpack/transform/action/TransformPrivilegeChecker.ja\n"
            "  │ va#L160-L183.\n"
        )

        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [expected]

    def test_pick_url_keeps_bordered_prose_off_a_line_ending_url(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        # Border evidence alone cannot tell a wrap from prose that merely ends
        # on a URL, so a plain word after the border must not be glued on.
        payload = "│ See https://ex.com/docs   │\n│ Then run the installer    │\n"

        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["https://ex.com/docs"]

    def test_pick_url_canonicalizes_discussion_anchor_offset_variants(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        canonical = "https://github.com/elastic/kibana/pull/281262#discussion_r3669015246"
        payload = "\n".join(
            [
                canonical,
                f"{canonical}-",
                f"{canonical}-13",
                f"{canonical}_+13|Resolved",
                f"{canonical}_-13",
                f"{canonical}.+13",
                f"{canonical}.-13",
                f"{canonical}+13",
            ]
        )

        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [canonical]

    def test_pick_url_keeps_other_github_anchors(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = (
            "https://github.com/o/r/issues/1#issuecomment-987654\n"
            "https://github.com/o/r/pull/1#pullrequestreview-123\n"
            "https://github.com/o/r/pull/1/files#diff-abc123\n"
            "https://example.com/x#discussion_r123-suffix\n"
        )

        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "https://example.com/x#discussion_r123-suffix",
            "https://github.com/o/r/issues/1#issuecomment-987654",
            "https://github.com/o/r/pull/1#pullrequestreview-123",
            "https://github.com/o/r/pull/1/files#diff-abc123",
        ]

    def test_pick_url_keeps_legitimate_dash_suffixes(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = (
            "https://github.com/elastic/kibana/blob/main/x.ts#L10-L20\n"
            "https://example.com/a/b-1\n"
            "https://en.wikipedia.org/wiki/Foo-bar\n"
        )

        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "https://en.wikipedia.org/wiki/Foo-bar",
            "https://example.com/a/b-1",
            "https://github.com/elastic/kibana/blob/main/x.ts#L10-L20",
        ]

    def test_pick_url_keeps_unwrapped_url_line_separate_from_next_line(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = (
            "Check https://github.com/elastic/kibana/pull/1?tab=files\n"
            "src/plugins/foo.ts needs work\n"
            "  see https://github.com/o/r/pull/1?tab=files\n"
            "  src/foo.ts needs work\n"
            "done: https://ex.com/a#top\n"
            "  notes/today.md updated\n"
        )

        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "https://ex.com/a#top",
            "https://github.com/elastic/kibana/pull/1?tab=files",
            "https://github.com/o/r/pull/1?tab=files",
        ]

    def test_pick_url_extra_filter_keeps_non_url_matches(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = "ticket ABC-123 here\nsee https://ex.com/a\n"

        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates", "--extra-filter", "grep -oE '[A-Z]+-[0-9]+'"],
            input=payload,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["ABC-123", "https://ex.com/a"]

    def test_pick_url_extra_filter_keeps_stdout_from_nonzero_filter(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = "ticket ABC-123 here\nsee https://ex.com/a\n"

        result = subprocess.run(
            [
                "python3",
                str(strip_cr),
                "--extract-candidates",
                "--extra-filter",
                "grep -oE '[A-Z]+-[0-9]+'; exit 3",
            ],
            input=payload,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["ABC-123", "https://ex.com/a"]

    def test_pick_url_extra_filter_drops_blank_lines(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = "alpha\n\nbeta\n"

        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates", "--extra-filter", "cat"],
            input=payload,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["alpha", "beta"]

    def test_pick_url_preserves_literal_escape_sequences_outside_urls(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = "rename foo\\nbar.txt -> baz\nregex used: \\n and \\t here\n"

        result = subprocess.run(["python3", str(strip_cr)], input=payload, capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert result.stdout == payload

    def test_pick_url_drops_elided_ellipsis_url_candidates(self):
        script = TMUX_PICKERS.parent / "pick_url/executable_pick_url.sh"
        full_url = (
            "https://github.com/elastic/kibana/blob/68b7d8f46562cd075e5e3a566dd666c3626cee5d/"
            "src/platform/plugins/shared/console/server/routes/api/console/proxy/validation_config.ts#L35"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = tmp_path / "pane.txt"
            fixture.write_text(
                "see https://github.com/elastic/kibana/blob/.../src/platform/pl. Regression\n"
                "also https://github.com/elastic/kibana/blob/68b7d8f46562cd075e5e3a566dd666c3626cee5d/src/plat…\n"
                f"full {full_url} done\n"
                "short `https://site/x` and deeper `https://site/x/y`\n"
                "escaped https://site/x\\ and cited https://site/x/y:577:620:scripts/tests/test_tmux_pickers.py\n"
                "discussion https://github.com/elastic/kibana/pull/281262#discussion_r3669015246_+13|Resolved\n"
                "remote git@github.com:elastic/kibana.git\n"
            )
            items = tmp_path / "items.txt"
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text(
                "#!/usr/bin/env bash\n"
                'case "$1" in\n'
                '  capture-pane) cat "$TMUX_FIXTURE" ;;\n'
                "  show | display-message) exit 0 ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n"
            )
            fake_tmux.chmod(0o755)
            fake_fzf = fake_bin / "fzf"
            fake_fzf.write_text('#!/usr/bin/env bash\ncat > "$FZF_ITEMS"\nexit 1\n')
            fake_fzf.chmod(0o755)

            result = subprocess.run(
                [modern_bash(), str(script)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "TMUX": "fake",
                    "TMUX_FIXTURE": str(fixture),
                    "FZF_ITEMS": str(items),
                },
            )

            assert result.returncode == 0, result.stderr
            offered = items.read_text()
            assert full_url in offered
            assert "https://site/x/y" in offered
            assert "https://site/x`" not in offered
            assert "https://site/x\n" not in offered
            assert "https://site/x\\" not in offered
            assert "https://site/x/y:577" not in offered
            assert "https://github.com/elastic/kibana/pull/281262#discussion_r3669015246" in offered
            assert "#discussion_r3669015246_+13" not in offered
            assert "|Resolved" not in offered
            assert "https://github.com/elastic/kibana.git" in offered
            assert "blob/.../src/platform/pl" not in offered
            assert "…" not in offered

    def test_when_pick_url_captures_should_follow_viewport_and_history_contracts(self):
        script = TMUX_PICKERS.parent / "pick_url/executable_pick_url.sh"
        viewport_url = "https://example.com/viewport"
        bottom_url = "https://example.com/live-bottom"
        mismatch_url = "https://example.com/argument-mismatch"
        cases = [
            ("not in copy mode", "||38", "screen", "capture-pane -J -p -e", (bottom_url,)),
            ("copy mode at bottom", "copy-mode|0|38", "screen", "capture-pane -J -p -e", (bottom_url,)),
            (
                "shallow copy-mode scroll",
                "copy-mode|1|38",
                "screen",
                "capture-pane -J -p -e -S -1 -E 36",
                (viewport_url,),
            ),
            (
                "copy-mode visible-line boundary",
                "copy-mode|37|38",
                "screen",
                "capture-pane -J -p -e -S -37 -E 0",
                (viewport_url,),
            ),
            (
                "deep copy-mode scroll",
                "copy-mode|65|38",
                "screen",
                "capture-pane -J -p -e -S -65 -E -28",
                (viewport_url,),
            ),
            (
                "numeric limit covers viewport",
                "copy-mode|65|38",
                "100",
                "capture-pane -J -p -e -S -100",
                (viewport_url, bottom_url),
            ),
            (
                "numeric limit expands to viewport",
                "copy-mode|65|38",
                "50",
                "capture-pane -J -p -e -S -65",
                (viewport_url, bottom_url),
            ),
            (
                "numeric limit outside copy mode",
                "||38",
                "50",
                "capture-pane -J -p -e -S -50",
                (viewport_url, bottom_url),
            ),
            ("view mode keeps plain capture", "view-mode|28|38", "screen", "capture-pane -J -p -e", (bottom_url,)),
            ("tree mode keeps plain capture", "tree-mode||38", "screen", "capture-pane -J -p -e", (bottom_url,)),
            ("malformed scroll position", "copy-mode|bad|38", "screen", "capture-pane -J -p -e", (bottom_url,)),
            ("malformed pane height", "copy-mode|65|bad", "screen", "capture-pane -J -p -e", (bottom_url,)),
        ]

        for label, pane_state, history_limit, expected_capture_args, expected_urls in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                viewport = tmp_path / "viewport.txt"
                viewport.write_text(f"see {viewport_url}\n")
                bottom = tmp_path / "bottom.txt"
                bottom.write_text(f"see {bottom_url}\n")
                mismatch = tmp_path / "mismatch.txt"
                mismatch.write_text(f"see {mismatch_url}\n")
                items = tmp_path / "items.txt"
                args_log = tmp_path / "capture-args.txt"
                fake_bin = tmp_path / "bin"
                fake_bin.mkdir()
                fake_tmux = fake_bin / "tmux"
                fake_tmux.write_text(
                    "#!/usr/bin/env bash\n"
                    'case "$1" in\n'
                    "  show)\n"
                    '    if [[ "$*" == *"@pick_url_history_limit"* ]]; then printf "%s\\n" "$HISTORY_LIMIT"; fi\n'
                    "    ;;\n"
                    "  capture-pane)\n"
                    '    printf "%s\\n" "$*" > "$CAPTURE_ARGS"\n'
                    '    if [[ "$*" != "$EXPECTED_CAPTURE_ARGS" ]]; then\n'
                    '      cat "$MISMATCH_FIXTURE"\n'
                    '    elif [[ "$*" == *" -E "* ]]; then\n'
                    '      cat "$VIEWPORT_FIXTURE"\n'
                    '    elif [[ "$*" == *" -S "* ]]; then\n'
                    '      cat "$VIEWPORT_FIXTURE" "$BOTTOM_FIXTURE"\n'
                    "    else\n"
                    '      cat "$BOTTOM_FIXTURE"\n'
                    "    fi\n"
                    "    ;;\n"
                    '  display-message) [[ "$*" == *"-p"* ]] && printf "%s\\n" "$PANE_STATE" ;;\n'
                    "  *) exit 0 ;;\n"
                    "esac\n"
                )
                fake_tmux.chmod(0o755)
                fake_fzf = fake_bin / "fzf"
                fake_fzf.write_text('#!/usr/bin/env bash\ncat > "$FZF_ITEMS"\nexit 1\n')
                fake_fzf.chmod(0o755)

                result = subprocess.run(
                    [modern_bash(), str(script)],
                    capture_output=True,
                    text=True,
                    env={
                        **os.environ,
                        "PATH": f"{fake_bin}:{os.environ['PATH']}",
                        "TMUX": "fake",
                        "HISTORY_LIMIT": history_limit,
                        "PANE_STATE": pane_state,
                        "EXPECTED_CAPTURE_ARGS": expected_capture_args,
                        "BOTTOM_FIXTURE": str(bottom),
                        "VIEWPORT_FIXTURE": str(viewport),
                        "MISMATCH_FIXTURE": str(mismatch),
                        "CAPTURE_ARGS": str(args_log),
                        "FZF_ITEMS": str(items),
                    },
                )

                assert result.returncode == 0, result.stderr
                assert args_log.read_text().strip() == expected_capture_args, args_log.read_text()
                offered = items.read_text()
                for url in (viewport_url, bottom_url, mismatch_url):
                    assert (url in offered) is (url in expected_urls)

    def test_pick_url_joins_unbordered_wrapped_urls_across_lines(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = (
            "1. Removed Last Commit: Reset branch chore/console/cloud-deploy-284530 https://github.\n"
            "com/elastic/kibana/pull/286090 to commit 0c22ea648202 https://github.\n"
            "com/elastic/kibana/commit/0c22ea64820231ffc82d8c911375646c7de51437 (removing 3b89441cba29) and force-\n"
            "pushed to origin.\n"
            "2. Retriggered Cloud Deployment:\n"
            "  • Buildkite Build: kibana-deploy-cloud-from-pr #1344 https://buildkite.com/elastic/kibana-deploy-\n"
            "    cloud-from-pr/builds/1344\n"
            "  • Commit: 0c22ea64820231ffc82d8c911375646c7de51437 https://github.\n"
            "    com/elastic/kibana/commit/0c22ea64820231ffc82d8c911375646c7de51437\n"
            "  • PR: #286090 https://github.com/elastic/kibana/pull/286090\n"
        )
        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "https://buildkite.com/elastic/kibana-deploy-cloud-from-pr/builds/1344",
            "https://github.com/elastic/kibana/commit/0c22ea64820231ffc82d8c911375646c7de51437",
            "https://github.com/elastic/kibana/pull/286090",
        ]

    def test_pick_url_drops_bare_incomplete_host_candidates(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = (
            "standalone https://github and https://buildkite\n"
            "valid http://localhost and http://localhost:3000\n"
            "valid with path http://internal-wiki/docs and https://site/x/y\n"
            "valid domain https://github.com\n"
        )
        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "http://internal-wiki/docs",
            "http://localhost",
            "http://localhost:3000",
            "https://github.com",
            "https://site/x/y",
        ]

    def test_pick_url_joins_alphabetic_fragments_after_strong_url_continuation_evidence(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = (
            "host https://github.\n"
            "com\n"
            "path https://example.com/cloud-\n"
            "deploy\n"
            "query https://example.com/?q=\n"
            "value\n"
            "fragment https://example.com/page#\n"
            "section\n"
        )
        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "https://example.com/?q=value",
            "https://example.com/cloud-deploy",
            "https://example.com/page#section",
            "https://github.com",
        ]

    def test_pick_url_does_not_join_following_markdown_list_items(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = (
            "root https://example.com/\n"
            "- next item\n"
            "hyphen https://example.com/path-\n"
            "- another item\n"
            "numbered https://example.com/docs/\n"
            "1. first item\n"
        )
        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "https://example.com/docs/",
            "https://example.com/path-",
        ]

    def test_pick_url_does_not_join_unbordered_prose_after_trailing_slash(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = (
            "root https://example.com/\n"
            "**Note:** this is prose\n"
            "docs https://docs.example.com/\n"
            "### Next section\n"
            "details https://example.net/\n"
            "(Details) follow\n"
            "linked https://linked.example/\n"
            "[Docs](https://other.example/) follows\n"
        )
        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "https://docs.example.com/",
            "https://example.com/",
            "https://example.net/",
            "https://linked.example/",
            "https://other.example/",
        ]

    def test_pick_url_requires_borders_on_both_lines_for_trailing_slash_wraps(self):
        strip_cr = TMUX_PICKERS.parent / "pick_url/lib/strip_cr.py"
        payload = (
            "root https://base.example/\n"
            "│ [Docs](https://docs.example/path) │\n"
            "│ framed https://framed.example/ │\n"
            "[Other](https://other.example/path) follows\n"
        )
        result = subprocess.run(
            ["python3", str(strip_cr), "--extract-candidates"], input=payload, capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "https://base.example/",
            "https://docs.example/path",
            "https://framed.example/",
            "https://other.example/path",
        ]

    def test_gh_picker_uses_stable_identity_for_multi_selection_reload_sync(self):
        """WHEN display text changes, SHOULD key multi-selection by kind/repo/num."""
        picker = TMUX_PICKERS / "github/executable_gh_picker.sh"
        text = picker.read_text()
        assert "--id-nth=2,3,4" in text
        assert re.search(r"--multi\b", text)


class TestGhRowLoaderSpinnerOrdering(unittest.TestCase):
    """WHEN a row-loader spinner is stopped mid-render."""

    SPINNER_GLYPHS = ("◐", "◓", "◑", "◒")

    def test_each_spinner_waits_for_its_direct_post_children(self):
        source = (TMUX_PICKERS / "github/lib/executable_gh_row_loader.sh").read_text()
        assert source.count("trap '_gh_row_loader_spinner_cleanup \"$token\"' EXIT") == 3
        assert source.count("trap 'exit 0' TERM INT") == 3
        assert 'wait "$post_pid" 2> /dev/null || true' in source
        assert '(curl -s --max-time 1 -XPOST "http://127.0.0.1:${port}"' not in source
        callers = "\n".join(
            (TMUX_PICKERS / path).read_text()
            for path in (
                "github/executable_gh_batch_worktree.sh",
                "github/executable_gh_comment.sh",
                "github/lib/executable_gh_picker_palette.sh",
                "github/lib/executable_gh_row_loader.sh",
            )
        )
        assert '="$(gh_row_loader_start_' not in callers

    def _setup_fixture(self, tmp_path: Path) -> dict[str, Path]:
        picker_dir = tmp_path / "pickers/github"
        lib_dir = picker_dir / "lib"
        lib_dir.mkdir(parents=True)
        for name, target in (
            ("executable_gh_row_loader.sh", "gh_row_loader.sh"),
            ("gh_patch_picker_cache.py", "gh_patch_picker_cache.py"),
        ):
            (lib_dir / target).write_text((TMUX_PICKERS / "github/lib" / name).read_text())

        cache_dir = tmp_path / "cache/tmux"
        cache_dir.mkdir(parents=True)
        # One row whose marker cell is a plain space (no worktree): display is
        # state-icon + reset+space + marker-space + trailing text.
        (cache_dir / "gh_picker_work.tsv").write_text(
            "\x1b[32m●\x1b[0m  row-one\tpr\towner/repo\t1\thttps://example.test/1\n"
        )

        items_cmd = picker_dir / "gh_items.sh"
        items_cmd.write_text(
            "#!/usr/bin/env bash\n"
            'cache_file="$XDG_CACHE_HOME/tmux/gh_picker_${GH_PICKER_MODE:-work}.tsv"\n'
            'if [ "${1:-}" = "--refresh" ]; then\n'
            "  printf '\\033[32m●\\033[0m  row-refreshed\\tpr\\towner/repo\\t1\\thttps://example.test/1\\n' > \"$cache_file\"\n"
            "fi\n"
            # Slow render keeps a spinner frame in flight when stop lands.
            'sleep "${RENDER_SLEEP:-0}"\n'
            'cat "$cache_file"\n'
        )
        items_cmd.chmod(0o755)

        stub_bin = tmp_path / "bin"
        stub_bin.mkdir()
        posts_log = tmp_path / "posts.log"
        curl_start_log = tmp_path / "curl-start.log"
        curl_stub = stub_bin / "curl"
        curl_stub.write_text(
            "#!/usr/bin/env bash\n"
            # Log the rendered list content fzf would show (what the reload-sync
            # command prints), delayed for spinner frames so a stale frame lands
            # AFTER the authoritative stop render unless the loop aborts it.
            'body="${@: -1}"\n'
            'cmd="${body#reload-sync(}"\n'
            'cmd="${cmd%%)+*}"\n'
            '  out="$("$cmd" 2>/dev/null || true)"\n'
            '  printf \'START %s\\n\' "$out" >> "$CURL_START_LOG"\n'
            "  if printf '%s' \"$out\" | grep -q '◐\\|◓\\|◑\\|◒'; then\n"
            '    sleep "${CURL_STUB_DELAY:-0.2}"\n'
            "  elif [ \"${DELAY_ROW_ONE:-0}\" = 1 ] && printf '%s' \"$out\" | grep -q 'row-one'; then\n"
            '    sleep "${CURL_STUB_DELAY:-0.2}"\n'
            "  fi\n"
            '  printf \'POST %s\\n\' "$out" >> "$POSTS_LOG"\n'
            "exit 0\n"
        )
        curl_stub.chmod(0o755)

        return {
            "picker_dir": picker_dir,
            "cache_dir": cache_dir,
            "items_cmd": items_cmd,
            "stub_bin": stub_bin,
            "posts_log": posts_log,
            "curl_start_log": curl_start_log,
        }

    def test_stopped_spinner_cannot_clobber_final_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._setup_fixture(Path(tmp))
            lib = fixture["picker_dir"] / "lib/gh_row_loader.sh"
            harness = "\n".join(
                [
                    "set -euo pipefail",
                    f". {shlex.quote(str(lib))}",
                    "gh_row_loader_start_item pr owner/repo 1 work all "
                    + shlex.quote(str(fixture["items_cmd"]))
                    + " >/dev/null",
                    'pid="$gh_row_loader_last_pid"',
                    # Stop while the first frame is still rendering (RENDER_SLEEP=0.12).
                    "sleep 0.06",
                    (f'gh_row_loader_stop_spinner "$pid" work all {shlex.quote(str(fixture["items_cmd"]))}'),
                ]
            )
            env = {
                **os.environ,
                "XDG_CACHE_HOME": str(fixture["cache_dir"].parent),
                "PATH": f"{fixture['stub_bin']}:{os.environ['PATH']}",
                "POSTS_LOG": str(fixture["posts_log"]),
                "CURL_START_LOG": str(fixture["curl_start_log"]),
                "RENDER_SLEEP": "0.12",
                "FZF_PORT": "1",
            }
            subprocess.run([modern_bash(), "-c", harness], check=True, env=env)

            # Wait past the fake curl delay so a stale post would land if cleanup failed.
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline and not fixture["posts_log"].exists():
                time.sleep(0.01)
            time.sleep(0.4)
            posts = fixture["posts_log"].read_text().splitlines()
            assert posts, "stop_spinner never posted the authoritative render"
            last = posts[-1]
            assert "row-one" in last
            assert not any(glyph in last for glyph in self.SPINNER_GLYPHS), posts

    def test_direct_spinner_callers_stop_children_from_exit_cleanup(self):
        comment = (TMUX_PICKERS / "github/executable_gh_comment.sh").read_text()
        palette = (TMUX_PICKERS / "github/lib/executable_gh_picker_palette.sh").read_text()

        assert comment.count("trap cleanup EXIT") == 1
        assert 'gh_row_loader_stop_spinner "$row_loader_pid"' in comment
        assert 'row_loader_pid=""' in comment

        assert palette.count("trap cleanup EXIT") == 1
        assert (
            'gh_row_loader_stop_spinner "$row_loader_pid" "${mode:-work}" "${scope:-all}" "${items_cmd:-}"' in palette
        )
        assert 'gh_row_loader_stop_spinner "$row_loader_pid" "$mode" "$scope" "$items_cmd"' in palette
        assert palette.index(
            'gh_row_loader_stop_spinner "$row_loader_pid" "$mode" "$scope" "$items_cmd"'
        ) < palette.index('GH_PICKER_MODE="$mode" GH_PICKER_SCOPE="$scope" "$items_cmd" --refresh')


if __name__ == "__main__":
    unittest.main()
