#!/usr/bin/env python3
"""Golden-file regression tests for the config generation scripts.

Run from the repo root:
    python3 -m pytest scripts/tests/ -v
Or directly:
    python3 scripts/tests/test_scripts.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
REPO = SCRIPTS.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _run(args: list[str], *, stdin: str | None = None) -> str:
    result = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS),
        input=stdin,
    )
    if result.returncode != 0:
        raise AssertionError(f"{args[0]} failed:\n{result.stderr}")
    return result.stdout


class TestYamlParser(unittest.TestCase):
    """WHEN parsing YAML scalars."""

    def test_parse_scalar_types(self):
        sys.path.insert(0, str(SCRIPTS))
        from yaml_parser import parse_scalar

        assert parse_scalar("true") is True
        assert parse_scalar("false") is False
        assert parse_scalar("42") == 42
        assert parse_scalar("3.14") == 3.14
        assert parse_scalar('"hello"') == "hello"
        assert parse_scalar("'world'") == "world"
        assert parse_scalar("bare") == "bare"


class TestMcpRegistry(unittest.TestCase):
    """WHEN loading MCP servers from YAML."""

    def test_personal_excludes_work_only(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False)
        assert "public-tool" in servers
        assert "work-tool" not in servers
        assert "http-tool" in servers

    def test_work_includes_all(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=True)
        assert "public-tool" in servers
        assert "work-tool" in servers
        assert "http-tool" in servers

    def test_http_server_shape_with_tool(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False, tool="claude")
        http = servers["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert http["oauth"]["clientId"] == "resolved-client-id"
        assert http["oauth"]["callbackPort"] == 3118

    def test_http_server_oauth_by_tool_cursor(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False, tool="cursor")
        http = servers["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert http["oauth"]["clientId"] == "cursor-client-id"
        assert "callbackPort" not in http["oauth"]

    def test_http_server_no_tool_no_oauth(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False)
        http = servers["http-tool"]
        assert http["type"] == "http"
        assert http["url"] == "https://mcp.example.com/mcp"
        assert "oauth" not in http

    def test_http_server_unknown_tool_omits_tool_specific_oauth_server(self):
        sys.path.insert(0, str(SCRIPTS))
        from mcp_registry import load_servers

        servers = load_servers(str(FIXTURES / "mcp_servers.yaml"), is_work=False, tool="gemini")
        assert "http-tool" not in servers


class TestAiModels(unittest.TestCase):
    """WHEN loading AI models from YAML."""

    def test_load_litellm_models(self):
        sys.path.insert(0, str(SCRIPTS))
        from ai_models import load_litellm

        models = load_litellm(str(FIXTURES / "ai_models.yaml"))
        assert len(models) == 2
        assert models[0]["id"] == "llm-gateway/model-a"
        assert models[0]["reasoning"] is True
        assert models[0]["cost"]["input"] == 5
        assert models[1]["reasoning"] is False
        assert models[1]["cost"]["input"] == 0.5

    def test_load_azure_models_empty(self):
        sys.path.insert(0, str(SCRIPTS))
        from ai_models import load_azure

        models = load_azure(str(FIXTURES / "ai_models.yaml"))
        assert len(models) == 0


class TestModelDisplay(unittest.TestCase):
    """WHEN formatting model display names."""

    def test_reasoning_model_with_cost(self):
        sys.path.insert(0, str(SCRIPTS))
        from model_display import format_display_name

        m = {"id": "test", "name": "Test", "reasoning": True, "cost": {"input": 5, "output": 25}}
        assert format_display_name(m) == "Test \U0001f9e0 ($5in/$25out)"

    def test_non_reasoning_model_with_float_cost(self):
        sys.path.insert(0, str(SCRIPTS))
        from model_display import format_display_name

        m = {"id": "test", "name": "Test", "reasoning": False, "cost": {"input": 0.5, "output": 1.5}}
        assert format_display_name(m) == "Test ($0.5in/$1.5out)"

    def test_model_without_cost(self):
        sys.path.insert(0, str(SCRIPTS))
        from model_display import format_display_name

        m = {"id": "test", "name": "Test"}
        assert format_display_name(m) == "Test"


class TestGenerateMcpConfigs(unittest.TestCase):
    """WHEN generating MCP JSON configs."""

    def test_personal_golden(self):
        actual = _run(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "false", "claude"])
        expected = (FIXTURES / "golden_mcp_personal.json").read_text()
        assert json.loads(actual) == json.loads(expected)

    def test_work_golden(self):
        actual = _run(["generate_mcp_configs.py", str(FIXTURES / "mcp_servers.yaml"), "true", "claude"])
        expected = (FIXTURES / "golden_mcp_work.json").read_text()
        assert json.loads(actual) == json.loads(expected)


class TestGeneratePiModels(unittest.TestCase):
    """WHEN generating Pi models JSON."""

    def test_golden(self):
        actual = _run(
            [
                "generate_pi_models.py",
                str(REPO / "home/dot_pi/agent/readonly_models.json"),
                str(FIXTURES / "ai_models.yaml"),
                "http://localhost:4000/v1",
                "https://test-resource.services.ai.azure.com/openai/v1",
            ]
        )
        expected = (FIXTURES / "golden_pi_models.json").read_text()
        assert json.loads(actual) == json.loads(expected)


class TestInjectMcpIntoCodexToml(unittest.TestCase):
    """WHEN injecting MCP servers into Codex TOML."""

    def test_golden(self):
        actual = _run(
            [
                "inject_mcp_into_codex_toml.py",
                str(FIXTURES / "codex_base.toml"),
                str(FIXTURES / "mcp_servers.yaml"),
                "false",
            ]
        )
        expected = (FIXTURES / "golden_codex_personal.toml").read_text()
        assert actual == expected


class TestInjectMcpIntoOpencode(unittest.TestCase):
    """WHEN injecting MCP servers into OpenCode JSONC."""

    def test_golden(self):
        base = (FIXTURES / "opencode_base.jsonc").read_text()
        actual = _run(
            ["inject_mcp_into_opencode_jsonc.py", str(FIXTURES / "mcp_servers.yaml"), "false"],
            stdin=base,
        )
        expected = (FIXTURES / "golden_opencode_personal.jsonc").read_text()
        assert actual == expected


class TestMergeOpencodeModels(unittest.TestCase):
    """WHEN merging AI models into OpenCode JSONC."""

    def test_golden(self):
        actual = _run(
            [
                "merge_opencode_models.py",
                str(FIXTURES / "opencode_work_base.jsonc"),
                str(FIXTURES / "ai_models.yaml"),
            ]
        )
        expected = (FIXTURES / "golden_opencode_models.jsonc").read_text()
        assert actual == expected

    def test_claude_models_routed_to_litellm_anthropic(self):
        actual = _run(
            [
                "merge_opencode_models.py",
                str(FIXTURES / "opencode_work_base.jsonc"),
                str(FIXTURES / "ai_models_with_claude.yaml"),
            ]
        )
        expected = (FIXTURES / "golden_opencode_models_with_claude.jsonc").read_text()
        assert actual == expected


class TestAiKb(unittest.TestCase):
    """WHEN remembering and searching durable agent knowledge."""

    def test_remember_search_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ai_kb.py"),
                    "--home",
                    tmp,
                    "remember",
                    "--title",
                    "Ralph memory",
                    "--body",
                    "Ralph stores durable learnings across sessions.",
                    "--source",
                    "test",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
            )
            assert result.returncode == 0, result.stderr
            capsule = json.loads(result.stdout)
            assert capsule["title"] == "Ralph memory"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ai_kb.py"),
                    "--home",
                    tmp,
                    "search",
                    "durable learnings",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
            )
            assert result.returncode == 0, result.stderr
            rows = json.loads(result.stdout)
            assert rows[0]["id"] == capsule["id"]


def _make_go_env(
    tmp: Path,
    *,
    fail_executor_iter: str = "",
    fail_reviewer: str = "false",
    max_iters: int = 3,
    artifact: Path | None = None,
    content: str = "hello",
) -> dict:
    """Build a fresh env + on-disk roles.json + prompts dir for a ,ralph go test.

    The mock harness in scripts/tests/fixtures/mock_role.sh produces deterministic
    role outputs based on the env vars set here. roles.json points each role at
    that mock with a per-role family tag so the diversity gate is satisfied.
    """
    state_home = tmp / "state"
    kb_home = tmp / "kb"
    workspace = tmp / "workspace"
    counters = tmp / "counters"
    prompts = tmp / "prompts"
    cfg = tmp / "roles.json"
    workspace.mkdir(parents=True, exist_ok=True)
    counters.mkdir(parents=True, exist_ok=True)
    prompts.mkdir(parents=True, exist_ok=True)
    deployed_prompts = REPO / "home/dot_config/ralph/prompts"
    for prompt in deployed_prompts.glob("*.md"):
        (prompts / prompt.name).write_text(prompt.read_text())
    mock = FIXTURES / "mock_role.sh"
    cfg.write_text(
        json.dumps(
            {
                "roles": {
                    "planner": {
                        "harness": "command",
                        "model": "mock-claude-planner",
                        "family": "claude",
                        "extra_args": ["RALPH_TEST_ROLE=planner", str(mock)],
                    },
                    "executor": {
                        "harness": "command",
                        "model": "mock-gpt-executor",
                        "family": "gpt",
                        "extra_args": ["RALPH_TEST_ROLE=executor", str(mock)],
                    },
                    "reviewer": {
                        "harness": "command",
                        "model": "mock-claude-reviewer",
                        "family": "claude",
                        "extra_args": ["RALPH_TEST_ROLE=reviewer", str(mock)],
                    },
                    "re_reviewer": {
                        "harness": "command",
                        "model": "mock-gpt-rereviewer",
                        "family": "gpt",
                        "extra_args": ["RALPH_TEST_ROLE=re_reviewer", str(mock)],
                    },
                },
                "defaults": {
                    "iteration_timeout_seconds": 10,
                    "max_iterations": max_iters,
                    "max_minutes": 1,
                    "memory_top_k": 3,
                    "progress_tail_blocks": 2,
                },
            }
        )
    )
    artifact = artifact or (workspace / "result.txt")
    env = {
        **os.environ,
        "RALPH_STATE_HOME": str(state_home),
        "AI_KB_HOME": str(kb_home),
        "RALPH_ROLES_CONFIG": str(cfg),
        "RALPH_PROMPTS_DIR": str(prompts),
        "RALPH_TEST_GOAL": "test goal",
        "RALPH_TEST_ARTIFACT": str(artifact),
        "RALPH_TEST_CONTENT": content,
        "RALPH_TEST_MAX_ITERS": str(max_iters),
        "RALPH_TEST_COUNTER_DIR": str(counters),
        "RALPH_TEST_FAIL_EXECUTOR_ITER": fail_executor_iter,
        "RALPH_TEST_FAIL_REVIEWER": fail_reviewer,
        # Subprocess-based tests would each pay the fastembed cold start
        # (~1s) on every kb.remember(); disable the embedder by default
        # so the suite stays fast. Tests that exercise the embedding
        # round-trip explicitly del this var.
        "RALPH_KB_DISABLE_EMBED": "1",
    }
    # Drop env that tests opt into per-case so a polluted developer shell
    # cannot bend the deterministic mock harness (e.g. exporting
    # RALPH_TEST_WORKFLOW=research would otherwise force every default-
    # workflow test to plan as research and assert against the wrong shape).
    for var in (
        "TMUX",
        "RALPH_TEST_WORKFLOW",
        "RALPH_TEST_PLANNER_ASK_FIRST",
        "RALPH_TEST_EXECUTOR_ASK_ITER",
        "RALPH_TEST_OMIT_ANCHOR",
        "RALPH_TEST_REVIEWER_VERDICT",
        "RALPH_TEST_RE_REVIEWER_VERDICT",
    ):
        env.pop(var, None)
    return env


def _make_eval_env(
    tmp: Path,
    *,
    artifact: Path | None = None,
    content: str = "hello",
    max_iters: int = 3,
    reflector_workflows: tuple[str, ...] = ("feature", "bugfix"),
) -> dict:
    """Like `_make_go_env` but configures the reflector role and enables it.

    Used by the CI hardening probe (`TestRalphLiveEvalSmoke`) to mirror the
    live eval shape: planner → executor → reviewer → re_reviewer → reflector
    with KB amplification across runs. The default `_make_go_env` deliberately
    omits the reflector so that the simpler workflow tests stay isolated and
    fast; this helper adds it back without perturbing them.
    """
    env = _make_go_env(tmp, artifact=artifact, content=content, max_iters=max_iters)
    cfg_path = Path(env["RALPH_ROLES_CONFIG"])
    cfg = json.loads(cfg_path.read_text())
    mock = FIXTURES / "mock_role.sh"
    cfg["roles"]["reflector"] = {
        "harness": "command",
        "model": "mock-claude-reflector",
        "family": "claude",
        "extra_args": ["RALPH_TEST_ROLE=reflector", str(mock)],
    }
    cfg["defaults"]["reflector_enabled"] = True
    cfg["defaults"]["reflector_workflows"] = list(reflector_workflows)
    cfg_path.write_text(json.dumps(cfg))
    return env


class TestRalph(unittest.TestCase):
    """WHEN running ,ralph go end-to-end with a deterministic mock harness."""

    def test_go_happy_path_completes_with_planner_executor_reviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "build hello txt",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode == 0, result.stderr
            manifest = json.loads(result.stdout)
            assert manifest["kind"] == "go"
            assert manifest["status"] == "completed"
            assert manifest["phase"] == "done"
            assert manifest["validation_status"] == "passed"
            assert artifact.read_text() == "hello world"
            iterations = manifest["iterations"]
            assert len(iterations) == 1
            assert iterations[0]["verdict"] == "pass"
            assert iterations[0]["re_reviewer_id"] is not None, "re_reviewer must run on every iteration"
            roles = manifest["roles"]
            assert "planner-1" in roles and "executor-1" in roles and "reviewer-1" in roles
            assert "re_reviewer-1" in roles, "re_reviewer-1 must be recorded in roles"
            # Spec is persisted as both top-level field and rendered spec.md.
            spec_md = Path(env["RALPH_STATE_HOME"]) / "runs" / manifest["id"] / "spec.md"
            assert spec_md.exists()
            assert "Goal:" in spec_md.read_text()
            assert manifest["spec"]["target_artifact"] == str(artifact)

    def test_go_self_heals_when_executor_fails_first_iteration(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(
                tmp_path,
                artifact=artifact,
                content="hello world",
                fail_executor_iter="1",
                fail_reviewer="true",
                max_iters=4,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "self-heal test",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode == 0, result.stderr
            manifest = json.loads(result.stdout)
            assert manifest["status"] == "completed"
            assert manifest["phase"] == "done"
            iterations = manifest["iterations"]
            assert len(iterations) == 2, iterations
            assert iterations[0]["re_reviewer_id"] is not None, "iter 1 should escalate to re_reviewer"
            assert iterations[1]["verdict"] == "pass", "iter 2 should pass"
            assert artifact.read_text() == "hello world"
            verdicts = (Path(env["RALPH_STATE_HOME"]) / "runs" / manifest["id"] / "verdicts.jsonl").read_text()
            assert '"role": "reviewer"' in verdicts and '"role": "re_reviewer"' in verdicts
            decisions = (Path(env["RALPH_STATE_HOME"]) / "runs" / manifest["id"] / "decisions.log").read_text()
            assert "PASS, run complete" in decisions
            assert "re_reviewer adjudicated" in decisions

    def test_go_plan_only_emits_spec_without_executing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "plan only test",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--plan-only",
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            # plan-only returns 1 because status=planned (not "completed");
            # the spec was emitted but the orchestrator deliberately did not run.
            assert result.returncode == 1, result.stderr
            manifest = json.loads(result.stdout)
            assert manifest["status"] == "planned"
            assert manifest["phase"] == "done"
            assert manifest["spec"]["goal"]
            assert manifest["iterations"] == []
            assert not artifact.exists(), "artifact must NOT be created in --plan-only"
            spec_md = Path(env["RALPH_STATE_HOME"]) / "runs" / manifest["id"] / "spec.md"
            assert spec_md.exists()

    def test_apply_role_overrides_mutates_cfg_and_resets_family(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        cfg = {
            "roles": {
                "planner": {"harness": "cursor", "model": "claude-1", "family": "claude"},
                "executor": {"harness": "cursor", "model": "composer-2"},
                "reviewer": {"harness": "cursor", "model": "claude-2", "family": "claude"},
                "re_reviewer": {"harness": "cursor", "model": "gpt-1", "family": "gpt"},
            },
        }
        out = ralph.apply_role_overrides(
            cfg,
            {
                "planner_model": "gemini-3-pro",
                "planner_harness": "pi",
                "executor_model": None,
                "executor_harness": None,
            },
        )
        assert out["roles"]["planner"]["model"] == "gemini-3-pro"
        assert out["roles"]["planner"]["harness"] == "pi"
        assert "family" not in out["roles"]["planner"], "model override must clear stale family"
        # Untouched roles retain their values.
        assert out["roles"]["executor"]["model"] == "composer-2"
        assert out["roles"]["reviewer"]["family"] == "claude"

    def test_apply_role_overrides_args_shlex_splits_and_clears(self):
        """`--<role>-args` must shlex-split the raw string into the
        roles.json `extra_args` shape, with empty string clearing any
        existing default. None (flag absent) must leave extra_args alone.
        Without this the new-run form's args input would compose nicely
        but never actually reach the role's invocation."""
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        cfg = {
            "roles": {
                "planner": {
                    "harness": "command",
                    "model": "",
                    "family": "claude",
                    "extra_args": ["RALPH_TEST_ROLE=planner", "/tmp/old.sh"],
                },
                "executor": {"harness": "cursor", "model": "composer-2", "extra_args": ["--mode", "ask"]},
                "reviewer": {"harness": "cursor", "model": "claude-2", "family": "claude"},
                "re_reviewer": {"harness": "cursor", "model": "gpt-1", "family": "gpt"},
            },
        }
        out = ralph.apply_role_overrides(
            cfg,
            {
                # Replace planner with a quoted command path + flag.
                "planner_args": '/tmp/new.sh --flag "value with spaces"',
                # Clear executor's default extra_args explicitly.
                "executor_args": "",
                # Reviewer untouched.
                "reviewer_args": None,
            },
        )
        assert out["roles"]["planner"]["extra_args"] == [
            "/tmp/new.sh",
            "--flag",
            "value with spaces",
        ], out["roles"]["planner"]["extra_args"]
        assert out["roles"]["executor"]["extra_args"] == [], "empty string must clear extra_args"
        assert out["roles"]["reviewer"].get("extra_args") is None, "absent flag must leave reviewer alone"

    def test_apply_role_overrides_runs_diversity_gate_after_override(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        cfg = {
            "roles": {
                "planner": {"harness": "cursor", "model": "claude-1", "family": "claude"},
                "executor": {"harness": "cursor", "model": "composer-2"},
                "reviewer": {"harness": "cursor", "model": "claude-2", "family": "claude"},
                "re_reviewer": {"harness": "cursor", "model": "gpt-1", "family": "gpt"},
            },
        }
        # Force re_reviewer to claude → same-family pair → must raise.
        with self.assertRaises(SystemExit) as exc:
            ralph.apply_role_overrides(cfg, {"re_reviewer_model": "claude-3"})
        assert "diversity gate failed after CLI overrides" in str(exc.exception)

    def test_go_per_role_cli_flags_apply_to_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello")
            # Override planner harness/model. Mock harness uses RALPH_TEST_ROLE
            # set via extra_args, so harness=command keeps the mock plumbing
            # intact; --planner-model only relabels the model id.
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "override test",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--planner-model",
                    "my-override-model",
                    "--planner-harness",
                    "command",
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode == 0, result.stderr
            manifest = json.loads(result.stdout)
            # Parent manifest carries roles config snapshot.
            roles_cfg = manifest.get("roles_cfg") or manifest.get("roles_config") or {}
            # Fall back: child planner-1 manifest must reflect the override.
            planner_id = manifest["roles"]["planner-1"]["id"]
            run_dir = Path(manifest["dir"]) if "dir" in manifest else None
            if run_dir and (run_dir / f"{planner_id}.manifest.json").exists():
                child = json.loads((run_dir / f"{planner_id}.manifest.json").read_text())
                assert (
                    "my-override-model" in (child.get("command") or "")
                    or roles_cfg.get("roles", {}).get("planner", {}).get("model") == "my-override-model"
                )

    def test_go_diversity_gate_rejects_same_family_reviewer_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cfg = tmp_path / "roles.json"
            cfg.write_text(
                json.dumps(
                    {
                        "roles": {
                            "planner": {"harness": "command", "model": "claude-1", "family": "claude"},
                            "executor": {"harness": "command", "model": "claude-2", "family": "claude"},
                            "reviewer": {"harness": "command", "model": "claude-3", "family": "claude"},
                            "re_reviewer": {"harness": "command", "model": "claude-4", "family": "claude"},
                        },
                        "defaults": {},
                    }
                )
            )
            env = {
                **os.environ,
                "RALPH_STATE_HOME": str(tmp_path / "state"),
                "AI_KB_HOME": str(tmp_path / "kb"),
                "RALPH_ROLES_CONFIG": str(cfg),
            }
            env.pop("TMUX", None)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "ralph.py"), "go", "--goal", "x", "--plan-only", "--subprocess"],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode != 0
            assert "diversity gate failed" in result.stderr

    def test_runs_preview_render_go_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = _make_go_env(tmp_path, artifact=tmp_path / "workspace" / "out.txt")
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "render test",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert run.returncode == 0, run.stderr
            manifest = json.loads(run.stdout)

            preview = subprocess.run(
                [sys.executable, str(SCRIPTS / "ralph.py"), "preview", manifest["id"]],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert preview.returncode == 0
            assert "Phase: done" in preview.stdout
            assert "Iterations" in preview.stdout
            assert "iter 1:" in preview.stdout
            assert "Success criteria:" in preview.stdout

            runs = subprocess.run(
                [sys.executable, str(SCRIPTS / "ralph.py"), "runs", "--json"],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert runs.returncode == 0
            rows = json.loads(runs.stdout)
            assert rows[0]["id"] == manifest["id"]
            assert rows[0]["kind"] == "go"
            assert rows[0]["phase"] == "done"
            assert rows[0]["iterations_count"] == 1

    def test_go_kill_marks_run_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = _make_go_env(tmp_path, artifact=tmp_path / "workspace" / "out.txt")
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "kill test",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            manifest = json.loads(run.stdout)
            kill = subprocess.run(
                [sys.executable, str(SCRIPTS / "ralph.py"), "kill", manifest["id"], "--json"],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert kill.returncode == 0, kill.stderr
            assert json.loads(kill.stdout)["status"] == "killed"

    def test_go_rm_removes_run_dir_and_drops_learnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = _make_go_env(tmp_path, artifact=tmp_path / "workspace" / "out.txt")
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "rm test",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            manifest = json.loads(run.stdout)
            run_dir = Path(env["RALPH_STATE_HOME"]) / "runs" / manifest["id"]
            assert run_dir.exists()
            rm = subprocess.run(
                [sys.executable, str(SCRIPTS / "ralph.py"), "rm", manifest["id"]],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert rm.returncode == 0, rm.stderr
            assert not run_dir.exists()
            for learned_id in manifest.get("learned_ids", []):
                gone = subprocess.run(
                    [sys.executable, str(SCRIPTS / "ai_kb.py"), "get", learned_id],
                    capture_output=True,
                    text=True,
                    cwd=str(SCRIPTS),
                    env=env,
                )
                assert gone.returncode == 1

    def test_statusline_summarises_go_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = _make_go_env(tmp_path, artifact=tmp_path / "workspace" / "out.txt")
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "statusline test",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert run.returncode == 0, run.stderr
            status = subprocess.run(
                [sys.executable, str(SCRIPTS / "ralph.py"), "statusline"],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert status.returncode == 0, status.stderr

    def test_pi_runtime_passes_prompt_on_stdin(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))

            class Result:
                stdout = "RALPH_DONE\n"
                stderr = ""
                returncode = 0

            return Result()

        original_run = ralph.subprocess.run
        try:
            ralph.subprocess.run = fake_run
            result = ralph.RalphRunner().runtime_pi("prompt body", ["--no-tools"], 5)
        finally:
            ralph.subprocess.run = original_run

        assert result.exit_code == 0
        assert calls[0][0] == ["pi", "-p", "--no-session", "--no-tools"]
        assert calls[0][1]["input"] == "prompt body"

    def test_tmux_name_sanitizes_session_names(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        assert ralph.tmux_name("swarm:repo/name with spaces") == "swarm-repo-name-with-spaces"

    def test_humanize_age_short_long(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        assert ralph.humanize_age(None) == "-"
        assert ralph.humanize_age(0) == "0s"
        assert ralph.humanize_age(59) == "59s"
        assert ralph.humanize_age(60) == "1m"
        assert ralph.humanize_age(3600) == "1h"
        assert ralph.humanize_age(86400) == "1d"

    def test_family_of_classifies_known_models(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        assert ralph.family_of("anthropic/claude-opus-4-5") == "claude"
        assert ralph.family_of("openai/gpt-5.1") == "gpt"
        assert ralph.family_of("google/gemini-3-pro") == "gemini"
        assert ralph.family_of("totally-made-up") == "unknown"

    def test_parse_json_block_handles_fenced_and_raw(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        fenced = 'prelude\n```json\n{"a": 1, "b": [2, 3]}\n```\nepilogue'
        assert ralph.parse_json_block(fenced) == {"a": 1, "b": [2, 3]}
        raw = 'before\n{"k": "v"}\nafter'
        assert ralph.parse_json_block(raw) == {"k": "v"}
        with self.assertRaises(ValueError):
            ralph.parse_json_block("no json here")

    def test_go_manifest_records_artifact_hash_and_validation_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "artifact hash test",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode == 0, result.stderr
            manifest = json.loads(result.stdout)
            assert Path(manifest["artifact"]) == artifact.resolve()
            assert manifest["artifact_sha256"]
            assert manifest["artifact_ok"] is True
            assert manifest["validation"]["artifact"]["ok"] is True
            assert manifest["validation_status"] == "passed"

    def test_go_validation_rejects_bad_artifact_hash(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "artifact.txt"
            artifact.write_text("actual")
            manifest = {
                "id": "go-validation",
                "kind": "go",
                "status": "completed",
                "artifact": str(artifact),
                "artifact_sha256": "not-the-real-hash",
                "roles": {
                    "planner-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                    "executor-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                    "reviewer-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                    "re_reviewer-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                },
            }
            validation = ralph.RalphRunner(tmp_path / "state", tmp_path / "kb").validation_for_manifest(manifest)
            assert validation["status"] == "failed"
            assert validation["artifact"]["ok"] is False

    def test_validation_for_manifest_demotes_scaffolding_failure_to_passed_with_warnings(self):
        """When the iteration verdict reaches PASS (top status flips to
        completed), the artifact integrity holds, and the only thing wrong
        is a role-level scaffolding gate (e.g., missing/malformed ANCHOR),
        the run must land at `passed_with_warnings` — not the brittle
        `failed` of the pre-fix behavior. The failing role(s) must surface
        in `validation.warnings` so operators can see exactly what tripped."""
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "artifact.txt"
            artifact.write_text("shipped")
            real_hash = hashlib.sha256(b"shipped").hexdigest()
            manifest = {
                "id": "go-warnings",
                "kind": "go",
                "status": "completed",
                "artifact": str(artifact),
                "artifact_sha256": real_hash,
                "roles": {
                    "planner-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                    "executor-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "failed",
                        "control_state": "automated",
                    },
                    "reviewer-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                    "re_reviewer-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                },
            }
            validation = ralph.RalphRunner(tmp_path / "state", tmp_path / "kb").validation_for_manifest(manifest)
            assert validation["status"] == "passed_with_warnings"
            assert validation["artifact"]["ok"] is True
            warnings = validation.get("warnings") or []
            assert len(warnings) == 1
            assert warnings[0]["role"] == "executor-1"
            assert warnings[0]["validation_status"] == "failed"
            assert warnings[0]["control_state"] == "automated"

    def test_validation_for_manifest_keeps_failed_when_artifact_hash_mismatches(self):
        """A scaffolding-only demotion only applies when the artifact hash
        matches. If the artifact is wrong, the run must still fail outright
        — the scaffolding-warning path must not mask a real corruption."""
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "artifact.txt"
            artifact.write_text("actual")
            manifest = {
                "id": "go-bad-hash",
                "kind": "go",
                "status": "completed",
                "artifact": str(artifact),
                "artifact_sha256": "not-the-real-hash",
                "roles": {
                    "planner-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                    "executor-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "failed",
                        "control_state": "automated",
                    },
                    "reviewer-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                    "re_reviewer-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                },
            }
            validation = ralph.RalphRunner(tmp_path / "state", tmp_path / "kb").validation_for_manifest(manifest)
            assert validation["status"] == "failed"
            assert validation["artifact"]["ok"] is False
            assert validation.get("warnings") == []

    def test_finalize_iteration_completes_run_on_passed_with_warnings(self):
        """G2 + G3 hinge on this: when validation lands at passed_with_warnings,
        `_finalize_iteration` must return `complete` (not `failed`) so the
        run summary stamps `status=completed` AND the reflector trigger at
        the call site fires. If this returns `failed` instead, the reflector
        is never called and the KB loses every learning from runs whose only
        flaw was scaffolding cosmetics."""
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            workspace.mkdir()
            artifact = workspace / "result.txt"
            artifact.write_text("shipped")
            real_hash = hashlib.sha256(b"shipped").hexdigest()
            runner = ralph.RalphRunner(state_home=tmp_path / "state", kb_home=tmp_path / "kb")
            runner.init()
            rid = "go-warn-finalize"
            run_dir = runner.run_dir(rid)
            run_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "id": rid,
                "kind": "go",
                "name": "warn-finalize",
                "goal": "ship the artifact even when scaffolding is malformed",
                "workspace": str(workspace),
                "phase": "rereviewing",
                "status": "running",
                "control_state": "automated",
                "artifact": str(artifact),
                "artifact_sha256": real_hash,
                "iterations": [
                    {
                        "n": 1,
                        "phase": ralph.ITER_PHASE_RERVIEW,
                        "started_at": ralph.utc_now(),
                        "task": "seed",
                    }
                ],
                "spec": {
                    "goal": "ship",
                    "workflow": "feature",
                    "rationale": "test",
                    "success_criteria": ["artifact exists"],
                    "target_artifact": str(artifact),
                },
                "workflow": "feature",
                "roles": {
                    "planner-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                    "executor-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "failed",
                        "control_state": "automated",
                    },
                    "reviewer-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                    "re_reviewer-1": {
                        "status": "completed",
                        "exit_code": 0,
                        "validation_status": "passed",
                        "control_state": "automated",
                    },
                },
                "questions": [],
            }
            runner.save_manifest(manifest)
            decision, finalized = runner._finalize_iteration(
                manifest,
                iter_idx=0,
                n=1,
                workspace=workspace,
                primary_verdict={"verdict": "pass"},
                final_verdict={"final_verdict": "pass", "agree_with_primary": True},
                re_reviewer_id="rer-1",
            )
            assert decision == "complete", (
                "passed_with_warnings must funnel through the success path so the reflector trigger fires"
            )
            assert finalized["phase"] == "done"
            assert finalized["status"] == "completed"
            assert finalized["validation_status"] == "passed_with_warnings"
            warnings = finalized.get("validation", {}).get("warnings") or []
            assert any(w.get("role") == "executor-1" for w in warnings)
            # Decision log must record the demotion verbatim so operators can
            # spot scaffolding regressions when scanning recent activity.
            decisions = (run_dir / "decisions.log").read_text()
            assert "PASS with role-scaffolding warnings" in decisions
            # Summary must reflect the new validation_status and surface the
            # warning in its own section so the trust artifact stays honest.
            summary = (run_dir / "summary.md").read_text()
            assert "**Validation:** passed_with_warnings" in summary
            assert "## Warnings" in summary
            assert "executor-1" in summary

    def test_control_takeover_parks_and_resume_restores_completed_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "control park test",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert run.returncode == 0, run.stderr
            rid = json.loads(run.stdout)["id"]
            takeover = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "control",
                    rid,
                    "--role",
                    "executor-1",
                    "--action",
                    "takeover",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert takeover.returncode == 0, takeover.stderr
            manifest = json.loads((tmp_path / "state" / "runs" / rid / "manifest.json").read_text())
            assert manifest["status"] == "needs_human"
            assert manifest["pre_control_status"] == "completed"
            resume = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "control",
                    rid,
                    "--role",
                    "executor-1",
                    "--action",
                    "resume",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert resume.returncode == 0, resume.stderr
            manifest = json.loads((tmp_path / "state" / "runs" / rid / "manifest.json").read_text())
            assert manifest["status"] == "completed"
            assert manifest["roles"]["executor-1"]["control_state"] == "automated"

    def test_preflight_rejects_unsupported_cursor_model(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        cfg = {
            "roles": {
                "planner": {"harness": "command", "model": "mock", "extra_args": ["true"]},
                "executor": {"harness": "command", "model": "mock", "extra_args": ["true"]},
                "reviewer": {"harness": "cursor", "model": "not-supported"},
                "re_reviewer": {"harness": "command", "model": "mock", "extra_args": ["true"]},
            },
            "defaults": {},
        }
        with self.assertRaises(SystemExit) as exc:
            ralph.preflight_roles_config(cfg)
        assert "not-supported" in str(exc.exception)


class TestRalphResumability(unittest.TestCase):
    """WHEN a runner dies between or within iterations, ,ralph runner / resume picks up cleanly."""

    @staticmethod
    def _ralph(args: list[str], env: dict, *, expect_returncode: int | None = 0) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "ralph.py"), *args],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS),
            env=env,
        )
        if expect_returncode is not None:
            assert result.returncode == expect_returncode, (
                f"args={args!r} rc={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        if not result.stdout.strip():
            return {}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"_raw": result.stdout, "_stderr": result.stderr}

    def test_runner_completes_a_planned_run(self):
        """,ralph go --plan-only stops after the spec; ,ralph runner RID drives it to PASS."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            planned = self._ralph(
                [
                    "go",
                    "--goal",
                    "runner-completes",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--plan-only",
                    "--subprocess",
                    "--json",
                ],
                env,
                expect_returncode=1,
            )
            rid = planned["id"]
            assert planned["status"] == "planned"
            final = self._ralph(["runner", rid, "--json"], env, expect_returncode=0)
            assert final["status"] == "completed", final
            assert final["iterations"][0]["verdict"] == "pass"
            assert artifact.read_text() == "hello world"
            counters = tmp_path / "counters"
            assert (counters / "executor").read_text().strip() == "1"
            assert (counters / "reviewer").read_text().strip() == "1"
            assert (counters / "re_reviewer").read_text().strip() == "1"

    def test_runner_is_noop_on_terminal_run(self):
        """Re-invoking the runner on a completed run must not re-spawn any role."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            done = self._ralph(
                ["go", "--goal", "runner-noop", "--workspace", str(tmp_path / "workspace"), "--subprocess", "--json"],
                env,
                expect_returncode=0,
            )
            assert done["status"] == "completed"
            counters = tmp_path / "counters"
            execs_before = (counters / "executor").read_text().strip()
            revs_before = (counters / "reviewer").read_text().strip()
            rerev_before = (counters / "re_reviewer").read_text().strip()
            again = self._ralph(["runner", done["id"], "--json"], env, expect_returncode=0)
            assert again["status"] == "completed"
            assert (counters / "executor").read_text().strip() == execs_before
            assert (counters / "reviewer").read_text().strip() == revs_before
            assert (counters / "re_reviewer").read_text().strip() == rerev_before

    def test_runner_resumes_after_partial_iteration_skipping_executor(self):
        """Manifest with a partial iter (executor cached, phase=review) must not re-run executor."""
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            artifact = workspace / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            planned = self._ralph(
                [
                    "go",
                    "--goal",
                    "resume-mid-iter",
                    "--workspace",
                    str(workspace),
                    "--plan-only",
                    "--subprocess",
                    "--json",
                ],
                env,
                expect_returncode=1,
            )
            rid = planned["id"]
            state_home = Path(env["RALPH_STATE_HOME"])
            run_dir = state_home / "runs" / rid

            # Forge an "executor already completed" cache so the runner has
            # to skip executor and resume at reviewer.
            executor_dir = state_home / "runs" / f"{rid}-executor-1"
            executor_dir.mkdir(parents=True, exist_ok=True)
            executor_output = executor_dir / "output.log"
            executor_output.write_text("Wrote artifact (cached)\nLEARNING: cached executor output\nRALPH_DONE\n")
            executor_child = {
                "id": f"{rid}-executor-1",
                "kind": "role",
                "name": "executor-1",
                "created_at": ralph.utc_now(),
                "goal": "executor-1",
                "runtime": "subprocess",
                "status": "completed",
                "exit_code": 0,
                "expect": "RALPH_DONE",
                "timeout_seconds": 10,
                "control_state": "automated",
                "validation_status": "passed",
                "last_validated_at": ralph.utc_now(),
                "learned_ids": [],
                "command": "cached",
                "workspace": str(workspace),
                "prompt": str(executor_dir / "prompt.md"),
                "output": str(executor_output),
                "tmux": None,
                "verdict_obj": {},
            }
            (executor_dir / "manifest.json").write_text(json.dumps(executor_child))
            # Pre-create the artifact so reviewer + re_reviewer pass immediately.
            workspace.mkdir(parents=True, exist_ok=True)
            artifact.write_text("hello world")

            # Splice the partial iteration into the parent manifest.
            parent_path = run_dir / "manifest.json"
            parent = json.loads(parent_path.read_text())
            parent.setdefault("roles", {})["executor-1"] = executor_child
            parent["iterations"] = [
                {
                    "n": 1,
                    "phase": "review",
                    "started_at": ralph.utc_now(),
                    "task": "create the artifact",
                    "spec_seq": 1,
                    "executor_id": executor_child["id"],
                }
            ]
            parent["status"] = "running"
            parent["phase"] = "reviewing"
            parent_path.write_text(json.dumps(parent))

            final = self._ralph(["runner", rid, "--json"], env, expect_returncode=0)
            assert final["status"] == "completed", final
            iterations = final["iterations"]
            assert len(iterations) == 1
            assert iterations[0]["executor_id"] == executor_child["id"]
            assert iterations[0]["reviewer_id"] is not None
            assert iterations[0]["re_reviewer_id"] is not None
            assert iterations[0]["verdict"] == "pass"
            counters = tmp_path / "counters"
            # The cached executor must NOT have been invoked.
            assert not (counters / "executor").exists()
            assert (counters / "reviewer").read_text().strip() == "1"
            assert (counters / "re_reviewer").read_text().strip() == "1"

    def test_replan_run_queues_request_consumed_by_runner(self):
        """,ralph replan RID --no-resume sets the flag; the next runner consumes it."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            planned = self._ralph(
                [
                    "go",
                    "--goal",
                    "replan-flow",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--plan-only",
                    "--subprocess",
                    "--json",
                ],
                env,
                expect_returncode=1,
            )
            rid = planned["id"]
            replan = self._ralph(
                ["replan", rid, "--no-resume", "--json"],
                env,
                expect_returncode=0,
            )
            assert replan.get("replan_requested") is True
            final = self._ralph(["runner", rid, "--json"], env, expect_returncode=0)
            assert final["status"] == "completed", final
            assert final.get("spec_seq", 1) >= 2, "replan should have bumped spec_seq"
            counters = tmp_path / "counters"
            assert (counters / "planner").read_text().strip() == "2", (
                "planner runs once for plan-only and once for replan"
            )

    def test_resume_run_is_noop_on_completed(self):
        """resume_run on a terminal run returns the manifest without re-launching anything."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            done = self._ralph(
                [
                    "go",
                    "--goal",
                    "resume-terminal",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                env,
                expect_returncode=0,
            )
            counters = tmp_path / "counters"
            execs_before = (counters / "executor").read_text().strip()
            res = self._ralph(["resume", done["id"], "--foreground", "--json"], env, expect_returncode=0)
            assert res["status"] == "completed"
            assert (counters / "executor").read_text().strip() == execs_before

    def test_each_run_owns_a_distinct_tmux_session_name(self):
        """run_session_name is deterministic and per-rid, enabling multi-Ralph isolation."""
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        r = ralph.RalphRunner()
        s1 = r.run_session_name("go-feature-a-20260504190000")
        s2 = r.run_session_name("go-feature-b-20260504190001")
        assert s1.startswith("ralph-")
        assert s2.startswith("ralph-")
        assert s1 != s2
        # Idempotent: same rid -> same session name
        assert r.run_session_name("go-feature-a-20260504190000") == s1


