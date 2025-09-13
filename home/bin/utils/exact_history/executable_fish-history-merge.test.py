#!/usr/bin/env python3
"""Tests for fish history merger"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
import subprocess

# Import the module to test
import importlib.util

history_merge_script_path = str(
    Path.home()
    / ".config"
    / "fish"
    / "my"
    / "functions"
    / "history"
    / "fish-history-merge.py"
)


spec = importlib.util.spec_from_file_location(
    "fish_history_merge", history_merge_script_path
)
if spec and spec.loader:
    fish_history_merge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fish_history_merge)
else:
    raise ImportError("Could not import fish-history-merge.py")


class TestFishHistoryMerge(unittest.TestCase):
    """Test cases for fish history merger"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.local_file = os.path.join(self.temp_dir, "local_history")
        self.remote_file = os.path.join(self.temp_dir, "remote_history")
        self.output_file = os.path.join(self.temp_dir, "output_history")

    def tearDown(self) -> None:
        """Clean up test fixtures"""
        for file in [self.local_file, self.remote_file, self.output_file]:
            if os.path.exists(file):
                os.remove(file)
        os.rmdir(self.temp_dir)

    def write_history(self, file_path: str, content: str) -> None:
        """Helper to write history content to a file"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def read_history(self, file_path: str) -> str:
        """Helper to read history content from a file"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_parse_empty_file(self) -> None:
        """Test parsing an empty history file"""
        self.write_history(self.local_file, "")
        result = fish_history_merge.parse_fish_history(self.local_file)
        self.assertEqual(result, {})

    def test_parse_single_entry(self) -> None:
        """Test parsing a single history entry"""
        content = """- cmd: ls -la
  when: 1700000000
"""
        self.write_history(self.local_file, content)
        result = fish_history_merge.parse_fish_history(self.local_file)

        self.assertEqual(len(result), 1)
        self.assertIn("ls -la", result)
        entry = result["ls -la"]
        self.assertEqual(entry["cmd"], "ls -la")
        self.assertEqual(entry["when"], 1700000000)

    def test_parse_entry_with_paths(self) -> None:
        """Test parsing an entry with paths"""
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
        """Test parsing multiple history entries"""
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
        """Test that duplicate commands keep the most recent version"""
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
        """Test parsing an entry without a 'when' field"""
        content = """- cmd: ls -la
"""
        self.write_history(self.local_file, content)
        result = fish_history_merge.parse_fish_history(self.local_file)

        self.assertEqual(len(result), 1)
        self.assertIn("ls -la", result)
        entry = result["ls -la"]
        self.assertEqual(entry["cmd"], "ls -la")
        self.assertNotIn("when", entry)

    def test_parse_invalid_file(self) -> None:
        """Test parsing a non-existent file"""
        result = fish_history_merge.parse_fish_history("/nonexistent/file")
        self.assertEqual(result, {})

    def test_merge_no_duplicates(self) -> None:
        """Test merging histories with no duplicate commands"""
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

        success = fish_history_merge.merge_histories(
            self.local_file, self.remote_file, self.output_file
        )
        self.assertTrue(success)

        output = self.read_history(self.output_file)
        # Check that all commands are present
        self.assertIn("ls", output)
        self.assertIn("pwd", output)
        self.assertIn("echo hello", output)
        self.assertIn("cd /tmp", output)

        # Check chronological order
        lines = output.strip().split("\n")
        commands = [line[7:] for line in lines if line.startswith("- cmd: ")]
        self.assertEqual(commands, ["ls", "echo hello", "pwd", "cd /tmp"])

    def test_merge_with_duplicates_keeps_recent(self) -> None:
        """Test that merging keeps the most recent version of duplicate commands"""
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

        success = fish_history_merge.merge_histories(
            self.local_file, self.remote_file, self.output_file
        )
        self.assertTrue(success)

        output = self.read_history(self.output_file)

        # Check that ls has the newer timestamp and path
        self.assertIn("when: 1700000003", output)
        self.assertIn("/new/path", output)
        self.assertNotIn("/old/path", output)

        # Verify chronological order
        lines = output.strip().split("\n")
        commands = [line[7:] for line in lines if line.startswith("- cmd: ")]
        self.assertEqual(commands, ["echo test", "pwd", "ls"])

    def test_merge_empty_files(self) -> None:
        """Test merging empty history files"""
        self.write_history(self.local_file, "")
        self.write_history(self.remote_file, "")

        success = fish_history_merge.merge_histories(
            self.local_file, self.remote_file, self.output_file
        )
        self.assertTrue(success)

        output = self.read_history(self.output_file)
        self.assertEqual(output, "")

    def test_merge_one_empty_file(self) -> None:
        """Test merging when one file is empty"""
        local_content = """- cmd: ls
  when: 1700000000
"""
        self.write_history(self.local_file, local_content)
        self.write_history(self.remote_file, "")

        success = fish_history_merge.merge_histories(
            self.local_file, self.remote_file, self.output_file
        )
        self.assertTrue(success)

        output = self.read_history(self.output_file)
        self.assertIn("ls", output)
        self.assertIn("1700000000", output)

    def test_merge_complex_entries(self) -> None:
        """Test merging complex entries with all fields"""
        local_content = """- cmd: git commit -m "Initial commit"
  when: 1700000000
  paths:
    - /home/user/project
    - /home/user/project/.git
- cmd: make clean
  when: 1700000002
"""
        remote_content = """- cmd: git push origin main
  when: 1700000001
  paths:
    - /home/user/project
- cmd: make clean
  when: 1700000003
  paths:
    - /home/user/project/build
"""
        self.write_history(self.local_file, local_content)
        self.write_history(self.remote_file, remote_content)

        success = fish_history_merge.merge_histories(
            self.local_file, self.remote_file, self.output_file
        )
        self.assertTrue(success)

        output = self.read_history(self.output_file)

        # Check all commands are present
        self.assertIn('git commit -m "Initial commit"', output)
        self.assertIn("git push origin main", output)
        self.assertIn("make clean", output)

        # make clean should have the newer timestamp
        self.assertIn("when: 1700000003", output)
        self.assertIn("/home/user/project/build", output)

    def test_merge_with_missing_when_fields(self) -> None:
        """Test merging entries where some lack 'when' fields"""
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

        success = fish_history_merge.merge_histories(
            self.local_file, self.remote_file, self.output_file
        )
        self.assertTrue(success)

        output = self.read_history(self.output_file)
        # ls should have the timestamp from remote since it's newer
        lines = output.strip().split("\n")

        # Find the ls command and check its timestamp
        for i, line in enumerate(lines):
            if line == "- cmd: ls":
                # Check next line for when field
                if i + 1 < len(lines):
                    self.assertEqual(lines[i + 1], "  when: 1700000003")

    def test_merge_invalid_output_path(self) -> None:
        """Test merge with invalid output path"""
        self.write_history(self.local_file, "- cmd: ls\n  when: 1700000000\n")
        self.write_history(self.remote_file, "- cmd: pwd\n  when: 1700000001\n")

        success = fish_history_merge.merge_histories(
            self.local_file,
            self.remote_file,
            "/invalid/path/that/does/not/exist/output",
        )
        self.assertFalse(success)

    def test_command_line_interface(self) -> None:
        """Test the command-line interface"""
        local_content = """- cmd: ls
  when: 1700000000
"""
        remote_content = """- cmd: pwd
  when: 1700000001
"""
        self.write_history(self.local_file, local_content)
        self.write_history(self.remote_file, remote_content)

        # Test with correct arguments
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
        """Test the command-line interface with wrong number of arguments"""
        # Test with too few arguments
        result = subprocess.run(
            [sys.executable, history_merge_script_path, "file1"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Usage:", result.stdout)

    def test_special_characters_in_commands(self) -> None:
        """Test handling of special characters in commands"""
        local_content = """- cmd: echo "Hello, World!"
  when: 1700000000
- cmd: grep -E '^[0-9]+$' file.txt
  when: 1700000001
"""
        self.write_history(self.local_file, local_content)
        self.write_history(self.remote_file, "")

        success = fish_history_merge.merge_histories(
            self.local_file, self.remote_file, self.output_file
        )
        self.assertTrue(success)

        output = self.read_history(self.output_file)
        self.assertIn('echo "Hello, World!"', output)
        self.assertIn("grep -E '^[0-9]+$' file.txt", output)


if __name__ == "__main__":
    unittest.main()
