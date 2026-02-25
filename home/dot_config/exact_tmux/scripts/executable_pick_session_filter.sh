#!/usr/bin/env bash
set -euo pipefail

query="${*:-}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"

items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"

if [ ! -x "$items_cmd" ]; then
  # Fallback: if items can't be generated, show whatever cache exists.
  [ -f "$cache_file" ] && cat "$cache_file"
  exit 0
fi

if ! need_cmd python3 || ! need_cmd fzf; then
  exec "$items_cmd"
fi

mutation_ttl="300"
current_name=""
if [ -n "${TMUX:-}" ] && need_cmd tmux; then
  mutation_ttl="$(tmux show-option -gqv '@pick_session_mutation_tombstone_ttl' 2>/dev/null || printf '%s' "$mutation_ttl")"
  current_name="$(tmux display-message -p '#S' 2>/dev/null || true)"
fi
case "$mutation_ttl" in
'' | *[!0-9]*) mutation_ttl="300" ;;
esac

QUERY="$query" ITEMS_CMD="$items_cmd" CACHE_FILE="$cache_file" MUTATION_FILE="$mutation_file" MUTATION_TTL="$mutation_ttl" CURRENT_SESSION_NAME="$current_name" python3 - <<'PY'
import os
import re
import signal
import subprocess
import sys
import time

query = os.environ.get("QUERY", "")
items_cmd = os.environ.get("ITEMS_CMD", "").strip()

signal.signal(signal.SIGPIPE, signal.SIG_DFL)

def norm_token(s: str) -> str:
    s = (s or "").strip().lower()
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]+", "", s)

def compute_mk(parts: list[str]) -> str:
    if len(parts) >= 6 and (parts[5] or "").strip():
        mk = parts[5].strip()
        # Augment cached match keys with normalized variants so queries like
        # `kibanamain` still match `kibana|main`.
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
    if kind == "worktree":
        branch = meta
        if branch.startswith("wt_root:"):
            branch = branch[len("wt_root:") :]
        elif branch.startswith("wt:"):
            branch = branch[len("wt:") :]
        root = target.rstrip("/") if target else ""
        repo = root.split("/")[-1] if root else ""
        # Wrapper layout (`,w`): root worktree often lives in `<repo>/main`.
        if repo in ("main", "master", "trunk", "develop", "dev") and "/" in root:
            repo = root.split("/")[-2]
        wt_name = f"{repo}|{branch}" if (repo and branch) else (repo or base)
        tokens = [p for p in [wt_name, base, path] if p]
        normed = [norm_token(t) for t in tokens]
        normed = [t for t in normed if t]
        return " ".join(tokens + normed)
    if kind == "dir":
        tokens = [p for p in [base, path] if p]
        normed = [norm_token(t) for t in tokens]
        normed = [t for t in normed if t]
        return " ".join(tokens + normed)
    tokens = [p for p in [base, path] if p]
    normed = [norm_token(t) for t in tokens]
    normed = [t for t in normed if t]
    return " ".join(tokens + normed)

base_out = ""
if items_cmd:
    try:
        base_out = subprocess.run(
            [items_cmd],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout
    except Exception:
        base_out = ""

if not base_out:
    sys.exit(0)

lines: list[str] = []
for raw in base_out.splitlines():
    line = raw.rstrip("\n")
    if not line:
        continue
    lines.append(line)

def dedup_best(rows: list[str]) -> list[str]:
    kind_prio = {"session": 3, "worktree": 2, "dir": 1}
    best_by_path: dict[str, tuple[int, int]] = {}
    # First pass: choose the best row index for each path.
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
    # Second pass: emit rows in original order, keeping only the best per path.
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

if not query.strip():
    # When the query is empty, fzf shows the list as-is. Bucket by kind so
    # sessions are always hoisted above worktrees/dirs, even if the base list
    # contains "promoted" sessions in the middle (for example right after
    # creating a session from a worktree and reopening the picker).
    sessions: list[str] = []
    worktrees: list[str] = []
    dirs: list[str] = []
    other: list[str] = []
    for line in dedup_best(lines):
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
    for bucket in (sessions, worktrees, dirs, other):
        for line in bucket:
            print(line)
    sys.exit(0)

filter_lines: list[str] = []
for ln in lines:
    parts = ln.split("\t")
    mk = compute_mk(parts) or (parts[0] if parts else "")
    mk = (mk or "").replace("\x1f", " ").strip()
    filter_lines.append(f"{mk}\x1f{ln}")

proc = subprocess.run(
    # IMPORTANT: do not pass `--ansi` here. In `--filter` mode, fzf strips ANSI
    # sequences from its output when `--ansi` is enabled, which would make the
    # picker lose colors while typing.
    ["fzf", "--exact", "--filter", query, "--delimiter", "\x1f", "--nth", "1"],
    input="\n".join(filter_lines) + "\n",
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    check=False,
)

sessions: list[str] = []
worktrees: list[str] = []
dirs: list[str] = []
other: list[str] = []

for raw in proc.stdout.splitlines():
    line = raw.rstrip("\n")
    if not line:
        continue
    try:
        _mk, line = line.split("\x1f", 1)
    except ValueError:
        continue
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

def emit_bucket(rows: list[str]):
    for line in dedup_best(rows):
        parts = line.split("\t")
        if len(parts) >= 5:
            path = parts[2] or ""
            if path:
                if path in seen_paths:
                    continue
                seen_paths.add(path)
        print(line)

emit_bucket(sessions)
emit_bucket(worktrees)
emit_bucket(dirs)
emit_bucket(other)
PY
