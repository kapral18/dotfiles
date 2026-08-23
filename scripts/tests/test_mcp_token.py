#!/usr/bin/env python3
"""Focused tests for mcp token."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestMcpTokenCommand(unittest.TestCase):
    """WHEN selecting cached MCP OAuth tokens."""

    def _jwt(self, exp: int) -> str:
        def encode(value: dict[str, object]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'exp': exp})}.sig"

    def _write_cache(self, home: Path, access_token: str, *, server: str = "scsi-main") -> Path:
        cache = home / ".cursor/projects/p/mcp-auth.json"
        cache.parent.mkdir(parents=True)
        cache.write_text(
            json.dumps(
                {
                    server: {
                        "tokens": {
                            "access_token": access_token,
                            "expires_in": 3600,
                            "token_type": "Bearer",
                        }
                    }
                }
            )
        )
        os.utime(cache, None)
        return cache

    def test_jwt_expiry_overrides_fresh_cache_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self._write_cache(home, self._jwt(int(time.time()) + 60))
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "scsi-main"],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home)},
            )

        assert result.returncode == 1
        assert "no valid scsi-main token" in result.stderr

    def test_jwt_token_with_sufficient_expiry_is_selected(self):
        token = self._jwt(int(time.time()) + 900)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self._write_cache(home, token)
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "scsi-main", "--json"],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home)},
            )

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["token"] == token
        assert payload["seconds_left"] > 300

    def test_login_force_refreshes_opaque_tokens_without_trusting_cache_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            bindir = root / "bin"
            bindir.mkdir()
            cache = self._write_cache(home, "opaque-slack-token", server="slack")
            (bindir / "cursor-agent").write_text(
                "#!/usr/bin/env bash\n"
                'if [ "$1 $2" = "mcp login" ]; then\n'
                f"  touch {shlex.quote(str(cache))}\n"
                "fi\n"
                "exit 0\n"
            )
            (bindir / "cursor-agent").chmod(0o755)
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "slack", "--login"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                },
            )

        assert result.returncode == 0, result.stderr
        assert "running cursor-agent mcp login slack" in result.stderr
        assert result.stdout.strip() == "opaque-slack-token"

    def test_plain_read_does_not_trust_opaque_cache_mtime_without_login_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self._write_cache(home, "opaque-slack-token", server="slack")
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "slack"],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home)},
            )

        assert result.returncode == 1
        assert "no valid slack token" in result.stderr

    def test_login_without_cursor_agent_reports_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            result = subprocess.run(
                [sys.executable, str(MCP_TOKEN_COMMAND), "scsi-main", "--login"],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home), "PATH": str(bindir)},
            )

        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert "cursor-agent not found" in result.stderr


class TestMcpTokenWorkspaceCache(unittest.TestCase):
    """WHEN resolving Cursor's current-workspace OAuth cache locally."""

    def test_trusted_workspace_metadata_matches_resolved_paths(self):
        mod = _load_mcp_token_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "home/.cursor/projects"
            project = projects / "p"
            workspace = root / "workspace"
            logical_workspace = root / "logical-workspace"
            project.mkdir(parents=True)
            workspace.mkdir()
            logical_workspace.symlink_to(workspace)
            (project / ".workspace-trusted").write_text(json.dumps({"workspacePath": str(logical_workspace)}))
            with mock.patch.object(mod, "CURSOR_CACHE_GLOB", str(projects / "*/mcp-auth.json")):
                path = mod._cursor_workspace_cache_path(str(workspace))

        assert path == str(project / "mcp-auth.json")

    def test_deterministic_slug_fallback_matches_cursor_project_paths(self):
        mod = _load_mcp_token_module()
        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp) / "home/.cursor/projects"
            with mock.patch.object(mod, "CURSOR_CACHE_GLOB", str(projects / "*/mcp-auth.json")):
                path = mod._cursor_workspace_cache_path("/Users/example/work/a_b")

        assert path == str(projects / "Users-example-work-a-b/mcp-auth.json")


