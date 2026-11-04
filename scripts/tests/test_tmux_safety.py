#!/usr/bin/env python3
"""Isolated behavioral checks for picker deletion, identity and writer safety."""

from __future__ import annotations

import contextlib
import fcntl
import io
import json
import os
import re
import runpy
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from _test_support import REPO, TMUX_PICKERS, modern_bash


class _PickerCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "home"
        self.pickers = self.home / ".config/tmux/scripts/pickers"
        for source in TMUX_PICKERS.rglob("*"):
            if not source.is_file() or "__pycache__" in source.parts:
                continue
            relative = source.relative_to(TMUX_PICKERS)
            target = self.pickers / relative.parent / relative.name.removeprefix("executable_")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            target.chmod(0o755 if relative.name.startswith("executable_") else 0o644)
        shared = self.home / "lib/shared"
        shared.mkdir(parents=True)
        (shared / "worktree_nested_git.py").write_bytes(
            (REPO / "home/exact_lib/exact_shared/worktree_nested_git.py").read_bytes()
        )
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.cache = self.root / "cache/tmux"
        self.cache.mkdir(parents=True)
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Picker Test",
            "GIT_AUTHOR_EMAIL": "picker@example.invalid",
            "GIT_COMMITTER_NAME": "Picker Test",
            "GIT_COMMITTER_EMAIL": "picker@example.invalid",
        }
        self.env.pop("TMUX", None)
        self.stub("tmux", "exit 1")
        self.stub("zoxide", "exit 0")

    def stub(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)

    def shell(self, script: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [modern_bash(), str(script), *args], env={**self.env, **env}, capture_output=True, text=True, timeout=15
        )

    def git(self, cwd: Path, *args: str) -> str:
        return subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args],
            cwd=cwd,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()


