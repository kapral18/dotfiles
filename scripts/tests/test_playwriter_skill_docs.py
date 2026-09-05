#!/usr/bin/env python3
"""Verify lossless documentation routing without installing Playwriter or running a browser."""

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "home/exact_dot_agents/exact_skills/exact_k-playwriter/exact_scripts/readonly_read_docs.py"
SPEC = importlib.util.spec_from_file_location("playwriter_skill_docs", SOURCE)
DOCS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOCS)

# Deliberately small independent document: code-block headings must remain prose,
# every real section belongs to exactly one required or conditional contract.
RAW = b"""## rules
Never close another user's browser.
```md
## this is code, not a section
```
## taking screenshots
Use CSS scale and absolute artifact paths.
## utility functions
**getLatestLogs** - read all startup logs on first call.
log recipe
**createDebugger** - fetch debugger API docs before using.
debug recipe
### Recording user actions for skill generation
Read the whole document, never truncate.
"""
CORE = {"rules", "utility functions", "getLatestLogs"}
GROUPS = {
    "screenshots": {"taking screenshots"},
    "debugger": {"createDebugger"},
    "recorder": {"Recording user actions for skill generation"},
}


class ReadDocsTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(DOCS, "AUDITED_SHA", hashlib.sha256(RAW).hexdigest()),
            patch.object(DOCS, "CORE", CORE.copy()),
            patch.object(DOCS, "GROUPS", GROUPS.copy()),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_partition_preserves_every_byte_and_ignores_fenced_heading(self):
        blocks = DOCS.sections(RAW)
        self.assertEqual(b"".join(x["raw"] for x in blocks), RAW)
        self.assertEqual(len(blocks), 6)
        self.assertIn(b"## this is code, not a section", blocks[0]["raw"])

    def test_core_keeps_guard_and_first_call_logs_without_conditional_recipes(self):
        output, receipt = DOCS.select(RAW, ["core"])
        self.assertIn(b"Never close another user's browser.", output)
        self.assertIn(b"read all startup logs on first call", output)
        self.assertNotIn(b"CSS scale", output)
        self.assertNotIn(b"debug recipe", output)
        self.assertFalse(receipt["requires_core"])

    def test_operation_is_complete_and_does_not_reload_core(self):
        output, receipt = DOCS.select(RAW, ["screenshots"])
        self.assertEqual(output, b"## taking screenshots\nUse CSS scale and absolute artifact paths.\n")
        self.assertTrue(receipt["requires_core"])

    def test_requested_core_and_operation_preserve_source_order(self):
        output, _ = DOCS.select(RAW, ["screenshots", "core"])
        self.assertLess(output.index(b"## rules"), output.index(b"## taking screenshots"))
        self.assertLess(output.index(b"## taking screenshots"), output.index(b"## utility functions"))
        self.assertNotIn(b"debug recipe", output)

    def test_recorder_always_reads_full_document(self):
        for requested in [["recorder"], ["core", "recorder"], ["full"]]:
            output, receipt = DOCS.select(RAW, requested)
            self.assertEqual(output, RAW)
            self.assertEqual(receipt["mode"], "full")

    def test_changed_document_never_uses_old_partition(self):
        changed = RAW.replace(b"Never close", b"Never ever close")
        output, receipt = DOCS.select(changed, ["screenshots"])
        self.assertEqual(output, changed)
        self.assertEqual(receipt["mode"], "full-unrecognized-document")

    def test_changed_or_unresolved_package_version_forces_full_document(self):
        for version in ["0.6.0", None, ""]:
            output, receipt = DOCS.select(RAW, ["screenshots"], version=version)
            self.assertEqual(output, RAW)
            self.assertEqual(receipt["mode"], "full-unrecognized-version")

    def test_truncated_document_is_returned_as_full_unknown_not_known_core(self):
        truncated = RAW[:-40]
        output, receipt = DOCS.select(truncated, ["core"])
        self.assertEqual(output, truncated)
        self.assertEqual(receipt["mode"], "full-unrecognized-document")

    def test_unclassified_new_heading_falls_back_even_if_hash_was_updated(self):
        changed = RAW + b"## new global guard\nNever leak secrets.\n"
        with patch.object(DOCS, "AUDITED_SHA", hashlib.sha256(changed).hexdigest()):
            output, receipt = DOCS.select(changed, ["core"])
        self.assertEqual(output, changed)
        self.assertEqual(receipt["mode"], "full-inventory-mismatch")

    def test_missing_mapped_section_falls_back(self):
        with patch.object(DOCS, "CORE", CORE | {"missing"}):
            output, receipt = DOCS.select(RAW, ["core"])
        self.assertEqual(output, RAW)
        self.assertEqual(receipt["mode"], "full-inventory-mismatch")

    def test_duplicate_heading_falls_back(self):
        changed = RAW + b"## rules\nA second guard.\n"
        with patch.object(DOCS, "AUDITED_SHA", hashlib.sha256(changed).hexdigest()):
            output, receipt = DOCS.select(changed, ["core"])
        self.assertEqual(output, changed)
        self.assertEqual(receipt["mode"], "full-inventory-mismatch")

    def test_unclassified_preamble_falls_back(self):
        changed = b"A new global instruction.\n" + RAW
        with patch.object(DOCS, "AUDITED_SHA", hashlib.sha256(changed).hexdigest()):
            output, receipt = DOCS.select(changed, ["core"])
        self.assertEqual(output, changed)
        self.assertEqual(receipt["mode"], "full-inventory-mismatch")

    def test_invalid_profile_is_rejected_before_calling_playwriter(self):
        with (
            patch.object(sys, "argv", ["read_docs.py", "invented"]),
            patch.object(DOCS.subprocess, "run") as run,
            patch.object(DOCS.shutil, "which", side_effect=AssertionError("Invalid profile reached CLI discovery")),
        ):
            with self.assertRaises(SystemExit) as exit_context:
                DOCS.main()
            self.assertEqual(exit_context.exception.code, 2)
            run.assert_not_called()

    def test_list_does_not_require_installed_binary(self):
        with (
            patch.object(sys, "argv", ["read_docs.py", "--list"]),
            patch.object(
                DOCS.shutil, "which", side_effect=AssertionError("Profile listing reached CLI discovery")
            ) as which,
        ):
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(DOCS.main(), 0)
            self.assertIn("screenshots", out.getvalue())
            which.assert_not_called()

    def test_missing_binary_is_not_success(self):
        with patch.object(sys, "argv", ["read_docs.py"]), patch.object(DOCS.shutil, "which", return_value=None):
            with self.assertRaises(SystemExit) as exit_context:
                DOCS.main()
            self.assertEqual(exit_context.exception.code, 1)

    def test_failed_cli_is_not_treated_as_documentation(self):
        result = subprocess.CompletedProcess(["playwriter", "skill"], 7, b"partial text", b"failed\n")
        stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        stdout = type("Stdout", (), {"buffer": io.BytesIO()})()
        with (
            patch.object(sys, "argv", ["read_docs.py"]),
            patch.object(DOCS.shutil, "which", return_value="/bin/playwriter"),
            patch.object(DOCS.subprocess, "run", return_value=result),
            patch.object(sys, "stderr", stderr),
            patch.object(sys, "stdout", stdout),
        ):
            self.assertEqual(DOCS.main(), 7)
            self.assertEqual(stderr.buffer.getvalue(), b"failed\n")
            self.assertEqual(stdout.buffer.getvalue(), b"")

    def test_when_cli_succeeds_should_preserve_document_and_verify_package_identity(self):
        core = (
            b"## rules\nNever close another user's browser.\n```md\n"
            b"## this is code, not a section\n```\n"
            b"## utility functions\n**getLatestLogs** - read all startup logs on first call.\nlog recipe\n"
        )
        cases = [
            ("known", {"name": "playwriter", "version": "0.5.0"}, RAW + b"\n", [], core),
            ("no-added-newline", {"name": "playwriter", "version": "0.5.0"}, RAW, [], core),
            ("full", {"name": "playwriter", "version": "0.5.0"}, RAW + b"\n", ["full"], RAW),
            ("changed-version", {"name": "playwriter", "version": "0.6.0"}, RAW + b"\n", [], RAW),
            ("wrong-package", {"name": "another-package", "version": "0.5.0"}, RAW + b"\n", [], RAW),
            ("missing-package", None, RAW + b"\n", [], RAW),
            ("missing-version", {"name": "playwriter"}, RAW + b"\n", [], RAW),
            ("unknown-text", {"name": "playwriter", "version": "0.5.0"}, b"New safety rule.", [], b"New safety rule."),
            (
                "unknown-newline",
                {"name": "playwriter", "version": "0.5.0"},
                b"New safety rule.\n",
                [],
                b"New safety rule.\n",
            ),
        ]
        for label, metadata, raw, groups, expected in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                binary = root / "package/bin/cli.js"
                binary.parent.mkdir(parents=True)
                binary.write_text("")
                linked = root / "playwriter"
                linked.symlink_to(binary)
                if metadata is not None:
                    (root / "package/package.json").write_text(json.dumps(metadata))
                result = subprocess.CompletedProcess([str(linked), "skill"], 0, raw, b"")
                stdout = type("Stdout", (), {"buffer": io.BytesIO()})()
                stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
                with (
                    patch.object(sys, "argv", ["read_docs.py", *groups]),
                    patch.object(DOCS.shutil, "which", return_value=str(linked)),
                    patch.object(DOCS.subprocess, "run", return_value=result) as run,
                    patch.object(sys, "stdout", stdout),
                    patch.object(sys, "stderr", stderr),
                ):
                    self.assertEqual(DOCS.main(), 0)
                self.assertEqual(stdout.buffer.getvalue(), expected)
                stderr.flush()
                self.assertEqual(json.loads(stderr.buffer.getvalue())["command"], [str(binary), "skill"])
                run.assert_called_once_with([str(linked), "skill"], capture_output=True, check=False)

    def test_when_bold_definition_is_outside_utilities_should_remain_section_content(self):
        changed = RAW.replace(
            b"## taking screenshots\n", b"**ordinary bold text** - not a utility.\n## taking screenshots\n"
        )
        with patch.object(DOCS, "AUDITED_SHA", hashlib.sha256(changed).hexdigest()):
            output, receipt = DOCS.select(changed, ["core"])
        self.assertIn(b"**ordinary bold text** - not a utility.\n", output)
        self.assertNotIn(b"Use CSS scale", output)
        self.assertEqual(receipt["mode"], "selected-complete-sections")


