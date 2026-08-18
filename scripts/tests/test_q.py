#!/usr/bin/env python3
"""Tests for the `,q` one-shot OpenRouter pi agent."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "home" / "exact_lib" / "exact_,q" / "main.py"
LAUNCHER = REPO / "home" / "exact_bin" / "executable_,q"


def load_core():
    spec = importlib.util.spec_from_file_location("q_launcher", CORE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {CORE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestQ(unittest.TestCase):
    """WHEN launching a one-shot OpenRouter pi agent via `,q`."""

    def run_q(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        check: bool = False,
        stdin: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(CORE), *args],
            cwd=REPO,
            env={**os.environ, **(env or {})},
            text=True,
            capture_output=True,
            check=False,
            input=stdin,
        )
        if check and result.returncode != 0:
            self.fail(f",q {' '.join(args)} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        return result

    def test_when_q_is_dry_run_it_emits_stripped_pi_argv_without_the_deepseek_pin(self) -> None:
        result = self.run_q("--dry-run", "hello", "world", check=True)
        payload = json.loads(result.stdout)
        argv = payload["argv"]
        core = load_core()

        self.assertTrue(payload["q"])
        self.assertEqual("inclusionai/ling-3.0-flash", payload["model"])
        self.assertEqual("pi", argv[0])
        self.assertEqual(
            [
                "--provider",
                "openrouter",
                "--model",
                "inclusionai/ling-3.0-flash",
                "--system-prompt",
                core.Q_SYSTEM_PROMPT,
                "--append-system-prompt",
                core.Q_APPEND_SYSTEM_PROMPT,
                "--no-session",
                "--thinking",
                "off",
                "--offline",
                "--no-skills",
                "--no-themes",
                "--no-context-files",
                "--no-prompt-templates",
                "--no-extensions",
                "-p",
                "hello world",
            ],
            argv[1:],
        )
        self.assertNotIn("deepseek", " ".join(argv))
        self.assertNotIn("--no-tools", argv)
        self.assertTrue(core.Q_SYSTEM_PROMPT.strip())
        self.assertEqual("", core.Q_APPEND_SYSTEM_PROMPT)

    def test_when_q_prompt_is_missing_it_fails_closed(self) -> None:
        core = load_core()
        empty = self.run_q(stdin="")
        with self.assertRaisesRegex(core.PlanError, "q requires a prompt"):
            core.parse_q([], stdin_is_tty=True)
        with self.assertRaisesRegex(core.PlanError, "q prompt is empty"):
            core.parse_q([], stdin=io.StringIO("   \n"), stdin_is_tty=False)

        self.assertEqual(2, empty.returncode)
        self.assertIn("q prompt is empty", empty.stderr)

    def test_when_q_reads_stdin_it_uses_that_as_the_prompt(self) -> None:
        result = self.run_q("--dry-run", stdin="from stdin\n", check=True)
        payload = json.loads(result.stdout)
        self.assertEqual("from stdin\n", payload["argv"][-1])

    def test_when_q_executes_the_fake_pi_receives_the_stripped_argv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / "bin"
            bindir.mkdir()
            log = root / "leaf.json"
            fake = bindir / "pi"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "Path(os.environ['AI_FAKE_LOG']).write_text(json.dumps({'argv': sys.argv}))\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = {
                "AI_FAKE_LOG": str(log),
                "PATH": os.pathsep.join([str(bindir), os.environ["PATH"]]),
            }

            result = self.run_q("ping", env=env, check=True)
            payload = json.loads(log.read_text(encoding="utf-8"))

            self.assertEqual("", result.stdout)
            self.assertEqual("pi", Path(payload["argv"][0]).name)
            self.assertEqual(load_core().leaf_argv("ping"), ("pi", *payload["argv"][1:]))

    def test_when_q_is_given_a_harness_flag_it_is_rejected(self) -> None:
        result = self.run_q("--depth", "deep", "hello")
        self.assertEqual(2, result.returncode)
        self.assertIn("unrecognized arguments", result.stderr)

    @unittest.skipUnless(shutil.which("pi"), "pi is not installed")
    def test_when_q_flags_are_emitted_installed_pi_documents_them(self) -> None:
        help_text = subprocess.run(
            [shutil.which("pi") or "pi", "--help"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        argv = load_core().leaf_argv("probe")
        flags = [arg for arg in argv if arg.startswith("--")]
        missing = [flag for flag in flags if flag not in help_text]
        self.assertEqual([], missing)

    def test_when_launcher_is_used_it_delegates_to_the_deployed_library(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            deployed = home / "lib" / ",q"
            deployed.mkdir(parents=True)
            shutil.copy2(CORE, deployed / "main.py")
            env = {**os.environ, "HOME": str(home)}
            result = subprocess.run(
                ["/bin/bash", str(LAUNCHER), "--dry-run", "ping"],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stdout)["q"])
        self.assertLessEqual(len(LAUNCHER.read_text(encoding="utf-8").splitlines()), 15)

    @unittest.skipUnless(shutil.which("fish"), "fish is not installed")
    def test_when_fish_completes_q_it_offers_dry_run(self) -> None:
        completion = REPO / "home" / "dot_config" / "fish" / "completions" / "readonly_,q.fish"
        result = subprocess.run(
            [
                shutil.which("fish") or "fish",
                "-c",
                "source $argv[1]; complete -C ',q -'",
                str(completion),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        tokens = {line.split("\t", 1)[0] for line in result.stdout.splitlines() if line.strip()}
        self.assertIn("--dry-run", tokens)


if __name__ == "__main__":
    unittest.main()
