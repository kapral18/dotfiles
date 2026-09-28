from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.formal_support import (
    CLI,
    CliError,
    build_mod,
    exe_mod,
    init_git_repo,
    leankit_mod,
)


class TestBuildDiagnostics(unittest.TestCase):
    """WHEN lake build output is parsed into a compact receipt."""

    def test_diagnostics_are_parsed_with_folded_continuation_lines(self) -> None:
        output = (
            "Unit/Model.lean:12:3: error: unknown identifier 'foo'\n"
            "  additional goal state line\n"
            "Unit/Step.lean:5:0: warning: unused variable 'x'\n"
        )
        diagnostics = build_mod.parse_diagnostics(output)
        self.assertEqual(2, len(diagnostics))
        self.assertEqual("error", diagnostics[0]["severity"])
        self.assertIn("additional goal state line", diagnostics[0]["message"])
        self.assertEqual("warning", diagnostics[1]["severity"])

    def test_lake_status_lines_end_the_diagnostic_without_folding_or_diagnosing(self) -> None:
        """Y1 (round 8): a Lake job-status line (`✔`/`⚠`/`ℹ [n/m] ...`), the trailing `Build
        completed successfully (N jobs).` summary, a plain `info: ...` progress line, and the
        `Some required targets logged failures:` / `- <target>` block are never folded into an
        open diagnostic's message and never become diagnostics of their own -- each only ends
        whatever diagnostic is currently open. A genuine Lean continuation line (goal state)
        right after a real diagnostic must still fold, unaffected by any of this."""
        output = (
            "Unit/Model.lean:12:3: error: unknown identifier 'foo'\n"
            "  additional goal state line\n"
            "✔ [3/10] Built Unit.Model:c.o (61ms)\n"
            "⚠ [4/10] Built Unit.Step (231ms)\n"
            "warning: Unit/Step.lean:3:7: unused variable `y`\n"
            "ℹ [5/10] Built Unit (12ms)\n"
            "info: toolchain not updated; already up-to-date\n"
            "Build completed successfully (5 jobs).\n"
            "Some required targets logged failures:\n"
            "- Unit.Model\n"
            "- Unit.Step\n"
        )

        diagnostics = build_mod.parse_diagnostics(output)

        self.assertEqual(2, len(diagnostics))
        self.assertEqual("error", diagnostics[0]["severity"])
        self.assertIn("additional goal state line", diagnostics[0]["message"])
        self.assertEqual("warning", diagnostics[1]["severity"])
        self.assertEqual("unused variable `y`", diagnostics[1]["message"])

    def test_lake_4_34_1s_own_severity_first_wrapping_is_parsed(self) -> None:
        """Reproduces a real `lake build` failure verbatim (A13): Lake 4.34.1 wraps a Lean
        diagnostic with the severity *before* the location, `error: file:line:col: msg` --
        the opposite order from the plain Lean-diagnostic form above. r5/U2.1: the preceding
        `✖ [..] Building <module>` job-failure marker now also becomes its own positionless
        diagnostic (so a Lean subprocess crash with *only* a marker line, never an `error:` line,
        still yields >= 1 diagnostic) -- the positioned diagnostic that follows is unaffected."""
        output = (
            "info: Unit: no previous manifest, creating one from scratch\n"
            "✖ [7/21] Building Unit.Step (468ms)\n"
            "error: Unit/Step.lean:24:30: Unknown constant `Unit.St.bogus_missing`\n"
            "\n"
            "Note: Inferred this name from the expected resulting type of `.bogus_missing`:\n"
            "  St\n"
        )

        diagnostics = build_mod.parse_diagnostics(output)

        self.assertEqual(2, len(diagnostics))
        self.assertEqual("error", diagnostics[0]["severity"])
        self.assertIsNone(diagnostics[0]["file"])
        self.assertIn("Building Unit.Step", diagnostics[0]["message"])
        self.assertEqual("error", diagnostics[1]["severity"])
        self.assertEqual("Unit/Step.lean", diagnostics[1]["file"])
        self.assertEqual(24, diagnostics[1]["line"])
        self.assertEqual(30, diagnostics[1]["col"])
        self.assertIn("Unknown constant", diagnostics[1]["message"])

    def test_lake_wrapped_warning_is_parsed(self) -> None:
        output = "warning: Unit/Step.lean:5:0: unused variable `x`\n"

        diagnostics = build_mod.parse_diagnostics(output)

        self.assertEqual(1, len(diagnostics))
        self.assertEqual("warning", diagnostics[0]["severity"])
        self.assertEqual(5, diagnostics[0]["line"])

    def test_a_positionless_bad_import_error_is_parsed_with_null_line_and_col(self) -> None:
        """Reproduces a real Lake 4.34.1 bad-import failure verbatim (S3.2): the importing
        file's own diagnostic line names no line/col at all, unlike every other Lean/Lake
        diagnostic form above. r5/U2.1: this shape is no longer enumerated by name -- it is
        parsed by the generic `error: ...` rule, so `file` is `None` (the message text still
        names the file inline) instead of being extracted into the `file` field."""
        output = "error: Unit/Step.lean: bad import 'Unit.Nope'\n"

        diagnostics = build_mod.parse_diagnostics(output)

        self.assertEqual(1, len(diagnostics))
        self.assertEqual("error", diagnostics[0]["severity"])
        self.assertIsNone(diagnostics[0]["file"])
        self.assertIsNone(diagnostics[0]["line"])
        self.assertIsNone(diagnostics[0]["col"])
        self.assertIn("Unit/Step.lean: bad import 'Unit.Nope'", diagnostics[0]["message"])

    def test_a_no_such_file_error_is_parsed_with_the_file_from_the_next_line(self) -> None:
        """Reproduces the real Lake 4.34.1 diagnostic pair emitted for the *missing* module
        itself (S3.2), before the importing file's own `bad import` line. The first diagnostic's
        `  file: <path>` continuation-line attachment is generic (not tied to this one named
        shape) and is unaffected by r5/U2.1; the second (bad-import) diagnostic's `file` is now
        `None` per the generic `error: ...` rule (see the positionless-bad-import test above)."""
        output = (
            "error: no such file or directory (error code: 2)\n"
            "  file: /work/u/Unit/Nope.lean\n"
            "error: Unit/Step.lean: bad import 'Unit.Nope'\n"
        )

        diagnostics = build_mod.parse_diagnostics(output)

        self.assertEqual(2, len(diagnostics))
        self.assertEqual("error", diagnostics[0]["severity"])
        self.assertEqual("/work/u/Unit/Nope.lean", diagnostics[0]["file"])
        self.assertIsNone(diagnostics[0]["line"])
        self.assertIsNone(diagnostics[0]["col"])
        self.assertIsNone(diagnostics[1]["file"])
        self.assertIn("Unit/Step.lean: bad import 'Unit.Nope'", diagnostics[1]["message"])

    def test_a_real_bad_import_build_log_yields_at_least_one_error_diagnostic(self) -> None:
        """Verbatim capture of a real `lake build` bad-import failure (S3.2 refuter repro:
        `/tmp/converge-refute-r4-env/imp/lake-out.txt`) -- `parse_diagnostics` must never return
        zero diagnostics for this output, or `run_audit` misclassifies a genuine bad-import
        build failure as an environment error instead of an ordinary fail. r5/U2.1: every
        `✖ [..] <verb> <target>` job-failure marker line is now its own diagnostic too (not only
        the `error: ...` lines), so `Unit/Step.lean` now surfaces in a diagnostic's `message`
        (the generic `error: ...` rule no longer extracts it into `file`)."""
        output = (
            "✖ [7/14] Running Unit.Nope\n"
            "error: no such file or directory (error code: 2)\n"
            "  file: /work/u/Unit/Nope.lean\n"
            "✖ [9/14] Running Unit.Step\n"
            "error: Unit/Step.lean: bad import 'Unit.Nope'\n"
            "✖ [14/14] Running unit:exe\n"
            "error: bad imports (see the 'Main' job for details)\n"
            "Some required targets logged failures:\n"
            "- Unit.Nope\n"
            "- Unit.Step\n"
            "error: build failed\n"
        )

        diagnostics = build_mod.parse_diagnostics(output)

        errors = [d for d in diagnostics if d["severity"] == "error"]
        self.assertGreaterEqual(len(errors), 1)
        self.assertTrue(any("Unit/Step.lean" in (d["message"] or "") for d in errors))


