#!/usr/bin/env bash
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"

ansi_wrap() {
  local code="$1"
  local text="$2"
  printf '\033[%sm%s\033[0m' "$code" "$text"
}

display_session_entry() {
  local name="$1"
  local path_display="$2"
  printf '%s  %s  %s' \
    "$(ansi_wrap '38;5;42' '')" \
    "$(ansi_wrap '1;38;5;81' "$name")" \
    "$(ansi_wrap '2;38;5;246' "$path_display")"
}

display_dir_entry() {
  local path_display="$1"
  printf '%s  %s' "$(ansi_wrap '38;5;75' '')" "$(ansi_wrap '38;5;110' "$path_display")"
}

wait_ms="${PICK_SESSION_CACHE_WAIT_MS:-0}"
mutation_ttl="${PICK_SESSION_MUTATION_TOMBSTONE_TTL:-300}"
if [ -n "${TMUX:-}" ]; then
  wait_ms="$(tmux show-option -gqv '@pick_session_cache_wait_ms' 2>/dev/null || printf '%s' "$wait_ms")"
  mutation_ttl="$(tmux show-option -gqv '@pick_session_mutation_tombstone_ttl' 2>/dev/null || printf '%s' "$mutation_ttl")"
fi
case "$wait_ms" in
  ''|*[!0-9]*) wait_ms=0 ;;
esac
case "$mutation_ttl" in
  ''|*[!0-9]*) mutation_ttl=300 ;;
esac

if [ -f "$cache_file" ]; then
  # Keep the UI correct even if the cache is slightly stale:
  # - Don't show the current session's path as a worktree/dir entry
  # - If a cached worktree/dir now has a session, show it as a session
  # - Preserve cached ordering/grouping whenever possible
  if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ] && command -v python3 >/dev/null 2>&1; then
    MUTATIONS_FILE="$mutation_file" MUTATION_TTL="$mutation_ttl" python3 -u - "$cache_file" <<'PY'
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

cache_file = sys.argv[1]

# fzf reload/focus can terminate the producer early; exit quietly on SIGPIPE.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

RESET = "\033[0m"

def color(code, text):
    return f"\033[{code}m{text}{RESET}"

def display_session_entry(name, path_display):
    return f"{color('38;5;42', '')}  {color('1;38;5;81', name)}  {color('2;38;5;246', path_display)}"

def display_worktree_entry(path_display):
    return f"{color('38;5;214', '')}  {color('38;5;221', path_display)}"

def display_dir_entry(path_display):
    return f"{color('38;5;75', '')}  {color('38;5;110', path_display)}"

def resolve_path(p: str) -> str:
    try:
        return str(Path(p).resolve())
    except Exception:
        return p

def find_worktree_root_for_path(p: str) -> str:
    cur = Path(p)
    if cur.is_file():
        cur = cur.parent
    try:
        cur = cur.resolve()
    except Exception:
        cur = Path(p)
    for _ in range(12):
        if (cur / ".git").exists():
            return resolve_path(str(cur))
        if cur.parent == cur:
            break
        cur = cur.parent
    return ""

def tildefy(p: str) -> str:
    home = os.path.expanduser("~")
    if p == home:
        return "~"
    if p.startswith(home + "/"):
        return "~/" + p[len(home) + 1 :]
    return p

def head_branch_for_worktree_root(root: str) -> str:
    gitp = Path(root) / ".git"
    gitdir = None
    try:
        if gitp.is_dir():
            gitdir = gitp
        elif gitp.is_file():
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if first.startswith("gitdir:"):
                raw = first.split(":", 1)[1].strip()
                gitdir = Path(raw) if os.path.isabs(raw) else (Path(root) / raw)
    except Exception:
        gitdir = None
    if gitdir is None:
        return ""
    try:
        head = Path(gitdir).resolve().joinpath("HEAD").read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        if ref.startswith("refs/heads/"):
            return ref[len("refs/heads/") :]
    return ""

def repo_display_for_root(root: str) -> str:
    rootp = Path(root)
    repo = rootp.name
    root_branch = head_branch_for_worktree_root(root)
    if root_branch and repo == root_branch:
        repo = rootp.parent.name
    return repo or rootp.name

def tmux_out(args):
    return subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout

