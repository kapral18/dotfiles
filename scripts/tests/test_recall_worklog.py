#!/usr/bin/env python3
"""Depth-aware recall and asynchronous worklog regression tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import _test_support  # noqa: F401
from _test_support import REPO

SCRIPTS = REPO / "scripts"
HOOKS = REPO / "home" / "exact_dot_agents" / "exact_hooks"
PI_EXTENSION = REPO / "home" / "dot_pi" / "agent" / "extensions" / "ai-kb-recall.ts"


def _test_root(test_case: unittest.TestCase, prefix: str) -> Path:
    base = Path(os.environ.get("TEST_ARTIFACT_ROOT") or os.environ.get("TMPDIR") or tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    root = base / f"{prefix}-{os.getpid()}-{time.time_ns()}"
    test_case.addCleanup(shutil.rmtree, root, True)
    return root


def _base_env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["AGENT_MEMORY_SPEC_ROOT"] = str(root / "specs")
    env["PYTHONPATH"] = f"{SCRIPTS}{os.pathsep}{env.get('PYTHONPATH', '')}"
    # The hook's per-profile search timeout races the stub subprocess under
    # full-suite load; a generous floor keeps depth-parity assertions
    # deterministic without changing production defaults.
    env["AI_KB_RECALL_TIMEOUT"] = "60"
    return env


def _deploy_hooks(root: Path) -> Path:
    deployed = root / "deployed-hooks"
    deployed.mkdir(parents=True, exist_ok=True)
    for source, target in (
        ("hook_common.py", "hook_common.py"),
        ("executable_session_context.py", "session_context.py"),
        ("executable_perturn_recall.py", "perturn_recall.py"),
    ):
        (deployed / target).write_text((HOOKS / source).read_text(encoding="utf-8"), encoding="utf-8")
    return deployed


def _make_search_stub(root: Path, workspace: Path, count: int = 12) -> tuple[Path, Path]:
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    log = root / "search.jsonl"
    rows = [
        {
            "id": f"capsule-{index}",
            "title": f"Depth capsule {index}",
            "body": "x" * 500,
            "kind": "fact",
            "scope": "project",
            "workspace_path": str(workspace),
            "cosine_score": 0.9,
        }
        for index in range(count)
    ]
    stub = bindir / ",ai-kb"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "query = sys.stdin.read()\n"
        "with open(os.environ['SEARCH_LOG'], 'a', encoding='utf-8') as stream:\n"
        "    stream.write(json.dumps({'args': sys.argv[1:], 'query': query, "
        "'connect_only': os.environ.get('AI_EMBED_CONNECT_ONLY')}) + '\\n')\n"
        f"print({json.dumps(rows)!r})\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return bindir, log


def _run_recall(root: Path, depth: str | None, prompt: str) -> tuple[dict, list[dict]]:
    workspace = root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    workspace = workspace.resolve()
    deployed = _deploy_hooks(root)
    bindir, log = _make_search_stub(root, workspace)
    env = _base_env(root)
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["SEARCH_LOG"] = str(log)
    if depth is None:
        env.pop("AI_AGENT_DEPTH", None)
        session_id = "depth-unset"
    else:
        env["AI_AGENT_DEPTH"] = depth
        session_id = f"depth-{depth}"
    result = subprocess.run(
        [sys.executable, str(deployed / "perturn_recall.py")],
        input=json.dumps(
            {
                "hook_event_name": "UserPromptSubmit",
                "workspace_roots": [str(workspace)],
                "session_id": session_id,
                "prompt": prompt,
            }
        ),
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
        check=True,
    )
    searches = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    return json.loads(result.stdout or "{}"), searches


def _enqueue_in_process(args: tuple[str, str, str, int]) -> None:
    spec_dir, session_key, worklog, index = args
    import worklog_queue

    worklog_queue.enqueue(
        Path(spec_dir),
        session_key,
        "current",
        Path(worklog),
        {"command": f"command-{index}", "event": "postToolUse"},
        start_worker=False,
    )


def _enqueue_after_marker(args: tuple[str, str, str, str]) -> None:
    spec_dir, worklog, marker, session_key = args
    Path(marker).write_text("ready", encoding="utf-8")
    import worklog_queue

    worklog_queue.enqueue(
        Path(spec_dir),
        session_key,
        "current",
        Path(worklog),
        {"command": "concurrent"},
        start_worker=False,
    )


def _flush_in_process(spec_dir: str) -> tuple[int, int, int]:
    import worklog_queue

    result = worklog_queue.flush_spec_dir(Path(spec_dir))
    return result.flushed, result.pending, result.errors


def _run_pi_depth(root: Path, depth: str | None) -> tuple[dict, list[dict]]:
    workspace = root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    workspace = workspace.resolve()
    bindir, log = _make_search_stub(root, workspace)
    script = """
