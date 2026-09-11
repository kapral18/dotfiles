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

PROJECTION = Path(os.environ.get("AGENT_BANDS_FILE", os.path.expanduser("~/.config/ai/agent-bands.v1.json")))
HARNESS_ENV = "AGENT_BAND_HARNESS"
SCHEMA_HARNESS_ENV = "AGENT_BAND_SCHEMA_HARNESS"
MODEL_OVERRIDE_ENV = "AGENT_BAND_MODEL_OVERRIDE"
EFFORT_OVERRIDE_ENV = "AGENT_BAND_EFFORT_OVERRIDE"
MODEL_FORMAT_ENV = "AGENT_BAND_MODEL_FORMAT"
THINKING_SUFFIXES = {"off", "minimal", "none", "low", "medium", "high", "xhigh", "max"}

# Native aliases are finite transport slots, not permission to change category capability.
_CLAUDE_ALIASES = {"haiku", "sonnet", "opus", "fable"}


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
    # Cursor's selector is the complete wire control; its auto lanes have no effort field.
    # Backend-schema routes must follow the backend contract, not the frontend's exception.
    keys = ("model",) if harness == "cursor" else ("model", "effort")
    return isinstance(pick, dict) and all(isinstance(pick.get(key), str) and pick[key] for key in keys)


def _generic_pick(harness: str, pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    """Generic workers may carry another lane, but a model alone does not select its effort."""
    asked = tool_input.get("model")
    rows = _load().get("harnesses", {}).get(harness, {}).get("agents", {}).values()
    matches = [row for row in rows if isinstance(row, dict) and row.get("model") == asked]
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


def _split_thinking_suffix(model: str) -> tuple[str, str | None]:
    base, separator, suffix = model.rpartition(":")
    if separator and suffix in THINKING_SUFFIXES:
        return base, suffix
    return model, None


def _claude_alias_for_backend_model(model: str) -> str | None:
    """The Claude family alias a backend wire model projects onto, or None when none fits.

    The rules mirror the four `ANTHROPIC_DEFAULT_*_MODEL` slots `,claude-openrouter` exports
    (home/exact_bin/executable_,claude-openrouter), so on that route the alias ladder
    (haiku < sonnet < opus < fable) is the tier ladder:

        anthropic / claude  -> fable   T1 research/review/orchestrate (claude-fable-5.1 high)
        gpt / openai        -> opus    T2 implement (gpt-5.6-sol high)
        glm / z-ai          -> sonnet  T3 mechanical (glm-5.3-flash high)
        google / gemini     -> haiku   memory (gemini-3.8-flash low)

    Pi's `refute` pick is `openrouter/openai/gpt-5.6-sol`, which the `gpt`/`openai` rule sends to
    `opus`. That slot carries high instead of xhigh; `_claude` denies the mismatched wire pair
    rather than substituting the implementation lane for refutation.
    """
    lowered = model.lower()
    if "anthropic" in lowered or "claude" in lowered:
        return "fable"
    if "gpt" in lowered or "openai" in lowered:
        return "opus"
    if "glm" in lowered or "z-ai" in lowered:
        return "sonnet"
    if "google" in lowered or "gemini" in lowered:
        return "haiku"
    return None


def _format_pick(pick: dict[str, Any], harness: str, schema_harness: str) -> dict[str, Any]:
    model = pick.get("model")
    if not isinstance(model, str):
        return pick

    formatted = dict(pick)
    if os.environ.get(MODEL_FORMAT_ENV) == "openrouter-preset":
        base, suffix = _split_thinking_suffix(model)
        if base.startswith("openrouter/"):
            base = base.removeprefix("openrouter/")
        effort = suffix or formatted.get("effort")
        if isinstance(effort, str) and effort:
            formatted["model"] = f"{base}@preset/effort-{effort}"
            formatted["effort"] = effort
        else:
            formatted["model"] = base
        alias = _claude_alias_for_backend_model(base)
        if alias:
            formatted["alias"] = alias

    if harness == "claude_code" and schema_harness != harness:
        formatted["force_alias"] = True
    return formatted


def _claude(payload: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    routes_json = os.environ.get("AGENT_BAND_CLAUDE_ROUTES")
    if routes_json is not None:
        try:
            routes = json.loads(routes_json)
            alias = routes.get(f"{pick.get('model')}@lane-{pick.get('effort')}")
        except (ValueError, AttributeError):
            alias = None
        if not isinstance(alias, str) or alias not in _CLAUDE_ALIASES:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "This subscription route has no exact Claude alias for the assigned model/effort lane. Do not substitute another lane.",
                }
            }
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": dict(tool_input, model=alias),
            }
        }
    # Claude's Agent tool constrains `model` to the family aliases sonnet|opus|haiku|fable
    # (claude-code 2.1.222; anything else fails updatedInput schema validation), and each alias
    # resolves through one ANTHROPIC_DEFAULT_*_MODEL. The alias is a lossy projection of the band:
    # the tiers map onto three aliases (T1 research/review/orchestrate `fable`, T2 implement `opus`,
    # T3 mechanical/memory `sonnet`), so effort inside a tier is invisible to the hook — the profile
    # frontmatter's exact id and effort are what hold that, and they win whenever no `model` is passed.
    #
    # Enforce the assigned alias in both directions. A cheaper model is not a valid
    # replacement for a strong role. Omitted overrides retain the profile's exact id/effort.
    alias = pick.get("alias")
    asked = tool_input.get("model")
    wire = os.environ.get(f"ANTHROPIC_DEFAULT_{str(alias).upper()}_MODEL")
    if os.environ.get(MODEL_FORMAT_ENV) == "openrouter-preset" and wire != pick.get("model"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "The OpenRouter Claude alias does not carry the assigned model/effort pair. Do not substitute its other lane.",
            }
        }
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
    # Verified against cursor-agent 2026.07.23: updated_input replaces the whole input object
    # rather than merging, so the untouched keys have to be echoed back. Transcript exports now
    # label the tool `Subagent`; the payload shape is assumed unchanged (not re-verified).
    return {"updated_input": dict(tool_input, model=pick["model"])}