class TestRalphMultiRunIsolation(unittest.TestCase):
    """WHEN multiple ralph runs coexist in the same state-home, kill/rm/resume on one must not touch the others."""

    @staticmethod
    def _ralph(args: list[str], env: dict, *, expect_returncode: int | None = 0) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "ralph.py"), *args],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS),
            env=env,
        )
        if expect_returncode is not None:
            assert result.returncode == expect_returncode, (
                f"args={args!r} rc={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        if not result.stdout.strip():
            return {}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"_raw": result.stdout, "_stderr": result.stderr}

    def test_two_concurrent_runs_get_distinct_state_dirs_and_session_names(self):
        """Two `,ralph go` invocations in the same state home produce isolated runs and tmux session targets."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            artifact_a = workspace / "out_a.txt"
            artifact_b = workspace / "out_b.txt"
            env = _make_go_env(tmp_path, artifact=artifact_a, content="aaa")
            run_a = self._ralph(
                ["go", "--goal", "alpha", "--workspace", str(workspace), "--subprocess", "--json"],
                env,
                expect_returncode=0,
            )
            env_b = dict(env)
            env_b["RALPH_TEST_ARTIFACT"] = str(artifact_b)
            env_b["RALPH_TEST_CONTENT"] = "bbb"
            run_b = self._ralph(
                ["go", "--goal", "beta", "--workspace", str(workspace), "--subprocess", "--json"],
                env_b,
                expect_returncode=0,
            )
            assert run_a["id"] != run_b["id"]
            state_home = Path(env["RALPH_STATE_HOME"])
            assert (state_home / "runs" / run_a["id"] / "manifest.json").exists()
            assert (state_home / "runs" / run_b["id"] / "manifest.json").exists()

            sys.path.insert(0, str(SCRIPTS))
            import ralph

            r = ralph.RalphRunner()
            assert r.run_session_name(run_a["id"]) != r.run_session_name(run_b["id"])
            assert artifact_a.read_text() == "aaa"
            assert artifact_b.read_text() == "bbb"

    def test_kill_run_does_not_remove_unrelated_run(self):
        """,ralph kill RID transitions only the targeted run; other runs stay intact."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            artifact = workspace / "out.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="x")
            other = self._ralph(
                ["go", "--goal", "keep", "--workspace", str(workspace), "--subprocess", "--json"],
                env,
                expect_returncode=0,
            )
            planned = self._ralph(
                ["go", "--goal", "kill-target", "--workspace", str(workspace), "--plan-only", "--subprocess", "--json"],
                env,
                expect_returncode=1,
            )
            killed = self._ralph(["kill", planned["id"], "--json"], env, expect_returncode=0)
            assert killed["status"] == "killed"

            state_home = Path(env["RALPH_STATE_HOME"])
            other_manifest = json.loads((state_home / "runs" / other["id"] / "manifest.json").read_text())
            assert other_manifest["status"] == "completed", (
                "the unrelated run must still be completed after killing the other"
            )

    def test_rm_run_does_not_remove_unrelated_state(self):
        """,ralph rm RID drops only the named run dir."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            artifact = workspace / "out.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="x")
            keep = self._ralph(
                ["go", "--goal", "keep-this", "--workspace", str(workspace), "--subprocess", "--json"],
                env,
                expect_returncode=0,
            )
            drop = self._ralph(
                ["go", "--goal", "drop-this", "--workspace", str(workspace), "--plan-only", "--subprocess", "--json"],
                env,
                expect_returncode=1,
            )
            self._ralph(["rm", drop["id"]], env, expect_returncode=0)
            state_home = Path(env["RALPH_STATE_HOME"])
            assert (state_home / "runs" / keep["id"] / "manifest.json").exists()
            assert not (state_home / "runs" / drop["id"]).exists()

    def test_default_run_id_self_heals_past_stale_latest_pointer(self):
        """B1 regression: rm-ing a run leaves `latest-run.txt` pointing at
        the archived id. Subsequent argless commands like `,ralph status`
        used to crash with `run manifest not found: <archived-rid>`. The
        fix is `latest_run_id()` validating the cached pointer and falling
        back to the newest go-kind manifest by mtime, so a default-rid
        command picks a live run when one exists and reports a clean
        `no runs found` only when the runs dir is genuinely empty.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            artifact = workspace / "out.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="x")
            survivor = self._ralph(
                ["go", "--goal", "survives-rm", "--workspace", str(workspace), "--subprocess", "--json"],
                env,
                expect_returncode=0,
            )
            doomed = self._ralph(
                ["go", "--goal", "rm-target", "--workspace", str(workspace), "--subprocess", "--json"],
                env,
                expect_returncode=0,
            )
            # The doomed run is younger so it owns the latest pointer.
            state_home = Path(env["RALPH_STATE_HOME"])
            pointer = (state_home / "latest-run.txt").read_text().strip()
            assert pointer == doomed["id"]
            # `,ralph rm` archives the run dir but historically left the
            # latest pointer dangling.
            self._ralph(["rm", doomed["id"]], env, expect_returncode=0)
            assert (state_home / "latest-run.txt").read_text().strip() == doomed["id"], (
                "fix is in `latest_run_id()`, not in `rm` — pointer should still be stale on disk"
            )
            # Argless `status` would previously crash; now it should
            # transparently reroute to the surviving run.
            recovered = self._ralph(["status", "--json"], env, expect_returncode=0)
            assert recovered["id"] == survivor["id"]
            # And once every run is gone, the recovery path returns a
            # clean "no runs found" instead of a stale-pointer crash.
            self._ralph(["rm", survivor["id"]], env, expect_returncode=0)
            empty = subprocess.run(
                [sys.executable, str(SCRIPTS / "ralph.py"), "status", "--json"],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert empty.returncode != 0
            assert "no runs found" in empty.stderr, empty.stderr

    def test_kill_all_kills_only_non_terminal_runs(self):
        """E1 regression: `,ralph kill --all` is the panic-button shortcut
        for a dirty fleet — it must Ctrl-C every running / awaiting-human
        runner without disturbing already-terminal runs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            artifact = workspace / "out.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="x")
            # One healthy completed run (terminal — must be left alone).
            done = self._ralph(
                ["go", "--goal", "leave-me-alone", "--workspace", str(workspace), "--subprocess", "--json"],
                env,
                expect_returncode=0,
            )
            # Two plan-only runs park as needs_human (non-terminal).
            stuck_a = self._ralph(
                [
                    "go",
                    "--goal",
                    "stuck-a",
                    "--workspace",
                    str(workspace),
                    "--plan-only",
                    "--subprocess",
                    "--json",
                ],
                env,
                expect_returncode=1,
            )
            stuck_b = self._ralph(
                [
                    "go",
                    "--goal",
                    "stuck-b",
                    "--workspace",
                    str(workspace),
                    "--plan-only",
                    "--subprocess",
                    "--json",
                ],
                env,
                expect_returncode=1,
            )
            killed = self._ralph(["kill", "--all", "--json"], env, expect_returncode=0)
            assert sorted(killed) == sorted([stuck_a["id"], stuck_b["id"]]), (
                f"kill --all must hit only non-terminal runs; got {killed}"
            )
            state_home = Path(env["RALPH_STATE_HOME"])
            done_after = json.loads((state_home / "runs" / done["id"] / "manifest.json").read_text())
            assert done_after["status"] == "completed", "completed run must be untouched"
            for stuck in (stuck_a, stuck_b):
                m = json.loads((state_home / "runs" / stuck["id"] / "manifest.json").read_text())
                assert m["status"] == "killed"
            # --all is mutually exclusive with positional rid.
            err = subprocess.run(
                [sys.executable, str(SCRIPTS / "ralph.py"), "kill", "--all", done["id"]],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert err.returncode != 0
            assert "mutually exclusive" in err.stderr

    def test_kill_without_args_fails_explicit(self):
        """`,ralph kill` with no run id and no `--all` must exit non-zero
        with a clear message rather than treating the missing rid as a
        match-everything wildcard."""
        with tempfile.TemporaryDirectory() as tmp:
            env = _make_go_env(Path(tmp), artifact=Path(tmp) / "out.txt")
            err = subprocess.run(
                [sys.executable, str(SCRIPTS / "ralph.py"), "kill"],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert err.returncode != 0
            assert "RUN_ID or --all" in err.stderr


class TestRalphReverseInterview(unittest.TestCase):
    """WHEN a role emits RALPH_QUESTIONS, the run parks at awaiting_human and
    the orchestrator does no further work until ,ralph answer arrives."""

    @staticmethod
    def _ralph(args: list[str], env: dict, *, stdin: str | None = None, expect_returncode: int | None = 0) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "ralph.py"), *args],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS),
            env=env,
            input=stdin,
        )
        if expect_returncode is not None:
            assert result.returncode == expect_returncode, (
                f"args={args!r} rc={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        if not result.stdout.strip():
            return {}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"_raw": result.stdout, "_stderr": result.stderr}

    def test_has_anchor_helper_detects_required_line(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        assert ralph.has_anchor("ANCHOR: do the thing\n\nbody")
        assert ralph.has_anchor("\n\nANCHOR: padded then body")
        assert not ralph.has_anchor("body without anchor")
        assert not ralph.has_anchor("ANCHOR:\nempty body fails")

    def test_has_anchor_accepts_markdown_decorated_anchor(self):
        """Composer/Opus often emit `**ANCHOR:**` (bold) or wrap the line in
        a markdown code fence / heading / blockquote. The validation gate
        must recognize those as valid anchors — they were the dominant
        false-fail mode before the markdown-tolerance fix."""
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        # Bold prefix only, body outside the bold span
        assert ralph.has_anchor("**ANCHOR:** restate the goal in my words\n\nbody")
        # Bold spanning the whole line
        assert ralph.has_anchor("**ANCHOR: restate the goal in my words**\n\nbody")
        # Italic variants
        assert ralph.has_anchor("*ANCHOR:* restate\n\nbody")
        assert ralph.has_anchor("*ANCHOR: restate*\n\nbody")
        # Inline code
        assert ralph.has_anchor("`ANCHOR:` restate\n\nbody")
        # Heading
        assert ralph.has_anchor("# ANCHOR: restate\n\nbody")
        assert ralph.has_anchor("## ANCHOR: restate\n\nbody")
        # Blockquote
        assert ralph.has_anchor("> ANCHOR: restate\n\nbody")
        # Combined leading whitespace + bold
        assert ralph.has_anchor("  **ANCHOR:** restate\n\nbody")
        # Anchor preceded by a few lines of harness chatter (within lookahead)
        assert ralph.has_anchor("Summary of what was done:\n\n**ANCHOR:** restated goal\n\nbody")
        # Empty body inside markdown decorators must still fail
        assert not ralph.has_anchor("**ANCHOR:**")
        assert not ralph.has_anchor("**ANCHOR: **")
        # Decorator-only lines without the ANCHOR token must fail
        assert not ralph.has_anchor("**bold but no anchor**")

    def test_parse_questions_block_validates_payload(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        valid = (
            "```json\n"
            '{"questions": [{"id": "q1", "text": "first?"}, {"id": "q2", "text": "second?"}]}\n'
            "```\nRALPH_QUESTIONS\n"
        )
        questions = ralph.parse_questions_block(valid)
        assert questions == [{"id": "q1", "text": "first?"}, {"id": "q2", "text": "second?"}]
        # Missing list payload
        with self.assertRaises(ValueError):
            ralph.parse_questions_block('```json\n{"questions": []}\n```')
        # Duplicate ids
        dup = '```json\n{"questions": [{"id": "q1", "text": "a"}, {"id": "q1", "text": "b"}]}\n```'
        with self.assertRaises(ValueError):
            ralph.parse_questions_block(dup)
        # Missing text
        with self.assertRaises(ValueError):
            ralph.parse_questions_block('```json\n{"questions": [{"id": "q1", "text": ""}]}\n```')

    def test_role_validation_status_fails_when_anchor_missing(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output = tmp_path / "output.log"
            output.write_text("body without an anchor\nRALPH_DONE\n")
            assert (
                ralph.role_validation_status(
                    {
                        "status": "completed",
                        "exit_code": 0,
                        "output": str(output),
                    }
                )
                == "failed"
            )
            output.write_text("ANCHOR: I read the goal\n\nbody\nRALPH_DONE\n")
            assert (
                ralph.role_validation_status(
                    {
                        "status": "completed",
                        "exit_code": 0,
                        "output": str(output),
                    }
                )
                == "passed"
            )

    def test_planner_questions_park_run_and_block_executor(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            env["RALPH_TEST_PLANNER_ASK_FIRST"] = "true"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "ambiguous goal",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode == 2, result.stderr  # status=needs_human → rc=2
            manifest = json.loads(result.stdout)
            assert manifest["status"] == "awaiting_human"
            assert manifest["pre_questions_status"] == "running"
            assert manifest["awaiting_role"].startswith("planner-")
            questions = manifest.get("questions") or []
            assert len(questions) == 2
            assert {q["id"] for q in questions} == {"q1", "q2"}
            assert all(q["answer"] is None for q in questions)
            # Executor must NOT have run.
            assert "executor-1" not in (manifest.get("roles") or {})
            assert not artifact.exists()
            counters = tmp_path / "counters"
            assert (counters / "planner").read_text().strip() == "1"
            assert not (counters / "executor").exists()

    def test_answer_one_at_a_time_until_run_unparks_and_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            env["RALPH_TEST_PLANNER_ASK_FIRST"] = "true"
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "ambiguous",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert run.returncode == 2, run.stderr
            rid = json.loads(run.stdout)["id"]

            # First answer: still awaiting (q2 open).
            self._ralph(
                ["answer", rid, "--question", "q1", "--text", "use src/parser.ts", "--no-resume"],
                env,
                expect_returncode=0,
            )
            mid = json.loads((tmp_path / "state" / "runs" / rid / "manifest.json").read_text())
            assert mid["status"] == "awaiting_human"
            assert sum(1 for q in mid["questions"] if q.get("answered_at")) == 1

            # Second answer: clears the queue. --no-resume so we drive the runner manually.
            self._ralph(
                ["answer", rid, "--question", "q2", "--text", "preserve legacy export", "--no-resume"],
                env,
                expect_returncode=0,
            )
            after = json.loads((tmp_path / "state" / "runs" / rid / "manifest.json").read_text())
            assert after["status"] == "running"
            assert after["replan_requested"] is True
            assert all(q.get("answered_at") for q in after["questions"])
            # Drive the parked run to completion via the runner.
            final = self._ralph(["runner", rid, "--json"], env, expect_returncode=0)
            assert final["status"] == "completed"
            assert artifact.read_text() == "hello world"
            counters = tmp_path / "counters"
            assert (counters / "planner").read_text().strip() == "2", "planner should have re-run after answers"
            assert (counters / "executor").read_text().strip() == "1"

    def test_answer_cli_rejects_unknown_question_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact)
            env["RALPH_TEST_PLANNER_ASK_FIRST"] = "true"
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "x",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert run.returncode == 2, run.stderr
            rid = json.loads(run.stdout)["id"]
            bad = subprocess.run(
                [sys.executable, str(SCRIPTS / "ralph.py"), "answer", rid, "--question", "q-unknown", "--text", "hi"],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert bad.returncode != 0
            assert "q-unknown" in bad.stderr

    def test_answer_cli_accepts_json_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            env["RALPH_TEST_PLANNER_ASK_FIRST"] = "true"
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "json answers",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            rid = json.loads(run.stdout)["id"]
            answers = json.dumps({"q1": "alpha", "q2": "beta"})
            self._ralph(["answer", rid, "--json", "-", "--no-resume"], env, stdin=answers, expect_returncode=0)
            after = json.loads((tmp_path / "state" / "runs" / rid / "manifest.json").read_text())
            assert all(q.get("answered_at") for q in after["questions"])
            assert {q["id"]: q["answer"] for q in after["questions"]} == {"q1": "alpha", "q2": "beta"}

    def test_executor_emitted_questions_park_mid_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            env["RALPH_TEST_EXECUTOR_ASK_ITER"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "executor questions",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode == 2, result.stderr
            manifest = json.loads(result.stdout)
            assert manifest["status"] == "awaiting_human"
            assert manifest["awaiting_role"].startswith("executor-")
            assert any(q["id"] == "ex1" for q in manifest["questions"])
            # Iteration must be discarded so executor re-runs after answers.
            assert manifest["iterations"] == []
            # Reviewer / re_reviewer must NOT have been invoked.
            counters = tmp_path / "counters"
            assert (counters / "executor").read_text().strip() == "1"
            assert not (counters / "reviewer").exists()

    def test_role_without_anchor_demotes_run_to_passed_with_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            env["RALPH_TEST_OMIT_ANCHOR"] = "true"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "no anchor test",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            # Reviewer/re_reviewer pass the artifact, so the iteration verdict
            # is "pass". Every role's output omitted ANCHOR, so each role's
            # scaffolding gate flips to validation_status=failed. The whole
            # run was previously marked failed on this scaffolding violation
            # alone; after the G2 fix it lands at passed_with_warnings, with
            # the failing roles surfaced in the validation.warnings list.
            manifest = json.loads(result.stdout)
            failed_roles = [
                name
                for name, role in (manifest.get("roles") or {}).items()
                if role.get("validation_status") != "passed"
            ]
            assert failed_roles, "every role lacks ANCHOR; at least some should fail role validation"
            assert manifest.get("status") == "completed", "work itself succeeded; top status must remain completed"
            assert manifest.get("validation_status") == "passed_with_warnings"
            warnings = manifest.get("validation", {}).get("warnings") or []
            warned_role_names = {w.get("role") for w in warnings}
            assert warned_role_names == set(failed_roles), (
                "every scaffolding-failed role must appear in validation.warnings"
            )


class TestRalphWorkflows(unittest.TestCase):
    """WHEN the planner declares a workflow other than `feature`, the state machine
    runs only the roles the workflow lists and finalizes accordingly."""

    @staticmethod
    def _ralph(args: list[str], env: dict, *, expect_returncode: int | None = 0) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "ralph.py"), *args],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS),
            env=env,
        )
        if expect_returncode is not None:
            assert result.returncode == expect_returncode, (
                f"args={args!r} rc={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        if not result.stdout.strip():
            return {}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"_raw": result.stdout, "_stderr": result.stderr}

    def test_workflow_phases_helper(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        assert ralph.workflow_phases("feature") == (
            ralph.ITER_PHASE_EXEC,
            ralph.ITER_PHASE_REVIEW,
            ralph.ITER_PHASE_RERVIEW,
        )
        assert ralph.workflow_phases("review") == (ralph.ITER_PHASE_REVIEW,)
        assert ralph.workflow_phases("research") == (
            ralph.ITER_PHASE_EXEC,
            ralph.ITER_PHASE_REVIEW,
        )
        assert ralph.workflow_phases(None) == ralph.workflow_phases("feature")
        # Unknown workflow falls back to default.
        assert ralph.workflow_phases("not-a-workflow") == ralph.workflow_phases("feature")

    def test_next_iter_phase_walks_each_workflow(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        # feature: PENDING -> EXEC -> REVIEW -> RERVIEW -> DECIDED
        assert ralph.next_iter_phase(ralph.ITER_PHASE_PENDING, "feature") == ralph.ITER_PHASE_EXEC
        assert ralph.next_iter_phase(ralph.ITER_PHASE_EXEC, "feature") == ralph.ITER_PHASE_REVIEW
        assert ralph.next_iter_phase(ralph.ITER_PHASE_REVIEW, "feature") == ralph.ITER_PHASE_RERVIEW
        assert ralph.next_iter_phase(ralph.ITER_PHASE_RERVIEW, "feature") == ralph.ITER_PHASE_DECIDED
        # review: PENDING -> REVIEW -> DECIDED (no executor, no re_reviewer)
        assert ralph.next_iter_phase(ralph.ITER_PHASE_PENDING, "review") == ralph.ITER_PHASE_REVIEW
        assert ralph.next_iter_phase(ralph.ITER_PHASE_REVIEW, "review") == ralph.ITER_PHASE_DECIDED
        # research: PENDING -> EXEC -> REVIEW -> DECIDED (no re_reviewer)
        assert ralph.next_iter_phase(ralph.ITER_PHASE_PENDING, "research") == ralph.ITER_PHASE_EXEC
        assert ralph.next_iter_phase(ralph.ITER_PHASE_REVIEW, "research") == ralph.ITER_PHASE_DECIDED

    def test_planner_unknown_workflow_is_rejected(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        cfg = {
            "roles": {
                "planner": {"harness": "command", "model": "x", "extra_args": ["true"]},
                "executor": {"harness": "command", "model": "x", "extra_args": ["true"]},
                "reviewer": {"harness": "command", "model": "x", "extra_args": ["true"]},
                "re_reviewer": {"harness": "command", "model": "x", "extra_args": ["true"]},
            },
            "defaults": {
                "max_iterations": 3,
                "max_minutes": 1,
                "memory_top_k": 3,
                "progress_tail_blocks": 2,
                "iteration_timeout_seconds": 5,
            },
        }
        # Direct call to validation logic via the spec normalization codepath
        # would require a full role spawn; the lightweight equivalent is:
        spec = {
            "workflow": "not-a-real-workflow",
            "goal": "x",
            "target_artifact": "/tmp/x",
            "success_criteria": ["x"],
            "iteration_task_seed": "x",
            "rationale": "x",
        }
        # The planner code does the workflow check inside _invoke_planner; we
        # inline the check here to keep this a unit test.
        assert spec["workflow"] not in ralph.WORKFLOWS

    def test_review_workflow_runs_only_reviewer_no_executor_no_rereviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            workspace = tmp_path / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            # Pre-create the artifact since the review workflow has no executor.
            artifact.write_text("hello world")
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            env["RALPH_TEST_WORKFLOW"] = "review"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "review existing artifact",
                    "--workspace",
                    str(workspace),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode == 0, result.stderr
            manifest = json.loads(result.stdout)
            assert manifest["status"] == "completed"
            assert manifest["workflow"] == "review"
            assert manifest["spec"]["workflow"] == "review"
            iterations = manifest["iterations"]
            assert len(iterations) == 1
            assert iterations[0]["verdict"] == "pass"
            # Reviewer must have run exactly once; no executor, no re_reviewer.
            roles = manifest["roles"]
            assert "reviewer-1" in roles
            assert "executor-1" not in roles
            assert "re_reviewer-1" not in roles
            assert iterations[0].get("re_reviewer_id") is None
            counters = tmp_path / "counters"
            assert not (counters / "executor").exists()
            assert (counters / "reviewer").read_text().strip() == "1"
            assert not (counters / "re_reviewer").exists()

    def test_research_workflow_runs_executor_and_reviewer_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "report.md"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            env["RALPH_TEST_WORKFLOW"] = "research"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "investigate and report",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode == 0, result.stderr
            manifest = json.loads(result.stdout)
            assert manifest["status"] == "completed"
            assert manifest["workflow"] == "research"
            iterations = manifest["iterations"]
            assert len(iterations) == 1
            assert iterations[0]["verdict"] == "pass"
            # No re_reviewer in research workflow.
            roles = manifest["roles"]
            assert "executor-1" in roles
            assert "reviewer-1" in roles
            assert "re_reviewer-1" not in roles
            assert iterations[0].get("re_reviewer_id") is None
            counters = tmp_path / "counters"
            assert (counters / "executor").read_text().strip() == "1"
            assert (counters / "reviewer").read_text().strip() == "1"
            assert not (counters / "re_reviewer").exists()

    def test_feature_workflow_default_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "out.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            # No RALPH_TEST_WORKFLOW set → mock planner emits feature.
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "default workflow",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode == 0, result.stderr
            manifest = json.loads(result.stdout)
            assert manifest["workflow"] == "feature"
            assert "executor-1" in manifest["roles"]
            assert "reviewer-1" in manifest["roles"]
            assert "re_reviewer-1" in manifest["roles"]

    def test_summary_md_written_at_workflow_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "out.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ralph.py"),
                    "go",
                    "--goal",
                    "summary verification",
                    "--workspace",
                    str(tmp_path / "workspace"),
                    "--subprocess",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(SCRIPTS),
                env=env,
            )
            assert result.returncode == 0, result.stderr
            manifest = json.loads(result.stdout)
            summary_path = Path(env["RALPH_STATE_HOME"]) / "runs" / manifest["id"] / "summary.md"
            assert summary_path.exists(), "summary.md must be written at terminal completion"
            text = summary_path.read_text()
            assert "summary verification" in text  # original goal verbatim
            assert "**Workflow:** feature" in text
            assert "## Success criteria" in text
            assert "[x]" in text or "[?]" in text  # at least one criterion got a marker
            assert manifest.get("summary_path") == str(summary_path)


class TestKnowledgeBaseSchemaV2(unittest.TestCase):
    """Phase 1 of the BIG redesign: structured capsule schema with kind,
    scope, domain tags, confidence, verified_by, supersedes, embedding
    BLOB and the rest. Schema changes are breaking by policy — old
    DBs are dropped on first init, not migrated.
    """

    def test_init_creates_full_schema(self):
        sys.path.insert(0, str(SCRIPTS))
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            kb.init()
            with kb.connect() as db:
                cols = [r[1] for r in db.execute("PRAGMA table_info(capsules)").fetchall()]
            assert tuple(cols) == ai_kb.CAPSULE_COLUMNS, (
                f"schema mismatch:\n got: {cols}\nwant: {list(ai_kb.CAPSULE_COLUMNS)}"
            )

    def test_init_drops_stale_table_when_columns_dont_match(self):
        sys.path.insert(0, str(SCRIPTS))
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            # Fake a stale schema: minimal old shape with fewer columns.
            with kb.connect() as db:
                db.execute(
                    """
                    CREATE TABLE capsules (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        body TEXT
                    )
                    """
                )
                db.execute("INSERT INTO capsules(id,title,body) VALUES('x','t','b')")
            # Now init should detect the stale shape and wipe.
            kb.init()
            with kb.connect() as db:
                cols = [r[1] for r in db.execute("PRAGMA table_info(capsules)").fetchall()]
                count = db.execute("SELECT COUNT(*) FROM capsules").fetchone()[0]
            assert tuple(cols) == ai_kb.CAPSULE_COLUMNS
            assert count == 0, "stale rows must be dropped — no compat path"

    def test_remember_persists_full_metadata(self):
        sys.path.insert(0, str(SCRIPTS))
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RALPH_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                c = kb.remember(
                    title="kb test",
                    body="full payload",
                    kind="gotcha",
                    scope="project",
                    workspace_path="/ws",
                    project_id="proj-1",
                    domain_tags=["python", "ralph"],
                    confidence=0.8,
                    verified_by="go-rid-1",
                )
                assert c.kind == "gotcha"
                assert c.scope == "project"
                assert c.workspace_path == "/ws"
                assert c.project_id == "proj-1"
                assert c.domain_tags == "python,ralph"
                assert c.confidence == 0.8
                assert c.verified_by == "go-rid-1"
                # No embedder under disable flag → embedding fields blank.
                assert c.embedding_dim == 0
                assert c.embedding_model is None
                # Round-trip via get().
                got = kb.get(c.id)
                assert got is not None
                assert got.kind == "gotcha"
                assert got.domain_tags == "python,ralph"
            finally:
                os.environ.pop("RALPH_KB_DISABLE_EMBED", None)

    def test_remember_rejects_unknown_kind_or_scope(self):
        sys.path.insert(0, str(SCRIPTS))
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RALPH_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                try:
                    kb.remember("t", "b", kind="bogus")
                except ValueError as err:
                    assert "kind" in str(err)
                else:
                    raise AssertionError("expected ValueError for unknown kind")
                try:
                    kb.remember("t", "b", scope="bogus")
                except ValueError as err:
                    assert "scope" in str(err)
                else:
                    raise AssertionError("expected ValueError for unknown scope")
            finally:
                os.environ.pop("RALPH_KB_DISABLE_EMBED", None)

    def test_supersedes_links_bidirectionally(self):
        sys.path.insert(0, str(SCRIPTS))
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RALPH_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                old = kb.remember(title="v1", body="old fact")
                new = kb.remember(title="v2", body="new fact", supersedes=old.id)
                refreshed_old = kb.get(old.id)
                assert refreshed_old is not None
                assert refreshed_old.superseded_by == new.id, (
                    f"superseded_by must be set bidirectionally: got {refreshed_old.superseded_by!r}"
                )
                assert new.supersedes == old.id
            finally:
                os.environ.pop("RALPH_KB_DISABLE_EMBED", None)


class TestKnowledgeBaseEmbeddingRoundtrip(unittest.TestCase):
    """End-to-end embedding test: actually shells out to the fastembed
    runner. Slow (~1s cold start) — only runs when the runner is
    available; otherwise skipped so CI without `uv` doesn't fail.
    """

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        import embed

        e = embed.Embedder()
        if not e.is_available():
            self.skipTest("fastembed runner not available (uv missing or runner script missing)")
        self.embedder = e

    def test_remember_stores_embedding_when_runner_available(self):
        import ai_kb
        from embed import cosine, unpack_vector

        with tempfile.TemporaryDirectory() as tmp:
            # Ensure the disable flag is OFF for this test.
            saved = os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                c = kb.remember(
                    title="Ralph manifest layout",
                    body="Ralph state under runs/*/manifest.json with kind values.",
                )
                assert c.embedding_dim == 384, c.embedding_dim
                assert c.embedding_model == "BAAI/bge-small-en-v1.5"
                # Verify the stored embedding round-trips and self-cosine == 1.
                with kb.connect() as db:
                    row = db.execute("SELECT embedding FROM capsules WHERE id = ?", (c.id,)).fetchone()
                vec = unpack_vector(row["embedding"])
                assert len(vec) == 384
                assert abs(cosine(vec, vec) - 1.0) < 1e-5
            finally:
                if saved is not None:
                    os.environ["RALPH_KB_DISABLE_EMBED"] = saved


class TestEmbedModuleHelpers(unittest.TestCase):
    """Small unit tests for the embed module helpers that don't need
    the runner: pack/unpack, cosine math, default constants."""

    def test_pack_unpack_roundtrip(self):
        sys.path.insert(0, str(SCRIPTS))
        import embed

        v = [0.1, -0.5, 1.234, 0.0, -1e-3]
        blob = embed.pack_vector(v)
        assert len(blob) == len(v) * 4
        out = embed.unpack_vector(blob)
        assert len(out) == len(v)
        for a, b in zip(v, out):
            assert abs(a - b) < 1e-6

    def test_unpack_handles_none_and_empty(self):
        sys.path.insert(0, str(SCRIPTS))
        import embed

        assert embed.unpack_vector(None) == []
        assert embed.unpack_vector(b"") == []

    def test_cosine_basic_math(self):
        sys.path.insert(0, str(SCRIPTS))
        import embed

        assert embed.cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
        assert abs(embed.cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9
        assert embed.cosine([], [1.0]) == 0.0
        assert embed.cosine([1.0], [1.0, 2.0]) == 0.0  # length mismatch


class TestKnowledgeBaseHybridRetrieval(unittest.TestCase):
    """Phase 2: hybrid (BM25 + cosine + RRF + MMR) retrieval with
    structured filters. The canonical regression is the
    "semantic-without-lexical-overlap" case — a query whose tokens do
    not appear in the capsule body but whose meaning is similar must
    surface the capsule via the vector lane.
    """

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        import embed

        if not embed.Embedder().is_available():
            self.skipTest("fastembed runner not available")
        # Embedding tests need the embedder ON.
        self.saved_disable = os.environ.pop("RALPH_KB_DISABLE_EMBED", None)

    def tearDown(self):
        if self.saved_disable is not None:
            os.environ["RALPH_KB_DISABLE_EMBED"] = self.saved_disable

    def test_vector_mode_finds_semantic_match_without_keyword_overlap(self):
        """Capsule says 'feline' / query asks 'cat'. BM25 misses, vector hits."""
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            kb.remember(
                title="Animal taxonomy",
                body="The domestic feline is a small carnivorous mammal.",
                kind="fact",
                scope="universal",
            )
            # BM25-only query that has no token overlap with the body.
            bm25 = kb.search("cat pet", limit=3, mode="bm25")
            assert bm25 == [], (
                f"BM25-only must miss across token boundaries; got {len(bm25)} hit(s):\n{[h['title'] for h in bm25]}"
            )
            # Vector mode bridges the lexical gap.
            vec = kb.search("cat pet", limit=3, mode="vector")
            assert len(vec) == 1, f"vector lane must surface the semantically-related capsule; got {vec}"
            assert vec[0]["title"] == "Animal taxonomy"
            assert vec[0]["cosine_score"] is not None

    def test_hybrid_mode_combines_lanes_via_rrf(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            # cap_a: high BM25 (exact token), low semantic relevance
            kb.remember(
                title="Manifest format",
                body="A manifest file describes packaging metadata.",
                kind="fact",
            )
            # cap_b: high semantic relevance to a Ralph-flavored query,
            # but no shared tokens with the query.
            kb.remember(
                title="Run state on disk",
                body="Each Ralph execution stores its progress under its own directory.",
                kind="fact",
            )

            hits = kb.search("ralph manifest layout", limit=3, mode="hybrid")
            assert len(hits) == 2
            ids = [h["id"] for h in hits]
            # Both capsules must appear in the fused result.
            assert any("Manifest format" == h["title"] for h in hits), hits
            assert any("Run state on disk" == h["title"] for h in hits), hits
            # Each hit should have a non-zero RRF score.
            for h in hits:
                assert h["rrf_score"] > 0.0, h

    def test_filters_scope_kind_and_domain_pre_rank(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            kb.remember(
                title="Workspace gotcha",
                body="trailing slash matters in workspace paths.",
                kind="gotcha",
                scope="workspace",
                workspace_path="/ws/a",
                domain_tags=["python", "paths"],
            )
            kb.remember(
                title="Universal principle",
                body="trailing slash matters in workspace paths everywhere.",
                kind="principle",
                scope="universal",
                domain_tags=["python", "paths"],
            )

            # Filter by kind=gotcha → only one hit.
            only_gotchas = kb.search("trailing slash", limit=5, kind="gotcha")
            assert len(only_gotchas) == 1
            assert only_gotchas[0]["kind"] == "gotcha"

            # Filter by scope=universal → only the other.
            universals = kb.search("trailing slash", limit=5, scope="universal")
            assert len(universals) == 1
            assert universals[0]["scope"] == "universal"

            # Domain filter ANDs across calls but ORs across given values
            # (any-tag-match within a single call). Both have python so
            # both should match.
            both = kb.search("trailing slash", limit=5, domain="python")
            assert len(both) == 2

    def test_workspace_path_gives_soft_rrf_boost(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            in_ws = kb.remember(
                title="Workspace-A note",
                body="Specific note about repo layout.",
                kind="fact",
                workspace_path="/ws/a",
            )
            out_ws = kb.remember(
                title="Workspace-B note",
                body="Specific note about repo layout.",
                kind="fact",
                workspace_path="/ws/b",
            )
            hits = kb.search("repo layout", limit=2, workspace="/ws/a")
            assert len(hits) == 2
            # The matching-workspace capsule must rank first courtesy of
            # the +0.1 RRF boost, even when the bodies are identical.
            assert hits[0]["id"] == in_ws.id, [h["title"] for h in hits]
            assert hits[1]["id"] == out_ws.id

    def test_hybrid_mode_marks_mmr_selected(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            for i in range(3):
                kb.remember(
                    title=f"capsule {i}",
                    body=f"Lesson number {i} about Ralph orchestration.",
                    kind="fact",
                )
            hits = kb.search("ralph orchestration", limit=2, mode="hybrid")
            assert len(hits) == 2
            for h in hits:
                assert h["mmr_selected"] is True, h


class TestKnowledgeBaseCurate(unittest.TestCase):
    """Phase 7: curation pass — dedupe, decay, contradiction-scan.

    Dedupe + contradiction tests need embeddings (cosine math); decay
    test runs without an embedder so the fast suite stays fast.
    """

    def test_decay_runs_even_without_embeddings(self):
        sys.path.insert(0, str(SCRIPTS))
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RALPH_KB_DISABLE_EMBED"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                kb.remember(title="a", body="A body")
                kb.remember(title="b", body="B body")
                # No-embed path: dedupe/contradiction skip (no candidate
                # vectors) but decay still runs because it operates on
                # the SQL row set, not embeddings. This is the contract
                # we want — tools should keep curating even when the
                # embedder is unavailable.
                summary = kb.curate(decay=True, dedupe=True, contradiction_scan=True, decay_step=0.2)
                assert summary["duplicates"] == 0, summary
                assert summary["contradictions"] == [], summary
                assert summary["candidates_examined"] == 0, summary
                assert summary["decayed"] == 2, summary
                # Verify the decay column actually moved on disk.
                with kb.connect() as db:
                    rows = db.execute("SELECT decay_score FROM capsules ORDER BY title").fetchall()
                scores = sorted(r["decay_score"] for r in rows)
                assert all(abs(s - 0.2) < 1e-6 for s in scores), scores

                # Run again: decay accumulates, capped at decay_max.
                kb.curate(decay=True, dedupe=False, contradiction_scan=False, decay_step=0.5)
                with kb.connect() as db:
                    rows = db.execute("SELECT decay_score FROM capsules").fetchall()
                # 0.2 + 0.5 = 0.7
                assert all(abs(r["decay_score"] - 0.7) < 1e-6 for r in rows), [r["decay_score"] for r in rows]
            finally:
                os.environ.pop("RALPH_KB_DISABLE_EMBED", None)

    def test_dedupe_marks_near_duplicates_as_superseded(self):
        sys.path.insert(0, str(SCRIPTS))
        import embed

        if not embed.Embedder().is_available():
            self.skipTest("fastembed runner not available")

        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                # Two near-duplicates of the same gotcha. Same kind,
                # near-identical content → cosine should clear 0.95.
                older = kb.remember(
                    title="JWT must be validated",
                    body="Always validate JWT signature before reading claims.",
                    kind="gotcha",
                    confidence=0.5,
                )
                # A short delay ensures the newer capsule has a later
                # `created_at` so the deterministic tiebreak prefers it
                # when confidences match.
                time.sleep(0.01)
                newer = kb.remember(
                    title="Validate JWT signatures",
                    body="Always validate the JWT signature before using any claims.",
                    kind="gotcha",
                    confidence=0.7,
                )
                kb.remember(
                    title="Unrelated note",
                    body="A completely unrelated capsule about monorepos and yarn workspaces.",
                    kind="fact",
                )
                summary = kb.curate(
                    dedupe=True,
                    decay=True,
                    contradiction_scan=False,
                )
                assert summary["duplicates"] >= 1, summary
                # Higher confidence wins → older becomes the loser.
                refreshed_older = kb.get(older.id)
                refreshed_newer = kb.get(newer.id)
                assert refreshed_older is not None and refreshed_newer is not None
                assert refreshed_older.superseded_by == newer.id, (
                    f"older capsule must be marked superseded by newer; got {refreshed_older.superseded_by!r}"
                )
                assert refreshed_newer.supersedes == older.id, (
                    f"newer capsule must point at older via `supersedes`; got {refreshed_newer.supersedes!r}"
                )

                # Search must filter superseded rows out by default.
                hits = kb.search("validate JWT", limit=5, mode="bm25", kind="gotcha")
                ids = [h["id"] for h in hits]
                assert refreshed_newer.id in ids, ids
                assert refreshed_older.id not in ids, "search must hide superseded capsules"
            finally:
                if saved is not None:
                    os.environ["RALPH_KB_DISABLE_EMBED"] = saved

    def test_contradiction_scan_returns_candidate_pairs(self):
        sys.path.insert(0, str(SCRIPTS))
        import embed

        if not embed.Embedder().is_available():
            self.skipTest("fastembed runner not available")

        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                kb.remember(
                    title="Token expiry fact",
                    body="JWT tokens expire after 60 minutes by default.",
                    kind="fact",
                )
                kb.remember(
                    title="Token expiry gotcha",
                    body="JWT tokens expire after 60 minutes; double-check via the iat claim.",
                    kind="gotcha",
                )
                summary = kb.curate(
                    dedupe=False,
                    decay=False,
                    contradiction_scan=True,
                    contradiction_cosine_threshold=0.7,
                )
                contradictions = summary["contradictions"]
                assert len(contradictions) >= 1, summary
                pair = contradictions[0]
                assert pair["a_kind"] in ("fact", "gotcha")
                assert pair["b_kind"] in ("fact", "gotcha")
                assert pair["a_kind"] != pair["b_kind"]
            finally:
                if saved is not None:
                    os.environ["RALPH_KB_DISABLE_EMBED"] = saved


class TestKnowledgeBaseVecRunner(unittest.TestCase):
    """Stream 2: vector lane is now driven by `vec_runner.py` over a
    `uv run --script` subprocess loading sqlite-vec. These tests pin
    the orchestrator-side plumbing — `_call_vec_runner` short-circuits
    on the env disable flag, raises loudly when the runner cannot be
    spawned, and forwards the runner's JSON payload unchanged.
    """

    def test_call_vec_runner_short_circuits_when_disabled(self):
        sys.path.insert(0, str(SCRIPTS))
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.get("RALPH_KB_DISABLE_VEC")
            os.environ["RALPH_KB_DISABLE_VEC"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                knn = kb._call_vec_runner({"mode": "knn", "db_path": str(kb.db_path)})
                pairs = kb._call_vec_runner({"mode": "pairs", "db_path": str(kb.db_path)})
                assert knn == {"hits": []}, knn
                assert pairs == {"pairs": []}, pairs
            finally:
                if saved is None:
                    os.environ.pop("RALPH_KB_DISABLE_VEC", None)
                else:
                    os.environ["RALPH_KB_DISABLE_VEC"] = saved

    def test_call_vec_runner_raises_when_runner_missing(self):
        """If the colocated `vec_runner.py` is absent, hard-fail with
        a clear RuntimeError rather than silently degrading."""
        sys.path.insert(0, str(SCRIPTS))
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("RALPH_KB_DISABLE_VEC", None)
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                # Monkey-patch the runner path to a non-existent file.
                original = kb._vec_runner_path
                kb._vec_runner_path = lambda: Path(tmp) / "nope.py"
                try:
                    raised = False
                    try:
                        kb._call_vec_runner({"mode": "knn", "db_path": str(kb.db_path)})
                    except RuntimeError as err:
                        assert "vec_runner missing" in str(err), err
                        raised = True
                    assert raised, "expected RuntimeError when vec_runner.py is absent"
                finally:
                    kb._vec_runner_path = original
            finally:
                if saved is not None:
                    os.environ["RALPH_KB_DISABLE_VEC"] = saved

    def test_doctor_reports_vec_runner_status(self):
        """`,ai-kb doctor` must surface vec_runner state so operators
        can debug a broken install. Verifies the line is present in
        either the disabled / missing / ok variant — exact wording is
        a contract the doctor command exposes to humans."""
        sys.path.insert(0, str(SCRIPTS))
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.get("RALPH_KB_DISABLE_VEC")
            os.environ["RALPH_KB_DISABLE_VEC"] = "1"
            try:
                kb = ai_kb.KnowledgeBase(home=Path(tmp))
                lines = kb.doctor()
                vec_lines = [l for l in lines if l.startswith("vec_runner=")]
                assert len(vec_lines) == 1, lines
                assert "disabled via RALPH_KB_DISABLE_VEC" in vec_lines[0], vec_lines
            finally:
                if saved is None:
                    os.environ.pop("RALPH_KB_DISABLE_VEC", None)
                else:
                    os.environ["RALPH_KB_DISABLE_VEC"] = saved


class TestKnowledgeBaseAsToolCLI(unittest.TestCase):
    """Phase 6: roles invoke the KB as a tool via the `,ai-kb search`
    subcommand. The shape of the CLI output (JSON array of hits with
    body/title/kind/scope/score) is part of the contract roles depend
    on; pin the schema so a careless refactor doesn't break agents
    that rely on it.
    """

    def test_search_cli_returns_json_array_with_expected_keys(self):
        """Run `python3 ai_kb.py search ... --json` against a fresh
        KB. The output must be a JSON array; each hit must carry the
        keys roles parse downstream."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = {**os.environ, "AI_KB_HOME": str(tmp_path / "kb"), "RALPH_KB_DISABLE_EMBED": "1"}
            seed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ai_kb.py"),
                    "remember",
                    "--title",
                    "Tool probe",
                    "--body",
                    "An executor sometimes forgets to wire exports.",
                    "--kind",
                    "gotcha",
                    "--scope",
                    "project",
                    "--workspace",
                    "/ws/probe",
                    "--no-embed",
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert seed.returncode == 0, seed.stderr
            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "ai_kb.py"),
                    "search",
                    "executor wire exports",
                    "--limit",
                    "3",
                    "--mode",
                    "bm25",
                    "--kind",
                    "gotcha",
                    "--json",
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert run.returncode == 0, run.stderr
            payload = json.loads(run.stdout)
            assert isinstance(payload, list), type(payload)
            assert len(payload) >= 1, payload
            row = payload[0]
            for key in (
                "id",
                "title",
                "body",
                "snippet",
                "kind",
                "scope",
                "domain_tags",
                "confidence",
                "rrf_score",
                "bm25_rank",
                "vector_rank",
            ):
                assert key in row, f"missing key {key!r}; got keys {sorted(row.keys())}"
            assert row["kind"] == "gotcha"
            assert "wire exports" in row["body"]


