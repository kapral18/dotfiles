from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _test_support import REPO


@unittest.skipUnless(shutil.which("ghostty") and shutil.which("fish"), "requires Ghostty and fish")
class TestGhosttyNativeShell(unittest.TestCase):
    def test_WHEN_connecting_over_ssh_SHOULD_enable_native_setup_and_preserve_arguments(self):
        ghostty = Path(shutil.which("ghostty")).resolve()
        resources = Path(os.environ.get("GHOSTTY_RESOURCES_DIR", ghostty.parent.parent / "Resources/ghostty"))
        integration = resources / "shell-integration/fish/vendor_conf.d/ghostty-shell-integration.fish"
        self.assertTrue(integration.is_file(), f"missing Ghostty fish integration: {integration}")
        config = REPO / "home/dot_config/exact_ghostty/readonly_config"
        validated = subprocess.run(
            [str(ghostty), "+validate-config", f"--config-file={config}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        features = re.search(r"^shell-integration-features\s*=\s*(.+)$", config.read_text(), re.MULTILINE)
        self.assertIsNotNone(features)

        with tempfile.TemporaryDirectory() as tmp:
            arguments = Path(tmp) / "arguments"
            command = Path(tmp) / "ghostty"
            command.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$GHOSTTY_TEST_ARGS"\n')
            command.chmod(0o755)
            actual = subprocess.run(
                [
                    "fish",
                    "--no-config",
                    "--interactive",
                    "--command",
                    "function ssh; return 99; end; "
                    'source "$GHOSTTY_TEST_INTEGRATION"; '
                    "emit fish_prompt >/dev/null; "
                    "ssh -p 2222 user@example.invalid \"printf 'hello world'\"",
                ],
                env={
                    **os.environ,
                    "GHOSTTY_SHELL_FEATURES": features[1],
                    "GHOSTTY_BIN_DIR": tmp,
                    "GHOSTTY_TEST_ARGS": str(arguments),
                    "GHOSTTY_TEST_INTEGRATION": str(integration),
                    "XDG_CONFIG_HOME": tmp,
                    "XDG_DATA_HOME": tmp,
                    "TERM": "dumb",
                },
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(actual.returncode, 0, actual.stderr)
            self.assertEqual(
                arguments.read_text().splitlines(),
                ["+ssh", "--", "-p", "2222", "user@example.invalid", "printf 'hello world'"],
            )


if __name__ == "__main__":
    unittest.main()