class TestLeankitEnsureKitRaceSafety(unittest.TestCase):
    """WHEN two concurrent ``ensure_kit`` calls target the same kit hash, or a prior process was
    killed mid-copy, ``ensure_kit`` must never crash or silently trust a partial copy -- A15."""

    class _FakeLayout:
        def __init__(self, root: Path) -> None:
            self.root = root

        def kit_dir(self, kit_hash: str) -> Path:
            return self.root / "_kit" / kit_hash

    def _stub_source(self, tmp: Path) -> Path:
        source = tmp / "source"
        source.mkdir()
        (source / "f.txt").write_text("hello\n", encoding="utf-8")
        return source

    def test_concurrent_ensure_kit_calls_all_succeed_and_produce_one_complete_kit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._stub_source(tmp_path)
            layout = self._FakeLayout(tmp_path / "state")

            real_copytree = shutil.copytree
            copytree_calls: list[Any] = []

            def slow_copytree(src: Any, dst: Any, *a: Any, **k: Any) -> Any:
                # Widen the race window so concurrent callers reliably overlap instead of
                # happening to serialize via the GIL and fast local-disk I/O.
                copytree_calls.append((src, dst))
                time.sleep(0.05)
                return real_copytree(src, dst, *a, **k)

            errors: list[BaseException] = []

            def worker() -> None:
                try:
                    leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

            with mock.patch.object(leankit_mod, "kit_source_dir", return_value=source):
                with mock.patch.object(leankit_mod.shutil, "copytree", side_effect=slow_copytree):
                    threads = [threading.Thread(target=worker) for _ in range(6)]
                    for t in threads:
                        t.start()
                    for t in threads:
                        t.join()

                self.assertEqual([], errors)
                kh = leankit_mod.kit_hash()
                dest = layout.kit_dir(kh)
                self.assertTrue((dest / leankit_mod._KIT_MARKER).exists())
                self.assertTrue((dest / "f.txt").exists())
                # The per-kit-hash lock (`leankit.kit_lock`) must serialize all 6 concurrent
                # callers onto a single winning copy -- the refuter measured 1 `copytree` call
                # with the lock held vs. 6 with `kit_lock` reduced to a no-op.
                self.assertEqual(1, len(copytree_calls))

    def test_first_ensure_accepts_an_initially_empty_lock_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._stub_source(tmp_path)
            layout = self._FakeLayout(tmp_path / "state")

            with mock.patch.object(leankit_mod, "kit_source_dir", return_value=source):
                kh = leankit_mod.kit_hash()
                lock_path = leankit_mod.kit_lock_path(layout.kit_dir(kh))
                lock_path.parent.mkdir(parents=True)
                lock_path.write_text("", encoding="utf-8")

                leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]

            with open(lock_path, "r+", encoding="utf-8") as handle:
                self.assertEqual([os.getpid()], leankit_mod.pending_owner_pids(handle))
            self.assertTrue((layout.kit_dir(kh) / leankit_mod._KIT_MARKER).exists())

    def test_malformed_owner_state_is_rejected_before_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._stub_source(tmp_path)
            layout = self._FakeLayout(tmp_path / "state")

            with mock.patch.object(leankit_mod, "kit_source_dir", return_value=source):
                kh = leankit_mod.kit_hash()
                dest = layout.kit_dir(kh)
                lock_path = leankit_mod.kit_lock_path(dest)
                lock_path.parent.mkdir(parents=True)
                malformed = '{"owners":"not-an-array"}'
                lock_path.write_text(malformed, encoding="utf-8")

                with self.assertRaises(CliError) as ctx:
                    leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]

            self.assertEqual(2, ctx.exception.code)
            self.assertEqual(malformed, lock_path.read_text(encoding="utf-8"))
            self.assertFalse(dest.exists())

    def test_a_partial_kit_without_the_marker_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._stub_source(tmp_path)
            layout = self._FakeLayout(tmp_path / "state")

            with mock.patch.object(leankit_mod, "kit_source_dir", return_value=source):
                kh = leankit_mod.kit_hash()
                dest = layout.kit_dir(kh)
                dest.mkdir(parents=True)
                (dest / "garbage.txt").write_text("partial\n", encoding="utf-8")

                leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]

                self.assertTrue((dest / "f.txt").exists())
                self.assertFalse((dest / "garbage.txt").exists())
                self.assertTrue((dest / leankit_mod._KIT_MARKER).exists())

    def test_a_second_ensure_kit_call_never_touches_an_already_complete_dest(self) -> None:
        """Gap test for mutant 488 (``if (dest / _KIT_MARKER).exists(): return kh`` -> ``if
        False``): a mutated guard would fall through to `rmtree`+recopy every time, wiping out
        any build artifact (``.lake/built``) the first call's caller produced in `dest`."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._stub_source(tmp_path)
            layout = self._FakeLayout(tmp_path / "state")

            with mock.patch.object(leankit_mod, "kit_source_dir", return_value=source):
                kh = leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]
                dest = layout.kit_dir(kh)
                built = dest / ".lake" / "built"
                built.parent.mkdir(parents=True)
                built.write_text("built artifact\n", encoding="utf-8")

                second_kh = leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]

                self.assertEqual(kh, second_kh)
                self.assertTrue(built.exists())

    def test_os_replace_failing_with_no_completed_kit_present_re_raises(self) -> None:
        """Gap test for mutant 491 (``if not (dest / _KIT_MARKER).exists(): raise`` -> ``if
        False``): an `os.replace` failure unrelated to the marker race (no complete `dest` ever
        appears) must propagate, not be swallowed as if another process had won."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._stub_source(tmp_path)
            layout = self._FakeLayout(tmp_path / "state")

            with mock.patch.object(leankit_mod, "kit_source_dir", return_value=source):
                with mock.patch.object(leankit_mod.os, "replace", side_effect=OSError("disk full")):
                    with self.assertRaises(OSError):
                        leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]

                kh = leankit_mod.kit_hash()
                dest = layout.kit_dir(kh)
                self.assertFalse((dest / leankit_mod._KIT_MARKER).exists())

    def test_a_complete_dest_that_appears_mid_check_is_never_rmtreed(self) -> None:
        """Reproduces the race evidence (/tmp/converge-refute-r2-env/race.py,
        /tmp/converge-refute-r2-correctness/p6.py): a stale pre-lock ``dest.exists()`` read taken
        right before another process finishes must not cause this call to `rmtree` that other
        process's now-complete kit -- the marker is re-checked once `kit_lock` is held."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._stub_source(tmp_path)
            layout = self._FakeLayout(tmp_path / "state")

            with mock.patch.object(leankit_mod, "kit_source_dir", return_value=source):
                kh = leankit_mod.kit_hash()
                dest = layout.kit_dir(kh)

                real_exists = Path.exists
                state = {"fired": False}

                def patched_exists(self: Path) -> bool:
                    # Capture the (about to become stale) result *before* firing the concurrent
                    # call, exactly like the race evidence: the caller's own read is a snapshot
                    # taken right before another process finishes.
                    r = real_exists(self)
                    if self.name == leankit_mod._KIT_MARKER and not state["fired"]:
                        state["fired"] = True
                        # A concurrent "other process" finishes a full ensure_kit right after
                        # this call's own (now-stale) marker check.
                        leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]
                    return r

                rmtree_calls: list[Path] = []
                real_rmtree = shutil.rmtree

                def tracking_rmtree(path: Any, *a: Any, **k: Any) -> Any:
                    rmtree_calls.append(Path(path))
                    return real_rmtree(path, *a, **k)

                with mock.patch.object(Path, "exists", patched_exists):
                    with mock.patch.object(leankit_mod.shutil, "rmtree", side_effect=tracking_rmtree):
                        leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]

                self.assertNotIn(dest, rmtree_calls)
                self.assertTrue((dest / leankit_mod._KIT_MARKER).exists())
                self.assertTrue((dest / "f.txt").exists())

    def test_ensure_kit_falls_through_to_copy_when_the_marker_vanishes_before_the_lock(self) -> None:
        """P5.2: the marker-already-there fast path takes the lock but must re-check the marker
        once it is held -- a concurrent `catalog.gc` sweep can remove an unreferenced `dest`
        (marker included) between the unlocked fast-path check and `ensure_kit` actually taking
        the lock. Blindly recording ownership on a `dest` that no longer has its marker would
        return a kit hash whose kit dir is gone or incomplete."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._stub_source(tmp_path)
            layout = self._FakeLayout(tmp_path / "state")

            with mock.patch.object(leankit_mod, "kit_source_dir", return_value=source):
                kh = leankit_mod.kit_hash()
                dest = layout.kit_dir(kh)
                dest.mkdir(parents=True)
                (dest / leankit_mod._KIT_MARKER).write_text("", encoding="utf-8")

                real_kit_lock = leankit_mod.kit_lock
                state = {"fired": False}

                @contextlib.contextmanager
                def racing_kit_lock(d: Any, *, blocking: bool = True) -> Any:
                    with real_kit_lock(d, blocking=blocking) as handle:
                        if not state["fired"]:
                            state["fired"] = True
                            marker = dest / leankit_mod._KIT_MARKER
                            if marker.exists():
                                # Simulate the concurrent removal landing right after the
                                # unlocked fast-path check but before this lock is (re-)held.
                                marker.unlink()
                        yield handle

                with mock.patch.object(leankit_mod, "kit_lock", side_effect=racing_kit_lock):
                    result_kh = leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]

                self.assertEqual(kh, result_kh)
                self.assertTrue((dest / "f.txt").exists())
                self.assertTrue((dest / leankit_mod._KIT_MARKER).exists())

    def test_distinct_live_callers_are_both_retained_as_pending_owners(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._stub_source(tmp_path)
            layout = self._FakeLayout(tmp_path / "state")

            with mock.patch.object(leankit_mod, "kit_source_dir", return_value=source):
                with mock.patch.object(leankit_mod.os, "kill", return_value=None):
                    with mock.patch.object(leankit_mod.os, "getpid", side_effect=[101, 202]):
                        kh = leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]
                        leankit_mod.ensure_kit(layout)  # type: ignore[arg-type]

            lock_path = leankit_mod.kit_lock_path(layout.kit_dir(kh))
            with open(lock_path, "r+", encoding="utf-8") as handle:
                self.assertEqual([101, 202], leankit_mod.pending_owner_pids(handle))


