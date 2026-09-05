#!/usr/bin/env python3
"""Focused tests for openrouter wrappers."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestOpenRouterWrappers(unittest.TestCase):
    """WHEN launching a harness through OpenRouter."""

    def setUp(self):
        self.wrapper_home_directory = tempfile.TemporaryDirectory()
        wrapper_home = Path(self.wrapper_home_directory.name)
        _install_openrouter_preset_stub(wrapper_home)
        self.wrapper_home_environment = mock.patch.dict(
            os.environ,
            {"HOME": str(wrapper_home)},
        )
        self.wrapper_home_environment.start()

    def tearDown(self):
        self.wrapper_home_environment.stop()
        self.wrapper_home_directory.cleanup()

    def _openrouter_route_fixture(self):
        home = Path(self.wrapper_home_directory.name)
        bindir = home / "bin"
        bindir.mkdir()
        capture = (
            f"#!{sys.executable}\nimport json,os,sys\n"
            "print(json.dumps({'env': dict(os.environ), 'argv': sys.argv[1:]}))\n"
        )
        local = home / ".local/share/cursor-agent-local/versions/fixture/cursor-agent-local"
        for path in (local, *(bindir / name for name in ("claude", "copilot", ",copilot", "codex"))):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(capture)
            path.chmod(0o755)
        calls = home / "preset-calls"
        helper = home / "lib/shared/openrouter_presets.py"
        helper.write_text(
            '#!/bin/sh\nif [ "$1" = "--context-window" ]; then echo 200000; exit; fi\n'
            'printf "%s\\n" "$1" >> "$PRESET_CALLS"\n'
        )
        env = {
            **os.environ,
            "HOME": str(home),
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "OPENROUTER_API_KEY": "fixture-key",
            "CURSOR_AGENT_LOCAL_VERSION": "fixture",
            "CODEX_WRAPPER_BIN": str(bindir / "codex"),
            "PRESET_CALLS": str(calls),
        }
        return calls, env

    def _assert_openrouter_roles(self, harness, observed, band_gate, shim, projection):
        # Independent category contract, also checked against the generated registry.
        wires = {
            "memory": "google/gemini-3.7-flash@preset/effort-high",
            "mechanical": "deepseek/deepseek-v4-flash@preset/effort-xhigh",
            "refute": "anthropic/claude-sonnet-4.6@preset/effort-xhigh",
        }
        default_wire = "openai/gpt-5.5@preset/effort-xhigh"
        gate_env = {**observed["env"], "AGENT_BAND_HARNESS": "claude_code" if harness == "claude" else harness}
        with mock.patch.dict(os.environ, gate_env, clear=True):
            # Mechanical has no current named binding; its alias remains a preserved input.
            aliases = {
                "opus": wires["memory"],
                "haiku": wires["mechanical"],
                "sonnet": wires["refute"],
                "fable": default_wire,
            }
            for alias, wire in aliases.items():
                base, effort = wire.split("@preset/effort-")
                pick = band_gate._format_pick({"model": f"openrouter/{base}:{effort}"}, "claude_code", "pi")
                self.assertEqual(pick.get("alias"), alias)
                if harness == "claude":
                    self.assertEqual(observed["env"][f"ANTHROPIC_DEFAULT_{alias.upper()}_MODEL"], wire)
            for role, pick in projection["harnesses"]["pi"]["agents"].items():
                expected = wires.get(pick["category"], default_wire)
                base, thinking = pick["model"].removeprefix("openrouter/").rsplit(":", 1)
                self.assertEqual(f"{base}@preset/effort-{thinking}", expected)
                gate_input = json.dumps(
                    {
                        "tool_name": "Agent",
                        "tool_input": {"subagent_type": role, "model": "unregistered-model", "prompt": "fixture"},
                    }
                )
                gate_output = io.StringIO()
                with (
                    mock.patch.object(sys, "stdin", io.StringIO(gate_input)),
                    mock.patch.object(sys, "stdout", gate_output),
                ):
                    self.assertEqual(band_gate.main(), 0)
                output = json.loads(gate_output.getvalue())
                updated = output.get(
                    "updated_input",
                    output.get("modifiedArgs", output.get("hookSpecificOutput", {}).get("updatedInput", {})),
                )
                model = updated.get("model")
                if harness == "claude":
                    self.assertIn(model, aliases, (role, output))
                    model = observed["env"][f"ANTHROPIC_DEFAULT_{model.upper()}_MODEL"]
                self.assertEqual(model, expected, (harness, role))
                if harness == "cursor":
                    allowed = observed["env"]["CURSOR_AGENT_ALLOWED_MODEL"]
                    self.assertIsNone(shim.enforce_allowed_model({"model": model}, allowed))
                    self.assertIsNotNone(shim.enforce_allowed_model({"model": "unregistered-model"}, allowed))

    def test_SHOULD_route_memory_and_prepare_each_required_effort_once(self):
        """WHEN a wrapper inherits Pi categories, every bound role reaches its wire model."""
        import importlib.util

        modules = []
        for name, path in (
            ("shim_contract", "home/exact_lib/exact_,cursor-agent-shim/shim.py"),
            ("band_contract", "home/exact_dot_agents/exact_hooks/executable_band_gate.py"),
        ):
            spec = importlib.util.spec_from_file_location(name, REPO / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules.append(module)
        shim, band_gate = modules
        band_gate.PROJECTION = REPO / "home/dot_config/ai/readonly_agent-bands.v1.json"
        projection = json.loads(band_gate.PROJECTION.read_text())
        calls, env = self._openrouter_route_fixture()
        for harness in ("claude", "codex", "copilot", "cursor"):
            for effort in ("none", "high", "xhigh", "max"):
                with self.subTest(harness=harness, effort=effort):
                    calls.write_text("")
                    result = subprocess.run(
                        [
                            modern_bash(),
                            str(REPO / f"home/exact_bin/executable_,{harness}-openrouter"),
                            *(["--no-shim"] if harness == "cursor" else []),
                            "--model",
                            "moonshotai/kimi-k3",
                            "--effort",
                            effort,
                            "-p",
                            "fixture",
                        ],
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    observed = json.loads(result.stdout)
                    self.assertCountEqual(calls.read_text().splitlines(), set((effort, "high", "xhigh")))
                    wire = f"moonshotai/kimi-k3@preset/effort-{effort}"
                    self.assertTrue(wire in observed["argv"] or wire in observed["env"].values())
                    self._assert_openrouter_roles(harness, observed, band_gate, shim, projection)

    def test_SHOULD_create_only_a_missing_preset_in_the_active_account(self):
        module = _load_openrouter_presets_module()
        existing_response = mock.MagicMock()
        existing_response.__enter__.return_value = io.BytesIO(b'{"data":{"slug":"effort-high"}}')
        missing_error = module.urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/presets/effort-max",
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"error":"not found"}'),
        )
        created_response = mock.MagicMock()
        created_response.__enter__.return_value = io.BytesIO(
            b'{"data":{"designated_version":{"config":{"reasoning":{"effort":"max"}}}}}'
        )

        with mock.patch.object(module.URL_OPENER, "open", return_value=existing_response) as urlopen:
            module.ensure_preset("high", "active-account-key")
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(urlopen.call_args.args[0].get_method(), "GET")

        with mock.patch.object(
            module.URL_OPENER,
            "open",
            side_effect=[missing_error, created_response],
        ) as urlopen:
            module.ensure_preset("max", "active-account-key")
        self.assertEqual([call.args[0].get_method() for call in urlopen.call_args_list], ["GET", "POST"])
        post_request = urlopen.call_args_list[1].args[0]
        self.assertEqual(json.loads(post_request.data), {"reasoning": {"effort": "max"}})
        self.assertEqual(post_request.get_header("Authorization"), "Bearer active-account-key")

        enriched_response = mock.MagicMock()
        enriched_response.__enter__.return_value = io.BytesIO(
            b'{"data":{"designated_version":{"config":{"reasoning":{"effort":"max"},"provider":{}}}}}'
        )
        with mock.patch.object(
            module.URL_OPENER,
            "open",
            side_effect=[missing_error, enriched_response],
        ):
            module.ensure_preset("max", "active-account-key")

        conflict_error = module.urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/presets/effort-max/chat/completions",
            409,
            "Conflict",
            {},
            io.BytesIO(b'{"error":"resource conflict"}'),
        )
        concurrently_created_response = mock.MagicMock()
        concurrently_created_response.__enter__.return_value = io.BytesIO(b'{"data":{"slug":"effort-max"}}')
        with mock.patch.object(
            module.URL_OPENER,
            "open",
            side_effect=[missing_error, conflict_error, concurrently_created_response],
        ) as urlopen:
            module.ensure_preset("max", "active-account-key")
        self.assertEqual(
            [call.args[0].get_method() for call in urlopen.call_args_list],
            ["GET", "POST", "GET"],
        )

    def test_SHOULD_fail_preset_preflight_when_required_state_cannot_be_confirmed(self):
        module = _load_openrouter_presets_module()

        lookup_error = module.urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/presets/effort-high",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":"invalid key"}'),
        )
        with mock.patch.object(module.URL_OPENER, "open", side_effect=lookup_error):
            with self.assertRaisesRegex(module.PresetError, "GET .* HTTP 401") as raised_error:
                module.ensure_preset("high", "active-account-key")
        self.assertNotIn("active-account-key", str(raised_error.exception))

        timeout_response = mock.MagicMock()
        timeout_response.__enter__.return_value.read.side_effect = TimeoutError("timed out")
        with mock.patch.object(module.URL_OPENER, "open", return_value=timeout_response):
            with self.assertRaisesRegex(module.PresetError, "response read failed"):
                module.ensure_preset("high", "active-account-key")

        malformed_lookup_response = mock.MagicMock()
        malformed_lookup_response.__enter__.return_value = io.BytesIO(b"not-json")
        with mock.patch.object(
            module.URL_OPENER,
            "open",
            return_value=malformed_lookup_response,
        ):
            with self.assertRaisesRegex(module.PresetError, "GET .* returned invalid JSON"):
                module.ensure_preset("high", "active-account-key")

        mismatched_lookup_response = mock.MagicMock()
        mismatched_lookup_response.__enter__.return_value = io.BytesIO(b'{"data":{"slug":"effort-low"}}')
        with mock.patch.object(
            module.URL_OPENER,
            "open",
            return_value=mismatched_lookup_response,
        ):
            with self.assertRaisesRegex(module.PresetError, "unexpected preset slug"):
                module.ensure_preset("high", "active-account-key")

        missing_error = module.urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/presets/effort-high",
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"error":"not found"}'),
        )
        creation_error = module.urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/presets/effort-high/chat/completions",
            500,
            "Internal Server Error",
            {},
            io.BytesIO(b'{"error":"failed"}'),
        )
        with mock.patch.object(
            module.URL_OPENER,
            "open",
            side_effect=[missing_error, creation_error],
        ):
            with self.assertRaisesRegex(module.PresetError, "POST .* HTTP 500"):
                module.ensure_preset("high", "active-account-key")

        mismatched_response = mock.MagicMock()
        mismatched_response.__enter__.return_value = io.BytesIO(
            b'{"data":{"designated_version":{"config":{"reasoning":{"effort":"low"}}}}}'
        )
        with mock.patch.object(
            module.URL_OPENER,
            "open",
            side_effect=[missing_error, mismatched_response],
        ):
            with self.assertRaisesRegex(module.PresetError, "unexpected reasoning effort"):
                module.ensure_preset("high", "active-account-key")

        malformed_response = mock.MagicMock()
        malformed_response.__enter__.return_value = io.BytesIO(b"not-json")
        with mock.patch.object(
            module.URL_OPENER,
            "open",
            side_effect=[missing_error, malformed_response],
        ):
            with self.assertRaisesRegex(module.PresetError, "returned invalid JSON"):
                module.ensure_preset("high", "active-account-key")

        unexpected_shape_response = mock.MagicMock()
        unexpected_shape_response.__enter__.return_value = io.BytesIO(b"[]")
        with mock.patch.object(
            module.URL_OPENER,
            "open",
            side_effect=[missing_error, unexpected_shape_response],
        ):
            with self.assertRaisesRegex(module.PresetError, "unexpected JSON shape"):
                module.ensure_preset("high", "active-account-key")

    def test_SHOULD_reject_redirects_without_forwarding_the_active_account_key(self):
        module = _load_openrouter_presets_module()
        received_authorization_headers = []

        class RedirectHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", target_url)
                self.end_headers()

            def log_message(self, *args):
                pass

        class CaptureHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                received_authorization_headers.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        capture_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), CaptureHandler)
        target_url = f"http://127.0.0.1:{capture_server.server_port}/captured"
        redirect_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        server_threads = [
            threading.Thread(target=server.serve_forever, daemon=True) for server in (capture_server, redirect_server)
        ]
        for server_thread in server_threads:
            server_thread.start()

        try:
            with mock.patch.object(
                module,
                "BASE_URL",
                f"http://127.0.0.1:{redirect_server.server_port}",
            ):
                with self.assertRaisesRegex(module.PresetError, "GET .* HTTP 302"):
                    module.ensure_preset("high", "active-account-key")
        finally:
            redirect_server.shutdown()
            capture_server.shutdown()
            redirect_server.server_close()
            capture_server.server_close()
            for server_thread in server_threads:
                server_thread.join()

        self.assertEqual(received_authorization_headers, [])

    def test_SHOULD_resolve_openrouter_context_windows_from_catalog(self):
        module = _load_openrouter_presets_module()

        def response(payload: dict):
            mocked = mock.MagicMock()
            mocked.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
            return mocked

        catalog = {
            "data": [
                {
                    "id": "openai/gpt-5.5",
                    "context_length": 1050000,
                    "pricing": {"overrides": [{"min_prompt_tokens": 272000}]},
                },
                {
                    "id": "stealth/ox-alpha",
                    "context_length": None,
                    "pricing": None,
                },
            ]
        }
        endpoints = {
            "data": {
                "id": "stealth/ox-alpha",
                "context_length": None,
                "endpoints": [{"provider_name": "Stealth", "context_length": 1048576}],
            }
        }

        with mock.patch.object(
            module.URL_OPENER,
            "open",
            side_effect=[response(catalog), response(catalog), response(catalog), response(endpoints)],
        ):
            self.assertEqual(module.resolve_context_window("openai/gpt-5.5", "short", "active-key"), 272000)
            self.assertEqual(module.resolve_context_window("openai/gpt-5.5", "long", "active-key"), 1050000)
            self.assertEqual(
                module.resolve_context_window("stealth/ox-alpha@preset/effort-max", "long", "active-key"),
                1048576,
            )

    def test_SHOULD_run_account_local_preset_preflight_in_every_wrapper(self):
        for relative in (
            "home/exact_bin/executable_,claude-openrouter",
            "home/exact_bin/executable_,codex-openrouter",
            "home/exact_bin/executable_,copilot-openrouter",
            "home/exact_bin/executable_,cursor-openrouter",
        ):
            with self.subTest(command=relative):
                source = (REPO / relative).read_text()
                self.assertIn(
                    'readonly OPENROUTER_PRESET_HELPER="$HOME/lib/shared/openrouter_presets.py"',
                    source,
                )
                self.assertIn('"$OPENROUTER_PRESET_HELPER" "$OPENROUTER_EFFORT"', source)
                self.assertIn("tr -d '[:space:]'", source)

    def test_SHOULD_clear_claude_api_credentials(self):
        source = (REPO / "home/exact_bin/executable_,claude-openrouter").read_text()
        assert 'export ANTHROPIC_API_KEY=""' in source
        assert 'export ANTHROPIC_AUTH_TOKEN="$api_key"' in source
        assert "unset ANTHROPIC_CUSTOM_HEADERS" in source
        assert "export CLAUDE_CODE_DISABLE_THINKING=1" in source
        assert 'export CLAUDE_CODE_EFFORT_LEVEL="$CLAUDE_EFFORT"' in source

    def test_SHOULD_map_claude_tiers_to_the_pi_openrouter_backend_schema(self):
        source = (REPO / "home/exact_bin/executable_,claude-openrouter").read_text()
        assert 'export ANTHROPIC_DEFAULT_OPUS_MODEL="$OPENROUTER_PI_MEMORY_WIRE_MODEL"' in source
        assert 'export ANTHROPIC_DEFAULT_SONNET_MODEL="$OPENROUTER_PI_SONNET_WIRE_MODEL"' in source
        assert 'export ANTHROPIC_DEFAULT_HAIKU_MODEL="$OPENROUTER_PI_DEEPSEEK_WIRE_MODEL"' in source
        assert 'export ANTHROPIC_DEFAULT_FABLE_MODEL="$OPENROUTER_PI_GPT55_WIRE_MODEL"' in source
        assert 'export CLAUDE_CODE_SUBAGENT_MODEL="$OPENROUTER_PI_GPT55_WIRE_MODEL"' in source
        assert 'export AGENT_BAND_SCHEMA_HARNESS="pi"' in source
        assert 'export AGENT_BAND_MODEL_FORMAT="openrouter-preset"' in source

    def test_SHOULD_mark_suffix_wrappers_with_their_backend_lane_schema(self):
        expectations = {
            "claude-openrouter": ("pi", "openrouter-preset"),
            "codex-openrouter": ("pi", "openrouter-preset"),
            "copilot-openrouter": ("pi", "openrouter-preset"),
            "cursor-openrouter": ("pi", "openrouter-preset"),
            "claude-copilot": ("copilot", None),
            "codex-copilot": ("copilot", None),
            "cursor-copilot": ("copilot", None),
            "claude-codex": ("codex", None),
            "copilot-codex": ("codex", None),
            "cursor-codex": ("codex", None),
        }
        for command, (schema, model_format) in expectations.items():
            with self.subTest(command=command):
                source = (REPO / f"home/exact_bin/executable_,{command}").read_text()
                assert "unset AGENT_BAND_MODEL_OVERRIDE AGENT_BAND_EFFORT_OVERRIDE" in source
                assert f'export AGENT_BAND_SCHEMA_HARNESS="{schema}"' in source
                if model_format is None:
                    assert "AGENT_BAND_MODEL_FORMAT" in source
                    assert f'export AGENT_BAND_MODEL_FORMAT="{model_format}"' not in source
                else:
                    assert f'export AGENT_BAND_MODEL_FORMAT="{model_format}"' in source

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
                if relative.endswith((",claude-openrouter", ",copilot-openrouter")):
                    assert 'OPENROUTER_CONTEXT="short"' in source
                assert "--no-thinking" in source
                assert 'OPENROUTER_EFFORT="minimal"' in source
                assert 'readonly OPENROUTER_WIRE_MODEL="$OPENROUTER_MODEL@preset/effort-$OPENROUTER_EFFORT"' in source

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
            "effort=max",
            "subagent=openai/gpt-5.5@preset/effort-xhigh",
            f"args=--model {OPENROUTER_WIRE_PIN} --effort max -p review",
        ]

    def test_SHOULD_pass_supported_openrouter_effort_to_claude_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            claude = bindir / "claude"
            claude.write_text(
                """#!/usr/bin/env bash
