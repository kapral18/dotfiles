#!/usr/bin/env python3
"""Behavior tests for ,codeowners --owner-of."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[2] / "home/exact_lib/exact_,codeowners/main.sh"


class CodeownersOwnerOfTests(unittest.TestCase):
    """WHEN looking up the owner of a path."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".github").mkdir()
        (self.repo / ".github/CODEOWNERS").write_text("* @everyone\n**/logs @team-logs\nsrc/*.ts @team-ts\n")

    def owner(self, path: str) -> str:
        out = subprocess.run(
            ["bash", str(MAIN), "--owner-of", path], cwd=self.repo, text=True, capture_output=True
        ).stdout
        return out.split()[-1]

    def test_glob_directory_pattern_owns_files_beneath_it(self) -> None:
        self.assertEqual(self.owner("a/logs/x.txt"), "@team-logs")

    def test_glob_file_pattern_stays_a_file_match(self) -> None:
        self.assertEqual(self.owner("src/a.ts"), "@team-ts")
        self.assertEqual(self.owner("src/a.ts/inner"), "@everyone")


if __name__ == "__main__":
    unittest.main()
