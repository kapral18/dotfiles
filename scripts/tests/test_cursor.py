#!/usr/bin/env python3
"""Focused tests for cursor."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestCursorWrapper(unittest.TestCase):
    """WHEN Cursor launches with OAuth MCP preflight."""

    def test_seeds_current_workspace_from_live_cache_without_browser(self):
        global_token = "opaque-global-workspace-token"
        with (
            _liveness_server({global_token: 200}) as (url, _handler),
            tempfile.TemporaryDirectory() as tmp,
        ):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "workspace"
            config = home / ".cursor/mcp.json"
            global_cache = home / ".cursor/projects/global/mcp-auth.json"
            workspace_cache = home / ".cursor/projects/workspace/mcp-auth.json"
            ledger = home / ".cache/mcp-token/opaque-refresh.json"
            log = root / "cursor-agent.log"
            for path in (
                bindir,
                workspace,
                config.parent,
                global_cache.parent,
                workspace_cache.parent,
                ledger.parent,
            ):
                path.mkdir(parents=True, exist_ok=True)
            (workspace_cache.parent / ".workspace-trusted").write_text(json.dumps({"workspacePath": str(workspace)}))
            config.write_text(json.dumps({"mcpServers": {"slack": {"url": url, "auth": {"CLIENT_ID": "fixture"}}}}))
            global_cache.write_text(
                json.dumps(
                    {
                        "slack": {
                            "tokens": {
                                "access_token": global_token,
                                "expires_in": 3600,
                                "refresh_token": "refresh-chain",
                            }
                        }
                    }
                )
            )
            ledger.write_text(
                json.dumps(
                    {
                        "slack": {
                            "source": str(global_cache),
                            "token_sha256": hashlib.sha256(global_token.encode()).hexdigest(),
                            "refreshed_at": time.time(),
                        }
                    }
                )
            )

            token_helper = bindir / ",mcp-token"
            token_helper.write_text(
                f'#!/usr/bin/env bash\nexec {shlex.quote(sys.executable)} {shlex.quote(str(MCP_TOKEN_COMMAND))} "$@"\n'
            )
            token_helper.chmod(0o755)
            real_cursor = bindir / "cursor-agent"
            real_cursor.write_text(
                "#!/usr/bin/env bash\n"
                f"printf '%s\\n' \"$*\" >> {shlex.quote(str(log))}\n"
                'if [[ "${1:-}" == "mcp" ]]; then\n'
                "  exit 0\n"
                "fi\n"
                f"if [[ -s {shlex.quote(str(workspace_cache))} ]]; then\n"
                "  echo 'SESSION_MCP_STATUS=ready'\n"
                "else\n"
                "  echo 'SESSION_MCP_STATUS=requires_authentication'\n"
                "fi\n"
            )
            real_cursor.chmod(0o755)

            result = subprocess.run(
                [
                    modern_bash(),
                    str(REPO / "home/exact_bin/executable_,cursor"),
                    "--force",
                    "--approve-mcps",
                ],
                capture_output=True,
                text=True,
                cwd=workspace,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "CURSOR_AGENT_REAL_BIN": str(real_cursor),
                },
            )
            calls = log.read_text().splitlines()
            seeded = json.loads(workspace_cache.read_text()) if workspace_cache.exists() else {}
            donor = json.loads(global_cache.read_text())

        assert result.returncode == 0, result.stderr
        assert "SESSION_MCP_STATUS=ready" in result.stdout
        assert not any("mcp login" in call for call in calls), "a live cached chain must seed, not pop a browser"
        assert seeded.get("slack", {}).get("tokens", {}).get("access_token") == global_token
        assert seeded["slack"]["tokens"].get("refresh_token") == "refresh-chain"
        assert donor["slack"]["tokens"]["access_token"] == global_token, "the donor cache must stay untouched"

    def test_preflights_cursor_oauth_and_auth_client_id_servers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            config = home / ".cursor/mcp.json"
            config.parent.mkdir(parents=True)
            bindir.mkdir()
            config.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "scsi-main": {"url": "https://scsi.invalid/mcp", "oauth": {"clientId": "fixture"}},
                            "slack": {"url": "https://slack.invalid/mcp", "auth": {"CLIENT_ID": "fixture"}},
                        }
                    }
                )
            )
            token_log = root / "mcp-token.log"
            token_helper = bindir / ",mcp-token"
            token_helper.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> \"$MCP_TOKEN_LOG\"\nprintf 'fixture-token\\n'\n"
            )
            token_helper.chmod(0o755)
            real_cursor = bindir / "cursor-agent"
            real_cursor.write_text("#!/usr/bin/env bash\necho REAL_CURSOR_STARTED\n")
            real_cursor.chmod(0o755)

            result = subprocess.run(
                [modern_bash(), str(REPO / "home/exact_bin/executable_,cursor")],
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                    "CURSOR_AGENT_REAL_BIN": str(real_cursor),
                    "MCP_TOKEN_LOG": str(token_log),
                },
            )
            calls = token_log.read_text().splitlines()

        assert result.returncode == 0, result.stderr
        assert "REAL_CURSOR_STARTED" in result.stdout
        assert calls == [
            "scsi-main --login --quiet --no-proactive-rotation",
            "slack --login --quiet --no-proactive-rotation",
        ]


if __name__ == "__main__":
    unittest.main()
