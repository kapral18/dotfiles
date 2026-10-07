#!/usr/bin/env python3
"""Tests for the Claude Code mods under `home/dot_claude/exact_mods/`."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODS = REPO / "home" / "dot_claude" / "exact_mods"
PROFILES = [REPO / "home" / "dot_claude" / f"settings.{name}.json" for name in ("personal", "work")]
# The repo-only plugin Claude loads from the project's .claude/skills folder.
DOTFILES_GUARD = REPO / ".claude" / "skills" / "dotfiles-guard"
SHELL_SOURCE = MODS / "sop-guard" / "hooks" / "readonly_shell.ts"


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

    def test_every_profile_loads_every_mod(self):
        mods = sorted(f"~/.claude/mods/{target_name(mod.name)}" for mod in MODS.iterdir() if mod.is_dir())
        self.assertTrue(mods)
        for profile in PROFILES:
            dirs = json.loads(profile.read_text())["env"]["CLAUDE_CODE_PLUGIN_DIRS"].split(":")
            self.assertEqual(sorted(dirs), mods, profile.name)

    def test_mod_folders_are_not_exact(self):
        # The engine writes `.claude-plugin/types/` and `tsconfig.json` into each mod folder.
        for mod in MODS.iterdir():
            self.assertFalse(mod.name.startswith("exact_"), mod.name)

    def test_dotfiles_guard_scanner_matches_sop_guard(self):
        # A plugin cannot import outside its folder, so dotfiles-guard keeps a copy.
        self.assertEqual((DOTFILES_GUARD / "hooks" / "shell.ts").read_text(), SHELL_SOURCE.read_text())

    @unittest.skipUnless(shutil.which("claude"), "claude is not installed")
    def test_mods_validate_and_pass_their_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mod in sorted(path for path in MODS.iterdir() if path.is_dir()):
                folder = render(mod, Path(tmp))
                self.check_plugin(folder)
            self.check_plugin(DOTFILES_GUARD)

    def check_plugin(self, folder: Path):
        for action in ("validate", "test"):
            with self.subTest(mod=folder.name, action=action):
                run = subprocess.run(
                    ["claude", "plugin", action, str(folder)], capture_output=True, text=True, timeout=120
                )
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
