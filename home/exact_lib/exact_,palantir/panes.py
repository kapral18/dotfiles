#!/usr/bin/env python3
"""Interactive agent pane transport for ,palantir.

One legion is one tmux session; its organisation is windows and panes:

    window 0 ``command``   pane 0 = coordinator agent, pane 1 = supervisor
    window per active stage (``triage``, ``implement``, ...) with the role's
    interactive agent in pane 0

Every role runs a real interactive harness CLI (``copilot``, ``claude``,
``pi``, ``opencode``) so both the supervisor and the human can inject
follow-up turns mid-flight. All injects are composer-guarded: only a pane whose
composer verdict is ``empty`` (idle prompt) takes keys; every other verdict
blocks and the caller retries on its own cadence. The structured handshake back
is file-based: a role brief instructs the agent to write
``stages/<stage>.result.json`` when done, which keeps the flow observable in
tmux while staying maximally detached.

CLI (stdlib only):

  panes.py [--state-home P] start-stage LEGION_ID --stage S [--brief JSON]
  panes.py [--state-home P] start-coordinator LEGION_ID
  panes.py [--state-home P] send-word LEGION_ID --window W --text T [--force-wait N]
  panes.py [--state-home P] pane-verdict LEGION_ID --window W
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import time
from pathlib import Path
from typing import Optional

import composer
import legion_state
import palantir_config

COMMAND_WINDOW = "command"

# Launch argv per harness. Each starts an interactive session in the pane's
# cwd (the legion worktree); the role brief arrives as the first injected turn.
# Roles run unattended, so each harness gets its own full-autonomy flag; the
# human boundary is the machine's cleared_for_human gate, not per-tool prompts.
HARNESS_ARGV = {
    "copilot": ["copilot", "--allow-all"],
    "claude": ["claude", "--dangerously-skip-permissions"],
    "pi": ["pi", "--approve"],
    "opencode": ["opencode"],
}

HARNESS_ENV = {
    # Copilot checks this environment variable before CLI flags are parsed.
    # Without it, every fresh legion worktree stops at the folder-trust dialog.
    "copilot": {"COPILOT_ALLOW_ALL": "true"},
}


# Shells a dead harness pane falls back to; seeing one of these as the pane's
# current command means the agent is gone and the pane must not take a brief.
SHELL_COMMANDS = frozenset({"fish", "zsh", "bash", "sh", "dash", "nu", "-fish", "-zsh", "-bash", "-sh"})


class PaneError(RuntimeError):
    pass


def harness_argv(harness: str, model: str = "") -> "list[str]":
    argv = HARNESS_ARGV.get(harness)
    if argv is None:
        raise PaneError(f"unknown harness {harness!r}; known: {sorted(HARNESS_ARGV)}")
    argv = list(argv)
    if model:
        argv.extend(["--model", model])
    return argv


def harness_command(harness: str, model: str = "", role: str = "") -> str:
    env = HARNESS_ENV.get(harness, {})
    parts = [f"{key}={shlex.quote(value)}" for key, value in env.items()]
    if role:
        parts.append(f"PALANTIR_AGENT_ROLE={shlex.quote(role)}")
    parts.extend(shlex.quote(part) for part in harness_argv(harness, model))
    return " ".join(parts)


def session_name(legion_id: str) -> str:
    return f"legion-{legion_id}"


def pane_target(session: str, window: str) -> str:
    proc = composer.run_tmux("list-panes", "-t", f"={session}:{window}", "-F", "#{pane_id}")
    pane_id = proc.stdout.splitlines()[0].strip() if proc.returncode == 0 and proc.stdout else ""
    if not pane_id:
        raise PaneError(f"no pane in {session}:{window}: {proc.stderr.strip()}")
    return pane_id


def window_exists(session: str, window: str) -> bool:
    proc = composer.run_tmux("list-windows", "-t", f"={session}", "-F", "#{window_name}")
    if proc.returncode != 0:
        return False
    return window in proc.stdout.split()


def ensure_window(session: str, window: str, cwd: str) -> str:
    """Create the named window when missing; return the pane target."""
    if not window_exists(session, window):
        proc = composer.run_tmux("new-window", "-d", "-t", f"={session}", "-n", window, "-c", cwd)
        if proc.returncode != 0:
            raise PaneError(f"cannot create window {window!r} in {session}: {proc.stderr.strip()}")
    return pane_target(session, window)


def pane_verdict(session: str, window: str) -> str:
    """Composer verdict for a role pane: empty | pending | busy | unknown."""
    try:
        text = composer.capture(pane_target(session, window), composer.CAPTURE_LINES)
    except (PaneError, RuntimeError):
        return "unknown"
    verdict, _reason = composer.classify(text)
    return verdict


def inject_when_idle(session: str, window: str, text: str, wait_secs: int = 30, interval: float = 1.0) -> bool:
    """Composer-guarded literal inject. Returns False when the pane never idles.

    Fail-safe: only the ``empty`` verdict authorizes keys; ``busy``/``pending``/
    ``unknown`` all block. The text is sent literally (``send-keys -l``) so tmux
    never interprets it, then a single Enter.
    """
    try:
        target = pane_target(session, window)
    except PaneError:
        return False
    deadline = time.monotonic() + wait_secs
    while True:
        if pane_verdict(session, window) == "empty":
            proc = composer.run_tmux("send-keys", "-t", target, "-l", text)
            if proc.returncode != 0:
                return False
            return composer.run_tmux("send-keys", "-t", target, "Enter").returncode == 0
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def pane_current_command(session: str, window: str) -> str:
    proc = composer.run_tmux("display-message", "-p", "-t", f"={session}:{window}", "#{pane_current_command}")
    return proc.stdout.strip() if proc.returncode == 0 else ""


def launch_agent(
    session: str,
    window: str,
    cwd: str,
    harness: str,
    model: str = "",
    role: str = "",
    marker_path: "Path | None" = None,
    settle_secs: int = 10,
    delivered_path: "Path | None" = None,
) -> str:
    """Start the role's interactive harness in its window; return the target."""
    target = ensure_window(session, window, cwd)
    if marker_path is not None and marker_path.is_file():
        # The marker says the harness was launched, but if the pane has fallen
        # back to a plain shell *and* the composer is empty, the agent exited.
        # A shell-looking current command alone is insufficient during harness
        # startup and must not erase a live marker.
        if pane_current_command(session, window) not in SHELL_COMMANDS:
            return target
        if pane_verdict(session, window) != "empty":
            return target
        marker_path.unlink(missing_ok=True)
        if delivered_path is not None:
            delivered_path.unlink(missing_ok=True)
    deadline = time.monotonic() + settle_secs
    while pane_verdict(session, window) != "empty":
        if time.monotonic() >= deadline:
            raise PaneError(f"{session}:{window} did not become idle before harness launch")
        time.sleep(0.2)
    cmd = harness_command(harness, model, role)
    proc = composer.run_tmux("send-keys", "-t", target, "-l", cmd)
    if proc.returncode != 0:
        raise PaneError(f"cannot launch {harness} in {target}: {proc.stderr.strip()}")
    proc = composer.run_tmux("send-keys", "-t", target, "C-m")
    if proc.returncode != 0:
        raise PaneError(f"cannot submit {harness} in {target}: {proc.stderr.strip()}")
    if marker_path is not None:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(
            json.dumps({"target": target, "harness": harness, "model": model}, indent=2) + "\n",
            encoding="utf-8",
        )
    return target


