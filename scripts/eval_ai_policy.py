#!/usr/bin/env python3
"""Eval scaffolding for the SOP policy compiler — plan mode only.

`plan` reads a fixture matrix and reports the exact supported cell count, estimated
tokens, harnesses, unsupported-cell summary, and required spend approval before any live request
could be issued. `verify-routing`/`verify-behavior` exist so criteria 6/7 are
mechanically checkable, but every cell is reported `blocked` rather than
executed: live cross-product eval spend is an explicit external dependency
(see the sop-distillation spec packet) requiring the user's separate approval
of an authorized payload and spend. This module never performs a network
call or invokes a model.

Usage:
    eval_ai_policy.py plan --matrix PATH [--manifest PATH] [--capabilities PATH]
    eval_ai_policy.py verify-routing --matrix PATH --runs-root PATH [--capabilities PATH]
    eval_ai_policy.py verify-behavior --baseline-ref REF --candidate-ref REF --matrix PATH --runs-root PATH [--capabilities PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ai_harness_capabilities as capabilities

try:
    import yaml
except ImportError:  # pragma: no cover - repo has no PyYAML dependency by convention
    yaml = None


def _load_matrix(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    return _parse_minimal_yaml(text)


def _parse_minimal_yaml(text: str) -> dict:
    """Hand-rolled fallback parser for this repo's flat matrix fixture shape.

    Matches the existing no-PyYAML-dependency convention (scripts/ai_models.py
    hand-parses YAML sections rather than adding a dependency). Only supports
    the flat list-of-scalars-under-a-key shape the fixture matrix uses.
    """
    result: dict[str, list[str]] = {}
    current_key = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current_key = line[:-1].strip()
            result[current_key] = []
        elif line.strip().startswith("- ") and current_key is not None:
            result[current_key].append(line.strip()[2:].strip().strip('"'))
    return result


def _dimensions(matrix: dict) -> tuple[list, list, list, list, int]:
    harnesses = matrix.get("harnesses", [])
    models = matrix.get("frontier_models", [])
    roles = matrix.get("agent_roles", [])
    scenarios = matrix.get("scenarios", [])
    repetitions = int(matrix.get("repetitions", [1])[0]) if matrix.get("repetitions") else 1
    return harnesses, models, roles, scenarios, repetitions


def _cells(matrix: dict) -> list[dict]:
    harnesses, models, roles, scenarios, repetitions = _dimensions(matrix)
    return [
        {
            "harness": harness,
            "frontier_model": model,
            "agent_role": role,
            "scenario": scenario,
            "repetition": repetition,
        }
        for harness in harnesses
        for model in models
        for role in roles
        for scenario in scenarios
        for repetition in range(1, repetitions + 1)
    ]


def _cell_supported(cell: dict, snapshot: dict[str, capabilities.HarnessCapability]) -> tuple[bool, str | None]:
    harness = snapshot.get(cell["harness"])
    if harness is None:
        return False, "no capability snapshot entry"
    if cell["agent_role"] == "subagent-static-pinned" and harness.subagent_model_binding != "static":
        return False, f"subagent_model_binding is {harness.subagent_model_binding!r}, not 'static'"
    return True, None


def _partition_cells(matrix: dict, capability_snapshot: Path | None) -> tuple[list[dict], list[dict]]:
    cells = _cells(matrix)
    if capability_snapshot is None:
        return cells, []
    snapshot = capabilities.load_snapshot_path(capability_snapshot)
    supported = []
    unsupported = []
    for cell in cells:
        is_supported, reason = _cell_supported(cell, snapshot)
        if is_supported:
            supported.append(cell)
        else:
            unsupported.append({**cell, "unsupported_reason": reason})
    return supported, unsupported


def _scenario_rule_id(scenario: str) -> str:
    for suffix in (".positive", ".negative-control", ".malformed-input"):
        if scenario.endswith(suffix):
            return scenario[: -len(suffix)]
    return scenario


def _risk_tier_summary(cells: list[dict], manifest_path: Path | None) -> dict | None:
    if manifest_path is None:
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tiers = {record["id"]: record["risk_tier"] for record in manifest.get("rules", [])}
    scenario_counts: dict[str, int] = {}
    cell_counts: dict[str, int] = {}
    unknown_rules = []
    seen_scenarios = set()
    for cell in cells:
        scenario = cell["scenario"]
        rule_id = _scenario_rule_id(scenario)
        tier = tiers.get(rule_id)
        if tier is None:
            unknown_rules.append(rule_id)
            tier = "unknown"
        cell_counts[tier] = cell_counts.get(tier, 0) + 1
        if scenario not in seen_scenarios:
            scenario_counts[tier] = scenario_counts.get(tier, 0) + 1
            seen_scenarios.add(scenario)
    return {
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "cell_counts": dict(sorted(cell_counts.items())),
        "unknown_rule_ids": sorted(set(unknown_rules)),
    }


def _unsupported_summary(cells: list[dict]) -> list[dict]:
    grouped: dict[tuple[str | None, str, str], int] = {}
    for cell in cells:
        key = (cell.get("unsupported_reason"), cell["harness"], cell["agent_role"])
        grouped[key] = grouped.get(key, 0) + 1
    return [
        {"reason": reason, "harness": harness, "agent_role": role, "count": count}
        for (reason, harness, role), count in sorted(grouped.items())
    ]


def cmd_plan(args: argparse.Namespace) -> int:
    matrix = _load_matrix(args.matrix)
    harnesses, models, roles, scenarios, repetitions = _dimensions(matrix)

    supported_cells, unsupported_cells = _partition_cells(matrix, args.capabilities)
    cell_count = len(supported_cells)
    input_tokens = cell_count * args.input_tokens_per_cell
    output_tokens = cell_count * args.output_tokens_per_cell
    risk_tiers = _risk_tier_summary(supported_cells, args.manifest)
    plan = {
        "cell_count": cell_count,
        "dimensions": {
            "harnesses": harnesses,
            "frontier_models": models,
            "agent_roles": roles,
            "scenarios": scenarios,
            "repetitions": repetitions,
        },
        "estimated_requests": cell_count,
        "token_estimate_basis": {
            "input_tokens_per_cell": args.input_tokens_per_cell,
            "output_tokens_per_cell": args.output_tokens_per_cell,
        },
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "estimated_total_tokens": input_tokens + output_tokens,
        "risk_tiers": risk_tiers,
        "harnesses": sorted(set(harnesses)),
        "unsupported_cell_count": len(unsupported_cells),
        "unsupported_summary": _unsupported_summary(unsupported_cells),
        "max_authorized_spend": None,
        "authorization_status": "not authorized — plan mode never issues live requests; "
        "execution requires a separate explicit approval token from the user per the "
        "sop-distillation spec packet's external-dependencies section",
    }
    print(json.dumps(plan, indent=2))
    return 0


def _blocked_report(matrix_path: Path, runs_root: Path, mode: str, capability_snapshot: Path | None = None) -> dict:
    matrix = _load_matrix(matrix_path)
    supported_cells, unsupported_cells = _partition_cells(matrix, capability_snapshot)
    return {
        "mode": mode,
        "runs_root": str(runs_root),
        "cells": [
            {
                **cell,
                "status": "blocked",
                "reason": "live cross-product eval execution is an external dependency blocked on "
                "user-approved paid spend; no live request was issued",
            }
            for cell in supported_cells
        ],
        "unsupported_cell_count": len(unsupported_cells),
        "unsupported_summary": _unsupported_summary(unsupported_cells),
        "unblocked_count": 0,
        "blocked_count": len(supported_cells),
    }


def cmd_verify_routing(args: argparse.Namespace) -> int:
    report = _blocked_report(args.matrix, args.runs_root, "verify-routing", args.capabilities)
    print(json.dumps(report, indent=2))
    return 2 if report["blocked_count"] or report["unsupported_cell_count"] else 0


def cmd_verify_behavior(args: argparse.Namespace) -> int:
    report = _blocked_report(args.matrix, args.runs_root, "verify-behavior", args.capabilities)
    report["baseline_ref"] = args.baseline_ref
    report["candidate_ref"] = args.candidate_ref
    print(json.dumps(report, indent=2))
    return 2 if report["blocked_count"] or report["unsupported_cell_count"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SOP policy eval scaffolding (plan mode only)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    plan = sub.add_parser("plan")
    plan.add_argument("--matrix", type=Path, required=True)
    plan.add_argument("--manifest", type=Path)
    plan.add_argument("--capabilities", type=Path)
    plan.add_argument("--input-tokens-per-cell", type=int, default=4000)
    plan.add_argument("--output-tokens-per-cell", type=int, default=1000)

    routing = sub.add_parser("verify-routing")
    routing.add_argument("--matrix", type=Path, required=True)
    routing.add_argument("--runs-root", type=Path, required=True)
    routing.add_argument("--capabilities", type=Path)

    behavior = sub.add_parser("verify-behavior")
    behavior.add_argument("--baseline-ref", required=True)
    behavior.add_argument("--candidate-ref", required=True)
    behavior.add_argument("--matrix", type=Path, required=True)
    behavior.add_argument("--runs-root", type=Path, required=True)
    behavior.add_argument("--capabilities", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "plan":
        return cmd_plan(args)
    if args.cmd == "verify-routing":
        return cmd_verify_routing(args)
    if args.cmd == "verify-behavior":
        return cmd_verify_behavior(args)
    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
