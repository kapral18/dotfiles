#!/usr/bin/env python3
"""Tests for generate_mcp_configs.py and the Copilot MCP wrapper."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
import time
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

COPILOT_LAUNCHER = REPO / "home/exact_bin/executable_,copilot"
COPILOT_LIBRARY = REPO / "home/exact_lib/exact_,copilot/main.py"
ARTIFACT_HELPER = REPO / "scripts/generated_artifact_ledger.py"


FAKE_GENERATOR = r"""#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path


def append(path, line):
    with Path(path).open("a") as stream:
        stream.write(line + "\n")


plan = json.loads(Path(os.environ["FAKE_PLAN"]).read_text())
flag = sys.argv[-1]
if flag == "--copilot-header-auth-plan":
    append(os.environ["FAKE_GENERATOR_LOG"], "plan")
    if os.environ.get("FAKE_GENERATOR_FAIL") == "plan":
        raise SystemExit(7)
    print(json.dumps(plan))
    raise SystemExit(0)

if flag != "--header-auth-overrides-stdin":
    raise SystemExit(8)
append(os.environ["FAKE_GENERATOR_LOG"], "render")
if os.environ.get("FAKE_GENERATOR_FAIL") == "render":
    raise SystemExit(9)
overrides = json.load(sys.stdin)
append(os.environ["FAKE_GENERATOR_LOG"], "override-keys=" + ",".join(sorted(overrides)))

