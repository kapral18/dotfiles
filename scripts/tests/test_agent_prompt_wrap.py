#!/usr/bin/env python3
"""Focused observable contracts for the tmux prompt wrapper."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HANDLER = REPO / "home/dot_config/exact_tmux/exact_scripts/agent_prompt_wrap/executable_handle_enter.sh"


class TestAgentPromptWrap(unittest.TestCase):
    """WHEN Alt-Enter is handled for a pane."""

    def run_handler(self, processes: str, *, toggle="1", tty="/dev/ttys999"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / "bin"
            bindir.mkdir()
            prefix = root / ".config/tmux/agent_prompts/prefix.txt"
            prefix.parent.mkdir(parents=True)
            prefix.write_text("PREFIX\n")
            log = root / "calls.jsonl"
            tmux = bindir / "tmux"
            tmux.write_text(
                "#!/usr/bin/env python3\nimport os,sys,json\nwith open(os.environ['WRAP_CALLS'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\nif sys.argv[1]=='show':print(os.environ['WRAP_TOGGLE'])\nif sys.argv[1]=='display':print(os.environ['WRAP_TTY'])\n"
            )
            ps = bindir / "ps"
            ps.write_text(
                "#!/usr/bin/env python3\nimport os,sys\nrows=os.environ['WRAP_PROCESSES'].splitlines()\nfields=sys.argv[sys.argv.index('-o')+1]\nfor row in rows:\n print(row if fields != 'command=' else ' '.join(row.split()[3:]))\n"
            )
            tmux.chmod(0o755)
            ps.chmod(0o755)
            result = subprocess.run(
                ["/bin/bash", str(HANDLER), "%999"],
                env={
                    **os.environ,
                    "HOME": str(root),
                    "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
                    "WRAP_CALLS": str(log),
                    "WRAP_TOGGLE": toggle,
                    "WRAP_TTY": tty,
                    "WRAP_PROCESSES": processes,
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            return [json.loads(row) for row in log.read_text().splitlines()]

    def test_SHOULD_wrap_each_running_foreground_agent(self):
        for command in [
            "/bin/claude",
            "/bin/cursor-agent",
            "/bin/pi",
            "/bin/copilot",
            "pi",
            "claude",
            "node /module/pi-coding-agent/cli.js",
            "/usr/bin/node --enable-source-maps /module/pi-coding-agent/dist/bundle/cli.js",
            "/usr/bin/node /bin/pi",
        ]:
            with self.subTest(command=command):
                calls = self.run_handler("42 42 S+ " + command)
                self.assertIn(["send-keys", "-t", "%999", "C-a"], calls)
                self.assertIn(["paste-buffer", "-t", "%999", "-p"], calls)
                self.assertEqual(["send-keys", "-t", "%999", "C-e"], calls[-1])
                self.assertNotIn(["send-keys", "-t", "%999", "M-Enter"], calls)

    def test_SHOULD_pass_through_background_stopped_and_nonagent_processes(self):
        for processes in [
            "11 11 S+ /bin/bash\n42 11 S /bin/pi",
            "42 42 T+ /bin/pi",
            "42 42 S+ /bin/pioneer",
            "42 42 S+ /bin/pip",
            "42 42 S+ /bin/bash",
            "42 42 S+ /usr/bin/tail -f /tmp/pi",
            "42 42 S+ /usr/bin/printf pi-coding-agent",
            "42 42 S+ node unrelated.js /module/pi-coding-agent/cli.js",
            "",
        ]:
            with self.subTest(processes=processes):
                calls = self.run_handler(processes)
                self.assertEqual(["send-keys", "-t", "%999", "M-Enter"], calls[-1])
                self.assertFalse(any(row[0] == "paste-buffer" for row in calls))

    def test_SHOULD_pass_through_when_disabled_or_tty_missing(self):
        for toggle, tty in [("0", "/dev/ttys999"), ("1", "")]:
            with self.subTest(toggle=toggle, tty=tty):
                calls = self.run_handler("42 42 S+ /bin/pi", toggle=toggle, tty=tty)
                self.assertEqual(["send-keys", "-t", "%999", "M-Enter"], calls[-1])
                self.assertFalse(any(row[0] == "paste-buffer" for row in calls))


if __name__ == "__main__":
    unittest.main()
