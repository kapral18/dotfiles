#!/usr/bin/env python3
"""Focused tests for cursor llama cpp."""

from __future__ import annotations

import http.server
import json
import shutil
import threading
import unittest
import urllib.error
from urllib.request import Request, urlopen

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestCursorLlamaCppWrapper(unittest.TestCase):
    """WHEN Cursor launches against the local llama.cpp router."""

    def test_SHOULD_deliver_a_stream_event_before_upstream_completion(self):
        import importlib

        proxy_dir = str(REPO / "home/exact_lib/exact_,cursor-agent-shim")
        with mock.patch.object(sys, "path", [proxy_dir, *sys.path]):
            proxy = importlib.import_module("llama_cpp_proxy")
        observed = threading.Event()
        sent_before_completion = []

        class StreamingHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(b"data: first\n\n")
                self.wfile.flush()
                sent_before_completion.append(observed.wait(3))
                self.wfile.write(b"data: done\n\n")

        upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), StreamingHandler)
        server = proxy.LlamaProxyServer(("127.0.0.1", 0), f"http://127.0.0.1:{upstream.server_port}", {})
        threads = [threading.Thread(target=item.serve_forever, daemon=True) for item in (upstream, server)]
        for thread in threads:
            thread.start()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/v1/chat/completions", data=b"{}")
            with urlopen(request, timeout=5) as response:
                self.assertEqual(response.readline(), b"data: first\n")
                observed.set()
                self.assertIn(b"data: done", response.read())
            self.assertEqual(sent_before_completion, [True])
        finally:
            observed.set()
            for item in (server, upstream):
                item.shutdown()
                item.server_close()
            for thread in threads:
                thread.join()

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
            shim_dir = home / "lib" / ",cursor-agent-shim"
            shim_dir.mkdir(parents=True)
            for name in ("shim.py", "llama_cpp_proxy.py"):
                shutil.copy(REPO / "home/exact_lib/exact_,cursor-agent-shim" / name, shim_dir / name)
            catalog = home / ".codex" / "llama-cpp-model-catalog.json"
            catalog.parent.mkdir()
            catalog.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "slug": "nemotron-3.5",
                                "context_window": 262_144,
                                "auto_compact_token_limit": 200_000,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

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
        lines = result.stdout.splitlines()
        assert lines[0].startswith("base=http://127.0.0.1:")
        assert lines[0].endswith("/v1")
        assert lines[1:] == [
            "key=fixture-local-key",
            "band-model=nemotron-3.5",
            "args=--model nemotron-3.5 -p review",
        ]
        with self.assertRaises(urllib.error.URLError):
            urlopen(lines[0].removeprefix("base=") + "/models", timeout=0.1)

    def test_SHOULD_serve_selected_catalog_budget_and_transparently_forward_through_the_lease(self):
        wrapper = REPO / "home/exact_bin/executable_,cursor-llama-cpp"
        seen: dict[str, object] = {}

        class Upstream(http.server.BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_POST(self):
                seen["path"] = self.path
                seen["authorization"] = self.headers.get("Authorization")
                seen["body"] = self.rfile.read(int(self.headers["Content-Length"]))
                body = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                home = root / "home"
                bindir = root / "bin"
                bindir.mkdir()
                version = "2026.08.11-test"
                local_dir = home / ".local/share/cursor-agent-local/versions" / version
                local_dir.mkdir(parents=True)
                shim_dir = home / "lib" / ",cursor-agent-shim"
                shim_dir.mkdir(parents=True)
                for name in ("shim.py", "llama_cpp_proxy.py"):
                    shutil.copy(REPO / "home/exact_lib/exact_,cursor-agent-shim" / name, shim_dir / name)
                catalog = home / ".codex" / "llama-cpp-model-catalog.json"
                catalog.parent.mkdir()
                catalog.write_text(
                    json.dumps(
                        {
                            "models": [
                                {
                                    "slug": "qwen3.8-27b",
                                    "context_window": 131_072,
                                    "auto_compact_token_limit": 100_000,
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
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
                    """#!/usr/bin/env python3
import json
import os
from urllib.request import Request, urlopen

base = os.environ["CURSOR_LOCAL_AGENT_BASE_URL"]
with urlopen(base + "/models", timeout=5) as response:
    print(json.dumps(json.load(response), sort_keys=True))
request = Request(
    base + "/chat/completions",
    data=b'{"model":"qwen3.8-27b","messages":[]}',
    headers={"Authorization": "Bearer fixture-local-key", "Content-Type": "application/json"},
    method="POST",
)
with urlopen(request, timeout=5) as response:
    print(response.read().decode())
""",
                    encoding="utf-8",
                )
                local.chmod(0o755)

                result = subprocess.run(
                    [modern_bash(), str(wrapper), "--model", "qwen3.8-27b"],
                    capture_output=True,
                    text=True,
                    env={
                        **os.environ,
                        "HOME": str(home),
                        "PATH": f"{bindir}:{os.environ['PATH']}",
                        "LLAMA_CPP_HOST": "127.0.0.1",
                        "LLAMA_CPP_PORT": str(upstream.server_port),
                        "LLAMA_CPP_API_KEY": "fixture-local-key",
                    },
                )
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=5)

        assert result.returncode == 0, result.stderr
        metadata, response = result.stdout.splitlines()
        assert json.loads(metadata) == {
            "data": [
                {
                    "api_types": ["openai_chat"],
                    "capabilities": {
                        "context_length": 99_072,
                        "input_modalities": ["text"],
                        "max_output_tokens": 32_000,
                        "output_modalities": ["text"],
                        "supports_reasoning": False,
                        "supports_streaming": True,
                        "supports_tool_use": True,
                        "supports_vision": False,
                    },
                    "id": "qwen3.8-27b",
                }
            ]
        }
        assert response == '{"ok":true}'
        assert seen == {
            "path": "/v1/chat/completions",
            "authorization": "Bearer fixture-local-key",
            "body": b'{"model":"qwen3.8-27b","messages":[]}',
        }

    def test_SHOULD_enter_the_shared_router_lifecycle_from_every_harness(self):
        for harness in ("claude", "codex", "cursor", "opencode"):
            with self.subTest(harness=harness):
                wrapper = REPO / f"home/exact_bin/executable_,{harness}-llama-cpp"
                self.assertIn("exec ,llama-cpp run --", wrapper.read_text())

    def test_SHOULD_offer_router_ids_from_every_llama_cpp_harness_completion(self):
        cases = (
            ("ne", "nemotron-3.5"),
            ("qwen3.5", "qwen3.5-9b"),
            ("qwen3.8", "qwen3.8-27b"),
            ("qwen3.8-27b-i", "qwen3.8-27b-instruct"),
        )
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


class TestClaudeLlamaCppWrapper(unittest.TestCase):
    """WHEN Claude Code launches against the local llama.cpp router."""

    def run_wrapper(self, argv, *, extra_env=None, settings_override=None):
        wrapper = REPO / "home/exact_bin/executable_,claude-llama-cpp"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            claude_dir = home / ".claude"
            bindir = root / "bin"
            claude_dir.mkdir(parents=True)
            bindir.mkdir()
            for name in (
                "settings.llama-cpp.json",
                "settings.llama-cpp.qwen3.8.json",
                "custom-settings.json",
            ):
                (claude_dir / name).write_text("{}\n", encoding="utf-8")

            claude = bindir / "claude"
            claude.write_text(
                """#!/usr/bin/env bash
printf 'base=%s\nkey=%s\ncompact=%s\nargs=%s\n' "$ANTHROPIC_BASE_URL" "$ANTHROPIC_API_KEY" "${CLAUDE_CODE_AUTO_COMPACT_WINDOW-}" "$*"
""",
                encoding="utf-8",
            )
            claude.chmod(0o755)
            lifecycle = bindir / ",llama-cpp"
            lifecycle.write_text(
                '#!/usr/bin/env bash\n[[ "$1" == run && "$2" == -- ]] || exit 2\nshift 2\nexec "$@"\n',
                encoding="utf-8",
            )
            lifecycle.chmod(0o755)

            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}:{os.environ['PATH']}",
                "LLAMA_CPP_HOST": "127.0.0.9",
                "LLAMA_CPP_PORT": "9090",
                "LLAMA_CPP_API_KEY": "fixture-local-key",
            }
            if settings_override:
                env["CLAUDE_LLAMA_CPP_SETTINGS"] = str(claude_dir / settings_override)
            if extra_env:
                env.update(extra_env)
            result = subprocess.run(
                [modern_bash(), str(wrapper), *argv],
                capture_output=True,
                text=True,
                env=env,
            )
            return result, home

    def test_SHOULD_select_settings_for_the_effective_local_model(self):
        cases = (
            ((), {}, "settings.llama-cpp.json", "--model nemotron-3.5"),
            (
                ("--model", "qwen3.8-27b", "-p", "review"),
                {},
                "settings.llama-cpp.qwen3.8.json",
                "--model qwen3.8-27b -p review",
            ),
            (("--model=qwen3.8-27b-instruct",), {}, "settings.llama-cpp.qwen3.8.json", "--model=qwen3.8-27b-instruct"),
            (("-m", "qwen3.8-27b-instruct"), {}, "settings.llama-cpp.qwen3.8.json", "-m qwen3.8-27b-instruct"),
            (("-m", "qwen3.5-9b"), {}, "settings.llama-cpp.json", "-m qwen3.5-9b"),
            (
                ("--", "--model", "qwen3.8-27b"),
                {},
                "settings.llama-cpp.json",
                "--model nemotron-3.5 -- --model qwen3.8-27b",
            ),
            ((), {"CLAUDE_LLAMA_CPP_MODEL": "qwen3.8-27b"}, "settings.llama-cpp.qwen3.8.json", "--model qwen3.8-27b"),
        )
        for argv, extra_env, settings_name, forwarded in cases:
            with self.subTest(argv=argv, env=extra_env):
                result, home = self.run_wrapper(argv, extra_env=extra_env)

                assert result.returncode == 0, result.stderr
                assert result.stdout.splitlines() == [
                    "base=http://127.0.0.9:9090",
                    "key=fixture-local-key",
                    "compact=",
                    f"args=--settings {home}/.claude/{settings_name} {forwarded}",
                ]

    def test_SHOULD_respect_an_explicit_settings_override(self):
        result, home = self.run_wrapper(
            ("--model", "qwen3.8-27b"),
            settings_override="custom-settings.json",
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "base=http://127.0.0.9:9090",
            "key=fixture-local-key",
            "compact=",
            f"args=--settings {home}/.claude/custom-settings.json --model qwen3.8-27b",
        ]

    def test_SHOULD_clear_an_inherited_global_compaction_window_for_model_scoped_settings(self):
        result, home = self.run_wrapper(
            ("--model", "qwen3.8-27b"),
            extra_env={"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "999999"},
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "base=http://127.0.0.9:9090",
            "key=fixture-local-key",
            "compact=",
            f"args=--settings {home}/.claude/settings.llama-cpp.qwen3.8.json --model qwen3.8-27b",
        ]


if __name__ == "__main__":
    unittest.main()
