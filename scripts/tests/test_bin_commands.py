#!/usr/bin/env python3
"""Tests for deployed bin command wrappers and command libraries."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import http.server
import importlib.util
import io
import json
import os
import queue
import re
import shlex
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock
from urllib.request import Request, urlopen

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
import ai_models
from _test_support import (
    ARTIFACT_COMMAND,
    CODEX_COMMAND,
    COPILOT_COMMAND,
    KBN_STACK_COMMAND,
    MCP_TOKEN_COMMAND,
    REPO,
    modern_bash,
)

# Every OpenRouter wrapper defaults to this route; model and effort remain selectable.
OPENROUTER_PIN = "deepseek/deepseek-v4-flash-0731"
OPENROUTER_WIRE_PIN = f"{OPENROUTER_PIN}@preset/deepseek-lanes-max"


def _load_artifact_command():
    loader = SourceFileLoader("artifact_command", str(ARTIFACT_COMMAND))
    spec = importlib.util.spec_from_loader("artifact_command", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load ,artifact command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_unwrap_md_command():
    source = REPO / "home/exact_bin/executable_,unwrap-md"
    loader = SourceFileLoader("unwrap_md_command", str(source))
    spec = importlib.util.spec_from_loader("unwrap_md_command", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load unwrap-md command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_mcp_token_module():
    loader = SourceFileLoader("mcp_token_main", str(MCP_TOKEN_COMMAND))
    spec = importlib.util.spec_from_loader("mcp_token_main", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load ,mcp-token command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _es_dash_e_settings(cmd: list[str]) -> list[str]:
    settings: list[str] = []
    index = 0
    while index < len(cmd):
        if cmd[index] == "-E" and index + 1 < len(cmd):
            settings.append(cmd[index + 1])
            index += 2
            continue
        index += 1
    return settings


def _load_kbn_stack_command():
    loader = SourceFileLoader("kbn_stack_command", str(KBN_STACK_COMMAND))
    spec = importlib.util.spec_from_loader("kbn_stack_command", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load ,kbn-stack command module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def _patched_ports(kbn_stack, alive_slots: dict[int, tuple[bool, bool]]):
    """Make ,kbn-stack port liveness deterministic for slot-reclamation tests.

    ``alive_slots`` maps slot -> (kbn_alive, es_alive). port_listener_pids reports
    a synthetic pid for ports whose half is alive; kill_port_listeners records the
    port and clears it; save_registry is captured instead of writing to disk.
    """
    alive_ports: set[int] = set()
    for slot, (kbn_alive, es_alive) in alive_slots.items():
        cfg = kbn_stack.derive(slot)
        if kbn_alive:
            alive_ports.add(cfg["kbn_port"])
        if es_alive:
            alive_ports.add(cfg["es_http"])

    state: dict = {"killed": [], "saved": []}
    original_listeners = kbn_stack.port_listener_pids
    original_kill = kbn_stack.kill_port_listeners
    original_save = kbn_stack.save_registry

    def fake_listeners(port):
        return [10000 + port] if port in alive_ports else []

    def fake_kill(port):
        if port is None or port not in alive_ports:
            return False
        alive_ports.discard(port)
        state["killed"].append(port)
        return True

    kbn_stack.port_listener_pids = fake_listeners
    kbn_stack.kill_port_listeners = fake_kill
    kbn_stack.save_registry = lambda reg: state["saved"].append({k: dict(v) for k, v in reg.items()})
    try:
        yield state
    finally:
        kbn_stack.port_listener_pids = original_listeners
        kbn_stack.kill_port_listeners = original_kill
        kbn_stack.save_registry = original_save


_HANG_AFTER_UNBIND_SERVER = """\
import os
import signal
import socket
import sys
import time

port = int(sys.argv[1])
role = sys.argv[2]
if role == "worker":
    signal.signal(signal.SIGTERM, lambda *_: None)
    while True:
        time.sleep(60)

sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("127.0.0.1", port))
sock.listen(1)


def hang(_signum, _frame):
    try:
        sock.close()
    except OSError:
        pass
    while True:
        time.sleep(60)


signal.signal(signal.SIGTERM, hang)
print(f"ready {os.getpid()}", flush=True)
while True:
    time.sleep(60)
"""


def _spawn_hang_after_unbind_group(script: Path) -> tuple[int, int, list[int]]:
    """Start a session: leader + listener that hangs after closing the port + worker.

    Returns ``(port, pgid, member_pids)``.
    """
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    leader = os.fork()
    if leader == 0:
        os.setsid()
        if os.fork() == 0:
            os.execv(sys.executable, [sys.executable, str(script), str(port), "listener"])
        if os.fork() == 0:
            os.execv(sys.executable, [sys.executable, str(script), str(port), "worker"])
        while True:
            try:
                os.wait()
            except ChildProcessError:
                time.sleep(60)
    deadline = time.monotonic() + 5
    listeners: list[int] = []
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
        )
        listeners = [int(tok) for tok in result.stdout.split() if tok.isdigit()]
        if listeners:
            break
        time.sleep(0.05)
    if not listeners:
        try:
            os.killpg(os.getpgid(leader), signal.SIGKILL)
        except OSError:
            pass
        raise AssertionError("hang-after-unbind harness failed to bind")
    pgid = os.getpgid(listeners[0])
    ps = subprocess.run(["ps", "-axo", "pid=,pgid="], capture_output=True, text=True, check=False)
    members = []
    for line in ps.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == str(pgid):
            members.append(int(parts[0]))
    return port, pgid, members


def _reap_group(pgid: int, leader: int | None = None) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass
    if leader is not None:
        try:
            os.waitpid(leader, 0)
        except ChildProcessError:
            pass


def _capture_stop_existing_serverless(kbn_stack, registry: dict, new_started_by: str):
    stopped: list[tuple[str, bool]] = []
    saved: list[dict] = []
    original_stop_entry = kbn_stack.stop_entry
    original_save_registry = kbn_stack.save_registry

    def fake_stop_entry(worktree, entry, *, allow_user_owned=True):
        stopped.append((worktree, allow_user_owned))
        return True

    kbn_stack.stop_entry = fake_stop_entry
    kbn_stack.save_registry = lambda updated: saved.append(json.loads(json.dumps(updated)))
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                kbn_stack.stop_existing_serverless(registry, "/current", new_started_by)
            except SystemExit:
                blocked = True
            else:
                blocked = False
    finally:
        kbn_stack.stop_entry = original_stop_entry
        kbn_stack.save_registry = original_save_registry

    return blocked, stopped, saved


class TestWIssueCommand(unittest.TestCase):
    """WHEN creating an issue worktree through the deployed read-only command library."""

    def test_should_create_and_focus_on_outer_tmux_with_read_only_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bin_dir = home / "bin"
            w_dir = home / "lib/,w"
            shared_dir = home / "lib/shared"
            repo = root / "repo"
            bin_dir.mkdir(parents=True)
            w_dir.mkdir(parents=True)
            shared_dir.mkdir(parents=True)
            repo.mkdir()

            source_w = REPO / "home/exact_lib/exact_,w"
            source_shared = REPO / "home/exact_lib/exact_shared"
            for name in ("issue.sh", "issue_lib.sh", "add.sh", "open.sh", "switch.sh", "ls.sh"):
                shutil.copyfile(source_w / name, w_dir / name)
                (w_dir / name).chmod(0o444)
            for name in ("bash_utils_lib.sh", "worktree_lib.sh"):
                shutil.copyfile(source_shared / name, shared_dir / name)
                (shared_dir / name).chmod(0o444)

            gh = bin_dir / "gh"
            gh.write_text(
                "#!/usr/bin/env bash\nif [[ ${1:-} == repo && ${2:-} == view ]]; then printf 'owner/repo\\n'; fi\n"
            )
            gh.chmod(0o755)
            zoxide = bin_dir / "zoxide"
            zoxide.write_text("#!/usr/bin/env bash\nexit 0\n")
            zoxide.chmod(0o755)
            tmux_log = root / "tmux.log"
            tmux_session = root / "tmux-session"
            tmux = bin_dir / "tmux"
            tmux.write_text(
                "#!/usr/bin/env bash\n"
                'printf \'%s\\n\' "$*" >> "$TMUX_LOG"\n'
                'case " $* " in\n'
                "  *' has-session '*) [[ -f \"$TMUX_SESSION_FILE\" ]] ;;\n"
                "  *' new-session '*)\n"
                "    if [[ -n ${TMUX_FAIL_ONCE_FILE:-} && -f $TMUX_FAIL_ONCE_FILE ]]; then\n"
                '      rm -f "$TMUX_FAIL_ONCE_FILE"\n'
                "      exit 1\n"
                "    fi\n"
                '    : > "$TMUX_SESSION_FILE"\n'
                "    ;;\n"
                "  *' list-clients '*) printf 'fixture-client\\n' ;;\n"
                "  *' switch-client '*) exit 0 ;;\n"
                "esac\n"
            )
            tmux.chmod(0o755)

            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "commit.gpgSign", "false"], cwd=repo, check=True)
            (repo / "README").write_text("fixture\n")
            subprocess.run(["git", "add", "README"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)

            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bin_dir}:/opt/homebrew/bin:/usr/bin:/bin",
                "COMMA_W_PRUNE": "0",
                "TMUX_LOG": str(tmux_log),
                "TMUX_SESSION_FILE": str(tmux_session),
                "TMUX_FAIL_ONCE_FILE": str(root / "tmux-fail-once"),
            }
            for key in ("TMUX", "TMUX_PANE", "OUTER_TMUX_SOCKET", "OUTER_TMUX_CLIENT"):
                env.pop(key, None)
            env["OUTER_TMUX_SOCKET"] = str(root / "outer.sock")

            result = subprocess.run(
                [modern_bash(), str(w_dir / "issue.sh"), "--focus", "-q", "-b", "fix/test/create", "123"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, result.stderr
            worktrees = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            assert "branch refs/heads/fix/test/create-123" in worktrees
            assert tmux_session.exists(), tmux_log.read_text() if tmux_log.exists() else "tmux was never invoked"
            assert f"-S {root / 'outer.sock'} new-session -d" in tmux_log.read_text()

            focus_result = subprocess.run(
                [modern_bash(), str(w_dir / "issue.sh"), "--focus", "-q", "123"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            assert focus_result.returncode == 0, focus_result.stderr

            manual_worktree = root / "manual-worktree"
            subprocess.run(
                ["git", "worktree", "add", "-b", "fix/test/manual", str(manual_worktree), "main"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            manual_focus_result = subprocess.run(
                [modern_bash(), str(w_dir / "issue.sh"), "--focus", "-q", "-b", "fix/test/manual", "456"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            assert manual_focus_result.returncode == 0, manual_focus_result.stderr

            switch_result = subprocess.run(
                [modern_bash(), str(w_dir / "switch.sh"), "-q", "fix/test/create-123"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            assert switch_result.returncode == 0, switch_result.stderr
            assert "switch-client -c fixture-client" in tmux_log.read_text()

            remove_result = subprocess.run(
                [
                    modern_bash(),
                    "-c",
                    'source "$1"; _remove_worktree_tmux_session 1 "$2" "$3"',
                    "fixture",
                    str(shared_dir / "worktree_lib.sh"),
                    str(manual_worktree),
                    "fixture-remove-session",
                ],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            assert remove_result.returncode == 0, remove_result.stderr
            assert "kill-session -t =fixture-remove-session" in tmux_log.read_text()

            tmux_session.unlink(missing_ok=True)
            fail_once = Path(env["TMUX_FAIL_ONCE_FILE"])
            fail_once.write_text("fail\n")
            first_attempt = subprocess.run(
                [modern_bash(), str(w_dir / "issue.sh"), "-q", "-b", "fix/test/retry", "789"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            assert first_attempt.returncode != 0, first_attempt.stderr
            assert not tmux_session.exists(), "failed new-session was reported as success"
            tmux_log.write_text("")

            retry = subprocess.run(
                [modern_bash(), str(w_dir / "issue.sh"), "-q", "789"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            assert retry.returncode == 0, retry.stderr
            assert tmux_session.exists(), "existing worktree did not retry session creation"
            expected_session = f"{root.name}|fix/test/retry-789"
            assert f"new-session -d -s {expected_session}" in tmux_log.read_text()

    def test_tmux_session_create_and_focus_use_exact_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            sessions = root / "sessions.txt"
            sessions.write_text("repo|fix-long\n")
            tmux_log = root / "tmux.log"
            tmux = bin_dir / "tmux"
            tmux.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$TMUX_LOG"
if [ "${1:-}" = "-S" ]; then shift 2; fi
command="${1:-}"
shift || true
target=""
session=""
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case "${args[i]}" in
    -t) target="${args[i + 1]}" ;;
    -s) session="${args[i + 1]}" ;;
  esac
done
matches_target() {
  local requested="$1"
  if [[ "$requested" == =* ]]; then
    grep -Fxq -- "${requested#=}" "$TMUX_SESSIONS"
  else
    awk -v prefix="$requested" 'index($0, prefix) == 1 { found = 1 } END { exit !found }' "$TMUX_SESSIONS"
  fi
}
case "$command" in
  has-session) matches_target "$target" ;;
  new-session) printf '%s\n' "$session" >> "$TMUX_SESSIONS" ;;
  list-clients) printf 'fixture-client\n' ;;
  switch-client | attach-session) matches_target "$target" ;;
esac
"""
            )
            tmux.chmod(0o755)
            worktree_path = root / "worktree"
            worktree_path.mkdir()
            shared = REPO / "home/exact_lib/exact_shared/worktree_lib.sh"
            probe = subprocess.run(
                [
                    modern_bash(),
                    "-c",
                    'source "$1"; _add_worktree_tmux_session 1 repo fix "$2"; '
                    '_comma_w_focus_tmux_session 1 "repo|fix" "$2"',
                    "fixture",
                    str(shared),
                    str(worktree_path),
                ],
                env={
                    **os.environ,
                    "HOME": str(root),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "OUTER_TMUX_SOCKET": str(root / "outer.sock"),
                    "OUTER_TMUX_CLIENT": "fixture-client",
                    "TMUX_LOG": str(tmux_log),
                    "TMUX_SESSIONS": str(sessions),
                },
                capture_output=True,
                text=True,
            )
            assert probe.returncode == 0, probe.stderr
            assert sessions.read_text().splitlines() == ["repo|fix-long", "repo|fix"]
            log = tmux_log.read_text()
            assert "has-session -t =repo|fix" in log
            assert "switch-client -c fixture-client -t =repo|fix" in log

    def test_should_invoke_pr_migration_helper_through_bash(self):
        source = (REPO / "home/exact_lib/exact_,w/prs.sh").read_text()
        assert 'bash "$(dirname "$0")/mv.sh"' in source
        assert (
            '_add_worktree_tmux_session "$quiet_mode" "$parent_name" "$local_branch" "$existing_path"\n'
            '    if [ "$focus_mode" -eq 1 ]; then'
        ) in source

    def test_pr_retry_repairs_session_after_new_session_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bin_dir = home / "bin"
            w_dir = home / "lib/,w"
            shared_dir = home / "lib/shared"
            repo = root / "repo"
            remote = root / "remote.git"
            for path in (bin_dir, w_dir, shared_dir, repo):
                path.mkdir(parents=True)

            shutil.copyfile(REPO / "home/exact_lib/exact_,w/prs.sh", w_dir / "prs.sh")
            (w_dir / "prs.sh").chmod(0o444)
            for name in ("bash_utils_lib.sh", "worktree_lib.sh"):
                shutil.copyfile(REPO / "home/exact_lib/exact_shared" / name, shared_dir / name)
                (shared_dir / name).chmod(0o444)

            gh = bin_dir / "gh"
            gh.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ ${1:-} == repo && ${2:-} == view ]]; then\n"
                "  printf 'owner\\trepo\\n'\n"
                "elif [[ ${1:-} == pr && ${2:-} == view ]]; then\n"
                "  printf 'feature/pr\\trepo\\towner\\n'\n"
                "fi\n"
            )
            gh.chmod(0o755)
            zoxide = bin_dir / "zoxide"
            zoxide.write_text("#!/usr/bin/env bash\nexit 0\n")
            zoxide.chmod(0o755)

            tmux_session = root / "tmux-session"
            fail_once = root / "tmux-fail-once"
            tmux = bin_dir / "tmux"
            tmux.write_text(
                "#!/usr/bin/env bash\n"
                'case " $* " in\n'
                "  *' has-session '*) [[ -f \"$TMUX_SESSION_FILE\" ]] ;;\n"
                "  *' new-session '*)\n"
                "    if [[ -f $TMUX_FAIL_ONCE_FILE ]]; then\n"
                '      rm -f "$TMUX_FAIL_ONCE_FILE"\n'
                "      exit 1\n"
                "    fi\n"
                '    : > "$TMUX_SESSION_FILE"\n'
                "    ;;\n"
                "esac\n"
            )
            tmux.chmod(0o755)

            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "commit.gpgSign", "false"], cwd=repo, check=True)
            (repo / "README").write_text("fixture\n")
            subprocess.run(["git", "add", "README"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "switch", "-c", "feature/pr"], cwd=repo, check=True, capture_output=True)
            (repo / "PR").write_text("pr\n")
            subprocess.run(["git", "add", "PR"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "pr"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", "feature/pr"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "switch", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "branch", "-D", "feature/pr"], cwd=repo, check=True, capture_output=True)

            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bin_dir}:/opt/homebrew/bin:/usr/bin:/bin",
                "COMMA_W_PRUNE": "0",
                "OUTER_TMUX_SOCKET": str(root / "outer.sock"),
                "TMUX_SESSION_FILE": str(tmux_session),
                "TMUX_FAIL_ONCE_FILE": str(fail_once),
            }
            env.pop("TMUX", None)
            env.pop("TMUX_PANE", None)
            fail_once.write_text("fail\n")

            first = subprocess.run(
                [modern_bash(), str(w_dir / "prs.sh"), "-q", "123"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            assert first.returncode != 0, first.stderr
            assert not tmux_session.exists(), "failed PR new-session was reported as success"

            retry = subprocess.run(
                [modern_bash(), str(w_dir / "prs.sh"), "-q", "123"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            assert retry.returncode == 0, retry.stderr
            assert tmux_session.exists(), "existing PR worktree did not retry session creation"


class TestArtifactCommand(unittest.TestCase):
    """WHEN creating cache-only browser artifacts."""

    def test_detects_dotfiles_ambient_theme(self):
        artifact = _load_artifact_command()

        theme = artifact.detect_ambient_theme(REPO)

        assert theme["name"] == "dotfiles"
        assert ".mermaids/" in theme["markers"]
        assert "home/" in theme["markers"]

    def test_injects_ambient_theme_once(self):
        artifact = _load_artifact_command()
        html_doc = "<!doctype html><html><head><title>x</title></head><body><main>hello</main></body></html>"

        themed = artifact.inject_ambient_theme(html_doc)
        twice = artifact.inject_ambient_theme(themed)

        assert artifact.AMBIENT_THEME_STYLE_ID in themed
        assert themed == twice
        assert themed.index(artifact.AMBIENT_THEME_STYLE_ID) < themed.index("</head>")

    def test_write_injects_theme_under_cache_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            source = Path(tmp) / "source.html"
            source.write_text("<!doctype html><html><head></head><body><main>demo</main></body></html>")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ARTIFACT_COMMAND),
                    "write",
                    "demo",
                    "--file",
                    str(source),
                ],
                cwd=REPO,
                env={**os.environ, "XDG_CACHE_HOME": str(cache)},
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, result.stderr
            output = Path(result.stdout.strip())
            assert output.is_file()
            assert cache.resolve() in output.resolve().parents
            assert "agent-artifact-ambient-theme" in output.read_text()

    def test_normalizes_feedback_batch_and_flattens_prompts(self):
        artifact = _load_artifact_command()

        batch = artifact.normalize_feedback_batch(
            {
                "items": [
                    {"prompt": "tighten this", "selector": "main > h1", "text": "Heading"},
                    {"prompt": "  ", "selector": "ignored"},
                    {"prompt": "add checklist", "selection": "selected text"},
                ]
            }
        )

        assert batch is not None
        assert batch["batch_id"]
        assert len(batch["items"]) == 2
        prompts = artifact.flatten_feedback_batches([batch])
        assert [item["prompt"] for item in prompts] == ["tighten this", "add checklist"]
        assert prompts[0]["item_index"] == 1
        assert prompts[1]["item_index"] == 2
        assert prompts[0]["batch_id"] == batch["batch_id"]

    def test_live_feedback_context_survives_normalization(self):
        artifact = _load_artifact_command()

        batch = artifact.normalize_feedback_batch(
            {
                "items": [
                    {
                        "prompt": "move this control",
                        "selector": 'button[data-test-subj="save"]',
                        "text": "Save",
                        "url": "http://localhost:5601/app/demo",
                        "title": "Demo - Kibana",
                        "role": "button",
                        "label": "Save changes",
                        "source": "live-overlay",
                        "rect": {"x": 10, "y": 20, "width": 30, "height": 40},
                        "ancestors": [{"selector": "form", "role": "form", "label": "Settings"}],
                    }
                ]
            }
        )

        assert batch is not None
        prompt = artifact.flatten_feedback_batches([batch])[0]
        assert prompt["source"] == "live-overlay"
        assert prompt["url"] == "http://localhost:5601/app/demo"
        assert prompt["role"] == "button"
        assert prompt["rect"]["width"] == 30
        assert prompt["ancestors"][0]["selector"] == "form"

    def test_feedback_poll_archives_delivered_batches(self):
        artifact = _load_artifact_command()

        with tempfile.TemporaryDirectory() as tmp:
            fdir = Path(tmp) / "feedback"
            fdir.mkdir()
            old_feedback_dir = artifact.feedback_dir
            artifact.feedback_dir = lambda: fdir
            try:
                pending = artifact.feedback_path("demo")
                pending.write_text('{"prompt":"tighten"}\n', encoding="utf-8")

                records, archive = artifact.read_and_archive_feedback("demo")

                assert [record["prompt"] for record in records] == ["tighten"]
                assert archive is not None
                assert archive.is_file()
                assert not pending.exists()
                assert archive.parent == fdir / "delivered"
            finally:
                artifact.feedback_dir = old_feedback_dir

    def test_clear_ended_allows_reusing_artifact_name(self):
        artifact = _load_artifact_command()

        with tempfile.TemporaryDirectory() as tmp:
            fdir = Path(tmp) / "feedback"
            fdir.mkdir()
            old_feedback_dir = artifact.feedback_dir
            artifact.feedback_dir = lambda: fdir
            try:
                ended = artifact.ended_path("demo")
                ended.write_text("", encoding="utf-8")

                artifact.clear_ended("demo")

                assert not ended.exists()
            finally:
                artifact.feedback_dir = old_feedback_dir

    def test_register_poller_tracks_current_session_and_unregisters(self):
        artifact = _load_artifact_command()

        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp) / "pollers"
            old_pollers_dir = artifact.pollers_dir
            artifact.pollers_dir = lambda: pdir
            try:
                artifact.register_poller("demo", 30)

                path = artifact.poller_path("demo")
                record = json.loads(path.read_text(encoding="utf-8"))
                assert record["artifact"] == "demo.html"
                assert record["pid"] == os.getpid()
                assert record["timeout"] == 30
                assert record["session_dir"]

                artifact.unregister_poller("demo")

                assert not path.exists()
            finally:
                artifact.pollers_dir = old_pollers_dir

    def test_stale_poller_records_are_pruned(self):
        artifact = _load_artifact_command()

        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp) / "pollers"
            pdir.mkdir()
            old_pollers_dir = artifact.pollers_dir
            artifact.pollers_dir = lambda: pdir
            try:
                stale = pdir / "demo.html.json"
                stale.write_text(json.dumps({"artifact": "demo.html", "pid": 999999999}) + "\n", encoding="utf-8")

                assert artifact.active_poller_records() == []
                assert not stale.exists()
            finally:
                artifact.pollers_dir = old_pollers_dir

    def test_current_pid_record_must_still_match_poller_command(self):
        artifact = _load_artifact_command()

        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp) / "pollers"
            pdir.mkdir()
            old_pollers_dir = artifact.pollers_dir
            artifact.pollers_dir = lambda: pdir
            try:
                stale = pdir / "demo.html.json"
                stale.write_text(json.dumps({"artifact": "demo.html", "pid": os.getpid()}) + "\n", encoding="utf-8")

                assert artifact.active_poller_records() == []
                assert not stale.exists()
            finally:
                artifact.pollers_dir = old_pollers_dir

    def test_poller_command_parser_extracts_artifact_name(self):
        artifact = _load_artifact_command()

        assert (
            artifact.poll_artifact_from_command("python3 /Users/me/bin/,artifact poll demo --timeout 60") == "demo.html"
        )
        assert (
            artifact.poll_artifact_from_command("python3 home/exact_lib/exact_,artifact/main.py poll")
            == "artifact.html"
        )
        assert artifact.poll_artifact_from_command("python3 /tmp/other poll demo") is None

    def test_stop_poller_record_does_not_kill_unmatched_pid(self):
        artifact = _load_artifact_command()

        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.html.json"
            record = {"artifact": "demo.html", "pid": child.pid, "path": str(path)}
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            try:
                artifact.stop_poller_record(record)

                assert child.poll() is None
                assert not path.exists()
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)

    def test_poll_stop_terminates_tracked_poller_process(self):
        command = [sys.executable, str(ARTIFACT_COMMAND)]

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            env = {**os.environ, "XDG_CACHE_HOME": str(cache)}
            child = subprocess.Popen(
                [*command, "poll", "demo", "--timeout", "60"],
                cwd=REPO,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                poller_file = next(cache.glob("agent-artifacts/sessions/*/*/pollers/demo.html.json"), None)
                deadline = time.time() + 5
                while poller_file is None and time.time() < deadline:
                    time.sleep(0.05)
                    poller_file = next(cache.glob("agent-artifacts/sessions/*/*/pollers/demo.html.json"), None)
                assert poller_file is not None

                result = subprocess.run(
                    [*command, "poll-stop", "demo"],
                    cwd=REPO,
                    env=env,
                    capture_output=True,
                    text=True,
                )

                assert result.returncode == 0, result.stderr
                child.wait(timeout=5)
                assert child.returncode is not None
                assert not poller_file.exists()
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)

    def test_chrome_exposes_hover_highlight_and_expanded_anchor_card(self):
        artifact = _load_artifact_command()

        injected = artifact.inject_client_script("<html><body><main><p>hello</p></main></body></html>")
        chrome = artifact.chrome_page("demo.html")

        assert "__agent_artifact_hover" in injected
        assert "__agent_artifact_selected" in injected
        assert "function areaTargetFor" in injected
        assert "function expandedTargetFor" in injected
        assert "document.documentElement" in injected
        assert "event.altKey" in injected
        assert "agent-artifact-ready" in injected
        assert "[data-card], .card, .panel, .callout" in injected
        assert 'class="anchor-card"' in chrome
        assert "Alt-click expands" in chrome
        assert "dock expanded upward" in chrome
        assert "expanded" in chrome

    def test_generated_feedback_mode_starts_hidden_and_gates_capture(self):
        artifact = _load_artifact_command()

        injected = artifact.inject_client_script("<html><body><button>Save</button></body></html>")
        chrome = artifact.chrome_page("demo.html")

        assert "let captureEnabled = false;" in injected
        assert 'event.data.type === "agent-artifact-capture"' in injected
        assert injected.count("if (!captureEnabled) return;") == 3
        assert "if (!captureEnabled) clearHighlights();" in injected
        assert 'id="feedbackToggle"' in chrome
        assert 'aria-expanded="false"' in chrome
        assert "let feedbackActive = false;" in chrome
        assert 'document.body.classList.toggle("feedback-active", feedbackActive)' in chrome
        assert "agent-artifact-capture" in chrome

    def test_live_overlay_script_exposes_pause_teardown_and_minimal_context(self):
        artifact = _load_artifact_command()

        script = artifact.live_overlay_script("live.html", "http://127.0.0.1:12345")

        assert "__agent_artifact_live_overlay" in script
        assert "attachShadow" in script
        assert 'source: "live-overlay"' in script
        assert "rect: rectOf(el)" in script
        assert "ancestors: ancestorsOf(el)" in script
        assert "pause" in script
        assert "destroy" in script
        assert "drain" in script
        assert "Local post blocked" in script
        assert "/api/feedback/" in script

    def test_live_start_serves_script_with_cors(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            env = {**os.environ, "XDG_CACHE_HOME": str(cache)}
            command = [sys.executable, str(ARTIFACT_COMMAND)]
            result = subprocess.run(
                [*command, "live", "start", "demo", "--json"],
                cwd=REPO,
                env=env,
                capture_output=True,
                text=True,
            )
            try:
                assert result.returncode == 0, result.stderr
                info = json.loads(result.stdout)
                script_response = urlopen(info["script_url"], timeout=5)
                assert script_response.headers["access-control-allow-origin"] == "*"
                assert "__agent_artifact_live_overlay" in script_response.read().decode()
                options = urlopen(
                    Request(info["feedback_url"], method="OPTIONS", headers={"origin": "http://localhost:5601"}),
                    timeout=5,
                )
                assert options.status == 204
                assert options.headers["access-control-allow-origin"] == "*"
            finally:
                subprocess.run([*command, "stop"], cwd=REPO, env=env, capture_output=True, text=True)


class TestUnwrapMdCommand(unittest.TestCase):
    """WHEN unwrapping markdown prose."""

    def test_unwraps_regular_markdown_paragraphs(self):
        unwrap_md = _load_unwrap_md_command()
        text = "This is one paragraph\nthat was hard wrapped.\n\n- Keep list items\n  structural.\n"

        result = unwrap_md.unwrap(text, "docs/topics/example.md")

        assert result == "This is one paragraph that was hard wrapped.\n\n- Keep list items structural.\n"

    def test_normalizes_sop_instruction_short_sentence_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Keep this gate visible.\nDo not hide it later in the same line.\n"

        result = unwrap_md.unwrap(text, "home/readonly_AGENTS.md")

        assert result == "Keep this gate visible. Do not hide it later in the same line.\n"

    def test_normalizes_conform_temp_sop_entrypoint_as_ai_markdown(self):
        unwrap_md = _load_unwrap_md_command()
        text = (
            "This SOP is not optional guidance — it is a binding operational contract. "
            "Every instruction herein MUST be followed to the letter, without exception.\n"
        )

        result = unwrap_md.unwrap(text, "home/.conform.1234567.readonly_AGENTS.md")

        assert result == (
            "This SOP is not optional guidance — it is a binding operational contract.\n"
            "Every instruction herein MUST be followed to the letter, without exception.\n"
        )

    def test_normalizes_skill_instruction_short_sentence_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Use when the exact trigger matches.\nLoad the skill before acting.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == "Use when the exact trigger matches. Load the skill before acting.\n"

    def test_normalizes_skill_instruction_wraps_without_splitting_short_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Finish a sentence before moving\nto the next line. Start the next sentence on its own line.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == "Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"

    def test_normalizes_skill_list_items_without_splitting_short_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "- Finish a sentence before moving\n  to the next line. Start the next sentence on its own line.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert (
            result == "- Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"
        )

    def test_preserves_indented_skill_prose_prefixes(self):
        unwrap_md = _load_unwrap_md_command()
        text = "   Finish a sentence before moving\n   to the next line. Start the next sentence on its own line.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert (
            result == "   Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"
        )

    def test_wraps_skill_prose_at_sentence_boundary_over_soft_limit(self):
        unwrap_md = _load_unwrap_md_command()
        text = (
            "This sentence is deliberately long enough that appending the next sentence would cross the formatter boundary "
            "without needing to split this sentence. Start the next sentence on its own line.\n"
        )

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == (
            "This sentence is deliberately long enough that appending the next sentence would cross the formatter boundary without needing to split this sentence.\n"
            "Start the next sentence on its own line.\n"
        )

    def test_wraps_single_long_skill_sentence_at_clause_boundary(self):
        unwrap_md = _load_unwrap_md_command()
        text = (
            "Keep the review gate visible for the controller because workers cannot mutate shared state safely; "
            "and return verification needs instead of running destructive probes inside parallel lanes.\n"
        )

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == (
            "Keep the review gate visible for the controller because workers cannot mutate shared state safely;\n"
            "and return verification needs instead of running destructive probes inside parallel lanes.\n"
        )

    def test_keeps_single_long_skill_sentence_without_strong_clause_boundary(self):
        unwrap_md = _load_unwrap_md_command()
        text = (
            "Review documentation updates preserve routing metadata through generated summaries across delegated workflows "
            "to keep every prompt input readable during later audits while retaining the exact details reviewers need.\n"
        )

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == text

    def test_preserves_multiline_inline_code_examples(self):
        unwrap_md = _load_unwrap_md_command()
        text = "- `First sentence. Second sentence\nwithout closing until here.`\n"

        result = unwrap_md.unwrap(text, "home/readonly_AGENTS.md")

        assert result == text

    def test_does_not_split_common_abbreviations_as_skill_sentences(self):
        unwrap_md = _load_unwrap_md_command()
        text = 'Use examples, e.g. "the review skill", before acting. Then continue.\n'

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == 'Use examples, e.g. "the review skill", before acting. Then continue.\n'

    def test_normalizes_skill_reference_short_sentence_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Keep the review gate visible.\nDo not bury it after another clause.\n"

        result = unwrap_md.unwrap(
            text,
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_common.md",
        )

        assert result == "Keep the review gate visible. Do not bury it after another clause.\n"

    def test_normalizes_agent_hook_short_sentence_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Keep hook behavior visible.\nDo not collapse support instructions.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_hooks/readonly_README.md")

        assert result == "Keep hook behavior visible. Do not collapse support instructions.\n"


