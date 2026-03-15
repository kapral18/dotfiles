#!/usr/bin/env python3
import os
import time

cache_in = os.environ["CACHE_FILE"]
pending = os.environ["PENDING_FILE"]
mutations_file = os.environ.get("MUTATIONS_FILE", "")
mutation_ttl = int(os.environ.get("MUTATION_TTL", "300") or "300")

pending_paths = set()
pending_rows = []
if pending and os.path.exists(pending):
    with open(pending, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            tag, sep, p = line.partition("\t")
            if sep and tag == "WT" and p:
                pending_rows.append(p)

mutation_path_prefixes = set()
mutation_session_targets = set()
live_session_names = set()

if mutations_file and os.path.exists(mutations_file):
    now = int(time.time())
    keep = []
    changed = False
    with open(mutations_file, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 2)
            if len(parts) != 3:
                changed = True
                continue
            ts_s, kind, value = parts
            if not value:
                changed = True
                continue
            try:
                ts = int(ts_s)
            except Exception:
                changed = True
                continue
            if mutation_ttl >= 0 and (now - ts) > mutation_ttl:
                changed = True
                continue
            keep.append(line)
            if kind == "PATH_PREFIX":
                mutation_path_prefixes.add(value)
            elif kind == "SESSION_TARGET":
                mutation_session_targets.add(value)
    if changed:
        tmp = mutations_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for line in keep:
                f.write(line + "\n")
        os.replace(tmp, mutations_file)

try:
    import subprocess

    out = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout
    for row in out.splitlines():
        row = row.strip()
        if row:
            live_session_names.add(row)
except Exception:
    pass


def under_any_prefix(p: str, prefixes: set) -> bool:
    if not p:
        return False
    for base in prefixes:
        if p == base or p.startswith(base + "/"):
            return True
    return False


# Prune stale pending entries: if the path still exists and there is no active
# mutation tombstone covering it, it should not remain hidden forever.
if pending and os.path.exists(pending) and pending_rows:
    keep = []
    changed = False
    for p in pending_rows:
        if not p:
            changed = True
            continue
        if os.path.exists(p):
            if under_any_prefix(p, mutation_path_prefixes):
                keep.append(p)
            else:
                changed = True
        else:
            keep.append(p)
    if changed:
        tmp = pending + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for p in keep:
                f.write("WT\t" + p + "\n")
        os.replace(tmp, pending)
    pending_paths = set(keep)
else:
    pending_paths = set(pending_rows)


def path_is_tombstoned(kind, p):
    if kind not in ("dir", "worktree"):
        return False
    for base in pending_paths:
        if p == base or p.startswith(base + "/"):
            return True
    for base in mutation_path_prefixes:
        if p == base or p.startswith(base + "/"):
            return True
    return False


def session_is_tombstoned(kind, target):
    return kind == "session" and target in mutation_session_targets and target not in live_session_names


out = []
with open(cache_in, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        kind = parts[1]
        path = parts[2]
        target = parts[4]
        if path_is_tombstoned(kind, path) or session_is_tombstoned(kind, target):
            continue
        out.append(line)

cache_out = os.environ["CACHE_OUT"]
with open(cache_out, "w", encoding="utf-8") as f:
    f.writelines(out)
