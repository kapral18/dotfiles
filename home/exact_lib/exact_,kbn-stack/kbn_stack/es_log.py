"""Following an Elasticsearch setup log: trigger/expiry/exit verdicts and failure excerpts.

A spawned ES that exits before the setup trigger fails the start immediately
with a log excerpt instead of idling out the setup timeout.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from kbn_stack import config, procs, trial_license


def es_log_excerpt(logfile: Path, limit: int = 6) -> str:
    """The log's last error lines plus its tail, for a failure message the reader can act on."""
    try:
        lines = [line.rstrip() for line in logfile.read_text(encoding="utf-8", errors="replace").splitlines()]
    except OSError:
        return ""
    errors = [line for line in lines if any(token in line for token in ("ERROR", "FATAL", "Error:", "exit code"))]
    picked: list[str] = []
    for line in errors[-limit:] + lines[-limit:]:
        if line and line not in picked:
            picked.append(line)
    return "\n".join(f"    {line[:240]}" for line in picked)


def setup_failure_message(verdict: str, logfile: Path) -> str:
    excerpt = es_log_excerpt(logfile)
    detail = f"\n{excerpt}" if excerpt else ""
    if verdict == config.WAIT_EXITED:
        return f"Elasticsearch exited before finishing setup (see {logfile}):{detail}"
    if verdict == config.WAIT_EXPIRED:
        return (
            f"Elasticsearch still reports an expired trial license after the data dir was rotated "
            f"(see {logfile}):{detail}"
        )
    return f"Elasticsearch did not finish setup within {int(config.ES_SETUP_TIMEOUT)}s (see {logfile}):{detail}"


def boot_marker() -> str:
    """First line every ES log writer emits; unique per boot so a follower can tell a rewrite from appends."""
    return f",kbn-stack: Elasticsearch log opened {time.time():.6f} (pid {os.getpid()})\n"


class LogFollower:
    """Line reader over an ES log that a respawn may truncate and rewrite.

    A rewrite is detected when the file shrank below the read offset, or when
    its first line changed while the file stayed at least as long: a fresh boot
    that outgrew the old offset within one poll would otherwise be read from
    the middle and its trigger missed. ``readline`` returns ``""`` when idle.
    """

    def __init__(self, logfile: Path) -> None:
        self.logfile = logfile
        self.handle = logfile.open("r", encoding="utf-8", errors="replace")
        self.head: str | None = None
        self.idle = False

    def __enter__(self) -> "LogFollower":
        return self

    def __exit__(self, *exc: object) -> None:
        self.handle.close()

    def readline(self) -> str:
        # Check before reading: once the file has been idle, new bytes may belong to a
        # rewrite that already outgrew our offset, and reading them would start mid-line.
        if self.idle and self._rewritten():
            self.handle.seek(0)
            self.head = None
        at_start = self.head is None and self.handle.tell() == 0
        line = self.handle.readline()
        self.idle = not line
        if line and at_start and line.endswith("\n"):
            self.head = line
        return line

    def read(self) -> str:
        return self.handle.read()

    def _rewritten(self) -> bool:
        try:
            size = self.logfile.stat().st_size
        except OSError:
            return False
        if size < self.handle.tell():
            return True
        if self.head is None:
            return False
        try:
            with self.logfile.open("r", encoding="utf-8", errors="replace") as probe:
                return probe.readline() != self.head
        except OSError:
            return False


def wait_for_trigger(
    logfile: Path,
    timeout: float,
    trigger: str = config.TRIGGER_STRING,
    es_pid: int | None = None,
) -> str:
    """Follow the ES log until setup completes; return a ``WAIT_*`` verdict.

    ``WAIT_TRIGGER`` when the setup trigger appears, ``WAIT_EXPIRED`` when the
    log proves the data dir's trial expired (kbn-es would stop ES ~120s later
    without a trigger), ``WAIT_EXITED`` when ``es_pid`` (the spawned launcher)
    is gone with no trigger in the remaining log, ``WAIT_TIMEOUT`` otherwise.
    """
    deadline = time.monotonic() + timeout
    # spawn_background truncates the log before launching ES. Reading from byte
    # zero also detects a trigger written before this reader opens the file.
    with LogFollower(logfile) as log:
        while True:
            line = log.readline()
            if line:
                if trigger in line:
                    return config.WAIT_TRIGGER
                if trial_license.license_expired_line(line):
                    return config.WAIT_EXPIRED
                continue
            if es_pid is not None and not procs.pid_alive(es_pid):
                # The launcher may have flushed its last lines while we slept.
                if trigger in log.read():
                    return config.WAIT_TRIGGER
                return config.WAIT_EXITED
            if time.monotonic() >= deadline:
                return config.WAIT_TIMEOUT
            time.sleep(0.5)
