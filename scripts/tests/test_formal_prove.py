from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest import mock

from tests.formal_support import (
    prove_mod,
)

_FAKE_KIT_DIR = Path("/fake/kit")
_FAKE_FORMALCHECK = _FAKE_KIT_DIR / ".lake" / "build" / "bin" / "formalcheck"


@contextmanager
def _patch_kit_pipeline() -> Iterator[None]:
    """Patches ``_kit_dir_for_unit``/``ensure_formalcheck`` so ``run_prove`` reaches its own
    ``run()`` call for the `formalcheck` invocation without needing a real ``MANIFEST.json``/kit
    checkout on disk. Every ``run_prove``-wiring test below cares about what ``run_prove`` does
    with a *given* formalcheck/leanchecker result, not the kit-resolution step itself (covered
    separately by ``TestKitResolution``)."""
    with mock.patch.object(prove_mod, "_kit_dir_for_unit", return_value=_FAKE_KIT_DIR):
        with mock.patch.object(prove_mod, "ensure_formalcheck", return_value=_FAKE_FORMALCHECK):
            yield


class TestProve(unittest.TestCase):
    """WHEN the forbidden-token scan and `formalcheck`'s JSON output are checked without Lean
    (the enumeration itself -- run by the compiled `formalcheck` executable, not a Python regex --
    is covered by real-Lean tests in ``TestProveOverRealLean``)."""

    def test_forbidden_token_scan_ignores_comments_and_catches_sorry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text(
                "-- sorry mentioned only in a comment, should not count\n"
                "/- admit is also only in a block comment -/\n"
                "theorem ok_theorem : True := by\n"
                "  sorry\n",
                encoding="utf-8",
            )

            hits = prove_mod.scan_forbidden_tokens(unit_dir)

            self.assertEqual(1, len(hits))
            self.assertEqual("sorry", hits[0]["token"])
            self.assertEqual(4, hits[0]["line"])

    def test_strip_comments_handles_nested_block_comments_and_doc_comments_preserving_line_numbers(self) -> None:
        source = (
            "/- outer /- inner sorry -/ still outer -/\n"
            "/-- doc comment mentioning admit -/\n"
            "theorem ok_theorem : True := by\n"
            "  trivial\n"
            "-- axiom in a line comment\n"
            "theorem another : True := by\n"
            "  sorry\n"
        )

        stripped = prove_mod.strip_comments(source)
        hits_by_line = {}
        for lineno, line in enumerate(stripped.splitlines(), start=1):
            for match in prove_mod._TOKEN_RE.finditer(line):
                hits_by_line[lineno] = match.group(1)

        # The nested comment on line 1 and the doc comment on line 2 must not surface a hit, and
        # the real `sorry` on line 7 (after two comment-only lines) must keep its true line
        # number, proving comment removal replaced text with newlines rather than dropping lines.
        self.assertEqual({7: "sorry"}, hits_by_line)

    def test_forbidden_token_scan_catches_add_decl_core_a_live_kernel_bypass_route(self) -> None:
        """S1.4: `env.addDeclCore 0 decl none false` (the kernel-level `addDeclCore`, positionally
        passing `false` for `doCheck`) is a real, live route that bypasses the kernel check without
        `debug.skipKernelTC` (see the `FORBIDDEN_TOKENS` comment) -- the scan must catch the
        `addDeclCore` call itself."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text(
                "run_cmd do\n  let env ← getEnv\n  let env ← IO.ofExcept (env.addDeclCore 0 decl none false)\n",
                encoding="utf-8",
            )

            hits = prove_mod.scan_forbidden_tokens(unit_dir)

            hits_by_line = {hit["line"]: hit["token"] for hit in hits}
            self.assertEqual({3: "addDeclCore"}, hits_by_line)

    def test_forbidden_token_scan_never_opens_a_comment_from_a_string_literal(self) -> None:
        """Q1.1: a string literal containing `"/-"` or `"--"` must never be mistaken for a
        comment opener -- both real forbidden tokens after it must still surface at their real
        line numbers."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Model.lean").write_text(
                'def banner : String := "/-"\ndef banner2 : String := "--"\nnative_decide\nunsafe\n',
                encoding="utf-8",
            )

            hits = prove_mod.scan_forbidden_tokens(unit_dir)

            hits_by_line = {hit["line"]: hit["token"] for hit in hits}
            self.assertEqual({3: "native_decide", 4: "unsafe"}, hits_by_line)

    def test_strip_comments_a_lone_prime_in_an_identifier_is_not_mistaken_for_a_char_literal(self) -> None:
        source = "theorem reset_from_done' : True := trivial\n-- sorry\n"

        stripped = prove_mod.strip_comments(source)

        self.assertEqual("theorem reset_from_done' : True := trivial\n\n", stripped)

    def test_strip_comments_a_stray_top_level_close_never_makes_depth_negative(self) -> None:
        """Q1.5: a stray `-/` with no matching `/-` at depth 0 is not a comment opener/closer at
        all -- it is copied through verbatim, and the following line comment is still stripped
        normally (depth must never go negative)."""
        stripped = prove_mod.strip_comments("a -/ b\n-- sorry\n")

        self.assertEqual("a -/ b\n\n", stripped)

    def test_strip_comments_a_raw_string_with_embedded_quote_and_slash_dash_never_opens_a_comment(
        self,
    ) -> None:
        """S1.1: `r#"a"/-"#` is real, compiling Lean (confirmed against a real Lean 4.34.1
        toolchain) whose body is the literal text `a"/-` -- the lone `"` at single-hash depth does
        not close the string early, and the embedded `/-` never opens a block comment. The whole
        token round-trips unchanged, and a real `native_decide` immediately after it still surfaces
        as a hit at its own line."""
        source = 'def banner : String := r#"a"/-"#\ntheorem t : 2 + 2 = 4 := by native_decide\n-- -/\n'

        stripped = prove_mod.strip_comments(source)

        self.assertEqual('def banner : String := r#"a"/-"#\ntheorem t : 2 + 2 = 4 := by native_decide\n\n', stripped)
        hits = {m.group(1) for m in prove_mod._TOKEN_RE.finditer(stripped)}
        self.assertEqual({"native_decide"}, hits)

    def test_strip_comments_a_raw_string_has_no_escapes_and_does_not_swallow_the_next_line(self) -> None:
        """S1.1: `r"\\"` (a raw string whose body is one literal backslash) is real, compiling
        Lean -- the backslash does not escape the closing quote (raw strings have no escapes), so
        the string closes right there and a plain string opening on the very next line is not
        mistaken for still being inside the raw string."""
        source = 'def p : String := r"\\"\ndef q : String := "/-"\nunsafe def f : Nat := 1\n'

        stripped = prove_mod.strip_comments(source)

        self.assertEqual(source, stripped)
        hits = {m.group(1) for m in prove_mod._TOKEN_RE.finditer(stripped)}
        self.assertEqual({"unsafe"}, hits)

    def test_strip_comments_an_interpolated_string_never_opens_a_comment_from_its_own_braces(
        self,
    ) -> None:
        """S1.1: `s!"{"/-"}"` is real, compiling Lean -- the `{...}` is real code containing a
        nested plain string literal `"/-"`, so the `/-` inside it never opens a block comment
        (which would otherwise swallow the rest of the file, including the real `unsafe` below)."""
        source = 's!"{"/-"}"\nunsafe def hidden2 : Nat := 1\n-- -/\ndef main : IO Unit := 0\n'

        stripped = prove_mod.strip_comments(source)

        self.assertEqual('s!"{"/-"}"\nunsafe def hidden2 : Nat := 1\n\ndef main : IO Unit := 0\n', stripped)
        hits = {m.group(1) for m in prove_mod._TOKEN_RE.finditer(stripped)}
        self.assertEqual({"unsafe"}, hits)

    def test_strip_comments_an_identifier_ending_in_a_prefix_letter_is_not_mistaken_for_one(
        self,
    ) -> None:
        """S1.1: a raw/interpolated-string prefix letter is only recognized when the character
        right before it is not itself an identifier character -- `myVarr"foo"`/`xs!"foo"` (an
        ordinary identifier applied to a plain string, no space) must not be misread as a
        raw/interpolated-string opener."""
        self.assertEqual('myVarr"foo"', prove_mod.strip_comments('myVarr"foo"'))
        self.assertEqual('xs!"foo"', prove_mod.strip_comments('xs!"foo"'))

    def test_strip_comments_never_raises_on_an_unterminated_raw_or_interpolated_string_at_eof(
        self,
    ) -> None:
        """S1.2: the new raw-string and interpolated-string paths must degrade to "copy the rest
        of the text through unchanged" at EOF, exactly like the pre-existing plain-string/char
        cases, and never raise IndexError."""
        cases = ['r"abc', 'r#"abc', 's!"abc', 's!"{abc', 's!"{"abc']
        for source in cases:
            with self.subTest(source=source):
                self.assertEqual(source, prove_mod.strip_comments(source))

    def test_check_prove_theorems_accepts_the_allowed_set_and_rejects_extra_axioms(self) -> None:
        clean = prove_mod.check_prove_theorems(
            [
                {"name": "Unit.ok_theorem", "axioms": []},
                {"name": "Unit.other_theorem", "axioms": ["propext", "Classical.choice"]},
            ]
        )
        self.assertTrue(clean["ok"])
        self.assertEqual([], clean["disallowed_axioms"])

        dirty = prove_mod.check_prove_theorems([{"name": "Unit.bad_theorem", "axioms": ["propext", "myCustomAxiom"]}])
        self.assertFalse(dirty["ok"])
        self.assertIn("myCustomAxiom", dirty["disallowed_axioms"])

    def test_check_prove_theorems_is_not_ok_for_zero_theorems(self) -> None:
        result = prove_mod.check_prove_theorems([])
        self.assertFalse(result["ok"])
        self.assertEqual(0, result["theorem_count"])

    def test_parse_prove_json_accepts_the_expected_shape_and_sorts_and_deduplicates(self) -> None:
        stdout = json.dumps(
            {
                "theorems": [{"name": "Unit.z", "axioms": []}, {"name": "Unit.a", "axioms": ["sorryAx"]}],
                "user_written": ["Unit.z", "Unit.a"],
                "scope_violations": [
                    {"name": "Unit.b", "kind": "unsafe"},
                    {"name": "Unit.b", "kind": "extern"},
                    {"name": "Unit.b", "kind": "extern"},
                ],
            }
        )
        parsed = prove_mod.parse_prove_json(stdout)
        self.assertNotIn("error", parsed)
        self.assertEqual(["Unit.a", "Unit.z"], [t["name"] for t in parsed["theorems"]])
        self.assertEqual(["Unit.a", "Unit.z"], parsed["user_written"])
        self.assertEqual(
            [{"name": "Unit.b", "kind": "extern"}, {"name": "Unit.b", "kind": "unsafe"}], parsed["scope_violations"]
        )

    def test_parse_prove_json_reports_an_error_for_garbage_stdout(self) -> None:
        parsed = prove_mod.parse_prove_json("not json at all")
        self.assertIn("error", parsed)

    def test_parse_prove_json_reports_an_error_for_a_missing_theorems_key(self) -> None:
        parsed = prove_mod.parse_prove_json(json.dumps({"nope": [], "user_written": [], "scope_violations": []}))
        self.assertIn("error", parsed)

    def test_parse_prove_json_reports_an_error_for_a_missing_user_written_key(self) -> None:
        parsed = prove_mod.parse_prove_json(json.dumps({"theorems": [], "scope_violations": []}))
        self.assertIn("error", parsed)

    def test_parse_prove_json_reports_an_error_for_a_missing_scope_violations_key(self) -> None:
        parsed = prove_mod.parse_prove_json(json.dumps({"theorems": [], "user_written": []}))
        self.assertIn("error", parsed)

    def test_parse_prove_json_reports_an_error_for_a_malformed_theorem_entry(self) -> None:
        parsed = prove_mod.parse_prove_json(
            json.dumps({"theorems": [{"name": "Unit.a"}], "user_written": [], "scope_violations": []})
        )
        self.assertIn("error", parsed)

    def test_parse_prove_json_reports_an_error_for_a_malformed_user_written_entry(self) -> None:
        parsed = prove_mod.parse_prove_json(
            json.dumps({"theorems": [], "user_written": [1, 2], "scope_violations": []})
        )
        self.assertIn("error", parsed)

    def test_parse_prove_json_reports_an_error_for_a_malformed_scope_violations_entry(self) -> None:
        parsed = prove_mod.parse_prove_json(
            json.dumps({"theorems": [], "user_written": [], "scope_violations": [{"name": "Unit.a"}]})
        )
        self.assertIn("error", parsed)

    def test_compute_module_scope_lists_every_lean_file_under_the_unit_dir_excluding_dot_lake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text("", encoding="utf-8")
            (unit_dir / "Unit" / "Model.lean").write_text("", encoding="utf-8")
            (unit_dir / "Main.lean").write_text("", encoding="utf-8")
            (unit_dir / "Evil.lean").write_text("", encoding="utf-8")
            (unit_dir / ".lake" / "formal").mkdir(parents=True)
            (unit_dir / ".lake" / "formal" / "Axioms.lean").write_text("", encoding="utf-8")

            modules = prove_mod.compute_module_scope(unit_dir)

            self.assertEqual(["Evil", "Main", "Unit.Model", "Unit.Proofs"], modules)

    def test_compute_module_scope_excludes_every_top_level_dir_manifest_excludes(self) -> None:
        """W1: `compute_module_scope` must skip every top-level dir `manifest.EXCLUDED_DIRS`
        excludes from the snapshot/version hash (`receipts`, `traces`, `.lake`, `tmp`), not only
        `.lake/` -- a scratch `tmp/Scratch.lean` used to enter the module scope as a bogus
        `tmp.Scratch` build target that Lake can never resolve (`unknown target`), even though
        `tmp/` is already excluded from the snapshot id that gates `,formal audit`'s own receipt
        cache."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text("", encoding="utf-8")
            (unit_dir / "tmp").mkdir()
            (unit_dir / "tmp" / "Scratch.lean").write_text("", encoding="utf-8")
            (unit_dir / "receipts").mkdir()
            (unit_dir / "receipts" / "Old.lean").write_text("", encoding="utf-8")
            (unit_dir / "traces").mkdir()
            (unit_dir / "traces" / "Trace.lean").write_text("", encoding="utf-8")

            modules = prove_mod.compute_module_scope(unit_dir)

            self.assertEqual(["Unit.Proofs"], modules)

    def test_scan_forbidden_tokens_excludes_every_top_level_dir_manifest_excludes(self) -> None:
        """W1: mirrors the module-scope exclusion above for the forbidden-token scan -- a
        forbidden token in a scratch file under `tmp/` must never surface a hit."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "tmp").mkdir()
            (unit_dir / "tmp" / "Scratch.lean").write_text("sorry\n", encoding="utf-8")

            hits = prove_mod.scan_forbidden_tokens(unit_dir)

            self.assertEqual([], hits)


