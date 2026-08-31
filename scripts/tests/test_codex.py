#!/usr/bin/env python3
"""Focused tests for codex."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


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

    def test_local_models_inject_catalog_metadata(self):
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
            for model in ("nemotron-3.5", "qwen3.5-9b", "qwen3.8-27b", "qwen3.8-27b-instruct"):
                with self.subTest(model=model):
                    result = subprocess.run(
                        [sys.executable, str(CODEX_COMMAND), "--model", model, "exec", "hi"],
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

    def test_resolves_codex_from_path_when_real_bin_unset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bindir = root / "bin"
            home.mkdir()
            bindir.mkdir()
            real_codex = bindir / "codex"
            real_codex.write_text("#!/usr/bin/env bash\necho REAL_CODEX_FROM_PATH\n")
            real_codex.chmod(0o755)
            clean_env = {k: v for k, v in os.environ.items() if k != "CODEX_REAL_BIN"}
            result = subprocess.run(
                [sys.executable, str(CODEX_COMMAND), "exec", "hi"],
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env={
                    **clean_env,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                },
            )
            assert result.returncode == 0, result.stderr
            assert "REAL_CODEX_FROM_PATH" in result.stdout

    def test_fails_when_codex_binary_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bindir = root / "bin"
            home.mkdir()
            bindir.mkdir()
            clean_env = {k: v for k, v in os.environ.items() if k != "CODEX_REAL_BIN"}
            result = subprocess.run(
                [sys.executable, str(CODEX_COMMAND), "exec", "hi"],
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env={
                    **clean_env,
                    "HOME": str(home),
                    "PATH": "/usr/bin:/bin",
                },
            )
            assert result.returncode == 127
            assert "Error: real Codex binary not found at codex." in result.stderr


if __name__ == "__main__":
    unittest.main()
