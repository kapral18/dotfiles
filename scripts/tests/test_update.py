"""Tests for ``home/exact_lib/exact_,update/main.sh`` output relay.

``_relay_output`` replaces the former ``sed`` prefix pipe. It must show a partial
line (an interactive prompt without a trailing newline) before the child finishes,
keep the per-line prefix, forward the child's exit status through ``PIPESTATUS``,
and end on a fresh line when the child stops mid-line.
"""

from __future__ import annotations

import os
import pty
import re
import select
import subprocess
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


if __name__ == "__main__":
    unittest.main()
