#!/usr/bin/env python3
"""Pin a delegated agent to its category's band, whatever model the caller asked for.

Agent profiles already declare the right model, but a profile is only a default: every harness
lets the spawning model pass its own ``model`` argument per call, and several ship built-in
subagents with no profile at all. This is the backstop that makes the band non-negotiable.

It reads the flattened projection at ``~/.config/ai/agent-bands.v1.json`` (written by
scripts/generate_agent_bands.py) and rewrites the delegation payload in place. Harnesses disagree
on both the request and the response shape, so each gets an adapter selected by
``AGENT_BAND_HARNESS``; an unknown harness, an unbound agent, or a missing projection is a no-op,
never a block. Refusing a spawn because tiering data is stale would be worse than running it on
the caller's model.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECTION = Path(os.environ.get("AGENT_BANDS_FILE", os.path.expanduser("~/.config/ai/agent-bands.v1.json")))
HARNESS_ENV = "AGENT_BAND_HARNESS"
MODEL_OVERRIDE_ENV = "AGENT_BAND_MODEL_OVERRIDE"
EFFORT_OVERRIDE_ENV = "AGENT_BAND_EFFORT_OVERRIDE"

# Claude family aliases ordered by capability, so the gate can tell an upward escape from a
# sideways or downward one. `fable` is a small fast model, not a frontier one, so it sits with
# haiku. An unknown alias is treated as above the ceiling: clamp rather than let it through.
_CLAUDE_RANK = {"haiku": 0, "fable": 0, "sonnet": 1, "opus": 2}
_CLAUDE_CEILING = max(_CLAUDE_RANK.values()) + 1


def _load() -> dict[str, Any]:
    try:
        return json.loads(PROJECTION.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _pick(harness: str, agent: str) -> dict[str, Any] | None:
    projection = _load()
    if not projection:
        return None
    return projection.get("harnesses", {}).get(harness, {}).get("agents", {}).get(agent)


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


def _claude(payload: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    # Claude's Agent tool constrains `model` to the family aliases sonnet|opus|haiku|fable
    # (claude-code 2.1.222; anything else fails updatedInput schema validation), and each alias
    # resolves through one ANTHROPIC_DEFAULT_*_MODEL. The alias is a lossy projection of the band:
    # all three bands (claude-fable-5) spell `fable`, so the alias cannot separate them and the
    # hook cannot hold a cheap-band agent below medium-effort Fable — the profile frontmatter's
    # exact id is what does that, and it wins whenever no `model` is passed.
    #
    # What the hook can still enforce is the ceiling: clamp whenever the asked alias is MORE
    # capable than the band's. Comparing rank rather than equality is what stops
    # `model: "sonnet"` on a cheap-band agent, which an `asked == alias` early return let through.
    alias = pick.get("alias")
    asked = tool_input.get("model")
    if not alias or not isinstance(asked, str) or asked == alias:
        return {}
    if _CLAUDE_RANK.get(asked, _CLAUDE_CEILING) <= _CLAUDE_RANK.get(alias, 0):
        # An in-band or cheaper alias: the caller is not escaping upward, so leave it alone.
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": dict(tool_input, model=alias),
        }
    }


def _cursor(payload: dict[str, Any], pick: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    # Verified against cursor-agent 2026.07.23: updated_input replaces the whole input object
    # rather than merging, so the untouched keys have to be echoed back.
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
DELEGATION_TOOLS = {"Task", "Agent", "spawn_agent", "subagent", "task"}


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
    adapter = ADAPTERS.get(harness)
    tool = payload.get("tool_name") or payload.get("tool") or ""
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

    agent = _agent_name(payload, tool_input)
    pick = _pick(harness, agent) if agent else None
    override = _override(harness)
    if override:
        pick = {**(pick or {}), **override}
    if pick is None:
        print("{}")
        return 0

    print(json.dumps(adapter(payload, pick, tool_input) or {}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
