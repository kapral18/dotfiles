#!/usr/bin/env python3
"""Flat-TOML config loader for ,palantir (stdlib only; no tomllib on Python 3.9).

Deployed config lives at ``~/.config/palantir/config.toml`` (chezmoi-managed,
from ``home/dot_config/palantir/readonly_config.toml.tmpl``). It is a flat
``key = value`` file -- no nested tables -- so a tiny hand parser suffices (the
repo precedent is hand-parsing YAML without PyYAML; same discipline here).
Unknown keys are ignored; missing keys fall back to the defaults below.

Resolved keys:

  default_harness            str   interactive agent CLI for role panes
  coordinator_harness        str   harness for the per-legion coordinator pane
  triage_harness             str   per-role harness overrides (same for
  diagnose_harness                 diagnose/investigate/implement/
  investigate_harness              adversarial_review; empty = default_harness)
  implement_harness          str
  adversarial_review_harness str
  implement_model            str   optional model per role (harness-specific)
  adversarial_review_model   str
  adversarial_review_family  str   explicit family when the model name hides it
  watch_interval_secs        int   supervisor poll interval
  max_implement_attempts     int   implement rework budget per legion (verify failures + review-blocker returns)
  inject_settle_secs         int   wait after pane spawn before first inject

CLI (stdlib):

  palantir_config.py get <key>     print a single value (exit 1 if unknown)
  palantir_config.py show          print all resolved values as JSON
  palantir_config.py roles         print the resolved role table as JSON
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

DEFAULTS = {
    "default_harness": "copilot",
    "coordinator_harness": "",
    "coordinator_model": "gpt-5.6-sol",
    "coordinator_family": "gpt",
    "triage_harness": "",
    "triage_model": "gpt-5.6-sol",
    "triage_family": "gpt",
    "diagnose_harness": "",
    "diagnose_model": "gpt-5.6-sol",
    "diagnose_family": "gpt",
    "investigate_harness": "",
    "investigate_model": "gpt-5.6-sol",
    "investigate_family": "gpt",
    "implement_harness": "",
    "adversarial_review_harness": "copilot",
    "implement_model": "gpt-5.6-sol",
    "implement_family": "gpt",
    "adversarial_review_model": "claude-fable-5",
    "adversarial_review_family": "claude",
    "watch_interval_secs": 20,
    "max_implement_attempts": 3,
    "inject_settle_secs": 2,
}

_ROLE_KEYS = ("triage", "diagnose", "investigate", "implement", "adversarial_review")


def config_path() -> Path:
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return Path(os.environ.get("PALANTIR_CONFIG", xdg / "palantir" / "config.toml")).expanduser()


def _parse_flat_toml(text: str) -> dict:
    values: dict = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.split("#", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return values


def load(path: Optional[Path] = None) -> dict:
    """Resolve config: file values over defaults, coerced to default types."""
    resolved = dict(DEFAULTS)
    target = path or config_path()
    try:
        raw = _parse_flat_toml(target.read_text(encoding="utf-8"))
    except OSError:
        raw = {}
    for key, value in raw.items():
        if key not in resolved:
            continue
        default = DEFAULTS[key]
        if isinstance(default, bool):
            resolved[key] = value.lower() in ("1", "true", "yes", "on")
        elif isinstance(default, int):
            try:
                resolved[key] = int(value)
            except ValueError:
                pass
        else:
            resolved[key] = value
    return resolved


def roles(config: Optional[dict] = None) -> dict:
    """The role table handed to machine.resolve_roles at summon time."""
    cfg = config or load()
    table: dict = {}
    for role in _ROLE_KEYS:
        name = role.replace("_", "-")
        table[name] = {
            "harness": cfg.get(f"{role}_harness") or cfg["default_harness"],
            "model": cfg.get(f"{role}_model", ""),
        }
        family = cfg.get(f"{role}_family", "")
        if family:
            table[name]["family"] = family
    table["coordinator"] = {
        "harness": cfg.get("coordinator_harness") or cfg["default_harness"],
        "model": cfg.get("coordinator_model", ""),
    }
    if cfg.get("coordinator_family"):
        table["coordinator"]["family"] = cfg["coordinator_family"]
    return table


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = argparse.ArgumentParser(prog="palantir_config.py", description=",palantir config resolver")
    sub = parser.add_subparsers(dest="command", required=True)
    get_p = sub.add_parser("get")
    get_p.add_argument("key")
    sub.add_parser("show")
    sub.add_parser("roles")
    args = parser.parse_args(argv)

    cfg = load()
    if args.command == "get":
        if args.key not in cfg:
            print(f"unknown config key: {args.key}", file=sys.stderr)
            return 1
        print(cfg[args.key])
        return 0
    if args.command == "roles":
        print(json.dumps(roles(cfg), indent=2))
        return 0
    print(json.dumps(cfg, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
