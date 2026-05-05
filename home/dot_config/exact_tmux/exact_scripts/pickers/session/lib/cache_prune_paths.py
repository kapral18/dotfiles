#!/usr/bin/env python3
import os

cache_file = os.environ["CACHE_FILE"]
wt_paths = {p for p in os.environ.get("PENDING_WT", "").split("\n") if p}
dir_paths = {p for p in os.environ.get("PENDING_DIRS", "").split("\n") if p}
paths = wt_paths.union(dir_paths)


def should_drop(kind, p):
    if not p:
        return False
    for base in paths:
        if p == base or p.startswith(base + "/"):
            # Drop dir rows under removed worktrees too.
            if kind in ("dir", "worktree", "session"):
                return True
    return False


out = []
with open(cache_file, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        kind = parts[1]
        path = parts[2]
        if should_drop(kind, path):
            continue
        out.append(line)

tmp = cache_file + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    f.writelines(out)
os.replace(tmp, cache_file)
