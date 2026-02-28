#!/usr/bin/env bash
set -euo pipefail

sel_file="${1:-}"
mode="${2:-}"
query="${3:-}"
items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"

if [ -z "$sel_file" ] || [ ! -f "$sel_file" ] || [ ! -x "$items_cmd" ]; then
  exec "$items_cmd"
fi

python3 -u - "$sel_file" "$items_cmd" "$mode" "$query" <<'PY'
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

sel_file = sys.argv[1]
items_cmd = sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else ""
query = sys.argv[4] if len(sys.argv) > 4 else ""

signal.signal(signal.SIGPIPE, signal.SIG_DFL)

selected = set()
selected_rows = []
with open(sel_file, "r", encoding="utf-8", errors="replace") as f:
    for raw in f:
        line = raw.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        _display, kind, path, meta, target = parts[:5]
        selected.add((kind, path, target))
        selected_rows.append((kind, path, meta, target))

def append_mutation_tombstones():
    if mode not in ("kill", "remove"):
        return
    xdg_cache = os.environ.get("XDG_CACHE_HOME", "").strip()
    cache_dir = Path(xdg_cache) / "tmux" if xdg_cache else (Path.home() / ".cache" / "tmux")
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return
    mutation_file = cache_dir / "pick_session_mutations.tsv"
    now = int(time.time())
    lines = []
    def resolve_path(p: str) -> str:
        try:
            return str(Path(p).resolve())
        except Exception:
            return p

    def worktree_dir_for_path(p: str) -> str:
        cur = Path(p)
        if cur.is_file():
            cur = cur.parent
        try:
            cur = cur.resolve()
        except Exception:
            cur = Path(p)
        for _ in range(16):
            if (cur / ".git").exists():
                return str(cur)
            if cur.parent == cur:
                break
            cur = cur.parent
        return ""

    if mode == "kill":
        for kind, _path, _meta, target in selected_rows:
            if kind == "session" and target:
                lines.append(f"{now}\tSESSION_TARGET\t{target}\n")
            elif kind == "dir" and _path:
                lines.append(f"{now}\tPATH_PREFIX\t{resolve_path(_path)}\n")
    elif mode == "remove":
        for kind, path, meta, _target in selected_rows:
            if not path:
                continue
            if kind == "worktree":
                lines.append(f"{now}\tPATH_PREFIX\t{resolve_path(path)}\n")
                continue
            if kind == "session":
                meta_base = (meta or "").split("|", 1)[0]
                if meta_base.startswith("sess_root:") or meta_base.startswith("sess_wt:"):
                    wt = worktree_dir_for_path(path) or path
                    lines.append(f"{now}\tPATH_PREFIX\t{resolve_path(wt)}\n")
                else:
                    lines.append(f"{now}\tPATH_PREFIX\t{resolve_path(path)}\n")
            if kind == "dir":
                lines.append(f"{now}\tPATH_PREFIX\t{resolve_path(path)}\n")
    if not lines:
        return
    try:
        with open(mutation_file, "a", encoding="utf-8") as mf:
            mf.writelines(lines)
    except Exception:
        pass

append_mutation_tombstones()

proc = subprocess.run([items_cmd], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
base_rows = []
for raw in proc.stdout.splitlines():
    if not raw:
        continue
    parts = raw.split("\t")
    if len(parts) < 5:
        base_rows.append(raw)
        continue
    _display, kind, path, _meta, target = parts[:5]
    if (kind, path, target) in selected:
        if mode == "kill" and kind == "worktree":
            pass
        else:
            continue
    base_rows.append(raw)

# --- shared grouping logic ---

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
        pr = KIND_PRIO.get(kind, 0)
        prev = best_by_path.get(path)
        if prev is None or pr > prev[0]:
            best_by_path[path] = (pr, i)
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
        best = best_by_path.get(path)
        if best is None:
            out.append(line)
            continue
        if best[1] != i:
            continue
        if path in seen:
            continue
        seen.add(path)
        out.append(line)
    return out


def wrapper_for_root(root):
    base = os.path.basename(root.rstrip("/"))
    if base in DEFAULT_BRANCHES:
        parent = os.path.dirname(root.rstrip("/"))
        return parent if parent else root
    return root


def grouped_output(rows):
    deduped = dedup_best(rows)

    wt_path_to_root = {}
    for line in deduped:
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        kind, path, target = parts[1], parts[2], parts[4]
        if kind == "worktree" and target:
            wt_path_to_root[path] = target

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

    def session_name_for_row(line: str) -> str:
        parts = line.split("\t")
        if len(parts) >= 5:
            return (parts[4] or "").strip().lower()
        return ""

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
            return (1, "", "")
        meta = (parts[3] or "")
        path = (parts[2] or "")
        is_root = 0 if meta.startswith("wt_root:") else 1
        branch = meta.split(":", 1)[1] if ":" in meta else meta
        return (is_root, (branch or "").lower(), path.lower())

    result = []

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
        session_groups.append((first_name, root))
    session_groups.sort()

    emitted_worktree_roots = set()
    for _name, root in session_groups:
        data = root_groups[root]
        result.extend(sorted(data["sessions"], key=session_sort_key))
        if root not in emitted_worktree_roots:
            result.extend(sorted(data["worktrees"], key=worktree_sort_key))
            emitted_worktree_roots.add(root)

    result.extend(sorted(ungrouped_sessions, key=session_sort_key))

    for root in sorted([r for r in root_order if not root_groups[r]["sessions"]]):
        result.extend(sorted(root_groups[root]["worktrees"], key=worktree_sort_key))

    wrapper_by_path = {}
    for line in wrapper_dirs:
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2]:
            wrapper_by_path[parts[2]] = line

    emitted_wrappers = set()
    for _name, root in session_groups:
        w = wrapper_for_root(root)
        if w in emitted_wrappers:
            continue
        dline = wrapper_by_path.get(w)
        if dline:
            result.append(dline)
            emitted_wrappers.add(w)

    for line in sorted(ungrouped_sessions, key=session_sort_key):
        parts = line.split("\t")
        if len(parts) < 3 or not parts[2]:
            continue
        w = wrapper_for_root(parts[2])
        if w in emitted_wrappers:
            continue
        dline = wrapper_by_path.get(w)
        if dline:
            result.append(dline)
            emitted_wrappers.add(w)

    result.extend(other_dirs)
    result.extend(other_rows)
    return result


for line in grouped_output(base_rows):
    print(line)
PY