class TestMcpTokenCommand(unittest.TestCase):
    """WHEN selecting cached MCP OAuth tokens."""

    def _jwt(self, exp: int) -> str:
        def encode(value: dict[str, object]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'exp': exp})}.sig"

    def _write_cache(self, home: Path, access_token: str, *, server: str = "scsi-main") -> Path:
        cache = home / ".cursor/projects/p/mcp-auth.json"
        cache.parent.mkdir(parents=True)
        cache.write_text(
            json.dumps(
                {
                    server: {
                        "tokens": {
                            "access_token": access_token,
                            "expires_in": 3600,
                            "token_type": "Bearer",
                        }
                    }
                }
            )
        )
        os.utime(cache, None)
        return cache

    def test_jwt_expiry_overrides_fresh_cache_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self._write_cache(home, self._jwt(int(time.time()) + 60))
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "scsi-main"],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home)},
            )

        assert result.returncode == 1
        assert "no valid scsi-main token" in result.stderr

    def test_jwt_token_with_sufficient_expiry_is_selected(self):
        token = self._jwt(int(time.time()) + 900)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self._write_cache(home, token)
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "scsi-main", "--json"],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home)},
            )

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["token"] == token
        assert payload["seconds_left"] > 300

    def test_login_force_refreshes_opaque_tokens_without_trusting_cache_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bindir = root / "bin"
            bindir.mkdir()
            cache = self._write_cache(home, "opaque-slack-token", server="slack")
            (bindir / "cursor-agent").write_text(
                "#!/usr/bin/env bash\n"
                'if [ "$1 $2" = "mcp login" ]; then\n'
                f"  touch {shlex.quote(str(cache))}\n"
                "fi\n"
                "exit 0\n"
            )
            (bindir / "cursor-agent").chmod(0o755)
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "slack", "--login"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                },
            )

        assert result.returncode == 0, result.stderr
        assert "running cursor-agent mcp login slack" in result.stderr
        assert result.stdout.strip() == "opaque-slack-token"

    def test_plain_read_does_not_trust_opaque_cache_mtime_without_login_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self._write_cache(home, "opaque-slack-token", server="slack")
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "slack"],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home)},
            )

        assert result.returncode == 1
        assert "no valid slack token" in result.stderr

    def test_login_without_cursor_agent_reports_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "scsi-main", "--login"],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home), "PATH": str(bindir)},
            )

        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert "cursor-agent not found" in result.stderr


class _LivenessHandler(http.server.BaseHTTPRequestHandler):
    """Classifies an MCP ``initialize`` POST by its bearer token.

    ``status_by_token`` maps an access token to the HTTP status the fake Slack
    MCP endpoint should return (200 live, 401/403 revoked, 500 server error).
    Unknown tokens are treated as revoked (401). Every hit is counted so tests
    can assert the plain-read / JWT paths never touch the network.
    """

    status_by_token: dict[str, int] = {}
    hits: list[str] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        self.rfile.read(length)
        auth = self.headers.get("Authorization", "")
        token = auth[len("Bearer ") :] if auth.startswith("Bearer ") else ""
        type(self).hits.append(token)
        code = type(self).status_by_token.get(token, 401)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        # A response body the command must never echo to stdout/stderr.
        self.wfile.write(b'{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"slack"}}}')

    def log_message(self, *args):  # silence access logging
        return


@contextlib.contextmanager
def _liveness_server(status_by_token: dict[str, int]):
    """Run the classifying MCP endpoint on localhost; yield (url, handler)."""

    class Handler(_LivenessHandler):
        pass

    Handler.status_by_token = dict(status_by_token)
    Handler.hits = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/mcp", Handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class _SinkHandler(http.server.BaseHTTPRequestHandler):
    """Records every request that reaches a redirect target (a second origin).

    The liveness probe must never follow a 3xx and resend the bearer here; each
    hit captures the method and Authorization header so a test can prove none of
    the token ever crossed to this origin.
    """

    hits: list[dict[str, str]] = []

    def _record(self, method: str) -> None:
        type(self).hits.append({"method": method, "authorization": self.headers.get("Authorization", "")})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"sink"}}}')

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        self.rfile.read(length)
        self._record("POST")

    def do_GET(self):  # noqa: N802
        self._record("GET")

    def log_message(self, *args):  # silence access logging
        return


@contextlib.contextmanager
def _redirecting_endpoint(status: int = 302):
    """Yield (probe_url, sink_handler); probe_url answers with a 3xx to the sink.

    ``probe_url`` is the URL the command reads from ``~/.cursor/mcp.json``. It
    responds to the probe with an HTTP *status* redirect whose ``Location`` is a
    different origin (the sink). A safe probe treats the 3xx as UNKNOWN and never
    contacts the sink; the sink's recorded hits expose a bearer-forwarding leak.
    """

    class Sink(_SinkHandler):
        pass

    Sink.hits = []
    sink = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Sink)
    sink_url = f"http://127.0.0.1:{sink.server_address[1]}/sink"

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0") or "0")
            self.rfile.read(length)
            self.send_response(status)
            self.send_header("Location", sink_url)
            self.end_headers()

        def log_message(self, *args):
            return

    redirect = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    probe_url = f"http://127.0.0.1:{redirect.server_address[1]}/mcp"
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (sink, redirect)]
    for t in threads:
        t.start()
    try:
        yield probe_url, Sink
    finally:
        for s in (sink, redirect):
            s.shutdown()
            s.server_close()
        for t in threads:
            t.join()


class TestMcpTokenWorkspaceCache(unittest.TestCase):
    """WHEN resolving Cursor's current-workspace OAuth cache locally."""

    def test_trusted_workspace_metadata_matches_resolved_paths(self):
        mod = _load_mcp_token_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "home/.cursor/projects"
            project = projects / "p"
            workspace = root / "workspace"
            logical_workspace = root / "logical-workspace"
            project.mkdir(parents=True)
            workspace.mkdir()
            logical_workspace.symlink_to(workspace)
            (project / ".workspace-trusted").write_text(json.dumps({"workspacePath": str(logical_workspace)}))
            with mock.patch.object(mod, "CURSOR_CACHE_GLOB", str(projects / "*/mcp-auth.json")):
                path = mod._cursor_workspace_cache_path(str(workspace))

        assert path == str(project / "mcp-auth.json")

    def test_deterministic_slug_fallback_matches_cursor_project_paths(self):
        mod = _load_mcp_token_module()
        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp) / "home/.cursor/projects"
            with mock.patch.object(mod, "CURSOR_CACHE_GLOB", str(projects / "*/mcp-auth.json")):
                path = mod._cursor_workspace_cache_path("/Users/example/work/a_b")

        assert path == str(projects / "Users-example-work-a-b/mcp-auth.json")


