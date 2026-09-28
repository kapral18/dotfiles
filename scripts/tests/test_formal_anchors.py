from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.formal_support import (
    anchors_mod,
    commit_all,
    init_git_repo,
    manifest_mod,
    paths_mod,
    run_formal,
)


class TestAnchors(unittest.TestCase):
    """WHEN the working tree changes around an anchored snippet."""

    def _anchor(
        self,
        path: str,
        text: str,
        start: int,
        end: int,
        unique: bool = True,
        source_text: str | None = None,
    ) -> dict[str, Any]:
        anchor = {
            "id": "A1",
            "path": path,
            "start": start,
            "end": end,
            "snippet": anchors_mod.normalize_snippet(text.removesuffix("\n")),
            "unique": unique,
        }
        if source_text is not None:
            anchor["source_sha"] = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        return anchor

    def test_when_the_file_is_unchanged_the_anchor_resolves_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            original = "def foo():\n    return 1\n"
            (workspace / "sample.py").write_text(original + "\ndef bar():\n    return 2\n", encoding="utf-8")
            anchor = self._anchor("sample.py", original, 1, 2)

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("unchanged", result["status"])
            self.assertEqual(1, result["start"])
            self.assertEqual(2, result["end"])
            self.assertFalse(result["relocated"])

    def test_when_nonliteral_whitespace_changes_the_anchor_is_edited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            original = "def foo():\n    return 1\n"
            (workspace / "sample.py").write_text(original, encoding="utf-8")
            anchor = self._anchor("sample.py", original, 1, 2)

            reformatted = "def foo():   \n\n    return    1\n"
            (workspace / "sample.py").write_text(reformatted, encoding="utf-8")

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("edited", result["status"])

    def test_when_indentation_or_token_spacing_changes_the_anchor_is_edited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            original = "def foo():\n    return 1\n"
            (workspace / "sample.py").write_text(original, encoding="utf-8")
            anchor = self._anchor("sample.py", original, 1, 2)

            # Exact source semantics preserve indentation and every space between tokens.
            reindented = "def foo() :\n        return   1  \n"
            (workspace / "sample.py").write_text(reindented, encoding="utf-8")

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("edited", result["status"])

    def test_when_lines_shift_the_anchor_reports_new_start_and_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            original = "def foo():\n    return 1\n"
            (workspace / "sample.py").write_text(original, encoding="utf-8")
            anchor = self._anchor("sample.py", original, 1, 2)

            shifted = "# a leading comment\n# another one\n" + original
            (workspace / "sample.py").write_text(shifted, encoding="utf-8")

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("unchanged", result["status"])
            self.assertEqual(3, result["start"])
            self.assertEqual(4, result["end"])
            self.assertTrue(result["relocated"])

    def test_when_the_anchored_text_is_edited_the_anchor_is_edited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            original = "def foo():\n    return 1\n"
            (workspace / "sample.py").write_text(original, encoding="utf-8")
            anchor = self._anchor("sample.py", original, 1, 2)

            (workspace / "sample.py").write_text("def foo():\n    return 2\n", encoding="utf-8")

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("edited", result["status"])

    def test_when_the_file_is_gone_the_anchor_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            anchor = self._anchor("sample.py", "def foo():\n    return 1\n", 1, 2)

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("missing", result["status"])

    def test_when_the_anchored_duplicate_is_edited_a_non_unique_anchor_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            duplicated = "    if s == 1:\n        return 2"
            content = f"def a(s):\n{duplicated}\n    return s\n\ndef b(s):\n{duplicated}\n    return s\n"
            (workspace / "m.py").write_text(content, encoding="utf-8")
            anchor = self._anchor("m.py", duplicated, 7, 8, unique=False, source_text=content)

            unchanged = anchors_mod.check_anchor(workspace, anchor)
            self.assertEqual("unchanged", unchanged["status"])
            self.assertFalse(unchanged["relocated"])

            edited = content.replace(
                f"def b(s):\n{duplicated}",
                "def b(s):\n    if s == 1:\n        return 99",
            )
            (workspace / "m.py").write_text(edited, encoding="utf-8")

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("edited", result["status"])
            self.assertEqual("ambiguous", result.get("reason"))

    def test_when_a_duplicate_shifts_into_the_deleted_occurrences_coordinates_it_is_ambiguous(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            content = "def a():\n    return 1\ndef b():\n    return 1\n"
            (workspace / "m.py").write_text(content, encoding="utf-8")
            anchor = self._anchor("m.py", "    return 1", 2, 2, unique=False, source_text=content)

            unchanged = anchors_mod.check_anchor(workspace, anchor)
            self.assertEqual("unchanged", unchanged["status"])

            (workspace / "m.py").write_text("def b():\n    return 1\n", encoding="utf-8")
            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("edited", result["status"])
            self.assertEqual("ambiguous", result.get("reason"))

    def test_literal_whitespace_and_multiline_blank_lines_are_exact(self) -> None:
        cases = (
            ('return value == "a  b"\n', 'return value == "a b"\n', 1, 1),
            ('return value == "a\tb"\n', 'return value == "a b"\n', 1, 1),
            ('value = """first\n\nsecond"""\n', 'value = """first\nsecond"""\n', 1, 3),
        )
        for original, changed, start, end in cases:
            with self.subTest(original=original), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                (workspace / "sample.py").write_text(original, encoding="utf-8")
                snippet = anchors_mod.extract_snippet(workspace / "sample.py", start, end)
                anchor = self._anchor("sample.py", snippet, start, end)

                (workspace / "sample.py").write_text(changed, encoding="utf-8")
                result = anchors_mod.check_anchor(workspace, anchor)

                self.assertEqual("edited", result["status"])

    def test_when_the_snippet_is_unique_at_add_time_a_single_remaining_match_still_relocates(self) -> None:
        """The `unique`-at-add-time gate must not block an ordinary, unambiguous relocation:
        exactly one current occurrence plus `unique: True` still resolves `unchanged`."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            original = "def foo():\n    return 1\n"
            (workspace / "sample.py").write_text(original, encoding="utf-8")
            anchor = self._anchor("sample.py", original, 1, 2, unique=True)

            shifted = "# a leading comment\n" + original
            (workspace / "sample.py").write_text(shifted, encoding="utf-8")

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("unchanged", result["status"])
            self.assertEqual(2, result["start"])
            self.assertEqual(3, result["end"])
            self.assertTrue(result["relocated"])


class TestCheckAnchorUnreadablePath(unittest.TestCase):
    """WHEN an anchored path is now a directory, or its content is no longer valid UTF-8 text
    (Q4.1): `check_anchor` must report `edited`/`reason: "unreadable"`, never let a raw
    `IsADirectoryError`/`UnicodeDecodeError` crash `anchors check`/`catalog stale`/`status`/the
    audit anchors stage."""

    def _anchor(self, path: str, text: str, start: int, end: int) -> dict[str, Any]:
        return {
            "id": "A1",
            "path": path,
            "start": start,
            "end": end,
            "snippet": anchors_mod.normalize_snippet(text),
            "unique": True,
        }

    def test_when_the_anchored_path_is_now_a_directory_the_anchor_is_edited_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            anchor = self._anchor("sample.py", "def foo():\n    return 1\n", 1, 2)
            (workspace / "sample.py").mkdir()

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("edited", result["status"])
            self.assertEqual("unreadable", result.get("reason"))

    def test_when_the_anchored_file_is_no_longer_utf8_the_anchor_is_edited_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            anchor = self._anchor("sample.py", "def foo():\n    return 1\n", 1, 2)
            (workspace / "sample.py").write_bytes(b"caf\xe9 = 1\n")

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("edited", result["status"])
            self.assertEqual("unreadable", result.get("reason"))

    def test_extract_snippet_on_a_directory_raises_value_error_not_is_a_directory_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adir"
            path.mkdir()

            with self.assertRaises(ValueError):
                anchors_mod.extract_snippet(path, 1, 1)

    def test_trim_to_nonblank_on_a_non_utf8_file_raises_value_error_not_unicode_decode_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bin.py"
            path.write_bytes(b"caf\xe9 = 1\n")

            with self.assertRaises(ValueError):
                anchors_mod.trim_to_nonblank(path, 1, 1)

    def test_count_occurrences_on_a_directory_raises_value_error_not_is_a_directory_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adir"
            path.mkdir()

            with self.assertRaises(ValueError):
                anchors_mod.count_occurrences(path, "x")


class TestAnchorsCheckStaleStatusAuditSurviveAnUnreadablePath(unittest.TestCase):
    """WHEN an anchored path is now a directory (Q4.1, CLI-level): `anchors check`, `catalog
    stale`, `status`, and `,formal audit`'s anchors stage must all still exit cleanly (no raw
    traceback on stderr), reporting the anchor as not `unchanged` rather than crashing."""

    def test_anchors_check_on_a_directory_anchor_exits_1_with_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("x = 1\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:1-1", "--id", "A1", check=True)
            (workspace / "m.py").unlink()
            (workspace / "m.py").mkdir()

            result = run_formal(workspace, formal_home, "anchors", "check", "u", "--json")

            self.assertEqual(1, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("edited", payload["anchors"][0]["status"])
            self.assertEqual("unreadable", payload["anchors"][0].get("reason"))

    def test_status_on_a_directory_anchor_exits_0_with_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("x = 1\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:1-1", "--id", "A1", check=True)
            (workspace / "m.py").unlink()
            (workspace / "m.py").mkdir()

            result = run_formal(workspace, formal_home, "status", "--json")

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("stale", payload["units"][0]["anchor_state"])


class TestAnchorsAddTrimsBlankLines(unittest.TestCase):
    """WHEN `,formal anchors add` is given a range with a leading/trailing blank line (A3): the
    recorded start/end trims down to the first/last non-blank line in the requested range, and a
    range that is entirely blank lines is rejected (exit 2) rather than recorded as an empty
    anchor."""

    def test_add_records_exact_internal_whitespace_and_complete_source_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            source = 'first = "a  b"\n\nsecond = "c\td"\n'
            init_git_repo(workspace)
            (workspace / "m.py").write_text(source, encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:1-3", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertEqual('first = "a  b"\n\nsecond = "c\td"', payload["snippet"])
            self.assertEqual(hashlib.sha256(source.encode("utf-8")).hexdigest(), payload["source_sha"])

    def test_add_records_a_non_unique_origin_that_resolves_unchanged_before_any_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            source = "def a():\n    return 1\ndef b():\n    return 1\n"
            init_git_repo(workspace)
            (workspace / "m.py").write_text(source, encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            added = run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:2-2", "--json", check=True)
            checked = run_formal(workspace, formal_home, "anchors", "check", "u", "--json", check=True)

            self.assertFalse(json.loads(added.stdout)["unique"])
            resolved = json.loads(checked.stdout)["anchors"][0]
            self.assertEqual("unchanged", resolved["status"])
            self.assertFalse(resolved["relocated"])

    def test_a_leading_blank_line_in_the_requested_range_is_trimmed_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("def a():\n\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:2-3", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertEqual(3, payload["start"])
            self.assertEqual(3, payload["end"])

    def test_a_trailing_blank_line_in_the_requested_range_is_trimmed_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("a = 1\nb = 2\n\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:1-3", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertEqual(1, payload["start"])
            self.assertEqual(2, payload["end"])

    def test_an_entirely_blank_range_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("x = 1\n\n\ny = 2\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:2-3")

            self.assertEqual(2, result.returncode)
            self.assertIn("blank", result.stderr)


class TestAnchorsReAnchorAndWrite(unittest.TestCase):
    """WHEN anchors add re-anchors an existing id, and anchors check --write persists relocation."""

    def test_when_adding_an_anchor_with_an_existing_id_it_replaces_that_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "u1.py").write_text("def a():\n    return 1\n\n\ndef b():\n    return 2\n", encoding="utf-8")
            commit_all(workspace, "add u1.py")
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u1", "u1.py:1-2", "--id", "A1", check=True)

            result = run_formal(
                workspace, formal_home, "anchors", "add", "u1", "u1.py:4-5", "--id", "A1", "--json", check=True
            )

            payload = json.loads(result.stdout)
            # `u1.py` line 4 is blank (the two blank lines separating `a`/`b`); A1's
            # `trim_to_nonblank` (see `TestAnchorsAddTrimsBlankLines`) trims a re-anchor's
            # requested range exactly like a fresh one, so the recorded start is 5, not the
            # requested 4 -- this test previously asserted the untrimmed 4 (the pre-A1 behavior).
            self.assertEqual(5, payload["start"])
            list_result = run_formal(workspace, formal_home, "anchors", "list", "u1", "--json", check=True)
            anchors = json.loads(list_result.stdout)["anchors"]
            self.assertEqual(1, len(anchors))
            self.assertEqual(5, anchors[0]["start"])

    def test_when_check_write_is_passed_relocated_start_and_end_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "u1.py").write_text("def u1():\n    return 1\n", encoding="utf-8")
            commit_all(workspace, "add u1.py")
            run_formal(workspace, formal_home, "init", "u1", "--design", check=True)
            run_formal(workspace, formal_home, "anchors", "add", "u1", "u1.py:1-2", "--id", "A1", check=True)

            (workspace / "u1.py").write_text(
                "# a leading comment\n# another one\ndef u1():\n    return 1\n", encoding="utf-8"
            )

            check_result = run_formal(workspace, formal_home, "anchors", "check", "u1", "--write", "--json")
            self.assertEqual(0, check_result.returncode, check_result.stderr)

            list_result = run_formal(workspace, formal_home, "anchors", "list", "u1", "--json", check=True)
            anchors = json.loads(list_result.stdout)["anchors"]
            self.assertEqual(3, anchors[0]["start"])
            self.assertEqual(4, anchors[0]["end"])


class TestAnchorsPathNormalization(unittest.TestCase):
    """WHEN an anchor is recorded with a `./`-prefixed path (F2)."""

    def test_when_a_dot_slash_path_is_added_it_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("x = 1\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "./m.py:1-1", "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertEqual("m.py", payload["path"])


class TestAnchorsAddRejectsBadInput(unittest.TestCase):
    """WHEN `,formal anchors add` is given an out-of-range line range, a malformed
    `path:start-end` location, or a nonexistent target file: each is rejected with exit 2 and
    ANCHORS.json is left untouched (test-integrity group: "anchors add rejects bad input exit 2")."""

    def _init(self, workspace: Path, formal_home: Path) -> Path:
        init_git_repo(workspace)
        (workspace / "m.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
        commit_all(workspace, "add m.py")
        run_formal(workspace, formal_home, "init", "u", "--design", check=True)
        with mock.patch.dict(os.environ, {"AGENT_FORMAL_HOME": str(formal_home)}):
            layout = paths_mod.Layout(paths_mod.workspace_root(str(workspace)))
        return layout.work_dir("u")

    def test_an_out_of_range_line_range_is_rejected_with_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            unit_dir = self._init(workspace, formal_home)

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:1-99")

            self.assertEqual(2, result.returncode)
            self.assertFalse((unit_dir / manifest_mod.ANCHORS_NAME).exists())

    def test_a_malformed_location_is_rejected_with_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            unit_dir = self._init(workspace, formal_home)

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "bogus")

            self.assertEqual(2, result.returncode)
            self.assertIn("Invalid anchor location", result.stderr)
            self.assertFalse((unit_dir / manifest_mod.ANCHORS_NAME).exists())

    def test_a_nonexistent_target_file_is_rejected_with_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            unit_dir = self._init(workspace, formal_home)

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "nope.py:1-1")

            self.assertEqual(2, result.returncode)
            self.assertIn("Anchor target not found", result.stderr)
            self.assertFalse((unit_dir / manifest_mod.ANCHORS_NAME).exists())


class TestCheckAnchorEmptyOrZeroMatchSnippet(unittest.TestCase):
    """WHEN an anchor's recorded snippet is empty, or its exact text has zero occurrences in
    the current file: both resolve `edited`, and only the zero-match case can ever set `reason`
    -- an empty snippet is rejected before any search happens, so it never carries a `reason`
    key either (test-integrity group: "empty/zero-match anchor -> edited")."""

    def test_an_empty_snippet_resolves_edited_with_no_reason_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "sample.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
            anchor = {"id": "A1", "path": "sample.py", "start": 1, "end": 2, "snippet": "", "unique": True}

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("edited", result["status"])
            self.assertNotIn("reason", result)

    def test_a_snippet_with_zero_occurrences_resolves_edited_with_no_reason_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "sample.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
            anchor = {
                "id": "A1",
                "path": "sample.py",
                "start": 1,
                "end": 2,
                "snippet": anchors_mod.normalize_snippet("this text never appears anywhere"),
                "unique": True,
            }

            result = anchors_mod.check_anchor(workspace, anchor)

            self.assertEqual("edited", result["status"])
            self.assertNotIn("reason", result)


class TestAnchorsFormFeedIsNotALineBreak(unittest.TestCase):
    """WHEN a file contains a form-feed (`\\x0c`) mid-line (P4.1): `str.splitlines()` treats it
    as its own line break, shifting every anchor line number after it; `anchors.py`'s
    `_split_lines` must split on `"\\n"` only, so a `\\x0c` inside a line never counts as a
    second line."""

    def test_a_form_feed_within_a_line_does_not_shift_line_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            # `str.splitlines()` would read this as 3 lines ("a", "b", "c"); the real file has 2
            # physical lines ("a\x0cb" and "c").
            path.write_text("a\x0cb\nc\n", encoding="utf-8")

            self.assertEqual("a\x0cb", anchors_mod.extract_snippet(path, 1, 1))
            self.assertEqual("c", anchors_mod.extract_snippet(path, 2, 2))
            with self.assertRaises(ValueError):
                anchors_mod.extract_snippet(path, 3, 3)

    def test_normalize_lines_keeps_a_form_feed_line_as_line_one_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text("a\x0cb\nc\n", encoding="utf-8")

            result = anchors_mod.normalize_lines(path.read_text(encoding="utf-8"))

            self.assertEqual([lineno for lineno, _ in result], [1, 2])


class TestAnchorsAddWorkspacePathContainment(unittest.TestCase):
    """WHEN `,formal anchors add` is given an absolute path, or a relative path containing
    `..` (P4.2): an absolute path inside the workspace is stored repo-relative, and any path
    that resolves outside the workspace is rejected with exit 2."""

    def test_an_absolute_path_inside_the_workspace_is_stored_repo_relative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("x = 1\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            absolute_location = f"{(workspace / 'm.py').resolve()}:1-1"

            result = run_formal(workspace, formal_home, "anchors", "add", "u", absolute_location, "--json", check=True)

            payload = json.loads(result.stdout)
            self.assertEqual("m.py", payload["path"])

    def test_an_absolute_path_outside_the_workspace_is_rejected_with_exit_2(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            tempfile.TemporaryDirectory() as home_tmp,
            tempfile.TemporaryDirectory() as outside_tmp,
        ):
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)
            outside_file = Path(outside_tmp) / "secret.py"
            outside_file.write_text("x = 1\n", encoding="utf-8")

            result = run_formal(workspace, formal_home, "anchors", "add", "u", f"{outside_file}:1-1")

            self.assertEqual(2, result.returncode)
            self.assertIn("outside the workspace", result.stderr)

    def test_a_relative_dot_dot_path_escaping_the_workspace_is_rejected_with_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp) / "repo"
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace.parent / "outside.py").write_text("x = 1\n", encoding="utf-8")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            result = run_formal(workspace, formal_home, "anchors", "add", "u", "../outside.py:1-1")

            self.assertEqual(2, result.returncode)
            self.assertIn("outside the workspace", result.stderr)


class TestAnchorsCheckOnUninitializedUnitExitsTwo(unittest.TestCase):
    """WHEN `anchors check` names a unit that was never initialized (gap test, mutant 132):
    exit 2, with stderr naming `,formal init` as the fix."""

    def test_anchors_check_on_a_nonexistent_unit_exits_2_naming_formal_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)

            result = run_formal(workspace, formal_home, "anchors", "check", "nope")

            self.assertEqual(2, result.returncode)
            self.assertIn("Run `,formal init` first", result.stderr)


class TestAnchorIdAllocation(unittest.TestCase):
    """WHEN `anchors add` is called twice without `--id`: ids are allocated sequentially
    (A1, A2, ...) (test-integrity group "anchor id allocation")."""

    def test_two_adds_without_an_explicit_id_allocate_a1_then_a2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            workspace = Path(tmp)
            formal_home = Path(home_tmp)
            init_git_repo(workspace)
            (workspace / "m.py").write_text("a = 1\nb = 2\nc = 3\nd = 4\n", encoding="utf-8")
            commit_all(workspace, "add m.py")
            run_formal(workspace, formal_home, "init", "u", "--design", check=True)

            first = run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:1-1", "--json", check=True)
            second = run_formal(workspace, formal_home, "anchors", "add", "u", "m.py:2-2", "--json", check=True)

            self.assertEqual("A1", json.loads(first.stdout)["id"])
            self.assertEqual("A2", json.loads(second.stdout)["id"])


if __name__ == "__main__":
    unittest.main()
