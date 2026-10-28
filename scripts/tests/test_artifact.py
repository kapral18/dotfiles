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


class TestArtifactCommand(unittest.TestCase):
    """WHEN creating cache-only browser artifacts."""

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
                # The overlay must post feedback back to the server that served it.
                assert json.dumps(info["server_url"]) in script_response.read().decode()
                asset_response = urlopen(info["server_url"] + "/assets/chrome.js", timeout=5)
                assert asset_response.headers["content-type"] == "application/javascript; charset=utf-8"
                assert asset_response.read().decode() == artifact_assets.asset_text("chrome.js")
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
