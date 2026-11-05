from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).with_name("neovim_workflows.lua")


def workflow_lua() -> str | None:
    concrete_path = os.pathsep.join(path for path in os.get_exec_path() if Path(path).name != "shims")
    for name in ["luajit", "lua5.4", "lua5.3", "lua5.2"]:
        binary = shutil.which(name, path=concrete_path)
        if binary:
            return binary
    shim = shutil.which("lua")
    if shim and Path(shim).resolve().name == "mise":
        installs = Path(shim).parent.parent / "installs/lua"
        for version in ["5.4", "5.3", "5.2"]:
            for binary in sorted(installs.glob(f"{version}.*/bin/lua"), reverse=True):
                if os.access(binary, os.X_OK):
                    return str(binary)
    return None


LUA = workflow_lua()


@unittest.skipUnless(LUA, "LuaJIT or Lua 5.2+ is not installed")
class NeovimWorkflowTests(unittest.TestCase):
    def run_case(self, case: str, *arguments: str) -> str:
        with tempfile.TemporaryDirectory(prefix="neovim-workflows-") as temporary:
            env = os.environ | {
                "HOME": temporary,
                "XDG_CONFIG_HOME": temporary,
                "XDG_CACHE_HOME": temporary,
                "XDG_DATA_HOME": temporary,
                "XDG_STATE_HOME": temporary,
            }
            result = subprocess.run(
                [LUA, str(HARNESS), str(REPO), case, *arguments], capture_output=True, text=True, env=env, timeout=10
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout

    def test_autoformat_toggle_follows_current_buffer_and_force_bypasses_gates(self):
        self.run_case("format")

    def test_formatexpr_calls_the_configured_formatter(self):
        self.run_case("formatexpr")

    def test_compose_server_starts_only_for_compose_files(self):
        self.run_case("docker")

    def test_terminal_replacement_and_close_preserve_other_owners_and_user_jobs(self):
        self.run_case("terminal")

    def test_batch_worktree_generated_lua_launches_independent_owned_terminals(self):
        import sys

        from _test_support import modern_bash

        source = REPO / "home/dot_config/herdr/exact_scripts/pickers/github"
        with tempfile.TemporaryDirectory(prefix="batch-terminal-") as temporary:
            directory = Path(temporary)
            github = directory / "github"
            github.mkdir()
            script = github / "gh_batch_worktree.sh"
            shutil.copyfile(source / "executable_gh_batch_worktree.sh", script)
            shutil.copyfile(source / "readonly_gh_batch_branch_prompt.txt", github / "gh_batch_branch_prompt.txt")
            selected_targets = directory / "home/.config/herdr/scripts/pickers/github/lib/gh_selected_targets.py"
            selected_targets.parent.mkdir(parents=True)
            shutil.copyfile(source / "lib/gh_selected_targets.py", selected_targets)
            binary = directory / "bin"
            binary.mkdir()
            (binary / "python3").symlink_to(sys.executable)
            stubs = {
                "gh": "#!/bin/sh\nprintf 'Fixture issue\\n'\n",
                "nvim": '#!/bin/sh\nwhile [ "$#" -gt 0 ]; do\nif [ "$1" = -c ]; then shift; printf \'%s\\n\' "$1" >> "$CAPTURE_LUA"; fi\nshift\ndone\n',
            }
            for name, content in stubs.items():
                target = binary / name
                target.write_text(content)
                target.chmod(0o700)
            detach = directory / "home/lib/shared/detach.sh"
            detach.parent.mkdir(parents=True)
            detach.write_text("#!/bin/sh\nexit 0\n")
            detach.chmod(0o700)
            capture = directory / "editor-lua"
            selection = directory / "selection.tsv"
            selection.write_text("Issue42\tissue\towner/repo\t42\thttps://example.test/issues/42\n")
            env = {
                "HOME": str(directory / "home"),
                "XDG_CACHE_HOME": str(directory / "cache"),
                "PATH": str(binary) + os.pathsep + "/usr/bin:/bin",
                "EDITOR": "nvim",
                "CAPTURE_LUA": str(capture),
            }
            for _ in range(2):
                result = subprocess.run(
                    [modern_bash(), str(script), str(selection)],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.run_case("terminal", str(capture))

    def test_schema_cache_and_async_references_keep_the_resolved_kubernetes_version(self):
        self.run_case("k8s")

    def test_jest_debug_paths_resolve_from_the_package_working_directory(self):
        import shlex

        manual, cwd, scripted, script_cwd, regular, regular_cwd = self.run_case("jest").splitlines()
        self.assertEqual(cwd, "/project/packages/widget")
        self.assertEqual(script_cwd, cwd)
        self.assertEqual(regular_cwd, cwd)
        args = shlex.split(manual)
        self.assertEqual(args[:2], ["node", "--inspect-brk"])
        self.assertEqual((Path(cwd) / args[2]).resolve(), Path("/project/node_modules/.bin/jest"))
        for command in [manual, scripted, regular]:
            args = shlex.split(command)
            self.assertEqual((Path(cwd) / args[args.index("--config") + 1]).resolve(), Path("/project/jest.config.js"))
            test_args = [arg for arg in args if arg.endswith(".test.ts")]
            self.assertEqual(
                [(Path(cwd) / arg).resolve() for arg in test_args],
                [Path("/project/packages/widget/example's space.test.ts")],
            )

    def test_python_callback_preserves_filename_and_test_selector_as_literal_arguments(self):
        import shlex

        with tempfile.TemporaryDirectory(prefix="python-test-command-") as temporary:
            directory = Path(temporary)
            test_file = directory / "test's spaces; echo unexpected.py"
            script_file = directory / "script's spaces; echo unexpected.py"
            test_file.touch()
            script_file.touch()
            commands = self.run_case("python_commands", test_file.name, script_file.name).splitlines()
            self.assertEqual(len(commands), 3)
            expected = [
                ["--color=yes", test_file.name + "::TestWidget::test_value"],
                [test_file.name, "TestWidget.test_value", "-v"],
                [script_file.name],
            ]
            for command, arguments in zip(commands, expected):
                tokens = shlex.split(command)
                self.assertEqual(tokens[1 : 1 + len(arguments)], arguments)
                runner = directory / tokens[0]
                runner.write_text("#!/bin/sh\nprintf '%s\\0' \"$@\" > \"$CAPTURE_ARGS\"\nprintf 'OK\\n'\n")
                runner.chmod(0o700)
                capture = directory / "arguments"
                result = subprocess.run(
                    ["/bin/sh", "-c", command],
                    cwd=directory,
                    env={
                        "PATH": str(directory) + os.pathsep + "/usr/bin:/bin",
                        "HOME": temporary,
                        "CAPTURE_ARGS": str(capture),
                    },
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(capture.read_bytes().split(b"\0")[:-1], [arg.encode() for arg in arguments])

    def test_typescript_move_uses_native_workspace_refactor_and_keeps_edits_unsaved(self):
        self.run_case("move")

    def test_typescript_move_rolls_back_partial_edits_and_rejects_changed_buffers(self):
        self.run_case("move_failure")

    @unittest.skipUnless(shutil.which("jq"), "jq is not installed")
    def test_jsonl_formatter_uses_unsaved_input_and_emits_one_json_value_per_line(self):
        import json

        args = self.run_case("jsonl").splitlines()
        with tempfile.TemporaryDirectory(prefix="jsonl-formatter-") as temporary:
            source = Path(temporary) / "records.jsonl"
            source.write_text('{"stale":true}\n')
            command = ["jq", *(str(source) if item == "$FILENAME" else item for item in args)]
            result = subprocess.run(
                command,
                input='{"edited": true, "nested": {"count": 2}}\n{"new": true}\n',
                text=True,
                capture_output=True,
                timeout=5,
                check=True,
            )
            self.assertEqual(
                [json.loads(line) for line in result.stdout.splitlines()],
                [{"edited": True, "nested": {"count": 2}}, {"new": True}],
            )
            self.assertEqual(source.read_text(), '{"stale":true}\n')


if __name__ == "__main__":
    unittest.main()
