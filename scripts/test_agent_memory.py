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

    def test_merge_combines_specs_worklogs_and_rewrites_pointers(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "source-topic.txt").write_text("topic: source-topic\nsource details\n")
                (spec_dir / "dest-topic.txt").write_text("topic: dest-topic\ndest details\n")
                (spec_dir / "source-topic.no_context").write_text("")
                (spec_dir / "_active_topic.txt").write_text("source-topic\n")
                (spec_dir / ".session-topic-session-a.txt").write_text("source-topic\n")
                (spec_dir / ".session-topic-session-b.txt").write_text("dest-topic\n")
                (spec_dir / "dest-topic.worklog.jsonl").write_text(
                    json.dumps(
                        {
                            "event": "note",
                            "text": "dest middle",
                            "ts": "2026-07-11T12:00:02+00:00",
                            "worklog_id": "dest-1",
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                (spec_dir / "source-topic.worklog.jsonl").write_text(
                    "\n".join(
                        [
                            json.dumps(
                                {
                                    "event": "note",
                                    "text": "source late",
                                    "ts": "2026-07-11T12:00:03+00:00",
                                    "worklog_id": "source-2",
                                },
                                sort_keys=True,
                            ),
                            json.dumps(
                                {
                                    "event": "note",
                                    "text": "source early",
                                    "ts": "2026-07-11T12:00:01+00:00",
                                    "worklog_id": "source-1",
                                },
                                sort_keys=True,
                            ),
                        ]
                    )
                    + "\n"
                )

                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    assert (
                        agent_memory.main(["merge", "source-topic", "dest-topic", "--workspace", str(workspace)]) == 0
                    )

                dest_spec = (spec_dir / "dest-topic.txt").read_text()
                assert dest_spec.startswith("topic: dest-topic\ndest details\n")
                assert "--- merged from source-topic on " in dest_spec
                assert dest_spec.endswith("topic: source-topic\nsource details\n")
                entries = [
                    json.loads(line) for line in (spec_dir / "dest-topic.worklog.jsonl").read_text().splitlines()
                ]
                assert [entry["text"] for entry in entries] == ["source early", "dest middle", "source late"]
                assert (spec_dir / ".session-topic-session-a.txt").read_text().strip() == "dest-topic"
                assert (spec_dir / ".session-topic-session-b.txt").read_text().strip() == "dest-topic"
                assert (spec_dir / "_active_topic.txt").read_text().strip() == "dest-topic"
                assert not (spec_dir / "source-topic.txt").exists()
                assert not (spec_dir / "source-topic.worklog.jsonl").exists()
                assert not (spec_dir / "source-topic.no_context").exists()
                assert not (spec_dir / "dest-topic.no_context").exists()
                output = buffer.getvalue()
                assert "migrated worklog events: 2" in output
                assert "removed source no-context sentinel without propagation" in output
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_merge_dry_run_does_not_mutate_topic_files(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "source-topic.txt").write_text("topic: source-topic\n")
                (spec_dir / "dest-topic.txt").write_text("topic: dest-topic\n")
                (spec_dir / "source-topic.worklog.jsonl").write_text(
                    '{"text":"source","ts":"2026-07-11T12:00:01+00:00"}\n'
                )
                (spec_dir / "_active_topic.txt").write_text("source-topic\n")
                (spec_dir / ".session-topic-session-a.txt").write_text("source-topic\n")
                before = {path.name: path.read_text() for path in spec_dir.iterdir() if path.is_file()}

                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    assert (
                        agent_memory.main(
                            ["merge", "source-topic", "dest-topic", "--dry-run", "--workspace", str(workspace)]
                        )
                        == 0
                    )

                after = {path.name: path.read_text() for path in spec_dir.iterdir() if path.is_file()}
                assert after == before
                assert "dry-run merge: source-topic -> dest-topic" in buffer.getvalue()
                assert "would rewrite session binding" in buffer.getvalue()
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_merge_rejects_source_equal_dest(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "same-topic.txt").write_text("topic: same-topic\n")

                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        agent_memory.main(["merge", "same-topic", "same-topic", "--workspace", str(workspace)])
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_merge_rejects_missing_source(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()

                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        agent_memory.main(["merge", "missing-topic", "dest-topic", "--workspace", str(workspace)])
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_merge_rejects_generic_dest_topic(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "source-topic.txt").write_text("topic: source-topic\n")

                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        agent_memory.main(["merge", "source-topic", "current", "--workspace", str(workspace)])
            finally:
                agent_memory.SPEC_ROOT = old_spec_root

    def test_merge_creates_missing_dest_spec(self):
        import agent_memory

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as spec_root:
            old_spec_root = agent_memory.SPEC_ROOT
            agent_memory.SPEC_ROOT = Path(spec_root)
            try:
                workspace = Path(tmp).resolve()
                spec_dir = agent_memory.spec_dir_for(workspace)
                spec_dir.mkdir(parents=True)
                (spec_dir / "source-topic.txt").write_text("topic: source-topic\nsource details\n")

                with contextlib.redirect_stdout(io.StringIO()):
                    assert agent_memory.main(["merge", "source-topic", "new-dest", "--workspace", str(workspace)]) == 0

                dest_spec = (spec_dir / "new-dest.txt").read_text()
                assert dest_spec.startswith("topic: new-dest\n")
                assert "--- merged from source-topic on " in dest_spec
                assert "source details" in dest_spec
                assert not (spec_dir / "source-topic.txt").exists()
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


class TestAgentMemoryNote(unittest.TestCase):
    """WHEN recording structured insights with `,agent-memory note`."""

    def _roots(self, stack: contextlib.ExitStack):
        import agent_memory

        tmp = stack.enter_context(tempfile.TemporaryDirectory())
        spec_root = stack.enter_context(tempfile.TemporaryDirectory())
        mirror_root = stack.enter_context(tempfile.TemporaryDirectory())
        old_spec_root = agent_memory.SPEC_ROOT
        agent_memory.SPEC_ROOT = Path(spec_root)
        old_mirror = os.environ.get("AGENT_MEMORY_MIRROR_ROOT")
        os.environ["AGENT_MEMORY_MIRROR_ROOT"] = str(Path(mirror_root) / "mirror")

        def restore():
            agent_memory.SPEC_ROOT = old_spec_root
            if old_mirror is None:
                os.environ.pop("AGENT_MEMORY_MIRROR_ROOT", None)
            else:
                os.environ["AGENT_MEMORY_MIRROR_ROOT"] = old_mirror

        stack.callback(restore)
        return Path(tmp).resolve()

    def test_note_lands_in_topic_worklog_with_structured_fields(self):
        import agent_memory

        with contextlib.ExitStack() as stack:
            workspace = self._roots(stack)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = agent_memory.main(
                    [
                        "note",
                        "principle",
                        "prefer   spec_mirror over moving /tmp/specs",
                        "--ref",
                        "scripts/spec_mirror.py",
                        "--ref",
                        "docs/x.md",
                        "--workspace",
                        str(workspace),
                        "--topic",
                        "mirror-design",
                    ]
                )
            assert code == 0
            assert "note recorded: principle -> mirror-design" in out.getvalue()
            spec_dir = agent_memory.spec_dir_for(workspace)
            entries = [json.loads(line) for line in (spec_dir / "mirror-design.worklog.jsonl").read_text().splitlines()]
            assert len(entries) == 1
            entry = entries[0]
            assert entry["event"] == "note"
            assert entry["note_kind"] == "principle"
            # Whitespace is collapsed so the note stays one clean line.
            assert entry["text"] == "prefer spec_mirror over moving /tmp/specs"
            assert entry["refs"] == "scripts/spec_mirror.py,docs/x.md"

    def test_note_rejects_empty_text_and_unknown_kind(self):
        import agent_memory

        with contextlib.ExitStack() as stack:
            workspace = self._roots(stack)
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stdout(io.StringIO()):
                    agent_memory.main(["note", "principle", "   ", "--workspace", str(workspace)])
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    agent_memory.main(["note", "brainstorm", "text", "--workspace", str(workspace)])
            # `doc` is ingestion-only in the capsule taxonomy and not a note kind.
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    agent_memory.main(["note", "doc", "text", "--workspace", str(workspace)])

    def test_question_notes_are_marked_task_scoped(self):
        import agent_memory

        with contextlib.ExitStack() as stack:
            workspace = self._roots(stack)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = agent_memory.main(
                    ["note", "question", "mirror session buckets too?", "--workspace", str(workspace), "--topic", "t1"]
                )
            assert code == 0
            assert "not harvested" in out.getvalue()


class TestAgentMemoryMirror(unittest.TestCase):
    """WHEN named topics are mirrored to persistent state and restored."""

    def _roots(self, stack: contextlib.ExitStack):
        return TestAgentMemoryNote._roots(self, stack)

    def test_note_syncs_named_topic_to_mirror(self):
        import agent_memory
        import spec_mirror

        with contextlib.ExitStack() as stack:
            workspace = self._roots(stack)
            with contextlib.redirect_stdout(io.StringIO()):
                agent_memory.main(
                    ["note", "fact", "mirrored insight", "--workspace", str(workspace), "--topic", "keep-me"]
                )
            mirrored = spec_mirror.mirror_dir_for(workspace) / "keep-me.worklog.jsonl"
            assert mirrored.is_file()
            assert "mirrored insight" in mirrored.read_text()

    def test_status_restores_named_topic_after_spec_root_loss(self):
        import agent_memory
        import spec_mirror

        with contextlib.ExitStack() as stack:
            workspace = self._roots(stack)
            spec_dir = agent_memory.spec_dir_for(workspace)
            spec_dir.mkdir(parents=True)
            (spec_dir / "long-effort.txt").write_text("topic: long-effort\ntarget: survive reboots\n")
            (spec_dir / "_active_topic.txt").write_text("long-effort\n")
            synced = spec_mirror.sync_topic(spec_dir, workspace, "long-effort")
            assert "long-effort.txt" in synced

            # Simulate a macOS reboot: /tmp/specs is wiped.
            for path in sorted(spec_dir.iterdir()):
                path.unlink()

            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = agent_memory.main(["status", "--workspace", str(workspace)])
            assert code == 0
            assert (spec_dir / "long-effort.txt").read_text().startswith("topic: long-effort")
            # The restored active pointer re-selects the named topic.
            assert "selected_topic: long-effort" in out.getvalue()

    def test_session_fallback_topics_are_never_mirrored(self):
        import spec_mirror

        with contextlib.ExitStack() as stack:
            workspace = self._roots(stack)
            import agent_memory

            spec_dir = agent_memory.spec_dir_for(workspace)
            spec_dir.mkdir(parents=True)
            (spec_dir / "session-abc.worklog.jsonl").write_text("{}\n")
            (spec_dir / "current.txt").write_text("scratch\n")
            assert spec_mirror.sync_topic(spec_dir, workspace, "session-abc") == []
            assert spec_mirror.sync_topic(spec_dir, workspace, "current") == []

    def test_wipe_current_forgets_the_mirror_copy(self):
        """A wiped topic must not resurrect from the mirror on the next restore."""
        import agent_memory
        import spec_mirror

        with contextlib.ExitStack() as stack:
            workspace = self._roots(stack)
            spec_dir = agent_memory.spec_dir_for(workspace)
            spec_dir.mkdir(parents=True)
            (spec_dir / "doomed.txt").write_text("topic: doomed\n")
            (spec_dir / "_active_topic.txt").write_text("doomed\n")
            spec_mirror.sync_topic(spec_dir, workspace, "doomed")
            with contextlib.redirect_stdout(io.StringIO()):
                assert agent_memory.main(["wipe-current", "--workspace", str(workspace)]) == 0
            assert not (spec_dir / "doomed.txt").exists()
            restored = spec_mirror.restore_topics(spec_dir, workspace)
            assert "doomed.txt" not in restored
            assert not (spec_dir / "doomed.txt").exists()


if __name__ == "__main__":
    unittest.main()
