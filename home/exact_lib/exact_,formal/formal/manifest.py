"""Unit work-dir lifecycle: MANIFEST.json, ANCHORS.json, init, and content
hashes (snapshot id for the current tree, version id for a saved unit)."""

from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path
from typing import Any, Callable

from . import leankit, paths
from .util import CliError, read_json, run_raw, sha256_hex, short_hash, write_json

MANIFEST_NAME = "MANIFEST.json"
ANCHORS_NAME = "ANCHORS.json"
# Runtime/build artifacts never hashed into a snapshot or version id, and never copied into a
# saved catalog version. `EXCLUDED_DIRS` names are excluded only at the *top level* of the unit
# dir (a nested dir that happens to share one of these names is real unit content);
# `EXCLUDED_FILES` are excluded by basename at any depth. `copytree_ignore` below and
# `unit_files_for_hash` are the single shared application of this rule -- a saved version's
# copied content must never diverge from what was hashed to produce its version id.
EXCLUDED_DIRS = {"receipts", "traces", ".lake", "tmp"}
EXCLUDED_FILES = {"lake-manifest.json"}
# The exact two MANIFEST.json fields `init_unit`/`checkout_version` overwrite with the current
# branch/HEAD on every init/checkout. `catalog.checkout_version`'s dirty guard already excludes
# these two from its own MANIFEST comparison under a private name; this shared constant and
# `manifest_digest_excluding_checkout_fields` are the same normalization applied to a saved
# version's id (see `version_id_for_unit`), so identical unit content saved on different
# branches/commits still gets the same version id.
CHECKOUT_REWRITTEN_MANIFEST_KEYS = ("branch", "source_commit")


def manifest_path(unit_dir: Path) -> Path:
    return unit_dir / MANIFEST_NAME


def anchors_path(unit_dir: Path) -> Path:
    return unit_dir / ANCHORS_NAME


def load_manifest(unit_dir: Path) -> dict[str, Any]:
    path = manifest_path(unit_dir)
    if not path.exists():
        raise CliError(f"No unit at {unit_dir}. Run `,formal init` first.", code=2)
    return read_json(path)


def save_manifest(unit_dir: Path, manifest: dict[str, Any]) -> None:
    write_json(manifest_path(unit_dir), manifest)


def load_anchors(unit_dir: Path) -> list[dict[str, Any]]:
    path = anchors_path(unit_dir)
    if not path.exists():
        return []
    return read_json(path).get("anchors", [])


def save_anchors(unit_dir: Path, anchors: list[dict[str, Any]]) -> None:
    write_json(anchors_path(unit_dir), {"anchors": anchors})


def next_anchor_id(anchors: list[dict[str, Any]]) -> str:
    highest = 0
    for anchor in anchors:
        value = str(anchor.get("id", ""))
        if value.startswith("A"):
            try:
                highest = max(highest, int(value[1:]))
            except ValueError:
                continue
    return f"A{highest + 1}"


def init_unit(
    layout: paths.Layout,
    unit: str,
    tier: str,
    design: bool,
    from_version: str | None,
) -> Path:
    unit_dir = layout.work_dir(unit)
    if unit_dir.exists() and any(unit_dir.iterdir()):
        raise CliError(f"Unit work dir already exists and is not empty: {unit_dir}", code=2)
    unit_dir.mkdir(parents=True, exist_ok=True)

    if from_version:
        source = layout.version_dir(unit, from_version)
        if not source.exists():
            raise CliError(f"No saved version {from_version} for unit {unit}: {source}", code=2)
        shutil.copytree(source, unit_dir, dirs_exist_ok=True)
        manifest = load_manifest(unit_dir)
        manifest["repo_id"] = layout.repo_id
        manifest["branch"] = paths.current_branch(layout.workspace) or paths.branch_slug(layout.workspace)
        manifest["source_commit"] = paths.head_commit(layout.workspace) or ""
        save_manifest(unit_dir, manifest)
        return unit_dir

    kit_hash = leankit.ensure_kit(layout)
    values = {
        "KIT_PATH": str(layout.kit_dir(kit_hash)),
        "UNIT": unit,
        "TIER": tier,
        "DESIGN": "true" if design else "false",
        "REPO_ID": layout.repo_id,
        "BRANCH": paths.current_branch(layout.workspace) or paths.branch_slug(layout.workspace),
        "SOURCE_COMMIT": paths.head_commit(layout.workspace) or "",
        "KIT_HASH": kit_hash,
    }
    leankit.copy_template(unit_dir, values)

    manifest_file = manifest_path(unit_dir)
    manifest = read_json(manifest_file) if manifest_file.exists() else {}
    manifest.setdefault("unit", unit)
    manifest["tier"] = tier
    manifest["design"] = design
    manifest["repo_id"] = layout.repo_id
    manifest["branch"] = values["BRANCH"]
    manifest["source_commit"] = values["SOURCE_COMMIT"]
    manifest["toolchain"] = paths.PINNED_TOOLCHAIN
    manifest["kit_hash"] = kit_hash
    manifest.setdefault("adapter", None)
    manifest.setdefault("budgets", {"max_states": 100000, "max_depth": None})
    manifest.setdefault("abstractions", [])
    manifest.setdefault("unmodeled", [])
    # `--against` differential replay stays refused (exit 2) until the unit's own MANIFEST
    # explicitly opts in (see `cli.cmd_replay`); the template ships the same default.
    manifest.setdefault("replay", {"differential": False})
    save_manifest(unit_dir, manifest)
    return unit_dir


