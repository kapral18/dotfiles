#!/usr/bin/env python3
"""Regression tests for shared agent hook scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / "home" / "exact_dot_agents" / "exact_hooks"
AGENT_MEMORY = REPO / "scripts" / "agent_memory.py"
# Default spec root is namespaced per test file so direct invocations
# (python3 scripts/tests/test_agent_hooks.py) and the parallel shard runner
# never share the mutable queue/worklog state with other test files. The shard
# runner additionally overrides AGENT_MEMORY_SPEC_ROOT per file.
SPEC_ROOT = Path(
    os.environ.get("AGENT_MEMORY_SPEC_ROOT") or Path(os.environ.get("TMPDIR", "/tmp")) / "agent-hook-specs-agent-hooks"
)
PARENT_SESSION_ENV = "COPILOT_AGENT_SESSION_ID"
KEEP_PARENT_SESSION_ENV = "AGENT_HOOK_TEST_KEEP_COPILOT_PARENT"
GH_STUB_LOGIN = "gh-stub-login"


def _make_gh_stub_dir() -> Path:
    """Stub `gh` so session_context's identity probe never hits the network in tests."""
    directory = Path(tempfile.mkdtemp(prefix="agent-hook-gh-stub-"))
    stub = directory / "gh"
    stub.write_text(f"#!/bin/sh\nprintf '%s\\n' '{GH_STUB_LOGIN}'\n")
    stub.chmod(0o755)
    return directory


GH_STUB_DIR = _make_gh_stub_dir()


def hook_env(env: dict | None = None) -> dict:
    effective_env = dict(os.environ) if env is None else dict(env)
    parent_session = effective_env.get(PARENT_SESSION_ENV, "")
    keep_parent_session = effective_env.pop(KEEP_PARENT_SESSION_ENV, "") == "1"
    effective_env.pop(PARENT_SESSION_ENV, None)
    if keep_parent_session and parent_session:
        effective_env[PARENT_SESSION_ENV] = parent_session
    effective_env["PYTHONPATH"] = f"{REPO / 'scripts'}{os.pathsep}{effective_env.get('PYTHONPATH', '')}"
    effective_env["PATH"] = f"{GH_STUB_DIR}{os.pathsep}{effective_env.get('PATH', '')}"
    effective_env.setdefault("AGENT_MEMORY_SPEC_ROOT", str(SPEC_ROOT))
    # Keep hook subprocesses away from the real persistent topic mirror.
    effective_env.setdefault("AGENT_MEMORY_MIRROR_ROOT", str(SPEC_ROOT / ".mirror-test"))
    effective_env.setdefault("XDG_CONFIG_HOME", str(SPEC_ROOT / ".xdg-config-test"))
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


def keep_parent_env(parent_session: str) -> dict:
    env = dict(os.environ)
    env[PARENT_SESSION_ENV] = parent_session
    env[KEEP_PARENT_SESSION_ENV] = "1"
    return env


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
        f"    rows = json.loads({payload!r})\n"
        "    if '--workspace-gate' in args:\n"
        "        # Mirror the real KB contract: --workspace-gate keeps only\n"
        "        # workspace-local or domain/universal capsules.\n"
        "        ws = args[args.index('--workspace') + 1] if '--workspace' in args else ''\n"
        "        rows = [r for r in rows if r.get('workspace_path') == ws or r.get('scope') in ('domain', 'universal')]\n"
        "    sys.stdout.write(json.dumps(rows))\n"
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


