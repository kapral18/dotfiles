#!/usr/bin/env python3
"""Deterministic legion state machine for ,palantir.

Pure logic, no tmux, no subprocess: every decision the orchestrator makes is a
function from (manifest, event) to (manifest', actions). The runtime layer
(supervisor.py) owns transport; this module owns truth. That split keeps the
control loop free of model inference and fully table-testable.

Stages (one legion = one effort = one tmux session):

    summon -> triage -> [diagnose -> investigate ->] implement
           -> adversarial_review -> verify -> cleared_for_human
    holding    (parked for a human decision; question, triage rejection, or exhausted budget)
    banished   (terminal)

Invariants:

  * ``cleared_for_human`` is reachable only through ``verify`` with every
    acceptance criterion green AND the adversarial review reporting zero open
    blockers. There is no other edge into it.
  * ``adversarial_review`` must run on a different model family than
    ``implement`` (enforced at role resolution, refused at summon time).
  * Every return of ``implement`` to work — a failed verify or an
    adversarial review with open blockers — spends one shared
    ``max_implement_attempts`` budget; an exhausted budget parks the
    legion in ``holding`` instead of looping.
  * Closing a legion (``banish`` from any stage, or ``grant_clear`` from
    ``cleared_for_human``) emits a memory-routing packet: durable findings ->
    ,ai-kb; task-scoped -> /tmp/specs; repo-intrinsic -> the target repo's
    AGENTS.md via the legion's own worktree.
"""

from __future__ import annotations

from typing import Optional

STAGES = (
    "summon",
    "triage",
    "diagnose",
    "investigate",
    "implement",
    "adversarial_review",
    "verify",
    "cleared_for_human",
    "holding",
    "banished",
)

TERMINAL_STAGES = frozenset({"banished"})
ATTENTION_STAGES = frozenset({"cleared_for_human", "holding"})

# Stages whose work is done by an interactive agent pane. ``verify`` is absent
# on purpose: criteria checks are machine-run by the supervisor, never judged
# by an agent.
ROLE_BY_STAGE = {
    "triage": "triage",
    "diagnose": "diagnose",
    "investigate": "investigate",
    "implement": "implement",
    "adversarial_review": "adversarial-review",
}

# Model families for the adversarial-diversity guard.
FAMILIES = ("claude", "gpt", "gemini", "llama", "mistral", "deepseek")

_MODEL_FAMILY_PREFIXES = (
    ("claude", "claude"),
    ("gpt", "gpt"),
    ("o1", "gpt"),
    ("o3", "gpt"),
    ("codex", "gpt"),
    ("gemini", "gemini"),
    ("llama", "llama"),
    ("mistral", "mistral"),
    ("deepseek", "deepseek"),
)

# An interactive harness with no explicit model runs its own default; these are
# the verified defaults for the harnesses on PATH.
_HARNESS_DEFAULT_FAMILY = {
    "copilot": "gpt",
    "claude": "claude",
    "pi": "claude",
    "opencode": "claude",
}


class MachineError(RuntimeError):
    """A transition or guard was violated."""


def derive_family(harness: str, model: str) -> str:
    """Resolve the model family for a role from its model name or harness default."""
    low = (model or "").lower()
    for prefix, family in _MODEL_FAMILY_PREFIXES:
        if low.startswith(prefix):
            return family
    fallback = _HARNESS_DEFAULT_FAMILY.get((harness or "").lower())
    if fallback:
        return fallback
    raise MachineError(f"cannot derive model family for harness={harness!r} model={model!r}; set family explicitly")


def resolve_roles(roles: dict) -> dict:
    """Fill in families and enforce the adversarial-diversity guard.

    ``roles`` maps role name -> {harness, model, family?}. Returns a copy with
    ``family`` resolved for every role. Raises ``MachineError`` when the
    adversarial-review family equals the implement family.
    """
    resolved: dict = {}
    for name, spec in roles.items():
        spec = dict(spec)
        if not spec.get("family"):
            spec["family"] = derive_family(spec.get("harness", ""), spec.get("model", ""))
        if spec["family"] not in FAMILIES:
            raise MachineError(f"role {name}: unknown family {spec['family']!r}")
        resolved[name] = spec
    impl = resolved.get("implement")
    review = resolved.get("adversarial-review")
    if impl and review and impl["family"] == review["family"]:
        raise MachineError(
            "adversarial-review must run on a different model family than implement "
            f"(both are {impl['family']!r}); change one role's harness/model/family"
        )
    return resolved


