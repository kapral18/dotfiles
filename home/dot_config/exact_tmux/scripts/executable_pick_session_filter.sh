#!/usr/bin/env bash
set -euo pipefail

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"
update_cmd="$HOME/.config/tmux/scripts/pick_session_index_update.sh"

refresh=0
for arg in "$@"; do
  case "$arg" in
  --refresh) refresh=1 ;;
  esac
done

if [ "$refresh" -eq 1 ] && [ -x "$update_cmd" ]; then
  "$update_cmd" --force --quiet >/dev/null 2>&1 || true
fi

if [ ! -x "$items_cmd" ]; then
  cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
  cache_file="${cache_dir}/pick_session_items.tsv"
  [ -f "$cache_file" ] && cat "$cache_file"
  exit 0
fi

if ! need_cmd python3; then
  exec "$items_cmd"
fi

scan_roots_raw=""
if command -v tmux >/dev/null 2>&1; then
  scan_roots_raw="$(tmux show-option -gqv '@pick_session_worktree_scan_roots' 2>/dev/null || true)"
fi
if [ -z "${scan_roots_raw:-}" ]; then
  scan_roots_raw="$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share"
fi

ITEMS_CMD="$items_cmd" PICK_SESSION_SCAN_ROOTS="$scan_roots_raw" python3 -u - <<'PY'
import os
import signal
import subprocess
import sys
from pathlib import Path

signal.signal(signal.SIGPIPE, signal.SIG_DFL)

items_cmd = os.environ.get("ITEMS_CMD", "").strip()
if not items_cmd:
    sys.exit(0)

roots_raw = (os.environ.get("PICK_SESSION_SCAN_ROOTS", "") or "").strip()

def resolve_path(p: str) -> str:
    if not p:
        return ""
    try:
        return str(Path(p).expanduser().resolve())
    except Exception:
        try:
            return os.path.realpath(os.path.expanduser(p))
        except Exception:
            return p

scan_roots = []
for part in (roots_raw.split(",") if roots_raw else []):
    part = part.strip()
    if not part:
        continue
    scan_roots.append(resolve_path(part))
home_root = resolve_path("~")
if home_root and home_root not in scan_roots:
    scan_roots.append(home_root)

def scan_root_rank_for_path(p: str) -> int:
    rp = resolve_path(p)
    if not rp:
        return 999
    for i, r in enumerate(scan_roots):
        if not r:
            continue
        if rp == r or rp.startswith(r + os.sep):
            return i
    return 999

def scan_root_prefix_for_path(p: str, depth: int = 2) -> str:
    rp = resolve_path(p)
    if not rp:
        return ""
    for r in scan_roots:
        if not r:
            continue
        if rp == r:
            return ""
        if rp.startswith(r + os.sep):
            rel = rp[len(r):].lstrip(os.sep)
            segs = [s for s in rel.split(os.sep) if s]
            return "/".join(segs[:depth])
    return ""

try:
    base_out = subprocess.run(
        [items_cmd], check=False, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True,
    ).stdout
except Exception:
    sys.exit(0)

if not base_out:
    sys.exit(0)

lines = [l.rstrip("\n") for l in base_out.splitlines() if l.rstrip("\n")]

KIND_PRIO = {"session": 3, "worktree": 2, "dir": 1}
DEFAULT_BRANCHES = {"main", "master", "trunk", "develop", "dev"}


def dedup_best(rows):
    best_by_path = {}
    for i, line in enumerate(rows):
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        kind, path = parts[1], parts[2] or ""
        if not path:
            continue
        key = resolve_path(path)
        pr = KIND_PRIO.get(kind, 0)
        prev = best_by_path.get(key)
        if prev is None or pr > prev[0]:
            best_by_path[key] = (pr, i)
    out = []
    seen = set()
    for i, line in enumerate(rows):
        parts = line.split("\t")
        if len(parts) < 5:
            out.append(line)
            continue
        path = parts[2] or ""
        if not path:
            out.append(line)
            continue
        key = resolve_path(path)
        best = best_by_path.get(key)
        if best is None:
            out.append(line)
            continue
        if best[1] != i:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def wrapper_for_root(root):
    base = os.path.basename(root.rstrip("/"))
    if base in DEFAULT_BRANCHES:
        parent = os.path.dirname(root.rstrip("/"))
        return parent if parent else root
    return root


deduped = dedup_best(lines)

