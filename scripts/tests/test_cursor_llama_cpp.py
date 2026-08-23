#!/usr/bin/env python3
"""Focused tests for cursor llama cpp."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


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


if __name__ == "__main__":
    unittest.main()
