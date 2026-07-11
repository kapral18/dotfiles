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
AGENT_MEMORY = REPO / "scripts" / "agent_memory.py"
SPEC_ROOT = Path(
    os.environ.get("AGENT_MEMORY_SPEC_ROOT") or Path(os.environ.get("TMPDIR", "/tmp")) / "agent-hook-specs"
)


def hook_env(env: dict | None = None) -> dict:
    effective_env = dict(os.environ) if env is None else dict(env)
    effective_env["PYTHONPATH"] = f"{REPO / 'scripts'}{os.pathsep}{effective_env.get('PYTHONPATH', '')}"
    effective_env.setdefault("AGENT_MEMORY_SPEC_ROOT", str(SPEC_ROOT))
    return effective_env


def run_hook(name: str, payload: dict, env: dict | None = None) -> dict:
    result = subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=hook_env(env),
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
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "if args and args[0] == 'search':\n"
        "    query = sys.stdin.read() if '--query-stdin' in args else (args[1] if len(args) > 1 else '')\n"
        "    if os.environ.get('AI_KB_STUB_LOG'):\n"
        "        with open(os.environ['AI_KB_STUB_LOG'], 'a') as stream:\n"
        "            stream.write(json.dumps({'args': args, 'query': query}) + '\\n')\n"
        f"    sys.stdout.write({payload!r})\n"
        "    sys.exit(0)\n"
        "sys.exit(0)\n"
    )
    stub.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    return env


def bind_session_topic(spec_dir: Path, session_id: str, topic: str) -> None:
    (spec_dir / f".session-topic-{session_id}.txt").write_text(topic + "\n")


def flush_worklog(spec_dir: Path) -> None:
    import worklog_queue

    result = worklog_queue.flush_spec_dir(spec_dir)
    assert result.errors == 0
    assert result.pending == 0


