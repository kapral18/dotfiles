"""Aggregate gate: run (or reuse) each tier's stage receipts for one snapshot and produce the
``audit.json`` verdict + ``certifies`` wording.

Stage status values (``stages[<name>]["status"]``): ``pass``, ``fail``, ``unverified`` (no
replay adapter), ``n/a`` (design unit's skipped replay), and ``error`` -- an *environment*
failure (missing/timed-out tool, spawn failure) rather than a genuine check result. ``not-run``
is not one of these: a stage a ``--require`` set excludes is never attempted and is simply
absent from ``stages`` entirely; only the ``certifies`` conformance wording reports "not-run"
text when ``replay`` is the excluded stage. An ``error`` stage's receipt is never persisted to
disk (so it can never be reused as a stale cached result once the environment is fixed), and its
presence makes ``,formal audit`` exit 2, matching a usage/environment error rather than an
ordinary check failure.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from . import anchors as anchors_mod
from . import build as build_mod
from . import exe as exe_mod
from . import manifest as manifest_mod
from . import prove as prove_mod
from . import replay as replay_mod
from .util import CliError, read_json, write_json

F2_STAGES = ("anchors", "build", "explore", "mutate", "replay")
F3_EXTRA_STAGES = ("prove",)


def required_stages(tier: str, require_arg: str | None) -> list[str]:
    if require_arg is not None:
        stages = [stage.strip() for stage in require_arg.split(",") if stage.strip()]
        if not stages:
            raise CliError("`--require` needs at least one stage name.", code=2)
        if "prove" in stages and ("build" not in stages or stages.index("build") > stages.index("prove")):
            # Preserve an explicitly early build: moving it past replay/explore would bypass
            # their failure prerequisite. Only insert or move a missing/late proof dependency.
            stages = [stage for stage in stages if stage != "build"]
            stages.insert(stages.index("prove"), "build")
        return stages
    stages = list(F2_STAGES)
    if tier == "F3":
        stages += list(F3_EXTRA_STAGES)
    return stages


def receipt_dir(unit_dir: Path, snapshot: str) -> Path:
    return unit_dir / "receipts" / snapshot


def stage_receipt_path(unit_dir: Path, snapshot: str, stage: str) -> Path:
    return receipt_dir(unit_dir, snapshot) / f"{stage}.json"


def _load_or_none(path: Path) -> dict[str, Any] | None:
    return read_json(path) if path.exists() else None


def run_stage_anchors(unit_dir: Path, workspace: Path, design: bool) -> dict[str, Any]:
    anchors = manifest_mod.load_anchors(unit_dir)
    if not anchors and not design:
        return {"kind": "anchors", "ok": False, "anchors": [], "error": "no anchors"}
    checks = [anchors_mod.check_anchor(workspace, anchor) for anchor in anchors]
    return {"kind": "anchors", "ok": all(c["status"] == "unchanged" for c in checks), "anchors": checks}


def run_stage_build(unit_dir: Path, proofs: bool, timeout: float | None) -> dict[str, Any]:
    receipt = build_mod.lake_build(unit_dir, proofs=proofs, timeout=timeout)
    # Record whether *this* build compiled `Unit.Proofs` so a later run that needs proofs can
    # tell a cached receipt made without them apart from a fresh one -- see the cache-miss check
    # in `run_audit`'s `build` stage dispatch below.
    receipt["proofs"] = proofs
    return receipt


def run_stage_explore(unit_dir: Path, manifest: dict[str, Any], timeout: float | None) -> dict[str, Any]:
    budgets = manifest.get("budgets") or {}
    receipt = exe_mod.explore(unit_dir, budgets.get("max_states"), budgets.get("max_depth"), timeout=timeout)
    props = receipt.get("props", [])
    if exe_mod.explore_vacuous(props):
        # A unit with zero properties passes vacuously -- explore never actually checked
        # anything. This is not the same failure as a violated property, so it is reported
        # distinctly rather than folded into a generic `ok: False`. The standalone `,formal
        # explore` command applies the identical `exe_mod.explore_vacuous` condition.
        receipt["ok"] = False
        receipt["error"] = "no properties"
        return receipt
    receipt["ok"] = all(exe_mod.prop_ok(p) for p in props)
    return receipt


def run_stage_mutate(unit_dir: Path, manifest: dict[str, Any], timeout: float | None) -> dict[str, Any]:
    budgets = manifest.get("budgets") or {}
    receipt = exe_mod.mutate(unit_dir, budgets.get("max_states"), budgets.get("max_depth"), timeout=timeout)
    mutants = receipt.get("mutants", [])
    if not mutants:
        # Zero mutants "kills" nothing -- a vacuous "every mutant killed" pass proves no
        # property is adequate at all (SOP §3.6: mutants must each be killed by a named
        # property; there is nothing to name here).
        receipt["ok"] = False
        receipt["error"] = "no mutants"
        return receipt
    vacuous = exe_mod.mutate_vacuous_names(mutants)
    if vacuous:
        # A mutant with no declared expected killer documents nothing: `wrong-killer`
        # reclassification and the audit cross-check both depend on `expected` naming the
        # property the mutant is *supposed* to be caught by, even when it currently survives.
        # The standalone `,formal mutate` command applies the identical
        # `exe_mod.mutate_vacuous_names` condition.
        receipt["ok"] = False
        receipt["error"] = f"vacuous: mutant(s) with no declared expected killer: {', '.join(vacuous)}"
        return receipt
    control_ok = bool(receipt.get("control", {}).get("ok"))
    not_killed = [m for m in mutants if m.get("status") in ("survived", "wrong-killer")]
    receipt["ok"] = control_ok and not not_killed
    return receipt


def run_stage_replay(
    unit_dir: Path, workspace: Path, manifest: dict[str, Any], timeout: float | None
) -> dict[str, Any]:
    """Always returns a receipt (never ``None``): the no-adapter case is recorded as
    ``unverified: True`` so a cached reload of this exact receipt classifies the same way as a
    fresh run (see ``run_audit``'s ``replay`` dispatch)."""
    adapter = manifest.get("adapter") or {}
    if not adapter.get("cmd"):
        return {"kind": "replay", "ok": False, "unverified": True, "note": "no adapter configured"}
    budgets = manifest.get("budgets") or {}
    max_traces = budgets.get("max_traces", 500)
    output = exe_mod.traces(
        unit_dir,
        "cover",
        max_traces,
        timeout=timeout,
        max_states=budgets.get("max_states"),
        max_depth=budgets.get("max_depth"),
    )
    traces_path = unit_dir / "traces" / "traces.jsonl"
    traces_path.parent.mkdir(parents=True, exist_ok=True)
    traces_path.write_text(output, encoding="utf-8")
    return replay_mod.run_replay(unit_dir, workspace, manifest, None, timeout=timeout)


def run_stage_prove(unit_dir: Path, build_receipt: dict[str, Any], timeout: float | None) -> dict[str, Any]:
    return prove_mod.run_prove(unit_dir, build_receipt, timeout=timeout)


def _explore_summary(receipt: dict[str, Any] | None) -> str:
    if not receipt:
        return "n/a"
    props = receipt.get("props", [])
    holds = sum(1 for p in props if p.get("expect") == "holds" and p.get("status") == "holds")
    refuted = sum(1 for p in props if p.get("expect") == "refuted" and p.get("status") == "violated")
    suffix = " within budget" if receipt.get("bounded") else ""
    return f"{holds} props hold{suffix}, {refuted} refuted as expected"


def _mutate_summary(receipt: dict[str, Any] | None) -> str:
    if not receipt:
        return "mutants n/a"
    mutants = receipt.get("mutants", [])
    killed = sum(1 for m in mutants if m.get("status") == "killed")
    return f"mutants {killed}/{len(mutants)} killed"


def _conformance_summary(
    stage_status: str, receipt: dict[str, Any] | None, explore_receipt: dict[str, Any] | None, max_traces: int
) -> str:
    if stage_status == "n/a":
        return "conformance: n/a-design"
    if stage_status == "not-run":
        # `--require` excluded `replay` entirely -- distinct from a design unit's skip (that
        # is a real, permanent `n/a`), and distinct from an adapter-less `unverified` run.
        return "conformance: not-run"
    if stage_status == "unverified" or not receipt:
        return "conformance: unverified"
    passed, total = receipt.get("passed", 0), receipt.get("total", 0)
    if total == 0:
        # Zero traces compared is neither a capped cover nor a complete one -- there is nothing
        # to describe as covered.
        return f"conformance: {passed}/{total} traces compared"
    explore_succeeded = bool(
        explore_receipt
        and explore_receipt.get("kind") == "explore"
        and explore_receipt.get("ok") is True
        and isinstance(explore_receipt.get("states"), int)
        and not isinstance(explore_receipt.get("states"), bool)
        and explore_receipt["states"] >= 0
        and isinstance(explore_receipt.get("bounded"), bool)
    )
    if not explore_succeeded:
        # A skipped, failed, or malformed exploration receipt does not establish how many states
        # are reachable, even when a replay receipt for the same snapshot is successful.
        return f"conformance: {passed}/{total} traces compared (cover unknown, explore did not complete successfully)"
    reachable = explore_receipt["states"]
    if reachable > max_traces:
        return f"conformance: {passed}/{total} traces compared (cover capped at {max_traces}; {reachable} reachable states)"
    if explore_receipt["bounded"]:
        # `explore` itself hit a budget: `states` is only what was reached within that budget,
        # never the true total reachable count, so a full cover of *that* is not a complete
        # cover of the unit's real state space -- never print "(complete cover)" here.
        return (
            f"conformance: {passed}/{total} traces compared (explore was budget-bounded, cover not guaranteed complete)"
        )
    return f"conformance: {passed}/{total} traces compared (complete cover)"


def _prove_summary(stage_status: str, receipt: dict[str, Any] | None) -> str:
    if stage_status == "n/a" or not receipt:
        return "proofs: n/a"
    axioms = receipt.get("axioms")
    if axioms is None:
        # `run_prove` short-circuited before ever running the axiom check -- a forbidden-token
        # hit, a build failure, or an unparsable `formalcheck` result all leave `axioms: None`
        # on the receipt with no theorem counted. `axioms or {}` used to fold this into an empty
        # `disallowed_axioms` list and print "axioms clean", falsely claiming a check that never
        # ran; report the reason instead (never a theorem/constant count that was never computed).
        reason = receipt.get("error") or receipt.get("message")
        if not reason and receipt.get("forbidden_tokens"):
            # Each hit is a `{"file", "line", "token"}` dict (`prove.scan_forbidden_tokens`),
            # never a bare token string -- `", ".join(...)` on the dicts themselves raises
            # `TypeError` and audit.json is never written; format each hit explicitly instead.
            reason = "forbidden token(s): " + ", ".join(
                f"{hit['token']}@{hit['file']}:{hit['line']}" for hit in receipt["forbidden_tokens"]
            )
        if not reason and not receipt.get("build_ok", True):
            reason = "build failed"
        return f"proofs: axioms not checked ({reason})" if reason else "proofs: axioms not checked"
    checked_count = receipt.get("theorem_count", 0)
    user_written_count = receipt.get("user_written_count", 0)
    disallowed = axioms.get("disallowed_axioms") or []
    prefix = f"proofs: {user_written_count} theorems ({checked_count} constants axiom-checked)"
    if disallowed:
        # `axioms["disallowed_axioms"]` (`check_prove_theorems`) is derived only from the
        # `theorems` array `formalcheck` returns for `Unit.Proofs`'s own theorem-kind constants.
        # `formalcheck`'s `violationsFor` (`Check.lean`) also records a `disallowed_axiom`
        # `scope_violations` entry for every constant it walks, including `Unit.Proofs`'s own
        # theorems -- so a `Unit.Proofs` theorem that uses a disallowed axiom (e.g. `decide
        # +native`) makes both `disallowed` and `scope_violations` non-empty at the same time.
        # Report the axiom names here first, before the scope-violation branch below ever gets a
        # chance to swallow them behind a generic "scope violation(s)" line.
        return f"{prefix}, axioms dirty: " + ", ".join(disallowed)
    scope_violations = receipt.get("scope_violations") or []
    if scope_violations:
        # Reached only when `Unit.Proofs`'s own theorems' axioms are clean (`disallowed` empty
        # above): some other constant across the unit's whole module scope still failed a semantic
        # check (`axiom_declaration`, `unsafe`, `extern`, `implemented_by`, or a `disallowed_axiom`
        # on any constant other than `Unit.Proofs`'s own theorems -- e.g. a `Model.lean` def, or a
        # non-theorem `Unit.Proofs` def/instance, built with `decide +native`) --
        # `Unit.Proofs`'s own axioms being clean never means "axioms clean" here.
        names = ", ".join(f"{v['name']} ({v['kind']})" for v in scope_violations[:5])
        return f"{prefix}, scope violation(s): {names}"
    kernel_check = receipt.get("kernel_check")
    if kernel_check is not None and not kernel_check.get("ok"):
        # `kernel_check` only runs after `Unit.Proofs`'s own axioms and every scope violation
        # already passed (`run_prove`'s independent `leanchecker` re-check) -- a failure here is
        # a real kernel rejection of the built modules, never something "axioms clean" describes.
        message = kernel_check.get("message") or "kernel re-check failed"
        return f"{prefix}, kernel re-check failed: {message}"
    return f"{prefix}, axioms clean"


def run_audit(
    unit_dir: Path,
    workspace: Path,
    manifest: dict[str, Any],
    snapshot: str,
    require_arg: str | None,
    allow_unverified_conformance: bool,
    timeout: float | None,
) -> dict[str, Any]:
    # "Missing lake is detected before stages and exits 2": checked once, before any stage
    # runs or any receipt directory is created, so a missing toolchain never gets a chance to
    # write (and later have reused) a misleading cached "fail" receipt.
    if shutil.which("lake") is None:
        raise CliError(
            "`lake` is not on PATH; install the pinned Lean toolchain (see `,formal doctor --install`).",
            code=2,
        )

    tier = manifest.get("tier", "F2")
    design = bool(manifest.get("design"))
    stages_needed = required_stages(tier, require_arg)
    receipt_dir(unit_dir, snapshot).mkdir(parents=True, exist_ok=True)
    stages_out: dict[str, Any] = {}
    build_receipt: dict[str, Any] | None = None

    def record(name: str, status: str, receipt_payload: dict[str, Any] | None, persist: bool = True) -> None:
        path = stage_receipt_path(unit_dir, snapshot, name)
        write = persist and receipt_payload is not None
        if write:
            write_json(path, receipt_payload)
        stages_out[name] = {"status": status, "receipt": str(path) if write else None}

    def build_failed() -> bool:
        return build_receipt is not None and not build_receipt.get("ok")

    def build_environment_error() -> bool:
        return bool(build_receipt and build_receipt.get("environment_error"))

    def skip_for_build_failure(kind: str) -> None:
        # Never call into `lake exe` (explore/mutate/replay's trace generation, or prove's own
        # `lake build`) once the build is already known broken: `lake exe` auto-builds and its
        # non-zero exit raises a usage-error `CliError(code=2)`, which would otherwise abort
        # `run_audit` before every later stage is recorded and before `audit.json` is written --
        # turning a model build failure (verdict `fail`, exit 1) into a usage-error exit 2. When
        # the build itself failed for an *environment* reason, the cascaded skip note is equally
        # environment-tainted and must not be persisted either -- fixing the environment and
        # re-running must not find a stale cached "fail: skipped: build failed".
        record(
            kind,
            "fail",
            {"kind": kind, "ok": False, "note": "skipped: build failed"},
            persist=not build_environment_error(),
        )

    def run_stage_guarded(name: str, compute: Any, cached: dict[str, Any] | None) -> None:
        """Run one stage's producer, classify its outcome, and record it -- catching a raised
        ``CliError`` (adapter crash, `lake exe` failure, a lean-invocation timeout) instead of
        letting it abort the whole audit before ``audit.json`` is written and before later
        stages (e.g. F3's ``prove``) get a chance to run. An ``environment_error`` (missing
        tool, timeout, spawn failure) becomes stage status ``error`` and is never persisted;
        anything else is an ordinary ``fail``."""
        nonlocal build_receipt
        try:
            receipt = cached if cached is not None else compute()
        except CliError as exc:
            status = "error" if exc.environment_error else "fail"
            failure_receipt = {
                "kind": name,
                "ok": False,
                "environment_error": exc.environment_error,
                "message": exc.message,
            }
            record(name, status, failure_receipt, persist=not exc.environment_error)
            if name == "build":
                # A raised build failure must still gate later required stages exactly like an
                # ordinary (non-raising) build failure -- `build_failed()` reads `build_receipt`.
                build_receipt = failure_receipt
            return
        if (
            name == "build"
            and not receipt.get("ok")
            and not receipt.get("environment_error")
            and receipt.get("empty_output")
        ):
            # `build.py`'s own `has_environment_signature` check already catches an elan/Lake
            # environment-provisioning failure (unresolvable toolchain pin, offline download, a
            # missing/non-executable toolchain binary) at the source, setting `environment_error`
            # directly on the receipt -- this reclassification only ever sees a *different*,
            # narrower case: a nonzero `lake build` exit that produced literally no stdout/stderr
            # text at all (`build.py`'s `empty_output` flag). No text at all can never have
            # produced a genuine parsed diagnostic, so this is never a real check result to cache;
            # every real compile failure captured so far (bad import, module-imports-itself, a
            # non-UTF-8 source file, a crashed Lean subprocess -- see
            # `TestAuditRealBuildFailuresAreNeverEnvironmentErrors` in `test_formal_audit.py`)
            # prints at least one recognized `error:`/job-failure line and is not reclassified
            # here.
            receipt = dict(receipt)
            receipt["environment_error"] = True
            receipt["message"] = receipt.get("message") or (
                "`lake build` exited nonzero with no output at all -- the pinned Lean toolchain "
                "may be missing or unreachable (see `,formal doctor --install`)."
            )
        if name == "build":
            build_receipt = receipt
        if receipt.get("environment_error"):
            record(name, "error", receipt, persist=False)
        elif name == "replay" and receipt.get("unverified"):
            record(name, "unverified", receipt)
        else:
            record(name, "pass" if receipt.get("ok") else "fail", receipt)

    for stage in stages_needed:
        cached = _load_or_none(stage_receipt_path(unit_dir, snapshot, stage))
        if stage == "anchors":
            receipt = cached or run_stage_anchors(unit_dir, workspace, design)
            record(stage, "pass" if receipt.get("ok") else "fail", receipt)
        elif stage == "build":
            proofs_needed = tier == "F3" or "prove" in stages_needed
            if cached is not None and proofs_needed and not cached.get("proofs"):
                # A cached receipt from an earlier run that never compiled `Unit.Proofs` cannot
                # satisfy a run that needs proofs (F3, or `prove` in this `--require` set): reused
                # as-is it would let `prove` axiom-check against a build that never actually
                # recompiled (or even validated) `Unit.Proofs.lean`. Treat it as a cache miss so
                # `run_stage_build` recomputes with `proofs=True` below.
                cached = None
            run_stage_guarded(
                stage,
                lambda: run_stage_build(unit_dir, proofs=proofs_needed, timeout=timeout),
                cached,
            )
        elif stage == "explore":
            if build_failed():
                skip_for_build_failure(stage)
                continue
            run_stage_guarded(stage, lambda: run_stage_explore(unit_dir, manifest, timeout=timeout), cached)
        elif stage == "mutate":
            if build_failed():
                skip_for_build_failure(stage)
                continue
            run_stage_guarded(stage, lambda: run_stage_mutate(unit_dir, manifest, timeout=timeout), cached)
        elif stage == "replay":
            if design:
                record(stage, "n/a", {"kind": "replay", "ok": True, "note": "design unit"})
                continue
            if build_failed():
                skip_for_build_failure(stage)
                continue
            run_stage_guarded(stage, lambda: run_stage_replay(unit_dir, workspace, manifest, timeout=timeout), cached)
        elif stage == "prove":
            if build_failed():
                skip_for_build_failure(stage)
                continue
            if build_receipt is None:
                # `required_stages` now always puts `build` ahead of `prove` in the same
                # `--require` set, so this should never actually trigger -- it exists so a future
                # caller can never compute (and cache) a prove receipt against a synthesized `{}`
                # build receipt, which would misreport `build_ok: False` for a build that simply
                # never ran.
                raise CliError("`prove` requires `build` to have run in the same `--require` set.", code=2)
            run_stage_guarded(stage, lambda: run_stage_prove(unit_dir, build_receipt, timeout=timeout), cached)
        else:
            raise CliError(f"Unknown audit stage: {stage}", code=2)

    ok = True
    has_error = False
    for info in stages_out.values():
        status = info["status"]
        if status == "error":
            has_error = True
        if status in ("pass", "n/a"):
            continue
        if status == "unverified" and allow_unverified_conformance:
            continue
        ok = False

    explore_receipt = _load_or_none(stage_receipt_path(unit_dir, snapshot, "explore"))
    mutate_receipt = _load_or_none(stage_receipt_path(unit_dir, snapshot, "mutate"))
    replay_receipt = _load_or_none(stage_receipt_path(unit_dir, snapshot, "replay"))
    prove_receipt = _load_or_none(stage_receipt_path(unit_dir, snapshot, "prove"))
    replay_status = stages_out.get("replay", {}).get("status", "not-run")
    prove_status = stages_out.get("prove", {}).get("status", "n/a")
    max_traces = (manifest.get("budgets") or {}).get("max_traces", 500)

    certifies = "; ".join(
        [
            f"model: {_explore_summary(explore_receipt)}",
            _mutate_summary(mutate_receipt),
            _conformance_summary(replay_status, replay_receipt, explore_receipt, max_traces),
            _prove_summary(prove_status, prove_receipt),
        ]
    )

    audit_receipt = {
        "unit": manifest.get("unit"),
        "snapshot": snapshot,
        "tier": tier,
        "stages": stages_out,
        "verdict": "pass" if ok else "fail",
        "has_error": has_error,
        "certifies": certifies,
    }
    write_json(unit_dir / "receipts" / snapshot / "audit.json", audit_receipt)
    return audit_receipt
