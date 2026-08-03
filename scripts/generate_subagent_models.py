#!/usr/bin/env python3
"""Resolve Copilot's and Gemini's subagent rosters against the band registry in .chezmoidata/ai_models/tiering.yaml.

Both harnesses pin subagent models inside a settings file that the harness itself rewrites at
runtime, so the merge scripts reconcile a checked-in source rather than rendering a template.
That source has to carry literal model ids, and Copilot's has drifted from the registry before.
This keeps the roster (which subagents exist) in the settings file and the picks (what each one
runs on) in .chezmoidata/ai_models/tiering.yaml, regenerating one from the other.

    generate_subagent_models.py check     exit 1 and print the divergence
    generate_subagent_models.py write     rewrite the settings files in place

Copilot spells the short context window "default" and the long one "long_context"; Gemini has no
context or effort dial on an override, so only the model id is written there.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import ai_models

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "home/.chezmoidata/ai_models"
COPILOT = REPO / "home/private_dot_copilot/settings.json"
GEMINI = REPO / "home/dot_gemini/settings.json"
CONTEXT_TIERS = {"short": "default", "long": "long_context"}


def _pick(harness: str, agent: str) -> dict[str, str]:
    resolved = ai_models.resolve_agent_model(REGISTRY, harness, agent)
    if resolved is None:
        raise SystemExit(f"{agent} is in the {harness} roster but has no agent_bindings entry in {REGISTRY}")
    return resolved


def copilot_desired(settings: dict) -> dict:
    for name, agent in settings["subagents"]["agents"].items():
        pick = _pick("copilot", name)
        agent["model"] = pick["model"]
        agent["effortLevel"] = pick["effort"]
        agent["contextTier"] = CONTEXT_TIERS[pick["context"]]
    return settings


def gemini_desired(settings: dict) -> dict:
    for name, override in settings["agents"]["overrides"].items():
        override.setdefault("modelConfig", {})["model"] = _pick("gemini", name)["model"]
    return settings


TARGETS = (
    (COPILOT, copilot_desired),
    (GEMINI, gemini_desired),
)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("check", "write"):
        print(__doc__, file=sys.stderr)
        return 2

    diverged = False
    for path, build in TARGETS:
        current = path.read_text(encoding="utf-8")
        desired = json.dumps(build(json.loads(current)), indent=2) + "\n"
        if current == desired:
            continue
        if argv[1] == "write":
            path.write_text(desired, encoding="utf-8")
            continue
        diverged = True
        print(f"{path} diverges from the band registry; run: {Path(__file__).name} write", file=sys.stderr)
        for line_current, line_desired in zip(current.splitlines(), desired.splitlines()):
            if line_current != line_desired:
                print(f"  -{line_current}\n  +{line_desired}", file=sys.stderr)

    return 1 if diverged else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
