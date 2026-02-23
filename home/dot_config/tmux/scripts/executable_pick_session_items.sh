#!/usr/bin/env bash
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
session_tombstone_live_grace_s="${PICK_SESSION_SESSION_TOMBSTONE_LIVE_GRACE_S:-2}"

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
  session_tombstone_live_grace_s="$(tmux show-option -gqv '@pick_session_session_tombstone_live_grace_s' 2>/dev/null || printf '%s' "$session_tombstone_live_grace_s")"
fi
case "$wait_ms" in
  ''|*[!0-9]*) wait_ms=0 ;;
esac
case "$mutation_ttl" in
  ''|*[!0-9]*) mutation_ttl=300 ;;
esac
case "$session_tombstone_live_grace_s" in
  ''|*[!0-9]*) session_tombstone_live_grace_s=2 ;;
esac

if [ -f "$cache_file" ]; then
  # Keep the UI correct even if the cache is slightly stale:
  # - Don't show the current session's path as a worktree/dir entry
  # - If a cached worktree/dir now has a session, show it as a session
  # - Preserve cached ordering/grouping whenever possible
  if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ] && command -v python3 >/dev/null 2>&1; then
    MUTATIONS_FILE="$mutation_file" MUTATION_TTL="$mutation_ttl" SESSION_TOMBSTONE_LIVE_GRACE_S="$session_tombstone_live_grace_s" python3 -u - "$cache_file" <<'PY'
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

def worktree_group_root_for_path(p: str) -> str:
    wt = find_worktree_root_for_path(p)
    if not wt:
        return ""
    gitp = Path(wt) / ".git"
    try:
        if gitp.is_dir():
            return wt
        if gitp.is_file():
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if not first.startswith("gitdir:"):
                return wt
            raw = first.split(":", 1)[1].strip()
            gitdir = Path(raw) if os.path.isabs(raw) else (Path(wt) / raw)
            gitdir = Path(resolve_path(str(gitdir)))
            norm = str(gitdir).replace("\\", "/")
            if "/worktrees/" in norm:
                common_dir = Path(resolve_path(str(gitdir.parent.parent)))
                return resolve_path(str(common_dir.parent))
    except Exception:
        return wt
    return wt

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
    live_grace_raw = os.environ.get("SESSION_TOMBSTONE_LIVE_GRACE_S", "2").strip()
    try:
        ttl = int(ttl_raw or "300")
    except Exception:
        ttl = 300
    try:
        live_grace = int(live_grace_raw or "2")
    except Exception:
        live_grace = 2
    path_prefixes = set()
    session_targets = set()
    fresh_session_targets = set()
    if not mutation_path or not os.path.exists(mutation_path):
        return path_prefixes, session_targets, fresh_session_targets
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
                if live_grace >= 0 and (now - ts) <= live_grace:
                    fresh_session_targets.add(value)
    return path_prefixes, session_targets, fresh_session_targets

mutation_path_prefixes, mutation_session_targets, fresh_session_targets = load_mutation_tombstones()

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
live_session_names = set()
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
    if path_tombstoned("session", rp):
        continue
    if name in fresh_session_targets:
        continue
    live_session_names.add(name)
    sess_by_rpath[rp] = name
    wt_root = find_worktree_root_for_path(rp)
    if wt_root:
        sess_by_rpath.setdefault(wt_root, name)

printed_sessions = set()
def parse_worktree_meta(meta: str):
    if meta.startswith("wt_root:"):
        return (meta[len("wt_root:") :], True)
    if meta.startswith("wt:"):
        return (meta[len("wt:") :], False)
    return ("", False)

def parse_session_worktree_meta(meta: str):
    meta_base = meta.split("|", 1)[0]
    if meta_base.startswith("sess_root:"):
        return (meta_base[len("sess_root:") :], True)
    if meta_base.startswith("sess_wt:"):
        return (meta_base[len("sess_wt:") :], False)
    return (None, None)

def synthesize_worktree_session_row(rec, live_name: str):
    rpath = rec["rpath"]
    branch = rec.get("branch") or ""
    root = rec.get("group_root") or ""
    is_root = bool(rec.get("is_root"))
    expected = ""
    if branch and root:
        expected = f"{repo_display_for_root(root)}|{branch}"
    label = expected or live_name
    meta_base = f"sess_root:{branch}" if is_root else f"sess_wt:{branch}"
    meta = meta_base
    if expected and live_name and live_name != expected:
        meta = f"{meta_base}|expected={expected}"
    return f"{display_session_entry(label, tildefy(rpath))}\tsession\t{rpath}\t{meta}\t{live_name}"

def cache_session_row_label(row):
    label = row["target"]
    meta = row.get("meta") or ""
    if "|expected=" in meta:
        label = meta.split("|expected=", 1)[1]
    return label

def output_session_row(line: str, rpath: str, meta: str, target: str):
    label = target
    if "|expected=" in meta:
        label = meta.split("|expected=", 1)[1]
    if target:
        printed_sessions.add(target)
    if rpath:
        printed_sessions.add(rpath)
    if label and rpath:
        print(f"{display_session_entry(label, tildefy(rpath))}\tsession\t{rpath}\t{meta}\t{target}")
    else:
        print(line)

def output_dir_or_promoted_dir(row):
    rpath = row["rpath"]
    if rpath and rpath in sess_by_rpath:
        name = sess_by_rpath[rpath]
        print(f"{display_session_entry(name, tildefy(rpath))}\tsession\t{rpath}\t\t{name}")
        printed_sessions.add(name)
        printed_sessions.add(rpath)
        return
    print(f"{display_dir_entry(tildefy(rpath))}\tdir\t{row['path']}\t{row['meta']}\t{row['target']}")

