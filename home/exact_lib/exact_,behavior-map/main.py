#!/usr/bin/env python3
"""Per-repo behavior map for agents: base entries plus per-branch overlays.

Storage under $AGENT_BEHAVIOR_MAP_DIR (default ~/.local/share/k-ai-behavior-map)/<repo>/:

    base/<area>/<name>.md                 behavior on the default branch
    branches/<slug>/<area>/<name>.md      one branch's changes (`status: removed` marks a deletion)
    branches/<slug>/<area>/<name>.base.md the base entry the branch started from (three-way merge input)
    branches/<slug>/<area>/<name>.merge.md promote conflict output, waiting for `resolve`
    branches/<slug>/.branch               branch name and the commit the overlay started at

<repo> is the basename of the main checkout, so every worktree of a repo shares one map.
Every write takes a repo lock; `save` also refuses when the entry changed since it was read.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STATE_RE = re.compile(r"^\S+ --\S+--> \S+$")
HEADER_RE = re.compile(r"^<!-- behavior-map id=(\S+) layer=(\S+) hash=([0-9a-f]+)(?: flags=(\S*))? -->$")
LABEL_RE = re.compile(r"^(Trigger|Expect|Must not|Gotchas):\s+\S")
FIELDS = ("id", "status", "anchors", "verify", "verified_date", "fingerprint", "states")
STATUSES = ("verified", "unverified", "removed")
REQUIRED_LABELS = ("Trigger", "Expect")
MAX_ANCHORS = 3
MAX_BODY_BYTES = 1200
AREA_SOFT_LIMIT = 15
LOCK_TIMEOUT = 10.0
LOCK_STALE_AFTER = 60.0
PROBLEM_FLAGS = ("invalid", "broken", "stale", "drift", "conflict", "unverified")


class MapError(Exception):
    """A user-facing failure; main() prints it and exits 1."""


# ---------------------------------------------------------------- git


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise MapError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def git_ok(*args: str, cwd: Path | None = None) -> bool:
    return subprocess.run(["git", *args], capture_output=True, cwd=cwd).returncode == 0


def ref_exists(ref: str) -> bool:
    return git_ok("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")


def detect_repo() -> str:
    common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    # A main checkout's common dir is `<repo>/.git`; a bare repo's is the repo itself.
    name = (common.parent if common.name == ".git" else common).name
    return re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-.")[:64] or "repo"


def default_branch() -> str:
    head = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], capture_output=True, text=True
    )
    if head.returncode == 0 and "/" in head.stdout:
        return head.stdout.strip().split("/", 1)[1]
    for candidate in ("main", "master", "trunk"):
        if git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"):
            return candidate
    return current_branch() or "main"


def current_branch() -> str | None:
    result = subprocess.run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() or None if result.returncode == 0 else None


def branch_slug(branch: str) -> str:
    cleaned = re.sub(r"[^a-z0-9._-]+", "-", branch.lower()).strip("-.")[:48] or "branch"
    return f"{cleaned}-{hashlib.sha1(branch.encode()).hexdigest()[:6]}"


# ---------------------------------------------------------------- context


@dataclass
class Context:
    root: Path
    repo: str
    toplevel: Path
    branch: str | None
    default: str

    @property
    def on_base(self) -> bool:
        return self.branch is None or self.branch == self.default

    @property
    def base(self) -> Path:
        return self.root / "base"

    def overlay(self, branch: str | None = None) -> Path:
        name = branch or self.branch
        if name is None:
            raise MapError("detached HEAD: pass --branch to choose a layer")
        return self.root / "branches" / branch_slug(name)

    def require_branch(self) -> None:
        if self.branch is None:
            raise MapError("detached HEAD: pass --branch to choose the layer to write")

    def layer_label(self) -> str:
        return f"base ({self.default})" if self.on_base else f"branch {self.branch}"


def build_context(args: argparse.Namespace) -> Context:
    if not git_ok("rev-parse", "--git-dir"):
        raise MapError("not inside a git repository")
    store = os.environ.get("AGENT_BEHAVIOR_MAP_DIR")
    root_dir = Path(store) if store else Path.home() / ".local/share/k-ai-behavior-map"
    repo = args.repo or detect_repo()
    if not SLUG_RE.match(repo):
        raise MapError(f"invalid repo name {repo!r}")
    return Context(
        root=root_dir / repo,
        repo=repo,
        toplevel=Path(git("rev-parse", "--show-toplevel")),
        branch=args.branch or current_branch(),
        default=default_branch(),
    )


# ---------------------------------------------------------------- entries


@dataclass
class Entry:
    meta: dict[str, str | list[str]]
    body: str

    @property
    def status(self) -> str:
        value = self.meta.get("status")
        return value if isinstance(value, str) else ""

    def items(self, key: str) -> list[str]:
        value = self.meta.get(key)
        return value if isinstance(value, list) else []

    def label(self, name: str) -> str:
        for line in self.body.splitlines():
            if line.startswith(f"{name}:"):
                return line[len(name) + 1 :].strip()
        return ""


def split_id(entry_id: str) -> tuple[str, str]:
    parts = entry_id.split("/")
    if len(parts) != 2 or not all(SLUG_RE.match(part) for part in parts) or parts[1].endswith((".base", ".merge")):
        raise MapError(f"invalid id {entry_id!r}; use <area>/<name> with lowercase letters, digits, '.', '_', '-'")
    return parts[0], parts[1]


def entry_path(layer: Path, entry_id: str, suffix: str = ".md") -> Path:
    area, name = split_id(entry_id)
    return layer / area / f"{name}{suffix}"


def layer_ids(layer: Path) -> list[str]:
    if not layer.is_dir():
        return []
    ids = []
    for path in sorted(layer.glob("*/*.md")):
        if path.name.endswith((".base.md", ".merge.md")):
            continue
        ids.append(f"{path.parent.name}/{path.name[: -len('.md')]}")
    return ids


def _scalar(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return re.sub(r"(^|\s+)#(\s.*)?$", "", value)


def parse_entry(text: str) -> Entry:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise MapError("entry must start with a '---' front matter block")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise MapError("front matter has no closing '---'") from None
    meta: dict[str, str | list[str]] = {}
    key: str | None = None
    for raw in lines[1:end]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if key is None or not isinstance(meta.get(key), list):
                raise MapError(f"list item outside a list field: {raw!r}")
            meta[key].append(_scalar(stripped[2:]))  # type: ignore[union-attr]
            continue
        match = re.match(r"^([a-z_]+):(.*)$", raw)
        if not match:
            raise MapError(f"bad front matter line: {raw!r}")
        key = match.group(1)
        value = _scalar(match.group(2))
        meta[key] = value if value else []
    return Entry(meta=meta, body="\n".join(lines[end + 1 :]).strip("\n"))


def validate(entry: Entry, entry_id: str) -> list[str]:
    errors = [f"unknown field {key!r}" for key in entry.meta if key not in FIELDS]
    if entry.meta.get("id") != entry_id:
        errors.append(f"id must be {entry_id!r}")
    if entry.status not in STATUSES:
        errors.append(f"status must be one of {', '.join(STATUSES)}")
    if entry.status == "removed":
        return errors
    anchors = entry.items("anchors")
    if not 1 <= len(anchors) <= MAX_ANCHORS:
        errors.append(f"anchors: list 1-{MAX_ANCHORS} `path`, `path::symbol`, or `dir/` items")
    for anchor in anchors:
        path = anchor.split("::", 1)[0]
        if not path or path.startswith("/") or ".." in Path(path).parts:
            errors.append(f"anchor {anchor!r} must be a repo-relative path")
        elif path.endswith("/") and "::" in anchor:
            errors.append(f"anchor {anchor!r}: a directory anchor takes no symbol")
    verify = entry.meta.get("verify")
    if not isinstance(verify, str) or not verify:
        errors.append("verify: give the command (or `judgment: ...`) that proves the behavior")
    if entry.status == "verified":
        if not DATE_RE.match(str(entry.meta.get("verified_date", ""))):
            errors.append("verified_date: YYYY-MM-DD")
    if "states" in entry.meta:
        states = entry.items("states")
        bad = [item for item in states if not STATE_RE.match(item)]
        if not states or bad:
            errors.append("states: list `from --event--> to` items")
    seen: list[str] = []
    for line in entry.body.splitlines():
        if not line.strip():
            continue
        label = LABEL_RE.match(line)
        if label:
            if label.group(1) in seen:
                errors.append(f"duplicate body label {label.group(1)!r}")
            seen.append(label.group(1))
        elif not (seen and (line.startswith("  ") or line.startswith("- "))):
            errors.append(f"body line must start with Trigger:, Expect:, Must not:, or Gotchas: ({line!r})")
    errors.extend(f"body needs a {name}: line" for name in REQUIRED_LABELS if name not in seen)
    if len(entry.body.encode()) > MAX_BODY_BYTES:
        errors.append(f"body is over {MAX_BODY_BYTES} bytes; split the behavior or cut words")
    return errors


def is_removal(path: Path) -> bool:
    try:
        return path.is_file() and parse_entry(path.read_text(encoding="utf-8")).status == "removed"
    except MapError:
        return False


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def read_or_none(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")
    os.replace(tmp, path)


@contextlib.contextmanager
def repo_lock(ctx: Context) -> Iterator[None]:
    ctx.root.mkdir(parents=True, exist_ok=True)
    lock = ctx.root / ".lock"
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            with contextlib.suppress(FileNotFoundError):
                if time.time() - lock.stat().st_mtime > LOCK_STALE_AFTER:
                    lock.rmdir()
                    continue
            if time.monotonic() > deadline:
                raise MapError(f"map is locked by another session ({lock})") from None
            time.sleep(0.1)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            lock.rmdir()


# ---------------------------------------------------------------- views


@dataclass
class View:
    id: str
    path: Path
    layer: str
    entry: Entry | None
    flags: list[str] = field(default_factory=list)


def without_fingerprint(text: str | None) -> str | None:
    """Drop the machine-owned `fingerprint:` line, so a re-save alone is neither drift nor a merge conflict."""
    if text is None:
        return None
    return "".join(line for line in text.splitlines(keepends=True) if not line.startswith("fingerprint:"))


def _overlay_files_drifted(ctx: Context, overlay: Path, entry_id: str) -> bool:
    fork = read_or_none(entry_path(overlay, entry_id, ".base.md"))
    return without_fingerprint(read_or_none(entry_path(ctx.base, entry_id))) != without_fingerprint(fork)


def _anchor_flags(ctx: Context, entry: Entry) -> list[str]:
    flags: list[str] = []
    for anchor in entry.items("anchors"):
        rel, _, symbol = anchor.partition("::")
        target = ctx.toplevel / rel
        # A directory named without its trailing `/` would hash as missing and never go stale.
        missing = not target.is_dir() if rel.endswith("/") else not target.is_file()
        if missing or (symbol and target.is_file() and symbol not in target.read_text(errors="replace")):
            flags.append("broken")
    if entry.status == "verified" and entry.meta.get("fingerprint") != fingerprint(ctx, entry.items("anchors")):
        flags.append("stale")
    return sorted(set(flags))


def fingerprint(ctx: Context, anchors: list[str]) -> str:
    """Hash the content of the anchored files (every file under a `dir/` anchor), so commits alone never go stale."""
    digest = hashlib.sha256()
    for anchor in sorted(anchors):
        rel = anchor.split("::", 1)[0]
        names = [rel]
        if rel.endswith("/"):
            names = git("ls-files", "-co", "--exclude-standard", "--", rel, cwd=ctx.toplevel).splitlines()
        for name in sorted(names):
            path = ctx.toplevel / name
            digest.update(name.encode() + b"\0" + (path.read_bytes() if path.is_file() else b"<missing>") + b"\0")
    return digest.hexdigest()[:12]


def with_fingerprint(ctx: Context, text: str, entry: Entry) -> str:
    """Return the entry text with its `fingerprint:` line set from the current anchored content."""
    lines = text.splitlines()
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    head = [line for line in lines[1:end] if not line.startswith("fingerprint:")]
    stamp = f"fingerprint: {fingerprint(ctx, entry.items('anchors'))}"
    return "\n".join(["---", *head, stamp, *lines[end:]]) + "\n"


def collect_views(ctx: Context, with_anchor_checks: bool = True) -> dict[str, View]:
    views: dict[str, View] = {}
    overlay = None if ctx.on_base else ctx.overlay()
    for entry_id in layer_ids(ctx.base):
        views[entry_id] = View(entry_id, entry_path(ctx.base, entry_id), "base", None)
    if overlay is not None:
        for entry_id in layer_ids(overlay):
            views[entry_id] = View(entry_id, entry_path(overlay, entry_id), "branch", None)
    for entry_id, view in list(views.items()):
        try:
            view.entry = parse_entry(view.path.read_text(encoding="utf-8"))
            if validate(view.entry, entry_id):
                view.flags.append("invalid")
        except MapError:
            view.flags.append("invalid")
        if view.layer == "branch" and overlay is not None:
            view.flags.append("overlay")
            if _overlay_files_drifted(ctx, overlay, entry_id):
                view.flags.append("drift")
            if entry_path(overlay, entry_id, ".merge.md").exists():
                view.flags.append("conflict")
        if view.entry is not None and view.entry.status == "removed":
            del views[entry_id]
            continue
        if view.entry is not None and "invalid" not in view.flags:
            if view.entry.status == "unverified":
                view.flags.append("unverified")
            if with_anchor_checks:
                view.flags.extend(_anchor_flags(ctx, view.entry))
    return views


def overlay_dirs(ctx: Context) -> list[Path]:
    branches = ctx.root / "branches"
    return sorted(p for p in branches.iterdir() if p.is_dir()) if branches.is_dir() else []


def overlay_meta(overlay: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in (read_or_none(overlay / ".branch") or "").splitlines():
        key, _, value = line.partition("=")
        meta[key.strip()] = value.strip()
    return meta


def status_line(ctx: Context, views: dict[str, View]) -> str:
    counts = {flag: sum(flag in v.flags for v in views.values()) for flag in PROBLEM_FLAGS}
    parts = [f"behavior-map {ctx.repo}", f"layer {ctx.layer_label()}", f"{len(views)} entries"]
    parts.extend(f"{count} {flag}" for flag, count in counts.items() if count)
    if not ctx.on_base:
        parts.append(f"{sum('overlay' in v.flags for v in views.values())} from this branch")
    others = len(overlay_dirs(ctx)) - (0 if ctx.on_base or not ctx.overlay().is_dir() else 1)
    if others:
        parts.append(f"{others} other branch overlays")
    return " · ".join(parts)


def header(view: View) -> str:
    layer = "base" if view.layer == "base" else f"branch:{view.path.parents[1].name}"
    return f"<!-- behavior-map id={view.id} layer={layer} hash={file_hash(view.path)} flags={','.join(view.flags)} -->"


# ---------------------------------------------------------------- commands


def cmd_path(ctx: Context, args: argparse.Namespace) -> int:
    print(ctx.root)
    return 0


def cmd_show(ctx: Context, args: argparse.Namespace) -> int:
    views = collect_views(ctx, with_anchor_checks=not args.ids)
    if args.ids:
        print("\n".join(sorted(views)))
        return 0
    print(status_line(ctx, views))
    if not views:
        if layer_ids(ctx.base) or overlay_dirs(ctx):
            print("No entries in this view.")
        else:
            print("No entries yet. Before you change code here, map that area (k-behavior-map skill, area init).")
        return 0
    target = args.target
    if target is None:
        width = max(len(entry_id) for entry_id in views)
        for entry_id, view in sorted(views.items()):
            expect = view.entry.label("Expect") if view.entry else ""
            flags = f"[{','.join(view.flags)}] " if view.flags else ""
            print(f"{entry_id:<{width}}  {flags}{expect[:90]}")
        return 0
    selected = [v for k, v in sorted(views.items()) if k == target or k.split("/", 1)[0] == target]
    if not selected:
        raise MapError(f"no entry or area {target!r}")
    for view in selected:
        print()
        print(header(view))
        sys.stdout.write(view.path.read_text(encoding="utf-8"))
    return 0


def _read_stdin_entry(entry_id: str) -> tuple[str, str | None]:
    """Return the entry text and the hash from its `show` header; lines before the front matter are dropped."""
    lines = sys.stdin.read().splitlines(keepends=True)
    expected = None
    while lines and lines[0].strip() != "---":
        match = HEADER_RE.match(lines.pop(0).strip())
        if match:
            if match.group(1) != entry_id:
                raise MapError(f"header is for {match.group(1)!r}, not {entry_id!r}")
            expected = match.group(3)
    body = "".join(lines)
    if not body.strip():
        raise MapError("empty entry on stdin")
    return body, expected


def _check_unchanged(path: Path, expected: str | None, force: bool) -> None:
    if force:
        return
    if path.is_file():
        if expected is None:
            raise MapError(
                f"{path} exists; read it with `show <id>`, keep the header line in what you save, or pass --force"
            )
        if file_hash(path) != expected:
            raise MapError(f"{path} changed since you read it; run `show <id>` again and merge")
    elif expected is not None:
        raise MapError(f"{path} was removed since you read it")


def _start_overlay(ctx: Context, overlay: Path, entry_id: str, rebased: bool) -> None:
    """Record the base entry this branch starts from, once per entry (or again on --rebased)."""
    if overlay_meta(overlay).get("branch") is None:
        tip = f"refs/heads/{ctx.branch}" if ref_exists(f"refs/heads/{ctx.branch}") else "HEAD"
        atomic_write(overlay / ".branch", f"branch={ctx.branch}\nfork={git('rev-parse', tip)}\n")
    if entry_path(overlay, entry_id).exists() and not rebased:
        return
    fork = entry_path(overlay, entry_id, ".base.md")
    base_text = read_or_none(entry_path(ctx.base, entry_id))
    if base_text is None:
        fork.unlink(missing_ok=True)
    else:
        atomic_write(fork, base_text)


def cmd_save(ctx: Context, args: argparse.Namespace) -> int:
    ctx.require_branch()
    split_id(args.id)
    text, expected = _read_stdin_entry(args.id)
    entry = parse_entry(text)
    errors = validate(entry, args.id)
    if entry.status == "removed":
        errors.append("use `remove <id>` to delete an entry")
    if errors:
        raise MapError("invalid entry:\n  " + "\n  ".join(errors))
    with repo_lock(ctx):
        if ctx.on_base:
            target = entry_path(ctx.base, args.id)
            _check_unchanged(target, expected, args.force)
        else:
            overlay = ctx.overlay()
            target = entry_path(overlay, args.id)
            current = target if target.exists() and not is_removal(target) else entry_path(ctx.base, args.id)
            _check_unchanged(current, expected, args.force)
            _start_overlay(ctx, overlay, args.id, args.rebased)
        atomic_write(target, with_fingerprint(ctx, text, entry))
    print(target)
    return 0


def cmd_remove(ctx: Context, args: argparse.Namespace) -> int:
    ctx.require_branch()
    split_id(args.id)
    with repo_lock(ctx):
        base_entry = entry_path(ctx.base, args.id)
        if ctx.on_base:
            if not base_entry.exists():
                raise MapError(f"no base entry {args.id!r}")
            base_entry.unlink()
            print(f"removed {base_entry}")
            return 0
        overlay = ctx.overlay()
        target = entry_path(overlay, args.id)
        if not base_entry.exists():
            if not target.exists():
                raise MapError(f"no entry {args.id!r}")
            _drop_overlay_entry(overlay, args.id)
            print(f"removed {target}")
            return 0
        _start_overlay(ctx, overlay, args.id, rebased=False)
        atomic_write(target, f"---\nid: {args.id}\nstatus: removed\n---\n")
    print(f"marked {args.id} removed on branch {ctx.branch}")
    return 0


def _changed_files(ctx: Context, since: str | None) -> set[str]:
    if since is None:
        since = "HEAD"
        if not ctx.on_base:
            for target in (ctx.default, f"origin/{ctx.default}"):
                if ref_exists(target):
                    since = git("merge-base", "HEAD", target, cwd=ctx.toplevel)
                    break
    changed = git("diff", "--name-only", since, cwd=ctx.toplevel).splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard", cwd=ctx.toplevel).splitlines()
    return {path for path in (*changed, *untracked) if path}


def _repo_paths(ctx: Context, raw: list[str]) -> set[str]:
    top = ctx.toplevel.resolve()
    paths: set[str] = set()
    for item in raw:
        path = Path(item)
        full = (path if path.is_absolute() else Path.cwd() / path).resolve()
        try:
            rel = full.relative_to(top).as_posix()
        except ValueError:
            raise MapError(f"{item} is outside the repo") from None
        paths.add(f"{rel}/" if full.is_dir() and rel != "." else rel)
    return paths


def area_dirs(views: dict[str, View]) -> dict[str, set[str]]:
    """Map each area to the directories its entries claim with `path/` anchors; file anchors claim only the file."""
    areas: dict[str, set[str]] = {}
    for entry_id, view in views.items():
        if view.entry is None:
            continue
        for anchor in view.entry.items("anchors"):
            if anchor.endswith("/"):
                areas.setdefault(entry_id.split("/", 1)[0], set()).add(anchor)
    return areas


def cmd_affected(ctx: Context, args: argparse.Namespace) -> int:
    views = collect_views(ctx, with_anchor_checks=False)
    if args.paths and args.since:
        raise MapError("give planned paths or --since, not both")
    changed = _repo_paths(ctx, args.paths) if args.paths else _changed_files(ctx, args.since)
    covered: set[str] = set()
    for entry_id, view in sorted(views.items()):
        if view.entry is None:
            continue
        anchors = {anchor.split("::", 1)[0] for anchor in view.entry.items("anchors")}
        hits = sorted({p for p in changed for a in anchors if p == a or (a.endswith("/") and p.startswith(a))})
        if hits:
            covered.update(hits)
            print(f"entry {entry_id}: {', '.join(hits)}")
    for area, dirs in sorted(area_dirs(views).items()):
        hits = sorted(path for path in changed if any(path.startswith(directory) for directory in dirs))
        if hits:
            covered.update(hits)
            count = sum(entry_id.split("/", 1)[0] == area for entry_id in views)
            print(f"area {area}: {count} entries, check them with `show {area}`; changed {', '.join(hits)}")
    unmapped = sorted(changed - covered)
    if unmapped:
        dirs = {path.rstrip("/") if path.endswith("/") else Path(path).parent.as_posix() for path in unmapped}
        print(f"unmapped: {', '.join(sorted(dirs))}")
    print(f"{len(changed)} files; {len(unmapped)} outside every mapped area")
    return 0


def branch_state(ctx: Context, overlay: Path, offline: bool) -> str:
    meta = overlay_meta(overlay)
    name = meta.get("branch", "")
    if not name:
        return "unknown"
    local = f"refs/heads/{name}"
    if ref_exists(local):
        tip = git("rev-parse", local)
        if tip != meta.get("fork"):
            for target in (ctx.default, f"origin/{ctx.default}"):
                if ref_exists(target) and git_ok("merge-base", "--is-ancestor", local, target):
                    return "merged"
    if not offline and shutil.which("gh"):
        with contextlib.suppress(subprocess.TimeoutExpired, OSError):
            result = subprocess.run(
                ["gh", "pr", "view", name, "--json", "state", "-q", ".state"],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=ctx.toplevel,
            )
            state = {"MERGED": "merged", "CLOSED": "closed", "OPEN": "open"}.get(result.stdout.strip())
            if state:
                return state
    return "open" if ref_exists(local) else "gone"


def cmd_check(ctx: Context, args: argparse.Namespace) -> int:
    views = collect_views(ctx)
    problems = 0
    print(status_line(ctx, views))
    for entry_id, view in sorted(views.items()):
        flags = [flag for flag in view.flags if flag in PROBLEM_FLAGS]
        if flags:
            problems += 1
            print(f"{entry_id}: {', '.join(flags)}")
    areas: dict[str, int] = {}
    for entry_id in views:
        areas[entry_id.split("/", 1)[0]] = areas.get(entry_id.split("/", 1)[0], 0) + 1
    for area, count in sorted(areas.items()):
        if count > AREA_SOFT_LIMIT:
            problems += 1
            print(f"area {area}: {count} entries (soft limit {AREA_SOFT_LIMIT}); keep only critical behaviors")
    advice = {"merged": "run `promote`", "closed": "run `drop`", "gone": "branch is gone; `promote` or `drop`"}
    for overlay in overlay_dirs(ctx):
        state = branch_state(ctx, overlay, args.offline)
        name = overlay_meta(overlay).get("branch", overlay.name)
        conflicts = len(list(overlay.glob("*/*.merge.md")))
        if state in advice or conflicts:
            problems += 1
            extra = f"; {conflicts} conflicts wait for `resolve`" if conflicts else ""
            print(f"overlay {name}: {state}" + (f" — {advice[state]}" if state in advice else "") + extra)
    if problems == 0:
        print("behavior map OK")
    return 1 if problems else 0


def _drop_overlay_entry(overlay: Path, entry_id: str) -> None:
    for suffix in (".md", ".base.md", ".merge.md"):
        entry_path(overlay, entry_id, suffix).unlink(missing_ok=True)
    area_dir = entry_path(overlay, entry_id).parent
    if area_dir.is_dir() and not any(area_dir.iterdir()):
        area_dir.rmdir()
    if not layer_ids(overlay) and not list(overlay.glob("*/*.merge.md")):
        shutil.rmtree(overlay, ignore_errors=True)


def _merge3(current: str, ancestor: str, branch: str) -> tuple[str, bool]:
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, text in (("base", current), ("fork", ancestor), ("branch", branch)):
            path = Path(tmp) / name
            path.write_text(text, encoding="utf-8")
            paths.append(str(path))
        result = subprocess.run(
            ["git", "merge-file", "-p", "-L", "base", "-L", "fork", "-L", "branch", *paths],
            capture_output=True,
            text=True,
        )
    if result.returncode < 0:
        raise MapError(f"git merge-file failed: {result.stderr.strip()}")
    return result.stdout, result.returncode == 0


def cmd_promote(ctx: Context, args: argparse.Namespace) -> int:
    overlay = ctx.overlay(args.target_branch)
    if not overlay.is_dir():
        raise MapError(f"no overlay for branch {args.target_branch!r}")
    if not args.force:
        state = branch_state(ctx, overlay, args.offline)
        if state != "merged":
            raise MapError(f"branch {args.target_branch!r} is {state}, not merged; pass --force to promote anyway")
    promoted, conflicts = 0, []
    with repo_lock(ctx):
        for entry_id in layer_ids(overlay):
            if entry_path(overlay, entry_id, ".merge.md").exists():
                conflicts.append(entry_id)
                continue
            branch_text = entry_path(overlay, entry_id).read_text(encoding="utf-8")
            base_entry = entry_path(ctx.base, entry_id)
            current = without_fingerprint(read_or_none(base_entry))
            ancestor = without_fingerprint(read_or_none(entry_path(overlay, entry_id, ".base.md")))
            removed = parse_entry(branch_text).status == "removed"
            if current == ancestor or (removed and current is None):
                if removed:
                    base_entry.unlink(missing_ok=True)
                else:
                    atomic_write(base_entry, branch_text)
            elif removed:
                atomic_write(
                    entry_path(overlay, entry_id, ".merge.md"),
                    "<!-- removed on the branch, changed on base; keep, rewrite, or remove it -->\n" + (current or ""),
                )
                conflicts.append(entry_id)
                continue
            else:
                merged, clean = _merge3(current or "", ancestor or "", without_fingerprint(branch_text) or "")
                if clean:
                    try:
                        clean = not validate(parse_entry(merged), entry_id)
                    except MapError:
                        clean = False
                if not clean:
                    atomic_write(entry_path(overlay, entry_id, ".merge.md"), merged)
                    conflicts.append(entry_id)
                    continue
                atomic_write(base_entry, merged)
            _drop_overlay_entry(overlay, entry_id)
            promoted += 1
    print(f"promoted {promoted} entries from {args.target_branch}")
    for entry_id in conflicts:
        print(f"conflict {entry_id}: {entry_path(overlay, entry_id, '.merge.md')}")
    if conflicts:
        print(f"Resolve each with: ,behavior-map resolve {args.target_branch} <id> < resolved-entry.md")
    return 1 if conflicts else 0


def cmd_resolve(ctx: Context, args: argparse.Namespace) -> int:
    overlay = ctx.overlay(args.target_branch)
    if not entry_path(overlay, args.id).exists():
        raise MapError(f"no overlay entry {args.id!r} on branch {args.target_branch!r}")
    text, _ = _read_stdin_entry(args.id)
    entry = parse_entry(text)
    errors = validate(entry, args.id)
    if errors:
        raise MapError("invalid entry:\n  " + "\n  ".join(errors))
    with repo_lock(ctx):
        base_entry = entry_path(ctx.base, args.id)
        if entry.status == "removed":
            base_entry.unlink(missing_ok=True)
        else:
            atomic_write(base_entry, with_fingerprint(ctx, text, entry))
        _drop_overlay_entry(overlay, args.id)
    print(f"resolved {args.id} into base")
    return 0


def cmd_drop(ctx: Context, args: argparse.Namespace) -> int:
    overlay = ctx.overlay(args.target_branch)
    if not overlay.is_dir():
        raise MapError(f"no overlay for branch {args.target_branch!r}")
    with repo_lock(ctx):
        if args.id:
            if not entry_path(overlay, args.id).exists():
                raise MapError(f"no overlay entry {args.id!r}")
            _drop_overlay_entry(overlay, args.id)
        else:
            shutil.rmtree(overlay)
    print(f"dropped {args.id or 'overlay'} from {args.target_branch}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=",behavior-map", description=__doc__.splitlines()[0])
    parser.add_argument("--repo", help="map namespace (default: basename of the main checkout)")
    parser.add_argument("--branch", help="act as this branch (default: current branch)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("path", help="print the map directory for this repo").set_defaults(func=cmd_path)

    show = sub.add_parser("show", help="status line and index; or full entries for an area or id")
    show.add_argument("target", nargs="?", help="<area> or <area>/<name>")
    show.add_argument("--ids", action="store_true", help="print entry ids only")
    show.set_defaults(func=cmd_show)

    save = sub.add_parser("save", help="write the entry on stdin to this branch's layer")
    save.add_argument("id", help="<area>/<name>")
    save.add_argument("--rebased", action="store_true", help="branch entry now builds on the current base entry")
    save.add_argument("--force", action="store_true", help="skip the changed-since-read check")
    save.set_defaults(func=cmd_save)

    remove = sub.add_parser("remove", help="delete an entry (on a branch: mark it removed)")
    remove.add_argument("id")
    remove.set_defaults(func=cmd_remove)

    affected = sub.add_parser("affected", help="entries and areas a change touches, and unmapped paths")
    affected.add_argument("paths", nargs="*", help="planned paths (default: this worktree's diff)")
    affected.add_argument("--since", help="compare against this rev (default: fork point, or HEAD on base)")
    affected.set_defaults(func=cmd_affected)

    check = sub.add_parser("check", help="list stale, broken, drifted, and conflicting entries and overlays")
    check.add_argument("--offline", action="store_true", help="do not ask gh about pull request state")
    check.set_defaults(func=cmd_check)

    promote = sub.add_parser("promote", help="merge a branch overlay into the base map")
    promote.add_argument("target_branch", metavar="branch")
    promote.add_argument("--force", action="store_true", help="promote even if the branch is not merged")
    promote.add_argument("--offline", action="store_true", help="do not ask gh about pull request state")
    promote.set_defaults(func=cmd_promote)

    resolve = sub.add_parser("resolve", help="write the resolved entry on stdin to base and clear the conflict")
    resolve.add_argument("target_branch", metavar="branch")
    resolve.add_argument("id")
    resolve.set_defaults(func=cmd_resolve)

    drop = sub.add_parser("drop", help="delete a branch overlay, or one entry of it")
    drop.add_argument("target_branch", metavar="branch")
    drop.add_argument("id", nargs="?")
    drop.set_defaults(func=cmd_drop)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(build_context(args), args)
    except MapError as error:
        print(f",behavior-map: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
