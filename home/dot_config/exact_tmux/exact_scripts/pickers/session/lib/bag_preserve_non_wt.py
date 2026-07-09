#!/usr/bin/env python3
import os
import shutil
from pathlib import Path

wrapper = Path(os.environ["WRAPPER"]).resolve()
bag_root = Path(os.environ["BAG_ROOT"]).resolve()
wt_rels_raw = os.environ.get("WT_RELS", "")
status_file = os.environ.get("BAG_PRESERVE_STATUS_FILE", "")
git_scan_depth_raw = os.environ.get("BAG_GIT_SCAN_DEPTH", "8")
try:
    git_scan_depth = int(git_scan_depth_raw or "8")
except Exception:
    git_scan_depth = 8

worktree_roots = set()
protected_dirs = set()
for rel in wt_rels_raw.splitlines():
    rel = rel.strip().strip("/")
    if not rel:
        continue
    root = (wrapper / rel).resolve()
    worktree_roots.add(root)
    cur = root
    while True:
        protected_dirs.add(cur)
        if cur == wrapper:
            break
        if cur.parent == cur:
            break
        cur = cur.parent
protected_dirs.add(wrapper)


def is_relative_to_path(p: Path, base: Path) -> bool:
    try:
        p.relative_to(base)
        return True
    except Exception:
        return False


def is_under_selected_worktree(p: Path) -> bool:
    return any(is_relative_to_path(p, root) for root in worktree_roots)


def write_status(blocked_by_unselected_git_root: bool):
    if not status_file:
        return
    try:
        with open(status_file, "w", encoding="utf-8") as f:
            f.write(f"blocked_by_unselected_git_root={int(blocked_by_unselected_git_root)}\n")
    except Exception:
        pass


def has_unselected_git_root() -> bool:
    for root, dirs, files in os.walk(wrapper, topdown=True, followlinks=False):
        rootp = Path(root).resolve()
        if is_under_selected_worktree(rootp):
            dirs[:] = []
            continue

        if ".git" in dirs or ".git" in files:
            return True

        try:
            depth = len(rootp.relative_to(wrapper).parts)
        except Exception:
            depth = 0
        if git_scan_depth >= 0 and depth >= git_scan_depth:
            dirs[:] = []

    return False


def is_worktree_root(p: Path) -> bool:
    try:
        rp = p.resolve()
    except Exception:
        rp = p
    return rp in worktree_roots


def is_protected_dir(p: Path) -> bool:
    try:
        rp = p.resolve()
    except Exception:
        rp = p
    return rp in protected_dirs


def rel_to_wrapper(p: Path) -> Path:
    try:
        return p.resolve().relative_to(wrapper)
    except Exception:
        try:
            return p.relative_to(wrapper)
        except Exception:
            return Path("")


def move_to_bag(src: Path):
    rel = rel_to_wrapper(src)
    if not rel or str(rel) == ".":
        return
    dest = bag_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(src), str(dest))
        return True
    except Exception:
        return False


moved = 0

if has_unselected_git_root():
    write_status(True)
    print(moved)
    raise SystemExit(0)

write_status(False)

for root, dirs, files in os.walk(wrapper, topdown=True, followlinks=False):
    rootp = Path(root)
    if is_worktree_root(rootp):
        dirs[:] = []
        continue

    next_dirs = []
    for d in dirs:
        child = rootp / d
        if is_worktree_root(child):
            continue
        if child.is_symlink():
            moved += 1 if move_to_bag(child) else 0
            continue
        if not is_protected_dir(child):
            moved += 1 if move_to_bag(child) else 0
            continue
        next_dirs.append(d)
    dirs[:] = next_dirs

    for f in files:
        if f == ".DS_Store":
            try:
                (rootp / f).unlink()
            except Exception:
                pass
            continue
        moved += 1 if move_to_bag(rootp / f) else 0

print(moved)
