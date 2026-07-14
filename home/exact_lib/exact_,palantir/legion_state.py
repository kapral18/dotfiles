#!/usr/bin/env python3
"""Legion manifest I/O and registry for ,palantir.

One legion is one directory under the palantir state home::

    $PALANTIR_STATE_HOME/legions/<legion_id>/manifest.json

``PALANTIR_STATE_HOME`` defaults to ``$XDG_STATE_HOME/palantir``
(``~/.local/state/palantir``). The registry is flat — a legion IS the effort,
and its tmux session is its organisation. Writes are atomic (tmp + ``os.replace``) so a crash never
leaves a half-written manifest; read-modify-write cycles are serialized by a
per-legion ``fcntl`` lock.

Sidecar files under a legion dir (written by the runtime, read by the
dashboard):

    goal.txt                 the raw goal text (no shell re-parse)
    stages/<stage>.brief.json    what the stage agent was asked to do
    stages/<stage>.result.json   the structured handshake a stage agent writes
    questions.log            structured question events
    .supervisor.lock/        single-supervisor lock (one per legion)

CLI (stdlib only):

  legion_state.py [--state-home PATH] ls [--json]
  legion_state.py [--state-home PATH] new --goal G [--git-root P] [...]
  legion_state.py [--state-home PATH] show LEGION_ID
  legion_state.py [--state-home PATH] set LEGION_ID KEY VALUE
  legion_state.py [--state-home PATH] paths LEGION_ID
  legion_state.py [--state-home PATH] doctor
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import secrets
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import machine

MANIFEST_NAME = "manifest.json"


def default_state_home() -> Path:
    xdg = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return Path(os.environ.get("PALANTIR_STATE_HOME", xdg / "palantir")).expanduser()


class LegionState:
    """Read/write legion manifests and own the flat legion registry."""

    def __init__(self, state_home: Optional[Path] = None) -> None:
        self.state_home = state_home or default_state_home()
        self.legions_dir = self.state_home / "legions"

    def init(self) -> None:
        self.legions_dir.mkdir(parents=True, exist_ok=True)

    def legion_dir(self, legion_id: str) -> Path:
        return self.legions_dir / legion_id

    def manifest_path(self, legion_id: str) -> Path:
        return self.legion_dir(legion_id) / MANIFEST_NAME

    def stages_dir(self, legion_id: str) -> Path:
        return self.legion_dir(legion_id) / "stages"

    def paths(self, legion_id: str) -> dict:
        d = self.legion_dir(legion_id)
        return {
            "state_home": str(self.state_home),
            "legion_dir": str(d),
            "manifest": str(d / MANIFEST_NAME),
            "stages_dir": str(d / "stages"),
            "goal": str(d / "goal.txt"),
        }

    @contextmanager
    def lock(self, legion_id: str) -> Iterator[None]:
        """Serialize read-modify-write operations for one legion.

        Refuses to create the legion dir: locking a nonexistent legion would
        otherwise leave unbanishable lock-only debris dirs behind.
        """
        d = self.legion_dir(legion_id)
        if not d.is_dir():
            raise SystemExit(f"legion not found: {legion_id}")
        with (d / ".manifest.lock").open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    # -- manifest I/O ----------------------------------------------------- #

    def _atomic_write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / f".{path.name}.{secrets.token_hex(4)}.tmp"
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

    def save(self, manifest: dict) -> None:
        legion_id = manifest.get("id")
        if not legion_id:
            raise SystemExit("legion manifest has no id")
        self._atomic_write(self.manifest_path(legion_id), json.dumps(manifest, indent=2) + "\n")

    def load(self, legion_id: str) -> dict:
        path = self.manifest_path(legion_id)
        if not path.exists():
            if self.legion_dir(legion_id).is_dir():
                raise SystemExit(
                    f"legion {legion_id} has no manifest (lock-only debris); ',palantir banish {legion_id}' removes it"
                )
            raise SystemExit(f"legion not found: {legion_id}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"corrupt legion manifest {path}: {exc}") from exc

    def new_legion(
        self,
        goal: str,
        git_root: Optional[str] = None,
        worktree: str = "",
        session: str = "",
        roles: Optional[dict] = None,
        criteria: Optional[list] = None,
        max_implement_attempts: int = 3,
    ) -> dict:
        """Create and persist a summoned legion; roles pass the diversity guard here."""
        self.init()
        legion_id = secrets.token_hex(4)
        created_at = time.time_ns()
        manifest = {
            "id": legion_id,
            "goal": goal,
            "created_at_unix_ns": created_at,
            "stage_started_at_unix_ns": created_at,
            "stage": "summon",
            "session": session,
            "worktree": worktree,
            "owns_worktree": bool(git_root and worktree and Path(git_root).resolve() != Path(worktree).resolve()),
            "roles": machine.resolve_roles(roles or {}),
            "criteria": machine.validate_criteria(criteria or []),
            "implement_attempts": 0,
            "max_implement_attempts": int(max_implement_attempts),
            "review_blockers": [],
            "wake_observations": {},
            "pending_wakes": [],
            "pending_actions": [],
            "coordinator_transport": {"status": "starting", "last_error": ""},
            "memory_packet_written": False,
        }
        if git_root:
            manifest["git_root"] = str(Path(git_root).resolve())
        d = self.legion_dir(legion_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "goal.txt").write_text(goal, encoding="utf-8")
        self.save(manifest)
        return manifest

    def list_legions(self) -> "list[str]":
        """All legion dirs newest first, including manifest-less debris dirs
        (surfaced as corrupt by summaries) so nothing is invisible to the stone."""
        if not self.legions_dir.exists():
            return []

        def mtime(d: Path) -> float:
            manifest = d / MANIFEST_NAME
            return (manifest if manifest.exists() else d).stat().st_mtime

        dirs = [d for d in self.legions_dir.iterdir() if d.is_dir()]
        return [d.name for d in sorted(dirs, key=mtime, reverse=True)]

    def summaries(self) -> "list[dict]":
        rows = []
        for legion_id in self.list_legions():
            try:
                manifest = self.load(legion_id)
                stage = manifest.get("stage", "")
                if stage not in machine.STAGES:
                    rows.append(
                        {
                            "id": legion_id,
                            "stage": "corrupt",
                            "attention": "corrupt",
                            "goal": manifest.get("goal", ""),
                            "invalid_stage": stage,
                        }
                    )
                else:
                    rows.append(machine.summarize(manifest))
            except SystemExit:
                rows.append({"id": legion_id, "stage": "corrupt", "attention": "corrupt", "goal": ""})
        return rows

    def apply_event(self, legion_id: str, event: dict) -> "tuple[dict, list[dict]]":
        """Locked transition: load -> machine.transition -> save. Returns (manifest, actions)."""
        with self.lock(legion_id):
            manifest = self.load(legion_id)
            previous_stage = manifest.get("stage")
            manifest, actions = machine.transition(manifest, event)
            if manifest.get("stage") != previous_stage:
                manifest["stage_started_at_unix_ns"] = time.time_ns()
            actions = [{**action, "_action_id": secrets.token_hex(8)} for action in actions]
            manifest["pending_actions"] = list(manifest.get("pending_actions") or []) + actions
            self.save(manifest)
        return manifest, actions

    def enqueue_actions(self, legion_id: str, actions: list[dict]) -> list[dict]:
        queued = [{**action, "_action_id": secrets.token_hex(8)} for action in actions]
        with self.lock(legion_id):
            manifest = self.load(legion_id)
            manifest["pending_actions"] = list(manifest.get("pending_actions") or []) + queued
            self.save(manifest)
        return queued

    def acknowledge_action(self, legion_id: str, action_id: str) -> None:
        with self.lock(legion_id):
            manifest = self.load(legion_id)
            pending = list(manifest.get("pending_actions") or [])
            if pending and pending[0].get("_action_id") == action_id:
                manifest["pending_actions"] = pending[1:]
                self.save(manifest)

    def remove(self, legion_id: str) -> None:
        d = self.legion_dir(legion_id)
        if d.exists():
            shutil.rmtree(d)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def _state(args: argparse.Namespace) -> LegionState:
    return LegionState(Path(args.state_home) if args.state_home else None)


def cmd_ls(args: argparse.Namespace) -> int:
    state = _state(args)
    rows = state.summaries()
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    for row in rows:
        flag = f" [{row['attention']}]" if row.get("attention") else ""
        print(f"{row['id']}  {row['stage']:<18}{flag}  {row.get('goal', '')[:60]}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    state = _state(args)
    roles = json.loads(args.roles) if args.roles else {}
    criteria = json.loads(args.criteria) if args.criteria else []
    manifest = state.new_legion(
        goal=args.goal,
        git_root=args.git_root,
        worktree=args.worktree or "",
        session=args.session or "",
        roles=roles,
        criteria=criteria,
        max_implement_attempts=args.max_implement_attempts,
    )
    print(manifest["id"])
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    print(json.dumps(_state(args).load(args.legion_id), indent=2))
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    state = _state(args)
    with state.lock(args.legion_id):
        manifest = state.load(args.legion_id)
        manifest[args.key] = args.value
        state.save(manifest)
    return 0


def cmd_paths(args: argparse.Namespace) -> int:
    print(json.dumps(_state(args).paths(args.legion_id), indent=2))
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    _state(args).remove(args.legion_id)
    return 0


def cmd_remove_debris(args: argparse.Namespace) -> int:
    """Fail-closed removal of a lock-only debris dir (no manifest)."""
    state = _state(args)
    if not state.legion_dir(args.legion_id).is_dir():
        raise SystemExit(f"legion not found: {args.legion_id}")
    if state.manifest_path(args.legion_id).exists():
        raise SystemExit(f"{args.legion_id} has a manifest; use ,palantir banish")
    import supervisor  # lazy: supervisor imports this module at load time

    if supervisor.SupervisorLock(state, args.legion_id).alive():
        raise SystemExit(
            f"{args.legion_id} has a live supervisor; run ,palantir keep-watch {args.legion_id} --stop first"
        )
    state.remove(args.legion_id)
    print(f"removed debris legion dir {args.legion_id}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    state = _state(args)
    problems = []
    for tool in ("tmux", "git", "fzf", "uv"):
        if shutil.which(tool) is None:
            problems.append(f"missing dependency: {tool}")
    state.init()
    if not os.access(state.state_home, os.W_OK):
        problems.append(f"state home not writable: {state.state_home}")
    for line in problems:
        print(line, file=sys.stderr)
    print(f"state home: {state.state_home} ({len(state.list_legions())} legions)")
    return 1 if problems else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legion_state.py", description=",palantir legion manifest I/O")
    parser.add_argument("--state-home", help="override PALANTIR_STATE_HOME")
    sub = parser.add_subparsers(dest="command", required=True)

    ls_p = sub.add_parser("ls", help="list legions (newest first)")
    ls_p.add_argument("--json", action="store_true")
    ls_p.set_defaults(func=cmd_ls)

    new_p = sub.add_parser("new", help="create a summoned legion")
    new_p.add_argument("--goal", required=True)
    new_p.add_argument("--git-root")
    new_p.add_argument("--worktree")
    new_p.add_argument("--session")
    new_p.add_argument("--roles", help="JSON: role -> {harness, model, family?}")
    new_p.add_argument("--criteria", help="JSON: [{text, check, status}]")
    new_p.add_argument("--max-implement-attempts", type=int, default=3)
    new_p.set_defaults(func=cmd_new)

    show_p = sub.add_parser("show", help="print one legion manifest")
    show_p.add_argument("legion_id")
    show_p.set_defaults(func=cmd_show)

    set_p = sub.add_parser("set", help="set one string key on the manifest")
    set_p.add_argument("legion_id")
    set_p.add_argument("key")
    set_p.add_argument("value")
    set_p.set_defaults(func=cmd_set)

    paths_p = sub.add_parser("paths", help="print legion paths as JSON")
    paths_p.add_argument("legion_id")
    paths_p.set_defaults(func=cmd_paths)

    remove_p = sub.add_parser("remove", help=argparse.SUPPRESS)
    remove_p.add_argument("legion_id")
    remove_p.set_defaults(func=cmd_remove)

    remove_debris_p = sub.add_parser("remove-debris", help=argparse.SUPPRESS)
    remove_debris_p.add_argument("legion_id")
    remove_debris_p.set_defaults(func=cmd_remove_debris)

    doctor_p = sub.add_parser("doctor", help="check dependencies and state home")
    doctor_p.set_defaults(func=cmd_doctor)

    return parser


def main(argv: "Optional[list[str]]" = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