def run_perturn_recall(tmp: str, payload: dict, env: dict) -> dict:
    """Run executable_perturn_recall.py under its deployed (unprefixed) name.

    perturn_recall.py does `from session_context import context_disabled`, an
    unprefixed sibling import that only resolves once both hook files sit
    alongside each other using their deployed names (chezmoi drops the
    `executable_` prefix on install) — mirrors the rename dance in
    test_warmstart_and_perturn_share_conversation_seen_state.
    """
    deployed_hooks = Path(tmp) / "deployed-hooks"
    if not deployed_hooks.exists():
        deployed_hooks.mkdir()
        for source, target in (
            ("hook_common.py", "hook_common.py"),
            ("executable_session_context.py", "session_context.py"),
            ("executable_perturn_recall.py", "perturn_recall.py"),
        ):
            (deployed_hooks / target).write_text((HOOKS / source).read_text())
    result = subprocess.run(
        [sys.executable, str(deployed_hooks / "perturn_recall.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=hook_env(env),
    )
    if result.returncode != 0:
        raise AssertionError(f"perturn_recall.py failed:\nSTDOUT={result.stdout}\nSTDERR={result.stderr}")
    return json.loads(result.stdout or "{}")


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
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            flush_worklog(spec_dir)
            worklog = spec_dir / "current.worklog.jsonl"
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
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            flush_worklog(spec_dir)
            worklog = spec_dir / "current.worklog.jsonl"
            assert len(worklog.read_text().splitlines()) == 200

    def test_session_context_emits_cursor_and_claude_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "hook-session", "hook-test")
            (spec_dir / "hook-test.txt").write_text("target: prove context injection\n")

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
                "session_id": "hook-session",
            }
            result = run_hook("executable_session_context.py", payload)

            assert "target: prove context injection" in result["additional_context"]
            assert result["hookSpecificOutput"]["hookEventName"] == "SessionStart"
            assert "target: prove context injection" in result["hookSpecificOutput"]["additionalContext"]

    def test_session_context_warms_resident_embedder_only_when_adapter_opts_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = root / "lib/,ai-kb/embed_client.py"
            client.parent.mkdir(parents=True)
            marker = root / "warm-count"
            client.write_text(
                "#!/usr/bin/env python3\n"
                "import os, pathlib\n"
                "path = pathlib.Path(os.environ['WARM_MARKER'])\n"
                "count = int(path.read_text()) if path.exists() else 0\n"
                "path.write_text(str(count + 1))\n"
            )
            payload = {
                "hook_event_name": "SessionStart",
                "workspace_roots": [tmp],
                "session_id": "warm-test",
            }
            base_env = {**os.environ, "HOME": tmp, "WARM_MARKER": str(marker)}

            run_hook("executable_session_context.py", payload, env=base_env)
            self.assertFalse(marker.exists())
            run_hook(
                "executable_session_context.py",
                payload,
                env={**base_env, "AI_EMBED_WARM": "1"},
            )
            self.assertEqual(marker.read_text(), "1")
            run_hook(
                "executable_session_context.py",
                {**payload, "warm_embedder": True},
                env=base_env,
            )
            self.assertEqual(marker.read_text(), "2")

    def test_perturn_recall_marks_ai_kb_embedding_connect_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / "bin"
            bindir.mkdir()
            marker = root / "connect-only"
            stub = bindir / ",ai-kb"
            stub.write_text(
                "#!/usr/bin/env python3\n"
                "import os, pathlib\n"
                "pathlib.Path(os.environ['CONNECT_ONLY_MARKER']).write_text("
                "os.environ.get('AI_EMBED_CONNECT_ONLY', ''))\n"
                "print('[]')\n"
            )
            stub.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                "CONNECT_ONLY_MARKER": str(marker),
            }
            result = run_perturn_recall(
                tmp,
                {
                    "hook_event_name": "UserPromptSubmit",
                    "workspace_roots": [tmp],
                    "session_id": "connect-only-test",
                    "prompt": "substantive prompt must not spawn an embed worker",
                },
                env,
            )

            self.assertEqual(result, {})
            self.assertEqual(marker.read_text(), "1")

    def test_session_context_offers_bucket_creation_on_default_branch_without_topics(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
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
            assert "Topic Buckets" in context
            assert "No existing topic buckets" in context
            assert "Agent should create a new bucket automatically" in context
            assert ",agent-memory select <new-topic> --create --session-id abc-123" in context
            assert ",ai-kb search" in context

    def test_session_context_offers_bucket_creation_when_runtime_has_no_session_id(self):
        with self.make_git_workspace("main") as tmp:
            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
            }
            context = run_hook("executable_session_context.py", payload)["additional_context"]

            assert "### Topic Buckets" in context
            assert "No existing topic buckets" in context
            assert ",agent-memory select <new-topic> --create --session-id <session-id>" in context
            assert "### Active Topic Spec" not in context

    def test_session_context_offers_existing_topic_buckets_without_loading_active_topic(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "_active_topic.txt").write_text("stale-homebrew\n")
            (spec_dir / "stale-homebrew.txt").write_text(
                "target: stale cask task\naction: continue old unrelated work\n"
            )
            (spec_dir / "agent-topic-buckets.txt").write_text(
                "target: improve agent topic selection\naction: design topic buckets\n"
            )

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
                "session_id": "bucket-probe",
            }
            context = run_hook("executable_session_context.py", payload)["additional_context"]

            assert "### Topic Buckets" in context
            assert "`stale-homebrew`" in context
            assert "`agent-topic-buckets`" in context
            assert "Agent should bind automatically when exactly one bucket clearly matches" in context
            assert "Ask the user only when multiple buckets plausibly match" in context
            assert "target: stale cask task" not in context
            assert "### Active Topic Spec" not in context

    def test_session_context_lists_buckets_newest_first_with_summary_and_age(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)

            old = spec_dir / "old-topic.txt"
            old.write_text("summary: explicit one-line label\ntarget: ignored when summary present\n")
            fresh = spec_dir / "fresh-topic.txt"
            fresh.write_text("plain notes without labelled lines\n")
            fresh_worklog = spec_dir / "fresh-topic.worklog.jsonl"
            fresh_worklog.write_text('{"line": "recent work"}\n')

            now = os.stat(spec_dir).st_mtime
            os.utime(old, (now - 7200, now - 7200))
            os.utime(fresh, (now - 7200, now - 7200))
            os.utime(fresh_worklog, (now - 300, now - 300))

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
                "session_id": "bucket-order-probe",
            }
            context = run_hook("executable_session_context.py", payload)["additional_context"]

            assert "Existing buckets (newest first by last update):" in context
            fresh_line = next(line for line in context.splitlines() if "`fresh-topic`" in line)
            old_line = next(line for line in context.splitlines() if "`old-topic`" in line)
            assert context.index(fresh_line) < context.index(old_line), "worklog mtime must outrank spec mtime"
            assert "explicit one-line label" in old_line
            assert "target=" not in old_line
            assert "no summary" in fresh_line
            assert "5m ago" in fresh_line
            assert "(2h ago)" in old_line

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
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            flush_worklog(spec_dir)

            assert not (spec_dir / "current.worklog.jsonl").exists()
            assert (spec_dir / "session-abc-123.worklog.jsonl").exists()

    def test_worklog_recorder_does_not_write_to_workspace_active_topic_for_unbound_session(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "_active_topic.txt").write_text("stale-homebrew\n")
            (spec_dir / "stale-homebrew.txt").write_text("target: stale cask task\n")

            payload = {
                "session_id": "abc-123",
                "hook_event_name": "postToolUse",
                "workspace_roots": [tmp],
                "tool_name": "Shell",
                "tool_input": {"command": "printf ok"},
                "tool_output": '{"stdout":"ok"}',
            }

            assert run_hook("executable_worklog_recorder.py", payload) == {}
            flush_worklog(spec_dir)

            assert not (spec_dir / "stale-homebrew.worklog.jsonl").exists()
            assert (spec_dir / "session-abc-123.worklog.jsonl").exists()

    def test_session_context_keeps_current_topic_on_feature_branch(self):
        with self.make_git_workspace("feature-memory") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
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

    def test_session_context_offers_bucket_creation_on_feature_branch_without_current_spec(self):
        with self.make_git_workspace("feature-memory") as tmp:
            payload = {
                "conversation_id": "abc-123",
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
            }
            context = run_hook("executable_session_context.py", payload)["additional_context"]

            assert "### Topic Buckets" in context
            assert "No existing topic buckets" in context
            assert "Agent should create a new bucket automatically" in context
            assert ",agent-memory select <new-topic> --create --session-id abc-123" in context
            assert "### Active Topic Spec" not in context

    def test_session_context_can_be_disabled_by_workspace_sentinel(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
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
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
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
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "review-session", "review-123")
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
                "session_id": "review-session",
            }
            result = run_hook("executable_session_context.py", payload)
            context = result["additional_context"]

            assert "target: PR owner/repo#123" in context
            assert "prior conclusion should not be injected" not in context
            assert "stale finding" not in context
            assert "verdict: Approve" not in context
            assert "Recent Hook Worklog" not in context
            assert "review clean-room mode" in context

    def test_session_context_bounds_oversized_review_spec_after_sanitizing(self):
        # Regression guard for memory-review-bypass follow-up (fix-review-context-bound):
        # is_review_topic()'s sanitized body must still be checked against
        # MAX_SPEC_CHARS. A review spec whose pre-conclusion body alone exceeds the
        # bound must NOT be injected verbatim just because it is "already sanitized" —
        # it must fall through to the same wholesale omission-with-pointer contract as
        # an oversized normal-topic spec, never a partial/truncated dump.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "review-big-session", "review-big")
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

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
                "session_id": "review-big-session",
            }
            result = run_hook("executable_session_context.py", payload)
            context = result["additional_context"]

            assert "Active topic spec omitted" in context
            assert "x" * 4000 not in context
            assert "prior conclusion should never appear" not in context
            assert "stale finding should never appear" not in context
            assert "verdict: Approve" not in context
            assert "Recent Hook Worklog" not in context
            assert len(context) < 3000

    def test_session_context_appends_aikb_reminder_with_named_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "memory-session", "memory-systems")
            (spec_dir / "memory-systems.txt").write_text("target: wire memory systems\n")

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
                "session_id": "memory-session",
            }
            context = run_hook("executable_session_context.py", payload)["additional_context"]

            assert "target: wire memory systems" in context
            assert "Durable Memory (,ai-kb)" in context
            assert ",ai-kb remember" in context
            assert "No Named Topic Active" not in context

    def test_session_context_warmstart_injects_relevant_learnings_for_named_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "warm-session", "memory-systems")
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
            payload = {"hook_event_name": "sessionStart", "workspace_roots": [tmp], "session_id": "warm-session"}
            context = run_hook("executable_session_context.py", payload, env=env)["additional_context"]

            assert "### Relevant Learnings (,ai-kb)" in context
            assert "Local capsule that should surface" in context
            assert "(gotcha)" in context
            assert "…" in context  # body truncated to the bound

    def test_session_context_warmstart_gates_out_unrelated_workspace_project_capsule(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "warm-gate-session", "memory-systems")
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
            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
                "session_id": "warm-gate-session",
            }
            context = run_hook("executable_session_context.py", payload, env=env)["additional_context"]

            assert "Foreign project capsule" not in context  # other-workspace project scope: gated out
            assert "Universal principle capsule" in context  # universal scope: allowed cross-project

    def test_agent_memory_select_binds_only_one_session_to_topic_bucket(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "stale-homebrew.txt").write_text("target: stale cask task\n")
            (spec_dir / "agent-topic-buckets.txt").write_text("target: improve agent topic selection\n")

            subprocess.run(
                [
                    sys.executable,
                    str(AGENT_MEMORY),
                    "select",
                    "agent-topic-buckets",
                    "--workspace",
                    workspace,
                    "--session-id",
                    "session-a",
                ],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                env=hook_env(),
                check=True,
            )

            selected = run_hook(
                "executable_session_context.py",
                {"hook_event_name": "sessionStart", "workspace_roots": [tmp], "session_id": "session-a"},
            )["additional_context"]
            other = run_hook(
                "executable_session_context.py",
                {"hook_event_name": "sessionStart", "workspace_roots": [tmp], "session_id": "session-b"},
            )["additional_context"]

            assert "target: improve agent topic selection" in selected
            assert "target: stale cask task" not in selected
            assert "### Topic Buckets" in other
            assert "target: improve agent topic selection" not in other

    def test_session_context_without_session_key_does_not_inject_current_on_default_branch(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "current.txt").write_text("target: stale shared current\n")
            (spec_dir / "focused-topic.txt").write_text("target: focused work\n")

            context = run_hook(
                "executable_session_context.py",
                {"hook_event_name": "sessionStart", "workspace_roots": [tmp]},
            )["additional_context"]

            assert "### Topic Buckets" in context
            assert "focused-topic" in context
            assert "target: stale shared current" not in context

    def test_session_context_warmstart_skipped_for_generic_and_session_topics(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
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
            REPO / "home" / "dot_gemini" / "settings.json",
            REPO / "home" / "dot_cursor" / "hooks.json",
        ]

        for file_path in files_to_check:
            content = file_path.read_text()
            assert "pr-anchor-gate" not in content
            assert "pulls/.*/(reviews|comments)" not in content

        assert not (
            REPO / "home" / "private_dot_copilot" / "exact_hooks" / "executable_copilot-pr-anchor-gate.sh"
        ).exists()
        assert not (HOOKS / "executable_gemini-pr-anchor-gate.sh").exists()

    def test_copilot_agent_memory_extension_maps_sdk_payloads(self):
        extension = REPO / "home/private_dot_copilot/exact_extensions/exact_agent-memory/readonly_extension.mjs"
        script = """
process.env.COPILOT_AGENT_MEMORY_EXTENSION_TEST = "1";
const mod = await import(process.argv[1]);
const sessionStart = mod.sessionStartPayload({
  sessionId: "copilot-session",
  workingDirectory: "/tmp/workspace",
  source: "new",
  initialPrompt: "hello"
});
const postTool = mod.postToolUsePayload({
  sessionId: "copilot-session",
  workingDirectory: "/tmp/workspace",
  toolName: "bash",
  toolArgs: { command: "printf ok" },
  toolResult: { textResultForLlm: "ok", resultType: "success" }
});
const failedTool = mod.postToolUseFailurePayload({
  sessionId: "copilot-session",
  workingDirectory: "/tmp/workspace",
  toolName: "bash",
  toolArgs: { command: "false" },
  error: "exit 1"
});
console.log(JSON.stringify({ sessionStart, postTool, failedTool }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(extension)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)

        assert payload["sessionStart"]["session_id"] == "copilot-session"
        assert payload["sessionStart"]["workspace_roots"] == ["/tmp/workspace"]
        assert payload["sessionStart"]["initial_prompt"] == "hello"
        assert payload["sessionStart"]["warm_embedder"] is True
        assert payload["postTool"]["tool_name"] == "bash"
        assert payload["postTool"]["tool_input"] == {"command": "printf ok"}
        assert payload["postTool"]["tool_output"] == "ok"
        assert payload["failedTool"]["hook_event_name"] == "postToolUseFailure"
        assert payload["failedTool"]["error_message"] == "exit 1"

    def test_warmstart_and_perturn_share_conversation_seen_state(self):
        with self.make_git_workspace("feature/conversation-seen") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "conversation-a", "conversation-memory")
            (spec_dir / "conversation-memory.txt").write_text("target: preserve recall dedupe across hooks\n")
            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "capsule-a",
                        "title": "Conversation-scoped capsule",
                        "body": "inject once",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                        "bm25_score": -10.0,
                        "cosine_score": 0.8,
                    }
                ],
            )

            warmstart = run_hook(
                "executable_session_context.py",
                {
                    "conversation_id": "conversation-a",
                    "hook_event_name": "sessionStart",
                    "workspace_roots": [tmp],
                },
                env=env,
            )["additional_context"]
            seen_path = spec_dir / ".recall-seen-conversation-a.json"
            deployed_hooks = Path(tmp) / "deployed-hooks"
            deployed_hooks.mkdir()
            for source, target in (
                ("hook_common.py", "hook_common.py"),
                ("executable_session_context.py", "session_context.py"),
                ("executable_perturn_recall.py", "perturn_recall.py"),
            ):
                (deployed_hooks / target).write_text((HOOKS / source).read_text())
            result = subprocess.run(
                [sys.executable, str(deployed_hooks / "perturn_recall.py")],
                input=json.dumps(
                    {
                        "conversation_id": "conversation-a",
                        "hook_event_name": "UserPromptSubmit",
                        "workspace_roots": [tmp],
                        "prompt": "preserve recall dedupe across hooks",
                    }
                ),
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env=hook_env(env),
            )
            assert result.returncode == 0, result.stderr
            perturn = json.loads(result.stdout or "{}")

            assert "Conversation-scoped capsule" in warmstart
            assert json.loads(seen_path.read_text()) == ["capsule-a"]
            assert perturn == {}

    def test_perturn_recall_hybrid_gate_uses_best_cosine_and_preserves_fused_order(self):
        # Hybrid rows are RRF+MMR fused-rank order, not best-cosine-first: row0 has no
        # cosine at all and a later row is the strongest hit. The gate must scan every
        # row for the best available cosine (not assume rows[0] holds it) to recall, and
        # the surviving rows must keep their original fused presentation order.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "capsule-first",
                        "title": "First fused row missing cosine",
                        "kind": "note",
                        "scope": "project",
                        "workspace_path": workspace,
                    },
                    {
                        "id": "capsule-second",
                        "title": "Second fused row strongest cosine",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                        "cosine_score": 0.9,
                    },
                    {
                        "id": "capsule-third",
                        "title": "Third fused row within floor",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                        "cosine_score": 0.8,
                    },
                    {
                        "id": "capsule-fourth",
                        "title": "Fourth fused row below floor",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                        "cosine_score": 0.5,
                    },
                ],
            )

            result = run_perturn_recall(
                tmp,
                {
                    "hook_event_name": "UserPromptSubmit",
                    "workspace_roots": [tmp],
                    "prompt": "recall guidance for this hybrid gate test",
                },
                env,
            )

            context = result["hookSpecificOutput"]["additionalContext"]
            first_pos = context.index("First fused row missing cosine")
            second_pos = context.index("Second fused row strongest cosine")
            third_pos = context.index("Third fused row within floor")
            assert first_pos < second_pos < third_pos
            assert "Fourth fused row below floor" not in context

    def test_perturn_recall_hybrid_gate_suppresses_below_absolute_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "capsule-a",
                        "title": "Weak hit one",
                        "kind": "note",
                        "scope": "project",
                        "workspace_path": workspace,
                        "cosine_score": 0.4,
                    },
                    {
                        "id": "capsule-b",
                        "title": "Weak hit two",
                        "kind": "note",
                        "scope": "project",
                        "workspace_path": workspace,
                        "cosine_score": 0.45,
                    },
                ],
            )

            result = run_perturn_recall(
                tmp,
                {
                    "hook_event_name": "UserPromptSubmit",
                    "workspace_roots": [tmp],
                    "prompt": "recall guidance for this hybrid gate test",
                },
                env,
            )

            assert result == {}

    def test_perturn_recall_hybrid_gate_suppresses_when_all_cosine_scores_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "capsule-a",
                        "title": "No cosine one",
                        "kind": "note",
                        "scope": "project",
                        "workspace_path": workspace,
                    },
                    {
                        "id": "capsule-b",
                        "title": "No cosine two",
                        "kind": "note",
                        "scope": "project",
                        "workspace_path": workspace,
                    },
                ],
            )

            result = run_perturn_recall(
                tmp,
                {
                    "hook_event_name": "UserPromptSubmit",
                    "workspace_roots": [tmp],
                    "prompt": "recall guidance for this hybrid gate test",
                },
                env,
            )

            assert result == {}

    def test_session_context_warmstart_unions_prior_seen_ids(self):
        # A resume/compact fires a second warm start in the same conversation.
        # The seen-file must load-union-save so capsules already recorded (by an
        # earlier warm start or the per-turn recall hook) are never dropped and
        # re-injected. Overwrite semantics would clobber the prior id.
        with self.make_git_workspace("feature/warm-union") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "warm-union", "union-memory")
            (spec_dir / "union-memory.txt").write_text("target: preserve recall dedupe across warm starts\n")
            seen_path = spec_dir / ".recall-seen-warm-union.json"
            seen_path.write_text(json.dumps(["capsule-prior"]))
            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "capsule-a",
                        "title": "Warm capsule that should surface",
                        "body": "inject once",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                        "bm25_score": -10.0,
                    }
                ],
            )
            run_hook(
                "executable_session_context.py",
                {
                    "conversation_id": "warm-union",
                    "hook_event_name": "sessionStart",
                    "workspace_roots": [tmp],
                },
                env=env,
            )

            assert json.loads(seen_path.read_text()) == ["capsule-a", "capsule-prior"]

    def test_opencode_worklog_adapter_passes_session_id(self):
        extension = REPO / "home/dot_config/opencode/plugins/agent-memory.ts"
        with tempfile.TemporaryDirectory() as tmp:
            hooks_dir = Path(tmp) / ".agents" / "hooks"
            hooks_dir.mkdir(parents=True)
            for name in ("session_context.py", "worklog_dispatcher.sh", "perturn_recall.py"):
                (hooks_dir / name).write_text("")

            script = """
