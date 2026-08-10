#!/usr/bin/env python3
"""Project the band registry into a deployed JSON the hooks can read.

The pre-tool-use band hook runs from ``~/.agents/hooks`` with no access to this repo, so the
resolved per-agent picks have to exist as a plain file under ``~/.config/ai``. This flattens
the three-table lookup once, at apply time, so the hook does no resolution of its own: it looks up
``harnesses.<harness>.agents.<name>`` and gets the final pick (``model``, optional ``effort`` /
``alias``). Category/binding/band tables stay in ``ai_models``; they are not redeployed.

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
SCHEMA_VERSION = "1.0.0"
KIND = "ai.agent-bands"
CLAUDE_ALIASES = ("opus", "sonnet", "haiku")


def _claude_alias(model: str) -> str | None:
    for alias in CLAUDE_ALIASES:
        if alias in model:
            return alias
    return None


def build() -> dict:
    bindings = ai_models.load_agent_bindings(REGISTRY)
    bands = ai_models.load_model_bands(REGISTRY)

    harnesses = {}
    for harness in sorted(bands):
        agents = {}
        for agent in sorted(bindings):
            pick = ai_models.resolve_agent_model(REGISTRY, harness, agent)
            entry = {
                "model": pick["model"],
            }
            if pick["effort"]:
                entry["effort"] = pick["effort"]
            if harness == "claude_code":
                alias = _claude_alias(pick["model"])
                if alias:
                    entry["alias"] = alias
            agents[agent] = entry
        harnesses[harness] = {"agents": agents}

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