def validate_criteria(criteria: object) -> list[dict]:
    """Return a normalized criteria list or refuse malformed verify input."""
    if not isinstance(criteria, list):
        raise MachineError("criteria must be a JSON list")
    normalized: list[dict] = []
    for index, raw in enumerate(criteria):
        if not isinstance(raw, dict):
            raise MachineError(f"criterion {index + 1} must be an object")
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise MachineError(f"criterion {index + 1} needs non-empty text")
        check = raw.get("check")
        if check is not None and (not isinstance(check, str) or not check.strip()):
            raise MachineError(f"criterion {index + 1} check must be a non-empty string")
        normalized.append(dict(raw))
    return normalized


# --------------------------------------------------------------------------- #
# Events and actions                                                          #
# --------------------------------------------------------------------------- #
# Events (dicts, ``kind`` discriminates):
#   {"kind": "stage_result", "stage": s, "verdict": v, ...}
#   {"kind": "criteria_report", "green": bool, "failures": [..]}
#   {"kind": "question", "role": r, "text": t}
#   {"kind": "answer", "text": t}
#   {"kind": "grant_clear"}   (human grants the landed legion; closes it)
#   {"kind": "banish"}
#
# Actions returned to the runtime (dicts, ``kind`` discriminates):
#   {"kind": "start_stage", "stage": s, "role": r|None, "brief": {...}}
#   {"kind": "run_verify"}
#   {"kind": "wake_coordinator", "event": {...}}
#   {"kind": "route_memory", "packet": {...}}

_TRIAGE_ROUTES = {
    "implement": "implement",
    "diagnose": "diagnose",
    "reject": "holding",
}

_STAGE_SUCCESSOR = {
    "diagnose": "investigate",
    "investigate": "implement",
    "implement": "adversarial_review",
}


def _start(stage: str, brief: Optional[dict] = None) -> dict:
    return {
        "kind": "start_stage",
        "stage": stage,
        "role": ROLE_BY_STAGE.get(stage),
        "brief": brief or {},
    }


def _wake(event: dict) -> dict:
    return {"kind": "wake_coordinator", "event": event}


def memory_routing_packet(manifest: dict) -> dict:
    """The three-layer routing packet emitted when a legion closes."""
    return {
        "legion": manifest.get("id", ""),
        "goal": manifest.get("goal", ""),
        "worktree": manifest.get("worktree", ""),
        "routes": {
            "durable": ",ai-kb remember (generalizable, verified findings with provenance)",
            "ephemeral": "/tmp/specs (task-scoped worklog and intent spec)",
            "repo": "target repo AGENTS.md via the legion worktree (repo-intrinsic conventions)",
        },
    }


def _close(manifest: dict, reason: str) -> "tuple[dict, list[dict]]":
    manifest = dict(manifest)
    current_attention = attention_event(manifest)
    if current_attention is not None:
        manifest = resolve_condition(manifest, current_attention["kind"])
    actions: list = []
    if not manifest.get("memory_packet_written"):
        actions.append({"kind": "route_memory", "packet": memory_routing_packet(manifest)})
    manifest["stage"] = "banished"
    manifest["closed_reason"] = reason
    return manifest, actions


