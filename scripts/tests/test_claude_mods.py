#!/usr/bin/env python3
"""Tests for the Claude Code mods under `home/dot_claude/exact_mods/`."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODS = REPO / "home" / "dot_claude" / "exact_mods"
SETTINGS = REPO / "home" / "dot_claude" / "settings.json"
# Mod events that keep Claude Code's Code Mode from starting (2.1.326 installedModsThatCheckToolCallsAtStartup);
# tool checks belong in settings command hooks instead.
CODE_MODE_BLOCKERS = re.compile(
    r"""on\(\s*['"](tool\.|classic\.(PreToolUse|PermissionRequest|PermissionDenied|PostToolUse|TaskCreated|TaskCompleted|"""
    r"""Elicitation|WorktreeCreate)|agent\.(offer|spawn)|session\.send)"""
)


def target_name(part: str) -> str:
    """The deployed name of one chezmoi source path part."""
    for prefix in ("exact_", "readonly_", "executable_"):
        part = part.removeprefix(prefix)
    return "." + part.removeprefix("dot_") if part.startswith("dot_") else part


def render(mod: Path, into: Path) -> Path:
    """Copy a mod's source to `into` under its deployed file names."""
    out = into / target_name(mod.name)
    for source in mod.rglob("*"):
        if source.is_file():
            target = out.joinpath(*(target_name(part) for part in source.relative_to(mod).parts))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    return out


class TestClaudeMods(unittest.TestCase):
    """WHEN the Claude Code mods deploy and load."""

    def test_settings_load_every_mod(self):
        mods = sorted(f"~/.claude/mods/{target_name(mod.name)}" for mod in MODS.iterdir() if mod.is_dir())
        self.assertTrue(mods)
        dirs = json.loads(SETTINGS.read_text())["env"]["CLAUDE_CODE_PLUGIN_DIRS"].split(":")
        self.assertEqual(sorted(dirs), mods)

    def test_mod_folders_are_not_exact(self):
        # The engine writes `.claude-plugin/types/` and `tsconfig.json` into each mod folder.
        for mod in MODS.iterdir():
            self.assertFalse(mod.name.startswith("exact_"), mod.name)

    def test_mods_leave_code_mode_on(self):
        for source in MODS.rglob("*register.ts"):
            self.assertIsNone(CODE_MODE_BLOCKERS.search(source.read_text()), source)

    @unittest.skipUnless(shutil.which("claude"), "claude is not installed")
    def test_mods_validate_and_pass_their_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            env = {**os.environ, "HOME": str(home), "CLAUDE_CONFIG_DIR": str(home / ".claude")}
            for mod in sorted(path for path in MODS.iterdir() if path.is_dir()):
                folder = render(mod, root)
                self.check_plugin(folder, env)

    def check_plugin(self, folder: Path, env: dict[str, str]):
        for action in ("validate", "test"):
            with self.subTest(mod=folder.name, action=action):
                run = subprocess.run(
                    ["claude", "plugin", action, str(folder)],
                    cwd=folder,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
