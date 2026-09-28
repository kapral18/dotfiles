"""Persistent per-machine catalog: index, version resolution, staleness,
uncovered-hunk discovery, save, and gc."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import anchors as anchors_mod
from . import audit as audit_mod
from . import leankit, paths
from . import manifest as manifest_mod
from .util import CliError, locked_file, normalize_repo_path, read_json, run, sha256_hex, write_json, write_json_atomic


def load_index(layout: paths.Layout) -> dict[str, Any]:
    path = layout.index_json()
    if not path.exists():
        return {"units": {}}
    return read_json(path)


def save_index(layout: paths.Layout, index: dict[str, Any]) -> None:
    write_json_atomic(layout.index_json(), index)


def index_lock_path(layout: paths.Layout) -> Path:
    return layout.repo_dir / "index.lock"


def update_index(layout: paths.Layout, mutate: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Read-modify-write ``index.json`` under an exclusive file lock (guards concurrent
    ``catalog save``/``catalog gc`` invocations, possibly across worktrees sharing the same
    catalog, from a lost update), writing atomically via a temp file + ``os.replace`` so a
    concurrent reader never observes a half-written file. ``mutate`` edits ``index`` in place."""
    layout.repo_dir.mkdir(parents=True, exist_ok=True)
    with locked_file(index_lock_path(layout)):
        index = load_index(layout)
        mutate(index)
        save_index(layout, index)
        return index


def ensure_repo_json(layout: paths.Layout) -> None:
    path = layout.repo_json()
    if path.exists():
        return
    write_json(
        path,
        {
            "repo_id": layout.repo_id,
            "common_dir": str(paths.git_common_dir(layout.workspace)),
            "remote_url": paths.remote_url(layout.workspace),
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        },
    )


def list_versions(layout: paths.Layout, unit: str) -> list[dict[str, Any]]:
    return load_index(layout).get("units", {}).get(unit, {}).get("versions", [])


def version_anchors(layout: paths.Layout, unit: str, version_id: str) -> list[dict[str, Any]]:
    path = layout.version_dir(unit, version_id) / manifest_mod.ANCHORS_NAME
    if not path.exists():
        return []
    return read_json(path).get("anchors", [])


def version_valid(layout: paths.Layout, unit: str, version_id: str) -> bool:
    version_anchor_list = version_anchors(layout, unit, version_id)
    if not version_anchor_list:
        return False
    return all(
        anchors_mod.check_anchor(layout.workspace, anchor)["status"] == "unchanged" for anchor in version_anchor_list
    )


def _version_branches(version: dict[str, Any]) -> dict[str, int]:
    """Return opaque storage-key memberships and each branch's last save sequence."""
    branches = version.get("branches")
    if (
        not isinstance(branches, dict)
        or not branches
        or any(
            not isinstance(branch, str) or not branch or not isinstance(seq, int) or isinstance(seq, bool) or seq < 1
            for branch, seq in branches.items()
        )
    ):
        raise CliError(
            "Invalid catalog version record: branches must map non-empty strings to positive integer save sequences.",
            code=2,
        )
    return dict(branches)


def resolve_version(layout: paths.Layout, unit: str) -> dict[str, Any] | None:
    """Newest anchor-valid version, preferring the current branch's own save order."""
    versions = list_versions(layout, unit)
    current_branch = paths.branch_slug(layout.workspace)
    valid = [v for v in versions if version_valid(layout, unit, v["id"])]
    if not valid:
        return None
    memberships = [(version, _version_branches(version)) for version in valid]
    same_branch = [
        (version, branches[current_branch]) for version, branches in memberships if current_branch in branches
    ]
    if same_branch:
        return max(same_branch, key=lambda item: item[1])[0]
    return max(valid, key=_by_seq)


def _by_seq(version: dict[str, Any]) -> int:
    """Sort key for "newest version": a monotonically increasing per-unit ``seq`` assigned at
    save time (never wall-clock ``created``, whose second-granularity display timestamp cannot
    order two saves that land in the same second)."""
    return version.get("seq", 0)


