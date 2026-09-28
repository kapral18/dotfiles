"""Small stdlib-only helpers shared across the ``,formal`` modules: subprocess
execution with a configurable timeout, hashing, JSON I/O, and the atomic /
locked write helpers ``catalog.py``'s ``index.json`` read-modify-write uses."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

DEFAULT_TIMEOUT = float(os.environ.get("FORMAL_TIMEOUT", "900"))

# Subprocess exit codes that mean "the tool could not run at all" (missing binary, spawn
# failure, or a timeout) rather than "the tool ran and reported a real failure". Callers use
# this to classify a stage as an environment error (``,formal audit``'s ``error`` stage status,
# never cached) instead of an ordinary check failure.
ENVIRONMENT_EXIT_CODES = frozenset({124, 127})


class CliError(Exception):
    """A ,formal usage/environment/check error with an explicit exit code.

    ``environment_error`` marks a failure that reflects the *environment* (missing tool,
    spawn failure, timeout) rather than a genuine check result -- ``,formal audit`` uses it to
    classify a stage ``error`` (distinct from ``fail``) and to refuse to cache the receipt.
    """

    def __init__(self, message: str, code: int = 2, environment_error: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.environment_error = environment_error


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))


def short_hash(data: bytes, length: int = 16) -> str:
    return sha256_hex(data)[:length]


def normalize_repo_path(path: str) -> str:
    """Normalize a repo-relative path the same way at anchor-record time and at every later
    comparison (``os.path.normpath``; collapses a leading ``./`` as a side effect), so
    ``./m.py`` and ``m.py`` are always the same anchor path."""
    return os.path.normpath(path)


def is_environment_failure(result: subprocess.CompletedProcess[Any]) -> bool:
    return result.returncode in ENVIRONMENT_EXIT_CODES


def _kill_process_group(process: subprocess.Popen[Any]) -> None:
    """Kill the process session owned by a timeout-managed helper."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run(
    argv: list[str],
    cwd: Path | str | None = None,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, applying the ``FORMAL_TIMEOUT`` (default 900s) budget.

    Decodes with ``errors="surrogateescape"`` (never the default strict decode): output
    containing non-UTF-8 bytes (e.g. a ``git diff`` over latin-1 file content) must never crash
    the caller with a ``UnicodeDecodeError`` -- ``,formal audit``/``catalog save``/``catalog
    uncovered`` all read subprocess text output through this helper.
    """
    effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="surrogateescape",
            env=env,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=effective_timeout)
            return subprocess.CompletedProcess(argv, process.returncode, stdout=stdout, stderr=stderr)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            stdout, stderr = process.communicate()
            return subprocess.CompletedProcess(
                argv,
                124,
                stdout=stdout or "",
                stderr=(stderr or "") + f"\n[,formal] timed out after {effective_timeout}s",
            )
    except OSError as exc:
        return subprocess.CompletedProcess(argv, 127, stdout="", stderr=str(exc))


def run_shell(
    command: str,
    cwd: Path | str | None = None,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="surrogateescape",
            env=env,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=effective_timeout)
            return subprocess.CompletedProcess(command, process.returncode, stdout=stdout, stderr=stderr)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            stdout, stderr = process.communicate()
            return subprocess.CompletedProcess(
                command,
                124,
                stdout=stdout or "",
                stderr=(stderr or "") + f"\n[,formal] timed out after {effective_timeout}s",
            )
    except OSError as exc:
        return subprocess.CompletedProcess(command, 127, stdout="", stderr=str(exc))


def run_raw(
    argv: list[str],
    cwd: Path | str | None = None,
    timeout: float | None = None,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Like ``run``, but captures raw bytes with no text decoding at all -- for git plumbing
    (``diff --binary``, ``ls-files -z``) whose output must be hashed byte-for-byte and must
    never be mangled or crash on a non-UTF-8 filename or file content. ``input_bytes`` feeds the
    subprocess's stdin directly (e.g. piping a captured ``git archive`` into ``tar -x`` as two
    separate subprocesses, each with its own checked exit code, instead of a shell pipeline whose
    exit status is only the *last* command's and would silently mask the first one's failure)."""
    effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.PIPE if input_bytes is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(input=input_bytes, timeout=effective_timeout)
            return subprocess.CompletedProcess(argv, process.returncode, stdout=stdout, stderr=stderr)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            stdout, stderr = process.communicate()
            return subprocess.CompletedProcess(
                argv,
                124,
                stdout=stdout or b"",
                stderr=(stderr or b"") + f"\n[,formal] timed out after {effective_timeout}s".encode("utf-8"),
            )
    except OSError as exc:
        return subprocess.CompletedProcess(argv, 127, stdout=b"", stderr=str(exc).encode("utf-8"))


def print_json(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def read_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CliError(f"Not found: {path}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CliError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write via a temp file in the same directory, then ``os.replace`` -- a concurrent reader
    of ``path`` never observes a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(tmp_name, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


@contextlib.contextmanager
def locked_file(lock_path: Path) -> Iterator[None]:
    """Exclusive ``flock`` around a read-modify-write sequence on some other file (e.g.
    ``index.json``): guards concurrent ``catalog save``/``catalog gc`` invocations (possibly
    across worktrees sharing the same catalog) from a lost update or a reader observing a
    half-written file."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
