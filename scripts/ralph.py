#!/usr/bin/env python3
"""Opinionated Ralph orchestrator: planner -> executor -> reviewer -> re-reviewer loop.

Usage:
    ralph.py go --goal GOAL [--workspace PATH] [--plan-only] [--detach|--foreground] [--subprocess] [--json]
    ralph.py runner RUN_ID                      # internal: the resumable state-machine loop
    ralph.py resume RUN_ID                      # re-launch the runner if it died; no-op if alive
    ralph.py replan RUN_ID                      # queue a replan; runner picks it up next loop
    ralph.py dry-run --goal GOAL [--memory-query QUERY]
    ralph.py status [RUN_ID] [--json]
    ralph.py runs [--json] [--limit N] [--workspace PATH] [--session NAME]
    ralph.py role RUN_ID ROLE [--json]
    ralph.py items [--limit N]
    ralph.py preview RUN_ID [ROLE] [--mode summary|tail]
    ralph.py dashboard [RUN_ID]
    ralph.py tail [RUN_ID] [--role ROLE] [--lines N]
    ralph.py attach [RUN_ID] [--role ROLE]
    ralph.py verify [RUN_ID] [--json]
    ralph.py control RUN_ID --role ROLE --action takeover|dirty|resume|auto [--json]
    ralph.py kill RUN_ID [--role ROLE]
    ralph.py rm RUN_ID|--all-completed [--keep-learnings]
    ralph.py statusline
    ralph.py doctor

Roles config: ~/.config/ralph/roles.json (override with $RALPH_ROLES_CONFIG)
Prompts:      ~/.config/ralph/prompts/{planner,executor,reviewer,re_reviewer}.md

Resumable state machine
-----------------------

A run's iteration loop is a state machine driven entirely by the manifest on
disk. Each transition writes the manifest before performing the side effect, so
a runner that dies at any point can be re-launched and will resume at the
earliest pending phase without re-doing completed work.

Per-iteration phases (manifest.iterations[i].phase):

    iter_pending -> exec_pending -> exec_running -> exec_done
                                                       |
                                  review_pending -> review_running -> review_done
                                                                            |
                                rereview_pending -> rereview_running -> rereview_done
                                                                            |
                                                                       iter_decided
                                                                          | | |
                                                                        pass / needs_iteration / block

Run-level liveness:

    manifest.runner = {
        "pid": <int>,            # PID of the currently-running runner process
        "host": <hostname>,      # for shared state-dirs across machines
        "started_at": <iso8601>, # when the current runner started
        "heartbeat_at": <iso>,   # updated on every manifest save
        "alive": <bool>,         # set False on clean exit
    }

The runner takes an exclusive flock on `<run_dir>/runner.pid` for its full
lifetime. `,ralph resume RUN_ID` no-ops if the lock is held; otherwise it
re-launches `,ralph runner RUN_ID` detached.

Role-pane idempotency:

    Each role spawn is named `<short-rid>:<role>-<n>` in the run's tmux session
    (`ralph-<short-rid>`). Spawn logic on (re)entry to a *_running phase:

      - pane alive  + output.txt has RALPH_DONE  -> consume cached output, advance
      - pane alive  + output.txt incomplete       -> attach + wait
      - pane gone   + output.txt has RALPH_DONE  -> consume cached output, advance
      - pane gone   + output.txt incomplete       -> re-spawn into same window name

Artifact writes are atomic at file granularity (manifest.json, progress.jsonl,
verdicts.jsonl, decisions.jsonl, iterations/<n>/<role>/output.txt). Readers
(dashboard, ralph-tui) get a consistent snapshot at every fsnotify tick.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ai_kb import CAPSULE_KINDS, CAPSULE_SCOPES, KnowledgeBase

DONE_MARKER = "RALPH_DONE"
REPLAN_MARKER = "RALPH_REPLAN"
QUESTIONS_MARKER = "RALPH_QUESTIONS"
LEARNING_PREFIX = "LEARNING:"


def _kind_for_role(role: str | None) -> str:
    """Map a role identifier (e.g. `planner-2`, `re_reviewer-1`) to
    the default capsule kind for facts that role emits.

    The mapping is opinionated so role authors don't have to think
    about taxonomy when emitting `LEARNING:` lines:

      planner / executor / reflector -> fact (general observation)
      reviewer                        -> gotcha (defects observed)
      re_reviewer                     -> principle (verification heuristic)

    The reflector role (Phase 4) overrides this when it emits
    structured JSON capsules with explicit kinds.
    """
    base = (role or "").split("-")[0]
    if base == "reviewer":
        return "gotcha"
    if base == "re_reviewer":
        return "principle"
    # planner, executor, reflector, unknown -> fact
    return "fact"


ANCHOR_PREFIX = "ANCHOR:"
SELF_CHECK_PREFIX = "SELF_CHECK:"
ANCHOR_LOOKAHEAD_LINES = 30  # role outputs may have leading harness chatter; scan first N lines for ANCHOR
CONTROL_ACTIONS = ("takeover", "dirty", "resume", "auto")
CONTROL_STATE_BY_ACTION = {
    "takeover": "manual_control",
    "dirty": "dirty_control",
    "resume": "resume_requested",
    "auto": "automated",
}
CONTROL_BLOCKING_STATES = ("manual_control", "dirty_control", "resume_requested")
TERMINAL_STATUSES = ("completed", "needs_human", "failed", "killed")
SUPERVISABLE_STATUSES = ("running", "needs_verification")
ORCHESTRATOR_PHASES = (
    "planning",
    "executing",
    "reviewing",
    "rereviewing",
    "replanning",
    "blocked",
    "done",
    "failed",
)

# Per-iteration phase tags (manifest.iterations[i].phase). The state machine
# advances strictly left-to-right within an iteration; a kill or process death
# leaves the iteration parked at whichever phase was current when the manifest
# was last saved, and the runner resumes from that phase on next launch.
#
# A role's "running vs done" is inferred from its output.txt and from the
# parent manifest's roles[] cache, so we do not need separate _running and
# _done phases — the phase name names the *currently active role*.
ITER_PHASE_PENDING = "pending"
ITER_PHASE_EXEC = "exec"
ITER_PHASE_REVIEW = "review"
ITER_PHASE_RERVIEW = "rereview"
ITER_PHASE_DECIDED = "decided"

ITER_PHASES_TERMINAL = (ITER_PHASE_DECIDED,)
ITER_PHASES_ROLE_RUNNING = (
    ITER_PHASE_EXEC,
    ITER_PHASE_REVIEW,
    ITER_PHASE_RERVIEW,
)
# Map per-iteration phase to the human-readable top-level `manifest.phase`.
# This is just a label for dashboards; the state machine is driven by the
# per-iteration phase, not by the top-level string.
_ITER_PHASE_TOP_NAME: dict[str, str] = {
    ITER_PHASE_EXEC: "executing",
    ITER_PHASE_REVIEW: "reviewing",
    ITER_PHASE_RERVIEW: "rereviewing",
}

# Workflow registry: each workflow declares the ordered list of per-iteration
# phases the state machine drives. The current "feature" loop is one of four
# templates; the others diverge in shape:
#
#   feature  : full ladder; default coding workflow.
#   bugfix   : same shape as feature; the planner prompt seeds a test-first
#              executor task. Loop-level behavior is identical.
#   review   : single reviewer pass over an existing artifact; no executor,
#              no re_reviewer. Verdict drives completion in one iteration.
#   research : planner -> executor (read-only investigator) -> reviewer.
#              No re_reviewer; reviewer's verdict is final.
#
# Adding a new workflow = adding a row here and (optionally) tightening the
# planner prompt to teach it about the new shape.
WORKFLOWS: dict[str, dict[str, Any]] = {
    "feature": {
        "iter_phases": (ITER_PHASE_EXEC, ITER_PHASE_REVIEW, ITER_PHASE_RERVIEW),
        "description": "planner -> executor -> reviewer -> re_reviewer (loop until pass)",
    },
    "bugfix": {
        "iter_phases": (ITER_PHASE_EXEC, ITER_PHASE_REVIEW, ITER_PHASE_RERVIEW),
        "description": "feature ladder with test-first executor seed",
    },
    "review": {
        "iter_phases": (ITER_PHASE_REVIEW,),
        "description": "single reviewer pass over an existing artifact (no executor, no re_reviewer)",
    },
    "research": {
        "iter_phases": (ITER_PHASE_EXEC, ITER_PHASE_REVIEW),
        "description": "planner -> executor (read-only investigator) -> reviewer (no re_reviewer)",
    },
}
DEFAULT_WORKFLOW = "feature"


def workflow_phases(workflow: str | None) -> tuple[str, ...]:
    """Return the iteration phase tuple for a workflow; falls back to feature."""
    return WORKFLOWS.get(workflow or DEFAULT_WORKFLOW, WORKFLOWS[DEFAULT_WORKFLOW])["iter_phases"]


def next_iter_phase(current: str, workflow: str | None) -> str:
    """Return the next iteration phase for `current` in `workflow`, or DECIDED if last.

    `current=ITER_PHASE_PENDING` returns the workflow's first phase.
    Unknown phases (e.g. legacy values) collapse to DECIDED so the loop
    finalizes safely instead of looping forever.
    """
    phases = workflow_phases(workflow)
    if current == ITER_PHASE_PENDING:
        return phases[0] if phases else ITER_PHASE_DECIDED
    try:
        idx = phases.index(current)
    except ValueError:
        return ITER_PHASE_DECIDED
    if idx + 1 >= len(phases):
        return ITER_PHASE_DECIDED
    return phases[idx + 1]


DEFAULT_ROLES_CONFIG = Path.home() / ".config" / "ralph" / "roles.json"
DEFAULT_PROMPTS_DIR = Path.home() / ".config" / "ralph" / "prompts"

# Curated model sets used for CLI preflight. Keep aligned with
# tools/ralph-tui/internal/state/models.go; these are intentionally narrower
# than all provider models because Ralph defaults to the user's known-good set.
CURSOR_MODELS = {
    "composer-2-fast",
    "composer-2",
    "claude-opus-4-7-thinking-max",
    "claude-opus-4-7-thinking-xhigh",
    "claude-opus-4-7-thinking-high",
    "claude-opus-4-7-thinking-medium",
    "claude-opus-4-7-thinking-low",
    "claude-opus-4-7-max",
    "claude-opus-4-7-xhigh",
    "claude-opus-4-7-high",
    "claude-opus-4-7-medium",
    "claude-opus-4-7-low",
    "gpt-5.5-extra-high",
    "gpt-5.5-extra-high-fast",
    "gpt-5.5-high",
    "gpt-5.5-high-fast",
    "gpt-5.5-medium",
    "gpt-5.5-medium-fast",
    "gpt-5.5-low",
    "gpt-5.5-low-fast",
    "gpt-5.3-codex-xhigh",
    "gpt-5.3-codex-xhigh-fast",
    "gpt-5.3-codex-high",
    "gpt-5.3-codex-high-fast",
    "gpt-5.3-codex",
    "gpt-5.3-codex-fast",
    "gpt-5.3-codex-low",
    "gpt-5.3-codex-low-fast",
    "gpt-5.3-codex-spark-preview-xhigh",
    "gpt-5.3-codex-spark-preview-high",
    "gpt-5.3-codex-spark-preview",
    "gpt-5.3-codex-spark-preview-low",
    "gemini-3.1-pro",
    "gemini-3-flash",
}

PI_MODELS = {
    "llm-gateway/claude-opus-4-7",
    "llm-gateway/gpt-5.5",
    "llm-gateway/gemini-3.1-pro-preview",
    "llm-gateway/gemini-3.1-pro-preview-customtools",
    "llm-gateway/Kimi-K2.6",
    "openrouter/anthropic/claude-opus-4.7-thinking",
    "openrouter/anthropic/claude-opus-4.7",
    "openrouter/openai/gpt-5.5",
    "openrouter/openai/gpt-5.3-codex",
    "openrouter/google/gemini-3-pro",
    "openrouter/google/gemini-3-flash",
}


_FAMILY_KEYWORDS = (
    ("claude", ("claude", "opus", "sonnet", "haiku", "anthropic")),
    ("gpt", ("gpt", "openai", "o3", "o4")),
    ("gemini", ("gemini", "google")),
    ("llama", ("llama", "groq")),
    ("mistral", ("mistral",)),
    ("deepseek", ("deepseek",)),
)


def family_of(model: str) -> str:
    """Map a model id to a coarse family bucket for the diversity gate."""
    lowered = (model or "").lower()
    for family, keywords in _FAMILY_KEYWORDS:
        if any(k in lowered for k in keywords):
            return family
    return "unknown"


def load_roles_config(path: Path | None = None) -> dict[str, Any]:
    """Load roles.json and enforce the reviewer/re_reviewer diversity gate."""
    cfg_path = Path(path or os.environ.get("RALPH_ROLES_CONFIG", DEFAULT_ROLES_CONFIG)).expanduser()
    if not cfg_path.exists():
        raise SystemExit(
            f"roles config not found at {cfg_path}; copy the chezmoi default "
            f"(home/dot_config/ralph/roles.json) or set RALPH_ROLES_CONFIG."
        )
    try:
        cfg = json.loads(cfg_path.read_text())
    except json.JSONDecodeError as err:
        raise SystemExit(f"roles config {cfg_path} is not valid JSON: {err}")
    roles = cfg.get("roles", {})
    for required in ("planner", "executor", "reviewer", "re_reviewer"):
        if required not in roles:
            raise SystemExit(f"roles config {cfg_path} missing required role: {required}")
    rev_family = roles["reviewer"].get("family") or family_of(roles["reviewer"]["model"])
    rer_family = roles["re_reviewer"].get("family") or family_of(roles["re_reviewer"]["model"])
    if rev_family == rer_family:
        raise SystemExit(
            f"diversity gate failed in {cfg_path}: reviewer model "
            f"({roles['reviewer']['model']}, family={rev_family}) and re_reviewer model "
            f"({roles['re_reviewer']['model']}, family={rer_family}) must be different families. "
            f"Edit roles.json so re_reviewer is in {{claude,gpt,gemini,llama,mistral,deepseek}} \\ {{{rev_family}}} "
            f"(or set an explicit `family` override on the role)."
        )
    cfg.setdefault("defaults", {}).setdefault("max_iterations", 5)
    cfg["defaults"].setdefault("max_minutes", 15)
    cfg["defaults"].setdefault("memory_top_k", 5)
    cfg["defaults"].setdefault("progress_tail_blocks", 3)
    cfg["defaults"].setdefault("iteration_timeout_seconds", 300)
    return cfg


def apply_role_overrides(cfg: dict[str, Any], cli_args: dict[str, Any]) -> dict[str, Any]:
    """Apply per-role CLI overrides (--<role>-{model,harness}) to a loaded roles config.

    Mutates and returns cfg. Overrides clear any prior `family` field on the
    role so the diversity gate re-derives family from the new model id (or the
    user can set RALPH_ROLES_CONFIG with explicit family fields). Re-runs the
    diversity gate so a same-family pair fails fast at CLI parse time rather
    than mid-run.
    """
    roles = cfg.get("roles", {})
    for role_arg, role_key in (
        ("planner", "planner"),
        ("executor", "executor"),
        ("reviewer", "reviewer"),
        ("re_reviewer", "re_reviewer"),
    ):
        model_key = f"{role_arg}_model"
        harness_key = f"{role_arg}_harness"
        args_key = f"{role_arg}_args"
        if cli_args.get(model_key):
            roles[role_key]["model"] = cli_args[model_key]
            roles[role_key].pop("family", None)
        if cli_args.get(harness_key):
            roles[role_key]["harness"] = cli_args[harness_key]
        # `extra_args` is a list[str] in roles.json; the CLI flag accepts a
        # single shell-style string for ergonomics (matches how a user would
        # type the command). shlex.split mirrors `,ralph` runtime tokenization.
        # `None` = leave existing extra_args (the common form-submit case
        # when the user didn't touch the args field). Empty string =
        # explicit clear (operator wants the role to run with bare model).
        if args_key in cli_args and cli_args[args_key] is not None:
            raw = cli_args[args_key]
            roles[role_key]["extra_args"] = shlex.split(raw) if raw.strip() else []
    rev_family = roles["reviewer"].get("family") or family_of(roles["reviewer"]["model"])
    rer_family = roles["re_reviewer"].get("family") or family_of(roles["re_reviewer"]["model"])
    if rev_family == rer_family:
        raise SystemExit(
            f"diversity gate failed after CLI overrides: reviewer model "
            f"({roles['reviewer']['model']}, family={rev_family}) and re_reviewer model "
            f"({roles['re_reviewer']['model']}, family={rer_family}) must be different families."
        )
    return cfg


def cursor_agent_binary() -> str:
    """Return the Cursor Agent binary Ralph should execute."""
    if shutil.which("agent"):
        return "agent"
    if shutil.which("cursor-agent"):
        return "cursor-agent"
    return "agent"


def preflight_roles_config(cfg: dict[str, Any]) -> None:
    """Fail fast when a role harness/model cannot be launched safely."""
    roles = cfg.get("roles", {})
    missing: list[str] = []
    for role, spec in roles.items():
        harness = spec.get("harness")
        model = spec.get("model") or ""
        if harness == "cursor":
            if not (shutil.which("agent") or shutil.which("cursor-agent")):
                missing.append(f"{role}: cursor harness needs `agent` or `cursor-agent` on PATH")
            if model and model not in CURSOR_MODELS:
                missing.append(f"{role}: cursor model {model!r} is not in the curated supported list")
        elif harness == "pi":
            if not shutil.which("pi"):
                missing.append(f"{role}: pi harness needs `pi` on PATH")
            if model and model not in PI_MODELS:
                missing.append(f"{role}: pi model {model!r} is not in the curated supported list")
        elif harness == "command":
            if not (spec.get("extra_args") or model):
                missing.append(f"{role}: command harness needs extra_args or model command")
        else:
            missing.append(f"{role}: unknown harness {harness!r}")
    if missing:
        raise SystemExit("role preflight failed:\n- " + "\n- ".join(missing))


def load_role_prompt(role: str, prompts_dir: Path | None = None) -> Path:
    """Resolve the markdown prompt file for the given role and return its path."""
    base = Path(prompts_dir or os.environ.get("RALPH_PROMPTS_DIR", DEFAULT_PROMPTS_DIR)).expanduser()
    p = base / f"{role}.md"
    if not p.exists():
        raise SystemExit(
            f"prompt template missing for role={role}: {p} (copy from chezmoi "
            f"home/dot_config/ralph/prompts/, or set RALPH_PROMPTS_DIR)"
        )
    return p


# --- elastic workspace gating -----------------------------------------------
#
# In elastic-belonging codebases (the operator's day job) we want the
# reviewer / re-reviewer roles to actually invoke the operator's
# `/review` skill rather than the lightweight default review. The
# skill content (shared rules + local-changes mode) is inlined into
# the role prompt as a primary instruction; the role's existing JSON
# output contract is preserved so the orchestrator's verdict parser
# is unchanged.
#
# Detection is git-remote-driven: any remote URL whose path starts
# with `elastic/` qualifies. This catches forks (origin points at
# `elastic/<repo>`) and personal mirrors via the upstream remote.

REVIEW_SKILL_DIR = Path(os.environ.get("RALPH_REVIEW_SKILL_DIR", "~/.agents/skills/review")).expanduser()
ELASTIC_REMOTE_RE = re.compile(r"(github\.com[:/])elastic/", re.IGNORECASE)


def is_elastic_workspace(workspace: Path) -> bool:
    """True iff the workspace's git remotes include an `elastic/<repo>`
    URL (HTTPS or SSH form).

    Returns False for non-git directories, paths that don't exist, or
    repos with no elastic remote. Best-effort: a `git remote -v`
    failure (e.g. corrupted .git/) yields False rather than raising.
    """
    if not workspace or not Path(workspace).exists():
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", str(workspace), "remote", "-v"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    if proc.returncode != 0:
        return False
    return bool(ELASTIC_REMOTE_RE.search(proc.stdout or ""))


def _read_skill_file(name: str) -> str:
    """Best-effort read of a review-skill source file. Returns an
    empty string if the file is missing so the preamble degrades to
    "we tried" rather than crashing the role spawn.
    """
    path = REVIEW_SKILL_DIR / name
    try:
        return path.read_text()
    except (FileNotFoundError, OSError):
        return ""


def elastic_review_preamble(role: str) -> str:
    """Render the `## REVIEW SKILL HEURISTICS (elastic)` block that is
    prepended to the dynamic context for elastic reviewer / re-reviewer
    invocations.

    The preamble:
      - declares the role is running the `/review` skill (skill-as-primary)
      - inlines `references/shared_rules.md` verbatim (verification disciplines)
      - inlines `references/local_changes.md` verbatim (closest-mode skill body)
      - normalizes the skill's "fix in working tree" guidance into Ralph's
        `next_task` JSON field, since this reviewer never modifies code
      - reminds the model to honor the existing JSON output contract from
        the system prompt above

    Returns "" when the skill files are unavailable so non-elastic
    callers (which never call this) and broken-skill installs both
    degrade silently to the default review path.
    """
    shared = _read_skill_file("references/shared_rules.md").strip()
    mode = _read_skill_file("references/local_changes.md").strip()
    if not shared and not mode:
        return ""
    role_label = "RE-REVIEWER" if role == "re_reviewer" else "REVIEWER"
    sections = [
        "## REVIEW SKILL HEURISTICS (elastic)",
        "",
        f"You are running the operator's `/review` skill in **local_changes** mode "
        f"as the Ralph {role_label}. The skill's verification disciplines are the "
        f"primary instruction for this review. Apply them to the executor's "
        f"iteration artifact below.",
        "",
        "**Format normalization** — Ralph reviewers never modify code; the "
        "executor does that on the next iteration. Translate the skill's "
        "'verify and fix in working tree' guidance into:",
        "  - concrete, fixable issues listed in `criteria_unmet`",
        "  - one specific next step in `next_task` (only required when verdict=needs_iteration)",
        "Honor the JSON output contract from the role prompt above; do not "
        "emit prose review comments. The skill content is for *how* to verify, "
        "not *what* to output.",
        "",
        "### shared_rules.md (skill verification disciplines)",
        "",
        shared or "(skill file unavailable)",
        "",
        "### local_changes.md (skill mode body)",
        "",
        mode or "(skill file unavailable)",
        "",
        "---",
        "",
        "End of /review skill content. Apply its disciplines to the inputs below.",
        "",
    ]
    return "\n".join(sections)


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n(\{.*?\})\s*```", re.DOTALL)


_ANCHOR_MARKDOWN_DECORATORS = "*_`#> \t"


def has_anchor(text: str) -> bool:
    """True iff the role output begins (within the first N lines) with a non-empty `ANCHOR:` line.

    Roles MUST re-anchor every iteration by restating the goal in their own
    words. A missing or empty `ANCHOR:` line means the role broke contract; the
    orchestrator gates role validation on this.

    Markdown-decorated anchor lines are accepted: `**ANCHOR:** body`,
    `*ANCHOR: body*`, `` `ANCHOR:` body ``, `# ANCHOR: body`, and `> ANCHOR:
    body` all count, because the prefix is what matters and those decorators
    are common formatter output. Leading whitespace, asterisks, underscores,
    backticks, hash signs, and quote markers are stripped before the prefix
    check; trailing decorators are tolerated when computing whether the body
    is non-empty.
    """
    if not text:
        return False
    for line in text.splitlines()[:ANCHOR_LOOKAHEAD_LINES]:
        stripped = line.strip()
        if not stripped:
            continue
        prefix_clean = stripped.lstrip(_ANCHOR_MARKDOWN_DECORATORS)
        if not prefix_clean.startswith(ANCHOR_PREFIX):
            continue
        body = prefix_clean[len(ANCHOR_PREFIX) :].rstrip(_ANCHOR_MARKDOWN_DECORATORS).strip()
        if body:
            return True
    return False


def parse_questions_block(text: str) -> list[dict[str, Any]]:
    """Extract `questions[]` from a role/planner output that ended with RALPH_QUESTIONS.

    Returns the list of `{"id": str, "text": str}` dicts. Raises ValueError
    when the JSON is missing, malformed, or `questions` is not a list of items
    with stable string ids and non-empty text.
    """
    payload = parse_json_block(text)
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("RALPH_QUESTIONS block has no non-empty `questions` list")
    cleaned: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in questions:
        if not isinstance(raw, dict):
            raise ValueError(f"questions entry must be an object: {raw!r}")
        qid = str(raw.get("id") or "").strip()
        qtext = str(raw.get("text") or "").strip()
        if not qid or not qtext:
            raise ValueError(f"questions entry needs non-empty id+text: {raw!r}")
        if qid in seen_ids:
            raise ValueError(f"duplicate question id in block: {qid}")
        seen_ids.add(qid)
        cleaned.append({"id": qid, "text": qtext})
    return cleaned


def parse_json_block(text: str) -> dict[str, Any]:
    """Extract the first fenced ```json block from text and parse it.

    Tolerant of missing language tag and trailing prose. Raises ValueError
    with the offending payload if no block is found or JSON parsing fails.
    """
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        # Fall back to first standalone {...} blob.
        brace = text.find("{")
        if brace < 0:
            raise ValueError("no JSON block found in output")
        depth = 0
        end = -1
        for i, ch in enumerate(text[brace:], start=brace):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end < 0:
            raise ValueError("unterminated JSON object in output")
        payload = text[brace:end]
    else:
        payload = match.group(1)
    try:
        return json.loads(payload)
    except json.JSONDecodeError as err:
        raise ValueError(f"JSON parse failed: {err}; payload={payload!r}")


def default_state_home() -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return Path(os.environ.get("RALPH_STATE_HOME", state_home / "ralph")).expanduser()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")


def tmux_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value)[:80].strip("-") or "ralph"


def short_id(value: str) -> str:
    return value[-6:] if len(value) > 6 else value


def humanize_age(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    seconds = int(seconds)
    if seconds < 0:
        return "-"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def role_validation_status(role: dict[str, Any]) -> str:
    """Validation gate: a role passes only when status=completed, exit=0, AND its
    output contains an `ANCHOR:` re-anchoring line.

    The ANCHOR check is skipped when the output path is missing or unreadable
    (in-progress roles, sparse synthetic dicts in tests). When the output is
    present, ANCHOR is mandatory: a missing anchor flips validation to failed
    even if the role exited cleanly.
    """
    if role.get("status") != "completed" or role.get("exit_code") != 0:
        return "failed"
    output_path = role.get("output")
    if not output_path:
        return "passed"
    p = Path(output_path)
    if not p.exists():
        return "passed"
    try:
        text = p.read_text()
    except OSError:
        return "passed"
    if not has_anchor(text):
        return "failed"
    return "passed"


def role_summary(role: dict[str, Any]) -> dict[str, Any]:
    tmux = role.get("tmux") or {}
    output_path = role.get("output")
    last_output_age = output_age_seconds(Path(output_path)) if output_path else None
    return {
        "id": role.get("id"),
        "name": role.get("name"),
        "goal": role.get("goal"),
        "status": role.get("status"),
        "exit_code": role.get("exit_code"),
        "control_state": role.get("control_state", "automated"),
        "validation_status": role.get("validation_status", role_validation_status(role)),
        "pane": tmux.get("pane"),
        "session": tmux.get("session"),
        "window": tmux.get("window"),
        "output": output_path,
        "command": role.get("command"),
        "run_script": role.get("run_script"),
        "learned_count": len(role.get("learned_ids", [])),
        "last_output_age_seconds": last_output_age,
    }


def output_age_seconds(path: Path | None) -> float | None:
    if path is None or not path.exists():
        return None
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None


def redact(text: str) -> str:
    patterns = [
        (re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"), r"\1=REDACTED"),
        (re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._~+/=-]+"), "Authorization: Bearer REDACTED"),
        (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "sk-REDACTED"),
    ]
    value = text
    for pattern, replacement in patterns:
        value = pattern.sub(replacement, value)
    return value


def wait_for_tmux_shell(pane_id: str, timeout: float = 5.0) -> None:
    shells = {"bash", "zsh", "fish", "sh"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", pane_id, "#{pane_current_command}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip() in shells:
            return
        time.sleep(0.1)


def current_tmux_session() -> str | None:
    if not os.environ.get("TMUX"):
        return None
    result = subprocess.run(["tmux", "display-message", "-p", "#S"], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return name or None


def tmux_session_exists(name: str) -> bool:
    return subprocess.run(["tmux", "has-session", "-t", name], capture_output=True).returncode == 0


def tmux_window_exists(target: str) -> bool:
    result = subprocess.run(
        ["tmux", "list-windows", "-F", "#{window_name}", "-t", target.split(":", 1)[0]],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    if ":" in target:
        wanted = target.split(":", 1)[1]
        return wanted in result.stdout.split()
    return True


def tmux_pane_exists(pane: str) -> bool:
    if not pane:
        return False
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", pane, "#{pane_id}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == pane


# --- runner liveness ---------------------------------------------------------
#
# Each run has a PID file at <run_dir>/runner.pid. The runner takes an exclusive
# fcntl flock on the file for its whole lifetime; `,ralph resume` opens the file
# non-blocking and skips the relaunch if it can't acquire the lock. Stale PID
# files are tolerated: a non-running PID released its lock when the process
# exited, so the next acquire succeeds.


def runner_pid_path(run_dir: Path) -> Path:
    return run_dir / "runner.pid"


def runner_alive(run_dir: Path) -> bool:
    """True iff a runner process currently holds the PID-file lock."""
    pid_path = runner_pid_path(run_dir)
    if not pid_path.exists():
        return False
    try:
        fh = pid_path.open("r+")
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as err:
            if err.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                return True  # someone holds it
            raise
        # We acquired the lock -> nobody else held it -> runner not alive.
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return False
    finally:
        fh.close()


def acquire_runner_lock(run_dir: Path):
    """Acquire the runner flock; returns the open file handle. Raises on contention."""
    run_dir.mkdir(parents=True, exist_ok=True)
    pid_path = runner_pid_path(run_dir)
    fh = pid_path.open("a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as err:
        fh.close()
        if err.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
            raise RuntimeError(f"runner already alive for {run_dir.name}")
        raise
    fh.seek(0)
    fh.truncate()
    fh.write(f"{os.getpid()}\n")
    fh.flush()
    os.fsync(fh.fileno())
    return fh


def release_runner_lock(fh) -> None:
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    finally:
        fh.close()


# --- iteration state introspection -------------------------------------------


def current_iteration(manifest: dict[str, Any]) -> dict[str, Any] | None:
    """Last iteration record if it is not yet decided, else None.

    The state machine treats the absence of an open iteration as "ready to
    start the next one". `len(manifest['iterations'])` then gives the iter
    number to assign to the next start.
    """
    iterations = manifest.get("iterations") or []
    if not iterations:
        return None
    last = iterations[-1]
    if iter_phase(last) in ITER_PHASES_TERMINAL:
        return None
    return last


def iter_phase(iteration: dict[str, Any]) -> str:
    return iteration.get("phase") or ITER_PHASE_PENDING


def iter_verdict(iteration: dict[str, Any]) -> str | None:
    return iteration.get("verdict")


@dataclass
class RuntimeResult:
    output: str
    exit_code: int


class RalphRunner:
    def __init__(self, state_home: Path | None = None, kb_home: Path | None = None):
        self.state_home = state_home or default_state_home()
        self.runs_dir = self.state_home / "runs"
        self.bag_dir = self.state_home / ".bag"
        self.kb = KnowledgeBase(kb_home)

    def init(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.kb.init()

    def run_dir(self, rid: str) -> Path:
        return self.runs_dir / rid

    def search_memory(self, query: str, limit: int) -> list[dict[str, object]]:
        return self.kb.search(query, limit)

    def assemble_prompt(
        self,
        goal: str,
        memory_query: str | None,
        memory_limit: int,
        acceptance: str | None,
    ) -> str:
        query = memory_query or goal
        memories = self.search_memory(query, memory_limit)
        memory_text = "\n".join(f"- {row['title']} ({row['id']}): {row['snippet']}" for row in memories)
        if not memory_text:
            memory_text = "- No relevant durable memory found."
        acceptance_text = acceptance or f"Print {DONE_MARKER} when the goal is complete."
        return "\n".join(
            [
                "# Ralph Run",
                "",
                "You are executing one fresh Ralph loop turn.",
                "Use durable memory only when it is relevant. Do not reveal secrets.",
                f"Completion signal: print `{DONE_MARKER}` exactly once when done.",
                "",
                "## Goal",
                goal,
                "",
                "## Relevant Durable Memory",
                memory_text,
                "",
                "## Acceptance Criteria",
                acceptance_text,
                "",
                "## Learning Capture",
                f"If this run learns a durable reusable fact, emit `{LEARNING_PREFIX} <fact>`.",
            ]
        )

    def runtime_local(self, goal: str, prompt: str) -> RuntimeResult:
        context_count = prompt.count("\n- ") - 1
        output = "\n".join(
            [
                f"Local Ralph runtime completed goal: {goal}",
                f"{LEARNING_PREFIX} Ralph local runtime can complete `{goal}` and persist reusable learnings across runs.",
                f"Memory snippets considered: {max(context_count, 0)}",
                DONE_MARKER,
            ]
        )
        return RuntimeResult(output=output, exit_code=0)

    def runtime_command(self, command: str, prompt: str, timeout: int) -> RuntimeResult:
        try:
            proc = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                shell=True,
                timeout=timeout,
            )
            return RuntimeResult(output=proc.stdout + proc.stderr, exit_code=proc.returncode)
        except subprocess.TimeoutExpired as err:
            output = (err.stdout or "") + (err.stderr or "")
            output += f"\nRALPH_TIMEOUT after {timeout}s\n"
            return RuntimeResult(output=output, exit_code=124)

    def runtime_pi(self, prompt: str, extra_args: list[str], timeout: int) -> RuntimeResult:
        cmd = ["pi", "-p", "--no-session", *extra_args]
        try:
            proc = subprocess.run(cmd, input=prompt, text=True, capture_output=True, timeout=timeout)
            return RuntimeResult(output=proc.stdout + proc.stderr, exit_code=proc.returncode)
        except subprocess.TimeoutExpired as err:
            output = (err.stdout or "") + (err.stderr or "")
            output += f"\nRALPH_TIMEOUT after {timeout}s\n"
            return RuntimeResult(output=output, exit_code=124)

    def runtime_cursor(self, prompt: str, workspace: Path, extra_args: list[str], timeout: int) -> RuntimeResult:
        cmd = [
            "agent",
            "--print",
            "--output-format",
            "stream-json",
            "--trust",
            "--workspace",
            str(workspace),
            *extra_args,
            prompt,
        ]
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
            return RuntimeResult(output=proc.stdout + proc.stderr, exit_code=proc.returncode)
        except subprocess.TimeoutExpired as err:
            output = (err.stdout or "") + (err.stderr or "")
            output += f"\nRALPH_TIMEOUT after {timeout}s\n"
            return RuntimeResult(output=output, exit_code=124)

    def execute_tmux_role(
        self,
        *,
        rid: str,
        role_name: str,
        goal: str,
        command: str,
        memory_query: str | None,
        memory_limit: int,
        acceptance: str,
        expect: str,
        workspace: Path,
        timeout: int,
        session_name: str,
        window_name: str,
        create_session: bool,
        keep_window: bool = False,
        prompt_override: str | None = None,
    ) -> dict[str, Any]:
        self.init()
        directory = self.run_dir(rid)
        directory.mkdir(parents=True, exist_ok=True)
        prompt = (
            prompt_override
            if prompt_override is not None
            else self.assemble_prompt(goal, memory_query, memory_limit, acceptance)
        )
        prompt_path = directory / "prompt.md"
        raw_output = directory / "output.raw.log"
        output_path = directory / "output.log"
        exit_path = directory / "exit-code.txt"
        run_script = directory / "run.sh"
        prompt_path.write_text(redact(prompt))
        # Each harness's `command` string includes its own prompt-supply
        # mechanism (stdin redirect, $(cat <file>) substitution, etc.) so the
        # run.sh wrapper only handles output redirection. We do NOT add a
        # per-command stdin redirect here because cursor-agent stalls when
        # both a positional prompt arg AND a non-empty stdin are provided.
        run_script.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    f"cd {shlex.quote(str(workspace))}",
                    f"{command} > {shlex.quote(str(raw_output))} 2>&1",
                    "code=$?",
                    f"printf '%s\\n' \"$code\" > {shlex.quote(str(exit_path))}",
                    f"printf '\\n[ralph:{role_name}] exit=%s\\n' \"$code\"",
                ]
            )
            + "\n"
        )
        run_script.chmod(0o755)

        target = f"{session_name}:{window_name}"
        pane_id = ""
        target_exists = tmux_window_exists(target)
        if target_exists:
            # A previous runner may have died while this role pane was still
            # alive. Reuse the pane and wait for its exit marker instead of
            # spawning a duplicate LLM call.
            pane_id = subprocess.run(
                ["tmux", "display-message", "-p", "-t", target, "#{pane_id}"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        elif create_session:
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name, "-n", window_name, "-c", str(workspace)],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            subprocess.run(
                ["tmux", "new-window", "-d", "-t", session_name, "-n", window_name, "-c", str(workspace)],
                check=True,
                capture_output=True,
                text=True,
            )

        if not target_exists:
            pane_id = subprocess.run(
                ["tmux", "display-message", "-p", "-t", target, "#{pane_id}"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            shell = f"bash {shlex.quote(str(run_script))}"
            wait_for_tmux_shell(pane_id)
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "-l", shell],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "C-m"],
                check=True,
                capture_output=True,
                text=True,
            )

        deadline = time.time() + timeout
        while not exit_path.exists() and time.time() < deadline:
            time.sleep(0.1)

        timed_out = not exit_path.exists()
        if timed_out:
            subprocess.run(["tmux", "send-keys", "-t", pane_id, "C-c"], check=False)
            raw = raw_output.read_text() if raw_output.exists() else ""
            raw += f"\nRALPH_TIMEOUT after {timeout}s\n"
            exit_code = 124
        else:
            raw = raw_output.read_text() if raw_output.exists() else ""
            exit_code = int(exit_path.read_text().strip() or "1")

        output = redact(raw)
        output_path.write_text(output)
        learned_ids = self.capture_learnings(rid, output, role=role_name, workspace=str(workspace))
        completed = exit_code == 0 and expect in output

        pane_alive = tmux_pane_exists(pane_id)
        window_closed = False
        if completed and not keep_window and pane_alive:
            kill = subprocess.run(["tmux", "kill-window", "-t", target], capture_output=True, text=True)
            window_closed = kill.returncode == 0
            pane_alive = pane_alive and not window_closed

        manifest = {
            "id": rid,
            "kind": "role",
            "name": role_name,
            "created_at": utc_now(),
            "goal": goal,
            "runtime": "tmux-command",
            "status": "completed" if completed else "failed",
            "exit_code": exit_code,
            "expect": expect,
            "timeout_seconds": timeout,
            "control_state": "automated",
            "validation_status": role_validation_status(
                {
                    "status": "completed" if completed else "failed",
                    "exit_code": exit_code,
                    "output": str(output_path),
                }
            ),
            "last_validated_at": utc_now(),
            "learned_ids": learned_ids,
            "command": command,
            "run_script": str(run_script),
            "workspace": str(workspace),
            "prompt": str(prompt_path),
            "output": str(output_path),
            "tmux": {
                "session": session_name,
                "window": window_name,
                "pane": pane_id,
                "target": target,
                "alive": pane_alive,
                "closed_on_success": window_closed,
            },
        }
        self.save_manifest(manifest)
        return manifest

    # --- ,ralph go orchestrator ---------------------------------------------

    def _blocking_control_roles(self, manifest: dict[str, Any]) -> list[str]:
        roles = manifest.get("roles") or {}
        return [
            name for name, role in roles.items() if role.get("control_state", "automated") in CONTROL_BLOCKING_STATES
        ]

    def _park_if_controlled(self, manifest: dict[str, Any]) -> dict[str, Any]:
        blocked = self._blocking_control_roles(manifest)
        if not blocked:
            return manifest
        manifest["status"] = "needs_human"
        manifest["validation_status"] = "needs_verification"
        manifest["control_state"] = "manual_control"
        manifest["blocked_roles"] = blocked
        manifest["validation"] = self.validation_for_manifest(manifest)
        self._append_decision(
            self.run_dir(manifest["id"]),
            "parked for manual control: " + ", ".join(blocked),
        )
        self.save_manifest(manifest)
        return manifest

    def _unpark_if_control_clear(self, manifest: dict[str, Any]) -> dict[str, Any]:
        if self._blocking_control_roles(manifest):
            return manifest
        if manifest.get("status") in ("needs_human", "needs_verification"):
            manifest["status"] = manifest.pop("pre_control_status", None) or "running"
            manifest["control_state"] = "automated"
            manifest.pop("blocked_roles", None)
        manifest["validation"] = self.validation_for_manifest(manifest)
        manifest["validation_status"] = manifest["validation"]["status"]
        self.save_manifest(manifest)
        return manifest

    def _open_questions(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        """Return the `questions[]` entries that have not been answered yet."""
        return [q for q in (manifest.get("questions") or []) if not q.get("answered_at")]

    def _park_for_questions(
        self,
        manifest: dict[str, Any],
        questions: list[dict[str, Any]],
        *,
        asked_by: str,
    ) -> dict[str, Any]:
        """Append role-emitted questions to the manifest and park the run.

        Idempotent: re-asking a question with the same id is a no-op (we keep
        the original asked_at). The runner is parked at status=awaiting_human;
        ,ralph answer is the only way out.
        """
        existing = list(manifest.get("questions") or [])
        existing_ids = {q.get("id") for q in existing}
        now = utc_now()
        added: list[str] = []
        for q in questions:
            if q.get("id") in existing_ids:
                continue
            existing.append(
                {
                    "id": q["id"],
                    "role": asked_by,
                    "asked_at": now,
                    "text": q["text"],
                    "answer": None,
                    "answered_at": None,
                }
            )
            added.append(q["id"])
        manifest["questions"] = existing
        if manifest.get("status") not in ("completed", "failed", "killed"):
            if manifest.get("status") not in ("awaiting_human",):
                manifest["pre_questions_status"] = manifest.get("status")
            manifest["status"] = "awaiting_human"
        manifest.setdefault("phase", "awaiting_human")
        manifest["awaiting_role"] = asked_by
        manifest["validation_status"] = "needs_verification"
        directory = self.run_dir(manifest["id"])
        if added:
            self._append_decision(
                directory,
                f"parked for human answer (asked_by={asked_by}); new questions: {', '.join(added)}",
            )
        else:
            self._append_decision(directory, f"already awaiting human (asked_by={asked_by})")
        manifest["validation"] = self.validation_for_manifest(manifest)
        self.save_manifest(manifest)
        return manifest

    def _unpark_when_answered(self, manifest: dict[str, Any]) -> dict[str, Any]:
        """Flip status back to running once every question is answered.

        Sets `replan_requested=True` so the state-machine loop pulls the
        planner again, this time with `## ANSWERS` folded into context. The
        questioning role's cached output is dropped so it re-runs after replan
        when the planner says to continue.
        """
        if self._open_questions(manifest):
            return manifest
        if manifest.get("status") != "awaiting_human":
            return manifest
        prior = manifest.pop("pre_questions_status", None) or "running"
        manifest["status"] = prior
        manifest["phase"] = "replanning"
        manifest["replan_requested"] = True
        asked_by = manifest.pop("awaiting_role", None)
        if asked_by:
            roles = manifest.get("roles") or {}
            cached = roles.get(asked_by)
            if cached:
                roles.pop(asked_by, None)
                manifest["roles"] = roles
        manifest["validation"] = self.validation_for_manifest(manifest)
        manifest["validation_status"] = manifest["validation"]["status"]
        self._append_decision(
            self.run_dir(manifest["id"]),
            "all questions answered; queued replan",
        )
        self.save_manifest(manifest)
        return manifest

    def _output_questions(self, output_text: str) -> list[dict[str, Any]] | None:
        """If the role output ended with RALPH_QUESTIONS, parse and return the list.

        Returns None when the marker is absent. Raises ValueError when the
        marker is present but the JSON block is malformed (caller should turn
        that into a hard error since the role broke contract).
        """
        if QUESTIONS_MARKER not in (output_text or ""):
            return None
        return parse_questions_block(output_text)

    def _format_answers(self, manifest: dict[str, Any]) -> str:
        """Render the answered `questions[]` as a `## ANSWERS` markdown section.

        Returns the empty string when no answered questions exist.
        """
        answered = [q for q in (manifest.get("questions") or []) if q.get("answered_at")]
        if not answered:
            return ""
        lines = []
        for q in answered:
            lines.append(f"- **{q['id']}** (asked by {q.get('role', '?')}): {q.get('text', '')}")
            lines.append(f"  → {q.get('answer', '').strip()}")
        return "\n".join(lines)

    def _artifact_path_from_spec(self, spec: dict[str, Any], workspace: Path) -> str | None:
        target = spec.get("target_artifact")
        if not target:
            return None
        p = Path(str(target)).expanduser()
        if not p.is_absolute():
            p = workspace / p
        return str(p.resolve())

    def _sync_artifact_from_spec(self, manifest: dict[str, Any], workspace: Path) -> None:
        artifact = self._artifact_path_from_spec(manifest.get("spec") or {}, workspace)
        if artifact:
            manifest["artifact"] = artifact

    def _freeze_artifact_hash(self, manifest: dict[str, Any], workspace: Path) -> None:
        self._sync_artifact_from_spec(manifest, workspace)
        artifact = manifest.get("artifact")
        if not artifact:
            return
        path = Path(artifact)
        if path.exists():
            manifest["artifact_sha256"] = sha256_file(path)
            manifest["artifact_ok"] = True
        else:
            manifest.pop("artifact_sha256", None)
            manifest["artifact_ok"] = False

    def go(
        self,
        *,
        goal: str,
        workspace: Path,
        roles_cfg: dict[str, Any],
        tmux_mode: bool,
        plan_only: bool = False,
        detached: bool = False,
        workflow_hint: str | None = None,
    ) -> dict[str, Any]:
        """Initialize a fresh go run, invoke the planner, then drive iterations.

        Steps:
            1. Create a new run dir + manifest.
            2. Allocate a dedicated tmux session `ralph-<short-rid>` if tmux_mode.
            3. Invoke the planner; persist spec.
            4. If plan_only: return early.
            5. If detached: spawn `,ralph runner <rid>` (a fresh process) and
               return immediately.
            6. Else: drive the state-machine loop inline (foreground).

        Resume / replan flows live in `resume_run()` and `replan_run()`.
        """
        self.init()
        slug = tmux_name(goal[:32] or "go")
        rid = f"go-{slug}-{run_id()}"
        directory = self.run_dir(rid)
        directory.mkdir(parents=True)
        manifest = {
            "id": rid,
            "kind": "go",
            "name": slug,
            "created_at": utc_now(),
            "goal": goal,
            "workspace": str(workspace.expanduser().resolve()),
            "runtime": "orchestrator",
            "phase": "planning",
            "status": "running",
            "control_state": "automated",
            "iterations": [],
            "roles": {},
            "learned_ids": [],
            "roles_cfg": roles_cfg["roles"],
            "defaults": roles_cfg["defaults"],
            "tmux": None,
            "spec_seq": 1,
            "runner": None,
            "operator_workflow_hint": workflow_hint or None,
        }
        self.save_manifest(manifest)
        self.write_latest(rid)

        session_name = self._allocate_session(rid, tmux_mode=tmux_mode)
        # _allocate_session writes manifest["tmux"]={"session": ...} to disk
        # but our local `manifest` reference predates that write. Reload so
        # downstream save_manifest calls don't clobber the tmux session
        # field with the stale `None` from the initial creation block. Then
        # the detached runner picks up the session name on resume and the
        # `,ralph rm` path can find it to kill.
        manifest = self.load_manifest(rid)

        defaults = roles_cfg["defaults"]
        spec = self._invoke_planner(
            manifest=manifest,
            goal=goal,
            workspace=workspace,
            roles_cfg=roles_cfg,
            session_name=session_name,
        )
        manifest = self.load_manifest(rid)
        if isinstance(spec, dict) and "_questions" in spec:
            self._park_for_questions(
                manifest,
                spec["_questions"],
                asked_by=spec.get("_role_name", "planner-1"),
            )
            return self.load_manifest(rid)
        manifest["spec"] = spec
        manifest["workflow"] = spec.get("workflow", DEFAULT_WORKFLOW)
        self._sync_artifact_from_spec(manifest, workspace)
        manifest["phase"] = "executing"
        self._append_decision(
            directory,
            f"planner emitted spec; workflow={manifest['workflow']} "
            f"max_iters={spec['max_iterations']} max_min={spec['max_minutes']}",
        )
        self.save_manifest(manifest)
        if plan_only:
            manifest["status"] = "planned"
            manifest["phase"] = "done"
            manifest["validation_status"] = "needs_verification"
            self.save_manifest(manifest)
            return manifest

        if detached:
            self._spawn_detached_runner(rid)
            return self.load_manifest(rid)

        return self._run_with_lock(
            rid,
            workspace=workspace,
            roles_cfg=roles_cfg,
            session_name=session_name,
            defaults=defaults,
        )

    def run_session_name(self, rid: str) -> str:
        """Stable tmux session name for a given run id (`ralph-<short-rid>`)."""
        return tmux_name(f"ralph-{short_id(rid)}")

    def _allocate_session(self, rid: str, *, tmux_mode: bool) -> str | None:
        """Create (or reuse) the dedicated tmux session for this run.

        Each run owns its own session so multiple Ralph runs can coexist
        without polluting the user's main tmux session. The session name is
        deterministic (`ralph-<short-rid>`), so resumes find the same session.
        """
        if not tmux_mode:
            return None
        session_name = self.run_session_name(rid)
        if not tmux_session_exists(session_name):
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name],
                check=True,
                capture_output=True,
                text=True,
            )
        manifest = self.load_manifest(rid)
        manifest["tmux"] = {"session": session_name}
        self.save_manifest(manifest)
        self.run_dir(rid).mkdir(parents=True, exist_ok=True)
        return session_name

    def run_runner(self, rid: str) -> dict[str, Any]:
        """Resume the state machine for an existing run. Used by `,ralph runner`.

        Re-uses the manifest's recorded tmux session if alive. The lock is
        acquired here; if another runner is alive, this raises.
        """
        self.init()
        manifest = self.load_manifest(rid)
        if manifest.get("kind") != "go":
            raise SystemExit(f"{rid} is not a go run")
        if manifest.get("status") in ("completed", "failed", "killed"):
            return manifest
        if manifest.get("status") == "needs_human":
            if self._blocking_control_roles(manifest):
                return manifest
            manifest = self._unpark_if_control_clear(manifest)
        if manifest.get("status") == "planned":
            manifest["status"] = "running"
            manifest["phase"] = "executing"
            self.save_manifest(manifest)
        roles_cfg = {
            "roles": manifest.get("roles_cfg") or {},
            "defaults": manifest.get("defaults") or {},
        }
        if not roles_cfg["roles"] or not roles_cfg["defaults"]:
            # Fall back to current on-disk roles.json (e.g. older manifests).
            on_disk = load_roles_config()
            if not roles_cfg["roles"]:
                roles_cfg["roles"] = on_disk["roles"]
            if not roles_cfg["defaults"]:
                roles_cfg["defaults"] = on_disk["defaults"]
        workspace = Path(manifest.get("workspace") or Path.cwd()).expanduser()
        tmux_info = manifest.get("tmux") or {}
        session_name = tmux_info.get("session")
        if session_name and not tmux_session_exists(session_name):
            # Each run owns its session; recreate it on resume so role panes
            # have somewhere to live. If tmux server is gone entirely, demote
            # to subprocess mode for this resume.
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name],
                check=False,
                capture_output=True,
                text=True,
            )
            if not tmux_session_exists(session_name):
                session_name = None
        return self._run_with_lock(
            rid,
            workspace=workspace,
            roles_cfg=roles_cfg,
            session_name=session_name,
            defaults=roles_cfg["defaults"],
        )

    def resume_run(self, rid: str, *, detached: bool = True) -> dict[str, Any]:
        """Re-launch the runner for an existing run if it is not already alive.

        No-op when the run is already terminal or when a runner currently holds
        the lock. Returns the (possibly stale) manifest after the launch
        attempt; callers re-read it to observe progress.
        """
        self.init()
        manifest = self.load_manifest(rid)
        if manifest.get("kind") != "go":
            raise SystemExit(f"{rid} is not a go run")
        if manifest.get("status") in ("completed", "failed", "killed"):
            return manifest
        if manifest.get("status") == "needs_human":
            if self._blocking_control_roles(manifest):
                return manifest
            manifest = self._unpark_if_control_clear(manifest)
        run_dir = self.run_dir(rid)
        if runner_alive(run_dir):
            return manifest
        if detached:
            self._spawn_detached_runner(rid)
            return self.load_manifest(rid)
        return self.run_runner(rid)

    def answer_run(
        self,
        rid: str,
        answers: dict[str, str],
        *,
        auto_resume: bool = True,
    ) -> dict[str, Any]:
        """Record human answers for the named run and unpark when all are filled.

        `answers` maps question id -> answer text. Question ids that don't
        exist on the run are reported as a SystemExit. Already-answered
        questions are overwritten (last write wins) so the operator can fix
        a typo without manually editing the manifest.

        When every open question becomes answered, the run flips back to
        `running` with `replan_requested=True`. When `auto_resume` is True and
        no runner currently holds the lock, a detached runner is spawned so
        the planner consumes the answers immediately.
        """
        self.init()
        manifest = self.load_manifest(rid)
        if manifest.get("kind") != "go":
            raise SystemExit(f"{rid} is not a go run")
        if manifest.get("status") in ("completed", "failed", "killed"):
            raise SystemExit(f"{rid} is terminal ({manifest.get('status')}); cannot answer")
        questions = list(manifest.get("questions") or [])
        if not questions:
            raise SystemExit(f"{rid} has no recorded questions")
        by_id = {q.get("id"): q for q in questions}
        unknown = [qid for qid in answers if qid not in by_id]
        if unknown:
            raise SystemExit(
                f"{rid} has no questions with id(s): {', '.join(unknown)}; "
                f"open ids: {', '.join(q['id'] for q in self._open_questions(manifest)) or '(none)'}"
            )
        now = utc_now()
        for qid, text in answers.items():
            cleaned = (text or "").strip()
            if not cleaned:
                raise SystemExit(f"answer for {qid} is empty; provide non-empty text")
            by_id[qid]["answer"] = cleaned
            by_id[qid]["answered_at"] = now
        manifest["questions"] = questions
        directory = self.run_dir(rid)
        self._append_decision(
            directory,
            f"answered: {', '.join(sorted(answers.keys()))}",
        )
        self.save_manifest(manifest)
        manifest = self._unpark_when_answered(manifest)
        if (
            auto_resume
            and manifest.get("status") not in ("awaiting_human", "completed", "failed", "killed")
            and not runner_alive(directory)
        ):
            self._spawn_detached_runner(rid)
        return self.load_manifest(rid)

    def replan_run(self, rid: str, *, auto_resume: bool = True) -> dict[str, Any]:
        """Queue a replan; the runner picks it up at the next loop step.

        If no runner is alive, resume one (detached) so the replan actually
        runs. Returns the (possibly stale) manifest after the request is
        recorded.
        """
        self.init()
        manifest = self.load_manifest(rid)
        if manifest.get("kind") != "go":
            raise SystemExit(f"{rid} is not a go run")
        if manifest.get("status") in ("completed", "needs_human", "failed", "killed"):
            raise SystemExit(f"{rid} is terminal ({manifest.get('status')}); cannot replan")
        manifest["replan_requested"] = True
        directory = self.run_dir(rid)
        self._append_decision(directory, "replan queued via ,ralph replan")
        self.save_manifest(manifest)
        if auto_resume and not runner_alive(directory):
            self._spawn_detached_runner(rid)
        return self.load_manifest(rid)

    def _spawn_detached_runner(self, rid: str) -> None:
        """Fork+exec `,ralph runner RID` so it survives caller disconnect."""
        ralph_bin = shutil.which(",ralph") or (
            str(Path(__file__).resolve()) if Path(__file__).resolve().exists() else None
        )
        if not ralph_bin:
            raise SystemExit("cannot find ',ralph' or ralph.py to detach runner")
        cmd: list[str] = []
        if ralph_bin.endswith(".py"):
            cmd = [sys.executable, ralph_bin]
        else:
            cmd = [ralph_bin]
        cmd += ["runner", rid]
        log_path = self.run_dir(rid) / "runner.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fh = log_path.open("ab", buffering=0)
        try:
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=log_fh,
                stderr=log_fh,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            log_fh.close()

    # --- orchestrator helpers -----------------------------------------------

    def _run_with_lock(
        self,
        rid: str,
        *,
        workspace: Path,
        roles_cfg: dict[str, Any],
        session_name: str | None,
        defaults: dict[str, Any],
    ) -> dict[str, Any]:
        """Take the runner flock, drive the state machine to a terminal state.

        Resumable: on entry, the manifest may already have completed iterations
        and a partial in-progress iteration. The state machine inspects each
        iteration's phase and resumes from the earliest pending phase.
        """
        run_dir = self.run_dir(rid)
        try:
            lock = acquire_runner_lock(run_dir)
        except RuntimeError as err:
            raise SystemExit(str(err))
        try:
            # If the run is paused at "planned" (after `,ralph go --plan-only`),
            # flip to "running" before the state machine starts iterating.
            manifest = self.load_manifest(rid)
            if manifest.get("status") == "planned":
                manifest["status"] = "running"
                manifest["phase"] = "executing"
                self.save_manifest(manifest)
            self._mark_runner_started(rid)
            manifest = self.load_manifest(rid)
            try:
                result = self._state_machine_loop(
                    manifest=manifest,
                    workspace=workspace,
                    roles_cfg=roles_cfg,
                    session_name=session_name,
                    defaults=defaults,
                )
            finally:
                self._mark_runner_exited(rid)
            return result
        finally:
            release_runner_lock(lock)
            try:
                runner_pid_path(run_dir).unlink()
            except OSError:
                pass

    def _mark_runner_started(self, rid: str) -> None:
        try:
            manifest = self.load_manifest(rid)
        except FileNotFoundError:
            return
        manifest["runner"] = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "started_at": utc_now(),
            "heartbeat_at": utc_now(),
            "alive": True,
        }
        self.save_manifest(manifest)

    def _mark_runner_exited(self, rid: str) -> None:
        try:
            manifest = self.load_manifest(rid)
        except FileNotFoundError:
            return
        runner_block = dict(manifest.get("runner") or {})
        runner_block["alive"] = False
        runner_block["exited_at"] = utc_now()
        runner_block["heartbeat_at"] = utc_now()
        manifest["runner"] = runner_block
        self.save_manifest(manifest)

    def _heartbeat(self, manifest: dict[str, Any]) -> None:
        runner_block = dict(manifest.get("runner") or {})
        runner_block["heartbeat_at"] = utc_now()
        runner_block["alive"] = True
        manifest["runner"] = runner_block

    def _state_machine_loop(
        self,
        *,
        manifest: dict[str, Any],
        workspace: Path,
        roles_cfg: dict[str, Any],
        session_name: str | None,
        defaults: dict[str, Any],
    ) -> dict[str, Any]:
        """Phase-driven, resumable iteration loop.

        Each loop iteration is a single state-machine step:
          1. Reload manifest (catches external mutations: kill, control, replan).
          2. Update heartbeat.
          3. Compute next state from manifest fields.
          4. Apply the transition, save manifest.

        Crashes between save points are recoverable: on relaunch, the runner
        sees the last persisted phase and re-enters that phase. Idempotent
        role spawning prevents redundant work for already-completed roles.
        """
        rid = manifest["id"]
        directory = self.run_dir(rid)
        spec = manifest.get("spec") or {}
        max_iters = int(spec.get("max_iterations") or defaults["max_iterations"])
        max_seconds = int(spec.get("max_minutes") or defaults["max_minutes"]) * 60
        # The wall-clock cap restarts on each runner launch. A run resumed after
        # being parked for hours otherwise immediately fails on the cap, which is
        # not what the user wants.
        deadline = time.time() + max_seconds
        next_task = (
            ((manifest.get("iterations") or [{}])[-1].get("next_task") if manifest.get("iterations") else None)
            or spec.get("iteration_task_seed")
            or "Begin work toward the success_criteria."
        )

        while True:
            manifest = self.load_manifest(rid)
            self._heartbeat(manifest)
            self.save_manifest(manifest)

            if manifest.get("status") in TERMINAL_STATUSES:
                return manifest

            if manifest.get("status") == "awaiting_human":
                # Open questions block the runner. ,ralph answer is the only
                # way out; it sets replan_requested so the next loop tick
                # consumes answers via the planner.
                return manifest

            if self._blocking_control_roles(manifest):
                return self._park_if_controlled(manifest)

            if time.time() > deadline:
                manifest["phase"] = "failed"
                manifest["status"] = "failed"
                manifest["validation_status"] = "failed"
                self._append_decision(directory, f"wall-time cap ({max_seconds}s) reached")
                self.save_manifest(manifest)
                return manifest

            # External replan request (set by `,ralph replan RID` or by an
            # executor that printed RALPH_REPLAN). Consume it before doing any
            # other work in the iteration.
            if manifest.get("replan_requested"):
                self._append_decision(directory, "consuming replan request")
                manifest["phase"] = "replanning"
                manifest["replan_requested"] = False
                self.save_manifest(manifest)
                new_spec = self._invoke_planner(
                    manifest=manifest,
                    goal=manifest.get("goal", ""),
                    workspace=workspace,
                    roles_cfg=roles_cfg,
                    session_name=session_name,
                    replan_progress=self._read_progress(directory),
                )
                manifest = self.load_manifest(rid)
                if isinstance(new_spec, dict) and "_questions" in new_spec:
                    self._park_for_questions(
                        manifest,
                        new_spec["_questions"],
                        asked_by=new_spec.get("_role_name", "planner-replan"),
                    )
                    return self.load_manifest(rid)
                manifest["spec"] = new_spec
                manifest["spec_seq"] = (manifest.get("spec_seq") or 1) + 1
                self._sync_artifact_from_spec(manifest, workspace)
                manifest["phase"] = "executing"
                self.save_manifest(manifest)
                spec = new_spec
                max_iters = int(new_spec.get("max_iterations") or defaults["max_iterations"])
                max_seconds = int(new_spec.get("max_minutes") or defaults["max_minutes"]) * 60
                deadline = time.time() + max_seconds
                next_task = new_spec.get("iteration_task_seed") or next_task
                continue

            cur = current_iteration(manifest)
            if cur is None:
                # Either start a new iteration, or terminate on cap.
                completed = sum(1 for it in (manifest.get("iterations") or []) if iter_phase(it) == ITER_PHASE_DECIDED)
                n = completed + 1
                if n > max_iters:
                    manifest["phase"] = "failed"
                    manifest["status"] = "failed"
                    manifest["validation_status"] = "failed"
                    self._append_decision(directory, f"iteration cap ({max_iters}) exhausted without pass")
                    self.save_manifest(manifest)
                    return manifest
                new_iter = {
                    "n": n,
                    "phase": ITER_PHASE_PENDING,
                    "started_at": utc_now(),
                    "task": next_task,
                    "spec_seq": manifest.get("spec_seq", 1),
                }
                manifest.setdefault("iterations", []).append(new_iter)
                self.save_manifest(manifest)
                continue

            n = cur["n"]
            phase = iter_phase(cur)
            iter_idx = manifest["iterations"].index(cur)
            workflow = manifest.get("workflow") or DEFAULT_WORKFLOW

            if phase == ITER_PHASE_PENDING:
                first = workflow_phases(workflow)[0]
                manifest["iterations"][iter_idx]["phase"] = first
                manifest["phase"] = _ITER_PHASE_TOP_NAME.get(first, "executing")
                self.save_manifest(manifest)
                continue

            if phase == ITER_PHASE_EXEC:
                task = cur.get("task") or next_task
                executor = self._invoke_role_idempotent(
                    "executor",
                    manifest,
                    spec=spec,
                    workspace=workspace,
                    roles_cfg=roles_cfg,
                    session_name=session_name,
                    iter_n=n,
                    task=task,
                )
                self._append_progress(directory, n, "executor", executor)
                output_path = Path(executor.get("output") or "")
                output_text = output_path.read_text() if output_path.exists() else ""
                if QUESTIONS_MARKER in output_text:
                    try:
                        questions = parse_questions_block(output_text)
                    except ValueError as err:
                        self._append_decision(
                            directory,
                            f"iter {n}: executor emitted RALPH_QUESTIONS but block was unparseable: {err}; ignoring",
                        )
                    else:
                        manifest = self.load_manifest(rid)
                        manifest["iterations"] = [it for it in manifest["iterations"] if it.get("n") != n]
                        return self._park_for_questions(
                            manifest, questions, asked_by=executor.get("name", f"executor-{n}")
                        )
                if REPLAN_MARKER in output_text:
                    self._append_decision(directory, f"iter {n}: executor requested replan; iteration discarded")
                    manifest = self.load_manifest(rid)
                    manifest["iterations"] = [it for it in manifest["iterations"] if it.get("n") != n]
                    manifest["replan_requested"] = True
                    self.save_manifest(manifest)
                    continue

                manifest = self.load_manifest(rid)
                manifest["iterations"][iter_idx]["executor_id"] = executor["id"]
                next_p = next_iter_phase(ITER_PHASE_EXEC, workflow)
                manifest["iterations"][iter_idx]["phase"] = next_p
                manifest["phase"] = _ITER_PHASE_TOP_NAME.get(next_p, "executing")
                self.save_manifest(manifest)
                continue

            if phase == ITER_PHASE_REVIEW:
                executor = (manifest.get("roles") or {}).get(f"executor-{n}") or {}
                reviewer = self._invoke_role_idempotent(
                    "reviewer",
                    manifest,
                    spec=spec,
                    workspace=workspace,
                    roles_cfg=roles_cfg,
                    session_name=session_name,
                    iter_n=n,
                    executor=executor,
                )
                reviewer_output_path = Path(reviewer.get("output") or "")
                reviewer_output_text = reviewer_output_path.read_text() if reviewer_output_path.exists() else ""
                if QUESTIONS_MARKER in reviewer_output_text:
                    try:
                        questions = parse_questions_block(reviewer_output_text)
                    except ValueError as err:
                        self._append_decision(
                            directory,
                            f"iter {n}: reviewer emitted RALPH_QUESTIONS but block was unparseable: {err}; ignoring",
                        )
                    else:
                        manifest = self.load_manifest(rid)
                        return self._park_for_questions(
                            manifest, questions, asked_by=reviewer.get("name", f"reviewer-{n}")
                        )
                primary_verdict = reviewer.get("verdict_obj") or {
                    "verdict": "fail",
                    "notes": "reviewer cache had no verdict_obj",
                }
                self._append_progress(directory, n, "reviewer", reviewer)
                self._append_verdict(directory, n, "reviewer", primary_verdict)

                manifest = self.load_manifest(rid)
                manifest["iterations"][iter_idx]["reviewer_id"] = reviewer["id"]
                manifest["iterations"][iter_idx]["primary_verdict"] = primary_verdict.get("verdict")
                next_p = next_iter_phase(ITER_PHASE_REVIEW, workflow)
                if next_p == ITER_PHASE_DECIDED:
                    # Workflows without re_reviewer (review, research) finalize
                    # using the primary verdict directly.
                    decision, manifest = self._finalize_iteration(
                        manifest,
                        iter_idx=iter_idx,
                        n=n,
                        workspace=workspace,
                        primary_verdict=primary_verdict,
                        final_verdict=primary_verdict,
                        re_reviewer_id=None,
                    )
                    if decision == "complete":
                        # Best-effort distillation; reflector failure
                        # never invalidates the run that just passed.
                        self._invoke_reflector(
                            manifest=manifest,
                            spec=spec,
                            workspace=workspace,
                            roles_cfg=roles_cfg,
                            session_name=session_name,
                        )
                        manifest = self.load_manifest(rid)
                    if decision in ("complete", "blocked", "failed"):
                        return manifest
                    next_task = manifest["iterations"][iter_idx]["next_task"]
                    continue
                manifest["iterations"][iter_idx]["phase"] = next_p
                manifest["phase"] = _ITER_PHASE_TOP_NAME.get(next_p, "rereviewing")
                self.save_manifest(manifest)
                continue

            if phase == ITER_PHASE_RERVIEW:
                executor = (manifest.get("roles") or {}).get(f"executor-{n}") or {}
                reviewer = (manifest.get("roles") or {}).get(f"reviewer-{n}") or {}
                primary_verdict = reviewer.get("verdict_obj") or {
                    "verdict": "fail",
                    "notes": "reviewer cache had no verdict_obj",
                }
                re_reviewer = self._invoke_role_idempotent(
                    "re_reviewer",
                    manifest,
                    spec=spec,
                    workspace=workspace,
                    roles_cfg=roles_cfg,
                    session_name=session_name,
                    iter_n=n,
                    executor=executor,
                    primary_verdict=primary_verdict,
                )
                rer_output_path = Path(re_reviewer.get("output") or "")
                rer_output_text = rer_output_path.read_text() if rer_output_path.exists() else ""
                if QUESTIONS_MARKER in rer_output_text:
                    try:
                        questions = parse_questions_block(rer_output_text)
                    except ValueError as err:
                        self._append_decision(
                            directory,
                            f"iter {n}: re_reviewer emitted RALPH_QUESTIONS but block was unparseable: {err}; ignoring",
                        )
                    else:
                        manifest = self.load_manifest(rid)
                        return self._park_for_questions(
                            manifest, questions, asked_by=re_reviewer.get("name", f"re_reviewer-{n}")
                        )
                final_verdict = re_reviewer.get("verdict_obj") or {
                    "agree_with_primary": True,
                    "final_verdict": primary_verdict.get("verdict", "fail"),
                    "notes": "re_reviewer cache had no verdict_obj",
                }
                self._append_progress(directory, n, "re_reviewer", re_reviewer)
                self._append_verdict(directory, n, "re_reviewer", final_verdict)
                self._append_decision(
                    directory,
                    f"iter {n}: re_reviewer adjudicated -> {final_verdict.get('final_verdict')}",
                )
                manifest = self.load_manifest(rid)
                decision, manifest = self._finalize_iteration(
                    manifest,
                    iter_idx=iter_idx,
                    n=n,
                    workspace=workspace,
                    primary_verdict=primary_verdict,
                    final_verdict=final_verdict,
                    re_reviewer_id=re_reviewer["id"],
                )
                if decision == "complete":
                    self._invoke_reflector(
                        manifest=manifest,
                        spec=spec,
                        workspace=workspace,
                        roles_cfg=roles_cfg,
                        session_name=session_name,
                    )
                    manifest = self.load_manifest(rid)
                if decision in ("complete", "blocked", "failed"):
                    return manifest
                next_task = manifest["iterations"][iter_idx]["next_task"]
                continue

            # Defensive: should never hit (current_iteration excludes DECIDED).
            raise AssertionError(f"unexpected iter phase: {phase}")

    def _invoke_role_idempotent(
        self,
        role: str,
        manifest: dict[str, Any],
        *,
        spec: dict[str, Any],
        workspace: Path,
        roles_cfg: dict[str, Any],
        session_name: str | None,
        iter_n: int,
        executor: dict[str, Any] | None = None,
        primary_verdict: dict[str, Any] | None = None,
        task: str | None = None,
    ) -> dict[str, Any]:
        """Spawn a role pane only if no completed cached output exists.

        Resume safety: when a runner is restarted mid-iteration, the manifest
        may already record a completed role for the in-progress iteration. Re-
        spawning would waste an LLM call AND clobber the role's tmux pane.
        """
        name = f"{role}-{iter_n}"
        cached = (manifest.get("roles") or {}).get(name)
        if cached and cached.get("status") == "completed":
            # Reviewers persist their parsed verdict on the cached dict; if a
            # crash happened between parse and save, re-parse from output.
            if role in ("reviewer", "re_reviewer") and "verdict_obj" not in cached:
                output_path = Path(cached.get("output") or "")
                try:
                    cached["verdict_obj"] = parse_json_block(output_path.read_text())
                except (ValueError, FileNotFoundError, OSError):
                    pass
            return cached

        if role == "executor":
            return self._invoke_executor(
                manifest=manifest,
                spec=spec,
                workspace=workspace,
                roles_cfg=roles_cfg,
                session_name=session_name,
                iter_n=iter_n,
                task=task or "",
            )
        if role == "reviewer":
            return self._invoke_reviewer(
                manifest=manifest,
                spec=spec,
                workspace=workspace,
                roles_cfg=roles_cfg,
                session_name=session_name,
                iter_n=iter_n,
                executor=executor or {},
            )
        if role == "re_reviewer":
            return self._invoke_re_reviewer(
                manifest=manifest,
                spec=spec,
                workspace=workspace,
                roles_cfg=roles_cfg,
                session_name=session_name,
                iter_n=iter_n,
                executor=executor or {},
                primary_verdict=primary_verdict or {},
            )
        raise ValueError(f"unknown role: {role}")

    def _invoke_planner(self, *, manifest, goal, workspace, roles_cfg, session_name, replan_progress=None):
        """Invoke the planner; return a spec dict OR a `{"_questions": [...]}` sentinel.

        Shape A: planner emitted a normal SPEC JSON; returns the spec dict.
        Shape B: planner emitted `RALPH_QUESTIONS` with a `{"questions": [...]}`
        block; returns `{"_questions": [...], "_role_name": "planner-N"}` so
        the caller can park the run via `_park_for_questions`.
        """
        cfg = roles_cfg["roles"]["planner"]
        defaults = roles_cfg["defaults"]
        answers_block = self._format_answers(manifest)
        workflow_hint = manifest.get("operator_workflow_hint")
        context, retrieval_hits = self._planner_context(
            goal,
            workspace,
            defaults["memory_top_k"],
            replan_progress,
            answers_block,
            workflow_hint,
        )
        rid = f"{manifest['id']}-planner-{len(manifest.get('iterations', [])) + 1 if replan_progress else 1}"
        role_data = self._spawn_role(
            rid=rid,
            role_name=f"planner-{rid.split('-planner-')[-1]}",
            harness=cfg["harness"],
            model=cfg["model"],
            extra_args=cfg.get("extra_args", []),
            prompt_text=context,
            workspace=workspace,
            session_name=session_name,
            defaults=defaults,
        )
        role_data["retrieval_log"] = self._compress_retrieval_log(retrieval_hits)
        manifest.setdefault("roles", {})[role_data["name"]] = role_data
        manifest["learned_ids"] = list({*manifest.get("learned_ids", []), *role_data.get("learned_ids", [])})
        self.save_manifest(manifest)
        output_text = Path(role_data["output"]).read_text()
        try:
            questions = self._output_questions(output_text)
        except ValueError as err:
            raise SystemExit(f"planner emitted RALPH_QUESTIONS but block was unparseable: {err}")
        if questions is not None:
            return {"_questions": questions, "_role_name": role_data["name"]}
        try:
            spec = parse_json_block(output_text)
        except ValueError as err:
            raise SystemExit(f"planner output did not contain valid JSON spec: {err}")
        if "questions" in spec and not spec.get("target_artifact"):
            # Planner emitted a questions block but forgot the marker. Treat as Shape B.
            try:
                clean = parse_questions_block(output_text)
            except ValueError as inner:
                raise SystemExit(f"planner JSON had `questions` but no usable structure: {inner}")
            return {"_questions": clean, "_role_name": role_data["name"]}
        spec.setdefault("max_iterations", defaults["max_iterations"])
        spec.setdefault("max_minutes", defaults["max_minutes"])
        spec.setdefault("executor_count", 1)
        spec.setdefault("iteration_task_seed", "Make the first concrete change toward success_criteria.")
        spec.setdefault("workflow", DEFAULT_WORKFLOW)
        if spec["workflow"] not in WORKFLOWS:
            raise SystemExit(
                f"planner emitted unknown workflow: {spec['workflow']!r}; valid choices are {sorted(WORKFLOWS.keys())}"
            )
        executor_count = int(spec.get("executor_count") or 1)
        if executor_count != 1:
            raise SystemExit(
                "planner requested executor_count="
                f"{executor_count}, but Ralph currently supports exactly one executor per iteration. "
                "Set executor_count to 1 until true multi-executor orchestration is implemented."
            )
        # Persist spec as both top-level field and rendered spec.md for humans/replan.
        directory = self.run_dir(manifest["id"])
        (directory / "spec.md").write_text(self._render_spec_md(spec))
        return spec

    def _invoke_executor(self, *, manifest, spec, workspace, roles_cfg, session_name, iter_n, task):
        cfg = roles_cfg["roles"]["executor"]
        context, retrieval_hits = self._executor_context(manifest, spec, workspace, task, roles_cfg["defaults"])
        rid = f"{manifest['id']}-executor-{iter_n}"
        role_data = self._spawn_role(
            rid=rid,
            role_name=f"executor-{iter_n}",
            harness=cfg["harness"],
            model=cfg["model"],
            extra_args=cfg.get("extra_args", []),
            prompt_text=context,
            workspace=workspace,
            session_name=session_name,
            defaults=roles_cfg["defaults"],
        )
        role_data["retrieval_log"] = self._compress_retrieval_log(retrieval_hits)
        manifest.setdefault("roles", {})[role_data["name"]] = role_data
        manifest["learned_ids"] = list({*manifest.get("learned_ids", []), *role_data.get("learned_ids", [])})
        self.save_manifest(manifest)
        return role_data

    def _invoke_reviewer(self, *, manifest, spec, workspace, roles_cfg, session_name, iter_n, executor):
        cfg = roles_cfg["roles"]["reviewer"]
        context, retrieval_hits = self._reviewer_context(manifest, spec, workspace, executor, roles_cfg["defaults"])
        rid = f"{manifest['id']}-reviewer-{iter_n}"
        role_data = self._spawn_role(
            rid=rid,
            role_name=f"reviewer-{iter_n}",
            harness=cfg["harness"],
            model=cfg["model"],
            extra_args=cfg.get("extra_args", []),
            prompt_text=context,
            workspace=workspace,
            session_name=session_name,
            defaults=roles_cfg["defaults"],
        )
        role_data["retrieval_log"] = self._compress_retrieval_log(retrieval_hits)
        manifest.setdefault("roles", {})[role_data["name"]] = role_data
        output_text = Path(role_data["output"]).read_text()
        if QUESTIONS_MARKER in output_text:
            # Reviewer asked the human; loop handles parking. Leave verdict
            # absent so the loop's QUESTIONS branch is the sole consumer.
            role_data["verdict_obj"] = None
            self.save_manifest(manifest)
            return role_data
        try:
            verdict_obj = parse_json_block(output_text)
        except ValueError as err:
            verdict_obj = {
                "verdict": "fail",
                "notes": f"reviewer output unparseable: {err}",
                "criteria_met": [],
                "criteria_unmet": [],
            }
        role_data["verdict_obj"] = verdict_obj
        self.save_manifest(manifest)
        return role_data

    def _invoke_re_reviewer(
        self, *, manifest, spec, workspace, roles_cfg, session_name, iter_n, executor, primary_verdict
    ):
        cfg = roles_cfg["roles"]["re_reviewer"]
        context, retrieval_hits = self._re_reviewer_context(
            manifest, spec, workspace, executor, primary_verdict, roles_cfg["defaults"]
        )
        rid = f"{manifest['id']}-re_reviewer-{iter_n}"
        role_data = self._spawn_role(
            rid=rid,
            role_name=f"re_reviewer-{iter_n}",
            harness=cfg["harness"],
            model=cfg["model"],
            extra_args=cfg.get("extra_args", []),
            prompt_text=context,
            workspace=workspace,
            session_name=session_name,
            defaults=roles_cfg["defaults"],
        )
        role_data["retrieval_log"] = self._compress_retrieval_log(retrieval_hits)
        manifest.setdefault("roles", {})[role_data["name"]] = role_data
        output_text = Path(role_data["output"]).read_text()
        if QUESTIONS_MARKER in output_text:
            role_data["verdict_obj"] = None
            self.save_manifest(manifest)
            return role_data
        try:
            verdict_obj = parse_json_block(output_text)
        except ValueError as err:
            verdict_obj = {
                "agree_with_primary": True,
                "final_verdict": primary_verdict.get("verdict", "fail"),
                "notes": f"re_reviewer output unparseable: {err}; defaulting to primary verdict",
            }
        role_data["verdict_obj"] = verdict_obj
        self.save_manifest(manifest)
        return role_data

    def _invoke_reflector(
        self,
        *,
        manifest: dict[str, Any],
        spec: dict[str, Any],
        workspace: Path,
        roles_cfg: dict[str, Any],
        session_name: str | None,
    ) -> dict[str, Any] | None:
        """Run the reflector role on a successful run, parse its
        structured `{"capsules": [...]}` output, and store each capsule
        in the KB.

        Best-effort: returns None if the reflector is disabled, the
        workflow doesn't opt in, the reflector role isn't configured,
        or anything goes wrong during invocation/parsing. The
        orchestrator never blocks on reflector failure — the run
        already passed verification.

        Stores the role record under `manifest['roles']['reflector-1']`
        with the list of newly-stored capsule IDs in `learned_ids`.
        """
        defaults = roles_cfg.get("defaults") or {}
        if not defaults.get("reflector_enabled", False):
            return None
        workflow = manifest.get("workflow") or DEFAULT_WORKFLOW
        allowed = defaults.get("reflector_workflows") or []
        if workflow not in allowed:
            return None
        cfg = (roles_cfg.get("roles") or {}).get("reflector")
        if not cfg:
            return None

        # Reflector is one-shot per run; idempotent re-entry is a no-op
        # because we keep the role record once it exists.
        existing = (manifest.get("roles") or {}).get("reflector-1")
        if existing and existing.get("status") == "completed":
            return existing

        try:
            context = self._reflector_context(manifest, spec, workspace, defaults)
            rid = f"{manifest['id']}-reflector-1"
            role_data = self._spawn_role(
                rid=rid,
                role_name="reflector-1",
                harness=cfg["harness"],
                model=cfg["model"],
                extra_args=cfg.get("extra_args", []),
                prompt_text=context,
                workspace=workspace,
                session_name=session_name,
                defaults=defaults,
            )
        except Exception as err:
            self._append_decision(
                self.run_dir(manifest["id"]),
                f"reflector spawn failed (non-fatal): {err}",
            )
            return None
        manifest.setdefault("roles", {})[role_data["name"]] = role_data
        # Parse the structured output and turn each capsule into a real
        # KB row. capture_learnings already harvested any LEARNING:
        # lines from the role output (kind=fact by default for the
        # reflector role); the structured capsules below are the
        # primary product.
        output_text = ""
        try:
            output_text = Path(role_data["output"]).read_text()
        except (OSError, FileNotFoundError):
            pass
        new_ids: list[str] = []
        try:
            payload = parse_json_block(output_text) if output_text else {}
        except ValueError as err:
            self._append_decision(
                self.run_dir(manifest["id"]),
                f"reflector emitted unparseable JSON (non-fatal): {err}",
            )
            payload = {}
        capsules = payload.get("capsules") if isinstance(payload, dict) else None
        if isinstance(capsules, list):
            for entry in capsules:
                cid = self._store_reflector_capsule(entry, manifest=manifest, workspace=workspace)
                if cid:
                    new_ids.append(cid)
        if new_ids:
            role_data.setdefault("learned_ids", []).extend(new_ids)
            manifest["learned_ids"] = list({*manifest.get("learned_ids", []), *new_ids})
            self._append_decision(
                self.run_dir(manifest["id"]),
                f"reflector: stored {len(new_ids)} structured capsule(s)",
            )
        else:
            self._append_decision(
                self.run_dir(manifest["id"]),
                "reflector: 0 structured capsules (no durable lessons)",
            )
        self.save_manifest(manifest)
        return role_data

    def _store_reflector_capsule(
        self,
        entry: dict,
        *,
        manifest: dict[str, Any],
        workspace: Path,
    ) -> str | None:
        """Validate one entry from the reflector's `{"capsules":[...]}`
        list and persist it via `kb.remember()`. Returns the new
        capsule id or None if the entry was malformed.

        Validation is permissive: missing fields fall back to safe
        defaults so a half-formatted reflector output still produces
        usable capsules. Hard-invalid entries (non-dict, missing
        title/body) are skipped silently — the orchestrator already
        logged the run as complete.
        """
        if not isinstance(entry, dict):
            return None
        title = (entry.get("title") or "").strip()
        body = (entry.get("body") or "").strip()
        if not title or not body:
            return None
        kind = entry.get("kind") or "fact"
        if kind not in CAPSULE_KINDS:
            kind = "fact"
        scope = entry.get("scope") or "project"
        if scope not in CAPSULE_SCOPES:
            scope = "project"
        confidence = entry.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else 0.6
        except (TypeError, ValueError):
            confidence = 0.6
        domain_tags = entry.get("domain_tags") or []
        if not isinstance(domain_tags, list):
            domain_tags = []
        refs = entry.get("refs") or []
        if not isinstance(refs, list):
            refs = []
        try:
            capsule = self.kb.remember(
                title=title,
                body=body,
                kind=kind,
                scope=scope,
                source=f"ralph:{manifest['id']}:reflector",
                tags="ralph,reflector",
                workspace_path=str(workspace),
                domain_tags=[str(t) for t in domain_tags],
                confidence=max(0.0, min(1.0, confidence)),
                verified_by=manifest["id"],
                refs=[str(r) for r in refs],
            )
        except Exception:
            return None
        return capsule.id

    def _reflector_context(
        self,
        manifest: dict[str, Any],
        spec: dict[str, Any],
        workspace: Path,
        defaults: dict[str, Any],
    ) -> str:
        """Build the reflector's prompt body. Includes the spec, run
        summary counts, the tail of the last 2 iterations, the artifact
        state, and the list of capsule ids already harvested from
        per-role LEARNING: lines (so reflector can `refs` them and
        avoid storing duplicates).
        """
        directory = self.run_dir(manifest["id"])
        iters = manifest.get("iterations") or []
        completed_iters = [it for it in iters if it.get("phase") == ITER_PHASE_DECIDED]
        last_two = iters[-2:] if iters else []
        roles = manifest.get("roles") or {}
        # Tail of the last role outputs from the last 2 iterations.
        tails: list[str] = []
        for it in last_two:
            n = it.get("n", "?")
            for role_name in (f"executor-{n}", f"reviewer-{n}", f"re_reviewer-{n}"):
                role_data = roles.get(role_name) or {}
                out_path = role_data.get("output")
                if out_path:
                    tails.append(f"### {role_name}")
                    tails.append(self._tail_of(out_path, 80))
        artifact_summary = self._artifact_summary(spec.get("target_artifact"), workspace)
        learned_block = "\n".join(f"- {cid}" for cid in (manifest.get("learned_ids") or [])) or "(none)"
        run_summary = (
            f"- iterations: {len(completed_iters)}/{len(iters)}\n"
            f"- workflow: {manifest.get('workflow')}\n"
            f"- run id: {manifest.get('id')}\n"
            f"- final status: {manifest.get('status')}"
        )
        return (
            "\n".join(
                [
                    "## SPEC",
                    f"```json\n{json.dumps(spec, indent=2)}\n```",
                    "",
                    "## RUN SUMMARY",
                    run_summary,
                    "",
                    "## RECENT ITERATION TAILS",
                    "\n\n".join(tails) if tails else "(no iterations recorded)",
                    "",
                    "## ARTIFACT STATE",
                    artifact_summary,
                    "",
                    "## EXISTING LEARNINGS THIS RUN",
                    learned_block,
                    "",
                    "## WORKSPACE",
                    str(workspace),
                ]
            )
            + "\n"
        )

    def _spawn_role(
        self,
        *,
        rid: str,
        role_name: str,
        harness: str,
        model: str,
        extra_args: list[str],
        prompt_text: str,
        workspace: Path,
        session_name: str | None,
        defaults: dict[str, Any],
    ) -> dict[str, Any]:
        timeout = int(defaults["iteration_timeout_seconds"])
        prompt_path = load_role_prompt(role_name.split("-")[0])
        # role_prompt_path is the file the orchestrator will write the user
        # message to inside this role's run dir; we bake its absolute path
        # into the per-harness command so each harness can choose stdin vs
        # positional-arg supply explicitly.
        role_prompt_path = shlex.quote(str(self.run_dir(rid) / "prompt.md"))
        if harness == "pi":
            command_parts = [
                "pi",
                "-p",
                "--no-session",
                "--model",
                model,
                "--append-system-prompt",
                str(prompt_path),
                *extra_args,
            ]
            command = " ".join(shlex.quote(p) for p in command_parts) + f" < {role_prompt_path}"
        elif harness == "cursor":
            command_parts = [
                cursor_agent_binary(),
                "--print",
                "--output-format",
                "text",
                "--trust",
                "--workspace",
                str(workspace),
                "--model",
                model,
                *extra_args,
            ]
            # cursor-agent reads the prompt as the trailing positional arg;
            # we MUST NOT redirect stdin too — when both are provided
            # cursor-agent stalls indefinitely.
            command = " ".join(shlex.quote(p) for p in command_parts) + f' -- "$(cat {role_prompt_path})"'
        elif harness == "command":
            command = (" ".join(extra_args) if extra_args else model) + f" < {role_prompt_path}"
        else:
            raise SystemExit(f"unknown harness for role {role_name}: {harness}")

        # Compose the full prompt body sent on stdin: role system prompt is
        # already wired via --append-system-prompt for pi; for cursor we inline
        # it at the top of the user message so the role identity travels with
        # the context.
        if harness == "cursor":
            prompt_body = f"# ROLE PROMPT\n\n{prompt_path.read_text()}\n\n---\n\n{prompt_text}"
        else:
            prompt_body = prompt_text

        if session_name and tmux_session_exists(session_name):
            return self.execute_tmux_role(
                rid=rid,
                role_name=role_name,
                goal=prompt_text.splitlines()[0] if prompt_text else role_name,
                command=command,
                memory_query=None,
                memory_limit=0,
                acceptance="See role prompt; emit RALPH_DONE on completion.",
                expect=DONE_MARKER,
                workspace=workspace,
                timeout=timeout,
                session_name=session_name,
                window_name=tmux_name(role_name)[:30],
                create_session=False,
                keep_window=False,
                prompt_override=prompt_body,
            )
        return self._execute_subprocess_role(
            rid=rid,
            role_name=role_name,
            command=command,
            prompt_body=prompt_body,
            workspace=workspace,
            timeout=timeout,
            expect=DONE_MARKER,
        )

    def _execute_subprocess_role(self, *, rid, role_name, command, prompt_body, workspace, timeout, expect):
        directory = self.run_dir(rid)
        directory.mkdir(parents=True, exist_ok=True)
        prompt_path = directory / "prompt.md"
        prompt_path.write_text(redact(prompt_body))
        # Run inside the workspace so relative paths resolve as the planner intended.
        cwd_command = f"cd {shlex.quote(str(workspace))} && {command}"
        result = self.runtime_command(cwd_command, prompt_body, timeout)
        output = redact(result.output)
        output_path = directory / "output.log"
        output_path.write_text(output)
        learned_ids = self.capture_learnings(rid, output, role=role_name, workspace=str(workspace))
        completed = result.exit_code == 0 and expect in output
        manifest = {
            "id": rid,
            "kind": "role",
            "name": role_name,
            "created_at": utc_now(),
            "goal": role_name,
            "runtime": "subprocess",
            "status": "completed" if completed else "failed",
            "exit_code": result.exit_code,
            "expect": expect,
            "timeout_seconds": timeout,
            "control_state": "automated",
            "validation_status": role_validation_status(
                {
                    "status": "completed" if completed else "failed",
                    "exit_code": result.exit_code,
                    "output": str(output_path),
                }
            ),
            "last_validated_at": utc_now(),
            "learned_ids": learned_ids,
            "command": command,
            "workspace": str(workspace),
            "prompt": str(prompt_path),
            "output": str(output_path),
            "tmux": None,
        }
        self.save_manifest(manifest)
        return manifest

    # --- context builders ---------------------------------------------------

    def _planner_context(
        self,
        goal: str,
        workspace: Path,
        top_k: int,
        replan_progress: str | None,
        answers_block: str | None = None,
        workflow_hint: str | None = None,
    ) -> tuple[str, list[dict]]:
        """Build the planner prompt body. Returns (text, retrieval_hits)
        so the orchestrator can persist a `retrieval_log` per role."""
        # Planner gets the broadest KB slice — any prior learning may
        # influence planning. Workspace-bias surfaces project-local
        # capsules first; universal/principle capsules still mix in.
        learnings, hits = self._fetch_learnings(goal, top_k, workspace=str(workspace))
        sections = [
            "## GOAL",
            goal.strip(),
            "",
            "## WORKSPACE",
            str(workspace),
            "",
            "## RECENT LEARNINGS",
            learnings or "(none)",
        ]
        if workflow_hint:
            sections += [
                "",
                "## OPERATOR HINT",
                f"The operator selected workflow=`{workflow_hint}` in the run launcher. "
                "Honor this unless the goal materially conflicts with that workflow shape; "
                "if you override it, explain why in `rationale`.",
            ]
        if replan_progress:
            sections += ["", "## PRIOR PROGRESS (replan)", replan_progress]
        if answers_block:
            sections += ["", "## ANSWERS", answers_block]
        return "\n".join(sections) + "\n", hits

    def _executor_context(self, manifest, spec, workspace, task, defaults):
        progress_tail = self._read_progress_tail(self.run_dir(manifest["id"]), defaults["progress_tail_blocks"])
        # Executor query blends goal with the per-iteration task so the
        # KB lane can also surface task-specific recipes/gotchas. Filter
        # to the kinds an implementer benefits from — not principles
        # (those are for the verifier roles).
        executor_query = " ".join(
            [
                spec.get("goal") or manifest["goal"],
                task,
                spec.get("target_artifact") or "",
                manifest.get("workflow") or "",
            ]
        ).strip()
        learnings, hits = self._fetch_learnings(
            executor_query,
            defaults["memory_top_k"],
            kinds=["fact", "recipe", "gotcha", "anti_pattern", "pattern"],
            workspace=str(workspace),
        )
        artifact_summary = self._artifact_summary(spec.get("target_artifact"), workspace)
        text = (
            "\n".join(
                [
                    "## SPEC",
                    f"```json\n{json.dumps(spec, indent=2)}\n```",
                    "",
                    "## TASK FOR THIS ITERATION",
                    task,
                    "",
                    "## PROGRESS TAIL",
                    progress_tail or "(no prior iterations)",
                    "",
                    "## RECENT LEARNINGS",
                    learnings or "(none)",
                    "",
                    "## ARTIFACT STATE",
                    artifact_summary,
                ]
            )
            + "\n"
        )
        return text, hits

    def _reviewer_context(self, manifest, spec, workspace, executor, defaults):
        executor_path = (executor or {}).get("output")
        if executor_path:
            executor_section = self._tail_of(executor_path, 200)
        else:
            executor_section = "(no executor in this workflow; review the artifact directly against the SPEC)"
        progress_tail = self._read_progress_tail(self.run_dir(manifest["id"]), defaults["progress_tail_blocks"])
        artifact_summary = self._artifact_summary(spec.get("target_artifact"), workspace)
        # Reviewer gets the gotcha/anti_pattern slice — its job is to
        # spot what's wrong; relevant prior failure modes are the most
        # useful prompt context.
        criteria_blob = " ".join(spec.get("success_criteria") or [])
        learnings, hits = self._fetch_learnings(
            f"{spec.get('goal') or manifest['goal']} {criteria_blob}",
            defaults["memory_top_k"],
            kinds=["gotcha", "anti_pattern"],
            workspace=str(workspace),
        )
        sections: list[str] = []
        if is_elastic_workspace(workspace):
            preamble = elastic_review_preamble("reviewer")
            if preamble:
                sections.append(preamble)
        sections.extend(
            [
                "## SPEC",
                f"```json\n{json.dumps(spec, indent=2)}\n```",
                "",
                "## EXECUTOR OUTPUT (this iteration)",
                executor_section,
                "",
                "## ARTIFACT STATE",
                artifact_summary,
                "",
                "## PROGRESS TAIL",
                progress_tail or "(no prior iterations)",
                "",
                "## RECENT LEARNINGS",
                learnings or "(none)",
            ]
        )
        text = "\n".join(sections) + "\n"
        return text, hits

    def _re_reviewer_context(self, manifest, spec, workspace, executor, primary_verdict, defaults):
        executor_tail = self._tail_of(executor["output"], 200)
        progress_tail = self._read_progress_tail(self.run_dir(manifest["id"]), defaults["progress_tail_blocks"])
        artifact_summary = self._artifact_summary(spec.get("target_artifact"), workspace)
        # Re-reviewer gets gotcha + anti_pattern + principle. Principles
        # capture verification heuristics ("if reviewer says pass on
        # criterion X, double-check Y too") — exactly what an
        # adversarial second-opinion role benefits from.
        criteria_blob = " ".join(spec.get("success_criteria") or [])
        verdict_notes = (primary_verdict or {}).get("notes") or ""
        learnings, hits = self._fetch_learnings(
            f"{spec.get('goal') or manifest['goal']} {criteria_blob} {verdict_notes}",
            defaults["memory_top_k"],
            kinds=["gotcha", "anti_pattern", "principle"],
            workspace=str(workspace),
        )
        sections: list[str] = []
        if is_elastic_workspace(workspace):
            preamble = elastic_review_preamble("re_reviewer")
            if preamble:
                sections.append(preamble)
        sections.extend(
            [
                "## SPEC",
                f"```json\n{json.dumps(spec, indent=2)}\n```",
                "",
                "## EXECUTOR OUTPUT",
                executor_tail,
                "",
                "## PRIMARY REVIEWER VERDICT",
                f"```json\n{json.dumps(primary_verdict, indent=2)}\n```",
                "",
                "## ARTIFACT STATE",
                artifact_summary,
                "",
                "## PROGRESS TAIL",
                progress_tail or "(no prior iterations)",
                "",
                "## RECENT LEARNINGS",
                learnings or "(none)",
            ]
        )
        text = "\n".join(sections) + "\n"
        return text, hits

    @staticmethod
    def _compress_retrieval_log(hits: list[dict]) -> list[dict]:
        """Strip a search-hit list down to the small subset the TUI
        and curator care about. Avoids ballooning the role manifest
        with body text and float scores nobody renders.

        We keep id (so the TUI can `,ai-kb get` for full content),
        title (one-line preview), kind (taxonomy badge), scope
        (badge), confidence (color hint), and rrf_score (rank order).
        """
        out: list[dict] = []
        for h in hits or []:
            out.append(
                {
                    "id": h.get("id"),
                    "title": h.get("title"),
                    "kind": h.get("kind"),
                    "scope": h.get("scope"),
                    "confidence": h.get("confidence"),
                    "rrf_score": h.get("rrf_score"),
                }
            )
        return out

    def _fetch_learnings(
        self,
        query: str,
        top_k: int,
        *,
        kinds: list[str] | None = None,
        scope: list[str] | None = None,
        workspace: str | None = None,
    ) -> tuple[str, list[dict]]:
        """Pull top-K capsule bodies relevant to `query` (filtered by
        kind/scope/workspace) and format them as bullets for the
        `## RECENT LEARNINGS` prompt section.

        Returns (formatted_text, hits). The orchestrator persists the
        raw `hits` into the role's `retrieval_log` manifest field so
        the TUI can show "which capsules fed this prompt". Hits are
        the JSON-friendly shape returned by `kb.search()` and include
        kind/scope/score breakdown for diagnostics.

        Prefers the capsule body (the actual lesson) over snippet over
        title — bare titles like `Ralph learning go-…-executor-1`
        carry no useful signal.

        Soft-fails: any error or unavailable KB returns ("", []) so
        the caller can render `(none)` and continue.
        """
        if top_k <= 0:
            return "", []
        try:
            hits = (
                self.kb.search(
                    query,
                    limit=top_k,
                    kind=kinds,
                    scope=scope,
                    workspace=workspace,
                )
                if hasattr(self, "kb") and self.kb
                else []
            )
        except Exception:
            hits = []
        if not hits:
            return "", []
        lines = []
        for h in hits:
            body_text = (h.get("body") or "").strip()
            if not body_text:
                body_text = (h.get("snippet") or "").strip()
            if not body_text:
                body_text = h.get("title", "") or ""
            first = body_text.splitlines()[0] if body_text else ""
            lines.append(f"- {first}")
        return "\n".join(lines), hits

    def _artifact_summary(self, target: str | None, workspace: Path | None = None) -> str:
        if not target or target == "none":
            return "(no artifact path declared)"
        p = Path(target).expanduser()
        if not p.is_absolute() and workspace:
            p = (workspace / p).resolve()
        if not p.exists():
            return f"(target {p} does not exist yet)"
        try:
            content = p.read_text()
        except Exception as err:
            return f"(cannot read {p}: {err})"
        if len(content) > 4000:
            return content[:2000] + f"\n\n... [{len(content) - 4000} bytes elided] ...\n\n" + content[-2000:]
        return content

    def _tail_of(self, path_str: str | None, lines: int) -> str:
        if not path_str:
            return "(no output)"
        p = Path(path_str)
        if not p.exists():
            return "(output file missing)"
        text = p.read_text()
        return "\n".join(text.splitlines()[-lines:])

    # --- progress / verdict / decisions persistence -------------------------

    def _append_progress(self, directory: Path, iter_n: int, role: str, role_data: dict):
        progress = directory / "progress.md"
        block = [
            f"## iter {iter_n} — {role} ({role_data.get('id')})",
            f"status: {role_data.get('status')}  validation: {role_data.get('validation_status')}",
        ]
        if role_data.get("verdict_obj"):
            block.append("verdict: " + json.dumps(role_data["verdict_obj"]))
        out = role_data.get("output")
        if out and Path(out).exists():
            tail = "\n".join(Path(out).read_text().splitlines()[-15:])
            block += ["", "```", tail, "```"]
        block.append("")
        with progress.open("a") as f:
            f.write("\n".join(block) + "\n")

    def _read_progress(self, directory: Path) -> str:
        p = directory / "progress.md"
        return p.read_text() if p.exists() else ""

    def _read_progress_tail(self, directory: Path, n_blocks: int) -> str:
        text = self._read_progress(directory)
        if not text:
            return ""
        # Blocks separated by lines starting with '## iter'
        blocks = re.split(r"(?=^## iter )", text, flags=re.MULTILINE)
        blocks = [b for b in blocks if b.strip()]
        return "".join(blocks[-n_blocks:])

    def _append_verdict(self, directory: Path, iter_n: int, role: str, verdict: dict):
        with (directory / "verdicts.jsonl").open("a") as f:
            f.write(json.dumps({"iter": iter_n, "role": role, "verdict": verdict, "at": utc_now()}) + "\n")

    def _append_decision(self, directory: Path, msg: str):
        with (directory / "decisions.log").open("a") as f:
            f.write(f"{utc_now()}\t{msg}\n")

    def _write_summary(self, manifest: dict[str, Any], workspace: Path) -> Path:
        """Write the anchored `summary.md` at workflow end.

        This is the "scan in 30 seconds" trust artifact: original goal verbatim,
        workflow used, success criteria check-list, artifact path+sha, open
        questions (if any), and a tail of the decisions log. Always rewrites
        on each call so the latest run state wins.
        """
        directory = self.run_dir(manifest["id"])
        spec = manifest.get("spec") or {}
        criteria = list(spec.get("success_criteria") or [])
        verdicts: list[dict[str, Any]] = []
        verdicts_path = directory / "verdicts.jsonl"
        if verdicts_path.exists():
            for line in verdicts_path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    verdicts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        # Prefer the reviewer's verdict over the re_reviewer's because
        # only the reviewer carries `criteria_met` / `criteria_unmet`
        # arrays. The re_reviewer's verdict shape is
        # `{agree_with_primary, final_verdict, ...}` — using it as the
        # source of criteria markers leaves every criterion as `[?]` even
        # when the reviewer accepted them all.
        last_verdict_obj: dict[str, Any] = {}
        for entry in reversed(verdicts):
            if entry.get("role") != "reviewer":
                continue
            verdict = entry.get("verdict") or {}
            if verdict:
                last_verdict_obj = verdict
                break
        if not last_verdict_obj:
            # Workflows without a reviewer (none today) or runs that
            # ended before any reviewer ran — fall back to the most
            # recent non-empty verdict so summary markers still convey
            # whatever signal we have.
            for entry in reversed(verdicts):
                verdict = entry.get("verdict") or {}
                if verdict:
                    last_verdict_obj = verdict
                    break
        criteria_met = list(last_verdict_obj.get("criteria_met") or [])
        criteria_unmet = list(last_verdict_obj.get("criteria_unmet") or [])
        met_set = {c.strip() for c in criteria_met}
        unmet_set = {c.strip() for c in criteria_unmet}

        def status_marker(criterion: str) -> str:
            cleaned = (criterion or "").strip()
            if cleaned in met_set:
                return "[x]"
            if cleaned in unmet_set:
                return "[ ]"
            return "[?]"

        artifact = manifest.get("artifact") or "(none)"
        sha = manifest.get("artifact_sha256") or "(unset)"
        questions = manifest.get("questions") or []
        open_qs = [q for q in questions if not q.get("answered_at")]
        decisions_path = directory / "decisions.log"
        decisions_tail: list[str] = []
        if decisions_path.exists():
            decisions_tail = decisions_path.read_text().splitlines()[-15:]
        validation_warnings = (manifest.get("validation") or {}).get("warnings") or []
        lines = [
            f"# Ralph run summary — {manifest.get('id')}",
            "",
            f"**Status:** {manifest.get('status')}  ",
            f"**Validation:** {manifest.get('validation_status') or '(unset)'}  ",
            f"**Workflow:** {manifest.get('workflow') or DEFAULT_WORKFLOW}",
            "",
        ]
        if validation_warnings:
            lines += [
                "## Warnings",
                "",
            ]
            for w in validation_warnings:
                role_name = w.get("role", "?")
                vs = w.get("validation_status", "?")
                cs = w.get("control_state", "?")
                lines.append(f"- **{role_name}**: validation_status=`{vs}`, control_state=`{cs}`")
            lines.append("")
        lines += [
            "## Goal (verbatim)",
            "",
            "> " + (manifest.get("goal") or "").strip().replace("\n", "\n> "),
            "",
            "## Workflow rationale",
            "",
            spec.get("rationale") or "(no rationale recorded)",
            "",
            "## Success criteria",
            "",
        ]
        if criteria:
            for c in criteria:
                lines.append(f"- {status_marker(c)} {c}")
        else:
            lines.append("- (planner emitted none)")
        lines += [
            "",
            "## Artifact",
            "",
            f"- Path: `{artifact}`",
            f"- sha256: `{sha}`",
            f"- Hash gate: `{manifest.get('artifact_ok')}`",
            "",
            "## Open questions",
            "",
        ]
        if open_qs:
            for q in open_qs:
                lines.append(f"- **{q.get('id')}**: {q.get('text')}")
        else:
            lines.append("- (none)")
        if questions and any(q.get("answered_at") for q in questions):
            lines += ["", "## Answered questions"]
            for q in questions:
                if not q.get("answered_at"):
                    continue
                lines.append(f"- **{q['id']}** ({q.get('role')}): {q.get('text')}")
                lines.append(f"  → {q.get('answer')}")
        lines += [
            "",
            "## Decisions tail",
            "",
            "```",
            *decisions_tail,
            "```",
            "",
        ]
        path = directory / "summary.md"
        path.write_text("\n".join(lines))
        manifest["summary_path"] = str(path)
        return path

    def _finalize_iteration(
        self,
        manifest: dict[str, Any],
        *,
        iter_idx: int,
        n: int,
        workspace: Path,
        primary_verdict: dict[str, Any],
        final_verdict: dict[str, Any],
        re_reviewer_id: str | None,
    ) -> tuple[str, dict[str, Any]]:
        """Apply the final verdict to the iteration record and decide next step.

        Returns one of `("complete", "blocked", "failed", "continue")` plus the
        updated manifest. Writes `summary.md` for any terminal outcome.
        """
        rid = manifest["id"]
        directory = self.run_dir(rid)
        workflow = manifest.get("workflow") or DEFAULT_WORKFLOW
        phases = workflow_phases(workflow)
        iter_rec = manifest["iterations"][iter_idx]
        if re_reviewer_id is not None:
            iter_rec["re_reviewer_id"] = re_reviewer_id
        resolved = final_verdict.get("final_verdict") or final_verdict.get("verdict") or "fail"
        iter_rec["verdict"] = resolved
        iter_rec["ended_at"] = utc_now()
        iter_rec["phase"] = ITER_PHASE_DECIDED
        iter_rec["next_task"] = (
            final_verdict.get("next_task")
            or primary_verdict.get("next_task")
            or "Address reviewer feedback above and re-attempt."
        )
        # Workflows without an executor (e.g. "review") cannot iterate; collapse
        # needs_iteration to fail so the run terminates instead of looping.
        has_executor = ITER_PHASE_EXEC in phases
        if not has_executor and resolved == "needs_iteration":
            resolved = "fail"
            iter_rec["verdict"] = "fail"

        if resolved == "pass":
            self._freeze_artifact_hash(manifest, workspace)
            manifest["phase"] = "done"
            manifest["status"] = "completed"
            manifest["validation"] = self.validation_for_manifest(manifest)
            manifest["validation_status"] = manifest["validation"]["status"]
            if manifest["validation_status"] not in ("passed", "passed_with_warnings"):
                manifest["phase"] = "failed"
                manifest["status"] = "failed"
                self._append_decision(
                    directory,
                    f"iter {n}: PASS verdict rejected by validation ({manifest['validation_status']})",
                )
                self._write_summary(manifest, workspace)
                self.save_manifest(manifest)
                return "failed", manifest
            if manifest["validation_status"] == "passed_with_warnings":
                warnings = manifest["validation"].get("warnings") or []
                role_names = ", ".join(w.get("role", "?") for w in warnings) or "n/a"
                self._append_decision(
                    directory,
                    f"iter {n}: PASS with role-scaffolding warnings ({role_names}), run complete",
                )
            else:
                self._append_decision(directory, f"iter {n}: PASS, run complete")
            self._write_summary(manifest, workspace)
            self.save_manifest(manifest)
            return "complete", manifest
        if resolved == "block":
            manifest["phase"] = "blocked"
            manifest["status"] = "needs_human"
            manifest["validation_status"] = "needs_verification"
            manifest["control_state"] = "manual_control"
            manifest["block_reason"] = final_verdict.get("blocking_reason") or final_verdict.get("notes") or "blocked"
            self._append_decision(
                directory,
                f"iter {n}: BLOCK -> escalating to human ({manifest['block_reason']})",
            )
            self._write_summary(manifest, workspace)
            self.save_manifest(manifest)
            return "blocked", manifest
        if resolved == "fail":
            manifest["phase"] = "failed"
            manifest["status"] = "failed"
            manifest["validation_status"] = "failed"
            self._append_decision(
                directory,
                f"iter {n}: FAIL ({workflow}) -> ending without retry",
            )
            self._write_summary(manifest, workspace)
            self.save_manifest(manifest)
            return "failed", manifest
        # needs_iteration → loop continues; caller seeds next_task.
        self.save_manifest(manifest)
        return "continue", manifest

    def _render_spec_md(self, spec: dict[str, Any]) -> str:
        return (
            "# Ralph spec\n\n"
            f"Goal: {spec.get('goal')}\n\n"
            f"Target artifact: `{spec.get('target_artifact')}`\n\n"
            f"Complexity: {spec.get('complexity')}\n\n"
            f"Caps: max_iterations={spec.get('max_iterations')}, max_minutes={spec.get('max_minutes')}\n\n"
            "Success criteria:\n" + "\n".join(f"- {c}" for c in spec.get("success_criteria", [])) + "\n\n"
            f"Iteration task seed: {spec.get('iteration_task_seed')}\n\n"
            f"Rationale: {spec.get('rationale')}\n\n"
            "```json\n" + json.dumps(spec, indent=2) + "\n```\n"
        )

    def capture_learnings(
        self,
        rid: str,
        output: str,
        *,
        role: str | None = None,
        workspace: str | None = None,
    ) -> list[str]:
        """Scan a role's output for `LEARNING:` lines and persist each
        as a structured capsule. The capsule's `kind` is inferred from
        the role base-name (planner/executor → fact, reviewer → gotcha,
        re_reviewer → principle, reflector → fact). The `scope` is
        `project` whenever a workspace path is known so retrieval can
        bias toward project-local capsules; otherwise `universal`.

        Tags include the role base-name so the TUI / curator can filter
        by source-role later. Returns the list of new capsule IDs so
        the role manifest can record them in `learned_ids`.
        """
        learned_ids: list[str] = []
        kind = _kind_for_role(role)
        scope = "project" if workspace else "universal"
        role_base = (role or "").split("-")[0] or "unknown"
        for line in output.splitlines():
            if not line.startswith(LEARNING_PREFIX):
                continue
            body = line[len(LEARNING_PREFIX) :].strip()
            if not body:
                continue
            capsule = self.kb.remember(
                title=f"{role_base} learning · {body[:60]}",
                body=body,
                kind=kind,
                scope=scope,
                source=f"ralph:{rid}",
                tags=f"ralph,session-learning,{role_base}",
                workspace_path=workspace,
                domain_tags=[role_base],
                confidence=0.6,  # raw role-emitted; reflector raises this on verification
                verified_by=None,
            )
            learned_ids.append(capsule.id)
        return learned_ids

    def write_latest(self, rid: str) -> None:
        self.state_home.mkdir(parents=True, exist_ok=True)
        (self.state_home / "latest-run.txt").write_text(rid)

    def latest_run_id(self) -> str | None:
        """Return the most-recent run id, self-healing past a stale pointer.

        `latest-run.txt` is written at run creation but never cleaned up by
        `rm`, so a routine `,ralph rm <rid>` followed by `,ralph dashboard`
        used to crash with "run manifest not found: <archived-rid>". We now
        validate the cached pointer against `manifest_path()` and fall back
        to scanning `runs_dir` for the newest go-kind manifest by mtime when
        the pointer is stale, returning `None` only when neither lane has a
        live run.
        """
        path = self.state_home / "latest-run.txt"
        rid = path.read_text().strip() if path.exists() else ""
        if rid and self.manifest_path(rid).exists():
            return rid
        return self._latest_go_run_by_mtime()

    def _latest_go_run_by_mtime(self) -> str | None:
        if not self.runs_dir.exists():
            return None
        for manifest_path in sorted(
            self.runs_dir.glob("*/manifest.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                manifest = json.loads(manifest_path.read_text())
            except Exception:
                continue
            if manifest.get("kind") == "go" and manifest.get("id"):
                return manifest["id"]
        return None

    def manifest_path(self, rid: str) -> Path:
        return self.run_dir(rid) / "manifest.json"

    def save_manifest(self, manifest: dict[str, Any]) -> None:
        rid = manifest.get("id")
        if not rid:
            raise SystemExit("manifest has no id")
        path = self.manifest_path(rid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2))

    def load_manifest(self, rid: str | None) -> dict[str, Any]:
        actual_id = rid or self.latest_run_id()
        if not actual_id:
            raise SystemExit("no runs found")
        path = self.manifest_path(actual_id)
        if not path.exists():
            raise SystemExit(f"run manifest not found: {actual_id}")
        return json.loads(path.read_text())

    def list_runs(
        self,
        limit: int = 50,
        current_workspace: Path | None = None,
        session: str | None = None,
    ) -> list[dict[str, Any]]:
        self.init()
        manifests: list[dict[str, Any]] = []
        if not self.runs_dir.exists():
            return manifests
        workspace_resolved = current_workspace.expanduser().resolve() if current_workspace else None
        for path in sorted(self.runs_dir.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                manifest = json.loads(path.read_text())
            except Exception:
                continue
            if manifest.get("kind") == "role":
                continue
            workspace = manifest.get("workspace")
            if workspace_resolved and workspace:
                try:
                    if Path(workspace).expanduser().resolve() != workspace_resolved:
                        continue
                except Exception:
                    continue
            if session:
                target_session = (manifest.get("tmux") or {}).get("session")
                if target_session != session:
                    continue
            manifests.append(self.summarize_manifest(manifest))
            if len(manifests) >= limit:
                break
        return manifests

    def summarize_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        roles = manifest.get("roles") or {}
        validation = manifest.get("validation") or {}
        created_at = manifest.get("created_at")
        age_seconds = None
        if created_at:
            try:
                age_seconds = max(0.0, time.time() - datetime.fromisoformat(created_at).timestamp())
            except ValueError:
                age_seconds = None
        return {
            "id": manifest.get("id"),
            "short_id": short_id(manifest.get("id") or ""),
            "name": manifest.get("name"),
            "kind": manifest.get("kind") or "go",
            "phase": manifest.get("phase"),
            "iterations_count": len(manifest.get("iterations") or []),
            "created_at": created_at,
            "age_seconds": age_seconds,
            "goal": manifest.get("goal"),
            "runtime": manifest.get("runtime"),
            "mode": manifest.get("mode"),
            "status": manifest.get("status"),
            "workspace": manifest.get("workspace"),
            "artifact": manifest.get("artifact"),
            "artifact_ok": manifest.get("artifact_ok"),
            "validation_status": validation.get("status") or manifest.get("validation_status"),
            "tmux": manifest.get("tmux"),
            "roles": {name: role_summary(role) for name, role in roles.items()},
            "learned_count": len(manifest.get("learned_ids", [])),
        }

    def validation_for_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        roles = manifest.get("roles") or {}
        role_gates = {
            name: {
                "status": role.get("status") == "completed",
                "validation_status": role.get("validation_status", role_validation_status(role)),
                "control_state": role.get("control_state", "automated"),
            }
            for name, role in roles.items()
        }
        artifact = manifest.get("artifact")
        expected_hash = manifest.get("artifact_sha256")
        artifact_exists = bool(artifact and Path(artifact).exists())
        artifact_hash = sha256_file(Path(artifact)) if artifact_exists else None
        artifact_ok = artifact_exists and (not expected_hash or expected_hash == artifact_hash) if artifact else True
        needs_verification = any(
            gate["control_state"] in ("manual_control", "dirty_control", "resume_requested")
            or gate["validation_status"] == "needs_verification"
            for gate in role_gates.values()
        )
        roles_ok = all(
            gate["status"] and gate["validation_status"] == "passed" and gate["control_state"] == "automated"
            for gate in role_gates.values()
        )
        # For "go" runs, the final reviewer verdict still drives completion,
        # but validation must also prove the supporting gates: automated roles
        # and artifact integrity when an artifact is declared.
        #
        # `passed_with_warnings` covers the case where the iteration verdict
        # reached PASS (so top_status flipped to "completed"), the artifact
        # exists and matches the expected hash, but a role-level scaffolding
        # gate (typically a missing or malformed ANCHOR line in role output)
        # came back failed. Treating that as a hard failure used to drop the
        # whole run on a cosmetic violation; demoting it to a warning keeps
        # the success signal honest while still surfacing the breach.
        if manifest.get("kind") == "go":
            top_status = manifest.get("status")
            if top_status == "completed":
                if roles_ok and artifact_ok:
                    status = "passed"
                elif needs_verification:
                    status = "needs_verification"
                elif artifact_ok:
                    status = "passed_with_warnings"
                else:
                    status = "failed"
            elif top_status == "needs_human":
                status = "needs_verification"
            elif top_status in ("failed", "killed"):
                status = "failed"
            else:
                status = "needs_verification"
        elif needs_verification:
            status = "needs_verification"
        else:
            status = (
                "passed"
                if all(g["status"] and g["validation_status"] == "passed" for g in role_gates.values()) and artifact_ok
                else "failed"
            )
        warnings: list[dict[str, str]] = []
        if status == "passed_with_warnings":
            for name, gate in role_gates.items():
                if gate["status"] and gate["validation_status"] == "passed" and gate["control_state"] == "automated":
                    continue
                warnings.append(
                    {
                        "role": name,
                        "validation_status": gate["validation_status"],
                        "control_state": gate["control_state"],
                    }
                )
        return {
            "status": status,
            "validated_at": utc_now(),
            "artifact": {
                "path": artifact,
                "exists": artifact_exists,
                "sha256": artifact_hash,
                "expected_sha256": expected_hash,
                "ok": artifact_ok,
            }
            if artifact
            else None,
            "roles": role_gates,
            "warnings": warnings,
        }

    def validate_run(self, rid: str | None) -> dict[str, Any]:
        manifest = self.load_manifest(rid)
        for role in (manifest.get("roles") or {}).values():
            if role.get("control_state") != "resume_requested":
                continue
            role["validation_status"] = role_validation_status(role)
            if role["validation_status"] == "passed":
                role["control_state"] = "automated"
            role["last_validated_at"] = utc_now()
        manifest["validation"] = self.validation_for_manifest(manifest)
        if not self._blocking_control_roles(manifest) and manifest.get("status") == "needs_human":
            manifest = self._unpark_if_control_clear(manifest)
        self.save_manifest(manifest)
        return manifest["validation"]

    def set_role_control(self, rid: str | None, role: str, action: str) -> dict[str, Any]:
        if action not in CONTROL_STATE_BY_ACTION:
            raise SystemExit(f"unknown control action: {action}")
        manifest = self.load_manifest(rid)
        roles = manifest.get("roles") or {}
        if role not in roles:
            raise SystemExit(f"role not found: {role}")
        roles[role]["control_state"] = CONTROL_STATE_BY_ACTION[action]
        if action in ("takeover", "dirty", "resume"):
            if action in ("takeover", "dirty") and manifest.get("status") != "needs_human":
                manifest["pre_control_status"] = manifest.get("status")
            roles[role]["validation_status"] = "needs_verification"
            manifest["status"] = "needs_human"
            manifest["validation_status"] = "needs_verification"
            manifest["control_state"] = "manual_control"
        else:
            roles[role]["validation_status"] = role_validation_status(roles[role])
            if not self._blocking_control_roles(manifest):
                manifest["status"] = "running" if manifest.get("status") == "needs_human" else manifest.get("status")
                manifest["control_state"] = "automated"
                manifest.pop("blocked_roles", None)
        roles[role]["control_updated_at"] = utc_now()
        manifest["validation"] = self.validation_for_manifest(manifest)
        self.save_manifest(manifest)
        if action == "resume":
            self.validate_run(rid or manifest["id"])
            updated = self.load_manifest(rid or manifest["id"])
            updated = self._unpark_if_control_clear(updated)
            return updated["roles"][role]
        return roles[role]

    def role_detail(self, rid: str | None, role: str | None) -> dict[str, Any]:
        manifest = self.load_manifest(rid)
        if not role:
            return manifest
        roles = manifest.get("roles") or {}
        if role not in roles:
            raise SystemExit(f"role not found: {role}")
        return roles[role]

    def preview(self, rid: str | None, role: str | None, mode: str = "summary") -> str:
        manifest = self.role_manifest(rid, role)
        if role:
            tmux = manifest.get("tmux") or {}
            output_path = manifest.get("output")
            output_age = output_age_seconds(Path(output_path)) if output_path else None
            lines = [
                f"\x1b[1mRole: {role}\x1b[0m",
                f"Status: {manifest.get('status')}  Validation: {manifest.get('validation_status')}",
                f"Control: {manifest.get('control_state', 'automated')}",
                f"Pane: {tmux.get('pane', '-')}  Session: {tmux.get('session', '-')}  Window: {tmux.get('window', '-')}",
                f"Output: {output_path or '-'} ({humanize_age(output_age)} ago)",
                "",
            ]
            tail_lines = 200 if mode == "tail" else 40
            if output_path and Path(output_path).exists():
                content = redact(Path(output_path).read_text())
                lines.extend(content.splitlines()[-tail_lines:])
            return "\n".join(lines)
        validation = manifest.get("validation") or {}
        validation_label = validation.get("status") or manifest.get("validation_status") or "-"
        roles = manifest.get("roles") or {}
        kind = manifest.get("kind") or "go"
        phase = manifest.get("phase") or "-"
        lines = [
            f"\x1b[1mRun: {manifest.get('id')}\x1b[0m",
            f"Kind: {kind}  Phase: {phase}  Runtime: {manifest.get('runtime')}",
            f"Status: {manifest.get('status')}  Validation: {validation_label}",
            f"Goal: {manifest.get('goal')}",
        ]
        if manifest.get("workspace"):
            lines.append(f"Workspace: {manifest['workspace']}")
        spec = manifest.get("spec") or {}
        if spec:
            lines.append(
                f"Target: {spec.get('target_artifact')}  Caps: iters<={spec.get('max_iterations')} mins<={spec.get('max_minutes')}"
            )
            criteria = spec.get("success_criteria") or []
            if criteria:
                lines.append("Success criteria:")
                for c in criteria[:5]:
                    lines.append(f"  - {c}")
        if manifest.get("block_reason"):
            lines.append(f"\x1b[38;5;208mBlocked: {manifest['block_reason']}\x1b[0m")
        if manifest.get("artifact"):
            lines.append(f"Artifact: {manifest['artifact']}  ok={manifest.get('artifact_ok')}")
        if manifest.get("tmux"):
            lines.append(f"Tmux session: {(manifest['tmux'] or {}).get('session', '-')}")
        iterations = manifest.get("iterations") or []
        if iterations:
            lines.append("")
            lines.append("\x1b[1mIterations\x1b[0m")
            for it in iterations:
                rer_mark = " +rereview" if it.get("re_reviewer_id") else ""
                lines.append(f"  iter {it['n']}: \x1b[1m{it.get('verdict', '-')}\x1b[0m{rer_mark}")
        if roles:
            lines.append("")
            lines.append("\x1b[1mRoles\x1b[0m")
            for name, role_data in roles.items():
                tmux = role_data.get("tmux") or {}
                age = humanize_age(
                    output_age_seconds(Path(role_data.get("output", ""))) if role_data.get("output") else None
                )
                lines.append(
                    f"  {name}: {role_data.get('status')} / {role_data.get('validation_status', '-')}"
                    f"  ctrl={role_data.get('control_state', 'automated')}"
                    f"  pane={tmux.get('pane', '-')}  out={age}"
                )
        if mode == "tail":
            for name, role_data in roles.items():
                output_path = role_data.get("output")
                if not output_path or not Path(output_path).exists():
                    continue
                lines.append("")
                lines.append(f"\x1b[1m── {name} tail ──\x1b[0m")
                content = redact(Path(output_path).read_text())
                lines.extend(content.splitlines()[-40:])
        if manifest.get("learned_ids"):
            lines.append("")
            lines.append(f"Learned: {', '.join(manifest['learned_ids'])}")
        return "\n".join(lines)

    def role_manifest(self, rid: str | None, role: str | None) -> dict[str, Any]:
        manifest = self.load_manifest(rid)
        if not role:
            return manifest
        roles = manifest.get("roles") or {}
        if role not in roles:
            raise SystemExit(f"role not found: {role}")
        return roles[role]

    def kill(self, rid: str | None, role: str | None) -> dict[str, Any]:
        manifest = self.load_manifest(rid)
        is_multi_role = manifest.get("kind") == "go"
        roles_to_kill: dict[str, dict[str, Any]] = {}
        if role:
            target = manifest.get("roles", {}).get(role) if is_multi_role else None
            if not target and not is_multi_role:
                target = manifest
            if not target:
                raise SystemExit(f"role not found: {role}")
            roles_to_kill[role] = target
        elif is_multi_role:
            roles_to_kill = manifest.get("roles") or {}
        else:
            roles_to_kill["__solo__"] = manifest
        for name, role_data in roles_to_kill.items():
            tmux = role_data.get("tmux") or {}
            pane = tmux.get("pane")
            already_done = role_data.get("status") in ("completed", "failed")
            if pane and tmux_pane_exists(pane):
                subprocess.run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
                time.sleep(0.2)
                subprocess.run(["tmux", "kill-pane", "-t", pane], check=False)
            if not already_done:
                role_data["status"] = "killed"
                role_data["validation_status"] = "failed"
                role_data["killed_at"] = utc_now()
            role_data["control_state"] = "automated"
            if isinstance(tmux, dict):
                tmux["alive"] = False
                role_data["tmux"] = tmux
            self.save_manifest(role_data)
        if not role and is_multi_role:
            session = (manifest.get("tmux") or {}).get("session")
            # Each go run owns its dedicated session; killing the run kills
            # the session unconditionally.
            if session and tmux_session_exists(session):
                subprocess.run(["tmux", "kill-session", "-t", session], check=False)
            # If a runner is alive, signal it to stop and unlink its PID file.
            run_dir = self.run_dir(manifest["id"])
            pid_path = runner_pid_path(run_dir)
            if pid_path.exists():
                try:
                    pid = int(pid_path.read_text().strip() or "0")
                    if pid:
                        os.kill(pid, 15)  # SIGTERM
                except (ValueError, OSError):
                    pass
            manifest["status"] = "killed"
            manifest["phase"] = "failed"
            manifest["validation"] = self.validation_for_manifest(manifest)
            self.save_manifest(manifest)
        elif not is_multi_role:
            manifest["status"] = "killed"
            self.save_manifest(manifest)
        else:
            manifest["validation"] = self.validation_for_manifest(manifest)
            self.save_manifest(manifest)
        return manifest

    def remove(self, rid: str | None, all_completed: bool, keep_learnings: bool) -> list[str]:
        removed: list[str] = []
        targets: list[dict[str, Any]] = []
        if all_completed:
            for run in self.list_runs(limit=10_000):
                if run.get("status") in ("completed", "failed", "killed"):
                    targets.append(self.load_manifest(run["id"]))
        else:
            targets.append(self.load_manifest(rid))
        self.bag_dir.mkdir(parents=True, exist_ok=True)
        for manifest in targets:
            run_id_value = manifest["id"]
            # Tear down the run's dedicated tmux session before archiving so
            # no orphan panes survive a removed run.
            session = (manifest.get("tmux") or {}).get("session")
            if session and tmux_session_exists(session):
                subprocess.run(["tmux", "kill-session", "-t", session], check=False)
            for child_id in self._role_run_ids(manifest):
                self._archive_run(child_id)
                removed.append(child_id)
            self._archive_run(run_id_value)
            removed.append(run_id_value)
            if not keep_learnings:
                for capsule_id in manifest.get("learned_ids", []):
                    self.kb.remove(capsule_id)
        return removed

    def _role_run_ids(self, manifest: dict[str, Any]) -> list[str]:
        roles = manifest.get("roles") or {}
        return [role_data["id"] for role_data in roles.values() if role_data.get("id")]

    def _archive_run(self, rid: str) -> None:
        src = self.run_dir(rid)
        if not src.exists():
            return
        dest = self.bag_dir / f"{rid}-{int(time.time())}"
        shutil.move(str(src), str(dest))

    def supervisor_once(self) -> list[dict[str, Any]]:
        """Resume dead non-terminal runners that are safe to automate."""
        self.init()
        actions: list[dict[str, Any]] = []
        if not self.runs_dir.exists():
            return actions
        for path in sorted(self.runs_dir.glob("*/manifest.json")):
            try:
                manifest = json.loads(path.read_text())
            except Exception:
                continue
            if manifest.get("kind") != "go":
                continue
            rid = manifest.get("id")
            status = manifest.get("status")
            if not rid or status not in SUPERVISABLE_STATUSES:
                continue
            if self._blocking_control_roles(manifest):
                actions.append({"id": rid, "action": "skip", "reason": "manual_control"})
                continue
            run_dir = self.run_dir(rid)
            if runner_alive(run_dir):
                actions.append({"id": rid, "action": "skip", "reason": "runner_alive"})
                continue
            self._spawn_detached_runner(rid)
            actions.append({"id": rid, "action": "resume"})
        return actions

    def supervisor_loop(self, interval: int) -> None:
        while True:
            self.supervisor_once()
            time.sleep(max(1, interval))

    def statusline(self) -> str:
        runs = self.list_runs(limit=200)
        running = sum(1 for r in runs if r.get("status") not in ("completed", "failed", "killed"))
        needs = sum(1 for r in runs if r.get("validation_status") == "needs_verification")
        passed = sum(
            1
            for r in runs
            if r.get("status") == "completed" and r.get("validation_status") in ("passed", "passed_with_warnings")
        )
        parts = []
        if running:
            parts.append(f"R:{running}")
        if needs:
            parts.append(f"V:{needs}")
        if passed and not running and not needs:
            parts.append(f"\u2713{passed}")
        if not parts:
            return ""
        # Trailing affordance pointing operators at the TUI dashboard popup
        # (`prefix+A`). Faint so it doesn't add visual weight, but visible
        # enough to make the binding discoverable from the status bar alone.
        return " ".join(parts) + " \x1b[2m(^A)\x1b[0m"

    def doctor(self) -> list[str]:
        self.init()
        checks = [f"state_home={self.state_home}", f"runs_dir={self.runs_dir}"]
        checks.extend(self.kb.doctor())
        for binary in ("pi", "agent"):
            found = subprocess.run(["/usr/bin/env", "which", binary], capture_output=True, text=True)
            checks.append(f"{binary}={found.stdout.strip() if found.returncode == 0 else 'missing'}")
        found = subprocess.run(["/usr/bin/env", "which", "tmux"], capture_output=True, text=True)
        checks.append(f"tmux={found.stdout.strip() if found.returncode == 0 else 'missing'}")
        return checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ralph orchestrator")
    parser.add_argument("--state-home", type=Path, help="Override RALPH_STATE_HOME")
    parser.add_argument("--kb-home", type=Path, help="Override AI_KB_HOME")
    sub = parser.add_subparsers(dest="cmd", required=True)

    dry = sub.add_parser("dry-run")
    dry.add_argument("--goal", required=True)
    dry.add_argument("--memory-query")
    dry.add_argument("--memory-limit", type=int, default=5)
    dry.add_argument("--acceptance")

    go = sub.add_parser("go", help="Create a new go run; plan + drive iteration loop")
    go.add_argument("--goal", required=True, help="Free-text goal")
    go.add_argument("--workspace", type=Path, default=Path.cwd())
    go.add_argument("--plan-only", action="store_true", help="Run planner and stop (emit spec.md, no execution)")
    go.add_argument(
        "--workflow",
        choices=tuple(WORKFLOWS.keys()),
        help="Operator hint passed to the planner; the planner is encouraged "
        "to emit this workflow in spec but may override with rationale.",
    )
    go.add_argument("--roles-config", type=Path, help="Override path to roles.json")
    # Per-role overrides applied on top of roles.json (re-runs the diversity gate
    # after applying). Empty string = leave unchanged.
    for _role in ("planner", "executor", "reviewer", "re-reviewer"):
        go.add_argument(f"--{_role}-model", default=None, help=f"Override roles.json {_role.replace('-', '_')}.model")
        go.add_argument(
            f"--{_role}-harness",
            default=None,
            choices=("cursor", "pi", "command"),
            help=f"Override roles.json {_role.replace('-', '_')}.harness",
        )
        go.add_argument(
            f"--{_role}-args",
            default=None,
            help=(
                f"Override roles.json {_role.replace('-', '_')}.extra_args. "
                f"Single string, shlex-split server-side. Required when "
                f"--{_role}-harness=command; optional cursor/pi flag tail "
                f"otherwise. Empty string clears extra_args."
            ),
        )
    fg_group = go.add_mutually_exclusive_group()
    fg_group.add_argument("--foreground", action="store_true", help="Run state machine inline; block until terminal")
    fg_group.add_argument(
        "--detach", action="store_true", help="Spawn the runner detached and return immediately (default with tmux)"
    )
    go.add_argument(
        "--subprocess",
        action="store_true",
        help="Run roles as subprocesses (no tmux); implies --foreground; for tests/CI",
    )
    go.add_argument("--json", action="store_true")

    runner_cmd = sub.add_parser("runner", help="Internal: drive the resumable state-machine loop for a run")
    runner_cmd.add_argument("run_id")
    runner_cmd.add_argument("--json", action="store_true")

    resume = sub.add_parser("resume", help="Re-launch the runner for an existing run if it died")
    resume.add_argument("run_id")
    resume.add_argument("--foreground", action="store_true", help="Run the state machine inline rather than detaching")
    resume.add_argument("--json", action="store_true")

    replan = sub.add_parser("replan", help="Queue a replan; the runner picks it up next loop")
    replan.add_argument("run_id")
    replan.add_argument("--no-resume", action="store_true", help="Do not auto-resume the runner if it is dead")
    replan.add_argument("--json", action="store_true")

    answer = sub.add_parser(
        "answer",
        help="Provide human answer(s) for a run that parked at status=awaiting_human",
    )
    answer.add_argument("run_id")
    qmode = answer.add_mutually_exclusive_group(required=True)
    qmode.add_argument(
        "--question",
        metavar="ID",
        help="Question id to answer; pair with --text for the answer body",
    )
    qmode.add_argument(
        "--json",
        metavar="PATH",
        help="Read a JSON object {qid: answer, ...} from PATH (use - for stdin)",
    )
    answer.add_argument("--text", help="Answer body when --question is used")
    answer.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not auto-spawn a detached runner if the answers fully resolve the questions",
    )
    answer.add_argument("--print-json", action="store_true", help="Emit the post-answer manifest as JSON")

    supervisor = sub.add_parser("supervisor", help="Resume dead non-terminal Ralph runners")
    supervisor.add_argument("--loop", action="store_true", help="Keep supervising until interrupted")
    supervisor.add_argument("--interval", type=int, default=30, help="Loop sleep interval in seconds")
    supervisor.add_argument("--json", action="store_true")

    status = sub.add_parser("status")
    status.add_argument("run_id", nargs="?")
    status.add_argument("--json", action="store_true")

    runs = sub.add_parser("runs")
    runs.add_argument("--limit", type=int, default=50)
    runs.add_argument("--workspace", type=Path)
    runs.add_argument("--session")
    runs.add_argument("--json", action="store_true")

    role = sub.add_parser("role")
    role.add_argument("run_id")
    role.add_argument("role")
    role.add_argument("--json", action="store_true")

    sub.add_parser(
        "dashboard",
        help="Open the Bubble Tea TUI (alias for prefix+A / ralph-tui)",
    )

    preview = sub.add_parser("preview")
    preview.add_argument("run_id")
    preview.add_argument("role", nargs="?")
    preview.add_argument("--mode", choices=("summary", "tail"), default="summary")

    tail = sub.add_parser("tail")
    tail.add_argument("run_id", nargs="?")
    tail.add_argument("--role")
    tail.add_argument("--lines", type=int, default=80)

    attach = sub.add_parser("attach")
    attach.add_argument("run_id", nargs="?")
    attach.add_argument("--role")

    verify = sub.add_parser("verify")
    verify.add_argument("run_id", nargs="?")
    verify.add_argument("--json", action="store_true")

    control = sub.add_parser("control")
    control.add_argument("run_id")
    control.add_argument("--role", required=True)
    control.add_argument("--action", required=True, choices=CONTROL_ACTIONS)
    control.add_argument("--json", action="store_true")

    kill = sub.add_parser("kill", help="Ctrl-C role panes and mark run(s) killed")
    kill.add_argument("run_id", nargs="?")
    kill.add_argument("--role")
    kill.add_argument(
        "--all",
        action="store_true",
        help="Kill every non-terminal run (no run_id / --role allowed)",
    )
    kill.add_argument("--json", action="store_true")

    rm = sub.add_parser("rm")
    rm.add_argument("run_id", nargs="?")
    rm.add_argument("--all-completed", action="store_true")
    rm.add_argument("--keep-learnings", action="store_true")

    sub.add_parser("statusline")
    sub.add_parser("doctor")
    return parser


def render_runs_text(rows: Iterable[dict[str, Any]]) -> str:
    out: list[str] = []
    for row in rows:
        validation = row.get("validation_status") or row.get("status") or "-"
        age = humanize_age(row.get("age_seconds"))
        name = row.get("name") or row.get("short_id")
        out.append(f"{name}\t{validation}\t{row.get('runtime')}\t{age}\t{row.get('goal') or ''}")
    return "\n".join(out)


def _print_run_summary(manifest: dict[str, Any], as_json: bool) -> int:
    status = manifest.get("status", "?")
    if as_json:
        print(json.dumps(manifest, indent=2))
    else:
        phase = manifest.get("phase", "?")
        iters = len(manifest.get("iterations") or [])
        print(f"{manifest['id']}\tphase={phase}\tstatus={status}\titerations={iters}")
        spec = manifest.get("spec") or {}
        if spec:
            print(f"  goal: {spec.get('goal')}")
            print(f"  target: {spec.get('target_artifact')}")
        if manifest.get("block_reason"):
            print(f"  blocked: {manifest['block_reason']}")
    if status == "completed":
        return 0
    if status in ("needs_human", "awaiting_human"):
        # Both park the runner and require human input (control or answers).
        return 2
    if status == "running":
        # Either detached/foreground spawn returned mid-loop, or a resume/replan
        # successfully queued work. Either way the call did its job.
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runner = RalphRunner(args.state_home, args.kb_home)

    if args.cmd == "dry-run":
        prompt = runner.assemble_prompt(args.goal, args.memory_query, args.memory_limit, args.acceptance)
        print(prompt)
        print(f"\nApprox tokens: {max(1, len(prompt) // 4)}", file=sys.stderr)
        return 0
    if args.cmd == "go":
        roles_cfg = load_roles_config(args.roles_config)
        roles_cfg = apply_role_overrides(roles_cfg, vars(args))
        preflight_roles_config(roles_cfg)
        if args.subprocess:
            tmux_mode = False
            detached = False
        else:
            in_tmux = bool(os.environ.get("TMUX"))
            tmux_mode = in_tmux  # tmux mode iff caller is currently in tmux
            # Default to detached when running interactively in tmux so the
            # caller's terminal returns immediately. --foreground forces inline.
            if args.foreground:
                detached = False
            elif args.detach:
                detached = True
            else:
                detached = in_tmux
        manifest = runner.go(
            goal=args.goal,
            workspace=args.workspace,
            roles_cfg=roles_cfg,
            tmux_mode=tmux_mode,
            plan_only=args.plan_only,
            detached=detached,
            workflow_hint=args.workflow,
        )
        return _print_run_summary(manifest, args.json)
    if args.cmd == "runner":
        manifest = runner.run_runner(args.run_id)
        return _print_run_summary(manifest, args.json)
    if args.cmd == "resume":
        manifest = runner.resume_run(args.run_id, detached=not args.foreground)
        # When resume is detached, status remains "running" (the spawned
        # runner is doing the work). When --foreground, status will be the
        # final state of the resumed loop. Either way a successful resume call
        # means the right thing was done on disk; report 0.
        if args.json:
            print(json.dumps(manifest, indent=2))
        else:
            print(f"{manifest['id']}\tstatus={manifest.get('status', '?')}\tresumed=detached={not args.foreground}")
        return 0
    if args.cmd == "replan":
        manifest = runner.replan_run(args.run_id, auto_resume=not args.no_resume)
        if args.json:
            print(json.dumps(manifest, indent=2))
        else:
            print(f"{manifest['id']}\treplan_requested=true")
        return 0
    if args.cmd == "answer":
        if args.question:
            if not args.text:
                raise SystemExit("--question requires --text")
            answers = {args.question: args.text}
        else:
            source = args.json
            raw = sys.stdin.read() if source == "-" else Path(source).read_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as err:
                raise SystemExit(f"--json input was not valid JSON: {err}")
            if not isinstance(payload, dict) or not payload:
                raise SystemExit("--json input must be a non-empty JSON object {qid: answer, ...}")
            answers = {str(k): str(v) for k, v in payload.items()}
        manifest = runner.answer_run(args.run_id, answers, auto_resume=not args.no_resume)
        if args.print_json:
            print(json.dumps(manifest, indent=2))
        else:
            open_qs = [q["id"] for q in (manifest.get("questions") or []) if not q.get("answered_at")]
            tail = f"open={','.join(open_qs)}" if open_qs else "all answered"
            print(f"{manifest['id']}\tstatus={manifest.get('status')}\t{tail}")
        return 0
    if args.cmd == "supervisor":
        if args.loop:
            runner.supervisor_loop(args.interval)
            return 0
        actions = runner.supervisor_once()
        if args.json:
            print(json.dumps(actions, indent=2))
        else:
            for action in actions:
                print(f"{action['id']}\t{action['action']}\t{action.get('reason', '')}".rstrip())
        return 0
    if args.cmd == "status":
        manifest = runner.load_manifest(args.run_id)
        if args.json:
            print(json.dumps(manifest, indent=2))
        else:
            validation = (manifest.get("validation") or {}).get("status") or manifest.get("validation_status") or "-"
            print(
                f"{manifest['id']}\t{manifest['status']}\t{validation}\t"
                f"{manifest.get('runtime')}\t{manifest.get('goal')}"
            )
        return 0 if manifest["status"] == "completed" else 1
    if args.cmd == "runs":
        rows = runner.list_runs(args.limit, args.workspace, args.session)
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            print(render_runs_text(rows))
        return 0
    if args.cmd == "role":
        detail = runner.role_detail(args.run_id, args.role)
        if args.json:
            print(json.dumps(detail, indent=2))
        else:
            summary = role_summary(detail)
            print(
                f"{args.run_id}\t{args.role}\t{summary['status']}\t"
                f"{summary['validation_status']}\t{summary['control_state']}\t{summary['pane'] or '-'}"
            )
        return 0
    if args.cmd == "dashboard":
        # Thin alias for the tmux popup binding (`prefix+A`). Exec the
        # Bubble Tea binary directly so we don't have two competing
        # "dashboard" surfaces (the old text-preview shape was a confusing
        # name collision; use `,ralph preview` for that flow).
        tui_path = Path(os.environ.get("RALPH_TUI_BIN") or Path.home() / ".local/bin/ralph-tui")
        if tui_path.exists() and os.access(str(tui_path), os.X_OK):
            os.execv(str(tui_path), [str(tui_path)])
        raise SystemExit(
            f"ralph-tui binary not found at {tui_path}; install via "
            f"`chezmoi apply` or set RALPH_TUI_BIN, then re-run "
            f"`,ralph dashboard`. Use `,ralph preview <RID>` for the "
            f"text view."
        )
    if args.cmd == "preview":
        print(runner.preview(args.run_id, args.role, mode=args.mode))
        return 0
    if args.cmd == "tail":
        manifest = runner.role_manifest(args.run_id, args.role)
        output = manifest.get("output")
        if output and Path(output).exists():
            print("\n".join(redact(Path(output).read_text()).splitlines()[-args.lines :]))
            return 0
        tmux_info = manifest.get("tmux") or {}
        pane = tmux_info.get("pane")
        if pane:
            subprocess.run(["tmux", "capture-pane", "-p", "-t", pane, "-S", f"-{args.lines}"], check=False)
            return 0
        raise SystemExit("no output or tmux pane available")
    if args.cmd == "attach":
        manifest = runner.role_manifest(args.run_id, args.role)
        tmux_info = manifest.get("tmux") or {}
        session = tmux_info.get("session")
        pane = tmux_info.get("pane")
        output_path = manifest.get("output")
        label = f"{manifest.get('id')}{':' + args.role if args.role else ''}"

        def fallback_to_output(reason: str) -> int:
            if output_path and Path(output_path).exists() and os.environ.get("TMUX"):
                editor = os.environ.get("PAGER") or os.environ.get("EDITOR") or "less -R"
                subprocess.run(
                    [
                        "tmux",
                        "display-popup",
                        "-w",
                        "90%",
                        "-h",
                        "90%",
                        "-T",
                        f" {label} — {reason} ",
                        "-E",
                        f"{editor} {shlex.quote(output_path)}",
                    ],
                    check=False,
                )
                return 0
            if output_path and Path(output_path).exists():
                print(redact(Path(output_path).read_text()))
                return 0
            raise SystemExit(f"{label}: {reason}; no output to show")

        pane_alive = bool(pane) and tmux_pane_exists(pane)
        if not session and not pane:
            return fallback_to_output("no tmux pane (solo/subprocess run)")
        if session and not tmux_session_exists(session):
            return fallback_to_output(f"session {session} is gone")
        if pane and not pane_alive:
            return fallback_to_output(f"pane {pane} no longer alive")
        target = pane if pane_alive else session
        if not target:
            return fallback_to_output("no live tmux target")
        verb = "switch-client" if os.environ.get("TMUX") else "attach-session"
        result = subprocess.run(["tmux", verb, "-t", target], capture_output=True, text=True)
        if result.returncode != 0:
            err = result.stderr.strip() or "tmux refused to attach"
            return fallback_to_output(err)
        return 0
    if args.cmd == "verify":
        validation = runner.validate_run(args.run_id)
        if args.json:
            print(json.dumps(validation, indent=2))
        else:
            print(f"validation\t{validation['status']}")
            artifact = validation.get("artifact") or {}
            if artifact:
                print(f"artifact\tok={artifact.get('ok')}\t{artifact.get('path')}")
            for role, gate in (validation.get("roles") or {}).items():
                print(
                    f"role\t{role}\tstatus={gate['status']}\t"
                    f"validation={gate['validation_status']}\tcontrol={gate['control_state']}"
                )
        return 0 if validation["status"] == "passed" else 1
    if args.cmd == "control":
        detail = runner.set_role_control(args.run_id, args.role, args.action)
        if args.json:
            print(json.dumps(detail, indent=2))
        else:
            print(
                f"{args.run_id}\t{args.role}\tcontrol={detail.get('control_state')}\t"
                f"validation={detail.get('validation_status')}"
            )
        return 0
    if args.cmd == "kill":
        if args.all:
            if args.run_id or args.role:
                raise SystemExit("--all is mutually exclusive with RUN_ID and --role")
            killed: list[dict[str, Any]] = []
            # Mirror the exclusion list `statusline()` uses: anything not
            # in a terminal status counts as "live" and gets killed. This
            # covers running / needs_human / awaiting_human / planned and
            # is robust to future non-terminal statuses being added.
            for run in runner.list_runs(limit=10_000):
                if run.get("status") not in ("completed", "failed", "killed"):
                    killed.append(runner.kill(run["id"], None))
            if args.json:
                print(json.dumps([m["id"] for m in killed]))
            else:
                for m in killed:
                    print(f"{m['id']}\tstatus={m['status']}")
            return 0
        if not args.run_id:
            raise SystemExit("kill requires RUN_ID or --all")
        manifest = runner.kill(args.run_id, args.role)
        if args.json:
            print(json.dumps(manifest, indent=2))
        else:
            print(f"{manifest['id']}\tstatus={manifest['status']}")
        return 0
    if args.cmd == "rm":
        if not args.run_id and not args.all_completed:
            raise SystemExit("rm requires RUN_ID or --all-completed")
        removed = runner.remove(args.run_id, args.all_completed, args.keep_learnings)
        for rid in removed:
            print(rid)
        return 0
    if args.cmd == "statusline":
        print(runner.statusline())
        return 0
    if args.cmd == "doctor":
        for check in runner.doctor():
            print(check)
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