class TestKitLockBlockingFailure(unittest.TestCase):
    """WHEN `kit_lock`'s underlying `flock` fails for a reason other than lock contention (Q5.4):
    a blocking acquisition must raise, never silently yield `None` into `_record_owner`; a
    non-blocking caller keeps its existing "still in use" contract."""

    def test_a_blocking_flock_failure_raises_cli_error_code_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "kit" / "deadbeef"
            with mock.patch.object(leankit_mod.fcntl, "flock", side_effect=OSError("no locks available")):
                with self.assertRaises(CliError) as ctx:
                    with leankit_mod.kit_lock(dest):
                        pass
            self.assertEqual(2, ctx.exception.code)

    def test_a_non_blocking_flock_failure_still_yields_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "kit" / "deadbeef"
            with mock.patch.object(leankit_mod.fcntl, "flock", side_effect=OSError("resource temporarily unavailable")):
                with leankit_mod.kit_lock(dest, blocking=False) as handle:
                    self.assertIsNone(handle)


class TestCopyTemplateMissingSource(unittest.TestCase):
    """WHEN `copy_template`'s own template source is missing -- gap test for mutant 489
    (``if not source.exists(): raise CliError`` -> ``if False``)."""

    def test_formal_lib_dir_with_a_kit_but_no_unit_template_fails_init_with_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            formal_home = tmp_path / "home"
            init_git_repo(workspace)

            # A `FORMAL_LIB_DIR` that provides a real `lean/FormalKit` (so `ensure_kit` succeeds)
            # but no `templates/unit` at all (so `copy_template`'s own guard must fire).
            custom_lib = tmp_path / "custom-lib"
            kit_dir = custom_lib / "lean" / "FormalKit"
            kit_dir.mkdir(parents=True)
            (kit_dir / "lakefile.toml").write_text('name = "FormalKit"\n', encoding="utf-8")

            env = {**os.environ, "AGENT_FORMAL_HOME": str(formal_home), "FORMAL_LIB_DIR": str(custom_lib)}
            result = subprocess.run(
                [sys.executable, str(CLI), "init", "u1"], cwd=workspace, env=env, text=True, capture_output=True
            )

            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("Unit template not found", result.stderr)
            self.assertIn(str(custom_lib), result.stderr)