def worklog_entries(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def topic_paths_result(payload: dict, env: dict | None = None) -> dict:
    effective_env = hook_env(env)
    effective_env["PYTHONPATH"] = f"{HOOKS}{os.pathsep}{effective_env.get('PYTHONPATH', '')}"
    script = (
        "import json, sys\n"
        "from hook_common import topic_paths\n"
        "payload = json.loads(sys.stdin.read())\n"
        "workspace, topic, spec_path, worklog_path = topic_paths(payload)\n"
        "print(json.dumps({'workspace': str(workspace), 'topic': topic, 'spec': str(spec_path), 'worklog': str(worklog_path)}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=effective_env,
        check=True,
    )
    return json.loads(result.stdout)


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

    def test_antigravity_worklog_payload_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "conversationId": "agy-worklog",
                "workspacePaths": [tmp],
                "modelName": "gemini-3.7-flash-high",
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "printf ok"},
                },
                "error": "exit status 1",
            }
            env = hook_env()
            env["AGENT_HOOK_EVENT"] = "PostToolUse"
            env["AGENT_HOOK_OUTPUT"] = "antigravity"

            assert run_hook("executable_worklog_recorder.py", payload, env=env) == {}
            spec_dir = SPEC_ROOT / str(Path(tmp).resolve()).lstrip("/")
            flush_worklog(spec_dir)
            entry = worklog_entries(spec_dir / "current.worklog.jsonl")[-1]

            assert entry["event"] == "PostToolUse"
            assert entry["model"] == "gemini-3.7-flash-high"
            assert entry["tool_name"] == "run_command"
            assert entry["command"] == "printf ok"
            assert entry["error"] == "exit status 1"

    def test_worklog_recorder_keeps_bounded_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            worklog_path = spec_dir / "current.worklog.jsonl"

            import worklog_queue

            self.assertEqual(worklog_queue.DEFAULT_MAX_WORKLOG_LINES, 200)
            receipt = None
            for index in range(5):
                receipt = worklog_queue.enqueue(
                    spec_dir,
                    "bounded-tail-test",
                    "current",
                    worklog_path,
                    {
                        "ts": f"2026-01-01T00:00:0{index}+00:00",
                        "workspace": workspace,
                        "topic": "current",
                        "line": index,
                    },
                    start_worker=False,
                )
            assert receipt is not None
            worklog_queue.run_worker(
                receipt.queue_dir,
                config=worklog_queue.QueueConfig(max_worklog_lines=3, worker_idle_seconds=0),
            )

            worklog = spec_dir / "current.worklog.jsonl"
            assert [entry["line"] for entry in worklog_entries(worklog)] == [2, 3, 4]

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

    def test_antigravity_session_context_injects_only_on_first_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "agy-session", "agy-hook-test")
            (spec_dir / "agy-hook-test.txt").write_text("target: prove Antigravity context injection\n")
            env = hook_env()
            env["AGENT_HOOK_OUTPUT"] = "antigravity"
            env["AGENT_HOOK_EVENT"] = "PreInvocation"
            payload = {
                "conversationId": "agy-session",
                "workspacePaths": [tmp],
                "modelName": "gemini-3.7-flash-high",
                "invocationNum": 0,
                "initialNumSteps": 1,
            }

            first = run_hook("executable_session_context.py", payload, env=env)
            assert "target: prove Antigravity context injection" in first["injectSteps"][0]["ephemeralMessage"]
            assert run_hook("executable_session_context.py", {**payload, "invocationNum": 1}, env=env) == {}

    def test_session_context_prefixes_github_identity_from_gh_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "hook_event_name": "SessionStart",
                "workspace_roots": [tmp],
                "session_id": "gh-identity-test",
            }
            context = run_hook("executable_session_context.py", payload)["additional_context"]

            assert "### GitHub identity" in context
            assert GH_STUB_LOGIN in context

    def test_session_context_omits_github_identity_when_gh_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "hook_event_name": "SessionStart",
                "workspace_roots": [tmp],
                "session_id": "gh-identity-missing-test",
            }
            env = dict(os.environ)
            env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
            # hook_env prepends the gh stub dir; strip it back out so `gh` is absent.
            effective = hook_env(env)
            effective["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
            result = subprocess.run(
                [sys.executable, str(HOOKS / "executable_session_context.py")],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env=effective,
                check=True,
            )
            context = json.loads(result.stdout or "{}").get("additional_context", "")

            assert "### GitHub identity" not in context

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

    def test_worklog_recorder_uses_parent_selected_topic_for_copilot_subagent_writes(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            parent_session = "ff17ae29-3a1f-4409-bd73-1ee3ebbcb6c5"
            bind_session_topic(spec_dir, parent_session, "kibana-pr-review-277247")
            payload = {
                "session_id": "toolu_01EoFakeSubagentCall",
                "hook_event_name": "postToolUse",
                "workspace_roots": [tmp],
                "tool_name": "Shell",
                "tool_input": {"command": "printf subagent"},
                "tool_output": "ok",
            }

            assert run_hook("executable_worklog_recorder.py", payload, env=keep_parent_env(parent_session)) == {}
            flush_worklog(spec_dir)
            entries = worklog_entries(spec_dir / "kibana-pr-review-277247.worklog.jsonl")

            assert len(entries) == 1
            assert entries[0]["topic"] == "kibana-pr-review-277247"
            assert entries[0]["session_key"] == "toolu_01EoFakeSubagentCall"
            assert not (spec_dir / "session-toolu_01EoFakeSubagentCa.worklog.jsonl").exists()

    def test_worklog_recorder_uses_parent_fallback_bucket_for_unselected_copilot_subagent_on_default_branch(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            parent_session = "ff17ae29-3a1f-4409-bd73-1ee3ebbcb6c5"
            parent_bucket = f"session-{parent_session[:24]}"
            payload = {
                "session_id": "toolu_01EoFakeSubagentCall",
                "hook_event_name": "postToolUse",
                "workspace_roots": [tmp],
                "tool_name": "Shell",
                "tool_input": {"command": "printf fallback"},
                "tool_output": "ok",
            }

            assert run_hook("executable_worklog_recorder.py", payload, env=keep_parent_env(parent_session)) == {}
            flush_worklog(spec_dir)
            entries = worklog_entries(spec_dir / f"{parent_bucket}.worklog.jsonl")

            assert entries[0]["topic"] == parent_bucket
            assert entries[0]["session_key"] == "toolu_01EoFakeSubagentCall"
            assert not (spec_dir / "session-toolu_01EoFakeSubagentCa.worklog.jsonl").exists()

    def test_worklog_recorder_without_parent_env_keeps_payload_session_fallback(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            payload = {
                "session_id": "toolu_01EoFakeSubagentCall",
                "hook_event_name": "postToolUse",
                "workspace_roots": [tmp],
                "tool_name": "Shell",
                "tool_input": {"command": "printf legacy"},
                "tool_output": "ok",
            }

            assert run_hook("executable_worklog_recorder.py", payload) == {}
            flush_worklog(spec_dir)

            assert (spec_dir / "session-toolu_01EoFakeSubagentCa.worklog.jsonl").exists()

    def test_worklog_recorder_payload_selection_wins_over_parent_selection(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            parent_session = "ff17ae29-3a1f-4409-bd73-1ee3ebbcb6c5"
            payload_session = "toolu_01EoFakeSubagentCall"
            bind_session_topic(spec_dir, parent_session, "parent-topic")
            bind_session_topic(spec_dir, payload_session, "payload-topic")
            payload = {
                "session_id": payload_session,
                "hook_event_name": "postToolUse",
                "workspace_roots": [tmp],
                "tool_name": "Shell",
                "tool_input": {"command": "printf selected"},
                "tool_output": "ok",
            }

            assert run_hook("executable_worklog_recorder.py", payload, env=keep_parent_env(parent_session)) == {}
            flush_worklog(spec_dir)

            assert (spec_dir / "payload-topic.worklog.jsonl").exists()
            assert not (spec_dir / "parent-topic.worklog.jsonl").exists()

    def test_worklog_recorder_keeps_current_topic_on_feature_branch_without_selections(self):
        with self.make_git_workspace("feature/worklog-parent") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            parent_session = "ff17ae29-3a1f-4409-bd73-1ee3ebbcb6c5"
            payload = {
                "session_id": "toolu_01EoFakeSubagentCall",
                "hook_event_name": "postToolUse",
                "workspace_roots": [tmp],
                "tool_name": "Shell",
                "tool_input": {"command": "printf feature"},
                "tool_output": "ok",
            }

            assert run_hook("executable_worklog_recorder.py", payload, env=keep_parent_env(parent_session)) == {}
            flush_worklog(spec_dir)

            assert (spec_dir / "current.worklog.jsonl").exists()
            assert not (spec_dir / f"session-{parent_session[:24]}.worklog.jsonl").exists()

    def test_read_topic_paths_ignore_parent_session_env(self):
        with self.make_git_workspace("main") as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            parent_session = "ff17ae29-3a1f-4409-bd73-1ee3ebbcb6c5"
            bind_session_topic(spec_dir, parent_session, "parent-topic")
            payload = {
                "session_id": "toolu_01EoFakeSubagentCall",
                "hook_event_name": "SessionStart",
                "workspace_roots": [tmp],
            }

            without_parent = topic_paths_result(payload)
            with_parent = topic_paths_result(payload, env=keep_parent_env(parent_session))

            self.assertEqual(with_parent, without_parent)
            self.assertEqual(with_parent["topic"], "session-toolu_01EoFakeSubagentCa")

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
            assert (
                len(context) <= len((REPO / "home/dot_config/exact_tmux/agent_prompts/prefix.txt").read_text()) + 1800
            )

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
            # The reminder routes both KB directions through the smol operator and
            # forbids parent-inline CLI use outside the no-spawn fallback.
            assert "smol" in context
            assert "scribe mode" in context
            assert "Do not run `,ai-kb search`/`get`/`remember` inline" in context
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

    def test_session_context_restores_named_topic_from_mirror_after_spec_loss(self):
        """A wiped /tmp/specs (reboot) self-heals named topics from the persistent mirror."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as mirror_root:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            env = hook_env()
            env["AGENT_MEMORY_MIRROR_ROOT"] = str(Path(mirror_root) / "mirror")

            (spec_dir / "reboot-survivor.txt").write_text("target: survive the reboot\nsummary: durability probe\n")
            (spec_dir / "_active_topic.txt").write_text("reboot-survivor\n")
            import spec_mirror

            saved_mirror = os.environ.get("AGENT_MEMORY_MIRROR_ROOT")
            os.environ["AGENT_MEMORY_MIRROR_ROOT"] = env["AGENT_MEMORY_MIRROR_ROOT"]
            try:
                assert "reboot-survivor.txt" in spec_mirror.sync_topic(spec_dir, Path(workspace), "reboot-survivor")
            finally:
                if saved_mirror is None:
                    os.environ.pop("AGENT_MEMORY_MIRROR_ROOT", None)
                else:
                    os.environ["AGENT_MEMORY_MIRROR_ROOT"] = saved_mirror

            for path in sorted(spec_dir.iterdir()):
                path.unlink()

            payload = {"hook_event_name": "sessionStart", "workspace_roots": [tmp], "session_id": "mirror-restore"}
            context = run_hook("executable_session_context.py", payload, env=env)["additional_context"]

            assert (spec_dir / "reboot-survivor.txt").exists()
            assert "reboot-survivor" in context

    def test_hook_specific_output_shape_drops_top_level_context_key(self):
        """Codex rejects unknown top-level result keys; AGENT_HOOK_OUTPUT=hook_specific keeps only hookSpecificOutput."""
        with tempfile.TemporaryDirectory() as tmp:
            payload = {"hook_event_name": "SessionStart", "workspace_roots": [tmp], "session_id": "shape-probe"}
            env = hook_env()
            env["AGENT_HOOK_OUTPUT"] = "hook_specific"
            result = run_hook("executable_session_context.py", payload, env=env)
            assert "additional_context" not in result, sorted(result)
            assert result["hookSpecificOutput"]["hookEventName"] == "SessionStart"
            assert result["hookSpecificOutput"]["additionalContext"]

    def test_session_context_notices_harnesses_without_per_turn_recall(self):
        """Adapters that never request embedder warm-up (Cursor) get the recall notice; warm adapters do not."""
        with tempfile.TemporaryDirectory() as tmp:
            payload = {"hook_event_name": "sessionStart", "workspace_roots": [tmp], "session_id": "notice-probe"}
            env = hook_env()
            env.pop("AI_EMBED_WARM", None)
            cold = run_hook("executable_session_context.py", payload, env=env)["additional_context"]
            assert "Recall Notice" in cold
            assert ",agent-memory note" in cold

            warm = run_hook(
                "executable_session_context.py",
                {**payload, "session_id": "notice-probe-warm", "warm_embedder": True},
                env={**env, "AI_AGENT_DEPTH": "fast"},
            )["additional_context"]
            assert "Recall Notice" not in warm

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

    def test_cursor_and_codex_perturn_recall_wiring(self):
        # Cursor 2026.07.16+ supports additionalContext on beforeSubmitPrompt
        # (10k cap, verified from the installed bundle); the hook rides that
        # event and the sessionStart warm signal suppresses the Recall Notice.
        cursor = json.loads((REPO / "home" / "dot_cursor" / "hooks.json").read_text())
        before_submit = cursor["hooks"]["beforeSubmitPrompt"]
        assert any("perturn_recall.py" in hook["command"] for hook in before_submit)
        session_start = cursor["hooks"]["sessionStart"]
        assert any("AI_EMBED_WARM=1" in hook["command"] for hook in session_start)

        # Codex rejects unknown top-level output keys, so its perturn entry must
        # strip the dual-channel emit down to hookSpecificOutput.
        codex = (REPO / "home" / "dot_codex" / "hooks.json.tmpl").read_text()
        prompt_block = codex.split('"UserPromptSubmit"', 1)[1].split('"PostToolUse"', 1)[0]
        assert "perturn_recall.py" in prompt_block
        assert "AGENT_HOOK_OUTPUT=hook_specific" in prompt_block

        antigravity = json.loads((REPO / "home/dot_gemini/config/readonly_hooks.json").read_text())
        assert "session_context.py" in json.dumps(antigravity["agent-context"]["PreInvocation"])
        assert "premise_nudge.py" in json.dumps(antigravity["agent-context"]["PreInvocation"])
        assert "worklog_dispatcher.sh" in json.dumps(antigravity["agent-worklog"]["PostToolUse"])
        assert "gemini-git-gate.py" in json.dumps(antigravity["git-safety"]["PreToolUse"])
        assert "premise_nudge.py" in json.dumps(antigravity["git-safety"]["PreToolUse"])
        assert "AGENT_HOOK_OUTPUT=antigravity" in json.dumps(antigravity)

    def test_antigravity_worklog_dispatcher_returns_empty_json(self):
        dispatcher = REPO / "home/exact_dot_agents/exact_hooks/executable_worklog_dispatcher.sh"
        with tempfile.TemporaryDirectory() as tmp:
            hooks_dir = Path(tmp)
            target = hooks_dir / "worklog_dispatcher.sh"
            target.write_text(dispatcher.read_text())
            target.chmod(0o755)
            recorder = hooks_dir / "worklog_recorder.py"
            recorder.write_text("#!/usr/bin/env python3\nimport sys\nsys.stdin.read()\nprint('{}')\n")
            recorder.chmod(0o755)
            result = subprocess.run(
                [str(target)],
                input='{"toolCall":{"name":"run_command","args":{"CommandLine":"true"}}}',
                text=True,
                capture_output=True,
                env={**os.environ, "AGENT_HOOK_OUTPUT": "antigravity"},
                check=False,
            )

        assert result.returncode == 0
        assert json.loads(result.stdout) == {}

    def test_pr_anchor_verification_is_instruction_only(self):
        files_to_check = [
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

    def test_perturn_recall_stages_candidates_and_injects_pointer_only(self):
        # Staging contract: gate-passing rows go to the candidates file in full,
        # the injected context is only the smol pointer (never capsule bodies),
        # and the seen-file stays untouched — admissions are smol's write.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "capsule-a",
                        "title": "Staged capsule title sentinel",
                        "body": "staged capsule body sentinel",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                        "cosine_score": 0.8,
                    }
                ],
            )

            result = run_perturn_recall(
                tmp,
                {
                    "conversation_id": "stage-once",
                    "hook_event_name": "UserPromptSubmit",
                    "workspace_roots": [tmp],
                    "prompt": "recall guidance for this staging test",
                },
                env,
            )

            context = result["hookSpecificOutput"]["additionalContext"]
            candidates_path = spec_dir / ".recall-candidates-stage-once.json"
            assert "### ,ai-kb candidates staged" in context
            assert str(candidates_path) in context
            assert "k-ai-kb/references/smol-operator.md" in context
            # Harnesses with a fixed Task subagent set (cursor) route to a generic isolated
            # spawn on the memory-band model; harness-CLI one-shots are an external mechanism
            # and stay out of the flow.
            assert "spawn a generic isolated subagent" in context
            assert "never a harness-CLI one-shot" in context
            # The judge contract needs the session-state paths; the pointer must carry them.
            assert "Session state: " in context
            assert ".worklog.jsonl" in context
            assert "Staged capsule title sentinel" not in context
            assert "staged capsule body sentinel" not in context
            staged_rows = json.loads(candidates_path.read_text())
            assert [row["id"] for row in staged_rows] == ["capsule-a"]
            assert staged_rows[0]["body"] == "staged capsule body sentinel"
            assert json.loads((spec_dir / ".recall-staged-stage-once.json").read_text()) == ["capsule-a"]
            assert not (spec_dir / ".recall-seen-stage-once.json").exists()

    def test_perturn_recall_without_session_key_stages_nothing_and_injects_nothing(self):
        # Staging is session-scoped state: without a session key there is nothing to
        # stage against, so keyless payloads get no pointer and no capsule bodies —
        # recall degrades to the pull path instead of reintroducing unjudged injection.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "capsule-a",
                        "title": "Keyless capsule title sentinel",
                        "body": "keyless capsule body sentinel",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                        "cosine_score": 0.8,
                    }
                ],
            )

            result = run_perturn_recall(
                tmp,
                {
                    "hook_event_name": "UserPromptSubmit",
                    "workspace_roots": [tmp],
                    "prompt": "recall guidance for this staging test",
                },
                env,
            )

            assert result == {}
            if spec_dir.exists():
                assert not list(spec_dir.glob(".recall-candidates-*"))
                assert not list(spec_dir.glob(".recall-staged-*"))

    def test_perturn_recall_rewarm_fires_when_hybrid_rows_lack_cosine(self):
        # Search runs connect-only, so a cold resident embedder returns rows
        # without cosine_score; the absolute gate then suppresses staging.
        # The hook must fire a detached embed_client ensure so the NEXT turn
        # regains the dense lane, while this turn still stages/injects nothing.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "capsule-a",
                        "title": "Cold embedder capsule",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                    }
                ],
            )
            fake_home = Path(tmp) / "home"
            marker = fake_home / "rewarm-marker.txt"
            client = fake_home / "lib" / ",ai-kb" / "embed_client.py"
            client.parent.mkdir(parents=True)
            client.write_text(
                f"import pathlib, sys\npathlib.Path({str(marker)!r}).write_text(' '.join(sys.argv[1:]))\n"
            )
            env["HOME"] = str(fake_home)

            result = run_perturn_recall(
                tmp,
                {
                    "conversation_id": "cold-embedder",
                    "hook_event_name": "UserPromptSubmit",
                    "workspace_roots": [tmp],
                    "prompt": "recall guidance for this staging test",
                },
                env,
            )

            assert result == {}
            if spec_dir.exists():
                assert not list(spec_dir.glob(".recall-candidates-cold-embedder*"))
            deadline = time.time() + 5
            while not marker.exists() and time.time() < deadline:
                time.sleep(0.05)
            assert marker.exists(), "detached embed_client ensure never ran"
            assert marker.read_text() == "ensure"

            # Warm phase: rows that carry cosine_score must NOT fire the
            # re-warm — an always-fire regression would spawn embed_client on
            # every turn. The wait window is one-sided (a very slow spawn could
            # land after it) but the spawn lands in milliseconds in practice.
            marker.unlink()
            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "capsule-warm",
                        "title": "Warm embedder capsule",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                        "cosine_score": 0.8,
                    }
                ],
            )
            env["HOME"] = str(fake_home)
            run_perturn_recall(
                tmp,
                {
                    "conversation_id": "warm-embedder",
                    "hook_event_name": "UserPromptSubmit",
                    "workspace_roots": [tmp],
                    "prompt": "recall guidance for this staging test",
                },
                env,
            )
            assert list(spec_dir.glob(".recall-candidates-warm-embedder*")), "warm search never staged"
            time.sleep(0.8)
            assert not marker.exists(), "re-warm fired despite warm cosine rows"

    def test_perturn_recall_does_not_repoint_already_staged_candidates(self):
        # The staged ledger dedups the pointer: an identical candidate set on the
        # next prompt injects nothing, while a genuinely new capsule id re-points.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            payload = {
                "conversation_id": "repoint-guard",
                "hook_event_name": "UserPromptSubmit",
                "workspace_roots": [tmp],
                "prompt": "recall guidance for this staging test",
            }
            row_a = {
                "id": "capsule-a",
                "title": "First staged capsule",
                "kind": "gotcha",
                "scope": "project",
                "workspace_path": workspace,
                "cosine_score": 0.8,
            }
            env = make_aikb_stub(Path(tmp), [row_a])

            first = run_perturn_recall(tmp, payload, env)
            second = run_perturn_recall(tmp, payload, env)
            env = make_aikb_stub(Path(tmp), [row_a, {**row_a, "id": "capsule-b", "title": "New staged capsule"}])
            third = run_perturn_recall(tmp, payload, env)

            assert "### ,ai-kb candidates staged" in first["hookSpecificOutput"]["additionalContext"]
            assert second == {}
            assert "### ,ai-kb candidates staged" in third["hookSpecificOutput"]["additionalContext"]
            staged_rows = json.loads((spec_dir / ".recall-candidates-repoint-guard.json").read_text())
            assert [row["id"] for row in staged_rows] == ["capsule-a", "capsule-b"]
            assert json.loads((spec_dir / ".recall-staged-repoint-guard.json").read_text()) == [
                "capsule-a",
                "capsule-b",
            ]

    def test_perturn_recall_hybrid_gate_uses_best_cosine_and_preserves_fused_order(self):
        # Hybrid rows are RRF+MMR fused-rank order, not best-cosine-first: row0 has no
        # cosine at all and a later row is the strongest hit. The gate must scan every
        # row for the best available cosine (not assume rows[0] holds it), and the
        # staged candidate set must keep the original fused presentation order.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
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
                    "conversation_id": "fused-order",
                    "hook_event_name": "UserPromptSubmit",
                    "workspace_roots": [tmp],
                    "prompt": "recall guidance for this hybrid gate test",
                },
                env,
            )

            context = result["hookSpecificOutput"]["additionalContext"]
            assert "### ,ai-kb candidates staged" in context
            assert "fused row" not in context
            staged_rows = json.loads((spec_dir / ".recall-candidates-fused-order.json").read_text())
            assert [row["id"] for row in staged_rows] == ["capsule-first", "capsule-second", "capsule-third"]

    def test_perturn_recall_hybrid_gate_suppresses_below_absolute_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
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
                    "conversation_id": "gate-suppress",
                    "hook_event_name": "UserPromptSubmit",
                    "workspace_roots": [tmp],
                    "prompt": "recall guidance for this hybrid gate test",
                },
                env,
            )

            assert result == {}
            assert not (spec_dir / ".recall-candidates-gate-suppress.json").exists()

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

    def test_pi_recall_injects_shared_session_context_once_per_session_start(self):
        extension = REPO / "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts"
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            hooks_dir = home / ".agents" / "hooks"
            hooks_dir.mkdir(parents=True)
            payload_log = Path(tmp) / "session-context-payloads.jsonl"
            session_context = hooks_dir / "session_context.py"
            session_context.write_text(
                f"""#!/usr/bin/env python3
import json
import sys

payload = json.load(sys.stdin)
with open({str(payload_log)!r}, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(payload, sort_keys=True) + "\\n")
context = "SHARED_SESSION_CONTEXT::" + payload["session_id"] + "::" + payload["initial_prompt"]
print(json.dumps({{"additional_context": context}}))
"""
            )
            session_context.chmod(0o755)
            spec_file = Path(tmp) / "current.txt"
            script = """
const mod = await import(process.argv[1]);
const workspace = process.argv[2];
let specFile = process.argv[3];
let selectedTopic = "current";
const handlers = {};
const pi = {
  async exec(command, args) {
    if (command === ",ai-kb" && args[0] === "--help") return { code: 0, killed: false, stdout: "" };
    if (command === ",agent-memory") {
      return {
        code: 0,
        killed: false,
        stdout: JSON.stringify({
          workspace,
          selected_topic: selectedTopic,
          session_key: "pi-session-context",
          is_named_topic: false,
          spec_file: specFile,
          spec_exists: false
        })
      };
    }
    if (command === "python3" && args[0].endsWith("/lib/,ai-kb/embed_client.py")) {
      return { code: 0, killed: false, stdout: "{}" };
    }
    if (command === "cat" && args[0].endsWith("/tmux/agent_prompts/prefix.txt")) {
      return { code: 0, killed: false, stdout: "VERIFICATION_PREFIX" };
    }
    if (command === "cat") return { code: 1, killed: false, stdout: "" };
    throw new Error(`unexpected exec: ${command} ${args.join(" ")}`);
  },
  on(event, handler) { handlers[event] = handler; }
};
let contextPercent = 5;
const ctx = {
  cwd: workspace,
  getContextUsage() { return { percent: contextPercent }; },
  sessionManager: { getSessionId() { return "pi-session-context"; } }
};
await mod.default(pi);
await handlers.session_start({ type: "session_start", reason: "startup" }, ctx);
const first = await handlers.before_agent_start({ prompt: "first" }, ctx);
const second = await handlers.before_agent_start({ prompt: "next" }, ctx);
contextPercent = 26;
const grown = await handlers.before_agent_start({ prompt: "growth" }, ctx);
selectedTopic = "next-topic";
specFile = specFile.replace("current.txt", "next-topic.txt");
const topicChanged = await handlers.before_agent_start({ prompt: "topic shift" }, ctx);
await handlers.session_compact({ type: "session_compact" }, ctx);
contextPercent = null;
const compacted = await handlers.before_agent_start({ prompt: "compacted" }, ctx);
contextPercent = 7;
const afterCompactionBaseline = await handlers.before_agent_start({ prompt: "baseline" }, ctx);
contextPercent = 28;
const grownAfterCompaction = await handlers.before_agent_start({ prompt: "regrowth" }, ctx);
await handlers.session_start({ type: "session_start", reason: "resume" }, ctx);
const resumed = await handlers.before_agent_start({ prompt: "resume" }, ctx);
console.log(JSON.stringify({
  first,
  second: second ?? null,
  grown,
  topicChanged,
  compacted,
  afterCompactionBaseline: afterCompactionBaseline ?? null,
  grownAfterCompaction,
  resumed
}));
"""
            env = dict(os.environ)
            env["HOME"] = str(home)
            env["AI_AGENT_DEPTH"] = "balanced"
            env["NODE_NO_WARNINGS"] = "1"
            result = subprocess.run(
                ["node", "--input-type=module", "-e", script, str(extension), str(Path(tmp).resolve()), str(spec_file)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            payload = json.loads(result.stdout)

            assert "SHARED_SESSION_CONTEXT::pi-session-context" in payload["first"]["message"]["content"]
            assert payload["second"] is None
            assert "VERIFICATION_PREFIX" in payload["grown"]["message"]["content"]
            assert (
                "SHARED_SESSION_CONTEXT::pi-session-context::topic shift"
                in payload["topicChanged"]["message"]["content"]
            )
            assert "VERIFICATION_PREFIX" in payload["compacted"]["message"]["content"]
            assert payload["afterCompactionBaseline"] is None
            assert "VERIFICATION_PREFIX" in payload["grownAfterCompaction"]["message"]["content"]
            assert "SHARED_SESSION_CONTEXT::pi-session-context" in payload["resumed"]["message"]["content"]
            hook_payloads = [json.loads(line) for line in payload_log.read_text().splitlines()]
            assert hook_payloads == [
                {
                    "cwd": str(Path(tmp).resolve()),
                    "hook_event_name": "sessionStart",
                    "initial_prompt": "first",
                    "session_id": "pi-session-context",
                    "source": "pi",
                    "warm_embedder": True,
                    "workspace_roots": [str(Path(tmp).resolve())],
                },
                {
                    "cwd": str(Path(tmp).resolve()),
                    "hook_event_name": "sessionStart",
                    "initial_prompt": "topic shift",
                    "session_id": "pi-session-context",
                    "source": "pi",
                    "warm_embedder": True,
                    "workspace_roots": [str(Path(tmp).resolve())],
                },
                {
                    "cwd": str(Path(tmp).resolve()),
                    "hook_event_name": "sessionStart",
                    "initial_prompt": "resume",
                    "session_id": "pi-session-context",
                    "source": "pi",
                    "warm_embedder": True,
                    "workspace_roots": [str(Path(tmp).resolve())],
                },
            ]

    def test_runtime_extensions_enable_search_tools_and_gate_git_mutation(self):
        extension_cases = [REPO / "home/dot_pi/agent/exact_extensions/runtime-parity.ts"]
        for extension in extension_cases:
            with self.subTest(extension=str(extension.relative_to(REPO))):
                with tempfile.TemporaryDirectory() as tmp:
                    home = Path(tmp) / "home"
                    hooks_dir = home / ".agents" / "hooks"
                    hooks_dir.mkdir(parents=True)
                    gate = hooks_dir / "gemini-git-gate.py"
                    gate.write_text((HOOKS / "executable_gemini-git-gate.py").read_text())
                    gate.chmod(0o755)
                    script = """
const mod = await import(process.argv[1]);
function makePi() {
  const handlers = {};
  let active = ["read", "bash", "edit", "write"];
  return {
    handlers,
    getActiveTools() { return [...active]; },
    setActiveTools(tools) { active = [...tools]; },
    on(event, handler) { handlers[event] = handler; }
  };
}
const pi = makePi();
await mod.default(pi);
await pi.handlers.session_start({ type: "session_start", reason: "startup" }, {});
const ctxWithoutUi = { hasUI: false };
const ctxAllowing = { hasUI: true, ui: { async confirm() { return true; } } };
const ctxHanging = { hasUI: true, ui: { async confirm() { return new Promise(() => {}); } } };
const heredocCommand = [
  "node - <<'NODE'",
  "const root = `${process.env.HOME}/tmp/demo`;",
  "const lockPath = `${root}/.git/index.lock`;",
  "const body = JSON.stringify({ path: lockPath, message: 'not a git command' });",
  "await fetch(`${root}/api/items`, { method: 'PUT', body });",
  "NODE",
].join("\\n");
const safe = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "safe", toolName: "bash", input: { command: "git config push.default" } },
  ctxWithoutUi
);
const blocked = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "blocked", toolName: "bash", input: { command: "git push" } },
  ctxWithoutUi
);
const caseVariantBlocked = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "case-variant", toolName: "bash", input: { command: "GIT push" } },
  ctxWithoutUi
);
const aliasBlocked = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "alias", toolName: "bash", input: { command: "git -c alias.p=push p" } },
  ctxWithoutUi
);
const concatenatedBlocked = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "concatenated", toolName: "bash", input: { command: 'g""it push' } },
  ctxWithoutUi
);
const escapedBlocked = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "escaped", toolName: "bash", input: { command: String.raw`g\\it commit` } },
  ctxWithoutUi
);
const expandedBlocked = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "expanded", toolName: "bash", input: { command: String.raw`g$'it' push` } },
  ctxWithoutUi
);
const inertGitText = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "inert", toolName: "bash", input: { command: "rg 'git push' home" } },
  ctxWithoutUi
);
const gitLockProbe = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "lock-probe", toolName: "bash", input: { command: "stat .git/FETCH_HEAD.lock .git/index.lock" } },
  ctxWithoutUi
);
const heredocAllowed = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "heredoc", toolName: "bash", input: { command: heredocCommand } },
  ctxWithoutUi
);

