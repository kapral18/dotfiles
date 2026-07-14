#!/usr/bin/env python3
"""Per-legion deterministic supervisor for ,palantir.

One process per legion (fcntl-locked; a second start is refused). Each tick it:

  1. reads the legion manifest (machine truth, never pane scraping for state)
  2. consumes any ``stages/<stage>.result.json`` handshake a role agent wrote,
     feeds it to ``machine.transition``, and executes the returned actions
  3. runs ``verify`` itself: every acceptance criterion's ``check`` command from
     the legion worktree (exit 0 = green) -- criteria are machine-checked,
     never agent-judged
  4. surfaces actionable conditions to the coordinator pane exactly once per
     unresolved condition (``machine.dedupe_wake``), re-surfacing only after a
     resolve+recur

The supervisor does no model inference and never publishes anything; it is the
spine the coordinator agent's judgment hangs off.

CLI (stdlib only):

  supervisor.py [--state-home P] run LEGION_ID [--once] [--interval N]
  supervisor.py [--state-home P] verify LEGION_ID     (one verify pass, prints report)
  supervisor.py [--state-home P] status LEGION_ID     (lock holder + stage)
  supervisor.py [--state-home P] stop LEGION_ID
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import legion_state
import machine
import palantir_config
import panes

CHECK_TIMEOUT_SECS = 600


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


class SupervisorLock:
    """Single supervisor per legion; same fcntl discipline as the state lock."""

    def __init__(self, state: legion_state.LegionState, legion_id: str) -> None:
        self.lock_dir = state.legion_dir(legion_id) / ".supervisor.lock"
        self.lock_file = self.lock_dir / "lock"
        self.pid_file = self.lock_dir / "pid"
        self._handle: Any = None

    def holder_pid(self) -> "Optional[int]":
        try:
            return int(self.pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def alive(self) -> bool:
        if not self.lock_file.is_file():
            return False
        with self.lock_file.open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return False

    def acquire(self) -> None:
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        handle = self.lock_file.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise RuntimeError(f"supervisor already running (pid {self.holder_pid() or 'unknown'})") from exc
        self._handle = handle
        self.pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")

    def release(self) -> None:
        if self._handle is None:
            return
        if self.holder_pid() == os.getpid():
            self.pid_file.unlink(missing_ok=True)
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None

    def stop(self) -> bool:
        pid = self.holder_pid()
        if not self.alive():
            return False
        if not pid or not _pid_alive(pid):
            raise RuntimeError("supervisor lock has no live holder pid; refusing to signal")
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not _pid_alive(pid):
                return True
            time.sleep(0.05)
        os.kill(pid, signal.SIGKILL)
        return True


def run_criteria(manifest: dict) -> dict:
    """Machine-run verify: execute every criterion check from the worktree.

    Returns a ``criteria_report`` event. A criterion without a ``check``
    command is a judgment criterion: it stays for the human and does not block
    machine verify, but is reported.
    """
    worktree = manifest.get("worktree") or "."
    failures: "list[dict]" = []
    checked = 0
    for criterion in manifest.get("criteria") or []:
        check = criterion.get("check")
        if not check:
            continue
        checked += 1
        try:
            proc = subprocess.run(
                ["bash", "-c", check],
                cwd=worktree,
                capture_output=True,
                text=True,
                timeout=CHECK_TIMEOUT_SECS,
                check=False,
            )
            code = proc.returncode
            tail = (proc.stdout + proc.stderr).strip()[-400:]
        except subprocess.TimeoutExpired:
            code, tail = 124, f"timed out after {CHECK_TIMEOUT_SECS}s"
        criterion["status"] = "green" if code == 0 else "red"
        if code != 0:
            failures.append({"text": criterion.get("text", ""), "check": check, "exit": code, "output": tail})
    return {"kind": "criteria_report", "green": not failures, "failures": failures, "checked": checked}


class Supervisor:
    def __init__(self, state: legion_state.LegionState, legion_id: str, config: "Optional[dict]" = None) -> None:
        self.state = state
        self.legion_id = legion_id
        self.config = config or palantir_config.load()
        self.lock = SupervisorLock(state, legion_id)
        self.log_file = state.legion_dir(legion_id) / ".supervisor.log"
        self._stop = False

    def log(self, message: str) -> None:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")

    # -- actions ----------------------------------------------------------- #

    def execute(self, actions: "list[dict]") -> None:
        for action in actions:
            kind = action.get("kind")
            if kind == "start_stage":
                try:
                    info = panes.start_stage(self.state, self.legion_id, action["stage"], action.get("brief") or {})
                except panes.PaneError as exc:
                    self.log(f"start_stage {action['stage']} deferred: {exc}")
                    continue
                self.log(f"start_stage {action['stage']} injected={info['injected']}")
            elif kind == "run_verify":
                self.verify_pass()
            elif kind == "wake_coordinator":
                self.surface(action.get("event") or {})
            elif kind == "route_memory":
                packet = action.get("packet") or {}
                self.state._atomic_write(
                    self.state.legion_dir(self.legion_id) / "memory-routing.json",
                    json.dumps(packet, indent=2) + "\n",
                )
                delivered = panes.wake_coordinator(
                    self.state, self.legion_id, {"kind": "route_memory", "packet": packet}
                )
                self.log(f"route_memory delivered={delivered}")
            else:
                self.log(f"unknown action {kind!r} ignored")

    def surface(self, event: dict) -> None:
        """Deliver one coordinator wake, deduplicated per unresolved condition."""
        key = event.get("kind", "event")
        fingerprint = json.dumps(event, sort_keys=True)
        with self.state.lock(self.legion_id):
            manifest = self.state.load(self.legion_id)
            observations, enqueue = machine.dedupe_wake(manifest.get("wake_observations") or {}, key, fingerprint)
            manifest["wake_observations"] = observations
            self.state.save(manifest)
        if not enqueue:
            return
        delivered = panes.wake_coordinator(self.state, self.legion_id, event)
        self.log(f"wake {key} delivered={delivered}")
        if not delivered:
            # Blocked pane: drop the observation so the next tick retries.
            with self.state.lock(self.legion_id):
                manifest = self.state.load(self.legion_id)
                manifest["wake_observations"] = machine.resolve_wake(manifest.get("wake_observations") or {}, key)
                self.state.save(manifest)

    def verify_pass(self) -> dict:
        # Run the (potentially long) criteria checks without holding the
        # manifest lock so answer/grant/banish dispatches never block on a
        # slow check; re-lock only to persist the per-criterion status flips.
        manifest = self.state.load(self.legion_id)
        report = run_criteria(manifest)
        with self.state.lock(self.legion_id):
            latest = self.state.load(self.legion_id)
            latest["criteria"] = manifest.get("criteria") or []
            self.state.save(latest)
        self.log(f"verify checked={report['checked']} green={report['green']}")
        try:
            _manifest, actions = self.state.apply_event(self.legion_id, report)
        except machine.MachineError as exc:
            # Stage moved while checks ran (e.g. a concurrent banish); the
            # report is stale, not fatal.
            self.log(f"criteria_report refused: {exc}")
            return report
        self.execute(actions)
        return report

    def dispatch_event(self, event: dict) -> dict:
        """Apply a human/control event and execute every resulting runtime action."""
        if event.get("kind") in {"grant_clear", "banish"} and os.environ.get("PALANTIR_AGENT_ROLE"):
            raise machine.MachineError(
                f"{event['kind']} is human-only (agent role: {os.environ['PALANTIR_AGENT_ROLE']})"
            )
        manifest, actions = self.state.apply_event(self.legion_id, event)
        self.execute(actions)
        return manifest

    # -- tick -------------------------------------------------------------- #

    def consume_stage_result(self, manifest: dict) -> bool:
        """Feed a completed stage handshake file into the machine. True if consumed."""
        stage = manifest.get("stage", "")
        if stage not in machine.ROLE_BY_STAGE:
            return False
        result_path = self.state.stages_dir(self.legion_id) / f"{stage}.result.json"
        if not result_path.is_file():
            return False
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.log(f"unreadable {result_path.name}: {exc}")
            return False
        history = {**payload, "consumed_at_unix_ns": time.time_ns()}
        with (self.state.stages_dir(self.legion_id) / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(history, ensure_ascii=False) + "\n")
        result_path.unlink(missing_ok=True)
        if payload.get("kind") == "question":
            event = {"kind": "question", "role": stage, "text": payload.get("text", "")}
        else:
            payload["kind"] = "stage_result"
            payload.setdefault("stage", stage)
            event = payload
        try:
            _manifest, actions = self.state.apply_event(self.legion_id, event)
        except machine.MachineError as exc:
            self.log(f"transition refused for {stage} result: {exc}")
            self.surface({"kind": "transition_refused", "stage": stage, "error": str(exc)})
            return False
        self.execute(actions)
        return True

    def tick(self) -> None:
        manifest = self.state.load(self.legion_id)
        stage = manifest.get("stage", "")
        if stage == "summon":
            # Entry edge: coordinator up, then triage. No stage_result needed.
            try:
                panes.start_coordinator(self.state, self.legion_id)
            except panes.PaneError as exc:
                self.log(f"coordinator launch deferred: {exc}")
            with self.state.lock(self.legion_id):
                manifest = self.state.load(self.legion_id)
                manifest["stage"] = "triage"
                self.state.save(manifest)
            self.execute([{"kind": "start_stage", "stage": "triage", "role": "triage", "brief": {}}])
            return
        if stage in machine.TERMINAL_STAGES:
            self._stop = True
            return
        try:
            panes.start_coordinator(self.state, self.legion_id)
        except panes.PaneError as exc:
            self.log(f"coordinator delivery retry deferred: {exc}")
        if self.consume_stage_result(manifest):
            return
        # Re-surface the parked/cleared condition every tick: dedupe_wake makes
        # it once-per-condition, and a delivery that hit a blocked coordinator
        # pane (dropped observation) is retried here.
        wake = machine.attention_event(manifest)
        if wake is not None:
            self.surface(wake)
        if stage in machine.ROLE_BY_STAGE:
            brief_path = self.state.stages_dir(self.legion_id) / f"{stage}.brief.json"
            if brief_path.is_file():
                try:
                    brief = json.loads(brief_path.read_text(encoding="utf-8"))
                    info = panes.start_stage(self.state, self.legion_id, stage, brief)
                    self.log(f"retry_stage {stage} injected={info['injected']}")
                except (OSError, json.JSONDecodeError, panes.PaneError) as exc:
                    self.log(f"retry_stage {stage} deferred: {exc}")

    def run(self, once: bool = False, interval: "Optional[int]" = None) -> int:
        try:
            self.lock.acquire()
        except RuntimeError as exc:
            print(f"palantir: {exc}", file=sys.stderr)
            return 1
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "_stop", True))
        pause = interval if interval is not None else int(self.config.get("watch_interval_secs", 20))
        try:
            while not self._stop:
                try:
                    self.tick()
                except Exception as exc:  # noqa: BLE001 -- the supervisor must outlive one bad tick
                    self.log(f"tick failed: {type(exc).__name__}: {exc}")
                if once:
                    break
                time.sleep(max(1, pause))
        finally:
            self.lock.release()
        return 0


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = argparse.ArgumentParser(prog="supervisor.py", description=",palantir per-legion supervisor")
    parser.add_argument("--state-home")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("legion_id")
    run_p.add_argument("--once", action="store_true")
    run_p.add_argument("--interval", type=int)

    for name in ("verify", "status", "stop"):
        p = sub.add_parser(name)
        p.add_argument("legion_id")

    dispatch_p = sub.add_parser("dispatch")
    dispatch_p.add_argument("legion_id")
    dispatch_p.add_argument("--json-event", required=True)

    args = parser.parse_args(argv)
    state = legion_state.LegionState(Path(args.state_home) if args.state_home else None)

    if args.command == "run":
        return Supervisor(state, args.legion_id).run(once=args.once, interval=args.interval)
    if args.command == "verify":
        report = Supervisor(state, args.legion_id).verify_pass()
        print(json.dumps(report, indent=2))
        return 0 if report["green"] else 1
    if args.command == "status":
        lock = SupervisorLock(state, args.legion_id)
        manifest = state.load(args.legion_id)
        print(
            json.dumps(
                {
                    "stage": manifest.get("stage"),
                    "supervisor_alive": lock.alive(),
                    "supervisor_pid": lock.holder_pid(),
                }
            )
        )
        return 0
    if args.command == "stop":
        stopped = SupervisorLock(state, args.legion_id).stop()
        print("stopped" if stopped else "not running")
        return 0
    if args.command == "dispatch":
        try:
            event = json.loads(args.json_event)
            manifest = Supervisor(state, args.legion_id).dispatch_event(event)
        except (json.JSONDecodeError, machine.MachineError) as exc:
            raise SystemExit(f"dispatch refused: {exc}") from exc
        print(json.dumps({"stage": manifest["stage"]}))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
