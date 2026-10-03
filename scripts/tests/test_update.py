"""Tests for ``home/exact_lib/exact_,update/main.sh`` output relay.

``_relay_output`` replaces the former ``sed`` prefix pipe. It must show a partial
line (an interactive prompt without a trailing newline) before the child finishes,
keep the per-line prefix, forward the child's exit status through ``PIPESTATUS``,
and end on a fresh line when the child stops mid-line.
"""

from __future__ import annotations

import json
import os
import pty
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAIN_SH = REPO / "home/exact_lib/exact_,update/main.sh"


def _relay_source() -> str:
    text = MAIN_SH.read_text(encoding="utf-8")
    match = re.search(r"^RELAY_POLL_SECONDS=.*?\n_relay_output\(\) \{\n.*?^\}\n", text, re.S | re.M)
    assert match, "_relay_output not found in main.sh"
    return match.group(0)


def _run_on_pty(script: str, timeout: float = 5.0) -> tuple[list[tuple[float, bytes]], int]:
    """Run ``script`` under bash with stdout on a pty; return timestamped chunks and exit status."""
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        ["bash", "-c", _relay_source() + "\nC_DIM='' C_R=''\n" + script],
        stdin=subprocess.DEVNULL,
        stdout=slave,
        stderr=slave,
        close_fds=True,
    )
    os.close(slave)
    chunks: list[tuple[float, bytes]] = []
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        ready, _, _ = select.select([master], [], [], 0.05)
        if ready:
            try:
                data = os.read(master, 4096)
            except OSError:
                break
            if not data:
                break
            chunks.append((time.monotonic() - start, data))
        elif proc.poll() is not None:
            # drain anything left after exit
            ready, _, _ = select.select([master], [], [], 0.2)
            if ready:
                try:
                    data = os.read(master, 4096)
                    if data:
                        chunks.append((time.monotonic() - start, data))
                except OSError:
                    pass
            break
    os.close(master)
    return chunks, proc.wait(timeout=timeout)


class RelayOutputTests(unittest.TestCase):
    def test_partial_prompt_is_visible_before_child_finishes(self) -> None:
        script = (
            "( printf 'x has changed since chezmoi last wrote it [overwrite,skip,quit]? '; sleep 1.2; echo done )"
            " | _relay_output"
        )
        chunks, rc = _run_on_pty(script)
        self.assertEqual(rc, 0)
        prompt_at = next((t for t, data in chunks if b"[overwrite,skip,quit]? " in data), None)
        self.assertIsNotNone(prompt_at, f"prompt never surfaced; chunks={chunks!r}")
        self.assertLess(prompt_at, 1.0, "prompt was held back until the child finished")
        output = b"".join(data for _, data in chunks)
        self.assertIn(
            "    │ x has changed since chezmoi last wrote it [overwrite,skip,quit]? done\r\n".encode(), output
        )

    def test_prefix_on_every_line_and_child_status_forwarded(self) -> None:
        script = (
            "( printf 'one\\ntwo\\n'; exit 7 ) | _relay_output; rc=${PIPESTATUS[0]}; "
            'printf \'rc=%s\\n\' "$rc"; exit "$rc"'
        )
        chunks, rc = _run_on_pty(script)
        output = b"".join(data for _, data in chunks)
        self.assertEqual(rc, 7)
        self.assertIn("    │ one\r\n    │ two\r\nrc=7\r\n".encode(), output)

    def test_child_ending_mid_line_gets_newline(self) -> None:
        script = "printf 'no newline' | _relay_output; printf 'NEXT\\n'"
        chunks, rc = _run_on_pty(script)
        output = b"".join(data for _, data in chunks)
        self.assertEqual(rc, 0)
        self.assertIn("    │ no newline\r\nNEXT\r\n".encode(), output)

    def test_run_timed_uses_relay_not_sed(self) -> None:
        text = MAIN_SH.read_text(encoding="utf-8")
        self.assertIn('"$@" 2>&1 | _relay_output', text)
        self.assertNotIn('| sed "s/^/', text)


NATIVE_RUNNER = MAIN_SH.with_name("readonly_native_runner.py")

FAKE_DEKIT = r"""import json
import os
from pathlib import Path
import signal
import subprocess
import sys

root = Path(sys.argv[2])
command = sys.argv[3:]
config = json.loads((root / "dekit.yaml").read_text())
with open(os.environ["UPDATE_TEST_CALLS"], "a") as log:
    log.write(json.dumps({"command": command, "root": str(root), "config": config,
                          "env": {key: os.environ.get(key) for key in
                                  ("HOME", "XDG_RUNTIME_DIR", "XDG_STATE_HOME")}}) + "\n")
mode = os.environ.get("UPDATE_TEST_MODE", "complete")
if command == ["up"]:
    if mode == "remove_original":
        Path(os.environ["UPDATE_TEST_ORIGINAL_DEKIT"]).unlink()
    if mode == "up_failure":
        sys.exit(19)
    if mode not in ("early_q", "early_Q", "hold"):
        for task in config["tasks"].values():
            env = dict(os.environ)
            for key, value in task["env"].items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value
            subprocess.run(task["cmd"], env=env, cwd=task["cwd"])
    if mode.startswith("token:"):
        (root / "uv.rc").write_text(mode[len("token:"):])
    if mode == "missing":
        (root / "uv.rc").unlink()
elif command == ["attach", "--no-start"]:
    if mode == "attach_failure":
        sys.exit(23)
    if mode == "hold":
        Path(os.environ["UPDATE_TEST_READY"]).touch()
        while True:
            signal.pause()
elif command == ["runner", "stop"]:
    if mode == "stop_failure":
        sys.exit(29)
else:
    sys.exit(42)
"""


class ParallelRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="update-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls"
        self.steps = self.root / "steps"
        self.cwd = self.root / "cwd with 'quotes'"
        self.cwd.mkdir()
        self.main = self.cwd / "main.sh"
        self.main.write_text(MAIN_SH.read_text())
        (self.cwd / "native_runner.py").write_text(NATIVE_RUNNER.read_text())
        self.env = {
            **os.environ,
            "HOME": str(self.root),
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "UPDATE_TEST_CALLS": str(self.calls),
            "UPDATE_TEST_STEPS": str(self.steps),
            "UPDATE_TEST_READY": str(self.root / "ready"),
        }
        for key in ("XDG_RUNTIME_DIR", "XDG_STATE_HOME"):
            self.env.pop(key, None)
        for category in ("gh", "uv"):
            self.write_command(
                category,
                f"""#!/bin/bash
printf '{category}\\n' >> "$UPDATE_TEST_STEPS"
exit "${{UPDATE_TEST_{category.upper()}_RC:-0}}"
""",
            )
        self.write_command("dekit", f"#!{sys.executable}\n" + FAKE_DEKIT)

    def write_command(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def run_update(self, args: list[str] | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["/bin/bash", str(self.main), *(args or ["--only", "gh,uv"])],
            env=self.env,
            cwd=self.cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def invocations(self) -> list[dict]:
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_when_native_jobs_complete_should_report_actual_category_results(self) -> None:
        self.env["UPDATE_TEST_UV_RC"] = "7"
        result = self.run_update(["--only", "gh,uv", "--verbose"])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("1 updated", result.stdout)
        self.assertIn("1 failed", result.stdout)
        calls = self.invocations()
        self.assertEqual([call["command"] for call in calls], [["up"], ["attach", "--no-start"], ["runner", "stop"]])
        self.assertEqual(set(calls[0]["config"]["tasks"]), {"gh", "uv"})
        self.assertFalse(Path(calls[0]["root"]).exists())
        self.assertEqual(set(self.steps.read_text().splitlines()), {"gh", "uv"})

    def test_when_bypassed_should_run_only_selected_sequential_categories(self) -> None:
        cases = (
            (["--only", "gh"], {"gh"}),
            (["--only", "unknown"], set()),
            (["--skip", "dotfiles,brew,mise,uv,cargo,pnpm,gems,go,manual"], {"gh"}),
            (["--only", "gh,uv", "--dry-run"], set()),
        )
        for args, expected in cases:
            with self.subTest(args=args):
                self.steps.unlink(missing_ok=True)
                result = self.run_update(args)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(self.calls.exists())
                actual = set(self.steps.read_text().splitlines()) if self.steps.exists() else set()
                self.assertEqual(actual, expected)
        (self.bin / "dekit").unlink()
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.calls.exists())
        self.assertEqual(set(self.steps.read_text().splitlines()), {"gh", "uv"})

    def test_when_job_environment_is_restored_should_preserve_cwd_home_and_xdg(self) -> None:
        self.env["XDG_STATE_HOME"] = str(self.root / "original state")
        self.write_command(
            "gh",
            f"#!{sys.executable}\n"
            + "import json,os\nfrom pathlib import Path\n"
            + "Path(os.environ['UPDATE_TEST_STEPS']).write_text(json.dumps({"
            + "'cwd': os.getcwd(), 'home': os.environ['HOME'], "
            + "'runtime': os.environ.get('XDG_RUNTIME_DIR'), "
            + "'state': os.environ.get('XDG_STATE_HOME')}))\n",
        )
        self.write_command("uv", "#!/bin/bash\nexit 0\n")
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            json.loads(self.steps.read_text()),
            {
                "cwd": str(self.cwd.resolve()),
                "home": str(self.root),
                "runtime": None,
                "state": str(self.root / "original state"),
            },
        )
        launch = self.invocations()[0]
        self.assertEqual(launch["config"]["kernel"]["path"], str(Path(launch["root"]) / "dekit"))
        self.assertNotEqual(launch["env"]["XDG_STATE_HOME"], self.env["XDG_STATE_HOME"])

    def test_when_original_executable_is_removed_during_startup_should_attach_and_stop(self) -> None:
        original = self.root / "Cellar" / "dekit" / "bin" / "dekit"
        original.parent.mkdir(parents=True)
        (self.bin / "dekit").rename(original)
        (self.bin / "dekit").symlink_to(original)
        self.env["UPDATE_TEST_MODE"] = "remove_original"
        self.env["UPDATE_TEST_ORIGINAL_DEKIT"] = str(original)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(original.exists())
        self.assertIn("2 updated", result.stdout)
        calls = self.invocations()
        self.assertEqual([call["command"] for call in calls], [["up"], ["attach", "--no-start"], ["runner", "stop"]])
        root = Path(calls[0]["root"])
        self.assertTrue(all(call["config"]["kernel"]["path"] == str(root / "dekit") for call in calls))
        self.assertFalse(root.exists())

    def test_when_closed_early_should_fail_incomplete_jobs_and_stop_owned_runner(self) -> None:
        for mode in ("early_q", "early_Q"):
            with self.subTest(mode=mode):
                self.calls.unlink(missing_ok=True)
                self.env["UPDATE_TEST_MODE"] = mode
                result = self.run_update()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("0 updated", result.stdout)
                self.assertIn("2 failed", result.stdout)
                calls = self.invocations()
                self.assertEqual(calls[-1]["command"], ["runner", "stop"])
                self.assertFalse(Path(calls[0]["root"]).exists())

    def test_when_status_is_missing_or_malformed_should_never_count_it_as_success(self) -> None:
        for mode in ("missing", "token:0junk", "token:0 1", "token:", "token:00", "token:0\nextra"):
            with self.subTest(mode=mode):
                self.env["UPDATE_TEST_MODE"] = mode
                result = self.run_update()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("1 updated", result.stdout)
                self.assertIn("1 failed", result.stdout)

    def prepare_manual(self) -> Path:
        template = (
            self.root
            / ".local/share/chezmoi/home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl"
        )
        template.parent.mkdir(parents=True)
        marker = self.root / "manual-ran"
        template.write_text(f"touch '{marker}'\n")
        self.write_command("chezmoi", "#!/bin/bash\ncat\n")
        return marker

    def test_when_startup_or_attach_fails_should_stop_and_skip_manual(self) -> None:
        marker = self.prepare_manual()
        for mode in ("up_failure", "attach_failure"):
            with self.subTest(mode=mode):
                self.calls.unlink(missing_ok=True)
                self.env["UPDATE_TEST_MODE"] = mode
                result = self.run_update(["--only", "gh,uv,manual"])
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("native dekit lifecycle failed", result.stdout)
                self.assertFalse(marker.exists())
                calls = self.invocations()
                self.assertEqual(calls[-1]["command"], ["runner", "stop"])
                self.assertFalse(Path(calls[0]["root"]).exists())

    def test_when_stop_fails_should_retain_exact_root_and_report_recovery(self) -> None:
        self.env["UPDATE_TEST_MODE"] = "stop_failure"
        result = self.run_update()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        root = Path(self.invocations()[0]["root"])
        self.addCleanup(shutil.rmtree, root)
        self.assertTrue(root.exists())
        self.assertTrue(os.access(root / "dekit", os.X_OK))
        self.assertIn(str(root), result.stderr)
        self.assertIn("Recovery:", result.stderr)
        self.assertIn("runner stop", result.stderr)

    def test_when_parent_receives_signal_should_wait_for_cleanup_and_skip_manual(self) -> None:
        marker = self.prepare_manual()
        for signum in (signal.SIGINT, signal.SIGTERM):
            for process_group in (False, True):
                with self.subTest(signal=signum, process_group=process_group):
                    self.calls.unlink(missing_ok=True)
                    ready = Path(self.env["UPDATE_TEST_READY"])
                    ready.unlink(missing_ok=True)
                    self.env["UPDATE_TEST_MODE"] = "hold"
                    proc = subprocess.Popen(
                        ["/bin/bash", str(self.main), "--only", "gh,uv,manual"],
                        env=self.env,
                        cwd=self.cwd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        start_new_session=True,
                    )
                    try:
                        deadline = time.monotonic() + 10
                        while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
                            time.sleep(0.02)
                        self.assertTrue(ready.exists(), "native attach did not become ready")
                        if process_group:
                            os.killpg(proc.pid, signum)
                        else:
                            proc.send_signal(signum)
                        stdout, stderr = proc.communicate(timeout=10)
                        self.assertEqual(proc.returncode, 128 + signum, stdout + stderr)
                        calls = self.invocations()
                        self.assertEqual(calls[-1]["command"], ["runner", "stop"])
                        self.assertFalse(Path(calls[0]["root"]).exists())
                        self.assertFalse(marker.exists())
                    finally:
                        if proc.poll() is None:
                            os.killpg(proc.pid, signal.SIGKILL)
                            proc.communicate()


if __name__ == "__main__":
    unittest.main()