class TestMcpTokenLoginLiveness(unittest.TestCase):
    """WHEN ``,mcp-token <server> --login`` validates opaque-token liveness.

    Opaque tokens (e.g. Slack) can be revoked while the local ledger still pins
    them as nominally fresh. ``--login`` must probe the ledger-selected token
    against the server URL from the generated ``~/.cursor/mcp.json`` and recover
    a live cached alternative or run cursor login, instead of returning a dead
    token. These are real-seam tests: a local HTTP endpoint classifies tokens,
    an isolated ``HOME`` holds the caches/ledger/config, and a stub cursor-agent
    stands in for the browser flow. No network mocks assert the command's own
    helpers.
    """

    def _sha(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _write_cache(self, home: Path, name: str, server: str, token: str, *, age: float = 0.0) -> None:
        cache = home / ".cursor/projects" / name / "mcp-auth.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({server: {"tokens": {"access_token": token, "expires_in": 3600}}}))
        if age:
            when = time.time() - age
            os.utime(cache, (when, when))

    def _write_mcp_json(self, home: Path, server: str, url: str | None) -> None:
        cfg = home / ".cursor/mcp.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, object] = {}
        if url is not None:
            entry["url"] = url
        cfg.write_text(json.dumps({"mcpServers": {server: entry}}))

    def _write_ledger(self, home: Path, server: str, token: str, source: str) -> None:
        state_dir = home / ".cache/mcp-token"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "opaque-refresh.json").write_text(
            json.dumps({server: {"source": source, "token_sha256": self._sha(token), "refreshed_at": time.time()}})
        )

    def _read_ledger(self, home: Path, server: str) -> dict[str, object]:
        try:
            with open(home / ".cache/mcp-token/opaque-refresh.json") as f:
                return json.load(f).get(server, {})
        except (OSError, ValueError):
            return {}

    def _stub_cursor_agent(self, bindir: Path, home: Path, server: str, *, writes_token: str | None) -> Path:
        marker = home / "cursor-agent-ran"
        lines = ["#!/usr/bin/env bash", f"touch {shlex.quote(str(marker))}"]
        if writes_token is not None:
            cache = home / ".cursor/projects/login/mcp-auth.json"
            payload = json.dumps({server: {"tokens": {"access_token": writes_token, "expires_in": 3600}}})
            lines += [
                f"mkdir -p {shlex.quote(str(cache.parent))}",
                f"cat > {shlex.quote(str(cache))} <<'EOF'\n{payload}\nEOF",
            ]
        lines.append("exit 0")
        agent = bindir / "cursor-agent"
        agent.write_text("\n".join(lines) + "\n")
        agent.chmod(0o755)
        return marker

    def _run(self, home: Path, bindir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MCP_TOKEN_COMMAND), *args],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )

    def _jwt(self, exp: int) -> str:
        def encode(value: dict[str, object]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'exp': exp})}.sig"

    def test_revoked_ledger_token_selects_live_cached_alternative_and_repoints_ledger(self):
        revoked = "opaque-revoked-ledger"
        live = "opaque-live-alternative"
        with _liveness_server({revoked: 401, live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "old", "slack", revoked, age=100)
            self._write_cache(home, "new", "slack", live, age=10)
            self._write_ledger(home, "slack", revoked, str(home / ".cursor/projects/old/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()
            ledger_sha = self._read_ledger(home, "slack").get("token_sha256")

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == live
        assert not cursor_ran, "cursor-agent must not run when a live cached token exists"
        assert ledger_sha == self._sha(live)
        assert revoked not in result.stderr and live not in result.stderr

    def test_live_ledger_token_skips_login(self):
        live = "opaque-live-ledger"
        with _liveness_server({live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", live)
            self._write_ledger(home, "slack", live, str(home / ".cursor/projects/p/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()
            hits = list(handler.hits)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == live
        assert not cursor_ran
        assert hits == [live], "exactly the ledger token should be probed"

    def test_server_error_retains_nominal_ledger_candidate_without_promoting_alternative(self):
        nominal = "opaque-nominal-5xx"
        other = "opaque-other-live"
        with _liveness_server({nominal: 500, other: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "old", "slack", nominal, age=100)
            self._write_cache(home, "new", "slack", other, age=10)
            self._write_ledger(home, "slack", nominal, str(home / ".cursor/projects/old/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()
            ledger_sha = self._read_ledger(home, "slack").get("token_sha256")

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == nominal, "unknown liveness must preserve the nominal ledger token"
        assert not cursor_ran
        assert ledger_sha == self._sha(nominal)

    def test_network_error_retains_nominal_ledger_candidate(self):
        nominal = "opaque-nominal-neterr"
        # Reserve then release a port so the config URL points at a closed socket.
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        dead_port = probe.getsockname()[1]
        probe.close()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", f"http://127.0.0.1:{dead_port}/mcp")
            self._write_cache(home, "p", "slack", nominal)
            self._write_ledger(home, "slack", nominal, str(home / ".cursor/projects/p/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == nominal
        assert not cursor_ran

    def test_all_revoked_triggers_cursor_login_and_accepts_new_live_token(self):
        revoked = "opaque-all-revoked"
        fresh = "opaque-fresh-from-login"
        with _liveness_server({revoked: 401, fresh: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", revoked, age=100)
            self._write_ledger(home, "slack", revoked, str(home / ".cursor/projects/p/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=fresh)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()
            ledger_sha = self._read_ledger(home, "slack").get("token_sha256")

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh
        assert cursor_ran, "cursor-agent login must run when every cached token is revoked"
        assert ledger_sha == self._sha(fresh)

    def test_cursor_login_writing_still_revoked_token_is_not_success(self):
        revoked = "opaque-revoked-a"
        still_revoked = "opaque-revoked-b"
        with (
            _liveness_server({revoked: 401, still_revoked: 401}) as (url, handler),
            tempfile.TemporaryDirectory() as tmp,
        ):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", revoked, age=100)
            self._write_ledger(home, "slack", revoked, str(home / ".cursor/projects/p/mcp-auth.json"))
            self._stub_cursor_agent(bindir, home, "slack", writes_token=still_revoked)
            result = self._run(home, bindir, ["slack", "--login"])

        assert result.returncode == 1, "cursor exit 0 with a still-revoked token must not count as success"
        assert result.stdout.strip() == ""
        assert "did not yield a live token" in result.stderr
        assert revoked not in result.stderr and still_revoked not in result.stderr

    def test_force_invokes_login_even_when_ledger_token_is_live(self):
        live = "opaque-live-but-forced"
        fresh = "opaque-forced-fresh"
        with _liveness_server({live: 200, fresh: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", live)
            self._write_ledger(home, "slack", live, str(home / ".cursor/projects/p/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=fresh)
            result = self._run(home, bindir, ["slack", "--login", "--force", "--quiet"])
            cursor_ran = marker.exists()

        assert result.returncode == 0, result.stderr
        assert cursor_ran, "--force must always run the browser login"
        assert result.stdout.strip() == fresh

    def test_jwt_login_short_circuit_makes_no_liveness_probe(self):
        token = self._jwt(int(time.time()) + 1200)
        with _liveness_server({}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "scsi-main", url)
            self._write_cache(home, "p", "scsi-main", token)
            marker = self._stub_cursor_agent(bindir, home, "scsi-main", writes_token=None)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            cursor_ran = marker.exists()
            hits = list(handler.hits)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == token
        assert not cursor_ran
        assert hits == [], "a fresh JWT must short-circuit without a liveness probe"

    def test_plain_read_makes_no_liveness_probe(self):
        live = "opaque-live-plain"
        with _liveness_server({live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", live)
            self._write_ledger(home, "slack", live, str(home / ".cursor/projects/p/mcp-auth.json"))
            result = self._run(home, bindir, ["slack"])
            hits = list(handler.hits)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == live
        assert hits == [], "plain reads must stay local with no network probe"

    def test_login_never_leaks_token_or_response_body_on_stderr(self):
        revoked = "opaque-leak-check-revoked"
        live = "opaque-leak-check-live"
        with _liveness_server({revoked: 401, live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "old", "slack", revoked, age=100)
            self._write_cache(home, "new", "slack", live, age=10)
            self._write_ledger(home, "slack", revoked, str(home / ".cursor/projects/old/mcp-auth.json"))
            self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            # Not --quiet: any status text streams to stderr, mimicking wrappers.
            result = self._run(home, bindir, ["slack", "--login"])

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == live
        assert revoked not in result.stderr
        assert live not in result.stderr
        assert "serverInfo" not in result.stderr

    def test_login_probe_does_not_follow_redirect_or_leak_bearer_to_other_origin(self):
        # A 3xx from the probe URL must be UNKNOWN: the bearer must never be
        # resent to the redirect target, whose 200 would otherwise read LIVE.
        nominal = "opaque-redirect-nominal"
        with _redirecting_endpoint(302) as (url, sink), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", nominal)
            self._write_ledger(home, "slack", nominal, str(home / ".cursor/projects/p/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()
            sink_hits = list(sink.hits)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == nominal, "an unfollowed 3xx is UNKNOWN and must preserve the nominal token"
        assert sink_hits == [], f"probe must not follow the redirect to another origin; sink saw {sink_hits}"
        assert not cursor_ran, "unknown liveness must not force a browser login"
        assert nominal not in result.stderr

    def test_force_login_writing_revoked_token_does_not_adopt_preexisting_live_cache(self):
        # --force browser login that yields a revoked token is a failure; a live
        # token that predates this login must not rescue it.
        old_live = "opaque-old-live-preexisting"
        new_revoked = "opaque-new-revoked-from-login"
        with (
            _liveness_server({old_live: 200, new_revoked: 401}) as (url, handler),
            tempfile.TemporaryDirectory() as tmp,
        ):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "old", "slack", old_live, age=100)
            self._write_ledger(home, "slack", old_live, str(home / ".cursor/projects/old/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=new_revoked)
            result = self._run(home, bindir, ["slack", "--login", "--force", "--quiet"])
            cursor_ran = marker.exists()
            ledger_sha = self._read_ledger(home, "slack").get("token_sha256")

        assert result.returncode == 1, "a failed browser login must not be rescued by a pre-login live cache"
        assert result.stdout.strip() == "", "no token may be printed when browser login failed"
        assert old_live not in result.stdout
        assert cursor_ran
        assert ledger_sha == self._sha(old_live), "failed login must not repoint the ledger"

    def test_force_login_writing_no_token_fails_even_with_live_cache(self):
        # cursor login that writes/touches no cache produced nothing this attempt;
        # a pre-existing live cache must not make that count as success.
        old_live = "opaque-old-live-nowrite"
        with _liveness_server({old_live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "old", "slack", old_live, age=100)
            self._write_ledger(home, "slack", old_live, str(home / ".cursor/projects/old/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--force", "--quiet"])
            cursor_ran = marker.exists()

        assert result.returncode == 1, "login that writes/touches no cache is a failure even with a live cache"
        assert result.stdout.strip() == ""
        assert cursor_ran

    def test_adopted_cached_alternative_reports_conservative_verification_lease(self):
        # A provider-verified cached alternative gets a short verification lease,
        # not the provider's full nominal lifetime.
        revoked = "opaque-nominal-revoked-lease"
        old_live = "opaque-old-live-alt-lease"
        with _liveness_server({revoked: 401, old_live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "n", "slack", revoked, age=0)
            # An alternative already ~3500s into its nominal 3600s life.
            self._write_cache(home, "old", "slack", old_live, age=3500)
            self._write_ledger(home, "slack", revoked, str(home / ".cursor/projects/n/mcp-auth.json"))
            self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet", "--json"])

        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["token"] == old_live, "the live cached alternative must be adopted"
        seconds_left = payload["seconds_left"]
        mod = _load_mcp_token_module()
        assert mod.EXPIRY_SKEW_SECONDS < seconds_left <= mod.VERIFIED_ADOPTION_TTL_SECONDS, (
            "adopted alternative must report a conservative verification lease "
            f"(> {mod.EXPIRY_SKEW_SECONDS}, <= {mod.VERIFIED_ADOPTION_TTL_SECONDS}), got {seconds_left}"
        )


class TestMcpTokenSilentRotation(unittest.TestCase):
    """WHEN ``--login`` rotates a short or stale token via cursor's refresh grant.

    cursor silently executes the provider's ``refresh_token`` grant whenever a
    stored access token stops working, so ``--login`` invalidates the cached
    access token and runs a targeted ``cursor-agent mcp list-tools <server>``
    in the cache's resolvable workspace instead of popping a browser. These are
    real-seam tests: an isolated ``HOME`` holds caches/ledger/config and a stub
    cursor-agent records its argv/cwd and plays the provider's rotation.
    """

    def _jwt(self, exp: int) -> str:
        def encode(value: dict[str, object]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'exp': exp})}.sig"

    def _sha(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _write_rotatable_cache(
        self,
        home: Path,
        name: str,
        server: str,
        token: str,
        *,
        refresh_token: str | None = "refresh-chain",
        workspace: Path | None = None,
    ) -> Path:
        project = home / ".cursor/projects" / name
        project.mkdir(parents=True, exist_ok=True)
        tokens: dict[str, object] = {"access_token": token, "expires_in": 3600}
        if refresh_token is not None:
            tokens["refresh_token"] = refresh_token
        cache = project / "mcp-auth.json"
        cache.write_text(json.dumps({server: {"tokens": tokens}}))
        if workspace is not None:
            workspace.mkdir(parents=True, exist_ok=True)
            (project / ".workspace-trusted").write_text(json.dumps({"workspacePath": str(workspace)}))
        return cache

    def _write_mcp_json(self, home: Path, server: str, url: str | None) -> None:
        cfg = home / ".cursor/mcp.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, object] = {}
        if url is not None:
            entry["url"] = url
        cfg.write_text(json.dumps({"mcpServers": {server: entry}}))

    def _write_ledger(self, home: Path, server: str, token: str, source: str) -> None:
        state_dir = home / ".cache/mcp-token"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "opaque-refresh.json").write_text(
            json.dumps({server: {"source": source, "token_sha256": self._sha(token), "refreshed_at": time.time()}})
        )

    def _read_ledger(self, home: Path, server: str) -> dict[str, object]:
        try:
            with open(home / ".cache/mcp-token/opaque-refresh.json") as f:
                return json.load(f).get(server, {})
        except (OSError, ValueError):
            return {}

    def _stub_rotating_cursor_agent(
        self,
        bindir: Path,
        home: Path,
        cache: Path,
        server: str,
        *,
        rotates_to: str | None,
    ) -> Path:
        """Stub cursor-agent: logs ``cwd argv`` per call; ``mcp list-tools`` plays the refresh grant."""
        log = home / "cursor-agent.log"
        lines = ["#!/usr/bin/env bash", f'echo "$PWD $*" >> {shlex.quote(str(log))}']
        if rotates_to is not None:
            payload = json.dumps(
                {server: {"tokens": {"access_token": rotates_to, "refresh_token": "rotated-chain", "expires_in": 3600}}}
            )
            lines += [
                'if [ "$1 $2" = "mcp list-tools" ]; then',
                f"cat > {shlex.quote(str(cache))} <<'EOF'\n{payload}\nEOF",
                "fi",
            ]
        lines.append("exit 0")
        agent = bindir / "cursor-agent"
        agent.write_text("\n".join(lines) + "\n")
        agent.chmod(0o755)
        return log

    def _run(
        self,
        home: Path,
        bindir: Path,
        args: list[str],
        *,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MCP_TOKEN_COMMAND), *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )

    def test_SHOULD_bound_cursor_server_approval(self):
        mod = _load_mcp_token_module()
        with mock.patch.object(
            mod.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["cursor-agent", "mcp", "enable"], 1),
        ) as run:
            approved = mod._enable_cursor_server("scsi-main", "/tmp")

        assert approved is False
        assert run.call_args.kwargs["timeout"] == mod.ROTATE_TIMEOUT_SECONDS

    def test_short_jwt_rotates_silently_in_trusted_workspace_without_browser(self):
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        fresh = self._jwt(int(time.time()) + 3600)
        with _liveness_server({}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "scsi-main", url)
            cache = self._write_rotatable_cache(home, "p", "scsi-main", short, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=fresh)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            calls = log.read_text().splitlines() if log.exists() else []
            hits = list(handler.hits)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh, "the rotated token must be selected"
        assert len(calls) == 2, calls
        assert calls[0].endswith(" mcp enable scsi-main"), calls
        cwd_str, sep, invoked = calls[1].partition(" mcp ")
        assert sep and invoked == "list-tools scsi-main", calls
        assert Path(cwd_str).resolve() == workspace.resolve(), "rotation must run in the cache's trusted workspace"
        assert hits == [], "JWT rotation must not probe the server"

    def test_mint_workspace_forces_rotation_cwd_when_user_config_is_bridge(self):
        """WHEN user mcp.json is a bridge, rotate/login must use the mint OAuth cwd."""
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            workspace.mkdir()
            mint = home / ".cache/mcp-token/oauth-mint"
            mint_mcp = mint / ".cursor/mcp.json"
            mint_mcp.parent.mkdir(parents=True)
            mint_mcp.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "scsi-main": {
                                "url": "https://semantic-code-search.example/mcp",
                                "oauth": {"clientId": "mint-client"},
                            }
                        }
                    }
                )
            )
            (home / ".cursor").mkdir(parents=True)
            (home / ".cursor/mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "scsi-main": {
                                "command": ",mcp-token",
                                "args": [
                                    "scsi-main",
                                    "--bridge",
                                    "--url",
                                    "https://semantic-code-search.example/mcp",
                                ],
                            }
                        }
                    }
                )
            )
            donor = self._write_rotatable_cache(home, "donor", "scsi-main", short, workspace=workspace)
            mint_slug = re.sub(r"[^A-Za-z0-9]+", "-", str(mint.resolve())).strip("-")
            mint_cache = home / ".cursor/projects" / mint_slug / "mcp-auth.json"
            log = self._stub_rotating_cursor_agent(bindir, home, mint_cache, "scsi-main", rotates_to=fresh)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"], cwd=workspace)
            calls = log.read_text().splitlines() if log.exists() else []
            donor_token = json.loads(donor.read_text())["scsi-main"]["tokens"]["access_token"]

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh
        assert len(calls) == 2, calls
        for call, expected in zip(calls, ("enable scsi-main", "list-tools scsi-main")):
            cwd_str, sep, invoked = call.partition(" mcp ")
            assert sep and invoked == expected, calls
            assert Path(cwd_str).resolve() == mint.resolve(), calls
        assert donor_token == short, "donor cache must not be the rotation target when mint exists"

    def test_expired_jwt_with_refresh_is_not_workspace_ready(self):
        mod = _load_mcp_token_module()
        expired = self._jwt(int(time.time()) - 60)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, workspace = root / "home", root / "ws"
            home.mkdir()
            workspace.mkdir()
            env_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            try:
                mod.CURSOR_CACHE_GLOB = str(home / ".cursor/projects/*/mcp-auth.json")
                cache = home / ".cursor/projects" / re.sub(r"[^A-Za-z0-9]+", "-", str(workspace.resolve())).strip("-")
                cache.mkdir(parents=True)
                (cache / "mcp-auth.json").write_text(
                    json.dumps(
                        {
                            "scsi-main": {
                                "tokens": {
                                    "access_token": expired,
                                    "refresh_token": "still-here",
                                    "expires_in": 3600,
                                }
                            }
                        }
                    )
                )
                status = None
                cwd = os.getcwd()
                try:
                    os.chdir(workspace)
                    status = mod._cursor_workspace_auth_status("scsi-main")
                finally:
                    os.chdir(cwd)
            finally:
                os.environ["HOME"] = env_home

        assert status == mod.WORKSPACE_REQUIRES_AUTH

    def test_expired_untrusted_cache_rotates_through_the_current_workspace(self):
        expired = self._jwt(int(time.time()) - 100)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "current-workspace"
            home.mkdir()
            bindir.mkdir()
            workspace.mkdir()
            source = self._write_rotatable_cache(home, "untrusted-source", "scsi-main", expired)
            project_slug = re.sub(r"[^A-Za-z0-9]+", "-", str(workspace.resolve())).strip("-")
            current_cache = home / ".cursor/projects" / project_slug / "mcp-auth.json"
            log = self._stub_rotating_cursor_agent(bindir, home, current_cache, "scsi-main", rotates_to=fresh)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"], cwd=workspace)
            calls = log.read_text().splitlines() if log.exists() else []
            source_access_token = json.loads(source.read_text())["scsi-main"]["tokens"]["access_token"]

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh
        assert len(calls) == 2, calls
        assert calls[0].endswith(" mcp enable scsi-main"), calls
        cwd_str, sep, invoked = calls[1].partition(" mcp ")
        assert sep and invoked == "list-tools scsi-main", calls
        assert Path(cwd_str).resolve() == workspace.resolve()
        assert not any("mcp login" in call for call in calls)
        assert source_access_token == expired

    def test_no_proactive_rotation_defers_short_jwt_rotation(self):
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", short, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            result = self._run(
                home,
                bindir,
                ["scsi-main", "--login", "--quiet", "--no-proactive-rotation"],
                cwd=workspace,
            )
            cursor_ran = log.exists()

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == short, "the still-valid token must be returned without waiting"
        assert not cursor_ran, "a ready workspace cache must not launch cursor-agent during preflight"

    def test_no_proactive_rotation_keeps_critical_rotation_blocking(self):
        mod = _load_mcp_token_module()
        critical = self._jwt(int(time.time()) + mod.BLOCKING_ROTATE_TTL_SECONDS - 60)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", critical, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=fresh)
            result = self._run(
                home,
                bindir,
                ["scsi-main", "--login", "--quiet", "--no-proactive-rotation"],
                cwd=workspace,
            )
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh
        assert any("mcp list-tools scsi-main" in call for call in calls)

    def test_rotate_after_reject_adopts_concurrent_rotation_without_regrant(self):
        # Worker 1 already rotated the chain; worker 2's 401-triggered rotation
        # must adopt the fresh token under the lock instead of overwriting it
        # with another sentinel-and-grant cycle.
        mod = _load_mcp_token_module()
        rejected = self._jwt(int(time.time()) + 1200)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", fresh, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=fresh)
            env_home, env_path = os.environ.get("HOME"), os.environ.get("PATH")
            os.environ["HOME"] = str(home)
            os.environ["PATH"] = f"{bindir}{os.pathsep}{env_path}"
            try:
                mod.CURSOR_CACHE_GLOB = str(home / ".cursor/projects/*/mcp-auth.json")
                mod.ROTATION_LOCK = str(home / ".cache/mcp-token/rotation.lock")
                mod.OPAQUE_REFRESH_STATE = str(home / ".cache/mcp-token/opaque-refresh.json")
                adopted = mod._rotate_after_reject("scsi-main", rejected)
                rotated_same = mod._rotate_after_reject("scsi-main", fresh)
            finally:
                os.environ["HOME"] = env_home
                os.environ["PATH"] = env_path
            calls = log.read_text().splitlines() if log.exists() else []

        assert adopted is True, "a differing cached token proves another worker already rotated"
        assert rotated_same is True, "rejecting the currently cached token must execute the grant"
        assert len(calls) == 2, f"only one enable plus the same-token grant may run cursor-agent, got {calls}"

    def test_concurrent_logins_rotate_once(self):
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", short, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=fresh)
            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            }
            command = [sys.executable, str(MCP_TOKEN_COMMAND), "scsi-main", "--login", "--quiet"]
            workers = [
                subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
                for _ in range(2)
            ]
            results = [worker.communicate(timeout=5) + (worker.returncode,) for worker in workers]
            calls = log.read_text().splitlines() if log.exists() else []

        assert all(returncode == 0 for _stdout, _stderr, returncode in results), results
        assert len(calls) == 2, "one enable plus one grant must serve concurrent rotations"

    def test_jwt_with_runway_skips_rotation(self):
        mod = _load_mcp_token_module()
        token = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS + 900)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", token, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            cursor_ran = log.exists()

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == token
        assert not cursor_ran, "a token above the min-TTL floor must skip rotation entirely"

    def test_failed_rotation_restores_cache_and_keeps_valid_token(self):
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", short, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            cache_token = json.loads(cache.read_text())["scsi-main"]["tokens"]["access_token"]
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == short, "a still-valid token must survive a failed rotation"
        assert cache_token == short, "the invalidated access token must be restored on failure"
        assert not any("mcp login" in call for call in calls), "a still-valid token must never escalate to a browser"

    def test_expired_tokens_rotate_silently_before_browser(self):
        expired = self._jwt(int(time.time()) - 100)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", expired, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=fresh)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh
        assert not any("mcp login" in call for call in calls), "rotation must run before any browser flow"

    def test_revoked_opaque_rotation_earns_full_window_not_adoption_lease(self):
        revoked = "opaque-revoked-nominal"
        old_live = "opaque-old-live-alternative"
        fresh = "opaque-fresh-rotated"
        with (
            _liveness_server({revoked: 401, old_live: 200, fresh: 200}) as (url, handler),
            tempfile.TemporaryDirectory() as tmp,
        ):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            cache = self._write_rotatable_cache(home, "new", "slack", revoked, workspace=workspace)
            self._write_rotatable_cache(home, "old", "slack", old_live, refresh_token=None)
            os.utime(home / ".cursor/projects/old/mcp-auth.json", (time.time() - 100, time.time() - 100))
            self._write_ledger(home, "slack", revoked, str(cache))
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "slack", rotates_to=fresh)
            result = self._run(home, bindir, ["slack", "--login", "--quiet", "--json"])
            ledger = self._read_ledger(home, "slack")
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["token"] == fresh, "a fresh rotation must beat adopting an aged cached alternative"
        mod = _load_mcp_token_module()
        assert payload["seconds_left"] > mod.VERIFIED_ADOPTION_TTL_SECONDS, (
            "a provider-minted rotation earns the full nominal window, not an adoption lease"
        )
        assert ledger.get("token_sha256") == self._sha(fresh)
        assert "valid_until" not in ledger
        assert not any("mcp login" in call for call in calls)

    def test_failed_untrusted_refresh_falls_back_to_browser(self):
        expired = self._jwt(int(time.time()) - 100)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            # The first cache has a refresh token but belongs to neither the
            # current workspace nor a trusted recorded workspace. The second
            # has a resolvable workspace but no refresh token.
            self._write_rotatable_cache(home, "no-ws", "scsi-main", expired, workspace=None)
            self._write_rotatable_cache(home, "no-rt", "scsi-main", expired, refresh_token=None, workspace=root / "ws")
            cache = home / ".cursor/projects/no-ws/mcp-auth.json"
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 1, "no rotatable cache and a failed browser login must fail"
        assert any("list-tools scsi-main" in call for call in calls), "the newest refresh chain must be tried"
        assert any("mcp login scsi-main" in call for call in calls), "the browser flow remains the last resort"

    def test_rotation_sentinel_never_leaks_to_output(self):
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", short, workspace=workspace)
            self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            # Not --quiet: status text streams to stderr, mimicking wrappers.
            result = self._run(home, bindir, ["scsi-main", "--login"])

        assert result.returncode == 0, result.stderr
        assert mod.ROTATION_SENTINEL not in result.stdout
        assert mod.ROTATION_SENTINEL not in result.stderr
        assert short not in result.stderr


class TestMcpTokenWorkspaceSeeding(unittest.TestCase):
    """WHEN ``--login --no-proactive-rotation`` runs in a workspace cursor has never seen.

    cursor-agent reads only its own per-project OAuth cache, so a fresh worktree
    starts unauthenticated even when other project caches hold live chains.
    Token chains are not workspace-bound, so the workspace-auth gate must seed
    the missing cache from the newest verified cached chain and reserve the
    browser flow for the case where no verifiable chain exists. These are
    real-seam tests: an isolated ``HOME``, a local liveness endpoint, and a stub
    cursor-agent standing in for the browser flow.
    """

    def _sha(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _jwt(self, exp: int) -> str:
        def encode(value: dict[str, object]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'exp': exp})}.sig"

    def _slug(self, workspace: Path) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", os.path.realpath(workspace)).strip("-")

    def _write_cache(self, home: Path, name: str, server: str, tokens: dict[str, object]) -> Path:
        cache = home / ".cursor/projects" / name / "mcp-auth.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({server: {"tokens": tokens}}))
        return cache

    def _write_mcp_json(self, home: Path, server: str, url: str) -> None:
        cfg = home / ".cursor/mcp.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({"mcpServers": {server: {"url": url}}}))

    def _write_ledger(self, home: Path, server: str, token: str, source: str) -> None:
        state_dir = home / ".cache/mcp-token"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "opaque-refresh.json").write_text(
            json.dumps({server: {"source": source, "token_sha256": self._sha(token), "refreshed_at": time.time()}})
        )

    def _stub_cursor_agent(self, bindir: Path, log: Path, *, login_writes: tuple[Path, str] | None = None) -> None:
        lines = ["#!/usr/bin/env bash", f"printf '%s\\n' \"$*\" >> {shlex.quote(str(log))}"]
        if login_writes is not None:
            cache, payload = login_writes
            lines += [
                'if [[ "${1:-} ${2:-}" == "mcp login" ]]; then',
                f"  mkdir -p {shlex.quote(str(cache.parent))}",
                f"  cat > {shlex.quote(str(cache))} <<'EOF'\n{payload}\nEOF",
                "fi",
            ]
        lines.append("exit 0")
        agent = bindir / "cursor-agent"
        agent.write_text("\n".join(lines) + "\n")
        agent.chmod(0o755)

    def _run(self, home: Path, bindir: Path, workspace: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MCP_TOKEN_COMMAND), *args],
            capture_output=True,
            text=True,
            cwd=workspace,
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )

    def test_missing_workspace_cache_is_seeded_from_live_opaque_chain_without_browser(self):
        live = "opaque-live-donor"
        with _liveness_server({live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            bindir.mkdir()
            workspace.mkdir()
            self._write_mcp_json(home, "slack", url)
            donor_tokens = {"access_token": live, "expires_in": 3600, "refresh_token": "refresh-chain"}
            donor = self._write_cache(home, "donor", "slack", donor_tokens)
            self._write_ledger(home, "slack", live, str(donor))
            log = root / "cursor-agent.log"
            self._stub_cursor_agent(bindir, log)

            result = self._run(home, bindir, workspace, ["slack", "--login", "--quiet", "--no-proactive-rotation"])
            calls = log.read_text().splitlines() if log.exists() else []
            seeded_path = home / ".cursor/projects" / self._slug(workspace) / "mcp-auth.json"
            seeded = json.loads(seeded_path.read_text()) if seeded_path.exists() else {}
            seeded_mode = seeded_path.stat().st_mode & 0o777 if seeded_path.exists() else None
            donor_after = json.loads(donor.read_text())

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == live
        assert not any("mcp login" in call for call in calls), "a live cached chain must seed, not pop a browser"
        assert seeded.get("slack", {}).get("tokens") == donor_tokens, "the full donor chain must be copied"
        assert seeded_mode == 0o600, "a seeded token cache must be owner-only"
        assert donor_after["slack"]["tokens"] == donor_tokens, "the donor cache must stay untouched"
        assert live not in result.stderr

    def test_fresh_jwt_seeds_workspace_cache_without_any_liveness_probe(self):
        fresh = self._jwt(int(time.time()) + 7200)
        with _liveness_server({}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            bindir.mkdir()
            workspace.mkdir()
            self._write_mcp_json(home, "scsi-main", url)
            self._write_cache(home, "donor", "scsi-main", {"access_token": fresh, "expires_in": 3600})
            log = root / "cursor-agent.log"
            self._stub_cursor_agent(bindir, log)

            result = self._run(home, bindir, workspace, ["scsi-main", "--login", "--quiet", "--no-proactive-rotation"])
            calls = log.read_text().splitlines() if log.exists() else []
            hits = list(handler.hits)
            seeded_path = home / ".cursor/projects" / self._slug(workspace) / "mcp-auth.json"
            seeded = json.loads(seeded_path.read_text()) if seeded_path.exists() else {}

        assert result.returncode == 0, result.stderr
        assert hits == [], "a JWT's exp is authoritative; seeding must not probe"
        assert calls == [], "no cursor-agent invocation is needed to seed a fresh JWT"
        assert seeded.get("scsi-main", {}).get("tokens", {}).get("access_token") == fresh

    def test_unverifiable_opaque_chain_is_never_seeded_and_browser_runs_last(self):
        nominal = "opaque-unverifiable"
        fresh = "opaque-browser-minted"
        with _liveness_server({nominal: 500, fresh: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            bindir.mkdir()
            workspace.mkdir()
            self._write_mcp_json(home, "slack", url)
            donor = self._write_cache(
                home, "donor", "slack", {"access_token": nominal, "expires_in": 3600, "refresh_token": "rt"}
            )
            self._write_ledger(home, "slack", nominal, str(donor))
            workspace_cache = home / ".cursor/projects" / self._slug(workspace) / "mcp-auth.json"
            payload = json.dumps({"slack": {"tokens": {"access_token": fresh, "expires_in": 3600}}})
            log = root / "cursor-agent.log"
            self._stub_cursor_agent(bindir, log, login_writes=(workspace_cache, payload))

            result = self._run(home, bindir, workspace, ["slack", "--login", "--quiet", "--no-proactive-rotation"])
            calls = log.read_text().splitlines() if log.exists() else []
            seeded = json.loads(workspace_cache.read_text()) if workspace_cache.exists() else {}

        assert result.returncode == 0, result.stderr
        assert any("mcp login slack" in call for call in calls), (
            "an unverifiable chain must not be seeded; the browser flow remains the fallback"
        )
        assert seeded.get("slack", {}).get("tokens", {}).get("access_token") == fresh

    def test_seeding_preserves_other_servers_in_existing_workspace_cache(self):
        live = "opaque-live-donor"
        with _liveness_server({live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            bindir.mkdir()
            workspace.mkdir()
            self._write_mcp_json(home, "slack", url)
            donor = self._write_cache(
                home, "donor", "slack", {"access_token": live, "expires_in": 3600, "refresh_token": "rt"}
            )
            self._write_ledger(home, "slack", live, str(donor))
            other_tokens = {"access_token": "other-server-token", "expires_in": 3600}
            workspace_cache = self._write_cache(home, self._slug(workspace), "kibana", other_tokens)
            log = root / "cursor-agent.log"
            self._stub_cursor_agent(bindir, log)

            result = self._run(home, bindir, workspace, ["slack", "--login", "--quiet", "--no-proactive-rotation"])
            calls = log.read_text().splitlines() if log.exists() else []
            seeded = json.loads(workspace_cache.read_text())

        assert result.returncode == 0, result.stderr
        assert not any("mcp login" in call for call in calls)
        assert seeded.get("slack", {}).get("tokens", {}).get("access_token") == live
        assert seeded.get("kibana", {}).get("tokens") == other_tokens, "other servers' entries must be preserved"


class TestVertexWrappers(unittest.TestCase):
    """WHEN launching a supported harness through the shared Vertex adapter."""

    def test_SHOULD_forward_the_harness_name_and_every_argument_to_the_shared_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_core = Path(tmp) / "main.py"
            fake_core.write_text(
                "import json\nimport sys\nprint(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            for harness in ("codex", "copilot", "claude"):
                with self.subTest(harness=harness):
                    result = subprocess.run(
                        [
                            modern_bash(),
                            str(REPO / f"home/exact_bin/executable_,{harness}-vertex"),
                            "--model",
                            "claude-opus-4-7",
                            "--effort",
                            "xhigh",
                            "-p",
                            "prompt",
                        ],
                        capture_output=True,
                        text=True,
                        env={**os.environ, "VERTEX_ADAPTER_LIB": str(fake_core)},
                    )

                    assert result.returncode == 0, result.stderr
                    assert json.loads(result.stdout) == [
                        harness,
                        "--model",
                        "claude-opus-4-7",
                        "--effort",
                        "xhigh",
                        "-p",
                        "prompt",
                    ]


def _install_shim_stub(home: Path) -> None:
    """Drop a stub shim.py into a fake HOME so the launcher's shim branch works.

    The launcher exits 1 when the shim file is missing, because the shim is the
    session guardrail now. The stub announces a port on fd 3 (the launcher's
    ready pipe) and then loops, so the launcher's poll loop advances past the
    ready check without a real HTTP server.
    """
    shim_dir = home / "lib" / ",cursor-agent-shim"
    shim_dir.mkdir(parents=True, exist_ok=True)
    (shim_dir / "shim.py").write_text(
        '#!/usr/bin/env python3\nimport os, time\nos.write(3, b"PORT=9876\\n")\ntime.sleep(60)\n',
        encoding="utf-8",
    )


class TestOpenRouterWrappers(unittest.TestCase):
    """WHEN launching Claude or Codex through OpenRouter."""

    def test_SHOULD_clear_claude_api_credentials(self):
        source = (REPO / "home/exact_bin/executable_,claude-openrouter").read_text()
        assert 'export ANTHROPIC_API_KEY=""' in source
        assert 'export ANTHROPIC_AUTH_TOKEN="$api_key"' in source
        assert "unset ANTHROPIC_CUSTOM_HEADERS" in source
        assert "export CLAUDE_CODE_DISABLE_THINKING=1" in source
        assert 'export CLAUDE_CODE_EFFORT_LEVEL="$CLAUDE_EFFORT"' in source

    def test_SHOULD_pin_every_claude_tier_to_the_default_openrouter_model(self):
        # All four tiers name one id on purpose: an unpinned tier would route a background
        # task to a list-price model while the rest of the session runs the discounted one.
        source = (REPO / "home/exact_bin/executable_,claude-openrouter").read_text()
        for tier in ("OPUS", "SONNET", "HAIKU", "FABLE"):
            assert f'export ANTHROPIC_DEFAULT_{tier}_MODEL="$OPENROUTER_WIRE_MODEL"' in source
        assert 'export CLAUDE_CODE_SUBAGENT_MODEL="$OPENROUTER_WIRE_MODEL"' in source

    def test_SHOULD_stop_the_claude_base_url_before_the_messages_path(self):
        # Claude Code appends /v1/messages, and OpenRouter answers that path with the
        # Anthropic Messages schema, so the exported base URL must end at /api.
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            claude = bindir / "claude"
            claude.write_text('#!/usr/bin/env bash\nprintf "%s" "$ANTHROPIC_BASE_URL"\n', encoding="utf-8")
            claude.chmod(0o755)
            result = subprocess.run(
                [modern_bash(), str(REPO / "home/exact_bin/executable_,claude-openrouter")],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{bindir}:{os.environ['PATH']}",
                    "OPENROUTER_API_KEY": "fixture-key",
                },
            )

        assert result.returncode == 0, result.stderr
        assert result.stdout == "https://openrouter.ai/api"

    def test_SHOULD_configure_codex_with_the_openrouter_responses_route(self):
        source = (REPO / "home/exact_bin/executable_,codex-openrouter").read_text()
        assert 'model_providers.openrouter.base_url=\\"https://openrouter.ai/api/v1\\"' in source
        assert 'model_providers.openrouter.env_key=\\"OPENROUTER_API_KEY\\"' in source
        assert 'model_providers.openrouter.wire_api=\\"responses\\"' in source
        assert 'model_provider=\\"openrouter\\"' in source

    def test_SHOULD_default_every_openrouter_launcher_to_deepseek_at_max_effort(self):
        # The route is defaulted rather than strict: model and effort remain selectable via flags.
        for relative in (
            "home/exact_bin/executable_,claude-openrouter",
            "home/exact_bin/executable_,codex-openrouter",
            "home/exact_bin/executable_,copilot-openrouter",
            "home/exact_bin/executable_,cursor-openrouter",
        ):
            with self.subTest(command=relative):
                source = (REPO / relative).read_text()
                assert f'OPENROUTER_MODEL="{OPENROUTER_PIN}"' in source
                assert 'OPENROUTER_EFFORT="max"' in source
                assert 'readonly OPENROUTER_WIRE_MODEL="$OPENROUTER_MODEL@preset/$preset_slug"' in source
                assert 'preset_slug="$family-lanes-$preset_effort"' in source  # max composes, no cap

    def test_SHOULD_keep_reasoning_models_that_omit_supported_efforts(self):
        # OpenRouter lists inclusionai/ling-3.0-flash under supported_parameters=reasoning
        # with reasoning={mandatory:false, default_enabled:true} and no supported_efforts.
        # The completer used to skip those rows, so --model never offered the id.
        source = (REPO / "home/dot_config/fish/functions/readonly___openrouter_catalog.fish").read_text()
        start = source.index("import json, sys")
        end = source.index("' $tmp", start)
        snippet = source[start:end]
        self.assertNotIn("if not efforts:", snippet)
        fixture = {
            "data": [
                {
                    "id": "inclusionai/ling-3.0-flash",
                    "reasoning": {"mandatory": False, "default_enabled": True},
                },
                {
                    "id": "deepseek/deepseek-v4-flash-0731",
                    "reasoning": {"supported_efforts": ["max", "high", "low"]},
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "models.json"
            catalog.write_text(json.dumps(fixture), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-c", snippet, str(catalog)],
                check=True,
                capture_output=True,
                text=True,
            )
        rows = dict(line.split("\t", 1) for line in result.stdout.splitlines())
        self.assertEqual(rows["inclusionai/ling-3.0-flash"], "")
        self.assertEqual(rows["deepseek/deepseek-v4-flash-0731"], "max,high,low")

    def test_SHOULD_share_openrouter_catalog_across_chat_wrappers(self):
        # Live catalog omits none for DeepSeek; completions still force-union none onto catalog efforts.
        source = (REPO / "home/dot_config/fish/functions/readonly___openrouter_catalog.fish").read_text()
        assert "not contains -- none $efforts" in source
        assert "set efforts none $efforts" in source
        assert 'test -z "$parts[2]"' in source
        assert "~/.cache/,openrouter/models.tsv" in source
        for relative in (
            "home/dot_config/fish/completions/readonly_,claude-openrouter.fish",
            "home/dot_config/fish/completions/readonly_,codex-openrouter.fish",
            "home/dot_config/fish/completions/readonly_,copilot-openrouter.fish",
            "home/dot_config/fish/completions/readonly_,cursor-openrouter.fish",
        ):
            with self.subTest(completion=relative):
                text = (REPO / relative).read_text()
                assert "functions/__openrouter_catalog.fish" in text
                assert "(__openrouter_catalog_models)" in text
                assert "(__openrouter_catalog_efforts)" in text

    def test_SHOULD_complete_cursor_codex_from_the_live_codex_model_cache(self):
        source = (REPO / "home/dot_config/fish/completions/readonly_,cursor-codex.fish").read_text()

        assert 'cache "$HOME/.codex/models_cache.json"' in source
        assert 'model.get("supported_reasoning_levels", [])' in source
        assert "(__cursor_codex_models)" in source
        assert "(__cursor_codex_efforts)" in source

    def test_SHOULD_hard_pin_claude_route_over_environment_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            claude = bindir / "claude"
            claude.write_text(
                """#!/usr/bin/env bash
printf 'model=%s\\neffort=%s\\nsubagent=%s\\nargs=%s\\n' \
  "$ANTHROPIC_MODEL" "$CLAUDE_CODE_EFFORT_LEVEL" "$CLAUDE_CODE_SUBAGENT_MODEL" "$*"
""",
                encoding="utf-8",
            )
            claude.chmod(0o755)
            result = subprocess.run(
                [modern_bash(), str(REPO / "home/exact_bin/executable_,claude-openrouter"), "-p", "review"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{bindir}:{os.environ['PATH']}",
                    "OPENROUTER_API_KEY": "fixture-key",
                    "ANTHROPIC_MODEL": "other-model",
                    "CLAUDE_CODE_EFFORT_LEVEL": "low",
                    "CLAUDE_CODE_SUBAGENT_MODEL": "other-model",
                },
            )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            f"model={OPENROUTER_WIRE_PIN}",
            "effort=high",
            f"subagent={OPENROUTER_WIRE_PIN}",
            f"args=--model {OPENROUTER_WIRE_PIN} --effort high -p review",
        ]

    def test_SHOULD_hard_pin_codex_and_copilot_routes_over_environment_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            codex = bindir / "codex"
            codex.write_text(
                """#!/usr/bin/env bash
printf 'band-model=%s\\nband-effort=%s\\nargs=%s\\n' \
  "$AGENT_BAND_MODEL_OVERRIDE" "$AGENT_BAND_EFFORT_OVERRIDE" "$*"
""",
                encoding="utf-8",
            )
            codex.chmod(0o755)
            copilot = bindir / "copilot"
            copilot.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            copilot.chmod(0o755)
            copilot_wrapper = bindir / ",copilot"
            copilot_wrapper.write_text(
                """#!/usr/bin/env bash
printf 'type=%s\\nmodel=%s\\nwire=%s\\nband-model=%s\\nband-effort=%s\\nargs=%s\\n' \
  "$COPILOT_PROVIDER_TYPE" "$COPILOT_MODEL" "$COPILOT_PROVIDER_WIRE_MODEL" \
  "$AGENT_BAND_MODEL_OVERRIDE" "$AGENT_BAND_EFFORT_OVERRIDE" "$*"
echo "base=$COPILOT_PROVIDER_BASE_URL"
""",
                encoding="utf-8",
            )
            copilot_wrapper.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{bindir}:{os.environ['PATH']}",
                "OPENROUTER_API_KEY": "fixture-key",
                "AGENT_BAND_MODEL_OVERRIDE": "other-model",
                "AGENT_BAND_EFFORT_OVERRIDE": "low",
            }
            codex_result = subprocess.run(
                [
                    modern_bash(),
                    str(REPO / "home/exact_bin/executable_,codex-openrouter"),
                    "--ask-for-approval",
                    "on-request",
                ],
                capture_output=True,
                text=True,
                env={**env, "CODEX_WRAPPER_BIN": str(codex), "CODEX_OPENROUTER_MODEL": "other-model"},
            )
            copilot_result = subprocess.run(
                [modern_bash(), str(REPO / "home/exact_bin/executable_,copilot-openrouter"), "-p", "review"],
                capture_output=True,
                text=True,
                env={
                    **env,
                    "COPILOT_PROVIDER_TYPE": "openai",
                    "COPILOT_PROVIDER_BASE_URL": "https://other.example/api",
                    "COPILOT_OPENROUTER_MODEL": "other-model",
                },
            )

        assert codex_result.returncode == 0, codex_result.stderr
        assert codex_result.stdout.splitlines()[:2] == [f"band-model={OPENROUTER_WIRE_PIN}", "band-effort=high"]
        assert f"--model {OPENROUTER_WIRE_PIN}" in codex_result.stdout
        # Effort rides the preset slug, not a Codex body field, so model_reasoning_effort is unset.
        assert "model_reasoning_effort" not in codex_result.stdout
        assert copilot_result.returncode == 0, copilot_result.stderr
        assert copilot_result.stdout.splitlines() == [
            "type=anthropic",
            f"model={OPENROUTER_PIN}",
            f"wire={OPENROUTER_WIRE_PIN}",
            f"band-model={OPENROUTER_WIRE_PIN}",
            "band-effort=high",
            f"args=--model {OPENROUTER_PIN} --effort high -p review",
            "base=https://openrouter.ai/api",
        ]

    def test_SHOULD_hard_pin_cursor_route_over_environment_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            home = Path(tmp) / "home"
            _install_shim_stub(home)
            version = "2026.08.04-test"
            local_bin = home / ".local" / "share" / "cursor-agent-local" / "versions" / version
            local_bin.mkdir(parents=True)
            cursor_agent = bindir / "cursor-agent"
            cursor_agent.write_text(f'#!/usr/bin/env bash\necho "{version}"\n', encoding="utf-8")
            cursor_agent.chmod(0o755)
            local = local_bin / "cursor-agent-local"
            local.write_text(
                """#!/usr/bin/env bash
printf 'base=%s\nkey=%s\nband-model=%s\nargs=%s\n' \\
  "$CURSOR_LOCAL_AGENT_BASE_URL" "$CURSOR_LOCAL_AGENT_API_KEY" "$AGENT_BAND_MODEL_OVERRIDE" "$*"
""",
                encoding="utf-8",
            )
            local.chmod(0o755)
            result = subprocess.run(
                [modern_bash(), str(REPO / "home/exact_bin/executable_,cursor-openrouter"), "-p", "review"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{bindir}:{os.environ['PATH']}",
                    "HOME": str(home),
                    "OPENROUTER_API_KEY": "fixture-key",
                    "CURSOR_LOCAL_AGENT_BASE_URL": "https://evil.example/v1",
                    "CURSOR_LOCAL_AGENT_API_KEY": "evil-key",
                    "ANTHROPIC_BASE_URL": "https://evil.example",
                    "ANTHROPIC_AUTH_TOKEN": "evil-key",
                    "AGENT_BAND_MODEL_OVERRIDE": "other-model",
                },
            )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "base=http://127.0.0.1:9876/api/v1",
            "key=fixture-key",
            f"band-model={OPENROUTER_WIRE_PIN}",
            f"args=--model {OPENROUTER_WIRE_PIN} -p review",
        ]

    def test_SHOULD_self_heal_a_missing_cursor_agent_local_flavor(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            home = Path(tmp) / "home"
            _install_shim_stub(home)
            version = "2026.08.04-test"
            cursor_agent = bindir / "cursor-agent"
            cursor_agent.write_text(f'#!/usr/bin/env bash\necho "{version}"\n', encoding="utf-8")
            cursor_agent.chmod(0o755)
            installer = home / "lib" / ",cursor-agent-local"
            installer.mkdir(parents=True)
            marker = Path(tmp) / "installed"
            install = installer / "install.sh"
            install.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
dest="$HOME/.local/share/cursor-agent-local/versions/$1"
mkdir -p "$dest"
cat > "$dest/cursor-agent-local" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$dest/cursor-agent-local"
touch "%s"
"""
                % marker,
                encoding="utf-8",
            )
            result = subprocess.run(
                [modern_bash(), str(REPO / "home/exact_bin/executable_,cursor-openrouter")],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{bindir}:{os.environ['PATH']}",
                    "HOME": str(home),
                    "OPENROUTER_API_KEY": "fixture-key",
                },
            )

            assert result.returncode == 0, result.stderr
            assert marker.exists()

    def test_SHOULD_compose_wire_model_from_model_and_effort_flags(self):
        # Model and effort are selectable; the wire id composes the matching preset slug.
        cases = [
            (["-p", "x"], "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max"),
            (
                ["--model", "deepseek/deepseek-v4-flash-0731", "--effort", "max"],
                "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max",
            ),
            (["--model", "moonshotai/kimi-k3", "--effort", "max"], "moonshotai/kimi-k3@preset/kimi-lanes-max"),
            (
                ["--model", "openai/gpt-5.6-terra", "--effort", "minimal"],
                "openai/gpt-5.6-terra@preset/terra-lanes-minimal",
            ),
            (
                ["--effort", "none"],
                "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-none",
            ),
            (
                ["--model", "openai/gpt-5.6-terra", "--effort", "none"],
                "openai/gpt-5.6-terra@preset/terra-lanes-none",
            ),
            (["--model", "qwen/qwen3.8-max", "--effort", "high"], "qwen/qwen3.8-max@preset/effort-high"),
            (["--model", "qwen/qwen3.8-max", "--effort", "none"], "qwen/qwen3.8-max@preset/effort-none"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            claude = bindir / "claude"
            claude.write_text('#!/usr/bin/env bash\necho "model=$ANTHROPIC_MODEL"\n', encoding="utf-8")
            claude.chmod(0o755)
            for argv, expected in cases:
                with self.subTest(argv=argv):
                    result = subprocess.run(
                        [modern_bash(), str(REPO / "home/exact_bin/executable_,claude-openrouter"), *argv],
                        capture_output=True,
                        text=True,
                        env={
                            **os.environ,
                            "PATH": f"{bindir}:{os.environ['PATH']}",
                            "OPENROUTER_API_KEY": "fixture-key",
                        },
                    )
                    assert result.returncode == 0, result.stderr
                    assert f"model={expected}" in result.stdout

    def test_SHOULD_compose_wire_model_for_codex_copilot_and_cursor(self):
        # The same model/effort -> preset-slug composition runs in every wrapper; only the
        # leaf delivery differs (argv for codex/cursor, provider env for copilot).
        cases = [
            (["-p", "x"], "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max"),
            (
                ["--model", "deepseek/deepseek-v4-flash-0731", "--effort", "max"],
                "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max",
            ),
            (["--thinking", "max"], "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max"),
            (["--no-thinking"], "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-minimal"),
            (["--effort", "none"], "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-none"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            codex = bindir / "codex"
            codex.write_text('#!/usr/bin/env bash\necho "args=$*"\n', encoding="utf-8")
            codex.chmod(0o755)
            copilot = bindir / ",copilot"
            copilot.write_text('#!/usr/bin/env bash\necho "wire=$COPILOT_PROVIDER_WIRE_MODEL"\n', encoding="utf-8")
            copilot.chmod(0o755)
            home = Path(tmp) / "home"
            _install_shim_stub(home)
            version = "2026.08.04-test"
            local_bin = home / ".local" / "share" / "cursor-agent-local" / "versions" / version
            local_bin.mkdir(parents=True)
            local = local_bin / "cursor-agent-local"
            local.write_text('#!/usr/bin/env bash\necho "args=$*"\n', encoding="utf-8")
            local.chmod(0o755)
            cursor_agent = bindir / "cursor-agent"
            cursor_agent.write_text(f'#!/usr/bin/env bash\necho "{version}"\n', encoding="utf-8")
            cursor_agent.chmod(0o755)
            runners = {
                "home/exact_bin/executable_,codex-openrouter": {"CODEX_WRAPPER_BIN": str(codex)},
                "home/exact_bin/executable_,copilot-openrouter": {},
                "home/exact_bin/executable_,cursor-openrouter": {"HOME": str(home)},
            }
            for argv, expected in cases:
                for relative, extra_env in runners.items():
                    with self.subTest(command=relative, argv=argv):
                        result = subprocess.run(
                            [modern_bash(), str(REPO / relative), *argv],
                            capture_output=True,
                            text=True,
                            env={
                                **os.environ,
                                **extra_env,
                                "PATH": f"{bindir}:{os.environ['PATH']}",
                                "OPENROUTER_API_KEY": "fixture-key",
                            },
                        )
                        assert result.returncode == 0, result.stderr
                        assert expected in result.stdout

    def test_SHOULD_reject_empty_or_missing_model_and_effort_values(self):
        # Empty --model=/--effort= would compose a garbage wire id that only fails at the
        # provider; a trailing --model must exit 2, not crash on set -u.
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            for command in ("claude", "codex", ",copilot"):
                fake = bindir / command
                fake.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                fake.chmod(0o755)
            home = Path(tmp) / "home"
            _install_shim_stub(home)
            version = "2026.08.04-test"
            local_bin = home / ".local" / "share" / "cursor-agent-local" / "versions" / version
            local_bin.mkdir(parents=True)
            local = local_bin / "cursor-agent-local"
            local.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            local.chmod(0o755)
            cursor_agent = bindir / "cursor-agent"
            cursor_agent.write_text(f'#!/usr/bin/env bash\necho "{version}"\n', encoding="utf-8")
            cursor_agent.chmod(0o755)
            runners = {
                "home/exact_bin/executable_,claude-openrouter": {},
                "home/exact_bin/executable_,codex-openrouter": {"CODEX_WRAPPER_BIN": str(bindir / "codex")},
                "home/exact_bin/executable_,copilot-openrouter": {},
                "home/exact_bin/executable_,cursor-openrouter": {"HOME": str(home)},
            }
            for relative, extra_env in runners.items():
                for argv in (["--model="], ["--effort="], ["--model"], ["--effort"]):
                    with self.subTest(command=relative, argv=argv):
                        result = subprocess.run(
                            [modern_bash(), str(REPO / relative), *argv],
                            capture_output=True,
                            text=True,
                            env={
                                **os.environ,
                                **extra_env,
                                "PATH": f"{bindir}:{os.environ['PATH']}",
                                "OPENROUTER_API_KEY": "fixture-key",
                            },
                        )
                        assert result.returncode == 2
                        assert "requires a value" in result.stderr or "non-empty values" in result.stderr

    def test_SHOULD_reject_provider_override_flags(self):
        # Route-pinning flags (base URL, API key, config) stay rejected; only model/effort open up.
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            for command in ("claude", "copilot", ",copilot"):
                fake = bindir / command
                fake.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                fake.chmod(0o755)
            codex = bindir / "codex"
            codex.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            codex.chmod(0o755)
            home = Path(tmp) / "home"
            version = "2026.08.04-test"
            local_bin = home / ".local" / "share" / "cursor-agent-local" / "versions" / version
            local_bin.mkdir(parents=True)
            local = local_bin / "cursor-agent-local"
            local.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            local.chmod(0o755)
            cursor_agent = bindir / "cursor-agent"
            cursor_agent.write_text(f'#!/usr/bin/env bash\necho "{version}"\n', encoding="utf-8")
            cursor_agent.chmod(0o755)
            cases = {
                "home/exact_bin/executable_,claude-openrouter": ({}, ["--fallback-model", "other"]),
                "home/exact_bin/executable_,codex-openrouter": ({"CODEX_WRAPPER_BIN": str(codex)}, ["-c", "model=x"]),
                "home/exact_bin/executable_,cursor-openrouter": (
                    {"HOME": str(home)},
                    ["--base-url", "https://evil.example"],
                ),
            }
            for relative, (extra_env, argv) in cases.items():
                with self.subTest(command=relative):
                    result = subprocess.run(
                        [modern_bash(), str(REPO / relative), *argv],
                        capture_output=True,
                        text=True,
                        env={
                            **os.environ,
                            **extra_env,
                            "PATH": f"{bindir}:{os.environ['PATH']}",
                            "OPENROUTER_API_KEY": "fixture-key",
                        },
                    )
                    assert result.returncode == 2
                    assert "pins OpenRouter" in result.stderr

    def test_SHOULD_fail_closed_without_an_openrouter_key(self):
        for relative in (
            "home/exact_bin/executable_,claude-openrouter",
            "home/exact_bin/executable_,codex-openrouter",
            "home/exact_bin/executable_,cursor-openrouter",
        ):
            with self.subTest(command=relative):
                source = (REPO / relative).read_text()
                assert "pass show openrouter/api/token" in source
                assert "Error: set OPENROUTER_API_KEY or pass entry openrouter/api/token." in source

    def test_SHOULD_run_the_shim_for_every_pinned_route(self):
        # The strict-flag rewrite exists because cursor-agent-local's reasoning
        # predicate matches "openai/..." ids; DeepSeek/Kimi/GLM ids were never
        # affected. But the shim is also the model guardrail, which applies to
        # every model, so the launcher must keep the default route shimmed and
        # only `--no-shim` (direct-OpenRouter opt-out) may skip it.
        source = (REPO / "home/exact_bin/executable_,cursor-openrouter").read_text()
        assert "needs_shim" in source
        assert "needs_shim=1" in source
        assert 'CURSOR_LOCAL_AGENT_BASE_URL="http://127.0.0.1:$shim_port/api/v1"' in source
        assert "--no-shim" in source
        assert "trap shim_cleanup EXIT" in source
        # The guardrail env is exported before the shim branch.
        assert 'export CURSOR_AGENT_ALLOWED_MODEL="$OPENROUTER_WIRE_MODEL"' in source

    def test_SHOULD_strip_tool_strict_from_chat_completions(self):
        # The shell schema shipped in cursor-agent-local/2026.08.04 declares
        # debounce_ms optional but omits it from required; OpenAI strict mode
        # rejects that with 400 invalid_function_parameters. The shim strips the
        # strict flag, which is the verified workaround (live probe 2026-08-09).
        shim_path = REPO / "home/exact_lib/exact_,cursor-agent-shim/shim.py"
        assert shim_path.is_file()
        loader = SourceFileLoader("cursor_agent_shim", str(shim_path))
        spec = importlib.util.spec_from_loader("cursor_agent_shim", loader)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        payload = {
            "model": "openai/gpt-5.6-luna@preset/effort-xhigh",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "Shell",
                        "description": "run",
                        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
                        "strict": True,
                    },
                },
                {"type": "function", "function": {"name": "Read", "parameters": {"type": "object"}, "strict": True}},
            ],
        }
        rewritten = module.rewrite_chat_completions(payload)
        for tool in rewritten["tools"]:
            assert "strict" not in tool["function"]
        # original payload untouched
        assert payload["tools"][0]["function"]["strict"] is True

        # non-tool requests pass through untouched (structure preserved, same object)
        via = module.rewrite_chat_completions({"model": "x", "messages": [{"role": "user", "content": "hi"}]})
        assert via == {"model": "x", "messages": [{"role": "user", "content": "hi"}]}

    def test_SHOULD_reject_chat_completions_whose_model_is_not_the_pinned_session_model(self):
        module = self._load_shim_module()

        allowed = "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max"
        assert module.enforce_allowed_model({"model": allowed, "messages": []}, allowed) is None

        violations = {
            "claude-sonnet-4.6": "an unbound profile model must be rejected",
            "claude-opus-4-8": "a costly family id must be rejected",
            "openai/gpt-5.6-terra": "a different route id must be rejected",
            # Same provider prefix but no preset suffix: not the pinned session model.
            "deepseek/deepseek-v4-flash-0731": "a bare provider model must be rejected",
        }
        for model, reason in violations.items():
            with self.subTest(model=model):
                error = module.enforce_allowed_model({"model": model, "messages": []}, allowed)
                assert error is not None, reason
                assert "not the pinned session model" in error

        # Missing/non-string model is a violation, not a pass-through.
        for payload in ({}, {"model": 5}, {"model": ""}):
            assert module.enforce_allowed_model(payload, allowed) is not None

    def test_SHOULD_403_a_guardrail_violation_before_upstream_contact(self):
        module = self._load_shim_module()

        upstream_hit_count = 0

        class _CountingHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, _fmt, *_args):
                return

            def do_POST(self):
                nonlocal upstream_hit_count
                upstream_hit_count += 1
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                body = b'{"choices":[]}'
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        fake_upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _CountingHandler)
        fake_upstream.daemon_threads = True
        upstream_port = fake_upstream.server_address[1]
        upstream_thread = threading.Thread(target=fake_upstream.serve_forever, daemon=True)
        upstream_thread.start()

        original_upstream = module.UPSTREAM
        original_allowed = module.ALLOWED_MODEL
        module.UPSTREAM = f"http://127.0.0.1:{upstream_port}"
        module.API_KEY = "fixture-key"
        module.ALLOWED_MODEL = "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max"

        shim_server = module.ShimServer(("127.0.0.1", 0), module.ShimHandler)
        shim_server.daemon_threads = True
        shim_port = shim_server.server_address[1]
        shim_thread = threading.Thread(target=shim_server.serve_forever, daemon=True)
        shim_thread.start()

        def _post(model: str):
            body = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}]}).encode()
            req = Request(
                f"http://127.0.0.1:{shim_port}/api/v1/chat/completions",
                data=body,
                headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
                method="POST",
            )
            try:
                urlopen(req, timeout=5)
                raise AssertionError(f"expected 403 for model {model!r}, got 200")
            except Exception as exc:
                code = getattr(exc, "code", None)
                assert code == 403, f"expected 403 for model {model!r}, got {code}"

        try:
            # A subagent escape (Claude-family profile model) is blocked before upstream.
            _post("claude-sonnet-4.6")
            # A different pinned-route id (e.g. resume of another session) is blocked too.
            _post("openai/gpt-5.6-terra@preset/terra-lanes-max")
            assert upstream_hit_count == 0, f"fake upstream was contacted {upstream_hit_count} times"
        finally:
            module.UPSTREAM = original_upstream
            module.ALLOWED_MODEL = original_allowed
            shim_server.shutdown()
            shim_server.server_close()
            fake_upstream.shutdown()
            fake_upstream.server_close()
            shim_thread.join(timeout=5)
            upstream_thread.join(timeout=5)

    def test_SHOULD_let_the_pinned_model_through_the_guardrail(self):
        module = self._load_shim_module()

        upstream_models: list[str] = []

        class _CaptureHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, _fmt, *_args):
                return

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0) or 0)
                payload = json.loads(self.rfile.read(length))
                upstream_models.append(payload.get("model", ""))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                body = b'{"choices":[]}'
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        fake_upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
        fake_upstream.daemon_threads = True
        upstream_port = fake_upstream.server_address[1]
        upstream_thread = threading.Thread(target=fake_upstream.serve_forever, daemon=True)
        upstream_thread.start()

        original_upstream = module.UPSTREAM
        original_allowed = module.ALLOWED_MODEL
        module.UPSTREAM = f"http://127.0.0.1:{upstream_port}"
        module.API_KEY = "fixture-key"
        module.ALLOWED_MODEL = "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max"

        shim_server = module.ShimServer(("127.0.0.1", 0), module.ShimHandler)
        shim_server.daemon_threads = True
        shim_port = shim_server.server_address[1]
        shim_thread = threading.Thread(target=shim_server.serve_forever, daemon=True)
        shim_thread.start()

        body = json.dumps({"model": module.ALLOWED_MODEL, "messages": [{"role": "user", "content": "hi"}]}).encode()
        req = Request(
            f"http://127.0.0.1:{shim_port}/api/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
            method="POST",
        )
        try:
            with urlopen(req, timeout=5) as resp:
                resp.read()
            assert upstream_models == [module.ALLOWED_MODEL]
        finally:
            module.UPSTREAM = original_upstream
            module.ALLOWED_MODEL = original_allowed
            shim_server.shutdown()
            shim_server.server_close()
            fake_upstream.shutdown()
            fake_upstream.server_close()
            shim_thread.join(timeout=5)
            upstream_thread.join(timeout=5)

    def test_SHOULD_export_api_key_as_env_var_not_positional_arg(self):
        source = (REPO / "home/exact_bin/executable_,cursor-openrouter").read_text()
        # Key is exported into the environment before the shim launch.
        assert 'export OPENROUTER_API_KEY="$api_key"' in source
        # Shim is invoked with only the port argument.
        assert 'sys.argv[1:] = ["0"]' in source
        # Old two-argument form must be absent.
        assert 'sys.argv[1:] = ["0", sys.argv[1]]' not in source
        # Key must not appear as a positional argument on the shim launch line.
        assert '"$api_key" 3>' not in source
        # Export must precede the shim launch (export line appears before the python3 -c line).
        export_pos = source.index('export OPENROUTER_API_KEY="$api_key"')
        launch_pos = source.index("python3")
        assert export_pos < launch_pos

    def _load_shim_module(self):
        shim_path = REPO / "home/exact_lib/exact_,cursor-agent-shim/shim.py"
        loader = SourceFileLoader("cursor_agent_shim_live", str(shim_path))
        spec = importlib.util.spec_from_loader("cursor_agent_shim_live", loader)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_SHOULD_return_400_for_non_dict_chat_completion_bodies_without_upstream_contact(self):
        module = self._load_shim_module()

        upstream_hit_count = 0

        class _CountingHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, _fmt, *_args):
                return

            def do_POST(self):
                nonlocal upstream_hit_count
                upstream_hit_count += 1
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                body = b'{"choices":[]}'
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        fake_upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _CountingHandler)
        fake_upstream.daemon_threads = True
        upstream_port = fake_upstream.server_address[1]
        upstream_thread = threading.Thread(target=fake_upstream.serve_forever, daemon=True)
        upstream_thread.start()

        original_upstream = module.UPSTREAM
        module.UPSTREAM = f"http://127.0.0.1:{upstream_port}"
        module.API_KEY = "fixture-key"

        shim_server = module.ShimServer(("127.0.0.1", 0), module.ShimHandler)
        shim_server.daemon_threads = True
        shim_port = shim_server.server_address[1]
        shim_thread = threading.Thread(target=shim_server.serve_forever, daemon=True)
        shim_thread.start()

        invalid_bodies = [
            b"[]",
            b'["a","b"]',
            b"1",
            b'"just-a-string"',
        ]
        try:
            for body in invalid_bodies:
                req = Request(
                    f"http://127.0.0.1:{shim_port}/api/v1/chat/completions",
                    data=body,
                    headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
                    method="POST",
                )
                try:
                    urlopen(req, timeout=5)
                    raise AssertionError(f"expected 400 for body {body!r}, got 200")
                except Exception as exc:
                    code = getattr(exc, "code", None)
                    assert code == 400, f"expected 400 for body {body!r}, got {code}"
            assert upstream_hit_count == 0, f"fake upstream was contacted {upstream_hit_count} times"
        finally:
            module.UPSTREAM = original_upstream
            shim_server.shutdown()
            shim_server.server_close()
            fake_upstream.shutdown()
            fake_upstream.server_close()
            shim_thread.join(timeout=5)
            upstream_thread.join(timeout=5)

    def test_SHOULD_stream_response_and_forward_headers_and_propagate_http_errors(self):
        module = self._load_shim_module()

        _recorded_content_type: list[str] = []
        _response_mode: list[str] = ["stream"]

        STREAM_BODY = b"data: hello\n\ndata: world\n\n"
        ERROR_BODY = b'{"error":{"message":"rate limited","code":429}}'

        class _FakeUpstreamHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, _fmt, *_args):
                return

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0) or 0)
                self.rfile.read(length)
                _recorded_content_type.append(self.headers.get("Content-Type", ""))
                if _response_mode[0] == "stream":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Content-Length", str(len(STREAM_BODY)))
                    self.end_headers()
                    # Write in two chunks to exercise incremental forwarding.
                    half = len(STREAM_BODY) // 2
                    self.wfile.write(STREAM_BODY[:half])
                    self.wfile.flush()
                    self.wfile.write(STREAM_BODY[half:])
                else:
                    self.send_response(429)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(ERROR_BODY)))
                    self.end_headers()
                    self.wfile.write(ERROR_BODY)

        fake_upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FakeUpstreamHandler)
        fake_upstream.daemon_threads = True
        upstream_port = fake_upstream.server_address[1]
        upstream_thread = threading.Thread(target=fake_upstream.serve_forever, daemon=True)
        upstream_thread.start()

        original_upstream = module.UPSTREAM
        module.UPSTREAM = f"http://127.0.0.1:{upstream_port}"
        module.API_KEY = "fixture-key"

        shim_server = module.ShimServer(("127.0.0.1", 0), module.ShimHandler)
        shim_server.daemon_threads = True
        shim_port = shim_server.server_address[1]
        shim_thread = threading.Thread(target=shim_server.serve_forever, daemon=True)
        shim_thread.start()

        post_body = json.dumps({"model": "openai/gpt-5.6-luna", "messages": []}).encode()

        try:
            # --- streaming path ---
            req = Request(
                f"http://127.0.0.1:{shim_port}/api/v1/chat/completions",
                data=post_body,
                headers={"Content-Type": "application/json", "Content-Length": str(len(post_body))},
                method="POST",
            )
            with urlopen(req, timeout=5) as resp:
                downstream_body = resp.read()
                downstream_ct = resp.headers.get("Content-Type", "")
                downstream_cl = resp.headers.get("Content-Length", "")

            assert downstream_body == STREAM_BODY
            assert "text/event-stream" in downstream_ct
            # Inbound tool-name rewrite can change SSE byte length, so the shim
            # omits Content-Length and closes the connection instead.
            assert downstream_cl == ""
            assert _recorded_content_type and _recorded_content_type[-1] == "application/json"

            # --- HTTP error path ---
            _response_mode[0] = "error"
            req2 = Request(
                f"http://127.0.0.1:{shim_port}/api/v1/chat/completions",
                data=post_body,
                headers={"Content-Type": "application/json", "Content-Length": str(len(post_body))},
                method="POST",
            )
            try:
                urlopen(req2, timeout=5)
                raise AssertionError("expected HTTP error 429, got 200")
            except Exception as exc:
                assert getattr(exc, "code", None) == 429
                error_ct = exc.headers.get("Content-Type", "")  # type: ignore[union-attr]
                assert "application/json" in error_ct
                error_body = exc.read()  # type: ignore[union-attr]
                assert error_body == ERROR_BODY
        finally:
            module.UPSTREAM = original_upstream
            shim_server.shutdown()
            shim_server.server_close()
            fake_upstream.shutdown()
            fake_upstream.server_close()
            shim_thread.join(timeout=5)
            upstream_thread.join(timeout=5)


class TestInstallYarnPkgs(unittest.TestCase):
    """WHEN syncing global yarn packages with optional version pins."""

    def _fixture(self, tmp: str, desired: str, installed: dict[str, str]):
        home = Path(tmp) / "home"
        home.mkdir()
        (home / ".default-yarn-pkgs").write_text(desired, encoding="utf-8")
        bindir = Path(tmp) / "bin"
        bindir.mkdir()
        global_dir = Path(tmp) / "yarn-global"
        (global_dir / "node_modules").mkdir(parents=True)
        (global_dir / "package.json").write_text(json.dumps({"dependencies": dict.fromkeys(installed, "*")}))
        for name, version in installed.items():
            pkg_dir = global_dir / "node_modules" / name
            pkg_dir.mkdir(parents=True, exist_ok=True)
            (pkg_dir / "package.json").write_text(json.dumps({"version": version}), encoding="utf-8")
        log = Path(tmp) / "yarn.log"
        yarn = bindir / "yarn"
        yarn.write_text(
            f'#!/usr/bin/env bash\nif [[ "$1 $2" == "global dir" ]]; then\n  echo "{global_dir}"\n  exit 0\nfi\n'
            f'echo "$*" >> "{log}"\nexit 0\n',
            encoding="utf-8",
        )
        yarn.chmod(0o755)
        return home, bindir, log

    def _run(self, home: Path, bindir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [modern_bash(), str(REPO / "home/exact_bin/executable_,install-yarn-pkgs")],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home), "PATH": f"{bindir}:{os.environ['PATH']}"},
        )

    def test_SHOULD_repin_pinned_packages_and_upgrade_only_unpinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log = self._fixture(
                tmp,
                "pinned@1.2.3\n@org/scoped@2.0.0\nunpinned\n",
                {"pinned": "1.0.0", "@org/scoped": "2.0.0", "unpinned": "0.9.0"},
            )
            result = self._run(home, bindir)
            actions = log.read_text(encoding="utf-8").splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        # Wrong-version pin is re-installed at the exact pin; matching pin is left alone.
        assert "global add pinned@1.2.3" in actions
        assert not any("add @org/scoped" in action for action in actions)
        # Pinned packages are never upgraded; the unpinned one is.
        assert "global upgrade unpinned --latest" in actions
        assert not any(action.startswith("global upgrade pinned") for action in actions)
        assert not any(action.startswith("global upgrade @org/scoped") for action in actions)

    def test_SHOULD_install_missing_with_pin_and_remove_undesired(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, bindir, log = self._fixture(tmp, "new-pkg@3.1.0\nfresh\n", {"stray": "1.0.0"})
            result = self._run(home, bindir)
            actions = log.read_text(encoding="utf-8").splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        assert "global add new-pkg@3.1.0" in actions
        assert "global add fresh@latest" in actions
        assert "global remove stray" in actions


class TestCopilotWrapper(unittest.TestCase):
    """WHEN launching or resuming Copilot through the managed wrapper."""

    def _write_session(
        self,
        home: Path,
        session_id: str,
        *,
        cwd: Path,
        summary: str,
        updated_at: str,
    ) -> None:
        copilot_home = home / ".copilot"
        copilot_home.mkdir(parents=True, exist_ok=True)
        database = sqlite3.connect(copilot_home / "session-store.db")
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                cwd TEXT,
                repository TEXT,
                branch TEXT,
                summary TEXT,
                created_at TEXT,
                updated_at TEXT,
                host_type TEXT
            )
            """
        )
        database.execute(
            """
            INSERT INTO sessions (id, cwd, repository, branch, summary, created_at, updated_at, host_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                str(cwd),
                "owner/repo",
                "main",
                summary,
                updated_at,
                updated_at,
                "github",
            ),
        )
        database.commit()
        database.close()
        state = copilot_home / "session-state" / session_id
        state.mkdir(parents=True)
        (state / "events.jsonl").write_text("{}\n")

    def _write_real_copilot(self, bindir: Path) -> Path:
        real = bindir / "copilot-real"
        real.write_text("#!/usr/bin/env bash\nprintf 'ARGS='; printf '<%s>' \"$@\"; printf '\\n'\n")
        real.chmod(0o755)
        return real

    def test_SHOULD_replace_bare_resume_with_the_selected_exact_session_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "workspace"
            home.mkdir()
            bindir.mkdir()
            workspace.mkdir()
            older = "11111111-1111-4111-8111-111111111111"
            selected = "22222222-2222-4222-8222-222222222222"
            self._write_session(
                home,
                older,
                cwd=workspace,
                summary="Older session",
                updated_at="2026-07-21T10:00:00.000Z",
            )
            self._write_session(
                home,
                selected,
                cwd=workspace,
                summary="Selected session",
                updated_at="2026-07-22T10:00:00.000Z",
            )
            fzf_input = root / "fzf-input"
            fzf = bindir / "fzf"
            fzf.write_text(
                "#!/usr/bin/env python3\n"
                "import os, sys\n"
                "rows = sys.stdin.read().splitlines()\n"
                "open(os.environ['FZF_INPUT'], 'w').write('\\n'.join(rows))\n"
                "print(rows[0])\n"
            )
            fzf.chmod(0o755)
            real = self._write_real_copilot(bindir)

            result = subprocess.run(
                [sys.executable, str(COPILOT_COMMAND), "--yolo", "--resume"],
                capture_output=True,
                text=True,
                cwd=workspace,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "COPILOT_REAL_BIN": str(real),
                    "FZF_INPUT": str(fzf_input),
                },
            )
            picker_rows = fzf_input.read_text()

        assert result.returncode == 0, result.stderr
        assert f"<--session-id={selected}>" in result.stdout
        assert "<--resume>" not in result.stdout
        assert "Selected session" in picker_rows
        assert older in picker_rows

    def test_SHOULD_pass_explicit_resume_through_without_opening_the_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            real = self._write_real_copilot(bindir)

            result = subprocess.run(
                [sys.executable, str(COPILOT_COMMAND), "--yolo", "--resume=abc1234"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}/bin:/usr/bin",
                    "COPILOT_REAL_BIN": str(real),
                },
            )

        assert result.returncode == 0, result.stderr
        assert "ARGS=<--yolo><--resume=abc1234>" in result.stdout

    def test_SHOULD_pass_a_space_separated_resume_value_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            real = self._write_real_copilot(bindir)

            result = subprocess.run(
                [sys.executable, str(COPILOT_COMMAND), "--resume", "session name", "--yolo"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}/bin:/usr/bin",
                    "COPILOT_REAL_BIN": str(real),
                },
            )

        assert result.returncode == 0, result.stderr
        assert "ARGS=<--resume><session name><--yolo>" in result.stdout

    def test_SHOULD_resolve_a_path_searchable_real_copilot_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_real_copilot(bindir)

            result = subprocess.run(
                [sys.executable, str(COPILOT_COMMAND), "--version"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}/bin:/usr/bin",
                    "COPILOT_REAL_BIN": "copilot-real",
                },
            )

        assert result.returncode == 0, result.stderr
        assert "ARGS=<--version>" in result.stdout


class TestCodexWrapper(unittest.TestCase):
    """WHEN launching Codex through the managed wrapper.

    MCP auth needs no launch-time work: hosted OAuth servers run as
    ",mcp-token --bridge" stdio entries in the rendered config, so the wrapper
    only injects local llama.cpp model metadata and execs the real binary.
    """

    def test_launches_without_token_machinery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bindir = root / "bin"
            home.mkdir()
            bindir.mkdir()
            token_log = root / "mcp-token.log"
            token_helper = bindir / ",mcp-token"
            token_helper.write_text('#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> "$MCP_TOKEN_LOG"\n')
            token_helper.chmod(0o755)
            real_codex = bindir / "codex-real"
            real_codex.write_text("#!/usr/bin/env bash\necho REAL_CODEX_STARTED\nprintf 'ARGS=%s\\n' \"$*\"\n")
            real_codex.chmod(0o755)
            result = subprocess.run(
                [sys.executable, str(CODEX_COMMAND), "exec", "hi"],
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "CODEX_REAL_BIN": str(real_codex),
                    "MCP_TOKEN_LOG": str(token_log),
                },
            )
            token_calls = token_log.read_text().splitlines() if token_log.exists() else []

        assert result.returncode == 0, result.stderr
        assert "REAL_CODEX_STARTED" in result.stdout
        assert token_calls == [], "launch must not touch ,mcp-token; the bridge owns auth per request"

    def test_local_models_inject_catalog_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bindir = root / "bin"
            codex_home = home / ".codex"
            catalog = codex_home / "llama-cpp-model-catalog.json"
            codex_home.mkdir(parents=True)
            bindir.mkdir()
            catalog.write_text("{}\n")
            real_codex = bindir / "codex-real"
            real_codex.write_text("#!/usr/bin/env bash\nprintf 'ARGS=%s\\n' \"$*\"\n")
            real_codex.chmod(0o755)
            for model in ("nemotron-3.5", "qwen3.5-9b"):
                with self.subTest(model=model):
                    result = subprocess.run(
                        [sys.executable, str(CODEX_COMMAND), "--model", model, "exec", "hi"],
                        capture_output=True,
                        text=True,
                        cwd=str(REPO),
                        env={
                            **os.environ,
                            "HOME": str(home),
                            "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                            "CODEX_REAL_BIN": str(real_codex),
                        },
                    )

                    assert result.returncode == 0
                    assert f'model_catalog_json="{catalog}"' in result.stdout


class TestCursorLlamaCppWrapper(unittest.TestCase):
    """WHEN Cursor launches against the local llama.cpp router."""

    def test_SHOULD_pin_the_local_endpoint_key_and_selected_model(self):
        wrapper = REPO / "home/exact_bin/executable_,cursor-llama-cpp"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bindir = root / "bin"
            bindir.mkdir()
            version = "2026.08.11-test"
            local_dir = home / ".local/share/cursor-agent-local/versions" / version
            local_dir.mkdir(parents=True)

            cursor_agent = bindir / "cursor-agent"
            cursor_agent.write_text(f'#!/usr/bin/env bash\necho "{version}"\n', encoding="utf-8")
            cursor_agent.chmod(0o755)
            lifecycle = bindir / ",llama-cpp"
            lifecycle.write_text(
                '#!/usr/bin/env bash\n[[ "$1" == run && "$2" == -- ]] || exit 2\nshift 2\nexec "$@"\n',
                encoding="utf-8",
            )
            lifecycle.chmod(0o755)
            local = local_dir / "cursor-agent-local"
            local.write_text(
                """#!/usr/bin/env bash
printf 'base=%s\nkey=%s\nband-model=%s\nargs=%s\n' \\
  "$CURSOR_LOCAL_AGENT_BASE_URL" "$CURSOR_LOCAL_AGENT_API_KEY" "$AGENT_BAND_MODEL_OVERRIDE" "$*"
""",
                encoding="utf-8",
            )
            local.chmod(0o755)

            result = subprocess.run(
                [modern_bash(), str(wrapper), "-m", "nemotron-3.5", "-p", "review"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}:{os.environ['PATH']}",
                    "LLAMA_CPP_HOST": "127.0.0.9",
                    "LLAMA_CPP_PORT": "9090",
                    "LLAMA_CPP_API_KEY": "fixture-local-key",
                    "CURSOR_LOCAL_AGENT_BASE_URL": "https://evil.example/v1",
                    "CURSOR_LOCAL_AGENT_API_KEY": "evil-key",
                    "AGENT_BAND_MODEL_OVERRIDE": "other-model",
                },
            )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "base=http://127.0.0.9:9090/v1",
            "key=fixture-local-key",
            "band-model=nemotron-3.5",
            "args=--model nemotron-3.5 -p review",
        ]

    def test_SHOULD_enter_the_shared_router_lifecycle_from_every_harness(self):
        for harness in ("claude", "codex", "cursor", "opencode"):
            with self.subTest(harness=harness):
                wrapper = REPO / f"home/exact_bin/executable_,{harness}-llama-cpp"
                self.assertIn("exec ,llama-cpp run --", wrapper.read_text())

    def test_SHOULD_offer_router_ids_from_every_llama_cpp_harness_completion(self):
        cases = (("ne", "nemotron-3.5"), ("qwen3.5", "qwen3.5-9b"))
        for harness in ("claude", "codex", "cursor", "opencode"):
            for prefix, model_id in cases:
                with self.subTest(harness=harness, model=model_id):
                    completion = REPO / f"home/dot_config/fish/completions/readonly_,{harness}-llama-cpp.fish"
                    result = subprocess.run(
                        [
                            "fish",
                            "--no-config",
                            "-c",
                            f"source {shlex.quote(str(completion))}; complete -C ',{harness}-llama-cpp --model {prefix}'",
                        ],
                        capture_output=True,
                        text=True,
                    )

                    assert result.returncode == 0, result.stderr
                    assert f"{model_id}\t" in result.stdout

    def test_SHOULD_complete_llama_cpp_stop_and_force(self):
        completion = REPO / "home/dot_config/fish/completions/readonly_,llama-cpp.fish"
        subcommand = subprocess.run(
            ["fish", "--no-config", "-c", f"source {shlex.quote(str(completion))}; complete -C ',llama-cpp st'"],
            capture_output=True,
            text=True,
        )
        force = subprocess.run(
            [
                "fish",
                "--no-config",
                "-c",
                f"source {shlex.quote(str(completion))}; complete -C ',llama-cpp stop --f'",
            ],
            capture_output=True,
            text=True,
        )

        assert subcommand.returncode == 0, subcommand.stderr
        assert "stop\tStop the lifecycle-owned router" in subcommand.stdout
        assert force.returncode == 0, force.stderr
        assert "--force\tInterrupt active consumers and stop the owned router" in force.stdout


class TestCursorWrapper(unittest.TestCase):
    """WHEN Cursor launches with OAuth MCP preflight."""

    def test_seeds_current_workspace_from_live_cache_without_browser(self):
        global_token = "opaque-global-workspace-token"
        with (
            _liveness_server({global_token: 200}) as (url, _handler),
            tempfile.TemporaryDirectory() as tmp,
        ):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "workspace"
            config = home / ".cursor/mcp.json"
            global_cache = home / ".cursor/projects/global/mcp-auth.json"
            workspace_cache = home / ".cursor/projects/workspace/mcp-auth.json"
            ledger = home / ".cache/mcp-token/opaque-refresh.json"
            log = root / "cursor-agent.log"
            for path in (
                bindir,
                workspace,
                config.parent,
                global_cache.parent,
                workspace_cache.parent,
                ledger.parent,
            ):
                path.mkdir(parents=True, exist_ok=True)
            (workspace_cache.parent / ".workspace-trusted").write_text(json.dumps({"workspacePath": str(workspace)}))
            config.write_text(json.dumps({"mcpServers": {"slack": {"url": url, "auth": {"CLIENT_ID": "fixture"}}}}))
            global_cache.write_text(
                json.dumps(
                    {
                        "slack": {
                            "tokens": {
                                "access_token": global_token,
                                "expires_in": 3600,
                                "refresh_token": "refresh-chain",
                            }
                        }
                    }
                )
            )
            ledger.write_text(
                json.dumps(
                    {
                        "slack": {
                            "source": str(global_cache),
                            "token_sha256": hashlib.sha256(global_token.encode()).hexdigest(),
                            "refreshed_at": time.time(),
                        }
                    }
                )
            )

            token_helper = bindir / ",mcp-token"
            token_helper.write_text(
                f'#!/usr/bin/env bash\nexec {shlex.quote(sys.executable)} {shlex.quote(str(MCP_TOKEN_COMMAND))} "$@"\n'
            )
            token_helper.chmod(0o755)
            real_cursor = bindir / "cursor-agent"
            real_cursor.write_text(
                "#!/usr/bin/env bash\n"
                f"printf '%s\\n' \"$*\" >> {shlex.quote(str(log))}\n"
                'if [[ "${1:-}" == "mcp" ]]; then\n'
                "  exit 0\n"
                "fi\n"
                f"if [[ -s {shlex.quote(str(workspace_cache))} ]]; then\n"
                "  echo 'SESSION_MCP_STATUS=ready'\n"
                "else\n"
                "  echo 'SESSION_MCP_STATUS=requires_authentication'\n"
                "fi\n"
            )
            real_cursor.chmod(0o755)

            result = subprocess.run(
                [
                    modern_bash(),
                    str(REPO / "home/exact_bin/executable_,cursor"),
                    "--force",
                    "--approve-mcps",
                ],
                capture_output=True,
                text=True,
                cwd=workspace,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "CURSOR_AGENT_REAL_BIN": str(real_cursor),
                },
            )
            calls = log.read_text().splitlines()
            seeded = json.loads(workspace_cache.read_text()) if workspace_cache.exists() else {}
            donor = json.loads(global_cache.read_text())

        assert result.returncode == 0, result.stderr
        assert "SESSION_MCP_STATUS=ready" in result.stdout
        assert not any("mcp login" in call for call in calls), "a live cached chain must seed, not pop a browser"
        assert seeded.get("slack", {}).get("tokens", {}).get("access_token") == global_token
        assert seeded["slack"]["tokens"].get("refresh_token") == "refresh-chain"
        assert donor["slack"]["tokens"]["access_token"] == global_token, "the donor cache must stay untouched"

    def test_preflights_cursor_oauth_and_auth_client_id_servers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            config = home / ".cursor/mcp.json"
            config.parent.mkdir(parents=True)
            bindir.mkdir()
            config.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "scsi-main": {"url": "https://scsi.invalid/mcp", "oauth": {"clientId": "fixture"}},
                            "slack": {"url": "https://slack.invalid/mcp", "auth": {"CLIENT_ID": "fixture"}},
                        }
                    }
                )
            )
            token_log = root / "mcp-token.log"
            token_helper = bindir / ",mcp-token"
            token_helper.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> \"$MCP_TOKEN_LOG\"\nprintf 'fixture-token\\n'\n"
            )
            token_helper.chmod(0o755)
            real_cursor = bindir / "cursor-agent"
            real_cursor.write_text("#!/usr/bin/env bash\necho REAL_CURSOR_STARTED\n")
            real_cursor.chmod(0o755)

            result = subprocess.run(
                [modern_bash(), str(REPO / "home/exact_bin/executable_,cursor")],
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "CURSOR_AGENT_REAL_BIN": str(real_cursor),
                    "MCP_TOKEN_LOG": str(token_log),
                },
            )
            calls = token_log.read_text().splitlines()

        assert result.returncode == 0, result.stderr
        assert "REAL_CURSOR_STARTED" in result.stdout
        assert calls == [
            "scsi-main --login --quiet --no-proactive-rotation",
            "slack --login --quiet --no-proactive-rotation",
        ]


class TestKbnStackCommand(unittest.TestCase):
    """WHEN tracking ,kbn-stack registry ownership."""

    def test_infers_legacy_ownership_safely(self):
        kbn_stack = _load_kbn_stack_command()

        assert kbn_stack.stack_started_by({"started_by": kbn_stack.STARTED_BY_AGENT}) == kbn_stack.STARTED_BY_AGENT
        assert kbn_stack.stack_started_by({"started_by": kbn_stack.STARTED_BY_USER}) == kbn_stack.STARTED_BY_USER
        assert kbn_stack.stack_started_by({"start_mode": "agent-detach"}) == kbn_stack.STARTED_BY_AGENT
        assert kbn_stack.stack_started_by({"kbn_pid": 1234}) == kbn_stack.STARTED_BY_AGENT
        assert kbn_stack.stack_started_by({"es_pid": "1234"}) == kbn_stack.STARTED_BY_USER
        assert kbn_stack.stack_started_by({"backend": "serverless"}) == kbn_stack.STARTED_BY_USER

    def test_records_start_mode_from_detach_or_tmux_context(self):
        kbn_stack = _load_kbn_stack_command()

        assert kbn_stack.start_mode(kbn_stack.parse_args(["--detach"]), None) == "agent-detach"
        assert kbn_stack.start_mode(kbn_stack.parse_args([]), "%1") == "interactive-tmux"
        assert kbn_stack.start_mode(kbn_stack.parse_args([]), None) == "manual-command"

    def test_status_state_uses_recorded_readiness_and_live_evidence(self):
        kbn_stack = _load_kbn_stack_command()
        cases = (
            (True, True, (True, True), "ready"),
            (True, False, (True, True), "ready"),
            (False, True, (False, False), "starting"),
            (False, True, (False, True), "starting"),
            (True, True, (False, True), "degraded"),
            (True, True, (True, False), "degraded"),
            (False, False, (True, True), "degraded"),
            (False, False, (False, False), "stale"),
        )
        for ready, process_alive, liveness, expected in cases:
            with self.subTest(ready=ready, process_alive=process_alive, liveness=liveness):
                entry = {"ready": ready}
                assert kbn_stack.status_state(entry, process_alive, *liveness) == expected

    def test_status_lists_registered_stacks_in_slot_order(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/B": {
                "slot": 2,
                "backend": "serverless",
                "branch": "feature/b",
                "started_by": kbn_stack.STARTED_BY_AGENT,
                "ready": False,
            },
            "/wt/A": {
                "slot": 0,
                "backend": "snapshot",
                "branch": "main",
                "started_by": kbn_stack.STARTED_BY_USER,
                "ready": True,
            },
        }
        with mock.patch.object(kbn_stack, "status_state", side_effect=["ready", "starting"]):
            with mock.patch.object(kbn_stack, "slot_liveness", side_effect=[(True, True), (False, True)]):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    assert kbn_stack.run_status(registry) == 0

        lines = output.getvalue().splitlines()
        assert lines[0].split() == ["STATE", "SLOT", "BACKEND", "OWNER", "KIBANA", "ES", "BRANCH", "WORKTREE"]
        assert lines[1].split() == ["ready", "0", "snapshot", "user", "up", "up", "main", "/wt/A"]
        assert lines[2].split() == ["starting", "2", "serverless", "agent", "down", "up", "feature/b", "/wt/B"]

    def test_status_does_not_require_a_kibana_worktree(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack, "load_registry", return_value={}) as load_registry:
            with mock.patch.object(kbn_stack, "run_status", return_value=0) as run_status:
                with mock.patch.object(
                    kbn_stack, "resolve_worktree", side_effect=AssertionError("unexpected worktree lookup")
                ):
                    assert kbn_stack.main(["--status"]) == 0

        load_registry.assert_called_once_with()
        run_status.assert_called_once_with({})

    def test_prune_removes_only_fully_stale_entries(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/ready": {"slot": 0, "backend": "snapshot", "ready": True},
            "/starting": {"slot": 1, "backend": "snapshot", "ready": False, "started_by_pid": 1234},
            "/degraded": {"slot": 2, "backend": "snapshot", "ready": True},
            "/stale": {"slot": 3, "backend": "snapshot", "ready": True},
        }
        alive_slots = {0: (True, True), 1: (False, False), 2: (False, True), 3: (False, False)}
        with mock.patch.object(kbn_stack, "pid_alive", side_effect=lambda pid: pid == 1234):
            with _patched_ports(kbn_stack, alive_slots=alive_slots) as state:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    assert kbn_stack.run_prune(registry) == 0

        assert set(registry) == {"/ready", "/starting", "/degraded"}
        assert set(state["saved"][-1]) == {"/ready", "/starting", "/degraded"}
        assert state["killed"] == []
        assert "/stale" in output.getvalue()

    def test_prune_does_not_require_a_kibana_worktree(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack, "load_registry", return_value={}) as load_registry:
            with mock.patch.object(kbn_stack, "run_prune", return_value=0) as run_prune:
                with mock.patch.object(
                    kbn_stack, "resolve_worktree", side_effect=AssertionError("unexpected worktree lookup")
                ):
                    assert kbn_stack.main(["--prune"]) == 0

        load_registry.assert_called_once_with()
        run_prune.assert_called_once_with({})

    def test_prune_may_ignore_the_exiting_launcher_pid(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/stale": {"slot": 0, "started_by_pid": 1234}}
        with mock.patch.object(kbn_stack, "pid_alive", side_effect=lambda pid: pid == 1234):
            with _patched_ports(kbn_stack, alive_slots={0: (False, False)}) as state:
                with contextlib.redirect_stdout(io.StringIO()):
                    assert kbn_stack.run_prune(registry, ignored_pid=1234) == 0

        assert registry == {}
        assert state["saved"][-1] == {}

    def test_when_trigger_precedes_detached_reader_should_detect_it(self):
        kbn_stack = _load_kbn_stack_command()

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(f"{kbn_stack.TRIGGER_STRING}\n", encoding="utf-8")
            with mock.patch.object(kbn_stack.time, "monotonic", side_effect=[0.0, 0.0, 2.0]):
                with mock.patch.object(kbn_stack.time, "sleep"):
                    detected = kbn_stack.wait_for_trigger(logfile, timeout=1)

        assert detected is True

    def test_when_trigger_follows_detached_reader_should_detect_it(self):
        kbn_stack = _load_kbn_stack_command()

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text("", encoding="utf-8")

            def write_trigger(_seconds):
                logfile.write_text(f"{kbn_stack.TRIGGER_STRING}\n", encoding="utf-8")

            with mock.patch.object(kbn_stack.time, "monotonic", side_effect=[0.0, 0.0, 0.0]):
                with mock.patch.object(kbn_stack.time, "sleep", side_effect=write_trigger):
                    detected = kbn_stack.wait_for_trigger(logfile, timeout=1)

        assert detected is True

    def test_when_trigger_precedes_interactive_reader_should_launch_kibana(self):
        kbn_stack = _load_kbn_stack_command()

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(f"{kbn_stack.TRIGGER_STRING}\n", encoding="utf-8")
            with mock.patch.object(kbn_stack, "ensure_trial_license") as ensure_trial:
                with mock.patch.object(kbn_stack.subprocess, "run") as run:
                    with mock.patch.object(kbn_stack, "kibana_ready", return_value=True):
                        with mock.patch.object(kbn_stack, "mark_ready") as mark_ready:
                            kbn_stack.start_kibana_on_trigger(
                                logfile,
                                "http://localhost:9200",
                                "yarn start",
                                "%2",
                                "/worktree",
                                "http://localhost:5601",
                            )

        ensure_trial.assert_called_once_with("http://localhost:9200")
        wrapped_command = shlex.join(
            [sys.executable, str(Path(kbn_stack.__file__).resolve()), "--run-with-prune", "yarn", "start"]
        )
        run.assert_called_once_with(
            ["tmux", "send-keys", "-t", "%2", wrapped_command, "C-m"],
            check=False,
        )
        mark_ready.assert_called_once_with("/worktree", True)

    def test_interrupted_kibana_wrapper_invokes_quiet_pruning(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/worktree": {"slot": 0}}
        with mock.patch.object(kbn_stack.subprocess, "run", side_effect=KeyboardInterrupt):
            with mock.patch.object(kbn_stack, "load_registry", return_value=registry):
                with mock.patch.object(kbn_stack, "run_prune") as run_prune:
                    assert kbn_stack.run_with_prune(["yarn", "start"]) == 130

        run_prune.assert_called_once_with(registry, quiet=True)

    def test_interrupted_foreground_es_invokes_quiet_pruning(self):
        kbn_stack = _load_kbn_stack_command()
        proc = mock.Mock()
        proc.stdout = mock.MagicMock()
        proc.stdout.__iter__.side_effect = KeyboardInterrupt
        registry = {"/worktree": {"slot": 0}}

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            with mock.patch.object(kbn_stack.subprocess, "Popen", return_value=proc):
                with mock.patch.object(kbn_stack, "load_registry", return_value=registry):
                    with mock.patch.object(kbn_stack, "run_prune") as run_prune:
                        with self.assertRaises(KeyboardInterrupt):
                            kbn_stack.run_foreground_es(["yarn", "es"], logfile)

        run_prune.assert_called_once_with(registry, ignored_pid=os.getpid(), quiet=True)

    def test_pid_alive_rejects_non_pid_values(self):
        kbn_stack = _load_kbn_stack_command()

        for value in (None, "123", 1.5, True, False, 0, -1, 1 << 100):
            with self.subTest(value=value):
                assert kbn_stack.pid_alive(value) is False

    def test_pid_alive_classifies_process_probe_results(self):
        kbn_stack = _load_kbn_stack_command()

        with mock.patch.object(kbn_stack.os, "kill", return_value=None):
            assert kbn_stack.pid_alive(1234) is True
        with mock.patch.object(kbn_stack.os, "kill", side_effect=ProcessLookupError):
            assert kbn_stack.pid_alive(1234) is False
        with mock.patch.object(kbn_stack.os, "kill", side_effect=PermissionError):
            assert kbn_stack.pid_alive(1234) is True

    def test_pid_alive_treats_zombie_as_dead(self):
        kbn_stack = _load_kbn_stack_command()
        child = os.fork()
        if child == 0:
            os._exit(0)
        try:
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if kbn_stack.pid_is_zombie(child):
                    break
                time.sleep(0.02)
            else:
                self.fail("child did not become a zombie")
            assert kbn_stack.pid_alive(child) is False
        finally:
            os.waitpid(child, 0)

    def test_ensure_ports_free_names_the_squatting_pid(self):
        kbn_stack = _load_kbn_stack_command()
        cfg = kbn_stack.derive(0)
        cfg["slot"] = 0

        with mock.patch.object(
            kbn_stack, "port_listener_pids", lambda port: [49880] if port == cfg["kbn_port"] else []
        ):
            with mock.patch.object(kbn_stack, "describe_pid", lambda pid: "node scripts/kibana --dev"):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    with self.assertRaises(SystemExit):
                        kbn_stack.ensure_ports_free(cfg)
        message = err.getvalue()
        assert "already in use" in message
        assert "49880" in message
        assert "node scripts/kibana --dev" in message

    def test_ensure_ports_free_passes_when_ports_are_free(self):
        kbn_stack = _load_kbn_stack_command()
        cfg = kbn_stack.derive(0)
        cfg["slot"] = 0

        with mock.patch.object(kbn_stack, "port_listener_pids", lambda port: []):
            kbn_stack.ensure_ports_free(cfg)

    def test_listener_identity_accepts_own_process_group_and_descendants(self):
        kbn_stack = _load_kbn_stack_command()

        with mock.patch.object(kbn_stack, "port_listener_pids", lambda port: [222]):
            with mock.patch.object(kbn_stack.os, "getpgid", lambda pid: 111):
                ok, listeners = kbn_stack.listener_identity_ok(5601, 111)
        assert ok is True
        assert listeners == [222]

        with mock.patch.object(kbn_stack, "port_listener_pids", lambda port: [333]):
            with mock.patch.object(kbn_stack.os, "getpgid", lambda pid: {111: 111, 333: 999}[pid]):
                with mock.patch.object(kbn_stack, "pid_ancestors", lambda pid: {111, 1}):
                    ok, _ = kbn_stack.listener_identity_ok(5601, 111)
        assert ok is True

    def test_listener_identity_rejects_foreign_squatter(self):
        kbn_stack = _load_kbn_stack_command()

        with mock.patch.object(kbn_stack, "port_listener_pids", lambda port: [49880]):
            with mock.patch.object(kbn_stack.os, "getpgid", lambda pid: {111: 111, 49880: 777}[pid]):
                with mock.patch.object(kbn_stack, "pid_ancestors", lambda pid: {777, 1}):
                    ok, listeners = kbn_stack.listener_identity_ok(5601, 111)
        assert ok is False
        assert listeners == [49880]

        with mock.patch.object(kbn_stack, "port_listener_pids", lambda port: []):
            ok, listeners = kbn_stack.listener_identity_ok(5601, 111)
        assert ok is False
        assert listeners == []

    def test_agent_start_does_not_stop_user_owned_serverless(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/user": {
                "backend": "serverless",
                "slot": 0,
                "started_by": kbn_stack.STARTED_BY_USER,
            }
        }
        blocked, stopped, saved = _capture_stop_existing_serverless(
            kbn_stack,
            registry,
            kbn_stack.STARTED_BY_AGENT,
        )

        assert blocked is True
        assert stopped == []
        assert "/user" in registry
        assert saved == []

    def test_agent_start_does_not_stop_any_serverless_when_user_owned_serverless_blocks(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/agent": {
                "backend": "serverless",
                "slot": 0,
                "started_by": kbn_stack.STARTED_BY_AGENT,
            },
            "/user": {
                "backend": "serverless",
                "slot": 0,
                "started_by": kbn_stack.STARTED_BY_USER,
            },
        }
        blocked, stopped, saved = _capture_stop_existing_serverless(
            kbn_stack,
            registry,
            kbn_stack.STARTED_BY_AGENT,
        )

        assert blocked is True
        assert stopped == []
        assert set(registry) == {"/agent", "/user"}
        assert saved == []

    def test_agent_start_may_replace_agent_owned_serverless(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/agent": {
                "backend": "serverless",
                "slot": 0,
                "started_by": kbn_stack.STARTED_BY_AGENT,
            }
        }
        blocked, stopped, _saved = _capture_stop_existing_serverless(
            kbn_stack,
            registry,
            kbn_stack.STARTED_BY_AGENT,
        )

        assert blocked is False
        assert stopped == [("/agent", False)]
        assert registry == {}

    def test_stop_entry_respects_user_owned_guard(self):
        kbn_stack = _load_kbn_stack_command()
        calls: list[str | tuple[str, int]] = []
        entry = {
            "backend": "serverless",
            "slot": 0,
            "started_by": kbn_stack.STARTED_BY_USER,
        }
        original_docker_kill_serverless = kbn_stack.docker_kill_serverless
        original_kill_pid_group = kbn_stack.kill_pid_group

        kbn_stack.docker_kill_serverless = lambda: calls.append("docker")
        kbn_stack.kill_pid_group = lambda pid: calls.append(("pid", pid))
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                assert kbn_stack.stop_entry("/user", entry, allow_user_owned=False) is False
            assert calls == []

            with contextlib.redirect_stdout(io.StringIO()):
                assert kbn_stack.stop_entry("/user", entry, allow_user_owned=True) is True
            assert calls == ["docker"]
        finally:
            kbn_stack.docker_kill_serverless = original_docker_kill_serverless
            kbn_stack.kill_pid_group = original_kill_pid_group

    def test_reclaim_dead_slots_frees_both_dead_snapshot_slot(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/A": {"slot": 0, "backend": "snapshot"},
            "/wt/B": {"slot": 1, "backend": "snapshot"},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                slot = kbn_stack.allocate_slot(registry, "/wt/C", None)

        assert changed is True
        assert "/wt/B" not in registry
        assert state["killed"] == []
        assert slot == 1

    def test_reclaim_keeps_slot_while_any_recorded_process_is_alive(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack, "pid_alive", side_effect=lambda pid: pid == 1234):
            for key in ("started_by_pid", "kbn_pid", "es_pid"):
                for liveness in ((False, False), (False, True)):
                    with self.subTest(key=key, liveness=liveness):
                        registry = {
                            "/wt/A": {"slot": 0, "backend": "snapshot"},
                            "/wt/B": {"slot": 1, "backend": "snapshot", key: 1234},
                        }
                        with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: liveness}) as state:
                            with contextlib.redirect_stdout(io.StringIO()):
                                changed = kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                                slot = kbn_stack.allocate_slot(registry, "/wt/C", None)

                        assert changed is False
                        assert "/wt/B" in registry
                        assert state["killed"] == []
                        assert slot == 2

    def test_reclaim_dead_recorded_process_still_frees_slot(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/A": {"slot": 0, "backend": "snapshot"},
            "/wt/B": {"slot": 1, "backend": "snapshot", "started_by_pid": 1234},
        }
        with mock.patch.object(kbn_stack, "pid_alive", return_value=False):
            with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: (False, False)}) as state:
                with contextlib.redirect_stdout(io.StringIO()):
                    changed = kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                    slot = kbn_stack.allocate_slot(registry, "/wt/C", None)

        assert changed is True
        assert "/wt/B" not in registry
        assert state["killed"] == []
        assert slot == 1

    def test_reclaim_kills_surviving_half_when_pair_split(self):
        kbn_stack = _load_kbn_stack_command()
        kbn_port, es_http = kbn_stack.derive(1)["kbn_port"], kbn_stack.derive(1)["es_http"]
        for alive, dead_survivor in (((False, True), es_http), ((True, False), kbn_port)):
            registry = {
                "/wt/A": {"slot": 0, "backend": "snapshot"},
                "/wt/B": {"slot": 1, "backend": "snapshot"},
            }
            with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: alive}) as state:
                with contextlib.redirect_stdout(io.StringIO()):
                    kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                    slot = kbn_stack.allocate_slot(registry, "/wt/C", None)
            assert state["killed"] == [dead_survivor], alive
            assert "/wt/B" not in registry
            assert slot == 1

    def test_reclaim_keeps_both_alive_slot_and_climbs(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/A": {"slot": 0, "backend": "snapshot"},
            "/wt/B": {"slot": 1, "backend": "snapshot"},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: (True, True)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                slot = kbn_stack.allocate_slot(registry, "/wt/C", None)

        assert changed is False
        assert "/wt/B" in registry
        assert state["killed"] == []
        assert slot == 2

    def test_reclaim_never_touches_serverless_entry(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/S": {"slot": 0, "backend": "serverless"}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                slot = kbn_stack.allocate_slot(registry, "/wt/C", None)

        assert changed is False
        assert "/wt/S" in registry
        assert state["killed"] == []
        assert slot == 1

    def test_reclaim_leaves_current_worktree_sticky(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot"}}
        with _patched_ports(kbn_stack, alive_slots={1: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.reclaim_dead_slots(registry, "/wt/B")
                slot = kbn_stack.allocate_slot(registry, "/wt/B", None)

        assert changed is False
        assert "/wt/B" in registry
        assert state["killed"] == []
        assert slot == 1

    def test_run_stop_reclaims_interactive_stack_by_port(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot", "started_by": kbn_stack.STARTED_BY_USER}}
        kbn_port, es_http = kbn_stack.derive(1)["kbn_port"], kbn_stack.derive(1)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.run_stop("/wt/B", registry)

        assert rc == 0
        assert "/wt/B" not in registry
        assert set(state["killed"]) == {kbn_port, es_http}

    def test_run_stop_drops_stale_entry_when_nothing_listens(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot", "started_by": kbn_stack.STARTED_BY_USER}}
        with _patched_ports(kbn_stack, alive_slots={1: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.run_stop("/wt/B", registry)

        assert rc == 0
        assert "/wt/B" not in registry
        assert state["killed"] == []

    def test_run_stop_all_reclaims_pidless_interactive_entry(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot", "started_by": kbn_stack.STARTED_BY_USER}}
        kbn_port, es_http = kbn_stack.derive(1)["kbn_port"], kbn_stack.derive(1)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.run_stop_all(registry)

        assert rc == 0
        assert state["saved"][-1] == {}
        assert set(state["killed"]) == {kbn_port, es_http}

    def test_run_stop_reclaims_ports_even_when_recorded_pids_exist(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/B": {
                "slot": 1,
                "backend": "snapshot",
                "started_by": kbn_stack.STARTED_BY_AGENT,
                "kbn_pid": 4242,
                "es_pid": 4243,
            }
        }
        kbn_port, es_http = kbn_stack.derive(1)["kbn_port"], kbn_stack.derive(1)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with mock.patch.object(kbn_stack, "kill_pid_group") as kill_group:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = kbn_stack.run_stop("/wt/B", registry)

        assert rc == 0
        assert "/wt/B" not in registry
        assert kill_group.mock_calls == [mock.call(4242), mock.call(4243)]
        assert set(state["killed"]) == {kbn_port, es_http}

    def test_kill_port_listeners_reaps_hang_after_unbind_process_group(self):
        kbn_stack = _load_kbn_stack_command()
        kbn_stack.KILL_GRACE_SECONDS = 0.2
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "hang_server.py"
            script.write_text(_HANG_AFTER_UNBIND_SERVER)
            port, pgid, members = _spawn_hang_after_unbind_group(script)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    acted = kbn_stack.kill_port_listeners(port)
                live = [pid for pid in members if kbn_stack.pid_alive(pid)]
                assert acted is True
                assert kbn_stack.port_listener_pids(port) == []
                assert live == [], live
            finally:
                _reap_group(pgid, leader=pgid)

    def test_snapshot_es_command_pins_merge_disk_watermark_before_user_flags(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args(["-E", "node.attr.foo=bar"])
        cfg = kbn_stack.derive(0)
        cfg["slot"] = 0
        cmd = kbn_stack.es_command(args, cfg, Path("/tmp/es-data"))
        settings = _es_dash_e_settings(cmd)
        assert "indices.merge.disk.watermark.high=2gb" in settings
        assert settings.index("indices.merge.disk.watermark.high=2gb") < settings.index("node.attr.foo=bar")

    def test_snapshot_es_command_lets_later_user_flag_override_merge_disk_watermark(self):
        kbn_stack = _load_kbn_stack_command()
        override = "indices.merge.disk.watermark.high=99%"
        args = kbn_stack.parse_args(["-E", override])
        cfg = kbn_stack.derive(0)
        cfg["slot"] = 0
        cmd = kbn_stack.es_command(args, cfg, Path("/tmp/es-data"))
        settings = _es_dash_e_settings(cmd)
        assert settings.count("indices.merge.disk.watermark.high=2gb") == 1
        assert settings.index("indices.merge.disk.watermark.high=2gb") < settings.index(override)

    def test_default_groups_platform_injects_allowlist_on_yarn_start(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args([])
        assert args.plugin_groups == ("platform",)
        assert args.es_heap == "1g"
        cmd = kbn_stack.kibana_command(args, kbn_stack.derive(0))
        assert "--plugins.allowlistPluginGroups.0=platform" in cmd
        assert "--plugins.allowlistPluginGroups.1=" not in cmd

    def test_groups_all_omits_allowlist(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args(["--groups", "all"])
        assert args.plugin_groups == ()
        cmd = kbn_stack.kibana_command(args, kbn_stack.derive(0))
        assert "allowlistPluginGroups" not in cmd

    def test_groups_comma_list_indexes_from_zero(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args(["--groups", "platform,security"])
        flags = kbn_stack.resolved_kbn_flags(args)
        assert flags[:2] == [
            "plugins.allowlistPluginGroups.0=platform",
            "plugins.allowlistPluginGroups.1=security",
        ]

    def test_explicit_k_allowlist_skips_group_injection(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args(["-K", "plugins.allowlistPluginGroups.0=security"])
        assert kbn_stack.resolved_kbn_flags(args) == ["plugins.allowlistPluginGroups.0=security"]

    def test_unknown_group_exits(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.parse_args(["--groups", "nope"])

    def test_groups_all_cannot_mix_with_named_groups(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.parse_args(["--groups", "all,platform"])

    def test_es_java_opts_sets_xms_xmx_and_keeps_other_tokens(self):
        kbn_stack = _load_kbn_stack_command()
        assert kbn_stack.es_java_opts("1g") == "-Xms1g -Xmx1g"
        assert kbn_stack.es_java_opts("512m", "-Xms1536m -Xmx1536m -XX:+UseG1GC") == "-Xms512m -Xmx512m -XX:+UseG1GC"

    def test_serverless_rejects_custom_es_heap(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.parse_args(["--es", "serverless", "--es-heap", "512m"])

    def test_serverless_allows_default_es_heap(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args(["--es", "serverless"])
        assert args.es_heap == "1g"

    def test_invalid_es_heap_exits(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.parse_args(["--es-heap", "1"])


class _BridgeMcpHandler(http.server.BaseHTTPRequestHandler):
    """Fake streamable-HTTP MCP endpoint for bridge tests.

    Accepts only tokens in ``live_tokens``; answers ``initialize`` with a JSON
    body plus ``Mcp-Session-Id``; answers requests via JSON or SSE (methods in
    ``sse_methods``); records every POST/DELETE with token and session id.
    """

    live_tokens: set[str] = set()
    sse_methods: set[str] = set()
    connect_timeouts_remaining: dict[str, int] = {}
    hits: list[tuple] = []
    lock = threading.Lock()

    def log_message(self, *args):
        pass

    def do_DELETE(self):
        with self.lock:
            self.hits.append(("DELETE", None, self.headers.get("Mcp-Session-Id")))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _reply(self, status: int, data: bytes = b"", content_type: str | None = None, session: str | None = None):
        self.send_response(status)
        if session:
            self.send_header("Mcp-Session-Id", session)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        token = self.headers.get("Authorization", "").rpartition(" ")[2]
        method = body.get("method")
        with self.lock:
            self.hits.append(("POST", method, token, self.headers.get("Mcp-Session-Id")))
            connect_timeouts_remaining = self.connect_timeouts_remaining.get(method, 0)
            if connect_timeouts_remaining:
                self.connect_timeouts_remaining[method] = connect_timeouts_remaining - 1
        if connect_timeouts_remaining:
            self._reply(
                503,
                b"upstream connect error or disconnect/reset before headers. reset reason: connection timeout",
                "text/plain",
            )
            return
        if token not in self.live_tokens:
            self._reply(401)
            return
        if method == "initialize":
            payload = {"jsonrpc": "2.0", "id": body.get("id"), "result": {"serverInfo": {"name": "fake"}}}
            self._reply(200, json.dumps(payload).encode(), "application/json", session="bridge-session")
            return
        if "id" not in body:
            self._reply(202)
            return
        if method in self.sse_methods:
            progress = {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"step": 1}}
            result = {"jsonrpc": "2.0", "id": body["id"], "result": {"via": "sse"}}
            data = (
                b"event: message\ndata: " + json.dumps(progress).encode() + b"\n\n"
                b"data: " + json.dumps(result).encode() + b"\n\n"
            )
            self._reply(200, data, "text/event-stream")
            return
        payload = {"jsonrpc": "2.0", "id": body["id"], "result": {"echo": method}}
        self._reply(200, json.dumps(payload).encode(), "application/json")


@contextlib.contextmanager
def _bridge_mcp_server(
    live_tokens: set[str],
    sse_methods: set[str] | None = None,
    connect_timeouts: dict[str, int] | None = None,
):
    _BridgeMcpHandler.live_tokens = set(live_tokens)
    _BridgeMcpHandler.sse_methods = set(sse_methods or ())
    _BridgeMcpHandler.connect_timeouts_remaining = dict(connect_timeouts or {})
    _BridgeMcpHandler.hits = []
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _BridgeMcpHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/mcp", _BridgeMcpHandler
    finally:
        httpd.shutdown()
        httpd.server_close()


class _BridgeSession:
    """Drive a ,mcp-token --bridge subprocess over stdio, one message at a time."""

    def __init__(
        self,
        home: Path,
        bindir: Path,
        server: str,
        url: str,
        *extra_args: str,
        cwd: Path | None = None,
    ):
        self.process = subprocess.Popen(
            [sys.executable, str(MCP_TOKEN_COMMAND), server, "--bridge", "--url", url, *extra_args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        self._lines: queue.Queue[bytes] = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line)

    def send(self, message: dict) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message).encode() + b"\n")
        self.process.stdin.flush()

    def recv(self, timeout: float = 10.0) -> dict:
        return json.loads(self._lines.get(timeout=timeout))

    def close(self, timeout: float = 10.0) -> int:
        assert self.process.stdin is not None
        self.process.stdin.close()
        returncode = self.process.wait(timeout=timeout)
        if self.process.stdout is not None:
            self.process.stdout.close()
        return returncode


class TestMcpTokenBridge(unittest.TestCase):
    """WHEN an agent session runs a hosted OAuth MCP server through the bridge.

    Real-seam tests: an isolated ``HOME`` holds cursor caches, a stub
    cursor-agent plays the refresh grant, and a fake streamable-HTTP server
    classifies bearers. The deep state table (resurrection, same-token retry,
    malformed stdin, concurrency) lives in the /tmp state-machine harness.
    """

    def _jwt(self, exp: int, subject: str = "a") -> str:
        def encode(value: dict[str, object]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'exp': exp, 'sub': subject})}.sig"

    def _write_cache(self, home: Path, server: str, token: str, *, workspace: Path | None = None) -> Path:
        project = home / ".cursor/projects/p"
        project.mkdir(parents=True, exist_ok=True)
        cache = project / "mcp-auth.json"
        cache.write_text(
            json.dumps({server: {"tokens": {"access_token": token, "refresh_token": "chain", "expires_in": 3600}}})
        )
        if workspace is not None:
            workspace.mkdir(parents=True, exist_ok=True)
            (project / ".workspace-trusted").write_text(json.dumps({"workspacePath": str(workspace)}))
        return cache

    INITIALIZE = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}

    def test_serves_requests_with_fresh_bearer_and_session_id(self):
        token = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp, _bridge_mcp_server({token}) as (url, handler):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_cache(home, "scsi-main", token)
            session = _BridgeSession(home, bindir, "scsi-main", url)
            session.send(self.INITIALIZE)
            init_response = session.recv()
            session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            session.send({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            list_response = session.recv()
            returncode = session.close()
            hits = list(handler.hits)

        assert returncode == 0
        assert init_response["result"]["serverInfo"]["name"] == "fake"
        assert list_response["id"] == 1 and list_response["result"]["echo"] == "tools/list"
        posts = [hit for hit in hits if hit[0] == "POST"]
        assert all(hit[2] == token for hit in posts), "every request must carry the cached bearer"
        assert posts[-1][3] == "bridge-session", "captured session id must be echoed"
        assert ("DELETE", None, "bridge-session") in hits, "stdin EOF must close the server session"

    def test_rejected_bearer_rotates_and_retries_within_session(self):
        stale = self._jwt(int(time.time()) + 3600, "stale")
        fresh = self._jwt(int(time.time()) + 3600, "fresh")
        with tempfile.TemporaryDirectory() as tmp, _bridge_mcp_server({fresh}) as (url, handler):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_cache(home, "scsi-main", stale, workspace=workspace)
            rotated = json.dumps(
                {"scsi-main": {"tokens": {"access_token": fresh, "refresh_token": "next", "expires_in": 3600}}}
            )
            agent = bindir / "cursor-agent"
            agent.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "$1 $2" = "mcp list-tools" ]; then\n'
                f"cat > {shlex.quote(str(cache))} <<'EOF'\n{rotated}\nEOF\n"
                "fi\nexit 0\n"
            )
            agent.chmod(0o755)
            session = _BridgeSession(home, bindir, "scsi-main", url)
            session.send(self.INITIALIZE)
            init_response = session.recv(timeout=30)
            returncode = session.close()
            hits = list(handler.hits)

        assert returncode == 0
        assert "result" in init_response, f"rotated retry must succeed: {init_response}"
        tokens_seen = [hit[2] for hit in hits if hit[0] == "POST" and hit[1] == "initialize"]
        assert tokens_seen == [stale, fresh], "exactly one rejected then one rotated retry"

    def test_expired_untrusted_cache_rotates_through_the_bridge_workspace(self):
        expired = self._jwt(int(time.time()) - 100, "expired")
        fresh = self._jwt(int(time.time()) + 3600, "fresh")
        with tempfile.TemporaryDirectory() as tmp, _bridge_mcp_server({fresh}) as (url, _handler):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "current-workspace"
            home.mkdir()
            bindir.mkdir()
            workspace.mkdir()
            source = home / ".cursor/projects/untrusted-source/mcp-auth.json"
            source.parent.mkdir(parents=True)
            source.write_text(
                json.dumps(
                    {
                        "scsi-main": {
                            "tokens": {
                                "access_token": expired,
                                "refresh_token": "chain",
                                "expires_in": 3600,
                            }
                        }
                    }
                )
            )
            project_slug = re.sub(r"[^A-Za-z0-9]+", "-", str(workspace.resolve())).strip("-")
            current_cache = home / ".cursor/projects" / project_slug / "mcp-auth.json"
            rotated = json.dumps(
                {"scsi-main": {"tokens": {"access_token": fresh, "refresh_token": "next", "expires_in": 3600}}}
            )
            agent = bindir / "cursor-agent"
            agent.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "$1 $2" = "mcp list-tools" ]; then\n'
                f"cat > {shlex.quote(str(current_cache))} <<'EOF'\n{rotated}\nEOF\n"
                "fi\nexit 0\n"
            )
            agent.chmod(0o755)
            session = _BridgeSession(home, bindir, "scsi-main", url, cwd=workspace)
            session.send(self.INITIALIZE)
            init_response = session.recv(timeout=3)
            returncode = session.close()

        assert returncode == 0
        assert "result" in init_response, f"current-workspace refresh chain must recover the bridge: {init_response}"

    def test_failed_refresh_chain_opens_browser_login_and_recovers(self):
        expired = self._jwt(int(time.time()) - 100, "expired")
        fresh = self._jwt(int(time.time()) + 3600, "fresh")
        with tempfile.TemporaryDirectory() as tmp, _bridge_mcp_server({fresh}) as (url, _handler):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_cache(home, "scsi-main", expired, workspace=workspace)
            calls = root / "cursor-agent.log"
            logged_in = json.dumps(
                {"scsi-main": {"tokens": {"access_token": fresh, "refresh_token": "next", "expires_in": 3600}}}
            )
            agent = bindir / "cursor-agent"
            agent.write_text(
                "#!/usr/bin/env bash\n"
                f'printf "%s\\n" "$*" >> {shlex.quote(str(calls))}\n'
                'if [ "$1 $2" = "mcp login" ]; then\n'
                f"cat > {shlex.quote(str(cache))} <<'EOF'\n{logged_in}\nEOF\n"
                "fi\n"
                "exit 0\n"
            )
            agent.chmod(0o755)
            session = _BridgeSession(home, bindir, "scsi-main", url)
            session.send(self.INITIALIZE)
            init_response = session.recv(timeout=5)
            returncode = session.close()
            invocations = calls.read_text().splitlines()

        assert returncode == 0
        assert "result" in init_response, f"browser login must recover the active bridge: {init_response}"
        assert invocations == [
            "mcp enable scsi-main",
            "mcp list-tools scsi-main",
            "mcp enable scsi-main",
            "mcp login scsi-main",
        ]

    def test_concurrent_bridges_share_one_browser_login(self):
        expired = self._jwt(int(time.time()) - 100, "expired")
        fresh = self._jwt(int(time.time()) + 3600, "fresh")
        with tempfile.TemporaryDirectory() as tmp, _bridge_mcp_server({fresh}) as (url, _handler):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_cache(home, "scsi-main", expired, workspace=workspace)
            calls = root / "cursor-agent.log"
            logged_in = json.dumps(
                {"scsi-main": {"tokens": {"access_token": fresh, "refresh_token": "next", "expires_in": 3600}}}
            )
            agent = bindir / "cursor-agent"
            agent.write_text(
                "#!/usr/bin/env bash\n"
                f'printf "%s\\n" "$*" >> {shlex.quote(str(calls))}\n'
                'if [ "$1 $2" = "mcp login" ]; then\n'
                "sleep 1\n"
                f"cat > {shlex.quote(str(cache))} <<'EOF'\n{logged_in}\nEOF\n"
                "fi\n"
                "exit 0\n"
            )
            agent.chmod(0o755)
            sessions = [_BridgeSession(home, bindir, "scsi-main", url) for _ in range(2)]
            for session in sessions:
                session.send(self.INITIALIZE)
            responses = [session.recv(timeout=8) for session in sessions]
            returncodes = [session.close() for session in sessions]
            invocations = calls.read_text().splitlines()

        assert returncodes == [0, 0]
        assert all("result" in response for response in responses)
        assert invocations.count("mcp login scsi-main") == 1

    def test_sse_response_streams_messages_in_order(self):
        token = self._jwt(int(time.time()) + 3600)
        with (
            tempfile.TemporaryDirectory() as tmp,
            _bridge_mcp_server({token}, sse_methods={"tools/call"}) as (url, _handler),
        ):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_cache(home, "scsi-main", token)
            session = _BridgeSession(home, bindir, "scsi-main", url)
            session.send(self.INITIALIZE)
            session.recv()
            session.send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "x"}})
            progress = session.recv()
            response = session.recv()
            returncode = session.close()

        assert returncode == 0
        assert progress["method"] == "notifications/progress", "SSE events must stream before the response"
        assert response["id"] == 2 and response["result"]["via"] == "sse"

    def test_opt_in_retries_upstream_connect_timeout_once(self):
        token = self._jwt(int(time.time()) + 3600)
        with (
            tempfile.TemporaryDirectory() as tmp,
            _bridge_mcp_server({token}, connect_timeouts={"tools/call": 1}) as (url, handler),
        ):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_cache(home, "scsi-main", token)
            session = _BridgeSession(home, bindir, "scsi-main", url, "--retry-connect-timeouts")
            session.send(self.INITIALIZE)
            session.recv(timeout=2)
            session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            session.send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_indices"}})
            response = session.recv(timeout=2)
            returncode = session.close()
            calls = [hit for hit in handler.hits if hit[0] == "POST" and hit[1] == "tools/call"]

        assert returncode == 0
        assert response["id"] == 3 and response["result"]["echo"] == "tools/call"
        assert len(calls) == 2, "the exact upstream connect timeout should be retried once"

    def test_connect_timeout_without_opt_in_is_not_retried(self):
        token = self._jwt(int(time.time()) + 3600)
        with (
            tempfile.TemporaryDirectory() as tmp,
            _bridge_mcp_server({token}, connect_timeouts={"tools/call": 1}) as (url, handler),
        ):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_cache(home, "slack", token)
            session = _BridgeSession(home, bindir, "slack", url)
            session.send(self.INITIALIZE)
            session.recv(timeout=2)
            session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            session.send({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "send_message"}})
            response = session.recv(timeout=2)
            returncode = session.close()
            calls = [hit for hit in handler.hits if hit[0] == "POST" and hit[1] == "tools/call"]

        assert returncode == 0
        assert response["id"] == 4
        assert response["error"]["message"] == "bridge request failed: HTTP 503"
        assert len(calls) == 1, "side-effecting endpoints must remain non-retriable by default"


if __name__ == "__main__":
    unittest.main()