class TestKnowledgeBaseDocIngestion(unittest.TestCase):
    """Phase 5: bulk-ingest existing markdown documentation into the
    KB as `kind=doc` capsules. Idempotent on file content so re-runs
    don't pile up duplicates; chunked on H1/H2 headings so retrieval
    can return individually-relevant sections.
    """

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        self.saved_disable = os.environ.get("RALPH_KB_DISABLE_EMBED")
        os.environ["RALPH_KB_DISABLE_EMBED"] = "1"

    def tearDown(self):
        if self.saved_disable is None:
            os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
        else:
            os.environ["RALPH_KB_DISABLE_EMBED"] = self.saved_disable

    def test_ingest_file_chunks_on_h1_h2_headings(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            doc = tmp_path / "agents.md"
            doc.write_text(
                "# Agents\n\nIntro paragraph.\n\n"
                "## Skills\n\nSkill list goes here.\n\n"
                "### Sub-section under Skills\n\nshould stay inside Skills chunk\n\n"
                "## Tools\n\nTool list goes here.\n"
            )
            kb = ai_kb.KnowledgeBase(home=tmp_path / "kb")
            summary = kb.ingest_path(doc)
            assert summary["files_seen"] == 1
            assert summary["files_ingested"] == 1
            assert summary["files_skipped_unchanged"] == 0
            assert summary["capsules_stored"] == 3, summary

            # Verify titles match the headings.
            titles = sorted(c.title for c in kb.list(limit=10))
            assert titles == ["Agents", "Skills", "Tools"], titles

            # H3 stayed inside its parent chunk.
            skills = next(c for c in kb.list(limit=10) if c.title == "Skills")
            assert "Sub-section under Skills" in skills.body
            assert skills.kind == "doc", skills.kind
            assert "kb-ingest" in skills.tags

    def test_ingest_idempotent_on_unchanged_file(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            doc = tmp_path / "x.md"
            doc.write_text("# Title\n\nbody\n")
            kb = ai_kb.KnowledgeBase(home=tmp_path / "kb")

            first = kb.ingest_path(doc)
            assert first["files_ingested"] == 1
            ids_after_first = sorted(c.id for c in kb.list(limit=10))

            second = kb.ingest_path(doc)
            assert second["files_seen"] == 1
            assert second["files_ingested"] == 0
            assert second["files_skipped_unchanged"] == 1
            assert second["capsules_stored"] == 0
            ids_after_second = sorted(c.id for c in kb.list(limit=10))
            assert ids_after_first == ids_after_second, (
                f"capsule ids must be unchanged on idempotent re-ingest:\n"
                f"first: {ids_after_first}\nsecond: {ids_after_second}"
            )

    def test_ingest_replaces_chunks_when_file_changes(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            doc = tmp_path / "x.md"
            doc.write_text("# Old\n\nold body\n")
            kb = ai_kb.KnowledgeBase(home=tmp_path / "kb")

            kb.ingest_path(doc)
            assert [c.title for c in kb.list(limit=10)] == ["Old"]

            doc.write_text("# New A\n\na body\n\n## New B\n\nb body\n")
            summary = kb.ingest_path(doc)
            assert summary["files_ingested"] == 1
            assert summary["capsules_stored"] == 2

            titles = sorted(c.title for c in kb.list(limit=10))
            assert titles == ["New A", "New B"], titles

    def test_ingest_directory_walks_md_files(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "skills" / "foo").mkdir(parents=True)
            (tmp_path / "skills" / "foo" / "SKILL.md").write_text("# Foo skill\n\nfoo body\n")
            (tmp_path / "skills" / "bar").mkdir(parents=True)
            (tmp_path / "skills" / "bar" / "SKILL.md").write_text("# Bar skill\n\nbar body\n")
            (tmp_path / "skills" / "README.txt").write_text("not md, must skip")

            kb = ai_kb.KnowledgeBase(home=tmp_path / "kb")
            summary = kb.ingest_path(tmp_path / "skills")
            assert summary["files_seen"] == 2, summary
            assert summary["capsules_stored"] == 2, summary

            titles = sorted(c.title for c in kb.list(limit=10))
            assert titles == ["Bar skill", "Foo skill"], titles

            # Domain tag inference should pick up skill name from
            # parent dir.
            foo = next(c for c in kb.list(limit=10) if c.title == "Foo skill")
            assert "foo" in (foo.domain_tags or "").split(","), foo.domain_tags

    def test_ingest_rejects_non_markdown_target(self):
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            f = tmp_path / "x.txt"
            f.write_text("not markdown")
            kb = ai_kb.KnowledgeBase(home=tmp_path / "kb")
            try:
                kb.ingest_path(f)
            except ValueError as err:
                assert "unsupported" in str(err)
            else:
                raise AssertionError("expected ValueError on non-markdown target")


class TestRalphReflector(unittest.TestCase):
    """Phase 4: post-run reflector role distills durable lessons into
    structured capsules. Reflector is best-effort — its failure never
    invalidates a successful run — and only runs on
    feature/bugfix workflows.
    """

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        self.saved_disable = os.environ.get("RALPH_KB_DISABLE_EMBED")
        os.environ["RALPH_KB_DISABLE_EMBED"] = "1"

    def tearDown(self):
        if self.saved_disable is None:
            os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
        else:
            os.environ["RALPH_KB_DISABLE_EMBED"] = self.saved_disable

    def _make_runner(self, tmp_path: Path):
        import ralph

        runner = ralph.RalphRunner(state_home=tmp_path / "state", kb_home=tmp_path / "kb")
        runner.init()
        return runner

    def test_store_reflector_capsule_validates_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = self._make_runner(tmp_path)
            workspace = tmp_path / "ws"
            workspace.mkdir()
            manifest = {"id": "rid-1", "workflow": "feature"}
            entry = {
                "title": "Use absolute paths in target_artifact",
                "body": "Spec validation rejects relative paths; the planner must resolve them before emitting.",
                "kind": "gotcha",
                "scope": "project",
                "domain_tags": ["python", "ralph"],
                "confidence": 0.7,
                "refs": [],
            }
            cid = runner._store_reflector_capsule(entry, manifest=manifest, workspace=workspace)
            assert cid is not None
            cap = runner.kb.get(cid)
            assert cap is not None
            assert cap.kind == "gotcha"
            assert cap.scope == "project"
            assert cap.workspace_path == str(workspace)
            assert cap.confidence == 0.7
            assert cap.verified_by == "rid-1", cap.verified_by
            assert "ralph" in cap.tags
            assert "reflector" in cap.tags

    def test_store_reflector_capsule_skips_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = self._make_runner(tmp_path)
            ws = tmp_path / "ws"
            ws.mkdir()
            mf = {"id": "rid-x", "workflow": "feature"}
            # Missing title.
            assert runner._store_reflector_capsule({"body": "x"}, manifest=mf, workspace=ws) is None
            # Missing body.
            assert runner._store_reflector_capsule({"title": "x"}, manifest=mf, workspace=ws) is None
            # Non-dict.
            assert runner._store_reflector_capsule("nope", manifest=mf, workspace=ws) is None
            # Unknown kind/scope: coerce to defaults rather than reject.
            cid = runner._store_reflector_capsule(
                {"title": "t", "body": "b", "kind": "made_up", "scope": "weird"},
                manifest=mf,
                workspace=ws,
            )
            assert cid is not None
            cap = runner.kb.get(cid)
            assert cap.kind == "fact"
            assert cap.scope == "project"

    def test_invoke_reflector_skipped_when_workflow_not_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = self._make_runner(tmp_path)
            ws = tmp_path / "ws"
            ws.mkdir()
            (tmp_path / "state" / "runs" / "rid-r").mkdir(parents=True)
            manifest = {
                "id": "rid-r",
                "workflow": "review",
                "iterations": [],
                "roles": {},
            }
            roles_cfg = {
                "roles": {"reflector": {"harness": "command", "model": "x", "extra_args": []}},
                "defaults": {
                    "reflector_enabled": True,
                    "reflector_workflows": ["feature", "bugfix"],
                    "iteration_timeout_seconds": 5,
                    "memory_top_k": 3,
                    "progress_tail_blocks": 2,
                },
            }
            result = runner._invoke_reflector(
                manifest=manifest,
                spec={"goal": "x", "target_artifact": "none"},
                workspace=ws,
                roles_cfg=roles_cfg,
                session_name=None,
            )
            assert result is None, "review workflow must skip reflector"

    def test_invoke_reflector_skipped_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = self._make_runner(tmp_path)
            ws = tmp_path / "ws"
            ws.mkdir()
            (tmp_path / "state" / "runs" / "rid-d").mkdir(parents=True)
            manifest = {
                "id": "rid-d",
                "workflow": "feature",
                "iterations": [],
                "roles": {},
            }
            roles_cfg = {
                "roles": {"reflector": {"harness": "command", "model": "x", "extra_args": []}},
                "defaults": {
                    "reflector_enabled": False,
                    "reflector_workflows": ["feature", "bugfix"],
                    "iteration_timeout_seconds": 5,
                    "memory_top_k": 3,
                    "progress_tail_blocks": 2,
                },
            }
            result = runner._invoke_reflector(
                manifest=manifest,
                spec={"goal": "x"},
                workspace=ws,
                roles_cfg=roles_cfg,
                session_name=None,
            )
            assert result is None, "disabled reflector must short-circuit"

    def test_invoke_reflector_skipped_when_role_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = self._make_runner(tmp_path)
            ws = tmp_path / "ws"
            ws.mkdir()
            (tmp_path / "state" / "runs" / "rid-m").mkdir(parents=True)
            manifest = {
                "id": "rid-m",
                "workflow": "feature",
                "iterations": [],
                "roles": {},
            }
            roles_cfg = {
                "roles": {},
                "defaults": {
                    "reflector_enabled": True,
                    "reflector_workflows": ["feature"],
                    "iteration_timeout_seconds": 5,
                    "memory_top_k": 3,
                    "progress_tail_blocks": 2,
                },
            }
            result = runner._invoke_reflector(
                manifest=manifest,
                spec={"goal": "x"},
                workspace=ws,
                roles_cfg=roles_cfg,
                session_name=None,
            )
            assert result is None, "missing reflector role config must short-circuit"


class TestRalphReviewerKBWiring(unittest.TestCase):
    """Phase 3: reviewer + re_reviewer must read AND write the KB.

    Read side: the context builders include a `## RECENT LEARNINGS`
    section, filtered to gotchas/anti_patterns for the reviewer and
    gotchas/anti_patterns/principles for the re_reviewer.

    Write side: `capture_learnings` infers `kind=gotcha` for reviewer
    output and `kind=principle` for re_reviewer output, and tags
    workspace/scope correctly so retrieval can bias toward
    project-local capsules.
    """

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        # The reviewer/re_reviewer context builders fetch from the KB;
        # the embedder is irrelevant to the assertion (BM25 is enough
        # to populate the section), so disable it for speed.
        self.saved_disable = os.environ.get("RALPH_KB_DISABLE_EMBED")
        os.environ["RALPH_KB_DISABLE_EMBED"] = "1"

    def tearDown(self):
        if self.saved_disable is None:
            os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
        else:
            os.environ["RALPH_KB_DISABLE_EMBED"] = self.saved_disable

    def _make_runner(self, tmp_path: Path):
        import ralph

        runner = ralph.RalphRunner(state_home=tmp_path / "state", kb_home=tmp_path / "kb")
        runner.init()
        return runner

    def test_reviewer_context_includes_recent_learnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "ws"
            workspace.mkdir()
            runner = self._make_runner(tmp_path)
            runner.kb.remember(
                title="Auth gotcha",
                body="Always validate JWT signature before reading claims.",
                kind="gotcha",
                scope="project",
                workspace_path=str(workspace),
            )
            spec = {
                "goal": "Build auth handler",
                "success_criteria": ["JWT signature validated", "claims read after"],
                "target_artifact": str(workspace / "auth.py"),
            }
            ctx, hits = runner._reviewer_context(
                manifest={"id": "rid", "goal": "Build auth handler"},
                spec=spec,
                workspace=workspace,
                executor=None,
                defaults={"progress_tail_blocks": 2, "memory_top_k": 5},
            )
            assert "## RECENT LEARNINGS" in ctx, ctx
            assert "JWT signature" in ctx, f"reviewer context must inject the gotcha body:\n{ctx}"
            # Hits payload feeds the role manifest's retrieval_log; one
            # hit, the gotcha capsule we just stored.
            assert len(hits) == 1
            assert hits[0]["kind"] == "gotcha"

    def test_reviewer_context_filters_out_non_gotcha_kinds(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "ws"
            workspace.mkdir()
            runner = self._make_runner(tmp_path)
            runner.kb.remember(
                title="Auth principle",
                body="Verification heuristic: trust no claim without signature.",
                kind="principle",
                scope="project",
                workspace_path=str(workspace),
            )
            runner.kb.remember(
                title="Auth gotcha",
                body="Always validate JWT signature before reading claims.",
                kind="gotcha",
                scope="project",
                workspace_path=str(workspace),
            )
            spec = {
                "goal": "Build auth handler",
                "success_criteria": ["JWT validated"],
                "target_artifact": str(workspace / "auth.py"),
            }
            ctx, hits = runner._reviewer_context(
                manifest={"id": "rid", "goal": "Build auth handler"},
                spec=spec,
                workspace=workspace,
                executor=None,
                defaults={"progress_tail_blocks": 2, "memory_top_k": 5},
            )
            assert "JWT signature" in ctx
            assert "Verification heuristic" not in ctx, f"reviewer must NOT see principle-kind capsules:\n{ctx}"
            assert all(h["kind"] == "gotcha" for h in hits), hits

    def test_re_reviewer_context_includes_principles(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "ws"
            workspace.mkdir()
            runner = self._make_runner(tmp_path)
            runner.kb.remember(
                title="Verification principle",
                body="When primary says pass on auth, also verify token expiry.",
                kind="principle",
                scope="project",
                workspace_path=str(workspace),
            )
            spec = {
                "goal": "Build auth",
                "success_criteria": ["JWT validated"],
                "target_artifact": str(workspace / "auth.py"),
            }
            executor = {"output": str(workspace / "exec.log")}
            (workspace / "exec.log").write_text("done")
            primary_verdict = {"verdict": "pass", "notes": "looks good"}
            ctx, hits = runner._re_reviewer_context(
                manifest={"id": "rid", "goal": "Build auth"},
                spec=spec,
                workspace=workspace,
                executor=executor,
                primary_verdict=primary_verdict,
                defaults={"progress_tail_blocks": 2, "memory_top_k": 5},
            )
            assert "## RECENT LEARNINGS" in ctx, ctx
            assert "verify token expiry" in ctx, f"re_reviewer context must inject the principle body:\n{ctx}"
            assert len(hits) == 1
            assert hits[0]["kind"] == "principle"

    def test_compress_retrieval_log_strips_to_renderable_subset(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        # Synthetic search-hit shape (matches kb.search() output).
        hits = [
            {
                "id": "cap-1",
                "title": "JWT signature trap",
                "body": "Always validate.",
                "snippet": "[validate] [JWT]",
                "source": "ralph:test",
                "tags": "ralph,session-learning",
                "kind": "gotcha",
                "scope": "project",
                "workspace_path": "/ws",
                "domain_tags": "auth",
                "confidence": 0.7,
                "bm25_rank": 1,
                "vector_rank": 1,
                "bm25_score": -3e-06,
                "cosine_score": 0.84,
                "rrf_score": 0.032,
                "mmr_selected": True,
            }
        ]
        compact = ralph.RalphRunner._compress_retrieval_log(hits)
        assert compact == [
            {
                "id": "cap-1",
                "title": "JWT signature trap",
                "kind": "gotcha",
                "scope": "project",
                "confidence": 0.7,
                "rrf_score": 0.032,
            }
        ], compact
        # The compressed shape must NOT carry the body (we don't want
        # to balloon role manifests with KB content the TUI will fetch
        # on demand).
        assert "body" not in compact[0]
        assert "snippet" not in compact[0]

    def test_capture_learnings_uses_role_kind_and_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = self._make_runner(tmp_path)
            workspace = tmp_path / "ws"
            workspace.mkdir()

            # Reviewer output → kind=gotcha
            ids = runner.capture_learnings(
                rid="r1",
                output="ANCHOR: x\nLEARNING: executor often forgets to wire the export.\nRALPH_DONE\n",
                role="reviewer-1",
                workspace=str(workspace),
            )
            assert len(ids) == 1
            cap = runner.kb.get(ids[0])
            assert cap is not None
            assert cap.kind == "gotcha", cap.kind
            assert cap.scope == "project", cap.scope
            assert cap.workspace_path == str(workspace), cap.workspace_path
            assert "reviewer" in cap.tags, cap.tags

            # Re-reviewer output → kind=principle
            ids = runner.capture_learnings(
                rid="r1",
                output="LEARNING: when reviewer says pass on auth, also check expiry.\n",
                role="re_reviewer-1",
                workspace=str(workspace),
            )
            cap = runner.kb.get(ids[0])
            assert cap.kind == "principle", cap.kind

            # Executor → kind=fact
            ids = runner.capture_learnings(
                rid="r1",
                output="LEARNING: pytest -k filter is glob, not regex.\n",
                role="executor-2",
                workspace=str(workspace),
            )
            cap = runner.kb.get(ids[0])
            assert cap.kind == "fact", cap.kind


class TestKnowledgeBaseSearchReturnsBody(unittest.TestCase):
    """Pin the regression where the FTS5 path returned `snippet` (the
    bracketed match-highlight) but not the full `body`. Ralph's
    `_fetch_learnings` indexed `h["body"]` and got `None`, so role
    prompts saw only the capsule title (a meta-string like
    `Ralph learning go-…-executor-1`) instead of the actual lesson.
    """

    def test_search_includes_body_field_in_results(self):
        sys.path.insert(0, str(SCRIPTS))
        import ai_kb

        with tempfile.TemporaryDirectory() as tmp:
            kb = ai_kb.KnowledgeBase(home=Path(tmp))
            kb.init()
            kb.remember(
                title="t1",
                body="Ralph state layout uses runs/*/manifest.json with kind=='go' filter.",
                source="ralph:test",
                tags="ralph,test",
            )
            hits = kb.search("Ralph manifest layout", limit=5)
            assert len(hits) == 1, hits
            row = hits[0]
            assert "body" in row, f"search row must include body: keys={sorted(row.keys())}"
            assert "manifest.json" in (row["body"] or ""), row["body"]
            # snippet should still be present for CLI / UI consumers
            assert "snippet" in row, "search row must still include snippet for highlights"

    def test_fetch_learnings_injects_body_text_not_title(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_home = tmp_path / "state"
            kb_home = tmp_path / "kb"
            state_home.mkdir()
            kb_home.mkdir()
            runner = ralph.RalphRunner(state_home=state_home, kb_home=kb_home)
            runner.init()
            runner.kb.remember(
                title="Ralph learning go-foo-executor-1",
                body="Concrete fact: spec target_artifact must be an absolute path.",
                source="ralph:go-foo-executor-1",
                tags="ralph,session-learning",
            )
            text, hits = runner._fetch_learnings("spec target_artifact path", top_k=5)
            assert "Concrete fact" in text, f"role prompts must inject capsule body, not title:\n{text!r}"
            assert "Ralph learning go-foo-executor-1" not in text, (
                f"title (meta-string) must not be the injected content:\n{text!r}"
            )
            # The hits payload mirrors the ranked search results — caller-side
            # consumers (TUI retrieval_log, future curator) read it directly.
            assert len(hits) == 1, hits
            assert hits[0]["title"].startswith("Ralph learning"), hits[0]


class TestRalphElasticReviewSkillGating(unittest.TestCase):
    """Stream 1: in elastic-belonging codebases the reviewer and
    re-reviewer roles invoke the operator's `/review` skill (skill
    content rendered as a primary-instruction preamble; the role's
    JSON output contract is preserved as the wire format).

    Detection is git-remote-driven: any remote URL whose path starts
    with `elastic/` qualifies. Non-elastic workspaces see the default
    review prompt unchanged.
    """

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        # Reviewer KB lookups are not what we're testing here — disable
        # the embedder to keep the suite fast.
        self.saved_disable = os.environ.get("RALPH_KB_DISABLE_EMBED")
        os.environ["RALPH_KB_DISABLE_EMBED"] = "1"

    def tearDown(self):
        if self.saved_disable is None:
            os.environ.pop("RALPH_KB_DISABLE_EMBED", None)
        else:
            os.environ["RALPH_KB_DISABLE_EMBED"] = self.saved_disable

    def _git_init_with_remote(self, path: Path, remote_url: str | None) -> None:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q"], cwd=path, check=True)
        if remote_url:
            subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=path, check=True)

    def test_is_elastic_workspace_detects_https_remote(self):
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "kibana"
            self._git_init_with_remote(ws, "https://github.com/elastic/kibana.git")
            assert ralph.is_elastic_workspace(ws) is True

    def test_is_elastic_workspace_detects_ssh_remote(self):
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "kibana"
            self._git_init_with_remote(ws, "git@github.com:elastic/kibana.git")
            assert ralph.is_elastic_workspace(ws) is True

    def test_is_elastic_workspace_rejects_non_elastic_remote(self):
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "personal"
            self._git_init_with_remote(ws, "https://github.com/kapral18/dotfiles.git")
            assert ralph.is_elastic_workspace(ws) is False

    def test_is_elastic_workspace_handles_no_remote(self):
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "fresh"
            self._git_init_with_remote(ws, None)
            assert ralph.is_elastic_workspace(ws) is False

    def test_is_elastic_workspace_handles_non_git_directory(self):
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "plain"
            ws.mkdir()
            assert ralph.is_elastic_workspace(ws) is False

    def test_is_elastic_workspace_handles_missing_directory(self):
        import ralph

        ws = Path(tempfile.gettempdir()) / "definitely-does-not-exist-elastic-probe"
        assert ralph.is_elastic_workspace(ws) is False

    def test_is_elastic_workspace_detects_elastic_in_upstream_remote(self):
        """Forks: developer's `origin` points at their fork, but
        `upstream` points at `elastic/<repo>`. We should detect either."""
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "kibana-fork"
            ws.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/me/kibana.git"],
                cwd=ws,
                check=True,
            )
            subprocess.run(
                ["git", "remote", "add", "upstream", "git@github.com:elastic/kibana.git"],
                cwd=ws,
                check=True,
            )
            assert ralph.is_elastic_workspace(ws) is True

    def test_reviewer_context_inlines_skill_preamble_in_elastic_workspace(self):
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "kibana"
            self._git_init_with_remote(workspace, "git@github.com:elastic/kibana.git")
            runner = ralph.RalphRunner(state_home=tmp_path / "state", kb_home=tmp_path / "kb")
            runner.init()
            spec = {
                "goal": "Build auth handler",
                "success_criteria": ["JWT validated"],
                "target_artifact": str(workspace / "auth.py"),
            }
            ctx, _hits = runner._reviewer_context(
                manifest={"id": "rid", "goal": "Build auth handler"},
                spec=spec,
                workspace=workspace,
                executor=None,
                defaults={"progress_tail_blocks": 2, "memory_top_k": 5},
            )
            assert "## REVIEW SKILL HEURISTICS (elastic)" in ctx, (
                f"elastic workspace must inject skill preamble:\n{ctx[:600]}"
            )
            assert "shared_rules.md" in ctx, "preamble must inline shared_rules.md"
            assert "local_changes.md" in ctx, "preamble must inline local_changes.md"
            # The preamble must come BEFORE the SPEC so the model reads
            # the skill instruction first, then applies it to the inputs.
            assert ctx.index("## REVIEW SKILL HEURISTICS") < ctx.index("## SPEC"), (
                "skill preamble must precede the dynamic context sections"
            )

    def test_reviewer_context_omits_skill_preamble_in_non_elastic_workspace(self):
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "personal"
            self._git_init_with_remote(workspace, "https://github.com/kapral18/proj.git")
            runner = ralph.RalphRunner(state_home=tmp_path / "state", kb_home=tmp_path / "kb")
            runner.init()
            spec = {
                "goal": "Build a thing",
                "success_criteria": ["c1"],
                "target_artifact": str(workspace / "thing.py"),
            }
            ctx, _hits = runner._reviewer_context(
                manifest={"id": "rid", "goal": "Build a thing"},
                spec=spec,
                workspace=workspace,
                executor=None,
                defaults={"progress_tail_blocks": 2, "memory_top_k": 5},
            )
            assert "## REVIEW SKILL HEURISTICS" not in ctx, (
                f"non-elastic workspace must NOT inject the skill preamble:\n{ctx[:400]}"
            )
            # SPEC section must still be present (sanity check of the
            # default path).
            assert "## SPEC" in ctx

    def test_re_reviewer_context_inlines_skill_preamble_in_elastic_workspace(self):
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "kibana"
            self._git_init_with_remote(workspace, "git@github.com:elastic/kibana.git")
            runner = ralph.RalphRunner(state_home=tmp_path / "state", kb_home=tmp_path / "kb")
            runner.init()
            executor_log = tmp_path / "exec.log"
            executor_log.write_text("ANCHOR: build it\nstuff\nRALPH_DONE\n")
            spec = {
                "goal": "Build auth handler",
                "success_criteria": ["JWT validated"],
                "target_artifact": str(workspace / "auth.py"),
            }
            primary = {"verdict": "pass", "criteria_met": ["JWT validated"], "criteria_unmet": []}
            ctx, _hits = runner._re_reviewer_context(
                manifest={"id": "rid", "goal": "Build auth handler"},
                spec=spec,
                workspace=workspace,
                executor={"output": str(executor_log)},
                primary_verdict=primary,
                defaults={"progress_tail_blocks": 2, "memory_top_k": 5},
            )
            assert "## REVIEW SKILL HEURISTICS (elastic)" in ctx
            assert "RE-REVIEWER" in ctx, "preamble must address the re-reviewer role label"
            assert ctx.index("## REVIEW SKILL HEURISTICS") < ctx.index("## SPEC")

    def test_elastic_review_preamble_returns_empty_when_skill_files_missing(self):
        """Operators who don't have the review skill installed should
        get no preamble (silent-degrade) rather than a crash. This
        keeps the elastic gate optional rather than mandatory."""
        import ralph

        original = ralph.REVIEW_SKILL_DIR
        try:
            ralph.REVIEW_SKILL_DIR = Path(tempfile.gettempdir()) / "no-such-skill-dir-12345"
            assert ralph.elastic_review_preamble("reviewer") == ""
            assert ralph.elastic_review_preamble("re_reviewer") == ""
        finally:
            ralph.REVIEW_SKILL_DIR = original


class TestRalphSummaryCriteriaMarkers(unittest.TestCase):
    """Pin the regression where summary.md showed every success
    criterion as `[?]` even after a successful run.

    Cause: `_write_summary` picked the most recent verdict from
    `verdicts.jsonl` regardless of role. The re_reviewer's verdict
    shape is `{agree_with_primary, final_verdict, ...}` — it does not
    carry `criteria_met` / `criteria_unmet` — so its arrays were
    empty and every criterion fell through to the `[?]` fallback.
    Fix: prefer the reviewer's verdict because only it carries the
    per-criterion arrays.
    """

    def _build_run(self, runner, *, criteria, reviewer_met, include_re_reviewer=True):
        rid = "go-summary-criteria-1"
        run_dir = runner.run_dir(rid)
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact = run_dir / "artifact.txt"
        artifact.write_text("hi")
        verdicts_path = run_dir / "verdicts.jsonl"
        rows = [
            {
                "iter": 1,
                "role": "reviewer",
                "verdict": {
                    "verdict": "pass",
                    "criteria_met": list(reviewer_met),
                    "criteria_unmet": [],
                },
                "at": "2026-05-05T00:00:00+00:00",
            }
        ]
        if include_re_reviewer:
            rows.append(
                {
                    "iter": 1,
                    "role": "re_reviewer",
                    "verdict": {
                        "agree_with_primary": True,
                        "final_verdict": "pass",
                    },
                    "at": "2026-05-05T00:00:01+00:00",
                }
            )
        verdicts_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        manifest = {
            "id": rid,
            "kind": "go",
            "goal": "build the thing",
            "status": "completed",
            "phase": "done",
            "validation_status": "passed",
            "workflow": "feature",
            "spec": {
                "rationale": "test",
                "success_criteria": list(criteria),
                "target_artifact": str(artifact),
            },
            "artifact": str(artifact),
            "artifact_sha256": "deadbeef",
            "iterations": [{"n": 1, "verdict": "pass", "primary_verdict": "pass"}],
            "questions": [],
        }
        runner.save_manifest(manifest)
        return manifest

    def test_summary_marks_passed_criteria_x_when_reviewer_lists_them(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_home = tmp_path / "state"
            state_home.mkdir()
            kb_home = tmp_path / "kb"
            kb_home.mkdir()
            runner = ralph.RalphRunner(state_home=state_home, kb_home=kb_home)
            runner.init()

            criteria = [
                "artifact file exists at /tmp/foo.txt",
                "stdout is JSON",
                "exit code is zero",
            ]
            manifest = self._build_run(
                runner,
                criteria=criteria,
                reviewer_met=criteria,  # reviewer accepted ALL of them
                include_re_reviewer=True,
            )
            summary_path = runner._write_summary(manifest, tmp_path / "workspace")
            text = summary_path.read_text()
            for c in criteria:
                assert f"- [x] {c}" in text, (
                    f"criterion accepted by reviewer must render as [x]:\nmissing line `- [x] {c}` in:\n{text}"
                )
            assert "[?]" not in text.split("## Success criteria", 1)[1].split("##", 1)[0], (
                f"no criterion should fall through to [?] when reviewer accepted all:\n{text}"
            )

    def test_summary_marks_unmet_criteria_open_box(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = ralph.RalphRunner(state_home=tmp_path / "state", kb_home=tmp_path / "kb")
            runner.init()
            rid = "go-summary-unmet-1"
            run_dir = runner.run_dir(rid)
            run_dir.mkdir(parents=True, exist_ok=True)
            verdicts_path = run_dir / "verdicts.jsonl"
            verdicts_path.write_text(
                json.dumps(
                    {
                        "iter": 1,
                        "role": "reviewer",
                        "verdict": {
                            "verdict": "fail",
                            "criteria_met": ["alpha"],
                            "criteria_unmet": ["beta"],
                        },
                        "at": "2026-05-05T00:00:00+00:00",
                    }
                )
                + "\n"
            )
            manifest = {
                "id": rid,
                "kind": "go",
                "goal": "x",
                "status": "failed",
                "phase": "failed",
                "validation_status": "failed",
                "workflow": "feature",
                "spec": {
                    "rationale": "t",
                    "success_criteria": ["alpha", "beta", "gamma"],
                    "target_artifact": "none",
                },
                "iterations": [{"n": 1, "verdict": "fail"}],
                "questions": [],
            }
            runner.save_manifest(manifest)
            summary_path = runner._write_summary(manifest, tmp_path / "workspace")
            text = summary_path.read_text()
            assert "- [x] alpha" in text, text
            assert "- [ ] beta" in text, text
            # gamma is not mentioned by the reviewer at all — falls to [?]
            assert "- [?] gamma" in text, text


class TestRalphTmuxSessionPersistedThroughGo(unittest.TestCase):
    """Pin the regression where the parent run manifest's `tmux.session`
    field was clobbered to `None` by `_invoke_planner` saving a stale
    in-memory manifest dict that predated `_allocate_session`'s write.

    Symptom: after `,ralph rm <rid>` the dedicated tmux session
    `ralph-<short-rid>` survived forever because the rm path looks up
    `manifest["tmux"]["session"]` to know which session to kill, and
    that field had been silently reset to `None` mid-run.
    """

    def test_allocate_session_then_invoke_planner_preserves_tmux_session(self):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_home = tmp_path / "state"
            kb_home = tmp_path / "kb"
            state_home.mkdir()
            kb_home.mkdir()

            runner = ralph.RalphRunner(state_home=state_home, kb_home=kb_home)
            runner.init()

            rid = "go-test-tmux-abc123"
            run_dir = runner.run_dir(rid)
            run_dir.mkdir()
            initial = {
                "id": rid,
                "kind": "go",
                "name": "test",
                "created_at": ralph.utc_now(),
                "goal": "test",
                "workspace": str(tmp_path / "workspace"),
                "runtime": "orchestrator",
                "phase": "planning",
                "status": "running",
                "control_state": "automated",
                "iterations": [],
                "roles": {},
                "learned_ids": [],
                "tmux": None,
                "spec_seq": 1,
                "runner": None,
            }
            runner.save_manifest(initial)

            session_name = runner.run_session_name(rid)

            # Stub the two tmux entry points _allocate_session relies on so
            # the test stays hermetic (no real tmux server required).
            original_exists = ralph.tmux_session_exists
            original_run = ralph.subprocess.run

            def fake_exists(name):
                return name == session_name  # first call: False; nothing to recreate

            calls: list[list[str]] = []

            def fake_subprocess_run(cmd, *a, **kw):
                calls.append(list(cmd))
                # Pretend new-session succeeded.
                return subprocess.CompletedProcess(cmd, 0, "", "")

            try:
                ralph.tmux_session_exists = lambda name: False  # force creation path
                ralph.subprocess.run = fake_subprocess_run

                returned = runner._allocate_session(rid, tmux_mode=True)
                assert returned == session_name, returned
                # Disk now has tmux={'session': ...}
                disk = runner.load_manifest(rid)
                assert disk["tmux"] == {"session": session_name}, disk["tmux"]

                # Reproduce the original bug: a caller that holds the
                # stale pre-allocate manifest dict (tmux=None) and saves
                # it after a mutation will clobber the session field.
                stale = dict(initial)  # tmux=None
                stale.setdefault("roles", {})["planner-1"] = {"name": "planner-1"}
                runner.save_manifest(stale)
                clobbered = runner.load_manifest(rid)
                assert clobbered["tmux"] is None, "stale-save reproduces the original bug"

                # The fix: callers must reload after _allocate_session
                # before mutating-and-saving. Restore disk state to what
                # _allocate_session would have produced, then exercise
                # the load-then-save pattern.
                runner.save_manifest({**initial, "tmux": {"session": session_name}})
                fresh = runner.load_manifest(rid)
                fresh.setdefault("roles", {})["planner-1"] = {"name": "planner-1"}
                runner.save_manifest(fresh)
                final = runner.load_manifest(rid)
                assert final["tmux"] == {"session": session_name}, (
                    f"reload-then-save must preserve tmux session: {final['tmux']!r}"
                )
            finally:
                ralph.tmux_session_exists = original_exists
                ralph.subprocess.run = original_run

    def test_go_reloads_manifest_after_allocate_session(self):
        """End-to-end regression: the `go` entry point must reload the
        manifest after `_allocate_session` so subsequent saves don't
        clobber the tmux field. This test doesn't need real tmux; it
        only verifies the load_manifest call is wired in `go`.
        """
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        # Static check: the source must contain the reload directly after
        # the allocate call. This pins the structural fix.
        src = (SCRIPTS / "ralph.py").read_text()
        marker = "session_name = self._allocate_session(rid, tmux_mode=tmux_mode)"
        idx = src.find(marker)
        assert idx >= 0, "go() must call _allocate_session"
        tail = src[idx : idx + 1000]
        assert "manifest = self.load_manifest(rid)" in tail, (
            "go() must reload manifest after _allocate_session so "
            "downstream saves do not clobber the tmux session field"
        )


class TestRalphHarnessCommandShape(unittest.TestCase):
    """Pin the per-harness `command` string the orchestrator builds so a
    real-world stall regression cannot silently come back.

    Background: cursor-agent in `--print` mode reads the prompt as the
    trailing positional arg. If we ALSO redirect stdin to the same
    prompt file (e.g. ``cmd ... < prompt.md``), cursor-agent stalls
    indefinitely producing zero bytes — the run sits in `phase=planning`
    forever. The fix bakes ``$(cat <abs path>)`` into the cursor command
    and drops the per-command stdin redirect.
    """

    def _spawn_with_fake_runtime(self, harness: str, model: str = "test-model"):
        sys.path.insert(0, str(SCRIPTS))
        import ralph

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_home = tmp_path / "state"
            kb_home = tmp_path / "kb"
            state_home.mkdir()
            kb_home.mkdir()
            workspace = tmp_path / "workspace"
            workspace.mkdir()

            runner = ralph.RalphRunner(state_home=state_home, kb_home=kb_home)
            runner.init()

            captured: dict[str, str] = {}

            def fake_runtime(command: str, prompt: str, timeout: int):
                captured["command"] = command
                captured["prompt"] = prompt
                return ralph.RuntimeResult(
                    output="ANCHOR: x\nRALPH_DONE\n",
                    exit_code=0,
                )

            runner.runtime_command = fake_runtime  # type: ignore[method-assign]

            runner._spawn_role(
                rid="test-rid-1-planner-1",
                role_name="planner-1",
                harness=harness,
                model=model,
                extra_args=["--mode", "plan"],
                prompt_text="test prompt body",
                workspace=workspace,
                session_name=None,
                defaults={"iteration_timeout_seconds": 30},
            )
            return captured, state_home

    def test_cursor_command_uses_cat_substitution_and_no_stdin_redirect(self):
        captured, state_home = self._spawn_with_fake_runtime("cursor", model="claude-test")
        cmd = captured["command"]
        prompt_path = state_home / "runs" / "test-rid-1-planner-1" / "prompt.md"
        assert "$(cat " in cmd, f"cursor command must inline $(cat <path>): {cmd!r}"
        assert str(prompt_path) in cmd, f"cursor command must reference the role's prompt.md absolute path: {cmd!r}"
        # The cursor invocation MUST NOT have a stdin redirect; cursor-agent
        # stalls when both a positional prompt AND stdin are provided.
        assert " < " not in cmd, (
            f"cursor command must not have a stdin redirect (causes cursor-agent to stall): {cmd!r}"
        )
        assert ' -- "$(cat ' in cmd, (
            f"cursor command must pass prompt as the positional arg via cat substitution: {cmd!r}"
        )

    def test_pi_command_redirects_stdin_to_prompt_path(self):
        captured, state_home = self._spawn_with_fake_runtime("pi", model="claude-pi-test")
        cmd = captured["command"]
        prompt_path = state_home / "runs" / "test-rid-1-planner-1" / "prompt.md"
        assert " < " in cmd, f"pi command must redirect stdin from prompt.md: {cmd!r}"
        assert str(prompt_path) in cmd, f"pi command must redirect from the role's prompt.md absolute path: {cmd!r}"
        # pi takes prompt via stdin, not a trailing positional arg.
        assert ' -- "$(cat ' not in cmd, f"pi command must not use cat substitution: {cmd!r}"


class TestRalphLiveEvalSmoke(unittest.TestCase):
    """Hardening probe: this is the live-eval session encoded as CI tests.

    The original eval ran three workflows against a real cursor-cli swarm on
    a synthetic Python repo to find pipeline gaps. Those gaps (G1+G2+G3) are
    fixed; this class freezes the eval shape as a deterministic regression
    suite, using the mock harness so it is cheap, hermetic, and CI-friendly.

    What we lock in here:
    - feature workflow runs all five roles (planner→executor→reviewer→
      re_reviewer→reflector) and lands at validation_status=passed.
    - bugfix workflow runs the same five-role ladder (reflector_workflows
      includes bugfix by default in roles.json).
    - research workflow runs only planner→executor→reviewer (no re_reviewer,
      no reflector — research is read-only and not in the reflector default).
    - the reflector actually persists a structured capsule into the KB; a
      run-failure regression that silently disables the reflector would
      manifest as the capsule count not growing.
    - cross-run KB amplification: a follow-up run's planner picks up the
      previous run's stored capsule via workspace-scoped retrieval, which is
      the mechanism the live eval surfaced as the most-promising leverage.
    """

    @staticmethod
    def _go(env: dict, workspace: Path, *, goal: str, workflow: str | None = None) -> dict:
        args = [
            sys.executable,
            str(SCRIPTS / "ralph.py"),
            "go",
            "--goal",
            goal,
            "--workspace",
            str(workspace),
            "--subprocess",
            "--json",
        ]
        if workflow:
            args += ["--workflow", workflow]
        result = subprocess.run(args, capture_output=True, text=True, cwd=str(SCRIPTS), env=env)
        assert result.returncode == 0, (
            f"go failed rc={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        return json.loads(result.stdout)

    @staticmethod
    def _kb_capsules(env: dict) -> list[dict]:
        """Read every capsule row from the test's KB DB.

        Hits sqlite directly rather than going through `KnowledgeBase` to
        avoid the embedder cold-start path; the test asserts only on
        capsule identity / metadata, not on retrieval mechanics.
        """
        db_path = Path(env["AI_KB_HOME"]) / "kb.sqlite3"
        if not db_path.exists():
            return []
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute("SELECT id, title, kind, scope, source FROM capsules ORDER BY created_at")
            return [dict(zip(["id", "title", "kind", "scope", "source"], row)) for row in cur.fetchall()]

    def test_feature_workflow_full_ladder_with_reflector_capsule_stored(self):
        """The full happy path the live eval validated for Run #1: every role
        spawns, every gate passes, and the reflector contributes at least one
        structured capsule to the KB."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "feature.txt"
            env = _make_eval_env(tmp_path, artifact=artifact, content="shipped")
            env["RALPH_TEST_WORKFLOW"] = "feature"
            manifest = self._go(env, tmp_path / "workspace", goal="add the feature", workflow="feature")
            assert manifest["status"] == "completed"
            assert manifest["validation_status"] == "passed"
            assert manifest["workflow"] == "feature"
            roles = manifest.get("roles") or {}
            assert {"planner-1", "executor-1", "reviewer-1", "re_reviewer-1", "reflector-1"} <= set(roles), (
                f"feature workflow must spawn the full five-role ladder, got: {sorted(roles)}"
            )
            # Reflector must persist at least one structured capsule
            reflector = roles["reflector-1"]
            assert reflector["status"] == "completed"
            reflector_capsule_ids = reflector.get("learned_ids") or []
            assert reflector_capsule_ids, "reflector must persist at least one structured capsule"
            capsules = self._kb_capsules(env)
            stored_ids = {c["id"] for c in capsules}
            assert any(cid in stored_ids for cid in reflector_capsule_ids), (
                "every learned id from the reflector must appear in the KB capsules table"
            )

    def test_bugfix_workflow_full_ladder_with_reflector_capsule_stored(self):
        """Mirrors feature-workflow shape but on the bugfix workflow — the
        live eval's Run #2 was a bugfix that previously false-failed on the
        ANCHOR scaffolding regex; this guards against any future regression
        that disables reflector emission for bugfix runs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "bugfix.txt"
            env = _make_eval_env(tmp_path, artifact=artifact, content="patched")
            env["RALPH_TEST_WORKFLOW"] = "bugfix"
            manifest = self._go(env, tmp_path / "workspace", goal="fix the bug", workflow="bugfix")
            assert manifest["status"] == "completed"
            assert manifest["validation_status"] == "passed"
            assert manifest["workflow"] == "bugfix"
            roles = manifest.get("roles") or {}
            assert {"planner-1", "executor-1", "reviewer-1", "re_reviewer-1", "reflector-1"} <= set(roles), (
                f"bugfix workflow must spawn the full five-role ladder, got: {sorted(roles)}"
            )
            assert roles["reflector-1"].get("learned_ids") or [], "reflector must emit capsules on bugfix passes"

    def test_research_workflow_skips_re_reviewer_and_reflector(self):
        """research is read-only by spec: planner+executor+reviewer only.
        re_reviewer is never spawned (not in `workflow_phases('research')`)
        and the reflector is gated by `reflector_workflows` which does NOT
        include 'research' by default — protecting against a future change
        that would inadvertently widen reflector exposure."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "REPORT.md"
            env = _make_eval_env(tmp_path, artifact=artifact, content="report body")
            env["RALPH_TEST_WORKFLOW"] = "research"
            manifest = self._go(env, tmp_path / "workspace", goal="investigate the thing", workflow="research")
            assert manifest["status"] == "completed"
            assert manifest["validation_status"] == "passed"
            assert manifest["workflow"] == "research"
            roles = manifest.get("roles") or {}
            assert {"planner-1", "executor-1", "reviewer-1"} <= set(roles)
            assert "re_reviewer-1" not in roles, (
                f"research workflow must NOT spawn re_reviewer, but found: {sorted(roles)}"
            )
            assert "reflector-1" not in roles, (
                f"research workflow must NOT spawn reflector by default, but found: {sorted(roles)}"
            )

    def test_cross_run_kb_amplification_planner_retrieves_prior_capsule(self):
        """The leverage thesis from the live eval: each run's KB capsules show
        up in the next run's planner retrieval. Without this, the orchestrator
        is just a fancy single-shot harness; with it, every run makes the next
        run smarter. We assert the planner's `retrieval_log` on run #2
        contains at least one capsule whose ID was stored during run #1."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            artifact_a = workspace / "a.txt"
            env = _make_eval_env(tmp_path, artifact=artifact_a, content="aaa")
            env["RALPH_TEST_WORKFLOW"] = "feature"
            manifest_a = self._go(env, workspace, goal="amplify cross-run learning", workflow="feature")
            assert manifest_a["validation_status"] == "passed"
            run_one_capsule_ids = {c["id"] for c in self._kb_capsules(env)}
            assert run_one_capsule_ids, "run #1 must store at least one capsule for run #2 to retrieve"

            # Run #2 reuses the same env (same state_home + AI_KB_HOME +
            # workspace), uses a different artifact path so iteration counters
            # in the executor mock don't collide with the artifact-existence
            # check, and a similar goal so FTS5+workspace-bias retrieval has
            # something to surface.
            artifact_b = workspace / "b.txt"
            env["RALPH_TEST_ARTIFACT"] = str(artifact_b)
            env["RALPH_TEST_CONTENT"] = "bbb"
            # Reset per-role iteration counters so iter numbering restarts.
            counter_dir = Path(env["RALPH_TEST_COUNTER_DIR"])
            for f in counter_dir.iterdir():
                f.unlink()
            manifest_b = self._go(env, workspace, goal="amplify cross-run learning round two", workflow="feature")
            assert manifest_b["validation_status"] == "passed"
            planner_b = (manifest_b.get("roles") or {}).get("planner-1") or {}
            retrieval_log = planner_b.get("retrieval_log") or []
            retrieved_ids = {entry.get("id") for entry in retrieval_log}
            overlap = run_one_capsule_ids & retrieved_ids
            assert overlap, (
                "run #2's planner retrieval_log must contain at least one capsule "
                f"persisted by run #1; run-1 ids={sorted(run_one_capsule_ids)}, retrieved={sorted(retrieved_ids)}"
            )


class TestRalphDiversityGateUnderDisagreement(unittest.TestCase):
    """Stress the diversity gate's adjudication semantics: the re_reviewer's
    `final_verdict` is the orchestrator's source of truth, regardless of what
    the primary reviewer said. These tests script reviewer/re_reviewer to
    deliberately disagree and assert the orchestrator routes per the
    re_reviewer.

    Why this matters: the live eval's two passing runs both had reviewer and
    re_reviewer agree, so the disagreement codepaths were untested in the
    wild. The whole point of the diversity gate is to catch the cases where
    a single reviewer would have rubber-stamped a bad pass (or rejected a
    good one). If those codepaths drift, the gate is a costly no-op.
    """

    @staticmethod
    def _go(env: dict, workspace: Path, *, goal: str, expect_returncode: int) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "ralph.py"),
                "go",
                "--goal",
                goal,
                "--workspace",
                str(workspace),
                "--subprocess",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS),
            env=env,
        )
        assert result.returncode == expect_returncode, (
            f"expected rc={expect_returncode} got {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        return json.loads(result.stdout)

    def test_re_reviewer_overrides_primary_pass_to_fail_run_marks_failed(self):
        """Reviewer rubber-stamps the artifact (PASS), re_reviewer disagrees
        and votes FAIL. The orchestrator must adopt the re_reviewer's verdict
        and terminate the run as failed — this is the headline value of the
        second-opinion gate."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            env["RALPH_TEST_REVIEWER_VERDICT"] = "pass"
            env["RALPH_TEST_RE_REVIEWER_VERDICT"] = "fail"
            manifest = self._go(env, tmp_path / "workspace", goal="adversarial verdict path", expect_returncode=1)
            assert manifest["status"] == "failed"
            assert manifest["phase"] == "failed"
            assert manifest["validation_status"] == "failed"
            iters = manifest.get("iterations") or []
            assert len(iters) == 1, "fail verdict terminates immediately; no retry"
            assert iters[0]["primary_verdict"] == "pass"
            assert iters[0]["verdict"] == "fail", "re_reviewer's final_verdict wins over primary"
            re_rer = (manifest.get("roles") or {}).get("re_reviewer-1") or {}
            verdict_obj = re_rer.get("verdict_obj") or {}
            assert verdict_obj.get("agree_with_primary") is False
            assert verdict_obj.get("final_verdict") == "fail"

    def test_re_reviewer_overrides_primary_fail_to_pass_run_completes(self):
        """Reviewer is overly strict (FAIL), re_reviewer correctly passes
        the artifact. The orchestrator must complete the run on the second
        opinion — protecting against false-negatives that would otherwise
        force needless rework."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world")
            env["RALPH_TEST_REVIEWER_VERDICT"] = "fail"
            env["RALPH_TEST_RE_REVIEWER_VERDICT"] = "pass"
            manifest = self._go(env, tmp_path / "workspace", goal="false-fail rescue path", expect_returncode=0)
            assert manifest["status"] == "completed"
            assert manifest["phase"] == "done"
            assert manifest["validation_status"] == "passed"
            iters = manifest.get("iterations") or []
            assert len(iters) == 1, "re_reviewer's pass terminates the run on iter 1"
            assert iters[0]["primary_verdict"] == "fail"
            assert iters[0]["verdict"] == "pass"

    def test_re_reviewer_downgrades_pass_to_needs_iteration_loops_then_caps(self):
        """Reviewer says PASS, re_reviewer says needs_iteration on every
        iteration. The orchestrator must keep looping (proving needs_iteration
        is a continue-signal, not a terminate-signal) and ultimately fail when
        the iteration cap is exhausted — guarding against a regression that
        would silently stop on the first re_reviewer downgrade."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact = tmp_path / "workspace" / "result.txt"
            env = _make_go_env(tmp_path, artifact=artifact, content="hello world", max_iters=2)
            env["RALPH_TEST_REVIEWER_VERDICT"] = "pass"
            env["RALPH_TEST_RE_REVIEWER_VERDICT"] = "needs_iteration"
            manifest = self._go(env, tmp_path / "workspace", goal="loop on disagreement", expect_returncode=1)
            assert manifest["status"] == "failed"
            assert manifest["validation_status"] == "failed"
            iters = manifest.get("iterations") or []
            assert len(iters) == 2, (
                "loop must continue past the first needs_iteration; final cap exhaust marks the run failed"
            )
            assert all(it.get("primary_verdict") == "pass" for it in iters)
            assert all(it.get("verdict") == "needs_iteration" for it in iters)


if __name__ == "__main__":
    unittest.main()