def stage_brief_text(legion: dict, stage: str, brief: dict, result_path: Path) -> str:
    """The first turn injected into a role pane: goal, brief, handshake contract."""
    role = stage.replace("_", "-")
    lines = [
        f"You are the {role} role of legion {legion['id']} working toward: {legion.get('goal', '')}.",
        f"Stage brief: {json.dumps(brief, ensure_ascii=False)}." if brief else "Stage brief: none.",
        "Work autonomously in this worktree. Ask nothing here; when a human decision is genuinely required, "
        f'write {{"kind": "question", "text": "..."}} to {result_path} and stop.',
        "When the stage is done, write JSON to "
        f"{result_path} with fields: kind=stage_result, stage={stage}, verdict, summary"
        + (", blockers (list; empty when none survive refutation)" if stage == "adversarial_review" else "")
        + (". Verdict is one of implement|diagnose|reject." if stage == "triage" else ". Verdict is done."),
    ]
    if stage == "implement":
        lines.append(
            "The deterministic supervisor exclusively owns the final acceptance run. "
            "Run focused development checks as needed, but do not run the full acceptance suite or claim its final status."
        )
    if stage == "adversarial_review":
        lines.append(
            "Audit the implementation and every acceptance check for observability; a vacuous check is a blocker even "
            "when a manually corrected command passes. The deterministic supervisor owns verification, so do not rerun "
            "the full acceptance suite."
        )
    return " ".join(lines)


def coordinator_brief_text(legion: dict) -> str:
    return (
        f"You are the coordinator of legion {legion['id']}: {legion.get('goal', '')}. "
        "A deterministic supervisor owns lifecycle and safety; you own judgment calls. "
        "Structured events arrive here as [palantir] lines: triage rejections, review blockers, "
        "verify failures, budget exhaustion, questions, and cleared_for_human. "
        "For each event, decide and act with the smallest correct step (answer via "
        "',palantir answer', send word via ',palantir send-word', or summarize for the human). "
        "Do not poll role panes, wait on result files, inspect progress, run stage checks, use tmux send-keys, "
        "or kill or restart role agents; the deterministic supervisor owns all lifecycle and progress monitoring. "
        "After handling one event, finish the turn and remain idle until the supervisor sends another event. "
        "Never call `,palantir grant` or `,palantir banish`; those are human-only controls. "
        "Never call `,palantir summon`; one legion per effort, no nested legions. "
        "Never publish (PRs, comments, pushes) without explicit human approval."
    )