def newest_version(layout: paths.Layout, unit: str) -> dict[str, Any] | None:
    """The most recently saved version on any branch, regardless of whether
    its anchors are currently valid."""
    versions = list_versions(layout, unit)
    if not versions:
        return None
    return sorted(versions, key=_by_seq, reverse=True)[0]


def _replace_work_dir_contents(destination: Path, source: Path) -> None:
    """Replace ``destination``'s contents with ``source``'s, preserving only
    an existing ``.lake/`` (the local Lake build cache; saved versions never
    contain one, so it is never overwritten by the copy below)."""
    if destination.exists():
        for entry in destination.iterdir():
            if entry.name == ".lake":
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


_CHECKOUT_REWRITTEN_MANIFEST_KEYS = ("branch", "source_commit")


def _manifest_digest_ignoring_checkout_fields(path: Path) -> str:
    """``MANIFEST.json``'s digest for the dirty-guard comparison only -- with ``branch`` and
    ``source_commit`` removed first, since ``checkout_version`` itself overwrites those two
    fields with the current branch/HEAD on every checkout. Comparing the raw file hash would
    otherwise flag a work dir that received no real edits at all as "differing" the moment HEAD
    moves between two checkouts of the same resolved version. Every other MANIFEST field still
    participates in the comparison unchanged."""
    manifest = read_json(path)
    for key in _CHECKOUT_REWRITTEN_MANIFEST_KEYS:
        manifest.pop(key, None)
    return sha256_hex(json.dumps(manifest, sort_keys=True).encode("utf-8"))


def _differing_paths(current_dir: Path, saved_dir: Path) -> list[str]:
    """Repo-relative-to-unit paths that differ between ``current_dir`` and ``saved_dir``, over
    the same hash-relevant file set ``manifest.unit_files_for_hash`` uses (``.lake``, ``tmp``,
    ``traces``, ``receipts`` excluded per the shared F16 rule): extra, missing, or
    content-modified files. Used to refuse a ``catalog checkout`` that would silently discard
    unsaved local edits."""
    current = dict(manifest_mod.unit_files_for_hash(current_dir))
    saved = dict(manifest_mod.unit_files_for_hash(saved_dir)) if saved_dir.exists() else {}
    manifest_name = manifest_mod.MANIFEST_NAME
    if manifest_name in current and manifest_name in saved:
        current[manifest_name] = _manifest_digest_ignoring_checkout_fields(current_dir / manifest_name)
        saved[manifest_name] = _manifest_digest_ignoring_checkout_fields(saved_dir / manifest_name)
    diffs = {rel for rel, digest in current.items() if saved.get(rel) != digest}
    diffs |= {rel for rel in saved if rel not in current}
    return sorted(diffs)


def checkout_version(layout: paths.Layout, unit: str, force: bool = False) -> Path:
    resolved = resolve_version(layout, unit)
    if not resolved:
        newest = newest_version(layout, unit)
        if newest:
            raise CliError(
                f"No resolvable (anchor-valid) version for unit {unit}. "
                f"Newest saved version is {newest['id']}; run `,formal init {unit} --from-version {newest['id']}`.",
                code=1,
            )
        raise CliError(f"No resolvable version for unit {unit}.", code=1)
    destination = layout.work_dir(unit)
    source = layout.version_dir(unit, resolved["id"])
    if destination.exists() and not force:
        diffs = _differing_paths(destination, source)
        if diffs:
            raise CliError(
                f"Work dir for unit {unit} differs from resolved version {resolved['id']} in: "
                f"{', '.join(diffs)}. Save first (`,formal catalog save {unit}`), or pass --force "
                "to discard these differences and check out the resolved version anyway.",
                code=2,
            )
    _replace_work_dir_contents(destination, source)
    manifest = manifest_mod.load_manifest(destination)
    manifest["repo_id"] = layout.repo_id
    manifest["branch"] = paths.current_branch(layout.workspace) or paths.branch_slug(layout.workspace)
    manifest["source_commit"] = paths.head_commit(layout.workspace) or ""
    manifest_mod.save_manifest(destination, manifest)
    return destination