class TestProveTheoremDetection(unittest.TestCase):
    """WHEN the precompiled `formalcheck` executable reports zero theorems (F13). Real Lean's own enumeration
    -- attributes, modifiers, and privacy -- is exercised end to end in ``TestProveOverRealLean``;
    this class only covers what ``run_prove`` does with the *reported* JSON, mocked here so it
    runs without Lean."""

    def test_zero_theorems_fails_prove_instead_of_passing_vacuously(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text("namespace Unit\nend Unit\n", encoding="utf-8")
            clean = subprocess.CompletedProcess(
                ["lake", "env", "formalcheck"],
                0,
                json.dumps({"theorems": [], "user_written": [], "scope_violations": []}),
                "",
            )

            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=clean):
                    receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertEqual(0, receipt["theorem_count"])
            self.assertEqual(0, receipt["user_written_count"])
            self.assertIn("no theorems", receipt.get("error", ""))

    def test_structure_and_inductive_only_file_has_a_nonzero_checked_count_but_fails_as_no_theorems(self) -> None:
        """A `Proofs.lean` with only `structure`/`inductive` declarations must still fail the
        vacuity guard: their compiler-generated `mk.inj`/`mk.injEq`/`sizeOf_spec` lemmas make the
        *checked* count nonzero (they are never excluded from the axiom check), but none of them
        is user-written, so the *user-written* count -- the one the guard actually uses -- is 0."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text(
                "namespace Unit\nstructure Foo where\n  x : Nat\nend Unit\n", encoding="utf-8"
            )
            # Simulates what the real `formalcheck` executable would report for such a file:
            # several compiler-generated theorem-kind constants checked, none of them user-written.
            clean = subprocess.CompletedProcess(
                ["lake", "env", "formalcheck"],
                0,
                json.dumps(
                    {
                        "theorems": [
                            {"name": "Unit.Foo.mk.inj", "axioms": []},
                            {"name": "Unit.Foo.mk.injEq", "axioms": []},
                        ],
                        "user_written": [],
                        "scope_violations": [],
                    }
                ),
                "",
            )

            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=clean):
                    receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertEqual(2, receipt["theorem_count"])
            self.assertEqual(0, receipt["user_written_count"])
            self.assertIn("no theorems", receipt.get("error", ""))


class TestProveParsingRederived(unittest.TestCase):
    """WHEN ``parse_prove_json``'s shape checks must not become a match-everything or
    never-match validator (re-derived after the source-regex enumeration was replaced by the
    precompiled `formalcheck` executable's own JSON output; test-integrity group "prove parsing")."""

    def test_a_genuinely_malformed_json_document_is_reported_as_an_error_not_silently_accepted(self) -> None:
        result = prove_mod.parse_prove_json("this is not a #print axioms line at all\n")

        self.assertIn("error", result)

    def test_a_json_document_that_is_not_an_object_is_reported_as_an_error(self) -> None:
        result = prove_mod.parse_prove_json(json.dumps(["Unit.foo"]))

        self.assertIn("error", result)

    def test_run_prove_fails_closed_when_lean_prints_a_real_compiler_error_instead_of_json(self) -> None:
        """P1.3: `lake env <formalcheck>` can exit nonzero with a non-JSON error on stdout (not an
        environment failure -- `is_environment_failure` only classifies 124/127) -- `run_prove`
        must fail with that message, never crash or claim a theorem count."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")
            broken = subprocess.CompletedProcess(
                ["lake", "env", "formalcheck"], 1, "Axioms.lean:3:0: error: unknown identifier 'Unit.Proofs'", ""
            )

            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=broken):
                    receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertIsNone(receipt["axioms"])
            self.assertIn("did not print valid JSON", receipt["error"])
            self.assertNotIn("theorem_count", receipt)


class TestStripCommentsExactOutputsR1toR9(unittest.TestCase):
    """S1.3: exact-output killer cases R1-R9 from the test-integrity refuter round
    (/tmp/converge-refute-r4-test-integrity/cur/scripts/tests/test_r4_killers.py), scoped to
    `strip_comments` only -- the case-path variant of that suite (`ActualCase`) belongs to a
    different owner (cli.py's `_actual_case_path`)."""

    CASES = {
        "R1_linecomment_starting_with_prime": ("x --' sorry\n", "x \n"),
        "R2_prime_ident_then_linecomment": ("exact h'-- sorry\n", "exact h'\n"),
        "R3_char_literal_double_quote": ("def q : Char := '\"'\n-- sorry\n", "def q : Char := '\"'\n\n"),
        "R4_comment_after_closed_string": ('def s := "x" -- sorry\n', 'def s := "x" \n'),
        "R5_dashdash_inside_string": (
            'example : "--".length = 2 := by native_decide\n',
            'example : "--".length = 2 := by native_decide\n',
        ),
        "R6_escaped_quote_then_blockopen_in_string": (
            'def s := "\\"/-"\nnative_decide\n-- -/\n',
            'def s := "\\"/-"\nnative_decide\n\n',
        ),
        "R7_prime_at_eof": ("#check x'", "#check x'"),
        "R8_unterminated_string_at_eof": ('"abc', '"abc'),
        "R9_backslash_at_eof_in_string": ('"\\', '"\\'),
    }

    def test_cases(self) -> None:
        for name, (src, want) in self.CASES.items():
            with self.subTest(name):
                self.assertEqual(want, prove_mod.strip_comments(src))


class TestStripCommentsExactOutputsR5MutantKillers(unittest.TestCase):
    """S1.2/S1.3 continued: exact-output killer cases for round 5 mutation-testing survivors
    608, 615, 617, 590, 597, 624 (see ``mutants/manifest.json`` under the round 5 formal
    mutation run) -- EOF safety for a bare ``r`` that never opens a raw string at all, and for
    an interpolated string's trailing backslash right after its opening quote, plus
    comment/brace handling inside an interpolated string's ``{expr}`` region."""

    CASES = {
        "M608_M615_bare_r_identifier_at_eof": ("a r", "a r"),
        "M617_interp_string_backslash_at_eof": ('s!"\\', 's!"\\'),
        "M590_interp_string_escaped_quote_before_linecomment": ('s!"a\\"b" -- c', 's!"a\\"b" '),
        "M597_M624_interp_string_nested_brace_and_blockcomment": ('s!"{ {a} /- c -/ }"', 's!"{ {a}  }"'),
        "M624_interp_string_brace_inside_blockcomment": ('s!"{ /- { -/ x}" -- z', 's!"{  x}" '),
    }

    def test_cases(self) -> None:
        for name, (src, want) in self.CASES.items():
            with self.subTest(name):
                self.assertEqual(want, prove_mod.strip_comments(src))


class TestProveShortCircuits(unittest.TestCase):
    """WHEN `run_prove` must never invoke Lean at all for a build failure or a forbidden-token
    hit -- zero theorems can no longer short-circuit before Lean runs, since Lean itself is now
    what discovers the theorem count (test-integrity group "prove short-circuits")."""

    def test_a_forbidden_token_hit_short_circuits_before_ever_calling_lean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text(
                "theorem ok_theorem : True := by\n  sorry\n", encoding="utf-8"
            )

            with mock.patch.object(prove_mod, "run") as run_mock:
                receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertTrue(receipt["forbidden_tokens"])
            run_mock.assert_not_called()

    def test_zero_theorems_still_calls_lean_since_lean_is_the_source_of_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text("namespace Unit\nend Unit\n", encoding="utf-8")
            clean = subprocess.CompletedProcess(
                ["lake", "env", "formalcheck"],
                0,
                json.dumps({"theorems": [], "user_written": [], "scope_violations": []}),
                "",
            )

            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=clean) as run_mock:
                    receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertEqual(0, receipt["theorem_count"])
            run_mock.assert_called_once()

    def test_a_failed_build_receipt_short_circuits_before_ever_calling_lean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")

            with mock.patch.object(prove_mod, "run") as run_mock:
                receipt = prove_mod.run_prove(unit_dir, {"ok": False}, timeout=30)

            self.assertFalse(receipt["ok"])
            # Never claims a theorem count without ever asking Lean.
            self.assertIsNone(receipt.get("theorem_count"))
            run_mock.assert_not_called()

    def test_a_failed_build_never_scans_tokens_even_with_a_non_utf8_lean_file(self) -> None:
        """V1.2 (round 6): `run_prove` must check `build_receipt["ok"]` *before* ever scanning --
        a failed build can leave a unit dir containing a broken/non-UTF-8 `.lean` file (a stray
        module the build itself already rejected), and the old ordering scanned unconditionally
        first, crashing with `UnicodeDecodeError` before this short-circuit was ever reached."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_bytes(b"-- caf\xe9\ntheorem t : True := trivial\n")

            with mock.patch.object(prove_mod, "scan_forbidden_tokens") as scan_mock:
                with mock.patch.object(prove_mod, "run") as run_mock:
                    receipt = prove_mod.run_prove(unit_dir, {"ok": False}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertEqual([], receipt["forbidden_tokens"])
            scan_mock.assert_not_called()
            run_mock.assert_not_called()

    def test_run_prove_never_raises_on_a_non_utf8_lean_file_when_the_build_passed(self) -> None:
        """V1.2 (round 6): a latin-1 byte in a comment (repro
        `/tmp/converge-refute-r6-correctness/cases/latin1`) used to crash `scan_forbidden_tokens`
        with `UnicodeDecodeError` -- `path.read_text(..., errors="replace")` degrades to scanning
        the replacement character in its place instead, so `run_prove` always returns a receipt
        dict, never a traceback."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_bytes(
                b"import Unit.Step\nnamespace Unit\n-- caf\xe9\ntheorem t1 : True := trivial\nend Unit\n"
            )

            receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertIsInstance(receipt, dict)
            self.assertEqual([], receipt["forbidden_tokens"])


