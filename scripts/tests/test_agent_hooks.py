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


def make_agent_memory_stub(directory: Path) -> Path:
    """A fake `,agent-memory` whose `select` writes the binding file the way the real CLI does."""
    bindir = directory / "agent-memory-stub-bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / ",agent-memory"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "if args[:1] != ['select']:\n"
        "    sys.exit(2)\n"
        "topic = args[1]\n"
        "key = args[args.index('--session-id') + 1]\n"
        "workspace = args[args.index('--workspace') + 1]\n"
        "if topic == 'current':\n"
        "    print('Refusing to select the generic topic', file=sys.stderr); sys.exit(1)\n"
        "spec_dir = Path(os.environ['AGENT_MEMORY_SPEC_ROOT']) / workspace.lstrip('/')\n"
        "spec_dir.mkdir(parents=True, exist_ok=True)\n"
        "(spec_dir / f'.session-topic-{key}.txt').write_text(topic + '\\n')\n"
        "(spec_dir / 'stub-select.log').write_text(' '.join(args) + '\\n')\n"
        "print('session topic:', topic)\n"
    )
    stub.chmod(0o755)
    return bindir


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
            ("reinforcement.py", "reinforcement.py"),
            ("correction_detector.py", "correction_detector.py"),
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
                len(context) <= len((REPO / "home/dot_config/exact_tmux/agent_prompts/prefix.txt").read_text()) + 2000
            )

    def test_session_context_no_longer_injects_the_prefix_at_session_start(self):
        # The SOP is fresh at the top of a new session; the excerpt only earns its place
        # after context growth or a compaction (see the reinforcement tests below).
        with tempfile.TemporaryDirectory() as tmp:
            config_home = Path(tmp) / "config"
            prefix_path = config_home / "tmux" / "agent_prompts" / "prefix.txt"
            prefix_path.parent.mkdir(parents=True)
            prefix_path.write_text("PREFIX_SENTINEL_START")
            env = dict(os.environ)
            env["XDG_CONFIG_HOME"] = str(config_home)

            result = run_hook(
                "executable_session_context.py",
                {"hook_event_name": "sessionStart", "workspace_roots": [tmp]},
                env=env,
            )

            assert "PREFIX_SENTINEL_START" not in result["additional_context"]
            assert "Apply the discipline above" not in result["additional_context"]

    @staticmethod
    def _write_claude_transcript(path: Path, context_tokens: int) -> None:
        rows = [
            {"type": "user", "message": {"role": "user", "content": "hello"}},
            {
                "type": "assistant",
                "message": {
                    "model": "claude-fable-5-1",
                    "usage": {
                        "input_tokens": 2,
                        "cache_read_input_tokens": context_tokens - 2,
                        "cache_creation_input_tokens": 0,
                        "output_tokens": 10,
                    },
                },
            },
        ]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    def _reinforcement_env(self, tmp: str, **extra: str) -> dict:
        config_home = Path(tmp) / "config"
        prefix_path = config_home / "tmux" / "agent_prompts" / "prefix.txt"
        prefix_path.parent.mkdir(parents=True, exist_ok=True)
        prefix_path.write_text("PREFIX_SENTINEL_REINFORCE")
        env = make_aikb_stub(Path(tmp), [])
        env["XDG_CONFIG_HOME"] = str(config_home)
        env.update(extra)
        return env

    def _bucket_workspace(self, branch: str):
        tmp = self.make_git_workspace(branch)
        workspace = str(Path(tmp.name).resolve())
        spec_dir = SPEC_ROOT / workspace.lstrip("/")
        spec_dir.mkdir(parents=True, exist_ok=True)
        for name in (".session-topic-bind-test.txt", "stub-select.log"):
            (spec_dir / name).unlink(missing_ok=True)
        (spec_dir / "alpha.txt").write_text("topic: alpha\nsummary: older thread\n")
        (spec_dir / "beta.txt").write_text("topic: beta\nsummary: newest thread\n")
        old = time.time() - 3600
        os.utime(spec_dir / "alpha.txt", (old, old))
        env = dict(hook_env())
        env["PATH"] = f"{make_agent_memory_stub(Path(tmp.name))}{os.pathsep}{env['PATH']}"
        return tmp, workspace, spec_dir, env

    def test_feature_branch_session_auto_binds_to_the_newest_bucket(self):
        tmp, workspace, spec_dir, env = self._bucket_workspace("feature/reinforce")
        with tmp:
            payload = {"hook_event_name": "SessionStart", "session_id": "bind-test", "workspace_roots": [workspace]}
            result = run_hook("executable_session_context.py", payload, env=env)
            context = result["additional_context"]
            self.assertIn("Auto-bound to `beta`", context)
            self.assertIn("newest thread", context)
            self.assertNotIn("### Topic Buckets", context)
            self.assertEqual((spec_dir / ".session-topic-bind-test.txt").read_text().strip(), "beta")
            self.assertIn("select beta --session-id bind-test", (spec_dir / "stub-select.log").read_text())

    def test_feature_branch_with_only_current_keeps_the_default_topic(self):
        tmp = self.make_git_workspace("feature/plain")
        with tmp:
            workspace = str(Path(tmp.name).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "current.txt").write_text("target: the working thread\n")
            env = dict(hook_env())
            env["PATH"] = f"{make_agent_memory_stub(Path(tmp.name))}{os.pathsep}{env['PATH']}"
            payload = {"hook_event_name": "SessionStart", "session_id": "plain-test", "workspace_roots": [workspace]}
            context = run_hook("executable_session_context.py", payload, env=env)["additional_context"]
            self.assertIn("the working thread", context)
            self.assertNotIn("Auto-bound", context)
            self.assertFalse((spec_dir / "stub-select.log").exists())

    def test_default_branch_keeps_the_picker_and_explains_the_bind(self):
        tmp, workspace, spec_dir, env = self._bucket_workspace("main")
        with tmp:
            payload = {"hook_event_name": "SessionStart", "session_id": "bind-test", "workspace_roots": [workspace]}
            context = run_hook("executable_session_context.py", payload, env=env)["additional_context"]
            self.assertIn("### Topic Buckets", context)
            self.assertIn("`current` is refused here", context)
            self.assertIn("same tool batch as your first investigation command", context)
            self.assertIn("binds automatically", context)
            self.assertNotIn("Auto-bound", context)
            self.assertFalse((spec_dir / ".session-topic-bind-test.txt").exists())

    def test_default_branch_prompt_naming_a_bucket_binds_and_defers_the_pointer(self):
        tmp, workspace, spec_dir, env = self._bucket_workspace("main")
        with tmp:
            env.update(
                make_aikb_stub(
                    Path(tmp.name),
                    [{"id": "cap-1", "title": "T", "body": "B", "scope": "universal", "cosine_score": 0.9}],
                )
            )
            env["PATH"] = f"{make_agent_memory_stub(Path(tmp.name))}{os.pathsep}{env['PATH']}"
            base = {"hook_event_name": "UserPromptSubmit", "session_id": "bind-test", "workspace_roots": [workspace]}
            # Unbound on main: candidates are staged for the pull path, but no judge pointer yet.
            first = run_perturn_recall(
                tmp.name, {**base, "prompt": "look into the retry storm in the queue worker"}, env
            )
            self.assertNotIn("candidates staged", json.dumps(first))
            candidates = spec_dir / ".recall-candidates-bind-test.json"
            self.assertEqual([row["id"] for row in json.loads(candidates.read_text())], ["cap-1"])
            # Naming the bucket binds without a model turn and the pointer fires with the binding.
            second = run_perturn_recall(tmp.name, {**base, "prompt": f"continue please {spec_dir / 'alpha.txt'}"}, env)
            context = second["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Bound this session to `alpha`", context)
            self.assertEqual((spec_dir / ".session-topic-bind-test.txt").read_text().strip(), "alpha")
            self.assertIn("candidates staged", context)
            third = run_perturn_recall(tmp.name, {**base, "prompt": "continue the queue investigation"}, env)
            self.assertNotIn("candidates staged", json.dumps(third))

    def _gate(self, payload: dict, env: dict | None = None) -> dict:
        return run_hook("executable_read_gate.py", payload, env=env)

    @staticmethod
    def _record_result(
        transcript: Path,
        tool_use_id: str,
        *,
        stdout: str | None = None,
        file_content: str | None = None,
        persisted: bool = False,
        codex_output: str | None = None,
    ) -> None:
        """Append a transcript row in the shape Claude Code (or Codex) writes for a tool result."""
        if codex_output is not None:
            row = {
                "type": "response_item",
                "payload": {"type": "function_call_output", "call_id": tool_use_id, "output": codex_output},
            }
        else:
            result: dict = (
                {"stdout": stdout or "", "stderr": ""}
                if file_content is None
                else {"type": "text", "file": {"filePath": "x", "content": file_content}}
            )
            if persisted:
                result["persistedOutputPath"] = "/tmp/preview.txt"
            text = "<persisted-output>\npreview" if persisted else (stdout if file_content is None else file_content)
            row = {
                "type": "user",
                "toolUseResult": result,
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": text}],
                },
            }
        with transcript.open("a") as handle:
            handle.write(json.dumps(row) + "\n")

    def _read_cycle(self, base: dict, target: Path, tool_use_id: str, *, numbered: bool = True) -> dict:
        """First read: pre (allow), post (record), transcript row (Read shape). Returns the pre payload."""
        read = {**base, "tool_name": "Read", "tool_input": {"file_path": str(target)}, "tool_use_id": tool_use_id}
        # A first read (or a read after the file changed) is always allowed; it may carry a staleness note.
        self.assertNotIn("reason", self._gate({**read, "hook_event_name": "PreToolUse"}))
        content = target.read_text()
        numbered_text = "\n".join(f"{i + 1}\t{line}" for i, line in enumerate(content.splitlines()))
        self._gate(
            {
                **read,
                "hook_event_name": "PostToolUse",
                "tool_response": {
                    "type": "text",
                    "file": {"filePath": str(target), "content": numbered_text if numbered else content},
                },
            }
        )
        self._record_result(
            Path(base["transcript_path"]), tool_use_id, file_content=numbered_text if numbered else content
        )
        return {**read, "hook_event_name": "PreToolUse"}

    def test_read_gate_blocks_only_a_byte_identical_second_whole_read_that_is_intact_in_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "module.py"
            target.write_text("print('v1')\nprint('more')\n")
            base = {"session_id": "gate-session", "workspace_roots": [tmp], "transcript_path": f"{tmp}/t.jsonl"}
            pre = self._read_cycle(base, target, "toolu_read_1")
            second = self._gate(pre)
            self.assertEqual(second["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("byte-identical to your read at", second["reason"])
            self.assertIn("offset/limit", second["reason"])
            # Targeted reads are never gated.
            self.assertEqual(self._gate({**pre, "tool_input": {"file_path": str(target), "offset": 1}}), {})
            # A changed file is allowed, with a staleness note; a fresh intact read blocks again.
            target.write_text("print('v2')\n")
            changed = self._gate(pre)
            self.assertNotIn("reason", changed)
            self.assertIn("changed since your read", changed["additional_context"])
            pre2 = self._read_cycle(base, target, "toolu_read_2")
            self.assertEqual(self._gate(pre2)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_read_gate_allows_when_history_is_truncated_missing_or_garbled(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "big.txt"
            target.write_text("line\n" * 50)
            transcript = Path(tmp) / "t.jsonl"
            base = {"session_id": "gate-history", "workspace_roots": [tmp], "transcript_path": str(transcript)}
            cat = {**base, "tool_name": "Bash", "tool_input": {"command": f"cat {target}"}}
            # 1. Truncated at record time (persisted preview): nothing is recorded, no block.
            self._gate(
                {
                    **cat,
                    "hook_event_name": "PostToolUse",
                    "tool_use_id": "t1",
                    "tool_response": {"stdout": "line\n", "persistedOutputPath": "/tmp/x"},
                }
            )
            self.assertEqual(self._gate({**cat, "hook_event_name": "PreToolUse"}), {})
            # 2. Recorded complete, but history later holds only a preview: allow with a note.
            self._gate(
                {
                    **cat,
                    "hook_event_name": "PostToolUse",
                    "tool_use_id": "t2",
                    "tool_response": {"stdout": target.read_text()},
                }
            )
            self._record_result(transcript, "t2", stdout="line\n", persisted=True)
            self.assertEqual(self._gate({**cat, "hook_event_name": "PreToolUse"}), {})
            ledger_file = next((SPEC_ROOT / str(Path(tmp).resolve()).lstrip("/")).glob(".reads-*gate-history*.json"))
            self.assertIn("truncated preview", json.loads(ledger_file.read_text())[str(target)]["dropped"])
            # 3. Recorded but the row never reached the transcript: allow silently, and the stale entry is dropped.
            self._gate(
                {
                    **cat,
                    "hook_event_name": "PostToolUse",
                    "tool_use_id": "t3",
                    "tool_response": {"stdout": target.read_text()},
                }
            )
            self.assertEqual(self._gate({**cat, "hook_event_name": "PreToolUse"}), {})
            self.assertIn("no longer found", json.loads(ledger_file.read_text())[str(target)]["dropped"])
            self.assertEqual(self._gate({**cat, "hook_event_name": "PreToolUse"}), {})
            # 4. Garbled copy in history: allow.
            self._gate(
                {
                    **cat,
                    "hook_event_name": "PostToolUse",
                    "tool_use_id": "t4",
                    "tool_response": {"stdout": target.read_text()},
                }
            )
            self._record_result(transcript, "t4", stdout="line\n" * 49 + "garbled\n")
            self.assertEqual(self._gate({**cat, "hook_event_name": "PreToolUse"}), {})
            self.assertIn("does not match", json.loads(ledger_file.read_text())[str(target)]["dropped"])
            # 5. Intact Bash stdout in history: block.
            self._gate(
                {
                    **cat,
                    "hook_event_name": "PostToolUse",
                    "tool_use_id": "t5",
                    "tool_response": {"stdout": target.read_text()},
                }
            )
            self._record_result(transcript, "t5", stdout=target.read_text())
            self.assertEqual(self._gate({**cat, "hook_event_name": "PreToolUse"})["decision"], "block")
            # 6a. OMP read tool decorates output with a [path#hash] header and N: line numbers.
            omp = {
                **base,
                "session_id": "gate-omp",
                "transcript_path": f"{tmp}/omp.jsonl",
                "tool_name": "read",
                "tool_input": {"path": str(target)},
            }
            decorated = (
                f"[{target}#00ab]\n"
                + "\n".join(f"{i + 1}:{line}" for i, line in enumerate(target.read_text().splitlines()))
                + "\n"
            )
            self._gate({**omp, "hook_event_name": "PostToolUse", "tool_use_id": "omp-1", "tool_response": decorated})
            with Path(omp["transcript_path"]).open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "type": "message",
                            "timestamp": "2099-01-01T00:00:00.000Z",
                            "message": {
                                "role": "toolResult",
                                "toolCallId": "omp-1",
                                "toolName": "read",
                                "isError": False,
                                "content": [{"type": "text", "text": decorated}],
                            },
                        }
                    )
                    + "\n"
                )
            self.assertEqual(
                self._gate({**omp, "hook_event_name": "PreToolUse"})["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            # 6b. Codex code mode: the hook id is an inner exec id, the rollout stores the outer
            #     call id with a JSON-wrapped output; the content fallback still finds the read.
            cm = {
                **base,
                "session_id": "gate-codemode",
                "transcript_path": f"{tmp}/codemode.jsonl",
                "tool_name": "Bash",
                "tool_input": {"command": f"cat {target}"},
            }
            self._gate(
                {
                    **cm,
                    "hook_event_name": "PostToolUse",
                    "tool_use_id": "exec-inner-1",
                    "tool_response": target.read_text(),
                }
            )
            wrapped = [
                {"type": "input_text", "text": "Script completed\nWall time 0.2 seconds\nOutput:\n"},
                {
                    "type": "input_text",
                    "text": json.dumps({"chunk_id": "x", "exit_code": 0, "output": target.read_text()}),
                },
            ]
            with Path(cm["transcript_path"]).open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "timestamp": "2099-01-01T00:00:00.000Z",
                            "type": "response_item",
                            "payload": {"type": "custom_tool_call_output", "call_id": "call_outer", "output": wrapped},
                        }
                    )
                    + "\n"
                )
            self.assertEqual(
                self._gate({**cm, "hook_event_name": "PreToolUse"})["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            # 6. Codex rollout shape: the exec output wraps the file text.
            codex = {
                **base,
                "session_id": "gate-codex",
                "transcript_path": f"{tmp}/rollout.jsonl",
                "tool_name": "shell",
                "tool_input": {"command": f"cat {target}"},
            }
            self._gate(
                {
                    **codex,
                    "hook_event_name": "PostToolUse",
                    "tool_use_id": "call_9",
                    "tool_response": "Process exited with code 0\nOutput:\n" + target.read_text(),
                }
            )
            self._record_result(
                Path(codex["transcript_path"]),
                "call_9",
                codex_output="Chunk ID: 1\nProcess exited with code 0\nOutput:\n" + target.read_text(),
            )
            self.assertEqual(
                self._gate({**codex, "hook_event_name": "PreToolUse"})["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

    def test_read_gate_never_touches_pipes_slices_children_or_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("hello\n")
            transcript = Path(tmp) / "t.jsonl"
            base = {"session_id": "gate-shell", "workspace_roots": [tmp], "transcript_path": str(transcript)}
            cat = {**base, "tool_name": "Bash", "tool_input": {"command": f"cat {target}"}}
            self._gate(
                {**cat, "hook_event_name": "PostToolUse", "tool_use_id": "c1", "tool_response": {"stdout": "hello\n"}}
            )
            self._record_result(transcript, "c1", stdout="hello\n")
            self.assertEqual(self._gate({**cat, "hook_event_name": "PreToolUse"})["decision"], "block")
            for command in (
                f"cat {target} | head -2",
                f"sed -n '1,3p' {target}",
                f"cat {target} > /dev/null",
                f"cat {target}; ls",
            ):
                with self.subTest(command=command):
                    self.assertEqual(
                        self._gate({**cat, "hook_event_name": "PreToolUse", "tool_input": {"command": command}}), {}
                    )
            # A child agent shares the session id but not the context: its own ledger, first read allowed.
            self.assertEqual(
                self._gate({**cat, "hook_event_name": "PreToolUse", "agent_id": "abc123", "agent_type": "Explore"}), {}
            )
            self.assertEqual(
                self._gate({**cat, "hook_event_name": "PreToolUse"}, env={**hook_env(), "AGENT_READ_GATE": "off"}), {}
            )

    def test_read_gate_cursor_events_use_store_db_history_and_stop_shrink(self):
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "c.txt"
            target.write_text("line one\nline two\n")
            config = Path(tmp) / "config"
            store = config / "cursor" / "chats" / "ws-hash" / "conv-1" / "store.db"
            store.parent.mkdir(parents=True)
            env = {**hook_env(), "XDG_CONFIG_HOME": str(config), "AGENT_HOOK_HARNESS": "cursor"}
            base = {"conversation_id": "conv-1", "workspace_roots": [tmp], "transcript_path": f"{tmp}/agent.jsonl"}
            read = {
                **base,
                "hook_event_name": "beforeReadFile",
                "file_path": str(target),
                "content": target.read_text(),
            }
            # First delivery: allowed and recorded (beforeReadFile fires after the read succeeded).
            self.assertEqual(self._gate(read, env=env), {"permission": "allow"})
            # Second delivery with no store row yet: not verifiable, allowed.
            self.assertEqual(self._gate(read, env=env), {"permission": "allow"})
            conn = sqlite3.connect(store)
            conn.execute("create table blobs (id text, data blob)")
            row = {
                "role": "tool",
                "content": [
                    {"type": "tool-result", "toolCallId": "x", "toolName": "Read", "result": target.read_text()}
                ],
                "id": "m1",
            }
            conn.execute("insert into blobs values (?, ?)", ("b1", json.dumps(row).encode()))
            conn.execute("insert into blobs values (?, ?)", ("b2", b"\x12\x03protobuf-ish"))
            conn.commit()
            conn.close()
            self._gate(read, env=env)  # re-record after the unverifiable pass dropped the entry
            denied = self._gate(read, env=env)
            self.assertEqual(denied["permission"], "deny")
            self.assertIn("byte-identical", denied["user_message"])
            # Shell path: cat is gated the same way; pipes are not.
            shell = {**base, "hook_event_name": "beforeShellExecution", "command": f"cat {target}"}
            self.assertEqual(self._gate(shell, env=env)["permission"], "deny")
            self.assertEqual(
                self._gate({**shell, "command": f"cat {target} | wc -l"}, env=env), {"permission": "allow"}
            )
            # A token shrink reported by the stop hook reads as a compaction: the old read no longer blocks.
            stop = {
                **base,
                "hook_event_name": "stop",
                "status": "completed",
                "input_tokens": 1000,
                "cache_read_tokens": 90000,
                "cache_write_tokens": 0,
            }
            self._gate(stop, env=env)
            self._gate({**stop, "cache_read_tokens": 20000}, env=env)
            self.assertEqual(self._gate(read, env=env), {"permission": "allow"})

    def test_read_gate_copilot_events_verify_history_and_respect_compaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "c.txt"
            target.write_text("line one\nline two\n")
            events = Path(tmp) / "events.jsonl"
            base = {
                "session_id": "cop-1",
                "workspace_roots": [tmp],
                "transcript_path": str(events),
                "tool_name": "view",
                "tool_input": {"path": str(target)},
            }
            self._gate({**base, "hook_event_name": "PostToolUse", "tool_response": target.read_text()})
            with events.open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "type": "tool.execution_complete",
                            "timestamp": "2099-01-01T00:00:00.000Z",
                            "data": {
                                "toolCallId": "call_1",
                                "success": True,
                                "result": {"content": target.read_text()},
                            },
                        }
                    )
                    + "\n"
                )
            self.assertEqual(
                self._gate({**base, "hook_event_name": "PreToolUse"})["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )
            # Copilot's ranged read (view_range) is the escape hatch and must pass.
            self.assertEqual(
                self._gate(
                    {**base, "hook_event_name": "PreToolUse", "tool_input": {"path": str(target), "view_range": [1, 2]}}
                ),
                {},
            )
            with events.open("a") as handle:
                handle.write(
                    json.dumps(
                        {"type": "session.compaction_complete", "timestamp": "2099-01-02T00:00:00.000Z", "data": {}}
                    )
                    + "\n"
                )
            self.assertEqual(self._gate({**base, "hook_event_name": "PreToolUse"}), {})

    def test_read_gate_opencode_payloads_verify_the_part_store_and_unwrap_the_read_envelope(self):
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "o.txt"
            target.write_text("alpha\nbeta 10:30\n\ngamma\n")
            db = Path(tmp) / "opencode.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "create table part (id text primary key, message_id text, session_id text, "
                "time_created integer, time_updated integer, data text)"
            )
            conn.commit()
            conn.close()
            envelope = (
                f"<path>{target}</path>\n<type>file</type>\n<content>\n1: alpha\n2: beta 10:30\n3: \n4: gamma\n\n"
                "(End of file - total 4 lines)\n</content>"
            )
            base = {"cwd": tmp, "session_id": "oc-1", "transcript_path": str(db), "tool_use_id": "call-1"}
            pre = {
                **base,
                "hook_event_name": "PreToolUse",
                "tool_name": "read",
                "tool_input": {"filePath": str(target)},
            }
            post = {**pre, "hook_event_name": "PostToolUse", "tool_response": envelope}
            self.assertEqual(self._gate(pre), {})
            self.assertEqual(self._gate(post), {})
            # No part row yet: the earlier read is unverifiable, so the re-read goes ahead silently.
            self.assertEqual(self._gate(pre), {})
            self.assertEqual(self._gate(post), {})
            now_ms = int(time.time() * 1000)

            def store_part(part_id: str, state: dict) -> None:
                conn = sqlite3.connect(db)
                data = json.dumps({"type": "tool", "tool": "read", "callID": "call-1", "state": state})
                conn.execute("insert into part values (?,?,?,?,?,?)", (part_id, "m1", "oc-1", now_ms, now_ms, data))
                conn.commit()
                conn.close()

            store_part(
                "p1", {"status": "completed", "input": {"filePath": str(target)}, "output": envelope, "time": {}}
            )
            denied = self._gate(pre)
            self.assertEqual(denied.get("decision"), "block")
            self.assertIn("byte-identical", denied["reason"])
            # A ranged read (offset/limit) is never gated.
            self.assertEqual(self._gate({**pre, "tool_input": {"filePath": str(target), "offset": 2, "limit": 1}}), {})
            # OpenCode's prune cleared the output: the copy left the live context, so the read goes ahead.
            conn = sqlite3.connect(db)
            conn.execute(
                "update part set data = ? where id = 'p1'",
                (
                    json.dumps(
                        {
                            "type": "tool",
                            "tool": "read",
                            "callID": "call-1",
                            "state": {
                                "status": "completed",
                                "input": {"filePath": str(target)},
                                "output": envelope,
                                "time": {"compacted": now_ms},
                            },
                        }
                    ),
                ),
            )
            conn.commit()
            conn.close()
            self.assertEqual(self._gate(pre), {})

    def test_read_gate_forgets_reads_from_before_a_compaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "big.txt"
            target.write_text("x" * 100 + "\n")
            transcript = Path(tmp) / "t.jsonl"
            base = {"session_id": "gate-compact", "workspace_roots": [tmp], "transcript_path": str(transcript)}
            pre = self._read_cycle(base, target, "toolu_c1")
            self.assertEqual(self._gate(pre)["decision"], "block")
            run_hook(
                "executable_session_context.py",
                {
                    "hook_event_name": "SessionStart",
                    "source": "compact",
                    "session_id": "gate-compact",
                    "workspace_roots": [tmp],
                },
            )
            self.assertEqual(self._gate(pre), {})

    def test_perturn_reinforcement_fires_only_after_material_context_growth(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            env = self._reinforcement_env(tmp)
            transcript = Path(tmp) / "transcript.jsonl"
            payload = {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "reinforce-growth",
                "workspace_roots": [tmp],
                "transcript_path": str(transcript),
                "prompt": "a substantive prompt for reinforcement",
            }

            self._write_claude_transcript(transcript, 20_000)
            first = run_perturn_recall(tmp, payload, env)
            assert "PREFIX_SENTINEL_REINFORCE" not in json.dumps(first), "first observation is the baseline"

            self._write_claude_transcript(transcript, 150_000)
            steady = run_perturn_recall(tmp, payload, env)
            assert "PREFIX_SENTINEL_REINFORCE" not in json.dumps(steady), "130k growth is under the 200k threshold"

            self._write_claude_transcript(transcript, 221_000)
            grown = run_perturn_recall(tmp, payload, env)
            context = grown["hookSpecificOutput"]["additionalContext"]
            assert context.startswith("PREFIX_SENTINEL_REINFORCE")
            assert "Apply the discipline above to this and later prompts" in context
            assert grown["additional_context"] == context

            again = run_perturn_recall(tmp, payload, env)
            assert "PREFIX_SENTINEL_REINFORCE" not in json.dumps(again), "baseline moved to the injection point"

            state = json.loads((spec_dir / "reinforce-growth.reinforce.json").read_text())
            assert state["reinjections"] == 1
            assert state["last_reason"] == "growth"
            assert state["last_tokens"] == 221_000

    def test_perturn_reinforcement_fires_after_compaction_signal_or_shrink(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self._reinforcement_env(tmp)
            transcript = Path(tmp) / "transcript.jsonl"
            payload = {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "reinforce-compact",
                "workspace_roots": [tmp],
                "transcript_path": str(transcript),
                "prompt": "a substantive prompt for reinforcement",
            }
            self._write_claude_transcript(transcript, 90_000)
            run_perturn_recall(tmp, payload, env)  # baseline

            # Claude Code re-fires SessionStart with source=compact after a compaction.
            run_hook(
                "executable_session_context.py",
                {
                    "hook_event_name": "SessionStart",
                    "source": "compact",
                    "session_id": "reinforce-compact",
                    "workspace_roots": [tmp],
                },
                env=env,
            )
            forced = run_perturn_recall(tmp, payload, env)
            assert forced["hookSpecificOutput"]["additionalContext"].startswith("PREFIX_SENTINEL_REINFORCE")

            # A large shrink of the observed context reads as a compaction on harnesses
            # that give no explicit signal.
            self._write_claude_transcript(transcript, 40_000)
            shrunk = run_perturn_recall(tmp, payload, env)
            assert shrunk["hookSpecificOutput"]["additionalContext"].startswith("PREFIX_SENTINEL_REINFORCE")

            self._write_claude_transcript(transcript, 41_000)
            assert "PREFIX_SENTINEL_REINFORCE" not in json.dumps(run_perturn_recall(tmp, payload, env))

    def test_perturn_reinforcement_reads_codex_rollout_token_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self._reinforcement_env(tmp)
            rollout = Path(tmp) / "rollout.jsonl"
            payload = {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "reinforce-codex",
                "workspace_roots": [tmp],
                "transcript_path": str(rollout),
                "prompt": "a substantive prompt for reinforcement",
            }

            def write(tokens: int) -> None:
                rows = [
                    {"type": "session_meta", "payload": {"id": "reinforce-codex"}},
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {"input_tokens": tokens, "output_tokens": 5},
                                "model_context_window": 258400,
                            },
                        },
                    },
                ]
                rollout.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            write(22_000)
            run_perturn_recall(tmp, payload, env)
            write(223_000)
            grown = run_perturn_recall(tmp, payload, env)
            assert grown["hookSpecificOutput"]["additionalContext"].startswith("PREFIX_SENTINEL_REINFORCE")

    def test_perturn_reinforcement_falls_back_to_a_prompt_interval_without_usage(self):
        # Cursor/Copilot payloads carry no transcript; the interval is the documented proxy.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            env = self._reinforcement_env(tmp, AGENT_REINFORCE_PROMPTS="3")
            payload = {
                "hook_event_name": "UserPromptSubmit",
                "conversation_id": "reinforce-interval",
                "workspace_roots": [tmp],
                "prompt": "a substantive prompt for reinforcement",
            }
            outcomes = [
                "PREFIX_SENTINEL_REINFORCE" in json.dumps(run_perturn_recall(tmp, payload, env)) for _ in range(5)
            ]
            assert outcomes == [False, False, False, True, False]
            state = json.loads((spec_dir / "reinforce-interval.reinforce.json").read_text())
            assert state["last_reason"] == "prompt-count"

    def test_perturn_reinforcement_counts_short_prompts_and_honours_the_kill_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self._reinforcement_env(tmp)
            transcript = Path(tmp) / "transcript.jsonl"
            payload = {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "reinforce-short",
                "workspace_roots": [tmp],
                "transcript_path": str(transcript),
                "prompt": "go",
            }
            self._write_claude_transcript(transcript, 10_000)
            assert run_perturn_recall(tmp, payload, env) == {}
            self._write_claude_transcript(transcript, 215_000)
            short = run_perturn_recall(tmp, payload, env)
            assert short["hookSpecificOutput"]["additionalContext"].startswith("PREFIX_SENTINEL_REINFORCE")
            assert "candidates staged" not in short["hookSpecificOutput"]["additionalContext"]

            self._write_claude_transcript(transcript, 500_000)
            assert run_perturn_recall(tmp, payload, {**env, "AGENT_REINFORCE": "off"}) == {}

    def test_session_context_leaf_suppresses_delegation_blocks(self):
        """Delegation text is root-only: a leaf gets none of it, the root gets it marked."""
        marker = "[ROOT ONLY] A delegated leaf ignores this block and returns findings to its parent instead."
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "leaf-session", "memory-systems")
            (spec_dir / "memory-systems.txt").write_text("target: wire memory systems\n")

            payload = {
                "hook_event_name": "sessionStart",
                "workspace_roots": [tmp],
                "session_id": "leaf-session",
            }
            leaf_env = {**keep_parent_env("copilot-parent-session"), "AI_AGENT_DEPTH": "fast"}
            root_env = {**os.environ, "AI_AGENT_DEPTH": "fast"}
            leaf = run_hook("executable_session_context.py", payload, env=leaf_env)["additional_context"]
            root = run_hook("executable_session_context.py", payload, env=root_env)["additional_context"]

            # The leaf still gets its topic context; only the blocks that tell it to
            # delegate are withheld.
            assert "target: wire memory systems" in leaf
            assert "k-agent-smol" not in leaf
            assert "Durable Memory (,ai-kb)" not in leaf
            assert marker not in leaf

            # Harnesses with no child signal fall back to the marker, so the root copy
            # must carry the sentence verbatim.
            assert marker in root
            assert "k-agent-smol" in root

    def test_balanced_depth_leaf_suppresses_state_writes_and_the_correction_directive(self):
        """The fast-depth leaf contract holds where retrieval actually runs.

        At `balanced` the startup warm start and per-turn recall both retrieve and stage, so
        this is the depth where a missing child guard would leak delegation text into a child
        and write session state on its behalf. The root at the same depth is the control: it
        keeps the marked blocks, and its non-marker text is byte-identical to the leaf's.
        """
        marker = "[ROOT ONLY] A delegated leaf ignores this block and returns findings to its parent instead."
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            stub = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "balanced-capsule",
                        "title": "Capsule the root must be pointed at",
                        "body": "B" * 400,
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": workspace,
                        "cosine_score": 0.8,
                    }
                ],
            )

            def fixture(name: str, env: dict) -> tuple[str, Path, dict]:
                """A private spec root per run, so the leaf's state dir starts and stays empty."""
                key = f"balanced-{name}"
                spec_root = Path(tmp) / f"{name}-spec-root"
                spec_dir = spec_root / workspace.lstrip("/")
                spec_dir.mkdir(parents=True)
                bind_session_topic(spec_dir, key, "memory-systems")
                (spec_dir / "memory-systems.txt").write_text("target: wire memory systems\n")
                effective = {
                    **env,
                    "PATH": stub["PATH"],
                    "AI_AGENT_DEPTH": "balanced",
                    # Reinforcement is not delegation text and both sides keep it: switching it
                    # off only keeps its own session-state file out of the no-write assertion.
                    "AGENT_REINFORCE": "off",
                    "AGENT_MEMORY_SPEC_ROOT": str(spec_root),
                }
                return key, spec_root, effective

            def runs(key: str, env: dict) -> tuple[str, dict]:
                startup = run_hook(
                    "executable_session_context.py",
                    {"hook_event_name": "sessionStart", "workspace_roots": [tmp], "session_id": key},
                    env=env,
                )["additional_context"]
                perturn = run_perturn_recall(
                    tmp,
                    {
                        "hook_event_name": "UserPromptSubmit",
                        "workspace_roots": [tmp],
                        "conversation_id": key,
                        "prompt": "Did you actually verify this claim, or did you just guess again?",
                    },
                    env,
                )
                return startup, perturn

            leaf_key, leaf_root, leaf_env = fixture("leaf", keep_parent_env("copilot-parent-balanced"))
            root_key, root_spec_root, root_env = fixture("root", dict(os.environ))
            before = sorted(str(path.relative_to(leaf_root)) for path in leaf_root.rglob("*"))
            leaf_startup, leaf_perturn = runs(leaf_key, leaf_env)
            root_startup, root_perturn = runs(root_key, root_env)

            # Leaf: topic context survives, every delegation-instructing block is withheld.
            assert "target: wire memory systems" in leaf_startup
            assert marker not in leaf_startup
            assert "Durable Memory (,ai-kb)" not in leaf_startup
            assert "candidates staged" not in leaf_startup
            assert "k-agent-smol" not in leaf_startup
            # Nothing is left for the per-turn hook to emit: no pointer, no correction block.
            assert leaf_perturn == {}
            # And the child wrote no candidate/pointer/seen state on its parent's behalf.
            assert sorted(str(path.relative_to(leaf_root)) for path in leaf_root.rglob("*")) == before

            # The root retains retrieval, bounded memory admission, and correction capture.
            root_perturn_context = root_perturn["hookSpecificOutput"]["additionalContext"]
            assert (root_spec_root / workspace.lstrip("/") / f".recall-candidates-{root_key}.json").exists()
            assert marker in root_startup
            assert "### User correction signal:" in root_perturn_context
            assert "Do not launch re-verification" in root_perturn_context
            assert "k-agent-smol" not in root_perturn_context
            assert "candidates staged" in root_startup
            assert ",agent-memory note anti_pattern" in root_perturn_context

    def test_cursor_startup_budget_omits_whole_artifacts_in_utf16_units(self):
        for fill in ("x", "😀"):
            with self.subTest(fill=fill), tempfile.TemporaryDirectory() as tmp:
                workspace = str(Path(tmp).resolve())
                spec_dir = SPEC_ROOT / workspace.lstrip("/")
                spec_dir.mkdir(parents=True, exist_ok=True)
                bind_session_topic(spec_dir, "cursor-cap", "maximal-topic")
                spec_path = spec_dir / "maximal-topic.txt"
                spec_body = "target: " + fill * 2492
                spec_path.write_text(spec_body)
                worklog_path = spec_dir / "maximal-topic.worklog.jsonl"
                worklog_body = json.dumps({"body": fill * 2980}, ensure_ascii=False) + "\n"
                worklog_path.write_text(worklog_body)
                config = Path(tmp) / "config"
                config.mkdir()
                env = {**hook_env(), "AI_AGENT_DEPTH": "fast", "XDG_CONFIG_HOME": str(config)}
                payload = {"session_id": "cursor-cap", "workspace_roots": [workspace], "warm_embedder": True}
                original = run_hook(
                    "executable_session_context.py", payload, env={**env, "AGENT_HOOK_HARNESS": "other"}
                )["additional_context"]
                bounded = run_hook(
                    "executable_session_context.py", payload, env={**env, "AGENT_HOOK_HARNESS": "cursor"}
                )["additional_context"]
                lengths = subprocess.run(
                    [
                        "node",
                        "-e",
                        "const fs=require('fs'); console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(s=>s.trim().length)))",
                    ],
                    input=json.dumps([original, bounded]),
                    capture_output=True,
                    text=True,
                    check=True,
                )
                original_units, bounded_units = json.loads(lengths.stdout)
                self.assertLessEqual(bounded_units, 10000)
                self.assertIn("Durable Memory (,ai-kb)", bounded)
                self.assertEqual(worklog_path.read_text(), worklog_body)
                if fill == "x":
                    # Same character counts, one UTF-16 unit each: fits, nothing is omitted.
                    self.assertLessEqual(original_units, 10000)
                    self.assertEqual(bounded, original)
                    self.assertIn(worklog_body.strip(), bounded)
                else:
                    # Two UTF-16 units per emoji: over the cap. Optional artifacts are omitted
                    # in order until the context fits: the worklog goes first and, once the
                    # remainder fits, the spec is retained whole (never sliced).
                    self.assertGreater(original_units, 10000)
                    self.assertIn(str(worklog_path), bounded)
                    self.assertNotIn(worklog_body.strip(), bounded)
                    self.assertIn(spec_body, bounded)
                self.assertEqual(spec_path.read_text(), spec_body)
                if fill == "x":
                    self.assertIn(spec_body, bounded)

    def test_named_startup_fast_and_disable_status_do_not_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            bind_session_topic(spec_dir, "gated-startup", "named-topic")
            (spec_dir / "named-topic.txt").write_text("target: a substantive named task")
            env = make_aikb_stub(Path(tmp), [{"id": "A", "title": "LEAK", "scope": "universal"}])
            log = Path(tmp) / "search-log.jsonl"
            env["AI_KB_STUB_LOG"] = str(log)
            payload = {"workspace_roots": [tmp], "session_id": "gated-startup"}
            fast = run_hook("executable_session_context.py", payload, env={**env, "AI_AGENT_DEPTH": "fast"})
            self.assertIn("a substantive named task", fast["additional_context"])
            self.assertFalse(log.exists())
            disabled = {**env, "AGENT_HOOK_CONTEXT": "off"}
            self.assertEqual(run_hook("executable_session_context.py", payload, env=disabled), {})
            self.assertEqual(
                run_hook("executable_session_context.py", {**payload, "context_status": True}, env=disabled),
                {"context_disabled": True},
            )
            self.assertFalse(log.exists())

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

    def test_codex_hook_matchers_cover_the_tool_names_codex_actually_reports(self):
        # Probed 2026-09-06 (codex-cli 0.153.4, `codex exec --dangerously-bypass-hook-trust` with a
        # catch-all dump hook): shell calls reach hooks as tool_name "Bash" (both the plain
        # exec_command tool and the code-mode exec tool) and spawns as "collaborationspawn_agent".
        # A matcher of "shell" never fired, so every Codex tool hook was silently inert.
        import re

        codex = json.loads(
            (REPO / "home" / "dot_codex" / "hooks.json.tmpl").read_text().replace("{{ .chezmoi.homeDir }}", "/h")
        )
        seen = {}
        for event, groups in codex["hooks"].items():
            for group in groups:
                for hook in group["hooks"]:
                    seen.setdefault(hook["command"].rsplit("/", 1)[-1].rstrip("'"), []).append(
                        (event, group.get("matcher"))
                    )
        for script in ("premise_nudge.py", "read_gate.py", "publish_gate.py"):
            for _event, matcher in seen[script]:
                self.assertTrue(re.fullmatch(matcher, "Bash") and re.search(matcher, "Bash"), (script, matcher))
        for _event, matcher in seen["band_gate.py"]:
            for name in ("collaborationspawn_agent", "spawn_agent"):
                self.assertTrue(re.fullmatch(matcher, name) and re.search(matcher, name), (matcher, name))

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
        assert "premise_nudge.py" in json.dumps(antigravity["agent-premise"]["PreToolUse"])
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

    def test_opencode_root_memory_and_leaf_delegation_are_separate(self):
        extension = REPO / "home/dot_config/opencode/plugins/agent-memory.ts"
        script = r"""
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
const tmp=mkdtempSync('/tmp/opencode-leaf-memory-');process.env.HOME=tmp;
const dir=join(tmp,'.agents/hooks');mkdirSync(dir,{recursive:true});
for(const name of ['session_context.py','worklog_dispatcher.sh','perturn_recall.py']) writeFileSync(join(dir,name),'');
const calls=[];const lookups=[];
const shell=(strings,...values)=>({quiet(){return this},nothrow(){calls.push(values);return Promise.resolve({stdout:JSON.stringify({hookSpecificOutput:{additionalContext:'ROOT_RECALL'}})})}});
const client={session:{async get({path}){lookups.push(path.id);if(path.id==='unknown')return {error:{}};return {data:{id:path.id,...(path.id==='child'?{parentID:'root'}:{})}}}}};
const mod=await import(process.argv[1]);const hooks=await mod.AgentMemoryPlugin({$:shell,directory:tmp,client});
for(const sessionID of ['root','child','unknown','root','child']) {
  const output={system:[]};await hooks['experimental.chat.system.transform']({sessionID},output);
  assert.deepEqual(output.system,sessionID==='root'?['ROOT_RECALL']:[]);
}
assert.equal(calls.length,1);assert.deepEqual(lookups,['root','child','unknown']);
for(const sessionID of ['root','child']) {
  const output={message:{id:'m'},parts:[{type:'text',text:'meaningful prompt'}]};
  await hooks['chat.message']({sessionID},output);
  assert.equal(output.parts.length,sessionID==='root'?2:1);
}
assert.equal(calls.length,2);
await hooks['tool.execute.before']({tool:'task',sessionID:'root'}, {args:{prompt:'ready packet'}});
for(const sessionID of ['child','unknown']) await assert.rejects(hooks['tool.execute.before']({tool:'task',sessionID},{args:{}}),/cannot delegate/);
await assert.rejects(hooks['tool.execute.before']({tool:'task',sessionID:'root'},{args:{task_id:'completed'}}),/resume/);
await hooks['tool.execute.after']({tool:'edit',sessionID:'child',callID:'c',args:{}},{output:'produced'});
assert.equal(calls.length,3); // Child worklog survives; root recall is not child context.
console.log('OpenCode root recall, child exclusion, identity failure, task and worklog cases passed');
"""
        result = subprocess.run(
            ["node", "--no-warnings", "--input-type=module", "-e", script, str(extension)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_opencode_SHOULD_keep_task_guards_when_optional_memory_helpers_are_missing(self):
        extension = REPO / "home/dot_config/opencode/plugins/agent-memory.ts"
        script = r"""
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
const tmp=mkdtempSync('/tmp/opencode-optional-memory-');
const mod=await import(process.argv[1]);
for(let mask=0;mask<8;mask++) {
  const home=join(tmp,String(mask));process.env.HOME=home;
  const dir=join(home,'.agents/hooks');mkdirSync(dir,{recursive:true});
  ['session_context.py','perturn_recall.py','worklog_dispatcher.sh'].forEach((name,index)=>{
    if(mask & (1<<index))writeFileSync(join(dir,name),'');
  });
  const calls=[];
  const shell=(strings,...values)=>({quiet(){return this},nothrow(){calls.push(values);return Promise.resolve({stdout:JSON.stringify({hookSpecificOutput:{additionalContext:'recall'}})})}});
  const client={session:{async get({path}){return path.id==='unknown'?{error:{}}:{data:{id:path.id,...(path.id==='child'?{parentID:'root'}:{})}}}}};
  const hooks=await mod.AgentMemoryPlugin({$:shell,directory:home,client});
  await hooks['tool.execute.before']({tool:'task',sessionID:'root'},{args:{}});
  for(const sessionID of ['child','unknown'])await assert.rejects(hooks['tool.execute.before']({tool:'task',sessionID},{args:{}}),/cannot delegate/);
  await assert.rejects(hooks['tool.execute.before']({tool:'task',sessionID:'root'},{args:{task_id:'done'}}),/resume/);
  const system={system:[]};await hooks['experimental.chat.system.transform']({sessionID:'root'},system);
  assert.deepEqual(system.system,mask&1?['recall']:[]);
  const prompt={message:{id:'m'},parts:[{type:'text',text:'relevant prompt'}]};
  await hooks['chat.message']({sessionID:'root'},prompt);
  assert.equal(prompt.parts.length,mask&2?2:1);
  await hooks['tool.execute.after']({tool:'edit',sessionID:'child',args:{}},{output:'produced'});
  assert.equal(calls.length,Boolean(mask&1)+Boolean(mask&2)+Boolean(mask&4));
}
console.log('all optional-helper combinations retain task guards and available memory');
"""
        result = subprocess.run(
            ["node", "--no-warnings", "--input-type=module", "-e", script, str(extension)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_opencode_plugin_gates_reads_and_supersedes_older_read_parts(self):
        plugin = REPO / "home/dot_config/opencode/plugins/agent-memory.ts"
        supersede = REPO / "home/dot_config/opencode/plugins/read-supersede.ts"
        with tempfile.TemporaryDirectory() as tmp:
            hooks_dir = Path(tmp) / ".agents" / "hooks"
            hooks_dir.mkdir(parents=True)
            for name in ("session_context.py", "worklog_dispatcher.sh", "perturn_recall.py", "read_gate.py"):
                (hooks_dir / name).write_text("")
            script = r"""
import assert from 'node:assert/strict';
const mod = await import(process.argv[1]);
const calls = [];
function shell(strings, ...values) {
  const argv = values.map(String);
  calls.push(argv);
  const gate = argv.some((v) => v.endsWith('read_gate.py'));
  const payload = gate ? JSON.parse(argv[0]) : {};
  const stdout = gate && payload.hook_event_name === 'PreToolUse' && payload.tool_name === 'read'
    ? JSON.stringify({ decision: 'block', reason: 'already in context' })
    : '{}';
  return { quiet() { return this; }, nothrow() { return Promise.resolve({ stdout, code: 0 }); } };
}
const hooks = await mod.AgentMemoryPlugin({ $: shell, directory: process.argv[2] });
await assert.rejects(
  hooks['tool.execute.before']({ tool: 'read', sessionID: 's', callID: 'c1' }, { args: { filePath: '/f' } }),
  /already in context/);
const pre = JSON.parse(calls[0][0]);
assert.deepEqual([pre.hook_event_name, pre.tool_name, pre.tool_use_id, pre.tool_input.filePath], ['PreToolUse', 'read', 'c1', '/f']);
assert.ok(pre.transcript_path.endsWith('/.local/share/opencode/opencode.db'));
// Ungated tools never reach the gate; bash does, and an allow resolves.
await hooks['tool.execute.before']({ tool: 'edit', sessionID: 's', callID: 'c2' }, { args: {} });
await hooks['tool.execute.before']({ tool: 'bash', sessionID: 's', callID: 'c3' }, { args: { command: 'cat /f' } });
assert.equal(calls.length, 2);
// After: the gate sees the tool output, then the worklog recorder runs as before.
await hooks['tool.execute.after']({ tool: 'read', sessionID: 's', callID: 'c1', args: { filePath: '/f' } }, { title: '/f', output: 'body', metadata: {} });
const post = JSON.parse(calls[2][0]);
assert.deepEqual([post.hook_event_name, post.tool_response, post.tool_use_id], ['PostToolUse', 'body', 'c1']);
assert.equal(calls.length, 4);

const sup = await import(process.argv[3]);
const notice = '[Superseded by a newer read of this file]';
const read = (path, output, extra = {}) => ({ type: 'tool', tool: 'read', state: { status: 'completed', input: { filePath: path, ...extra }, output, time: {} } });
const msg = (...parts) => ({ info: { role: 'assistant' }, parts });
let msgs = [msg(read('/f', 'v1')), { info: { role: 'user' }, parts: [{ type: 'text', text: 'edit' }] }, msg(read('/f', 'v2'), read('/g', 'w'))];
assert.equal(sup.supersedeReadParts(msgs, 1000, 900), 1);
assert.deepEqual([msgs[0].parts[0].state.output, msgs[2].parts[0].state.output, msgs[2].parts[1].state.output], [notice, 'v2', 'w']);
assert.equal(sup.supersedeReadParts(msgs, 1000, 900), 0, 'idempotent');
// Ranged reads and pruned parts are left alone.
msgs = [msg(read('/f', 'v1', { offset: 2 })), msg(read('/f', 'v2'))];
assert.equal(sup.supersedeReadParts(msgs, 1000, 900), 0);
msgs = [msg({ ...read('/f', 'v1'), state: { status: 'completed', input: { filePath: '/f' }, output: 'v1', time: { compacted: 5 } } }), msg(read('/f', 'v2'))];
assert.equal(sup.supersedeReadParts(msgs, 1000, 900), 0);
// Cache guard: a large suffix keeps the old copy unless the session idled 90 minutes.
msgs = [msg(read('/f', 'v1')), msg({ type: 'text', text: 'x'.repeat(40000) }), msg(read('/f', 'v2'))];
assert.equal(sup.supersedeReadParts(msgs, 1000, 900), 0);
assert.equal(sup.supersedeReadParts(msgs, 100 * 60_000, 0), 1);
// The plugin hook mutates output.messages in place.
const hooks2 = await sup.ReadSupersedePlugin({});
const out = { messages: [msg(read('/f', 'v1')), msg(read('/f', 'v2'))] };
await hooks2['experimental.chat.messages.transform']({}, out);
assert.equal(out.messages[0].parts[0].state.output, notice);
console.log(JSON.stringify({ ok: true }));
"""
            env = dict(os.environ)
            env["HOME"] = tmp
            env["NODE_NO_WARNINGS"] = "1"
            result = subprocess.run(
                ["node", "--input-type=module", "-e", script, str(plugin), tmp, str(supersede)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-1500:])
            self.assertIn('{"ok":true}', result.stdout)

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
const verificationPrefix = "P".repeat(3500) + "PREFIX_TAIL";
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
      return { code: 0, killed: false, stdout: verificationPrefix };
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
            assert "PREFIX_TAIL" in payload["grown"]["message"]["content"]
            assert (
                "SHARED_SESSION_CONTEXT::pi-session-context::topic shift"
                in payload["topicChanged"]["message"]["content"]
            )
            assert "PREFIX_TAIL" in payload["compacted"]["message"]["content"]
            assert payload["afterCompactionBaseline"] is None
            assert "PREFIX_TAIL" in payload["grownAfterCompaction"]["message"]["content"]
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
                    "context_status": True,
                    "workspace_roots": [str(Path(tmp).resolve())],
                },
                {
                    "cwd": str(Path(tmp).resolve()),
                    "hook_event_name": "sessionStart",
                    "initial_prompt": "topic shift",
                    "session_id": "pi-session-context",
                    "source": "pi",
                    "warm_embedder": True,
                    "context_status": True,
                    "workspace_roots": [str(Path(tmp).resolve())],
                },
                {
                    "cwd": str(Path(tmp).resolve()),
                    "hook_event_name": "sessionStart",
                    "initial_prompt": "resume",
                    "session_id": "pi-session-context",
                    "source": "pi",
                    "warm_embedder": True,
                    "context_status": True,
                    "workspace_roots": [str(Path(tmp).resolve())],
                },
            ]

    def test_runtime_extensions_enable_search_tools(self):
        extension_cases = [
            REPO / "home/dot_pi/agent/exact_extensions/runtime-parity.ts",
            REPO / "home/dot_omp/private_agent/extensions/runtime-parity.ts",
        ]
        for extension in extension_cases:
            with self.subTest(extension=str(extension.relative_to(REPO))):
                with tempfile.TemporaryDirectory() as tmp:
                    home = Path(tmp) / "home"
                    home.mkdir(parents=True)
                    script = """
const mod = await import(process.argv[1]);
function makePi() {
  const handlers = {};
  let active = ["read", "bash", "edit", "write"];
  return {
    handlers,
    events: { on() {} },
    getActiveTools() { return [...active]; },
    getAllTools() { return active.map(name => ({name})); },
    setActiveTools(tools) { active = [...tools]; },
    on(event, handler) { handlers[event] = handler; }
  };
}
const pi = makePi();
await mod.default(pi);
await pi.handlers.session_start({ type: "session_start", reason: "startup" }, {});
process.argv.push("--tools", "read,bash");
const explicit = makePi();
await mod.default(explicit);
await explicit.handlers.session_start({ type: "session_start", reason: "startup" }, {});
console.log(JSON.stringify({
  active: pi.getActiveTools(),
  toolCallHooked: "tool_call" in pi.handlers,
  explicit: explicit.getActiveTools()
}));
"""
                    env = dict(os.environ)
                    env["HOME"] = str(home)
                    env["NODE_NO_WARNINGS"] = "1"
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
                    assert payload["toolCallHooked"] is True
                    assert payload["explicit"] == ["read", "bash", "edit", "write"]

    def test_runtime_leaf_context_and_peer_send_boundaries(self):
        script = r"""
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
const tmp=mkdtempSync('/tmp/staged-leaf-runtime-');process.env.HOME=tmp;
writeFileSync(join(tmp,'AGENTS.md'),'ROOT_SOP_SENTINEL');
writeFileSync(join(tmp,'leaf.jsonl'),'native-session-fixture');
const ctx={sessionManager:{getSessionFile:()=>join(tmp,'leaf.jsonl')}};
const piModule=await import(process.argv[1]);const ompModule=await import(process.argv[2]);
function register(mod,tools=[]){const handlers={};mod.default({events:{on(){}},getAllTools(){return tools.map(name=>({name}))},on(name,callback){handlers[name]=(event)=>callback(event,ctx)}});return handlers}
const pi=register(piModule);
assert((await pi.before_agent_start({systemPrompt:'ordinary root'})).systemPrompt.includes('ROOT_SOP_SENTINEL'));
assert.equal(await pi.before_agent_start({systemPrompt:'[DELEGATION BOUNDARY]'}),undefined);
process.env.PI_SUBAGENT_CHILD='1';assert.equal(await pi.before_agent_start({systemPrompt:'ordinary child'}),undefined);delete process.env.PI_SUBAGENT_CHILD;
const omp=register(ompModule);
for(const name of [undefined, '', ' ', '\t\n']) {
  assert.equal(omp.tool_call({toolName:'hub',input:{op:'send',to:'done-worker',message:'wake',name}}).block,true);
}
assert.equal(omp.tool_call({toolName:'hub',input:{op:'send',name:'server',message:'input'}}),undefined);
assert.equal(omp.tool_call({toolName:'hub',input:{op:'send',name:' server ',message:'input'}}),undefined);
assert.equal(omp.tool_call({toolName:'hub',input:{op:'list'}}),undefined);
assert.equal(omp.tool_call({toolName:'bash',input:{command:'true'}}),undefined);
assert.equal(omp.tool_call({toolName:'bash',input:{command:'true',async:true}}),undefined);
assert.equal(omp.tool_call({toolName:'hub',input:{op:'start',name:'server'}}),undefined);
const tools=['yield'];const leaf=register(ompModule,tools);
for(const toolName of ['bash','eval','python','mcp']) {
  assert.equal(leaf.tool_call({toolName,input:{async:true}}).block,true);
  assert.equal(leaf.tool_call({toolName,input:{}}),undefined);
}
tools.length=0;
for(const toolName of ['task','advisor','hub']) assert.equal(leaf.tool_call({toolName,input:{}}).block,true);
assert.equal(leaf.tool_call({toolName:'yield',input:{data:{produced:'artifact'}}}),undefined);
const dispatch={agent:'k-agent-implementer',task:'settled packet',acceptance:false,agentScope:'user'};
for(const extra of [{},{context:'fresh'},{async:true}]) {
  assert.equal(pi.tool_call({toolName:'subagent',input:{...dispatch,...extra}}),undefined);
}
for(const extra of [{acceptance:undefined},{acceptance:'auto'},{acceptance:true},{context:'fork'},
  {context:'profile'},{model:'expensive:high'},{skills:true},{skill:true},{skill:['k-deep-review']},
  {skills:['k-code-quality']},{agentScope:undefined},{agentScope:'both'},{agentScope:'project'},{steeringRecovery:true},
  {workflow:[]},{workflowScript:'while(true){}'},{workflowScriptPath:'/tmp/loop.ts'},
  {chain:[]},{parallel:[]},{gate:'make check'},{agentContract:{}},
  {action:'resume'},{action:'steer'},{action:'schedule.create'},{action:'watchdog.configure'}]) {
  assert.equal(pi.tool_call({toolName:'subagent',input:{...dispatch,...extra}}).block,true,JSON.stringify(extra));
}
for(const action of ['list','status','debug.run','stop','interrupt']) {
  assert.equal(pi.tool_call({toolName:'subagent',input:{action}}),undefined);
}
process.env.PI_SUBAGENT_CHILD='1';
assert.equal(pi.tool_call({toolName:'subagent',input:dispatch}).block,true);
assert.equal(pi.tool_call({toolName:'subagent',input:{action:'status'}}).block,true);
assert.equal(pi.tool_call({toolName:'bash',input:{command:'true'}}),undefined);
delete process.env.PI_SUBAGENT_CHILD;
console.log('leaf-context and peer/process-send cases passed');
"""
        result = subprocess.run(
            [
                "node",
                "--no-warnings",
                "--input-type=module",
                "-e",
                script,
                str(REPO / "home/dot_pi/agent/exact_extensions/runtime-parity.ts"),
                str(REPO / "home/dot_omp/private_agent/extensions/runtime-parity.ts"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cases passed", result.stdout)

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

    def test_pi_read_gate_extension_blocks_a_verified_identical_read(self):
        script = r"""
import assert from 'node:assert/strict';
import { mkdir, writeFile, copyFile, chmod, appendFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { mkdtempSync } from 'node:fs';
const [extension, root] = process.argv.slice(1);
const tmp = mkdtempSync(join(tmpdir(), 'pi-read-gate-'));
const hooks = join(tmp, '.agents/hooks'); await mkdir(hooks, { recursive: true });
for (const [src, dst] of [['executable_read_gate.py', 'read_gate.py'], ['hook_common.py', 'hook_common.py'], ['reinforcement.py', 'reinforcement.py']]) {
  await copyFile(join(root, 'home/exact_dot_agents/exact_hooks', src), join(hooks, dst)); await chmod(join(hooks, dst), 0o755);
}
process.env.HOME = tmp; process.env.AGENT_MEMORY_SPEC_ROOT = join(tmp, 'specs');
const target = join(tmp, 'notes.txt'); await writeFile(target, 'alpha\nbeta\n');
const session = join(tmp, 'session.jsonl'); await writeFile(session, '');
const handlers = {};
const api = { on(k, v) { handlers[k] = v } };
const mod = await import(extension); await mod.default(api);
assert.equal(typeof handlers.tool_call, 'function'); assert.equal(typeof handlers.tool_result, 'function');
const ctx = { cwd: tmp, sessionManager: { getSessionId() { return 'pi-gate' }, getSessionFile() { return session } } };
const call = (id) => handlers.tool_call({ type: 'tool_call', toolCallId: id, toolName: 'read', input: { path: target } }, ctx);
assert.equal(await call('c1'), undefined, 'first read passes');
await handlers.tool_result({ type: 'tool_result', toolCallId: 'c1', toolName: 'read', input: { path: target }, content: [{ type: 'text', text: 'alpha\nbeta\n' }], isError: false }, ctx);
// Recorded, but not yet in the session file: history is not intact, so it still passes.
assert.equal(await call('c2'), undefined, 'unverifiable history passes');
await appendFile(session, JSON.stringify({ type: 'message', timestamp: '2099-01-01T00:00:00.000Z', message: { role: 'toolResult', toolCallId: 'c2', toolName: 'read', isError: false, content: [{ type: 'text', text: 'alpha\nbeta\n' }] } }) + '\n');
await handlers.tool_result({ type: 'tool_result', toolCallId: 'c2', toolName: 'read', input: { path: target }, content: [{ type: 'text', text: 'alpha\nbeta\n' }], isError: false }, ctx);
const blocked = await call('c3');
assert(blocked && blocked.block === true && /byte-identical/.test(blocked.reason), JSON.stringify(blocked));
// A slice and a changed file pass.
assert.equal(await handlers.tool_call({ type: 'tool_call', toolCallId: 'c4', toolName: 'read', input: { path: target, offset: 1 } }, ctx), undefined);
await writeFile(target, 'alpha\nbeta\ngamma\n');
assert.equal(await call('c5'), undefined, 'changed file passes');
console.log(JSON.stringify({ ok: true }));
"""
        # OMP is deliberately absent: it supersedes the earlier read result in the session the
        # moment a re-read is attempted (observed live 2026-09-06), so a block there would leave
        # the model with neither copy. OMP dedups re-reads natively.
        for extension in (REPO / "home/dot_pi/agent/exact_extensions/read-gate.ts",):
            with self.subTest(extension=str(extension.relative_to(REPO))):
                result = subprocess.run(
                    ["node", "--input-type=module", "-e", script, str(extension), str(REPO)],
                    cwd=str(REPO),
                    capture_output=True,
                    text=True,
                    env=hook_env(),
                )
                self.assertEqual(result.returncode, 0, result.stderr[-2000:])
                self.assertIn('{"ok":true}', result.stdout)

    def test_pi_read_supersede_extension_replaces_older_reads_with_a_cache_guard(self):
        script = r"""
import assert from 'node:assert/strict';
const mod = await import(process.argv[1]);
const { supersedeReads } = mod;
const read = (id, path) => ({ role: 'assistant', content: [{ type: 'toolCall', id, name: 'read', arguments: { path } }] });
const result = (id, text) => ({ role: 'toolResult', toolCallId: id, toolName: 'read', content: [{ type: 'text', text }] });
const notice = '[Superseded by a newer read of this file]';
// Two reads of the same file, small suffix: the older one is superseded, the newest kept.
let msgs = [read('a', '/f'), result('a', 'v1'), { role: 'user', content: 'edit it' }, read('b', '/f'), result('b', 'v2')];
let out = supersedeReads(msgs, 1000, 900);
assert.equal(out[1].content[0].text, notice); assert.equal(out[4].content[0].text, 'v2');
assert.equal(msgs[1].content[0].text, 'v1', 'input untouched');
// Different files are independent; skill:// style URIs are exempt.
assert.equal(supersedeReads([read('a', '/f'), result('a', 'v1'), read('b', '/g'), result('b', 'w')], 1000, 900), undefined);
assert.equal(supersedeReads([read('a', 'skill://x'), result('a', 'v1'), read('b', 'skill://x'), result('b', 'v2')], 1000, 900), undefined);
// Large suffix after the older read: cache guard keeps it unless the session idled 90 minutes.
const big = { role: 'user', content: 'x'.repeat(40000) };
msgs = [read('a', '/f'), result('a', 'v1'), big, read('b', '/f'), result('b', 'v2')];
assert.equal(supersedeReads(msgs, 1000, 900), undefined);
assert.equal(supersedeReads(msgs, 100 * 60_000, 0)[1].content[0].text, notice);
// Idempotent on an already superseded message.
assert.equal(supersedeReads(supersedeReads([read('a', '/f'), result('a', 'v1'), read('b', '/f'), result('b', 'v2')], 1000, 900), 1000, 900), undefined);
// The extension registers a context handler that returns the rewritten list.
const handlers = {}; await mod.default({ on(k, v) { handlers[k] = v } });
const res = await handlers.context({ type: 'context', messages: [read('a', '/f'), result('a', 'v1'), read('b', '/f'), result('b', 'v2')] });
assert.equal(res.messages[1].content[0].text, notice);
console.log(JSON.stringify({ ok: true }));
"""
        extension = REPO / "home/dot_pi/agent/exact_extensions/read-supersede.ts"
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(extension)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=hook_env(),
        )
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        self.assertIn('{"ok":true}', result.stdout)

    def test_review_cleanroom_and_utf16_context_state_table(self):
        script = r"""
import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from executable_session_context import neutral_review_spec,context_for_harness
import os
with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp); a=d/'alpha.txt'; b=d/'beta.txt'
    # All supported ATX equivalents strip conclusions; ordinary mentions stay intact.
    for heading in ['findings:', 'VERDICT', '# Findings', '###### Verified facts: ###', '  ## Inline comments ##']:
        out=neutral_review_spec('target: PR 1\n'+heading+'\nOLD_CONCLUSION',a)
        assert 'OLD_CONCLUSION' not in out,heading
        assert 'target: PR 1' in out
    for heading in ['findings are expected', '####### Findings', '#Findings', 'verify findings before publishing']:
        assert 'PRESERVED' in neutral_review_spec(heading+'\nPRESERVED',a),heading
os.environ['AGENT_HOOK_HARNESS']='cursor'
assert context_for_harness(['😀'*5000],[])=='😀'*5000
assert context_for_harness(['😀'*5000+'x'],[(0,'Read complete artifact at /tmp/example')])=='Read complete artifact at /tmp/example'
try:
    context_for_harness(['😀'*5000+'x'],[])
except ValueError:
    pass
else:
    raise AssertionError('oversized mandatory instructions were silently accepted')
os.environ['AGENT_HOOK_HARNESS']='other'
assert context_for_harness(['😀'*5000+'x'],[(0,'pointer')])=='😀'*5000+'x'
print('clean-room/context table passed')
"""
        result = subprocess.run([sys.executable, "-c", script, str(HOOKS)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("table passed", result.stdout)

    def test_pi_and_omp_context_permission_and_recall_transitions(self):
        script = r"""
    import assert from 'node:assert/strict';
    import {realpath,mkdtemp,mkdir,copyFile,chmod,writeFile,readFile,unlink,rename} from 'node:fs/promises';
    import {join} from 'node:path';
    const root=process.argv[1];
    const extension=process.argv[2];
    const tmp=await realpath(await mkdtemp('/tmp/setup-hooks-runtime-'));
    const hooks=join(tmp,'.agents/hooks');await mkdir(hooks,{recursive:true});
    for(const [src,dst] of [['executable_session_context.py','session_context.py'],['executable_perturn_recall.py','perturn_recall.py'],['hook_common.py','hook_common.py']]){
     await copyFile(join(root,'home/exact_dot_agents/exact_hooks',src),join(hooks,dst));await chmod(join(hooks,dst),0o755);
    }
    process.env.HOME=tmp;process.env.AI_AGENT_DEPTH='fast';process.env.AGENT_MEMORY_SPEC_ROOT=join(tmp,'specs');process.env.AGENT_MEMORY_MIRROR_ROOT=join(tmp,'mirror');process.env.XDG_CONFIG_HOME=join(tmp,'.config');
    const bin=join(tmp,'bin');await mkdir(bin);process.env.PATH=`${bin}:${process.env.PATH}`;
    await writeFile(join(bin,'gh'),'#!/bin/sh\nexit 1\n');await chmod(join(bin,'gh'),0o755);
    const searchLog=join(tmp,'search.jsonl');const rowsPath=join(tmp,'rows.json');
    await writeFile(rowsPath,JSON.stringify([{id:'A',title:'UNJUDGED_TITLE',body:'UNJUDGED_BODY'.repeat(50),scope:'universal',bm25_score:-10,cosine_score:0.8}]));
    await writeFile(join(bin,',ai-kb'),`#!/usr/bin/env python3\nimport json,sys\nif sys.argv[1:2]==['search']:\n query=sys.stdin.read()\n with open(${JSON.stringify(searchLog)},'a') as f: f.write(json.dumps({'args':sys.argv[1:],'query':query})+'\\n')\n print(open(${JSON.stringify(rowsPath)}).read())\n`);await chmod(join(bin,',ai-kb'),0o755);
    const worklog=join(tmp,'captured.jsonl');await writeFile(join(hooks,'worklog_dispatcher.sh'),`#!/usr/bin/env python3\nimport sys\nwith open(${JSON.stringify(worklog)},'a') as f:f.write(sys.stdin.read()+'\\n')\n`);await chmod(join(hooks,'worklog_dispatcher.sh'),0o755);
    await mkdir(join(tmp,'.config/tmux/agent_prompts'),{recursive:true});await writeFile(join(tmp,'.config/tmux/agent_prompts/prefix.txt'),'PREFIX_SENTINEL');
    const specDir=join(process.env.AGENT_MEMORY_SPEC_ROOT,tmp.slice(1));await mkdir(specDir,{recursive:true});
    let topic='alpha';const key='callback-session';let statusAvailable=true;let percent=5;
    async function bind(value,text='target: current task'){topic=value;await writeFile(join(specDir,`.session-topic-${key}.txt`),value);await writeFile(join(specDir,`${value}.txt`),text)}
    await bind('alpha');
    const mod=await import(extension);let handlers={};
    const api={on(k,v){handlers[k]=v},async exec(cmd,args){if(cmd===',ai-kb')return {code:0,stdout:'',killed:false};
     if(cmd===',agent-memory')return statusAvailable?{code:0,killed:false,stdout:JSON.stringify({workspace:tmp,selected_topic:topic,session_key:key,is_named_topic:true,spec_file:join(specDir,`${topic}.txt`),spec_exists:true})}:{code:1,stdout:'',killed:false};
     if(cmd==='cat'){try{return {code:0,stdout:await readFile(args[0],'utf8'),killed:false}}catch{return {code:1,stdout:'',killed:false}}}throw new Error(cmd)}};
    const ctx={cwd:tmp,getContextUsage(){return {percent}},sessionManager:{getSessionId(){return key}}};
    await mod.default(api);
    const content=async(prompt='Did you actually verify this claim?')=>(await handlers.before_agent_start({prompt},ctx))?.message?.content??'';
    process.env.AGENT_HOOK_CONTEXT='0';assert.equal(await content(),'');await handlers.session_compact({},ctx);percent=80;assert.equal(await content(),'');
    await handlers.tool_result({toolName:'bash',input:{command:'echo captured'},content:[{text:'captured'}]},ctx);
    delete process.env.AGENT_HOOK_CONTEXT;let enabled=await content();assert(enabled.includes('PREFIX_SENTINEL'));assert(enabled.includes('User correction signal'));assert(enabled.includes(',agent-memory note anti_pattern'));assert(enabled.includes('Do not launch re-verification'));assert(!enabled.includes('UNJUDGED')); 
    for(const sentinel of ['_no_session_context','alpha.no_context']){await writeFile(join(specDir,sentinel),'');assert.equal(await content(),'');await handlers.session_compact({},ctx);assert.equal(await content(),'');await unlink(join(specDir,sentinel));assert((await content()).includes('PREFIX_SENTINEL'))}
    await rename(join(hooks,'session_context.py'),join(hooks,'saved_context.py'));
    await handlers.session_start({},ctx);await writeFile(join(specDir,'alpha.no_context'),'');assert.equal(await content(),'');await unlink(join(specDir,'alpha.no_context'));assert((await content()).includes('User correction signal'));assert(!await readFile(searchLog,'utf8').catch(()=>''),'fast fallback searched');
    // Balanced fallback preserves retrieval while staging full rows and never admitting them.
    process.env.AI_AGENT_DEPTH='balanced';handlers={};await mod.default(api);let first=await content('short');assert(first.includes('candidates staged'));assert(!first.includes('UNJUDGED'));assert.equal(JSON.parse(await readFile(join(specDir,`.recall-candidates-${key}.json`),'utf8'))[0].body,'UNJUDGED_BODY'.repeat(50));assert.equal(await readFile(join(specDir,`.recall-seen-${key}.json`),'utf8').catch(()=>''),'');
    assert(!(await content('short')).includes('candidates staged'));
    await writeFile(rowsPath,JSON.stringify([{id:'B',title:'prompt-specific',body:'B',cosine_score:0.8}]));
    assert(!(await content('A substantive prompt for memory')).includes('candidates staged'));
    assert.deepEqual(JSON.parse(await readFile(join(specDir,`.recall-candidates-${key}.json`),'utf8')).map(r=>r.id),['A','B']);
    await writeFile(rowsPath,JSON.stringify([{id:'A',title:'UNJUDGED_TITLE',body:'body',bm25_score:-10,cosine_score:0.8}]));
    await bind('beta');assert((await content('short')).includes('candidates staged'));assert(!(await content('short')).includes('candidates staged'));await bind('alpha');assert((await content('short')).includes('candidates staged'));
    await writeFile(rowsPath,'[]');await bind('beta');assert(!(await content('short')).includes('candidates staged'));await writeFile(rowsPath,JSON.stringify([{id:'A',title:'UNJUDGED_TITLE',body:'body',bm25_score:-10,cosine_score:0.8}]));await bind('alpha');assert((await content('short')).includes('candidates staged'));
    await writeFile(rowsPath,'[]');await bind('beta');await content('short');await writeFile(rowsPath,JSON.stringify([{id:'A',title:'UNJUDGED_TITLE',body:'body',bm25_score:-10,cosine_score:0.8}]));assert((await content('A substantive prompt for memory')).includes('candidates staged'));assert(!(await content('A substantive prompt for memory')).includes('candidates staged'));
    // Clean-room fallback must not send prior conclusions as a BM25 query.
    const before=(await readFile(searchLog,'utf8')).split('\n').filter(Boolean).length;
    await bind('review-case','target: ordinary\n## Findings\nOLD_CONCLUSION');assert(!(await content('short')).includes('UNJUDGED'));
    await bind('other-case','target: PR 123\n## Findings\nOLD_CONCLUSION');await content('short');
    assert.equal((await readFile(searchLog,'utf8')).split('\n').filter(Boolean).length,before);
    // Children must neither retrieve nor receive root workflow hints.
    const searchesBeforeLeaf=await readFile(searchLog,'utf8');
    process.env.PI_SUBAGENT_CHILD='1';assert.equal(await content(),'');delete process.env.PI_SUBAGENT_CHILD;
    process.env.COPILOT_AGENT_SESSION_ID='parent';assert.equal(await content(),'');delete process.env.COPILOT_AGENT_SESSION_ID;
    assert.equal(await handlers.before_agent_start({prompt:'Did you verify?',systemPrompt:'[DELEGATION BOUNDARY]'},ctx),undefined);
    assert.equal(await readFile(searchLog,'utf8'),searchesBeforeLeaf);
    // A successful empty hook is not a disabled hook.
    await writeFile(join(hooks,'session_context.py'),'#!/usr/bin/env python3\nprint("{}")\n');await chmod(join(hooks,'session_context.py'),0o755);await handlers.session_start({},ctx);assert((await content()).includes('User correction signal'));
    // Explicit disable remains effective if the status CLI is unavailable.
    statusAvailable=false;process.env.AGENT_HOOK_CONTEXT='off';assert.equal(await content(),'');delete process.env.AGENT_HOOK_CONTEXT;
    for(let i=0;i<1000;i++){if((await readFile(worklog,'utf8').catch(()=>'')))break;await new Promise(r=>setTimeout(r,10))}assert((await readFile(worklog,'utf8')).includes('captured'));
    console.log(JSON.stringify({extension,cases:27,worklogCaptured:true,temporaryHome:tmp}));
    """
        for extension in (
            REPO / "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts",
            REPO / "home/dot_omp/private_agent/extensions/ai-kb-recall.ts",
        ):
            with self.subTest(extension=str(extension)):
                result = subprocess.run(
                    ["node", "--no-warnings", "--input-type=module", "-e", script, str(REPO), str(extension)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)["worklogCaptured"])

    def test_pi_and_omp_partial_install_keeps_independent_callbacks(self):
        script = r"""
import assert from 'node:assert/strict';
import {realpath,mkdtemp,mkdir,copyFile,chmod,writeFile,readFile,rename} from 'node:fs/promises';
import {join} from 'node:path';
const root=process.argv[1], extension=process.argv[2];
const mod=await import(extension);
let cases=0;
for(const failure of ['absent','failed','killed','throws']){
 for(const helper of ['available','missing']){
 for(const review of [false,true]){
  const tmp=await realpath(await mkdtemp('/tmp/hooks-partial-install-'));
  const hooks=join(tmp,'.agents/hooks');await mkdir(hooks,{recursive:true});
  for(const [src,dst] of [['executable_session_context.py','session_context.py'],['hook_common.py','hook_common.py']]){await copyFile(join(root,'home/exact_dot_agents/exact_hooks',src),join(hooks,dst));await chmod(join(hooks,dst),0o755)}
  if(helper==='missing')await rename(join(hooks,'session_context.py'),join(hooks,'disabled.py'));
  process.env.HOME=tmp;process.env.AI_AGENT_DEPTH='deep';process.env.AI_EMBED_WARM='1';process.env.AGENT_MEMORY_SPEC_ROOT=join(tmp,'specs');process.env.AGENT_MEMORY_MIRROR_ROOT=join(tmp,'mirror');process.env.XDG_CONFIG_HOME=join(tmp,'.config');delete process.env.AGENT_HOOK_CONTEXT;
  const specDir=join(process.env.AGENT_MEMORY_SPEC_ROOT,tmp.slice(1));await mkdir(specDir,{recursive:true});
  const key='partial';const topic=review?'review-partial':'ordinary';const specFile=join(specDir,`${topic}.txt`);await writeFile(specFile,review?'target: PR 123\n## Findings\nPRIOR_CONCLUSION':'target: current named task');await writeFile(join(specDir,`.session-topic-${key}.txt`),topic);
  const prefixPath=join(tmp,'.config/tmux/agent_prompts/prefix.txt');await mkdir(join(tmp,'.config/tmux/agent_prompts'),{recursive:true});await writeFile(prefixPath,'PREFIX_PARTIAL');
  const bin=join(tmp,'bin');await mkdir(bin);const log=join(tmp,'search.jsonl'), worklog=join(tmp,'worklog.jsonl');process.env.PATH=`${bin}:${process.env.PATH}`;
  for(const [file,text] of [['gh','#!/bin/sh\nexit 1\n'],[',ai-kb',`#!/usr/bin/env python3\nimport sys\nwith open(${JSON.stringify(log)},'a') as f:f.write('SEARCH_ATTEMPT\\n')\nprint('[]')\n`]]){await writeFile(join(bin,file),text);await chmod(join(bin,file),0o755)}
  await writeFile(join(hooks,'worklog_dispatcher.sh'),`#!/usr/bin/env python3\nimport sys\nwith open(${JSON.stringify(worklog)},'a') as f:f.write(sys.stdin.read()+'\\n')\n`);await chmod(join(hooks,'worklog_dispatcher.sh'),0o755);
  let probeCount=0, available=false;const handlers={};
  const api={on(k,v){handlers[k]=v},async exec(cmd,args){
   if(cmd===',ai-kb'){probeCount++;if(available)return {code:0,killed:false,stdout:''};if(failure==='throws')throw new Error('ENOENT');return {code:failure==='absent'?127:failure==='failed'?1:0,killed:failure==='killed',stdout:''}}
   if(cmd===',agent-memory')return {code:0,killed:false,stdout:JSON.stringify({workspace:tmp,selected_topic:topic,session_key:key,is_named_topic:true,spec_file:specFile,spec_exists:true})};
   if(cmd==='cat')return {code:0,killed:false,stdout:await readFile(args[0],'utf8')};throw new Error(cmd)
  }};
  await mod.default(api);
  assert.equal(typeof handlers.before_agent_start,'function',`${failure}/${helper}: context callback missing`);
  assert.equal(typeof handlers.tool_result,'function',`${failure}/${helper}: worklog callback missing`);
  const ctx={cwd:tmp,getContextUsage(){return {percent:5}},sessionManager:{getSessionId(){return key}}};
  await handlers.session_start({},ctx);
  const run=async()=> (await handlers.before_agent_start({prompt:'Did you actually verify this claim?'},ctx))?.message?.content??'';
  let first=await run();assert(!first.includes('PREFIX_PARTIAL'));assert(first.includes('User correction signal'));assert(!first.includes('PRIOR_CONCLUSION'));
  if(helper==='available')assert(first.includes(review?'target: PR 123':'target: current named task'));
  await handlers.session_compact({},ctx);assert((await run()).includes('PREFIX_PARTIAL'));
  process.env.AGENT_HOOK_CONTEXT='off';assert.equal(await run(),'');
  await handlers.tool_result({toolName:'bash',input:{command:'safe'},content:[{text:'WORKLOG_CAPTURED'}]},ctx);
  delete process.env.AGENT_HOOK_CONTEXT;assert((await run()).includes('User correction signal'));
  // Availability is sampled once; later installation must not silently reopen recall.
  available=true;await run();assert.equal(probeCount,1);
  assert.equal(await readFile(log,'utf8').catch(()=>''),'');
  for(let i=0;i<1000;i++){if(await readFile(worklog,'utf8').catch(()=>''))break;await new Promise(r=>setTimeout(r,10))}
  assert((await readFile(worklog,'utf8')).includes('WORKLOG_CAPTURED'));
  cases++;
 }
 }
}
console.log(JSON.stringify({extension,cases}));
"""
        for extension in (
            REPO / "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts",
            REPO / "home/dot_omp/private_agent/extensions/ai-kb-recall.ts",
        ):
            with self.subTest(extension=str(extension)):
                result = subprocess.run(
                    ["node", "--no-warnings", "--input-type=module", "-e", script, str(REPO), str(extension)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["cases"], 16)

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
            assert "k-agent-smol" in context
            assert "final learning batch" in context
            assert "When delegation is forbidden, use the skill's inline fallback" in context
            assert "No Named Topic Active" not in context

    def test_session_context_warmstart_stages_complete_candidates_for_named_topic(self):
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
                        "id": "local-capsule",
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

            assert "### ,ai-kb candidates staged" in context
            assert "Local capsule that should surface" not in context
            assert "B" * 100 not in context
            rows = json.loads((spec_dir / ".recall-candidates-warm-session.json").read_text())
            assert rows[0]["body"] == "B" * 400
            assert not (spec_dir / ".recall-seen-warm-session.json").exists()

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
                        "id": "foreign",
                        "title": "Foreign project capsule",
                        "body": "from another repo",
                        "kind": "gotcha",
                        "scope": "project",
                        "workspace_path": "/some/other/repo",
                    },
                    {
                        "id": "universal",
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
            assert "Universal principle capsule" not in context
            rows = json.loads((spec_dir / ".recall-candidates-warm-gate-session.json").read_text())
            assert [row["id"] for row in rows] == ["universal"]

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
            env = make_aikb_stub(
                Path(tmp),
                [
                    {
                        "id": "capsule-b",
                        "title": "Current prompt candidate",
                        "body": "B",
                        "scope": "universal",
                        "cosine_score": 0.8,
                    }
                ],
            )
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

            assert "### ,ai-kb candidates staged" in warmstart
            assert "Conversation-scoped capsule" not in warmstart
            assert not seen_path.exists()
            assert perturn == {}
            staged = json.loads((spec_dir / ".recall-candidates-conversation-a.json").read_text())
            assert [row["id"] for row in staged] == ["capsule-a", "capsule-b"]
            assert staged[0]["body"] == "inject once"

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
            # Admission remains available inline without ordering a generic spawn or
            # falling back to a harness CLI.
            assert "inline fallback" in context
            assert "No descendant agents or harness-CLI fallback" in context
            assert "spawn a generic isolated subagent" not in context
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
        # The staged ledger dedups identical candidate sets, and the pointed marker
        # caps the pointer at one per session-topic binding: a genuinely new capsule id
        # is still staged into the candidates file for the pull path, but it does not
        # spawn another judge (one measured judge cost 36k tokens for 2 admitted lines).
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
            assert "once per session-topic binding" in first["hookSpecificOutput"]["additionalContext"]
            assert second == {}
            assert third == {}, "a new capsule id must stage silently, not re-point the same session"
            pointed = json.loads((spec_dir / ".recall-pointed-repoint-guard.json").read_text())
            assert set(pointed) == {"topic"} and pointed["topic"]
            staged_rows = json.loads((spec_dir / ".recall-candidates-repoint-guard.json").read_text())
            assert [row["id"] for row in staged_rows] == ["capsule-a", "capsule-b"]
            assert json.loads((spec_dir / ".recall-staged-repoint-guard.json").read_text()) == [
                "capsule-a",
                "capsule-b",
            ]

    def test_perturn_recall_repoints_when_the_session_rebinds_to_another_topic(self):
        # The pointer budget is per session-topic binding, not per session: rebinding the
        # session to another topic mid-way must re-point once for the new topic and then
        # go silent again. A marker keyed on the session alone would never re-point.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            binding = spec_dir / ".session-topic-rebind.txt"
            payload = {
                "conversation_id": "rebind",
                "hook_event_name": "UserPromptSubmit",
                "workspace_roots": [tmp],
                "prompt": "recall guidance for this staging test",
            }
            row = {
                "id": "capsule-a",
                "title": "First staged capsule",
                "kind": "gotcha",
                "scope": "project",
                "workspace_path": workspace,
                "cosine_score": 0.8,
            }
            env = make_aikb_stub(Path(tmp), [row])

            binding.write_text("topic-alpha\n", encoding="utf-8")
            first = run_perturn_recall(tmp, payload, env)
            assert "### ,ai-kb candidates staged" in first["hookSpecificOutput"]["additionalContext"]
            assert "topic-alpha.txt" in first["hookSpecificOutput"]["additionalContext"]
            assert json.loads((spec_dir / ".recall-pointed-rebind.json").read_text()) == {"topic": "topic-alpha"}

            binding.write_text("topic-beta\n", encoding="utf-8")
            second = run_perturn_recall(tmp, payload, env)
            assert "hookSpecificOutput" in second, second
            assert "topic-beta.txt" in second["hookSpecificOutput"]["additionalContext"], second
            assert json.loads((spec_dir / ".recall-pointed-rebind.json").read_text()) == {"topic": "topic-beta"}

            assert run_perturn_recall(tmp, payload, env) == {}
            binding.write_text("topic-alpha\n", encoding="utf-8")
            assert "topic-alpha.txt" in run_perturn_recall(tmp, payload, env)["additional_context"]

    def test_perturn_recall_keeps_ids_unstaged_when_the_pointed_marker_cannot_be_written(self):
        # If the staged ledger were committed before the marker, a failed marker write would
        # leave the ids "already staged" with no pointer ever sent: the session's one pointer
        # consumed for nothing. A directory at the marker path forces the write to fail.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp).resolve())
            spec_dir = SPEC_ROOT / workspace.lstrip("/")
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / ".recall-pointed-marker-fails.json").mkdir()
            payload = {
                "conversation_id": "marker-fails",
                "hook_event_name": "UserPromptSubmit",
                "workspace_roots": [tmp],
                "prompt": "recall guidance for this staging test",
            }
            row = {
                "id": "capsule-a",
                "title": "First staged capsule",
                "kind": "gotcha",
                "scope": "project",
                "workspace_path": workspace,
                "cosine_score": 0.8,
            }
            env = make_aikb_stub(Path(tmp), [row])
            assert run_perturn_recall(tmp, payload, env) == {}
            assert not (spec_dir / ".recall-staged-marker-fails.json").exists(), "ids must stay unstaged"
            (spec_dir / ".recall-pointed-marker-fails.json").rmdir()
            recovered = run_perturn_recall(tmp, payload, env)
            assert "### ,ai-kb candidates staged" in recovered["hookSpecificOutput"]["additionalContext"]

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

    def test_session_context_warmstart_preserves_judge_owned_seen_ids(self):
        # A resume/compact fires a second warm start in the same conversation.
        # Startup must not admit any retrieved candidate or overwrite prior judge admissions.
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

            assert json.loads(seen_path.read_text()) == ["capsule-prior"]
            assert json.loads((spec_dir / ".recall-candidates-warm-union.json").read_text())[0]["id"] == "capsule-a"

    def test_pi_recall_uses_session_binding_and_stages_unadmitted_capsules(self):
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

            assert "### ,ai-kb candidates staged" in payload["first"]["message"]["content"]
            assert "Pi resume capsule" not in payload["first"]["message"]["content"]
            assert json.loads((Path(tmp) / ".recall-candidates-pi-session.json").read_text()) == rows
            assert payload.get("second") is None
            assert payload["seen"] == []
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

    def test_pi_recall_staging_contract_matches_perturn_recall(self):
        import re

        pi_extension = (REPO / "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts").read_text()
        omp_extension = (REPO / "home/dot_omp/private_agent/extensions/ai-kb-recall.ts").read_text()
        hook = (HOOKS / "executable_perturn_recall.py").read_text()

        session_context = (HOOKS / "executable_session_context.py").read_text()
        reinforcement = (HOOKS / "reinforcement.py").read_text()
        python_limit = int(re.search(r"^MAX_PREFIX_CHARS = (\d+)$", reinforcement, re.MULTILINE).group(1))
        prefix_length = len((REPO / "home/dot_config/exact_tmux/agent_prompts/prefix.txt").read_text().strip())
        assert prefix_length <= python_limit
        for extension in (pi_extension, omp_extension):
            extension_limit = int(re.search(r"^const PREFIX_MAX_CHARS = (\d+)$", extension, re.MULTILINE).group(1))
            assert extension_limit == python_limit

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
        assert '.recall-candidates-{session_key_value}.json"' in session_context
        assert '.recall-staged-{session_key_value}.json"' in session_context
        for extension in (pi_extension, omp_extension):
            assert ".recall-candidates-${sessionId}.json" in extension
            assert ".recall-staged-${sessionId}.json" in extension
            assert "stageCandidates(rows, status.spec_file, status.session_key)" in extension
            assert "Relevant Learnings for this request" not in extension

        # Keyless-session guard parity: both sides stage nothing without a session key.
        assert 'pointer = stage_candidates(rows, seen, spec_path, key) if key else ""' in hook
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
            hook_value = token(session_context, name)
            assert token(pi_extension, f"const {name}") == hook_value
            assert token(omp_extension, f"const {name}") == hook_value

    def test_staging_binding_and_warm_cache_state_table(self):
        script = r"""
import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from executable_session_context import stage_candidates,neutral_review_spec,context_for_harness
import os
with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp); a=d/'alpha.txt'; b=d/'beta.txt'
    A={'id':'A','title':'warm','body':'full-body'*100}; B={'id':'B','title':'current'}
    def step(topic,rows,expected_pointer,expected_ids=None,**kwargs):
        out=stage_candidates(rows,set(),topic,'session',**kwargs)
        assert bool(out)==expected_pointer,(topic,rows,out)
        if expected_ids is not None:
            assert [r['id'] for r in json.loads((d/'.recall-candidates-session.json').read_text())]==expected_ids
    step(a,[A],True,['A'],warm_start=True)
    step(a,[B],False,['A','B'])
    assert json.loads((d/'.recall-candidates-session.json').read_text())[0]==A
    step(b,[],False)
    step(a,[A],True,['A'])
    step(b,[],False)
    step(b,[B],True,['B'])
    step(b,[B],False,['B'])
    step(a,[B],True,['A','B'])
    # A judge's admission filters both retrieval lanes without mutating the seen file.
    (d/'.recall-seen-session.json').write_text('["A"]')
    stage_candidates([B],{'A'},a,'session')
    # Force a fresh row to exercise same-binding rewrite and both-lane admission filtering.
    stage_candidates([{'id':'C'}],{'A'},a,'session')
    assert [r['id'] for r in json.loads((d/'.recall-candidates-session.json').read_text())]==['C']
    assert (d/'.recall-seen-session.json').read_text()=='["A"]'
    # Missing/bad warm state cannot suppress current retrieval or import another topic.
    (d/'.recall-warm-session.json').write_text('invalid')
    step(b,[B],True,['B'])
    (d/'.recall-warm-session.json').unlink()
    step(a,[A],True,['A'])
    # A warm-cache write failure emits no partial pointer; next attempt remains eligible.
    (d/'.recall-warm-failed.json').mkdir()
    assert not stage_candidates([A],set(),a,'failed',warm_start=True)
    assert not (d/'.recall-candidates-failed.json').exists()
    (d/'.recall-warm-failed.json').rmdir()
    assert stage_candidates([A],set(),a,'failed',warm_start=True)
    assert not stage_candidates([A],set(),a,'')
    assert stage_candidates([{'id':str(i)} for i in range(8)],set(),a,'bounded',warm_start=True)
    assert len(json.loads((d/'.recall-warm-bounded.json').read_text())['rows'])==3
    # All supported ATX equivalents strip conclusions; ordinary mentions stay intact.
    for heading in ['findings:', 'VERDICT', '# Findings', '###### Verified facts: ###', '  ## Inline comments ##']:
        out=neutral_review_spec('target: PR 1\n'+heading+'\nOLD_CONCLUSION',a)
        assert 'OLD_CONCLUSION' not in out,heading
        assert 'target: PR 1' in out
    for heading in ['findings are expected', '####### Findings', '#Findings', 'verify findings before publishing']:
        assert 'PRESERVED' in neutral_review_spec(heading+'\nPRESERVED',a),heading
os.environ['AGENT_HOOK_HARNESS']='cursor'
assert context_for_harness(['😀'*5000],[])=='😀'*5000
assert context_for_harness(['😀'*5000+'x'],[(0,'Read complete artifact at /tmp/example')])=='Read complete artifact at /tmp/example'
try:
    context_for_harness(['😀'*5000+'x'],[])
except ValueError:
    pass
else:
    raise AssertionError('oversized mandatory instructions were silently accepted')
os.environ['AGENT_HOOK_HARNESS']='other'
assert context_for_harness(['😀'*5000+'x'],[(0,'pointer')])=='😀'*5000+'x'
print('binding/warm-cache/clean-room table passed')
"""
        result = subprocess.run([sys.executable, "-c", script, str(HOOKS)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("table passed", result.stdout)


class PublishGateTests(unittest.TestCase):
    """publish_gate.py: leaf publication is denied, root publication gets the SOP 3.8 checklist."""

    def bash(self, command: str, **extra) -> dict:
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "hook_event_name": "PreToolUse"}
        payload.update(extra)
        return payload

    def test_root_publication_rides_checklist_without_a_permission_decision(self):
        for command in (
            "gh pr create --title x --body-file /tmp/b.md",
            "gh -R owner/repo issue comment 3 -b $'ok'",
            "gh api repos/o/r/pulls/1/comments -f body=$'Text.' -F in_reply_to=5",
            "gh api graphql -f query='mutation { addPullRequestReviewThread(input: {}) { thread { id } } }'",
            "gh pr review 12 --approve -b 'Looks good.'",
            "timeout 120 gh pr comment 7 -b 'done'",
            "cd /tmp/wt && env FOO=1 gh issue comment 2 -b 'ok'",
            "gh api -X GET repos/o/r/pulls/1 --jq .title; gh api repos/o/r/issues/1/comments -f body='x'",
            "gws gmail +send --to a@example.com --subject s --body b",
            "gws chat +send --space spaces/AAA --text hi",
        ):
            out = run_hook("executable_publish_gate.py", self.bash(command))
            specific = out["hookSpecificOutput"]
            self.assertIn("Publication gate (SOP 3.8)", specific["additionalContext"], command)
            self.assertIn("k-communication", specific["additionalContext"], command)
            self.assertNotIn("permissionDecision", specific, command)
            self.assertNotIn("decision", out, command)

    def test_read_only_and_non_publication_commands_are_silent(self):
        for command in (
            "gh pr view 12 --json title,body",
            "GH_PAGER=cat gh api -X GET repos/o/r/contents/p -F ref=main",
            "gh api --paginate repos/o/r/pulls/1/comments",
            'gh api graphql -f query=\'query { repository(owner:"o", name:"r") { issueTypes(first: 5) { nodes { name } } } }\' -X GET',
            'GH_PAGER=cat gh api graphql -H "GraphQL-Features:issue_types" -f query=\'query { repository(owner:"o", name:"r") { issueTypes(first: 50) { nodes { id name } } } }\'',
            'gh api graphql -f query=\'{ repository(owner:"org",name:"repo") { issue(number:3) { id } } }\'',
            "git push --force-with-lease origin feat",
            "gws gmail +triage",
            "rg 'gh pr comment' docs/",
            'grep -rn "gh issue create" home/ | head',
            "echo gh pr create --fill",
        ):
            self.assertEqual(run_hook("executable_publish_gate.py", self.bash(command)), {}, command)
        self.assertEqual(
            run_hook(
                "executable_publish_gate.py",
                {"tool_name": "mcp__slack__slack_read_thread", "tool_input": {"channel_id": "C1", "thread_ts": "1.2"}},
            ),
            {},
        )

    def test_delegated_leaf_publication_is_denied(self):
        # Claude Code child: the payload carries `agent_id`.
        out = run_hook("executable_publish_gate.py", self.bash("gh pr comment 12 -b 'done'", agent_id="a-1"))
        self.assertEqual(out["decision"], "block")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("delegated leaf", out["hookSpecificOutput"]["permissionDecisionReason"])
        # Claude Code child calling the Slack MCP send tool.
        out = run_hook(
            "executable_publish_gate.py",
            {
                "tool_name": "mcp__slack__slack_send_message",
                "tool_input": {"channel_id": "C1", "message": "hi"},
                "agent_id": "a-2",
            },
        )
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("slack_send_message", out["hookSpecificOutput"]["permissionDecisionReason"])
        # Copilot sub-agent: the parent session env marks the leaf.
        out = run_hook(
            "executable_publish_gate.py",
            self.bash("gh issue create --title t --body b"),
            env=keep_parent_env("parent-session"),
        )
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_codex_output_mode_keeps_only_hook_specific_output(self):
        env = dict(os.environ)
        env["AGENT_HOOK_OUTPUT"] = "hook_specific"
        out = run_hook("executable_publish_gate.py", self.bash("gh pr edit 3 --body x", agent_id="a-3"), env=env)
        self.assertEqual(list(out), ["hookSpecificOutput"])
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_root_ask_mode_and_off_switch(self):
        env = dict(os.environ)
        env["AGENT_PUBLISH_GATE_ROOT"] = "ask"
        out = run_hook("executable_publish_gate.py", self.bash("gh pr create --fill"), env=env)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertIn("Publication gate (SOP 3.8)", out["hookSpecificOutput"]["additionalContext"])
        env = dict(os.environ)
        env["AGENT_PUBLISH_GATE"] = "off"
        self.assertEqual(
            run_hook("executable_publish_gate.py", self.bash("gh pr create --fill", agent_id="a-4"), env=env), {}
        )

    def test_claude_settings_wire_publish_gate_for_bash_and_slack(self):
        import re

        for name in ("settings.personal.json", "settings.work.json"):
            settings = json.loads((REPO / "home" / "dot_claude" / name).read_text())
            groups = [
                group
                for group in settings["hooks"]["PreToolUse"]
                if any(hook["command"].endswith("publish_gate.py") for hook in group["hooks"])
            ]
            self.assertEqual(len(groups), 1, name)
            matcher = groups[0]["matcher"]
            for tool in ("Bash", "mcp__slack__slack_send_message", "mcp__slack__slack_add_reaction"):
                self.assertTrue(re.fullmatch(matcher, tool), (name, matcher, tool))
            self.assertIsNone(re.fullmatch(matcher, "Read"), (name, matcher))


class BandGateTests(unittest.TestCase):
    """The pre-tool-use gate that pins a delegated agent to its category's band.

    Each harness gets its own request and response shape, all four verified against the running
    binaries, so the adapters are tested against a fixed projection rather than the deployed one:
    these assertions are about the wire contract, not about today's model picks. The rows carry
    `category`, the only band field the gate reads (projection schema >= 1.2.0), so an
    `implement`-bound row here really does take the lane pass-through path. The claude_code
    `searcher` row deliberately keeps the `haiku` alias no deployed category projects onto, so the
    bottom rung of the rank ladder stays covered.
    """

    PROJECTION = {
        "harnesses": {
            "claude_code": {
                "agents": {
                    "Explore": {
                        "category": "research",
                        "model": "claude-fable-5-1",
                        "alias": "fable",
                        "effort": "high",
                    },
                    "searcher": {
                        "category": "mechanical",
                        "model": "claude-haiku-4-5",
                        "alias": "haiku",
                        "effort": "low",
                    },
                    "k-agent-reviewer": {
                        "category": "review",
                        "model": "claude-fable-5-1",
                        "alias": "fable",
                        "effort": "high",
                    },
                    "k-agent-adversarial-verifier": {
                        "category": "refute",
                        "model": "claude-fable-5-1",
                        "alias": "fable",
                        "effort": "high",
                    },
                    "k-agent-smol": {
                        "category": "memory",
                        "model": "claude-sonnet-5",
                        "alias": "sonnet",
                        "effort": "low",
                    },
                    "general-purpose": {
                        "category": "implement",
                        "model": "claude-opus-5",
                        "alias": "opus",
                        "effort": "high",
                    },
                }
            },
            "cursor": {"agents": {"bugbot": {"category": "review", "model": "claude-opus-5-high", "effort": "high"}}},
            "codex": {"agents": {"explorer": {"category": "research", "model": "gpt-5.4", "effort": "high"}}},
            "copilot": {
                "agents": {
                    "explore": {
                        "category": "research",
                        "model": "gpt-5.3-codex",
                        "effort": "high",
                    }
                }
            },
            "pi": {
                "agents": {
                    "explorer": {
                        "category": "research",
                        "model": "anthropic/claude-fable-5.1:high",
                        "effort": "high",
                    },
                    "worker": {
                        "category": "mechanical",
                        "model": "openrouter/z-ai/glm-5.3-flash:high",
                        "effort": "high",
                    },
                    "k-agent-adversarial-verifier": {
                        "category": "refute",
                        "model": "openrouter/openai/gpt-5.6-sol:xhigh",
                        "effort": "xhigh",
                    },
                }
            },
            "gemini": {"agents": {"codebase_investigator": {"category": "research", "model": "gemini-3.8-flash"}}},
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
                "AGENT_BAND_CLAUDE_ROUTES",
                "AGENT_BAND_SUBSCRIPTION",
                "AGENT_BAND_CODEX_ROUTES",
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

    def test_codex_namespaced_spawn_tool_name_is_still_gated(self):
        # Live Codex payloads name the tool "collaborationspawn_agent" (probed 2026-09-06).
        answer = self.gate(
            "codex",
            {"tool_name": "collaborationspawn_agent", "tool_input": {"agent_type": "explorer", "message": "go"}},
        )
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertIn("model", answer["hookSpecificOutput"]["updatedInput"])

    def test_SHOULD_require_fresh_exact_subscription_claude_profiles(self):
        projection = {
            "harnesses": {
                "codex": {"agents": {"worker": {"category": "implement", "model": "gpt-cheap", "effort": "high"}}}
            }
        }
        payload = {"tool_name": "Agent", "tool_input": {"subagent_type": "worker", "prompt": "edit", "model": "fable"}}
        env = {
            "AGENT_BAND_SCHEMA_HARNESS": "codex",
            "AGENT_BAND_SUBSCRIPTION": "codex",
            "AGENT_BAND_CLAUDE_ROUTES": json.dumps({"worker": "gpt-cheap@lane-high"}),
        }
        good = self.gate("claude_code", payload, projection, env)["hookSpecificOutput"]
        self.assertEqual(good["updatedInput"], {"subagent_type": "worker", "prompt": "edit"})
        for changed in (
            {"AGENT_BAND_CLAUDE_ROUTES": ""},
            {"AGENT_BAND_CLAUDE_ROUTES": "[]"},
            {"AGENT_BAND_CLAUDE_ROUTES": '{"worker":"gpt-cheap@lane-low"}'},
            {"AGENT_BAND_MODEL_OVERRIDE": "root"},
            {"CLAUDE_CODE_SUBAGENT_MODEL": "root"},
        ):
            with self.subTest(changed=changed):
                result = self.gate("claude_code", payload, projection, {**env, **changed})["hookSpecificOutput"]
                self.assertEqual(result["permissionDecision"], "deny")
        for patch in ({"resume": "old"}, {"fork_context": True}):
            result = self.gate(
                "claude_code", {**payload, "tool_input": {**payload["tool_input"], **patch}}, projection, env
            )
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_openrouter_claude_rejects_the_refute_effort_substitution(self):
        result = self.gate(
            "claude_code",
            {
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "k-agent-adversarial-verifier", "prompt": "challenge"},
            },
            override={
                "AGENT_BAND_SCHEMA_HARNESS": "pi",
                "AGENT_BAND_MODEL_FORMAT": "openrouter-preset",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "openai/gpt-5.6-sol@preset/effort-high",
            },
        )["hookSpecificOutput"]
        self.assertEqual(result["permissionDecision"], "deny")
        self.assertNotIn("updatedInput", result)

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

    def test_claude_clamps_an_upward_alias_escape_to_the_band_alias(self):
        # Tier ladder: `fable` T1 (research / review / orchestrate) is above `opus` T2 (implement),
        # which is above `sonnet` T3 (mechanical / memory), which is above `haiku`.
        escape = self.gate(
            "claude_code",
            {"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose", "model": "fable"}},
        )
        self.assertEqual(escape["hookSpecificOutput"]["updatedInput"]["model"], "opus")
        # A strong category cannot be downgraded merely to save on its assigned judgment.
        self.assertEqual(
            self.gate(
                "claude_code",
                {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore", "model": "opus"}},
            )["hookSpecificOutput"]["updatedInput"]["model"],
            "fable",
        )

    def test_deployed_claude_projection_clamps_upward_alias_escapes(self):
        projection = json.loads((REPO / "home/dot_config/ai/readonly_agent-bands.v1.json").read_text(encoding="utf-8"))
        for agent, asked, clamped in (("cli_help", "fable", "sonnet"), ("general-purpose", "fable", "opus")):
            with self.subTest(agent=agent, asked=asked):
                answer = self.gate(
                    "claude_code",
                    {"tool_name": "Agent", "tool_input": {"subagent_type": agent, "model": asked}},
                    projection=projection,
                )
                self.assertEqual(answer["hookSpecificOutput"]["updatedInput"]["model"], clamped)
        # The capability floor matters as well as the spending ceiling.
        self.assertEqual(
            self.gate(
                "claude_code",
                {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore", "model": "opus"}},
                projection=projection,
            )["hookSpecificOutput"]["updatedInput"]["model"],
            "fable",
        )

    def test_claude_leaves_an_unqualified_call_alone_so_the_profile_keeps_the_exact_id(self):
        # The tier ladder (`fable` T1 / `opus` T2 / `sonnet` T3) is a lossy projection of the band:
        # effort inside a tier is invisible here, so writing the alias unasked would replace the
        # profile frontmatter's exact id with whatever ANTHROPIC_DEFAULT_FABLE_MODEL resolves to.
        self.assertEqual(
            self.gate("claude_code", {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore"}}),
            {},
        )

    def test_claude_clamps_an_upward_alias_escape_on_a_haiku_band_agent(self):
        # `sonnet` is not the T3 `haiku` band's alias, so it is an escape upward even though it is
        # not a different family. Comparing rank, not equality, is what catches it: an
        # `asked == alias` early return only guarded the exact alias and let every promotion above
        # it through.
        for asked in ("sonnet", "opus"):
            with self.subTest(asked=asked):
                answer = self.gate(
                    "claude_code",
                    {"tool_name": "Agent", "tool_input": {"subagent_type": "searcher", "model": asked}},
                )
                self.assertEqual(answer["hookSpecificOutput"]["updatedInput"]["model"], "haiku")

    def test_claude_SHOULD_preserve_strong_review_capability_against_a_cheaper_override(self):
        self.assertEqual(
            self.gate(
                "claude_code",
                {"tool_name": "Agent", "tool_input": {"subagent_type": "k-agent-reviewer", "model": "haiku"}},
            )["hookSpecificOutput"]["updatedInput"]["model"],
            "fable",
        )

    def test_claude_cannot_separate_bands_sharing_an_alias_and_says_so(self):
        # The retier left two residual collisions in the four-alias projection: `research`,
        # `review` and `refute` all ride T1 `fable`, and `mechanical` and `memory` both ride T3
        # `sonnet`. Inside a collision the gate sees only the alias, so an explicit
        # `model: "fable"` on the refute lane or `model: "sonnet"` on the memory lane is
        # indistinguishable from that agent's own band and passes. This is the Agent-tool alias
        # schema limit, not a gate bug; the profile frontmatter's exact id and effort are what hold
        # the band whenever no `model` argument is passed.
        for agent, asked in (("k-agent-adversarial-verifier", "fable"), ("k-agent-smol", "sonnet")):
            with self.subTest(agent=agent, asked=asked):
                self.assertEqual(
                    self.gate(
                        "claude_code",
                        {"tool_name": "Agent", "tool_input": {"subagent_type": agent, "model": asked}},
                    ),
                    {},
                )

        # The collision is real on the deployed projection, not just in this fixture: the two T3
        # bands share one alias while their efforts differ, and effort cannot ride an alias.
        deployed = json.loads((REPO / "home/dot_config/ai/readonly_agent-bands.v1.json").read_text(encoding="utf-8"))[
            "harnesses"
        ]["claude_code"]["agents"]
        mechanical = deployed["cli_help"]
        memory = deployed["k-agent-smol"]
        self.assertEqual(("mechanical", "memory"), (mechanical["category"], memory["category"]))
        self.assertEqual(mechanical["alias"], memory["alias"])
        self.assertNotEqual(mechanical["effort"], memory["effort"])

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
        # Pi rows are spelled either `openrouter/<provider>/<model>:<level>` or, for the native
        # anthropic route, `<provider>/<model>:<level>`; both have to reach OpenRouter as
        # `<provider>/<model>@preset/effort-<level>`, so the prefix strip and the suffix rewrite
        # are probed on one row each.
        route_env = {
            "AGENT_BAND_SCHEMA_HARNESS": "pi",
            "AGENT_BAND_MODEL_FORMAT": "openrouter-preset",
            "AGENT_BAND_CODEX_ROUTES": json.dumps(
                {
                    "worker": "z-ai/glm-5.3-flash@preset/effort-high",
                    "explorer": "anthropic/claude-fable-5.1@preset/effort-high",
                }
            ),
        }
        mechanical = self.gate(
            "codex",
            {"tool_name": "spawn_agent", "tool_input": {"agent_type": "worker", "message": "go"}},
            override=route_env,
        )
        updated = mechanical["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["model"], "z-ai/glm-5.3-flash@preset/effort-high")
        self.assertNotIn("reasoning_effort", updated)

        research = self.gate(
            "codex",
            {"tool_name": "spawn_agent", "tool_input": {"agent_type": "explorer", "message": "go"}},
            override=route_env,
        )
        updated = research["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["model"], "anthropic/claude-fable-5.1@preset/effort-high")
        self.assertNotIn("reasoning_effort", updated)

    def test_SHOULD_admit_only_fresh_projected_codex_openrouter_pairs(self):
        picks = {
            "worker": {"category": "implement", "model": "openrouter/openai/gpt-test:high", "effort": "high"},
            "k-agent-smol": {"category": "memory", "model": "openrouter/google/gemini-test:low", "effort": "low"},
            "explorer": {"category": "research", "model": "anthropic/strong:high", "effort": "high"},
            "k-agent-adversarial-verifier": {
                "category": "refute",
                "model": "openrouter/openai/gpt-test:xhigh",
                "effort": "xhigh",
            },
        }
        projection = {"harnesses": {"pi": {"agents": picks}}}
        routes = {
            "worker": "openai/gpt-test@preset/effort-high",
            "k-agent-smol": "google/gemini-test@preset/effort-low",
            "explorer": "anthropic/strong@preset/effort-high",
            "k-agent-adversarial-verifier": "openai/gpt-test@preset/effort-xhigh",
        }
        env = {
            "AGENT_BAND_SCHEMA_HARNESS": "pi",
            "AGENT_BAND_MODEL_FORMAT": "openrouter-preset",
            "AGENT_BAND_CODEX_ROUTES": json.dumps(routes),
        }
        for role, wire in routes.items():
            payload = {"tool_name": "spawn_agent", "tool_input": {"agent_type": role, "message": "packet"}}
            result = self.gate("codex", payload, projection, env)["hookSpecificOutput"]
            self.assertEqual(result["updatedInput"]["model"], wire)
            self.assertNotIn("reasoning_effort", result["updatedInput"])
        payload = {
            "tool_name": "spawn_agent",
            "tool_input": {
                "agent_type": "worker",
                "model": routes["k-agent-adversarial-verifier"],
                "reasoning_effort": "xhigh",
            },
        }
        result = self.gate("codex", payload, projection, env)["hookSpecificOutput"]
        self.assertEqual(result["updatedInput"]["model"], routes["k-agent-adversarial-verifier"])
        research_input = {
            **payload["tool_input"],
            "model": "anthropic/strong@preset/effort-high",
            "reasoning_effort": "high",
        }
        research = self.gate("codex", {**payload, "tool_input": research_input}, projection, env)["hookSpecificOutput"]
        self.assertEqual(research["updatedInput"]["model"], "anthropic/strong@preset/effort-high")
        for patch, changed in (
            ({"fork_context": True}, env),
            ({"reasoning_effort": "high"}, env),
            ({}, {**env, "AGENT_BAND_CODEX_ROUTES": ""}),
            ({}, {**env, "AGENT_BAND_CODEX_ROUTES": "{}"}),
            ({}, {**env, "AGENT_BAND_CODEX_ROUTES": "invalid"}),
            ({}, {**env, "AGENT_BAND_MODEL_OVERRIDE": "root"}),
            ({}, {**env, "AGENT_BAND_EFFORT_OVERRIDE": "low"}),
            ({}, {**env, "AGENT_BAND_CODEX_ROUTES": json.dumps({**routes, "worker": "stale"})}),
        ):
            with self.subTest(patch=patch, changed=changed):
                result = self.gate(
                    "codex", {**payload, "tool_input": {**payload["tool_input"], **patch}}, projection, changed
                )["hookSpecificOutput"]
                self.assertEqual(result["permissionDecision"], "deny")
        result = self.gate("codex", {**payload, "agent_id": "child"}, projection, env)["hookSpecificOutput"]
        self.assertEqual(result["permissionDecision"], "deny")

    def test_SHOULD_keep_openrouter_refute_distinct_from_implementation(self):
        projection = json.loads((REPO / "home/dot_config/ai/readonly_agent-bands.v1.json").read_text())
        routes = {
            "general-purpose": "openai/gpt-5.6-sol@preset/effort-high",
            "k-agent-adversarial-verifier": "openai/gpt-5.6-sol@preset/effort-xhigh",
        }
        env = {
            "AGENT_BAND_SCHEMA_HARNESS": "pi",
            "AGENT_BAND_MODEL_FORMAT": "openrouter-preset",
            "AGENT_BAND_CLAUDE_ROUTES": json.dumps(routes),
        }
        for role in routes:
            payload = {"tool_name": "Agent", "tool_input": {"subagent_type": role, "prompt": "p", "model": "opus"}}
            result = self.gate("claude_code", payload, projection, env)["hookSpecificOutput"]
            self.assertEqual(result["updatedInput"], {"subagent_type": role, "prompt": "p"})
            stale = {**routes, role: "openai/gpt-5.6-sol@preset/effort-low"}
            result = self.gate(
                "claude_code", payload, projection, {**env, "AGENT_BAND_CLAUDE_ROUTES": json.dumps(stale)}
            )
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

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
        # `_override` skips claude_code: the alias resolves through ANTHROPIC_DEFAULT_*_MODEL, which
        # the launcher already points at the route's model, and a raw provider id fails updatedInput
        # schema validation. A plain override sets no `force_alias` either, so the clamp still writes
        # the band's own alias — here `fable`, which is also what openai/gpt-5.2 would project to.
        answer = self.gate(
            "claude_code",
            {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore", "model": "ultra"}},
            override={"AGENT_BAND_MODEL_OVERRIDE": "openai/gpt-5.2"},
        )
        updated = answer["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["model"], "fable")
        self.assertNotIn("openai/gpt-5.2", json.dumps(updated))

    def test_gemini_has_no_adapter_because_invoke_agent_takes_no_model(self):
        self.assertEqual(
            self.gate(
                "gemini",
                {"tool_name": "invoke_agent", "tool_input": {"agent_name": "codebase_investigator", "prompt": "p"}},
            ),
            {},
        )

    def test_the_gate_leaves_ordinary_tools_and_external_adapters_alone(self):
        cases = [
            ("codex", {"tool_name": "Read", "tool_input": {"path": "x"}}, None),
            ("nosuchharness", {"tool_name": "spawn_agent", "tool_input": {"agent_type": "explorer"}}, None),
            # No adapter exists for Pi (no mutating pre-tool-use hook: its extension API blocks a
            # call, it cannot rewrite the arguments) or for OMP (the `task` tool takes no model
            # argument; categories are `@role` tokens modelRoles resolves). Both must no-op rather
            # than emit a shape the harness would reject.
            ("pi", {"tool_name": "spawn_agent", "tool_input": {"agent_type": "explorer", "message": "go"}}, None),
            ("omp", {"tool_name": "task", "tool_input": {"agent": "task", "prompt": "p"}}, None),
        ]
        for harness, payload, projection in cases:
            with self.subTest(harness=harness, payload=payload, projection=projection):
                self.assertEqual(self.gate(harness, payload, projection), {})

    def test_SHOULD_deny_delegation_without_a_registered_projection_or_role(self):
        for projection, args in (
            ({}, {"agent_type": "explorer"}),
            (None, {"agent_type": "not-bound"}),
            (None, {}),
            ({"harnesses": []}, {"agent_type": "explorer"}),
            (
                {"harnesses": {"codex": {"agents": {"explorer": {"model": "gpt", "effort": None}}}}},
                {"agent_type": "explorer"},
            ),
        ):
            with self.subTest(projection=projection, args=args):
                result = self.gate("codex", {"tool_name": "spawn_agent", "tool_input": args}, projection)
                self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_SHOULD_enforce_generic_model_effort_pairs_without_collapsing_other_lanes(self):
        for harness, tool, key in (("codex", "spawn_agent", "agent_type"), ("copilot", "task", "agent_type")):
            projection = {
                "harnesses": {
                    harness: {
                        "agents": {
                            "worker": {"category": "implement", "model": "cheap", "effort": "high"},
                            "research": {"category": "research", "model": "strong", "effort": "high"},
                            "refute": {"category": "refute", "model": "strong", "effort": "xhigh"},
                        }
                    }
                }
            }
            for model, requested, expected in (
                ("cheap", "low", "high"),
                ("cheap", None, "high"),
                ("strong", "high", "high"),
                ("strong", "xhigh", "xhigh"),
            ):
                with self.subTest(harness=harness, model=model, effort=requested):
                    args = {key: "worker", "model": model, "reasoning_effort": requested, "message": "packet"}
                    result = self.gate(harness, {"tool_name": tool, "tool_input": args}, projection)
                    updated = result.get("modifiedArgs") or result["hookSpecificOutput"]["updatedInput"]
                    self.assertEqual(
                        (updated["model"], updated["reasoning_effort"], updated["message"]), (model, expected, "packet")
                    )
            for effort in (None, "low"):
                result = self.gate(
                    harness,
                    {"tool_name": tool, "tool_input": {key: "worker", "model": "strong", "reasoning_effort": effort}},
                    projection,
                )
                self.assertEqual((result.get("hookSpecificOutput") or result)["permissionDecision"], "deny")
            projection["harnesses"][harness]["agents"]["research"].pop("effort")
            result = self.gate(
                harness, {"tool_name": tool, "tool_input": {key: "worker", "model": "strong"}}, projection
            )
            self.assertEqual((result.get("hookSpecificOutput") or result)["permissionDecision"], "deny")

    def test_SHOULD_preserve_cursor_selector_only_lanes_without_weakening_backend_effort(self):
        projection = {
            "harnesses": {
                "cursor": {
                    "agents": {
                        "generalPurpose": {"category": "implement", "model": "implement-high", "effort": "high"},
                        "k-agent-mechanical": {"category": "mechanical", "model": "auto"},
                        "k-agent-smol": {"category": "memory", "model": "auto"},
                    }
                },
                "codex": {"agents": {"generalPurpose": {"category": "implement", "model": "backend"}}},
                "copilot": {"agents": {"generalPurpose": {"category": "implement", "model": "backend"}}},
                "pi": {"agents": {"generalPurpose": {"category": "implement", "model": "openrouter/backend"}}},
            }
        }
        self.assertEqual(
            self.gate(
                "cursor",
                {
                    "tool_name": "Subagent",
                    "tool_input": {"subagent_type": "generalPurpose", "model": "auto", "prompt": "packet"},
                },
                projection,
            ),
            {},
        )
        for role in ("k-agent-mechanical", "k-agent-smol"):
            with self.subTest(role=role):
                result = self.gate(
                    "cursor",
                    {
                        "tool_name": "Task",
                        "tool_input": {"subagent_type": role, "model": "expensive", "prompt": "packet"},
                    },
                    projection,
                )
                self.assertEqual(result["updated_input"], {"subagent_type": role, "model": "auto", "prompt": "packet"})
        for backend in ("codex", "copilot", "pi"):
            with self.subTest(backend=backend):
                result = self.gate(
                    "cursor",
                    {"tool_name": "Task", "tool_input": {"subagent_type": "generalPurpose", "model": "auto"}},
                    projection,
                    override={"AGENT_BAND_SCHEMA_HARNESS": backend},
                )
                self.assertEqual(result["permission"], "deny")

    def test_SHOULD_deny_unverified_subscription_delegation_transports(self):
        cases = (
            ("codex", "spawn_agent", "permissionDecision"),
            ("copilot", "task", "permissionDecision"),
            ("cursor", "Task", "permission"),
        )
        for harness, tool, key in cases:
            with self.subTest(harness=harness):
                result = self.gate(
                    harness,
                    {"tool_name": tool, "tool_input": {"agent_type": "explore"}},
                    override={"AGENT_BAND_SUBSCRIPTION": "copilot"},
                )
                self.assertEqual((result.get("hookSpecificOutput") or result)[key], "deny")

    def test_SHOULD_project_codex_subscription_lanes_only_for_fresh_registered_leaves(self):
        projection = {
            "harnesses": {
                "copilot": {
                    "agents": {
                        "worker": {"category": "implement", "model": "claude-opus-5", "effort": "high"},
                        "explorer": {"category": "research", "model": "gpt-5.6-sol", "effort": "xhigh"},
                        "k-agent-smol": {"category": "memory", "model": "claude-sonnet-5", "effort": "low"},
                    }
                }
            }
        }
        routes = {
            "worker": "claude-opus-5@lane-high",
            "explorer": "gpt-5.6-sol@lane-xhigh",
            "k-agent-smol": "claude-sonnet-5@lane-low",
        }
        env = {
            "AGENT_BAND_SUBSCRIPTION": "copilot",
            "AGENT_BAND_SCHEMA_HARNESS": "copilot",
            "AGENT_BAND_CODEX_ROUTES": json.dumps(routes),
        }
        for role, selector in routes.items():
            with self.subTest(role=role):
                payload = {
                    "tool_name": "multi_agent_v1.spawn_agent",
                    "tool_input": {"agent_type": role, "message": "packet", "model": "root"},
                }
                result = self.gate("codex", payload, projection, env)["hookSpecificOutput"]
                self.assertEqual(result["permissionDecision"], "allow")
                self.assertEqual(result["updatedInput"]["model"], selector)
                self.assertEqual(result["updatedInput"]["reasoning_effort"], selector.split("@lane-")[1])
                self.assertEqual(result["updatedInput"]["message"], "packet")
        payload = {
            "tool_name": "spawn_agent",
            "tool_input": {"agent_type": "worker", "model": "claude-sonnet-5@lane-low", "reasoning_effort": "low"},
        }
        result = self.gate("codex", payload, projection, env)["hookSpecificOutput"]
        self.assertEqual(result["updatedInput"]["model"], "claude-sonnet-5@lane-low")
        for patch, changed_env in (
            ({"fork_context": True}, env),
            ({"reasoning_effort": "high"}, env),
            ({}, {**env, "AGENT_BAND_CODEX_ROUTES": "{}"}),
            ({}, {**env, "AGENT_BAND_CODEX_ROUTES": "invalid"}),
            ({}, {**env, "AGENT_BAND_MODEL_OVERRIDE": "root"}),
        ):
            with self.subTest(patch=patch, env=changed_env):
                bad = {**payload, "tool_input": {**payload["tool_input"], **patch}}
                result = self.gate("codex", bad, projection, changed_env)["hookSpecificOutput"]
                self.assertEqual(result["permissionDecision"], "deny")
        result = self.gate("codex", {**payload, "agent_id": "child"}, projection, env)["hookSpecificOutput"]
        self.assertEqual(result["permissionDecision"], "deny")
        for role in ("worker", "k-agent-smol"):
            stale = {**routes, role: routes["explorer"]}
            with self.subTest(stale_role=role):
                result = self.gate(
                    "codex",
                    {"tool_name": "spawn_agent", "tool_input": {"agent_type": role}},
                    projection,
                    {**env, "AGENT_BAND_CODEX_ROUTES": json.dumps(stale)},
                )["hookSpecificOutput"]
                self.assertEqual(result["permissionDecision"], "deny")

    def test_SHOULD_keep_native_codex_child_startup_and_recall_out_of_root_context(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = {
                "session_id": "child-session",
                "agent_id": "child-id",
                "agent_type": "worker",
                "cwd": directory,
                "prompt": "you guessed this again",
                "source": "startup",
            }
            env = {**os.environ, "AGENT_MEMORY_SPEC_ROOT": directory, "AGENT_HOOK_OUTPUT": "hook_specific"}
            self.assertEqual(run_hook("executable_session_context.py", payload, env), {})
            self.assertEqual(run_perturn_recall(directory, payload, env), {})
            self.assertEqual({path.name for path in Path(directory).iterdir()}, {"deployed-hooks"})

    def test_a_task_name_is_not_mistaken_for_the_role(self):
        # Codex's spawn_agent carries both; task_name is a free-text label.
        answer = self.gate(
            "codex",
            {"tool_name": "spawn_agent", "tool_input": {"task_name": "bugbot", "agent_type": "explorer"}},
        )
        self.assertEqual(answer["hookSpecificOutput"]["updatedInput"]["model"], "gpt-5.4")


if __name__ == "__main__":
    unittest.main()