class TestCopyTemplateStructuredValues(unittest.TestCase):
    """WHEN placeholder values contain string delimiters, generated JSON and TOML remain valid."""

    def test_json_and_toml_values_round_trip_quotes_backslashes_and_controls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "templates"
            destination = root / "unit"
            source.mkdir()
            (source / "MANIFEST.json").write_text('{"branch":"@@BRANCH@@"}\n', encoding="utf-8")
            (source / "lakefile.toml").write_text('path = "@@KIT_PATH@@"\n', encoding="utf-8")
            branch = 'topic"quoted\\path\nnext\tcolumn'
            kit_path = '/state/"quoted"\\kit\nnext\tcolumn'

            with mock.patch.object(leankit_mod, "templates_dir", return_value=source):
                leankit_mod.copy_template(destination, {"BRANCH": branch, "KIT_PATH": kit_path})

            manifest = json.loads((destination / "MANIFEST.json").read_text(encoding="utf-8"))
            key, separator, toml_literal = (
                (destination / "lakefile.toml").read_text(encoding="utf-8").strip().partition("=")
            )
            self.assertEqual(("path", "="), (key.strip(), separator))
            self.assertEqual(branch, manifest["branch"])
            # Generated TOML uses only basic-string escapes, whose emitted subset is JSON-compatible.
            self.assertEqual(kit_path, json.loads(toml_literal.strip()))


