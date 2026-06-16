#!/usr/bin/env python3
"""Regression tests for shared agent hook scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / "home" / "exact_dot_agents" / "exact_hooks"


def run_hook(name: str, payload: dict, env: dict | None = None) -> dict:
    result = subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(f"{name} failed:\nSTDOUT={result.stdout}\nSTDERR={result.stderr}")
    return json.loads(result.stdout or "{}")


def make_aikb_stub(directory: Path, rows: list[dict]) -> dict:
    """Create a fake `,ai-kb` on PATH that returns `rows` for `search --json`.

    Returns an env dict (PATH-prefixed) to pass to run_hook so the
    session_context warm-start resolves this stub instead of the real CLI.
    """
    bindir = directory / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    stub = bindir / ",ai-kb"
    payload = json.dumps(rows)
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "args = sys.argv[1:]\n"
        "if args and args[0] == 'search':\n"
        f"    sys.stdout.write({payload!r})\n"
        "    sys.exit(0)\n"
        "sys.exit(0)\n"
    )
    stub.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    return env


class TestAgentHooks(unittest.TestCase):
    """WHEN Cursor CLI lifecycle hooks run."""

    def make_git_workspace(self, branch: str) -> tempfile.TemporaryDirectory:
        tmp = tempfile.TemporaryDirectory()
        subprocess.run(["git", "init", "-q", "-b", branch], cwd=tmp.name, check=True)
        return tmp

    def test_worklog_recorder_writes_topic_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "hook_event_name": "postToolUse",
                "workspace_roots": [tmp],
                "model": "test-model",
                "tool_name": "Shell",
                "tool_input": {"command": "printf ok"},
                "tool_output": '{"stdout":"ok"}',
                "duration": 12,
            }

            assert run_hook("executable_worklog_recorder.py", payload) == {}
            workspace = str(Path(tmp).resolve())
            worklog = Path("/tmp/specs") / workspace.lstrip("/") / "current.worklog.jsonl"
            entry = json.loads(worklog.read_text().splitlines()[-1])

            assert entry["event"] == "postToolUse"
            assert entry["command"] == "printf ok"
            assert entry["tool_name"] == "Shell"

    def test_worklog_recorder_keeps_bounded_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "hook_event_name": "postToolUse",
                "workspace_roots": [tmp],
                "model": "test-model",
                "tool_name": "Shell",
                "tool_input": {"command": "printf ok"},
                "tool_output": '{"stdout":"ok"}',
                "duration": 12,
            }

            for _ in range(205):
                assert run_hook("executable_worklog_recorder.py", payload) == {}

            workspace = str(Path(tmp).resolve())
            worklog = Path("/tmp/specs") / workspace.lstrip("/") / "current.worklog.jsonl"
            assert len(worklog.read_text().splitlines()) == 200

    def test_session_context_emits_cursor_and_claude_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "_active_topic.txt").write_text("hook-test\n")
            (spec_dir / "hook-test.txt").write_text("target: prove context injection\n")

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
            }
            result = run_hook("executable_session_context.py", payload)

            assert "target: prove context injection" in result["additional_context"]
            assert result["hookSpecificOutput"]["hookEventName"] == "SessionStart"
            assert "target: prove context injection" in result["hookSpecificOutput"]["additionalContext"]

    def test_session_context_nudges_topic_on_default_branch_without_explicit_topic(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "current.txt").write_text("target: stale shared main context\n")
            (spec_dir / "current.worklog.jsonl").write_text('{"line": "stale"}\n')

            payload = {
                "conversation_id": "abc-123",
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
            }
            result = run_hook("executable_session_context.py", payload)
            context = result["additional_context"]

            assert "stale shared main context" not in context
            assert "stale" not in context
            assert "No Named Topic Active" in context
            assert ",agent-memory use" in context
            assert ",ai-kb search" in context

    def test_worklog_recorder_uses_session_topic_on_default_branch_without_explicit_topic(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            payload = {
                "conversation_id": "abc-123",
                "hook_event_name": "postToolUse",
                "workspace_roots": [tmp],
                "tool_name": "Shell",
                "tool_input": {"command": "printf ok"},
                "tool_output": '{"stdout":"ok"}',
            }

            assert run_hook("executable_worklog_recorder.py", payload) == {}
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")

            assert not (spec_dir / "current.worklog.jsonl").exists()
            assert (spec_dir / "session-abc-123.worklog.jsonl").exists()

    def test_session_context_keeps_current_topic_on_feature_branch(self):
        with self.make_git_workspace("feature-memory") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "current.txt").write_text("target: feature continuity\n")

            payload = {
                "conversation_id": "abc-123",
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
            }
            result = run_hook("executable_session_context.py", payload)

            assert "Active topic: `current`" in result["additional_context"]
            assert "target: feature continuity" in result["additional_context"]

    def test_session_context_can_be_disabled_by_workspace_sentinel(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "_no_session_context").write_text("")
            (spec_dir / "current.txt").write_text("target: should not inject\n")

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
            }
            assert run_hook("executable_session_context.py", payload) == {}

    def test_session_context_omits_oversized_spec_and_bounds_worklog_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "current.txt").write_text("target: " + ("x" * 4000) + "\nnever inject partial")
            (spec_dir / "current.worklog.jsonl").write_text("\n".join(f'{{"line": {i}}}' for i in range(30)) + "\n")

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
            }
            result = run_hook("executable_session_context.py", payload)
            context = result["additional_context"]

            assert "Active topic spec omitted" in context
            assert "never inject partial" not in context
            assert '"line": 29' in context
            assert '"line": 0' not in context
            assert len(context) < 6500

    def test_session_context_sanitizes_review_specs(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "_active_topic.txt").write_text("review-123\n")
            (spec_dir / "review-123.txt").write_text(
                "\n".join(
                    [
                        "topic: review-123",
                        "target: PR owner/repo#123",
                        "diff: 2 files",
                        "",
                        "verified facts:",
                        "  - prior conclusion should not be injected",
                        "findings:",
                        "  1. stale finding",
                        "verdict: Approve",
                    ]
                )
            )
            (spec_dir / "review-123.worklog.jsonl").write_text('{"line": "prior finding"}\n')

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
            }
            result = run_hook("executable_session_context.py", payload)
            context = result["additional_context"]

            assert "target: PR owner/repo#123" in context
            assert "prior conclusion should not be injected" not in context
            assert "stale finding" not in context
            assert "verdict: Approve" not in context
            assert "Recent Hook Worklog" not in context
            assert "review clean-room mode" in context

    def test_session_context_appends_aikb_reminder_with_named_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "_active_topic.txt").write_text("memory-systems\n")
            (spec_dir / "memory-systems.txt").write_text("target: wire memory systems\n")

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
            }
            context = run_hook("executable_session_context.py", payload)["additional_context"]

            assert "target: wire memory systems" in context
            assert "Durable Memory (,ai-kb)" in context
            assert ",ai-kb remember" in context
            assert "No Named Topic Active" not in context

    def test_session_context_warmstart_injects_relevant_learnings_for_named_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "_active_topic.txt").write_text("memory-systems\n")
            (spec_dir / "memory-systems.txt").write_text("target: wire memory systems\n")

            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "title": "Local capsule that should surface",
                        "body": "B" * 400,
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                    }
                ],
            )
            payload = {"hook_event_name": "sessionStart", "workspace_roots": [tmp]}
            context = run_hook("executable_session_context.py", payload, env=env)["additional_context"]

            assert "### Relevant Learnings (,ai-kb)" in context
            assert "Local capsule that should surface" in context
            assert "(gotcha)" in context
            assert "…" in context  # body truncated to the bound

    def test_session_context_warmstart_gates_out_unrelated_workspace_project_capsule(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "_active_topic.txt").write_text("memory-systems\n")
            (spec_dir / "memory-systems.txt").write_text("target: wire memory systems\n")

            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "title": "Foreign project capsule",
                        "body": "from another repo",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": "/some/other/repo",
                    },
                    {
                        "title": "Universal principle capsule",
                        "body": "applies everywhere",
                        "kind": "principle",
                        "scope": "universal",
                        "workspace_path": "/some/other/repo",
                    },
                ],
            )
            payload = {"hook_event_name": "sessionStart", "workspace_roots": [tmp]}
            context = run_hook("executable_session_context.py", payload, env=env)["additional_context"]

            assert "Foreign project capsule" not in context  # other-workspace project scope: gated out
            assert "Universal principle capsule" in context  # universal scope: allowed cross-project

    def test_session_context_warmstart_skipped_for_generic_and_session_topics(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = Path("/tmp/specs") / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            # No named pointer on a default branch -> session-* fallback; seed a session spec too.
            (spec_dir / "current.txt").write_text("target: generic fallback\n")

            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "title": "Should never surface for generic topic",
                        "body": "noise",
                        "kind": "gotcha",
                        "scope": "universal",
                        "workspace_path": workspace,
                    }
                ],
            )
            payload = {
                "conversation_id": "abc-123",
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
            }
            context = run_hook("executable_session_context.py", payload, env=env)["additional_context"]

            assert "### Relevant Learnings (,ai-kb)" not in context
            assert "Should never surface" not in context

    def test_pr_anchor_verification_is_instruction_only(self):
        files_to_check = [
            REPO / "home" / "dot_copilot" / "hooks.json",
            REPO / "home" / "dot_gemini" / "settings.json",
            REPO / "home" / "dot_cursor" / "hooks.json",
        ]

        for file_path in files_to_check:
            content = file_path.read_text()
            assert "pr-anchor-gate" not in content
            assert "pulls/.*/(reviews|comments)" not in content

        assert not (REPO / "home" / "dot_copilot" / "exact_hooks" / "executable_copilot-pr-anchor-gate.sh").exists()
        assert not (HOOKS / "executable_gemini-pr-anchor-gate.sh").exists()


if __name__ == "__main__":
    unittest.main()