const mod = await import(process.argv[1]);
const calls = [];
function shell(strings, ...values) {
  calls.push(values.map(String));
  return {
    quiet() { return this; },
    nothrow() { return Promise.resolve({ stdout: "{}", code: 0 }); }
  };
}
const hooks = await mod.AgentMemoryPlugin({ $: shell, directory: process.argv[2] });
await hooks["tool.execute.after"](
  { tool: "bash", sessionID: "opencode-session", callID: "call-a", args: {} },
  { title: "printf ok", output: "ok", metadata: {} }
);
console.log(calls[0][0]);
"""
            env = dict(os.environ)
            env["HOME"] = tmp
            env["NODE_NO_WARNINGS"] = "1"
            result = subprocess.run(
                ["node", "--input-type=module", "-e", script, str(extension), tmp],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            payload = json.loads(result.stdout)

            assert payload["session_id"] == "opencode-session"

    def test_pi_recall_uses_session_binding_and_persists_seen_capsules(self):
        extension = REPO / "home/dot_pi/agent/extensions/ai-kb-recall.ts"
        with tempfile.TemporaryDirectory() as tmp:
            spec_file = Path(tmp) / "pi-memory.txt"
            spec_file.write_text("target: persist pi recall dedupe\n")
            rows = [
                {
                    "id": "capsule-a",
                    "title": "Pi resume capsule",
                    "body": "inject once",
                    "kind": "gotcha",
                    "scope": "project",
                    "workspace_path": "/tmp/workspace",
                    "bm25_score": -10.0,
                }
            ]
            search_log = Path(tmp) / "search.jsonl"
            script = """
