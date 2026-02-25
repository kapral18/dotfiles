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
                    # Session paths can point at a subdir inside a worktree.
                    # Tombstone the worktree root so the repo/worktree row
                    # disappears immediately on the next reload.
                    wt = worktree_dir_for_path(path) or path
                    lines.append(f"{now}\tPATH_PREFIX\t{resolve_path(wt)}\n")
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
        continue
    base_rows.append(raw)

def norm_token(s: str) -> str:
    s = (s or "").strip().lower()
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]+", "", s)

def compute_mk(parts: list[str]) -> str:
    if len(parts) >= 6 and (parts[5] or "").strip():
        mk = parts[5].strip()
        extra: list[str] = []
        try:
            _display, kind, path, meta, target = parts[:5]
        except Exception:
            target = ""
            path = ""
        extra.extend([norm_token(mk), norm_token(target), norm_token(path)])
        extra = [t for t in extra if t]
        return " ".join([mk] + extra)
    if len(parts) < 5:
        return ""
    _display, kind, path, meta, target = parts[:5]
    path = (path or "").rstrip("/")
    base = path.split("/")[-1] if path else ""
    meta = (meta or "").strip()
    target = (target or "").strip()
    tokens: list[str] = []
    if kind == "session":
        tokens = [p for p in [target, base, path] if p]
        normed = [norm_token(t) for t in tokens]
        normed = [t for t in normed if t]
        return " ".join(tokens + normed)
    # For worktree/dir rows, the cached match key should already be present,
    # but keep a basic fallback here.
    tokens = [p for p in [base, path] if p]
    normed = [norm_token(t) for t in tokens]
    normed = [t for t in normed if t]
    return " ".join(tokens + normed)

def dedup_best(rows: list[str]) -> list[str]:
    kind_prio = {"session": 3, "worktree": 2, "dir": 1}
    best_by_path: dict[str, tuple[int, int]] = {}
    for i, line in enumerate(rows):
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        kind = parts[1]
        path = parts[2] or ""
        if not path:
            continue
        pr = kind_prio.get(kind, 0)
        prev = best_by_path.get(path)
        if prev is None or pr > prev[0]:
            best_by_path[path] = (pr, i)
    out: list[str] = []
    seen_paths: set[str] = set()
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
        if path in seen_paths:
            continue
        seen_paths.add(path)
        out.append(line)
    return out

def emit_buckets(rows: list[str]):
    sessions: list[str] = []
    worktrees: list[str] = []
    dirs: list[str] = []
    other: list[str] = []
    for line in rows:
        parts = line.split("\t")
        if len(parts) < 5:
            other.append(line)
            continue
        kind = parts[1]
        if kind == "session":
            sessions.append(line)
        elif kind == "worktree":
            worktrees.append(line)
        elif kind == "dir":
            dirs.append(line)
        else:
            other.append(line)
    seen_paths: set[str] = set()
    for bucket in (sessions, worktrees, dirs, other):
        for line in dedup_best(bucket):
            parts = line.split("\t")
            if len(parts) >= 5:
                path = parts[2] or ""
                if path:
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)
            print(line)

if not (query or "").strip():
    emit_buckets(base_rows)
    raise SystemExit(0)

filter_lines: list[str] = []
for ln in base_rows:
    parts = ln.split("\t")
    mk = compute_mk(parts) or (parts[0] if parts else "")
    mk = (mk or "").replace("\x1f", " ").strip()
    filter_lines.append(f"{mk}\x1f{ln}")

proc = subprocess.run(
    ["fzf", "--exact", "--filter", query, "--delimiter", "\x1f", "--nth", "1"],
    input="\n".join(filter_lines) + "\n",
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    check=False,
)

matched: list[str] = []
for raw in proc.stdout.splitlines():
    line = raw.rstrip("\n")
    if not line:
        continue
    try:
        _mk, line = line.split("\x1f", 1)
    except ValueError:
        continue
    matched.append(line)

emit_buckets(matched)
PY
