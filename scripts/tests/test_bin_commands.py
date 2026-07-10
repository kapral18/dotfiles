#!/usr/bin/env python3
"""Tests for deployed bin command wrappers and command libraries."""

from __future__ import annotations

import base64
import contextlib
import importlib.util
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
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

COPILOT_COMMAND = REPO / "home/exact_bin/executable_,copilot"


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

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_review/readonly_SKILL.md")

        assert result == "Use when the exact trigger matches. Load the skill before acting.\n"

    def test_normalizes_skill_instruction_wraps_without_splitting_short_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Finish a sentence before moving\nto the next line. Start the next sentence on its own line.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_review/readonly_SKILL.md")

        assert result == "Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"

    def test_normalizes_skill_list_items_without_splitting_short_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "- Finish a sentence before moving\n  to the next line. Start the next sentence on its own line.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_review/readonly_SKILL.md")

        assert (
            result == "- Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"
        )

    def test_preserves_indented_skill_prose_prefixes(self):
        unwrap_md = _load_unwrap_md_command()
        text = "   Finish a sentence before moving\n   to the next line. Start the next sentence on its own line.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_review/readonly_SKILL.md")

        assert (
            result == "   Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"
        )

    def test_wraps_skill_prose_at_sentence_boundary_over_soft_limit(self):
        unwrap_md = _load_unwrap_md_command()
        text = (
            "This sentence is deliberately long enough that appending the next sentence would cross the formatter boundary "
            "without needing to split this sentence. Start the next sentence on its own line.\n"
        )

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_review/readonly_SKILL.md")

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

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_review/readonly_SKILL.md")

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

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_review/readonly_SKILL.md")

        assert result == text

    def test_preserves_multiline_inline_code_examples(self):
        unwrap_md = _load_unwrap_md_command()
        text = "- `First sentence. Second sentence\nwithout closing until here.`\n"

        result = unwrap_md.unwrap(text, "home/readonly_AGENTS.md")

        assert result == text

    def test_does_not_split_common_abbreviations_as_skill_sentences(self):
        unwrap_md = _load_unwrap_md_command()
        text = 'Use examples, e.g. "the review skill", before acting. Then continue.\n'

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_review/readonly_SKILL.md")

        assert result == 'Use examples, e.g. "the review skill", before acting. Then continue.\n'

    def test_normalizes_skill_reference_short_sentence_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Keep the review gate visible.\nDo not bury it after another clause.\n"

        result = unwrap_md.unwrap(
            text,
            "home/exact_dot_agents/exact_skills/exact_review/exact_references/readonly_pr_common.md",
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


class TestCodexWrapper(unittest.TestCase):
    """WHEN launching Codex through the managed wrapper."""

    def _run_wrapper(
        self,
        *,
        token_helper_exit: int = 0,
        token: str = "fresh-token",
        args: list[str] | None = None,
        config_lines: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bindir = root / "bin"
            codex_home = home / ".codex"
            codex_home.mkdir(parents=True)
            bindir.mkdir()
            (codex_home / "config.toml").write_text(
                "\n".join(
                    config_lines
                    or [
                        "[mcp_servers.slack]",
                        'url = "https://mcp.slack.com/mcp"',
                        'bearer_token_env_var = "CODEX_MCP_TOKEN_SLACK"',
                        "",
                    ]
                )
            )
            (bindir / ",mcp-token").write_text(
                "#!/usr/bin/env bash\n"
                'printf \'%s\\n\' "$*" >> "$MCP_TOKEN_LOG"\n'
                f"if [[ {token_helper_exit} -ne 0 ]]; then exit {token_helper_exit}; fi\n"
                f"printf '%s\\n' {shlex.quote(token)}\n"
            )
            (bindir / ",mcp-token").chmod(0o755)
            real_codex = bindir / "codex-real"
            real_codex.write_text(
                "#!/usr/bin/env bash\n"
                "echo REAL_CODEX_STARTED\n"
                "echo TOKEN=${CODEX_MCP_TOKEN_SLACK-}\n"
                "printf 'ARGS=%s\\n' \"$*\"\n"
            )
            real_codex.chmod(0o755)

            return subprocess.run(
                [sys.executable, str(CODEX_COMMAND), *(args or [])],
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "CODEX_REAL_BIN": str(real_codex),
                    "MCP_TOKEN_LOG": str(root / "mcp-token.log"),
                },
            )

    def test_refreshes_mcp_token_env_before_launch(self):
        result = self._run_wrapper()

        assert result.returncode == 0
        assert "REAL_CODEX_STARTED" in result.stdout
        assert "TOKEN=fresh-token" in result.stdout

    def test_token_refresh_failure_blocks_launch(self):
        result = self._run_wrapper(token_helper_exit=1)

        assert result.returncode == 1
        assert "REAL_CODEX_STARTED" not in result.stdout
        assert "could not refresh MCP token(s): slack" in result.stderr

    def test_disabled_mcp_server_does_not_block_launch(self):
        result = self._run_wrapper(
            token_helper_exit=1,
            config_lines=[
                "[mcp_servers.slack]",
                "enabled = false",
                'url = "https://mcp.slack.com/mcp"',
                'bearer_token_env_var = "CODEX_MCP_TOKEN_SLACK"',
                "",
            ],
        )

        assert result.returncode == 0
        assert "REAL_CODEX_STARTED" in result.stdout
        assert "TOKEN=" in result.stdout
        assert "could not refresh MCP token(s): slack" not in result.stderr

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


class TestCopilotWrapper(unittest.TestCase):
    """WHEN classifying Copilot args to decide whether to refresh MCP tokens.

    The wrapper only skips the pre-launch token refresh for invocations that
    provably never open an MCP session. These regressions pin the fail-closed
    classifier against Copilot CLI 1.0.69's grammar using stubbed commands only
    (no real token, network, or Copilot session).
    """

    HEADER_AUTH_CONFIG = {"mcpServers": {"slack": {"type": "http", "headers": {"Authorization": "old-token"}}}}
    _USE_DEFAULT_CONFIG = object()

    def _run(
        self,
        args: list[str],
        *,
        config: object = _USE_DEFAULT_CONFIG,
        token_exit: int = 0,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bindir = root / "bin"
            (home / ".copilot").mkdir(parents=True)
            bindir.mkdir()
            # Symlink python3 into the stub bindir so the wrapper's PATH can
            # exclude chezmoi's install dir; the wrapper's rebake path is gated
            # on `command -v chezmoi`, so an absent chezmoi keeps the test fully
            # offline while python3 (for config parsing) stays available.
            (bindir / "python3").symlink_to(sys.executable)
            log = root / "mcp-token.log"
            token = bindir / ",mcp-token"
            token.write_text(f'#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> "$MCP_TOKEN_LOG"\nexit {token_exit}\n')
            token.chmod(0o755)
            real = bindir / "copilot-real"
            real.write_text("#!/usr/bin/env bash\nprintf 'REAL_COPILOT ARGS=%s\\n' \"$*\"\n")
            real.chmod(0o755)
            if config is not None:
                payload = self.HEADER_AUTH_CONFIG if config is self._USE_DEFAULT_CONFIG else config
                (home / ".copilot/mcp-config.json").write_text(json.dumps(payload))
            path = os.pathsep.join([str(bindir), "/usr/bin", "/bin", "/usr/sbin", "/sbin"])
            result = subprocess.run(
                [modern_bash(), str(COPILOT_COMMAND), *args],
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": path,
                    "COPILOT_REAL_BIN": str(real),
                    "MCP_TOKEN_LOG": str(log),
                },
            )
            token_calls = log.read_text() if log.exists() else ""
            return result, token_calls

    def _assert_refreshed(self, args: list[str]) -> None:
        result, token_calls = self._run(args)
        assert result.returncode == 0, result.stderr
        assert "slack --login --quiet" in token_calls, f"expected refresh for {args!r}"
        assert f"REAL_COPILOT ARGS={' '.join(args)}" in result.stdout

    def _assert_skipped(self, args: list[str]) -> None:
        result, token_calls = self._run(args)
        assert result.returncode == 0, result.stderr
        assert token_calls == "", f"expected no refresh for {args!r}, got {token_calls!r}"
        assert f"REAL_COPILOT ARGS={' '.join(args)}" in result.stdout

    def test_variadic_allow_tool_value_is_not_read_as_subcommand(self):
        # --allow-tool[=tools...] takes no space-separated value, so the trailing
        # `mcp` must not be misread as the admin subcommand: fail closed.
        self._assert_refreshed(["--allow-tool", "bash", "mcp", "-p", "hi"])

    def test_optional_value_resume_forces_refresh(self):
        # -r/--resume[=value] is optional-valued; `login` after it is ambiguous.
        self._assert_refreshed(["--resume", "login", "-p", "hi"])

    def test_prompt_flow_refreshes(self):
        self._assert_refreshed(["-p", "hi"])

    def test_model_flow_refreshes(self):
        self._assert_refreshed(["--model", "gpt-5.4", "-p", "hi"])

    def test_plugins_subcommand_skips_refresh(self):
        # `plugins` is a real 1.0.69 subcommand (distinct from `plugin`).
        self._assert_skipped(["plugins", "list"])

    def test_mcp_subcommand_skips_refresh(self):
        self._assert_skipped(["mcp", "list"])

    def test_help_after_global_flag_skips_refresh(self):
        self._assert_skipped(["--no-color", "--help"])

    def test_unknown_option_forces_refresh(self):
        # An unrecognized option may consume the next token, so the trailing
        # `mcp` must not be read as an admin subcommand: fail closed.
        self._assert_refreshed(["--future-value-option", "mcp"])

    def test_inline_ambiguous_allow_tool_forces_refresh(self):
        # Inline value form must still refresh: --allow-tool is variadic, so a
        # later bare `mcp` cannot be told apart from a swallowed value.
        self._assert_refreshed(["--allow-tool=bash", "mcp"])

    def test_inline_ambiguous_resume_forces_refresh(self):
        self._assert_refreshed(["--resume=login", "mcp"])

    def test_combined_short_flags_force_refresh(self):
        # -sp is -s plus -p<value>; treating it as a bare boolean would wrongly
        # skip, so unresolved short bundles fail closed.
        self._assert_refreshed(["-sp", "mcp"])

    def test_inline_required_value_model_stays_classifiable(self):
        # --model=<value> is a required-value option whose inline value is
        # self-contained, so the following `mcp` is an unambiguous subcommand.
        self._assert_skipped(["--model=gpt", "mcp"])

    def test_missing_config_generation_failure_blocks_launch(self):
        result, token_calls = self._run(["-p", "hi"], config=None)

        assert result.returncode == 1
        assert "could not re-bake fresh MCP tokens into" in result.stderr
        assert "REAL_COPILOT" not in result.stdout
        assert token_calls == ""

    def test_placeholder_authorization_blocks_launch(self):
        # The wrapper's refresh sentinel means "token still needs refreshing"; if
        # it survives into the config the wrapper must fail before launch.
        sentinel = re.search(r'refresh_placeholder="([^"]*)"', COPILOT_COMMAND.read_text())
        assert sentinel, "refresh_placeholder sentinel not found in wrapper"
        placeholder = {"mcpServers": {"slack": {"type": "http", "headers": {"Authorization": sentinel.group(1)}}}}
        result, token_calls = self._run(["-p", "hi"], config=placeholder)

        assert result.returncode == 1
        assert "MCP token refresh placeholder remains for: slack" in result.stderr
        assert "slack --login --quiet" in token_calls
        assert "REAL_COPILOT" not in result.stdout


if __name__ == "__main__":
    unittest.main()