active = Path(os.environ["FAKE_GENERATOR_ACTIVE"])
overlap = Path(os.environ["FAKE_GENERATOR_OVERLAP"])
owns_active = False
try:
    descriptor = os.open(active, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    owns_active = True
except FileExistsError:
    overlap.write_text("overlap\n")

block_once = os.environ.get("FAKE_GENERATOR_BLOCK_ONCE")
if block_once:
    marker = Path(block_once)
    try:
        descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        Path(os.environ["FAKE_GENERATOR_ENTERED"]).write_text("entered\n")
        release = Path(os.environ["FAKE_GENERATOR_RELEASE"])
        deadline = time.monotonic() + 5
        while not release.exists():
            if time.monotonic() > deadline:
                raise SystemExit(10)
            time.sleep(0.01)
    except FileExistsError:
        pass

try:
    servers = {
        "local": {
            "type": "local",
            "command": "true",
            "args": [],
            "tools": ["*"],
        }
    }
    placeholder_server = os.environ.get("FAKE_PLACEHOLDER_SERVER")
    mismatch_server = os.environ.get("FAKE_MISMATCH_SERVER")
    for row in plan["header_auth_servers"]:
        authorization = overrides[row["shell_command"]]
        if row["server"] == placeholder_server:
            authorization = plan["refresh_placeholder"]
        if row["server"] == mismatch_server:
            authorization = "******"
        servers[row["server"]] = {
            "type": "http",
            "url": "https://example.invalid/" + row["server"],
            "tools": ["*"],
            "headers": {"Authorization": authorization},
        }
    print(json.dumps({"mcpServers": servers}, indent=2))
finally:
    if owns_active:
        active.unlink(missing_ok=True)
"""


FAKE_TOKEN_PROVIDER = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

source = sys.argv[1]
with Path(os.environ["FAKE_TOKEN_LOG"]).open("a") as stream:
    stream.write(" ".join(sys.argv[1:]) + "\n")
tokens = json.loads(Path(os.environ["FAKE_TOKENS"]).read_text())
token = tokens.get(source)
if not isinstance(token, str):
    raise SystemExit(4)
print("provider diagnostic " + token, file=sys.stderr)
print(json.dumps({"token": token, "source": "fixture", "seconds_left": 3600, "rotation_due": False}))
"""


FAKE_COPILOT = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

with Path(os.environ["FAKE_COPILOT_LOG"]).open("a") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\n")
print("REAL_COPILOT_STARTED")
"""


FAKE_ARTIFACT_PROXY = r"""#!/usr/bin/env python3
import os
import sys
from pathlib import Path

with Path(os.environ["FAKE_ARTIFACT_LOG"]).open("a") as stream:
    stream.write("record\n")
if os.environ.get("FAKE_ARTIFACT_FAIL") == "1":
    raise SystemExit(11)
helper = os.environ["REAL_ARTIFACT_HELPER"]
os.execv(sys.executable, [sys.executable, helper, *sys.argv[1:]])
"""


@dataclass
class CopilotFixture:
    root: Path
    env: dict[str, str]
    config: Path
    ledger: Path
    generator_log: Path
    token_log: Path
    artifact_log: Path
    copilot_log: Path
    generator_entered: Path
    generator_release: Path
    generator_overlap: Path

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [modern_bash(), str(COPILOT_LAUNCHER), *args],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env=self.env,
        )

    def popen(self, *args: str) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [modern_bash(), str(COPILOT_LAUNCHER), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO),
            env=self.env,
        )


def _default_plan() -> dict[str, object]:
    return {
        "schema_version": 1,
        "refresh_placeholder": "__MCP_HEADER_AUTH_REFRESH_REQUIRED__",
        "header_auth_servers": [
            {
                "server": "jwt-primary",
                "token_source": "jwt-source",
                "shell_command": ",mcp-token jwt-source --bearer",
            },
            {
                "server": "jwt-secondary",
                "token_source": "jwt-source",
                "shell_command": ",mcp-token jwt-source --bearer",
            },
            {
                "server": "opaque",
                "token_source": "opaque-source",
                "shell_command": ",mcp-token opaque-source --bearer",
            },
        ],
    }


def _expected_document(plan: dict[str, object], tokens: dict[str, str]) -> dict[str, object]:
    servers: dict[str, object] = {
        "local": {
            "type": "local",
            "command": "true",
            "args": [],
            "tools": ["*"],
        }
    }
    for row in plan["header_auth_servers"]:
        assert isinstance(row, dict)
        server = str(row["server"])
        source = str(row["token_source"])
        servers[server] = {
            "type": "http",
            "url": "https://example.invalid/" + server,
            "tools": ["*"],
            "headers": {"Authorization": "Bearer " + tokens[source]},
        }
    return {"mcpServers": servers}


@contextlib.contextmanager
def copilot_fixture(
    *,
    initial_config: dict[str, object] | None = None,
    tokens: dict[str, str | None] | None = None,
):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        home = root / "home"
        source = root / "source/home"
        scripts = root / "source/scripts"
        bindir = root / "bin"
        copilot_dir = home / ".copilot"
        copilot_dir.mkdir(parents=True)
        (source / ".chezmoidata").mkdir(parents=True)
        scripts.mkdir(parents=True)
        bindir.mkdir()

        plan = _default_plan()
        token_values = tokens or {
            "jwt-source": "jwt.fake.payload",
            "opaque-source": "opaque-fake-token",
        }
        plan_path = root / "plan.json"
        tokens_path = root / "tokens.json"
        plan_path.write_text(json.dumps(plan))
        tokens_path.write_text(json.dumps(token_values))
        (source / ".chezmoidata/mcp_servers.yaml").write_text("mcp_servers: []\n")

        generator = scripts / "generate_mcp_configs.py"
        generator.write_text(FAKE_GENERATOR)
        generator.chmod(0o755)
        for dependency in ("mcp_registry.py", "yaml_parser.py", "chezmoi_lib.sh"):
            (scripts / dependency).write_text(f"# {dependency}\n")

        token_provider = bindir / ",mcp-token"
        token_provider.write_text(FAKE_TOKEN_PROVIDER)
        token_provider.chmod(0o755)
        real_copilot = bindir / "copilot-real"
        real_copilot.write_text(FAKE_COPILOT)
        real_copilot.chmod(0o755)
        artifact_proxy = scripts / "artifact-proxy.py"
        artifact_proxy.write_text(FAKE_ARTIFACT_PROXY)

        config = copilot_dir / "mcp-config.json"
        if initial_config is not None:
            config.write_text(json.dumps(initial_config))
            config.chmod(0o600)

        generator_log = root / "generator.log"
        token_log = root / "token.log"
        artifact_log = root / "artifact.log"
        copilot_log = root / "copilot.log"
        ledger = root / "state/generated_artifacts.v1.json"
        active = root / "generator.active"
        overlap = root / "generator.overlap"
        entered = root / "generator.entered"
        release = root / "generator.release"

        env = {
            **os.environ,
            "HOME": str(home),
            "PATH": os.pathsep.join([str(bindir), "/usr/bin", "/bin", "/usr/sbin", "/sbin"]),
            "COPILOT_REAL_BIN": str(real_copilot),
            "COPILOT_WRAPPER_LIB": str(COPILOT_LIBRARY),
            "COPILOT_SOURCE_DIR": str(source),
            "COPILOT_IS_WORK": "true",
            "COPILOT_MCP_GENERATOR": str(generator),
            "COPILOT_MCP_TOKEN_BIN": str(token_provider),
            "COPILOT_MCP_CONFIG": str(config),
            "COPILOT_MCP_LOCK": str(copilot_dir / "mcp-config.lock"),
            "COPILOT_ARTIFACT_HELPER": str(artifact_proxy),
            "CHEZMOI_ARTIFACT_LEDGER": str(ledger),
            "FAKE_PLAN": str(plan_path),
            "FAKE_TOKENS": str(tokens_path),
            "FAKE_GENERATOR_LOG": str(generator_log),
            "FAKE_TOKEN_LOG": str(token_log),
            "FAKE_ARTIFACT_LOG": str(artifact_log),
            "FAKE_COPILOT_LOG": str(copilot_log),
            "FAKE_GENERATOR_ACTIVE": str(active),
            "FAKE_GENERATOR_OVERLAP": str(overlap),
            "FAKE_GENERATOR_ENTERED": str(entered),
            "FAKE_GENERATOR_RELEASE": str(release),
            "REAL_ARTIFACT_HELPER": str(ARTIFACT_HELPER),
        }
        yield CopilotFixture(
            root=root,
            env=env,
            config=config,
            ledger=ledger,
            generator_log=generator_log,
            token_log=token_log,
            artifact_log=artifact_log,
            copilot_log=copilot_log,
            generator_entered=entered,
            generator_release=release,
            generator_overlap=overlap,
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

    def _header_auth_registry(self, root: Path) -> Path:
        registry = root / "mcp_servers.yaml"
        registry.write_text(
            """
mcp_servers:
  - name: first
    work_only: false
    type: http
    url: https://first.example/mcp
    oauth_by_tool:
      copilot:
        headerAuth: "$(,mcp-token shared --bearer)"
  - name: second
    work_only: false
    type: http
    url: https://second.example/mcp
    oauth_by_tool:
      copilot:
        headerAuth: "$(,mcp-token shared --bearer)"
  - name: third
    work_only: false
    type: http
    url: https://third.example/mcp
    oauth_by_tool:
      copilot:
        headerAuth: "$(,mcp-token opaque --bearer)"
""".lstrip()
        )
        return registry

    def _run_generator(
        self,
        registry: Path,
        flag: str,
        *,
        stdin: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/generate_mcp_configs.py"),
                str(registry),
                "false",
                "copilot",
                flag,
            ],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=str(REPO / "scripts"),
            env={
                **os.environ,
                "HOME": str(registry.parent / "home"),
                "PATH": "/usr/bin:/bin",
            },
        )

    def test_copilot_header_auth_plan_discovers_duplicate_sources_without_resolving(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = self._header_auth_registry(Path(temporary))
            result = self._run_generator(registry, "--copilot-header-auth-plan")

        assert result.returncode == 0, result.stderr
        plan = json.loads(result.stdout)
        assert plan["schema_version"] == 1
        assert [(row["server"], row["token_source"]) for row in plan["header_auth_servers"]] == [
            ("first", "shared"),
            ("second", "shared"),
            ("third", "opaque"),
        ]

    def test_copilot_header_auth_overrides_render_without_running_token_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = self._header_auth_registry(Path(temporary))
            overrides = {
                ",mcp-token shared --bearer": "Bearer shared-token",
                ",mcp-token opaque --bearer": "Bearer opaque-token",
            }
            result = self._run_generator(
                registry,
                "--header-auth-overrides-stdin",
                stdin=json.dumps(overrides),
            )

        assert result.returncode == 0, result.stderr
        servers = json.loads(result.stdout)["mcpServers"]
        assert servers["first"]["headers"]["Authorization"] == "Bearer shared-token"
        assert servers["second"]["headers"]["Authorization"] == "Bearer shared-token"
        assert servers["third"]["headers"]["Authorization"] == "Bearer opaque-token"

    def test_copilot_header_auth_overrides_fail_closed_when_a_source_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = self._header_auth_registry(Path(temporary))
            result = self._run_generator(
                registry,
                "--header-auth-overrides-stdin",
                stdin=json.dumps({",mcp-token shared --bearer": "Bearer shared-token"}),
            )

        assert result.returncode != 0
        assert "missing header-auth override" in result.stderr


class TestCopilotBatchWrapper(unittest.TestCase):
    """WHEN launching Copilot through the typed header-auth batch."""

    def test_batch_deduplicates_sources_renders_once_updates_ledger_and_execs(self):
        with copilot_fixture() as fixture:
            result = fixture.run("-p", "hello")

            assert result.returncode == 0, result.stderr
            assert "REAL_COPILOT_STARTED" in result.stdout
            assert fixture.token_log.read_text().splitlines() == [
                "jwt-source --login --quiet --launch-json",
                "opaque-source --login --quiet --launch-json",
            ]
            generator_calls = fixture.generator_log.read_text().splitlines()
            assert generator_calls[:2] == ["plan", "render"]
            assert len([line for line in generator_calls if line == "render"]) == 1
            document = json.loads(fixture.config.read_text())
            assert document == _expected_document(
                _default_plan(),
                {
                    "jwt-source": "jwt.fake.payload",
                    "opaque-source": "opaque-fake-token",
                },
            )
            assert fixture.config.stat().st_mode & 0o777 == 0o600
            assert fixture.config.parent.stat().st_mode & 0o777 == 0o700
            ledger = json.loads(fixture.ledger.read_text())
            assert ledger["artifacts"]["copilot-mcp"]["target"] == str(fixture.config)
            assert fixture.artifact_log.read_text().splitlines() == ["record"]
            assert json.loads(fixture.copilot_log.read_text()) == ["-p", "hello"]
            combined_output = result.stdout + result.stderr
            assert "jwt.fake.payload" not in combined_output
            assert "opaque-fake-token" not in combined_output
            assert "provider diagnostic" not in combined_output

    def test_partial_token_failure_blocks_render_write_ledger_and_exec(self):
        initial = {"mcpServers": {"old": {"type": "local", "command": "false"}}}
        with copilot_fixture(
            initial_config=initial,
            tokens={"jwt-source": "jwt.fake.payload", "opaque-source": None},
        ) as fixture:
            before = fixture.config.read_bytes()
            result = fixture.run("-p", "hello")

            assert result.returncode == 1
            assert "could not refresh MCP token(s): opaque" in result.stderr
            assert fixture.generator_log.read_text().splitlines() == ["plan"]
            assert fixture.config.read_bytes() == before
            assert not fixture.ledger.exists()
            assert not fixture.artifact_log.exists()
            assert not fixture.copilot_log.exists()
            assert "jwt.fake.payload" not in result.stdout + result.stderr

    def test_render_failure_blocks_target_ledger_and_exec(self):
        initial = {"mcpServers": {"old": {"type": "local", "command": "false"}}}
        with copilot_fixture(initial_config=initial) as fixture:
            fixture.env["FAKE_GENERATOR_FAIL"] = "render"
            before = fixture.config.read_bytes()
            result = fixture.run()

            assert result.returncode == 1
            assert "could not render fresh MCP config" in result.stderr
            assert fixture.config.read_bytes() == before
            assert not fixture.ledger.exists()
            assert not fixture.artifact_log.exists()
            assert not fixture.copilot_log.exists()

    def test_placeholder_after_render_blocks_target_ledger_and_exec(self):
        initial = {"mcpServers": {"old": {"type": "local", "command": "false"}}}
        with copilot_fixture(initial_config=initial) as fixture:
            fixture.env["FAKE_PLACEHOLDER_SERVER"] = "opaque"
            before = fixture.config.read_bytes()
            result = fixture.run()

            assert result.returncode == 1
            assert "MCP token refresh placeholder remains for: opaque" in result.stderr
            assert fixture.config.read_bytes() == before
            assert not fixture.ledger.exists()
            assert not fixture.artifact_log.exists()
            assert not fixture.copilot_log.exists()

    def test_mismatched_authorization_blocks_target_ledger_and_exec(self):
        initial = {"mcpServers": {"old": {"type": "local", "command": "false"}}}
        with copilot_fixture(initial_config=initial) as fixture:
            fixture.env["FAKE_MISMATCH_SERVER"] = "opaque"
            before = fixture.config.read_bytes()
            result = fixture.run()

            assert result.returncode == 1
            assert "rendered MCP Authorization mismatch for: opaque" in result.stderr
            assert fixture.config.read_bytes() == before
            assert not fixture.ledger.exists()
            assert not fixture.artifact_log.exists()
            assert not fixture.copilot_log.exists()

    def test_semantic_noop_preserves_target_and_ledger_inode_and_timestamps(self):
        tokens = {
            "jwt-source": "jwt.fake.payload",
            "opaque-source": "opaque-fake-token",
        }
        desired = _expected_document(_default_plan(), tokens)
        with copilot_fixture(initial_config=desired) as fixture:
            fixture.ledger.parent.mkdir(parents=True)
            fixture.ledger.write_text('{"schema_version":1,"artifacts":{}}\n')
            fixture.ledger.chmod(0o600)
            config_before = fixture.config.stat()
            ledger_before = fixture.ledger.stat()
            result = fixture.run()
            config_after = fixture.config.stat()
            ledger_after = fixture.ledger.stat()

            assert result.returncode == 0, result.stderr
            assert (config_before.st_ino, config_before.st_mtime_ns, config_before.st_ctime_ns) == (
                config_after.st_ino,
                config_after.st_mtime_ns,
                config_after.st_ctime_ns,
            )
            assert (ledger_before.st_ino, ledger_before.st_mtime_ns, ledger_before.st_ctime_ns) == (
                ledger_after.st_ino,
                ledger_after.st_mtime_ns,
                ledger_after.st_ctime_ns,
            )
            assert not fixture.artifact_log.exists()

    def test_changed_target_updates_artifact_once_then_second_launch_is_noop(self):
        initial = {"mcpServers": {"old": {"type": "local", "command": "false"}}}
        with copilot_fixture(initial_config=initial) as fixture:
            first = fixture.run()
            assert first.returncode == 0, first.stderr
            config_after_first = fixture.config.stat()
            ledger_after_first = fixture.ledger.stat()
            row_after_first = json.loads(fixture.ledger.read_text())["artifacts"]["copilot-mcp"]

            second = fixture.run()
            assert second.returncode == 0, second.stderr
            config_after_second = fixture.config.stat()
            ledger_after_second = fixture.ledger.stat()
            row_after_second = json.loads(fixture.ledger.read_text())["artifacts"]["copilot-mcp"]

            assert (config_after_first.st_ino, config_after_first.st_mtime_ns) == (
                config_after_second.st_ino,
                config_after_second.st_mtime_ns,
            )
            assert (ledger_after_first.st_ino, ledger_after_first.st_mtime_ns) == (
                ledger_after_second.st_ino,
                ledger_after_second.st_mtime_ns,
            )
            assert row_after_first["recorded_at"] == row_after_second["recorded_at"]
            assert fixture.artifact_log.read_text().splitlines() == ["record"]

    def test_artifact_failure_rolls_back_target_and_blocks_exec(self):
        initial = {"mcpServers": {"old": {"type": "local", "command": "false"}}}
        with copilot_fixture(initial_config=initial) as fixture:
            fixture.env["FAKE_ARTIFACT_FAIL"] = "1"
            before = fixture.config.read_bytes()
            result = fixture.run()

            assert result.returncode == 1
            assert "could not update generated artifact ledger" in result.stderr
            assert fixture.config.read_bytes() == before
            assert not fixture.copilot_log.exists()

    def test_concurrent_launches_are_locked_and_only_first_records_change(self):
        initial = {"mcpServers": {"old": {"type": "local", "command": "false"}}}
        with copilot_fixture(initial_config=initial) as fixture:
            fixture.env["FAKE_GENERATOR_BLOCK_ONCE"] = str(fixture.root / "generator.block-once")
            first = fixture.popen()
            deadline = time.monotonic() + 5
            while not fixture.generator_entered.exists():
                if first.poll() is not None:
                    stdout, stderr = first.communicate()
                    self.fail(f"first launch exited before render barrier: {stdout}\n{stderr}")
                if time.monotonic() > deadline:
                    first.kill()
                    self.fail("first launch did not reach render barrier")
                time.sleep(0.01)

            second = fixture.popen()
            time.sleep(0.1)
            fixture.generator_release.write_text("release\n")
            first_stdout, first_stderr = first.communicate(timeout=10)
            second_stdout, second_stderr = second.communicate(timeout=10)

            assert first.returncode == 0, first_stderr
            assert second.returncode == 0, second_stderr
            assert "REAL_COPILOT_STARTED" in first_stdout
            assert "REAL_COPILOT_STARTED" in second_stdout
            assert not fixture.generator_overlap.exists()
            assert fixture.artifact_log.read_text().splitlines() == ["record"]
            assert len(fixture.copilot_log.read_text().splitlines()) == 2

    def test_help_version_and_admin_commands_bypass_batch_unchanged(self):
        with copilot_fixture() as fixture:
            for args in (("--help",), ("--version",), ("mcp", "list")):
                result = fixture.run(*args)
                assert result.returncode == 0, result.stderr

            assert [json.loads(line) for line in fixture.copilot_log.read_text().splitlines()] == [
                ["--help"],
                ["--version"],
                ["mcp", "list"],
            ]
            assert not fixture.generator_log.exists()
            assert not fixture.token_log.exists()
            assert not fixture.artifact_log.exists()


if __name__ == "__main__":
    unittest.main()
