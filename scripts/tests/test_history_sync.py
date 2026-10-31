#!/usr/bin/env python3
"""Behavior tests for ,history-sync with a fake 1Password CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "home/exact_lib/exact_,history-sync"

FAKE_OP = """#!/bin/sh
store="$FAKE_OP_STORE"
case "$1 $2" in
  "account get") exit 0 ;;
  "document get") [ -f "$store" ] || exit 1; cp "$store" "$5" ;;
  "document edit") cp "$4" "$store" ;;
  "document create") cp "$3" "$store" ;;
  "item get") [ -f "$store" ] ;;
esac
"""


def entry(cmd: str, when: int) -> str:
    return f"- cmd: {cmd}\n  when: {when}\n"


class HistorySyncTests(unittest.TestCase):
    """WHEN fish history is synced through 1Password."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(LIB, self.root / "lib")
        (self.root / "bin").mkdir()
        (self.root / "bin/op").write_text(FAKE_OP)
        (self.root / "bin/op").chmod(0o755)
        self.history = self.root / "home/.local/share/fish/fish_history"
        self.history.parent.mkdir(parents=True)
        self.remote = self.root / "remote"
        self.env = {
            **os.environ,
            "HOME": str(self.root / "home"),
            "PATH": f"{self.root / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "FAKE_OP_STORE": str(self.remote),
        }

    def sync(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["bash", str(self.root / "lib/main.sh")], env=self.env, text=True, capture_output=True)

    def test_remote_with_repeated_commands_still_syncs(self) -> None:
        self.remote.write_text(entry("ls", 1) + entry("ls", 2) + entry("ls", 3) + entry("pwd", 3))
        self.history.write_text(entry("git status", 4))

        result = self.sync()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.history.read_text()
        for cmd in ("ls", "pwd", "git status"):
            self.assertIn(f"- cmd: {cmd}\n", text)
        self.assertEqual(self.remote.read_text(), text)

    def test_missing_local_history_installs_the_remote(self) -> None:
        self.remote.write_text(entry("ls", 1))

        result = self.sync()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("- cmd: ls\n", self.history.read_text())

    def test_command_appended_during_the_merge_survives(self) -> None:
        self.remote.write_text(entry("ls", 1))
        self.history.write_text(entry("pwd", 2))
        lib = self.root / "lib"
        (lib / "fish-history-merge.py").rename(lib / "real-merge.py")
        (lib / "fish-history-merge.py").write_text(
            "import os, pathlib, runpy, sys\n"
            "try:\n"
            "    runpy.run_path(os.path.join(os.path.dirname(__file__), 'real-merge.py'), run_name='__main__')\n"
            "finally:\n"
            "    flag = pathlib.Path(sys.argv[3] + '.appended')\n"
            "    if not flag.exists():\n"
            "        flag.touch()\n"
            f"        with open({str(self.history)!r}, 'a') as f: f.write({entry('make', 3)!r})\n"
        )

        result = self.sync()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for cmd in ("ls", "pwd", "make"):
            self.assertIn(f"- cmd: {cmd}\n", self.history.read_text())


if __name__ == "__main__":
    unittest.main()
