#!/usr/bin/env python3
"""Focused tests for the llama.cpp harness wrappers."""

from __future__ import annotations

import json
import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestLlamaCppWrappers(unittest.TestCase):
    """WHEN a harness wrapper launches against the local llama.cpp router."""

    def test_SHOULD_enter_the_shared_router_lifecycle_from_every_harness(self):
        for harness in ("claude", "codex", "opencode"):
            with self.subTest(harness=harness):
                wrapper = REPO / f"home/exact_bin/executable_,{harness}-llama-cpp"
                self.assertIn("exec ,llama-cpp run --", wrapper.read_text())

    def test_SHOULD_offer_router_ids_from_every_llama_cpp_harness_completion(self):
        cases = (
            ("ne", "nemotron-3.5"),
            ("qwen3.6", "qwen3.6-35b-a3b"),
            ("qwen3.6-35b-a3b-i", "qwen3.6-35b-a3b-instruct"),
        )
        for harness in ("claude", "codex", "opencode"):
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
                "settings.llama-cpp.qwen3.6.json",
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
                ("--model", "qwen3.6-35b-a3b", "-p", "review"),
                {},
                "settings.llama-cpp.qwen3.6.json",
                "--model qwen3.6-35b-a3b -p review",
            ),
            (
                ("--model=qwen3.6-35b-a3b-instruct",),
                {},
                "settings.llama-cpp.qwen3.6.json",
                "--model=qwen3.6-35b-a3b-instruct",
            ),
            (("-m", "qwen3.6-35b-a3b-instruct"), {}, "settings.llama-cpp.qwen3.6.json", "-m qwen3.6-35b-a3b-instruct"),
            (
                ("--", "--model", "qwen3.6-35b-a3b"),
                {},
                "settings.llama-cpp.json",
                "--model nemotron-3.5 -- --model qwen3.6-35b-a3b",
            ),
            (
                (),
                {"CLAUDE_LLAMA_CPP_MODEL": "qwen3.6-35b-a3b"},
                "settings.llama-cpp.qwen3.6.json",
                "--model qwen3.6-35b-a3b",
            ),
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
            ("--model", "qwen3.6-35b-a3b"),
            settings_override="custom-settings.json",
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "base=http://127.0.0.9:9090",
            "key=fixture-local-key",
            "compact=",
            f"args=--settings {home}/.claude/custom-settings.json --model qwen3.6-35b-a3b",
        ]

    def test_SHOULD_clear_an_inherited_global_compaction_window_for_model_scoped_settings(self):
        result, home = self.run_wrapper(
            ("--model", "qwen3.6-35b-a3b"),
            extra_env={"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "999999"},
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [
            "base=http://127.0.0.9:9090",
            "key=fixture-local-key",
            "compact=",
            f"args=--settings {home}/.claude/settings.llama-cpp.qwen3.6.json --model qwen3.6-35b-a3b",
        ]


if __name__ == "__main__":
    unittest.main()
