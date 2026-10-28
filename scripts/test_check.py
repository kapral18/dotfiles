#!/usr/bin/env python3
"""Tests for affected-first scripts/check.py planning."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from _test_support import REPO
from check import SLOW_SHARDS, collect_changed, plan_check, production_probe_paths
from test_runner import discover_files, resolve_files


class TestCheckPlan(unittest.TestCase):
    """WHEN planning make check from a changed-path set."""

    def test_WHEN_only_nvim_lua_changes_SHOULD_skip_tmux_picker_shards(self):
        plan = plan_check(
            REPO,
            full=False,
            changed=("home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_summarize-commit.lua",),
        )
        assert plan.mode == "affected"
        assert "tests/test_invariants.py" in plan.tests
        assert "tests/test_tmux_pickers.py" not in plan.tests
        assert "verify-templates" not in plan.gates
        assert plan.fmt_paths[-1].endswith("readonly_summarize-commit.lua")

    def test_WHEN_tmpl_changes_SHOULD_run_verify_templates(self):
        plan = plan_check(
            REPO,
            full=False,
            changed=("home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl",),
        )
        assert "verify-templates" in plan.gates
        assert "tests/test_invariants.py" in plan.tests

    def test_WHEN_nothing_changed_SHOULD_select_no_work(self):
        plan = plan_check(REPO, full=False, changed=())
        assert plan.tests == ()
        assert plan.gates == ()
        assert plan.fmt_paths == ()
        assert plan.extra == ()

    def test_WHEN_full_SHOULD_include_every_live_shard_and_gate(self):
        plan = plan_check(REPO, full=True, changed=())
        assert plan.mode == "full"
        assert "tests/test_tmux_pickers.py" in plan.tests
        assert "test_yaml_parser.py" in plan.tests
        assert "test_runner.py" not in plan.tests
        assert "verify-templates" in plan.gates
        assert "fish-history-merge" in plan.extra

    def test_WHEN_check_py_changes_SHOULD_run_test_check(self):
        plan = plan_check(REPO, full=False, changed=("scripts/check.py",))
        assert "test_check.py" in plan.tests
        assert "test_runner.py" not in plan.tests
        assert "tests/test_tmux_pickers.py" not in plan.tests

    def test_WHEN_test_runner_changes_SHOULD_not_select_itself_as_a_shard(self):
        plan = plan_check(REPO, full=False, changed=("scripts/test_runner.py",))
        assert "test_check.py" in plan.tests
        assert "test_runner.py" not in plan.tests

    def test_WHEN_chezmoi_lib_shell_changes_SHOULD_run_test_chezmoi_lib(self):
        plan = plan_check(REPO, full=False, changed=("scripts/chezmoi_lib.sh",))
        assert "test_chezmoi_lib.py" in plan.tests
        assert "tests/test_tmux_pickers.py" not in plan.tests

    def test_WHEN_yaml_parser_changes_SHOULD_run_direct_importer_tests(self):
        plan = plan_check(REPO, full=False, changed=("scripts/yaml_parser.py",))
        assert "test_yaml_parser.py" in plan.tests
        assert "test_mcp_registry.py" in plan.tests
        assert "tests/test_tmux_pickers.py" not in plan.tests

    def test_WHEN_test_support_changes_SHOULD_run_cheap_shards_not_slow_pickers(self):
        plan = plan_check(REPO, full=False, changed=("scripts/_test_support.py",))
        assert "test_yaml_parser.py" in plan.tests
        assert "test_check.py" in plan.tests
        for shard in SLOW_SHARDS:
            assert shard not in plan.tests

    def test_WHEN_every_live_shard_SHOULD_be_reachable_from_a_production_path(self):
        selected: set[str] = set()
        for path in production_probe_paths(REPO):
            selected.update(plan_check(REPO, full=False, changed=(path,)).tests)
        live = {path.relative_to(REPO / "scripts").as_posix() for path in discover_files()}
        assert sorted(live - selected) == []


class TestTestRunnerDiscovery(unittest.TestCase):
    """WHEN listing unittest shards."""

    def test_WHEN_resolving_the_runner_path_SHOULD_drop_it(self):
        assert resolve_files(["test_runner.py"]) == []


class TestTestRunnerIsolation(unittest.TestCase):
    """WHEN shards run, ambient state and the source tree stay untouched."""

    def _run_fixture(self, *, fail: bool) -> tuple[subprocess.CompletedProcess[str], list[dict]]:
        scratch = tempfile.TemporaryDirectory(prefix="runner-contract-")
        self.addCleanup(scratch.cleanup)
        root = Path(scratch.name)
        scripts = root / "scripts"
        scripts.mkdir()
        shutil.copy2(REPO / "scripts/test_runner.py", scripts / "test_runner.py")
        ambient = root / "ambient"
        ambient.mkdir()
        reports = root / "reports"
        reports.mkdir()
        source = textwrap.dedent("""
            import json
            import os
            import tempfile
            import unittest
            from pathlib import Path

            class Probe(unittest.TestCase):
                def test_state(self):
                    paths = {
                        "cwd": str(Path.cwd()),
                        "home": str(Path.home()),
                        "tmp": tempfile.gettempdir(),
                        **{key: os.environ[key] for key in (
                            "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME",
                            "XDG_STATE_HOME", "XDG_RUNTIME_DIR", "TMUX_TMPDIR",
                        )},
                    }
                    for value in paths.values():
                        Path(value, "probe").write_text(__name__)
                    report = {
                        "paths": paths,
                        "selectors": sorted(key for key in os.environ
                                            if key.startswith("GIT_") or key in ("TMUX", "TMUX_PANE", "LEAK_SENTINEL")),
                    }
                    Path(REPORTS, __name__ + ".json").write_text(json.dumps(report))
                    self.assertFalse(FAIL, "deliberate shard failure")
        """)
        source = f"REPORTS = {str(reports)!r}\nFAIL = {fail!r}\n" + source
        for name in ("test_ai_kb.py", "test_second.py"):
            (scripts / name).write_text(source)
        env = {
            **os.environ,
            "HOME": str(ambient),
            "TMPDIR": str(ambient),
            "GIT_DIR": str(ambient / ".git"),
            "GIT_WORK_TREE": str(ambient),
            "GIT_INDEX_FILE": str(ambient / "index"),
            "TMUX": "live-session",
            "TMUX_PANE": "%1",
            "LEAK_SENTINEL": "private-fixture-value",
        }
        for key in (
            "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME",
            "XDG_DATA_HOME",
            "XDG_STATE_HOME",
            "XDG_RUNTIME_DIR",
            "TMUX_TMPDIR",
        ):
            env[key] = str(ambient)
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        result = subprocess.run(
            ["python3", str(scripts / "test_runner.py"), "--workers", "2", "test_ai_kb.py", "test_second.py"],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(
            sorted(p.name for p in scripts.iterdir()), ["test_ai_kb.py", "test_runner.py", "test_second.py"]
        )
        self.assertEqual(list(ambient.iterdir()), [])
        actual = [json.loads((reports / name).read_text()) for name in ("test_ai_kb.json", "test_second.json")]
        return result, actual

    def test_WHEN_parallel_shards_write_default_paths_SHOULD_isolate_and_remove_their_state(self):
        result, reports = self._run_fixture(fail=False)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        first, second = reports
        self.assertEqual(first["selectors"], [])
        self.assertEqual(second["selectors"], [])
        self.assertTrue(set(first["paths"].values()).isdisjoint(second["paths"].values()), reports)
        for report in reports:
            for path in report["paths"].values():
                self.assertFalse(Path(path).exists(), path)

    def test_WHEN_a_shard_fails_SHOULD_report_failure_and_remove_its_state(self):
        result, reports = self._run_fixture(fail=True)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("deliberate shard failure", result.stderr)
        for report in reports:
            for path in report["paths"].values():
                self.assertFalse(Path(path).exists(), path)


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
            names = collect_changed(root, staged=False)
            assert "tracked.txt" in names
            assert "new.txt" in names

            subprocess.run(["git", "add", "new.txt"], cwd=root, check=True)
            staged = collect_changed(root, staged=True)
            assert staged == ("new.txt",)


class TestCheckCli(unittest.TestCase):
    """WHEN invoking scripts/check.py."""

    def test_WHEN_print_plan_with_full_SHOULD_emit_json_mode_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("check.py", "test_runner.py", "test_yaml_parser.py"):
                shutil.copy2(REPO / "scripts" / name, scripts / name)
            before = sorted(path.relative_to(root) for path in root.rglob("*"))
            env = os.environ.copy()
            for key in ("CHECK_FULL", "PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"):
                env.pop(key, None)
            result = subprocess.run(
                ["python3", str(scripts / "check.py"), "--full", "--print-plan"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            payload = json.loads(result.stdout)
            assert payload["mode"] == "full"
            assert "test_yaml_parser.py" in payload["tests"]
            assert "test_runner.py" not in payload["tests"]
            self.assertEqual(sorted(path.relative_to(root) for path in root.rglob("*")), before)

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