def transition(manifest: dict, event: dict) -> "tuple[dict, list[dict]]":
    """Apply one event; return the updated manifest and runtime actions.

    Raises ``MachineError`` on an edge that does not exist. The caller persists
    the returned manifest; this function never touches disk.
    """
    stage = manifest.get("stage", "summon")
    kind = event.get("kind")
    manifest = dict(manifest)

    if stage in TERMINAL_STAGES:
        raise MachineError(f"legion is {stage}; no further transitions")

    if kind == "banish":
        return _close(manifest, "banished by human")

    if kind == "question":
        if stage == "holding":
            raise MachineError("legion is already holding; answer the parked condition instead")
        manifest["stage"] = "holding"
        manifest["holding"] = {
            "reason": "question",
            "role": event.get("role", ""),
            "text": event.get("text", ""),
            "resume_stage": stage,
        }
        return manifest, [_wake(attention_event(manifest))]

    if kind == "answer":
        if stage != "holding":
            raise MachineError(f"answer while {stage}; only a holding legion takes an answer")
        current_attention = attention_event(manifest)
        if current_attention is not None:
            manifest = resolve_condition(manifest, current_attention["kind"])
        holding = manifest.pop("holding", {}) or {}
        resume = holding.get("resume_stage", "triage")
        manifest["stage"] = resume
        brief = {"answer": event.get("text", ""), "question": holding.get("text", "")}
        if resume == "verify":
            return manifest, [{"kind": "run_verify"}]
        return manifest, [_start(resume, brief)]

    if kind == "grant_clear":
        if stage != "cleared_for_human":
            raise MachineError(f"grant_clear while {stage}; only a cleared_for_human legion can be granted")
        return _close(manifest, "granted by human")

    if kind == "stage_result":
        got = event.get("stage")
        if got != stage:
            raise MachineError(f"stage_result for {got!r} while legion is in {stage!r}")
        verdict = event.get("verdict", "")

        if stage == "summon":
            raise MachineError("summon has no stage_result; the runtime starts triage directly")

        if stage == "triage":
            route = _TRIAGE_ROUTES.get(verdict)
            if route is None:
                raise MachineError(f"triage verdict {verdict!r} not in {sorted(_TRIAGE_ROUTES)}")
            if route == "holding":
                manifest["stage"] = "holding"
                manifest["holding"] = {
                    "reason": "triage-reject",
                    "text": event.get("summary", ""),
                    "resume_stage": "triage",
                }
                return manifest, [_wake(attention_event(manifest))]
            manifest["stage"] = route
            return manifest, [_start(route, {"triage": event.get("summary", "")})]

        if stage in _STAGE_SUCCESSOR:
            nxt = _STAGE_SUCCESSOR[stage]
            manifest["stage"] = nxt
            return manifest, [
                _start(
                    nxt,
                    {
                        "handoff": event.get("summary", ""),
                        "workspace_delta": event.get("workspace_delta") or {},
                    },
                )
            ]

        if stage == "adversarial_review":
            if "blockers" not in event:
                raise MachineError(
                    "adversarial_review result has no 'blockers' field; "
                    "a clean review must state blockers: [] explicitly (fail-closed)"
                )
            blockers = list(event.get("blockers") or [])
            manifest["review_blockers"] = blockers
            if blockers:
                attempts = int(manifest.get("implement_attempts", 0)) + 1
                manifest["implement_attempts"] = attempts
                budget = int(manifest.get("max_implement_attempts", 3))
                if attempts >= budget:
                    manifest["stage"] = "holding"
                    manifest["holding"] = {
                        "reason": "review-budget-exhausted",
                        "text": f"{attempts} implement attempts still carry review blockers",
                        "blockers": blockers,
                        "resume_stage": "implement",
                    }
                    return manifest, [_wake(attention_event(manifest))]
                manifest["stage"] = "implement"
                return manifest, [
                    _start("implement", {"review_blockers": blockers}),
                    _wake({"kind": "review_blockers", "blockers": blockers}),
                ]
            manifest = resolve_condition(manifest, "review_blockers")
            manifest["stage"] = "verify"
            return manifest, [{"kind": "run_verify"}]

        raise MachineError(f"stage {stage!r} takes no stage_result")

    if kind == "criteria_report":
        if stage != "verify":
            raise MachineError(f"criteria_report while {stage}; only verify consumes it")
        if manifest.get("review_blockers"):
            raise MachineError("verify ran with open review blockers; adversarial_review must clear first")
        if event.get("green"):
            manifest = resolve_condition(manifest, "verify_failed")
            manifest["stage"] = "cleared_for_human"
            return manifest, [_wake(attention_event(manifest))]
        failures = list(event.get("failures") or [])
        attempts = int(manifest.get("implement_attempts", 0)) + 1
        manifest["implement_attempts"] = attempts
        budget = int(manifest.get("max_implement_attempts", 3))
        if attempts >= budget:
            manifest["stage"] = "holding"
            manifest["holding"] = {
                "reason": "verify-budget-exhausted",
                "text": f"{attempts} implement attempts failed verify",
                "failures": failures,
                "resume_stage": "implement",
            }
            return manifest, [_wake(attention_event(manifest))]
        manifest["stage"] = "implement"
        return manifest, [
            _start("implement", {"verify_failures": failures, "attempt": attempts}),
            _wake({"kind": "verify_failed", "attempt": attempts}),
        ]

    raise MachineError(f"unknown event kind {kind!r}")