class TestMutateClassification(unittest.TestCase):
    """WHEN a mutant is killed by a property other than any it declared as an expected killer."""

    def test_when_killed_by_excludes_every_expected_killer_status_is_wrong_killer(self) -> None:
        mutant = {"name": "M1", "killed_by": ["P_other"], "expected": ["P1"], "status": "killed"}
        self.assertEqual("wrong-killer", exe_mod._classify_mutant(mutant))

    def test_when_an_expected_killer_is_among_the_actual_killers_status_stays_killed(self) -> None:
        mutant = {"name": "M1", "killed_by": ["P1", "P_other"], "expected": ["P1"], "status": "killed"}
        self.assertEqual("killed", exe_mod._classify_mutant(mutant))

    def test_survived_status_is_unaffected(self) -> None:
        mutant = {"name": "M1", "killed_by": [], "expected": ["P1"], "status": "survived"}
        self.assertEqual("survived", exe_mod._classify_mutant(mutant))

    def test_a_killed_mutant_with_no_declared_expected_killers_is_reclassified_wrong_killer(self) -> None:
        """A12 correction: this previously asserted `"killed"` (the pre-fix behavior) --
        an empty `expected` list names no property to validate the mutant against at all, so
        Lean-reported `killed` can never stand; it must reclassify exactly like an actual
        killer mismatch, `wrong-killer` (audit/the standalone `mutate` command additionally
        treat this mutant as vacuous and fail the whole stage)."""
        mutant = {"name": "M1", "killed_by": ["Px"], "expected": [], "status": "killed"}
        self.assertEqual("wrong-killer", exe_mod._classify_mutant(mutant))


class TestBuildReceiptCaps(unittest.TestCase):
    """WHEN a build produces more diagnostics than the receipt caps report (test-integrity group
    "build receipt caps (5 errors / 25 lines)")."""

    def test_parse_diagnostics_caps_continuation_lines_at_25(self) -> None:
        continuation = "\n".join(f"  goal state line {i}" for i in range(30))
        output = f"Unit/Model.lean:12:3: error: unknown identifier 'foo'\n{continuation}\n"

        diagnostics = build_mod.parse_diagnostics(output)

        self.assertEqual(1, len(diagnostics))
        self.assertEqual(25, len(diagnostics[0]["message"].splitlines()))

    def test_lake_build_caps_reported_errors_at_5_but_keeps_the_true_count(self) -> None:
        lines = "\n".join(f"Unit/Model.lean:{n}:1: error: bad thing {n}" for n in range(1, 8))  # 7 distinct errors
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            with mock.patch.object(
                build_mod, "run", return_value=subprocess.CompletedProcess(["lake", "build"], 1, lines, "")
            ):
                receipt = build_mod.lake_build(unit_dir, proofs=False, timeout=5)

        self.assertEqual(7, receipt["error_count"])
        self.assertEqual(5, len(receipt["errors"]))