# Build worktree path → root mapping from worktree rows.
wt_path_to_root = {}
for line in deduped:
    parts = line.split("\t")
    if len(parts) < 5:
        continue
    kind, path, target = parts[1], parts[2], parts[4]
    if kind == "worktree" and target:
        wt_path_to_root[path] = target

# Build wrapper → preferred root mapping so sessions can be grouped even when
# their exact worktree path has no worktree row (because the session row
# replaces it in the cache).
candidate_roots = set()
for line in deduped:
    parts = line.split("\t")
    if len(parts) < 5:
        continue
    kind, path, meta, target = parts[1], parts[2], parts[3], parts[4]
    if kind == "worktree" and target:
        candidate_roots.add(target)
    if kind == "session":
        meta_base = (meta or "").split("|")[0]
        if meta_base.startswith("sess_root:") and path:
            candidate_roots.add(path)

wrapper_to_root = {}
def prefer_root(a: str, b: str) -> str:
    abase = os.path.basename((a or "").rstrip("/"))
    bbase = os.path.basename((b or "").rstrip("/"))
    a_def = abase in DEFAULT_BRANCHES
    b_def = bbase in DEFAULT_BRANCHES
    if a_def and not b_def:
        return a
    if b_def and not a_def:
        return b
    # Prefer shorter path as a stable tie-breaker.
    return a if len(a) <= len(b) else b

for r in candidate_roots:
    w = wrapper_for_root(r)
    prev = wrapper_to_root.get(w)
    wrapper_to_root[w] = r if prev is None else prefer_root(prev, r)

wrapper_prefixes = sorted(wrapper_to_root.keys(), key=len, reverse=True)
def root_for_path_by_wrapper(p: str):
    if not p:
        return None
    for w in wrapper_prefixes:
        if p == w or p.startswith(w + "/"):
            return wrapper_to_root.get(w)
    return None

# Group entries by root, preserving insertion order.
root_order = []
root_groups = {}
ungrouped_sessions = []
dir_rows = []
other_rows = []


def ensure_group(root):
    if root not in root_groups:
        root_order.append(root)
        root_groups[root] = {"sessions": [], "worktrees": []}
    return root_groups[root]


for line in deduped:
    parts = line.split("\t")
    if len(parts) < 5:
        other_rows.append(line)
        continue
    kind, path, meta, target = parts[1], parts[2], parts[3], parts[4]

    if kind == "worktree":
        root = target or path
        ensure_group(root)["worktrees"].append(line)

    elif kind == "session":
        root = None
        meta_base = (meta or "").split("|")[0]
        if meta_base.startswith("sess_root:"):
            root = path
        elif meta_base.startswith("sess_wt:"):
            root = wt_path_to_root.get(path)
        if not root:
            root = wt_path_to_root.get(path)
        if not root:
            root = root_for_path_by_wrapper(path)
        if root:
            ensure_group(root)["sessions"].append(line)
        else:
            ungrouped_sessions.append(line)

    elif kind == "dir":
        dir_rows.append(line)

    else:
        other_rows.append(line)

# Determine wrapper dirs for roots that have sessions → used to tag related dirs.
session_wrappers = set()
for root in root_order:
    if root_groups[root]["sessions"]:
        session_wrappers.add(wrapper_for_root(root))
for line in ungrouped_sessions:
    parts = line.split("\t")
    if len(parts) >= 3 and parts[2]:
        session_wrappers.add(wrapper_for_root(parts[2]))

wrapper_dirs = []
other_dirs = []
for line in dir_rows:
    parts = line.split("\t")
    path = parts[2] if len(parts) > 2 else ""
    if path and path in session_wrappers:
        wrapper_dirs.append(line)
    else:
        other_dirs.append(line)

# --- Output in grouped order ---
def session_name_for_row(line: str) -> str:
    parts = line.split("\t")
    if len(parts) >= 5:
        return (parts[4] or "").strip().lower()
    return ""

# Prefer current session first, then name.
def is_current_session_row(line: str) -> bool:
    parts = line.split("\t")
    if not parts:
        return False
    return " (current)" in parts[0]

def session_sort_key(line: str):
    return (0 if is_current_session_row(line) else 1, session_name_for_row(line))

def worktree_sort_key(line: str):
    parts = line.split("\t")
    if len(parts) < 5:
        return (999, "", 1, "", "")
    meta = (parts[3] or "")
    path = (parts[2] or "")
    # Root checkout first, then branch-ish meta, then path.
    is_root = 0 if meta.startswith("wt_root:") else 1
    branch = meta.split(":", 1)[1] if ":" in meta else meta
    return (
        scan_root_rank_for_path(path),
        scan_root_prefix_for_path(path),
        is_root,
        (branch or "").lower(),
        path.lower(),
    )