# Fixed routing oracle from the fully audited Playwriter 0.5.0 manual, whose SHA is
# b4ecf1df8ae351719000212ce0b97858cfe0ec50ee51ed79d6a441123243e9ef.
# These fixtures must not be built from DOCS.CORE/GROUPS: a misplaced safety
# section must fail even when the production map remains internally consistent.
AUDITED_ROUTING = """core|CLI Usage
core|Session management
remote|Remote access (control browser from another machine)
direct|Direct CDP connection (no extension needed)
headless|Headless browser (no extension, no user browser)
cloud|Cloud browsers (stealth, proxies, CAPTCHA solving)
core|Execute code
core|Execute from file
recorder|Recording user actions for skill generation
stream|Live streaming to RTMP (X Live, Twitch, YouTube)
debug|Debugging playwriter issues
core|playwriter best practices
core|context variables
core|importing local scripts
core|rules
core|interaction feedback loop
core|common mistakes to avoid
core|accessibility snapshots
core|choosing between snapshot methods
core|selector best practices
core|working with pages
core|navigation
core|common patterns
core|utility functions
core|getLatestLogs
html|getCleanHTML
markdown|getPageMarkdown
core|waitForPageLoad
core|getCDPSession
locator|getLocatorStringForElement
react|getReactSource
react|getReactComponentInfo
pinned|inspectPinnedElement
styles|getStylesForLocator
debugger|createDebugger
editor|createEditor
screenshots|screenshotWithAccessibilityLabels
screenshots|resizeImageForAgent
video|recording.start / recording.stop
video|ghostCursor.show / ghostCursor.hide
video|createDemoVideo
pinned|pinned elements
screenshots|taking screenshots
evaluate|page.evaluate
files|loading files
network|network interception
input|computer use (low-level mouse/keyboard)
input|clicking
input|hover
input|scroll
input|drag
input|key hold / release / repeat
input|resize viewport
screenshots|region screenshot (zoom equivalent)
ghost|Ghost Browser integration"""


class ProductionRoutingTests(unittest.TestCase):
    def test_when_profile_is_selected_should_include_its_audited_complete_sections(self):
        rows = [line.split("|", 1) for line in AUDITED_ROUTING.splitlines()]
        sections = [(group, f"## {name}\nComplete section: {name}.\n".encode()) for group, name in rows]
        raw = b"".join(body for _, body in sections)
        profiles = dict.fromkeys(group for group, _ in rows)
        with patch.object(DOCS, "AUDITED_SHA", hashlib.sha256(raw).hexdigest()):
            for profile in profiles:
                with self.subTest(profile=profile):
                    output, _ = DOCS.select(raw, [profile])
                    expected = (
                        raw if profile == "recorder" else b"".join(body for group, body in sections if group == profile)
                    )
                    self.assertEqual(output, expected)


if __name__ == "__main__":
    unittest.main()
