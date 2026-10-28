#!/usr/bin/env python3
"""Tests for fish history merger"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Protocol, cast

current_dir = Path(__file__).resolve().parent
history_merge_script_path = str(current_dir / "fish-history-merge.py")


class FishHistoryMergeModule(Protocol):
    def parse_fish_history(self, file_path: str) -> dict[str, dict[str, str | int | list[str]]]: ...
    def merge_histories(self, local_file: str, remote_file: str, output_file: str) -> bool: ...


sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("fish_history_merge", history_merge_script_path)
if spec and spec.loader:
    _module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_module)
    fish_history_merge = cast(FishHistoryMergeModule, cast(object, _module))
else:
    raise ImportError(f"Could not import {history_merge_script_path}")


class TestFishHistoryMerge(unittest.TestCase):
    temp_dir: str = ""
    local_file: str = ""
    remote_file: str = ""
    output_file: str = ""

    def setUp(self) -> None:
        """Set up test fixtures"""
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.temp_dir = scratch.name
        self.local_file = os.path.join(self.temp_dir, "local_history")
        self.remote_file = os.path.join(self.temp_dir, "remote_history")
        self.output_file = os.path.join(self.temp_dir, "output_history")

    def write_history(self, file_path: str, content: str) -> None:
        """Helper to write history content to a file"""
        with open(file_path, "w", encoding="utf-8") as f:
            _ = f.write(content)

    def read_history(self, file_path: str) -> str:
        """Helper to read history content from a file"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_parse_empty_file(self) -> None:
        self.write_history(self.local_file, "")
        result = fish_history_merge.parse_fish_history(self.local_file)
        self.assertEqual(result, {})

    def test_parse_entry_with_paths(self) -> None:
        content = """- cmd: cd /home/user
  when: 1700000001
  paths:
    - /home/user
    - /home
"""
        self.write_history(self.local_file, content)
        result = fish_history_merge.parse_fish_history(self.local_file)

        self.assertEqual(len(result), 1)
        entry = result["cd /home/user"]
        self.assertEqual(entry["cmd"], "cd /home/user")
        self.assertEqual(entry["when"], 1700000001)
        paths = entry.get("paths")
        self.assertIsInstance(paths, list)
        if isinstance(paths, list):
            self.assertEqual(paths, ["/home/user", "/home"])

    def test_parse_multiple_entries(self) -> None:
        content = """- cmd: ls
  when: 1700000000
- cmd: pwd
  when: 1700000001
- cmd: echo hello
  when: 1700000002
  paths:
    - /tmp
"""
        self.write_history(self.local_file, content)
        result = fish_history_merge.parse_fish_history(self.local_file)

        self.assertEqual(len(result), 3)
        self.assertIn("ls", result)
        self.assertIn("pwd", result)
        self.assertIn("echo hello", result)

        self.assertEqual(result["ls"]["when"], 1700000000)
        self.assertEqual(result["pwd"]["when"], 1700000001)
        self.assertEqual(result["echo hello"]["when"], 1700000002)

    def test_parse_duplicate_commands_keeps_most_recent(self) -> None:
        content = """- cmd: ls
  when: 1700000000
- cmd: ls
  when: 1700000002
- cmd: ls
  when: 1700000001
"""
        self.write_history(self.local_file, content)
        result = fish_history_merge.parse_fish_history(self.local_file)

        self.assertEqual(len(result), 1)
        self.assertEqual(result["ls"]["when"], 1700000002)

    def test_parse_entry_without_when(self) -> None:
        content = """- cmd: ls -la
"""
        self.write_history(self.local_file, content)
        result = fish_history_merge.parse_fish_history(self.local_file)

        self.assertEqual(len(result), 1)
        self.assertIn("ls -la", result)
        entry = result["ls -la"]
        self.assertEqual(entry["cmd"], "ls -la")
        self.assertNotIn("when", entry)

    def test_parse_command_containing_cmd_marker(self) -> None:
        """Commands whose text contains the literal '- cmd: ' must not be split"""
        content = """- cmd: grep -- "- cmd: " file
  when: 1700000000
- cmd: echo "- cmd: not a real entry"
  when: 1700000001
- cmd: ls
  when: 1700000002
"""
        self.write_history(self.local_file, content)
        result = fish_history_merge.parse_fish_history(self.local_file)

        self.assertEqual(len(result), 3)
        self.assertIn('grep -- "- cmd: " file', result)
        self.assertIn('echo "- cmd: not a real entry"', result)
        self.assertIn("ls", result)
        self.assertEqual(result['grep -- "- cmd: " file']["when"], 1700000000)

    def test_parse_invalid_file(self) -> None:
        result = fish_history_merge.parse_fish_history("/nonexistent/file")
        self.assertEqual(result, {})

    def test_merge_no_duplicates(self) -> None:
        local_content = """- cmd: ls
  when: 1700000000
- cmd: pwd
  when: 1700000002
"""
        remote_content = """- cmd: echo hello
  when: 1700000001
- cmd: cd /tmp
  when: 1700000003
"""
        self.write_history(self.local_file, local_content)
        self.write_history(self.remote_file, remote_content)

        success = fish_history_merge.merge_histories(self.local_file, self.remote_file, self.output_file)
        self.assertTrue(success)

        output = self.read_history(self.output_file)
        self.assertIn("ls", output)
        self.assertIn("pwd", output)
        self.assertIn("echo hello", output)
        self.assertIn("cd /tmp", output)

        lines = output.strip().split("\n")
        commands = [line[7:] for line in lines if line.startswith("- cmd: ")]
        self.assertEqual(commands, ["ls", "echo hello", "pwd", "cd /tmp"])

    def test_merge_with_duplicates_keeps_recent(self) -> None:
        local_content = """- cmd: ls
  when: 1700000000
  paths:
    - /old/path
- cmd: pwd
  when: 1700000002
"""
        remote_content = """- cmd: ls
  when: 1700000003
  paths:
    - /new/path
- cmd: echo test
  when: 1700000001
"""
        self.write_history(self.local_file, local_content)
        self.write_history(self.remote_file, remote_content)

        success = fish_history_merge.merge_histories(self.local_file, self.remote_file, self.output_file)
        self.assertTrue(success)

        output = self.read_history(self.output_file)

        self.assertIn("when: 1700000003", output)
        self.assertIn("/new/path", output)
        self.assertNotIn("/old/path", output)

        lines = output.strip().split("\n")
        commands = [line[7:] for line in lines if line.startswith("- cmd: ")]
        self.assertEqual(commands, ["echo test", "pwd", "ls"])

    def test_merge_empty_files(self) -> None:
        self.write_history(self.local_file, "")
        self.write_history(self.remote_file, "")

        success = fish_history_merge.merge_histories(self.local_file, self.remote_file, self.output_file)
        self.assertTrue(success)

        output = self.read_history(self.output_file)
        self.assertEqual(output, "")

    def test_merge_with_missing_when_fields(self) -> None:
        local_content = """- cmd: ls
- cmd: pwd
  when: 1700000001
"""
        remote_content = """- cmd: echo hello
  when: 1700000002
- cmd: ls
  when: 1700000003
"""
        self.write_history(self.local_file, local_content)
        self.write_history(self.remote_file, remote_content)

        success = fish_history_merge.merge_histories(self.local_file, self.remote_file, self.output_file)
        self.assertTrue(success)

        output = self.read_history(self.output_file)
        self.assertIn("- cmd: ls\n  when: 1700000003\n", output)

    def test_merge_invalid_output_path(self) -> None:
        self.write_history(self.local_file, "- cmd: ls\n  when: 1700000000\n")
        self.write_history(self.remote_file, "- cmd: pwd\n  when: 1700000001\n")

        success = fish_history_merge.merge_histories(
            self.local_file,
            self.remote_file,
            str(Path(self.temp_dir) / "missing" / "output"),
        )
        self.assertFalse(success)

    def test_command_line_interface(self) -> None:
        local_content = """- cmd: ls
  when: 1700000000
"""
        remote_content = """- cmd: pwd
  when: 1700000001
"""
        self.write_history(self.local_file, local_content)
        self.write_history(self.remote_file, remote_content)

        result = subprocess.run(
            [
                sys.executable,
                history_merge_script_path,
                self.local_file,
                self.remote_file,
                self.output_file,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)

        output = self.read_history(self.output_file)
        self.assertIn("ls", output)
        self.assertIn("pwd", output)

    def test_command_line_interface_wrong_args(self) -> None:
        result = subprocess.run(
            [sys.executable, history_merge_script_path, "file1"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Usage:", result.stdout)


if __name__ == "__main__":
    _ = unittest.main()
