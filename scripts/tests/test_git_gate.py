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

    def test_allows_benign_substitution_alongside_inert_git_text(self):
        # Regression: a benign substitution plus quoted git prose elsewhere in
        # the segment must not deny; only the substitution body is executable.
        assert (
            gate.classify_command(
                ',ai-kb remember --body "ran \'git status --porcelain\' earlier" --workspace "$(pwd)"'
            )
            == "allow"
        )
        assert gate.classify_command('rg "$(git status)" home') == "allow"
        assert gate.classify_command('echo "cwd is $(pwd)" | ai-kb note "git status loop"') == "allow"

    def test_denies_mutating_git_inside_command_substitution(self):
        assert gate.classify_command("echo $(git push)") == "deny"
        assert gate.classify_command('echo "$(git commit -m x)"') == "deny"
        assert gate.classify_command("echo `git push`") == "deny"
        assert gate.classify_command("echo $(echo $(git push))") == "deny"

    def test_quoted_paren_inside_substitution_does_not_truncate_body(self):
        # Regression: a `)` inside quotes within a `$(...)` body is literal in
        # the shell; the scanner must not close the substitution early and
        # hide a mutating git command in the truncated remainder.
        assert gate.classify_command("echo \"$(printf 'a)b' && git push)\"") == "deny"
        assert gate.classify_command("echo \"$(printf 'a)b' && git status)\"") == "allow"
        # Double-quoted variant: a base-era bypass (base allows, real bash runs
        # the push) that only the quote-aware scanner closes.
        assert gate.classify_command('echo "$(printf "a)b" && git push)"') == "deny"
        assert gate.classify_command('echo "$(printf "a)b" && git status)"') == "allow"
        # The inner quotes belong to the substitution body, so the outer
        # string stays open and `&& git push` is literal text (verified
        # against bash/zsh); closing the outer quote first exposes it.
        assert gate.classify_command('echo "$(echo ")") && git push)"') == "allow"
        assert gate.classify_command('echo "$(echo ")")" && git push') == "deny"
        # Nested substitution inside double quotes within a body still nests.
        assert gate.classify_command('echo $(printf "%s" "$(git push)")') == "deny"
        # Unbalanced quote inside a body fails closed when git is mentioned.
        assert gate.classify_command('echo $(echo "unclosed && git push)') == "deny"

    def test_allows_unbalanced_substitution_without_git_word(self):
        assert gate.classify_command('echo "$(pwd') == "allow"

    def test_ignores_substitution_syntax_inside_single_quotes(self):
        # Regression: single-quoted text is literal in the shell, so prose
        # mentioning `git push` or $(git ...) inside single quotes is inert.
        assert (
            gate.classify_command(",ai-kb remember --body 'never run `git push` without asking' --kind gotcha")
            == "allow"
        )
        assert gate.classify_command("echo '$(git push)'") == "allow"
        assert gate.classify_command("echo 'literal $(git push'") == "allow"
        # Double quotes do not suppress substitution: still gated.
        assert gate.classify_command('echo "`git push`"') == "deny"
        assert gate.classify_command("echo \"'$(git push)'\"") == "deny"

    def test_allows_heredoc_with_template_strings_and_git_path_text(self):
        command = """node - <<'NODE'
const fs = require('fs');
const root = `${process.env.HOME}/tmp/demo`;
const lockPath = `${root}/.git/index.lock`;
const body = JSON.stringify({ path: lockPath, message: 'not a git command' });
await fetch(`${root}/api/items`, { method: 'PUT', body });
NODE"""
        assert gate.classify_command(command) == "allow"

    def test_denies_mutating_git_in_shell_heredoc_body(self):
        assert gate.classify_command("bash <<EOF\ngit push\nEOF") == "deny"
        assert gate.classify_command("sh <<EOF\ngit commit -m x\nEOF") == "deny"
        assert gate.classify_command("env bash <<EOF\ngit push\nEOF") == "deny"
        assert gate.classify_command("sudo bash <<EOF\ngit push\nEOF") == "deny"
        assert gate.classify_command("bash -s <<-EOF\n\tgit push\nEOF") == "deny"
        assert gate.classify_command("<<EOF bash\ngit push\nEOF") == "deny"
        assert gate.classify_command("env <<EOF bash\ngit push\nEOF") == "deny"
        assert gate.classify_command("bash 2>out <<EOF\ngit push\nEOF") == "deny"

    def test_allows_non_shell_heredoc_body_with_git_text(self):
        assert gate.classify_command("cat <<EOF\ngit push\nEOF") == "allow"
        assert gate.classify_command("node - <<'NODE'\nconsole.log('git push')\nNODE") == "allow"

    def test_keeps_heredoc_operator_order(self):
        command = "cat <<A <<-B\nbody\nA\n\tgit push\nB"
        assert gate.classify_command(command) == "allow"

    def test_denies_git_after_heredoc_redirection(self):
        assert gate.classify_command("cat <<EOF && git push\nbody\nEOF") == "deny"

    def test_denies_git_after_commented_heredoc_text(self):
        assert gate.classify_command("echo ok # <<EOF\ngit push\nEOF") == "deny"

    def test_allows_git_text_inside_shell_comment(self):
        assert gate.classify_command("echo ok # ; git push") == "allow"

    def test_denies_git_after_comment_glued_to_separator(self):
        assert gate.classify_command("echo a;#c\ngit push") == "deny"
        assert gate.classify_command("(echo a)#c\ngit push") == "deny"
        assert gate.classify_command("echo a&&#c\ngit push") == "deny"
        assert gate.classify_command("echo a|#c\ngit push") == "deny"
        assert gate.classify_command("(echo a)\ngit push") == "deny"

    def test_denies_unterminated_heredoc(self):
        assert gate.classify_command("cat <<EOF\n# git push") == "deny"

    def test_allows_git_paths_and_non_mutating_wrapped_git(self):
        assert gate.classify_command("stat .git/FETCH_HEAD.lock .git/index.lock") == "allow"
        assert gate.classify_command("sudo stat .git/FETCH_HEAD.lock") == "allow"
        assert gate.classify_command("sudo git status") == "allow"
        assert gate.classify_command("sudo git push") == "deny"
        assert gate.classify_command("env sudo git commit") == "deny"
        assert gate.classify_command("bash -lc 'git commit -m wip'") == "deny"
        assert gate.classify_command("sh -ec 'git push'") == "deny"
        assert gate.classify_command("command -p git push") == "deny"
        assert gate.classify_command("time -p git push") == "deny"
        assert gate.classify_command("bash --norc -c 'git push'") == "deny"
        # `push` is `$0`, not part of Bash's `-c` command string.
        assert gate.classify_command("bash -c git push") == "allow"

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

    def test_antigravity_shape_asks_before_push(self):
        payload = json.dumps(
            {
                "conversationId": "agy-session",
                "workspacePaths": ["/tmp/workspace"],
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "env X=1 git -c foo=bar push"},
                },
            }
        )
        result = run_gate(payload)
        assert result.returncode == 0, result.stderr
        body = json.loads(result.stdout)
        assert body["decision"] == "force_ask"
        assert "ANTIGRAVITY GIT WARNING" in body["reason"]

    def test_antigravity_shape_allows_unrelated_command(self):
        payload = json.dumps(
            {
                "conversationId": "agy-session",
                "workspacePaths": ["/tmp/workspace"],
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "ls -la"},
                },
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
        # Neither a Cursor top-level `command` string nor an Antigravity
        # `run_command` toolCall.args.CommandLine is present.
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

    def test_fails_closed_on_excessive_substitution_nesting(self):
        # Recursion depth is bounded by the interpreter; exceeding it must
        # fail closed (exit 2).
        command = "true " + "$(true " * 600 + "x" + ")" * 600
        payload = json.dumps(
            {
                "conversationId": "agy-session",
                "workspacePaths": ["/tmp/workspace"],
                "toolCall": {"name": "run_command", "args": {"CommandLine": command}},
            }
        )
        result = run_gate(payload)
        assert result.returncode == 2
        assert "failing closed" in result.stderr


if __name__ == "__main__":
    unittest.main()
