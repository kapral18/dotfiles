#!/usr/bin/env python3
"""Regression tests for the shared git commit/push safety gate hook."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO

HOOKS = REPO / "home" / "exact_dot_agents" / "exact_hooks"
GATE_SCRIPT = HOOKS / "executable_gemini-git-gate.py"


def _load_gate_module():
    loader = SourceFileLoader("git_gate_hook", str(GATE_SCRIPT))
    spec = importlib.util.spec_from_loader("git_gate_hook", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load git-gate hook module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate_module()


def run_gate(payload_text: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE_SCRIPT)],
        input=payload_text,
        capture_output=True,
        text=True,
    )


class TestClassifyCommand(unittest.TestCase):
    """WHEN classifying a raw shell command line for the git commit/push gate."""

    def test_denies_plain_commit_and_push(self):
        assert gate.classify_command("git commit") == "deny"
        assert gate.classify_command("git push") == "deny"

    def test_denies_case_variant_git_executable(self):
        assert gate.classify_command("GIT push") == "deny"
        assert gate.classify_command("/usr/bin/GIT commit") == "deny"

    def test_denies_configured_alias_that_expands_to_push(self):
        assert gate.classify_command("git -c alias.p=push p") == "deny"

    def test_denies_external_git_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = Path(tmp) / "git-parity-probe"
            command.write_text("#!/bin/sh\nexit 0\n")
            command.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": f"{tmp}{os.pathsep}{os.environ['PATH']}"}):
                assert gate.classify_command("git parity-probe") == "deny"

    def test_denies_env_split_string_forms(self):
        assert gate.classify_command("env -S'git push'") == "deny"
        assert gate.classify_command("env -S 'git commit -m test'") == "deny"
        assert gate.classify_command("env --split-string='git push'") == "deny"

    def test_denies_shell_expansion_in_git_command_tokens(self):
        assert gate.classify_command("g$'it' push") == "deny"
        assert gate.classify_command("git p$'ush'") == "deny"
        assert gate.classify_command(r"g$'\x69t' push") == "deny"
        assert gate.classify_command(r"git p$'\x75sh'") == "deny"
        assert gate.classify_command("g\\\nit push") == "deny"
        assert gate.classify_command("git pu\\\nsh") == "deny"

    def test_allows_inert_git_text_but_denies_command_substitution(self):
        assert gate.classify_command("echo git status") == "allow"
        assert gate.classify_command("rg 'git push' home") == "allow"
        assert gate.classify_command('rg "$(git push)" home') == "deny"

    def test_denies_alias_through_env_options(self):
        assert gate.classify_command("env -C . git -c alias.p=push p") == "deny"
        assert gate.classify_command("env -P /usr/bin git -c alias.p=push p") == "deny"
        assert gate.classify_command("env -u HOME git -c alias.p=push p") == "deny"

    def test_denies_commit_after_global_option(self):
        assert gate.classify_command("git -C . commit") == "deny"

    def test_denies_push_after_env_prefix_and_dash_c(self):
        assert gate.classify_command("env X=1 git -c foo=bar push") == "deny"

    def test_denies_commit_with_inline_global_option_value(self):
        assert gate.classify_command("git --git-dir=/tmp/repo commit -m 'wip'") == "deny"

    def test_denies_push_after_chained_command(self):
        assert gate.classify_command("echo hi && git push") == "deny"

    def test_denies_commit_after_semicolon(self):
        assert gate.classify_command("git commit; echo done") == "deny"

    def test_allows_git_config_push_default(self):
        assert gate.classify_command("git config push.default") == "allow"

    def test_allows_unrelated_shell_command(self):
        assert gate.classify_command("ls -la") == "allow"
        assert gate.classify_command("npm test") == "allow"

    def test_allows_unrelated_word_containing_git_substring(self):
        # "digit" contains "git" but not as a standalone word.
        assert gate.classify_command("echo digit") == "allow"

    def test_denies_git_mentioned_inside_nested_shell_string(self):
        # Quoted/nested sub-shell invocation: can't safely rule out commit/push.
        assert gate.classify_command("bash -c \"git commit -m 'wip'\"") == "deny"

    def test_denies_unbalanced_quoting_when_git_present(self):
        assert gate.classify_command("git commit -m 'unterminated") == "deny"

    def test_allows_unbalanced_quoting_when_no_git(self):
        assert gate.classify_command("echo 'unterminated") == "allow"

    def test_denies_unrecognized_global_option_before_subcommand(self):
        # An unenumerated global flag defeats safe subcommand location.
        assert gate.classify_command("git --totally-unknown-flag commit") == "deny"

    def test_allows_git_invocation_with_no_subcommand(self):
        assert gate.classify_command("git --version") == "allow"

    def test_allows_supported_git_global_options(self):
        assert gate.classify_command("git -P status") == "allow"
        assert gate.classify_command("git --no-lazy-fetch status") == "allow"

    def test_allows_empty_command(self):
        assert gate.classify_command("") == "allow"


class TestGateHookProcess(unittest.TestCase):
    """WHEN the hook script runs as a real subprocess against each harness payload shape."""

    def test_cursor_shape_denies_commit_with_ask_permission(self):
        payload = json.dumps({"hook_event_name": "beforeShellExecution", "command": "git -C . commit"})
        result = run_gate(payload)
        assert result.returncode == 0, result.stderr
        body = json.loads(result.stdout)
        assert body["permission"] == "ask"

    def test_cursor_shape_allows_git_config(self):
        payload = json.dumps({"hook_event_name": "beforeShellExecution", "command": "git config push.default"})
        result = run_gate(payload)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {"permission": "allow"}

    def test_gemini_shape_denies_push(self):
        payload = json.dumps(
            {
                "hook_event_name": "BeforeTool",
                "tool_name": "run_shell_command",
                "tool_input": {"command": "env X=1 git -c foo=bar push"},
            }
        )
        result = run_gate(payload)
        assert result.returncode == 0, result.stderr
        body = json.loads(result.stdout)
        assert body["decision"] == "deny"

    def test_gemini_shape_allows_unrelated_command(self):
        payload = json.dumps(
            {
                "hook_event_name": "BeforeTool",
                "tool_name": "run_shell_command",
                "tool_input": {"command": "ls -la"},
            }
        )
        result = run_gate(payload)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {"decision": "allow"}

    def test_fails_closed_on_malformed_json(self):
        result = run_gate("{not valid json")
        assert result.returncode == 2
        assert result.stdout == ""
        assert "failing closed" in result.stderr

    def test_fails_closed_on_unrecognized_payload_shape(self):
        # Neither a Cursor top-level `command` string nor a Gemini
        # `run_shell_command` tool_input.command is present.
        payload = json.dumps({"hook_event_name": "postToolUse", "tool_name": "Read"})
        result = run_gate(payload)
        assert result.returncode == 2
        assert result.stdout == ""
        assert "failing closed" in result.stderr

    def test_fails_closed_on_empty_stdin_is_actually_allow(self):
        # Empty stdin parses as `{}`, which is an unrecognized shape (no
        # command field at all) -> fail closed, not a silent allow.
        result = run_gate("")
        assert result.returncode == 2
        assert result.stdout == ""


if __name__ == "__main__":
    unittest.main()