# --- Output in scan-root order, preserving hierarchy within each scan root ---

session_groups = []
for root in root_order:
    data = root_groups[root]
    if not data["sessions"]:
        continue
    first_name = ""
    for s in data["sessions"]:
        n = session_name_for_row(s)
        if n and (not first_name or n < first_name):
            first_name = n
    group_path = wrapper_for_root(root) if root else ""
    session_groups.append(
        (
            scan_root_rank_for_path(group_path),
            scan_root_prefix_for_path(group_path),
            first_name,
            group_path.lower(),
            root,
        )
    )
session_groups.sort()

def ungrouped_session_sort_key(line: str):
    parts = line.split("\t")
    p = parts[2] if len(parts) >= 3 else ""
    w = wrapper_for_root(p) if p else ""
    base = w or p
    return (
        scan_root_rank_for_path(base),
        scan_root_prefix_for_path(base),
        session_sort_key(line),
        (base or "").lower(),
    )

def orphan_root_sort_key(r: str):
    gp = wrapper_for_root(r) if r else ""
    base = gp or r
    return (
        scan_root_rank_for_path(base),
        scan_root_prefix_for_path(base),
        (base or "").lower(),
        r,
    )

def dir_sort_key(line: str):
    parts = line.split("\t")
    p = parts[2] if len(parts) >= 3 else ""
    return (
        scan_root_rank_for_path(p),
        scan_root_prefix_for_path(p),
        (p or "").lower(),
    )

session_groups_by_rank = {}
for rank, pref, first_name, gpath, root in session_groups:
    session_groups_by_rank.setdefault(rank, []).append((pref, first_name, gpath, root))
for rank in session_groups_by_rank:
    session_groups_by_rank[rank].sort()

ungrouped_sessions_sorted = sorted(ungrouped_sessions, key=ungrouped_session_sort_key)
ungrouped_by_rank = {}
for line in ungrouped_sessions_sorted:
    rank = ungrouped_session_sort_key(line)[0]
    ungrouped_by_rank.setdefault(rank, []).append(line)

orphan_roots_sorted = sorted([r for r in root_order if not root_groups[r]["sessions"]], key=orphan_root_sort_key)
orphan_by_rank = {}
for r in orphan_roots_sorted:
    rank = orphan_root_sort_key(r)[0]
    orphan_by_rank.setdefault(rank, []).append(r)

other_dirs_sorted = sorted(other_dirs, key=dir_sort_key)
other_dirs_by_rank = {}
for line in other_dirs_sorted:
    rank = dir_sort_key(line)[0]
    other_dirs_by_rank.setdefault(rank, []).append(line)

wrapper_by_path = {}
for line in wrapper_dirs:
    parts = line.split("\t")
    if len(parts) >= 3 and parts[2]:
        wrapper_by_path[parts[2]] = line

emitted_worktree_roots = set()

def emit_rank(rank: int):
    # Session groups (session rows first, then their worktrees).
    for _pref, _first_name, _gpath, root in session_groups_by_rank.get(rank, []):
        data = root_groups[root]
        for line in sorted(data["sessions"], key=session_sort_key):
            print(line)
        if root not in emitted_worktree_roots:
            for line in sorted(data["worktrees"], key=worktree_sort_key):
                print(line)
            emitted_worktree_roots.add(root)

    # Ungrouped sessions.
    for line in ungrouped_by_rank.get(rank, []):
        print(line)

    # Orphan worktree groups (root has no session).
    for root in orphan_by_rank.get(rank, []):
        if root in emitted_worktree_roots:
            continue
        for line in sorted(root_groups[root]["worktrees"], key=worktree_sort_key):
            print(line)
        emitted_worktree_roots.add(root)

# 1) Ranks that have any sessions first (keeps related worktrees close).
ranks_with_sessions = sorted(set(session_groups_by_rank.keys()).union(ungrouped_by_rank.keys()))
for rank in ranks_with_sessions:
    emit_rank(rank)

# 2) Remaining ranks (worktrees-only) next.
for rank in sorted(set(orphan_by_rank.keys()).difference(ranks_with_sessions)):
    emit_rank(rank)

# 4. Anything else (non-session/worktree/dir).
for line in other_rows:
    print(line)

# 5. All directories at the end (still naturally grouped by scan root/prefix/path).
all_dirs_sorted = sorted(dir_rows, key=dir_sort_key)
for line in all_dirs_sorted:
    print(line)
PY
