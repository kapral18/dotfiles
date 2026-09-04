#!/usr/bin/env python3
"""Verify presentation assembly against independent byte-preserving edits."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _test_support import REPO

SKILL = REPO / "home/exact_dot_agents/exact_skills/exact_k-present-pr"
HELPER = SKILL / "exact_scripts/readonly_template.py"
TEMPLATE = SKILL / "exact_references/readonly_template.html"


class TestPresentationTemplate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.draft = self.directory / "draft.html"
        self.output = self.directory / "presentation.html"

    def run_helper(self, *args):
        return subprocess.run(
            [sys.executable, str(HELPER), *map(str, args)],
            capture_output=True,
            check=False,
        )

    def prepare(self):
        result = self.run_helper("prepare", TEMPLATE, self.draft)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_round_trip_is_byte_identical(self):
        self.prepare()
        result = self.run_helper("render", TEMPLATE, self.draft, self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), TEMPLATE.read_bytes())
        self.assertNotIn(b"<style>", self.draft.read_bytes())
        self.assertNotIn(b"<script>", self.draft.read_bytes())

    def test_content_edits_match_direct_template_edits(self):
        self.prepare()
        draft = self.draft.read_bytes()
        template = TEMPLATE.read_bytes()
        # Independent changes exercise arbitrary text, Unicode and new blocks.
        for before, after in (
            (b"</title>", " — example</title>".encode()),
            (b"</body>", b'<section id="extra">&lt;real diff&gt;</section></body>'),
            (
                b"</body>",
                b"<pre><code>b&quot;&lt;!-- K_PRESENT_PR_FIXED_STYLE --&gt;&quot;</code></pre></body>",
            ),
        ):
            self.assertEqual(draft.count(before), 1)
            self.assertEqual(template.count(before), 1)
            draft = draft.replace(before, after)
            template = template.replace(before, after)
        self.draft.write_bytes(draft)
        result = self.run_helper("render", TEMPLATE, self.draft, self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), template)

    def test_invalid_markers_leave_existing_output_untouched(self):
        self.prepare()
        draft = self.draft.read_bytes()
        cases = {
            "unknown": draft + b"<!-- K_PRESENT_PR_FIXED_OTHER -->",
            "unknown-with-whitespace": draft + b"<!--\n K_PRESENT_PR_FIXED_OTHER -->",
            "extra-damaged": draft + b"<!-- K_PRESENT_PR_FIXED_STYLE --!>",
        }
        for tag in (b"STYLE", b"SCRIPT"):
            marker = b"<!-- K_PRESENT_PR_FIXED_" + tag + b" -->"
            self.assertIn(marker, draft)
            cases.update(
                {
                    (tag, "missing"): draft.replace(marker, b""),
                    (tag, "duplicate"): draft + marker,
                    (tag, "damaged"): draft.replace(marker, marker.replace(b"-->", b"--!>")),
                }
            )
        for name, content in cases.items():
            with self.subTest(name=name):
                self.output.write_bytes(b"existing presentation")
                self.draft.write_bytes(content)
                result = self.run_helper("render", TEMPLATE, self.draft, self.output)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.output.read_bytes(), b"existing presentation")

    def test_invalid_template_and_input_alias_do_not_overwrite(self):
        template = self.directory / "template.html"
        valid = b"<html><style>body{}</style><script>x</script></html>"
        for block in (b"<style>body{}</style>", b"<script>x</script>"):
            for count in (0, 2):
                with self.subTest(block=block, count=count):
                    template.write_bytes(valid.replace(block, block * count))
                    result = self.run_helper("prepare", template, self.draft)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(b"template must contain exactly one", result.stderr)
                    self.assertFalse(self.draft.exists())
        # A valid template ensures alias rejection, not parsing failure, protects it.
        original = valid
        template.write_bytes(original)
        alias = self.directory / "alias.html"
        alias.symlink_to(template)
        result = self.run_helper("prepare", template, alias)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(template.read_bytes(), original)
        alias.unlink()
        os.link(template, alias)
        result = self.run_helper("prepare", template, alias)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(template.read_bytes(), original)

    def test_when_template_contains_reserved_marker_should_reject_without_writing(self):
        template = self.directory / "template.html"
        for tag in (b"STYLE", b"SCRIPT"):
            with self.subTest(tag=tag):
                template.write_bytes(b"<style>body{}</style><script>x</script><!-- K_PRESENT_PR_FIXED_" + tag + b" -->")
                self.draft.write_bytes(b"existing draft")
                result = self.run_helper("prepare", template, self.draft)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"reserved editing marker", result.stderr)
                self.assertEqual(self.draft.read_bytes(), b"existing draft")

    def test_when_tags_have_mixed_case_should_preserve_original_bytes(self):
        template = self.directory / "template.html"
        original = b'<STYLE media="all">body{}</STYLE><ScRiPt>\nx\n</sCrIpT>'
        template.write_bytes(original)
        result = self.run_helper("prepare", template, self.draft)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b"body{}", self.draft.read_bytes())
        self.assertNotIn(b"\nx\n", self.draft.read_bytes())
        result = self.run_helper("render", template, self.draft, self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), original)

    def test_when_render_output_aliases_input_should_reject_without_writing(self):
        template = self.directory / "template.html"
        template.write_bytes(b"<style>body{}</style><script>x</script>")
        result = self.run_helper("prepare", template, self.draft)
        self.assertEqual(result.returncode, 0, result.stderr)
        for source in (template, self.draft):
            for kind in ("same-path", "symlink", "hardlink"):
                with self.subTest(source=source.name, kind=kind):
                    original = source.read_bytes()
                    alias = self.directory / "alias.html"
                    if kind == "same-path":
                        destination = source
                    else:
                        destination = alias
                        if kind == "symlink":
                            alias.symlink_to(source)
                        else:
                            os.link(source, alias)
                    result = self.run_helper("render", template, self.draft, destination)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(b"output must be separate from its inputs", result.stderr)
                    self.assertEqual(source.read_bytes(), original)
                    if kind != "same-path":
                        alias.unlink()

    def test_when_missing_input_aliases_output_should_report_input_output_conflict(self):
        missing = self.directory / "missing.html"
        alias = self.directory / "alias.html"
        alias.symlink_to(missing)
        for destination in (missing, alias):
            with self.subTest(destination=destination.name):
                result = self.run_helper("prepare", missing, destination)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"output must be separate from its inputs", result.stderr)
                self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
