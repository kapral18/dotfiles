#!/usr/bin/env python3
"""Tests for generate_mcp_configs.py and the Copilot MCP wrapper."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import (
    FIXTURES,
    REPO,
    modern_bash,
    run_script,
)


class TestGenerateMcpConfigs(unittest.TestCase):
    """WHEN generating MCP JSON configs."""

    def test_personal_golden(self):
        actual = run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "claude"])
        expected = (FIXTURES / "golden_mcp_personal.json").read_text()
        assert json.loads(actual) == json.loads(expected)

    def test_work_golden(self):
        actual = run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "true", "claude"])
        expected = (FIXTURES / "golden_mcp_work.json").read_text()
        assert json.loads(actual) == json.loads(expected)

    def test_copilot_stdio_server_gets_local_type_and_tools(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "copilot"])
        )
        public = actual["mcpServers"]["public-tool"]
        assert public["type"] == "local"
        assert public["command"] == "docker"
        assert public["tools"] == ["*"]

    def test_copilot_http_oauth_uses_oauthclientid_and_redirectport(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "copilot"])
        )
        http = actual["mcpServers"]["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert http["tools"] == ["*"]
        assert http["oauthClientId"] == "copilot-client-id"
        assert http["auth"] == {"redirectPort": 4242}
        assert http["oauthScopes"] == ["openid", "email"]
        # Copilot config never carries the raw nested oauth block or a secret.
        assert "oauth" not in http
        assert "oauthPublicClient" not in http

    def test_copilot_http_header_auth_emits_authorization_header(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "copilot"])
        )
        header = actual["mcpServers"]["header-tool"]
        assert header["type"] == "http"
        assert header["url"] == "https://mcp.header.com/mcp"
        assert header["tools"] == ["*"]
        # headerAuth bypasses the OAuth flow: emit the resolved Authorization
        # header and none of the oauth keys.
        assert header["headers"] == {"Authorization": "Bearer resolved-token"}
        assert "oauthClientId" not in header
        assert "oauthScopes" not in header
        assert "auth" not in header

    def test_copilot_http_header_auth_failure_emits_refresh_placeholder(self):
        actual = json.loads(
            run_script(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "copilot"])
        )
        header = actual["mcpServers"]["stale-header-tool"]
        assert header["type"] == "http"
        assert header["url"] == "https://mcp.stale-header.com/mcp"
        assert header["headers"] == {"Authorization": "Bearer __MCP_TOKEN_REFRESH_REQUIRED__"}
        assert "oauthClientId" not in header
        assert "oauthScopes" not in header
        assert "auth" not in header


class TestCopilotWrapper(unittest.TestCase):
    """WHEN launching Copilot through the managed wrapper."""

    PLACEHOLDER = "Bearer __MCP_TOKEN_REFRESH_REQUIRED__"

    @dataclass(frozen=True)
    class WrapperResult:
        process: subprocess.CompletedProcess[str]
        config_mode: int
        config_dir_mode: int

    def _run_wrapper(
        self,
        *,
        token_helper_exit: int,
        generated_authorization: str,
        generator_exit: int = 0,
    ) -> WrapperResult:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            source = root / "source/home"
            scripts = root / "source/scripts"
            bindir = root / "bin"
            (home / ".copilot").mkdir(parents=True)
            (source / ".chezmoidata").mkdir(parents=True)
            scripts.mkdir(parents=True)
            bindir.mkdir()
            (home / ".copilot/mcp-config.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "slack": {
                                "type": "http",
                                "url": "https://mcp.slack.com/mcp",
                                "headers": {"Authorization": self.PLACEHOLDER},
                            }
                        }
                    }
                )
            )
            (source / ".chezmoidata/mcp_servers.yaml").write_text("mcp_servers: []\n")
            generated_doc = {
                "mcpServers": {
                    "slack": {
                        "type": "http",
                        "url": "https://mcp.slack.com/mcp",
                        "tools": ["*"],
                        "headers": {"Authorization": generated_authorization},
                    }
                }
            }
            if generator_exit == 0:
                generator_body = f"print({json.dumps(json.dumps(generated_doc, indent=2))})\n"
            else:
                generator_body = f"import sys\nsys.exit({generator_exit})\n"
            (scripts / "generate_mcp_configs.py").write_text("#!/usr/bin/env python3\n" + generator_body)
            (bindir / ",mcp-token").write_text(f"#!/usr/bin/env bash\nexit {token_helper_exit}\n")
            (bindir / ",mcp-token").chmod(0o755)
            (bindir / "chezmoi").write_text(
                "#!/usr/bin/env bash\n"
                'if [[ "$1" == data ]]; then\n'
                f"  printf '%s\\n' {shlex.quote(json.dumps({'chezmoi': {'sourceDir': str(source)}, 'isWork': True}))}\n"
                "else\n"
                "  exit 1\n"
                "fi\n"
            )
            (bindir / "chezmoi").chmod(0o755)
            real_copilot = bindir / "copilot-real"
            real_copilot.write_text("#!/usr/bin/env bash\necho REAL_COPILOT_STARTED\n")
            real_copilot.chmod(0o755)

            result = subprocess.run(
                [modern_bash(), str(REPO / "home/exact_bin/executable_,copilot")],
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "COPILOT_REAL_BIN": str(real_copilot),
                },
            )

            config_mode = (home / ".copilot/mcp-config.json").stat().st_mode & 0o777
            config_dir_mode = (home / ".copilot").stat().st_mode & 0o777

        return self.WrapperResult(result, config_mode, config_dir_mode)

    def test_stale_header_token_refresh_failure_blocks_launch(self):
        result = self._run_wrapper(token_helper_exit=1, generated_authorization=self.PLACEHOLDER)
        assert result.process.returncode == 1
        assert "REAL_COPILOT_STARTED" not in result.process.stdout
        assert "could not refresh MCP token(s): slack" in result.process.stderr

    def test_placeholder_after_rebake_blocks_launch(self):
        result = self._run_wrapper(token_helper_exit=0, generated_authorization=self.PLACEHOLDER)
        assert result.process.returncode == 1
        assert "REAL_COPILOT_STARTED" not in result.process.stdout
        assert "MCP token refresh placeholder remains for: slack" in result.process.stderr

    def test_rebake_failure_blocks_launch(self):
        result = self._run_wrapper(
            token_helper_exit=0,
            generated_authorization="Bearer fresh-token",
            generator_exit=7,
        )
        assert result.process.returncode == 1
        assert "REAL_COPILOT_STARTED" not in result.process.stdout
        assert "could not re-bake fresh MCP tokens" in result.process.stderr

    def test_rebake_writes_token_config_with_private_permissions(self):
        result = self._run_wrapper(token_helper_exit=0, generated_authorization="Bearer fresh-token")
        assert result.process.returncode == 0
        assert "REAL_COPILOT_STARTED" in result.process.stdout
        assert result.config_dir_mode == 0o700
        assert result.config_mode == 0o600


if __name__ == "__main__":
    unittest.main()
