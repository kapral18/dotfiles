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
artifact_commands = importlib.import_module("commands")
artifact_server = importlib.import_module("server")


class TestArtifactCommand(unittest.TestCase):
    """WHEN creating cache-only browser artifacts."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = mock.patch.dict(os.environ, {"XDG_CACHE_HOME": tmp.name})
        env.start()
        self.addCleanup(env.stop)

    def _check_feedback_client(self, case):
        result = subprocess.run(
            [
                "node",
                str(Path(__file__).with_name("artifact_client_harness.cjs")),
                str(ARTIFACT_MODULE_DIR / "chrome.js"),
                str(ARTIFACT_MODULE_DIR / "live_overlay.js"),
                case,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "completed: " + case, result.stdout.splitlines(), "client case did not reach its completion oracle"
        )

    def test_feedback_frame_preserves_typed_authorship(self):
        self._check_feedback_client("context")

    def test_feedback_clients_preserve_inflight_trays(self):
        self._check_feedback_client("submissions")

    def test_clean_stops_owned_processes_across_cached_contexts_before_deleting_metadata(self):
        import argparse
        import signal

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cache with spaces"
            contexts = [root / "sessions" / "tmux" / name for name in ("one", "two")]
            for index, sdir in enumerate(contexts):
                (sdir / "pollers").mkdir(parents=True)
                (sdir / "server.json").write_text(json.dumps({"pid": 100 + index, "process_started_at": "owned"}))
                (sdir / "pollers" / "demo.html.json").write_text(
                    json.dumps(
                        {
                            "pid": 200 + index,
                            "process_started_at": "owned",
                            "artifact": "demo.html",
                        }
                    )
                )

            def command(pid):
                if 100 <= pid < 102:
                    return f"python3 {artifact_server.ENTRYPOINT} server --session-dir {contexts[pid - 100]}"
                return f"python3 {ARTIFACT_MODULE_DIR / 'main.py'} poll demo"

            killed = []

            def kill(pid, sig):
                if sig:
                    self.assertTrue(root.exists())
                    self.assertTrue(any(root.rglob("*.json")))
                    killed.append((pid, sig))

            with (
                mock.patch.object(artifact_commands, "cache_root", return_value=root),
                mock.patch.object(artifact_feedback, "command_line_for_pid", side_effect=command),
                mock.patch.object(artifact_server, "command_line_for_pid", side_effect=command, create=True),
                mock.patch.object(artifact_feedback, "process_started_at", return_value="owned", create=True),
                mock.patch.object(artifact_server, "process_started_at", return_value="owned", create=True),
                mock.patch.object(artifact_feedback.os, "kill", side_effect=kill),
            ):
                artifact_commands.clean(argparse.Namespace(all=True))
            self.assertEqual(
                set(killed),
                {(100, signal.SIGTERM), (101, signal.SIGTERM), (200, signal.SIGTERM), (201, signal.SIGTERM)},
            )
            self.assertFalse(root.exists())

    def test_clean_preserves_every_context_when_any_live_record_cannot_be_verified(self):
        import argparse

        scenarios = [
            ("server", None, "owned", "valid"),
            ("poller", None, "owned", "valid"),
            ("server", "old", "owned", "valid"),
            ("poller", "owned", None, "valid"),
            ("server", "owned", "owned", "unrelated command"),
        ]
        for kind, recorded_start, actual_start, actual_command in scenarios:
            with (
                self.subTest(
                    kind=kind, recorded_start=recorded_start, actual_start=actual_start, actual_command=actual_command
                ),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp)
                owned = root / "sessions" / "tmux" / "a-owned"
                uncertain = root / "sessions" / "tmux" / "z-uncertain"
                owned.mkdir(parents=True)
                uncertain.mkdir()
                (owned / "server.json").write_text(json.dumps({"pid": 100, "process_started_at": "owned"}))
                record = {"pid": 200}
                if recorded_start is not None:
                    record["process_started_at"] = recorded_start
                if kind == "poller":
                    (uncertain / "pollers").mkdir()
                    record["artifact"] = "demo.html"
                    record_path = uncertain / "pollers" / "demo.html.json"
                else:
                    record_path = uncertain / "server.json"
                record_path.write_text(json.dumps(record))
                expected = {path.relative_to(root): path.read_bytes() for path in root.rglob("*.json")}
                signals = []

                def command(pid):
                    if pid == 100:
                        return f"python3 {artifact_server.ENTRYPOINT} server --session-dir {owned}"
                    if actual_command != "valid":
                        return actual_command
                    if kind == "server":
                        return f"python3 {artifact_server.ENTRYPOINT} server --session-dir {uncertain}"
                    return f"python3 {ARTIFACT_MODULE_DIR / 'main.py'} poll demo"

                def started(pid):
                    return "owned" if pid == 100 else actual_start

                def kill(pid, sig):
                    if sig:
                        signals.append((pid, sig))

                with (
                    mock.patch.object(artifact_commands, "cache_root", return_value=root),
                    mock.patch.object(artifact_feedback.os, "kill", side_effect=kill),
                    mock.patch.object(artifact_feedback, "command_line_for_pid", side_effect=command),
                    mock.patch.object(artifact_server, "command_line_for_pid", side_effect=command),
                    mock.patch.object(artifact_feedback, "process_started_at", side_effect=started),
                    mock.patch.object(artifact_server, "process_started_at", side_effect=started),
                ):
                    with self.assertRaisesRegex(SystemExit, "cannot verify active"):
                        artifact_commands.clean(argparse.Namespace(all=True))
                self.assertEqual(signals, [], "preflight must finish for all contexts before stopping any process")
                self.assertEqual({path.relative_to(root): path.read_bytes() for path in root.rglob("*.json")}, expected)

    def test_clean_removes_dead_legacy_server_and_poller_records(self):
        import argparse

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sdir = root / "sessions" / "tmux" / "context"
            (sdir / "pollers").mkdir(parents=True)
            (sdir / "server.json").write_text(json.dumps({"pid": 100}))
            (sdir / "pollers" / "demo.html.json").write_text(json.dumps({"pid": 200, "artifact": "demo.html"}))
            signals = []

            def kill(pid, sig):
                if sig == 0:
                    raise ProcessLookupError()
                signals.append((pid, sig))

            with (
                mock.patch.object(artifact_commands, "cache_root", return_value=root),
                mock.patch.object(artifact_feedback.os, "kill", side_effect=kill),
            ):
                artifact_commands.clean(argparse.Namespace(all=True))
            self.assertEqual(signals, [])
            self.assertFalse(root.exists())

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

    def test_feedback_reader_waits_for_the_producer_before_archiving(self):
        import argparse

        handlers = []

        class HTTPTransport:
            server_address = ("127.0.0.1", 1)

            def __init__(self, address, handler):
                handlers.append(handler)

            def server_close(self):
                pass

            def serve_forever(self):
                return

        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp)
            fdir = sdir / "feedback"
            with (
                mock.patch.object(artifact_server, "ArtifactHTTPServer", HTTPTransport),
                mock.patch.object(artifact_server.secrets, "token_urlsafe", return_value="request-token"),
            ):
                artifact_server.run_server(argparse.Namespace(session_dir=sdir))
            payload = json.dumps({"items": [{"prompt": "preserve this feedback"}]}).encode()
            handler = handlers[0].__new__(handlers[0])
            handler.path = "/api/feedback/demo"
            handler.headers = {
                "host": "127.0.0.1:1",
                "x-artifact-token": "request-token",
                "content-length": str(len(payload)),
            }
            handler.rfile = io.BytesIO(payload)
            handler.send_json = mock.Mock()
            opened = threading.Event()
            release = threading.Event()
            reader_done = threading.Event()
            original_open = Path.open
            errors = []
            delivered = []

            class PausedWrite:
                def __init__(self, handle):
                    self.handle = handle

                def __enter__(self):
                    opened.set()
                    if not release.wait(5):
                        raise TimeoutError("producer was not released")
                    return self.handle

                def __exit__(self, *args):
                    self.handle.close()

            def open_file(path, mode="r", *args, **kwargs):
                handle = original_open(path, mode, *args, **kwargs)
                if mode == "a" and path.suffix == ".jsonl":
                    return PausedWrite(handle)
                return handle

            def produce():
                try:
                    handler.do_POST()
                except BaseException as error:
                    errors.append(error)

            def consume():
                try:
                    delivered.extend(artifact_feedback.read_and_archive_feedback("demo")[0])
                except BaseException as error:
                    errors.append(error)
                finally:
                    reader_done.set()

            with (
                mock.patch.object(artifact_feedback, "feedback_dir", return_value=fdir),
                mock.patch.object(Path, "open", open_file),
            ):
                producer = threading.Thread(target=produce)
                reader = threading.Thread(target=consume)
                producer.start()
                self.assertTrue(opened.wait(5))
                reader.start()
                try:
                    self.assertFalse(reader_done.wait(0.1), "reader must wait for the append to finish")
                finally:
                    release.set()
                    producer.join(5)
                    reader.join(5)
                self.assertFalse(producer.is_alive() or reader.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(
                    [item["prompt"] for batch in delivered for item in batch["items"]], ["preserve this feedback"]
                )
                self.assertFalse(artifact_feedback.feedback_path("demo").exists())

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

    def test_live_unverified_poller_metadata_survives_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp) / "pollers"
            pdir.mkdir()
            old_pollers_dir = artifact_feedback.pollers_dir
            artifact_feedback.pollers_dir = lambda: pdir
            try:
                stale = pdir / "demo.html.json"
                stale.write_text(json.dumps({"artifact": "demo.html", "pid": os.getpid()}) + "\n", encoding="utf-8")

                actual = artifact_feedback.active_poller_records()
                self.assertEqual(len(actual), 1)
                self.assertEqual(actual[0]["ownership"], "unverified")
                self.assertTrue(stale.exists())
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
                with self.assertRaisesRegex(SystemExit, "cannot verify active poller"):
                    artifact_feedback.stop_poller_record(record)

                assert child.poll() is None
                assert path.exists()
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


class TestArtifactLifecycle(unittest.TestCase):
    def test_server_binding_does_not_require_reverse_dns(self):
        import argparse

        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp) / "session"
            with (
                mock.patch.dict(os.environ, {"XDG_CACHE_HOME": tmp}),
                mock.patch(
                    "socket.getfqdn", side_effect=AssertionError("local binding must not resolve a hostname")
                ) as dns,
                mock.patch.object(artifact_server.ThreadingHTTPServer, "serve_forever", return_value=None),
            ):
                artifact_server.run_server(argparse.Namespace(session_dir=sdir))
                dns.assert_not_called()
                self.assertFalse((sdir / "server.json").exists())

    def test_server_owner_matches_the_same_cache_through_a_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp) / "real"
            sdir.mkdir()
            alias = Path(tmp) / "alias"
            alias.symlink_to(sdir, target_is_directory=True)
            pid = os.getpid()
            state = {"pid": pid, "process_started_at": artifact_server.process_started_at(pid)}
            prefix = f"python3 {artifact_server.ENTRYPOINT} server --session-dir "
            with mock.patch.object(artifact_server, "command_line_for_pid", return_value=prefix + str(alias)):
                self.assertTrue(artifact_server.record_matches_live_server(sdir, state))
            with mock.patch.object(
                artifact_server, "command_line_for_pid", return_value=prefix + str(Path(tmp) / "other")
            ):
                self.assertFalse(artifact_server.record_matches_live_server(sdir, state))

    def test_concurrent_polls_with_the_same_sanitized_name_admit_one_owner(self):
        import select
        import textwrap

        script = textwrap.dedent(
            """
            import signal
            import sys
            from pathlib import Path
            from unittest import mock

            signal.alarm(10)
            sys.path.insert(0, sys.argv[1])
            import feedback

            role, name = sys.argv[2:]
            original_write = Path.write_text
            record_path = feedback.poller_path(name)

            def write(path, *args, **kwargs):
                if role == "first" and path == record_path:
                    print("publishing", flush=True)
                    sys.stdin.readline()
                return original_write(path, *args, **kwargs)

            print("attempting", flush=True)
            with mock.patch.object(Path, "write_text", write):
                try:
                    feedback.register_poller(name, 30)
                except SystemExit:
                    print("refused", flush=True)
                else:
                    print("registered", flush=True)
                    sys.stdin.readline()
                    feedback.unregister_poller(name)
            """
        )
        children = []

        def read_line(child):
            self.assertTrue(select.select([child.stdout], [], [], 5)[0], "poller fixture did not respond")
            return child.stdout.readline().decode().strip()

        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "XDG_CACHE_HOME": tmp, "TMUX": ""}
            try:
                for role, name in (("first", "demo name"), ("second", "demo-name")):
                    child = subprocess.Popen(
                        [sys.executable, "-c", script, str(ARTIFACT_MODULE_DIR), role, name],
                        cwd=REPO,
                        env=env,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0,
                    )
                    children.append(child)
                    self.assertEqual(read_line(child), "attempting")
                    if role == "first":
                        self.assertEqual(read_line(child), "publishing")
                first, second = children
                self.assertFalse(
                    select.select([second.stdout], [], [], 0.2)[0],
                    "a competing poller completed admission while the first owner was publishing",
                )
                first.stdin.write(b"publish\n")
                self.assertEqual(read_line(first), "registered")
                self.assertEqual(read_line(second), "refused")
                self.assertEqual(second.wait(timeout=5), 0)
                record_path = next(Path(tmp).glob("agent-artifacts/sessions/*/*/pollers/demo-name.html.json"))
                self.assertEqual(json.loads(record_path.read_text())["pid"], first.pid)
                first.stdin.write(b"finish\n")
                self.assertEqual(first.wait(timeout=5), 0)
                self.assertFalse(record_path.exists())
            finally:
                for child in children:
                    if child.poll() is None:
                        child.terminate()
                    child.wait(timeout=5)
                    for stream in (child.stdin, child.stdout, child.stderr):
                        stream.close()

    def test_server_admission_preserves_a_live_owner_with_unverified_metadata(self):
        import argparse

        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp) / "agent-artifacts" / "sessions" / "tmux" / "context"
            sdir.mkdir(parents=True)
            state_path = sdir / "server.json"
            state_path.write_text(json.dumps({"pid": os.getpid()}))
            expected = state_path.read_bytes()
            with (
                mock.patch.dict(os.environ, {"XDG_CACHE_HOME": tmp}),
                mock.patch.object(artifact_server, "ArtifactHTTPServer") as transport,
                mock.patch.object(artifact_server.subprocess, "Popen") as spawn,
            ):
                for admit in (
                    lambda: artifact_server.start_server(sdir),
                    lambda: artifact_server.run_server(argparse.Namespace(session_dir=sdir)),
                ):
                    with self.assertRaises(SystemExit):
                        admit()
                    self.assertEqual(state_path.read_bytes(), expected)
                    transport.assert_not_called()
                    spawn.assert_not_called()
                transport.assert_not_called()
                spawn.assert_not_called()

    def test_concurrent_server_starters_reuse_the_serving_owner_after_a_contender_exits(self):
        import argparse

        real_pid = os.getpid()
        identities = {}
        alive = set()
        children = []
        transports = {}
        results = []
        errors = []
        children_ready = threading.Event()
        release_children = threading.Event()
        loser_polled = threading.Event()
        shutdown = threading.Event()
        construction = threading.Lock()

        def getpid():
            return identities.get(threading.get_ident(), real_pid)

        def kill(pid, sig):
            if pid not in alive:
                raise ProcessLookupError()

        class HTTPTransport:
            def __init__(self, address, handler):
                self.pid = getpid()
                self.server_address = ("127.0.0.1", 7000 + len(transports))
                self.serving = threading.Event()
                transports[self.pid] = self

            def server_close(self):
                pass

            def serve_forever(self):
                self.serving.set()
                if not shutdown.wait(8):
                    raise TimeoutError("serving fixture was not stopped")

        class Child:
            def __init__(self, pid, sdir):
                self.pid = pid
                self.sdir = sdir
                self.done = threading.Event()
                self.thread = threading.Thread(target=self.run)

            def run(self):
                identities[threading.get_ident()] = self.pid
                try:
                    if not release_children.wait(5):
                        raise TimeoutError("server contenders were not released")
                    artifact_server.run_server(argparse.Namespace(session_dir=self.sdir))
                except BaseException as error:
                    errors.append(error)
                finally:
                    alive.discard(self.pid)
                    self.done.set()

            def poll(self):
                if self.done.is_set():
                    if self.pid not in transports:
                        loser_polled.set()
                    return 0
                return None

        def popen(argv, **kwargs):
            with construction:
                child = Child(41001 + len(children), Path(argv[-1]))
                children.append(child)
                alive.add(child.pid)
                child.thread.start()
                if len(children) == 2:
                    children_ready.set()
                return child

        def health(url, timeout=1):
            if not loser_polled.is_set():
                return None
            for transport in tuple(transports.values()):
                if url == f"http://127.0.0.1:{transport.server_address[1]}/health" and transport.serving.is_set():
                    return {"app": artifact_server.APP, "pid": transport.pid, "session_dir": str(sdir)}
            return None

        def start():
            try:
                results.append(artifact_server.start_server(sdir))
            except BaseException as error:
                errors.append(error)

        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp) / "agent-artifacts" / "sessions" / "tmux" / "context"
            sdir.mkdir(parents=True)
            with (
                mock.patch.dict(os.environ, {"XDG_CACHE_HOME": tmp}),
                mock.patch.object(artifact_server.os, "getpid", side_effect=getpid),
                mock.patch.object(artifact_server.os, "kill", side_effect=kill),
                mock.patch.object(artifact_server, "process_started_at", side_effect=lambda pid: f"start-{pid}"),
                mock.patch.object(
                    artifact_server,
                    "command_line_for_pid",
                    return_value=f"python3 {artifact_server.ENTRYPOINT} server --session-dir {sdir}",
                ),
                mock.patch.object(artifact_server, "ArtifactHTTPServer", HTTPTransport),
                mock.patch.object(artifact_server.subprocess, "Popen", side_effect=popen),
                mock.patch.object(artifact_server, "urlopen_json", side_effect=health),
            ):
                starters = [threading.Thread(target=start) for _ in range(2)]
                try:
                    for starter in starters:
                        starter.start()
                    self.assertTrue(children_ready.wait(5), "both callers must start before either contender publishes")
                    release_children.set()
                    for starter in starters:
                        starter.join(7)
                    self.assertFalse(any(starter.is_alive() for starter in starters))
                    self.assertEqual(len(transports), 1, "only one contender may become the serving owner")
                    self.assertEqual(errors, [])
                    transport = next(iter(transports.values()))
                    expected_url = f"http://127.0.0.1:{transport.server_address[1]}"
                    self.assertEqual(results, [expected_url, expected_url])
                    self.assertEqual(json.loads((sdir / "server.json").read_text())["pid"], transport.pid)
                finally:
                    release_children.set()
                    shutdown.set()
                    for starter in starters:
                        starter.join(8)
                    for child in children:
                        child.thread.join(8)

    def test_clean_serializes_poller_admission_and_stale_stop_preserves_the_new_owner(self):
        import argparse
        import signal

        real_pid = os.getpid()
        identities = {threading.get_ident(): 42001}
        alive = {42001, 42002}
        stopping = threading.Event()
        release_stop = threading.Event()
        admission_started = threading.Event()
        admission_done = threading.Event()
        signals = []
        errors = []

        def getpid():
            return identities.get(threading.get_ident(), real_pid)

        def kill(pid, sig):
            if pid not in alive:
                raise ProcessLookupError()
            if sig == signal.SIGTERM:
                signals.append(pid)
                alive.discard(pid)
                stopping.set()
                if not release_stop.wait(5):
                    raise TimeoutError("cleanup signal was not released")

        def clean():
            try:
                artifact_commands.clean(argparse.Namespace(all=True))
            except BaseException as error:
                errors.append(error)

        def register():
            identities[threading.get_ident()] = 42002
            admission_started.set()
            try:
                artifact_feedback.register_poller("demo", 30)
            except BaseException as error:
                errors.append(error)
            finally:
                admission_done.set()

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"XDG_CACHE_HOME": tmp, "TMUX": ""}),
            mock.patch.object(artifact_feedback.os, "getpid", side_effect=getpid),
            mock.patch.object(artifact_feedback.os, "kill", side_effect=kill),
            mock.patch.object(artifact_feedback, "process_started_at", side_effect=lambda pid: f"start-{pid}"),
            mock.patch.object(
                artifact_feedback,
                "command_line_for_pid",
                return_value=f"python3 {ARTIFACT_MODULE_DIR / 'main.py'} poll demo",
            ),
        ):
            artifact_feedback.register_poller("demo", 30)
            old_record = artifact_feedback.active_poller_record("demo")
            record_path = Path(old_record["path"])
            cleaner = threading.Thread(target=clean)
            replacement = threading.Thread(target=register)
            cleaner.start()
            try:
                self.assertTrue(stopping.wait(5))
                replacement.start()
                self.assertTrue(admission_started.wait(5))
                self.assertFalse(admission_done.wait(0.1), "admission must wait until cleanup has deleted the cache")
            finally:
                release_stop.set()
                cleaner.join(5)
                if replacement.ident is not None:
                    replacement.join(5)
            self.assertFalse(cleaner.is_alive() or replacement.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(signals, [42001])
            self.assertEqual(json.loads(record_path.read_text())["pid"], 42002)
            artifact_feedback.stop_poller_record(old_record)
            artifact_feedback.unregister_poller("demo")
            self.assertEqual(json.loads(record_path.read_text())["pid"], 42002)
            self.assertEqual(signals, [42001])

    def test_a_previous_server_finalizer_preserves_the_owner_admitted_after_clean(self):
        import argparse
        import signal

        real_pid = os.getpid()
        identities = {}
        alive = {43001, 43002}
        serving = {pid: threading.Event() for pid in alive}
        release = {pid: threading.Event() for pid in alive}
        errors = []
        signals = []

        def getpid():
            return identities.get(threading.get_ident(), real_pid)

        def kill(pid, sig):
            if pid not in alive:
                raise ProcessLookupError()
            if sig == signal.SIGTERM:
                signals.append(pid)

        class HTTPTransport:
            def __init__(self, address, handler):
                self.pid = getpid()
                self.server_address = ("127.0.0.1", 7100 + self.pid - 43000)

            def server_close(self):
                pass

            def serve_forever(self):
                serving[self.pid].set()
                if not release[self.pid].wait(8):
                    raise TimeoutError("server finalizer fixture was not released")

        def run(pid):
            identities[threading.get_ident()] = pid
            try:
                artifact_server.run_server(argparse.Namespace(session_dir=sdir))
            except BaseException as error:
                errors.append(error)
            finally:
                alive.discard(pid)

        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp) / "agent-artifacts" / "sessions" / "tmux" / "context"
            with (
                mock.patch.dict(os.environ, {"XDG_CACHE_HOME": tmp}),
                mock.patch.object(artifact_server.os, "getpid", side_effect=getpid),
                mock.patch.object(artifact_server.os, "kill", side_effect=kill),
                mock.patch.object(artifact_server, "process_started_at", side_effect=lambda pid: f"start-{pid}"),
                mock.patch.object(
                    artifact_server,
                    "command_line_for_pid",
                    return_value=f"python3 {artifact_server.ENTRYPOINT} server --session-dir {sdir}",
                ),
                mock.patch.object(artifact_server, "ArtifactHTTPServer", HTTPTransport),
            ):
                previous = threading.Thread(target=run, args=(43001,))
                replacement = threading.Thread(target=run, args=(43002,))
                previous.start()
                try:
                    self.assertTrue(serving[43001].wait(5))
                    artifact_commands.clean(argparse.Namespace(all=True))
                    self.assertEqual(signals, [43001])
                    self.assertFalse(sdir.exists())
                    replacement.start()
                    self.assertTrue(serving[43002].wait(5))
                    release[43001].set()
                    previous.join(5)
                    self.assertFalse(previous.is_alive())
                    self.assertTrue(
                        (sdir / "server.json").exists(), "previous finalizer deleted the replacement owner record"
                    )
                    self.assertEqual(json.loads((sdir / "server.json").read_text())["pid"], 43002)
                    self.assertTrue(replacement.is_alive())
                    self.assertEqual(errors, [])
                finally:
                    for event in release.values():
                        event.set()
                    previous.join(8)
                    if replacement.ident is not None:
                        replacement.join(8)


class TestArtifactServerAuth(unittest.TestCase):
    """WHEN a request reaches the local artifact server."""

    def setUp(self):
        import json as _json
        import subprocess as _sp
        import tempfile as _tf
        import time as _time

        self._json = _json
        tmp = _tf.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sdir = Path(tmp.name)
        self.proc = _sp.Popen(
            [sys.executable, str(ARTIFACT_MODULE_DIR / "main.py"), "server", "--session-dir", str(self.sdir)],
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            env={**os.environ, "XDG_CACHE_HOME": tmp.name},
        )
        self.addCleanup(self.proc.wait)
        self.addCleanup(self.proc.terminate)
        state_file = self.sdir / "server.json"
        deadline = _time.time() + 5
        while not state_file.exists() and _time.time() < deadline:
            _time.sleep(0.05)
        state = _json.loads(state_file.read_text())
        self.base = f"http://127.0.0.1:{state['port']}"
        self.token = state["token"]

    def request(self, path, token=None, body=None, host=None):
        import urllib.error
        import urllib.request

        headers = {"content-type": "text/plain"}
        if host is not None:
            headers["host"] = host
        if token is not None:
            headers["x-artifact-token"] = token
        data = None if body is None else self._json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    def test_feedback_without_token_is_refused(self):
        body = {"items": [{"prompt": "injected"}]}
        self.assertEqual(self.request("/api/feedback/live", body=body), 403)
        self.assertEqual(self.request("/api/feedback/live", token="guess", body=body), 403)
        self.assertFalse((self.sdir / "feedback" / "live.html.jsonl").exists())

    def test_feedback_with_token_is_queued(self):
        self.assertEqual(self.request("/api/feedback/live", token=self.token, body={"items": [{"prompt": "ok"}]}), 200)
        self.assertTrue((self.sdir / "feedback" / "live.html.jsonl").exists())

    def test_foreign_host_is_refused(self):
        rebound = "attacker.example:" + self.base.rsplit(":", 1)[1]
        self.assertEqual(self.request("/session/demo", host=rebound), 403)
        self.assertEqual(
            self.request("/api/feedback/live", token=self.token, body={"items": [{"prompt": "x"}]}, host=rebound), 403
        )
        self.assertEqual(self.request("/session/demo"), 200)
        self.assertFalse((self.sdir / "feedback" / "live.html.jsonl").exists())

    def test_live_overlay_script_requires_token(self):
        self.assertEqual(self.request("/live/live.js"), 403)
        self.assertEqual(self.request(f"/live/live.js?token={self.token}"), 200)


if __name__ == "__main__":
    unittest.main()
