from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.formal_support import (
    CLI,
    REPO,
    CliError,
    audit_mod,
    build_mod,
    cli_mod,
    commit_all,
    exe_mod,
    init_git_repo,
    manifest_mod,
    paths_mod,
    prove_mod,
    replay_mod,
    run_formal,
    util_mod,
)


class TestCliAuditExitCode(unittest.TestCase):
    """WHEN `,formal audit`'s process exit code must distinguish an environment error (2, an
    `error` stage) from an ordinary check failure (1) and a clean pass (0) -- A1."""

    def test_pure_classification(self) -> None:
        self.assertEqual(0, cli_mod.audit_exit_code({"verdict": "pass", "has_error": False}))
        self.assertEqual(1, cli_mod.audit_exit_code({"verdict": "fail", "has_error": False}))
        self.assertEqual(2, cli_mod.audit_exit_code({"verdict": "fail", "has_error": True}))
        # An `error` stage always wins, even alongside an otherwise-passing verdict (e.g. a
        # cached prior pass reused for one stage next to a fresh environment failure elsewhere).
        self.assertEqual(2, cli_mod.audit_exit_code({"verdict": "pass", "has_error": True}))

    def test_audit_process_exits_2_when_lake_is_a_broken_stub(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            tempfile.TemporaryDirectory() as home_tmp,
            tempfile.TemporaryDirectory() as bin_tmp,
        ):
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add m.py")

            run_formal(workspace, formal_home, "init", "u", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:1-2", check=True)

            stub_lake = Path(bin_tmp) / "lake"
            stub_lake.write_text("#!/usr/bin/env bash\nexit 124\n", encoding="utf-8")
            stub_lake.chmod(0o755)
            env = {**os.environ, "AGENT_FORMAL_HOME": str(formal_home), "PATH": f"{bin_tmp}:{os.environ['PATH']}"}

            result = subprocess.run(
                [sys.executable, str(CLI), "audit", "u", "--json"],
                cwd=workspace,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["has_error"])
            self.assertEqual("error", payload["stages"]["build"]["status"])


class TestCliStandaloneBuildProveEnvironmentError(unittest.TestCase):
    """WHEN standalone `,formal build`/`,formal prove` hit an environment error (missing
    `lake`, exit 127/124), the receipt message is printed and the process exits 2, not the
    ordinary 0/1 check-result codes -- A14."""

    def _stub_broken_lake(self, bin_tmp: Path) -> dict[str, str]:
        stub_lake = Path(bin_tmp) / "lake"
        stub_lake.write_text("#!/usr/bin/env bash\nexit 124\n", encoding="utf-8")
        stub_lake.chmod(0o755)
        return {"PATH": f"{bin_tmp}:{os.environ['PATH']}"}

    def test_standalone_build_exits_2_and_prints_the_receipt_message(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            tempfile.TemporaryDirectory() as home_tmp,
            tempfile.TemporaryDirectory() as bin_tmp,
        ):
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", check=True)

            env = {**os.environ, "AGENT_FORMAL_HOME": str(formal_home), **self._stub_broken_lake(bin_tmp)}
            result = subprocess.run(
                [sys.executable, str(CLI), "build", "u"], cwd=workspace, env=env, text=True, capture_output=True
            )

            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            self.assertIn("environment failure", result.stdout)
            self.assertNotIn("Build FAILED", result.stdout)

    def test_standalone_prove_exits_2_and_json_includes_environment_error_and_message(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            tempfile.TemporaryDirectory() as home_tmp,
            tempfile.TemporaryDirectory() as bin_tmp,
        ):
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", check=True)

            env = {**os.environ, "AGENT_FORMAL_HOME": str(formal_home), **self._stub_broken_lake(bin_tmp)}
            result = subprocess.run(
                [sys.executable, str(CLI), "prove", "u", "--json"],
                cwd=workspace,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload.get("environment_error"))
            self.assertIn("environment failure", payload.get("message", ""))

    def test_run_prove_s_own_lean_invocation_environment_failure_includes_a_message(self) -> None:
        """`run_prove`'s *own* `lake env <formalcheck>` environment-failure branch (distinct from
        the upstream `lake build` short-circuit exercised above) must also carry a `message` field
        so `cmd_prove`'s human/json output stays uniform regardless of which stage hit the
        environment failure."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")

            with (
                mock.patch.object(prove_mod, "_kit_dir_for_unit", return_value=unit_dir),
                mock.patch.object(prove_mod, "ensure_formalcheck", return_value=unit_dir / "formalcheck"),
                mock.patch.object(
                    prove_mod,
                    "run",
                    return_value=subprocess.CompletedProcess(["lake", "env", "formalcheck"], 124, "", "timed out"),
                ),
            ):
                receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=5)

            self.assertTrue(receipt.get("environment_error"))
            self.assertIn("environment failure", receipt.get("message", ""))


class TestFishCompletionJsonLeafOnly(unittest.TestCase):
    """WHEN the fish completion offers `--json` only after a leaf subcommand -- `_add_json_flag`
    in cli.py never runs on the bare `anchors`/`catalog` group parsers, so those group commands
    must not suggest a flag the real CLI rejects -- A16."""

    FISH_COMPLETION = REPO / "home" / "dot_config" / "fish" / "completions" / "readonly_,formal.fish"

    def _complete(self, partial_cmdline: str) -> str:
        if shutil.which("fish") is None:
            self.skipTest("fish not installed")
        with tempfile.TemporaryDirectory() as isolated_home:
            # Isolate HOME/XDG_CONFIG_HOME so fish's own completion autoloader never also picks
            # up the separately chezmoi-deployed `~/.config/fish/completions/,formal.fish` copy
            # alongside the one sourced here -- that would silently keep both old and new rules
            # active and mask a real fix (or a real regression) in the source file under test.
            env = {**os.environ, "HOME": isolated_home, "XDG_CONFIG_HOME": isolated_home}
            result = subprocess.run(
                ["fish", "-c", f"source '{self.FISH_COMPLETION}'; complete -C'{partial_cmdline}'"],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            return result.stdout

    def test_bare_anchors_does_not_offer_json(self) -> None:
        self.assertNotIn("--json", self._complete(",formal anchors --"))

    def test_bare_catalog_does_not_offer_json(self) -> None:
        self.assertNotIn("--json", self._complete(",formal catalog --"))

    def test_anchors_add_offers_json(self) -> None:
        self.assertIn("--json", self._complete(",formal anchors add --"))

    def test_catalog_list_offers_json(self) -> None:
        self.assertIn("--json", self._complete(",formal catalog list --"))

    def test_build_offers_json(self) -> None:
        self.assertIn("--json", self._complete(",formal build --"))


class TestFishCompletionAnchorsCatalogLeafDoesNotOfferSubcommands(unittest.TestCase):
    """WHEN a leaf `anchors`/`catalog` subcommand (`add`, `gc`, ...) is already chosen: the
    completion must not still offer sibling subcommand names as if none had been picked yet --
    a regression from an unquoted `-n` condition where `$__formal_anchors_subcommands`/
    `$__formal_catalog_subcommands` never interpolated (fish does not expand variables inside
    single quotes), so `and not __fish_seen_subcommand_from $var` always evaluated true and kept
    suggesting every sibling subcommand (S5.4)."""

    FISH_COMPLETION = REPO / "home" / "dot_config" / "fish" / "completions" / "readonly_,formal.fish"

    def _complete(self, partial_cmdline: str) -> str:
        if shutil.which("fish") is None:
            self.skipTest("fish not installed")
        with tempfile.TemporaryDirectory() as isolated_home:
            env = {**os.environ, "HOME": isolated_home, "XDG_CONFIG_HOME": isolated_home}
            result = subprocess.run(
                ["fish", "-c", f"source '{self.FISH_COMPLETION}'; complete -C'{partial_cmdline}'"],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            return result.stdout

    def _offered_names(self, completions: str) -> set[str]:
        return {line.split("\t", 1)[0] for line in completions.splitlines() if line}

    def test_anchors_add_does_not_offer_add_check_or_list(self) -> None:
        offered = self._offered_names(self._complete(",formal anchors add "))
        self.assertFalse(offered & {"add", "check", "list"}, offered)

    def test_catalog_gc_does_not_offer_catalog_subcommands(self) -> None:
        offered = self._offered_names(self._complete(",formal catalog gc "))
        self.assertFalse(offered & {"list", "resolve", "checkout", "stale", "uncovered", "save", "gc"}, offered)


class TestCliBudgetFlags(unittest.TestCase):
    """WHEN `mutate` gains the same `--max-states`/`--max-depth` override flags `explore` has,
    and MANIFEST budgets are used as the fallback when the flags are absent (F12)."""

    def test_mutate_subparser_accepts_max_states_and_max_depth(self) -> None:
        from formal import cli as cli_mod

        parser = cli_mod.build_parser()
        args = parser.parse_args(["mutate", "u", "--max-states", "10", "--max-depth", "3"])

        self.assertEqual(10, args.max_states)
        self.assertEqual(3, args.max_depth)

    def test_negative_limits_are_rejected_by_argument_parsing_and_zero_is_preserved(self) -> None:
        parser = cli_mod.build_parser()
        limit_flags = (
            ("explore", "u", "--max-states"),
            ("explore", "u", "--max-depth"),
            ("mutate", "u", "--max-states"),
            ("mutate", "u", "--max-depth"),
            ("traces", "u", "--max"),
            ("catalog", "gc", "--keep"),
        )
        for *prefix, flag in limit_flags:
            with self.subTest(command=prefix, flag=flag):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
                    parser.parse_args([*prefix, flag, "-1"])
                self.assertEqual(2, ctx.exception.code)

                parsed = parser.parse_args([*prefix, flag, "0"])
                self.assertEqual(0, getattr(parsed, flag.removeprefix("--").replace("-", "_")))

    def test_conformance_summary_never_says_complete_cover_when_explore_was_bounded(self) -> None:
        summary = audit_mod._conformance_summary("pass", {"total": 3, "passed": 3}, {"states": 3, "bounded": True}, 500)
        self.assertNotIn("complete cover", summary)


class TestCliExploreMutateVacuityGuards(unittest.TestCase):
    """WHEN the standalone `,formal explore`/`,formal mutate` commands must apply the same
    vacuity guards `audit` does (A12): zero properties/mutants, or any mutant with an empty
    declared expected killer, exits 1 with a `vacuous: ...` message naming the mutant, never a
    silent vacuous pass."""

    def _layout(self, workspace: Path, formal_home: Path):
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            return paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

    def test_zero_properties_fails_standalone_explore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", max_states=None, max_depth=None, json=True)

            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(
                    cli_mod.exe_mod,
                    "explore",
                    return_value={
                        "kind": "explore",
                        "states": 1,
                        "transitions": 0,
                        "depth": 0,
                        "bounded": False,
                        "props": [],
                    },
                ):
                    exit_code = cli_mod.cmd_explore(args)

            self.assertEqual(1, exit_code)

    def test_zero_mutants_fails_standalone_mutate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", max_states=None, max_depth=None, json=True)

            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(
                    cli_mod.exe_mod,
                    "mutate",
                    return_value={"kind": "mutate", "control": {"ok": True, "violations": []}, "mutants": []},
                ):
                    exit_code = cli_mod.cmd_mutate(args)

            self.assertEqual(1, exit_code)

    def test_a_mutant_with_empty_expected_fails_standalone_mutate_and_names_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", max_states=None, max_depth=None, json=True)
            mutate_payload = {
                "kind": "mutate",
                "control": {"ok": True, "violations": []},
                "mutants": [{"name": "M_vacuous", "status": "killed", "killed_by": ["P1"], "expected": []}],
            }

            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(cli_mod.exe_mod, "mutate", return_value=mutate_payload):
                    exit_code = cli_mod.cmd_mutate(args)

            self.assertEqual(1, exit_code)

    def test_a_killed_mutant_with_empty_expected_is_never_classified_killed(self) -> None:
        classified = exe_mod._classify_mutant({"name": "M1", "status": "killed", "killed_by": ["P1"], "expected": []})
        self.assertEqual("wrong-killer", classified)

    def test_a_killed_mutant_with_a_matching_expected_killer_stays_killed(self) -> None:
        classified = exe_mod._classify_mutant(
            {"name": "M1", "status": "killed", "killed_by": ["P1"], "expected": ["P1"]}
        )
        self.assertEqual("killed", classified)


class TestCliDoctor(unittest.TestCase):
    """WHEN `,formal doctor` checks elan/lake/lean and the pinned toolchain, and optionally
    installs it (test-integrity group "doctor")."""

    def _which(self, present: set[str]):
        def fake_which(tool: str) -> str | None:
            return f"/usr/bin/{tool}" if tool in present else None

        return fake_which

    def test_everything_present_and_toolchain_installed_exits_0_with_a_15s_timeout(self) -> None:
        calls: list[tuple[tuple[str, ...], float | None]] = []

        def fake_run(argv, timeout=None, **kwargs):
            calls.append((tuple(argv), timeout))
            return subprocess.CompletedProcess(argv, 0, f"stable\n{paths_mod.PINNED_TOOLCHAIN}\n", "")

        args = argparse.Namespace(install=False, json=True)
        with mock.patch.object(cli_mod.shutil, "which", side_effect=self._which({"elan", "lake", "lean"})):
            with mock.patch.object(util_mod, "run", side_effect=fake_run):
                exit_code = cli_mod.cmd_doctor(args)

        self.assertEqual(0, exit_code)
        self.assertEqual(1, len(calls))
        self.assertEqual(("elan", "toolchain", "list"), calls[0][0])
        self.assertEqual(15, calls[0][1])

    def test_install_without_elan_on_path_exits_2(self) -> None:
        args = argparse.Namespace(install=True, json=True)
        with mock.patch.object(cli_mod.shutil, "which", side_effect=self._which(set())):
            with self.assertRaises(CliError) as ctx:
                cli_mod.cmd_doctor(args)
        self.assertEqual(2, ctx.exception.code)
        self.assertIn("elan is not on PATH", ctx.exception.message)

    def test_install_failure_raises_with_the_installer_stderr_and_uses_a_600s_timeout(self) -> None:
        calls: list[tuple[tuple[str, ...], float | None]] = []

        def fake_run(argv, timeout=None, **kwargs):
            calls.append((tuple(argv), timeout))
            if argv[:2] == ["elan", "toolchain"] and argv[2] == "list":
                return subprocess.CompletedProcess(argv, 0, "stable\n", "")
            return subprocess.CompletedProcess(argv, 1, "", "network unreachable")

        args = argparse.Namespace(install=True, json=True)
        with mock.patch.object(cli_mod.shutil, "which", side_effect=self._which({"elan"})):
            with mock.patch.object(util_mod, "run", side_effect=fake_run):
                with self.assertRaises(CliError) as ctx:
                    cli_mod.cmd_doctor(args)

        self.assertEqual(1, ctx.exception.code)
        self.assertIn("network unreachable", ctx.exception.message)
        install_call = [c for c in calls if c[0][:3] == ("elan", "toolchain", "install")][0]
        self.assertEqual(600, install_call[1])

    def test_a_missing_tool_reports_missing_in_human_output_and_a_present_one_reports_its_path(self) -> None:
        args = argparse.Namespace(install=False, json=False)

        def fake_run(argv, timeout=None, **kwargs):
            return subprocess.CompletedProcess(argv, 1, "", "")

        buf = io.StringIO()
        with mock.patch.object(cli_mod.shutil, "which", side_effect=self._which({"lake", "lean"})):
            with mock.patch.object(util_mod, "run", side_effect=fake_run):
                with contextlib.redirect_stdout(buf):
                    cli_mod.cmd_doctor(args)

        output = buf.getvalue()
        self.assertIn("elan: MISSING", output)
        self.assertIn("lake: ok /usr/bin/lake", output)

    def test_toolchain_installed_state_is_reported_truthfully_in_human_output(self) -> None:
        args = argparse.Namespace(install=False, json=False)

        def fake_run(argv, timeout=None, **kwargs):
            return subprocess.CompletedProcess(argv, 0, f"{paths_mod.PINNED_TOOLCHAIN}\n", "")

        buf = io.StringIO()
        with mock.patch.object(cli_mod.shutil, "which", side_effect=self._which({"elan", "lake", "lean"})):
            with mock.patch.object(util_mod, "run", side_effect=fake_run):
                with contextlib.redirect_stdout(buf):
                    cli_mod.cmd_doctor(args)

        self.assertIn(f"toolchain {paths_mod.PINNED_TOOLCHAIN}: installed", buf.getvalue())


class TestCliBudgetForwarding(unittest.TestCase):
    """WHEN `,formal explore`/`,formal mutate` override MANIFEST budgets with `--max-states`/
    `--max-depth`, or fall back to the MANIFEST budgets when the flags are absent -- `None` is
    never forwarded as a literal value either way (test-integrity group "budget forwarding")."""

    def _layout(self, workspace: Path, formal_home: Path):
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            return paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

    def _init(self, workspace: Path, formal_home: Path):
        init_git_repo(workspace)
        layout = self._layout(workspace, formal_home)
        manifest_mod.init_unit(layout, "u", "F2", True, None)
        manifest = manifest_mod.load_manifest(layout.work_dir("u"))
        manifest["budgets"] = {"max_states": 111, "max_depth": 22}
        manifest_mod.save_manifest(layout.work_dir("u"), manifest)
        return layout

    def test_explore_cli_flags_override_the_manifest_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout = self._init(Path(tmp), Path(home_tmp))
            args = argparse.Namespace(unit="u", max_states=999, max_depth=None, json=True)
            captured: dict[str, Any] = {}

            def fake_explore(unit_dir, max_states, max_depth, timeout=None):
                captured["max_states"] = max_states
                captured["max_depth"] = max_depth
                return {"kind": "explore", "states": 1, "transitions": 0, "depth": 0, "bounded": False, "props": []}

            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(exe_mod, "explore", side_effect=fake_explore):
                    cli_mod.cmd_explore(args)

            self.assertEqual(999, captured["max_states"])  # CLI flag wins over the manifest's 111
            self.assertEqual(22, captured["max_depth"])  # absent flag falls back to the manifest's 22

    def test_mutate_cli_flags_fall_back_to_the_manifest_budget_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            layout = self._init(Path(tmp), Path(home_tmp))
            args = argparse.Namespace(unit="u", max_states=None, max_depth=None, json=True)
            captured: dict[str, Any] = {}

            def fake_mutate(unit_dir, max_states, max_depth, timeout=None):
                captured["max_states"] = max_states
                captured["max_depth"] = max_depth
                return {"kind": "mutate", "control": {"ok": True, "violations": []}, "mutants": []}

            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(exe_mod, "mutate", side_effect=fake_mutate):
                    cli_mod.cmd_mutate(args)

            self.assertEqual(111, captured["max_states"])
            self.assertEqual(22, captured["max_depth"])

    def test_budget_args_omits_a_none_value_entirely_and_forwards_a_given_one(self) -> None:
        self.assertEqual([], exe_mod._budget_args(None, None))
        self.assertEqual(["--max-states", "10"], exe_mod._budget_args(10, None))
        self.assertEqual(["--max-depth", "3"], exe_mod._budget_args(None, 3))
        self.assertEqual(["--max-states", "10", "--max-depth", "3"], exe_mod._budget_args(10, 3))


class TestCliHumanModeOutput(unittest.TestCase):
    """WHEN a command is run without `--json`: its human-readable text must carry the same key
    facts the JSON receipt does (test-integrity group "human-mode output")."""

    def _layout(self, workspace: Path, formal_home: Path):
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            return paths_mod.Layout(paths_mod.workspace_root(str(workspace)))

    def test_anchors_add_prints_added_then_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            added = run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:1-1", "--id", "A1")
            replaced = run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:2-2", "--id", "A1")

            self.assertIn("Added anchor A1", added.stdout)
            self.assertIn("Replaced anchor A1", replaced.stdout)

    def test_anchors_check_prints_the_resolved_range_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:1-2", "--id", "A1", check=True)

            result = run_formal(workspace, formal_home, "anchors", "check", "u")

            self.assertIn("(1-2)", result.stdout)

    def test_build_human_output_reports_build_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", proofs=False, json=False)
            ok_receipt = {"kind": "build", "ok": True, "error_count": 0, "warning_count": 0, "errors": []}

            buf = io.StringIO()
            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(build_mod, "lake_build", return_value=ok_receipt):
                    with contextlib.redirect_stdout(buf):
                        exit_code = cli_mod.cmd_build(args)

            self.assertIn("Build OK", buf.getvalue())
            self.assertEqual(0, exit_code)

    def test_explore_human_output_marks_a_holding_property_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", max_states=None, max_depth=None, json=False)
            receipt = {
                "kind": "explore",
                "states": 1,
                "transitions": 0,
                "depth": 0,
                "bounded": False,
                "props": [{"name": "P1", "expect": "holds", "status": "holds"}],
            }

            buf = io.StringIO()
            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(exe_mod, "explore", return_value=receipt):
                    with contextlib.redirect_stdout(buf):
                        cli_mod.cmd_explore(args)

            self.assertIn("[OK] P1", buf.getvalue())

    def test_mutate_human_output_names_the_expected_killers_for_a_wrong_killer_mutant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", max_states=None, max_depth=None, json=False)
            receipt = {
                "kind": "mutate",
                "control": {"ok": True, "violations": []},
                "mutants": [{"name": "M1", "status": "wrong-killer", "killed_by": ["P2"], "expected": ["P1"]}],
            }

            buf = io.StringIO()
            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(exe_mod, "mutate", return_value=receipt):
                    with contextlib.redirect_stdout(buf):
                        cli_mod.cmd_mutate(args)

            self.assertIn("expected killer(s): ['P1'], actual: ['P2']", buf.getvalue())

    def test_replay_human_output_reports_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", adapter=None, against=None, json=False)
            receipt = {"kind": "replay", "ok": True, "total": 2, "passed": 2, "results": []}

            buf = io.StringIO()
            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(replay_mod, "run_replay", return_value=receipt):
                    with contextlib.redirect_stdout(buf):
                        exit_code = cli_mod.cmd_replay(args)

            self.assertIn("Replay PASS", buf.getvalue())
            self.assertEqual(0, exit_code)

    def test_replay_human_output_lists_a_failing_trace_and_never_a_passing_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", adapter=None, against=None, json=False)
            receipt = {
                "kind": "replay",
                "ok": False,
                "total": 2,
                "passed": 1,
                "results": [
                    {"trace_id": "T1", "status": "pass"},
                    {"trace_id": "T2", "status": "mismatch", "detail": "diverged"},
                ],
            }

            buf = io.StringIO()
            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(replay_mod, "run_replay", return_value=receipt):
                    with contextlib.redirect_stdout(buf):
                        exit_code = cli_mod.cmd_replay(args)

            output = buf.getvalue()
            self.assertIn("T2: mismatch diverged", output)
            self.assertNotIn("T1:", output)
            self.assertEqual(1, exit_code)

    def test_prove_human_output_lists_disallowed_axioms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F3", False, None)
            args = argparse.Namespace(unit="u", json=False)
            build_ok = {"kind": "build", "ok": True, "error_count": 0, "warning_count": 0, "errors": []}
            prove_receipt = {
                "kind": "prove",
                "ok": False,
                "build_ok": True,
                "forbidden_tokens": [],
                "theorem_count": 1,
                "axioms": {"disallowed_axioms": ["myCustomAxiom"]},
            }

            buf = io.StringIO()
            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(build_mod, "lake_build", return_value=build_ok):
                    with mock.patch.object(prove_mod, "run_prove", return_value=prove_receipt):
                        with contextlib.redirect_stdout(buf):
                            exit_code = cli_mod.cmd_prove(args)

            self.assertIn("disallowed axioms: myCustomAxiom", buf.getvalue())
            self.assertIn("Prove FAILED", buf.getvalue())
            self.assertEqual(1, exit_code)

    def test_prove_human_output_reports_environment_error_and_skips_the_ok_failed_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F3", False, None)
            args = argparse.Namespace(unit="u", json=False)
            broken_build = {
                "kind": "build",
                "ok": False,
                "environment_error": True,
                "message": "environment failure: lake timed out",
            }

            buf = io.StringIO()
            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(build_mod, "lake_build", return_value=broken_build):
                    with contextlib.redirect_stdout(buf):
                        exit_code = cli_mod.cmd_prove(args)

            output = buf.getvalue()
            self.assertIn("environment failure: lake timed out", output)
            self.assertNotIn("Prove OK", output)
            self.assertNotIn("Prove FAILED", output)
            self.assertEqual(2, exit_code)

    def test_explore_human_output_reports_the_vacuous_error_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", max_states=None, max_depth=None, json=False)
            receipt = {
                "kind": "explore",
                "states": 1,
                "transitions": 0,
                "depth": 0,
                "bounded": False,
                "props": [],
            }

            buf = io.StringIO()
            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(exe_mod, "explore", return_value=receipt):
                    with contextlib.redirect_stdout(buf):
                        exit_code = cli_mod.cmd_explore(args)

            output = buf.getvalue()
            self.assertIn("Explore FAILED: vacuous: no properties", output)
            self.assertNotIn("Explore:", output)
            self.assertEqual(1, exit_code)

    def test_mutate_human_output_reports_the_vacuous_error_message_and_skips_control_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", max_states=None, max_depth=None, json=False)
            receipt = {"kind": "mutate", "control": {"ok": True, "violations": []}, "mutants": []}

            buf = io.StringIO()
            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(exe_mod, "mutate", return_value=receipt):
                    with contextlib.redirect_stdout(buf):
                        exit_code = cli_mod.cmd_mutate(args)

            output = buf.getvalue()
            self.assertIn("Mutate FAILED: vacuous: no mutants", output)
            self.assertNotIn("Mutate control:", output)
            self.assertEqual(1, exit_code)

    def test_mutate_human_output_reports_control_ok_when_the_control_run_holds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            layout = self._layout(workspace, Path(home_tmp))
            manifest_mod.init_unit(layout, "u", "F2", True, None)
            args = argparse.Namespace(unit="u", max_states=None, max_depth=None, json=False)
            receipt = {
                "kind": "mutate",
                "control": {"ok": True, "violations": []},
                "mutants": [{"name": "M1", "status": "killed", "killed_by": ["P1"], "expected": ["P1"]}],
            }

            buf = io.StringIO()
            with mock.patch.object(cli_mod, "build_layout", return_value=layout):
                with mock.patch.object(exe_mod, "mutate", return_value=receipt):
                    with contextlib.redirect_stdout(buf):
                        exit_code = cli_mod.cmd_mutate(args)

            output = buf.getvalue()
            self.assertIn("Mutate control: OK", output)
            self.assertNotIn("Mutate control: FAILED", output)
            self.assertEqual(0, exit_code)


class TestCliStatusCommand(unittest.TestCase):
    """WHEN `,formal status` reports each unit's on-branch/state/resolved-version row
    (test-integrity group "status command")."""

    def test_status_reports_valid_stale_no_anchors_and_catalog_only_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)

            # valid: on-branch, anchor unchanged.
            (workspace / "valid.py").write_text("def v():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add valid.py")
            run_formal(workspace, formal_home, "init", "valid", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "valid", "valid.py:1-2", check=True)

            # stale: on-branch, anchor edited.
            (workspace / "stale.py").write_text("def s():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add stale.py")
            run_formal(workspace, formal_home, "init", "stale", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "stale", "stale.py:1-2", check=True)
            (workspace / "stale.py").write_text("def s():\n    return 999\n", encoding="utf-8")

            # no-anchors: on-branch, zero anchors.
            run_formal(workspace, formal_home, "init", "bare", "--design", check=True)

            # catalog-only: not on this branch, but a saved version exists (resolved_version set).
            (workspace / "saved.py").write_text("def sv():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add saved.py")
            run_formal(workspace, formal_home, "init", "saved", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "saved", "saved.py:1-2", check=True)
            run_formal(workspace, formal_home, "catalog", "save", "saved", "--allow-unverified", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            shutil.rmtree(layout.work_dir("saved"))

            result = run_formal(workspace, formal_home, "status", "--json", check=True)

            rows = {row["unit"]: row for row in json.loads(result.stdout)["units"]}
            self.assertEqual("valid", rows["valid"]["anchor_state"])
            self.assertTrue(rows["valid"]["on_branch"])
            self.assertEqual("stale", rows["stale"]["anchor_state"])
            self.assertEqual("no-anchors", rows["bare"]["anchor_state"])
            self.assertFalse(rows["saved"]["on_branch"])
            self.assertIsNotNone(rows["saved"]["resolved_version"])


class TestAnchorsAddRecasesToTheOnDiskSpelling(unittest.TestCase):
    """WHEN `anchors add` is given a path in a different case than the actual on-disk/git-tracked
    spelling, on a case-insensitive filesystem (Q4.2): the anchor must be stored under the actual
    spelling, so a later `catalog stale --base`'s plain string match against `git diff`'s
    reported (tracked-case) paths still finds it. Skipped on a genuinely case-sensitive
    filesystem, where a differently-cased path is simply a different, nonexistent file."""

    def _fs_is_case_insensitive(self, tmp: Path) -> bool:
        probe = tmp / "case_probe.tmp"
        probe.write_text("x", encoding="utf-8")
        return (tmp / "CASE_PROBE.TMP").exists()

    def test_a_lowercase_typo_of_a_mixed_case_tracked_file_resolves_to_its_real_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            if not self._fs_is_case_insensitive(workspace):
                self.skipTest("filesystem is case-sensitive")
            init_git_repo(workspace)
            (workspace / "Src.py").write_text("a = 1\n", encoding="utf-8")
            base_ref = commit_all(workspace, "add Src.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "src.py:1-1", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertEqual("Src.py", payload["path"])

            (workspace / "Src.py").write_text("a = 2\n", encoding="utf-8")
            commit_all(workspace, "edit Src.py")

            stale_result = run_formal(
                workspace, formal_home, "catalog", "stale", "--base", base_ref, "--json", check=True
            )
            stale_units = {row["unit"] for row in json.loads(stale_result.stdout)["units"]}
            self.assertIn("u", stale_units)

    def test_a_case_only_disk_rename_still_anchors_under_gits_tracked_case(self) -> None:
        """A rename that changes only the on-disk case (a plain `mv M.py m.py` is a no-op on a
        case-insensitive filesystem; the two-step `mv M.py tmpx && mv tmpx m.py` below forces the
        actual dirent case to flip) leaves the disk spelling `m.py` while git still tracks `M.py`
        unchanged -- typing the tracked case on the command line must still store the anchor
        under git's own case, not whatever a directory listing of the disk happens to show (S5.1)."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            if not self._fs_is_case_insensitive(workspace):
                self.skipTest("filesystem is case-sensitive")
            init_git_repo(workspace)
            (workspace / "M.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
            base_ref = commit_all(workspace, "add M.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            (workspace / "M.py").rename(workspace / "tmpx")
            (workspace / "tmpx").rename(workspace / "m.py")

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "M.py:1-2", "--json", check=True)
            self.assertEqual("M.py", json.loads(result.stdout)["path"])

            (workspace / "m.py").write_text("a = 1\nb = 3\n", encoding="utf-8")
            commit_all(workspace, "edit via the lowercase disk name")

            stale_result = run_formal(
                workspace, formal_home, "catalog", "stale", "--base", base_ref, "--json", check=True
            )
            stale_units = {row["unit"] for row in json.loads(stale_result.stdout)["units"]}
            self.assertIn("u", stale_units)

    def test_an_nfd_typed_command_line_path_resolves_to_gits_nfc_tracked_name(self) -> None:
        """A caller-typed anchor path decomposed into NFD (e.g. a combining-accent sequence a
        keyboard/paste can produce for an accented character) must still resolve to the file
        git tracks under its own (typically NFC-composed) spelling, not be stored verbatim under
        the caller's decomposed spelling (S5.1)."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            nfc_name = unicodedata.normalize("NFC", "café.py")
            init_git_repo(workspace)
            (workspace / nfc_name).write_text("a = 1\n", encoding="utf-8")
            commit_all(workspace, "add nfc-named file")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            nfd_location = f"{unicodedata.normalize('NFD', 'café.py')}:1-1"

            result = run_formal(workspace, formal_home, "anchors", "add", "u", nfd_location, "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertEqual(nfc_name, payload["path"])
            self.assertTrue(unicodedata.is_normalized("NFC", payload["path"]))

    def test_actual_case_path_returns_a_nonexistent_path_unchanged(self) -> None:
        """`_actual_case_path` is only ever called after confirming the path exists under the
        workspace -- a path whose first component is not found at all (case-folded or not, and
        not tracked by git) must come back unchanged rather than crash or substitute an
        unrelated file (mutation-tested guard, S5.1)."""
        with tempfile.TemporaryDirectory() as tmp:
            rel = Path("nope/x.py")

            self.assertEqual(rel, cli_mod._actual_case_path(Path(tmp), rel))


class TestGitTrackedCaseLiteralPathspecAndSamefileGuard(unittest.TestCase):
    """WHEN `_git_tracked_case`'s pathspec must never let a literal `[`/`]`/`?` in the caller's
    filename be reinterpreted as a glob, and must never trust a git-reported name unless it is
    `os.path.samefile` with the exact path asked about (U3.1, mutants 67/109/134)."""

    def test_a_literal_bracket_filename_untracked_beside_a_tracked_glob_equivalent_stores_itself(
        self,
    ) -> None:
        """Without the `literal` pathspec magic, `:(icase)a[b].py` glob-matches the unrelated
        tracked `ab.py` (`[b]` is a one-character glob class) and would wrongly redirect the
        anchor there instead of storing the caller's own literal `a[b].py` (mutant 109)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            (workspace / "ab.py").write_text("x\n", encoding="utf-8")
            commit_all(workspace, "add ab.py")
            (workspace / "a[b].py").write_text("z\n", encoding="utf-8")

            self.assertEqual("a[b].py", cli_mod._resolve_anchor_path(workspace, "a[b].py"))

    def test_a_literal_bracket_directory_component_resolves_the_same_way(self) -> None:
        """The same literal-bracket rule inside a nested directory (a Next.js-style dynamic
        route segment), tracked `app/s/page.tsx` next to untracked `app/[s]/page.tsx`."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            (workspace / "app" / "s").mkdir(parents=True)
            (workspace / "app" / "s" / "page.tsx").write_text("x\n", encoding="utf-8")
            commit_all(workspace, "add app/s/page.tsx")
            (workspace / "app" / "[s]").mkdir(parents=True)
            (workspace / "app" / "[s]" / "page.tsx").write_text("z\n", encoding="utf-8")

            self.assertEqual("app/[s]/page.tsx", cli_mod._resolve_anchor_path(workspace, "app/[s]/page.tsx"))

    def test_a_tracked_directory_name_is_never_redirected_to_one_file_underneath_it(self) -> None:
        """Git's pathspec matching treats a bare tracked directory name as matching every path
        under it, even under `literal` -- resolving directory `src` (which contains tracked
        `src/a.py`) must not silently redirect the anchor to `src/a.py` underneath it; the
        `os.path.samefile` guard rejects that single glob/pathspec "match" because a directory
        and a file inside it are never the same file (mutant 109's directory case)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            (workspace / "src").mkdir()
            (workspace / "src" / "a.py").write_text("x\n", encoding="utf-8")
            commit_all(workspace, "add src/a.py")

            self.assertEqual("src", cli_mod._resolve_anchor_path(workspace, "src"))

    def test_multiple_glob_style_matches_with_no_samefile_survivor_falls_back_to_on_disk(
        self,
    ) -> None:
        """Two unrelated tracked files (`ab.py`, `ac.py`) that a *non-literal* pathspec would
        both glob-match against an untracked `a[bc].py` -- with `literal`, neither is even
        reported by git, so the on-disk fallback (not either tracked file) must win (mutant
        67/134's multi-match branch)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)
            (workspace / "ab.py").write_text("x\n", encoding="utf-8")
            (workspace / "ac.py").write_text("y\n", encoding="utf-8")
            commit_all(workspace, "add ab.py and ac.py")
            (workspace / "a[bc].py").write_text("z\n", encoding="utf-8")

            self.assertEqual("a[bc].py", cli_mod._resolve_anchor_path(workspace, "a[bc].py"))

    def _fs_is_case_insensitive(self, tmp: Path) -> bool:
        probe = tmp / "case_probe.tmp"
        probe.write_text("x", encoding="utf-8")
        return (tmp / "CASE_PROBE.TMP").exists()

    def test_a_case_only_rename_of_a_wildcard_named_file_still_resolves_to_gits_tracked_case(
        self,
    ) -> None:
        """`Q?.py` is tracked; a case-only on-disk rename (`mv Q?.py tmpx && mv tmpx q?.py`, the
        two-step form that actually flips the dirent case on a case-insensitive filesystem) must
        still resolve the caller's `q?.py` to git's own tracked `Q?.py`, with the literal `?`
        never expanding into a wildcard match against some other single-character filename
        (mutant 48's case-renamed variant). Skipped on a genuinely case-sensitive filesystem."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            if not self._fs_is_case_insensitive(workspace):
                self.skipTest("filesystem is case-sensitive")
            init_git_repo(workspace)
            (workspace / "Q?.py").write_text("x\n", encoding="utf-8")
            commit_all(workspace, "add Q?.py")
            os.rename(workspace / "Q?.py", workspace / "tmpx")
            os.rename(workspace / "tmpx", workspace / "q?.py")

            self.assertEqual("Q?.py", cli_mod._resolve_anchor_path(workspace, "q?.py"))


class TestResolveAnchorPathRejectsAnAncestorOfTheWorkspace(unittest.TestCase):
    """WHEN the resolved anchor path is an ancestor of the workspace root, both as a relative
    `..` and as the equivalent absolute parent path: both must raise `CliError` rather than be
    accepted as some in-workspace relative path (U3.2, mutant 112)."""

    def test_relative_dotdot_raises_cli_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)

            with self.assertRaises(CliError) as ctx:
                cli_mod._resolve_anchor_path(workspace, "..")
            self.assertEqual(2, ctx.exception.code)

    def test_the_equivalent_absolute_parent_path_raises_cli_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            init_git_repo(workspace)

            with self.assertRaises(CliError) as ctx:
                cli_mod._resolve_anchor_path(workspace, str(workspace.resolve().parent))
            self.assertEqual(2, ctx.exception.code)


class TestAnchorsAddAbsolutePathWithCaseDifferentWorkspacePrefix(unittest.TestCase):
    """WHEN an absolute anchor path's workspace-prefix component(s) differ from the workspace
    root only in case, on a case-insensitive filesystem (S5.2, low): `Path.relative_to`'s exact
    string prefix match would otherwise reject it (exit 2) even though it names a real file
    inside the workspace. Skipped on a genuinely case-sensitive filesystem."""

    def _fs_is_case_insensitive(self, tmp: Path) -> bool:
        probe = tmp / "case_probe.tmp"
        probe.write_text("x", encoding="utf-8")
        return (tmp / "CASE_PROBE.TMP").exists()

    def test_absolute_path_with_case_different_workspace_prefix_resolves_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            base = Path(tmp)
            if not self._fs_is_case_insensitive(base):
                self.skipTest("filesystem is case-sensitive")
            workspace = base / "CaseWs"
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            differently_cased_absolute = str(base / "casews" / "m.py")

            result = run_formal(
                workspace,
                formal_home,
                "anchors",
                "add",
                "u",
                f"{differently_cased_absolute}:1-2",
                "--json",
                check=True,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("m.py", json.loads(result.stdout)["path"])

    def test_distinct_case_sensitive_sibling_workspace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            base = Path(tmp)
            if self._fs_is_case_insensitive(base):
                self.skipTest("filesystem is case-insensitive")
            workspace = base / "CaseWs"
            outside = base / "casews"
            outside.mkdir()
            (outside / "m.py").write_text("outside\n", encoding="utf-8")
            init_git_repo(workspace)
            (workspace / "m.py").write_text("inside\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, Path(home_tmp), "init", "u", "--design", check=True)

            result = run_formal(
                workspace,
                Path(home_tmp),
                "anchors",
                "add",
                "u",
                f"{outside / 'm.py'}:1-1",
                "--json",
            )

            self.assertEqual(2, result.returncode)
            self.assertIn("outside the workspace", result.stderr)


class TestAnchorsAddFromASubdirectoryResolvesRepoRelative(unittest.TestCase):
    """WHEN `,formal anchors add` is invoked with the process cwd set to a workspace
    subdirectory (Q4.4, gap test): a relative location argument is still resolved relative to
    the repo (workspace) root, matching every other place an anchor's `path` is read back as
    workspace-relative -- not relative to the invoking shell's cwd."""

    def test_anchors_add_from_a_subdirectory_still_resolves_the_repo_root_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
            (workspace / "sub").mkdir()
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            env = {**os.environ, "AGENT_FORMAL_HOME": str(formal_home)}
            result = subprocess.run(
                [sys.executable, str(CLI), "anchors", "add", "u", "m.py:1-2", "--json"],
                cwd=workspace / "sub",
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("m.py", json.loads(result.stdout)["path"])


class TestHelpUnderPythonSafePath(unittest.TestCase):
    """WHEN the interpreter running `,formal` has `PYTHONSAFEPATH=1` set (Q4.5, gap test): a
    Python >= 3.11 interpreter with that flag skips its usual automatic insertion of the
    script's own directory into `sys.path` -- `main.py` inserts `MODULE_DIR` itself explicitly,
    so `,formal --help` must still exit 0. Skipped when no Python >= 3.11 interpreter is on
    PATH."""

    def _find_safepath_capable_python(self) -> str | None:
        for name in ("python3.13", "python3.12", "python3.11", "python3"):
            resolved = shutil.which(name)
            if not resolved:
                continue
            version = subprocess.run(
                [resolved, "-c", "import sys; print(sys.version_info >= (3, 11))"],
                capture_output=True,
                text=True,
                check=False,
            )
            if version.returncode == 0 and version.stdout.strip() == "True":
                return resolved
        return None

    def test_help_exits_0_under_pythonsafepath(self) -> None:
        interpreter = self._find_safepath_capable_python()
        if interpreter is None:
            self.skipTest("no Python >= 3.11 interpreter on PATH")
        env = {**os.environ, "PYTHONSAFEPATH": "1"}

        result = subprocess.run([interpreter, str(CLI), "--help"], env=env, text=True, capture_output=True, check=False)

        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