def dedupe_wake(observations: dict, key: str, fingerprint: str) -> "tuple[dict, bool]":
    """Enqueue-once semantics for actionable conditions.

    ``observations`` maps a condition key to the fingerprint last surfaced.
    Returns (updated observations, should_enqueue). An identical unresolved
    condition never enqueues twice; a resolved-then-recurred one does.
    """
    observations = dict(observations)
    if observations.get(key) == fingerprint:
        return observations, False
    observations[key] = fingerprint
    return observations, True


def resolve_wake(observations: dict, key: str) -> dict:
    """Mark a condition resolved so a recurrence enqueues again."""
    observations = dict(observations)
    observations.pop(key, None)
    return observations


def resolve_condition(manifest: dict, key: str) -> dict:
    """Drop delivered and queued wake state when a condition is no longer true."""
    manifest = dict(manifest)
    manifest["wake_observations"] = resolve_wake(manifest.get("wake_observations") or {}, key)
    manifest["pending_wakes"] = [item for item in (manifest.get("pending_wakes") or []) if item.get("key") != key]
    return manifest


def attention(manifest: dict) -> Optional[str]:
    """The dashboard/statusline attention flag for one legion, or None."""
    stage = manifest.get("stage", "")
    if stage == "cleared_for_human":
        return "cleared"
    if stage == "holding":
        return "holding"
    if stage == "banished" and manifest.get("teardown_status") != "complete":
        return "orphan"
    if stage == "banished" and manifest.get("memory_packet_written") and not manifest.get("memory_packet_routed"):
        return "unrouted"
    transport = manifest.get("coordinator_transport") or {}
    if stage not in TERMINAL_STAGES and transport.get("status") == "error":
        return "transport"
    return None


def attention_event(manifest: dict) -> Optional[dict]:
    """The wake event for a parked/cleared legion, or None.

    Single owner of these wake shapes: ``transition`` emits them from here and
    the supervisor re-surfaces them each tick — ``dedupe_wake`` suppresses a
    delivered condition and retries one whose delivery hit a blocked pane.
    """
    stage = manifest.get("stage", "")
    if stage == "cleared_for_human":
        return {"kind": "cleared_for_human"}
    if stage != "holding":
        return None
    holding = manifest.get("holding") or {}
    reason = holding.get("reason", "")
    if reason == "question":
        return {"kind": "question", "role": holding.get("role", ""), "text": holding.get("text", "")}
    if reason == "triage-reject":
        return {"kind": "triage_rejected", "summary": holding.get("text", "")}
    if reason == "verify-budget-exhausted":
        return {
            "kind": "budget_exhausted",
            "attempts": int(manifest.get("implement_attempts", 0)),
            "failures": list(holding.get("failures") or []),
        }
    if reason == "review-budget-exhausted":
        return {
            "kind": "budget_exhausted",
            "attempts": int(manifest.get("implement_attempts", 0)),
            "blockers": list(holding.get("blockers") or []),
        }
    return {"kind": "holding", "reason": reason, "text": holding.get("text", "")}


def summarize(manifest: dict) -> dict:
    """Stable read-model row for the dashboard and ``,palantir farsee``."""
    holding = manifest.get("holding") or {}
    transport = manifest.get("coordinator_transport") or {}
    return {
        "id": manifest.get("id", ""),
        "goal": manifest.get("goal", ""),
        "stage": manifest.get("stage", ""),
        "attention": attention(manifest),
        "session": manifest.get("session", ""),
        "worktree": manifest.get("worktree", ""),
        "implement_attempts": int(manifest.get("implement_attempts", 0)),
        "review_blockers": len(manifest.get("review_blockers") or []),
        "holding_reason": holding.get("reason", ""),
        "stage_started_at_unix_ns": int(manifest.get("stage_started_at_unix_ns", 0)),
        "pending_wakes": len(manifest.get("pending_wakes") or []),
        "coordinator_transport": transport.get("status", "unknown"),
        "coordinator_error": transport.get("last_error", ""),
        "teardown_status": manifest.get("teardown_status", ""),
        "memory_packet_written": bool(manifest.get("memory_packet_written")),
        "memory_packet_routed": bool(manifest.get("memory_packet_routed")),
        "criteria_total": len(manifest.get("criteria") or []),
        "criteria_green": sum(1 for c in (manifest.get("criteria") or []) if c.get("status") == "green"),
    }