const approved = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "approved", toolName: "bash", input: { command: "git commit -m ok" } },
  ctxAllowing
);
const hangingConfirmBlocked = await pi.handlers.tool_call(
  { type: "tool_call", toolCallId: "hanging-confirm", toolName: "bash", input: { command: "git commit -m timeout" } },
  ctxHanging
);
process.argv.push("--tools", "read,bash");
const explicit = makePi();
await mod.default(explicit);
await explicit.handlers.session_start({ type: "session_start", reason: "startup" }, {});
console.log(JSON.stringify({
  active: pi.getActiveTools(),
  safe: safe ?? null,
  blocked,
  caseVariantBlocked,
  aliasBlocked,
  concatenatedBlocked,
  escapedBlocked,
  expandedBlocked,
  inertGitText: inertGitText ?? null,
  gitLockProbe: gitLockProbe ?? null,
  heredocAllowed: heredocAllowed ?? null,
  approved: approved ?? null,
  hangingConfirmBlocked,
  explicit: explicit.getActiveTools()
}));
"""
                    env = dict(os.environ)
                    env["HOME"] = str(home)
                    env["NODE_NO_WARNINGS"] = "1"
                    env["AGENT_RUNTIME_CONFIRM_TIMEOUT_MS"] = "20"
                    result = subprocess.run(
                        ["node", "--input-type=module", "-e", script, str(extension)],
                        cwd=str(REPO),
                        capture_output=True,
                        text=True,
                        env=env,
                        check=True,
                    )
                    payload = json.loads(result.stdout)

                    assert payload["active"] == ["read", "bash", "edit", "write", "grep", "find", "ls"]
                    assert payload["safe"] is None
                    assert payload["blocked"]["block"] is True
                    assert "explicit approval" in payload["blocked"]["reason"]
                    assert payload["caseVariantBlocked"]["block"] is True
                    assert payload["aliasBlocked"]["block"] is True
                    assert payload["concatenatedBlocked"]["block"] is True
                    assert payload["escapedBlocked"]["block"] is True
                    assert payload["expandedBlocked"]["block"] is True
                    assert payload["inertGitText"] is None
                    assert payload["gitLockProbe"] is None
                    assert payload["heredocAllowed"] is None
                    assert payload["approved"] is None
                    assert payload["hangingConfirmBlocked"]["block"] is True
                    assert payload["explicit"] == ["read", "bash", "edit", "write"]

        omp_extension = REPO / "home/dot_omp/private_agent/extensions/runtime-parity.ts"
        omp_text = omp_extension.read_text()
        for snippet in (
            'const SEARCH_TOOLS = ["grep", "find", "ls"]',
            'const TOOL_SELECTION_FLAGS = ["--tools", "-t", "--exclude-tools", "-xt", "--no-tools", "-nt", "--no-builtin-tools", "-nbt"]',
            "function hasExplicitToolSelection(argv: string[]): boolean",
            "function enableSearchTools(pi: ExtensionAPI): void",
            "function runGitGate(command: string): Promise<GateProcessResult>",
            "async function confirmWithTimeout(request: Promise<boolean>): Promise<boolean>",
            'pi.on("session_start", () => {',
            'pi.on("tool_call", async (event, ctx) => {',
        ):
            assert snippet in omp_text
        assert "the OMP safety gate refused this command" in omp_text

    def test_pi_recall_uses_session_binding_and_persists_seen_capsules(self):
        extension = REPO / "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts"
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
  await pi.handlers.session_start(
    { type: "session_start", reason: "startup" },
    { sessionManager: { getSessionId() { return sessionId; } } }
  );
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
            env["HOME"] = str(Path(tmp) / "home")
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
                    "--workspace-gate",
                    "--json",
                ],
                "query": "target: persist pi recall dedupe",
            }
            assert searches == [expected_search, expected_search]
            assert payload["statusCalls"] == [
                ["status", "--json", "--workspace", "/tmp/workspace", "--session-id", "pi/session"],
                ["status", "--json", "--workspace", "/tmp/workspace", "--session-id", "pi/session"],
            ]

    def test_pi_recall_keyless_session_stages_nothing_at_runtime(self):
        extension = REPO / "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts"
        with tempfile.TemporaryDirectory() as tmp:
            spec_file = Path(tmp) / "pi-memory.txt"
            spec_file.write_text("target: persist pi recall dedupe\n")
            rows = [
                {
                    "id": "capsule-a",
                    "title": "Pi resume capsule",
                    "body": "must never stage without a session key",
                    "kind": "gotcha",
                    "scope": "project",
                    "workspace_path": "/tmp/workspace",
                    "cosine_score": 0.99,
                }
            ]
            search_log = Path(tmp) / "search.jsonl"
            script = """