def changed_paths_since(workspace: Path, base_ref: str) -> set[str]:
    merge_base = run(["git", "merge-base", base_ref, "HEAD"], cwd=workspace, timeout=15)
    if merge_base.returncode != 0:
        raise CliError(f"Cannot resolve merge-base for {base_ref}.", code=2)
    base = merge_base.stdout.strip()
    changed: set[str] = set()
    for argv in (
        # `--no-renames`: a plain `git diff --name-only` on a rename reports only the new
        # path, so a unit anchored to the file's *old* path (before the rename) would never
        # intersect this set. `--no-renames` reports it as a delete + add instead, surfacing
        # both the old and new paths. `-z` NUL-separates entries with no quoting, so a
        # non-ASCII path is never C-style-quoted (and thus missed by the `normalize_repo_path`
        # comparison against an anchor's plain path) the way plain `--name-only` output would
        # quote it.
        ["git", "diff", "-z", "--no-renames", "--name-only", base],
        ["git", "diff", "-z", "--no-renames", "--name-only"],
        ["git", "diff", "-z", "--no-renames", "--name-only", "--staged"],
    ):
        result = run(argv, cwd=workspace, timeout=30)
        # Fail closed like the rest of this module: a `git diff` that cannot run at all (missing
        # git, a timeout, a non-git workspace) must never be silently read as "this half of the
        # diff found nothing changed" -- `catalog stale --base`/`catalog status` would then miss
        # a real change instead of refusing.
        if result.returncode != 0:
            raise CliError(
                f"`git diff` failed (exit {result.returncode}) computing changed paths since {base_ref}.",
                code=2,
            )
        changed.update(normalize_repo_path(part) for part in result.stdout.split("\0") if part)
    # An untracked (but not ignored) file has no committed baseline to diff against, yet it is
    # still a real change relative to `base_ref` -- a unit anchored to it must count as touched
    # by the change under review, exactly like `catalog uncovered`'s own untracked-file handling.
    untracked = run(["git", "ls-files", "-z", "-o", "--exclude-standard"], cwd=workspace, timeout=30)
    if untracked.returncode != 0:
        raise CliError(
            f"`git ls-files` failed (exit {untracked.returncode}) computing changed paths since {base_ref}.",
            code=2,
        )
    changed.update(normalize_repo_path(part) for part in untracked.stdout.split("\0") if part)
    return changed


def current_reference_anchors(layout: paths.Layout, unit: str) -> list[dict[str, Any]]:
    """The anchors that currently represent ``unit``: the branch work dir
    when present, else the newest saved version on any branch -- regardless
    of whether that version's anchors are still valid. Staleness itself is
    what ``stale``/``status``/``uncovered`` need to detect, so the anchor
    source must not be pre-filtered to only-valid versions."""
    unit_dir = layout.work_dir(unit)
    if unit_dir.exists():
        return manifest_mod.load_anchors(unit_dir)
    newest = newest_version(layout, unit)
    return version_anchors(layout, unit, newest["id"]) if newest else []


def all_known_units(layout: paths.Layout) -> set[str]:
    units = set(load_index(layout).get("units", {}).keys())
    work_root = layout.repo_dir / "work"
    if work_root.exists():
        for branch_dir in work_root.iterdir():
            if branch_dir.is_dir():
                units.update(entry.name for entry in branch_dir.iterdir() if entry.is_dir())
    return units


def stale_units(layout: paths.Layout, base_ref: str | None) -> list[dict[str, Any]]:
    changed = changed_paths_since(layout.workspace, base_ref) if base_ref else None
    stale: list[dict[str, Any]] = []
    for unit in sorted(all_known_units(layout)):
        unit_anchors = current_reference_anchors(layout, unit)
        if not unit_anchors:
            continue
        if changed is not None and not ({normalize_repo_path(a["path"]) for a in unit_anchors} & changed):
            continue
        checks = [anchors_mod.check_anchor(layout.workspace, a) for a in unit_anchors]
        bad = [c for c in checks if c["status"] != "unchanged"]
        if bad:
            stale.append({"unit": unit, "anchors": bad})
    return stale