class TestEnvironmentFailureClassification(unittest.TestCase):
    """WHEN a Lean-toolchain subprocess exits 127 (missing binary): `lake build Unit.Proofs`,
    `lake exe unit explore`/`mutate`, and `lake exe unit traces` must each classify it as an
    environment error (never a genuine check result) (test-integrity group
    "environment-failure classification")."""

    def test_the_proofs_build_step_reports_environment_error_even_when_the_main_build_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            main_ok = subprocess.CompletedProcess(["lake", "build"], 0, "", "")
            proofs_env_failure = subprocess.CompletedProcess(["lake", "build", "Unit.Proofs"], 127, "", "not found")

            with mock.patch.object(build_mod.prove_mod, "compute_module_scope", return_value=["Unit.Proofs"]):
                with mock.patch.object(build_mod, "run", side_effect=[main_ok, proofs_env_failure]):
                    receipt = build_mod.lake_build(unit_dir, proofs=True, timeout=5)

            self.assertTrue(receipt.get("environment_error"))
            self.assertIn("lake build Unit.Proofs", receipt["message"])

    def test_the_proofs_build_step_builds_every_module_in_scope_not_only_unit_proofs(self) -> None:
        """V1.1 (round 6): a stray `.lean` file under the unit dir that nothing imports (e.g.
        `Unit/Scratch.lean`) never gets a `.olean` from the plain `lake build` above -- Lake's own
        default `lean_lib` build only builds each declared root plus its transitive import
        closure (confirmed against a real Lake 4.34.1 source read, `LeanLibConfig.lean`'s default
        `globs := roots.map Glob.one`), never every file under the root directory regardless of
        import status. The proofs build step must therefore name every module
        `prove.compute_module_scope` finds under the unit dir, not only `Unit.Proofs`, so a stray
        module's own compile error is a real build failure with diagnostics instead of a bare,
        undiagnosed `formalcheck`/`leanchecker` `importModules` failure later."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "Unit").mkdir()
            (unit_dir / "Unit" / "Proofs.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")
            (unit_dir / "Unit" / "Scratch.lean").write_text("def scratch : Nat := 1\n", encoding="utf-8")
            (unit_dir / "Main.lean").write_text("def main : IO Unit := pure ()\n", encoding="utf-8")
            calls: list[list[str]] = []

            def fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                calls.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, "", "")

            with mock.patch.object(build_mod, "run", side_effect=fake_run):
                receipt = build_mod.lake_build(unit_dir, proofs=True, timeout=5)

            self.assertTrue(receipt["ok"])
            self.assertEqual(2, len(calls))
            self.assertEqual(["lake", "build"], calls[1][:2])
            self.assertEqual({"Main", "Unit.Proofs", "Unit.Scratch"}, set(calls[1][2:]))

    def test_the_proofs_step_never_double_counts_a_warning_the_main_build_already_reported(self) -> None:
        """W2: the proofs step's own second, explicit `lake build <modules>` call replays every
        already-cached module's own diagnostics verbatim on top of what the first `lake build`
        already printed (confirmed against a real Lake 4.34.1 build) -- concatenating the two
        diagnostic lists unconditionally used to double-count a warning both builds report
        (`warning_count: 2` for one real warning). Merging on (file, line, col, severity,
        message) instead keeps that one warning counted once; a distinct warning the second
        build alone reports is still added."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            repeated_warning = "Unit/Model.lean:5:1: warning: unused variable `x`\n"
            distinct_warning = "Unit/Proofs.lean:2:1: warning: unused variable `y`\n"
            main_ok = subprocess.CompletedProcess(["lake", "build"], 0, repeated_warning, "")
            proofs_ok = subprocess.CompletedProcess(
                ["lake", "build", "Unit.Model", "Unit.Proofs"], 0, repeated_warning + distinct_warning, ""
            )

            with mock.patch.object(
                build_mod.prove_mod, "compute_module_scope", return_value=["Unit.Model", "Unit.Proofs"]
            ):
                with mock.patch.object(build_mod, "run", side_effect=[main_ok, proofs_ok]):
                    receipt = build_mod.lake_build(unit_dir, proofs=True, timeout=5)

            self.assertTrue(receipt["ok"])
            # 1 unique repeated warning + 1 distinct warning = 2 -- unconditional concatenation
            # would count the repeated one twice, for 3.
            self.assertEqual(2, receipt["warning_count"])

    def test_the_proofs_step_never_double_counts_a_warning_across_a_real_two_run_lake_build(self) -> None:
        """Y1 (round 8): `parse_diagnostics` used to fold every following non-blank line into the
        current diagnostic's message, including Lake's own status lines (`✔`/`⚠`/`ℹ [n/m] ...`,
        `Build completed successfully (N jobs).`, `info: ...`). Those differ between the first
        `lake build` and the proofs step's second, explicit `lake build <modules>` (different job
        counts and verbs -- `Built` vs `Replayed`), so the same real warning's *message* text
        never matched between runs and `_merge_diagnostics` never recognized it as a duplicate: 2
        real warnings reported `warning_count` 4. This fixture is the verbatim stdout/stderr of a
        real Lake 4.34.1 two-run build (round 8 correctness-refuter probe, paths already neutral:
        `Unit.Model`/`Unit.Step`) -- a status line must end the current diagnostic, never fold
        into it, so the merge recognizes both repeated warnings and the true count is 2."""
        out1 = (
            "⚠ [2/10] Built Unit.Model (262ms)\n"
            "warning: Unit/Model.lean:2:7: Variable name `x` is not explicitly referenced.\n"
            "\n"
            "Hint: The binding can be removed (if unused) or named `_` (if used implicitly). "
            "Alternatively, prefix the name with `_` to silence this warning:\n"
            "  [apply] _x\n"
            "\n"
            "Note: This linter can be disabled with `set_option linter.unusedVariables false`\n"
            "✔ [3/10] Built Unit.Model:c.o (61ms)\n"
            "⚠ [4/10] Built Unit.Step (231ms)\n"
            "warning: Unit/Step.lean:3:7: Variable name `y` is not explicitly referenced.\n"
            "\n"
            "Hint: The binding can be removed (if unused) or named `_` (if used implicitly). "
            "Alternatively, prefix the name with `_` to silence this warning:\n"
            "  [apply] _y\n"
            "\n"
            "Note: This linter can be disabled with `set_option linter.unusedVariables false`\n"
            "✔ [5/10] Built Unit.Step:c.o (59ms)\n"
            "✔ [6/10] Built Unit (242ms)\n"
            "✔ [7/10] Built Unit:c.o (60ms)\n"
            "✔ [8/10] Built Main (258ms)\n"
            "✔ [9/10] Built Main:c.o (64ms)\n"
            "✔ [10/10] Built unit:exe (127ms)\n"
            "Build completed successfully (10 jobs).\n"
        )
        err1 = (
            "info: Unit: no previous manifest, creating one from scratch\n"
            "info: toolchain not updated; already up-to-date\n"
        )
        out2 = (
            "⚠ [2/6] Replayed Unit.Model\n"
            "warning: Unit/Model.lean:2:7: Variable name `x` is not explicitly referenced.\n"
            "\n"
            "Hint: The binding can be removed (if unused) or named `_` (if used implicitly). "
            "Alternatively, prefix the name with `_` to silence this warning:\n"
            "  [apply] _x\n"
            "\n"
            "Note: This linter can be disabled with `set_option linter.unusedVariables false`\n"
            "⚠ [3/6] Replayed Unit.Step\n"
            "warning: Unit/Step.lean:3:7: Variable name `y` is not explicitly referenced.\n"
            "\n"
            "Hint: The binding can be removed (if unused) or named `_` (if used implicitly). "
            "Alternatively, prefix the name with `_` to silence this warning:\n"
            "  [apply] _y\n"
            "\n"
            "Note: This linter can be disabled with `set_option linter.unusedVariables false`\n"
            "Build completed successfully (6 jobs).\n"
        )

        diagnostics = build_mod.parse_diagnostics(out1 + "\n" + err1)
        self.assertEqual(2, len(diagnostics))
        for diag in diagnostics:
            self.assertEqual("warning", diag["severity"])
            for banned in ("✔", "⚠", "ℹ", "Build completed successfully", "info:"):
                self.assertNotIn(banned, diag["message"])

        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            main_ok = subprocess.CompletedProcess(["lake", "build"], 0, out1, err1)
            proofs_ok = subprocess.CompletedProcess(["lake", "build", "Unit.Model", "Unit.Step"], 0, out2, "")

            with mock.patch.object(
                build_mod.prove_mod, "compute_module_scope", return_value=["Unit.Model", "Unit.Step"]
            ):
                with mock.patch.object(build_mod, "run", side_effect=[main_ok, proofs_ok]):
                    receipt = build_mod.lake_build(unit_dir, proofs=True, timeout=5)

            self.assertTrue(receipt["ok"])
            # 2 real warnings (Unit.Model, Unit.Step), each replayed verbatim by the second `lake
            # build <modules>` call -- unfixed folding made the two runs' text differ (job
            # counts/verbs) so the merge never matched them, for `warning_count` 4.
            self.assertEqual(2, receipt["warning_count"])

    def test_explore_raises_an_environment_error_on_a_127_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            with mock.patch.object(
                exe_mod, "run", return_value=subprocess.CompletedProcess(["lake", "exe"], 127, "", "not found")
            ):
                with self.assertRaises(CliError) as ctx:
                    exe_mod.explore(unit_dir, None, None, timeout=5)
            self.assertTrue(ctx.exception.environment_error)

    def test_mutate_raises_an_environment_error_on_a_127_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            with mock.patch.object(
                exe_mod, "run", return_value=subprocess.CompletedProcess(["lake", "exe"], 127, "", "not found")
            ):
                with self.assertRaises(CliError) as ctx:
                    exe_mod.mutate(unit_dir, None, None, timeout=5)
            self.assertTrue(ctx.exception.environment_error)

    def test_explore_provisioning_failure_is_an_environment_error(self) -> None:
        result = subprocess.CompletedProcess(
            ["lake", "exe", "unit", "explore"], 1, "", "error: error during download\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(exe_mod, "run", return_value=result):
                with self.assertRaises(CliError) as ctx:
                    exe_mod.explore(Path(tmp), None, None, timeout=5)
        self.assertTrue(ctx.exception.environment_error)

    def test_traces_provisioning_failure_is_an_environment_error(self) -> None:
        result = subprocess.CompletedProcess(["lake", "exe", "unit", "traces"], 1, "", "error: error during download\n")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(exe_mod, "run", return_value=result):
                with self.assertRaises(CliError) as ctx:
                    exe_mod.traces(Path(tmp), "cover", None, timeout=5)
        self.assertTrue(ctx.exception.environment_error)

    def test_traces_raises_code_2_on_a_1_exit_without_marking_it_an_environment_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            with mock.patch.object(
                exe_mod, "run", return_value=subprocess.CompletedProcess(["lake", "exe"], 1, "", "boom")
            ):
                with self.assertRaises(CliError) as ctx:
                    exe_mod.traces(unit_dir, "cover", None, timeout=5)
            self.assertEqual(2, ctx.exception.code)
            self.assertFalse(ctx.exception.environment_error)

    def test_the_proofs_step_failing_on_its_own_check_fails_the_whole_build_ok(self) -> None:
        """Distinct from the environment-failure case above: the *main* build passes, and the
        *proofs* build genuinely fails its own check (an ordinary non-environment exit),
        which must still flip the combined receipt's `ok` to False."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            main_ok = subprocess.CompletedProcess(["lake", "build"], 0, "", "")
            proofs_check_failure = subprocess.CompletedProcess(
                ["lake", "build", "Unit.Proofs"], 1, "Unit/Proofs.lean:3:1: error: type mismatch\n", ""
            )

            with mock.patch.object(build_mod.prove_mod, "compute_module_scope", return_value=["Unit.Proofs"]):
                with mock.patch.object(build_mod, "run", side_effect=[main_ok, proofs_check_failure]):
                    receipt = build_mod.lake_build(unit_dir, proofs=True, timeout=5)

            self.assertFalse(receipt["ok"])
            self.assertFalse(receipt.get("environment_error"))
            self.assertEqual(1, receipt["error_count"])

    def test_a_nonzero_proofs_exit_with_no_parseable_diagnostic_still_fails_ok(self) -> None:
        """Isolates the bare `proofs_result.returncode == 0` check from the `errors` list (which
        alone would already force `ok` False): an empty, unparseable proofs failure has zero
        diagnostics, so only the returncode comparison itself can flip `ok`."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            main_ok = subprocess.CompletedProcess(["lake", "build"], 0, "", "")
            proofs_failure_no_diagnostics = subprocess.CompletedProcess(["lake", "build", "Unit.Proofs"], 1, "", "")

            with mock.patch.object(build_mod.prove_mod, "compute_module_scope", return_value=["Unit.Proofs"]):
                with mock.patch.object(build_mod, "run", side_effect=[main_ok, proofs_failure_no_diagnostics]):
                    receipt = build_mod.lake_build(unit_dir, proofs=True, timeout=5)

            self.assertEqual(0, receipt["error_count"])
            self.assertFalse(receipt["ok"])


class TestBuildEnvironmentSignatureClassification(unittest.TestCase):
    """WHEN `lake build` exits nonzero because elan/Lake could not even provision or run the
    pinned toolchain (never a genuine Lean check result) -- r5/U2.1: `parse_diagnostics` no
    longer enumerates every Lake failure shape by name, so `lake_build` must independently flag
    these elan/toolchain-provisioning signatures as `environment_error` itself (never inferred
    later from `error_count == 0`). Each simulated output is the exact text captured from a real
    elan 4.2.4 + Lean 4.34.1 install (/tmp/converge-fix-r5-U2/toolchain-missing/,
    /tmp/converge-fix-r5-U2/spawn/) -- see `build.py`'s `_ENV_SIGNATURE_RE` comment for the
    elan/Lean source references."""

    def test_an_unresolvable_toolchain_pin_is_an_environment_error(self) -> None:
        """Verbatim: `echo 'leanprover/lean4:v9.99.99-nonexistent' > lean-toolchain; lake build`
        (elan 4.2.4, real network) -- `error: no such release: '<tag>'` on stderr, exit 1."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            result = subprocess.CompletedProcess(
                ["lake", "build"], 1, "", "error: no such release: 'v9.99.99-nonexistent'\n"
            )
            with mock.patch.object(build_mod, "run", return_value=result):
                receipt = build_mod.lake_build(unit_dir, proofs=False, timeout=5)
            self.assertFalse(receipt["ok"])
            self.assertTrue(receipt.get("environment_error"))
            self.assertEqual(0, receipt["error_count"])

    def test_an_offline_download_failure_is_an_environment_error(self) -> None:
        """Verbatim: an uninstalled real toolchain with an unreachable proxy (elan 4.2.4) --
        `error: error during download` on stderr (wrapping the underlying curl error), exit 1."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            result = subprocess.CompletedProcess(
                ["lake", "build"],
                1,
                "",
                "error: error during download\n"
                "info: caused by: [7] Couldn't connect to server (Failed to connect to "
                "127.0.0.1 port 9 after 0 ms: Couldn't connect to server)\n",
            )
            with mock.patch.object(build_mod, "run", return_value=result):
                receipt = build_mod.lake_build(unit_dir, proofs=False, timeout=5)
            self.assertFalse(receipt["ok"])
            self.assertTrue(receipt.get("environment_error"))
            self.assertEqual(0, receipt["error_count"])

    def test_a_could_not_execute_external_process_failure_is_an_environment_error(self) -> None:
        """The Lean 4.34.1 runtime's own subprocess-spawn error (confirmed present verbatim in
        the installed toolchain's runtime dylib via `strings`): a genuinely missing or
        non-executable toolchain binary, never a Lean source diagnostic."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            result = subprocess.CompletedProcess(
                ["lake", "build"],
                1,
                "",
                "uncaught exception: could not execute external process 'lean' (No such file or directory)\n",
            )
            with mock.patch.object(build_mod, "run", return_value=result):
                receipt = build_mod.lake_build(unit_dir, proofs=False, timeout=5)
            self.assertFalse(receipt["ok"])
            self.assertTrue(receipt.get("environment_error"))
            self.assertEqual(0, receipt["error_count"])

    def test_the_proofs_step_hitting_an_environment_signature_is_also_an_environment_error(self) -> None:
        """Same signature, but on the *second* (`Unit.Proofs`) subprocess -- must be classified
        identically to the main-build case, not silently folded into an ordinary check failure."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            main_ok = subprocess.CompletedProcess(["lake", "build"], 0, "", "")
            proofs_env_signature = subprocess.CompletedProcess(
                ["lake", "build", "Unit.Proofs"], 1, "", "error: no such release: 'v9.99.99-nonexistent'\n"
            )
            with mock.patch.object(build_mod.prove_mod, "compute_module_scope", return_value=["Unit.Proofs"]):
                with mock.patch.object(build_mod, "run", side_effect=[main_ok, proofs_env_signature]):
                    receipt = build_mod.lake_build(unit_dir, proofs=True, timeout=5)
            self.assertTrue(receipt.get("environment_error"))

    def test_an_environment_signature_alongside_a_real_diagnostic_is_still_flagged(self) -> None:
        """The signature check runs regardless of what else is in the combined output -- an
        elan/toolchain failure line never becomes a diagnostic itself (`has_environment_signature`
        gates the whole receipt, independent of `parse_diagnostics`'s own per-line handling)."""
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            result = subprocess.CompletedProcess(
                ["lake", "build"],
                1,
                "Unit/Model.lean:1:0: error: unrelated diagnostic\n",
                "error: no such release: 'v9.99.99-nonexistent'\n",
            )
            with mock.patch.object(build_mod, "run", return_value=result):
                receipt = build_mod.lake_build(unit_dir, proofs=False, timeout=5)
            self.assertTrue(receipt.get("environment_error"))

    def test_has_environment_signature_is_false_for_an_ordinary_compile_error(self) -> None:
        self.assertFalse(build_mod.has_environment_signature("Unit/Model.lean:1:0: error: type mismatch\n"))

    def test_the_env_signature_line_itself_never_becomes_a_diagnostic(self) -> None:
        diagnostics = build_mod.parse_diagnostics("error: no such release: 'v9.99.99-nonexistent'\n")
        self.assertEqual([], diagnostics)