import { readFile } from "node:fs/promises";
const mod = await import(process.argv[1]);
const specFile = process.argv[2];
const workspace = "/tmp/workspace";
const sessionId = "pi/session";
const statusCalls = [];
const row = {
  id: "capsule-a",
  title: "Pi resume capsule",
  body: "inject once",
  kind: "gotcha",
  scope: "project",
  workspace_path: workspace,
  bm25_score: -10.0
};
function makePi() {
  const handlers = {};
  return {
    handlers,
    async exec(command, args) {
      if (command === ",ai-kb" && args[0] === "--help") return { code: 0, killed: false, stdout: "" };
      if (command === ",agent-memory") {
        statusCalls.push(args);
        return {
          code: 0,
          killed: false,
          stdout: JSON.stringify({
            workspace,
            selected_topic: "pi-memory",
            session_key: "pi-session",
            is_named_topic: true,
            spec_file: specFile,
            spec_exists: true
          })
        };
      }
      if (command === "cat" && args[0] === specFile) {
        return { code: 0, killed: false, stdout: "target: persist pi recall dedupe" };
      }
      if (command === "cat") return { code: 1, killed: false, stdout: "" };
      if (command === "python3" && args[0].endsWith("/lib/,ai-kb/embed_client.py") && args[1] === "ensure") {
        return { code: 0, killed: false, stdout: "{}" };
      }
      throw new Error(`unexpected exec: ${command} ${args.join(" ")}`);
    },
    on(event, handler) { handlers[event] = handler; }
  };
}
async function invokeFreshExtension() {
  const pi = makePi();
  await mod.default(pi);
  await pi.handlers.session_start({ type: "session_start", reason: "startup" }, {});
  return pi.handlers.before_agent_start(
    { prompt: "short" },
    {
      cwd: workspace,
      getContextUsage() { return null; },
      sessionManager: { getSessionId() { return sessionId; } }
    }
  );
}
const first = await invokeFreshExtension();
const second = await invokeFreshExtension();
let seen = [];
try {
  seen = JSON.parse(await readFile(`${specFile.slice(0, specFile.lastIndexOf("/"))}/.recall-seen-pi-session.json`, "utf8"));
} catch {}
console.log(JSON.stringify({ first, second, seen, statusCalls }));
"""
            env = make_aikb_stub(Path(tmp), rows)
            env["NODE_NO_WARNINGS"] = "1"
            env["AI_KB_STUB_LOG"] = str(search_log)
            result = subprocess.run(
                ["node", "--input-type=module", "-e", script, str(extension), str(spec_file)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            payload = json.loads(result.stdout)

            assert "Pi resume capsule" in payload["first"]["message"]["content"]
            assert payload.get("second") is None
            assert payload["seen"] == ["capsule-a"]
            searches = [json.loads(line) for line in search_log.read_text().splitlines()]
            expected_search = {
                "args": [
                    "search",
                    "--query-stdin",
                    "--limit",
                    "6",
                    "--mode",
                    "bm25",
                    "--workspace",
                    "/tmp/workspace",
                    "--json",
                ],
                "query": "target: persist pi recall dedupe",
            }
            assert searches == [expected_search, expected_search]
            assert payload["statusCalls"] == [
                ["status", "--json", "--workspace", "/tmp/workspace", "--session-id", "pi/session"],
                ["status", "--json", "--workspace", "/tmp/workspace", "--session-id", "pi/session"],
            ]

    def test_pi_recall_hybrid_gate_uses_best_cosine_and_preserves_fused_order(self):
        # Mirrors test_perturn_recall_hybrid_gate_uses_best_cosine_and_preserves_fused_order
        # (executable_perturn_recall.py): pi's applyRelevanceFloor must observe the same
        # per-turn hybrid contract — gate on the BEST cosine across all fused rows (not
        # rows[0]), and never reorder the surviving rows by cosine.
        extension = REPO / "home/dot_pi/agent/extensions/ai-kb-recall.ts"
        with tempfile.TemporaryDirectory() as tmp:
            # seenFileFor derives the recall-seen path from dirname(specFile), so route it
            # into this test's own tmpdir rather than a fixed path shared across test runs
            # (a fixed path would persist real .recall-seen-*.json state across invocations).
            spec_file = str(Path(tmp) / "hybrid-memory.txt")
            rows = [
                {
                    "id": "capsule-first",
                    "title": "First fused row missing cosine",
                    "kind": "note",
                    "scope": "project",
                    "workspace_path": "/tmp/workspace",
                },
                {
                    "id": "capsule-second",
                    "title": "Second fused row strongest cosine",
                    "kind": "gotcha",
                    "scope": "project",
                    "workspace_path": "/tmp/workspace",
                    "cosine_score": 0.9,
                },
                {
                    "id": "capsule-third",
                    "title": "Third fused row within floor",
                    "kind": "gotcha",
                    "scope": "project",
                    "workspace_path": "/tmp/workspace",
                    "cosine_score": 0.8,
                },
                {
                    "id": "capsule-fourth",
                    "title": "Fourth fused row below floor",
                    "kind": "gotcha",
                    "scope": "project",
                    "workspace_path": "/tmp/workspace",
                    "cosine_score": 0.5,
                },
            ]
            search_log = Path(tmp) / "search.jsonl"
            script = """