def _brief_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def start_stage(state: legion_state.LegionState, legion_id: str, stage: str, brief: dict) -> dict:
    """Create the stage window, launch its role agent, inject the brief."""
    legion = state.load(legion_id)
    session = legion.get("session") or session_name(legion_id)
    role = stage.replace("_", "-")
    spec = (legion.get("roles") or {}).get(role) or {}
    harness = spec.get("harness", "copilot")
    model = spec.get("model", "")
    stages_dir = state.stages_dir(legion_id)
    stages_dir.mkdir(parents=True, exist_ok=True)
    result_path = stages_dir / f"{stage}.result.json"
    text = stage_brief_text(legion, stage, brief, result_path)
    delivered_path = stages_dir / f"{stage}.delivered"
    digest = _brief_digest(text)
    (stages_dir / f"{stage}.brief.json").write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")

    settle_secs = int(palantir_config.load().get("inject_settle_secs", 10))
    target = launch_agent(
        session,
        stage,
        legion.get("worktree", "") or str(Path.home()),
        harness,
        model,
        role=role,
        marker_path=stages_dir / f"{stage}.agent.json",
        settle_secs=settle_secs,
        delivered_path=delivered_path,
    )
    # Already-delivered identical brief: leave the pane (and any result the
    # role just wrote) untouched; this is the supervisor's retry path.
    if delivered_path.is_file() and delivered_path.read_text(encoding="utf-8").strip() == digest:
        return {"target": target, "injected": False, "already_delivered": True, "result_path": str(result_path)}
    result_path.unlink(missing_ok=True)
    injected = inject_when_idle(session, stage, text, wait_secs=60)
    if injected:
        delivered_path.write_text(f"{digest}\n", encoding="utf-8")
    return {"target": target, "injected": injected, "result_path": str(result_path)}


def start_coordinator(state: legion_state.LegionState, legion_id: str) -> dict:
    legion = state.load(legion_id)
    session = legion.get("session") or session_name(legion_id)
    spec = (legion.get("roles") or {}).get("coordinator") or {}
    settle_secs = int(palantir_config.load().get("inject_settle_secs", 10))
    delivered_path = state.legion_dir(legion_id) / "coordinator.delivered"
    target = launch_agent(
        session,
        COMMAND_WINDOW,
        legion.get("worktree", "") or str(Path.home()),
        spec.get("harness", "copilot"),
        spec.get("model", ""),
        role="coordinator",
        marker_path=state.legion_dir(legion_id) / "coordinator.agent.json",
        settle_secs=settle_secs,
        delivered_path=delivered_path,
    )
    text = coordinator_brief_text(legion)
    digest = _brief_digest(text)
    if delivered_path.is_file() and delivered_path.read_text(encoding="utf-8").strip() == digest:
        return {"target": target, "injected": True}
    injected = inject_when_idle(session, COMMAND_WINDOW, text, wait_secs=60)
    if not injected:
        raise PaneError(f"{session}:{COMMAND_WINDOW} did not become idle for coordinator brief")
    delivered_path.write_text(f"{digest}\n", encoding="utf-8")
    return {"target": target, "injected": True}


def wake_coordinator(state: legion_state.LegionState, legion_id: str, event: dict) -> bool:
    legion = state.load(legion_id)
    session = legion.get("session") or session_name(legion_id)
    line = f"[palantir] {json.dumps(event, ensure_ascii=False)}"
    return inject_when_idle(session, COMMAND_WINDOW, line, wait_secs=20)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = argparse.ArgumentParser(prog="panes.py", description=",palantir pane transport")
    parser.add_argument("--state-home")
    sub = parser.add_subparsers(dest="command", required=True)

    ss = sub.add_parser("start-stage")
    ss.add_argument("legion_id")
    ss.add_argument("--stage", required=True)
    ss.add_argument("--brief", default="{}")

    sc = sub.add_parser("start-coordinator")
    sc.add_argument("legion_id")

    nd = sub.add_parser("send-word")
    nd.add_argument("legion_id")
    nd.add_argument("--window", required=True)
    nd.add_argument("--text", required=True)
    nd.add_argument("--force-wait", type=int, default=30)

    pv = sub.add_parser("pane-verdict")
    pv.add_argument("legion_id")
    pv.add_argument("--window", required=True)

    args = parser.parse_args(argv)
    state = legion_state.LegionState(Path(args.state_home) if args.state_home else None)

    if args.command == "start-stage":
        print(json.dumps(start_stage(state, args.legion_id, args.stage, json.loads(args.brief))))
        return 0
    if args.command == "start-coordinator":
        print(json.dumps(start_coordinator(state, args.legion_id)))
        return 0
    if args.command == "send-word":
        legion = state.load(args.legion_id)
        session = legion.get("session") or session_name(args.legion_id)
        ok = inject_when_idle(session, args.window, args.text, wait_secs=args.force_wait)
        print("injected" if ok else "blocked")
        return 0 if ok else 1
    if args.command == "pane-verdict":
        legion = state.load(args.legion_id)
        session = legion.get("session") or session_name(args.legion_id)
        print(pane_verdict(session, args.window))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
