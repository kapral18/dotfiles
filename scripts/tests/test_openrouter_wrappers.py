#!/usr/bin/env python3
"""Focused tests for openrouter wrappers."""

from __future__ import annotations

import unittest
import urllib.error

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
            {
                "HOME": str(wrapper_home),
                "CODEX_HOME": str(wrapper_home / ".codex"),
            },
        )
        self.wrapper_home_environment.start()

    def tearDown(self):
        self.wrapper_home_environment.stop()
        self.wrapper_home_directory.cleanup()

    def test_SHOULD_keep_distinct_preset_selectors_in_the_native_codex_catalog(self):
        module = _load_openrouter_presets_module()
        wires = [
            "openai/gpt-test@preset/effort-high",
            "openai/gpt-test@preset/effort-xhigh",
            "google/gemini-test@preset/effort-low",
        ]
        with mock.patch.object(module, "resolve_budget", return_value=module.ModelBudget(200000, 32000, 168000)):
            catalog = module._codex_catalog("short", [*wires, wires[0]], "fixture-key")
        self.assertEqual([row["slug"] for row in catalog["models"]], wires)
        for row in catalog["models"]:
            self.assertEqual(row["context_window"], 168000)
            self.assertEqual(row["auto_compact_token_limit"], 151200)

    def _openrouter_route_fixture(self):
        home = Path(self.wrapper_home_directory.name)
        bindir = home / "bin"
        bindir.mkdir()
        capture = (
            f"#!{sys.executable}\nimport json,os,sys\n"
            "print(json.dumps({'env': dict(os.environ), 'argv': sys.argv[1:]}))\n"
        )
        for path in (bindir / name for name in ("claude", "codex")):
            path.write_text(capture)
            path.chmod(0o755)
        calls = home / "preset-calls"
        helper = home / "lib/shared/openrouter_presets.py"
        helper.write_text(
            '#!/bin/sh\nif [ "$1" = "--context-window" ]; then echo 200000; exit; fi\n'
            'if [ "$1" = "--session-budget-env" ]; then echo "CONTEXT_LIMIT=1048576"; echo "MAX_OUTPUT_TOKENS=131072"; echo "PROMPT_LIMIT=200000"; exit; fi\n'
            'if [ "$1" = "--codex-model-catalog" ]; then shift 2; '
            f'''exec "{sys.executable}" -c 'import json,sys;print(json.dumps({{"models":[{{"slug":m}} for m in sys.argv[1:]]}}))' "$@"; fi\n'''
            'printf "%s\\n" "$1" >> "$PRESET_CALLS"\n'
        )
        env = {
            **os.environ,
            "HOME": str(home),
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "OPENROUTER_API_KEY": "fixture-key",
            "CODEX_WRAPPER_BIN": str(bindir / "codex"),
            "PRESET_CALLS": str(calls),
        }
        return calls, env

    def test_SHOULD_route_only_the_root_model_and_prepare_its_effort_once(self):
        """WHEN a wrapper launches, only the selected model's preset is prepared and no agent definitions ride along."""
        calls, env = self._openrouter_route_fixture()
        for harness in ("claude", "codex"):
            for effort in ("none", "high", "xhigh", "max"):
                with self.subTest(harness=harness, effort=effort):
                    calls.write_text("")
                    result = subprocess.run(
                        [
                            modern_bash(),
                            str(REPO / f"home/exact_bin/executable_,{harness}-openrouter"),
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
                    self.assertEqual(calls.read_text().splitlines(), [effort])
                    wire = f"moonshotai/kimi-k3@preset/effort-{effort}"
                    self.assertIn(wire, observed["argv"])
                    self.assertNotIn("--agents", observed["argv"])

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
                    "max_completion_tokens": 128000,
                    "pricing": {"overrides": [{"min_prompt_tokens": 272000}]},
                },
                {
                    "id": "stealth/ox-alpha",
                    "context_length": 1048576,
                    "max_completion_tokens": 65536,
                    "pricing": None,
                },
            ]
        }
        endpoints = {
            "data": {
                "id": "stealth/ox-alpha",
                "context_length": None,
                "endpoints": [{"provider_name": "Stealth", "context_length": 1048576, "max_completion_tokens": 65536}],
            }
        }

        with mock.patch.object(
            module.URL_OPENER,
            "open",
            side_effect=[response(catalog), response(catalog), response(catalog), response(endpoints)],
        ):
            self.assertEqual(module.resolve_context_window("openai/gpt-5.5", "short", "active-key"), 271999)
            self.assertEqual(module.resolve_context_window("openai/gpt-5.5", "long", "active-key"), 922000)
            self.assertEqual(
                module.resolve_context_window("stealth/ox-alpha@preset/effort-max", "long", "active-key"),
                983040,
            )

    def test_SHOULD_keep_provider_context_and_output_limits_paired(self):
        module = _load_openrouter_presets_module()
        catalog_model = {
            "id": "vendor/model",
            "context_length": 1050000,
            "max_completion_tokens": 128000,
            "top_provider": {"context_length": 900000, "max_completion_tokens": 64000},
            "pricing": {"overrides": [{"min_prompt_tokens": 272000}]},
        }
        with mock.patch.object(module, "_model_catalog_entry", return_value=catalog_model):
            short = module.resolve_budget("vendor/model", "short", "active-key")
            long = module.resolve_budget("vendor/model", "long", "active-key")
        self.assertEqual((short.context_limit, short.max_output_tokens, short.prompt_limit), (900000, 64000, 271999))
        self.assertEqual((long.context_limit, long.max_output_tokens, long.prompt_limit), (900000, 64000, 836000))

        with (
            mock.patch.object(
                module, "_model_catalog_entry", return_value={"id": "vendor/missing", "context_length": 1000}
            ),
            mock.patch.object(module, "_endpoint_capacity", return_value=None),
        ):
            with self.assertRaisesRegex(module.PresetError, "max_completion_tokens"):
                module.resolve_budget("vendor/missing", "long", "active-key")

    def test_SHOULD_use_a_safe_minimum_for_session_wide_budgets(self):
        module = _load_openrouter_presets_module()
        budgets = {
            "root": module.ModelBudget(1000000, 128000, 872000),
            "lane": module.ModelBudget(200000, 64000, 136000),
        }
        with mock.patch.object(module, "resolve_budget", side_effect=lambda model, *_: budgets[model]):
            budget = module.resolve_session_budget(["root", "lane"], "long", "active-key")
        self.assertEqual((budget.context_limit, budget.max_output_tokens, budget.prompt_limit), (200000, 64000, 136000))

    def test_SHOULD_run_account_local_preset_preflight_in_every_wrapper(self):
        for relative in (
            "home/exact_bin/executable_,claude-openrouter",
            "home/exact_bin/executable_,codex-openrouter",
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

    def test_SHOULD_map_every_claude_alias_to_the_selected_wire(self):
        source = (REPO / "home/exact_bin/executable_,claude-openrouter").read_text()
        for alias in ("FABLE", "OPUS", "SONNET", "HAIKU"):
            assert f'export ANTHROPIC_DEFAULT_{alias}_MODEL="$OPENROUTER_WIRE_MODEL"' in source
        assert "unset CLAUDE_CODE_SUBAGENT_MODEL" in source

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

    def test_SHOULD_default_every_openrouter_launcher_to_glm_flash_high_long(self):
        # The route is defaulted rather than strict: model, effort, and context remain selectable via flags.
        for relative in (
            "home/exact_bin/executable_,claude-openrouter",
            "home/exact_bin/executable_,codex-openrouter",
        ):
            with self.subTest(command=relative):
                source = (REPO / relative).read_text()
                assert f'OPENROUTER_MODEL="{OPENROUTER_PIN}"' in source
                assert 'OPENROUTER_EFFORT="high"' in source
                assert 'OPENROUTER_CONTEXT="long"' in source
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
                    "id": "z-ai/glm-5.3-flash",
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
        self.assertEqual(rows["z-ai/glm-5.3-flash"], "max,high,low")

    def test_SHOULD_share_openrouter_catalog_across_chat_wrappers(self):
        # Live catalog omits none for GLM 5.3 Flash; completions still force-union none onto catalog efforts.
        source = (REPO / "home/dot_config/fish/functions/readonly___openrouter_catalog.fish").read_text()
        assert "not contains -- none $efforts" in source
        assert "set efforts none $efforts" in source
        assert 'test -z "$parts[2]"' in source
        assert "~/.cache/,openrouter/models.tsv" in source
        for relative in (
            "home/dot_config/fish/completions/readonly_,claude-openrouter.fish",
            "home/dot_config/fish/completions/readonly_,codex-openrouter.fish",
        ):
            with self.subTest(completion=relative):
                text = (REPO / relative).read_text()
                assert "functions/__openrouter_catalog.fish" in text
                assert "(__openrouter_catalog_models)" in text
                assert "(__openrouter_catalog_efforts)" in text

    def test_SHOULD_hard_pin_claude_route_over_environment_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            claude = bindir / "claude"
            claude.write_text(
                f"#!{sys.executable}\nimport os,json,sys\nprint(json.dumps({{'env':dict(os.environ),'args':sys.argv[1:]}}))\n",
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
        observed = json.loads(result.stdout)
        self.assertEqual(observed["env"]["ANTHROPIC_MODEL"], OPENROUTER_WIRE_PIN)
        self.assertEqual(observed["env"]["CLAUDE_CODE_EFFORT_LEVEL"], "high")
        self.assertNotIn("CLAUDE_CODE_SUBAGENT_MODEL", observed["env"])
        self.assertEqual(observed["args"], ["--model", OPENROUTER_WIRE_PIN, "--effort", "high", "-p", "review"])

    def test_SHOULD_pass_supported_openrouter_effort_to_claude_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            claude = bindir / "claude"
            claude.write_text(
                f"#!{sys.executable}\nimport os,json,sys\nprint(json.dumps({{'env':dict(os.environ),'args':sys.argv[1:]}}))\n",
                encoding="utf-8",
            )
            claude.chmod(0o755)
            cases = [
                (["--effort", "low"], "xiaomi/mimo-v2.6-pro@preset/effort-low", "low"),
                (["--effort=xhigh"], "xiaomi/mimo-v2.6-pro@preset/effort-xhigh", "xhigh"),
                (["--effort", "none"], "xiaomi/mimo-v2.6-pro@preset/effort-none", "low"),
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
                observed = json.loads(result.stdout)
                self.assertEqual(observed["env"]["ANTHROPIC_MODEL"], expected_model)
                self.assertEqual(observed["env"]["CLAUDE_CODE_EFFORT_LEVEL"], expected_client_effort)
                self.assertEqual(
                    observed["args"],
                    ["--model", expected_model, "--effort", expected_client_effort, "-p", "review"],
                )

    def test_SHOULD_hard_pin_codex_route_over_environment_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp)
            codex = bindir / "codex"
            codex.write_text(
                """#!/usr/bin/env bash
printf 'args=%s\\n' "$*"
""",
                encoding="utf-8",
            )
            codex.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{bindir}:{os.environ['PATH']}",
                "OPENROUTER_API_KEY": "fixture-key",
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

        assert codex_result.returncode == 0, codex_result.stderr
        assert f"--model {OPENROUTER_WIRE_PIN}" in codex_result.stdout
        # Effort rides the preset slug, not a Codex body field, so model_reasoning_effort is unset.
        assert "model_reasoning_effort" not in codex_result.stdout

    def test_SHOULD_compose_wire_model_from_model_and_effort_flags(self):
        # Model and effort are selectable; the wire id composes the matching preset slug.
        cases = [
            (["-p", "x"], "xiaomi/mimo-v2.6-pro@preset/effort-high"),
            (
                ["--model", "z-ai/glm-5.3-flash", "--effort", "max"],
                "z-ai/glm-5.3-flash@preset/effort-max",
            ),
            (["--model", "moonshotai/kimi-k3", "--effort", "max"], "moonshotai/kimi-k3@preset/effort-max"),
            (
                ["--model", "openai/gpt-5.6-terra", "--effort", "minimal"],
                "openai/gpt-5.6-terra@preset/effort-minimal",
            ),
            (
                ["--effort", "none"],
                "xiaomi/mimo-v2.6-pro@preset/effort-none",
            ),
            (
                ["--model", "openai/gpt-5.6-terra", "--effort", "none"],
                "openai/gpt-5.6-terra@preset/effort-none",
            ),
            (["--model", "qwen/qwen3.8-max", "--effort", "high"], "qwen/qwen3.8-max@preset/effort-high"),
            (["--model", "google/gemini-3.8-flash", "--effort", "low"], "google/gemini-3.8-flash@preset/effort-low"),
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

    def test_SHOULD_compose_wire_model_for_codex(self):
        # The same model/effort -> preset-slug composition runs in every wrapper; only the
        # leaf delivery differs.
        cases = [
            (["-p", "x"], "xiaomi/mimo-v2.6-pro@preset/effort-high"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            codex = bindir / "codex"
            codex.write_text('#!/usr/bin/env bash\necho "args=$*"\n', encoding="utf-8")
            codex.chmod(0o755)
            runners = {
                "home/exact_bin/executable_,codex-openrouter": {"CODEX_WRAPPER_BIN": str(codex)},
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

            cases = [
                (
                    "home/exact_bin/executable_,claude-openrouter",
                    ["--context", "short"],
                    "model=xiaomi/mimo-v2.6-pro@preset/effort-high",
                ),
                (
                    "home/exact_bin/executable_,claude-openrouter",
                    ["--context", "long"],
                    "model=xiaomi/mimo-v2.6-pro@preset/effort-high",
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

    def test_SHOULD_project_small_prompt_and_output_limits_to_claude(self):
        _, env = self._openrouter_route_fixture()
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"
        helper = Path(env["HOME"]) / "lib/shared/openrouter_presets.py"
        for output_limit in (8192, 32768):
            prompt_limit = 65536 - output_limit
            with self.subTest(output_limit=output_limit):
                helper.write_text(
                    '#!/bin/sh\nif [ "$1" = "--session-budget-env" ]; then\n'
                    f'echo "CONTEXT_LIMIT=65536"\necho "MAX_OUTPUT_TOKENS={output_limit}"\n'
                    f'echo "PROMPT_LIMIT={prompt_limit}"\nfi\n'
                )
                result = subprocess.run(
                    [modern_bash(), str(REPO / "home/exact_bin/executable_,claude-openrouter")],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                actual = json.loads(result.stdout)["env"]
                self.assertEqual(actual["CLAUDE_CODE_MAX_CONTEXT_TOKENS"], str(prompt_limit))
                self.assertEqual(actual["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], str(prompt_limit))
                self.assertEqual(actual["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], str(output_limit))

    def test_SHOULD_reject_empty_or_missing_model_and_effort_values(self):
        # Empty --model=/--effort= would compose a garbage wire id that only fails at the
        # provider; a trailing --model must exit 2, not crash on set -u.
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            for command in ("claude", "codex"):
                fake = bindir / command
                fake.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                fake.chmod(0o755)
            runners = {
                "home/exact_bin/executable_,claude-openrouter": {},
                "home/exact_bin/executable_,codex-openrouter": {"CODEX_WRAPPER_BIN": str(bindir / "codex")},
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
            for command in ("claude",):
                fake = bindir / command
                fake.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                fake.chmod(0o755)
            codex = bindir / "codex"
            codex.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            codex.chmod(0o755)
            cases = {
                "home/exact_bin/executable_,claude-openrouter": ({}, ["--fallback-model", "other"]),
                "home/exact_bin/executable_,codex-openrouter": ({"CODEX_WRAPPER_BIN": str(codex)}, ["-c", "model=x"]),
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
        ):
            with self.subTest(command=relative):
                source = (REPO / relative).read_text()
                assert "pass show openrouter/api/token" in source
                assert "Error: set OPENROUTER_API_KEY or pass entry openrouter/api/token." in source


if __name__ == "__main__":
    unittest.main()