def load_mutation_tombstones():
    mutation_path = os.environ.get("MUTATIONS_FILE", "").strip()
    ttl_raw = os.environ.get("MUTATION_TTL", "300").strip()
    try:
        ttl = int(ttl_raw or "300")
    except Exception:
        ttl = 300
    path_prefixes = set()
    session_targets = set()
    if not mutation_path or not os.path.exists(mutation_path):
        return path_prefixes, session_targets
    now = int(time.time())
    with open(mutation_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            ts_s, kind, value = parts
            if not value:
                continue
            try:
                ts = int(ts_s)
            except Exception:
                continue
            if ttl >= 0 and (now - ts) > ttl:
                continue
            if kind == "PATH_PREFIX":
                path_prefixes.add(value)
            elif kind == "SESSION_TARGET":
                session_targets.add(value)
    return path_prefixes, session_targets

mutation_path_prefixes, mutation_session_targets = load_mutation_tombstones()

def path_tombstoned(kind: str, p: str) -> bool:
    if kind not in ("dir", "worktree", "session"):
        return False
    if not p:
        return False
    for base in mutation_path_prefixes:
        if p == base or p.startswith(base + "/"):
            return True
    return False

def session_tombstoned(name: str) -> bool:
    return bool(name and name in mutation_session_targets)

current_name = tmux_out([ "tmux", "display-message", "-p", "#S" ]).strip()
current_path = tmux_out([ "tmux", "display-message", "-p", "#{session_path}" ]).strip()
current_rp = resolve_path(current_path) if current_path else ""
current_wt_root = find_worktree_root_for_path(current_rp) if current_rp else ""

sess_out = tmux_out([ "tmux", "list-sessions", "-F", "#{session_name}\t#{session_path}" ])
sess_by_rpath = {}  # rpath -> name (also keyed by worktree root when detected)
for row in sess_out.splitlines():
    if not row:
        continue
    name, _, path = row.partition("\t")
    name = name.strip()
    path = path.strip()
    if not name:
        continue
    rp = resolve_path(path) if path else ""
    if not rp:
        continue
    if name == current_name:
        continue
    if path_tombstoned("session", rp) or session_tombstoned(name):
        continue
    sess_by_rpath[rp] = name
    wt_root = find_worktree_root_for_path(rp)
    if wt_root:
        sess_by_rpath.setdefault(wt_root, name)

printed_sessions = set()

with open(cache_file, "r", encoding="utf-8", errors="replace") as f:
    for raw in f:
        line = raw.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            print(line)
            continue
        display, kind, path, meta, target = parts[:5]
        # Cache rows are already emitted as absolute normalized paths by the
        # indexer; resolving every row here turns cold-start into thousands of
        # filesystem stats. Keep cache paths as-is and only resolve live tmux
        # paths above.
        rpath = path if path else ""

        if path_tombstoned(kind, rpath):
            continue
        if kind == "session" and session_tombstoned(target):
            continue

        # Never show the current session path (or its worktree root) as a
        # directory/worktree candidate.
        if kind in ( "dir", "worktree" ):
            if current_rp and rpath == current_rp:
                continue
            if current_wt_root and rpath == current_wt_root:
                continue

        if kind == "session":
            label = target
            if "|expected=" in meta:
                label = meta.split("|expected=", 1)[1]
            if target:
                printed_sessions.add(target)
            if rpath:
                printed_sessions.add(rpath)
            if label and rpath:
                print(f"{display_session_entry(label, tildefy(rpath))}\t{kind}\t{path}\t{meta}\t{target}")
            else:
                print(line)
            continue

        # Promote a cached worktree to a session if a session now exists there.
        if kind == "worktree" and rpath and rpath in sess_by_rpath:
            name = sess_by_rpath[rpath]
            # meta: wt_root:<br> or wt:<br>
            branch = ""
            is_root = False
            if meta.startswith("wt_root:"):
                branch = meta[len("wt_root:") :]
                is_root = True
            elif meta.startswith("wt:"):
                branch = meta[len("wt:") :]
            expected = ""
            if branch and target:
                repo = repo_display_for_root(target)
                expected = f"{repo}|{branch}"
            disp = display_session_entry(expected, tildefy(rpath)) if expected else display_session_entry(name, tildefy(rpath))
            meta_base = f"sess_root:{branch}" if is_root else f"sess_wt:{branch}"
            sess_meta = meta_base
            if expected and name != expected:
                sess_meta = f"{meta_base}|expected={expected}"
            print(f"{disp}\tsession\t{rpath}\t{sess_meta}\t{name}")
            printed_sessions.add(name)
            printed_sessions.add(rpath)
            continue

        # Hide a cached dir if a session now exists there.
        if kind == "dir" and rpath and rpath in sess_by_rpath:
            name = sess_by_rpath[rpath]
            disp = display_session_entry(name, tildefy(rpath))
            print(f"{disp}\tsession\t{rpath}\t\t{name}")
            printed_sessions.add(name)
            printed_sessions.add(rpath)
            continue

        if kind == "worktree" and rpath:
            print(f"{display_worktree_entry(tildefy(rpath))}\t{kind}\t{path}\t{meta}\t{target}")
            continue

        if kind == "dir" and rpath:
            print(f"{display_dir_entry(tildefy(rpath))}\t{kind}\t{path}\t{meta}\t{target}")
            continue

        print(line)

# Append any sessions not represented by cache lines (keeps picker usable even
# before the first index build completes).
for rp, name in sorted(sess_by_rpath.items(), key=lambda x: x[1]):
    if name in printed_sessions or rp in printed_sessions:
        continue
    if path_tombstoned("session", rp) or session_tombstoned(name):
        continue
    disp = display_session_entry(name, tildefy(rp))
    print(f"{disp}\tsession\t{rp}\t\t{name}")
PY
    exit 0
  fi

  cat "$cache_file"
  exit 0
fi

# Kick off a background refresh if we're inside tmux.
if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux run-shell -b "$HOME/.config/tmux/scripts/pick_session_index_update.sh --quiet --quick-only" 2>/dev/null || true
fi

# Give the background updater a moment to produce the cache on first run.
elapsed=0
while [ "$elapsed" -lt "$wait_ms" ]; do
  if [ -f "$cache_file" ]; then
    cat "$cache_file"
    exit 0
  fi
  sleep 0.03
  elapsed="$((elapsed + 30))"
done

# Fallback: show tmux sessions (fast) + home.
if command -v tmux >/dev/null 2>&1; then
  cur="$(tmux display-message -p '#S' 2>/dev/null || true)"
  tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null | while IFS=$'\t' read -r name path; do
    [ -n "$name" ] || continue
    [ "$name" = "$cur" ] && continue
    tpath="$path"
    # shellcheck disable=SC2088
    case "$path" in
      "$HOME") tpath="~" ;;
      "$HOME"/*) tpath="~/${path#"$HOME"/}" ;;
    esac
    # shellcheck disable=SC2088
    printf '%s\t%s\t%s\t%s\t%s\n' "$(display_session_entry "$name" "$tpath")" "session" "$path" "" "$name"
  done
fi

printf '%s\t%s\t%s\t%s\t%s\n' "$(display_dir_entry '~')" "dir" "$HOME" "" ""