class TestExeTracesMaxForwarding(unittest.TestCase):
    """WHEN `traces`'s own `max_n` argument is forwarded to `lake exe unit traces --max`, and
    omitted entirely (never as a literal `None`) when absent (part of "budget forwarding")."""

    def test_max_n_is_forwarded_as_a_flag_when_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            captured: dict[str, Any] = {}

            def fake_run(argv, **kwargs):
                captured["argv"] = argv
                return subprocess.CompletedProcess(argv, 0, "", "")

            with mock.patch.object(exe_mod, "run", side_effect=fake_run):
                exe_mod.traces(unit_dir, "cover", 42, timeout=5)

            self.assertIn("--max", captured["argv"])
            self.assertIn("42", captured["argv"])

    def test_max_n_none_is_never_forwarded_as_a_flag_at_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            captured: dict[str, Any] = {}

            def fake_run(argv, **kwargs):
                captured["argv"] = argv
                return subprocess.CompletedProcess(argv, 0, "", "")

            with mock.patch.object(exe_mod, "run", side_effect=fake_run):
                exe_mod.traces(unit_dir, "cover", None, timeout=5)

            self.assertNotIn("--max", captured["argv"])
            self.assertNotIn("None", captured["argv"])


class TestExePropOkTable(unittest.TestCase):
    """WHEN `prop_ok` decides whether a property's observed status meets its declared
    expectation -- the full 5-row truth table (test-integrity group "prop_ok table")."""

    def test_prop_ok_truth_table(self) -> None:
        cases = [
            ({"expect": "holds", "status": "holds"}, True),
            ({"expect": "holds", "status": "violated"}, False),
            ({"expect": "refuted", "status": "violated"}, True),
            ({"expect": "refuted", "status": "holds"}, False),
            ({"expect": "unknown-expect", "status": "holds"}, False),
        ]
        for prop, expected in cases:
            with self.subTest(prop=prop):
                self.assertEqual(expected, exe_mod.prop_ok(prop))


if __name__ == "__main__":
    unittest.main()
