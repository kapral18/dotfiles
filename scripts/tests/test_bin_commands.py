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
import socket
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
from _test_support import (
    ARTIFACT_COMMAND,
    CODEX_COMMAND,
    KBN_STACK_COMMAND,
    MCP_TOKEN_COMMAND,
    REPO,
    modern_bash,
)


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
            (bindir / "cursor-agent").write_text(f"#!/usr/bin/env bash\ntouch {shlex.quote(str(cache))}\nexit 0\n")
            (bindir / "cursor-agent").chmod(0o755)
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "slack", "--login"],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home), "PATH": str(bindir)},
            )

        assert result.returncode == 0
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
    in the cache's trusted workspace instead of popping a browser. These are
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
        assert len(calls) == 1, calls
        cwd_str, sep, invoked = calls[0].partition(" mcp ")
        assert sep and invoked == "list-tools scsi-main", calls
        assert Path(cwd_str).resolve() == workspace.resolve(), "rotation must run in the cache's trusted workspace"
        assert hits == [], "JWT rotation must not probe the server"

    def test_no_proactive_rotation_defers_short_jwt_rotation(self):
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
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet", "--no-proactive-rotation"])
            cursor_ran = log.exists()

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == short, "the still-valid token must be returned without waiting"
        assert not cursor_ran, "proactive rotation must stay off the caller's critical path"

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
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet", "--no-proactive-rotation"])
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
        assert len(calls) == 1, f"only the same-token rejection may run cursor-agent, got {calls}"

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
        assert len(calls) == 1, "the rotation lock and due recheck must deduplicate concurrent rotations"

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

    def test_rotation_requires_refresh_token_and_trusted_workspace(self):
        expired = self._jwt(int(time.time()) - 100)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            # refresh_token present but no .workspace-trusted; and vice versa.
            self._write_rotatable_cache(home, "no-ws", "scsi-main", expired, workspace=None)
            self._write_rotatable_cache(home, "no-rt", "scsi-main", expired, refresh_token=None, workspace=root / "ws")
            cache = home / ".cursor/projects/no-ws/mcp-auth.json"
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 1, "no rotatable cache and a failed browser login must fail"
        assert not any("list-tools" in call for call in calls), "rotation must not run without a rotatable cache"
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

    def test_local_model_injects_catalog_metadata(self):
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
            result = subprocess.run(
                [sys.executable, str(CODEX_COMMAND), "--model", "local", "exec", "hi"],
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


class TestCursorWrapper(unittest.TestCase):
    """WHEN Cursor launches with a still-valid token due for proactive rotation."""

    def test_defers_proactive_rotation_to_cursor_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            config = home / ".cursor/mcp.json"
            config.parent.mkdir(parents=True)
            bindir.mkdir()
            config.write_text(json.dumps({"mcpServers": {"slack": {"oauth": {"clientId": "fixture"}}}}))
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
        assert calls == ["slack --login --quiet --no-proactive-rotation"]


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

    def test_run_stop_all_still_leaves_pidless_interactive_entry(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot", "started_by": kbn_stack.STARTED_BY_USER}}
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.run_stop_all(registry)

        assert rc == 0
        assert "/wt/B" in state["saved"][-1]
        assert state["killed"] == []


class _BridgeMcpHandler(http.server.BaseHTTPRequestHandler):
    """Fake streamable-HTTP MCP endpoint for bridge tests.

    Accepts only tokens in ``live_tokens``; answers ``initialize`` with a JSON
    body plus ``Mcp-Session-Id``; answers requests via JSON or SSE (methods in
    ``sse_methods``); records every POST/DELETE with token and session id.
    """

    live_tokens: set[str] = set()
    sse_methods: set[str] = set()
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
def _bridge_mcp_server(live_tokens: set[str], sse_methods: set[str] | None = None):
    _BridgeMcpHandler.live_tokens = set(live_tokens)
    _BridgeMcpHandler.sse_methods = set(sse_methods or ())
    _BridgeMcpHandler.hits = []
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _BridgeMcpHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/mcp", _BridgeMcpHandler
    finally:
        httpd.shutdown()


class _BridgeSession:
    """Drive a ,mcp-token --bridge subprocess over stdio, one message at a time."""

    def __init__(self, home: Path, bindir: Path, server: str, url: str):
        self.process = subprocess.Popen(
            [sys.executable, str(MCP_TOKEN_COMMAND), server, "--bridge", "--url", url],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
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
        return self.process.wait(timeout=timeout)


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


if __name__ == "__main__":
    unittest.main()