def group_row_info(row):
    kind = row["kind"]
    rpath = row["rpath"]
    meta = row["meta"]
    target = row["target"]
    if kind == "worktree":
        branch, is_root = parse_worktree_meta(meta)
        root = target or ""
        if not root:
            return None
        return { "group_root": root, "branch": branch, "is_root": is_root }
    if kind == "session":
        branch, is_root = parse_session_worktree_meta(meta)
        if branch is None:
            return None
        root = rpath if is_root else worktree_group_root_for_path(rpath)
        if not root:
            return None
        return { "group_root": root, "branch": branch or "", "is_root": bool(is_root) }
    return None

def flush_group(rows):
    if not rows:
        return
    grouped = {}
    group_root = rows[0]["group_root"]
    for row in rows:
        path = row["rpath"]
        if not path:
            continue
        rec = grouped.setdefault(path, {
            "rpath": path,
            "group_root": row["group_root"],
            "branch": row.get("branch", ""),
            "is_root": row.get("is_root", False),
            "worktree_row": None,
            "session_row": None,
        })
        if row["kind"] == "worktree":
            rec["worktree_row"] = row
            rec["branch"] = row.get("branch", rec["branch"])
            rec["is_root"] = row.get("is_root", rec["is_root"])
        elif row["kind"] == "session":
            rec["session_row"] = row
            if row.get("branch") is not None:
                rec["branch"] = row.get("branch", rec["branch"])
            rec["is_root"] = row.get("is_root", rec["is_root"])

    def wt_sort_key(item):
        path, rec = item
        br = rec.get("branch", "") or ""
        return (0 if path == group_root or rec.get("is_root") else 1, br, path)

    emitted_paths = set()
    # Sessions first in group (live promotions + existing cached session rows).
    for path, rec in sorted(grouped.items(), key=wt_sort_key):
        live_name = sess_by_rpath.get(path, "")
        if live_name:
            print(synthesize_worktree_session_row(rec, live_name))
            printed_sessions.add(live_name)
            printed_sessions.add(path)
            emitted_paths.add(path)
            continue

        row = rec.get("session_row")
        if not row:
            continue
        target = row.get("target", "")
        # If the cache still contains a session row for a session that no
        # longer exists, treat it as stale so the worktree row can take over.
        if target and target not in live_session_names:
            continue
        if session_tombstoned(target) and target not in live_session_names:
            continue
        label = cache_session_row_label(row)
        print(f"{display_session_entry(label, tildefy(path))}\tsession\t{row['path']}\t{row['meta']}\t{target}")
        if target:
            printed_sessions.add(target)
        printed_sessions.add(path)
        emitted_paths.add(path)

    # Then remaining worktrees.
    for path, rec in sorted(grouped.items(), key=wt_sort_key):
        if path in emitted_paths:
            continue
        row = rec.get("worktree_row")
        if not row:
            continue
        print(f"{display_worktree_entry(tildefy(path))}\tworktree\t{row['path']}\t{row['meta']}\t{row['target']}")

def parse_cache_row(raw_line: str):
    line = raw_line.rstrip("\n")
    if not line:
        return None
    parts = line.split("\t")
    if len(parts) < 5:
        return { "raw": line, "parts": parts, "kind": "", "path": "", "meta": "", "target": "", "rpath": "" }
    _display, kind, path, meta, target = parts[:5]
    rpath = path if path else ""
    row = {
        "raw": line,
        "kind": kind,
        "path": path,
        "meta": meta,
        "target": target,
        "rpath": rpath,
    }
    info = group_row_info(row)
    if info:
        row.update(info)
    return row

current_group_rows = []
current_group_root = ""

def flush_current_group():
    global current_group_rows, current_group_root
    if current_group_rows:
        flush_group(current_group_rows)
        current_group_rows = []
        current_group_root = ""

with open(cache_file, "r", encoding="utf-8", errors="replace") as f:
    for raw in f:
        row = parse_cache_row(raw)
        if row is None:
            continue

        if len(row.get("parts", [])) and row.get("kind", "") == "":
            flush_current_group()
            print(row["raw"])
            continue

        kind = row["kind"]
        rpath = row["rpath"]
        meta = row["meta"]
        target = row["target"]

        if path_tombstoned(kind, rpath):
            continue
        if kind == "session" and session_tombstoned(target) and target not in live_session_names:
            continue
        if kind == "session" and target and target not in live_session_names:
            continue

        # Never show the current session path (or its worktree root) as a
        # directory/worktree candidate.
        if kind in ("dir", "worktree"):
            if current_rp and rpath == current_rp:
                continue
            if current_wt_root and rpath == current_wt_root:
                continue

        group_root = row.get("group_root", "")
        if group_root and kind in ("worktree", "session"):
            if current_group_root and group_root != current_group_root:
                flush_current_group()
            current_group_root = group_root
            current_group_rows.append(row)
            continue

        flush_current_group()

        if kind == "session":
            output_session_row(row["raw"], rpath, meta, target)
            continue

        if kind == "dir" and rpath:
            output_dir_or_promoted_dir(row)
            continue

        if kind == "worktree" and rpath:
            print(f"{display_worktree_entry(tildefy(rpath))}\t{kind}\t{row['path']}\t{meta}\t{target}")
            continue

        if kind == "dir" and rpath:
            print(f"{display_dir_entry(tildefy(rpath))}\t{kind}\t{row['path']}\t{meta}\t{target}")
            continue

        print(row["raw"])

flush_current_group()

# Append any sessions not represented by cache lines (keeps picker usable even
# before the first index build completes).
for rp, name in sorted(sess_by_rpath.items(), key=lambda x: x[1]):
    if name in printed_sessions or rp in printed_sessions:
        continue
    if path_tombstoned("session", rp):
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