_HUNK_RE = re.compile(r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@")


def _line_count(text: str) -> int:
    """Count of newline-terminated lines in ``text``, splitting only on a literal ``\\n`` --
    never ``str.splitlines``, which also treats other Unicode/control bytes (e.g. a literal
    ``\\x0c`` form feed) as line boundaries. Every other line-count in this module must agree
    with git's own convention (only ``\\n`` ends a line) or a body-line skip count computed from
    a hunk header's line totals falls out of sync with this function's result. An empty string
    counts as one (empty) line -- the minimum a hunk range can ever need."""
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    return len(lines) or 1


def _strip_trailing_tab(raw: str) -> str:
    """Drop exactly one trailing ``\\t`` git appends to a `---`/`+++` header when the path
    contains a space (e.g. ``"foo bar.py\\t"``) -- a path without a space never gets this tab, so
    stripping more than one would eat a real trailing tab byte that was itself quoted."""
    return raw[:-1] if raw.endswith("\t") else raw


def _unquote_git_path(raw: str) -> str:
    """Undo git's C-style path quoting (``"weird\\303\\251.py"``): applied to a path with a
    special/control byte (a literal quote, backslash, tab, or newline) even under
    ``core.quotePath=false`` -- that setting only stops quoting for an otherwise-plain non-ASCII
    path. A path that was never quoted (no wrapping double quotes) passes through unchanged."""
    if len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
        return raw
    body = raw[1:-1]
    simple_escapes = {"n": 10, "t": 9, "\\": 92, '"': 34}
    result = bytearray()
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body):
            nxt = body[index + 1]
            if nxt in "01234567":
                octal = body[index + 1 : index + 4]
                result.append(int(octal, 8))
                index += 4
                continue
            if nxt in simple_escapes:
                result.append(simple_escapes[nxt])
                index += 2
                continue
        result.extend(char.encode("utf-8"))
        index += 1
    return bytes(result).decode("utf-8", "surrogateescape")


def _untracked_hunks(workspace: Path) -> list[dict[str, Any]]:
    """Every untracked-but-not-ignored file, reported as one whole-file hunk:
    it has no committed baseline to diff against, so its entire content
    counts as changed (mirrors the untracked-file handling in
    ``manifest.snapshot_id``). Fails *closed*: a listing that cannot run at all (missing git, a
    timeout, a non-git workspace) must never be read as "no untracked files" -- ``catalog
    uncovered`` refuses (exit 2) per catalog.md's fail-closed git-plumbing rule, the same as a
    failed ``git diff``/``git ls-files`` elsewhere in this module."""
    result = run(["git", "ls-files", "-z", "-o", "--exclude-standard"], cwd=workspace, timeout=30)
    if result.returncode != 0:
        raise CliError(
            f"`git ls-files` failed (exit {result.returncode}); refusing to compute uncovered hunks from an "
            "incomplete untracked-file list.",
            code=2,
        )
    hunks: list[dict[str, Any]] = []
    for rel in sorted(part for part in result.stdout.split("\0") if part):
        file_path = workspace / rel
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        line_count = _line_count(text)
        hunks.append({"path": rel, "start": 1, "end": line_count})
    return hunks


