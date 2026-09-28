"""``lake build`` wrapper with compact Lean diagnostic parsing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import prove as prove_mod
from .util import is_environment_failure, run

_DIAG_RE = re.compile(r"^(?P<file>[^\n:]+):(?P<line>\d+):(?P<col>\d+): (?P<severity>error|warning): (?P<message>.*)$")
# Lake 4.34.1's own wrapping puts the severity *first*, before the location (confirmed against a
# real `lake build` failure): `error: Unit/Step.lean:24:30: Unknown constant ...`. The plain
# Lean-diagnostic form above (`file:line:col: error: msg`) is kept too -- both are matched, tried
# in the order below, per line.
_DIAG_RE_LAKE = re.compile(
    r"^(?P<severity>error|warning): (?P<file>[^\n:]+):(?P<line>\d+):(?P<col>\d+): (?P<message>.*)$"
)
# Lake 4.34.1's own failure lines take many shapes that never carry a `file:line:col:` position at
# all (confirmed against real `lake build` failures -- bad import, module-imports-itself/build
# cycle, non-UTF-8 source, a Lean subprocess crash, the trailing job-summary/`build failed` lines):
# `error: Unit/Step.lean: bad import 'Unit.Nope'`, `error: Unit/Proofs.lean: module imports
# itself`, `error: Tried to read file '...' containing non UTF-8 data.`, `error: Lean exited with
# code 134`, `error: build failed`. Enumerating every one of these shapes by name is exactly what
# missed the crash case (no shape at all, just a job-failure marker and no further diagnostic
# text) -- every remaining `error: ...` line becomes its own positionless diagnostic instead, so a
# never-before-seen Lake failure message still surfaces as `error_count >= 1` rather than falling
# through to `audit.py`'s environment-failure reclassification.
_ERROR_LINE_RE = re.compile(r"^error: (?P<message>.*)$")
# A Lake job-failure marker (`✖ [n/m] <Verb> <target>`, optionally suffixed with a `(<duration>)`)
# names the target that failed to build/run but may be the *only* signal for that failure (a
# subprocess crash before it can print its own `error: ...` line, or when stdout is interleaved
# oddly) -- confirmed real shapes use both `Building <module>` (a source-compile job) and `Running
# <module>`/`Running unit:exe`/`Running job computation` (import-resolution and driver jobs).
_LAKE_JOB_FAILURE_RE = re.compile(r"^✖ \[\d+/\d+\] \S+ (?P<target>.+?)(?: \([^)]*\))?$")
# A `no such file or directory (error code: N)` diagnostic names the missing file only on the
# following indented `  file: <path>` continuation line (confirmed real S3.2 bad-import failure);
# generalized so it attaches to *any* still-positionless diagnostic's continuation, not only this
# one named shape.
_FILE_CONTINUATION_RE = re.compile(r"^\s*file: (?P<file>.+)$")
# elan/Lake environment/toolchain-provisioning signatures (probed against a real elan 4.2.4 +
# pinned Lean 4.34.1 install, /tmp/converge-fix-r5-U2/toolchain-missing/): an unresolvable
# `lean-toolchain` pin prints `error: no such release: '<tag>'` (elan-dist manifestation.rs); an
# offline/unreachable download prints `error: error during download` (elan-utils utils.rs /
# download/src/lib.rs, wrapping the underlying curl error as its `caused by:` line); a genuinely
# missing or non-executable toolchain binary raises the Lean runtime's own
# `could not execute external process '<cmd>' ...` (confirmed present verbatim in the installed
# Lean 4.34.1 runtime dylib). None of these is a Lean source diagnostic -- matching lines are
# never folded into (or counted as) a diagnostic; `lake_build` below turns their presence into the
# receipt's own `environment_error` flag instead.
_ENV_SIGNATURE_RE = re.compile(
    r"no such release: '|toolchain '[^']*' is not installed|error during download|"
    r"could not execute external process"
)
# A Lake job-status line for a job that did *not* fail -- `✔` (built/ran/replayed clean), `⚠` (a
# warning was logged for that job, on the diagnostic line that follows), `ℹ` (an already-cached
# rebuild, e.g. `-v` "ran but had nothing new to do") -- confirmed against real Lake 4.34.1 output
# (round 8, /tmp/converge-refute-r8-correctness/p1 and a scratch `lake build`/`lake build -v`
# probe): `✔ [3/10] Built Unit.Model:c.o (61ms)`, `⚠ [4/10] Built Unit.Step (231ms)`, `⚠ [2/6]
# Replayed Unit.Model`, `ℹ [2/2] Built Unit.Model (189ms)`, `✔ [0/2] Ran job computation`. Every one
# of these lines only ever names a target/verb -- never a diagnostic message of its own (the real
# `warning: ...`/`error: ...` text, if any, is a separate line already matched by
# `_DIAG_RE`/`_DIAG_RE_LAKE` above) -- so a status line always ends whatever diagnostic is
# currently open and must never be folded into its message: two `lake build` runs whose job
# counts/timings/verbs differ (a first full build vs. the proofs step's second, explicit `lake
# build <modules>` replay) would otherwise make the very same real diagnostic compare unequal on
# `message` and double-count in `_merge_diagnostics`. Deliberately excludes `✖` (job *failure*),
# which stays its own positionless diagnostic via `_LAKE_JOB_FAILURE_RE` below, unchanged.
_LAKE_STATUS_LINE_RE = re.compile(r"^[✔⚠ℹ] \[\d+/\d+\] .+$")
# Lake's own trailing per-invocation summary line and its non-diagnostic `info: ...` progress lines
# (manifest creation, toolchain-already-up-to-date) -- confirmed real shapes (round 8), never a
# Lean diagnostic; ends the current diagnostic like `_LAKE_STATUS_LINE_RE` above.
_LAKE_BUILD_SUMMARY_RE = re.compile(r"^Build completed successfully \(\d+ jobs?\)\.$")
_LAKE_INFO_LINE_RE = re.compile(r"^info: .*$")
# The trailing `Some required targets logged failures:` / `- <target>` block Lake prints after a
# failed build (confirmed real shape, round 8 scratch probe) -- the header line ends the current
# diagnostic, and every following `- <target>` bullet is consumed until a non-bullet line breaks
# the block.
_LAKE_FAILED_TARGETS_HEADER_RE = re.compile(r"^Some required targets logged failures:$")
_LAKE_FAILED_TARGET_ITEM_RE = re.compile(r"^- \S.*$")
MAX_MESSAGE_LINES = 25
MAX_REPORTED_ERRORS = 5


def _merge_diagnostics(base: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Appends ``extra`` onto ``base``, skipping an exact duplicate (same ``file``, ``line``,
    ``col``, ``severity``, and ``message``) already present -- the proofs step's own second,
    explicit ``lake build <modules>`` call replays every already-cached module's own diagnostics
    verbatim on top of what the first `lake build` already printed (confirmed against a real Lake
    4.34.1 build: a warning from a module both builds touch is printed twice, once per
    invocation), so concatenating the two diagnostic lists unconditionally double-counted it in
    `warning_count`/`error_count`. A diagnostic that only appears in `extra` (a module the first
    build never reached, or one whose text genuinely differs) is still appended, in first-seen
    order."""
    seen = {(d["file"], d["line"], d["col"], d["severity"], d["message"]) for d in base}
    merged = list(base)
    for diag in extra:
        key = (diag["file"], diag["line"], diag["col"], diag["severity"], diag["message"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(diag)
    return merged


def has_environment_signature(output: str) -> bool:
    """``True`` when ``output`` contains an elan/Lake environment-provisioning signature (see
    ``_ENV_SIGNATURE_RE``) rather than a genuine Lean source diagnostic."""
    return bool(_ENV_SIGNATURE_RE.search(output))


def is_environment_or_provisioning_failure(result: Any) -> bool:
    """Classify process-level failures and elan/toolchain provisioning failures uniformly."""
    if is_environment_failure(result):
        return True
    combined = result.stdout + "\n" + result.stderr
    return result.returncode != 0 and has_environment_signature(combined)


def parse_diagnostics(output: str) -> list[dict[str, Any]]:
    """Parse ``file:line:col: error|warning: message`` diagnostics (or Lake's own
    ``error|warning: file:line:col: message`` wrapping), every other ``error: ...`` line, and
    every Lake ``✖ [n/m] <verb> <target>`` job-failure marker line, as positionless ``error``
    diagnostics -- folding unindented continuation lines (goal state, notes, job-failure detail)
    into the message, capped at ``MAX_MESSAGE_LINES`` per diagnostic. A line matching an
    elan/toolchain/environment signature (``_ENV_SIGNATURE_RE``) is never turned into a
    diagnostic at all -- see ``has_environment_signature``. A Lake status line -- a non-failure
    job marker (``_LAKE_STATUS_LINE_RE``), the build summary (``_LAKE_BUILD_SUMMARY_RE``), a plain
    ``info: ...`` line (``_LAKE_INFO_LINE_RE``), or the trailing failed-targets block
    (``_LAKE_FAILED_TARGETS_HEADER_RE`` / ``_LAKE_FAILED_TARGET_ITEM_RE``) -- always ends whatever
    diagnostic is currently open instead of being folded into its message or starting a new one;
    these differ between separate ``lake build`` invocations (job counts, timings, replay vs.
    build) even when the real diagnostic they surround is identical."""
    diagnostics: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_failed_targets_block = False
    for line in output.splitlines():
        if _ENV_SIGNATURE_RE.search(line):
            continue
        if in_failed_targets_block:
            if _LAKE_FAILED_TARGET_ITEM_RE.match(line):
                continue
            in_failed_targets_block = False
        if _LAKE_FAILED_TARGETS_HEADER_RE.match(line):
            if current:
                diagnostics.append(current)
                current = None
            in_failed_targets_block = True
            continue
        if _LAKE_STATUS_LINE_RE.match(line) or _LAKE_BUILD_SUMMARY_RE.match(line) or _LAKE_INFO_LINE_RE.match(line):
            if current:
                diagnostics.append(current)
                current = None
            continue
        match = _DIAG_RE.match(line) or _DIAG_RE_LAKE.match(line)
        if match:
            if current:
                diagnostics.append(current)
            current = {
                "file": match.group("file"),
                "line": int(match.group("line")),
                "col": int(match.group("col")),
                "severity": match.group("severity"),
                "message_lines": [match.group("message")],
            }
            continue
        error_line = _ERROR_LINE_RE.match(line)
        if error_line:
            if current:
                diagnostics.append(current)
            current = {
                "file": None,
                "line": None,
                "col": None,
                "severity": "error",
                "message_lines": [error_line.group("message")],
            }
            continue
        job_failure = _LAKE_JOB_FAILURE_RE.match(line)
        if job_failure:
            if current:
                diagnostics.append(current)
            current = {
                "file": None,
                "line": None,
                "col": None,
                "severity": "error",
                "message_lines": [line],
            }
            continue
        if current is not None and current["file"] is None and current["line"] is None:
            file_continuation = _FILE_CONTINUATION_RE.match(line)
            if file_continuation:
                current["file"] = file_continuation.group("file").strip()
                current["message_lines"].append(line)
                continue
        if current is not None and line.strip() and len(current["message_lines"]) < MAX_MESSAGE_LINES:
            current["message_lines"].append(line)
    if current:
        diagnostics.append(current)
    for diag in diagnostics:
        diag["message"] = "\n".join(diag.pop("message_lines"))
    return diagnostics


def _environment_failure_receipt(action: str, result) -> dict[str, Any]:
    return {
        "kind": "build",
        "ok": False,
        "environment_error": True,
        "error_count": 0,
        "warning_count": 0,
        "errors": [],
        "message": f"`{action}` environment failure (exit {result.returncode}): {result.stderr.strip()[:500]}",
    }


def lake_build(unit_dir: Path, proofs: bool, timeout: float | None = None) -> dict[str, Any]:
    """``lake build`` (with ``proofs=True`` also a second, explicit ``lake build <modules>`` over
    every module ``prove.compute_module_scope`` finds under the unit dir -- not only
    ``Unit.Proofs``). V1.1 (round 6): a real Lake 4.34.1 source read (``LeanLibConfig.lean``'s
    default ``globs := roots.map Glob.one``) confirms a `lean_lib`'s own default build only
    builds its declared root(s) plus their transitive import closure -- it never builds every
    ``.lean`` file under the root directory regardless of import status. A stray, unimported
    module (e.g. a scratch file nothing imports) therefore never gets a `.olean` from the plain
    `lake build` above; without a real compile attempt somewhere, its `.olean` is simply missing
    when `formalcheck`/`leanchecker` later try to `importModules` it by name, which fails with no
    Lean diagnostic at all (`,formal prove` used to report a bare "did not print valid JSON").
    Building the exact same filesystem-derived module list `,formal prove` later checks means a
    stray module *under a declared* `lean_lib` root (e.g. a scratch file under `Unit/`) gets a
    real compile attempt here, so a type error in it surfaces as an ordinary build failure with
    real diagnostics instead. Any other stray module -- one outside every declared root (never
    resolvable to any package's own module namespace at all), or one under a `lean_exe` root
    other than that exe's own root module (round 8: `Lake/Config/Package.lean:418-421`
    `isBuildableModule`, `LeanExe.lean:134` confirm Lake only ever builds a `lean_exe`'s exact
    root module by name, never any other file under the same directory, live-confirmed by a real
    `lake build Main.Helper` against the template's `lean_exe` root) -- instead fails this second
    `lake build` call itself with Lake's own `unknown target` error, not a diagnostic from the
    module's own content."""
    result = run(["lake", "build"], cwd=unit_dir, timeout=timeout)
    if is_environment_or_provisioning_failure(result):
        # The process could not run, or the elan proxy failed to provision the pinned toolchain
        # before a real Lean invocation began. Neither case is a genuine check result.
        return _environment_failure_receipt("lake build", result)
    combined = result.stdout + "\n" + result.stderr
    diagnostics = parse_diagnostics(combined)
    had_output = bool(combined.strip())
    ok = result.returncode == 0
    if proofs and ok:
        modules = prove_mod.compute_module_scope(unit_dir)
        proofs_action = f"lake build {' '.join(modules)}" if modules else "lake build"
        proofs_result = run(["lake", "build", *modules], cwd=unit_dir, timeout=timeout)
        if is_environment_or_provisioning_failure(proofs_result):
            return _environment_failure_receipt(proofs_action, proofs_result)
        proofs_combined = proofs_result.stdout + "\n" + proofs_result.stderr
        diagnostics = _merge_diagnostics(diagnostics, parse_diagnostics(proofs_combined))
        had_output = had_output or bool(proofs_combined.strip())
        ok = ok and proofs_result.returncode == 0
    errors = [d for d in diagnostics if d["severity"] == "error"]
    warnings = [d for d in diagnostics if d["severity"] == "warning"]
    receipt = {
        "kind": "build",
        "ok": ok and not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": [
            {"file": d["file"], "line": d["line"], "col": d["col"], "message": d["message"]}
            for d in errors[:MAX_REPORTED_ERRORS]
        ],
    }
    if not receipt["ok"] and not had_output:
        # A nonzero exit with literally no stdout/stderr text at all can never have produced a
        # genuine parsed diagnostic -- `run_stage_guarded` (audit.py) uses this flag instead of
        # guessing an environment failure merely from `error_count == 0`; a Lake failure that
        # printed text but happened to match zero recognized diagnostic shapes would leave
        # `had_output` true and this flag unset.
        receipt["empty_output"] = True
    return receipt
