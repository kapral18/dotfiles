from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRELOAD = REPO / "home/dot_claude/readonly_no-agent-summary.cjs"

FIXTURE = r"""
const timers = require("node:timers");
const { promisify } = require("node:util");
const { setTimeout: promiseTimeout } = require("node:timers/promises");

async function main() {
  const summaries = [];
  const ordinary = [];
  const handles = [];
  for (const [name, api] of [["global", globalThis], ["module", timers]]) {
    handles.push(api.setTimeout(() => { summaries.push("[AgentSummary] Timer fired"); }, 0));
    handles.push(api.setInterval(() => { summaries.push("agent_summary"); }, 0));
    const cancelled = api.setTimeout(() => { throw new Error("cancelled timer fired"); }, 0);
    api.clearTimeout(cancelled);
    await new Promise(resolve => {
      const interval = api.setInterval((value) => {
        ordinary.push(value);
        api.clearInterval(interval);
        resolve();
      }, 0, name);
    });
  }
  const values = await Promise.all([
    promisify(globalThis.setTimeout)(0, "global promise"),
    promisify(timers.setTimeout)(0, "module promise"),
    promiseTimeout(0, "timers/promises"),
  ]);
  for (const handle of handles) {
    if (typeof handle.unref !== "function") throw new Error("invalid timer handle");
    clearTimeout(handle);
    clearInterval(handle);
  }
  console.log(JSON.stringify({ summaries, ordinary, values }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
"""


@unittest.skipUnless(shutil.which("bun"), "bun is not installed")
class TestClaudeAgentSummary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="claude-summary-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / "timers.cjs"
        cls.source.write_text(FIXTURE)
        cls.binary = cls.root / "timers"
        cls.env = {"PATH": os.environ["PATH"], "HOME": str(cls.root)}
        subprocess.run(
            ["bun", "build", "--compile", "--bytecode", str(cls.source), "--outfile", str(cls.binary)],
            cwd=cls.root,
            env=cls.env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def run_fixture(self, command, preload=True):
        env = dict(self.env)
        if preload:
            env["BUN_OPTIONS"] = f"--preload {PRELOAD}"
        result = subprocess.run(command, cwd=self.root, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        actual = json.loads(result.stdout)
        self.assertEqual(actual["ordinary"], ["global", "module"])
        self.assertEqual(actual["values"], ["global promise", "module promise", "timers/promises"])
        return actual["summaries"]

    def test_SHOULD_suppress_only_summary_timers_in_compiled_bun(self):
        self.assertTrue(self.run_fixture([str(self.binary)], preload=False))
        self.assertEqual(self.run_fixture([str(self.binary)]), [])

    def test_SHOULD_leave_uncompiled_bun_timers_unchanged(self):
        self.assertTrue(self.run_fixture(["bun", str(self.source)]))

    def test_SHOULD_preserve_bun_options_once_across_shell_startup(self):
        home = self.root / "home with spaces"
        (home / ".claude").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PRELOAD, home / ".claude/no-agent-summary.cjs")
        for shell, path, boundary in (
            ("bash", "home/readonly_dot_profile.tmpl", "\nexport HOMEBREW_NO_AUTO_UPDATE"),
            ("zsh", "home/readonly_dot_profile.tmpl", "\nexport HOMEBREW_NO_AUTO_UPDATE"),
            ("fish", "home/dot_config/fish/readonly_config.fish.tmpl", "\nset -x HOMEBREW_NO_AUTO_UPDATE"),
        ):
            with self.subTest(shell=shell):
                source = (REPO / path).read_text().split(boundary, 1)[0]
                startup = self.root / f"startup.{shell}"
                startup.write_text(source)
                setup = "function fish_config; end; " if shell == "fish" else ""
                command = setup + f'source "{startup}"; source "{startup}"; printf "%s" "$BUN_OPTIONS"'
                argv = [shell, "--no-config", "-c", command] if shell == "fish" else [shell, "-c", command]
                env = {**self.env, "HOME": str(home), "BUN_OPTIONS": "--no-warnings"}
                result = subprocess.run(argv, cwd=self.root, env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                escaped_home = str(home).replace(" ", r"\ ")
                expected = f"--no-warnings --preload {escaped_home}/.claude/no-agent-summary.cjs"
                self.assertEqual(result.stdout, expected)
                run = subprocess.run(
                    [str(self.binary)],
                    cwd=self.root,
                    env={**env, "BUN_OPTIONS": result.stdout},
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertEqual(json.loads(run.stdout)["summaries"], [])


if __name__ == "__main__":
    unittest.main()