class TestMcpTokenLoginLiveness(unittest.TestCase):
    """WHEN ``,mcp-token <server> --login`` validates opaque-token liveness.

    Opaque tokens (e.g. Slack) can be revoked while the local ledger still pins
    them as nominally fresh. ``--login`` must probe the ledger-selected token
    against the server URL from the generated ``~/.cursor/mcp.json`` and recover
    a live cached alternative or run cursor login, instead of returning a dead
    token. These are real-seam tests: a local HTTP endpoint classifies tokens,
    an isolated ``HOME`` holds the caches/ledger/config, and a stub cursor-agent
    stands in for the browser flow. No network mocks assert the command's own
    helpers.
    """

    def _sha(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _write_cache(self, home: Path, name: str, server: str, token: str, *, age: float = 0.0) -> None:
        cache = home / ".cursor/projects" / name / "mcp-auth.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({server: {"tokens": {"access_token": token, "expires_in": 3600}}}))
        if age:
            when = time.time() - age
            os.utime(cache, (when, when))

    def _write_mcp_json(self, home: Path, server: str, url: str | None) -> None:
        cfg = home / ".cursor/mcp.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, object] = {}
        if url is not None:
            entry["url"] = url
        cfg.write_text(json.dumps({"mcpServers": {server: entry}}))

    def _write_ledger(self, home: Path, server: str, token: str, source: str) -> None:
        state_dir = home / ".cache/mcp-token"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "opaque-refresh.json").write_text(
            json.dumps({server: {"source": source, "token_sha256": self._sha(token), "refreshed_at": time.time()}})
        )

    def _read_ledger(self, home: Path, server: str) -> dict[str, object]:
        try:
            with open(home / ".cache/mcp-token/opaque-refresh.json") as f:
                return json.load(f).get(server, {})
        except (OSError, ValueError):
            return {}

    def _stub_cursor_agent(self, bindir: Path, home: Path, server: str, *, writes_token: str | None) -> Path:
        marker = home / "cursor-agent-ran"
        lines = ["#!/usr/bin/env bash", f"touch {shlex.quote(str(marker))}"]
        if writes_token is not None:
            cache = home / ".cursor/projects/login/mcp-auth.json"
            payload = json.dumps({server: {"tokens": {"access_token": writes_token, "expires_in": 3600}}})
            lines += [
                f"mkdir -p {shlex.quote(str(cache.parent))}",
                f"cat > {shlex.quote(str(cache))} <<'EOF'\n{payload}\nEOF",
            ]
        lines.append("exit 0")
        agent = bindir / "cursor-agent"
        agent.write_text("\n".join(lines) + "\n")
        agent.chmod(0o755)
        return marker

    def _run(self, home: Path, bindir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MCP_TOKEN_COMMAND), *args],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )

    def _jwt(self, exp: int) -> str:
        def encode(value: dict[str, object]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'exp': exp})}.sig"

    def test_revoked_ledger_token_selects_live_cached_alternative_and_repoints_ledger(self):
        revoked = "opaque-revoked-ledger"
        live = "opaque-live-alternative"
        with _liveness_server({revoked: 401, live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "old", "slack", revoked, age=100)
            self._write_cache(home, "new", "slack", live, age=10)
            self._write_ledger(home, "slack", revoked, str(home / ".cursor/projects/old/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()
            ledger_sha = self._read_ledger(home, "slack").get("token_sha256")

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == live
        assert not cursor_ran, "cursor-agent must not run when a live cached token exists"
        assert ledger_sha == self._sha(live)
        assert revoked not in result.stderr and live not in result.stderr

    def test_live_ledger_token_skips_login(self):
        live = "opaque-live-ledger"
        with _liveness_server({live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", live)
            self._write_ledger(home, "slack", live, str(home / ".cursor/projects/p/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()
            hits = list(handler.hits)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == live
        assert not cursor_ran
        assert hits == [live], "exactly the ledger token should be probed"

    def test_server_error_retains_nominal_ledger_candidate_without_promoting_alternative(self):
        nominal = "opaque-nominal-5xx"
        other = "opaque-other-live"
        with _liveness_server({nominal: 500, other: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "old", "slack", nominal, age=100)
            self._write_cache(home, "new", "slack", other, age=10)
            self._write_ledger(home, "slack", nominal, str(home / ".cursor/projects/old/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()
            ledger_sha = self._read_ledger(home, "slack").get("token_sha256")

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == nominal, "unknown liveness must preserve the nominal ledger token"
        assert not cursor_ran
        assert ledger_sha == self._sha(nominal)

    def test_network_error_retains_nominal_ledger_candidate(self):
        nominal = "opaque-nominal-neterr"
        # Reserve then release a port so the config URL points at a closed socket.
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        dead_port = probe.getsockname()[1]
        probe.close()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", f"http://127.0.0.1:{dead_port}/mcp")
            self._write_cache(home, "p", "slack", nominal)
            self._write_ledger(home, "slack", nominal, str(home / ".cursor/projects/p/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == nominal
        assert not cursor_ran

    def test_all_revoked_triggers_cursor_login_and_accepts_new_live_token(self):
        revoked = "opaque-all-revoked"
        fresh = "opaque-fresh-from-login"
        with _liveness_server({revoked: 401, fresh: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", revoked, age=100)
            self._write_ledger(home, "slack", revoked, str(home / ".cursor/projects/p/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=fresh)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()
            ledger_sha = self._read_ledger(home, "slack").get("token_sha256")

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh
        assert cursor_ran, "cursor-agent login must run when every cached token is revoked"
        assert ledger_sha == self._sha(fresh)

    def test_cursor_login_writing_still_revoked_token_is_not_success(self):
        revoked = "opaque-revoked-a"
        still_revoked = "opaque-revoked-b"
        with (
            _liveness_server({revoked: 401, still_revoked: 401}) as (url, handler),
            tempfile.TemporaryDirectory() as tmp,
        ):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", revoked, age=100)
            self._write_ledger(home, "slack", revoked, str(home / ".cursor/projects/p/mcp-auth.json"))
            self._stub_cursor_agent(bindir, home, "slack", writes_token=still_revoked)
            result = self._run(home, bindir, ["slack", "--login"])

        assert result.returncode == 1, "cursor exit 0 with a still-revoked token must not count as success"
        assert result.stdout.strip() == ""
        assert "did not yield a live token" in result.stderr
        assert revoked not in result.stderr and still_revoked not in result.stderr

    def test_force_invokes_login_even_when_ledger_token_is_live(self):
        live = "opaque-live-but-forced"
        fresh = "opaque-forced-fresh"
        with _liveness_server({live: 200, fresh: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", live)
            self._write_ledger(home, "slack", live, str(home / ".cursor/projects/p/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=fresh)
            result = self._run(home, bindir, ["slack", "--login", "--force", "--quiet"])
            cursor_ran = marker.exists()

        assert result.returncode == 0, result.stderr
        assert cursor_ran, "--force must always run the browser login"
        assert result.stdout.strip() == fresh

    def test_jwt_login_short_circuit_makes_no_liveness_probe(self):
        token = self._jwt(int(time.time()) + 1200)
        with _liveness_server({}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "scsi-main", url)
            self._write_cache(home, "p", "scsi-main", token)
            marker = self._stub_cursor_agent(bindir, home, "scsi-main", writes_token=None)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            cursor_ran = marker.exists()
            hits = list(handler.hits)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == token
        assert not cursor_ran
        assert hits == [], "a fresh JWT must short-circuit without a liveness probe"

    def test_plain_read_makes_no_liveness_probe(self):
        live = "opaque-live-plain"
        with _liveness_server({live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", live)
            self._write_ledger(home, "slack", live, str(home / ".cursor/projects/p/mcp-auth.json"))
            result = self._run(home, bindir, ["slack"])
            hits = list(handler.hits)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == live
        assert hits == [], "plain reads must stay local with no network probe"

    def test_login_never_leaks_token_or_response_body_on_stderr(self):
        revoked = "opaque-leak-check-revoked"
        live = "opaque-leak-check-live"
        with _liveness_server({revoked: 401, live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "old", "slack", revoked, age=100)
            self._write_cache(home, "new", "slack", live, age=10)
            self._write_ledger(home, "slack", revoked, str(home / ".cursor/projects/old/mcp-auth.json"))
            self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            # Not --quiet: any status text streams to stderr, mimicking wrappers.
            result = self._run(home, bindir, ["slack", "--login"])

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == live
        assert revoked not in result.stderr
        assert live not in result.stderr
        assert "serverInfo" not in result.stderr

    def test_login_probe_does_not_follow_redirect_or_leak_bearer_to_other_origin(self):
        # A 3xx from the probe URL must be UNKNOWN: the bearer must never be
        # resent to the redirect target, whose 200 would otherwise read LIVE.
        nominal = "opaque-redirect-nominal"
        with _redirecting_endpoint(302) as (url, sink), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "p", "slack", nominal)
            self._write_ledger(home, "slack", nominal, str(home / ".cursor/projects/p/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet"])
            cursor_ran = marker.exists()
            sink_hits = list(sink.hits)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == nominal, "an unfollowed 3xx is UNKNOWN and must preserve the nominal token"
        assert sink_hits == [], f"probe must not follow the redirect to another origin; sink saw {sink_hits}"
        assert not cursor_ran, "unknown liveness must not force a browser login"
        assert nominal not in result.stderr

    def test_force_login_writing_revoked_token_does_not_adopt_preexisting_live_cache(self):
        # --force browser login that yields a revoked token is a failure; a live
        # token that predates this login must not rescue it.
        old_live = "opaque-old-live-preexisting"
        new_revoked = "opaque-new-revoked-from-login"
        with (
            _liveness_server({old_live: 200, new_revoked: 401}) as (url, handler),
            tempfile.TemporaryDirectory() as tmp,
        ):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "old", "slack", old_live, age=100)
            self._write_ledger(home, "slack", old_live, str(home / ".cursor/projects/old/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=new_revoked)
            result = self._run(home, bindir, ["slack", "--login", "--force", "--quiet"])
            cursor_ran = marker.exists()
            ledger_sha = self._read_ledger(home, "slack").get("token_sha256")

        assert result.returncode == 1, "a failed browser login must not be rescued by a pre-login live cache"
        assert result.stdout.strip() == "", "no token may be printed when browser login failed"
        assert old_live not in result.stdout
        assert cursor_ran
        assert ledger_sha == self._sha(old_live), "failed login must not repoint the ledger"

    def test_force_login_writing_no_token_fails_even_with_live_cache(self):
        # cursor login that writes/touches no cache produced nothing this attempt;
        # a pre-existing live cache must not make that count as success.
        old_live = "opaque-old-live-nowrite"
        with _liveness_server({old_live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "old", "slack", old_live, age=100)
            self._write_ledger(home, "slack", old_live, str(home / ".cursor/projects/old/mcp-auth.json"))
            marker = self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--force", "--quiet"])
            cursor_ran = marker.exists()

        assert result.returncode == 1, "login that writes/touches no cache is a failure even with a live cache"
        assert result.stdout.strip() == ""
        assert cursor_ran

    def test_adopted_cached_alternative_reports_conservative_verification_lease(self):
        # A provider-verified cached alternative gets a short verification lease,
        # not the provider's full nominal lifetime.
        revoked = "opaque-nominal-revoked-lease"
        old_live = "opaque-old-live-alt-lease"
        with _liveness_server({revoked: 401, old_live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            self._write_cache(home, "n", "slack", revoked, age=0)
            # An alternative already ~3500s into its nominal 3600s life.
            self._write_cache(home, "old", "slack", old_live, age=3500)
            self._write_ledger(home, "slack", revoked, str(home / ".cursor/projects/n/mcp-auth.json"))
            self._stub_cursor_agent(bindir, home, "slack", writes_token=None)
            result = self._run(home, bindir, ["slack", "--login", "--quiet", "--json"])

        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["token"] == old_live, "the live cached alternative must be adopted"
        seconds_left = payload["seconds_left"]
        mod = _load_mcp_token_module()
        assert mod.EXPIRY_SKEW_SECONDS < seconds_left <= mod.VERIFIED_ADOPTION_TTL_SECONDS, (
            "adopted alternative must report a conservative verification lease "
            f"(> {mod.EXPIRY_SKEW_SECONDS}, <= {mod.VERIFIED_ADOPTION_TTL_SECONDS}), got {seconds_left}"
        )


class TestMcpTokenSilentRotation(unittest.TestCase):
    """WHEN ``--login`` rotates a short or stale token via cursor's refresh grant.

    cursor silently executes the provider's ``refresh_token`` grant whenever a
    stored access token stops working, so ``--login`` invalidates the cached
    access token and runs a targeted ``cursor-agent mcp list-tools <server>``
    in the cache's resolvable workspace instead of popping a browser. These are
    real-seam tests: an isolated ``HOME`` holds caches/ledger/config and a stub
    cursor-agent records its argv/cwd and plays the provider's rotation.
    """

    def _jwt(self, exp: int) -> str:
        def encode(value: dict[str, object]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'exp': exp})}.sig"

    def _sha(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _write_rotatable_cache(
        self,
        home: Path,
        name: str,
        server: str,
        token: str,
        *,
        refresh_token: str | None = "refresh-chain",
        workspace: Path | None = None,
    ) -> Path:
        project = home / ".cursor/projects" / name
        project.mkdir(parents=True, exist_ok=True)
        tokens: dict[str, object] = {"access_token": token, "expires_in": 3600}
        if refresh_token is not None:
            tokens["refresh_token"] = refresh_token
        cache = project / "mcp-auth.json"
        cache.write_text(json.dumps({server: {"tokens": tokens}}))
        if workspace is not None:
            workspace.mkdir(parents=True, exist_ok=True)
            (project / ".workspace-trusted").write_text(json.dumps({"workspacePath": str(workspace)}))
        return cache

    def _write_mcp_json(self, home: Path, server: str, url: str | None) -> None:
        cfg = home / ".cursor/mcp.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, object] = {}
        if url is not None:
            entry["url"] = url
        cfg.write_text(json.dumps({"mcpServers": {server: entry}}))

    def _write_ledger(self, home: Path, server: str, token: str, source: str) -> None:
        state_dir = home / ".cache/mcp-token"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "opaque-refresh.json").write_text(
            json.dumps({server: {"source": source, "token_sha256": self._sha(token), "refreshed_at": time.time()}})
        )

    def _read_ledger(self, home: Path, server: str) -> dict[str, object]:
        try:
            with open(home / ".cache/mcp-token/opaque-refresh.json") as f:
                return json.load(f).get(server, {})
        except (OSError, ValueError):
            return {}

    def _stub_rotating_cursor_agent(
        self,
        bindir: Path,
        home: Path,
        cache: Path,
        server: str,
        *,
        rotates_to: str | None,
    ) -> Path:
        """Stub cursor-agent: logs ``cwd argv`` per call; ``mcp list-tools`` plays the refresh grant."""
        log = home / "cursor-agent.log"
        lines = ["#!/usr/bin/env bash", f'echo "$PWD $*" >> {shlex.quote(str(log))}']
        if rotates_to is not None:
            payload = json.dumps(
                {server: {"tokens": {"access_token": rotates_to, "refresh_token": "rotated-chain", "expires_in": 3600}}}
            )
            lines += [
                'if [ "$1 $2" = "mcp list-tools" ]; then',
                f"cat > {shlex.quote(str(cache))} <<'EOF'\n{payload}\nEOF",
                "fi",
            ]
        lines.append("exit 0")
        agent = bindir / "cursor-agent"
        agent.write_text("\n".join(lines) + "\n")
        agent.chmod(0o755)
        return log

    def _run(
        self,
        home: Path,
        bindir: Path,
        args: list[str],
        *,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MCP_TOKEN_COMMAND), *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )

    def test_SHOULD_bound_cursor_server_approval(self):
        mod = _load_mcp_token_module()
        with mock.patch.object(
            mod.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["cursor-agent", "mcp", "enable"], 1),
        ) as run:
            approved = mod._enable_cursor_server("scsi-main", "/tmp")

        assert approved is False
        assert run.call_args.kwargs["timeout"] == mod.ROTATE_TIMEOUT_SECONDS

    def test_short_jwt_rotates_silently_in_trusted_workspace_without_browser(self):
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        fresh = self._jwt(int(time.time()) + 3600)
        with _liveness_server({}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "scsi-main", url)
            cache = self._write_rotatable_cache(home, "p", "scsi-main", short, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=fresh)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            calls = log.read_text().splitlines() if log.exists() else []
            hits = list(handler.hits)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh, "the rotated token must be selected"
        assert len(calls) == 2, calls
        assert calls[0].endswith(" mcp enable scsi-main"), calls
        cwd_str, sep, invoked = calls[1].partition(" mcp ")
        assert sep and invoked == "list-tools scsi-main", calls
        assert Path(cwd_str).resolve() == workspace.resolve(), "rotation must run in the cache's trusted workspace"
        assert hits == [], "JWT rotation must not probe the server"

    def test_mint_workspace_forces_rotation_cwd_when_user_config_is_bridge(self):
        """WHEN user mcp.json is a bridge, rotate/login must use the mint OAuth cwd."""
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            workspace.mkdir()
            mint = home / ".cache/mcp-token/oauth-mint"
            mint_mcp = mint / ".cursor/mcp.json"
            mint_mcp.parent.mkdir(parents=True)
            mint_mcp.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "scsi-main": {
                                "url": "https://semantic-code-search.example/mcp",
                                "oauth": {"clientId": "mint-client"},
                            }
                        }
                    }
                )
            )
            (home / ".cursor").mkdir(parents=True)
            (home / ".cursor/mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "scsi-main": {
                                "command": ",mcp-token",
                                "args": [
                                    "scsi-main",
                                    "--bridge",
                                    "--url",
                                    "https://semantic-code-search.example/mcp",
                                ],
                            }
                        }
                    }
                )
            )
            donor = self._write_rotatable_cache(home, "donor", "scsi-main", short, workspace=workspace)
            mint_slug = re.sub(r"[^A-Za-z0-9]+", "-", str(mint.resolve())).strip("-")
            mint_cache = home / ".cursor/projects" / mint_slug / "mcp-auth.json"
            log = self._stub_rotating_cursor_agent(bindir, home, mint_cache, "scsi-main", rotates_to=fresh)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"], cwd=workspace)
            calls = log.read_text().splitlines() if log.exists() else []
            donor_token = json.loads(donor.read_text())["scsi-main"]["tokens"]["access_token"]

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh
        assert len(calls) == 2, calls
        for call, expected in zip(calls, ("enable scsi-main", "list-tools scsi-main")):
            cwd_str, sep, invoked = call.partition(" mcp ")
            assert sep and invoked == expected, calls
            assert Path(cwd_str).resolve() == mint.resolve(), calls
        assert donor_token == short, "donor cache must not be the rotation target when mint exists"

    def test_expired_jwt_with_refresh_is_not_workspace_ready(self):
        mod = _load_mcp_token_module()
        expired = self._jwt(int(time.time()) - 60)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, workspace = root / "home", root / "ws"
            home.mkdir()
            workspace.mkdir()
            env_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            try:
                mod.CURSOR_CACHE_GLOB = str(home / ".cursor/projects/*/mcp-auth.json")
                cache = home / ".cursor/projects" / re.sub(r"[^A-Za-z0-9]+", "-", str(workspace.resolve())).strip("-")
                cache.mkdir(parents=True)
                (cache / "mcp-auth.json").write_text(
                    json.dumps(
                        {
                            "scsi-main": {
                                "tokens": {
                                    "access_token": expired,
                                    "refresh_token": "still-here",
                                    "expires_in": 3600,
                                }
                            }
                        }
                    )
                )
                status = None
                cwd = os.getcwd()
                try:
                    os.chdir(workspace)
                    status = mod._cursor_workspace_auth_status("scsi-main")
                finally:
                    os.chdir(cwd)
            finally:
                os.environ["HOME"] = env_home

        assert status == mod.WORKSPACE_REQUIRES_AUTH

    def test_expired_untrusted_cache_rotates_through_the_current_workspace(self):
        expired = self._jwt(int(time.time()) - 100)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "current-workspace"
            home.mkdir()
            bindir.mkdir()
            workspace.mkdir()
            source = self._write_rotatable_cache(home, "untrusted-source", "scsi-main", expired)
            project_slug = re.sub(r"[^A-Za-z0-9]+", "-", str(workspace.resolve())).strip("-")
            current_cache = home / ".cursor/projects" / project_slug / "mcp-auth.json"
            log = self._stub_rotating_cursor_agent(bindir, home, current_cache, "scsi-main", rotates_to=fresh)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"], cwd=workspace)
            calls = log.read_text().splitlines() if log.exists() else []
            source_access_token = json.loads(source.read_text())["scsi-main"]["tokens"]["access_token"]

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh
        assert len(calls) == 2, calls
        assert calls[0].endswith(" mcp enable scsi-main"), calls
        cwd_str, sep, invoked = calls[1].partition(" mcp ")
        assert sep and invoked == "list-tools scsi-main", calls
        assert Path(cwd_str).resolve() == workspace.resolve()
        assert not any("mcp login" in call for call in calls)
        assert source_access_token == expired

    def test_no_proactive_rotation_defers_short_jwt_rotation(self):
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", short, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            result = self._run(
                home,
                bindir,
                ["scsi-main", "--login", "--quiet", "--no-proactive-rotation"],
                cwd=workspace,
            )
            cursor_ran = log.exists()

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == short, "the still-valid token must be returned without waiting"
        assert not cursor_ran, "a ready workspace cache must not launch cursor-agent during preflight"

    def test_no_proactive_rotation_keeps_critical_rotation_blocking(self):
        mod = _load_mcp_token_module()
        critical = self._jwt(int(time.time()) + mod.BLOCKING_ROTATE_TTL_SECONDS - 60)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", critical, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=fresh)
            result = self._run(
                home,
                bindir,
                ["scsi-main", "--login", "--quiet", "--no-proactive-rotation"],
                cwd=workspace,
            )
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh
        assert any("mcp list-tools scsi-main" in call for call in calls)

    def test_rotate_after_reject_adopts_concurrent_rotation_without_regrant(self):
        # Worker 1 already rotated the chain; worker 2's 401-triggered rotation
        # must adopt the fresh token under the lock instead of overwriting it
        # with another sentinel-and-grant cycle.
        mod = _load_mcp_token_module()
        rejected = self._jwt(int(time.time()) + 1200)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", fresh, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=fresh)
            env_home, env_path = os.environ.get("HOME"), os.environ.get("PATH")
            os.environ["HOME"] = str(home)
            os.environ["PATH"] = f"{bindir}{os.pathsep}{env_path}"
            try:
                mod.CURSOR_CACHE_GLOB = str(home / ".cursor/projects/*/mcp-auth.json")
                mod.ROTATION_LOCK = str(home / ".cache/mcp-token/rotation.lock")
                mod.OPAQUE_REFRESH_STATE = str(home / ".cache/mcp-token/opaque-refresh.json")
                adopted = mod._rotate_after_reject("scsi-main", rejected)
                rotated_same = mod._rotate_after_reject("scsi-main", fresh)
            finally:
                os.environ["HOME"] = env_home
                os.environ["PATH"] = env_path
            calls = log.read_text().splitlines() if log.exists() else []

        assert adopted is True, "a differing cached token proves another worker already rotated"
        assert rotated_same is True, "rejecting the currently cached token must execute the grant"
        assert len(calls) == 2, f"only one enable plus the same-token grant may run cursor-agent, got {calls}"

    def test_concurrent_logins_rotate_once(self):
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", short, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=fresh)
            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            }
            command = [sys.executable, str(MCP_TOKEN_COMMAND), "scsi-main", "--login", "--quiet"]
            workers = [
                subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
                for _ in range(2)
            ]
            results = [worker.communicate(timeout=5) + (worker.returncode,) for worker in workers]
            calls = log.read_text().splitlines() if log.exists() else []

        assert all(returncode == 0 for _stdout, _stderr, returncode in results), results
        assert len(calls) == 2, "one enable plus one grant must serve concurrent rotations"

    def test_jwt_with_runway_skips_rotation(self):
        mod = _load_mcp_token_module()
        token = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS + 900)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", token, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            cursor_ran = log.exists()

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == token
        assert not cursor_ran, "a token above the min-TTL floor must skip rotation entirely"

    def test_failed_rotation_restores_cache_and_keeps_valid_token(self):
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", short, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            cache_token = json.loads(cache.read_text())["scsi-main"]["tokens"]["access_token"]
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == short, "a still-valid token must survive a failed rotation"
        assert cache_token == short, "the invalidated access token must be restored on failure"
        assert not any("mcp login" in call for call in calls), "a still-valid token must never escalate to a browser"

    def test_expired_tokens_rotate_silently_before_browser(self):
        expired = self._jwt(int(time.time()) - 100)
        fresh = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", expired, workspace=workspace)
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=fresh)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == fresh
        assert not any("mcp login" in call for call in calls), "rotation must run before any browser flow"

    def test_revoked_opaque_rotation_earns_full_window_not_adoption_lease(self):
        revoked = "opaque-revoked-nominal"
        old_live = "opaque-old-live-alternative"
        fresh = "opaque-fresh-rotated"
        with (
            _liveness_server({revoked: 401, old_live: 200, fresh: 200}) as (url, handler),
            tempfile.TemporaryDirectory() as tmp,
        ):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            self._write_mcp_json(home, "slack", url)
            cache = self._write_rotatable_cache(home, "new", "slack", revoked, workspace=workspace)
            self._write_rotatable_cache(home, "old", "slack", old_live, refresh_token=None)
            os.utime(home / ".cursor/projects/old/mcp-auth.json", (time.time() - 100, time.time() - 100))
            self._write_ledger(home, "slack", revoked, str(cache))
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "slack", rotates_to=fresh)
            result = self._run(home, bindir, ["slack", "--login", "--quiet", "--json"])
            ledger = self._read_ledger(home, "slack")
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["token"] == fresh, "a fresh rotation must beat adopting an aged cached alternative"
        mod = _load_mcp_token_module()
        assert payload["seconds_left"] > mod.VERIFIED_ADOPTION_TTL_SECONDS, (
            "a provider-minted rotation earns the full nominal window, not an adoption lease"
        )
        assert ledger.get("token_sha256") == self._sha(fresh)
        assert "valid_until" not in ledger
        assert not any("mcp login" in call for call in calls)

    def test_failed_untrusted_refresh_falls_back_to_browser(self):
        expired = self._jwt(int(time.time()) - 100)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            # The first cache has a refresh token but belongs to neither the
            # current workspace nor a trusted recorded workspace. The second
            # has a resolvable workspace but no refresh token.
            self._write_rotatable_cache(home, "no-ws", "scsi-main", expired, workspace=None)
            self._write_rotatable_cache(home, "no-rt", "scsi-main", expired, refresh_token=None, workspace=root / "ws")
            cache = home / ".cursor/projects/no-ws/mcp-auth.json"
            log = self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            result = self._run(home, bindir, ["scsi-main", "--login", "--quiet"])
            calls = log.read_text().splitlines() if log.exists() else []

        assert result.returncode == 1, "no rotatable cache and a failed browser login must fail"
        assert any("list-tools scsi-main" in call for call in calls), "the newest refresh chain must be tried"
        assert any("mcp login scsi-main" in call for call in calls), "the browser flow remains the last resort"

    def test_rotation_sentinel_never_leaks_to_output(self):
        mod = _load_mcp_token_module()
        short = self._jwt(int(time.time()) + mod.MIN_TTL_SECONDS - 600)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_rotatable_cache(home, "p", "scsi-main", short, workspace=workspace)
            self._stub_rotating_cursor_agent(bindir, home, cache, "scsi-main", rotates_to=None)
            # Not --quiet: status text streams to stderr, mimicking wrappers.
            result = self._run(home, bindir, ["scsi-main", "--login"])

        assert result.returncode == 0, result.stderr
        assert mod.ROTATION_SENTINEL not in result.stdout
        assert mod.ROTATION_SENTINEL not in result.stderr
        assert short not in result.stderr


class TestMcpTokenWorkspaceSeeding(unittest.TestCase):
    """WHEN ``--login --no-proactive-rotation`` runs in a workspace cursor has never seen.

    cursor-agent reads only its own per-project OAuth cache, so a fresh worktree
    starts unauthenticated even when other project caches hold live chains.
    Token chains are not workspace-bound, so the workspace-auth gate must seed
    the missing cache from the newest verified cached chain and reserve the
    browser flow for the case where no verifiable chain exists. These are
    real-seam tests: an isolated ``HOME``, a local liveness endpoint, and a stub
    cursor-agent standing in for the browser flow.
    """

    def _sha(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _jwt(self, exp: int) -> str:
        def encode(value: dict[str, object]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'exp': exp})}.sig"

    def _slug(self, workspace: Path) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", os.path.realpath(workspace)).strip("-")

    def _write_cache(self, home: Path, name: str, server: str, tokens: dict[str, object]) -> Path:
        cache = home / ".cursor/projects" / name / "mcp-auth.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({server: {"tokens": tokens}}))
        return cache

    def _write_mcp_json(self, home: Path, server: str, url: str) -> None:
        cfg = home / ".cursor/mcp.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({"mcpServers": {server: {"url": url}}}))

    def _write_ledger(self, home: Path, server: str, token: str, source: str) -> None:
        state_dir = home / ".cache/mcp-token"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "opaque-refresh.json").write_text(
            json.dumps({server: {"source": source, "token_sha256": self._sha(token), "refreshed_at": time.time()}})
        )

    def _stub_cursor_agent(self, bindir: Path, log: Path, *, login_writes: tuple[Path, str] | None = None) -> None:
        lines = ["#!/usr/bin/env bash", f"printf '%s\\n' \"$*\" >> {shlex.quote(str(log))}"]
        if login_writes is not None:
            cache, payload = login_writes
            lines += [
                'if [[ "${1:-} ${2:-}" == "mcp login" ]]; then',
                f"  mkdir -p {shlex.quote(str(cache.parent))}",
                f"  cat > {shlex.quote(str(cache))} <<'EOF'\n{payload}\nEOF",
                "fi",
            ]
        lines.append("exit 0")
        agent = bindir / "cursor-agent"
        agent.write_text("\n".join(lines) + "\n")
        agent.chmod(0o755)

    def _run(self, home: Path, bindir: Path, workspace: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MCP_TOKEN_COMMAND), *args],
            capture_output=True,
            text=True,
            cwd=workspace,
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )

    def test_missing_workspace_cache_is_seeded_from_live_opaque_chain_without_browser(self):
        live = "opaque-live-donor"
        with _liveness_server({live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            bindir.mkdir()
            workspace.mkdir()
            self._write_mcp_json(home, "slack", url)
            donor_tokens = {"access_token": live, "expires_in": 3600, "refresh_token": "refresh-chain"}
            donor = self._write_cache(home, "donor", "slack", donor_tokens)
            self._write_ledger(home, "slack", live, str(donor))
            log = root / "cursor-agent.log"
            self._stub_cursor_agent(bindir, log)

            result = self._run(home, bindir, workspace, ["slack", "--login", "--quiet", "--no-proactive-rotation"])
            calls = log.read_text().splitlines() if log.exists() else []
            seeded_path = home / ".cursor/projects" / self._slug(workspace) / "mcp-auth.json"
            seeded = json.loads(seeded_path.read_text()) if seeded_path.exists() else {}
            seeded_mode = seeded_path.stat().st_mode & 0o777 if seeded_path.exists() else None
            donor_after = json.loads(donor.read_text())

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == live
        assert not any("mcp login" in call for call in calls), "a live cached chain must seed, not pop a browser"
        assert seeded.get("slack", {}).get("tokens") == donor_tokens, "the full donor chain must be copied"
        assert seeded_mode == 0o600, "a seeded token cache must be owner-only"
        assert donor_after["slack"]["tokens"] == donor_tokens, "the donor cache must stay untouched"
        assert live not in result.stderr

    def test_fresh_jwt_seeds_workspace_cache_without_any_liveness_probe(self):
        fresh = self._jwt(int(time.time()) + 7200)
        with _liveness_server({}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            bindir.mkdir()
            workspace.mkdir()
            self._write_mcp_json(home, "scsi-main", url)
            self._write_cache(home, "donor", "scsi-main", {"access_token": fresh, "expires_in": 3600})
            log = root / "cursor-agent.log"
            self._stub_cursor_agent(bindir, log)

            result = self._run(home, bindir, workspace, ["scsi-main", "--login", "--quiet", "--no-proactive-rotation"])
            calls = log.read_text().splitlines() if log.exists() else []
            hits = list(handler.hits)
            seeded_path = home / ".cursor/projects" / self._slug(workspace) / "mcp-auth.json"
            seeded = json.loads(seeded_path.read_text()) if seeded_path.exists() else {}

        assert result.returncode == 0, result.stderr
        assert hits == [], "a JWT's exp is authoritative; seeding must not probe"
        assert calls == [], "no cursor-agent invocation is needed to seed a fresh JWT"
        assert seeded.get("scsi-main", {}).get("tokens", {}).get("access_token") == fresh

    def test_unverifiable_opaque_chain_is_never_seeded_and_browser_runs_last(self):
        nominal = "opaque-unverifiable"
        fresh = "opaque-browser-minted"
        with _liveness_server({nominal: 500, fresh: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            bindir.mkdir()
            workspace.mkdir()
            self._write_mcp_json(home, "slack", url)
            donor = self._write_cache(
                home, "donor", "slack", {"access_token": nominal, "expires_in": 3600, "refresh_token": "rt"}
            )
            self._write_ledger(home, "slack", nominal, str(donor))
            workspace_cache = home / ".cursor/projects" / self._slug(workspace) / "mcp-auth.json"
            payload = json.dumps({"slack": {"tokens": {"access_token": fresh, "expires_in": 3600}}})
            log = root / "cursor-agent.log"
            self._stub_cursor_agent(bindir, log, login_writes=(workspace_cache, payload))

            result = self._run(home, bindir, workspace, ["slack", "--login", "--quiet", "--no-proactive-rotation"])
            calls = log.read_text().splitlines() if log.exists() else []
            seeded = json.loads(workspace_cache.read_text()) if workspace_cache.exists() else {}

        assert result.returncode == 0, result.stderr
        assert any("mcp login slack" in call for call in calls), (
            "an unverifiable chain must not be seeded; the browser flow remains the fallback"
        )
        assert seeded.get("slack", {}).get("tokens", {}).get("access_token") == fresh

    def test_seeding_preserves_other_servers_in_existing_workspace_cache(self):
        live = "opaque-live-donor"
        with _liveness_server({live: 200}) as (url, handler), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            bindir.mkdir()
            workspace.mkdir()
            self._write_mcp_json(home, "slack", url)
            donor = self._write_cache(
                home, "donor", "slack", {"access_token": live, "expires_in": 3600, "refresh_token": "rt"}
            )
            self._write_ledger(home, "slack", live, str(donor))
            other_tokens = {"access_token": "other-server-token", "expires_in": 3600}
            workspace_cache = self._write_cache(home, self._slug(workspace), "kibana", other_tokens)
            log = root / "cursor-agent.log"
            self._stub_cursor_agent(bindir, log)

            result = self._run(home, bindir, workspace, ["slack", "--login", "--quiet", "--no-proactive-rotation"])
            calls = log.read_text().splitlines() if log.exists() else []
            seeded = json.loads(workspace_cache.read_text())

        assert result.returncode == 0, result.stderr
        assert not any("mcp login" in call for call in calls)
        assert seeded.get("slack", {}).get("tokens", {}).get("access_token") == live
        assert seeded.get("kibana", {}).get("tokens") == other_tokens, "other servers' entries must be preserved"


class TestMcpTokenBridge(unittest.TestCase):
    """WHEN an agent session runs a hosted OAuth MCP server through the bridge.

    Real-seam tests: an isolated ``HOME`` holds cursor caches, a stub
    cursor-agent plays the refresh grant, and a fake streamable-HTTP server
    classifies bearers. The deep state table (resurrection, same-token retry,
    malformed stdin, concurrency) lives in the /tmp state-machine harness.
    """

    def _jwt(self, exp: int, subject: str = "a") -> str:
        def encode(value: dict[str, object]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'exp': exp, 'sub': subject})}.sig"

    def _write_cache(self, home: Path, server: str, token: str, *, workspace: Path | None = None) -> Path:
        project = home / ".cursor/projects/p"
        project.mkdir(parents=True, exist_ok=True)
        cache = project / "mcp-auth.json"
        cache.write_text(
            json.dumps({server: {"tokens": {"access_token": token, "refresh_token": "chain", "expires_in": 3600}}})
        )
        if workspace is not None:
            workspace.mkdir(parents=True, exist_ok=True)
            (project / ".workspace-trusted").write_text(json.dumps({"workspacePath": str(workspace)}))
        return cache

    INITIALIZE = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}

    def test_serves_requests_with_fresh_bearer_and_session_id(self):
        token = self._jwt(int(time.time()) + 3600)
        with tempfile.TemporaryDirectory() as tmp, _bridge_mcp_server({token}) as (url, handler):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_cache(home, "scsi-main", token)
            session = _BridgeSession(home, bindir, "scsi-main", url)
            session.send(self.INITIALIZE)
            init_response = session.recv()
            session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            session.send({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            list_response = session.recv()
            returncode = session.close()
            hits = list(handler.hits)

        assert returncode == 0
        assert init_response["result"]["serverInfo"]["name"] == "fake"
        assert list_response["id"] == 1 and list_response["result"]["echo"] == "tools/list"
        posts = [hit for hit in hits if hit[0] == "POST"]
        assert all(hit[2] == token for hit in posts), "every request must carry the cached bearer"
        assert posts[-1][3] == "bridge-session", "captured session id must be echoed"
        assert ("DELETE", None, "bridge-session") in hits, "stdin EOF must close the server session"

    def test_rejected_bearer_rotates_and_retries_within_session(self):
        stale = self._jwt(int(time.time()) + 3600, "stale")
        fresh = self._jwt(int(time.time()) + 3600, "fresh")
        with tempfile.TemporaryDirectory() as tmp, _bridge_mcp_server({fresh}) as (url, handler):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_cache(home, "scsi-main", stale, workspace=workspace)
            rotated = json.dumps(
                {"scsi-main": {"tokens": {"access_token": fresh, "refresh_token": "next", "expires_in": 3600}}}
            )
            agent = bindir / "cursor-agent"
            agent.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "$1 $2" = "mcp list-tools" ]; then\n'
                f"cat > {shlex.quote(str(cache))} <<'EOF'\n{rotated}\nEOF\n"
                "fi\nexit 0\n"
            )
            agent.chmod(0o755)
            session = _BridgeSession(home, bindir, "scsi-main", url)
            session.send(self.INITIALIZE)
            init_response = session.recv(timeout=30)
            returncode = session.close()
            hits = list(handler.hits)

        assert returncode == 0
        assert "result" in init_response, f"rotated retry must succeed: {init_response}"
        tokens_seen = [hit[2] for hit in hits if hit[0] == "POST" and hit[1] == "initialize"]
        assert tokens_seen == [stale, fresh], "exactly one rejected then one rotated retry"

    def test_expired_untrusted_cache_rotates_through_the_bridge_workspace(self):
        expired = self._jwt(int(time.time()) - 100, "expired")
        fresh = self._jwt(int(time.time()) + 3600, "fresh")
        with tempfile.TemporaryDirectory() as tmp, _bridge_mcp_server({fresh}) as (url, _handler):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "current-workspace"
            home.mkdir()
            bindir.mkdir()
            workspace.mkdir()
            source = home / ".cursor/projects/untrusted-source/mcp-auth.json"
            source.parent.mkdir(parents=True)
            source.write_text(
                json.dumps(
                    {
                        "scsi-main": {
                            "tokens": {
                                "access_token": expired,
                                "refresh_token": "chain",
                                "expires_in": 3600,
                            }
                        }
                    }
                )
            )
            project_slug = re.sub(r"[^A-Za-z0-9]+", "-", str(workspace.resolve())).strip("-")
            current_cache = home / ".cursor/projects" / project_slug / "mcp-auth.json"
            rotated = json.dumps(
                {"scsi-main": {"tokens": {"access_token": fresh, "refresh_token": "next", "expires_in": 3600}}}
            )
            agent = bindir / "cursor-agent"
            agent.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "$1 $2" = "mcp list-tools" ]; then\n'
                f"cat > {shlex.quote(str(current_cache))} <<'EOF'\n{rotated}\nEOF\n"
                "fi\nexit 0\n"
            )
            agent.chmod(0o755)
            session = _BridgeSession(home, bindir, "scsi-main", url, cwd=workspace)
            session.send(self.INITIALIZE)
            init_response = session.recv(timeout=3)
            returncode = session.close()

        assert returncode == 0
        assert "result" in init_response, f"current-workspace refresh chain must recover the bridge: {init_response}"

    def test_failed_refresh_chain_opens_browser_login_and_recovers(self):
        expired = self._jwt(int(time.time()) - 100, "expired")
        fresh = self._jwt(int(time.time()) + 3600, "fresh")
        with tempfile.TemporaryDirectory() as tmp, _bridge_mcp_server({fresh}) as (url, _handler):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_cache(home, "scsi-main", expired, workspace=workspace)
            calls = root / "cursor-agent.log"
            logged_in = json.dumps(
                {"scsi-main": {"tokens": {"access_token": fresh, "refresh_token": "next", "expires_in": 3600}}}
            )
            agent = bindir / "cursor-agent"
            agent.write_text(
                "#!/usr/bin/env bash\n"
                f'printf "%s\\n" "$*" >> {shlex.quote(str(calls))}\n'
                'if [ "$1 $2" = "mcp login" ]; then\n'
                f"cat > {shlex.quote(str(cache))} <<'EOF'\n{logged_in}\nEOF\n"
                "fi\n"
                "exit 0\n"
            )
            agent.chmod(0o755)
            session = _BridgeSession(home, bindir, "scsi-main", url)
            session.send(self.INITIALIZE)
            init_response = session.recv(timeout=5)
            returncode = session.close()
            invocations = calls.read_text().splitlines()

        assert returncode == 0
        assert "result" in init_response, f"browser login must recover the active bridge: {init_response}"
        assert invocations == [
            "mcp enable scsi-main",
            "mcp list-tools scsi-main",
            "mcp enable scsi-main",
            "mcp login scsi-main",
        ]

    def test_concurrent_bridges_share_one_browser_login(self):
        expired = self._jwt(int(time.time()) - 100, "expired")
        fresh = self._jwt(int(time.time()) + 3600, "fresh")
        with tempfile.TemporaryDirectory() as tmp, _bridge_mcp_server({fresh}) as (url, _handler):
            root = Path(tmp)
            home, bindir, workspace = root / "home", root / "bin", root / "ws"
            home.mkdir()
            bindir.mkdir()
            cache = self._write_cache(home, "scsi-main", expired, workspace=workspace)
            calls = root / "cursor-agent.log"
            logged_in = json.dumps(
                {"scsi-main": {"tokens": {"access_token": fresh, "refresh_token": "next", "expires_in": 3600}}}
            )
            agent = bindir / "cursor-agent"
            agent.write_text(
                "#!/usr/bin/env bash\n"
                f'printf "%s\\n" "$*" >> {shlex.quote(str(calls))}\n'
                'if [ "$1 $2" = "mcp login" ]; then\n'
                "sleep 1\n"
                f"cat > {shlex.quote(str(cache))} <<'EOF'\n{logged_in}\nEOF\n"
                "fi\n"
                "exit 0\n"
            )
            agent.chmod(0o755)
            sessions = [_BridgeSession(home, bindir, "scsi-main", url) for _ in range(2)]
            for session in sessions:
                session.send(self.INITIALIZE)
            responses = [session.recv(timeout=8) for session in sessions]
            returncodes = [session.close() for session in sessions]
            invocations = calls.read_text().splitlines()

        assert returncodes == [0, 0]
        assert all("result" in response for response in responses)
        assert invocations.count("mcp login scsi-main") == 1

    def test_sse_response_streams_messages_in_order(self):
        token = self._jwt(int(time.time()) + 3600)
        with (
            tempfile.TemporaryDirectory() as tmp,
            _bridge_mcp_server({token}, sse_methods={"tools/call"}) as (url, _handler),
        ):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_cache(home, "scsi-main", token)
            session = _BridgeSession(home, bindir, "scsi-main", url)
            session.send(self.INITIALIZE)
            session.recv()
            session.send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "x"}})
            progress = session.recv()
            response = session.recv()
            returncode = session.close()

        assert returncode == 0
        assert progress["method"] == "notifications/progress", "SSE events must stream before the response"
        assert response["id"] == 2 and response["result"]["via"] == "sse"

    def test_opt_in_retries_upstream_connect_timeout_once(self):
        token = self._jwt(int(time.time()) + 3600)
        with (
            tempfile.TemporaryDirectory() as tmp,
            _bridge_mcp_server({token}, connect_timeouts={"tools/call": 1}) as (url, handler),
        ):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_cache(home, "scsi-main", token)
            session = _BridgeSession(home, bindir, "scsi-main", url, "--retry-connect-timeouts")
            session.send(self.INITIALIZE)
            session.recv(timeout=2)
            session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            session.send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_indices"}})
            response = session.recv(timeout=2)
            returncode = session.close()
            calls = [hit for hit in handler.hits if hit[0] == "POST" and hit[1] == "tools/call"]

        assert returncode == 0
        assert response["id"] == 3 and response["result"]["echo"] == "tools/call"
        assert len(calls) == 2, "the exact upstream connect timeout should be retried once"

    def test_connect_timeout_without_opt_in_is_not_retried(self):
        token = self._jwt(int(time.time()) + 3600)
        with (
            tempfile.TemporaryDirectory() as tmp,
            _bridge_mcp_server({token}, connect_timeouts={"tools/call": 1}) as (url, handler),
        ):
            root = Path(tmp)
            home, bindir = root / "home", root / "bin"
            home.mkdir()
            bindir.mkdir()
            self._write_cache(home, "slack", token)
            session = _BridgeSession(home, bindir, "slack", url)
            session.send(self.INITIALIZE)
            session.recv(timeout=2)
            session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            session.send({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "send_message"}})
            response = session.recv(timeout=2)
            returncode = session.close()
            calls = [hit for hit in handler.hits if hit[0] == "POST" and hit[1] == "tools/call"]

        assert returncode == 0
        assert response["id"] == 4
        assert response["error"]["message"] == "bridge request failed: HTTP 503"
        assert len(calls) == 1, "side-effecting endpoints must remain non-retriable by default"


if __name__ == "__main__":
    unittest.main()
