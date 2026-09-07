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

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "home/.chezmoidata/ai_models"
PROJECTION = REPO / "home/dot_config/ai/readonly_agent-bands.v1.json"
SCHEMA_VERSION = (
    "1.4.0"  # 1.1.0: counter_models; 1.2.0: agents.<name>.category; 1.3.0: cheap_lane_models; 1.4.0: lane_models
)
KIND = "ai.agent-bands"
CLAUDE_ALIASES = ("opus", "sonnet", "haiku", "fable")
CHEAP_LANES = ("mechanical", "memory")


def _claude_alias(model: str) -> str | None:
    for alias in CLAUDE_ALIASES:
        if alias in model:
            return alias
    return None


def build() -> dict:
    bindings = ai_models.load_agent_bindings(REGISTRY)
    category_models = ai_models.load_category_models(REGISTRY)

    harnesses = {}
    for harness in sorted(category_models):
        agents = {}
        cross_applied = set()
        for agent in sorted(bindings):
            if agent in ai_models.REVIEW_AUX_SLOTS:
                # Aux-slot lanes must project their override pick (e.g. cursor lanes_cross), or
                # the hook would rewrite cross-family spawns back onto the standard lane model.
                pick = ai_models.resolve_review_agent_model(REGISTRY, harness, agent)
                # The resolver reports the slot it landed on: an aux slot this harness does not
                # override degrades to the `lanes` override, or -- with no override table at all --
                # to the plain category pick. Either way the resolved model is the primary lane's,
                # so only an applied aux slot counts as a cross-family pick.
                if pick["source"] == "override" and pick["slot"] == ai_models.REVIEW_AUX_SLOTS[agent]:
                    cross_applied.add(agent)
            else:
                pick = ai_models.resolve_agent_model(REGISTRY, harness, agent)
            entry = {
                "model": pick["model"],
                # The gate's lane-pick pass-through applies only to `implement`-bound generic
                # types (Cursor `generalPurpose`, Codex `worker`, Copilot `task`, ...), never to a
                # bound profile asking for another lane's pick.
                "category": bindings[agent],
            }
            if pick["effort"]:
                entry["effort"] = pick["effort"]
            if harness == "claude_code":
                alias = _claude_alias(pick["model"])
                if alias:
                    entry["alias"] = alias
            agents[agent] = entry
        # Counter models: the refute picks, plus a cross-family-slot pick only on harnesses where
        # that slot actually applied (`cross_applied`) — a degraded aux slot resolves to the primary
        # lane model, and projecting that as a counter would hand the gate's counter pass-through a
        # primary model. Cheap-lane models: mechanical and memory. Both lists stay in the projection
        # because the docs and invariants read them by name, but the gate's pass-through is the wider
        # `lane_models`: every bound agent's resolved pick. A lane whose profile is unreachable on a
        # harness (Cursor never scans ~/.cursor/agents) is dispatched as the generic `implement` type
        # carrying its registry pick, and that holds for the research and review lanes too, not just
        # the counter and cheap ones — so the gate needs the whole set of lane picks to tell an
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
            if bindings[agent] == "refute" or agent in cross_applied:
                if model not in counter:
                    counter.append(model)
            elif bindings[agent] in CHEAP_LANES and model not in cheap:
                cheap.append(model)
        harnesses[harness] = {
            "agents": agents,
            "counter_models": counter,
            "cheap_lane_models": cheap,
            "lane_models": sorted(lanes),
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