printf 'model=%s\\neffort=%s\\nargs=%s\\n' "$ANTHROPIC_MODEL" "$CLAUDE_CODE_EFFORT_LEVEL" "$*"
""",
                encoding="utf-8",
            )
            claude.chmod(0o755)
            cases = [
                (["--effort", "low"], "deepseek/deepseek-v4-flash-0731@preset/effort-low", "low"),
                (["--effort=xhigh"], "deepseek/deepseek-v4-flash-0731@preset/effort-xhigh", "xhigh"),
                (["--effort", "none"], "deepseek/deepseek-v4-flash-0731@preset/effort-none", "low"),
            ]
            for argv, expected_model, expected_client_effort in cases:
                with self.subTest(argv=argv):
                    result = subprocess.run(
                        [
                            modern_bash(),
                            str(REPO / "home/exact_bin/executable_,claude-openrouter"),
                            *argv,
                            "-p",
                            "review",
                        ],
                        capture_output=True,
                        text=True,
                        env={
                            **os.environ,
                            "PATH": f"{bindir}:{os.environ['PATH']}",
                            "OPENROUTER_API_KEY": "fixture-key",
                        },
                    )

                assert result.returncode == 0, result.stderr
                assert result.stdout.splitlines() == [
                    f"model={expected_model}",
                    f"effort={expected_client_effort}",
                    f"args=--model {expected_model} --effort {expected_client_effort} -p review",
                ]

    def test_SHOULD_hard_pin_codex_and_copilot_routes_over_environment_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            codex = bindir / "codex"
            codex.write_text(
                """#!/usr/bin/env bash