def _excluded_top_level(rel: Path) -> bool:
    return bool(rel.parts) and rel.parts[0] in EXCLUDED_DIRS


def unit_files_for_hash(unit_dir: Path) -> list[tuple[str, str]]:
    entries = []
    for path in sorted(unit_dir.rglob("*")):
        if path.is_symlink() and path.is_dir():
            raise CliError(f"Symlinked directories are not allowed in a formal unit: {path}", code=2)
        if not path.is_file():
            continue
        rel = path.relative_to(unit_dir)
        if _excluded_top_level(rel):
            continue
        if rel.name in EXCLUDED_FILES:
            continue
        entries.append((str(rel), sha256_hex(path.read_bytes())))
    return entries


def copytree_ignore(source_root: Path) -> Callable[[str, list[str]], set[str]]:
    """``shutil.copytree``'s ``ignore`` callback for copying a unit dir into a saved catalog
    version -- applies the exact same rule as ``unit_files_for_hash`` (``EXCLUDED_DIRS`` only at
    the unit dir's top level, ``EXCLUDED_FILES`` by basename at any depth). ``ignore_patterns``
    alone cannot express this: it matches every name at every recursion depth, which would drop
    a nested directory that merely shares one of these names (real unit content) and let a
    saved version's copied content silently diverge from what was hashed to produce its
    version id."""
    source_root = Path(source_root)

    def _ignore(directory: str, names: list[str]) -> set[str]:
        skip = {name for name in names if name in EXCLUDED_FILES}
        if Path(directory) == source_root:
            skip |= {name for name in names if name in EXCLUDED_DIRS}
        return skip

    return _ignore


def manifest_digest_excluding_checkout_fields(path: Path) -> str:
    """sha256 hex of ``path``'s MANIFEST.json content with ``CHECKOUT_REWRITTEN_MANIFEST_KEYS``
    removed first, so a checkout/branch switch that rewrites only those fields never changes the
    digest."""
    manifest = read_json(path)
    for key in CHECKOUT_REWRITTEN_MANIFEST_KEYS:
        manifest.pop(key, None)
    return sha256_hex(json.dumps(manifest, sort_keys=True).encode("utf-8"))


def version_id_for_unit(unit_dir: Path) -> str:
    """First 16 hex of sha256 over sorted (relative path, file sha256), with MANIFEST.json's own
    entry replaced by ``manifest_digest_excluding_checkout_fields`` -- ``branch``/
    ``source_commit`` are excluded from the hash so the same unit content saved from two
    different branches or commits still produces the same version id."""
    entries = unit_files_for_hash(unit_dir)
    manifest_file = manifest_path(unit_dir)
    if manifest_file.exists():
        manifest_digest = manifest_digest_excluding_checkout_fields(manifest_file)
        entries = [(rel, manifest_digest if rel == MANIFEST_NAME else digest) for rel, digest in entries]
    payload = "\n".join(f"{rel}:{digest}" for rel, digest in entries)
    return short_hash(payload.encode("utf-8"))


def _extra_snapshot_entries(unit_dir: Path, workspace: Path) -> list[tuple[str, str]]:
    """Every anchored file, plus any file the adapter command names directly, hashed by path --
    regardless of git/gitignore status. ``git diff``/``git ls-files --exclude-standard`` never
    report a gitignored file's content (or even its presence), so without this an anchored file
    or adapter script that happens to be gitignored could change with no effect on the snapshot
    id at all."""
    seen: dict[str, str] = {}
    for anchor in load_anchors(unit_dir):
        candidate = workspace / anchor["path"]
        if candidate.is_file():
            seen.setdefault(str(candidate.resolve()), sha256_hex(candidate.read_bytes()))
    manifest_file = manifest_path(unit_dir)
    if manifest_file.exists():
        adapter = read_json(manifest_file).get("adapter") or {}
        cmd = adapter.get("cmd") or ""
        for token in shlex.split(cmd) if cmd else []:
            for base in (workspace, unit_dir):
                candidate = base / token
                if candidate.is_file():
                    seen.setdefault(str(candidate.resolve()), sha256_hex(candidate.read_bytes()))
                    break
    return sorted(seen.items())


