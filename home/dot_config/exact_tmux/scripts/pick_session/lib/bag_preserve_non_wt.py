#!/usr/bin/env python3
import os
import shutil
from pathlib import Path

wrapper = Path(os.environ["WRAPPER"]).resolve()
bag_root = Path(os.environ["BAG_ROOT"]).resolve()
wt_rels_raw = os.environ.get("WT_RELS", "")

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
