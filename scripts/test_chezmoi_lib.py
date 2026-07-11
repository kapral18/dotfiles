#!/usr/bin/env python3
"""Tests for the managed-config interfaces in chezmoi_lib.sh."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
from _test_support import REPO, SCRIPTS

LIB = SCRIPTS / "chezmoi_lib.sh"


class TestChezmoiManagedConfigLedger(unittest.TestCase):
    """WHEN generated-config checksums are recorded or retired."""

    def _call(self, operation: str, state_home: Path, target: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update({"XDG_STATE_HOME": str(state_home), "LIB": str(LIB), "TARGET": target})
        return subprocess.run(
            ["bash", "-c", f'source "$LIB"; chezmoi_{operation}_checksum "$TARGET"'],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def _manifest(state_home: Path) -> Path:
        return state_home / "chezmoi/managed_configs.tsv"

    def test_SHOULD_record_literal_paths_once_without_collateral_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_home = root / "state"
            target = root / "config[old].json"
            similar = root / "configo.json"
            target.write_text("new")
            manifest = self._manifest(state_home)
            manifest.parent.mkdir(parents=True)
            similar_row = f"{similar}\tkeep\t2026-01-01T00:00:00Z"
            manifest.write_text(
                f"{target}\told-one\t2026-01-01T00:00:00Z\n{target}\told-two\t2026-01-02T00:00:00Z\n{similar_row}\n"
            )

            result = self._call("record", state_home, str(target))
            rows = manifest.read_text().splitlines()
            temporary_artifacts = list(manifest.parent.glob("managed_configs.tsv.*"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(row.startswith(f"{target}\t") for row in rows), 1)
        self.assertIn(similar_row, rows)
        self.assertEqual(temporary_artifacts, [])

    def test_SHOULD_not_rewrite_an_exact_current_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_home = root / "state"
            target = root / "config.json"
            target.write_text("current")
            checksum = hashlib.sha256(target.read_bytes()).hexdigest()
            manifest = self._manifest(state_home)
            manifest.parent.mkdir(parents=True)
            content = f"{target}\t{checksum}\t2026-01-01T00:00:00Z\n"
            manifest.write_text(content)
            before = manifest.stat()

            result = self._call("record", state_home, str(target))
            after = manifest.stat()
            remaining = manifest.read_text()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(remaining, content)
        self.assertEqual((after.st_ino, after.st_mtime_ns), (before.st_ino, before.st_mtime_ns))

    def test_SHOULD_forget_every_exact_duplicate_and_preserve_similar_rows(self):
        target = "/tmp/generated/config[old].json"
        similar = "/tmp/generated/configXoldY.json"
        with tempfile.TemporaryDirectory() as tmp:
            state_home = Path(tmp) / "state"
            manifest = self._manifest(state_home)
            manifest.parent.mkdir(parents=True)
            similar_row = f"{similar}\tkeep\t2026-01-01T00:00:00Z"
            manifest.write_text(
                f"{target}\tone\t2026-01-01T00:00:00Z\n{similar_row}\n{target}\ttwo\t2026-01-02T00:00:00Z\n"
            )

            result = self._call("forget", state_home, target)
            rows = manifest.read_text().splitlines()
            temporary_artifacts = list(manifest.parent.glob("managed_configs.tsv.*"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(row.startswith(f"{target}\t") for row in rows))
        self.assertEqual(rows, [similar_row])
        self.assertEqual(temporary_artifacts, [])

    def test_SHOULD_leave_missing_or_unmatched_manifest_state_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_home = Path(tmp) / "state"
            manifest = self._manifest(state_home)
            missing = self._call("forget", state_home, "/tmp/absent.json")
            self.assertEqual(missing.returncode, 0, missing.stderr)
            self.assertFalse(manifest.exists())

            manifest.parent.mkdir(parents=True)
            content = "/tmp/other.json\tkeep\t2026-01-01T00:00:00Z\n"
            manifest.write_text(content)
            before = manifest.stat()
            unmatched = self._call("forget", state_home, "/tmp/absent.json")
            after = manifest.stat()
            remaining = manifest.read_text()

        self.assertEqual(unmatched.returncode, 0, unmatched.stderr)
        self.assertEqual(remaining, content)
        self.assertEqual((after.st_ino, after.st_mtime_ns), (before.st_ino, before.st_mtime_ns))

    def test_SHOULD_reject_empty_targets_and_keep_missing_target_record_as_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_home = Path(tmp) / "state"
            for operation in ("record", "forget"):
                with self.subTest(operation=operation):
                    result = self._call(operation, state_home, "")
                    self.assertNotEqual(result.returncode, 0)

            missing_target = self._call("record", state_home, "/tmp/definitely-absent-managed-config")
            manifest_exists = self._manifest(state_home).exists()

        self.assertEqual(missing_target.returncode, 0, missing_target.stderr)
        self.assertFalse(manifest_exists)


if __name__ == "__main__":
    unittest.main()