def _diff_target(workspace: Path) -> str:
    """``HEAD`` when it resolves to a real commit; otherwise (a repo with no commits yet --
    an "unborn" branch) the empty tree's object id, computed with ``git hash-object -t tree
    /dev/null`` so it matches the repo's own hash algorithm (sha1 or sha256) -- git recognizes
    this well-known empty-tree id as a diff target even though nothing ever writes it into the
    object database. ``git rev-parse --verify -q HEAD`` is the resolution check: ``-q`` means a
    HEAD that does not resolve exits non-zero with no stderr noise, so this never has to
    pattern-match git's error text. Any failure past this point (missing git, a timeout) still
    hits ``snapshot_id``'s own fail-closed ``diff_result.returncode`` check below via the
    ``git diff`` call itself."""
    head_check = run_raw(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=workspace, timeout=30)
    if head_check.returncode == 0:
        return "HEAD"
    empty_tree = run_raw(["git", "hash-object", "-t", "tree", "/dev/null"], cwd=workspace, timeout=30)
    if empty_tree.returncode != 0:
        raise CliError(
            f"`git hash-object -t tree /dev/null` failed (exit {empty_tree.returncode}); refusing to "
            "compute a snapshot with no resolvable HEAD and no empty-tree fallback.",
            code=2,
        )
    return empty_tree.stdout.decode("utf-8", "surrogateescape").strip()


def snapshot_id(workspace: Path, unit_dir: Path) -> str:
    """First 16 hex of sha256 over (unit file hashes, HEAD commit, whole-repo diff against HEAD
    or -- in a repo with no commits yet -- the empty tree (see ``_diff_target``), the contents
    of every untracked-but-not-ignored file, and every anchored/adapter file hashed directly by
    path). Anchored paths are not singled out in the diff/untracked halves: an anchor's coverage
    can shift (see ``anchors.check_anchor``), and any repo change -- tracked or untracked,
    anchored or not -- must invalidate a cached audit receipt. The git plumbing here fails
    *closed*: a ``git diff``/``git ls-files`` that cannot run (missing git, a timeout, a non-git
    workspace) must never be read as "no changes" -- it raises instead of silently computing a
    snapshot from incomplete information."""
    entries = unit_files_for_hash(unit_dir)
    head = paths.head_commit(workspace) or ""
    diff_target = _diff_target(workspace)
    # `--no-ext-diff`/`--no-textconv`: a repo-local `diff.external`/`diff.<driver>.textconv`
    # config must never substitute a third-party program's own output for git's raw diff bytes
    # -- that would change what gets hashed below with no real file content change, so the
    # snapshot id could go stale (or fail to change) independent of the actual working tree.
    # `--no-color`: strips a repo-local `color.diff` config's ANSI escapes out of the hashed
    # bytes. `--no-renames`: keeps a renamed-and-edited file's full add+delete diff content in
    # the hash rather than a compact rename entry (matches `catalog.diff_hunks`'s own flag).
    diff_result = run_raw(
        ["git", "diff", diff_target, "--binary", "--no-ext-diff", "--no-textconv", "--no-color", "--no-renames"],
        cwd=workspace,
        timeout=30,
    )
    if diff_result.returncode != 0:
        raise CliError(
            f"`git diff {diff_target} --binary` failed (exit {diff_result.returncode}); refusing to "
            "compute a snapshot from an incomplete diff.",
            code=2,
        )
    diff_sha = sha256_hex(diff_result.stdout)
    # `-z` NUL-separates entries with no quoting, so a non-ASCII/non-UTF-8 filename is not
    # C-style-quoted (and thus missed by a later `workspace / rel` lookup) the way plain
    # `ls-files` output would quote it.
    untracked_result = run_raw(["git", "ls-files", "-z", "-o", "--exclude-standard"], cwd=workspace, timeout=30)
    if untracked_result.returncode != 0:
        raise CliError(
            f"`git ls-files` failed (exit {untracked_result.returncode}); refusing to compute a "
            "snapshot from an incomplete untracked-file list.",
            code=2,
        )
    untracked_payload = bytearray()
    for rel_bytes in sorted(part for part in untracked_result.stdout.split(b"\0") if part):
        file_path = workspace / rel_bytes.decode("utf-8", "surrogateescape")
        if file_path.is_file():
            file_digest = bytes.fromhex(sha256_hex(file_path.read_bytes()))
            untracked_payload += len(rel_bytes).to_bytes(8, "big") + rel_bytes + file_digest
    untracked_sha = sha256_hex(bytes(untracked_payload))
    extra_entries = _extra_snapshot_entries(unit_dir, workspace)
    extra_sha = sha256_hex("\n".join(f"{path}:{digest}" for path, digest in extra_entries).encode("utf-8"))
    payload = (
        "\n".join(f"{rel}:{digest}" for rel, digest in entries)
        + f"\nHEAD:{head}\nDIFF:{diff_sha}\nUNTRACKED:{untracked_sha}\nEXTRA:{extra_sha}"
    )
    return short_hash(payload.encode("utf-8"))
