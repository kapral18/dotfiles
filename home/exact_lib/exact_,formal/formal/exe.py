"""Wrappers around the compiled FormalKit ``unit`` executable's ``explore``,
``mutate``, and ``traces`` JSON output shapes (contract §4). ``lake exe``
builds the executable if needed, so callers do not need a separate build step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .build import is_environment_or_provisioning_failure
from .util import CliError, run


def run_exe(unit_dir: Path, subcommand: str, extra_args: list[str], timeout: float | None = None):
    return run(["lake", "exe", "unit", subcommand, *extra_args], cwd=unit_dir, timeout=timeout)


def _budget_args(max_states: int | None, max_depth: int | None) -> list[str]:
    args: list[str] = []
    if max_states is not None:
        args += ["--max-states", str(max_states)]
    if max_depth is not None:
        args += ["--max-depth", str(max_depth)]
    return args


def _parse_json(result, action: str) -> dict[str, Any]:
    if result.returncode != 0:
        raise CliError(
            f"`lake exe unit {action}` failed:\n{result.stdout}\n{result.stderr}",
            code=2,
            environment_error=is_environment_or_provisioning_failure(result),
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CliError(f"Non-JSON {action} output: {exc}\n{result.stdout[:2000]}", code=2) from exc


def explore(
    unit_dir: Path, max_states: int | None, max_depth: int | None, timeout: float | None = None
) -> dict[str, Any]:
    result = run_exe(unit_dir, "explore", _budget_args(max_states, max_depth), timeout=timeout)
    return _parse_json(result, "explore")


def prop_ok(prop: dict[str, Any]) -> bool:
    """A ``holds`` expectation is met by status ``holds``; a ``refuted``
    expectation (a seeded false property) is met by status ``violated``."""
    expect = prop.get("expect")
    status = prop.get("status")
    if expect == "holds":
        return status == "holds"
    if expect == "refuted":
        return status == "violated"
    return False


def _classify_mutant(mutant: dict[str, Any]) -> str:
    """Reclassify a Lean-reported ``killed`` mutant as ``wrong-killer`` when
    none of its declared expected killers is among the properties that
    actually killed it: something killed the mutant, but not the property
    the author intended to validate, so the mutant is not proof the intended
    property is adequate. A mutant with an empty ``expected`` list names no
    property at all to validate against, so it is never classified
    ``killed`` either -- it falls into the same ``wrong-killer`` bucket
    (``audit``/the standalone ``mutate`` command additionally treat any
    such empty-``expected`` mutant as vacuous and fail the whole stage, see
    ``mutate_vacuous_names`` below). ``survived`` and killer-matching
    ``killed`` pass through unchanged."""
    status = mutant.get("status")
    if status != "killed":
        return status
    expected = mutant.get("expected") or []
    killed_by = mutant.get("killed_by") or []
    if expected and set(killed_by) & set(expected):
        return status
    return "wrong-killer"


def explore_vacuous(props: list[dict[str, Any]]) -> bool:
    """Zero declared properties is a vacuous pass -- ``explore`` never actually checked
    anything, which is not the same as a check that ran and found nothing violated. Shared by
    the standalone ``,formal explore`` command and ``audit.run_stage_explore`` so both apply the
    identical condition."""
    return not props


def mutate_vacuous_names(mutants: list[dict[str, Any]]) -> list[str]:
    """Names (sorted) of every mutant with no declared expected killer: it names no property to
    validate against, so it is vacuous even when Lean happens to report it ``killed`` or
    ``survived``. Shared by the standalone ``,formal mutate`` command and
    ``audit.run_stage_mutate`` so both apply the identical condition."""
    return sorted(m["name"] for m in mutants if not (m.get("expected") or []))


def mutate(
    unit_dir: Path, max_states: int | None, max_depth: int | None, timeout: float | None = None
) -> dict[str, Any]:
    result = run_exe(unit_dir, "mutate", _budget_args(max_states, max_depth), timeout=timeout)
    payload = _parse_json(result, "mutate")
    for mutant in payload.get("mutants", []):
        mutant["status"] = _classify_mutant(mutant)
    return payload


def traces(
    unit_dir: Path,
    mode: str,
    max_n: int | None,
    timeout: float | None = None,
    max_states: int | None = None,
    max_depth: int | None = None,
) -> str:
    args = ["--mode", mode]
    if max_n is not None:
        args += ["--max", str(max_n)]
    args += _budget_args(max_states, max_depth)
    result = run_exe(unit_dir, "traces", args, timeout=timeout)
    if result.returncode != 0:
        raise CliError(
            f"`lake exe unit traces` failed:\n{result.stdout}\n{result.stderr}",
            code=2,
            environment_error=is_environment_or_provisioning_failure(result),
        )
    return result.stdout