class TestProveLeanExitCodeGatesOk(unittest.TestCase):
    """WHEN `lake env <formalcheck>` exits nonzero but not with an environment-failure code:
    `run_prove` must fail closed even when the printed axiom-usage output would otherwise look
    clean, and must only pass when both the exit code is 0 AND the axiom check holds
    (test-integrity group "environment-failure classification" / prove.py's own returncode
    gate)."""

    def _unit_with_one_theorem(self, tmp: Path) -> Path:
        unit_dir = Path(tmp)
        (unit_dir / "Unit").mkdir()
        (unit_dir / "Unit" / "Proofs.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")
        return unit_dir

    def test_a_zero_exit_with_clean_axiom_output_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = self._unit_with_one_theorem(tmp)
            clean_json = json.dumps(
                {
                    "theorems": [{"name": "Unit.t", "axioms": []}],
                    "user_written": ["Unit.t"],
                    "scope_violations": [],
                }
            )
            clean = subprocess.CompletedProcess(["lake", "env", "formalcheck"], 0, clean_json, "")
            passing_kernel_check = {"ok": True, "environment_error": False, "exit_code": 0}
            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=clean):
                    with mock.patch.object(prove_mod, "run_kernel_recheck", return_value=passing_kernel_check):
                        receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertTrue(receipt["ok"])

    def test_a_nonzero_non_environment_exit_fails_even_with_clean_axiom_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = self._unit_with_one_theorem(tmp)
            clean_json = json.dumps(
                {
                    "theorems": [{"name": "Unit.t", "axioms": []}],
                    "user_written": ["Unit.t"],
                    "scope_violations": [],
                }
            )
            nonzero = subprocess.CompletedProcess(["lake", "env", "formalcheck"], 1, clean_json, "some warning")
            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=nonzero):
                    with mock.patch.object(prove_mod, "run_kernel_recheck") as kernel_mock:
                        receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertTrue(receipt["axioms"]["ok"])
            self.assertEqual(1, receipt["lean_exit_code"])
            # A nonzero, non-environment `formalcheck` exit already fails `receipt["ok"]` on its
            # own -- the independent kernel re-check is a final safety net over an *otherwise*
            # clean receipt, never reached once this earlier gate has already failed.
            kernel_mock.assert_not_called()

    def test_a_scope_violation_names_the_constant_and_kind_in_receipt_error(self) -> None:
        """V1.3 (mutant 578): a scope-violation payload must name the offending constant and its
        kind (e.g. `Unit.x (unsafe)`) in `receipt["error"]`."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = self._unit_with_one_theorem(tmp)
            violation_json = json.dumps(
                {
                    "theorems": [{"name": "Unit.t", "axioms": []}],
                    "user_written": ["Unit.t"],
                    "scope_violations": [{"name": "Unit.x", "kind": "unsafe"}],
                }
            )
            result = subprocess.CompletedProcess(["lake", "env", "formalcheck"], 0, violation_json, "")
            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=result):
                    receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertIn("Unit.x (unsafe)", receipt["error"])

    def test_an_axiom_only_failure_error_never_claims_a_scope_violation(self) -> None:
        """V1.3 (mutant 578): when only `Unit.Proofs`'s own axiom check fails (no
        `scope_violations` at all), `receipt["error"]` must not say "constant(s) in scope failed"
        -- that message is reserved for an actual scope violation."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = self._unit_with_one_theorem(tmp)
            dirty_json = json.dumps(
                {
                    "theorems": [{"name": "Unit.t", "axioms": ["sorryAx"]}],
                    "user_written": ["Unit.t"],
                    "scope_violations": [],
                }
            )
            result = subprocess.CompletedProcess(["lake", "env", "formalcheck"], 0, dirty_json, "")
            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=result):
                    receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertNotIn("constant(s) in scope failed", receipt.get("error", ""))

    def test_run_prove_propagates_an_ensure_formalcheck_environment_error_without_calling_run(self) -> None:
        """V1.3 (mutant 611, prove.py's `ensure_formalcheck` branch): when `ensure_formalcheck`
        itself reports an environment error, `run_prove` must propagate `environment_error: True`
        and never call `run` for `formalcheck` at all."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = self._unit_with_one_theorem(tmp)
            env_error = {"ok": False, "environment_error": True, "message": "x"}
            with mock.patch.object(prove_mod, "_kit_dir_for_unit", return_value=_FAKE_KIT_DIR):
                with mock.patch.object(prove_mod, "ensure_formalcheck", return_value=env_error):
                    with mock.patch.object(prove_mod, "run") as run_mock:
                        receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertTrue(receipt["environment_error"])
            self.assertEqual("x", receipt["message"])
            run_mock.assert_not_called()

    def test_run_prove_reports_an_environment_error_and_never_calls_run_when_kit_hash_is_missing(self) -> None:
        """V1.3 (mutant 625, prove.py's `kit_dir is None` branch): a `MANIFEST.json` with no
        usable `kit_hash` must fail closed with `environment_error: True` and a message naming
        `kit_hash`, and `run_prove` must never call `run` at all -- there is no kit dir to build
        `formalcheck` in or invoke it from."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = self._unit_with_one_theorem(tmp)
            (unit_dir / "MANIFEST.json").write_text(json.dumps({"unit": "u"}), encoding="utf-8")

            with mock.patch.object(prove_mod, "run") as run_mock:
                receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertTrue(receipt["environment_error"])
            self.assertIn("kit_hash", receipt["message"])
            run_mock.assert_not_called()


class TestKernelRecheck(unittest.TestCase):
    """S2.1: `run_kernel_recheck` classifies `lake env <absolute leanchecker path> <modules>`'s
    result, and `run_prove` only ever calls it once every earlier check has already said "pass"
    -- mocked here so it runs without Lean (the real kernel-bypass and clean-unit cases,
    including the absolute-path resolution and the explicit module list themselves, are
    exercised end to end against a real Lean 4.34.1 toolchain in
    ``test_formal_e2e.TestProveOverRealLean``)."""

    def _unit_with_one_theorem(self, tmp: Path) -> Path:
        unit_dir = Path(tmp)
        (unit_dir / "Unit").mkdir()
        (unit_dir / "Unit" / "Proofs.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")
        return unit_dir

    def test_run_kernel_recheck_passes_on_a_zero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            clean = subprocess.CompletedProcess(["lake", "env", "/toolchain/bin/leanchecker"], 0, "", "")
            with mock.patch.object(prove_mod, "resolve_leanchecker", return_value=Path("/toolchain/bin/leanchecker")):
                with mock.patch.object(prove_mod, "run", return_value=clean) as run_mock:
                    result = prove_mod.run_kernel_recheck(unit_dir, ["Unit.Proofs"], timeout=30)

            self.assertEqual({"ok": True, "environment_error": False, "exit_code": 0}, result)
            run_mock.assert_called_once_with(
                ["lake", "env", "/toolchain/bin/leanchecker", "Unit.Proofs"], cwd=unit_dir, timeout=30
            )

    def test_run_kernel_recheck_rejects_a_real_check_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            rejected = subprocess.CompletedProcess(
                ["lake", "env", "/toolchain/bin/leanchecker"],
                1,
                "",
                "leanchecker found a problem in Unit.Proofs\nuncaught exception: ...",
            )
            with mock.patch.object(prove_mod, "resolve_leanchecker", return_value=Path("/toolchain/bin/leanchecker")):
                with mock.patch.object(prove_mod, "run", return_value=rejected):
                    result = prove_mod.run_kernel_recheck(unit_dir, ["Unit.Proofs"], timeout=30)

            self.assertFalse(result["ok"])
            self.assertFalse(result["environment_error"])
            self.assertEqual(1, result["exit_code"])
            self.assertIn("Unit.Proofs", result["message"])

    def test_run_kernel_recheck_reports_an_environment_error_for_a_124_or_127_exit(self) -> None:
        for code in (124, 127):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                unit_dir = Path(tmp)
                env_fail = subprocess.CompletedProcess(["lake", "env", "/toolchain/bin/leanchecker"], code, "", "boom")
                with mock.patch.object(
                    prove_mod, "resolve_leanchecker", return_value=Path("/toolchain/bin/leanchecker")
                ):
                    with mock.patch.object(prove_mod, "run", return_value=env_fail):
                        result = prove_mod.run_kernel_recheck(unit_dir, ["Unit.Proofs"], timeout=30)

                self.assertFalse(result["ok"])
                self.assertTrue(result["environment_error"])

    def test_run_kernel_recheck_reports_an_environment_error_when_the_binary_is_missing(self) -> None:
        """`lake env <missing-binary>` exits 255 with `could not execute external process
        '<name>'` (confirmed against a real Lean 4.34.1 toolchain) -- neither exit code
        `is_environment_failure` already recognizes (124/127), so a missing `leanchecker` must
        still be classified as an environment error, never a pass."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            missing = subprocess.CompletedProcess(
                ["lake", "env", "/toolchain/bin/leanchecker"],
                255,
                "",
                "could not execute external process 'leanchecker'",
            )
            with mock.patch.object(prove_mod, "resolve_leanchecker", return_value=Path("/toolchain/bin/leanchecker")):
                with mock.patch.object(prove_mod, "run", return_value=missing):
                    result = prove_mod.run_kernel_recheck(unit_dir, ["Unit.Proofs"], timeout=30)

            self.assertFalse(result["ok"])
            self.assertTrue(result["environment_error"])
            self.assertEqual(255, result["exit_code"])

    def test_run_kernel_recheck_does_not_misclassify_an_ordinary_255_exit_as_missing(self) -> None:
        """A 255 exit without the "could not execute external process" marker is a real check
        failure, not a missing binary -- it must not be silently swallowed as an environment
        error (which `,formal audit` never caches)."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            weird = subprocess.CompletedProcess(
                ["lake", "env", "/toolchain/bin/leanchecker"], 255, "", "some other failure"
            )
            with mock.patch.object(prove_mod, "resolve_leanchecker", return_value=Path("/toolchain/bin/leanchecker")):
                with mock.patch.object(prove_mod, "run", return_value=weird):
                    result = prove_mod.run_kernel_recheck(unit_dir, ["Unit.Proofs"], timeout=30)

            self.assertFalse(result["ok"])
            self.assertFalse(result["environment_error"])

    def test_run_kernel_recheck_reports_the_resolve_leanchecker_environment_error_without_ever_calling_run(
        self,
    ) -> None:
        """When `resolve_leanchecker` itself fails (e.g. `lake env lean --print-prefix` failed, or
        the resolved binary does not exist), `run_kernel_recheck` must report that failure
        directly and never attempt to run a nonexistent/unresolved binary."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            leanchecker_error = {"ok": False, "environment_error": True, "message": "leanchecker binary not found"}
            with mock.patch.object(prove_mod, "resolve_leanchecker", return_value=leanchecker_error):
                with mock.patch.object(prove_mod, "run") as run_mock:
                    result = prove_mod.run_kernel_recheck(unit_dir, ["Unit.Proofs"], timeout=30)

            self.assertEqual({**leanchecker_error, "exit_code": None}, result)
            run_mock.assert_not_called()

    def test_run_prove_only_calls_the_kernel_recheck_once_every_earlier_check_already_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = self._unit_with_one_theorem(tmp)
            clean_json = json.dumps(
                {
                    "theorems": [{"name": "Unit.t", "axioms": []}],
                    "user_written": ["Unit.t"],
                    "scope_violations": [],
                }
            )
            clean_lean_result = subprocess.CompletedProcess(["lake", "env", "formalcheck"], 0, clean_json, "")
            passing_kernel_check = {"ok": True, "environment_error": False, "exit_code": 0}
            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=clean_lean_result):
                    with mock.patch.object(
                        prove_mod, "run_kernel_recheck", return_value=passing_kernel_check
                    ) as kernel_mock:
                        receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertTrue(receipt["ok"])
            self.assertEqual(passing_kernel_check, receipt["kernel_check"])
            kernel_mock.assert_called_once_with(unit_dir, ["Unit.Proofs"], 30)

    def test_run_prove_flips_ok_to_false_when_the_kernel_recheck_rejects_an_otherwise_clean_receipt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = self._unit_with_one_theorem(tmp)
            clean_json = json.dumps(
                {
                    "theorems": [{"name": "Unit.t", "axioms": []}],
                    "user_written": ["Unit.t"],
                    "scope_violations": [],
                }
            )
            clean_lean_result = subprocess.CompletedProcess(["lake", "env", "formalcheck"], 0, clean_json, "")
            rejected_kernel_check = {
                "ok": False,
                "environment_error": False,
                "exit_code": 1,
                "message": "kernel re-check (leanchecker) rejected the built modules (exit 1): ...Unit.Proofs...",
            }
            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=clean_lean_result):
                    with mock.patch.object(prove_mod, "run_kernel_recheck", return_value=rejected_kernel_check):
                        receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertTrue(receipt["axioms"]["ok"])  # the earlier axiom check still looked clean
            self.assertFalse(receipt["kernel_check"]["ok"])
            self.assertFalse(receipt["environment_error"])
            self.assertIn("Unit.Proofs", receipt["message"])

    def test_run_prove_never_calls_the_kernel_recheck_when_the_vacuity_guard_already_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text("namespace Unit\nend Unit\n", encoding="utf-8")
            empty_json = json.dumps({"theorems": [], "user_written": [], "scope_violations": []})
            clean_lean_result = subprocess.CompletedProcess(["lake", "env", "formalcheck"], 0, empty_json, "")
            with _patch_kit_pipeline():
                with mock.patch.object(prove_mod, "run", return_value=clean_lean_result) as run_mock:
                    with mock.patch.object(prove_mod, "run_kernel_recheck") as kernel_mock:
                        receipt = prove_mod.run_prove(unit_dir, {"ok": True}, timeout=30)

            self.assertFalse(receipt["ok"])
            self.assertNotIn("kernel_check", receipt)
            run_mock.assert_called_once()
            kernel_mock.assert_not_called()


class TestKitResolution(unittest.TestCase):
    """WHEN `_kit_dir_for_unit`, `ensure_formalcheck`, and `resolve_leanchecker` -- the three new
    helpers `run_prove` chains before ever invoking `formalcheck`/`leanchecker` -- resolve or
    report an environment error, mocked here so they run without Lean (the real kit-copy and
    absolute-path resolution are exercised end to end in ``test_formal_e2e``)."""

    def test_kit_dir_for_unit_reads_the_kit_hash_from_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "MANIFEST.json").write_text(json.dumps({"kit_hash": "abc123"}), encoding="utf-8")
            with mock.patch.object(prove_mod.paths, "state_root", return_value=Path("/state")):
                kit_dir = prove_mod._kit_dir_for_unit(unit_dir)

            self.assertEqual(Path("/state/_kit/abc123"), kit_dir)

    def test_kit_dir_for_unit_is_none_when_the_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            self.assertIsNone(prove_mod._kit_dir_for_unit(unit_dir))

    def test_kit_dir_for_unit_is_none_when_the_manifest_is_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "MANIFEST.json").write_text("not json", encoding="utf-8")
            self.assertIsNone(prove_mod._kit_dir_for_unit(unit_dir))

    def test_kit_dir_for_unit_is_none_when_the_kit_hash_key_is_missing_or_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "MANIFEST.json").write_text(json.dumps({"kit_hash": ""}), encoding="utf-8")
            self.assertIsNone(prove_mod._kit_dir_for_unit(unit_dir))

    def test_ensure_formalcheck_returns_the_built_binary_path_on_a_zero_exit(self) -> None:
        kit_dir = Path("/kit")
        clean = subprocess.CompletedProcess(["lake", "build", "formalcheck"], 0, "", "")
        with mock.patch.object(prove_mod, "run", return_value=clean) as run_mock:
            result = prove_mod.ensure_formalcheck(kit_dir, timeout=30)

        self.assertEqual(kit_dir / ".lake" / "build" / "bin" / "formalcheck", result)
        run_mock.assert_called_once_with(["lake", "build", "formalcheck"], cwd=kit_dir, timeout=30)

    def test_ensure_formalcheck_reports_an_environment_error_on_a_failed_build(self) -> None:
        kit_dir = Path("/kit")
        failed = subprocess.CompletedProcess(["lake", "build", "formalcheck"], 1, "", "error: build failed")
        with mock.patch.object(prove_mod, "run", return_value=failed):
            result = prove_mod.ensure_formalcheck(kit_dir, timeout=30)

        self.assertFalse(result["ok"])
        self.assertTrue(result["environment_error"])

    def test_resolve_leanchecker_returns_the_absolute_path_under_the_toolchain_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            prefix_dir = Path(tmp) / "toolchain"
            (prefix_dir / "bin").mkdir(parents=True)
            (prefix_dir / "bin" / "leanchecker").write_text("", encoding="utf-8")
            prefix_result = subprocess.CompletedProcess(
                ["lake", "env", "lean", "--print-prefix"], 0, f"{prefix_dir}\n", ""
            )
            with mock.patch.object(prove_mod, "run", return_value=prefix_result):
                resolved = prove_mod.resolve_leanchecker(unit_dir, timeout=30)

            self.assertEqual(prefix_dir / "bin" / "leanchecker", resolved)

    def test_resolve_leanchecker_reports_an_environment_error_when_the_prefix_lookup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            failed = subprocess.CompletedProcess(["lake", "env", "lean", "--print-prefix"], 1, "", "boom")
            with mock.patch.object(prove_mod, "run", return_value=failed):
                result = prove_mod.resolve_leanchecker(unit_dir, timeout=30)

            self.assertFalse(result["ok"])
            self.assertTrue(result["environment_error"])
            # V1.4 (mutant 616): a fallback path below (the resolved binary not existing) also
            # sets `ok: False`/`environment_error: True`, so those two assertions alone still pass
            # with this exact branch deleted -- pin the message itself, which only this branch
            # produces, naming `--print-prefix` and carrying lake's own stderr (`boom`).
            self.assertIn("--print-prefix", result["message"])
            self.assertIn("boom", result["message"])

    def test_resolve_leanchecker_reports_an_environment_error_when_the_resolved_binary_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            # A real toolchain prefix dir with no `bin/leanchecker` under it.
            prefix_result = subprocess.CompletedProcess(["lake", "env", "lean", "--print-prefix"], 0, f"{tmp}\n", "")
            with mock.patch.object(prove_mod, "run", return_value=prefix_result):
                result = prove_mod.resolve_leanchecker(unit_dir, timeout=30)

            self.assertFalse(result["ok"])
            self.assertTrue(result["environment_error"])
            self.assertIn("not found", result["message"])


if __name__ == "__main__":
    unittest.main()
