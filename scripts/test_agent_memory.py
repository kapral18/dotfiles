#!/usr/bin/env python3
"""Tests for agent_memory.py."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)


class TestAgentMemory(unittest.TestCase):
    """WHEN wiping hook memory for a workspace."""

    def test_wipe_current_deletes_explicit_active_topic_files(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "_active_topic.txt").write_text("review-123\n")
                (spec_dir / "review-123.txt").write_text("spec")
                (spec_dir / "review-123.worklog.jsonl").write_text("{}\n")
                (spec_dir / "other.txt").write_text("keep")

                with contextlib.redirect_stdout(io.StringIO()):
                    assert agent_memory.main(["wipe-current", "--workspace", str(workspace)]) == 0

                assert not (spec_dir / "review-123.txt").exists()
                assert not (spec_dir / "review-123.worklog.jsonl").exists()
                assert (spec_dir / "other.txt").exists()
                assert (spec_dir / "_active_topic.txt").exists()
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_wipe_current_prefers_latest_session_topic_on_default_branch(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp, check=True)
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                older = spec_dir / "session-old.worklog.jsonl"
                newer = spec_dir / "session-new.worklog.jsonl"
                older.write_text("old\n")
                newer.write_text("new\n")
                now = time.time()
                os.utime(older, (now - 10, now - 10))
                os.utime(newer, (now, now))
                (spec_dir / "current.worklog.jsonl").write_text("keep\n")

                with contextlib.redirect_stdout(io.StringIO()):
                    assert agent_memory.main(["wipe-current", "--workspace", str(workspace)]) == 0

                assert older.exists()
                assert not newer.exists()
                assert (spec_dir / "current.worklog.jsonl").exists()
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_use_sets_active_named_topic_and_seeds_spec(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                with contextlib.redirect_stdout(io.StringIO()):
                    assert agent_memory.main(["use", "memory-systems", "--workspace", str(workspace)]) == 0

                spec_dir = agent_memory.spec_dir_for(workspace)
                assert (spec_dir / "_active_topic.txt").read_text().strip() == "memory-systems"
                assert (spec_dir / "memory-systems.txt").read_text().startswith("topic: memory-systems")
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_use_does_not_clobber_existing_spec(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "memory-systems.txt").write_text("topic: memory-systems\nexisting content\n")

                with contextlib.redirect_stdout(io.StringIO()):
                    assert agent_memory.main(["use", "memory-systems", "--workspace", str(workspace)]) == 0

                assert "existing content" in (spec_dir / "memory-systems.txt").read_text()
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_use_rejects_generic_current_topic(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        agent_memory.main(["use", "current", "--workspace", str(workspace)])
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_status_json_reports_named_topic_and_spec(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                with contextlib.redirect_stdout(io.StringIO()):
                    agent_memory.main(["use", "memory-systems", "--workspace", str(workspace)])

                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    assert agent_memory.main(["status", "--json", "--workspace", str(workspace)]) == 0

                payload = json.loads(buffer.getvalue())
                assert payload["selected_topic"] == "memory-systems"
                assert payload["is_named_topic"] is True
                assert payload["spec_exists"] is True
                assert payload["spec_file"].endswith("memory-systems.txt")
                assert payload["workspace"] == str(workspace)
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_status_json_with_session_id_does_not_select_active_pointer(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp, check=True)
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "_active_topic.txt").write_text("memory-systems\n")
                (spec_dir / "memory-systems.txt").write_text("target: stale active pointer\n")

                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    assert (
                        agent_memory.main(
                            [
                                "status",
                                "--json",
                                "--workspace",
                                str(workspace),
                                "--session-id",
                                "abc/123",
                            ]
                        )
                        == 0
                    )

                payload = json.loads(buffer.getvalue())
                assert payload["selected_topic"] == "session-abc-123"
                assert payload["session_key"] == "abc-123"
                assert payload["session_selected_topic"] is None
                assert payload["is_named_topic"] is False
                assert payload["spec_file"].endswith("session-abc-123.txt")
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_status_json_flags_generic_topic_as_unnamed(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    assert (
                        agent_memory.main(["status", "--json", "--topic", "current", "--workspace", str(workspace)])
                        == 0
                    )

                payload = json.loads(buffer.getvalue())
                assert payload["selected_topic"] == "current"
                assert payload["is_named_topic"] is False
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_select_prints_selected_context_for_current_session(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "memory-systems.txt").write_text("target: make memory explicit\n")
                (spec_dir / "memory-systems.worklog.jsonl").write_text('{"event":"note","text":"recent work"}\n')

                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    assert (
                        agent_memory.main(
                            [
                                "select",
                                "memory-systems",
                                "--workspace",
                                str(workspace),
                                "--session-id",
                                "abc-123",
                            ]
                        )
                        == 0
                    )

                output = buffer.getvalue()
                assert "### Selected Topic Context" in output
                assert "target: make memory explicit" in output
                assert "#### Recent Hook Worklog" in output
                assert "recent work" in output
                assert (spec_dir / ".session-topic-abc-123.txt").read_text().strip() == "memory-systems"
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_select_migrates_prebind_fallback_worklog_into_topic(self):
        import agent_memory
        import worklog_queue

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                fallback = spec_dir / "session-sess-abc.worklog.jsonl"
                flushed_entry = {
                    "event": "postToolUse",
                    "text": "pre-bind flushed",
                    "ts": "2026-07-11T12:00:00+00:00",
                    "worklog_id": "pre-1",
                }
                fallback.write_text(json.dumps(flushed_entry, sort_keys=True) + "\n")
                worklog_queue.enqueue(
                    spec_dir,
                    "sess-abc",
                    "session-sess-abc",
                    fallback,
                    {"event": "postToolUse", "text": "pre-bind pending", "ts": "2026-07-11T12:00:01+00:00"},
                    start_worker=False,
                )

                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    assert (
                        agent_memory.main(
                            [
                                "select",
                                "memory-systems",
                                "--create",
                                "--workspace",
                                str(workspace),
                                "--session-id",
                                "sess-abc",
                            ]
                        )
                        == 0
                    )

                output = buffer.getvalue()
                assert "migrated: 2 pre-bind worklog events from session-sess-abc" in output
                assert not fallback.exists()
                topic_worklog = spec_dir / "memory-systems.worklog.jsonl"
                entries = [json.loads(line) for line in topic_worklog.read_text().splitlines()]
                assert [entry["text"] for entry in entries] == ["pre-bind flushed", "pre-bind pending"]
                assert "pre-bind flushed" in output
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_select_sanitizes_review_topic_clean_room(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
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

                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    assert (
                        agent_memory.main(
                            [
                                "select",
                                "review-123",
                                "--workspace",
                                str(workspace),
                                "--session-id",
                                "review-session",
                            ]
                        )
                        == 0
                    )

                output = buffer.getvalue()
                assert "target: PR owner/repo#123" in output
                assert "prior conclusion should not be injected" not in output
                assert "stale finding" not in output
                assert "verdict: Approve" not in output
                assert "Recent Hook Worklog" not in output
                assert "review clean-room mode" in output
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_select_omits_oversized_spec_with_pointer(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "oversized-topic.txt").write_text("target: " + ("x" * 4000) + "\nnever inject partial")

                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    assert (
                        agent_memory.main(
                            [
                                "select",
                                "oversized-topic",
                                "--workspace",
                                str(workspace),
                                "--session-id",
                                "abc-999",
                            ]
                        )
                        == 0
                    )

                output = buffer.getvalue()
                assert "Active topic spec omitted" in output
                assert "never inject partial" not in output
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_select_bounds_oversized_review_spec_after_sanitizing(self):
        # Regression guard for memory-review-bypass follow-up (fix-review-context-bound):
        # bounded_spec_text() must not return neutral_review_spec()'s output unconditionally
        # — a review spec whose pre-conclusion body alone exceeds SELECT_CONTEXT_MAX_SPEC_CHARS
        # must still fall through to the wholesale omission-with-pointer contract, never a
        # verbatim (or partially truncated) dump of the sanitized body.
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "review-big.txt").write_text(
                    "\n".join(
                        [
                            "topic: review-big",
                            "target: PR owner/repo#999",
                            "x" * 4000,
                            "",
                            "verified facts:",
                            "  - prior conclusion should never appear",
                            "findings:",
                            "  1. stale finding should never appear",
                            "verdict: Approve",
                        ]
                    )
                )
                (spec_dir / "review-big.worklog.jsonl").write_text('{"line": "prior finding"}\n')

                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    assert (
                        agent_memory.main(
                            [
                                "select",
                                "review-big",
                                "--workspace",
                                str(workspace),
                                "--session-id",
                                "review-big-session",
                            ]
                        )
                        == 0
                    )

                output = buffer.getvalue()
                assert "Active topic spec omitted" in output
                assert "x" * 4000 not in output
                assert "prior conclusion should never appear" not in output
                assert "stale finding should never appear" not in output
                assert "verdict: Approve" not in output
                assert "Recent Hook Worklog" not in output
                assert len(output) < 3000
            finally:
                agent_memory.SPEC_ROOT = old_spec_root


if __name__ == "__main__":
    unittest.main()
