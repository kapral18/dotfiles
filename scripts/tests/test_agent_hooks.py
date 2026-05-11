#!/usr/bin/env python3
"""Regression tests for shared agent hook scripts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / "home" / "exact_dot_agents" / "exact_hooks"


def run_hook(name: str, payload: dict) -> dict:
    result = subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if result.returncode != 0:
        raise AssertionError(f"{name} failed:\nSTDOUT={result.stdout}\nSTDERR={result.stderr}")
    return json.loads(result.stdout or "{}")


class TestAgentHooks(unittest.TestCase):
    """WHEN Cursor CLI lifecycle hooks run."""

    def make_git_workspace(self, branch: str) -> tempfile.TemporaryDirectory:
        tmp = tempfile.TemporaryDirectory()
        subprocess.run(["git", "init", "-q", "-b", branch], cwd=tmp.name, check=True)
        return tmp

    def test_evidence_anchor_bounded_followup_for_unanchored_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = {
                "conversation_id": "c1",
                "generation_id": "g1",
                "hook_event_name": "afterAgentResponse",
                "workspace_roots": [tmp],
                "text": "The Cursor hook setup is ready and it works correctly now.",
            }

            assert run_hook("executable_evidence_anchor.py", base) == {}

            stop = dict(base, hook_event_name="stop", status="completed", loop_count=0)
            first = run_hook("executable_evidence_anchor.py", stop)
            second = run_hook("executable_evidence_anchor.py", stop)

            assert "followup_message" in first
            assert "Retry:" in first["followup_message"]
            assert second == {}

    def test_evidence_anchor_allows_claims_with_visible_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "conversation_id": "c1",
                "generation_id": "g1",
                "hook_event_name": "afterAgentResponse",
                "workspace_roots": [tmp],
                "text": "Verified with `python3 scripts/tests/test_agent_hooks.py`: all tests passed.",
            }

            assert run_hook("executable_evidence_anchor.py", payload) == {}
            stop = dict(payload, hook_event_name="stop", status="completed", loop_count=0)
            assert run_hook("executable_evidence_anchor.py", stop) == {}

    def test_evidence_anchor_rejects_vague_verification_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "conversation_id": "c1",
                "generation_id": "g1",
                "hook_event_name": "afterAgentResponse",
                "workspace_roots": [tmp],
                "text": "Verified. The hook setup is correct and ready now.",
            }

            assert run_hook("executable_evidence_anchor.py", payload) == {}
            stop = dict(payload, hook_event_name="stop", status="completed", loop_count=0)
            result = run_hook("executable_evidence_anchor.py", stop)
            assert "followup_message" in result

    def test_evidence_anchor_allows_explicit_unknown_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "conversation_id": "c1",
                "generation_id": "g1",
                "hook_event_name": "afterAgentResponse",
                "workspace_roots": [tmp],
                "text": "The remote billing state is Unknown because it requires live account access that is not available locally.",
            }

            assert run_hook("executable_evidence_anchor.py", payload) == {}
            stop = dict(payload, hook_event_name="stop", status="completed", loop_count=0)
            assert run_hook("executable_evidence_anchor.py", stop) == {}

    def test_evidence_anchor_tracks_claims_from_thoughts(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "conversation_id": "c1",
                "generation_id": "g1",
                "hook_event_name": "afterAgentThought",
                "workspace_roots": [tmp],
                "text": "The config loader uses the user hook file and this is why the setup works.",
            }

            assert run_hook("executable_evidence_anchor.py", payload) == {}
            stop = dict(payload, hook_event_name="stop", status="completed", loop_count=0)
            result = run_hook("executable_evidence_anchor.py", stop)
            assert "followup_message" in result

    def test_evidence_anchor_records_later_tool_evidence_without_global_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            thought = {
                "conversation_id": "c1",
                "generation_id": "g1",
                "hook_event_name": "afterAgentThought",
                "workspace_roots": [tmp],
                "text": "The hook setup loads from the Cursor user hooks file.",
            }
            evidence = {
                "conversation_id": "c1",
                "generation_id": "g1",
                "hook_event_name": "postToolUse",
                "workspace_roots": [tmp],
                "tool_name": "Read",
                "tool_input": {"path": "/Users/test/.cursor/hooks.json"},
                "tool_output": '{"hooks":{"stop":[]}}',
            }

            assert run_hook("executable_evidence_anchor.py", thought) == {}
            assert run_hook("executable_evidence_anchor.py", evidence) == {}
            stop = dict(thought, hook_event_name="stop", status="completed", loop_count=0)
            result = run_hook("executable_evidence_anchor.py", stop)
            assert "followup_message" in result
            assert "The hook setup loads from the Cursor user hooks file." in result["followup_message"]

    def test_evidence_anchor_final_response_replaces_thought_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            thought = {
                "conversation_id": "c1",
                "generation_id": "g1",
                "hook_event_name": "afterAgentThought",
                "workspace_roots": [tmp],
                "text": "The hook setup loads from the Cursor user hooks file.",
            }
            response = {
                **thought,
                "hook_event_name": "afterAgentResponse",
                "text": (
                    "Verified: `/Users/test/.cursor/hooks.json` contains the user hook "
                    "configuration, so the hook setup loads from that file."
                ),
            }

            assert run_hook("executable_evidence_anchor.py", thought) == {}
            assert run_hook("executable_evidence_anchor.py", response) == {}
            stop = dict(thought, hook_event_name="stop", status="completed", loop_count=0)
            assert run_hook("executable_evidence_anchor.py", stop) == {}

    def test_evidence_anchor_keeps_unanchored_final_claim_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "conversation_id": "c1",
                "generation_id": "g1",
                "hook_event_name": "afterAgentResponse",
                "workspace_roots": [tmp],
                "text": (
                    "Verified: `/tmp/probe.txt` shows the hook script ran.\n\n"
                    "The review findings are complete and the CI flakes are unrelated."
                ),
            }

            assert run_hook("executable_evidence_anchor.py", payload) == {}
            stop = dict(payload, hook_event_name="stop", status="completed", loop_count=0)
            result = run_hook("executable_evidence_anchor.py", stop)
            assert "followup_message" in result
            assert "CI flakes are unrelated" in result["followup_message"]

    def test_evidence_anchor_writes_decision_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "conversation_id": "c1",
                "generation_id": "g1",
                "hook_event_name": "afterAgentResponse",
                "workspace_roots": [tmp],
                "text": "The hook setup is correct and ready now.",
            }

            assert run_hook("executable_evidence_anchor.py", payload) == {}
            workspace = str(Path(tmp).resolve())
            decision_log = Path("/tmp/specs") / workspace.lstrip("/") / "current.evidence_decisions.jsonl"
            entries = [json.loads(line) for line in decision_log.read_text().splitlines()]

            assert entries[-1]["decision"] == "track"
            assert entries[-1]["reason"] == "unanchored_claim_units"

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

    def test_session_context_uses_session_topic_on_default_branch_without_explicit_topic(self):
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

            assert result == {}

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


if __name__ == "__main__":
    unittest.main()
