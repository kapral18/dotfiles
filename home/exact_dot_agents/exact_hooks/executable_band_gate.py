#!/usr/bin/env python3
"""Pin a delegated agent to its category's band, whatever model the caller asked for.

Agent profiles already declare the right model, but a profile is only a default: every harness
lets the spawning model pass its own ``model`` argument per call, and several ship built-in
subagents with no profile at all. This is the backstop that makes the band non-negotiable.

It reads the flattened projection at ``~/.config/ai/agent-bands.v1.json`` (written by
scripts/generate_agent_bands.py) and rewrites the delegation payload in place. Harnesses disagree
on both the request and the response shape, so each gets an adapter selected by
``AGENT_BAND_HARNESS``. Known harnesses deny delegations with missing or ambiguous lane data;
ordinary tools and harnesses with their own runtime adapters are left alone.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from hook_common import is_delegated_leaf, read_payload

PROJECTION = Path(os.environ.get("AGENT_BANDS_FILE", os.path.expanduser("~/.config/ai/agent-bands.v1.json")))
HARNESS_ENV = "AGENT_BAND_HARNESS"
SCHEMA_HARNESS_ENV = "AGENT_BAND_SCHEMA_HARNESS"
MODEL_OVERRIDE_ENV = "AGENT_BAND_MODEL_OVERRIDE"
EFFORT_OVERRIDE_ENV = "AGENT_BAND_EFFORT_OVERRIDE"
MODEL_FORMAT_ENV = "AGENT_BAND_MODEL_FORMAT"


def _load() -> dict[str, Any]:
    try:
        value = json.loads(PROJECTION.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _pick(harness: str, agent: str) -> dict[str, Any] | None:
    projection = _load()
    if not projection:
        return None
    try:
        pick = projection["harnesses"][harness]["agents"].get(agent)
        return pick if _valid_pick(pick, harness) else None
    except (KeyError, TypeError, AttributeError):
        return None


def _valid_pick(pick: Any, harness: str) -> bool:
    # Cursor Task ids cannot encode effort; the user's saved Cursor config supplies it.
    # Backend-schema routes still require an explicit effort field.
    keys = ("model",) if harness == "cursor" else ("model", "effort")
    return isinstance(pick, dict) and all(isinstance(pick.get(key), str) and pick[key] for key in keys)


def _generic_pick(harness: str, pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    """Generic workers may carry another lane, but a model alone does not select its effort."""
    asked = tool_input.get("model")
    rows = _load().get("harnesses", {}).get(harness, {}).get("agents", {}).values()

    def transport_id(model: object) -> object:
        if os.environ.get(MODEL_FORMAT_ENV) == "openrouter-preset" and isinstance(model, str):
            return model.removeprefix("openrouter/")
        return model

    matches = [row for row in rows if isinstance(row, dict) and transport_id(row.get("model")) == transport_id(asked)]
    if not matches:
        return pick
    if not all(_valid_pick(row, harness) for row in matches):
        raise ValueError("The requested model has incomplete lane data. Do not guess its effort.")
    if harness == "cursor":
        return matches[0]
    efforts = {row.get("effort") for row in matches}
    requested = tool_input.get("reasoning_effort")
    if len(efforts) == 1:
        return matches[0]
    if requested in efforts:
        return next(row for row in matches if row.get("effort") == requested)
    raise ValueError(
        "This model serves multiple lane efforts. Supply the assigned category's exact reasoning_effort; do not guess or substitute another lane."
    )


def _deny(harness: str, reason: str) -> dict[str, Any]:
    if harness == "cursor":
        return {"permission": "deny", "user_message": reason}
    decision = {"permissionDecision": "deny", "permissionDecisionReason": reason}
    if harness == "copilot":
        return decision
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", **decision}}


def _override(harness: str) -> dict[str, Any] | None:
    """One model for every band, for a route whose catalog is a single model.

    A BYOK launcher points the whole session at one provider model; the bands still name the
    harness's native ids, and those travel to that provider as their own wire model. Copilot's
    `explore` reached openai/gpt-5.3-codex from a session pinned to gpt-5.6-terra this way, so
    the override has to reach unbound agents too, not just rewrite a band's pick.

    Claude Code is excluded because its Agent tool takes only the family aliases, and each alias
    already resolves through one ANTHROPIC_DEFAULT_*_MODEL the launcher sets.
    """
    model = os.environ.get(MODEL_OVERRIDE_ENV, "")
    if not model or harness == "claude_code":
        return None
    override: dict[str, Any] = {"model": model}
    effort = os.environ.get(EFFORT_OVERRIDE_ENV, "")
    if effort:
        override["effort"] = effort
    return override


def _format_pick(pick: dict[str, Any], harness: str, schema_harness: str) -> dict[str, Any]:
    model = pick.get("model")
    if not isinstance(model, str):
        return pick

    formatted = dict(pick)
    if os.environ.get(MODEL_FORMAT_ENV) == "openrouter-preset":
        base = model.removeprefix("openrouter/")
        effort = formatted.get("effort")
        if isinstance(effort, str) and effort:
            formatted["model"] = f"{base}@preset/effort-{effort}"
            formatted["effort"] = effort
        else:
            formatted["model"] = base

    if harness == "claude_code" and schema_harness != harness:
        formatted["force_alias"] = True
    return formatted


def _antigravity(payload: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    # Antigravity lanes are dynamic `define_subagent`/`invoke_subagent` calls, never profile
    # files: the registry carries no per-agent pick, so the tier and the name are the whole
    # enforcement surface (tiers per harness-capabilities IR: inherit|flash_lite|flash|pro).
    name = _agent_name(payload, tool_input) or tool_input.get("name")
    if not isinstance(name, str) or not name.startswith("k-agent-"):
        return {
            "decision": "deny",
            "reason": (
                "Antigravity lanes launch only as `k-agent-<role>` profiles; "
                f"{name!r} is not a managed lane. Define the role with `define_subagent` first."
            ),
        }
    tier = tool_input.get("model")
    if tier is not None and tier != "flash":
        return {
            "decision": "deny",
            "reason": (
                "Antigravity `invoke_subagent` accepts only the `flash` tier; "
                f"{tier!r} is not a lane tier. Pass `flash` for every category."
            ),
        }
    return {"decision": "allow"}


def _claude(payload: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    # Fresh managed leaf on every route (SOP §3.7: fresh worker context, a marker is not isolation).
    if tool_input.get("fork_context") or tool_input.get("resume"):
        return _deny("claude_code", "Claude lanes require a fresh managed leaf, not a fork or resume.")
    if os.environ.get("AGENT_BAND_SUBSCRIPTION") or os.environ.get(MODEL_FORMAT_ENV) == "openrouter-preset":
        try:
            routes = json.loads(os.environ.get("AGENT_BAND_CLAUDE_ROUTES", ""))
            expected = pick.get("model")
            if os.environ.get("AGENT_BAND_SUBSCRIPTION"):
                expected = f"{expected}@lane-{pick.get('effort')}"
            if not isinstance(routes, dict) or routes.get(_agent_name(payload, tool_input)) != expected or not pick:
                raise ValueError("The assigned Claude profile/lane is unavailable or stale; relaunch the wrapper.")
            if (
                os.environ.get(MODEL_OVERRIDE_ENV)
                or os.environ.get(EFFORT_OVERRIDE_ENV)
                or os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL")
            ):
                raise ValueError("Conflicting inherited Claude lane controls.")
        except (ValueError, TypeError) as error:
            return _deny("claude_code", str(error))
        updated = {key: value for key, value in tool_input.items() if key not in {"model", "reasoning_effort"}}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated}}
    # Claude's Agent tool constrains `model` to the family aliases sonnet|opus|haiku|fable
    # (claude-code 2.1.222; anything else fails updatedInput schema validation), and each alias
    # resolves through one ANTHROPIC_DEFAULT_*_MODEL. The alias is a lossy projection of the band:
    # the tiers map onto three aliases (T1 research/review/session `fable`, T2 implement `opus`,
    # T3 mechanical/memory `sonnet`), so effort inside a tier is invisible to the hook — the profile
    # frontmatter's exact id and effort are what hold that, and they win whenever no `model` is passed.
    #
    # Enforce the assigned alias in both directions. A cheaper model is not a valid
    # replacement for a strong role. Omitted overrides retain the profile's exact id/effort.
    alias = pick.get("alias")
    asked = tool_input.get("model")
    if pick.get("force_alias") and alias and asked != alias:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": dict(tool_input, model=alias),
            }
        }
    if not alias or not isinstance(asked, str) or asked == alias:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": dict(tool_input, model=alias),
        }
    }


def _cursor(payload: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    # Cursor Task accepts base ids only; effort is not encodable in the id and comes from saved user config.
    # updated_input replaces the whole object, so untouched keys must be echoed back.
    return {"updated_input": dict(tool_input, model=pick["model"])}


def _codex(payload: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    # Native routes admit forks the same way the subscription path did: deny unconditionally.
    if tool_input.get("fork_context") or tool_input.get("resume"):
        return _deny(
            "codex",
            "Subscription lanes require a fresh managed leaf; full-history forks inherit root configuration.",
        )
    # Codex rejects updatedInput unless permissionDecision is "allow" ("PreToolUse hook returned
    # updatedInput without permissionDecision:allow", codex 0.146.0). spawn_agent takes model and
    # reasoning_effort directly, so both dials are enforceable here.
    updated = dict(tool_input, model=pick["model"])
    if os.environ.get(MODEL_FORMAT_ENV) == "openrouter-preset":
        # The exact preset selector owns effort; native catalog levels are empty.
        updated.pop("reasoning_effort", None)
    elif pick.get("effort"):
        updated["reasoning_effort"] = pick["effort"]
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": updated,
        }
    }


def _codex_subscription_pick(
    agent: str, assigned: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]
) -> dict[str, Any]:
    """Admit only fresh leaves whose catalog and model-free profiles were projected at launch."""
    if tool_input.get("fork_context"):
        raise ValueError(
            "Subscription lanes require a fresh managed leaf; full-history forks inherit root configuration."
        )
    try:
        routes = json.loads(os.environ.get("AGENT_BAND_CODEX_ROUTES", ""))
    except ValueError as error:
        raise ValueError("Codex subscription lane configuration is missing; relaunch the repaired wrapper.") from error
    wire = f"{pick['model']}@lane-{pick['effort']}"
    expected = f"{assigned['model']}@lane-{assigned['effort']}"
    if not isinstance(routes, dict) or routes.get(agent) != expected or wire not in routes.values():
        raise ValueError("This Codex role or exact lane is unavailable in the session's projected provider catalog.")
    return {**pick, "model": wire}


def _codex_openrouter_pick(
    agent: str, assigned: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]
) -> dict[str, Any]:
    """Require the role and wire pair frozen by the OpenRouter launcher."""
    if tool_input.get("fork_context"):
        raise ValueError("OpenRouter lanes require a fresh managed leaf; full-history forks inherit root settings.")
    if os.environ.get(MODEL_OVERRIDE_ENV) or os.environ.get(EFFORT_OVERRIDE_ENV):
        raise ValueError("Conflicting inherited model controls on the Codex OpenRouter route.")
    try:
        routes = json.loads(os.environ.get("AGENT_BAND_CODEX_ROUTES", ""))
    except ValueError as error:
        raise ValueError("Codex OpenRouter lane configuration is missing; relaunch the wrapper.") from error
    expected = _format_pick(assigned, "codex", "pi")["model"]
    formatted = _format_pick(pick, "codex", "pi")
    if not isinstance(routes, dict) or routes.get(agent) != expected or formatted["model"] not in routes.values():
        raise ValueError("This Codex role or exact OpenRouter lane is unavailable in the session's projected catalog.")
    return formatted


def _copilot(payload: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    # Reached through the agent-memory extension's onPreToolUse, which returns modifiedArgs
    # (PreToolUseHookOutput, @github/copilot-sdk 1.0.77). The `task` schema exposes both `model`
    # and `reasoning_effort`, so both dials are enforceable here.
    updated = dict(tool_input, model=pick["model"])
    if pick.get("effort"):
        updated["reasoning_effort"] = pick["effort"]
    return {"modifiedArgs": updated}


# Antigravity deliberately has no projection pick: its dynamic `invoke_subagent`
# schema accepts abstract model tiers (`inherit`, `flash_lite`, `flash`, `pro`),
# so the `_antigravity` adapter above enforces the `flash` tier and the `k-agent-`
# name directly instead of rewriting a registry pick.
# OMP has none either: its `task` tool takes no model argument at all, and the categories are
# spelled as `@role` tokens that readonly_config.yml.tmpl's `modelRoles` resolves, so there is
# nothing on the wire to rewrite.
# Pi has none because there is nothing to rewrite it with: no per-call model override is
# admitted (the binding is static; `LEAF_PARAMETER_KEYS` in subagent-contract.ts admits no
# `model` or `workflowScript` key), and Pi exposes no mutating pre-tool-use hook — its
# extension API can block a call, not modify its arguments. The named child profile's own
# frontmatter is what holds the band there.
ADAPTERS = {
    "claude_code": _claude,
    "cursor": _cursor,
    "codex": _codex,
    "copilot": _copilot,
}

# Each harness names the delegation tool and its agent-selecting argument differently. Codex's
# spawn_agent takes agent_type (task_name is a label, not a role) while Cursor and Claude use
# subagent_type. Order matters only in that the first present key wins.
AGENT_KEYS = ("subagent_type", "agent_type", "agent", "agent_name", "role", "subagent")
# Cursor transcript exports label the delegation tool `Subagent` (2026-09-04) while the
# cursor-agent bundle still names the call type `taskToolCall`; which of the two the preToolUse
# payload carries as `tool_name` is unverified, so both are matched here, in the hooks.json
# matcher, and in the Copilot extension's verbatim mirror of this set.
DELEGATION_TOOLS = {
    "Task",
    "Agent",
    "spawn_agent",
    "subagent",
    "Subagent",
    "task",
    "invoke_subagent",
    "define_subagent",
}


def _agent_name(payload: dict[str, Any], tool_input: dict[str, Any]) -> str:
    for key in AGENT_KEYS:
        value = tool_input.get(key) or payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _passthrough(harness: str) -> int:
    # Antigravity PreToolUse treats a missing `decision` as a denial with no reason; every
    # other harness reads `{}` as "no opinion".
    print(json.dumps({"decision": "allow"}) if harness == "antigravity" else "{}")
    return 0


def main() -> int:
    harness = os.environ.get(HARNESS_ENV, "")
    try:
        payload = read_payload()  # normalises the Antigravity `toolCall` envelope into tool_name/tool_input
    except ValueError:
        return _passthrough(harness)
    if not isinstance(payload, dict):
        return _passthrough(harness)

    schema_harness = os.environ.get(SCHEMA_HARNESS_ENV, "") or harness
    adapter = ADAPTERS.get(harness)
    tool = payload.get("tool_name") or payload.get("tool") or ""
    # Codex 0.153 reports its spawn tool namespaced ("collaborationspawn_agent", probed
    # 2026-09-06); the suffix is the tool.
    if isinstance(tool, str) and tool.endswith("spawn_agent"):
        tool = "spawn_agent"
    tool_input = payload.get("tool_input") or payload.get("arguments") or {}

    # Copilot hands the tool arguments over as a JSON string rather than an object (verified
    # against copilot 1.0.77); every other harness sends an object.
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except ValueError:
            tool_input = {}

    if adapter is None and harness != "antigravity" or tool not in DELEGATION_TOOLS or not isinstance(tool_input, dict):
        return _passthrough(harness)

    if is_delegated_leaf(payload):
        if harness == "antigravity":
            print(json.dumps({"decision": "deny", "reason": "A delegated leaf must not launch another agent."}))
        else:
            print(json.dumps(_deny(harness, "A delegated leaf must not launch another agent.")))
        return 0

    if harness == "antigravity" and tool in {"invoke_subagent", "define_subagent"}:
        print(json.dumps(_antigravity(payload, tool_input) or {}, sort_keys=True))
        return 0

    if adapter is None:
        print("{}")
        return 0

    subscription = os.environ.get("AGENT_BAND_SUBSCRIPTION", "")
    codex_subscription = harness == "codex" and subscription == schema_harness == "copilot"
    codex_openrouter = (
        harness == "codex" and schema_harness == "pi" and os.environ.get(MODEL_FORMAT_ENV) == "openrouter-preset"
    )
    if subscription and harness != "claude_code" and not codex_subscription:
        print(
            json.dumps(
                _deny(
                    harness,
                    "This subscription frontend has no verified explicit child-lane transport. Delegation is disabled on this route; do not substitute the root model for a worker.",
                )
            )
        )
        return 0

    agent = _agent_name(payload, tool_input)
    pick = _pick(schema_harness, agent) if agent else None
    override = _override(harness)
    if override:
        pick = {**(pick or {}), **override}
    if pick is None:
        if harness == "claude_code" and "AGENT_BAND_CLAUDE_ROUTES" in os.environ:
            print(json.dumps(_claude(payload, {}, tool_input)))
            return 0
        print(
            json.dumps(
                _deny(
                    harness,
                    "No registered category is available for this agent. Do not delegate on an unbound or missing model projection.",
                )
            )
        )
        return 0

    # A generic subagent type binds to `implement` (Cursor `generalPurpose`, Codex `worker`,
    # Copilot `task`), and lanes whose profile is unreachable on a harness are launched through
    # that same generic type carrying their registry pick as an explicit `model` — Cursor never
    # scans ~/.cursor/agents, so the adversarial verifier, the cheap mechanical / k-agent-smol
    # lanes, and the research and review lanes all arrive that way. Rewriting such a launch to
    # the generic type's band would silently collapse the lane onto the implement model, so the
    # rule is category-aware: on an `implement`-bound type an exact registry model/effort pair
    # survives, while a model no lane asked for (or an omitted one) is rewritten to the
    # implement band. A bound non-generic agent (research, review, memory, ...) asking for
    # another lane's pick is still a matrix bypass and gets rewritten to its own band. Claude
    # keeps its own alias projection in the adapter.
    assigned = pick
    if harness != "claude_code" and not override and pick.get("category") == "implement":
        try:
            selection = tool_input
            if codex_subscription and isinstance(tool_input.get("model"), str) and "@lane-" in tool_input["model"]:
                base, _, effort = tool_input["model"].rpartition("@lane-")
                if tool_input.get("reasoning_effort", effort) != effort:
                    raise ValueError("The explicit subscription selector and reasoning effort disagree.")
                selection = dict(tool_input, model=base, reasoning_effort=effort)
            if (
                codex_openrouter
                and isinstance(tool_input.get("model"), str)
                and "@preset/effort-" in tool_input["model"]
            ):
                base, _, effort = tool_input["model"].rpartition("@preset/effort-")
                if tool_input.get("reasoning_effort", effort) != effort:
                    raise ValueError("The explicit OpenRouter selector and reasoning effort disagree.")
                selection = dict(tool_input, model=f"openrouter/{base}", reasoning_effort=effort)
            pick = _generic_pick(schema_harness, pick, selection)
        except ValueError as error:
            print(json.dumps(_deny(harness, str(error))))
            return 0

    if codex_subscription:
        try:
            if override or os.environ.get(MODEL_FORMAT_ENV):
                raise ValueError("Conflicting inherited provider controls on the Codex subscription route.")
            pick = _codex_subscription_pick(agent, assigned, pick, tool_input)
        except ValueError as error:
            print(json.dumps(_deny(harness, str(error))))
            return 0

    if codex_openrouter:
        try:
            pick = _codex_openrouter_pick(agent, assigned, pick, tool_input)
        except ValueError as error:
            print(json.dumps(_deny(harness, str(error))))
            return 0
    else:
        pick = _format_pick(pick, harness, schema_harness)
    if harness == "cursor" and tool_input.get("model") == pick.get("model"):
        # Cursor Task ids carry only the base model; effort comes from the user's saved config.
        print("{}")
        return 0
    print(json.dumps(adapter(payload, pick, tool_input) or {}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