class PickerSafetyTests(_PickerCase):
    def test_palette_dispatches_each_selected_entity_once(self) -> None:
        selection = self.root / "palette-selection.tsv"
        scope = self.root / "scope"
        scope.write_text("all")
        calls = self.root / "github-calls.jsonl"
        self.stub("items", "exit 0")
        self.stub("curl", "exit 0")
        (self.bin / "fzf").write_text(
            f"#!{sys.executable}\nimport os,sys\n"
            "for line in sys.stdin:\n"
            "    if line.startswith(os.environ['PALETTE_VERB']+'|'):\n"
            "        print(line.strip()); sys.exit(0)\n"
            "sys.exit(1)\n"
        )
        (self.bin / "fzf").chmod(0o755)
        (self.bin / "gh").write_text(
            f"#!{sys.executable}\nimport json,os,sys\n"
            "with open(os.environ['GH_ACTION_LOG'],'a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')\n"
        )
        (self.bin / "gh").chmod(0o755)

        def row(label, kind, repo, num, parent="", role=""):
            return "\t".join([label, kind, repo, num, "url", label, "", "", "", "", "", parent, role, ""])

        parents = [
            row("parent A", "pr", "owner/repo", "7", role="parent"),
            row("parent B", "pr", "owner/repo", "7", role="parent"),
        ]
        family = [
            parents[0],
            row("child A", "pr", "owner/repo", "8", "pr:owner/repo:7", "child"),
            parents[1],
            row("child B", "pr", "owner/repo", "9", "pr:owner/repo:7", "child"),
        ]
        marked = subprocess.run(
            [sys.executable, str(self.pickers / "github/lib/gh_picker_mark_subtree.py"), "1"],
            input="\n".join(family),
            capture_output=True,
            text=True,
            env=self.env,
            check=True,
            timeout=5,
        )
        positions = [int(value) for value in re.findall(r"pos\((\d+)\)\+toggle", marked.stdout)]
        self.assertEqual(positions, [1, 2, 3, 4])
        selected_family = [family[position - 1] for position in positions]
        selected_family += [
            row("other repo", "pr", "owner/other", "7"),
            row("issue", "issue", "owner/issues", "7"),
            row("missing", "header", "owner/repo", "0"),
        ]
        for verb, rows, expected in (
            (
                "comment",
                selected_family,
                [
                    ("pr", "owner/repo", "7"),
                    ("pr", "owner/repo", "8"),
                    ("pr", "owner/repo", "9"),
                    ("pr", "owner/other", "7"),
                    ("issue", "owner/issues", "7"),
                ],
            ),
            ("approve", parents, [("pr", "owner/repo", "7")]),
        ):
            with self.subTest(verb=verb):
                selection.write_text("\n".join(rows) + "\n")
                calls.write_text("")
                env = {**self.env, "PALETTE_VERB": verb, "GH_ACTION_LOG": str(calls)}
                env.pop("FZF_SOCK", None)
                result = subprocess.run(
                    [
                        modern_bash(),
                        str(self.pickers / "github/lib/gh_picker_palette.sh"),
                        str(selection),
                        str(scope),
                        str(self.bin / "items"),
                    ],
                    input="fixture comment\n",
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                argv = [json.loads(line) for line in calls.read_text().splitlines()]
                self.assertEqual([(args[0], args[args.index("-R") + 1], args[2]) for args in argv], expected)

    def test_root_selection_preserves_complete_worktree_paths_in_preflight(self) -> None:
        main = self.home / "code/repo with spaces/main"
        main.mkdir(parents=True)
        linked = main.parent / "feature one"
        self.git(main, "init", "-q", "-b", "main")
        self.git(main, "commit", "--allow-empty", "-qm", "base")
        self.git(main, "worktree", "add", "-q", "-b", "feature", str(linked))
        args_log = self.root / "preflight.json"
        command = self.bin / ",w"
        command.write_text(
            f"#!{sys.executable}\nimport json, sys\n"
            f"with open({str(args_log)!r}, 'w') as out: json.dump(sys.argv[1:], out)\n"
        )
        command.chmod(0o755)
        selection = self.root / "selection"
        selection.write_text(f"repo\tworktree\t{main}\twt_root:main\t{main}\n")

        result = self.shell(self.pickers / "session/action_remove_worktrees.sh", "--check", str(selection))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(args_log.read_text()), ["remove", "--preflight", "--paths", str(linked), str(main)])
        self.assertTrue(main.exists())
        self.assertTrue(linked.exists())

    def test_root_remover_preserves_stashes_and_notes_until_forced(self) -> None:
        (self.pickers / "session/index_update.sh").write_text("#!/bin/sh\nexit 0\n")
        script = self.pickers / "session/remove_all_worktrees.sh"
        for kind, ref in (("stash", "refs/stash"), ("notes", "refs/notes/commits")):
            with self.subTest(kind=kind):
                main = self.home / f"code/{kind}/main"
                main.mkdir(parents=True)
                self.git(main, "init", "-q", "-b", "main")
                (main / "README").write_text("base\n")
                self.git(main, "add", "README")
                self.git(main, "commit", "-qm", "base")
                published = self.git(main, "rev-parse", "HEAD")
                self.git(main, "update-ref", "refs/remotes/origin/main", published)
                if kind == "stash":
                    (main / "README").write_text("private stashed work\n")
                    self.git(main, "stash", "push", "-qm", "private work")
                else:
                    self.git(main, "notes", "add", "-m", "private note", "HEAD")
                unique = self.git(main, "rev-parse", ref)
                self.assertEqual(self.git(main, "status", "--porcelain"), "")
                self.assertEqual(self.git(main, "rev-parse", "HEAD"), published)

                refused = self.shell(script, str(main))

                self.assertEqual(refused.returncode, 3, refused.stderr)
                self.assertTrue((main / ".git").is_dir())
                self.assertEqual(self.git(main, "cat-file", "-t", unique), "commit")
                forced = self.shell(script, str(main), "1")
                self.assertEqual(forced.returncode, 0, forced.stderr)
                self.assertFalse(main.exists())

    def test_root_remover_deletes_clean_published_checkout(self) -> None:
        (self.pickers / "session/index_update.sh").write_text("#!/bin/sh\nexit 0\n")
        main = self.home / "code/published/main"
        main.mkdir(parents=True)
        self.git(main, "init", "-q", "-b", "main")
        self.git(main, "commit", "--allow-empty", "-qm", "base")
        self.git(main, "update-ref", "refs/remotes/origin/main", "HEAD")

        removed = self.shell(self.pickers / "session/remove_all_worktrees.sh", str(main))

        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(main.exists())

    def test_root_remover_refuses_dirty_checkout_and_local_only_history(self) -> None:
        main = self.home / "code/repo with spaces/main"
        main.mkdir(parents=True)
        self.git(main, "init", "-q", "-b", "main")
        self.git(main, "commit", "--allow-empty", "-qm", "base")
        self.git(main, "update-ref", "refs/remotes/origin/main", "HEAD")
        (main / "notes").write_text("unsaved\n")
        script = self.pickers / "session/remove_all_worktrees.sh"

        dirty = self.shell(script, str(main))

        self.assertEqual(dirty.returncode, 3, dirty.stderr)
        self.assertEqual((main / "notes").read_text(), "unsaved\n")
        (main / "notes").unlink()
        self.git(main, "commit", "--allow-empty", "-qm", "local-only")
        local_only = self.shell(script, str(main))
        self.assertEqual(local_only.returncode, 3, local_only.stderr)
        self.assertTrue((main / ".git").exists())

    def test_root_remover_preserves_detached_sibling_commits_after_preflight(self) -> None:
        main = self.home / "code/repo/main"
        main.mkdir(parents=True)
        self.git(main, "init", "-q", "-b", "main")
        self.git(main, "commit", "--allow-empty", "-qm", "base")
        self.git(main, "update-ref", "refs/remotes/origin/main", "HEAD")
        linked = main.parent / "detached"
        self.git(main, "worktree", "add", "-q", "--detach", str(linked))
        self.git(linked, "commit", "--allow-empty", "-qm", "after preflight")
        unique = self.git(linked, "rev-parse", "HEAD")

        result = self.shell(self.pickers / "session/remove_all_worktrees.sh", str(main))

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertTrue(main.exists())
        self.assertTrue(linked.exists())
        self.assertEqual(self.git(main, "cat-file", "-t", unique), "commit")

    def test_root_removal_preserves_initialized_and_deinitialized_submodule_history(self) -> None:
        source = self.root / "module-source"
        source.mkdir()
        self.git(source, "init", "-q", "-b", "main")
        self.git(source, "commit", "--allow-empty", "-qm", "base")
        module_origin = self.root / "module.git"
        self.git(self.root, "clone", "-q", "--bare", str(source), str(module_origin))
        main = self.home / "code/repo/main"
        main.mkdir(parents=True)
        self.git(main, "init", "-q", "-b", "main")
        self.git(main, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(module_origin), "module")
        module = main / "module"
        self.git(module, "commit", "--allow-empty", "-qm", "local module history")
        unique = self.git(module, "rev-parse", "HEAD")
        module_admin = Path(self.git(module, "rev-parse", "--absolute-git-dir"))
        self.git(main, "add", "module", ".gitmodules")
        self.git(main, "commit", "-qm", "record module")
        super_origin = self.root / "super.git"
        self.git(self.root, "init", "--bare", "-q", str(super_origin))
        self.git(main, "remote", "add", "origin", str(super_origin))
        self.git(main, "push", "-q", "origin", "HEAD:refs/heads/main")
        self.assertEqual(self.git(main, "status", "--porcelain"), "")
        remover = self.pickers / "session/remove_all_worktrees.sh"

        initialized = self.shell(remover, str(main))

        self.assertEqual(initialized.returncode, 3, initialized.stderr)
        self.assertIn("submodule", initialized.stderr)
        self.assertEqual(self.git(main, "--git-dir", str(module_admin), "cat-file", "-t", unique), "commit")
        self.git(main, "submodule", "deinit", "-f", "--", "module")
        self.git(main, "rm", "-q", "-f", "module")
        self.git(main, "commit", "-qm", "remove module tracking")
        self.git(main, "push", "-q", "origin", "HEAD:refs/heads/main")

        deinitialized = self.shell(remover, str(main))

        self.assertEqual(deinitialized.returncode, 3, deinitialized.stderr)
        self.assertIn("submodule history", deinitialized.stderr)
        self.assertEqual(self.git(main, "--git-dir", str(module_admin), "cat-file", "-t", unique), "commit")

    def test_check_mode_does_not_release_another_actions_cache_locks(self) -> None:
        cache_lock = self.cache / "pick_session_items.tsv.lock"
        pending_lock = self.cache / "pick_session_pending.tsv.lock"
        cache_lock.mkdir()
        pending_lock.mkdir()
        selection = self.root / "selection"
        selection.write_text(f"folder\tdir\t{self.home}\t\t\n")

        result = self.shell(self.pickers / "session/action_remove_worktrees.sh", "--check", str(selection))

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertTrue(cache_lock.is_dir())
        self.assertTrue(pending_lock.is_dir())

    def test_failed_preflight_cannot_be_treated_as_safe(self) -> None:
        main = self.home / "main"
        main.mkdir()
        (main / ".git").mkdir()
        self.stub(",w", "exit 1")
        selection = self.root / "selection"
        selection.write_text(f"repo\tworktree\t{main}\twt:feature\t{main.parent}\n")
        # Keep the git root resolvable; the external preflight itself is the failure.
        self.stub("git", "exit 0")

        result = self.shell(self.pickers / "session/action_remove_worktrees.sh", "--check", str(selection))

        self.assertEqual(result.returncode, 3)
        self.assertFalse((self.cache / "pick_session_mutations.tsv").exists())

    def test_palette_preview_and_microphone_help_never_execute_device_changes(self) -> None:
        changed = self.root / "device-changed"
        self.stub(",dangerous", f'touch "{changed}"')
        palette = REPO / "home/dot_config/exact_tmux/exact_scripts/command_palette/executable_palette.sh"

        preview = self.shell(palette, "--preview", "bin:,dangerous", ",dangerous")

        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertFalse(changed.exists())
        self.assertIn("Command: ,dangerous", preview.stdout)
        self.stub("SwitchAudioSource", f'touch "{changed}"\nprintf "MacBook Pro Microphone\\n"')
        microphone = REPO / "home/exact_bin/executable_,set-default-mic"
        for argument in ("--help", "--unknown"):
            result = self.shell(microphone, argument)
            self.assertEqual(result.returncode, 0 if argument == "--help" else 2)
            self.assertFalse(changed.exists())

    def test_dashboard_cold_start_preserves_paths_and_outer_client_as_data(self) -> None:
        home = self.root / "person's $(touch PWNED) home"
        home.mkdir()
        record = self.root / "dashboard.json"
        startup = self.root / "dashboard-startup.sh"
        startup.write_text(f"export PATH={shlex.quote(self.env['PATH'])}\n")
        socket = str(self.root / 'socket "$(touch PWNED)"')
        client = 'client"; touch PWNED; #'
        gh = self.bin / "gh"
        gh.write_text(
            f"#!{sys.executable}\n"
            "import json, os, signal, sys\n"
            "if sys.argv[1:] == ['dash', '--version']: sys.exit(0)\n"
            f"with open({str(record)!r}, 'w') as out:\n"
            "    json.dump([sys.argv[1:], {key: os.environ.get(key) for key in "
            "['GH_DASH_POPUP', 'OUTER_TMUX_SOCKET', 'OUTER_TMUX_CLIENT']}], out)\n"
            "os.kill(os.getppid(), signal.SIGTERM)\n"
        )
        gh.chmod(0o755)
        tmux = self.bin / "tmux"
        tmux.write_text(
            f"#!{sys.executable}\n"
            "import os, signal, subprocess, sys\n"
            "args = sys.argv[1:]\n"
            "if 'has-session' in args: sys.exit(1)\n"
            f"if args[:2] == ['display-message', '-p']: print({client!r})\n"
            "if 'new-session' in args:\n"
            "    index = args.index('-c')\n"
            "    command = args[index + 2:]\n"
            "    if len(command) == 1: command = ['/bin/sh', '-c', command[0]]\n"
            "    child = subprocess.Popen(command, cwd=args[index + 1], start_new_session=True)\n"
            "    try: child.wait(timeout=5)\n"
            "    finally:\n"
            "        if child.poll() is None:\n"
            "            os.killpg(child.pid, signal.SIGKILL)\n"
            "            child.wait()\n"
            f"    sys.exit(0 if os.path.exists({str(record)!r}) else 1)\n"
        )
        tmux.chmod(0o755)
        script = REPO / "home/dot_config/exact_tmux/exact_scripts/gh_dash/executable_popup.sh"

        result = subprocess.run(
            [modern_bash(), str(script)],
            cwd=home,
            env={**self.env, "HOME": str(home), "TMUX": f"{socket},123,0", "BASH_ENV": str(startup)},
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(record.read_text()),
            [
                ["dash", "--config", str(home / ".config/gh-dash/config.yml")],
                {"GH_DASH_POPUP": "1", "OUTER_TMUX_SOCKET": socket, "OUTER_TMUX_CLIENT": client},
            ],
        )
        self.assertFalse((home / "PWNED").exists())

    def test_popup_launchers_pass_direct_argv_without_mutating_server_shell(self) -> None:
        calls = self.root / "tmux.jsonl"
        tmux = self.bin / "tmux"
        tmux.write_text(
            f"#!{sys.executable}\nimport json, sys\n"
            f"with open({str(calls)!r}, 'a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')\n"
            "if sys.argv[1]=='display-message': print('40|80')\n"
        )
        tmux.chmod(0o755)
        prompt = self.home / ".config/tmux/scripts/gh_tfork/prompt.sh"
        prompt.parent.mkdir(parents=True)
        prompt.write_text("#!/bin/sh\nexit 0\n")
        prompt.chmod(0o755)
        launchers = [
            (self.pickers / "session/popup.sh", "/bin/bash"),
            (self.pickers / "github/gh_popup.sh", "/bin/bash"),
            (REPO / "home/dot_config/exact_tmux/exact_scripts/command_palette/executable_popup.sh", "/bin/bash"),
            (REPO / "home/dot_config/exact_tmux/exact_scripts/gh_tfork/executable_popup.sh", "/bin/bash"),
            (REPO / "home/dot_config/exact_tmux/exact_scripts/gh_dash/executable_popup.sh", "tmux"),
        ]
        for script, command in launchers:
            with self.subTest(script=script):
                calls.write_text("")
                result = self.shell(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                actual = [json.loads(line) for line in calls.read_text().splitlines()]
                self.assertFalse(any("default-shell" in call for call in actual), actual)
                popup = next(call for call in actual if call[0] == "display-popup")
                if command == "/bin/bash":
                    self.assertEqual(popup[-2], command)
                    self.assertTrue(popup[-1].endswith(".sh"))
                else:
                    self.assertEqual(popup[-6:], ["tmux", "-L", "gh-dash-popup", "attach", "-t", "dash"])

    def test_preview_keeps_target_after_empty_metadata(self) -> None:
        calls = self.root / "tmux.jsonl"
        tmux = self.bin / "tmux"
        tmux.write_text(
            f"#!{sys.executable}\nimport json, sys\n"
            f"with open({str(calls)!r}, 'a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')\n"
        )
        tmux.chmod(0o755)
        row = f"session\tsession\t{self.home}\t\tactual-session\tsearch words"

        result = self.shell(self.pickers / "session/preview.sh", row)

        self.assertEqual(result.returncode, 0, result.stderr)
        actual = [json.loads(line) for line in calls.read_text().splitlines()]
        self.assertTrue(any("=actual-session" in call or "actual-session" in call for call in actual), actual)
        self.assertFalse(any("search words" in call for call in actual), actual)

    def test_preview_of_stale_session_does_not_fall_back_to_a_prefix_match(self) -> None:
        tmux = self.bin / "tmux"
        tmux.write_text("#!/bin/sh\ncase \"$*\" in *'-t dev'*) printf 'PRIVATE DEVELOPMENT PANE\\n';; esac\n")
        tmux.chmod(0o755)
        row = f"session\tsession\t{self.home}\t\tdev\tsearch"

        result = self.shell(self.pickers / "session/preview.sh", row)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PRIVATE DEVELOPMENT PANE", result.stdout)


class PickerWriterTests(_PickerCase):
    def test_parallel_frecency_updates_all_survive(self) -> None:
        directory = self.home / "project"
        directory.mkdir()
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]); import frecency; "
            "[frecency.add(sys.argv[2]) for _ in range(20)]"
        )
        processes = [
            subprocess.Popen(
                [sys.executable, "-c", code, str(self.pickers / "session/lib"), str(directory)],
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(4)
        ]
        for process in processes:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stdout + stderr)
        row = (self.cache / "pick_session_frecency.tsv").read_text().split("\t")
        self.assertEqual(float(row[1]), 80)

    def test_publish_pruning_honors_pending_and_mutation_writer_locks(self) -> None:
        cache = self.cache / "items.tsv"
        cache.write_text(f"home\tdir\t{self.home}\t\t\n")
        publisher = self.pickers / "session/lib/publish_cache_filter.py"
        for resource_name, contents in (
            ("pending.tsv", f"WT\t{self.home}\n"),
            ("mutations.tsv", f"0\tPATH_PREFIX\t{self.home}\n"),
        ):
            with self.subTest(resource=resource_name):
                resource = self.cache / resource_name
                resource.write_text(contents)
                env = {
                    **self.env,
                    "CACHE_FILE": str(cache),
                    "CACHE_OUT": str(self.cache / "out"),
                    "PENDING_FILE": str(resource) if resource_name == "pending.tsv" else "",
                    "MUTATIONS_FILE": str(resource) if resource_name == "mutations.tsv" else "",
                }
                with Path(str(resource) + ".flock").open("a") as owner:
                    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    with patch.dict(os.environ, env, clear=True), patch("time.monotonic", side_effect=[0, 11]):
                        with self.assertRaises(TimeoutError):
                            runpy.run_path(str(publisher))
                self.assertEqual(resource.read_text(), contents)

    def test_marker_update_uses_new_lock_namespace_without_deleting_legacy_directory(self) -> None:
        cache = self.cache / "gh_picker.tsv"
        cache.write_text("\x1b[32m●\x1b[0m   row\tpr\towner/repo\t1\turl\n")
        legacy_lock = Path(str(cache) + ".lock")
        legacy_lock.mkdir()
        (legacy_lock / "pid").write_text("old-owner")

        result = subprocess.run(
            [
                sys.executable,
                str(self.pickers / "github/lib/gh_patch_picker_cache.py"),
                "--cache-file",
                str(cache),
                "--kind",
                "pr",
                "--repo",
                "owner/repo",
                "--num",
                "1",
            ],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=5,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("◆", cache.read_text())
        self.assertEqual((legacy_lock / "pid").read_text(), "old-owner")

    def test_index_publisher_does_not_reap_a_live_cache_injector(self) -> None:
        cache = self.cache / "pick_session_items.tsv"
        published = f"publisher\tdir\t{self.home}/published\t\t\n"
        cache.write_text(published)
        lock = Path(str(cache) + ".lock")
        lock.mkdir()
        marker = self.root / "index-started"
        generator = self.pickers / "session/index.sh"
        generator.write_text(f"#!/bin/sh\ntouch '{marker}'\nprintf '%s\n' '{published.rstrip()}'\n")
        generator.chmod(0o755)
        (self.pickers / "session/ordered_cache_update.sh").write_text("#!/bin/sh\nexit 0\n")
        lookalike = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", "/tmp/index_update.sh"])
        try:
            for owner in (str(os.getpid()), "", str(lookalike.pid)):
                with self.subTest(owner=owner):
                    (lock / "pid").write_text(owner)
                    result = self.shell(self.pickers / "session/index_update.sh", "--force", "--quiet", "--quick-only")

                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIsNone(lookalike.poll(), "forced refresh signaled an unverified lookalike process")
                    self.assertFalse(marker.exists())
                    self.assertEqual(cache.read_text(), published)
                    self.assertEqual((lock / "pid").read_text(), owner)
        finally:
            if lookalike.poll() is None:
                lookalike.kill()
            lookalike.wait(timeout=5)

    def _wait_for_path(self, path: Path) -> None:
        deadline = time.monotonic() + 3
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(path.exists(), f"fixture did not publish readiness: {path}")

    def test_index_force_preempts_verified_owner_but_defer_keeps_it_running(self) -> None:
        generator = self.pickers / "session/index.sh"
        started = self.root / "generators"
        release = self.root / "release-generator"
        row = f"fresh\tdir\t{self.home}/fresh\t\t"
        generator.write_text(
            "#!/usr/bin/env python3\nimport os,signal,time\nfrom pathlib import Path\n"
            "if os.environ.get('BLOCK_GENERATOR'): signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            f"with Path({str(started)!r}).open('a') as handle: handle.write(str(os.getpid())+'\\n')\n"
            f"release=Path({str(release)!r})\ndeadline=time.monotonic()+10\n"
            "while os.environ.get('BLOCK_GENERATOR') and not release.exists() and time.monotonic()<deadline: time.sleep(0.01)\n"
            f"print({row!r})\n"
        )
        generator.chmod(0o755)
        (self.pickers / "session/ordered_cache_update.sh").write_text("#!/bin/sh\nexit 0\n")
        script = self.pickers / "session/index_update.sh"
        owner = subprocess.Popen(
            [modern_bash(), str(script), "--force", "--quiet"],
            env={**self.env, "BLOCK_GENERATOR": "1"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self._wait_for_path(started)
            deadline = time.monotonic() + 3
            while len(started.read_text().splitlines()) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            generator_pids = started.read_text().splitlines()
            self.assertEqual(len(generator_pids), 2)
            cache = self.cache / "pick_session_items.tsv"
            lock = Path(str(cache) + ".lock")
            self.assertEqual(json.loads((lock / "owner.json").read_text())["pid"], owner.pid)

            deferred = self.shell(script, "--force", "--defer-if-busy", "--quiet", "--quick-only")

            self.assertEqual(deferred.returncode, 0, deferred.stderr)
            self.assertIsNone(owner.poll())
            self.assertEqual(started.read_text().splitlines(), generator_pids)
            refreshed = self.shell(script, "--force", "--quiet", "--quick-only")
            stdout, stderr = owner.communicate(timeout=5)
            self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
            self.assertEqual(owner.returncode, 0, stdout + stderr)
            self.assertEqual(len(started.read_text().splitlines()), 3)
            self.assertEqual(cache.read_text(), row + "\n")
            self.assertFalse(lock.exists())
            for generator_pid in generator_pids:
                remaining = subprocess.run(
                    ["ps", "-o", "stat=", "-o", "command=", "-p", generator_pid],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if remaining.returncode == 0 and not remaining.stdout.lstrip().startswith("Z"):
                    self.assertNotIn(str(generator), remaining.stdout, "preemption left its generator running")
        finally:
            release.touch()
            if owner.poll() is None:
                owner.kill()
            owner.communicate(timeout=5)

    def test_index_force_preserves_registered_nonpreemptible_cache_writer(self) -> None:
        cache = self.cache / "pick_session_items.tsv"
        row = f"cached\tdir\t{self.home}/cached\t\t\n"
        cache.write_text(row)
        ready = self.root / "writer-ready"
        release = self.root / "release-writer"
        generated = self.root / "generated"
        generator = self.pickers / "session/index.sh"
        generator.write_text(f"#!/bin/sh\ntouch '{generated}'\nprintf '%s' '{row}'\n")
        generator.chmod(0o755)
        (self.pickers / "session/ordered_cache_update.sh").write_text("#!/bin/sh\nexit 0\n")
        code = (
            "import sys,time\nfrom pathlib import Path\nPath(sys.argv[1]).touch()\n"
            "deadline=time.monotonic()+10\n"
            "while not Path(sys.argv[2]).exists() and time.monotonic()<deadline: time.sleep(0.01)\n"
        )
        writer = subprocess.Popen(
            [
                sys.executable,
                str(self.pickers / "lib/resource_lock.py"),
                "--timeout",
                "0",
                "cache-run",
                str(cache),
                sys.executable,
                "-c",
                code,
                str(ready),
                str(release),
            ],
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self._wait_for_path(ready)
            lock = Path(str(cache) + ".lock")
            self.assertFalse(json.loads((lock / "owner.json").read_text())["preemptible"])

            refused = self.shell(self.pickers / "session/index_update.sh", "--force", "--quiet", "--quick-only")

            self.assertEqual(refused.returncode, 0, refused.stderr)
            self.assertIsNone(writer.poll())
            self.assertFalse(generated.exists())
            self.assertEqual(cache.read_text(), row)
            release.touch()
            stdout, stderr = writer.communicate(timeout=5)
            self.assertEqual(writer.returncode, 0, stdout + stderr)
            self.assertFalse(lock.exists())
            after = self.shell(self.pickers / "session/index_update.sh", "--force", "--quiet", "--quick-only")
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertTrue(generated.exists())
        finally:
            release.touch()
            if writer.poll() is None:
                writer.kill()
            writer.communicate(timeout=5)

    def test_lock_timeout_does_not_run_command_or_release_owner(self) -> None:
        resource = self.cache / "preview-global"
        lock_file = Path(str(resource) + ".flock")
        marker = self.root / "ran"
        with lock_file.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.pickers / "lib/resource_lock.py"),
                    "--timeout",
                    "0",
                    "run",
                    str(resource),
                    "/usr/bin/touch",
                    str(marker),
                ],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(marker.exists())
            with lock_file.open("a") as contender:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)


class PickerIdentityTests(_PickerCase):
    def _assert_badged_session_target(
        self, *, rename_collision: bool, auto_rename: str | None = "on", stale_cached_expected: bool = False
    ) -> None:
        main = self.home / "code/repo/main"
        main.mkdir(parents=True)
        self.git(main, "init", "-q", "-b", "main")
        self.git(main, "commit", "--allow-empty", "-qm", "base")
        linked = main.parent / "feature"
        self.git(main, "worktree", "add", "-q", "-b", "feature", str(linked))
        state = self.root / "sessions.json"
        state.write_text(json.dumps({"review-session": str(linked)}))
        calls = self.root / "tmux-calls"
        tmux = self.bin / "tmux"
        tmux.write_text(
            f"#!{sys.executable}\nimport json, sys\n"
            f"state_path={str(state)!r}\n"
            f"with open({str(calls)!r}, 'a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')\n"
            "with open(state_path) as source: sessions=json.load(source)\n"
            "args=sys.argv[1:]\n"
            "if args[0]=='list-sessions':\n"
            "    fmt=args[args.index('-F')+1]\n"
            "    for name, path in sessions.items():\n"
            "        print(fmt.replace('#{session_name}', name).replace('#{?session_path,#{session_path},#{pane_current_path}}', path).replace('#{session_path}', path))\n"
            "elif args[0]=='display-message': print('other')\n"
            f"elif args[0]=='show-options': print({f'@pick_session_auto_rename_sessions {auto_rename}' if auto_rename is not None else ''!r})\n"
            "elif args[0]=='has-session': sys.exit(0 if args[-1].removeprefix('=') in sessions else 1)\n"
            "elif args[0]=='rename-session':\n"
            "    old=args[args.index('-t')+1].removeprefix('='); new=args[-1]\n"
            f"    if {rename_collision!r}:\n"
            f"        sessions[new]={str(self.home)!r}\n"
            "        with open(state_path, 'w') as out: json.dump(sessions, out)\n"
            "    if old not in sessions or new in sessions: sys.exit(1)\n"
            "    sessions[new]=sessions.pop(old)\n"
            "    with open(state_path, 'w') as out: json.dump(sessions, out)\n"
            "elif args[0]=='switch-client': sys.exit(0 if args[-1].removeprefix('=') in sessions else 1)\n"
        )
        tmux.chmod(0o755)
        self.stub("fzf", "exit 1")
        payload = {
            "number": 42,
            "state": "OPEN",
            "url": "https://github.com/owner/repo/pull/42",
            "reviewDecision": "REVIEW_REQUIRED",
            "closingIssuesReferences": [],
            "author": {"login": "contributor"},
        }
        self.stub("gh", f"printf '%s\\n' '{json.dumps(payload)}'")
        indexed = subprocess.run(
            [sys.executable, str(self.pickers / "session/lib/index_main.py")],
            env={
                **self.env,
                "PICK_SESSION_GITHUB_LOGIN": "me",
                "PICK_SESSION_QUICK": "1",
                "PICK_SESSION_SESSIONS_ONLY": "1",
                "PICK_SESSION_SKIP_DIRTY": "1",
                "PICK_SESSION_SKIP_GH": "0",
                "PICK_SESSION_SCAN_ROOTS": str(self.home / "code"),
                "PICK_SESSION_THREADS": "1",
            },
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(indexed.returncode, 0, indexed.stderr)
        row = next(line for line in indexed.stdout.splitlines() if "\tsession\t" in line)
        self.assertIn("prrole=review", row)
        if stale_cached_expected:
            fields = row.split("\t")
            fields[3] = (
                "sess_wt:feature|repo=code/repo"
                "|expected=code/repo|feature"
                "|pr=42:OPEN:REVIEW_REQUIRED::https://github.com/owner/repo/pull/42"
                "|prrole=review"
            )
            cache = self.cache / "pick_session_items.tsv"
            cache.write_text("\t".join(fields) + "\n")
            rehydrated = subprocess.run(
                [sys.executable, str(self.pickers / "session/lib/items_full_rehydrate.py"), str(cache)],
                env={**self.env, "PICK_SESSION_SCAN_ROOTS": str(self.home / "code")},
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(rehydrated.returncode, 0, rehydrated.stderr)
            row = rehydrated.stdout.rstrip("\n")
        selection = self.root / "selection"
        selection.write_text(row + "\n")

        result = self.shell(
            self.pickers / "session/pick_session.sh",
            PICK_SESSION_SELECTION_FILE=str(selection),
            TMUX="fixture,1,0",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        if auto_rename != "on" or stale_cached_expected:
            expected_sessions = {"review-session": str(linked)}
            expected_target = "review-session"
        elif rename_collision:
            expected_sessions = {"review-session": str(linked), "code/repo|feature": str(self.home)}
            expected_target = "review-session"
        else:
            expected_sessions = {"code/repo|feature": str(linked)}
            expected_target = "code/repo|feature"
        self.assertEqual(json.loads(state.read_text()), expected_sessions)
        actual = [json.loads(line) for line in calls.read_text().splitlines()]
        self.assertIn(["switch-client", "-t", f"={expected_target}"], actual)

    def test_badged_session_renames_and_switches_to_complete_canonical_name(self) -> None:
        self._assert_badged_session_target(rename_collision=False)

    def test_cached_badge_contaminated_expected_name_keeps_session_identity(self) -> None:
        self._assert_badged_session_target(rename_collision=False, auto_rename="on", stale_cached_expected=True)

    def test_concurrent_session_name_collision_keeps_original_selection(self) -> None:
        self._assert_badged_session_target(rename_collision=True)

    def test_disabled_auto_rename_keeps_badged_session_identity(self) -> None:
        self._assert_badged_session_target(rename_collision=False, auto_rename="off")

    def test_default_auto_rename_keeps_badged_session_identity(self) -> None:
        self._assert_badged_session_target(rename_collision=False, auto_rename=None)

    def _assert_session_path_collision(
        self,
        kind: str,
        *,
        reuse: bool = False,
        cache_busy: bool = False,
        canonical_holder: str = "other",
        auto_rename: str | None = None,
    ) -> None:
        selected = self.home / ("second/project" if kind == "dir" else "code/a_b/main")
        selected.mkdir(parents=True)
        first = self.home / (
            ".bag/worktree_remove/project"
            if canonical_holder == "bag"
            else ("first/project" if kind == "dir" else "code/a.b/main")
        )
        first.mkdir(parents=True)
        canonical = "project" if kind == "dir" else "code/a_b|main"
        meta = "" if kind == "dir" else "wt_root:main|repo=code/a_b"
        target = "" if kind == "dir" else str(selected)
        selection = self.root / "selection"
        selection.write_text(f"project\t{kind}\t{selected}\t{meta}\t{target}\n")
        calls = self.root / "tmux-calls"
        state = self.root / "sessions.json"
        sessions = {} if canonical_holder == "absent" else {canonical: str(first)}
        if reuse:
            sessions["review-pane"] = str(selected)
        state.write_text(json.dumps(sessions))
        tmux = self.bin / "tmux"
        tmux.write_text(
            f"#!{sys.executable}\nimport json, sys\n"
            f"state_path={str(state)!r}\n"
            f"with open({str(calls)!r}, 'a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')\n"
            "sessions=json.load(open(state_path)); args=sys.argv[1:]\n"
            "if args[0]=='list-sessions':\n"
            "    fmt=args[args.index('-F')+1]\n"
            "    for name, path in sessions.items():\n"
            "        print(fmt.replace('#{session_name}', name).replace('#{?session_path,#{session_path},#{pane_current_path}}', path).replace('#{session_path}', path))\n"
            f"elif args[0]=='show-option': print({auto_rename or ''!r})\n"
            f"elif args[0]=='show-options': print({f'@pick_session_auto_rename_sessions {auto_rename}' if auto_rename is not None else ''!r})\n"
            "elif args[0]=='display-message': print('other')\n"
            "elif args[0]=='has-session': sys.exit(0 if args[-1].lstrip('=') in sessions else 1)\n"
            "elif args[0]=='new-session':\n"
            "    if args[args.index('-s')+1] in sessions: sys.exit(1)\n"
            "    sessions[args[args.index('-s')+1]]=args[args.index('-c')+1]\n"
            "    with open(state_path, 'w') as out: json.dump(sessions, out)\n"
            "elif args[0]=='rename-session':\n"
            "    old=args[args.index('-t')+1].removeprefix('='); new=args[-1]\n"
            "    if old not in sessions or new in sessions: sys.exit(1)\n"
            "    sessions[new]=sessions.pop(old)\n"
            "    with open(state_path, 'w') as out: json.dump(sessions, out)\n"
            "elif args[0]=='switch-client': sys.exit(0 if args[-1].removeprefix('=') in sessions else 1)\n"
        )
        tmux.chmod(0o755)
        (self.home / ".config/tmux/pick_session_dir_exclude.txt").write_text("")

        cache = self.cache / "pick_session_items.tsv"
        published = f"publisher\tdir\t{self.home}/published\t\t\n"
        cache.write_text(published)
        lock = Path(str(cache) + ".lock")
        if cache_busy:
            lock.mkdir()
            (lock / "pid").write_text(str(os.getpid()))

        result = self.shell(
            self.pickers / "session/pick_session.sh",
            PICK_SESSION_SELECTION_FILE=str(selection),
            TMUX="fixture,1,0",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        sessions = json.loads(state.read_text())
        if canonical_holder != "absent":
            expected_holder = f"{canonical}@bag" if canonical_holder == "bag" and auto_rename == "on" else canonical
            self.assertEqual(sessions[expected_holder], str(first))
        selected_name = next((name for name, path in sessions.items() if path == str(selected)), None)
        self.assertIsNotNone(selected_name, sessions)
        actual = [json.loads(line) for line in calls.read_text().splitlines()]
        self.assertIn(["switch-client", "-t", f"={selected_name}"], actual)

        if reuse:
            expected_selected = canonical if canonical_holder != "other" and auto_rename == "on" else "review-pane"
            self.assertEqual(selected_name, expected_selected)
            self.assertFalse(any(call[0] == "new-session" for call in actual), actual)
        if cache_busy:
            self.assertEqual(cache.read_text(), published)
            self.assertEqual((lock / "pid").read_text(), str(os.getpid()))
        else:
            rows = [line.split("\t") for line in cache.read_text().splitlines()]
            selected_rows = [row for row in rows if row[2] == str(selected)]
            self.assertEqual(len(selected_rows), 1, rows)
            self.assertEqual(selected_rows[0][1:5], ["session", str(selected), "", selected_name])
            self.assertIn(published.strip(), cache.read_text())

    def test_directory_basename_collision_switches_to_its_own_path(self) -> None:
        self._assert_session_path_collision("dir")

    def test_directory_collision_reuses_a_session_already_at_selected_path(self) -> None:
        self._assert_session_path_collision("dir", reuse=True)

    def test_worktree_repo_name_collision_creates_a_session_at_selected_path(self) -> None:
        self._assert_session_path_collision("worktree")

    def test_worktree_repo_name_collision_reuses_a_session_already_at_selected_path(self) -> None:
        self._assert_session_path_collision("worktree", reuse=True)

    def test_disabled_auto_rename_reuses_directory_session_when_canonical_name_is_free(self) -> None:
        self._assert_session_path_collision("dir", reuse=True, canonical_holder="absent", auto_rename="off")

    def test_default_auto_rename_reuses_worktree_session_when_canonical_name_is_free(self) -> None:
        self._assert_session_path_collision("worktree", reuse=True, canonical_holder="absent")

    def test_enabled_auto_rename_canonicalizes_session_at_selected_path(self) -> None:
        self._assert_session_path_collision("worktree", reuse=True, canonical_holder="absent", auto_rename="on")

    def test_disabled_auto_rename_preserves_bagged_holder_and_opens_selected_path(self) -> None:
        self._assert_session_path_collision("dir", canonical_holder="bag", auto_rename="off")

    def test_enabled_auto_rename_moves_bagged_holder_aside(self) -> None:
        self._assert_session_path_collision("dir", canonical_holder="bag", auto_rename="on")

    def test_busy_cache_publisher_preserves_its_snapshot_and_selection_still_switches(self) -> None:
        self._assert_session_path_collision("dir", cache_busy=True)

    def test_filtered_match_order_drives_family_mark_collapse_and_section_jump(self) -> None:
        def row(label: str, kind: str, num: str, parent: str = "", role: str = "") -> str:
            return "\t".join([label, kind, "owner/repo", num, "url", label, "", "", "", "", "", parent, role])

        matches = [
            row("filtered child", "pr", "3", "pr:owner/repo:1", "child"),
            row("section", "header", "pr:0"),
            row("another child", "pr", "2", "pr:owner/repo:1", "child"),
        ]
        snapshot = self.root / "matches.tsv"
        snapshot.write_text("\n".join(matches) + "\n")
        scope = self.root / "scope"
        scope.write_text("all")
        items = self.bin / "items"
        self.stub("items", "exit 1")
        env = {"FZF_POS": "1"}
        lib = self.pickers / "github/lib"

        marked = self.shell(lib / "gh_picker_mark_subtree.sh", str(snapshot), **env)
        collapsed = self.shell(lib / "gh_picker_collapse.sh", "toggle", str(scope), str(items), str(snapshot), **env)
        jumped = self.shell(lib / "gh_picker_jump.sh", "next", str(snapshot), **env)

        self.assertEqual(marked.stdout, "pos(1)+toggle+pos(3)+toggle+pos(1)")
        self.assertEqual(jumped.stdout, "pos(2)")
        self.assertEqual(collapsed.returncode, 0, collapsed.stderr)
        state = (self.cache / "gh_picker_collapsed").read_text()
        self.assertIn("pr:owner/repo:1", state)

    def test_graphql_batches_keep_dotted_and_colliding_repo_names_distinct(self) -> None:
        with patch("signal.signal"):
            github = runpy.run_path(str(self.pickers / "github/lib/gh_items_main.py"))
            index_env = {**self.env, "PICK_SESSION_SESSIONS_ONLY": "1", "PICK_SESSION_SKIP_GH": "1"}
            with (
                patch.dict(os.environ, index_env, clear=True),
                patch("subprocess.run", return_value=subprocess.CompletedProcess(["tmux"], 0, "", "")),
            ):
                session = runpy.run_path(str(self.pickers / "session/lib/index_main.py"))
        keys = [("owner/repo.js", 7), ("owner/repo-name", 7), ("owner/repo_name", 7)]
        queries = []

        def graphql(command, **_kwargs):
            query = next(value.removeprefix("query=") for value in command if value.startswith("query="))
            queries.append(query)
            aliases = re.findall(r'([^\s{}]+): repository\(owner: "([^"]+)", name: "([^"]+)"\)', query)
            self.assertEqual(len(aliases), 3, query)
            self.assertEqual(len({alias for alias, _, _ in aliases}), 3, query)
            data = {}
            for alias, owner, name in aliases:
                self.assertRegex(alias, r"^[_A-Za-z][_0-9A-Za-z]*$")
                node = {
                    "number": 7,
                    "headRefName": "main",
                    "title": f"{owner}/{name}",
                    "state": "OPEN",
                    "reviewDecision": "APPROVED",
                    "parent": {"number": 1},
                }
                data[alias] = {"pullRequest": node, "issue": node}
            return subprocess.CompletedProcess(command, 0, json.dumps({"data": data}), "")

        with patch("subprocess.run", side_effect=graphql):
            actual_pr = github["_graphql_pr_metadata_chunk"](keys)
            actual_issue = github["_graphql_issue_metadata_chunk"](keys)
            actual_phantom = github["_graphql_phantom_parents"](keys)
            actual_ci = session["_batch_ci_graphql"]({repo: {num} for repo, num in keys})

        self.assertEqual(set(actual_pr), {repo for repo, _ in keys})
        self.assertEqual(set(actual_issue), {repo for repo, _ in keys})
        self.assertEqual(set(actual_phantom), set(keys))
        self.assertEqual(set(actual_ci), {repo for repo, _ in keys})
        self.assertEqual(len(queries), 4)

    def test_overlapping_sections_preserve_inferred_family_context(self) -> None:
        collapsed_file = self.cache / "gh_picker_collapsed"
        for kind, overlap in (("pr", False), ("pr", True), ("issue", False), ("issue", True)):
            with self.subTest(kind=kind, overlap=overlap):
                collapsed_file.unlink(missing_ok=True)
                config = self.root / f"inferred-{kind}.json"
                key = "prSections" if kind == "pr" else "issuesSections"
                sections = [{"title": "Family queue", "filters": "repo:owner/repo label:family", "scopes": ["focus"]}]
                if overlap:
                    sections.insert(
                        0, {"title": "Child queue", "filters": "repo:owner/repo label:child", "scopes": ["explore"]}
                    )
                config.write_text(json.dumps({key: sections}))
                cache = self.cache / f"inferred-{kind}.tsv"
                unexpected = []

                def title(num):
                    return "parent" if num == 1 else f"[8.{17 + num}] child (#1)"

                def external(command, **_kwargs):
                    if command[0] == "yq":
                        return subprocess.CompletedProcess(command, 0, config.read_text(), "")
                    if command[:3] == ["gh", "api", "user"]:
                        return subprocess.CompletedProcess(command, 0, "viewer", "")
                    if "search/issues" in command:
                        query = next(value for value in command if value.startswith("q="))
                        numbers = [2] if query.endswith("label:child") else [1, 2, 3]
                        items = [
                            {
                                "n": num,
                                "r": "owner/repo",
                                "t": title(num),
                                "s": "open",
                                "labels": ["child", "family"] if num == 2 else ["family"],
                                "url": f"url{num}",
                            }
                            for num in numbers
                        ]
                        return subprocess.CompletedProcess(command, 0, json.dumps(items), "")
                    if command[:3] == ["gh", "api", "graphql"]:
                        query = next(value for value in command if value.startswith("query="))
                        data = {}
                        for alias, field, number in re.findall(
                            r'(_\w+): repository\(owner: "owner", name: "repo"\) \{ (pullRequest|issue)\(number: (\d+)\)',
                            query,
                        ):
                            num = int(number)
                            node = {"number": num, "title": title(num), "state": "OPEN", "url": f"url{num}"}
                            if field == "pullRequest":
                                node.update(
                                    headRefName="main" if num == 1 else f"backport/8.{17 + num}/pr-1",
                                    baseRefName="main",
                                    body="",
                                )
                            else:
                                node.update(
                                    parent=None
                                    if num == 1
                                    else {
                                        "number": 1,
                                        "title": "parent",
                                        "state": "OPEN",
                                        "repository": {"nameWithOwner": "owner/repo"},
                                    },
                                    subIssuesSummary={"total": 2 if num == 1 else 0, "completed": 0},
                                )
                            data[alias] = {field: node}
                        return subprocess.CompletedProcess(command, 0, json.dumps({"data": data}), "")
                    unexpected.append(command)
                    raise AssertionError(command)

                with (
                    patch.dict(os.environ, self.env, clear=True),
                    patch("signal.signal"),
                    patch("subprocess.run", side_effect=external),
                ):

                    def render_main(*options):
                        with (
                            patch.object(
                                sys,
                                "argv",
                                ["gh_items_main.py", "--config", str(config), "--cache-file", str(cache), *options],
                            ),
                            contextlib.redirect_stdout(io.StringIO()) as output,
                        ):
                            module = runpy.run_path(str(self.pickers / "github/lib/gh_items_main.py"))
                            module["main"]()
                        return output.getvalue()

                    frames = [
                        render_main("--scope", "all"),
                        render_main("--scope", "focus", "--filter-cache"),
                        cache.read_text(),
                    ]
                    if kind == "pr" and overlap:
                        placeholders = []
                        for line in cache.read_text().splitlines():
                            parts = line.split("\t")
                            if parts[12] == "child":
                                parts[1], parts[3], parts[4] = "header", "0", ""
                            placeholders.append("\t".join(parts))
                        cache.write_text("\n".join(placeholders) + "\n")
                    collapsed_file.write_text(f"{kind}:owner/repo:1\n")
                    collapsed_frames = {
                        scope: render_main("--scope", scope, "--filter-cache") for scope in ("all", "focus")
                    }

                self.assertEqual(unexpected, [])
                for frame in frames:
                    family = []
                    in_family = False
                    for line in frame.splitlines():
                        parts = line.split("\t")
                        if parts[1:3] == ["header", ""]:
                            in_family = parts[3] == f"{kind}:{int(overlap)}"
                            continue
                        if in_family and parts[1:3] == [kind, "owner/repo"]:
                            family.append((parts[3], parts[12]))
                    self.assertEqual(family, [("1", "parent"), ("2", "child"), ("3", "child")])

                for scope, frame in collapsed_frames.items():
                    expected = {f"{kind}:{int(overlap)}": 2}
                    if scope == "all" and overlap:
                        expected[f"{kind}:0"] = 1
                    actual = {}
                    section = ""
                    for line in frame.splitlines():
                        parts = line.split("\t")
                        if parts[1:3] == ["header", ""]:
                            section = parts[3]
                            continue
                        self.assertNotEqual(parts[12], "child", frame)
                        if parts[12] == "parent":
                            actual[section] = parts[0]
                    self.assertEqual(actual.keys(), expected.keys())
                    for section, hidden in expected.items():
                        self.assertIn(f"({hidden} hidden)", actual[section])

    def test_unrelated_fetch_failure_keeps_fresh_context_families(self) -> None:
        config = self.root / "family-sections.json"
        config.write_text(
            json.dumps(
                {
                    "prSections": [
                        {"title": "Original", "filters": "repo:owner/repo label:original"},
                        {"title": "Backport", "filters": "repo:owner/repo label:backport"},
                        {"title": "Unrelated", "filters": "repo:owner/other"},
                    ]
                }
            )
        )
        cache = self.cache / "families.tsv"
        for failed, matching_cache, cached_parent in (
            (False, True, False),
            (True, True, False),
            (True, False, False),
            (True, True, True),
        ):
            with self.subTest(failed=failed, matching_cache=matching_cache, cached_parent=cached_parent):
                retained_filter = "repo:owner/repo label:retained" if cached_parent else "repo:owner/other"
                configuration = json.loads(config.read_text())
                configuration["prSections"][2]["filters"] = retained_filter
                config.write_text(json.dumps(configuration))
                section_id = "pr:2" if matching_cache else "pr:9"
                cached_repo, cached_num = ("owner/repo", 1) if cached_parent else ("owner/other", 99)
                cache.write_text(
                    f"prior section\theader\t\t{section_id}\nprior row\tpr\t{cached_repo}\t{cached_num}\turl\n"
                )
                unexpected = []

                def external(command, **_kwargs):
                    if command[0] == "yq":
                        return subprocess.CompletedProcess(command, 0, config.read_text(), "")
                    if command[:3] == ["gh", "api", "user"]:
                        return subprocess.CompletedProcess(command, 0, "viewer", "")
                    if "search/issues" in command:
                        query = next(value for value in command if value.startswith("q="))
                        if query == f"q={retained_filter}":
                            return subprocess.CompletedProcess(command, int(failed), "" if failed else "[]", "")
                        num = 1 if query.endswith("label:original") else 2
                        title = "original" if num == 1 else "[8.19] child (#1)"
                        label = "original" if num == 1 else "backport"
                        return subprocess.CompletedProcess(
                            command,
                            0,
                            json.dumps(
                                [
                                    {
                                        "n": num,
                                        "r": "owner/repo",
                                        "t": title,
                                        "s": "open",
                                        "labels": [label],
                                        "url": f"url{num}",
                                    }
                                ]
                            ),
                            "",
                        )
                    if command[:3] == ["gh", "api", "graphql"]:
                        query = next(value for value in command if value.startswith("query="))
                        data = {}
                        for alias, number in re.findall(
                            r'(_\w+): repository\(owner: "owner", name: "repo"\) \{ pullRequest\(number: (\d+)\)', query
                        ):
                            num = int(number)
                            data[alias] = {
                                "pullRequest": {
                                    "number": num,
                                    "headRefName": "main" if num == 1 else "backport/8.19/pr-1",
                                    "baseRefName": "main",
                                    "body": "",
                                    "state": "OPEN",
                                    "url": f"url{num}",
                                    "title": "original" if num == 1 else "[8.19] child (#1)",
                                }
                            }
                        return subprocess.CompletedProcess(command, 0, json.dumps({"data": data}), "")
                    unexpected.append(command)
                    raise AssertionError(command)

                with (
                    patch.dict(os.environ, self.env, clear=True),
                    patch("signal.signal"),
                    patch("subprocess.run", side_effect=external),
                    patch.object(
                        sys, "argv", ["gh_items_main.py", "--config", str(config), "--cache-file", str(cache)]
                    ),
                    contextlib.redirect_stdout(io.StringIO()) as rendered,
                ):
                    module = runpy.run_path(str(self.pickers / "github/lib/gh_items_main.py"))
                    module["main"]()

                self.assertEqual(unexpected, [])
                for frame in (cache.read_text(), rendered.getvalue()):
                    rows = [line.split("\t") for line in frame.splitlines()]
                    expected = ["1", "2", "1"] if failed and cached_parent else ["1", "1", "2"]
                    self.assertEqual([parts[3] for parts in rows if parts[1:3] == ["pr", "owner/repo"]], expected)
                    child = next(parts for parts in rows if parts[1:4] == ["pr", "owner/repo", "2"])
                    self.assertEqual(child[11:13], ["pr:owner/repo:1", "child"])
                    self.assertIn("2 items", next(parts[0] for parts in rows if parts[1:4] == ["header", "", "pr:1"]))

    def test_backport_metadata_outage_preserves_only_failed_section(self) -> None:
        config = self.root / "sections.json"
        configuration = {
            "prSections": [
                {
                    "title": "Maintenance",
                    "filters": "repo:owner/repo",
                    "source": "backport-failures",
                    "scopes": ["focus"],
                },
                {"title": "Ordinary", "filters": "repo:owner/repo is:pr", "scopes": ["explore"]},
            ]
        }
        cache = self.cache / "items.tsv"

        def saved_row(label, kind, num, parent="", role="", updated="", branch=""):
            return "\t".join(
                [label, kind, "owner/repo", num, "url", label, "", "", "", "", updated, parent, role, branch]
            )

        base_prior = (
            "\n".join(
                [
                    "old maintenance\theader\t\tpr:0",
                    saved_row("prior payload", "pr", "7", role="parent", updated="2026-01-01"),
                    saved_row("missing backport", "header", "0", "pr:owner/repo:7", "child", branch="8.19"),
                    saved_row("second saved parent", "pr", "8", role="parent", updated="2026-02-02"),
                ]
            )
            + "\n"
        )
        old_ordinary = "old ordinary\theader\t\tpr:1\nobsolete row\tpr\towner/other\t9\turl\n"
        modes = (
            "status",
            "status_with_data",
            "invalid",
            "partial",
            "graphql_errors",
            "timeout",
            "malformed_search",
            "overlap",
            "overlap_reversed",
            "overlap_family",
            "fresh_overlap_family",
            "empty",
        )

        for mode in modes:
            with self.subTest(mode=mode):
                sections = [dict(section) for section in configuration["prSections"]]
                if mode.endswith("overlap_family"):
                    sections[1]["source"] = "backport-failures"
                if mode == "overlap_reversed":
                    sections.reverse()
                config.write_text(json.dumps({"prSections": sections}))
                prior = base_prior.replace("pr:0", "pr:1") if mode == "overlap_reversed" else base_prior
                ordinary = old_ordinary.replace("pr:1", "pr:0") if mode == "overlap_reversed" else old_ordinary
                cache.write_text(ordinary + prior if mode == "overlap_reversed" else prior + ordinary)
                unexpected = []

                def external(command, **_kwargs):
                    if command[0] == "yq":
                        return subprocess.CompletedProcess(command, 0, config.read_text(), "")
                    if command[:3] == ["gh", "api", "user"]:
                        return subprocess.CompletedProcess(command, 0, "viewer", "")
                    if "search/issues" in command:
                        items = []
                        if "q=repo:owner/repo" in command:
                            items = [
                                {"n": n, "r": "owner/repo", "t": "parent", "s": "closed", "m": "merged"} for n in (7, 8)
                            ]
                            if mode == "malformed_search":
                                items = [None]
                        elif "q=repo:owner/repo is:pr" in command and "overlap" in mode:
                            items = [{"n": 7, "r": "owner/repo", "t": "fresh copy", "s": "closed", "m": "merged"}]
                        return subprocess.CompletedProcess(command, 0, json.dumps(items), "")
                    if command[:3] == ["gh", "api", "graphql"]:
                        query = next(value for value in command if value.startswith("query="))
                        if "search(query:" in query:
                            return subprocess.CompletedProcess(command, 0, '{"data": {}}', "")
                        if "comments(last:" in query:
                            data = {
                                f"_bp{i}": {
                                    "pullRequest": {
                                        "number": n,
                                        "comments": {"nodes": []},
                                        "labels": {"nodes": []},
                                        "baseRefName": "main",
                                    }
                                }
                                for i, n in enumerate((7, 8) if "pullRequest(number: 8)" in query else (7,))
                            }
                            failed_overlap = mode.startswith("overlap") and "pullRequest(number: 8)" in query
                            if mode.endswith("overlap_family") and not failed_overlap:
                                branch = "8.19" if "pullRequest(number: 8)" in query else "8.20"
                                for repo in data.values():
                                    repo["pullRequest"]["comments"]["nodes"] = [
                                        {"body": f"## 💔\n| ❌ | {branch} | no PR |"}
                                    ]
                            if mode == "timeout":
                                raise subprocess.TimeoutExpired(command, 30)
                            if mode == "partial":
                                del data["_bp1"]
                            result = {"data": data}
                            if mode == "graphql_errors":
                                result["errors"] = [{"message": "metadata unavailable"}]
                            output = "not json" if mode == "invalid" else json.dumps(result)
                            if mode == "status" or failed_overlap:
                                output = ""
                            return subprocess.CompletedProcess(
                                command, int(mode.startswith("status") or failed_overlap), output, ""
                            )
                        return subprocess.CompletedProcess(command, 0, '{"data": {}}', "")
                    unexpected.append(command)
                    raise AssertionError(command)

                with (
                    patch.dict(os.environ, self.env, clear=True),
                    patch("signal.signal"),
                    patch("subprocess.run", side_effect=external),
                    patch.object(
                        sys, "argv", ["gh_items_main.py", "--config", str(config), "--cache-file", str(cache)]
                    ),
                    contextlib.redirect_stdout(io.StringIO()) as rendered,
                ):
                    module = runpy.run_path(str(self.pickers / "github/lib/gh_items_main.py"))
                    module["main"]()

                self.assertEqual(unexpected, [])
                current = cache.read_text()
                retained = mode not in {"empty", "fresh_overlap_family"}
                self.assertEqual(prior in current, retained)
                self.assertEqual(prior in rendered.getvalue(), retained)
                self.assertIn("Ordinary", current)
                self.assertNotIn("obsolete row", current)
                if "overlap" in mode:
                    rows = [line.split("\t") for line in current.splitlines()]
                    family_contexts = 2 if mode.endswith("overlap_family") else 1
                    self.assertEqual(sum(parts[1:4] == ["pr", "owner/repo", "7"] for parts in rows), family_contexts)
                    self.assertEqual(
                        sum(
                            parts[1:4] == ["header", "owner/repo", "0"] and parts[11] == "pr:owner/repo:7"
                            for parts in rows
                        ),
                        family_contexts,
                    )
                    if family_contexts == 2:
                        self.assertEqual(
                            {
                                parts[13]
                                for parts in rows
                                if parts[1:4] == ["header", "owner/repo", "0"] and parts[11] == "pr:owner/repo:7"
                            },
                            {"8.19", "8.20"},
                        )
                    self.assertIn(
                        f"{2 if family_contexts == 2 else 0} items",
                        next(parts[0] for parts in rows if "Ordinary" in parts[0]),
                    )

        (self.cache / "gh_picker_sort").write_text("updated-desc")
        for scope, expected in (("focus", ["pr:0", "8", "7", "0"]), ("all", ["pr:0", "8", "7", "0", "pr:1", "9"])):
            with self.subTest(cache_only_scope=scope):
                cache.write_text(prior + old_ordinary)
                with (
                    patch.dict(os.environ, self.env, clear=True),
                    patch("signal.signal"),
                    patch("subprocess.run", side_effect=external),
                    patch.object(
                        sys,
                        "argv",
                        [
                            "gh_items_main.py",
                            "--config",
                            str(config),
                            "--cache-file",
                            str(cache),
                            "--filter-cache",
                            "--scope",
                            scope,
                        ],
                    ),
                    contextlib.redirect_stdout(io.StringIO()) as rendered,
                ):
                    module = runpy.run_path(str(self.pickers / "github/lib/gh_items_main.py"))
                    module["main"]()
                self.assertEqual([line.split("\t")[3] for line in rendered.getvalue().splitlines()], expected)

    def test_backport_batches_preserve_dotted_repository_results(self) -> None:
        with patch("signal.signal"):
            module = runpy.run_path(str(self.pickers / "github/lib/gh_items_main.py"))
        repos = ["owner/repo.js", "owner/repo-name", "owner/repo_name"]
        phases = set()

        def github(command, **_kwargs):
            if "search/issues" in command:
                items = [{"n": 7, "r": repo, "t": "parent", "s": "closed", "m": "merged"} for repo in repos]
                return subprocess.CompletedProcess(command, 0, json.dumps(items), "")
            query = next(value.removeprefix("query=") for value in command if value.startswith("query="))
            if "search(query:" in query:
                return subprocess.CompletedProcess(command, 0, '{"data": {}}', "")
            fields = re.findall(r'([^\s{}]+): repository\(owner: "([^"]+)", name: "([^"]+)"\)', query)
            self.assertEqual(len(fields), 3, query)
            data = {}
            for alias, owner, name in fields:
                self.assertRegex(alias, r"^[_A-Za-z][_0-9A-Za-z]*$")
                if "comments(last:" in query:
                    phases.add("parents")
                    node = {
                        "number": 7,
                        "comments": {
                            "nodes": [{"body": f"## 💚\n| ✅ | 8.19 | https://github.com/{owner}/{name}/pull/9 |"}]
                        },
                    }
                else:
                    phases.add("backports")
                    node = {"number": 9, "state": "OPEN", "title": "pending backport", "url": "url"}
                data[alias] = {"pullRequest": node}
            return subprocess.CompletedProcess(command, 0, json.dumps({"data": data}), "")

        with patch("subprocess.run", side_effect=github):
            rows = module["fetch_backport_failures"]("pr", 0, "Pending", "")

        self.assertEqual(phases, {"parents", "backports"})
        self.assertEqual({row["repo"] for row in rows if row.get("_backport_sub")}, set(repos))


if __name__ == "__main__":
    unittest.main()