def diff_hunks(workspace: Path, base_ref: str) -> list[dict[str, Any]]:
    merge_base = run(["git", "merge-base", base_ref, "HEAD"], cwd=workspace, timeout=15)
    if merge_base.returncode != 0:
        raise CliError(f"Cannot resolve merge-base for {base_ref}.", code=2)
    # `-c core.quotePath=false`: stops an otherwise-plain non-ASCII path from being C-quoted, but
    # a path with an actual special byte (a literal quote, backslash, tab, or newline) is still
    # quoted regardless -- `_unquote_git_path` below decodes that remaining quoted form.
    # `--no-renames`: matches `changed_paths_since`'s own flag -- overrides a repo-local
    # `diff.renames`/`diff.renameLimit` config so a renamed-and-edited file is always reported as
    # a deletion of the old path plus an addition of the new one, never collapsed under one path
    # (which would drop the old path's `deleted_file` coverage entirely). `--no-color`/
    # `--no-ext-diff`: a repo-local `color.diff`/`diff.external` config must never inject ANSI
    # escapes or a third-party diff tool's own output format into the text parsed below.
    # `--src-prefix=a/ --dst-prefix=b/`: pins the header prefixes the parsing below strips
    # (`raw.startswith("a/")`/`"b/"`) -- a repo-local `diff.mnemonicPrefix` (`i/`/`w/`) or
    # `diff.noprefix` (no prefix at all) config would otherwise change or remove them, leaving the
    # stripped prefix stuck in the reported path.
    # `--inter-hunk-context=0`: overrides a repo-local `diff.interHunkContext` config -- with
    # `--unified=0`, a fused hunk's header `old_count`/`new_count` each include the fused-in
    # context lines, but those context lines are printed only once (not once per side), so
    # `remaining_body_lines` below (computed as `old_count + count`) would overcount the real
    # printed body and skip past the true end of the hunk into whatever text follows (the next
    # file's own header/hunks), corrupting parsing for every file after the fused one.
    # `--no-textconv`: a repo-local `diff.<driver>.textconv` (via a `.gitattributes`/
    # `.git/info/attributes` `diff=<driver>` assignment) rewrites the compared text (e.g.
    # prepending banner lines) before git computes line numbers against it -- the hunk ranges
    # parsed below must always describe the real file's own line numbers, never a textconv-
    # rewritten view of it.
    diff = run(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--no-renames",
            "--no-color",
            "--no-ext-diff",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            "--unified=0",
            "--inter-hunk-context=0",
            "--no-textconv",
            merge_base.stdout.strip(),
        ],
        cwd=workspace,
        timeout=60,
    )
    if diff.returncode != 0:
        raise CliError(f"`git diff` failed (exit {diff.returncode}) computing hunks against {base_ref}.", code=2)
    hunks: list[dict[str, Any]] = []
    current_path: str | None = None
    old_path: str | None = None
    whole_file_deletion = False
    # Number of upcoming lines that are hunk *body* content (the `old_count + new_count` lines
    # git prints immediately after an `@@ ... @@` header) rather than a file header or the next
    # hunk header -- skipped from header/hunk detection below so a body line whose own added text
    # happens to start with `+++ `/`--- ` (e.g. an added line `++ x`, printed by git as `+++ x`)
    # is never misread as the next file's header.
    remaining_body_lines = 0
    # `.split("\n")` only (never `str.splitlines`): a body line containing a literal `\x0c` must
    # still count as one line here, or `remaining_body_lines` (derived from git's own line
    # totals, which also only count `\n`) falls out of sync with the real header/hunk boundaries.
    for line in diff.stdout.split("\n"):
        if remaining_body_lines > 0:
            remaining_body_lines -= 1
            continue
        if line.startswith("--- "):
            # Git appends one literal trailing tab to `---`/`+++` when the path itself contains a
            # space, so the tab survives even `core.quotePath=false` -- strip exactly one before
            # unquoting, or it becomes part of the reported path.
            raw = _unquote_git_path(_strip_trailing_tab(line[4:]))
            old_path = None if raw == "/dev/null" else (raw[2:] if raw.startswith("a/") else raw)
            continue
        if line.startswith("+++ "):
            raw = _unquote_git_path(_strip_trailing_tab(line[4:]))
            whole_file_deletion = raw == "/dev/null"
            current_path = None if whole_file_deletion else (raw[2:] if raw.startswith("b/") else raw)
            continue
        match = _HUNK_RE.match(line)
        if not match:
            continue
        old_count = int(match.group("old_count") or "1")
        count = int(match.group("count") or "1")
        remaining_body_lines = old_count + count
        if whole_file_deletion:
            # The new side is `/dev/null`: the whole file is gone, not merely one hunk of it --
            # report it once, under the *old* path (there is no new path to report it under),
            # `deleted_file: true`; `uncovered_hunks` treats coverage here as "did any unit
            # anchor this path at all", not a line-range overlap (there is no surviving range).
            if old_path is not None:
                hunks.append({"path": old_path, "start": 1, "end": max(old_count, 1), "deleted_file": True})
            continue
        if not current_path:
            continue
        start = int(match.group("start"))
        if count == 0:
            # A pure deletion contributes no new-side lines, so it cannot be reported as a
            # normal [start, end] range -- but the deleted content (e.g. a removed guard) is
            # still real changed content. `start` (git's own convention for a `+N,0` hunk) is
            # the last surviving new-file line *before* the gap; the gap is represented as the
            # existing neighbor line(s) that actually straddle it: both `start` and `start + 1`
            # when the deletion is inside the file, clamped to whichever single line remains
            # when the deletion sits at either edge (line 0 = before the first line, or past the
            # current last line) -- an anchor must cover every one of those surviving neighbors
            # to count as spanning the deletion, not merely touch one adjacent line.
            file_path = workspace / current_path
            try:
                line_count = _line_count(file_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                line_count = start + 1
            clamped_start = max(start, 1)
            clamped_end = min(start + 1, line_count) if line_count > 0 else clamped_start
            hunks.append({"path": current_path, "start": clamped_start, "end": clamped_end, "deletion": True})
            continue
        hunks.append({"path": current_path, "start": start, "end": start + count - 1})
    hunks += _untracked_hunks(workspace)
    return hunks


def uncovered_hunks(layout: paths.Layout, base_ref: str) -> list[dict[str, Any]]:
    hunks = diff_hunks(layout.workspace, base_ref)
    anchors_by_path: dict[str, list[tuple[int, int]]] = {}
    anchored_paths: set[str] = set()
    for unit in sorted(all_known_units(layout)):
        for anchor in current_reference_anchors(layout, unit):
            # Every anchored path, regardless of its current check status -- a whole-file
            # deletion's `deleted_file` hunk below is covered by "some unit anchors this path at
            # all", including an anchor that (correctly) now reports `missing` because its file
            # is gone.
            anchored_paths.add(anchor["path"])
            check = anchors_mod.check_anchor(layout.workspace, anchor)
            if check["status"] != "unchanged":
                # An edited/missing anchor no longer reliably covers any
                # location in the current tree -- its stored line numbers
                # would misreport coverage.
                continue
            start = check.get("start", anchor["start"])
            end = check.get("end", anchor["end"])
            anchors_by_path.setdefault(anchor["path"], []).append((start, end))
    uncovered = []
    for hunk in hunks:
        if hunk.get("deleted_file"):
            # There is no surviving line range to overlap at all -- the whole file is gone, so
            # coverage means only "did some unit anchor this path", never a range comparison.
            covered = hunk["path"] in anchored_paths
        else:
            ranges = anchors_by_path.get(hunk["path"], [])
            if hunk.get("deletion"):
                # A deletion hunk has no content of its own to "overlap" -- an ordinary overlap
                # check would let an anchor that merely touches one side of the gap (e.g. an
                # anchor ending exactly at `start`) count as covering content it never actually
                # included. Require the anchor to genuinely straddle the gap instead.
                covered = any(r_start <= hunk["start"] and r_end >= hunk["end"] for r_start, r_end in ranges)
            else:
                covered = any(not (hunk["end"] < r_start or hunk["start"] > r_end) for r_start, r_end in ranges)
        if not covered:
            uncovered.append(hunk)
    return uncovered


def _every_required_stage_passed(manifest: dict[str, Any], audit_receipt: dict[str, Any]) -> bool:
    """``verified:true`` requires every stage the unit's tier requires to be
    present in the receipt with status ``pass`` (design units' ``replay`` is
    ``n/a`` instead). Reading the receipt's own ``verdict`` is not enough: a
    verdict of ``pass`` can also come from the audit's own
    ``--allow-unverified-conformance`` leniency, which must not silently
    satisfy the catalog's own ``--allow-unverified`` gate."""
    tier = manifest.get("tier", "F2")
    design = bool(manifest.get("design"))
    required = audit_mod.required_stages(tier, None)
    stages = audit_receipt.get("stages", {})
    for name in required:
        status = stages.get(name, {}).get("status")
        if name == "replay" and design:
            if status != "n/a":
                return False
            continue
        if status != "pass":
            return False
    return True


def save_version(layout: paths.Layout, unit: str, unit_dir: Path, allow_unverified: bool) -> dict[str, Any]:
    manifest = manifest_mod.load_manifest(unit_dir)
    snapshot = manifest_mod.snapshot_id(layout.workspace, unit_dir)
    audit_path = unit_dir / "receipts" / snapshot / "audit.json"
    verified = False
    if audit_path.exists():
        verified = _every_required_stage_passed(manifest, read_json(audit_path))
    if not verified and not allow_unverified:
        raise CliError(
            f"No passing audit for snapshot {snapshot}. Run `,formal audit {unit}` or pass --allow-unverified.",
            code=1,
        )
    version_id = manifest_mod.version_id_for_unit(unit_dir)
    destination = layout.version_dir(unit, version_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.parent / f".{version_id}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    # Stage the complete immutable payload before taking the shared save/GC lock. Publication and
    # the index update then happen together under that lock, while an already-published content ID
    # is left untouched. Cleanup begins before the copy so partial copies and metadata failures
    # cannot leave unindexed staging directories behind.
    try:
        shutil.copytree(unit_dir, staged, ignore=manifest_mod.copytree_ignore(unit_dir))
        ensure_repo_json(layout)
        branch_key = paths.branch_slug(layout.workspace)
        branch = paths.current_branch(layout.workspace)
        if branch is None:
            branch = f"detached@{paths.head_commit(layout.workspace) or 'unknown'}"
        record = {
            "id": version_id,
            # Microseconds kept (never truncated to whole seconds): two saves that land in the same
            # wall-clock second must still be tell-apart-able for display, even though ordering
            # itself is decided by `seq` below, not by this timestamp.
            "created": datetime.now(timezone.utc).isoformat(),
            "branch": branch,
            "commit": manifest.get("source_commit"),
            "anchors_file": manifest_mod.ANCHORS_NAME,
            "verified": verified,
        }

        def _mutate(index: dict[str, Any]) -> None:
            unit_entry = index.setdefault("units", {}).setdefault(unit, {"versions": [], "work": []})
            previous = next((v for v in unit_entry["versions"] if v["id"] == version_id), None)
            associations = _version_branches(previous) if previous is not None else {}
            # Global sequence orders cross-branch fallback and GC. Each membership stores the
            # sequence of this branch's own latest save so another branch cannot change its choice.
            next_seq = max((v.get("seq", 0) for v in unit_entry["versions"]), default=0) + 1
            record["seq"] = next_seq
            record["branches"] = {**associations, branch_key: next_seq}
            if not destination.exists():
                os.replace(staged, destination)
            unit_entry["versions"] = [v for v in unit_entry["versions"] if v["id"] != version_id] + [record]
            if branch_key not in unit_entry["work"]:
                unit_entry["work"].append(branch_key)

        update_index(layout, _mutate)
        return record
    finally:
        shutil.rmtree(staged, ignore_errors=True)


_KIT_TMP_GLOB = ".*.tmp.*"


def _kit_owner_alive(handle: Any) -> bool:
    """True if any pending owner recorded under the held kit lock is still running."""
    for pid in leankit.pending_owner_pids(handle):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            # A live process we don't have permission to signal -- still alive, still potentially
            # referencing this kit.
            return True
        except (OSError, OverflowError):
            continue
        return True
    return False


def gc(layout: paths.Layout, keep: int) -> dict[str, Any]:
    """Drop old saved versions beyond ``keep``, then sweep ``_kit/`` for orphan kit dirs.

    A kit dir is *never* removed while: it is named like `leankit.ensure_kit`'s own in-progress
    temp copy (``_KIT_TMP_GLOB``, e.g. ``.<hash>.tmp.<uuid>``, matched by name so a concurrent
    `ensure_kit`'s partially-copied sibling is never raced even before it takes its own lock);
    some repo's MANIFEST.json or lakefile.toml still references its hash (``_live_kit_hashes``);
    `ensure_kit` currently holds its per-kit-hash lock (``leankit.kit_lock``, taken here
    non-blocking -- a contended lock means a copy/replace is actively in flight right now); or the
    pending owner recorded in that same lock file is still alive (``_kit_owner_alive`` -- covers
    the later window described there, after ``ensure_kit`` released the lock but before each
    caller's own MANIFEST/lakefile write, which this module cannot observe directly, has landed).
    Together these make `gc` agree with `ensure_kit` without requiring any change to
    `manifest.init_unit` (owned by another packet)."""
    removed_versions: list[dict[str, Any]] = []

    def _mutate(index: dict[str, Any]) -> None:
        for unit, entry in index.get("units", {}).items():
            versions = sorted(entry.get("versions", []), key=_by_seq, reverse=True)
            keepers, drop = versions[:keep], versions[keep:]
            for version in drop:
                version_dir = layout.version_dir(unit, version["id"])
                if version_dir.exists():
                    shutil.rmtree(version_dir)
                removed_versions.append({"unit": unit, "id": version["id"]})
            entry["versions"] = keepers

    update_index(layout, _mutate)

    removed_kits: list[str] = []
    kit_root = layout.root / "_kit"
    if kit_root.exists():
        for kit_dir in kit_root.iterdir():
            if not kit_dir.is_dir():
                continue
            if fnmatch.fnmatch(kit_dir.name, _KIT_TMP_GLOB):
                continue
            with leankit.kit_lock(kit_dir, blocking=False) as handle:
                if handle is None:
                    continue
                # Liveness (manifest/lakefile references, and the owner pid) is decided here,
                # while this kit's lock is held -- never from a snapshot taken before this loop
                # started -- so a concurrent `ensure_kit` that finishes (writes its MANIFEST.json
                # or lakefile.toml reference) after `gc` began is still seen as live.
                if kit_dir.name in _live_kit_hashes(layout.root):
                    continue
                if _kit_owner_alive(handle):
                    continue
                shutil.rmtree(kit_dir)
                removed_kits.append(kit_dir.name)
    return {"removed_versions": removed_versions, "removed_kits": removed_kits}


_NON_REPO_ROOT_DIRS = {"_kit", "_worktrees", "_exports"}
_KIT_PATH_RE = re.compile(r"_kit[/\\]([0-9a-f]+)")


def _live_kit_hashes(state_root: Path) -> set[str]:
    """A ``_kit/<hash>`` dir is live if *any* repo under the shared state
    root (not just the current one -- ``_kit`` is a root-level, cross-repo
    cache) still references it, from either a work dir or a saved version.
    Both the MANIFEST ``kit_hash`` field and the ``lakefile.toml`` require
    path are scanned so a manifest that drifted from its lakefile does not
    cause a live kit to be dropped."""
    live: set[str] = set()
    if not state_root.exists():
        return live
    for repo_dir in state_root.iterdir():
        if not repo_dir.is_dir() or repo_dir.name in _NON_REPO_ROOT_DIRS:
            continue
        for manifest_file in repo_dir.rglob(manifest_mod.MANIFEST_NAME):
            try:
                manifest = read_json(manifest_file)
            except CliError:
                continue
            kit_hash = manifest.get("kit_hash")
            if kit_hash:
                live.add(kit_hash)
        for lakefile in repo_dir.rglob("lakefile.toml"):
            try:
                text = lakefile.read_text(encoding="utf-8")
            except OSError:
                continue
            live.update(match.group(1) for match in _KIT_PATH_RE.finditer(text))
    return live