const mod = await import(process.argv[1]);
const specFile = process.argv[2];
const workspace = "/tmp/workspace";
const sessionId = "pi/session";
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
            selected_topic: "",
            session_key: "",
            is_named_topic: false,
            spec_file: specFile,
            spec_exists: true
          })
        };
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
const pi = makePi();
await mod.default(pi);
await pi.handlers.session_start(
  { type: "session_start", reason: "startup" },
  { sessionManager: { getSessionId() { return sessionId; } } }
);
const result = await pi.handlers.before_agent_start(
  { prompt: "cursor task band gate rewrites the subagent model param, how do I launch a pinned verifier lane?" },
  {
    cwd: workspace,
    getContextUsage() { return null; },
    sessionManager: { getSessionId() { return sessionId; } }
  }
);
console.log(JSON.stringify({ result: result ?? null }));
"""
            env = make_aikb_stub(Path(tmp), rows)
            env["NODE_NO_WARNINGS"] = "1"
            env["AI_KB_STUB_LOG"] = str(search_log)
            env["HOME"] = str(Path(tmp) / "home")
            result = subprocess.run(
                ["node", "--input-type=module", "-e", script, str(extension), str(spec_file)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            payload = json.loads(result.stdout)

            # A keyless session must inject nothing, stage nothing, and never search.
            assert payload["result"] is None
            assert sorted(Path(tmp).glob(".recall-*")) == []
            assert not search_log.exists()

    def test_pi_recall_injects_probe_budget_directive_from_fresh_ad_hoc_ledger(self):
        # The probe-budget consumer must fire through the real extension, not just
        # exist as source text: seed a fresh ad-hoc ledger next to the spec file and
        # assert the before_agent_start message carries the note; a stale ledger must
        # inject nothing (freshness cap keeps other sessions' failures out).
        from datetime import datetime, timezone

        extension = REPO / "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts"
        script = """
