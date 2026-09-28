"""Argument parsing and command dispatch for ``,formal``.

Exit codes: 0 ok, 1 check failed, 2 usage/environment error.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Any, Callable

from . import audit as audit_mod
from . import build as build_mod
from . import catalog as catalog_mod
from . import exe as exe_mod
from . import manifest as manifest_mod
from . import paths
from . import prove as prove_mod
from . import replay as replay_mod
from .anchors import (
    check_anchor,
    count_occurrences,
    extract_snippet,
    norm_sha,
    normalize_snippet,
    source_sha,
    trim_to_nonblank,
)
from .util import DEFAULT_TIMEOUT, CliError, normalize_repo_path, print_json, run_raw

VERSION = "0.1.0"

_LOCATION_RE = re.compile(r"^(?P<path>.+):(?P<start>\d+)-(?P<end>\d+)$")


def emit(args: argparse.Namespace, receipt: Any, human_fn: Callable[[], None]) -> None:
    if getattr(args, "json", False):
        print_json(receipt)
    else:
        human_fn()


def build_layout(args: argparse.Namespace) -> paths.Layout:
    return paths.Layout(paths.workspace_root(None))


# --------------------------------------------------------------------------
# doctor
# --------------------------------------------------------------------------


def _tool_check(tool: str) -> dict[str, Any]:
    found = shutil.which(tool)
    return {"present": found is not None, "path": found}


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = {tool: _tool_check(tool) for tool in ("elan", "lake", "lean")}
    toolchain_installed = False
    if checks["elan"]["present"]:
        from .util import run

        listed = run(["elan", "toolchain", "list"], timeout=15)
        toolchain_installed = listed.returncode == 0 and paths.PINNED_TOOLCHAIN in listed.stdout
    if args.install:
        if not checks["elan"]["present"]:
            raise CliError("elan is not on PATH; cannot install the pinned toolchain.", code=2)
        from .util import run

        installed = run(["elan", "toolchain", "install", paths.PINNED_TOOLCHAIN], timeout=600)
        toolchain_installed = installed.returncode == 0
        if not toolchain_installed:
            raise CliError(f"Failed to install {paths.PINNED_TOOLCHAIN}:\n{installed.stderr}", code=1)
    ok = all(check["present"] for check in checks.values()) and toolchain_installed
    receipt = {
        "kind": "doctor",
        "ok": ok,
        "tools": checks,
        "toolchain": paths.PINNED_TOOLCHAIN,
        "toolchain_installed": toolchain_installed,
    }

    def human() -> None:
        for tool, info in checks.items():
            print(f"{tool}: {'ok ' + info['path'] if info['present'] else 'MISSING'}")
        print(f"toolchain {paths.PINNED_TOOLCHAIN}: {'installed' if toolchain_installed else 'not installed'}")

    emit(args, receipt, human)
    return 0 if ok else 1


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = manifest_mod.init_unit(layout, args.unit, args.tier, args.design, args.from_version)
    receipt = {"kind": "init", "unit": args.unit, "unit_dir": str(unit_dir)}
    emit(args, receipt, lambda: print(f"Initialized unit {args.unit!r}: {unit_dir}"))
    return 0


# --------------------------------------------------------------------------
# anchors add | check | list
# --------------------------------------------------------------------------


def _nfc_casefold(name: str) -> str:
    """NFC-normalize before case-folding, so an NFD-decomposed name (e.g. a combining-accent
    sequence a keyboard/paste can produce for an accented character) compares equal to the same
    name in git's typical NFC-composed form -- a plain ``.casefold()`` alone only folds case, it
    never reconciles two different Unicode decompositions of the same visible character."""
    return unicodedata.normalize("NFC", name).casefold()


def _git_tracked_case(workspace: Path, rel_posix: str) -> str | None:
    """Ask git for the exact tracked spelling of ``rel_posix`` via a case-insensitive, literal
    pathspec (``:(icase,literal)`` -- ``literal`` turns off glob-metacharacter interpretation of
    ``rel_posix``, so a caller-typed literal ``[``/``]``/``?``/``*`` in a filename is matched as
    itself and never as a glob: without it, an untracked ``a[b].py`` on the command line would
    make ``:(icase)a[b].py`` glob-match a same-directory tracked ``ab.py`` instead), the
    authoritative source for the case ``git diff``/``git ls-files`` will later report for this
    same file (``catalog stale``/``catalog uncovered`` match those git-reported paths against
    anchor paths with a plain string comparison, so anchoring under any other case silently makes
    a real match invisible). Even a literal pathspec still matches every path *under* a tracked
    directory that shares ``rel_posix``'s name (git's normal directory-prefix pathspec
    semantics), so every candidate is additionally required to be ``os.path.samefile`` with
    ``workspace / rel_posix`` (the exact path the caller asked about) before it is trusted --
    otherwise resolving a bare tracked directory name (e.g. ``src``) would wrongly "find" one
    tracked file underneath it (e.g. ``src/a.py``) and redirect the anchor there. Returns the
    tracked spelling only for exactly one ``samefile`` match; zero matches (untracked, no git
    repository at all, or every candidate failing the ``samefile`` check) or more than one
    surviving ``samefile`` match (a genuinely ambiguous pathspec) fall back to the on-disk
    listing instead of guessing."""
    result = run_raw(
        ["git", "ls-files", "-z", "--full-name", "--", f":(icase,literal){rel_posix}"],
        cwd=workspace,
        timeout=15,
    )
    if result.returncode != 0:
        return None
    names = [part.decode("utf-8", "surrogateescape") for part in result.stdout.split(b"\0") if part]
    if not names:
        return None
    target = workspace / rel_posix
    matches = []
    for name in names:
        try:
            if os.path.samefile(workspace / name, target):
                matches.append(name)
        except OSError:
            continue
    return matches[0] if len(matches) == 1 else None


def _actual_case_path_on_disk(workspace: Path, rel: Path) -> Path:
    """Recover the exact on-disk spelling of ``rel`` (a path already confirmed to exist under
    ``workspace``, but not resolved by ``_git_tracked_case`` -- an untracked file), one path
    component at a time, via a directory listing. On a case-insensitive, case-preserving
    filesystem (the macOS/Windows default), the caller's literal command-line spelling (e.g.
    ``M.py``) can resolve to a real file while never matching the actual on-disk spelling.
    Every component below is matched by its exact name first, and only NFC-normalized
    case-folded (see ``_nfc_casefold``) as a fallback when no exact match is found in that
    directory listing. Falls back to the literal ``rel`` unchanged for a component whose parent
    cannot be listed, or that is not found at all (folded or not) in that listing."""
    resolved_parts: list[str] = []
    current = workspace
    for part in rel.parts:
        try:
            names = [entry.name for entry in os.scandir(current)]
        except OSError:
            return rel
        actual = part if part in names else None
        if actual is None:
            folded = {_nfc_casefold(name): name for name in names}
            actual = folded.get(_nfc_casefold(part))
        if actual is None:
            return rel
        resolved_parts.append(actual)
        current = current / actual
    return Path(*resolved_parts)


def _actual_case_path(workspace: Path, rel: Path) -> Path:
    """Recover the exact spelling ``rel`` (a path already confirmed to exist under
    ``workspace``) must be stored under: git's own tracked spelling when the file is tracked
    (see ``_git_tracked_case``), since that is what a later ``catalog stale``/``catalog
    uncovered`` will compare against; the on-disk spelling (see ``_actual_case_path_on_disk``)
    for an untracked file. Only called after confirming ``workspace / rel`` exists; the guard
    against redirecting an anchor to a different, unrelated file is ``_git_tracked_case``'s own
    ``os.path.samefile`` check against that same ``workspace / rel`` path, not merely this prior
    existence check -- existence alone would not stop git's pathspec matching (directory-prefix
    or, before ``literal``, glob semantics) from reporting an unrelated tracked file that also
    exists."""
    tracked = _git_tracked_case(workspace, rel.as_posix())
    if tracked is not None:
        return Path(tracked)
    return _actual_case_path_on_disk(workspace, rel)


def _relative_to_case_insensitive(absolute: Path, workspace_resolved: Path) -> Path | None:
    """Return a suffix for a case-folded workspace prefix only when it is the same directory.

    Folded component equality identifies a possible filesystem alias, but on a case-sensitive
    filesystem two distinct sibling directories can differ only by case. ``samefile`` proves
    that the prefix supplied by the caller and the workspace are one filesystem object before
    the caller's trailing path is rewritten as workspace-relative.
    """
    ws_parts = workspace_resolved.parts
    abs_parts = absolute.parts
    if len(abs_parts) < len(ws_parts):
        return None
    if any(_nfc_casefold(ws_part) != _nfc_casefold(abs_part) for ws_part, abs_part in zip(ws_parts, abs_parts)):
        return None
    supplied_prefix = Path(*abs_parts[: len(ws_parts)])
    try:
        if not os.path.samefile(supplied_prefix, workspace_resolved):
            return None
    except OSError:
        return None
    return Path(*abs_parts[len(ws_parts) :]) if len(abs_parts) > len(ws_parts) else Path(".")


def _resolve_anchor_path(workspace: Path, raw_path: str) -> str:
    """Resolve ``raw_path`` (as given on the ``anchors add`` command line) to a path relative to
    ``workspace``. An absolute path is accepted only when it resolves inside the workspace, in
    which case it is stored as the equivalent repo-relative path; any path -- absolute or a
    relative path containing ``..`` -- that resolves outside the workspace is rejected, since an
    anchor's ``path`` is always read back as workspace-relative everywhere else (``workspace /
    anchor["path"]`` in ``anchors.check_anchor`` and ``manifest._extra_snapshot_entries``).

    When the resolved path exists on disk, its case is corrected to the actual on-disk spelling
    (see ``_actual_case_path``) before being stored, so a case-insensitive-filesystem typo in
    ``raw_path`` never ends up stored in a case that later fails to match ``git``'s own reported
    case for the same file."""
    candidate = Path(raw_path)
    absolute = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    workspace_resolved = workspace.resolve()
    try:
        rel = absolute.relative_to(workspace_resolved)
    except ValueError:
        rel = _relative_to_case_insensitive(absolute, workspace_resolved)
        if rel is None:
            raise CliError(
                f"Anchor path {raw_path!r} is outside the workspace ({workspace_resolved}).", code=2
            ) from None
    if (workspace_resolved / rel).exists():
        rel = _actual_case_path(workspace_resolved, rel)
    return normalize_repo_path(str(rel))


def cmd_anchors_add(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest_mod.load_manifest(unit_dir)
    match = _LOCATION_RE.match(args.location)
    if not match:
        raise CliError(f"Invalid anchor location {args.location!r}; expected path:start-end.", code=2)
    # Normalize only the path representation: `./m.py` and `m.py` are always the same anchor
    # path. An absolute path inside the workspace is stored repo-relative; a path that resolves
    # outside the workspace is rejected (see `_resolve_anchor_path`).
    rel_path = _resolve_anchor_path(layout.workspace, match.group("path"))
    start, end = int(match.group("start")), int(match.group("end"))
    file_path = layout.workspace / rel_path
    if not file_path.exists():
        raise CliError(f"Anchor target not found: {file_path}", code=2)
    try:
        # A leading/trailing blank line in the requested range is never itself recorded as part
        # of the anchor (and an all-blank range is rejected outright). Blank lines inside the
        # resulting range remain exact snippet text.
        start, end = trim_to_nonblank(file_path, start, end)
        snippet_raw = extract_snippet(file_path, start, end)
        source_digest = source_sha(file_path)
    except ValueError as exc:
        raise CliError(str(exc), code=2) from exc
    normalized_snippet = normalize_snippet(snippet_raw)
    # Recorded now, checked later: `anchors.check_anchor` only relocates a moved anchor to a
    # new line range when it was unique in the file at add time -- a duplicate-text anchor
    # (e.g. two structurally identical functions) can never be safely relocated by text alone.
    unique = count_occurrences(file_path, normalized_snippet) == 1
    anchors = manifest_mod.load_anchors(unit_dir)
    anchor_id = args.id or manifest_mod.next_anchor_id(anchors)
    anchor = {
        "id": anchor_id,
        "path": rel_path,
        "start": start,
        "end": end,
        "norm_sha": norm_sha(snippet_raw),
        "source_sha": source_digest,
        "snippet": normalized_snippet,
        "note": args.note or "",
        "unique": unique,
    }
    # `--id <existing>` re-anchors that id at a new location (an edited row moving under the
    # agent's feet); every other id is untouched.
    replaced = any(a["id"] == anchor_id for a in anchors)
    anchors = [a for a in anchors if a["id"] != anchor_id] + [anchor]
    manifest_mod.save_anchors(unit_dir, anchors)
    verb = "Replaced" if replaced else "Added"
    emit(args, anchor, lambda: print(f"{verb} anchor {anchor_id}: {rel_path}:{start}-{end}"))
    return 0


def cmd_anchors_check(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest_mod.load_manifest(unit_dir)
    anchors = manifest_mod.load_anchors(unit_dir)
    checks = [check_anchor(layout.workspace, anchor) for anchor in anchors]
    ok = all(c["status"] == "unchanged" for c in checks)
    if args.write:
        checks_by_id = {c["id"]: c for c in checks}
        updated = []
        for anchor in anchors:
            check = checks_by_id.get(anchor["id"])
            if check and check["status"] == "unchanged":
                anchor = {**anchor, "start": check["start"], "end": check["end"]}
            updated.append(anchor)
        manifest_mod.save_anchors(unit_dir, updated)
    receipt = {"kind": "anchors_check", "unit": args.unit, "ok": ok, "anchors": checks}

    def human() -> None:
        for check in checks:
            suffix = f" ({check.get('start')}-{check.get('end')})" if check["status"] == "unchanged" else ""
            print(f"{check['id']}: {check['status']}{suffix}")

    emit(args, receipt, human)
    return 0 if ok else 1


def cmd_anchors_list(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest_mod.load_manifest(unit_dir)
    anchors = manifest_mod.load_anchors(unit_dir)
    receipt = {"kind": "anchors_list", "unit": args.unit, "anchors": anchors}

    def human() -> None:
        for anchor in anchors:
            print(f"{anchor['id']}: {anchor['path']}:{anchor['start']}-{anchor['end']} {anchor.get('note', '')}")

    emit(args, receipt, human)
    return 0


# --------------------------------------------------------------------------
# build / explore / mutate / traces / replay / prove / audit
# --------------------------------------------------------------------------


def cmd_build(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest_mod.load_manifest(unit_dir)
    receipt = build_mod.lake_build(unit_dir, proofs=args.proofs, timeout=DEFAULT_TIMEOUT)

    def human() -> None:
        if receipt.get("environment_error"):
            print(receipt["message"])
            return
        print(
            f"Build {'OK' if receipt['ok'] else 'FAILED'}: {receipt['error_count']} errors, {receipt['warning_count']} warnings"
        )
        for err in receipt["errors"]:
            print(f"  {err['file']}:{err['line']}:{err['col']}: {err['message']}")

    emit(args, receipt, human)
    if receipt.get("environment_error"):
        return 2
    return 0 if receipt["ok"] else 1


def cmd_explore(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest = manifest_mod.load_manifest(unit_dir)
    budgets = manifest.get("budgets") or {}
    max_states = args.max_states if args.max_states is not None else budgets.get("max_states")
    max_depth = args.max_depth if args.max_depth is not None else budgets.get("max_depth")
    receipt = exe_mod.explore(unit_dir, max_states, max_depth, timeout=DEFAULT_TIMEOUT)
    props = receipt.get("props", [])
    if exe_mod.explore_vacuous(props):
        # Zero declared properties is a vacuous pass, not a genuine "nothing violated" result --
        # the same condition `audit.run_stage_explore` applies.
        receipt["ok"] = False
        receipt["error"] = "vacuous: no properties"
    else:
        receipt["ok"] = all(exe_mod.prop_ok(prop) for prop in props)

    def human() -> None:
        if receipt.get("error"):
            print(f"Explore FAILED: {receipt['error']}")
            return
        print(
            f"Explore: {receipt['states']} states, {receipt['transitions']} transitions, bounded={receipt['bounded']}"
        )
        for prop in receipt["props"]:
            mark = "OK" if exe_mod.prop_ok(prop) else "FAIL"
            print(f"  [{mark}] {prop['name']} expect={prop['expect']} status={prop['status']}")

    emit(args, receipt, human)
    return 0 if receipt["ok"] else 1


def cmd_mutate(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest = manifest_mod.load_manifest(unit_dir)
    budgets = manifest.get("budgets") or {}
    max_states = args.max_states if args.max_states is not None else budgets.get("max_states")
    max_depth = args.max_depth if args.max_depth is not None else budgets.get("max_depth")
    receipt = exe_mod.mutate(unit_dir, max_states, max_depth, timeout=DEFAULT_TIMEOUT)
    mutants = receipt.get("mutants", [])
    control_ok = bool(receipt.get("control", {}).get("ok"))
    if not mutants:
        # Zero mutants "kills" nothing -- a vacuous "every mutant killed" pass proves no
        # property is adequate at all, the same condition `audit.run_stage_mutate` applies.
        receipt["ok"] = False
        receipt["error"] = "vacuous: no mutants"
    else:
        vacuous_names = exe_mod.mutate_vacuous_names(mutants)
        if vacuous_names:
            receipt["ok"] = False
            receipt["error"] = f"vacuous: mutant(s) with no declared expected killer: {', '.join(vacuous_names)}"
        else:
            not_killed = [m for m in mutants if m.get("status") in ("survived", "wrong-killer")]
            receipt["ok"] = control_ok and not not_killed

    def human() -> None:
        if receipt.get("error"):
            print(f"Mutate FAILED: {receipt['error']}")
            return
        print(f"Mutate control: {'OK' if control_ok else 'FAILED'}")
        for mutant in mutants:
            print(f"  {mutant['name']}: {mutant['status']}")
            if mutant["status"] == "wrong-killer":
                print(f"    expected killer(s): {mutant.get('expected')}, actual: {mutant.get('killed_by')}")

    emit(args, receipt, human)
    return 0 if receipt["ok"] else 1


def cmd_traces(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest = manifest_mod.load_manifest(unit_dir)
    budgets = manifest.get("budgets") or {}
    output = exe_mod.traces(
        unit_dir,
        args.mode,
        args.max,
        timeout=DEFAULT_TIMEOUT,
        max_states=budgets.get("max_states"),
        max_depth=budgets.get("max_depth"),
    )
    traces_path = unit_dir / "traces" / "traces.jsonl"
    traces_path.parent.mkdir(parents=True, exist_ok=True)
    traces_path.write_text(output, encoding="utf-8")
    count = sum(1 for line in output.splitlines() if line.strip())
    receipt = {"kind": "traces", "unit": args.unit, "mode": args.mode, "count": count, "path": str(traces_path)}
    emit(args, receipt, lambda: print(f"Wrote {count} traces to {traces_path}"))
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest = manifest_mod.load_manifest(unit_dir)
    if args.against:
        if not (manifest.get("replay") or {}).get("differential"):
            raise CliError(
                "Differential replay (`--against`) requires MANIFEST.json `replay.differential: "
                "true`. The adapter must execute the code under FORMAL_REPO_ROOT (never a shared "
                "live deployment) for a differential comparison to mean anything; set "
                "replay.differential: true once the adapter satisfies that contract.",
                code=2,
            )
        receipt = replay_mod.run_replay_differential(
            layout, unit_dir, layout.workspace, manifest, args.adapter, args.against, DEFAULT_TIMEOUT
        )
    else:
        receipt = replay_mod.run_replay(unit_dir, layout.workspace, manifest, args.adapter, DEFAULT_TIMEOUT)

    def human() -> None:
        print(f"Replay {'PASS' if receipt['ok'] else 'FAIL'}: {receipt['passed']}/{receipt['total']} traces")
        for result in receipt["results"]:
            if result["status"] != "pass":
                print(f"  {result['trace_id']}: {result['status']} {result.get('detail', '')}")

    emit(args, receipt, human)
    return 0 if receipt["ok"] else 1


def cmd_prove(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest_mod.load_manifest(unit_dir)
    build_receipt = build_mod.lake_build(unit_dir, proofs=True, timeout=DEFAULT_TIMEOUT)
    if build_receipt.get("environment_error"):
        # `lake build` itself never reached prove.py's own environment-failure checks (the
        # `formalcheck`/`leanchecker` invocations) -- surface the build receipt's
        # environment_error/message here instead of letting run_prove's generic
        # `not build_receipt["ok"]` branch discard it.
        receipt: dict = {
            "kind": "prove",
            "ok": False,
            "build_ok": False,
            "environment_error": True,
            "message": build_receipt["message"],
        }
    else:
        receipt = prove_mod.run_prove(unit_dir, build_receipt, timeout=DEFAULT_TIMEOUT)

    def human() -> None:
        if receipt.get("environment_error"):
            print(receipt["message"])
            return
        print(f"Prove {'OK' if receipt['ok'] else 'FAILED'}")
        for hit in receipt["forbidden_tokens"]:
            print(f"  forbidden token {hit['token']!r} at {hit['file']}:{hit['line']}")
        axioms = receipt.get("axioms") or {}
        if axioms.get("disallowed_axioms"):
            print(f"  disallowed axioms: {', '.join(axioms['disallowed_axioms'])}")

    emit(args, receipt, human)
    if receipt.get("environment_error"):
        return 2
    return 0 if receipt["ok"] else 1


def cmd_audit(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest = manifest_mod.load_manifest(unit_dir)
    snapshot = manifest_mod.snapshot_id(layout.workspace, unit_dir)
    receipt = audit_mod.run_audit(
        unit_dir, layout.workspace, manifest, snapshot, args.require, args.allow_unverified_conformance, DEFAULT_TIMEOUT
    )

    def human() -> None:
        print(f"Audit {receipt['verdict'].upper()} ({receipt['unit']} @ {receipt['snapshot']})")
        for name, info in receipt["stages"].items():
            print(f"  {name}: {info['status']}")
        print(receipt["certifies"])

    emit(args, receipt, human)
    return audit_exit_code(receipt)


def audit_exit_code(receipt: dict[str, Any]) -> int:
    """0 pass, 2 when any stage status is ``error`` (an environment failure, checked first since
    it means the check itself never really ran), 1 for an ordinary check failure."""
    if receipt.get("has_error"):
        return 2
    return 0 if receipt["verdict"] == "pass" else 1


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    branch = paths.branch_slug(layout.workspace)
    rows = []
    for unit in sorted(catalog_mod.all_known_units(layout)):
        unit_dir = layout.work_dir(unit)
        on_branch = unit_dir.exists()
        resolved = None if on_branch else catalog_mod.resolve_version(layout, unit)
        anchors = catalog_mod.current_reference_anchors(layout, unit)
        if not anchors:
            state = "no-anchors"
        else:
            checks = [check_anchor(layout.workspace, anchor) for anchor in anchors]
            state = "valid" if all(c["status"] == "unchanged" for c in checks) else "stale"
        rows.append(
            {
                "unit": unit,
                "on_branch": on_branch,
                "branch": branch,
                "resolved_version": resolved["id"] if resolved else None,
                "anchor_state": state,
            }
        )
    receipt = {"kind": "status", "branch": branch, "units": rows}

    def human() -> None:
        for row in rows:
            print(
                f"{row['unit']}: on_branch={row['on_branch']} state={row['anchor_state']} resolved={row['resolved_version']}"
            )

    emit(args, receipt, human)
    return 0


# --------------------------------------------------------------------------
# catalog list | resolve | checkout | stale | uncovered | save | gc
# --------------------------------------------------------------------------


def cmd_catalog_list(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    index = catalog_mod.load_index(layout)

    def human() -> None:
        for unit, entry in sorted(index.get("units", {}).items()):
            print(f"{unit}: {len(entry.get('versions', []))} version(s)")
            for version in entry.get("versions", []):
                print(f"  {version['id']} ({version.get('branch')}, {version.get('created')})")

    emit(args, index, human)
    return 0


def cmd_catalog_resolve(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    resolved = catalog_mod.resolve_version(layout, args.unit)
    if not resolved:
        raise CliError(f"No resolvable version for unit {args.unit}.", code=1)
    emit(args, resolved, lambda: print(f"{resolved['id']} ({resolved['branch']}, {resolved['created']})"))
    return 0


def cmd_catalog_checkout(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = catalog_mod.checkout_version(layout, args.unit, force=args.force)
    receipt = {"kind": "catalog_checkout", "unit": args.unit, "unit_dir": str(unit_dir)}
    emit(args, receipt, lambda: print(f"Checked out {args.unit} into {unit_dir}"))
    return 0


def cmd_catalog_stale(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    stale = catalog_mod.stale_units(layout, args.base)
    receipt = {"kind": "catalog_stale", "base": args.base, "units": stale}

    def human() -> None:
        for entry in stale:
            print(f"{entry['unit']}: {len(entry['anchors'])} anchor(s) not unchanged")

    emit(args, receipt, human)
    return 0


def cmd_catalog_uncovered(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    hunks = catalog_mod.uncovered_hunks(layout, args.base)
    receipt = {"kind": "catalog_uncovered", "base": args.base, "hunks": hunks}

    def human() -> None:
        for hunk in hunks:
            print(f"{hunk['path']}:{hunk['start']}-{hunk['end']}")

    emit(args, receipt, human)
    return 0


def cmd_catalog_save(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    unit_dir = layout.work_dir(args.unit)
    manifest_mod.load_manifest(unit_dir)
    record = catalog_mod.save_version(layout, args.unit, unit_dir, args.allow_unverified)
    emit(args, record, lambda: print(f"Saved version {record['id']} for {args.unit}"))
    return 0


def cmd_catalog_gc(args: argparse.Namespace) -> int:
    layout = build_layout(args)
    result = catalog_mod.gc(layout, args.keep)
    emit(
        args,
        result,
        lambda: print(
            f"Removed {len(result['removed_versions'])} version(s), {len(result['removed_kits'])} kit dir(s)"
        ),
    )
    return 0


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print the receipt as JSON.")


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=",formal", description="Persistent, diff-aware formal model catalog.")
    parser.add_argument("--version", action="version", version=f",formal {VERSION}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    doctor = subcommands.add_parser("doctor", help="Check elan/lake/lean and the pinned toolchain.")
    doctor.add_argument("--install", action="store_true", help="Install the pinned Lean toolchain.")
    _add_json_flag(doctor)
    doctor.set_defaults(func=cmd_doctor)

    init = subcommands.add_parser("init", help="Create a unit work dir from the template or a saved version.")
    init.add_argument("unit", help="Unit name.")
    init.add_argument("--tier", choices=["F2", "F3"], default="F2", help="Verification tier (default F2).")
    init.add_argument("--design", action="store_true", help="Design unit: models intended behavior before code exists.")
    init.add_argument("--from-version", metavar="ID", help="Materialize a saved version instead of the template.")
    _add_json_flag(init)
    init.set_defaults(func=cmd_init)

    anchors = subcommands.add_parser("anchors", help="Manage anchors for a unit.")
    anchors_sub = anchors.add_subparsers(dest="anchors_command", required=True)

    anchors_add = anchors_sub.add_parser("add", help="Record an exact-text anchor snippet.")
    anchors_add.add_argument("unit", help="Unit name.")
    anchors_add.add_argument("location", metavar="path:start-end", help="Repo-relative path and 1-based line range.")
    anchors_add.add_argument("--id", help="Explicit anchor id, such as A1; re-anchors it if the id already exists.")
    anchors_add.add_argument("--note", help="Free-text note.")
    _add_json_flag(anchors_add)
    anchors_add.set_defaults(func=cmd_anchors_add)

    anchors_check = anchors_sub.add_parser("check", help="Resolve every anchor against the current tree.")
    anchors_check.add_argument("unit", help="Unit name.")
    anchors_check.add_argument(
        "--write", action="store_true", help="Persist relocated start/end for every unchanged anchor."
    )
    _add_json_flag(anchors_check)
    anchors_check.set_defaults(func=cmd_anchors_check)

    anchors_list = anchors_sub.add_parser("list", help="List anchors for a unit.")
    anchors_list.add_argument("unit", help="Unit name.")
    _add_json_flag(anchors_list)
    anchors_list.set_defaults(func=cmd_anchors_list)

    build = subcommands.add_parser("build", help="lake build the unit.")
    build.add_argument("unit", help="Unit name.")
    build.add_argument("--proofs", action="store_true", help="Also build Unit.Proofs.")
    _add_json_flag(build)
    build.set_defaults(func=cmd_build)

    explore = subcommands.add_parser("explore", help="Exhaustively search reachable states for property violations.")
    explore.add_argument("unit", help="Unit name.")
    explore.add_argument("--max-states", type=_nonnegative_int, help="State budget override.")
    explore.add_argument("--max-depth", type=_nonnegative_int, help="Depth budget override.")
    _add_json_flag(explore)
    explore.set_defaults(func=cmd_explore)

    mutate = subcommands.add_parser("mutate", help="Run the control and each mutant step function.")
    mutate.add_argument("unit", help="Unit name.")
    mutate.add_argument("--max-states", type=_nonnegative_int, help="State budget override.")
    mutate.add_argument("--max-depth", type=_nonnegative_int, help="Depth budget override.")
    _add_json_flag(mutate)
    mutate.set_defaults(func=cmd_mutate)

    traces = subcommands.add_parser("traces", help="Write traces/traces.jsonl.")
    traces.add_argument("unit", help="Unit name.")
    traces.add_argument("--mode", choices=["cover", "failures"], default="cover", help="Trace selection mode.")
    traces.add_argument("--max", type=_nonnegative_int, help="Maximum traces (cover mode default 500).")
    _add_json_flag(traces)
    traces.set_defaults(func=cmd_traces)

    replay = subcommands.add_parser("replay", help="Feed traces to a real-code adapter and compare observed output.")
    replay.add_argument("unit", help="Unit name.")
    replay.add_argument("--adapter", help="Adapter shell command (overrides MANIFEST.adapter.cmd).")
    replay.add_argument("--against", metavar="REF", help="Differential mode: compare REF vs HEAD on the same traces.")
    _add_json_flag(replay)
    replay.set_defaults(func=cmd_replay)

    prove = subcommands.add_parser("prove", help="Forbidden-token scan plus collectAxioms on every Proofs theorem.")
    prove.add_argument("unit", help="Unit name.")
    _add_json_flag(prove)
    prove.set_defaults(func=cmd_prove)

    audit = subcommands.add_parser("audit", help="Aggregate gate over the tier's required stages.")
    audit.add_argument("unit", help="Unit name.")
    audit.add_argument("--require", help="Comma-separated stage override.")
    audit.add_argument(
        "--allow-unverified-conformance", action="store_true", help="Allow verdict pass when replay is unverified."
    )
    _add_json_flag(audit)
    audit.set_defaults(func=cmd_audit)

    status = subcommands.add_parser("status", help="Show every unit's state for the current repo.")
    _add_json_flag(status)
    status.set_defaults(func=cmd_status)

    catalog = subcommands.add_parser("catalog", help="Persistent per-machine unit-version catalog.")
    catalog_sub = catalog.add_subparsers(dest="catalog_command", required=True)

    catalog_list = catalog_sub.add_parser("list", help="List units and versions.")
    _add_json_flag(catalog_list)
    catalog_list.set_defaults(func=cmd_catalog_list)

    catalog_resolve = catalog_sub.add_parser("resolve", help="Resolve the newest valid version for a unit.")
    catalog_resolve.add_argument("unit", help="Unit name.")
    _add_json_flag(catalog_resolve)
    catalog_resolve.set_defaults(func=cmd_catalog_resolve)

    catalog_checkout = catalog_sub.add_parser(
        "checkout", help="Materialize the resolved version into this branch's work dir."
    )
    catalog_checkout.add_argument("unit", help="Unit name.")
    catalog_checkout.add_argument(
        "--force",
        action="store_true",
        help="Discard local work-dir differences from the resolved version instead of refusing.",
    )
    _add_json_flag(catalog_checkout)
    catalog_checkout.set_defaults(func=cmd_catalog_checkout)

    catalog_stale = catalog_sub.add_parser("stale", help="List units with any non-unchanged anchor.")
    catalog_stale.add_argument("--base", metavar="REF", help="Restrict to units anchoring files changed since REF.")
    _add_json_flag(catalog_stale)
    catalog_stale.set_defaults(func=cmd_catalog_stale)

    catalog_uncovered = catalog_sub.add_parser("uncovered", help="List changed hunks not overlapped by any anchor.")
    catalog_uncovered.add_argument("--base", metavar="REF", required=True, help="Diff base.")
    _add_json_flag(catalog_uncovered)
    catalog_uncovered.set_defaults(func=cmd_catalog_uncovered)

    catalog_save = catalog_sub.add_parser("save", help="Save the current unit snapshot as a catalog version.")
    catalog_save.add_argument("unit", help="Unit name.")
    catalog_save.add_argument("--allow-unverified", action="store_true", help="Save without a passing audit.")
    _add_json_flag(catalog_save)
    catalog_save.set_defaults(func=cmd_catalog_save)

    catalog_gc = catalog_sub.add_parser("gc", help="Drop old versions and orphan kit dirs.")
    catalog_gc.add_argument("--keep", type=_nonnegative_int, default=5, help="Versions to keep per unit (default 5).")
    _add_json_flag(catalog_gc)
    catalog_gc.set_defaults(func=cmd_catalog_gc)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CliError as exc:
        print(exc.message, file=sys.stderr)
        return exc.code
