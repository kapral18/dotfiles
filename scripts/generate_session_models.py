#!/usr/bin/env python3
"""Reconcile repo-owned harness root configs from session_models in tiering.yaml.

The session row is the root/main-session pick the user talks to. It is never a
delegation target. Cursor's root model/effort live in Cursor saved user config,
not in this repo, so this generator has no Cursor target.

    generate_session_models.py check     exit 1 and print the divergence
    generate_session_models.py write     rewrite the source files in place
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

import ai_models

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "home/.chezmoidata/ai_models"
CONTEXT_TIERS = {"short": "default", "long": "long_context"}
ANTIGRAVITY_DISPLAY = {"gemini-3.8-flash": "Gemini 3.8 Flash"}
CODEX_MODEL_RE = re.compile(r'^model\s*=\s*"[^"]*"', re.MULTILINE)
CODEX_EFFORT_RE = re.compile(r'^model_reasoning_effort\s*=\s*"[^"]*"', re.MULTILINE)
OMP_DEFAULT_RE = re.compile(r"^  default: .+$", re.MULTILINE)

ApplyFn = Callable[[str, dict[str, str]], str]


def apply_claude(current: str, row: dict[str, str]) -> str:
    settings = json.loads(current)
    model = row["model"]
    effort = row["effort"]
    settings["model"] = model
    settings["effortLevel"] = effort
    model_settings = settings.setdefault("modelSettings", {})
    entry = model_settings.setdefault(model, {})
    entry["effortLevel"] = effort
    return json.dumps(settings, indent=2) + "\n"


def apply_codex(current: str, row: dict[str, str]) -> str:
    updated, model_n = CODEX_MODEL_RE.subn(f'model = "{row["model"]}"', current, count=1)
    if model_n != 1:
        raise ValueError("codex config has no top-level model assignment")
    updated, effort_n = CODEX_EFFORT_RE.subn(f'model_reasoning_effort = "{row["effort"]}"', updated, count=1)
    if effort_n != 1:
        raise ValueError("codex config has no top-level model_reasoning_effort assignment")
    return updated


def apply_copilot(current: str, row: dict[str, str]) -> str:
    settings = json.loads(current)
    settings["model"] = row["model"]
    settings["effortLevel"] = row["effort"]
    settings["contextTier"] = CONTEXT_TIERS[row["context"]]
    return json.dumps(settings, indent=2) + "\n"


def apply_pi(current: str, row: dict[str, str]) -> str:
    model = row["model"]
    if "/" not in model:
        raise ValueError(f"pi session model {model!r} has no provider/model split")
    provider, default_model = model.split("/", 1)
    settings = json.loads(current)
    settings["defaultProvider"] = provider
    settings["defaultModel"] = default_model
    settings["defaultThinkingLevel"] = row["effort"]
    return json.dumps(settings, indent=2) + "\n"


def apply_omp(current: str, row: dict[str, str]) -> str:
    lines = current.splitlines(keepends=True)
    in_roles = False
    replaced = False
    out: list[str] = []
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped == "modelRoles:":
            in_roles = True
            out.append(line)
            continue
        if in_roles:
            if stripped and not stripped.startswith(" ") and not stripped.startswith("#"):
                in_roles = False
            elif OMP_DEFAULT_RE.match(stripped):
                newline = "\n" if line.endswith("\n") else ""
                out.append(f"  default: {row['model']}:{row['effort']}{newline}")
                replaced = True
                continue
        out.append(line)
    if not replaced:
        raise ValueError("omp config has no modelRoles.default line")
    return "".join(out)


def antigravity_display_name(row: dict[str, str]) -> str:
    try:
        display = ANTIGRAVITY_DISPLAY[row["model"]]
    except KeyError:
        raise ValueError(f"unmapped antigravity model id: {row['model']!r}") from None
    return f"{display} ({row['effort'].capitalize()})"


def apply_antigravity(current: str, row: dict[str, str]) -> str:
    settings = json.loads(current)
    settings["model"] = antigravity_display_name(row)
    return json.dumps(settings, indent=2) + "\n"


def default_targets(session: dict[str, dict[str, str]]) -> list[tuple[Path, dict[str, str], ApplyFn]]:
    return [
        (REPO / "home/dot_claude/settings.work.json", session["claude_code"], apply_claude),
        (REPO / "home/dot_claude/settings.personal.json", session["claude_code"], apply_claude),
        (REPO / "home/dot_codex/private_config.work.toml", session["codex"], apply_codex),
        (REPO / "home/dot_codex/private_config.personal.toml", session["codex"], apply_codex),
        (REPO / "home/private_dot_copilot/settings.json", session["copilot"], apply_copilot),
        (REPO / "home/dot_pi/agent/readonly_settings.work.json", session["pi"], apply_pi),
        (REPO / "home/dot_pi/agent/readonly_settings.personal.json", session["pi"], apply_pi),
        (REPO / "home/dot_omp/private_agent/readonly_config.yml.tmpl", session["omp"], apply_omp),
        (
            REPO / "home/dot_gemini/antigravity-cli/readonly_settings.policy.json",
            session["antigravity"],
            apply_antigravity,
        ),
    ]


def reconcile(mode: str, targets: list[tuple[Path, dict[str, str], ApplyFn]]) -> int:
    diverged = False
    for path, row, apply in targets:
        current = path.read_text(encoding="utf-8")
        desired = apply(current, row)
        if current == desired:
            continue
        if mode == "write":
            path.write_text(desired, encoding="utf-8")
            continue
        diverged = True
        print(f"{path} diverges from session_models; run: {Path(__file__).name} write", file=sys.stderr)
        for line_current, line_desired in zip(current.splitlines(), desired.splitlines()):
            if line_current != line_desired:
                print(f"  -{line_current}\n  +{line_desired}", file=sys.stderr)
    return 1 if diverged else 0


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("check", "write"):
        print(__doc__, file=sys.stderr)
        return 2
    session = ai_models.load_session_models(REGISTRY)
    return reconcile(argv[1], default_targets(session))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