const mod = await import(process.argv[1]);
const specFile = process.argv[2];
const workspace = "/tmp/workspace";
const sessionId = "pi/session-budget";
const handlers = {};
const pi = {
  async exec(command, args) {
    if (command === ",ai-kb" && args[0] === "--help") return { code: 0, killed: false, stdout: "" };
    if (command === ",agent-memory") {
      return {
        code: 0,
        killed: false,
        stdout: JSON.stringify({
          workspace,
          selected_topic: "budget-topic",
          session_key: "pi-session-budget",
          is_named_topic: false,
          spec_file: specFile,
          spec_exists: false
        })
      };
    }
    if (command === "cat") return { code: 1, killed: false, stdout: "" };
    if (command === "python3" && args[0].endsWith("/lib/,ai-kb/embed_client.py") && args[1] === "ensure") {
      return { code: 0, killed: false, stdout: "{}" };
    }
    throw new Error(`unexpected exec: ${command} ${args.join(" ")}`);
  },
  on(event, handler) { handlers[event] = handler; }
};
await mod.default(pi);
await handlers.session_start(
  { type: "session_start", reason: "startup" },
  { sessionManager: { getSessionId() { return sessionId; } } }
);
const result = await handlers.before_agent_start(
  { prompt: "why did you choose sqlite here?" },
  {
    cwd: workspace,
    getContextUsage() { return null; },
    sessionManager: { getSessionId() { return sessionId; } }
  }
);
console.log(JSON.stringify({ content: result?.message?.content ?? null }));
"""
        for label, ts, expect_fire in (
            ("fresh", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), True),
            ("stale", "2026-01-01T00:00:00Z", False),
        ):
            with self.subTest(ledger=label), tempfile.TemporaryDirectory() as tmp:
                spec_file = Path(tmp) / "budget-topic.txt"
                ledger = Path(tmp) / "ad-hoc.probe-ledger.jsonl"
                ledger.write_text(
                    "\n".join(json.dumps({"ts": ts, "result": "fail", "summary": "s"}) for _ in range(3)) + "\n",
                    encoding="utf-8",
                )
                env = make_aikb_stub(Path(tmp), [])
                env["NODE_NO_WARNINGS"] = "1"
                env["HOME"] = str(Path(tmp) / "home")
                result = subprocess.run(
                    ["node", "--input-type=module", "-e", script, str(extension), str(spec_file)],
                    cwd=str(REPO),
                    capture_output=True,
                    text=True,
                    env=env,
                    check=True,
                )
                content = json.loads(result.stdout)["content"]
                if expect_fire:
                    assert content is not None and "probe-budget-exhausted" in content
                    assert "Probe-budget hint" in content
                else:
                    assert content is None

    def test_pi_recall_staging_contract_matches_perturn_recall(self):
        import re

        pi_extension = (REPO / "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts").read_text()
        omp_extension = (REPO / "home/dot_omp/private_agent/extensions/ai-kb-recall.ts").read_text()
        hook = (HOOKS / "executable_perturn_recall.py").read_text()

        # Candidate-filter parity: the cosine gate/floor and workspace gate are unchanged.
        for extension in (pi_extension, omp_extension):
            assert "if (!cosines.length) return []" in extension
            assert "const topCosine = Math.max(...cosines)" in extension
            assert "return c == null || c >= cosineFloor" in extension
            assert '"--mode",\n    mode,' in extension
            assert '"--workspace-gate",' in extension

        assert "if not cosines:\n        return []" in hook
        assert "top = max(cosines)" in hook
        assert "not isinstance(cosine, (int, float)) or cosine >= floor" in hook
        assert '"--mode",\n                "hybrid",' in hook
        assert '"--workspace-gate",' in hook

        # Staging parity: same state-file names, per-turn path stages instead of
        # injecting bodies, and the pointer tokens carry identical values.
        assert '.recall-candidates-{session_key_value}.json"' in hook
        assert '.recall-staged-{session_key_value}.json"' in hook
        for extension in (pi_extension, omp_extension):
            assert ".recall-candidates-${sessionId}.json" in extension
            assert ".recall-staged-${sessionId}.json" in extension
            assert "stageCandidates(rows, status.spec_file, status.session_key)" in extension
            assert "Relevant Learnings for this request" not in extension

        # Keyless-session guard parity: both sides stage nothing without a session key.
        assert 'pointer = stage_candidates(rows, seen, spec_path, key) if key and rows else ""' in hook
        for extension in (pi_extension, omp_extension):
            assert "return status.session_key ? status : null" in extension

        # Cold-embedder re-warm parity: all-None cosine rows fire a detached
        # embed_client ensure on both sides (runtime-proven for the hook by
        # test_perturn_recall_rewarm_fires_when_hybrid_rows_lack_cosine).
        # Pin the exact trigger predicate and spawn shape: the TS branch has no
        # runtime test, so an inverted/weakened predicate or a dropped error
        # listener must fail here instead of shipping silently.
        assert "rewarm_embedder()" in hook
        for extension in (pi_extension, omp_extension):
            assert (
                'if (mode === "hybrid" && rows.length && !rows.some((row) => typeof row.cosine_score === "number")) {'
                in extension
            )
            assert "rewarmEmbedder()" in extension
            # Scope the spawn-shape pins to the rewarmEmbedder body: the same
            # strings appear in other detached-spawn helpers, so a file-wide
            # pin would keep passing with the rewarm listener deleted.
            rewarm_fn = extension[
                extension.index("function rewarmEmbedder") : extension.index(
                    "\n}", extension.index("function rewarmEmbedder")
                )
            ]
            assert 'spawn("python3", [client, "ensure"], { detached: true, stdio: "ignore" })' in rewarm_fn
            # spawn ENOENT emits an async "error" event; without a listener it
            # crashes the host process (verified by live node probe).
            assert 'child.on("error", () => {})' in rewarm_fn
            assert "child.unref()" in rewarm_fn

        def token(text: str, name: str) -> str:
            match = re.search(rf'{name} = "([^"]+)"', text)
            assert match, f"{name} missing"
            return match.group(1)

        for name in ("SMOL_CONTRACT_PATH", "STAGING_HEADER"):
            hook_value = token(hook, name)
            assert token(pi_extension, f"const {name}") == hook_value
            assert token(omp_extension, f"const {name}") == hook_value


class BandGateTests(unittest.TestCase):
    """The pre-tool-use gate that pins a delegated agent to its category's band.

    Each harness gets its own request and response shape, all four verified against the running
    binaries, so the adapters are tested against a fixed projection rather than the deployed one:
    these assertions are about the wire contract, not about today's model picks.
    """

    PROJECTION = {
        "harnesses": {
            "claude_code": {
                "agents": {
                    "Explore": {"band": "cheap", "model": "claude-fable-5-1", "alias": "fable"},
                    "searcher": {"band": "cheap", "model": "claude-haiku-4-5", "alias": "haiku"},
                    "reviewer": {"band": "max", "model": "claude-opus-5", "alias": "opus"},
                }
            },
            "cursor": {"agents": {"bugbot": {"band": "max", "model": "claude-opus-5-high"}}},
            "codex": {"agents": {"explorer": {"band": "cheap", "model": "gpt-5.4", "effort": "high"}}},
            "copilot": {
                "agents": {
                    "explore": {
                        "band": "cheap",
                        "model": "gpt-5.3-codex",
                        "effort": "high",
                    }
                }
            },
            "pi": {
                "agents": {
                    "explorer": {"band": "standard", "model": "openrouter/openai/gpt-5.5:xhigh", "effort": "xhigh"},
                    "worker": {
                        "band": "mechanical",
                        "model": "openrouter/deepseek/deepseek-v4-flash:xhigh",
                        "effort": "xhigh",
                    },
                    "adversarial-verifier": {
                        "band": "counter",
                        "model": "openrouter/anthropic/claude-sonnet-4.6:xhigh",
                        "effort": "xhigh",
                    },
                }
            },
            "gemini": {"agents": {"codebase_investigator": {"band": "cheap", "model": "gemini-3.7-flash"}}},
        }
    }

    def gate(
        self,
        harness: str,
        payload: dict,
        projection: dict | None = None,
        override: dict[str, str] | None = None,
    ) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            bands = Path(tmp) / "agent-bands.v1.json"
            bands.write_text(json.dumps(self.PROJECTION if projection is None else projection))
            excluded_env = {
                "AGENT_BAND_MODEL_OVERRIDE",
                "AGENT_BAND_EFFORT_OVERRIDE",
                "AGENT_BAND_SCHEMA_HARNESS",
                "AGENT_BAND_MODEL_FORMAT",
            }
            env = {key: value for key, value in os.environ.items() if key not in excluded_env}
            env.update(override or {})
            env["AGENT_BAND_HARNESS"] = harness
            env["AGENT_BANDS_FILE"] = str(bands)
            result = subprocess.run(
                [sys.executable, str(HOOKS / "executable_band_gate.py")],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout or "{}")

    def test_codex_rewrites_spawn_agent_model_and_effort_with_an_allow_decision(self):
        # codex 0.146.0 drops updatedInput unless permissionDecision is allow.
        answer = self.gate(
            "codex",
            {"tool_name": "spawn_agent", "tool_input": {"agent_type": "explorer", "message": "go"}},
        )
        specific = answer["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "allow")
        self.assertEqual(specific["updatedInput"]["model"], "gpt-5.4")
        self.assertEqual(specific["updatedInput"]["reasoning_effort"], "high")
        self.assertEqual(specific["updatedInput"]["message"], "go")

    def test_cursor_echoes_the_whole_input_because_updated_input_replaces_it(self):
        answer = self.gate(
            "cursor",
            {"tool_name": "Task", "tool_input": {"subagent_type": "bugbot", "prompt": "p", "model": "cheap-thing"}},
        )
        self.assertEqual(
            answer["updated_input"],
            {"subagent_type": "bugbot", "prompt": "p", "model": "claude-opus-5-high"},
        )

    def test_claude_clamps_a_cross_family_override_to_the_band_alias(self):
        answer = self.gate(
            "claude_code",
            {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore", "model": "opus"}},
        )
        self.assertEqual(answer["hookSpecificOutput"]["updatedInput"]["model"], "fable")

    def test_deployed_claude_projection_clamps_fable_category_agents(self):
        projection = json.loads((REPO / "home/dot_config/ai/readonly_agent-bands.v1.json").read_text(encoding="utf-8"))
        answer = self.gate(
            "claude_code",
            {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore", "model": "opus"}},
            projection=projection,
        )
        self.assertEqual(answer["hookSpecificOutput"]["updatedInput"]["model"], "fable")

    def test_claude_leaves_an_unqualified_call_alone_so_the_profile_keeps_the_exact_id(self):
        # All three bands share the `fable` alias, so writing it unasked would promote the cheap
        # band to whatever ANTHROPIC_DEFAULT_FABLE_MODEL resolves to.
        self.assertEqual(
            self.gate("claude_code", {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore"}}),
            {},
        )

    def test_claude_clamps_an_upward_alias_escape_on_the_lookup_category(self):
        # `sonnet` is not the lookup category's alias, so it is an escape upward even though it is not a
        # different family. Comparing rank, not equality, is what catches it: an `asked == alias`
        # early return only guarded the exact alias and let every promotion above it through.
        for asked in ("sonnet", "opus"):
            with self.subTest(asked=asked):
                answer = self.gate(
                    "claude_code",
                    {"tool_name": "Agent", "tool_input": {"subagent_type": "searcher", "model": asked}},
                )
                self.assertEqual(answer["hookSpecificOutput"]["updatedInput"]["model"], "haiku")

    def test_claude_leaves_a_downward_alias_choice_alone(self):
        # Bands are cost ceilings, not floors: a caller asking for something cheaper than the band
        # is not the leak this gate exists to close.
        self.assertEqual(
            self.gate(
                "claude_code",
                {"tool_name": "Agent", "tool_input": {"subagent_type": "reviewer", "model": "haiku"}},
            ),
            {},
        )

    def test_claude_cannot_separate_bands_sharing_an_alias_and_says_so(self):
        # All three bands (claude-fable-5-1) project to `fable`, so an
        # explicit `model: "fable"` on a cheap-band agent is indistinguishable from its own
        # band and passes. This is the Agent-tool alias schema limit, not a gate bug; the profile
        # frontmatter's exact id is what holds the band whenever no `model` argument is passed.
        self.assertEqual(
            self.gate(
                "claude_code",
                {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore", "model": "fable"}},
            ),
            {},
        )

    def test_copilot_answers_with_modified_args(self):
        answer = self.gate(
            "copilot",
            {"tool_name": "task", "tool_input": {"agent_type": "explore", "prompt": "p"}},
        )
        self.assertEqual(
            answer["modifiedArgs"],
            {
                "agent_type": "explore",
                "prompt": "p",
                "model": "gpt-5.3-codex",
                "reasoning_effort": "high",
            },
        )

    def test_copilot_tool_args_arrive_as_a_json_string(self):
        # copilot 1.0.77 serialises toolArgs before handing them to the extension hook; without
        # parsing them the gate silently no-ops and the caller's model wins.
        answer = self.gate(
            "copilot",
            {
                "tool_name": "task",
                "tool_input": json.dumps({"agent_type": "explore", "mode": "sync", "model": "claude-opus-5"}),
            },
        )
        self.assertEqual(
            answer["modifiedArgs"],
            {
                "agent_type": "explore",
                "mode": "sync",
                "model": "gpt-5.3-codex",
                "reasoning_effort": "high",
            },
        )

    def test_schema_harness_reads_backend_projection_but_keeps_frontend_shape(self):
        answer = self.gate(
            "codex",
            {"tool_name": "spawn_agent", "tool_input": {"agent_type": "explore", "message": "go"}},
            override={"AGENT_BAND_SCHEMA_HARNESS": "copilot"},
        )
        specific = answer["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "allow")
        self.assertEqual(
            specific["updatedInput"],
            {
                "agent_type": "explore",
                "message": "go",
                "model": "gpt-5.3-codex",
                "reasoning_effort": "high",
            },
        )

    def test_openrouter_schema_rows_normalize_to_preset_wire_models(self):
        answer = self.gate(
            "codex",
            {"tool_name": "spawn_agent", "tool_input": {"agent_type": "explorer", "message": "go"}},
            override={"AGENT_BAND_SCHEMA_HARNESS": "pi", "AGENT_BAND_MODEL_FORMAT": "openrouter-preset"},
        )
        updated = answer["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["model"], "openai/gpt-5.5@preset/effort-xhigh")
        self.assertEqual(updated["reasoning_effort"], "xhigh")

    def test_claude_openrouter_schema_forces_backend_alias_on_unqualified_calls(self):
        answer = self.gate(
            "claude_code",
            {"tool_name": "Agent", "tool_input": {"subagent_type": "explorer", "prompt": "p"}},
            override={"AGENT_BAND_SCHEMA_HARNESS": "pi", "AGENT_BAND_MODEL_FORMAT": "openrouter-preset"},
        )
        self.assertEqual(answer["hookSpecificOutput"]["updatedInput"]["model"], "fable")

        verifier = self.gate(
            "claude_code",
            {"tool_name": "Agent", "tool_input": {"subagent_type": "adversarial-verifier", "prompt": "p"}},
            override={"AGENT_BAND_SCHEMA_HARNESS": "pi", "AGENT_BAND_MODEL_FORMAT": "openrouter-preset"},
        )
        self.assertEqual(verifier["hookSpecificOutput"]["updatedInput"]["model"], "sonnet")

    def test_a_single_model_route_overrides_every_band_including_unbound_agents(self):
        # A BYOK launcher sells one provider model; a band id that is not that model reaches the
        # provider as its own wire model, so the override has to cover agents with no binding too.
        override = {"AGENT_BAND_MODEL_OVERRIDE": "openai/gpt-5.2", "AGENT_BAND_EFFORT_OVERRIDE": "high"}
        copilot = self.gate(
            "copilot",
            {"tool_name": "task", "tool_input": {"agent_type": "not-in-any-band", "prompt": "p"}},
            override=override,
        )
        self.assertEqual(copilot["modifiedArgs"]["model"], "openai/gpt-5.2")
        self.assertEqual(copilot["modifiedArgs"]["reasoning_effort"], "high")

        codex = self.gate(
            "codex",
            {"tool_name": "spawn_agent", "tool_input": {"agent_type": "explorer", "message": "go"}},
            override=override,
        )
        updated = codex["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["model"], "openai/gpt-5.2")
        self.assertEqual(updated["reasoning_effort"], "high")

    def test_claude_ignores_the_override_because_its_agent_tool_takes_only_family_aliases(self):
        # The alias resolves through ANTHROPIC_DEFAULT_*_MODEL, which the launcher already points
        # at the route's model; writing a raw id here fails updatedInput schema validation.
        answer = self.gate(
            "claude_code",
            {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore", "model": "opus"}},
            override={"AGENT_BAND_MODEL_OVERRIDE": "openai/gpt-5.2"},
        )
        self.assertEqual(answer["hookSpecificOutput"]["updatedInput"]["model"], "fable")

    def test_gemini_has_no_adapter_because_invoke_agent_takes_no_model(self):
        self.assertEqual(
            self.gate(
                "gemini",
                {"tool_name": "invoke_agent", "tool_input": {"agent_name": "codebase_investigator", "prompt": "p"}},
            ),
            {},
        )

    def test_the_gate_fails_open_rather_than_blocking_a_delegation(self):
        cases = [
            ("codex", {"tool_name": "Read", "tool_input": {"path": "x"}}, None),
            ("codex", {"tool_name": "spawn_agent", "tool_input": {"agent_type": "not-bound"}}, None),
            ("codex", {"tool_name": "spawn_agent", "tool_input": {"message": "no agent named"}}, None),
            ("nosuchharness", {"tool_name": "spawn_agent", "tool_input": {"agent_type": "explorer"}}, None),
            ("codex", {"tool_name": "spawn_agent", "tool_input": {"agent_type": "explorer"}}, {}),
        ]
        for harness, payload, projection in cases:
            with self.subTest(harness=harness, payload=payload, projection=projection):
                self.assertEqual(self.gate(harness, payload, projection), {})

    def test_a_task_name_is_not_mistaken_for_the_role(self):
        # Codex's spawn_agent carries both; task_name is a free-text label.
        answer = self.gate(
            "codex",
            {"tool_name": "spawn_agent", "tool_input": {"task_name": "bugbot", "agent_type": "explorer"}},
        )
        self.assertEqual(answer["hookSpecificOutput"]["updatedInput"]["model"], "gpt-5.4")


if __name__ == "__main__":
    unittest.main()