const mod = await import(process.argv[1]);
const workspace = process.argv[2];
const specFile = process.argv[3];
const handlers = {};
let warmCalls = 0;
const pi = {
  async exec(command, args) {
    if (command === ",ai-kb" && args[0] === "--help") return { code: 0, killed: false, stdout: "" };
    if (command === ",agent-memory") {
      return {
        code: 0,
        killed: false,
        stdout: JSON.stringify({
          workspace,
          selected_topic: "current",
          session_key: "pi-depth-session",
          is_named_topic: false,
          spec_file: specFile,
          spec_exists: false
        })
      };
    }
    if (command === "python3" && args[0].endsWith("/lib/,ai-kb/embed_client.py")) {
      warmCalls += 1;
      return { code: 0, killed: false, stdout: "{}" };
    }
    if (command === "cat") return { code: 1, killed: false, stdout: "" };
    throw new Error(`unexpected exec: ${command} ${args.join(" ")}`);
  },
  on(event, handler) { handlers[event] = handler; }
};
await mod.default(pi);
await handlers.session_start(
  { type: "session_start", reason: "startup" },
  { sessionManager: { getSessionId() { return "pi-depth-session"; } } }
);
const result = await handlers.before_agent_start(
  { prompt: "pi depth aware automatic recall " + "detail ".repeat(250) },
  {
    cwd: workspace,
    getContextUsage() { return null; },
    sessionManager: { getSessionId() { return "pi-depth-session"; } }
  }
);
console.log(JSON.stringify({ warmCalls, content: result?.message?.content ?? "" }));
"""
    env = _base_env(root)
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["SEARCH_LOG"] = str(log)
    env["HOME"] = str(root / "home")
    env["NODE_NO_WARNINGS"] = "1"
    if depth is None:
        env.pop("AI_AGENT_DEPTH", None)
    else:
        env["AI_AGENT_DEPTH"] = depth
    spec_file = root / "specs" / "current.txt"
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(PI_EXTENSION), str(workspace), str(spec_file)],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
        check=True,
    )
    searches = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    return json.loads(result.stdout), searches


class TestRecallDepth(unittest.TestCase):
    """WHEN automatic recall consumes AI_AGENT_DEPTH."""

    def test_depth_matrix_keeps_unset_balanced_parity_and_bounds_fast_and_deep(self) -> None:
        root = _test_root(self, "depth")
        root.mkdir(parents=True)
        prompt = "depth aware automatic recall " + ("detail " * 250)

        unset, unset_searches = _run_recall(root / "unset", None, prompt)
        balanced, balanced_searches = _run_recall(root / "balanced", "balanced", prompt)
        invalid, invalid_searches = _run_recall(root / "invalid", "unsupported", prompt)
        fast, fast_searches = _run_recall(root / "fast", "fast", prompt)
        deep, deep_searches = _run_recall(root / "deep", "deep", prompt)

        self.assertEqual(unset, balanced)
        self.assertEqual(invalid, balanced)
        self.assertEqual(
            {**unset_searches[0], "args": [*unset_searches[0]["args"][:7], "<workspace>", "--json"]},
            {**balanced_searches[0], "args": [*balanced_searches[0]["args"][:7], "<workspace>", "--json"]},
        )
        self.assertEqual(
            {**invalid_searches[0], "args": [*invalid_searches[0]["args"][:7], "<workspace>", "--json"]},
            {**balanced_searches[0], "args": [*balanced_searches[0]["args"][:7], "<workspace>", "--json"]},
        )
        self.assertEqual(len(unset_searches), 1)
        self.assertEqual(unset_searches[0]["args"][3], "6")
        self.assertEqual(unset_searches[0]["args"][5], "hybrid")
        self.assertEqual(len(unset_searches[0]["query"]), 601)
        self.assertEqual(unset_searches[0]["connect_only"], "1")
        self.assertEqual(unset["hookSpecificOutput"]["additionalContext"].count("- **"), 3)

        self.assertEqual(fast, {})
        self.assertEqual(fast_searches, [])

        self.assertEqual(len(deep_searches), 1)
        self.assertEqual(deep_searches[0]["args"][3], "12")
        self.assertEqual(deep_searches[0]["args"][5], "hybrid")
        self.assertEqual(len(deep_searches[0]["query"]), 1201)
        self.assertEqual(deep_searches[0]["connect_only"], "1")
        self.assertEqual(deep["hookSpecificOutput"]["additionalContext"].count("- **"), 5)

    def test_fast_session_start_does_not_warm_resident(self) -> None:
        root = _test_root(self, "warm")
        deployed = _deploy_hooks(root)
        workspace = root / "workspace"
        workspace.mkdir(parents=True)
        client = root / "home" / "lib" / ",ai-kb" / "embed_client.py"
        client.parent.mkdir(parents=True)
        marker = root / "warmed"
        client.write_text(
            "#!/usr/bin/env python3\nimport os, pathlib\npathlib.Path(os.environ['WARM_MARKER']).write_text('1')\n",
            encoding="utf-8",
        )
        client.chmod(0o755)
        env = _base_env(root)
        env.update(
            {
                "AI_AGENT_DEPTH": "fast",
                "AI_EMBED_WARM": "1",
                "HOME": str(root / "home"),
                "WARM_MARKER": str(marker),
            }
        )
        subprocess.run(
            [sys.executable, str(deployed / "session_context.py")],
            input=json.dumps(
                {
                    "hook_event_name": "SessionStart",
                    "workspace_roots": [str(workspace)],
                    "session_id": "fast-warm",
                }
            ),
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env=env,
            check=True,
        )
        self.assertFalse(marker.exists())

    def test_pi_uses_the_same_unset_fast_balanced_deep_contract(self) -> None:
        root = _test_root(self, "pi-depth")
        unset, unset_searches = _run_pi_depth(root / "unset", None)
        balanced, balanced_searches = _run_pi_depth(root / "balanced", "balanced")
        invalid, invalid_searches = _run_pi_depth(root / "invalid", "unsupported")
        fast, fast_searches = _run_pi_depth(root / "fast", "fast")
        deep, deep_searches = _run_pi_depth(root / "deep", "deep")

        self.assertEqual(unset, balanced)
        self.assertEqual(invalid, balanced)
        self.assertEqual(
            {**unset_searches[0], "args": [*unset_searches[0]["args"][:7], "<workspace>", "--json"]},
            {**balanced_searches[0], "args": [*balanced_searches[0]["args"][:7], "<workspace>", "--json"]},
        )
        self.assertEqual(
            {**invalid_searches[0], "args": [*invalid_searches[0]["args"][:7], "<workspace>", "--json"]},
            {**balanced_searches[0], "args": [*balanced_searches[0]["args"][:7], "<workspace>", "--json"]},
        )
        self.assertEqual(unset["warmCalls"], 0)
        self.assertEqual(unset["content"].count("- **"), 3)
        self.assertEqual(unset_searches[0]["args"][3], "6")
        self.assertEqual(unset_searches[0]["connect_only"], "1")

        self.assertEqual(fast, {"warmCalls": 0, "content": ""})
        self.assertEqual(fast_searches, [])

        self.assertEqual(deep["warmCalls"], 0)
        self.assertEqual(deep["content"].count("- **"), 5)
        self.assertEqual(deep_searches[0]["args"][3], "12")
        self.assertEqual(deep_searches[0]["connect_only"], "1")

    def test_adapter_inventory_keeps_shared_depth_contract_and_perturn_wiring(self) -> None:
        claude = (REPO / "home/dot_claude/settings.personal.json").read_text(encoding="utf-8")
        gemini = (REPO / "home/dot_gemini/settings.json").read_text(encoding="utf-8")
        opencode = (REPO / "home/dot_config/opencode/plugins/agent-memory.ts").read_text(encoding="utf-8")
        copilot = (
            REPO / "home/private_dot_copilot/exact_extensions/exact_agent-memory/readonly_extension.mjs"
        ).read_text(encoding="utf-8")
        pi = PI_EXTENSION.read_text(encoding="utf-8")
        cursor = (REPO / "home/dot_cursor/hooks.json").read_text(encoding="utf-8")
        codex = (REPO / "home/dot_codex/hooks.json.tmpl").read_text(encoding="utf-8")

        for adapter in (claude, gemini, opencode, copilot, codex, cursor):
            self.assertIn("perturn_recall.py", adapter)
        for adapter in (claude, gemini, opencode, copilot, cursor, codex):
            self.assertIn("worklog_dispatcher.sh", adapter)
        self.assertIn("AI_AGENT_DEPTH", pi)
        # Cursor >= 2026.07.16 injects additionalContext from beforeSubmitPrompt
        # (verified from the installed bundle); the hook must ride that event and
        # sessionStart must request the resident warm-up.
        self.assertIn("beforeSubmitPrompt", cursor)
        self.assertIn("AI_EMBED_WARM=1", cursor)
        # Codex spawns hook commands without a shell (verified against codex
        # 0.144.4: a literal `$HOME/...` command never expands and the hook
        # fails), so its adapter must use templated absolute paths.
        self.assertNotIn("$HOME", codex)
        self.assertIn("{{ .chezmoi.homeDir }}", codex)


class TestWorklogQueue(unittest.TestCase):
    """WHEN worklog events are queued and flushed outside the tool hook."""

    def setUp(self) -> None:
        self.root = _test_root(self, "queue")
        self.spec_dir = self.root / "specs" / "workspace"
        self.worklog = self.spec_dir / "current.worklog.jsonl"
        self.spec_dir.mkdir(parents=True)

    def test_queue_preserves_session_order_and_recovers_after_append_before_ack_crash(self) -> None:
        import worklog_queue

        receipts = [
            worklog_queue.enqueue(
                self.spec_dir,
                "canonical-session",
                "current",
                self.worklog,
                {"command": f"command-{index}", "event": "postToolUse"},
                start_worker=False,
            )
            for index in range(4)
        ]
        first_record = worklog_queue.read_queue_record(receipts[0].path)
        committed = {
            **first_record["entry"],
            "worklog_id": first_record["id"],
            "session_key": first_record["session_key"],
            "worklog_seq": first_record["seq"],
        }
        self.worklog.write_text(json.dumps(committed, sort_keys=True) + "\n", encoding="utf-8")

        result = worklog_queue.flush_session(receipts[0].queue_dir)
        entries = [json.loads(line) for line in self.worklog.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result.pending, 0)
        self.assertEqual([entry["command"] for entry in entries], [f"command-{index}" for index in range(4)])
        self.assertEqual(len({entry["worklog_id"] for entry in entries}), 4)
        self.assertTrue(all(entry["session_key"] == "canonical-session" for entry in entries))
        self.assertEqual([entry["worklog_seq"] for entry in entries], sorted(entry["worklog_seq"] for entry in entries))

    def test_concurrent_sessions_share_one_worklog_without_loss(self) -> None:
        import worklog_queue

        jobs = [(str(self.spec_dir), f"session-{index % 4}", str(self.worklog), index) for index in range(40)]
        with ProcessPoolExecutor(max_workers=8) as pool:
            list(pool.map(_enqueue_in_process, jobs))

        result = worklog_queue.flush_spec_dir(self.spec_dir)
        entries = [json.loads(line) for line in self.worklog.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result.pending, 0)
        self.assertEqual(len(entries), 40)
        self.assertEqual(len({entry["worklog_id"] for entry in entries}), 40)
        for session_key in {entry["session_key"] for entry in entries}:
            seqs = [entry["worklog_seq"] for entry in entries if entry["session_key"] == session_key]
            self.assertEqual(seqs, sorted(seqs))

    def test_spec_flush_is_linearized_against_new_session_enqueues(self) -> None:
        import worklog_queue

        blocker = worklog_queue.enqueue(
            self.spec_dir,
            "flush-blocker",
            "current",
            self.worklog,
            {"command": "before-flush"},
            start_worker=False,
        )
        marker = self.root / "enqueue-ready"
        with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn")) as pool:
            with worklog_queue._locked(worklog_queue._session_lifecycle_lock(self.spec_dir, blocker.queue_dir.name)):
                flush_future = pool.submit(_flush_in_process, str(self.spec_dir))
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    with worklog_queue._locked(
                        worklog_queue._spec_activity_lock(self.spec_dir),
                        blocking=False,
                        shared=True,
                    ) as acquired:
                        if not acquired:
                            break
                    time.sleep(0.01)
                else:
                    self.fail("flush did not acquire the spec activity lock")
                enqueue_future = pool.submit(
                    _enqueue_after_marker,
                    (str(self.spec_dir), str(self.worklog), str(marker), "during-flush"),
                )
                deadline = time.monotonic() + 2
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(marker.exists())
                time.sleep(0.05)
                self.assertFalse(enqueue_future.done())
            self.assertEqual(flush_future.result(timeout=2), (1, 0, 0))
            enqueue_future.result(timeout=2)

        after = worklog_queue.flush_spec_dir(self.spec_dir)
        commands = [json.loads(line)["command"] for line in self.worklog.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(after.flushed, 1)
        self.assertEqual(commands, ["before-flush", "concurrent"])

    def test_shared_topic_is_chronological_across_session_flush_order(self) -> None:
        import worklog_queue

        worklog_queue.enqueue(
            self.spec_dir,
            "z-older-session",
            "current",
            self.worklog,
            {"ts": "2026-07-11T12:00:01+00:00", "command": "older"},
            start_worker=False,
        )
        worklog_queue.enqueue(
            self.spec_dir,
            "a-newer-session",
            "current",
            self.worklog,
            {"ts": "2026-07-11T12:00:02+00:00", "command": "newer"},
            start_worker=False,
        )

        result = worklog_queue.flush_spec_dir(self.spec_dir)
        entries = [json.loads(line) for line in self.worklog.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result.pending, 0)
        self.assertEqual([entry["command"] for entry in entries], ["older", "newer"])

    def test_queue_bound_fails_loudly_without_discarding_pending_events(self) -> None:
        import worklog_queue

        config = worklog_queue.QueueConfig(max_pending=2, max_bytes=64 * 1024)
        for index in range(2):
            worklog_queue.enqueue(
                self.spec_dir,
                "bounded-session",
                "current",
                self.worklog,
                {"command": f"command-{index}"},
                config=config,
                start_worker=False,
            )
        with self.assertRaises(worklog_queue.QueueFullError):
            worklog_queue.enqueue(
                self.spec_dir,
                "bounded-session",
                "current",
                self.worklog,
                {"command": "overflow"},
                config=config,
                start_worker=False,
            )
        queue_dir = worklog_queue.session_queue_dir(self.spec_dir, "bounded-session")
        self.assertEqual(len(list(queue_dir.glob("*.json"))), 2)
        errors = worklog_queue.error_log_path(queue_dir).read_text(encoding="utf-8")
        self.assertIn("queue_full", errors)
        visible = worklog_queue.flush_spec_dir(self.spec_dir, config=config)
        self.assertGreater(visible.errors, 0)

    def test_malformed_record_remains_pending_and_visible(self) -> None:
        import worklog_queue

        receipt = worklog_queue.enqueue(
            self.spec_dir,
            "malformed-session",
            "current",
            self.worklog,
            {"command": "must not disappear"},
            start_worker=False,
        )
        receipt.path.write_text("{not-json}\n", encoding="utf-8")

        result = worklog_queue.flush_session(receipt.queue_dir)
        errors = worklog_queue.error_log_path(receipt.queue_dir).read_text(encoding="utf-8")

        self.assertEqual(result.pending, 1)
        self.assertGreater(result.errors, 0)
        self.assertIn("invalid_record", errors)

    def test_structurally_invalid_record_remains_pending_and_visible(self) -> None:
        import worklog_queue

        receipt = worklog_queue.enqueue(
            self.spec_dir,
            "invalid-fields-session",
            "current",
            self.worklog,
            {"command": "must not disappear"},
            start_worker=False,
        )
        receipt.path.write_text(
            json.dumps({"version": 1, "worklog": self.worklog.name, "entry": {}}) + "\n",
            encoding="utf-8",
        )

        result = worklog_queue.flush_session(receipt.queue_dir)

        self.assertEqual(result.pending, 1)
        self.assertGreater(result.errors, 0)
        self.assertIn("invalid_record", worklog_queue.error_log_path(receipt.queue_dir).read_text(encoding="utf-8"))

    def test_migrate_worklog_merges_dedupes_and_removes_source(self) -> None:
        import worklog_queue

        fallback = self.spec_dir / "session-abc.worklog.jsonl"
        shared = {
            "event": "postToolUse",
            "session_key": "abc",
            "worklog_id": "dup-1",
            "ts": "2026-07-11T12:00:01+00:00",
        }
        early = {"event": "postToolUse", "session_key": "abc", "worklog_id": "pre-1", "ts": "2026-07-11T11:59:59+00:00"}
        fallback.write_text(
            "\n".join(json.dumps(entry, sort_keys=True) for entry in (early, shared)) + "\n",
            encoding="utf-8",
        )
        later = {
            "event": "postToolUse",
            "session_key": "abc",
            "worklog_id": "post-1",
            "ts": "2026-07-11T12:00:02+00:00",
        }
        self.worklog.write_text(
            "\n".join(json.dumps(entry, sort_keys=True) for entry in (shared, later)) + "\n",
            encoding="utf-8",
        )

        migrated = worklog_queue.migrate_worklog(self.spec_dir, fallback.name, self.worklog.name)
        entries = [json.loads(line) for line in self.worklog.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(migrated, 1)
        self.assertFalse(fallback.exists())
        self.assertEqual([entry["worklog_id"] for entry in entries], ["pre-1", "dup-1", "post-1"])

    def test_migrate_worklog_rejects_targets_outside_spec_dir(self) -> None:
        import worklog_queue

        with self.assertRaises(worklog_queue.QueueError):
            worklog_queue.migrate_worklog(self.spec_dir, "../escape.worklog.jsonl", self.worklog.name)

    def test_migrate_worklog_noop_when_source_equals_target(self) -> None:
        import worklog_queue

        self.worklog.write_text(
            json.dumps({"event": "postToolUse", "worklog_id": "keep-1"}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        migrated = worklog_queue.migrate_worklog(self.spec_dir, self.worklog.name, self.worklog.name)

        self.assertEqual(migrated, 0)
        self.assertEqual(
            [json.loads(line)["worklog_id"] for line in self.worklog.read_text(encoding="utf-8").splitlines()],
            ["keep-1"],
        )

    def test_migrate_worklog_noop_when_source_missing(self) -> None:
        import worklog_queue

        self.worklog.write_text(
            json.dumps({"event": "postToolUse", "worklog_id": "keep-1"}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        migrated = worklog_queue.migrate_worklog(self.spec_dir, "session-missing.worklog.jsonl", self.worklog.name)

        self.assertEqual(migrated, 0)
        self.assertFalse((self.spec_dir / "session-missing.worklog.jsonl").exists())
        self.assertEqual(
            [json.loads(line)["worklog_id"] for line in self.worklog.read_text(encoding="utf-8").splitlines()],
            ["keep-1"],
        )

    def test_migrate_worklog_preserves_lines_without_worklog_id(self) -> None:
        import worklog_queue

        fallback = self.spec_dir / "session-idless.worklog.jsonl"
        fallback.write_text(
            json.dumps({"event": "postToolUse", "ts": "2026-07-11T12:00:00+00:00", "text": "no-id"}, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        self.worklog.write_text(
            json.dumps(
                {"event": "postToolUse", "worklog_id": "keep-1", "ts": "2026-07-11T11:59:59+00:00"},
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        migrated = worklog_queue.migrate_worklog(self.spec_dir, fallback.name, self.worklog.name)
        entries = [json.loads(line) for line in self.worklog.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(migrated, 1)
        self.assertFalse(fallback.exists())
        self.assertEqual([entry.get("worklog_id") for entry in entries], ["keep-1", None])

    def test_cleanup_stale_state_removes_only_old_fallback_state(self) -> None:
        import worklog_queue

        old = time.time() - 200
        stale_worklog = self.spec_dir / "session-stale.worklog.jsonl"
        stale_seen = self.spec_dir / ".recall-seen-stale.json"
        fresh_worklog = self.spec_dir / "session-fresh.worklog.jsonl"
        named_worklog = self.spec_dir / "named-topic.worklog.jsonl"
        for path in (stale_worklog, stale_seen, fresh_worklog, named_worklog):
            path.write_text("{}\n", encoding="utf-8")
        for path in (stale_worklog, stale_seen, named_worklog):
            os.utime(path, (old, old))

        removed = worklog_queue.cleanup_stale_state(
            self.spec_dir,
            config=worklog_queue.QueueConfig(cleanup_age_seconds=100),
        )

        self.assertEqual(removed, 2)
        self.assertFalse(stale_worklog.exists())
        self.assertFalse(stale_seen.exists())
        self.assertTrue(fresh_worklog.exists())
        self.assertTrue(named_worklog.exists())

    def test_cleanup_then_session_key_reuse_does_not_duplicate_event_ids(self) -> None:
        import worklog_queue

        first = worklog_queue.enqueue(
            self.spec_dir,
            "reused-session",
            "current",
            self.worklog,
            {"command": "first"},
            start_worker=False,
        )
        worklog_queue.flush_session(first.queue_dir)
        worklog_queue.cleanup_spec_dir(self.spec_dir, config=worklog_queue.QueueConfig(cleanup_age_seconds=-1))

        second = worklog_queue.enqueue(
            self.spec_dir,
            "reused-session",
            "current",
            self.worklog,
            {"command": "second"},
            start_worker=False,
        )
        result = worklog_queue.flush_session(second.queue_dir)
        entries = [json.loads(line) for line in self.worklog.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result.duplicates, 0)
        self.assertEqual([entry["command"] for entry in entries], ["first", "second"])
        self.assertEqual(len({entry["worklog_id"] for entry in entries}), 2)

    def test_cleanup_checks_oldest_sessions_before_its_per_pass_limit(self) -> None:
        import worklog_queue

        root = worklog_queue.queue_root(self.spec_dir)
        root.mkdir()
        for index in range(64):
            (root / f"a-fresh-{index:02d}").mkdir()
        stale = root / "z-stale"
        stale.mkdir()
        old = time.time() - 200
        os.utime(stale, (old, old))

        removed = worklog_queue.cleanup_spec_dir(
            self.spec_dir,
            config=worklog_queue.QueueConfig(cleanup_age_seconds=100),
        )

        self.assertEqual(removed, 1)
        self.assertFalse(stale.exists())
        self.assertEqual(len(list(root.iterdir())), 64)

    def test_harvest_flushes_pending_events_before_candidate_detection(self) -> None:
        import worklog_queue

        for index in range(2):
            worklog_queue.enqueue(
                self.spec_dir,
                "harvest-session",
                "current",
                self.worklog,
                {
                    "ts": f"2026-07-11T12:00:0{index}+00:00",
                    "command": "python3 -m unittest focused",
                    "event": "postToolUse",
                    "status": "success",
                },
                start_worker=False,
            )
        env = _base_env(self.root)
        env["AI_KB_DISABLE_EMBED"] = "1"
        env["AI_KB_DISABLE_VEC"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "ai_kb.py"),
                "--home",
                str(self.root / "kb"),
                "harvest",
                "--worklog",
                str(self.worklog),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env=env,
            check=True,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(payload["entries"], 2)
        self.assertEqual(payload["candidates"][0]["detector"], "repeated_command")
        self.assertEqual(worklog_queue.flush_spec_dir(self.spec_dir).pending, 0)

    def test_harvest_refuses_success_while_queue_error_is_active(self) -> None:
        import worklog_queue

        self.worklog.write_text("", encoding="utf-8")
        with self.assertRaises(worklog_queue.QueueFullError):
            worklog_queue.enqueue(
                self.spec_dir,
                "failed-harvest-session",
                "current",
                self.worklog,
                {"command": "not queued"},
                config=worklog_queue.QueueConfig(max_pending=0),
                start_worker=False,
            )
        env = _base_env(self.root)
        env["AI_KB_DISABLE_EMBED"] = "1"
        env["AI_KB_DISABLE_VEC"] = "1"

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "ai_kb.py"),
                "--home",
                str(self.root / "kb"),
                "harvest",
                "--worklog",
                str(self.worklog),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env=env,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("flush incomplete", result.stderr)

    def test_worker_exits_after_draining_and_bounded_idle(self) -> None:
        import worklog_queue

        receipt = worklog_queue.enqueue(
            self.spec_dir,
            "worker-session",
            "current",
            self.worklog,
            {"command": "printf worker"},
            start_worker=False,
        )
        started = time.perf_counter()
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "worklog_queue.py"),
                "worker",
                "--queue-dir",
                str(receipt.queue_dir),
                "--idle-seconds",
                "0.02",
                "--max-seconds",
                "0.2",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            check=True,
        )
        elapsed = time.perf_counter() - started

        self.assertEqual(result.stdout, "")
        self.assertLess(elapsed, 0.5)
        self.assertEqual(worklog_queue.flush_session(receipt.queue_dir).pending, 0)
        self.assertTrue(self.worklog.exists())

    def test_worker_idle_window_does_not_block_same_session_enqueue(self) -> None:
        import worklog_queue

        receipt = worklog_queue.enqueue(
            self.spec_dir,
            "coalesced-session",
            "current",
            self.worklog,
            {"command": "first"},
            start_worker=False,
        )
        worker = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPTS / "worklog_queue.py"),
                "worker",
                "--queue-dir",
                str(receipt.queue_dir),
                "--idle-seconds",
                "0.4",
                "--max-seconds",
                "1.5",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(REPO),
        )
        deadline = time.monotonic() + 1
        while not self.worklog.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.worklog.exists())
        self.assertIsNone(worker.poll())

        started = time.perf_counter()
        worklog_queue.enqueue(
            self.spec_dir,
            "coalesced-session",
            "current",
            self.worklog,
            {"command": "second"},
            start_worker=False,
        )
        enqueue_elapsed = time.perf_counter() - started
        worker.wait(timeout=2)
        commands = [json.loads(line)["command"] for line in self.worklog.read_text(encoding="utf-8").splitlines()]

        self.assertLess(enqueue_elapsed, 0.2)
        self.assertEqual(commands, ["first", "second"])


if __name__ == "__main__":
    unittest.main()
