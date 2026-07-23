#!/usr/bin/env python3
"""Launch Copilot CLI, avoiding the bare-resume MCP startup race.

Copilot 1.0.73 implements bare ``--resume`` by creating a temporary session,
then switching to the chosen session. MCP startup can remain attached to the
discarded temporary session, leaving every configured server at "Connecting".
Selecting from the same local session store first and launching
``--session-id=<id>`` starts directly in the intended session.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_REAL_COPILOT = "/opt/homebrew/bin/copilot"
BARE_RESUME_ARGS = {"--resume", "-r"}


@dataclass(frozen=True)
class Session:
    session_id: str
    cwd: str
    repository: str
    branch: str
    summary: str
    updated_at: str


def _copilot_home() -> Path:
    return Path(os.environ.get("COPILOT_HOME", Path.home() / ".copilot")).expanduser()


def _normalize(value: object, fallback: str = "") -> str:
    text = str(value) if value is not None else fallback
    return " ".join(text.split())


def _load_sessions(copilot_home: Path) -> list[Session]:
    database_path = copilot_home / "session-store.db"
    if not database_path.is_file():
        raise RuntimeError(f"Copilot session store not found: {database_path}")
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True, timeout=5) as database:
        rows = database.execute(
            """
            SELECT id, cwd, repository, branch, summary, updated_at
            FROM sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()
    sessions = []
    for session_id, cwd, repository, branch, summary, updated_at in rows:
        if not (copilot_home / "session-state" / session_id / "events.jsonl").is_file():
            continue
        sessions.append(
            Session(
                session_id=session_id,
                cwd=_normalize(cwd, "(unknown cwd)"),
                repository=_normalize(repository),
                branch=_normalize(branch),
                summary=_normalize(summary, "(unnamed session)"),
                updated_at=_normalize(updated_at),
            )
        )
    return sessions


def _session_row(session: Session, current_cwd: str) -> str:
    current = "*" if os.path.realpath(session.cwd) == current_cwd else " "
    repository = session.repository
    if session.branch:
        repository = f"{repository}@{session.branch}" if repository else session.branch
    updated = session.updated_at.replace("T", " ")[:19]
    return "\t".join(
        [
            session.session_id,
            current,
            updated,
            session.summary,
            repository or "(no repository)",
            session.cwd,
        ]
    )


def _select_session(copilot_home: Path) -> str:
    sessions = _load_sessions(copilot_home)
    if not sessions:
        raise RuntimeError("No resumable Copilot sessions found.")
    current_cwd = os.path.realpath(os.getcwd())
    rows = "\n".join(_session_row(session, current_cwd) for session in sessions) + "\n"
    try:
        result = subprocess.run(
            [
                "fzf",
                "--delimiter=\t",
                "--with-nth=2..",
                "--nth=3..",
                "--no-multi",
                "--layout=reverse",
                "--border",
                "--prompt=Copilot session> ",
                "--header=* current cwd | updated | name | repository | cwd",
            ],
            input=rows,
            text=True,
            stdout=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as error:
        raise RuntimeError("fzf is required for bare ,copilot --resume.") from error
    if result.returncode != 0 or not result.stdout.strip():
        raise KeyboardInterrupt
    return result.stdout.split("\t", 1)[0].strip()


def _rewrite_bare_resume(argv: list[str], copilot_home: Path) -> list[str]:
    rewritten = list(argv)
    for index, argument in enumerate(rewritten):
        next_argument = rewritten[index + 1] if index + 1 < len(rewritten) else None
        if argument in BARE_RESUME_ARGS and (next_argument is None or next_argument.startswith("-")):
            rewritten[index] = f"--session-id={_select_session(copilot_home)}"
            break
    return rewritten


def main(argv: list[str]) -> int:
    configured_copilot = os.environ.get("COPILOT_REAL_BIN", DEFAULT_REAL_COPILOT)
    real_copilot = shutil.which(configured_copilot)
    if real_copilot is None:
        print(f"Error: real copilot CLI not found at {configured_copilot}.", file=sys.stderr)
        return 127
    try:
        args = _rewrite_bare_resume(argv, _copilot_home())
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, sqlite3.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    try:
        os.execv(real_copilot, [real_copilot, *args])
    except OSError as error:
        print(f"Error: cannot exec {real_copilot}: {error}", file=sys.stderr)
        return 126
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