def _codex(payload: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    # Codex rejects updatedInput unless permissionDecision is "allow" ("PreToolUse hook returned
    # updatedInput without permissionDecision:allow", codex 0.146.0). spawn_agent takes model and
    # reasoning_effort directly, so both dials are enforceable here.
    updated = dict(tool_input, model=pick["model"])
    if pick.get("effort"):
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


def _copilot(payload: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    # Reached through the agent-memory extension's onPreToolUse, which returns modifiedArgs
    # (PreToolUseHookOutput, @github/copilot-sdk 1.0.77). The `task` schema exposes both `model`
    # and `reasoning_effort`, so both dials are enforceable here.
    updated = dict(tool_input, model=pick["model"])
    if pick.get("effort"):
        updated["reasoning_effort"] = pick["effort"]
    return {"modifiedArgs": updated}


# Antigravity deliberately has no adapter here. Its dynamic `invoke_subagent`
# schema accepts abstract model tiers (`inherit`, `flash_lite`, `flash`, `pro`),
# so the controller passes the registry's tier directly when launching a lane.
# OMP has none either: its `task` tool takes no model argument at all, and the categories are
# spelled as `@role` tokens that readonly_config.yml.tmpl's `modelRoles` resolves, so there is
# nothing on the wire to rewrite.
# Pi has none because there is nothing to rewrite it with: a per-call model override is reachable
# (including from a workflowScript), so the binding is runtime rather than static, but Pi exposes no
# mutating pre-tool-use hook — its extension API can block a call, not modify its arguments. The
# named child profile's own frontmatter is what holds the band there.
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
DELEGATION_TOOLS = {"Task", "Agent", "spawn_agent", "subagent", "Subagent", "task"}


def _agent_name(payload: dict[str, Any], tool_input: dict[str, Any]) -> str:
    for key in AGENT_KEYS:
        value = tool_input.get(key) or payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        print("{}")
        return 0

    harness = os.environ.get(HARNESS_ENV, "")
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

    if adapter is None or tool not in DELEGATION_TOOLS or not isinstance(tool_input, dict):
        print("{}")
        return 0

    if isinstance(payload.get("agent_id"), str) and payload["agent_id"].strip():
        print(json.dumps(_deny(harness, "A delegated leaf must not launch another agent.")))
        return 0

    subscription = os.environ.get("AGENT_BAND_SUBSCRIPTION", "")
    codex_subscription = harness == "codex" and subscription == schema_harness == "copilot"
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

    pick = _format_pick(pick, harness, schema_harness)
    if harness == "cursor" and tool_input.get("model") == pick.get("model"):
        # Cursor encodes effort in the model selector, not a separate argument.
        print("{}")
        return 0
    print(json.dumps(adapter(payload, pick, tool_input) or {}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
