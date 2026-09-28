"""Trace-replay conformance: run the real-code adapter over ``traces.jsonl``
and compare its observed output to the model's expectations, or (with
``--against``) diff two code revisions against each other on the same traces."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from . import paths
from .util import CliError, is_environment_failure, run, run_shell


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a traces/observed JSONL file, validating each line's shape so malformed adapter
    output becomes an ordinary ``CliError`` (code 1) here -- caught by ``,formal audit``'s stage
    guard as a persisted ``fail`` rather than aborting the audit. Duplicate trace IDs are invalid:
    each input trace has exactly one output record, with no last-record-wins retry semantics. An
    entry carrying a truthy ``error`` is exempt from the ``steps`` requirement; a falsy/absent
    ``error`` still requires ``steps`` (matching ``compare_trace``). Split on a literal ``\\n``
    only, never ``str.splitlines()``: the latter also breaks on U+2028/U+2029, which are valid raw
    bytes inside a JSON string on an otherwise single JSONL line."""
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise CliError(f"Malformed JSONL in {path}: invalid UTF-8 ({exc}).", code=1) from exc
    entries = []
    trace_lines: dict[str, int] = {}
    for lineno, raw_line in enumerate(text.split("\n"), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CliError(f"Malformed line {lineno} in {path}: invalid JSON ({exc}).", code=1) from exc
        if not isinstance(entry, dict):
            raise CliError(
                f"Malformed line {lineno} in {path}: expected a JSON object, got {type(entry).__name__}.", code=1
            )
        trace_id = entry.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            raise CliError(f"Malformed line {lineno} in {path}: missing or invalid 'trace_id'.", code=1)
        if trace_id in trace_lines:
            raise CliError(
                f"Malformed line {lineno} in {path}: duplicate 'trace_id' {trace_id!r} "
                f"(first seen on line {trace_lines[trace_id]}).",
                code=1,
            )
        trace_lines[trace_id] = lineno
        if not entry.get("error"):
            steps = entry.get("steps")
            if steps is None:
                raise CliError(f"Malformed line {lineno} in {path}: missing 'steps'.", code=1)
            if not isinstance(steps, list):
                raise CliError(f"Malformed line {lineno} in {path}: 'steps' must be a list.", code=1)
            for step_index, step in enumerate(steps):
                if not isinstance(step, dict):
                    raise CliError(
                        f"Malformed line {lineno} in {path} (trace {trace_id!r}, step {step_index}): "
                        f"expected a JSON object, got {type(step).__name__}.",
                        code=1,
                    )
                if "observed" in step:
                    observed = step["observed"]
                    if not isinstance(observed, dict):
                        raise CliError(
                            f"Malformed line {lineno} in {path} (trace {trace_id!r}, step {step_index}): "
                            f"'observed' must be an object, got {type(observed).__name__}.",
                            code=1,
                        )
        entries.append(entry)
    return entries


def resolve_adapter(manifest: dict[str, Any], adapter_flag: str | None) -> tuple[str, str]:
    if adapter_flag:
        return adapter_flag, "repo"
    adapter = manifest.get("adapter") or {}
    cmd = adapter.get("cmd")
    if not cmd:
        raise CliError("No adapter configured. Pass --adapter '<cmd>' or set MANIFEST.adapter.cmd.", code=2)
    return cmd, adapter.get("cwd", "repo")


def _adapter_cwd(cwd_kind: str, repo_root: Path, unit_dir: Path) -> Path:
    return unit_dir if cwd_kind == "unit" else repo_root


def run_adapter(
    cmd: str, cwd: Path, traces_path: Path, out_path: Path, unit_dir: Path, repo_root: Path, timeout: float | None
) -> None:
    """``FORMAL_REPO_ROOT`` is always set: the repo root on the HEAD side, the
    exported ``REF`` tree on the differential ``--against`` side. It is the
    only reliable "repo root" an adapter run against an exported ``REF`` can
    see, since that export is not part of the real repo's working tree."""
    env = {
        **os.environ,
        "FORMAL_TRACES": str(traces_path),
        "FORMAL_OUT": str(out_path),
        "FORMAL_UNIT_DIR": str(unit_dir),
        "FORMAL_REPO_ROOT": str(repo_root),
    }
    result = run_shell(cmd, cwd=cwd, timeout=timeout, env=env)
    if result.returncode != 0 and not out_path.exists():
        raise CliError(
            f"Adapter command failed ({result.returncode}):\n{result.stdout}\n{result.stderr}",
            code=1,
            environment_error=is_environment_failure(result),
        )


def _require_traces(unit_dir: Path) -> tuple[Path, list[dict[str, Any]]]:
    traces_path = unit_dir / "traces" / "traces.jsonl"
    trace_list = load_jsonl(traces_path)
    if not trace_list:
        raise CliError(f"No traces found at {traces_path}. Run `,formal traces <unit>` first.", code=2)
    return traces_path, trace_list


def _json_equal(expected: Any, observed: Any) -> bool:
    """Recursive equality for JSON-typed values, applied at every level of the recursion (not only
    the top). ``bool`` stays type-strict: Python's ``==`` conflates ``bool`` with ``int`` (``True ==
    1``, ``False == 0``), so a plain ``!=`` would call an observed ``1`` a match for an expected
    ``True`` (or ``[1, 0]`` a match for ``[True, False]``, since the conflation also survives inside
    a list/dict) -- either side being a ``bool`` requires both sides to be ``bool`` and equal-valued.
    Non-``bool`` ``int``/``float`` compare numerically instead (``1 == 1.0`` is a match): Lean's
    ``toJson (1.0 : Float)`` prints the integer literal ``1``, while a Python adapter's
    ``json.dumps`` prints ``1.0`` for the same value, so a strict type check would misreport that
    value contract as a divergence. Every other type stays type-strict, recursing into matching
    dict/list structures."""
    expected_is_bool = isinstance(expected, bool)
    observed_is_bool = isinstance(observed, bool)
    if expected_is_bool or observed_is_bool:
        return expected_is_bool and observed_is_bool and expected == observed
    if isinstance(expected, (int, float)) and isinstance(observed, (int, float)):
        return expected == observed
    if type(expected) is not type(observed):
        return False
    if isinstance(expected, dict):
        return expected.keys() == observed.keys() and all(_json_equal(expected[key], observed[key]) for key in expected)
    if isinstance(expected, list):
        return len(expected) == len(observed) and all(_json_equal(e, o) for e, o in zip(expected, observed))
    return expected == observed


def compare_field_by_field(expect: dict[str, Any], observed: dict[str, Any]) -> str | None:
    """Only keys present in ``expect`` are compared (contract §5)."""
    for key, expected_value in expect.items():
        if key not in observed:
            return f"missing observed field {key!r}"
        if not _json_equal(expected_value, observed[key]):
            return f"field {key!r} expected {expected_value!r}, observed {observed[key]!r}"
    return None


def compare_trace(trace: dict[str, Any], observed_entry: dict[str, Any] | None) -> dict[str, Any]:
    trace_id = trace["trace_id"]
    if observed_entry is None:
        return {"trace_id": trace_id, "status": "missing"}
    if observed_entry.get("error"):
        return {"trace_id": trace_id, "status": "error", "detail": observed_entry["error"]}
    # The adapter's observed shape is `{"trace_id","steps":[{"observed":obs}]}` (contract §5) --
    # no separate init_obs entry; the first step's expect/observed already captures the
    # post-first-event state, so only steps are compared.
    steps = trace.get("steps", [])
    observed_steps = observed_entry.get("steps", [])
    for index, step in enumerate(steps):
        if index >= len(observed_steps):
            return {
                "trace_id": trace_id,
                "status": "mismatch",
                "detail": f"missing observed step {index}",
                "step": index,
            }
        divergence = compare_field_by_field(step.get("expect", {}), observed_steps[index].get("observed", {}))
        if divergence:
            return {"trace_id": trace_id, "status": "mismatch", "detail": divergence, "step": index}
    return {"trace_id": trace_id, "status": "pass"}


def run_replay(
    unit_dir: Path,
    workspace: Path,
    manifest: dict[str, Any],
    adapter_flag: str | None,
    timeout: float | None = None,
) -> dict[str, Any]:
    traces_path, trace_list = _require_traces(unit_dir)
    cmd, cwd_kind = resolve_adapter(manifest, adapter_flag)
    out_path = unit_dir / "traces" / "observed.jsonl"
    out_path.unlink(missing_ok=True)
    run_adapter(cmd, _adapter_cwd(cwd_kind, workspace, unit_dir), traces_path, out_path, unit_dir, workspace, timeout)
    observed_by_id = {entry["trace_id"]: entry for entry in load_jsonl(out_path)}
    # A trace with zero steps has nothing to compare (only its presence in the adapter's output
    # would matter, which this compares elsewhere); it is not counted toward total/passed.
    results = [
        compare_trace(trace, observed_by_id.get(trace["trace_id"])) for trace in trace_list if trace.get("steps")
    ]
    passed = sum(1 for r in results if r["status"] == "pass")
    receipt = {
        "kind": "replay",
        "mode": "conformance",
        # Zero traces compared is a fail, never a vacuous pass (`passed == len(results)` would
        # otherwise read 0 == 0 as ok): there is nothing here that conformance was actually
        # checked against.
        "ok": len(results) > 0 and passed == len(results),
        "total": len(results),
        "passed": passed,
        "results": results,
    }
    if not results:
        receipt["note"] = "no traces compared"
    return receipt


def _compare_differential(
    trace_id: str,
    expected_step_count: int,
    head_entry: dict[str, Any] | None,
    ref_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    if head_entry is None or ref_entry is None:
        return {"trace_id": trace_id, "status": "missing"}
    if head_entry.get("error") or ref_entry.get("error"):
        return {"trace_id": trace_id, "status": "error", "detail": head_entry.get("error") or ref_entry.get("error")}
    head_steps = head_entry.get("steps", [])
    ref_steps = ref_entry.get("steps", [])
    if len(head_steps) != expected_step_count or len(ref_steps) != expected_step_count:
        return {
            "trace_id": trace_id,
            "status": "mismatch",
            "detail": (
                f"step count differs from input: expected {expected_step_count}, "
                f"head={len(head_steps)}, ref={len(ref_steps)}"
            ),
            "step": -1,
        }
    for index, (head_step, ref_step) in enumerate(zip(head_steps, ref_steps)):
        head_observed = head_step.get("observed", {})
        ref_observed = ref_step.get("observed", {})
        for key in sorted(set(head_observed) | set(ref_observed)):
            if key not in head_observed or key not in ref_observed:
                head_value = head_observed[key] if key in head_observed else "<missing>"
                ref_value = ref_observed[key] if key in ref_observed else "<missing>"
                return {
                    "trace_id": trace_id,
                    "status": "mismatch",
                    "step": index,
                    "detail": f"field {key!r}: head={head_value!r} ref={ref_value!r}",
                }
            if not _json_equal(head_observed[key], ref_observed[key]):
                return {
                    "trace_id": trace_id,
                    "status": "mismatch",
                    "step": index,
                    "detail": f"field {key!r}: head={head_observed[key]!r} ref={ref_observed[key]!r}",
                }
    return {"trace_id": trace_id, "status": "pass"}


def _export_ref(layout: paths.Layout, workspace: Path, ref: str, timeout: float | None) -> Path:
    """Materialize ``ref`` into a plain directory under the state root: no ``git worktree`` (no
    worktree-list side effects, no cleanup ordering with the real working tree) and no ``git
    archive`` (``git archive`` honors ``ref``'s ``.gitattributes`` -- ``export-ignore`` silently
    drops attributed paths from the export, e.g. a ``tests/`` directory the adapter imports, and
    ``export-subst`` rewrites ``$Format:...$`` placeholders -- so either would diverge the
    ``--against`` side from a plain checkout of ``ref`` for reasons unrelated to the code change
    under test).

    Instead this points ``GIT_INDEX_FILE`` at a fresh temp file under the state root (never
    ``workspace/.git/index`` -- no writes to the real repo's index), runs ``git read-tree <ref>``
    into that throwaway index, then ``git checkout-index -a --prefix=<dir>/`` writes the plain
    working files from it. ``git rev-parse --verify`` names an unresolvable ``ref`` up front with
    a clear "unknown ref" message; the read-tree and checkout-index steps are each checked
    separately (fail-closed) -- either failing removes the partial export directory and raises a
    ``CliError``, rather than leaving or reporting success for an incomplete export."""
    verify = run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{tree}}"], cwd=workspace, timeout=timeout)
    if verify.returncode != 0:
        raise CliError(f"Failed to export {ref}: unknown ref (git rev-parse could not resolve it).", code=2)
    export_dir = layout.exports_dir() / f"replay-{uuid.uuid4().hex[:12]}"
    export_dir.mkdir(parents=True, exist_ok=True)
    index_fd, index_name = tempfile.mkstemp(dir=str(layout.exports_dir()), prefix=".replay-index-", suffix=".tmp")
    os.close(index_fd)
    index_path = Path(index_name)
    index_env = {**os.environ, "GIT_INDEX_FILE": str(index_path)}
    try:
        read_tree = run(["git", "read-tree", ref], cwd=workspace, timeout=timeout, env=index_env)
        if read_tree.returncode != 0:
            raise CliError(
                f"Failed to export {ref}: `git read-tree` failed (exit {read_tree.returncode}):\n{read_tree.stderr}",
                code=2,
            )
        checkout = run(
            ["git", "checkout-index", "-a", f"--prefix={export_dir}/"], cwd=workspace, timeout=timeout, env=index_env
        )
        if checkout.returncode != 0:
            raise CliError(
                f"Failed to export {ref}: `git checkout-index` failed (exit {checkout.returncode}):\n{checkout.stderr}",
                code=2,
            )
    except CliError:
        shutil.rmtree(export_dir, ignore_errors=True)
        raise
    finally:
        index_path.unlink(missing_ok=True)
    return export_dir


def run_replay_differential(
    layout: paths.Layout,
    unit_dir: Path,
    workspace: Path,
    manifest: dict[str, Any],
    adapter_flag: str | None,
    ref: str,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Differential mode: old code (an exported checkout of ``ref``) is the
    oracle for new code (``HEAD``); model expectations are ignored."""
    traces_path, trace_list = _require_traces(unit_dir)
    cmd, cwd_kind = resolve_adapter(manifest, adapter_flag)
    export_dir = _export_ref(layout, workspace, ref, timeout)
    try:
        head_out = unit_dir / "traces" / "observed-head.jsonl"
        ref_out = unit_dir / "traces" / "observed-ref.jsonl"
        head_out.unlink(missing_ok=True)
        ref_out.unlink(missing_ok=True)
        head_cwd = _adapter_cwd(cwd_kind, workspace, unit_dir)
        ref_cwd = _adapter_cwd(cwd_kind, export_dir, unit_dir)
        run_adapter(cmd, head_cwd, traces_path, head_out, unit_dir, workspace, timeout)
        run_adapter(cmd, ref_cwd, traces_path, ref_out, unit_dir, export_dir, timeout)
    finally:
        shutil.rmtree(export_dir, ignore_errors=True)
    head_by_id = {entry["trace_id"]: entry for entry in load_jsonl(head_out)}
    ref_by_id = {entry["trace_id"]: entry for entry in load_jsonl(ref_out)}
    results = [
        _compare_differential(
            trace["trace_id"],
            len(trace["steps"]),
            head_by_id.get(trace["trace_id"]),
            ref_by_id.get(trace["trace_id"]),
        )
        for trace in trace_list
        if trace.get("steps")
    ]
    passed = sum(1 for r in results if r["status"] == "pass")
    receipt = {
        "kind": "replay",
        "mode": "differential",
        "against": ref,
        # Mirrors the normal-replay guard: zero traces compared must never read as a vacuous
        # pass (`passed == len(results)` would otherwise read 0 == 0 as ok).
        "ok": len(results) > 0 and passed == len(results),
        "total": len(results),
        "passed": passed,
        "results": results,
    }
    if not results:
        receipt["note"] = "no traces compared"
    return receipt
