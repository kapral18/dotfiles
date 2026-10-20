from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/merge_claude_global_config.py"
DESIRED = {"claude_global_config": {"diffSidebarOpen": False}}


class TestMergeClaudeGlobalConfig(unittest.TestCase):
    """WHEN declared keys are merged into Claude Code's runtime-owned ~/.claude.json."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "desired.json"
        self.target = self.root / "live.json"
        self.source.write_text(json.dumps(DESIRED), encoding="utf-8")

    def _merge(self, target: Path | None = None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.source), str(target or self.target)],
            capture_output=True,
            text=True,
        )

    def test_SHOULD_override_a_runtime_value_keep_other_state_and_skip_an_identical_rerun(self):
        # Raw text: a non-ASCII path and the lone surrogate Claude leaves when it cuts a stored prompt mid-emoji.
        live_text = (
            '{"numStartups": 3, "diffSidebarOpen": true, "projects": {"/tmp/naïve": {"lastPrompt": "cut \\ud83d"}}}'
        )
        self.target.write_text(live_text, encoding="utf-8")
        self.target.chmod(0o640)

        result = self._merge()

        self.assertEqual(result.returncode, 0, result.stderr)
        expected = {**json.loads(live_text), "diffSidebarOpen": False}
        self.assertEqual(json.loads(self.target.read_text(encoding="utf-8")), expected)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)
        before = (self.target.read_bytes(), self.target.stat().st_mtime_ns)
        self.assertEqual(self._merge().returncode, 0)
        self.assertEqual((self.target.read_bytes(), self.target.stat().st_mtime_ns), before)

    def test_SHOULD_treat_a_same_valued_key_of_another_json_type_as_drift(self):
        self.target.write_text('{"diffSidebarOpen": 0}', encoding="utf-8")

        result = self._merge()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json.loads(self.target.read_text(encoding="utf-8"))["diffSidebarOpen"], False)

    def test_SHOULD_bootstrap_a_missing_target_from_the_repo_keys_as_a_private_file(self):
        # The hook feeds this repo file to the helper; a bad edit must fail here, not mid-apply.
        self.source = REPO / "home/.chezmoidata/claude_global_config.json"

        result = self._merge()

        self.assertEqual(result.returncode, 0, result.stderr)
        declared = json.loads(self.source.read_text(encoding="utf-8"))["claude_global_config"]
        self.assertEqual(json.loads(self.target.read_text(encoding="utf-8")), declared)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)

    def test_SHOULD_write_through_a_symlinked_target_and_keep_the_link(self):
        real = self.root / "real.json"
        real.write_text('{"theme": "dark"}', encoding="utf-8")
        link = self.root / "link.json"
        link.symlink_to(real)

        result = self._merge(link)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertEqual(json.loads(real.read_text(encoding="utf-8")), {"theme": "dark", "diffSidebarOpen": False})

    def test_SHOULD_reject_invalid_documents_without_writing_live_bytes(self):
        valid_source = json.dumps(DESIRED)
        cases = [
            (valid_source, '{"runtime_state": "preserve",'),
            (valid_source, "[]"),
            ('{"claude_global_config": {}}', "{}"),
            ('{"claude_global_config": []}', "{}"),
            ('{"other": {"diffSidebarOpen": false}}', "{}"),
            ('{"claude_global_config": {"a b": false}}', "{}"),
            ('{"claude_global_config": {"x.y": false}}', "{}"),
            ("{", "{}"),
        ]
        for source, live in cases:
            with self.subTest(source=source, live=live):
                self.source.write_text(source, encoding="utf-8")
                self.target.write_text(live, encoding="utf-8")

                result = self._merge()

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Error:", result.stderr)
                self.assertEqual(self.target.read_text(encoding="utf-8"), live)
                self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["desired.json", "live.json"])


if __name__ == "__main__":
    unittest.main()
