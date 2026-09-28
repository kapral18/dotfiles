from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.formal_support import (
    FIXTURE_DIR,
    init_git_repo,
    paths_mod,
    run_formal,
)


class TestE2eToyFixture(unittest.TestCase):
    """WHEN the toy fixture unit runs the full F2/F3 lifecycle. Requires `lake` on PATH; fails
    (does not skip) when missing, per the worker contract."""

    def setUp(self) -> None:
        if shutil.which("lake") is None:
            self.fail(
                "`lake` is required for E2E ,formal tests and was not found on PATH. "
                "Install the pinned Lean toolchain (see `,formal doctor --install` or "
                "`brew install elan-init`) before running -k e2e."
            )

    def _copy_fixture_lean_sources(self, unit_dir: Path) -> None:
        fixture_unit = FIXTURE_DIR / "Unit"
        for name in ("Model.lean", "Step.lean", "Props.lean", "Mutants.lean"):
            source = fixture_unit / name
            if source.exists():
                shutil.copy2(source, unit_dir / "Unit" / name)
        for name in ("TRANSITIONS.md", "PROPERTIES.md"):
            source = FIXTURE_DIR / name
            if source.exists():
                shutil.copy2(source, unit_dir / name)

    def test_e2e_explore_mutate_replay_prove_over_the_toy_unit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)

            run_formal(workspace, formal_home, "init", "toy", "--tier", "F3", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("toy")
            # `paths.state_root()` now always resolves `AGENT_FORMAL_HOME` (U3.3): on macOS a
            # `tempfile.TemporaryDirectory()` under `/var` resolves to `/private/var`, so compare
            # against the resolved `formal_home` too, matching `test_formal_catalog.py`'s fix.
            self.assertTrue(unit_dir.is_relative_to(formal_home.resolve()))
            self._copy_fixture_lean_sources(unit_dir)

            build_result = run_formal(workspace, formal_home, "build", "toy", "--json")
            self.assertEqual(0, build_result.returncode, build_result.stdout + build_result.stderr)

            explore_result = run_formal(workspace, formal_home, "explore", "toy", "--json")
            self.assertEqual(0, explore_result.returncode, explore_result.stdout + explore_result.stderr)
            explore_payload = json.loads(explore_result.stdout)
            by_name = {p["name"]: p for p in explore_payload["props"]}
            self.assertEqual("holds", by_name["P1 done implies recorded"]["status"])
            p2 = by_name["P2 idle implies not recorded"]
            self.assertEqual("violated", p2["status"])
            self.assertEqual(
                {"init": 0, "events": [{"name": "start", "args": {}}, {"name": "cancel", "args": {}}]},
                p2["trace"],
            )
            self.assertEqual("holds", by_name["P3 reset from done always lands on idle"]["status"])

            closed_depth_result = run_formal(workspace, formal_home, "explore", "toy", "--max-depth", "3", "--json")
            self.assertEqual(0, closed_depth_result.returncode, closed_depth_result.stdout + closed_depth_result.stderr)
            closed_depth_payload = json.loads(closed_depth_result.stdout)
            self.assertFalse(closed_depth_payload["bounded"], closed_depth_payload)
            self.assertEqual(explore_payload["states"], closed_depth_payload["states"], closed_depth_payload)

            mutate_result = run_formal(workspace, formal_home, "mutate", "toy", "--json")
            mutate_payload = json.loads(mutate_result.stdout)
            self.assertTrue(mutate_payload["control"]["ok"])
            by_mutant = {m["name"]: m for m in mutate_payload["mutants"]}
            self.assertEqual("killed", by_mutant["M_killed"]["status"])
            self.assertEqual("survived", by_mutant["M_weak"]["status"])
            self.assertEqual(1, mutate_result.returncode)

            run_formal(workspace, formal_home, "traces", "toy", check=True)

            adapter_ok = FIXTURE_DIR / "adapter_ok.py"
            replay_ok = run_formal(
                workspace, formal_home, "replay", "toy", "--adapter", f"{sys.executable} {adapter_ok}", "--json"
            )
            self.assertEqual(0, replay_ok.returncode, replay_ok.stdout + replay_ok.stderr)

            adapter_diverge = FIXTURE_DIR / "adapter_diverge.py"
            replay_diverge = run_formal(
                workspace, formal_home, "replay", "toy", "--adapter", f"{sys.executable} {adapter_diverge}", "--json"
            )
            self.assertEqual(1, replay_diverge.returncode)
            diverge_payload = json.loads(replay_diverge.stdout)
            self.assertTrue(any(r["status"] != "pass" for r in diverge_payload["results"]))

            shutil.copy2(FIXTURE_DIR / "Proofs_sorry.lean", unit_dir / "Unit" / "Proofs.lean")
            prove_sorry = run_formal(workspace, formal_home, "prove", "toy", "--json")
            self.assertEqual(1, prove_sorry.returncode)
            sorry_payload = json.loads(prove_sorry.stdout)
            self.assertTrue(any(hit["token"] == "sorry" for hit in sorry_payload["forbidden_tokens"]))

            shutil.copy2(FIXTURE_DIR / "Proofs_ok.lean", unit_dir / "Unit" / "Proofs.lean")
            prove_ok = run_formal(workspace, formal_home, "prove", "toy", "--json")
            self.assertEqual(0, prove_ok.returncode, prove_ok.stdout + prove_ok.stderr)

    def test_bounded_refutation_is_inconclusive_and_never_kills_a_mutant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "bounded", "--tier", "F2", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                unit_dir = paths_mod.Layout(paths_mod.workspace_root(str(workspace))).work_dir("bounded")
            (unit_dir / "Unit" / "Model.lean").write_text(
                "namespace Unit\nabbrev St := Nat\ninductive Ev where | tick deriving Repr, BEq\nend Unit\n",
                encoding="utf-8",
            )
            (unit_dir / "Unit" / "Step.lean").write_text(
                "import Lean.Data.Json\nimport Unit.Model\nnamespace Unit\n"
                "def step (_ : St) : Ev → St | .tick => 1\n"
                "def inits : List St := [0]\ndef events : List Ev := [.tick]\n"
                "def key (st : St) : UInt64 := UInt64.ofNat st\n"
                'def obs (st : St) : Lean.Json := Lean.Json.mkObj [("n", Lean.Json.num st)]\n'
                'def evJson : Ev → Lean.Json | .tick => Lean.Json.mkObj [("name", Lean.Json.str "tick"), ("args", Lean.Json.mkObj [])]\n'
                "end Unit\n",
                encoding="utf-8",
            )
            (unit_dir / "Unit" / "Props.lean").write_text(
                "import FormalKit\nimport Unit.Step\nnamespace Unit\nopen FormalKit\n"
                'def props : List (Prop\' St Ev) := [{ name := "eventually one", expect := .refuted, '
                "check := fun _ st => st != 1 }]\nend Unit\n",
                encoding="utf-8",
            )
            (unit_dir / "Unit" / "Mutants.lean").write_text(
                "import FormalKit\nimport Unit.Step\nnamespace Unit\nopen FormalKit\n"
                "def delayed (st : St) : Ev → St | .tick => if st == 0 then 2 else 1\n"
                'def mutants : List (Mutant St Ev) := [{ name := "delayed", step := delayed, '
                'killedBy := ["eventually one"] }]\nend Unit\n',
                encoding="utf-8",
            )

            result = run_formal(workspace, formal_home, "mutate", "bounded", "--max-states", "2", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["control"]["ok"], payload)
            self.assertFalse(payload["control"]["bounded"], payload)
            mutant = payload["mutants"][0]
            self.assertEqual("survived", mutant["status"], payload)
            self.assertTrue(mutant["bounded"], payload)
            self.assertEqual(["eventually one"], mutant["inconclusive"], payload)
            self.assertEqual([], mutant["killed_by"], payload)

            control_result = run_formal(workspace, formal_home, "mutate", "bounded", "--max-states", "1", "--json")
            self.assertEqual(1, control_result.returncode, control_result.stdout + control_result.stderr)
            control_payload = json.loads(control_result.stdout)
            self.assertFalse(control_payload["control"]["ok"], control_payload)
            self.assertTrue(control_payload["control"]["bounded"], control_payload)
            self.assertEqual(["eventually one"], control_payload["control"]["inconclusive"], control_payload)


class TestProveOverRealLean(unittest.TestCase):
    """WHEN `,formal prove` runs its precompiled `formalcheck` executable against a real, compiled unit
    (F13/F17): every syntax shape a source regex could plausibly miss, and the lifted
    private-theorem restriction. Requires `lake` on PATH; fails (does not skip) when missing,
    per the worker contract."""

    def setUp(self) -> None:
        if shutil.which("lake") is None:
            self.fail(
                "`lake` is required for these real-Lean ,formal prove tests and was not found "
                "on PATH. Install the pinned Lean toolchain (see `,formal doctor --install` or "
                "`brew install elan-init`) before running -k RealLean."
            )

    def _init_toy_unit(self, workspace: Path, formal_home: Path, proofs_source: str) -> Path:
        init_git_repo(workspace)
        run_formal(workspace, formal_home, "init", "toy", "--tier", "F3", check=True)
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
        unit_dir = layout.work_dir("toy")
        fixture_unit = FIXTURE_DIR / "Unit"
        for name in ("Model.lean", "Step.lean", "Props.lean", "Mutants.lean"):
            shutil.copy2(fixture_unit / name, unit_dir / "Unit" / name)
        (unit_dir / "Unit" / "Proofs.lean").write_text(proofs_source, encoding="utf-8")
        return unit_dir

    def test_syntax_shapes_a_source_regex_could_miss_are_all_discovered_and_checked(self) -> None:
        # `open Nat in theorem open_in_trivial ...` on one line is the one shape confirmed to be
        # silently missed by the old regex-based `fully_qualified_theorems` (it never matches a
        # line that does not start with an optional attribute/modifier immediately followed by
        # `theorem`) -- the rest are included here as full-breadth coverage of what the generated
        # Lean program must still get right now that Lean itself does the enumeration.
        proofs_source = (
            "import Unit.Step\n\n"
            "namespace Unit\n\n"
            "theorem this_is_a_rather_long_and_verbose_theorem_name_for_testing_purposes : True := trivial\n\n"
            "theorem reset_from_done' (phase : Phase) (recorded : Bool) (h : phase = .done) :\n"
            "    (step { phase := phase, recorded := recorded } .reset).phase = .idle := by\n"
            "  subst h; cases recorded <;> decide\n\n"
            "section Grouped\n"
            "theorem grouped_trivial : True := trivial\n"
            "end Grouped\n\n"
            "open Nat in\ntheorem open_in_trivial : True := trivial\n\n"
            "@[simp]\ntheorem attr_own_line : True := trivial\n\n"
            "theorem Foo.bar : True := trivial\n\n"
            "mutual\ntheorem mutA : True := trivial\ntheorem mutB : True := mutA\nend\n\n"
            "end Unit\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            # P1.1: `@[simp] theorem attr_own_line ...` makes Lean synthesize an extra
            # `Unit.attr_own_line._simp_1` equation-lemma theorem -- checked (no exclusion) like
            # every other theorem-kind constant, so `theorem_count` is 9, one more than the 8
            # theorems actually written; `user_written_count` stays 8 since that auto-generated
            # lemma has no declaration range.
            self.assertEqual(9, payload["theorem_count"], payload)
            self.assertEqual(8, payload["user_written_count"], payload)
            names = {t["name"] for t in payload["axioms"]["theorems"]}
            self.assertIn("Unit.open_in_trivial", names)
            self.assertIn("Unit.Foo.bar", names)
            self.assertIn("Unit.mutA", names)
            self.assertIn("Unit.mutB", names)
            self.assertIn("Unit.attr_own_line._simp_1", names)
            self.assertNotIn("Unit.attr_own_line._simp_1", payload["user_written_theorems"])
            self.assertEqual([], payload["axioms"]["disallowed_axioms"])

    def test_a_private_theorem_is_checked_and_passes_when_axiom_clean(self) -> None:
        proofs_source = "namespace Unit\n\nprivate theorem hidden_ok : True := trivial\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(1, payload["theorem_count"])
            self.assertNotIn("private theorem unsupported", json.dumps(payload))
            names = [t["name"] for t in payload["axioms"]["theorems"]]
            self.assertEqual(["Unit.hidden_ok"], names)

    def test_a_private_theorem_using_sorry_still_fails_prove(self) -> None:
        proofs_source = "namespace Unit\n\nprivate theorem hidden_bad : True := by sorry\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(any(hit["token"] == "sorry" for hit in payload["forbidden_tokens"]))

    def test_zero_theorems_over_real_lean_fails_with_a_no_theorems_message(self) -> None:
        proofs_source = "namespace Unit\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(0, payload["theorem_count"])
            self.assertEqual(0, payload["user_written_count"])
            self.assertIn("no theorems", payload.get("error", ""))

    def test_structure_and_inductive_only_file_fails_no_theorems_despite_generated_lemmas(self) -> None:
        """P1.1: a `Proofs.lean` with only `structure`/`inductive` declarations has a nonzero
        *checked* count (their compiler-generated `mk.inj`/`mk.injEq`/`sizeOf_spec` lemmas are
        never excluded from the axiom check) but zero user-written theorems, so it must still
        fail the vacuity guard -- it must not pass just because Lean synthesized some lemmas."""
        proofs_source = (
            "namespace Unit\n\n"
            "structure Pair where\n"
            "  a : Nat\n"
            "  b : Nat\n\n"
            "inductive Choice where\n"
            "  | left\n"
            "  | right (n : Nat)\n\n"
            "end Unit\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertGreater(payload["theorem_count"], 0, payload)
            self.assertEqual(0, payload["user_written_count"], payload)
            self.assertIn("no theorems", payload.get("error", ""))

    def test_a_truly_one_line_file_with_open_in_theorem_passes_and_is_counted(self) -> None:
        proofs_source = "open Nat in theorem open_in_trivial : True := trivial\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(1, payload["theorem_count"])
            self.assertEqual(1, payload["user_written_count"])
            self.assertEqual(["open_in_trivial"], payload["user_written_theorems"])

    def test_a_private_theorem_calling_sorryax_directly_fails_via_the_axiom_check_not_the_token_scan(self) -> None:
        """`sorryAx True false` never matches the `\\bsorry\\b` forbidden-token regex (the
        identifier continues past the word boundary), so only the Lean-side axiom check --
        unaffected by the token scan short-circuit -- can catch it."""
        proofs_source = "namespace Unit\n\nprivate theorem hidden_bad : True := sorryAx True false\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["forbidden_tokens"])
            self.assertIn("sorryAx", payload["axioms"]["disallowed_axioms"])

    def test_an_underscore_named_theorem_calling_sorryax_still_gets_checked(self) -> None:
        """Before P1.1, `Name.isInternal` (true for any name component starting with `_`) wrongly
        excluded an underscore-named user theorem like `_t` from the axiom check entirely; it
        must now be checked like any other theorem and fail on its `sorryAx` axiom."""
        proofs_source = "namespace Unit\n\ntheorem _t : False := sorryAx False false\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["forbidden_tokens"])
            names = {t["name"] for t in payload["axioms"]["theorems"]}
            self.assertIn("Unit._t", names)
            self.assertIn("sorryAx", payload["axioms"]["disallowed_axioms"])

    def test_decide_plus_native_fails_via_its_native_axiom_with_no_forbidden_token_hit(self) -> None:
        """`by decide +native` leaves no literal `native_decide`/`unsafe`/`extern` token in the
        source -- only `Lean.collectAxioms` sees the resulting native-decide axiom."""
        proofs_source = "namespace Unit\n\nprivate theorem native_ok : (1 + 1 = 2) := by decide +native\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["forbidden_tokens"])
            self.assertTrue(payload["axioms"]["disallowed_axioms"], payload)

    def test_skip_kernel_tc_bypass_is_caught_by_the_forbidden_token_scan(self) -> None:
        """Q1.2: `set_option debug.skipKernelTC true in run_cmd ... Lean.addDecl decl` can add a
        theorem of `False` whose proof term the kernel never type-checks -- confirmed against a
        real Lean 4.34.1 toolchain that `Lean.collectAxioms` then reports zero axioms for it (the
        bypass leaves no axiom trace at all), so only the forbidden-token scan can catch it."""
        proofs_source = (
            "import Lean.Elab.Command\n\n"
            "open Lean Elab Command\n\n"
            "set_option debug.skipKernelTC true in\n"
            "run_cmd do\n"
            "  let decl := Declaration.thmDecl { name := `Unit.myFalseTheorem, levelParams := [], "
            "type := mkConst ``False, value := mkConst ``Nat.zero }\n"
            "  liftCoreM (Lean.addDecl decl)\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            # Must build cleanly first (V1.2, round 6): a failed build now short-circuits
            # `run_prove` *before* the token scan ever runs (`forbidden_tokens` would be `[]`),
            # so this assertion pins the fixture to the intended case -- only the token scan gates
            # `,formal prove` here, never a build failure.
            self.assertTrue(payload["build_ok"], payload)
            self.assertTrue(any(hit["token"] == "skipKernelTC" for hit in payload["forbidden_tokens"]), payload)

    def test_ext_structure_generated_theorems_alone_fail_as_no_theorems(self) -> None:
        """Q1.3: `@[ext] structure`'s generated `.ext`/`.ext_iff` theorems both have a Lean
        declaration range (pointing at the `@[ext]`/structure syntax, not at a real `theorem`
        keyword) -- a file with only such a structure must still fail the vacuity guard."""
        proofs_source = "namespace Unit\n\n@[ext]\nstructure ExtOnly where\n  a : Nat\n  b : Nat\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertGreater(payload["theorem_count"], 0, payload)
            self.assertEqual(0, payload["user_written_count"], payload)
            self.assertIn("no theorems", payload.get("error", ""))

    def test_attribute_ext_command_generated_theorems_alone_fail_as_no_theorems(self) -> None:
        """Q1.3: a standalone `attribute [ext]` command generates the same `.ext`/`.ext_iff`
        theorems as `@[ext] structure`, with the same declaration-range-but-no-`theorem`-keyword
        shape."""
        proofs_source = (
            "namespace Unit\n\nstructure AttrExtOnly where\n  a : Nat\n  b : Nat\n\n"
            "attribute [ext] AttrExtOnly\n\nend Unit\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertGreater(payload["theorem_count"], 0, payload)
            self.assertEqual(0, payload["user_written_count"], payload)
            self.assertIn("no theorems", payload.get("error", ""))

    def test_deriving_reflbeq_lawfulbeq_generated_theorem_alone_fails_as_no_theorems(self) -> None:
        """Q1.3: `deriving BEq, ReflBEq, LawfulBEq` synthesizes an `instLawfulBEq...`/
        `instReflBEq...` instance theorem with a declaration range pointing at the `deriving`
        clause, not at a real `theorem` keyword."""
        proofs_source = (
            "namespace Unit\n\ninductive DerivOnly where\n  | left\n  | right (n : Nat)\n"
            "  deriving BEq, ReflBEq, LawfulBEq\n\nend Unit\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertGreater(payload["theorem_count"], 0, payload)
            self.assertEqual(0, payload["user_written_count"], payload)
            self.assertIn("no theorems", payload.get("error", ""))

    def test_deriving_decidableeq_inhabited_nonempty_generated_theorem_alone_fails_as_no_theorems(self) -> None:
        """Q1.3: `deriving DecidableEq, Inhabited, Nonempty` synthesizes an `instNonempty...`
        instance theorem (`DecidableEq`/`Inhabited` derive `def`s, not theorems, but `Nonempty`
        derives a theorem-kind instance) with a declaration range pointing at the `deriving`
        clause, not at a real `theorem` keyword."""
        proofs_source = (
            "namespace Unit\n\ninductive DerivOnly2 where\n  | left\n  | right (n : Nat)\n"
            "  deriving DecidableEq, Inhabited, Nonempty\n\nend Unit\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertGreater(payload["theorem_count"], 0, payload)
            self.assertEqual(0, payload["user_written_count"], payload)
            self.assertIn("no theorems", payload.get("error", ""))

    def test_a_runtime_built_skip_kernel_tc_option_evades_the_token_scan_but_fails_the_kernel_recheck(
        self,
    ) -> None:
        """S2.1: `Name.mkStr2 "debug" ("skipKernel" ++ "TC")` builds the exact same option the
        literal `debug.skipKernelTC` token names, but the literal token `skipKernelTC` never
        appears anywhere in this source -- unlike `test_skip_kernel_tc_bypass_is_caught_by_the_
        forbidden_token_scan` above, the forbidden-token scan has nothing to match here, and
        `Lean.collectAxioms` on the resulting `boom : False := bogus` reports zero axioms (the
        bypass leaves no axiom trace either). Only the independent kernel re-check
        (`lake env leanchecker`, run after every other check already said "pass") can catch this
        -- this is the refuter's `bypass.lean` repro verbatim."""
        proofs_source = (
            "import Lean\n"
            "open Lean Elab Command\n\n"
            "namespace Unit\n\n"
            "run_cmd liftCoreM do\n"
            "  let decl := Declaration.thmDecl {\n"
            "    name := `Unit.bogus, levelParams := [], type := mkConst ``False, "
            "value := mkConst ``True.intro }\n"
            '  let opts := (← getOptions).setBool (Name.mkStr2 "debug" ("skipKernel" ++ "TC")) true\n'
            "  withOptions (fun _ => opts) (addDecl decl)\n\n"
            "theorem boom : False := bogus\n\n"
            "end Unit\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["forbidden_tokens"])
            self.assertEqual([], payload["axioms"]["disallowed_axioms"])
            self.assertTrue(payload["axioms"]["ok"], payload)
            self.assertFalse(payload["ok"], payload)
            self.assertFalse(payload["kernel_check"]["ok"], payload)
            self.assertFalse(payload["kernel_check"]["environment_error"], payload)
            self.assertIn("leanchecker", payload["kernel_check"]["message"])
            self.assertIn("Unit.bogus", payload["kernel_check"]["message"])

    def test_a_runtime_built_add_decl_core_bypass_proving_one_eq_two_fails_the_kernel_recheck(self) -> None:
        """S2.1: a second, differently-shaped kernel bypass (the refuter's "one_eq_two" case) --
        `Unit.one_eq_two` is declared with type `(1 : Nat) = 2` but its added proof term's real
        type is `(1 : Nat) = 1`, added under the same runtime-built `skipKernelTC` option so the
        elaborator never runs the kernel check that would reject the mismatch. Confirmed against
        a real Lean 4.34.1 toolchain: `lake build` succeeds and `Lean.collectAxioms` reports zero
        axioms for `Unit.one_eq_two`, but `lake env leanchecker` replays it through the real
        kernel afterwards and reports a declaration type mismatch."""
        proofs_source = (
            "import Lean\n"
            "open Lean Elab Command\n\n"
            "namespace Unit\n\n"
            "run_cmd liftCoreM do\n"
            "  let decl := Declaration.thmDecl {\n"
            "    name := `Unit.one_eq_two\n"
            "    levelParams := []\n"
            "    type := mkApp3 (mkConst ``Eq [Level.succ Level.zero]) (mkConst ``Nat) "
            "(mkRawNatLit 1) (mkRawNatLit 2)\n"
            "    value := mkApp2 (mkConst ``Eq.refl [Level.succ Level.zero]) (mkConst ``Nat) "
            "(mkRawNatLit 1) }\n"
            '  let opts := (← getOptions).setBool (Name.mkStr2 "debug" ("skipKernel" ++ "TC")) true\n'
            "  withOptions (fun _ => opts) (addDecl decl)\n\n"
            "theorem one_eq_two_thm : (1 : Nat) = 2 := Unit.one_eq_two\n\n"
            "end Unit\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["forbidden_tokens"])
            self.assertEqual([], payload["axioms"]["disallowed_axioms"])
            self.assertTrue(payload["axioms"]["ok"], payload)
            self.assertFalse(payload["ok"], payload)
            self.assertFalse(payload["kernel_check"]["ok"], payload)
            self.assertFalse(payload["kernel_check"]["environment_error"], payload)
            self.assertIn("leanchecker", payload["kernel_check"]["message"])
            self.assertIn("Unit.one_eq_two", payload["kernel_check"]["message"])

    def test_a_clean_unit_still_passes_the_kernel_recheck(self) -> None:
        """S2.1: the kernel re-check must not turn a genuinely clean unit into a false failure."""
        proofs_source = "namespace Unit\n\ntheorem clean_ok : True := trivial\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual({"ok": True, "environment_error": False, "exit_code": 0}, payload["kernel_check"])

    def test_a_doc_comment_mentioning_theorem_before_an_instance_is_not_counted_as_user_written(
        self,
    ) -> None:
        """S2.2: the old `(preText.splitOn "theorem").length > 1` check was a bare substring test
        over text that includes doc comments -- a doc comment mentioning the word "theorem" right
        before an unrelated `instance`/`structure` declaration must not make that declaration
        count as user-written; this file has no real `theorem` keyword anywhere at all, so it
        must fail the vacuity guard exactly like `test_ext_structure_generated_theorems_alone_
        fail_as_no_theorems` above."""
        proofs_source = (
            "namespace Unit\n\n"
            "structure Inv (n : Nat) : Prop where\n"
            "  /-- positive, see theorem -/\n"
            "  pos : n > 0\n\n"
            "/-- Nonempty witness for the theorem prover -/\n"
            "instance : Nonempty (Inv 1) := ⟨⟨Nat.one_pos⟩⟩\n\n"
            "end Unit\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertGreater(payload["theorem_count"], 0, payload)
            self.assertEqual(0, payload["user_written_count"], payload)
            self.assertEqual([], payload["user_written_theorems"], payload)
            self.assertIn("no theorems", payload.get("error", ""))

    def test_private_protected_simp_and_set_option_in_theorems_are_all_still_counted(self) -> None:
        """S2.2: the whole-token, comment-stripped check must still recognize every real
        `theorem` keyword through its leading modifiers/attributes, not just a bare `theorem
        name : ...` -- `private`, `protected`, `@[simp]`, and `set_option ... in` each place the
        keyword after some other syntax the old substring check already handled by accident."""
        proofs_source = (
            "namespace Unit\n\n"
            "private theorem priv_ok : True := trivial\n\n"
            "protected theorem prot_ok : True := trivial\n\n"
            "@[simp] theorem simp_ok : True := trivial\n\n"
            "set_option maxHeartbeats 400000 in\n"
            "theorem set_opt_ok : True := trivial\n\n"
            "end Unit\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(4, payload["user_written_count"], payload)
            self.assertEqual(
                {"Unit.priv_ok", "Unit.prot_ok", "Unit.simp_ok", "Unit.set_opt_ok"},
                set(payload["user_written_theorems"]),
            )
            self.assertTrue(payload["ok"], payload)
            self.assertTrue(payload["kernel_check"]["ok"], payload)

    def test_underscore_named_guillemet_theorem_is_counted_as_user_written(self) -> None:
        """Q1.3: `` theorem `«_x»` `` -- an underscore-named theorem that needs guillemet
        escaping -- must still be counted as user-written; a naive text-equality criterion
        comparing the selection-range text (which includes the guillemets) against the bare name
        component (which does not) would wrongly exclude it."""
        proofs_source = "theorem «_x» : True := trivial\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit(workspace, formal_home, proofs_source)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(1, payload["theorem_count"])
            self.assertEqual(1, payload["user_written_count"])
            self.assertEqual(["_x"], payload["user_written_theorems"])

    def _init_toy_unit_with_model_extra(
        self, workspace: Path, formal_home: Path, proofs_source: str, model_extra: str
    ) -> Path:
        """Like ``_init_toy_unit``, but appends ``model_extra`` (real Lean source, its own
        distinct namespace so it never collides with the fixture's own names) to the end of
        ``Unit/Model.lean`` -- used to exercise a semantic-only violation somewhere other than
        `Unit.Proofs` (round 5's `Model.lean`/`Esc*.lean` cases), still reachable through
        `Unit.Model`'s own place in the unit's module scope."""
        unit_dir = self._init_toy_unit(workspace, formal_home, proofs_source)
        model_path = unit_dir / "Unit" / "Model.lean"
        model_path.write_text(model_path.read_text(encoding="utf-8") + "\n" + model_extra, encoding="utf-8")
        return unit_dir

    def test_implemented_by_in_an_ordinary_path_dependency_fails_prove(self) -> None:
        proofs_source = (
            "import Unit.Model\n\nnamespace Unit\n\n"
            "theorem dependency_value_is_logical : dependencyValue = 3 := rfl\n\nend Unit\n"
        )
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            dependency_dir = workspace / "dep"
            dependency_dir.mkdir(parents=True)
            (dependency_dir / "lakefile.toml").write_text(
                'name = "Dep"\nversion = "0.1.0"\n\n[[lean_lib]]\nname = "Dep"\n',
                encoding="utf-8",
            )
            (dependency_dir / "Dep.lean").write_text(
                "namespace Dep\n"
                "def fastImpl (n : Nat) : Nat := n + 1\n"
                "@[implemented_by fastImpl] def spec (n : Nat) : Nat := n\n"
                "end Dep\n",
                encoding="utf-8",
            )
            unit_dir = self._init_toy_unit(workspace, formal_home, proofs_source)
            model_path = unit_dir / "Unit" / "Model.lean"
            model_path.write_text(
                "import Dep\n" + model_path.read_text(encoding="utf-8") + "\n"
                "namespace Unit\n"
                "def dependencyValue : Nat := Dep.spec 3\n"
                "end Unit\n",
                encoding="utf-8",
            )
            lakefile = unit_dir / "lakefile.toml"
            lakefile.write_text(
                lakefile.read_text(encoding="utf-8")
                + f'\n[[require]]\nname = "Dep"\npath = "{dependency_dir.as_posix()}"\n',
                encoding="utf-8",
            )

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["forbidden_tokens"], payload)
            violations = {(entry["name"], entry["kind"]) for entry in payload["scope_violations"]}
            self.assertIn(("Dep.spec", "implemented_by"), violations, payload)

    def test_implemented_by_hidden_from_the_broken_text_scan_is_still_caught_semantically(self) -> None:
        """U1.5: the refuter's `Esc.lean` (a `'\\x41'` char-escape the *current* `strip_comments`
        does not understand, which corrupts its scan state into a bogus unterminated string that
        swallows the rest of the file, including the literal `implemented_by` line -- confirmed:
        `prove.scan_forbidden_tokens` reports zero hits for this exact file today) still fails
        `,formal prove`, because `formalcheck` never scans text at all -- it reads
        `Lean.Compiler.getImplementedBy?` directly off the compiled environment."""
        model_extra = (
            "namespace Unit.EscTest\n"
            "def cs : List Char := ['\\x41','\"']\n"
            'def s1 : String := "/-"\n'
            "def fastImpl (n : Nat) : Nat := n + 1\n"
            "@[implemented_by fastImpl] def spec (n : Nat) : Nat := n\n"
            "theorem spec_id : spec 3 = 3 := rfl\n"
            'def s2 : String := "-/"\n'
            "end Unit.EscTest\n"
        )
        proofs_source = "namespace Unit\n\ntheorem clean_thm : True := trivial\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit_with_model_extra(workspace, formal_home, proofs_source, model_extra)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["forbidden_tokens"], payload)
            violations = {(v["name"], v["kind"]) for v in payload["scope_violations"]}
            self.assertIn(("Unit.EscTest.spec", "implemented_by"), violations, payload)

    def test_a_forbidden_construct_hidden_only_in_main_lean_fails_prove(self) -> None:
        """U1.5: a `debug.skipKernelTC` bypass placed directly in `Main.lean` (never
        `Unit/*.lean`) that adds an unrelated, ill-typed `Helper.bogus : False := True.intro` --
        the old design's forbidden-token scan (`Unit/*.lean` only) and kernel re-check (default,
        current-package-name-prefixed `leanchecker` with no explicit target, which never matches
        `Main`) both missed this; the explicit module list (which includes `Main`) passed to the
        broadened text scan and to `leanchecker` now both cover it -- `leanchecker`'s real kernel
        replay is what actually rejects the type mismatch (`collectAxioms` alone does not, see
        the module docstring)."""
        proofs_source = "namespace Unit\n\ntheorem clean_thm : True := trivial\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            unit_dir = self._init_toy_unit(workspace, formal_home, proofs_source)
            main_path = unit_dir / "Main.lean"
            original_main = main_path.read_text(encoding="utf-8")
            bypass = (
                "open Lean Elab Command in\n"
                "run_cmd liftCoreM do\n"
                "  let decl := Declaration.thmDecl {\n"
                "    name := `Helper.bogus, levelParams := [], type := mkConst ``False, "
                "value := mkConst ``True.intro }\n"
                '  let opts := (\u2190 getOptions).setBool (Name.mkStr2 "debug" ("skipKernel" ++ "TC")) true\n'
                "  withOptions (fun _ => opts) (addDecl decl)\n"
            )
            main_path.write_text("import Lean\n" + original_main + "\n" + bypass, encoding="utf-8")

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["axioms"]["ok"], payload)
            self.assertEqual([], payload["scope_violations"], payload)
            self.assertFalse(payload["kernel_check"]["ok"], payload)
            self.assertFalse(payload["kernel_check"]["environment_error"], payload)
            self.assertIn("Helper.bogus", payload["kernel_check"]["message"])

    def test_a_non_unit_prefix_lean_lib_bypass_fails_prove(self) -> None:
        """U1.5: a separate, non-`Unit`-prefixed `lean_lib` (`Evil`) a unit's own
        `lakefile.toml` adds, whose `Evil.bogus : False := True.intro` is added the same
        ill-typed way, referenced from a normally-elaborated `Unit.Proofs` theorem
        (`theorem boom : False := Evil.bogus`). `collectAxioms Unit.boom` reports zero axioms
        (elaboration trusts `Evil.bogus`'s already-recorded, never-kernel-checked type) -- only
        `leanchecker`'s real kernel replay of `Evil`'s own module (included because
        `compute_module_scope` lists every `.lean` file under the unit dir, not only a `Unit`-
        prefixed one) rejects it."""
        proofs_source = "import Evil\n\nnamespace Unit\n\ntheorem boom : False := Evil.bogus\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            unit_dir = self._init_toy_unit(workspace, formal_home, proofs_source)
            # `debug.skipKernelTC` is built at runtime from two string literals concatenated
            # (`"skipKernel" ++ "TC"`), the same evasion the S2.1 Main.lean-bypass test above
            # uses -- never the literal token, which the (secondary, non-load-bearing) forbidden-
            # token scan would otherwise catch first and short-circuit the receipt before the
            # semantic checker/kernel recheck this test actually exercises ever ran.
            (unit_dir / "Evil.lean").write_text(
                "import Lean\n"
                "open Lean Elab Command in\n"
                "run_cmd liftCoreM do\n"
                '  let opts := (← getOptions).setBool (Name.mkStr2 "debug" ("skipKernel" ++ "TC")) true\n'
                "  withOptions (fun _ => opts) (addDecl (Declaration.thmDecl { name := `Evil.bogus, "
                "levelParams := [], type := mkConst ``False, value := mkConst ``True.intro }))\n",
                encoding="utf-8",
            )
            lakefile = unit_dir / "lakefile.toml"
            lakefile.write_text(
                lakefile.read_text(encoding="utf-8") + '\n[[lean_lib]]\nname = "Evil"\n', encoding="utf-8"
            )

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["axioms"]["ok"], payload)
            self.assertEqual([], payload["scope_violations"], payload)
            self.assertFalse(payload["kernel_check"]["ok"], payload)
            self.assertFalse(payload["kernel_check"]["environment_error"], payload)
            self.assertIn("Evil.bogus", payload["kernel_check"]["message"])

    def test_a_unit_declared_lean_exe_named_leanchecker_never_shadows_the_real_one(self) -> None:
        """U1.5: a unit's own `lakefile.toml` can declare a `lean_exe` also named `leanchecker`
        (`lake env`'s `PATH` puts a unit's own built executables ahead of the toolchain's) -- the
        real kernel re-check must still run the toolchain's real binary by absolute path, never
        the bare, PATH-shadowed name, so a clean unit still passes and the fake binary is never
        the one that ran."""
        proofs_source = "namespace Unit\n\ntheorem clean_thm : True := trivial\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            unit_dir = self._init_toy_unit(workspace, formal_home, proofs_source)
            (unit_dir / "Fake.lean").write_text(
                'def main : IO UInt32 := do\n  IO.eprintln "PATH-shadow leanchecker ran"\n  pure 91\n',
                encoding="utf-8",
            )
            lakefile = unit_dir / "lakefile.toml"
            # `lake build` (no args) only builds `defaultTargets` -- add the fake `leanchecker`
            # exe there too so its `Fake` module is actually compiled (`compute_module_scope`
            # lists `Fake` from the filesystem regardless of whether it was built; an unbuilt
            # module in scope fails `formalcheck`/`leanchecker` with "unknown module prefix",
            # which would mask what this test actually exercises: that the real, absolute-path
            # `leanchecker` runs instead of this PATH-shadowing fake one).
            lakefile.write_text(
                lakefile.read_text(encoding="utf-8").replace(
                    'defaultTargets = ["unit"]', 'defaultTargets = ["unit", "leanchecker"]'
                )
                + '\n[[lean_exe]]\nname = "leanchecker"\nroot = "Fake"\n',
                encoding="utf-8",
            )

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertTrue(payload["kernel_check"]["ok"], payload)

    def test_a_partial_def_anywhere_in_scope_passes_prove(self) -> None:
        """U6.1 (round 5 threat-model amendment): a `partial def`'s logical declaration is a
        genuinely opaque constant, so it cannot make a proof unsound, and its compiled code is
        its own body -- `,formal prove` must not fail a unit merely for containing one. A live
        probe against a real Lean 4.34.1 toolchain (`/tmp/converge-fix-r5-U6/probe1`) shows
        neither the `partial def`'s user-visible name nor its compiler-generated
        `<name>._unsafe_rec` sibling trips `isUnsafe`, `Lean.isExtern`, or
        `Lean.Compiler.getImplementedBy?` either, so no other violation fires for it."""
        model_extra = (
            "namespace Unit.PartialTest\n"
            "partial def loopy : Nat \u2192 Nat\n  | 0 => 0\n  | n+1 => loopy n\n"
            "end Unit.PartialTest\n"
        )
        proofs_source = "namespace Unit\n\ntheorem clean_thm : True := trivial\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            self._init_toy_unit_with_model_extra(workspace, formal_home, proofs_source, model_extra)

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["forbidden_tokens"], payload)
            self.assertEqual([], payload["scope_violations"], payload)
            self.assertTrue(payload["ok"], payload)
            self.assertTrue(payload["kernel_check"]["ok"], payload)

    def test_a_clean_f3_template_unit_passes_prove_end_to_end(self) -> None:
        """U1.5: the real `templates/unit/` stamp (never the toy fixture's own `Unit/*.lean`),
        with one added clean theorem, must still pass every stage of the new checker end to
        end -- proving the semantic checker/kernel re-check work against the actual shipped
        template, not only the toy fixture."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "tmpl", "--tier", "F3", check=True)
            with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
                layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
            unit_dir = layout.work_dir("tmpl")
            (unit_dir / "Unit" / "Proofs.lean").write_text(
                "namespace Unit\n\ntheorem clean_thm : True := trivial\n\nend Unit\n", encoding="utf-8"
            )

            result = run_formal(workspace, formal_home, "prove", "tmpl", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual([], payload["scope_violations"], payload)
            self.assertTrue(payload["kernel_check"]["ok"], payload)

    def test_a_clean_stray_module_nothing_imports_still_builds_and_prove_passes(self) -> None:
        """V1.1 (round 6): `Unit/Scratch.lean` -- a `.lean` file under the unit dir that nothing
        imports -- has no `.olean` from the plain `lake build` above (Lake's own default
        `lean_lib` build only builds its declared roots plus their transitive import closure,
        confirmed against a real Lake 4.34.1 source read, `LeanLibConfig.lean`'s default `globs
        := roots.map Glob.one`). The proofs build step now names every module `compute_module_
        scope` finds, so this stray-but-clean module still gets a real compile attempt and
        `,formal prove` still passes (repro `/tmp/converge-refute-r6-correctness/cases/stray`)."""
        proofs_source = "namespace Unit\n\ntheorem clean_thm : True := trivial\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            unit_dir = self._init_toy_unit(workspace, formal_home, proofs_source)
            (unit_dir / "Unit" / "Scratch.lean").write_text("def scratch : Nat := 1\n", encoding="utf-8")

            result = run_formal(workspace, formal_home, "prove", "toy", "--json")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)

    def test_a_stray_module_with_a_type_error_fails_the_build_with_a_diagnostic(self) -> None:
        """V1.1 (round 6): a stray module that fails to *compile* must surface as an ordinary
        build failure with >= 1 diagnostic -- before this fix, the main `lake build` never even
        attempted to compile it (nothing imports it), so the type error went completely
        undiagnosed until `formalcheck`'s own `importModules` call for it failed with no Lean
        diagnostic at all (repro `/tmp/converge-refute-r6-correctness/cases/stray`)."""
        proofs_source = "namespace Unit\n\ntheorem clean_thm : True := trivial\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            unit_dir = self._init_toy_unit(workspace, formal_home, proofs_source)
            (unit_dir / "Unit" / "Scratch.lean").write_text('def scratch : Nat := "not a nat"\n', encoding="utf-8")

            result = run_formal(workspace, formal_home, "build", "toy", "--proofs", "--json")

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"], payload)
            self.assertFalse(payload.get("environment_error"), payload)
            self.assertGreaterEqual(payload["error_count"], 1, payload)
            self.assertTrue(
                any("Scratch.lean" in (err.get("file") or "") for err in payload["errors"]),
                payload,
            )

    def test_a_scratch_module_under_the_excluded_tmp_dir_is_never_built_or_scanned(self) -> None:
        """W1: `tmp/` is one of `manifest.EXCLUDED_DIRS`, never hashed into the snapshot id -- a
        scratch file placed there must also never enter `compute_module_scope`/
        `scan_forbidden_tokens`, or the proofs build step would pass it to `lake build` as a
        bogus `tmp.Scratch` target Lake can never resolve (`unknown target`). Both `,formal build
        --proofs` and `,formal prove` must still pass with the scratch file present, and the
        forbidden `sorry` inside it must never surface as a hit."""
        proofs_source = "namespace Unit\n\ntheorem clean_thm : True := trivial\n\nend Unit\n"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            unit_dir = self._init_toy_unit(workspace, formal_home, proofs_source)
            (unit_dir / "tmp").mkdir()
            (unit_dir / "tmp" / "Scratch.lean").write_text("sorry\n", encoding="utf-8")

            build_result = run_formal(workspace, formal_home, "build", "toy", "--proofs", "--json")
            self.assertEqual(0, build_result.returncode, build_result.stdout + build_result.stderr)
            build_payload = json.loads(build_result.stdout)
            self.assertTrue(build_payload["ok"], build_payload)

            prove_result = run_formal(workspace, formal_home, "prove", "toy", "--json")
            self.assertEqual(0, prove_result.returncode, prove_result.stdout + prove_result.stderr)
            prove_payload = json.loads(prove_result.stdout)
            self.assertTrue(prove_payload["ok"], prove_payload)
            self.assertEqual([], prove_payload["forbidden_tokens"], prove_payload)


if __name__ == "__main__":
    unittest.main()