printf 'schema=%s\\nformat=%s\\nband-model=%s\\nband-effort=%s\\nargs=%s\\n' \
  "$AGENT_BAND_SCHEMA_HARNESS" "$AGENT_BAND_MODEL_FORMAT" \
  "${AGENT_BAND_MODEL_OVERRIDE-}" "${AGENT_BAND_EFFORT_OVERRIDE-}" "$*"
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
printf 'type=%s\\nmodel=%s\\nwire=%s\\nschema=%s\\nformat=%s\\nband-model=%s\\nband-effort=%s\\nargs=%s\\n' \
  "$COPILOT_PROVIDER_TYPE" "$COPILOT_MODEL" "$COPILOT_PROVIDER_WIRE_MODEL" \
  "$AGENT_BAND_SCHEMA_HARNESS" "$AGENT_BAND_MODEL_FORMAT" \
  "${AGENT_BAND_MODEL_OVERRIDE-}" "${AGENT_BAND_EFFORT_OVERRIDE-}" "$*"
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
        assert codex_result.stdout.splitlines()[:4] == [
            "schema=pi",
            "format=openrouter-preset",
            "band-model=",
            "band-effort=",
        ]
        assert f"--model {OPENROUTER_WIRE_PIN}" in codex_result.stdout
        # Effort rides the preset slug, not a Codex body field, so model_reasoning_effort is unset.
        assert "model_reasoning_effort" not in codex_result.stdout
        assert copilot_result.returncode == 0, copilot_result.stderr
        assert copilot_result.stdout.splitlines() == [
            "type=anthropic",
            f"model={OPENROUTER_PIN}",
            f"wire={OPENROUTER_WIRE_PIN}",
            "schema=pi",
            "format=openrouter-preset",
            "band-model=",
            "band-effort=",
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
printf 'base=%s\nkey=%s\nallowed=%s\nschema=%s\nformat=%s\nband-model=%s\nargs=%s\n' \\
  "$CURSOR_LOCAL_AGENT_BASE_URL" "$CURSOR_LOCAL_AGENT_API_KEY" "$CURSOR_AGENT_ALLOWED_MODEL" \\
  "$AGENT_BAND_SCHEMA_HARNESS" "$AGENT_BAND_MODEL_FORMAT" "${AGENT_BAND_MODEL_OVERRIDE-}" "$*"
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
            "allowed=deepseek/deepseek-v4-flash-0731@preset/effort-max,openai/gpt-5.5@preset/effort-xhigh,deepseek/deepseek-v4-flash@preset/effort-xhigh,anthropic/claude-sonnet-4.6@preset/effort-xhigh,google/gemini-3.7-flash@preset/effort-high",
            "schema=pi",
            "format=openrouter-preset",
            "band-model=",
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
            (["-p", "x"], "deepseek/deepseek-v4-flash-0731@preset/effort-max"),
            (
                ["--model", "deepseek/deepseek-v4-flash-0731", "--effort", "max"],
                "deepseek/deepseek-v4-flash-0731@preset/effort-max",
            ),
            (["--model", "moonshotai/kimi-k3", "--effort", "max"], "moonshotai/kimi-k3@preset/effort-max"),
            (
                ["--model", "openai/gpt-5.6-terra", "--effort", "minimal"],
                "openai/gpt-5.6-terra@preset/effort-minimal",
            ),
            (
                ["--effort", "none"],
                "deepseek/deepseek-v4-flash-0731@preset/effort-none",
            ),
            (
                ["--model", "openai/gpt-5.6-terra", "--effort", "none"],
                "openai/gpt-5.6-terra@preset/effort-none",
            ),
            (["--model", "qwen/qwen3.8-max", "--effort", "high"], "qwen/qwen3.8-max@preset/effort-high"),
            (["--model", "google/gemini-3.7-flash", "--effort", "high"], "google/gemini-3.7-flash@preset/effort-high"),
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
            (["-p", "x"], "deepseek/deepseek-v4-flash-0731@preset/effort-max"),
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

    def test_SHOULD_apply_context_tier_where_the_openrouter_consumer_supports_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            claude = bindir / "claude"
            claude.write_text(
                '#!/usr/bin/env bash\necho "model=$ANTHROPIC_MODEL"\n',
                encoding="utf-8",
            )
            claude.chmod(0o755)
            copilot_cli = bindir / "copilot"
            copilot_cli.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            copilot_cli.chmod(0o755)
            managed_copilot = bindir / ",copilot"
            managed_copilot.write_text(
                '#!/usr/bin/env bash\necho "prompt=$COPILOT_PROVIDER_MAX_PROMPT_TOKENS wire=$COPILOT_PROVIDER_WIRE_MODEL"\n',
                encoding="utf-8",
            )
            managed_copilot.chmod(0o755)

            cases = [
                (
                    "home/exact_bin/executable_,claude-openrouter",
                    ["--context", "short"],
                    "model=deepseek/deepseek-v4-flash-0731@preset/effort-max",
                ),
                (
                    "home/exact_bin/executable_,claude-openrouter",
                    ["--context", "long"],
                    "model=deepseek/deepseek-v4-flash-0731@preset/effort-max",
                ),
                (
                    "home/exact_bin/executable_,copilot-openrouter",
                    ["--context=short"],
                    "prompt=200000 wire=deepseek/deepseek-v4-flash-0731@preset/effort-max",
                ),
            ]
            for relative, argv, expected in cases:
                with self.subTest(command=relative):
                    result = subprocess.run(
                        [modern_bash(), str(REPO / relative), *argv],
                        capture_output=True,
                        text=True,
                        env={
                            **os.environ,
                            "PATH": f"{bindir}:{os.environ['PATH']}",
                            "OPENROUTER_API_KEY": "fixture-key",
                        },
                    )
                    assert result.returncode == 0, result.stderr
                    assert expected in result.stdout

    def test_SHOULD_reject_context_tier_when_openrouter_consumer_has_no_verified_knob(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            codex = bindir / "codex"
            codex.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            codex.chmod(0o755)
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

            cases = {
                "home/exact_bin/executable_,codex-openrouter": (
                    {"CODEX_WRAPPER_BIN": str(codex)},
                    "Codex 0.149.0 exposes no verified context-window override",
                ),
                "home/exact_bin/executable_,cursor-openrouter": (
                    {"HOME": str(home)},
                    "cursor-agent-local forwards context suffixes literally",
                ),
            }
            for relative, (extra_env, expected) in cases.items():
                with self.subTest(command=relative):
                    result = subprocess.run(
                        [modern_bash(), str(REPO / relative), "--context", "short"],
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
                    assert expected in result.stderr

    def test_SHOULD_allow_cursor_openrouter_models_with_shim_tool_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
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

            result = subprocess.run(
                [
                    modern_bash(),
                    str(REPO / "home/exact_bin/executable_,cursor-openrouter"),
                    "--model",
                    "stealth/ox-alpha",
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}:{os.environ['PATH']}",
                    "OPENROUTER_API_KEY": "fixture-key",
                },
            )

        assert result.returncode == 0, result.stderr
        assert "empty tool-mode responses" not in result.stderr

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
        # The guardrail env is exported before the shim branch and includes the Pi backend lanes.
        assert 'export CURSOR_AGENT_ALLOWED_MODEL="$OPENROUTER_WIRE_MODEL,' in source
        assert "$OPENROUTER_PI_GPT55_WIRE_MODEL" in source
        assert "$OPENROUTER_PI_DEEPSEEK_WIRE_MODEL" in source
        assert "$OPENROUTER_PI_SONNET_WIRE_MODEL" in source

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

    def test_SHOULD_strip_tools_for_ox_alpha_chat_completions(self):
        module = self._load_shim_module()

        payload = {
            "model": "stealth/ox-alpha@preset/effort-max",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": "Shell", "parameters": {"type": "object"}, "strict": True},
                }
            ],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        }
        rewritten = module.rewrite_chat_completions(payload)
        assert "tools" not in rewritten
        assert "tool_choice" not in rewritten
        assert "parallel_tool_calls" not in rewritten
        assert "tools" in payload

        ordinary = dict(payload, model="deepseek/deepseek-v4-flash-0731@preset/effort-max")
        ordinary_rewritten = module.rewrite_chat_completions(ordinary)
        assert "tools" in ordinary_rewritten
        assert "strict" not in ordinary_rewritten["tools"][0]["function"]

    def test_SHOULD_reject_chat_completions_whose_model_is_not_the_pinned_session_model(self):
        module = self._load_shim_module()

        allowed = "deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max"
        assert module.enforce_allowed_model({"model": allowed, "messages": []}, allowed) is None
        allowlist = f"{allowed},openai/gpt-5.5@preset/effort-xhigh"
        assert (
            module.enforce_allowed_model(
                {"model": "openai/gpt-5.5@preset/effort-xhigh", "messages": []},
                allowlist,
            )
            is None
        )

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
                assert "not in the pinned session allowlist" in error

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

    def test_SHOULD_retry_empty_tool_mode_response_without_tools(self):
        module = self._load_shim_module()

        upstream_payloads: list[dict] = []

        class _FallbackHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, _fmt, *_args):
                return

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0) or 0)
                upstream_payloads.append(json.loads(self.rfile.read(length)))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                if len(upstream_payloads) == 1:
                    body = b'data: {"choices":[{"delta":{"content":""},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
                else:
                    body = b'data: {"choices":[{"delta":{"content":"OK"},"finish_reason":null}]}\n\ndata: [DONE]\n\n'
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        fake_upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FallbackHandler)
        fake_upstream.daemon_threads = True
        upstream_port = fake_upstream.server_address[1]
        upstream_thread = threading.Thread(target=fake_upstream.serve_forever, daemon=True)
        upstream_thread.start()

        original_upstream = module.UPSTREAM
        original_allowed = module.ALLOWED_MODEL
        original_discovered = set(module.DISCOVERED_NO_TOOL_MODELS)
        module.UPSTREAM = f"http://127.0.0.1:{upstream_port}"
        module.API_KEY = "fixture-key"
        module.ALLOWED_MODEL = "future/model@preset/effort-max"
        module.DISCOVERED_NO_TOOL_MODELS.clear()

        shim_server = module.ShimServer(("127.0.0.1", 0), module.ShimHandler)
        shim_server.daemon_threads = True
        shim_port = shim_server.server_address[1]
        shim_thread = threading.Thread(target=shim_server.serve_forever, daemon=True)
        shim_thread.start()

        body = json.dumps(
            {
                "model": module.ALLOWED_MODEL,
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [{"type": "function", "function": {"name": "Shell", "parameters": {"type": "object"}}}],
                "tool_choice": "auto",
                "parallel_tool_calls": True,
                "stream": True,
            }
        ).encode()
        try:
            req = Request(
                f"http://127.0.0.1:{shim_port}/api/v1/chat/completions",
                data=body,
                headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
                method="POST",
            )
            with urlopen(req, timeout=5) as resp:
                downstream_body = resp.read()
            assert b'"content":"OK"' in downstream_body
            assert len(upstream_payloads) == 2
            assert "tools" in upstream_payloads[0]
            assert "tools" not in upstream_payloads[1]
            assert "tool_choice" not in upstream_payloads[1]
            assert "parallel_tool_calls" not in upstream_payloads[1]
            assert "future/model" in module.DISCOVERED_NO_TOOL_MODELS
        finally:
            module.UPSTREAM = original_upstream
            module.ALLOWED_MODEL = original_allowed
            module.DISCOVERED_NO_TOOL_MODELS.clear()
            module.DISCOVERED_NO_TOOL_MODELS.update(original_discovered)
            shim_server.shutdown()
            shim_server.server_close()
            fake_upstream.shutdown()
            fake_upstream.server_close()
            shim_thread.join(timeout=5)
            upstream_thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
