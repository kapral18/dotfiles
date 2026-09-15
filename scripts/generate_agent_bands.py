#!/usr/bin/env python3
"""Project category model routing into a deployed JSON the hooks can read.

The pre-tool-use band hook runs from ``~/.agents/hooks`` with no access to this repo, so the
resolved per-agent picks have to exist as a plain file under ``~/.config/ai``. This flattens
the three-table lookup once, at apply time, so the hook does no resolution of its own: it looks up
``harnesses.<harness>.agents.<name>`` and gets the final pick (``model``, optional ``effort`` /
``alias``). Category/binding/model tables stay in ``ai_models``; they are not redeployed.

    generate_agent_bands.py check     exit 1 when the committed projection is stale
    generate_agent_bands.py write     regenerate it

``alias`` exists for Claude Code alone: its Agent tool takes a family alias rather than a model id,
so the hook can only enforce the coarser opus/sonnet/haiku choice there. The profile frontmatter
still carries the exact id, and the hook is the backstop for calls that pass ``model`` explicitly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import ai_models
from yaml_parser import parse_scalar

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "home/.chezmoidata/ai_models"
PROJECTION = REPO / "home/dot_config/ai/readonly_agent-bands.v1.json"
SCHEMA_VERSION = "1.6.0"  # 1.1.0: counter_models; 1.2.0: agents.<name>.category; 1.3.0: cheap_lane_models; 1.4.0: lane_models; 1.5.0: session; 1.6.0: reachable_agents
KIND = "ai.agent-bands"
CLAUDE_ALIASES = ("opus", "sonnet", "haiku", "fable")
CHEAP_LANES = ("mechanical", "memory")

# Antigravity effort is informational (`invoke_subagent` takes abstract tiers only), so its
# agent rows carry no effort. Every other harness keeps the registry effort on the row.
EFFORTLESS_HARNESSES = frozenset({"antigravity"})

# Where each harness keeps the profiles a delegation can reach by name: directory plus the
# filename affixes that wrap the binding name. Antigravity has no entry on purpose: its lanes
# are dynamic define_subagent/invoke_subagent calls, never files. Cursor templates exist on
# disk but the CLI never scans ~/.cursor/agents, so cursor counts as profile-less too.
PROFILE_DIRS = {
    "claude_code": ("home/dot_claude/exact_agents", "", ".md.tmpl"),
    "codex": ("home/dot_codex/exact_agents", "readonly_", ".toml.tmpl"),
    "copilot": ("home/private_dot_copilot/exact_agents", "readonly_", ".agent.md.tmpl"),
    "cursor": None,
    "omp": ("home/dot_omp/private_agent/exact_agents", "", ".md.tmpl"),
    "pi": ("home/dot_pi/agent/exact_agents", "", ".md.tmpl"),
    "antigravity": None,
}


def _load_binding_fallbacks() -> dict[str, dict[str, str]]:
    """Read the ``binding_fallbacks:`` map from tiering.yaml without external dependencies.

    Two-level block only (harness -> {generic, reason}); anything else fails closed so a
    hand-edited allow-list cannot silently widen. ``ai_models.SECTION_FILES`` names the file;
    it has no typed loader for this map yet, hence the local reader.
    """
    path = REGISTRY / "tiering.yaml"
    fallbacks: dict[str, dict[str, str]] = {}
    current: str | None = None
    in_section = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not raw_line.startswith(" "):
            if line.strip() == "binding_fallbacks:":
                in_section = True
                continue
            if in_section:
                break
            continue
        if not in_section:
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, _, value = line.strip().partition(":")
        key = key.strip()
        value = value.strip()
        if indent == 2 and not value:
            current = key
            fallbacks[current] = {}
        elif indent == 4 and current is not None and value:
            if key not in ("generic", "reason"):
                raise ValueError(f"{path}: binding_fallbacks.{current}.{key} is not generic|reason")
            fallbacks[current][key] = parse_scalar(value)
        else:
            raise ValueError(f"{path}: malformed binding_fallbacks line: {raw_line!r}")
    return fallbacks


def _profile_names(harness: str) -> set[str]:
    entry = PROFILE_DIRS.get(harness)
    if entry is None:
        return set()
    directory, prefix, suffix = entry
    names = set()
    root = REPO / directory
    if root.is_dir():
        for path in root.glob("*.tmpl"):
            name = path.name
            if prefix and name.startswith(prefix):
                name = name[len(prefix) :]
            if name.endswith(suffix):
                names.add(name[: -len(suffix)])
    return names


def _check_reachability(bindings: dict[str, str], category_models: dict) -> dict[str, list[str]]:
    """Fail closed when a (binding, harness) pair has no reachable profile and no reasoned fallback.

    Every profile-less pair must sit on a harness with a ``binding_fallbacks`` entry naming a
    generic type and a reason; the generic (unless ``none``) must itself be a bound agent so a
    typo cannot bless an unreachable lane. Returns the per-harness reachable-agent lists.
    """
    fallbacks = _load_binding_fallbacks()
    reachable: dict[str, list[str]] = {}
    uncovered: list[str] = []
    for harness in sorted(category_models):
        profiles = _profile_names(harness)
        reachable[harness] = sorted(agent for agent in sorted(bindings) if agent in profiles)
        fallback = fallbacks.get(harness)
        for agent in sorted(bindings):
            if agent in profiles:
                continue
            generic = (fallback or {}).get("generic", "")
            reason = (fallback or {}).get("reason", "")
            if not generic or not reason:
                uncovered.append(f"{harness}/{agent}: no profile and no reasoned fallback")
            elif generic != "none" and generic not in bindings:
                uncovered.append(f"{harness}/{agent}: fallback generic {generic!r} is not a bound agent")
    if uncovered:
        raise SystemExit(
            "unreachable (binding, harness) pairs without a reasoned binding_fallbacks entry:\n"
            + "\n".join(f"  {item}" for item in uncovered)
        )
    return reachable


def _claude_alias(model: str) -> str | None:
    for alias in CLAUDE_ALIASES:
        if alias in model:
            return alias
    return None


def build() -> dict:
    bindings = ai_models.load_agent_bindings(REGISTRY)
    category_models = ai_models.load_category_models(REGISTRY)
    session_models = ai_models.load_session_models(REGISTRY)
    reachable = _check_reachability(bindings, category_models)

    harnesses = {}
    for harness in sorted(category_models):
        agents = {}
        for agent in sorted(bindings):
            pick = ai_models.resolve_agent_model(REGISTRY, harness, agent)
            entry = {
                "model": pick["model"],
                # The gate's lane-pick pass-through applies only to `implement`-bound generic
                # types (Cursor `generalPurpose`, Codex `worker`, Copilot `task`, ...), never to a
                # bound profile asking for another lane's pick.
                "category": bindings[agent],
            }
            if pick["effort"] and harness not in EFFORTLESS_HARNESSES:
                entry["effort"] = pick["effort"]
            if harness == "claude_code":
                alias = _claude_alias(pick["model"])
                if alias:
                    entry["alias"] = alias
            agents[agent] = entry
        # Counter models: the refute picks. Cheap-lane models: mechanical and memory. Both lists stay in the projection
        # because docs and invariants read them by name. The gate matches complete `agents` rows,
        # not these model-only inventories. A lane whose profile is unreachable on a
        # harness (Cursor never scans ~/.cursor/agents) is dispatched as the generic `implement` type
        # carrying its registry pick, and that holds for the research and review lanes too, not just
        # the counter and cheap ones — so the gate needs the whole set of lane rows to tell an
        # explicit registry choice from a model nobody in the matrix asked for.
        counter = []
        cheap = []
        lanes = []
        for agent in sorted(bindings):
            model = agents[agent]["model"]
            if not model or model == "inherit":
                continue
            if model not in lanes:
                lanes.append(model)
            if bindings[agent] == "refute":
                if model not in counter:
                    counter.append(model)
            elif bindings[agent] in CHEAP_LANES and model not in cheap:
                cheap.append(model)
        session = session_models[harness]
        harnesses[harness] = {
            "agents": agents,
            "reachable_agents": reachable[harness],
            "counter_models": counter,
            "cheap_lane_models": cheap,
            "lane_models": sorted(lanes),
            "session": {
                "model": session["model"],
                "effort": session["effort"],
                "context": session["context"],
            },
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "harnesses": harnesses,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("check", "write"):
        print(__doc__, file=sys.stderr)
        return 2

    desired = json.dumps(build(), indent=2, sort_keys=False) + "\n"
    if argv[1] == "write":
        PROJECTION.parent.mkdir(parents=True, exist_ok=True)
        PROJECTION.write_text(desired, encoding="utf-8")
        return 0

    current = PROJECTION.read_text(encoding="utf-8") if PROJECTION.is_file() else ""
    if current != desired:
        print(f"{PROJECTION} is stale; run: {Path(__file__).name} write", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