const mod = await import(process.argv[1]);
const specFile = process.argv[2];
const workspace = "/tmp/workspace";
const sessionId = "pi/hybrid-session";
const rows = [
  { id: "capsule-first", title: "First fused row missing cosine", kind: "note", scope: "project", workspace_path: workspace },
  { id: "capsule-second", title: "Second fused row strongest cosine", kind: "gotcha", scope: "project", workspace_path: workspace, cosine_score: 0.9 },
  { id: "capsule-third", title: "Third fused row within floor", kind: "gotcha", scope: "project", workspace_path: workspace, cosine_score: 0.8 },
  { id: "capsule-fourth", title: "Fourth fused row below floor", kind: "gotcha", scope: "project", workspace_path: workspace, cosine_score: 0.5 }
];
function makePi() {
  const handlers = {};
  return {
    handlers,
    async exec(command, args) {
      if (command === ",ai-kb" && args[0] === "--help") return { code: 0, killed: false, stdout: "" };
      if (command === ",agent-memory") {
        return {
          code: 0,
          killed: false,
          stdout: JSON.stringify({
            workspace,
            selected_topic: "current",
            session_key: "hybrid-session",
            is_named_topic: false,
            spec_file: specFile,
            spec_exists: false
          })
        };
      }
      if (command === "python3" && args[0].endsWith("/lib/,ai-kb/embed_client.py") && args[1] === "ensure") {
        return { code: 0, killed: false, stdout: "{}" };
      }
      if (command === "cat") return { code: 1, killed: false, stdout: "" };
      throw new Error(`unexpected exec: ${command} ${args.join(" ")}`);
    },
    on(event, handler) { handlers[event] = handler; }
  };
}
const pi = makePi();
await mod.default(pi);
await pi.handlers.session_start({ type: "session_start", reason: "startup" }, {});
const result = await pi.handlers.before_agent_start(
  { prompt: "recall guidance for this hybrid gate test" },
  {
    cwd: workspace,
    getContextUsage() { return null; },
    sessionManager: { getSessionId() { return sessionId; } }
  }
);
console.log(JSON.stringify({ result }));
"""
            env = make_aikb_stub(Path(tmp), rows)
            env["NODE_NO_WARNINGS"] = "1"
            env["AI_KB_STUB_LOG"] = str(search_log)
            result = subprocess.run(
                ["node", "--input-type=module", "-e", script, str(extension), spec_file],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            payload = json.loads(result.stdout)
            content = payload["result"]["message"]["content"]

            first_pos = content.index("First fused row missing cosine")
            second_pos = content.index("Second fused row strongest cosine")
            third_pos = content.index("Third fused row within floor")
            assert first_pos < second_pos < third_pos
            assert "Fourth fused row below floor" not in content
            searches = [json.loads(line) for line in search_log.read_text().splitlines()]
            assert len(searches) == 1
            assert searches[0]["query"] == "recall guidance for this hybrid gate test"
            assert searches[0]["args"] == [
                "search",
                "--query-stdin",
                "--limit",
                "6",
                "--mode",
                "hybrid",
                "--workspace",
                "/tmp/workspace",
                "--json",
            ]


if __name__ == "__main__":
    unittest.main()
