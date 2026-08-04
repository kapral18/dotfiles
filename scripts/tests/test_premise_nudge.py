#!/usr/bin/env python3
"""Behavioral tests for the premise-nudge PreToolUse/PostToolUse hook.

The hook is wired into six harness configs, so a silent regression reaches every agent
session at once. These tests pin the two things a config cannot: which commands are
premise-carrying, and the per-harness wire format the nudge rides on.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO

HOOK = REPO / "home" / "exact_dot_agents" / "exact_hooks" / "executable_premise_nudge.py"


def run_hook(payload: object, env_extra: dict[str, str] | None = None) -> dict:
    """Invoke the hook exactly as a harness does: JSON on stdin, JSON on stdout."""
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    env = None
    if env_extra:
        import os

        env = {**os.environ, **env_extra}
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=raw,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
    return json.loads(result.stdout)


def context_of(result: dict) -> str:
    return str(result.get("hookSpecificOutput", {}).get("additionalContext", ""))


def assert_hook_is_live(case: unittest.TestCase) -> None:
    """Guard for silence assertions: `{}` from a dead hook looks like `{}` from a correct one.

    Every "should stay silent" test asserts an absence, which a hook that returns `{}`
    unconditionally also satisfies. Pairing each with one known-firing payload keeps the
    silence meaningful instead of vacuous.
    """
    live = run_hook({"tool_name": "Bash", "tool_input": {"command": "git stash"}})
    case.assertIn("Premise check", context_of(live), "hook is not firing at all; silence proves nothing")


class TestPremiseNudgeFiring(unittest.TestCase):
    """WHEN a command's success would look the same whether or not its premise holds."""

    def test_when_command_is_premise_carrying_should_emit_nudge(self):
        # Each of these can succeed while its premise is false, which is the whole trigger.
        for command in (
            "git stash",
            "git checkout -- file.py",
            "git checkout HEAD file.py",
            "git restore --source=HEAD f",
            "git revert abc123",
            "git reset --hard",
            "git push --force-with-lease",
            "pytest -k test_foo",
            "go test ./... -run TestX",
            "jest --filter mock",
            "monkeypatch.setattr(x)",
        ):
            with self.subTest(command=command):
                result = run_hook({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertIn("Premise check", context_of(result), f"expected a nudge for: {command}")

    def test_when_command_is_ordinary_should_stay_silent(self):
        # A nudge on every command is noise, and noise trains the agent to ignore it.
        # `git stash list` and `git checkout <branch>` are the near-misses worth pinning.
        assert_hook_is_live(self)
        for command in (
            "ls -la",
            "git log",
            "git status",
            "git push origin main",
            "git stash list",
            "git checkout main",
            "git checkout -b new-branch",
            "pytest tests/",
            # The subcommands are only premise-carrying under `git`. Without that anchor,
            # `make clean` and a prose mention of "stash" both fire.
            "make clean",
            "npm run clean -fd",
            "yarn clean",
            "rm -rf build && clean -fd",
            "echo 'remember to stash your work'",
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook({"tool_name": "Bash", "tool_input": {"command": command}}), {})

    def test_when_command_only_mentions_a_mock_should_stay_silent(self):
        # Recon *about* mocks creates no mock, so asserting "the mock matches the real interface"
        # about a grep is a false premise. Bare-word matching on the most common English token of
        # the six is also what trains an agent to ignore the channel the git patterns ride on.
        assert_hook_is_live(self)
        for command in (
            "rg mock src/",
            "git commit -m 'add stub'",
            "npm install mock-fs",
            "ls node_modules | grep mock",
            "code src/mock.ts",
            "npm test -- --grep mock",
            "rg 'xfail' tests/",
            "git log --grep=skipif",
            # Source text, not a run: a skip marker only carries the premise when a runner
            # actually executed with it.
            "it.skip('x')",
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook({"tool_name": "Bash", "tool_input": {"command": command}}), {})

    def test_when_mock_is_actually_constructed_should_emit_nudge(self):
        for command in (
            "monkeypatch.setattr(x)",
            "mocker.patch('a.b')",
            "jest.mock('./x')",
            "sinon.stub(obj,'m')",
            "vi.spyOn(o,'m')",
            "unittest.mock.patch",
        ):
            with self.subTest(command=command):
                result = run_hook({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertIn("Premise check", context_of(result), f"expected a nudge for: {command}")

    def test_when_git_command_discards_nothing_should_stay_silent(self):
        # `--soft` keeps index and working tree; `-n`/`--dry-run` is definitionally a no-op.
        assert_hook_is_live(self)
        for command in ("git reset --soft HEAD~1", "git clean -n", "git clean --dry-run"):
            with self.subTest(command=command):
                self.assertEqual(run_hook({"tool_name": "Bash", "tool_input": {"command": command}}), {})

    def test_when_dry_run_flag_is_in_a_later_command_should_still_emit_nudge(self):
        # The dangerous direction: a `-n` belonging to a *chained* command must not suppress the
        # nudge for a real `git clean -fd`. Scanning the whole line silently did exactly that.
        for command in (
            "git clean -fd && echo -n done",
            "git clean -fd; printf -n x",
            "git clean -n && git clean -fd",
            # Newline is a command separator too. Pinning only `;`/`&&` left the identical
            # multi-line form silent, which is a routine agent idiom.
            "git clean -fd\necho -n done",
            # After `--` everything is a pathspec, so a file literally named `-n` is not a flag.
            "git clean -fd -- -n",
        ):
            with self.subTest(command=command):
                result = run_hook({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertIn("Premise check", context_of(result), f"expected a nudge for: {command}")

    def test_when_dry_run_flag_is_clustered_should_stay_silent(self):
        # `-n` can sit anywhere in a combined short-flag run; each of these was confirmed
        # non-destructive by running it against a scratch repo.
        assert_hook_is_live(self)
        for command in ("git clean -nfd", "git clean -fdn", "git clean -ndf", "git clean -f -n", "git clean -xdfn"):
            with self.subTest(command=command):
                self.assertEqual(run_hook({"tool_name": "Bash", "tool_input": {"command": command}}), {})

    def test_when_exclude_flag_ends_in_n_should_still_emit_nudge(self):
        # `-e` takes a pattern, so `-en` is "exclude the pattern `n`", not a dry run. Confirmed
        # against real git: `git clean -fd -en` deletes files. Treating it as dry-run silenced
        # the nudge on a destructive command, which is the dangerous direction.
        for command in ("git clean -fd -en", "git clean -fdx -en", "git clean -df -en", "git clean -f -en"):
            with self.subTest(command=command):
                result = run_hook({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertIn("Premise check", context_of(result), f"expected a nudge for: {command}")

    def test_when_git_carries_global_options_should_still_emit_nudge(self):
        # `git` takes global options before the subcommand, so `git -C <path> clean -fd` is the
        # same destructive command. Anchoring on `git\s+<sub>` missed every such form, and `-C`
        # is the norm in agent use — confirmed against real git that these delete files.
        for command in (
            "git -C /other/repo clean -fd",
            "git --git-dir=x clean -fd",
            "git --work-tree=/w clean -fd",
            "git -C /x stash",
            "git -c core.x=1 reset --hard",
            "git -C /x checkout -- f.py",
            "git -C /x restore f",
            "git -C /x revert abc",
            "git -C /x push --force-with-lease",
            "git -C /x clean -fd -en",
            # Enumerating known flags was the wrong shape: each of these silently missed a
            # destructive command until the prefix was generalized to skip any option token.
            "git --no-pager clean -fd",
            "git -p clean -fd",
            "git -P clean -fd",
            "git --exec-path=/usr/bin clean -fd",
            "git --namespace=x clean -fd",
            "git -c 'a.b=1' clean -fd",
            "git -C /x -c a.b=1 clean -fd",
            "git --no-pager stash",
            "git --no-pager reset --hard",
        ):
            with self.subTest(command=command):
                result = run_hook({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertIn("Premise check", context_of(result), f"expected a nudge for: {command}")

    def test_when_git_carries_global_options_on_a_safe_command_should_stay_silent(self):
        assert_hook_is_live(self)
        for command in (
            "git -C /x stash list",
            "git -C /x clean -n",
            "git -C /x reset --soft HEAD~1",
            "git -C /x checkout main",
            "git -C /x log",
            "git -C /x push origin main",
            # The generalized option-skipping prefix must not swallow the subcommand itself.
            "git --no-pager diff",
            "git --no-pager status",
            "git --no-pager stash list",
            "git --no-pager checkout main",
            "git --no-pager reset --soft HEAD~1",
            "git --no-pager clean -n",
            "git branch -d x",
            "git add -A",
            "git commit -m x",
            # A subcommand name appearing as an *argument* is not that subcommand. A prefix that
            # skips any token (rather than only option-shaped ones) fires on all of these.
            "git log --oneline stash",
            "git branch -D clean",
            "git add -p reset",
            "git diff HEAD stash",
            "git config --get clean.requireForce",
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook({"tool_name": "Bash", "tool_input": {"command": command}}), {})

    def test_when_git_command_actually_discards_should_emit_nudge(self):
        for command in ("git reset --hard", "git clean -fd", "git clean -fdx", "git clean -fdX"):
            with self.subTest(command=command):
                result = run_hook({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertIn("Premise check", context_of(result), f"expected a nudge for: {command}")

    def test_when_tool_is_not_a_shell_should_stay_silent(self):
        # A Read whose argument happens to contain "git stash" is not running it.
        assert_hook_is_live(self)
        result = run_hook({"tool_name": "Read", "tool_input": {"command": "git stash"}})
        self.assertEqual(result, {})


class TestPremiseNudgeWireFormat(unittest.TestCase):
    """WHEN emitting to a harness that declared its own output shape."""

    def test_when_harness_is_claude_should_emit_both_channels(self):
        result = run_hook({"tool_name": "Bash", "tool_input": {"command": "git stash"}})
        self.assertIn("additional_context", result)
        self.assertIn("Premise check", context_of(result))

    def test_when_harness_is_codex_should_emit_only_hook_specific(self):
        # Codex rejects unknown top-level keys, so additional_context must be dropped.
        result = run_hook(
            {"tool_name": "shell", "tool_input": {"command": "git stash"}},
            env_extra={"AGENT_HOOK_OUTPUT": "hook_specific"},
        )
        self.assertNotIn("additional_context", result)
        self.assertIn("Premise check", context_of(result))

    def test_when_event_is_post_tool_use_should_echo_that_event_name(self):
        result = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "git stash"}, "hook_event_name": "PostToolUse"}
        )
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PostToolUse")

    def test_when_payload_is_cursor_shaped_should_read_top_level_command(self):
        # Cursor's shell events carry the command without naming a tool.
        result = run_hook({"command": "git push --force-with-lease"})
        self.assertIn("Premise check", context_of(result))

    def test_when_payload_is_copilot_shaped_should_parse_json_encoded_args(self):
        result = run_hook({"tool_name": "shell", "arguments": json.dumps({"command": "git stash"})})
        self.assertIn("Premise check", context_of(result))


class TestPremiseNudgeFailsOpen(unittest.TestCase):
    """WHEN the payload is malformed; a hook that blocks a call is worse than a missed nudge."""

    def test_when_payload_is_unusable_should_return_empty_object(self):
        for payload in ("", "   ", "not json{{", "[]", '"a string"', "null", "{}"):
            with self.subTest(payload=payload):
                self.assertEqual(run_hook(payload), {})


if __name__ == "__main__":
    unittest.main()
