#!/usr/bin/env python3
"""Behavior of the `,tg` launcher: pass-backed app key written into tele's config."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _test_support import REPO

LAUNCHER = REPO / "home" / "exact_bin" / "executable_,tg"

# Mirrors the head of tele's defaultConfig (cmd/tele/main.go): written by
# ensureConfig at the -config path before -theme-check exits.
TELE_DEFAULT_CONFIG = """telegram:
  api_id: 0
  api_hash: ""

ui:
  history_limit: 50
  # theme:
  #   dark: my-dark
"""

FAKE_TELE = f"""#!{sys.executable}
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["TG_TEST_CALLS"], "a") as calls:
    calls.write(json.dumps(args) + "\\n")
if "-theme-check" in args:
    path = Path(args[args.index("-config") + 1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text({TELE_DEFAULT_CONFIG!r})
"""

FAKE_PASS = """#!/bin/sh
file="$TG_TEST_PASS_DIR/$(basename "$2")"
[ -f "$file" ] || exit 1
cat "$file"
"""


@unittest.skipUnless(shutil.which("yq"), "yq is required by ,tg")
class TestTgLauncher(unittest.TestCase):
    """WHEN launching tele through ,tg."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        bindir = self.home / "bin"
        bindir.mkdir()
        for name, body in (("tele", FAKE_TELE), ("pass", FAKE_PASS)):
            (bindir / name).write_text(body)
            (bindir / name).chmod(0o755)
        self.pass_dir = self.home / "pass"
        self.pass_dir.mkdir()
        self.calls = self.home / "calls"
        self.default_config = self.home / ".config" / "tele" / "config.yml"
        yq_dir = str(Path(shutil.which("yq")).parent)
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{bindir}:{yq_dir}:/usr/bin:/bin",
            "TG_TEST_CALLS": str(self.calls),
            "TG_TEST_PASS_DIR": str(self.pass_dir),
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _set_pass(self, app_id: str, api_hash: str) -> None:
        (self.pass_dir / "app_id").write_text(app_id + "\n")
        (self.pass_dir / "api_hash").write_text(api_hash + "\n")

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["bash", str(LAUNCHER), *args], env=self.env, capture_output=True, text=True, check=False)

    def _tele_calls(self) -> list[list[str]]:
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def _key(self, config: Path) -> tuple[str, str]:
        def query(expr: str) -> str:
            return subprocess.run(["yq", expr, str(config)], capture_output=True, text=True, check=True).stdout.strip()

        return query(".telegram.api_id | tag") + "=" + query(".telegram.api_id"), query(".telegram.api_hash")

    def test_SHOULD_bootstrap_missing_default_config_then_write_key_and_forward_args(self) -> None:
        self._set_pass("12345", "h'a\"$sh")

        result = self._run("-e")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._key(self.default_config), ("!!int=12345", "h'a\"$sh"))
        self.assertIn("history_limit: 50", self.default_config.read_text())
        self.assertEqual(self.default_config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            self._tele_calls(),
            [["-config", str(self.default_config), "-theme-check"], ["-e"]],
        )

    def test_SHOULD_write_key_into_the_config_tele_will_read(self) -> None:
        self._set_pass("777", "hash")
        cases = {
            "single-dash equals": (["-config=CUSTOM"], "custom.yml"),
            "double-dash separate": (["-e", "--config", "CUSTOM"], "custom.yml"),
            "tilde path": (["-config", "~/tilde/config.yml"], "tilde/config.yml"),
            "flag after terminator": (["--", "-config", "CUSTOM"], ".config/tele/config.yml"),
            "flag after positional": (["chat", "-config", "CUSTOM"], ".config/tele/config.yml"),
        }
        for label, (args, expected_rel) in cases.items():
            with self.subTest(label):
                for path in (self.home / "custom.yml", self.home / "tilde", self.default_config.parent):
                    if path.is_dir():
                        shutil.rmtree(path)
                    elif path.exists():
                        path.unlink()
                resolved = [a.replace("CUSTOM", str(self.home / "custom.yml")) for a in args]

                result = self._run(*resolved)

                self.assertEqual(result.returncode, 0, result.stderr)
                written = [
                    p
                    for p in (self.home / "custom.yml", self.home / "tilde/config.yml", self.default_config)
                    if p.exists()
                ]
                self.assertEqual(written, [self.home / expected_rel])
                self.assertEqual(self._key(written[0]), ("!!int=777", "hash"))

    def test_SHOULD_keep_user_settings_and_skip_rewrite_when_key_is_current(self) -> None:
        self.default_config.parent.mkdir(parents=True)
        self.default_config.write_text("telegram:\n  api_id: 1\n  api_hash: old\nui:\n  history_limit: 77 # mine\n")
        self._set_pass("2", "new")

        self.assertEqual(self._run().returncode, 0)
        after_first = self.default_config.read_text()
        mtime = self.default_config.stat().st_mtime_ns
        self.assertEqual(self._run().returncode, 0)

        self.assertEqual(self._key(self.default_config), ("!!int=2", "new"))
        self.assertIn("history_limit: 77 # mine", after_first)
        self.assertEqual(self.default_config.stat().st_mtime_ns, mtime)

    def test_SHOULD_fail_without_running_tele_when_app_id_is_not_a_number(self) -> None:
        self._set_pass("12ab", "hash")

        result = self._run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is not a number", result.stderr)
        self.assertEqual(self._tele_calls(), [])
        self.assertFalse(self.default_config.exists())

    def test_SHOULD_run_tele_untouched_when_pass_has_no_key(self) -> None:
        result = self._run("--version")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._tele_calls(), [["--version"]])
        self.assertFalse(self.default_config.exists())


if __name__ == "__main__":
    unittest.main()
