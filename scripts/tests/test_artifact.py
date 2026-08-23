#!/usr/bin/env python3
"""Focused tests for artifact."""

from __future__ import annotations

import importlib
import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})

ARTIFACT_MODULE_DIR = ARTIFACT_COMMAND.parent
if str(ARTIFACT_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(ARTIFACT_MODULE_DIR))

artifact_assets = importlib.import_module("assets")
artifact_feedback = importlib.import_module("feedback")
artifact_server = importlib.import_module("server")


class TestArtifactCommand(unittest.TestCase):
    """WHEN creating cache-only browser artifacts."""

    def test_detects_dotfiles_ambient_theme(self):

        theme = artifact_assets.detect_ambient_theme(REPO)

        assert theme["name"] == "dotfiles"
        assert ".mermaids/" in theme["markers"]
        assert "home/" in theme["markers"]

    def test_injects_ambient_theme_once(self):
        html_doc = "<!doctype html><html><head><title>x</title></head><body><main>hello</main></body></html>"

        themed = artifact_assets.inject_ambient_theme(html_doc)
        twice = artifact_assets.inject_ambient_theme(themed)

        assert artifact_assets.AMBIENT_THEME_STYLE_ID in themed
        assert themed == twice
        assert themed.index(artifact_assets.AMBIENT_THEME_STYLE_ID) < themed.index("</head>")

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

        batch = artifact_feedback.normalize_feedback_batch(
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
        prompts = artifact_feedback.flatten_feedback_batches([batch])
        assert [item["prompt"] for item in prompts] == ["tighten this", "add checklist"]
        assert prompts[0]["item_index"] == 1
        assert prompts[1]["item_index"] == 2
        assert prompts[0]["batch_id"] == batch["batch_id"]

    def test_live_feedback_context_survives_normalization(self):

        batch = artifact_feedback.normalize_feedback_batch(
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
        prompt = artifact_feedback.flatten_feedback_batches([batch])[0]
        assert prompt["source"] == "live-overlay"
        assert prompt["url"] == "http://localhost:5601/app/demo"
        assert prompt["role"] == "button"
        assert prompt["rect"]["width"] == 30
        assert prompt["ancestors"][0]["selector"] == "form"

    def test_multi_target_feedback_survives_normalization(self):

        batch = artifact_feedback.normalize_feedback_batch(
            {
                "items": [
                    {
                        "prompt": "merge these two cards",
                        "selector": "main > section:nth-of-type(1)",
                        "text": "First card",
                        "targets": [
                            {"selector": "main > section:nth-of-type(1)", "text": "First card", "selection": ""},
                            {"selector": "main > section:nth-of-type(2)", "text": "Second card", "selection": ""},
                        ],
                    }
                ]
            }
        )

        assert batch is not None
        prompt = artifact_feedback.flatten_feedback_batches([batch])[0]
        assert prompt["prompt"] == "merge these two cards"
        assert len(prompt["targets"]) == 2
        assert prompt["targets"][1]["text"] == "Second card"

    def test_feedback_poll_archives_delivered_batches(self):
        with tempfile.TemporaryDirectory() as tmp:
            fdir = Path(tmp) / "feedback"
            fdir.mkdir()
            old_feedback_dir = artifact_feedback.feedback_dir
            artifact_feedback.feedback_dir = lambda: fdir
            try:
                pending = artifact_feedback.feedback_path("demo")
                pending.write_text('{"prompt":"tighten"}\n', encoding="utf-8")

                records, archive = artifact_feedback.read_and_archive_feedback("demo")

                assert [record["prompt"] for record in records] == ["tighten"]
                assert archive is not None
                assert archive.is_file()
                assert not pending.exists()
                assert archive.parent == fdir / "delivered"
            finally:
                artifact_feedback.feedback_dir = old_feedback_dir

    def test_clear_ended_allows_reusing_artifact_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            fdir = Path(tmp) / "feedback"
            fdir.mkdir()
            old_feedback_dir = artifact_feedback.feedback_dir
            artifact_feedback.feedback_dir = lambda: fdir
            try:
                ended = artifact_feedback.ended_path("demo")
                ended.write_text("", encoding="utf-8")

                artifact_feedback.clear_ended("demo")

                assert not ended.exists()
            finally:
                artifact_feedback.feedback_dir = old_feedback_dir

    def test_register_poller_tracks_current_session_and_unregisters(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp) / "pollers"
            old_pollers_dir = artifact_feedback.pollers_dir
            artifact_feedback.pollers_dir = lambda: pdir
            try:
                artifact_feedback.register_poller("demo", 30)

                path = artifact_feedback.poller_path("demo")
                record = json.loads(path.read_text(encoding="utf-8"))
                assert record["artifact"] == "demo.html"
                assert record["pid"] == os.getpid()
                assert record["timeout"] == 30
                assert record["session_dir"]

                artifact_feedback.unregister_poller("demo")

                assert not path.exists()
            finally:
                artifact_feedback.pollers_dir = old_pollers_dir

    def test_stale_poller_records_are_pruned(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp) / "pollers"
            pdir.mkdir()
            old_pollers_dir = artifact_feedback.pollers_dir
            artifact_feedback.pollers_dir = lambda: pdir
            try:
                stale = pdir / "demo.html.json"
                stale.write_text(json.dumps({"artifact": "demo.html", "pid": 999999999}) + "\n", encoding="utf-8")

                assert artifact_feedback.active_poller_records() == []
                assert not stale.exists()
            finally:
                artifact_feedback.pollers_dir = old_pollers_dir

    def test_current_pid_record_must_still_match_poller_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp) / "pollers"
            pdir.mkdir()
            old_pollers_dir = artifact_feedback.pollers_dir
            artifact_feedback.pollers_dir = lambda: pdir
            try:
                stale = pdir / "demo.html.json"
                stale.write_text(json.dumps({"artifact": "demo.html", "pid": os.getpid()}) + "\n", encoding="utf-8")

                assert artifact_feedback.active_poller_records() == []
                assert not stale.exists()
            finally:
                artifact_feedback.pollers_dir = old_pollers_dir

    def test_poller_command_parser_extracts_artifact_name(self):

        assert (
            artifact_feedback.poll_artifact_from_command("python3 /Users/me/bin/,artifact poll demo --timeout 60")
            == "demo.html"
        )
        assert (
            artifact_feedback.poll_artifact_from_command("python3 home/exact_lib/exact_,artifact/main.py poll")
            == "artifact.html"
        )
        assert artifact_feedback.poll_artifact_from_command("python3 /tmp/other poll demo") is None

    def test_stop_poller_record_does_not_kill_unmatched_pid(self):

        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.html.json"
            record = {"artifact": "demo.html", "pid": child.pid, "path": str(path)}
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            try:
                artifact_feedback.stop_poller_record(record)

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

        injected = artifact_assets.inject_client_script("<html><body><main><p>hello</p></main></body></html>")
        chrome = artifact_assets.chrome_page("demo.html")
        chrome_css = artifact_assets.asset_text("chrome.css")
        chrome_js = artifact_assets.asset_text("chrome.js")

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
        assert "dock expanded upward" in chrome_js
        assert ".dock.expanded" in chrome_css

    def test_chrome_exposes_cmd_click_multi_target_selection(self):

        injected = artifact_assets.inject_client_script("<html><body><main><p>hello</p></main></body></html>")
        chrome = artifact_assets.chrome_page("demo.html")
        chrome_js = artifact_assets.asset_text("chrome.js")

        assert "__agent_artifact_multi" in injected
        assert "let multiSelected = [];" in injected
        assert "function toggleMulti" in injected
        assert "event.metaKey || event.ctrlKey" in injected
        assert "agent-artifact-multi-context" in injected
        assert "agent-artifact-multi-clear" in injected
        assert "let multiContexts = [];" in chrome_js
        assert "item.targets = multiContexts.slice();" in chrome_js
        assert "targets pinned" in chrome_js
        assert "Cmd-click" in chrome

    def test_generated_feedback_mode_starts_hidden_and_gates_capture(self):

        injected = artifact_assets.inject_client_script("<html><body><button>Save</button></body></html>")
        chrome = artifact_assets.chrome_page("demo.html")
        chrome_js = artifact_assets.asset_text("chrome.js")

        assert "let captureEnabled = false;" in injected
        assert 'event.data.type === "agent-artifact-capture"' in injected
        assert injected.count("if (!captureEnabled) return;") == 3
        assert "if (!captureEnabled) clearHighlights();" in injected
        assert 'id="feedbackToggle"' in chrome
        assert 'aria-expanded="false"' in chrome
        assert "let feedbackActive = false;" in chrome_js
        assert 'document.body.classList.toggle("feedback-active", feedbackActive)' in chrome_js
        assert "agent-artifact-capture" in chrome_js

    def test_live_overlay_script_exposes_pause_teardown_and_minimal_context(self):

        script = artifact_server.live_overlay_script("live.html", "http://127.0.0.1:12345")

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

    def test_live_overlay_script_exposes_cmd_click_multi_target_selection(self):

        script = artifact_server.live_overlay_script("live.html", "http://127.0.0.1:12345")

        assert "const MULTI_CLASS" in script
        assert "let multiSelected = [];" in script
        assert "function toggleMulti(el, expand, selection)" in script
        assert "event.metaKey || event.ctrlKey" in script
        assert "item = { prompt, ...targets[0], targets };" in script
        assert "value.targets && value.targets.length" in script
        assert "Cmd-click pins multiple targets" in script
        assert 'window.addEventListener("scroll", syncHighlights, true);' in script

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
                asset_response = urlopen(info["server_url"] + "/assets/chrome.js", timeout=5)
                assert asset_response.headers["content-type"] == "application/javascript; charset=utf-8"
                assert "window.__AGENT_ARTIFACT_NAME__" in asset_response.read().decode()
                options = urlopen(
                    Request(info["feedback_url"], method="OPTIONS", headers={"origin": "http://localhost:5601"}),
                    timeout=5,
                )
                assert options.status == 204
                assert options.headers["access-control-allow-origin"] == "*"
            finally:
                subprocess.run([*command, "stop"], cwd=REPO, env=env, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
