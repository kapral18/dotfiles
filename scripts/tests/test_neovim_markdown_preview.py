from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    from .test_neovim_config_schemas import NVIM
except ImportError:
    from test_neovim_config_schemas import NVIM

REPO = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).with_name("neovim_markdown_preview.lua")


@unittest.skipUnless(NVIM, "Neovim is not installed")
class MarkdownPreviewTests(unittest.TestCase):
    """WHEN the preview plugin has already been cloned."""

    def run_case(self, case: str) -> None:
        with tempfile.TemporaryDirectory(prefix="markdown-preview-") as scratch:
            result = subprocess.run(
                [NVIM, "--headless", "-u", "NONE", "-i", "NONE", "-l", str(HARNESS), case],
                env=os.environ | {"PREVIEW_TEST_ROOT": str(REPO), "PREVIEW_TEST_TMP": scratch},
                text=True,
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_SHOULD_repair_missing_assets_and_preserve_installed_assets(self) -> None:
        self.run_case("repair")

    def test_SHOULD_report_an_installer_failure(self) -> None:
        self.run_case("failure")

    def test_SHOULD_reject_a_successful_installer_without_a_binary(self) -> None:
        self.run_case("missing")

    def test_SHOULD_report_a_killed_installer_with_an_existing_binary(self) -> None:
        self.run_case("signal")

    def test_SHOULD_reject_a_failed_update_that_leaves_the_old_binary(self) -> None:
        self.run_case("stale")


if __name__ == "__main__":
    unittest.main()
