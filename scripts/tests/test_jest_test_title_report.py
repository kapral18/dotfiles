from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

REPORTER = Path(__file__).resolve().parents[2] / "home/exact_lib/exact_,jest-test-title-report/main.mjs"


class TestJestTestTitleReport(unittest.TestCase):
    def test_WHEN_help_is_requested_SHOULD_exit_without_required_paths(self):
        for flag in ("-h", "--help"):
            with self.subTest(flag=flag):
                result = subprocess.run(["node", str(REPORTER), flag], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("USAGE:", result.stdout)

    def test_WHEN_a_required_path_is_missing_SHOULD_report_it_before_using_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "before").mkdir()
            (root / "after").mkdir()
            untouched = root / "true"
            untouched.write_text("keep\n")
            for argv, missing in (
                ([], "Missing --before"),
                (["--before", "before", "--after", "after", "--scope", ".", "--out"], "Missing --out"),
            ):
                with self.subTest(argv=argv):
                    result = subprocess.run(
                        ["node", str(REPORTER), *argv], cwd=root, capture_output=True, text=True, timeout=5
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn(missing, result.stderr)
                    self.assertEqual(untouched.read_text(), "keep\n")
