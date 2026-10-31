#!/usr/bin/env python3
"""Behavior tests for the Xcode install script with fake xcode-select and sudo."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "home/.chezmoiscripts/run_once_before_00-install-xcode.sh"


class InstallXcodeTests(unittest.TestCase):
    """WHEN the license step picks its developer directory."""

    def run_script(self, root: Path, developer: Path | None) -> tuple[subprocess.CompletedProcess[str], Path]:
        bin_dir = root / "bin"
        bin_dir.mkdir()
        log = root / "sudo.log"
        for name, body in (
            ("xcode-select", f'echo "{developer}"' if developer else '[ "$1" = --install ] || exit 2'),
            ("sudo", f'echo "$*" > "{log}"'),
        ):
            (bin_dir / name).write_text(f"#!/bin/sh\n{body}\n")
            (bin_dir / name).chmod(0o755)

        # The script's fixed /Applications path, moved under the temp root.
        script = root / "install-xcode.sh"
        script.write_text(SCRIPT.read_text().replace("/Applications/", f"{root}/Applications/"))
        result = subprocess.run(
            ["bash", str(script)],
            env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
            text=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
        )
        return result, log

    def test_license_is_accepted_against_the_selected_xcode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            developer = root / "Xcode.app/Contents/Developer"
            developer.mkdir(parents=True)
            (developer.parent / "MacOS").mkdir()
            result, log = self.run_script(root, developer)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text().strip(), f"DEVELOPER_DIR={developer} xcodebuild -license accept")

    def test_command_line_tools_fall_back_to_installed_xcode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CommandLineTools").mkdir()
            xcode = root / "Applications/Xcode.app/Contents/Developer"
            xcode.mkdir(parents=True)
            (xcode.parent / "MacOS").mkdir()
            result, log = self.run_script(root, root / "CommandLineTools")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text().strip(), f"DEVELOPER_DIR={xcode} xcodebuild -license accept")

    def test_command_line_tools_alone_skip_the_license(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CommandLineTools").mkdir()
            result, log = self.run_script(root, root / "CommandLineTools")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(log.exists())

    def test_missing_command_line_tools_stop_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result, log = self.run_script(Path(tmp), None)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Command Line Tools are still missing", result.stderr)
            self.assertFalse(log.exists())


if __name__ == "__main__":
    unittest.main()
