#!/usr/bin/env python3
"""Tests for affected-first scripts/check.py planning."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO
from check import SLOW_SHARDS, collect_changed, plan_check, production_probe_paths
from test_runner import NOT_TEST_FILES, discover_files, resolve_files


class TestCheckPlan(unittest.TestCase):
    """WHEN planning make check from a changed-path set."""

    def test_WHEN_only_nvim_lua_changes_SHOULD_skip_tmux_picker_shards(self):
        plan = plan_check(
            REPO,
            full=False,
            changed=("home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_summarize-commit.lua",),
            add_delete=False,
        )
        assert plan.mode == "affected"
        assert "tests/test_invariants.py" in plan.tests
        assert "tests/test_tmux_pickers.py" not in plan.tests
        assert "tests/test_bin_commands.py" not in plan.tests
        assert "verify-templates" not in plan.gates
        assert plan.fmt_paths[-1].endswith("readonly_summarize-commit.lua")

    def test_WHEN_tmux_picker_changes_SHOULD_select_picker_shards_not_adapters(self):
        plan = plan_check(
            REPO,
            full=False,
            changed=("home/dot_config/exact_tmux/exact_scripts/pickers/github/executable_gh_picker.sh",),
            add_delete=False,
        )
        assert "tests/test_tmux_pickers.py" in plan.tests
        assert "tests/test_gh_picker_dispatch_state.py" in plan.tests
        assert "tests/test_codex_adapter.py" not in plan.tests
        assert "tests/test_bin_commands.py" not in plan.tests

    def test_WHEN_tmpl_changes_SHOULD_run_verify_templates(self):
        plan = plan_check(
            REPO,
            full=False,
            changed=("home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl",),
            add_delete=False,
        )
        assert "verify-templates" in plan.gates
        assert "tests/test_invariants.py" in plan.tests

    def test_WHEN_sop_changes_SHOULD_run_focused_sop_policy_shard(self):
        plan = plan_check(REPO, full=False, changed=("home/readonly_AGENTS.md",), add_delete=False)
        assert "tests/test_sop_policy_invariants.py" in plan.tests
        assert "tests/test_invariants.py" not in plan.tests

    def test_WHEN_agent_prompt_prefix_changes_SHOULD_not_run_slow_picker_shards(self):
        plan = plan_check(
            REPO,
            full=False,
            changed=("home/dot_config/exact_tmux/agent_prompts/prefix.txt",),
            add_delete=False,
        )
        assert "tests/test_sop_policy_invariants.py" in plan.tests
        for shard in SLOW_SHARDS:
            assert shard not in plan.tests

    def test_WHEN_hook_readme_changes_SHOULD_not_run_hook_runtime_shards(self):
        plan = plan_check(
            REPO,
            full=False,
            changed=("home/exact_dot_agents/exact_hooks/readonly_README.md",),
            add_delete=False,
        )
        assert "tests/test_agent_hooks.py" not in plan.tests
        assert "tests/test_agent_skill_invariants.py" not in plan.tests

    def test_WHEN_hook_source_changes_SHOULD_run_hook_runtime_shards(self):
        plan = plan_check(
            REPO,
            full=False,
            changed=("home/exact_dot_agents/exact_hooks/executable_session_context.py",),
            add_delete=False,
        )
        assert "tests/test_agent_hooks.py" in plan.tests
        assert "tests/test_agent_skill_invariants.py" in plan.tests

    def test_WHEN_a_file_is_added_SHOULD_run_verify_mermaids(self):
        plan = plan_check(REPO, full=False, changed=("docs/topics/code-quality/formatting.md",), add_delete=True)
        assert "verify-mermaids" in plan.gates
        assert "verify-docs-navigation" in plan.gates

    def test_WHEN_nothing_changed_SHOULD_select_no_work(self):
        plan = plan_check(REPO, full=False, changed=(), add_delete=False)
        assert plan.tests == ()
        assert plan.gates == ()
        assert plan.fmt_paths == ()
        assert plan.extra == ()

    def test_WHEN_full_SHOULD_include_every_live_shard_and_gate(self):
        plan = plan_check(REPO, full=True, changed=(), add_delete=False)
        assert plan.mode == "full"
        assert "tests/test_tmux_pickers.py" in plan.tests
        assert "test_yaml_parser.py" in plan.tests
        assert "test_runner.py" not in plan.tests
        assert "verify-templates" in plan.gates
        assert "verify-agent-policy" in plan.gates
        assert "fish-history-merge" in plan.extra

    def test_WHEN_q_fish_completion_changes_SHOULD_run_q_shard(self):
        plan = plan_check(
            REPO,
            full=False,
            changed=("home/dot_config/fish/completions/readonly_,q.fish",),
            add_delete=False,
        )
        assert plan.tests == ("tests/test_q.py",)
        assert plan.gates == ("verify-bin-surface",)

    def test_WHEN_check_py_changes_SHOULD_run_test_check(self):
        plan = plan_check(REPO, full=False, changed=("scripts/check.py",), add_delete=False)
        assert "test_check.py" in plan.tests
        assert "test_runner.py" not in plan.tests
        assert "tests/test_tmux_pickers.py" not in plan.tests

    def test_WHEN_test_runner_changes_SHOULD_not_select_itself_as_a_shard(self):
        plan = plan_check(REPO, full=False, changed=("scripts/test_runner.py",), add_delete=False)
        assert "test_check.py" in plan.tests
        assert "test_runner.py" not in plan.tests

    def test_WHEN_chezmoi_lib_shell_changes_SHOULD_run_test_chezmoi_lib(self):
        plan = plan_check(REPO, full=False, changed=("scripts/chezmoi_lib.sh",), add_delete=False)
        assert "test_chezmoi_lib.py" in plan.tests
        assert "tests/test_tmux_pickers.py" not in plan.tests

    def test_WHEN_yaml_parser_changes_SHOULD_run_direct_importer_tests(self):
        plan = plan_check(REPO, full=False, changed=("scripts/yaml_parser.py",), add_delete=False)
        assert "test_yaml_parser.py" in plan.tests
        assert "test_ai_models.py" in plan.tests
        assert "test_mcp_registry.py" in plan.tests
        assert "tests/test_tmux_pickers.py" not in plan.tests

    def test_WHEN_llama_model_sources_change_SHOULD_run_model_mirror_shard(self):
        changed = (
            "home/dot_config/llama.cpp/models.ini.tmpl",
            "home/dot_codex/readonly_llama-cpp-model-catalog.json.tmpl",
            "home/dot_pi/agent/readonly_models.json",
            "home/dot_pi/agent/readonly_models.personal.json",
            "home/readonly_dot_default-llama-cpp-models.tmpl",
        )
        for path in changed:
            with self.subTest(path=path):
                plan = plan_check(REPO, full=False, changed=(path,), add_delete=False)
                assert "test_model_mirrors.py" in plan.tests
                if path == "home/dot_config/llama.cpp/models.ini.tmpl":
                    assert "tests/test_llama_cpp_lifecycle.py" in plan.tests

    def test_WHEN_copilot_adapter_changes_SHOULD_skip_bin_commands_and_pickers(self):
        plan = plan_check(
            REPO,
            full=False,
            changed=("home/exact_lib/exact_,copilot-adapter/main.py",),
            add_delete=False,
        )
        assert "tests/test_copilot_adapter.py" in plan.tests
        assert "tests/test_bin_commands.py" not in plan.tests
        assert "tests/test_tmux_pickers.py" not in plan.tests

    def test_WHEN_test_support_changes_SHOULD_run_cheap_shards_not_slow_pickers(self):
        plan = plan_check(REPO, full=False, changed=("scripts/_test_support.py",), add_delete=False)
        assert "test_yaml_parser.py" in plan.tests
        assert "test_check.py" in plan.tests
        for shard in SLOW_SHARDS:
            assert shard not in plan.tests

    def test_WHEN_every_live_shard_SHOULD_be_reachable_from_a_production_path(self):
        selected: set[str] = set()
        for path in production_probe_paths(REPO):
            selected.update(plan_check(REPO, full=False, changed=(path,), add_delete=False).tests)
        live = {path.relative_to(REPO / "scripts").as_posix() for path in discover_files()}
        assert sorted(live - selected) == []


class TestCheckEntryPoints(unittest.TestCase):
    """WHEN invoking make check or pre-commit."""

    def test_WHEN_makefile_check_SHOULD_stay_affected_and_check_full_uses_full(self):
        text = (REPO / "Makefile").read_text(encoding="utf-8")
        recipes: dict[str, list[str]] = {}
        current = None
        for line in text.splitlines():
            if line.startswith("\t"):
                if current is not None:
                    recipes.setdefault(current, []).append(line[1:])
                continue
            if line[:1] in {"", "#", "."}:
                current = None
                continue
            if ":" in line:
                current = line.split(":", 1)[0]
        assert recipes.get("check") == ["bin/check"]
        assert recipes.get("check-full") == ["CHECK_FULL=1 bin/check --full"]
        assert "check: lint " not in text

    def test_WHEN_agents_md_SHOULD_forbid_the_full_suite(self):
        text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        assert "Agents must not run `make check-full`" in text
        assert "Use `make check-full`" not in text

    def test_WHEN_agents_md_SHOULD_require_new_code_on_the_affected_map(self):
        text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        assert "keep them on the affected map in the same change" in text
        assert "add a `TEST_RULES` row" in text
        assert "Do not leave a new shard reachable only by `make check-full`" in text

    def test_WHEN_pre_commit_hook_SHOULD_run_staged_check_not_full_suite(self):
        text = (REPO / ".githooks/pre-commit").read_text(encoding="utf-8")
        lines = [line.strip() for line in text.splitlines()]
        assert "bin/check --staged" in lines
        assert "bin/check --full" not in lines
        assert "make -s check" not in text


class TestTestRunnerDiscovery(unittest.TestCase):
    """WHEN listing unittest shards."""

    def test_WHEN_discovering_shards_SHOULD_omit_the_runner_module(self):
        names = {path.name for path in discover_files()}
        assert "test_runner.py" not in names
        assert "test_runner.py" in NOT_TEST_FILES
        assert (REPO / "scripts" / "test_yaml_parser.py").name in names

    def test_WHEN_every_discovered_shard_SHOULD_define_a_TestCase(self):
        missing = []
        for path in discover_files():
            text = path.read_text(encoding="utf-8")
            if "unittest.TestCase" not in text and "(unittest.TestCase)" not in text:
                missing.append(path.name)
        assert missing == []

    def test_WHEN_resolving_the_runner_path_SHOULD_drop_it(self):
        assert resolve_files(["test_runner.py"]) == []


class TestCollectChanged(unittest.TestCase):
    """WHEN reading git dirty paths."""

    def test_WHEN_worktree_has_an_untracked_file_SHOULD_include_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True)
            (root / "tracked.txt").write_text("a\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=root, check=True)
            (root / "tracked.txt").write_text("b\n", encoding="utf-8")
            (root / "new.txt").write_text("n\n", encoding="utf-8")
            names, add_delete = collect_changed(root, staged=False)
            assert "tracked.txt" in names
            assert "new.txt" in names
            assert add_delete is True

            subprocess.run(["git", "add", "new.txt"], cwd=root, check=True)
            staged, staged_add = collect_changed(root, staged=True)
            assert staged == ("new.txt",)
            assert staged_add is True


class TestCheckCli(unittest.TestCase):
    """WHEN invoking scripts/check.py."""

    def test_WHEN_print_plan_with_full_SHOULD_emit_json_mode_full(self):
        env = os.environ.copy()
        env.pop("CHECK_FULL", None)
        result = subprocess.run(
            ["python3", "scripts/check.py", "--full", "--print-plan"],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["mode"] == "full"
        assert "test_yaml_parser.py" in payload["tests"]
        assert "test_runner.py" not in payload["tests"]

    def test_WHEN_full_run_without_CHECK_FULL_SHOULD_refuse(self):
        env = os.environ.copy()
        env.pop("CHECK_FULL", None)
        result = subprocess.run(
            ["python3", "scripts/check.py", "--full"],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=3,
        )
        assert result.returncode == 2
        assert "CHECK_FULL=1" in result.stderr
        assert "check: full" not in result.stdout


if __name__ == "__main__":
    unittest.main()
