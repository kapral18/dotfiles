#!/usr/bin/env bash
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
session_tombstone_live_grace_s="${PICK_SESSION_SESSION_TOMBSTONE_LIVE_GRACE_S:-2}"
cache_was_present=0
[ -f "$cache_file" ] && cache_was_present=1

ansi_wrap() {
  local code="$1"
  local text="$2"
  printf '\033[%sm%s\033[0m' "$code" "$text"
}

display_session_entry() {
  local name="$1"
  printf '%s  %s' \
    "$(ansi_wrap '38;5;42' '')" \
    "$(ansi_wrap '1;38;5;81' "$name")"
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
'' | *[!0-9]*) wait_ms=0 ;;
esac
case "$mutation_ttl" in
'' | *[!0-9]*) mutation_ttl=300 ;;
esac
case "$session_tombstone_live_grace_s" in
'' | *[!0-9]*) session_tombstone_live_grace_s=2 ;;
esac

if [ "$cache_was_present" -eq 1 ]; then
  cache_has_dir_rows=0
  if awk -F $'\t' 'NF>=5 && $2 == "dir" { found=1; exit } END { exit(found?0:1) }' "$cache_file" 2>/dev/null; then
    cache_has_dir_rows=1
  fi

  # Light path: when cache has only session rows, skip full Python rehydration.
  # Tombstone filtering only (no worktree promotion).
  if awk -F $'\t' 'NF>=5 && ($2=="worktree" || $2=="dir") { exit 1 }' "$cache_file" 2>/dev/null; then
    if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ] && command -v python3 >/dev/null 2>&1; then
      MUTATIONS_FILE="$mutation_file" PENDING_FILE="$pending_file" MUTATION_TTL="$mutation_ttl" SESSION_TOMBSTONE_LIVE_GRACE_S="$session_tombstone_live_grace_s" python3 -u - "$cache_file" <<'PYLIGHT'
import os
import signal
import sys
import time
from pathlib import Path

signal.signal(signal.SIGPIPE, signal.SIG_DFL)
cache_file = sys.argv[1]
mutations_file = os.environ.get("MUTATIONS_FILE", "")
pending_file = os.environ.get("PENDING_FILE", "")
mutation_ttl = int(os.environ.get("MUTATION_TTL", "300") or "300")
live_grace = int(os.environ.get("SESSION_TOMBSTONE_LIVE_GRACE_S", "2") or "2")

path_prefixes = set()
session_targets = set()
fresh_session_targets = set()
if mutations_file and os.path.exists(mutations_file):
    now = int(time.time())
    with open(mutations_file, "r", encoding="utf-8", errors="ignore") as f:
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
            if mutation_ttl >= 0 and (now - ts) > mutation_ttl:
                continue
            if kind == "PATH_PREFIX":
                path_prefixes.add(value)
            elif kind == "SESSION_TARGET":
                session_targets.add(value)
                if live_grace >= 0 and (now - ts) <= live_grace:
                    fresh_session_targets.add(value)

live_session_names = set()
try:
    import subprocess
    out = subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
    for row in (out or "").splitlines():
        if row.strip():
            live_session_names.add(row.strip())
except Exception:
    pass

def resolve_path(p):
    try:
        return str(Path(p).resolve())
    except Exception:
        return p

def gitdir_for_path(p: str) -> str:
    try:
        cur = Path(p)
        if cur.is_file():
            cur = cur.parent
        gitp = cur / ".git"
        if gitp.is_dir():
            return str(gitp)
        if gitp.is_file():
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if not first.startswith("gitdir:"):
                return ""
            raw = first.split(":", 1)[1].strip()
            gitdir = (cur / raw) if raw and not os.path.isabs(raw) else Path(raw)
            try:
                return str(gitdir.resolve())
            except Exception:
                return str(gitdir)
    except Exception:
        return ""
    return ""

def head_branch(gitdir: str) -> str:
    if not gitdir:
        return ""
    try:
        head = Path(gitdir, "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        if ref.startswith("refs/heads/"):
            return ref[len("refs/heads/") :]
    return ""

def worktree_meta_for_path(p: str) -> str:
    gd = gitdir_for_path(p)
    br = head_branch(gd)
    return f"wt_root:{br}" if br else ""

if pending_file and os.path.exists(pending_file):
    # Pending removals should not hide *live sessions*.
    # This light path only runs when the cache has sessions only, so pending
    # worktree suppression is not relevant here.
    pass

def path_tombstoned(kind, p):
    if kind not in ("dir", "worktree", "session") or not p:
        return False
    for base in path_prefixes:
        if p == base or p.startswith(base + "/"):
            return True
    return False

def session_tombstoned(name):
    return bool(name and name in session_targets)

with open(cache_file, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            print(line)
            continue
        kind, path, target = parts[1], parts[2], parts[4] if len(parts) > 4 else ""
        rpath = resolve_path(path) if path else ""
        if path_tombstoned(kind, rpath):
            continue
        if kind == "session" and session_tombstoned(target) and target not in live_session_names:
            # Keep the path selectable even when the session is killed/hidden.
            if rpath:
                base = os.path.basename(rpath.rstrip("/")) or rpath
                meta = worktree_meta_for_path(rpath)
                br = meta.split(":", 1)[1] if ":" in meta else ""
                mk = f"{base}|{br} {base} {rpath}" if br else f"{base} {rpath}"
                # Prefer a "worktree-like" entry when it's a git checkout.
                if os.path.exists(os.path.join(rpath, ".git")):
                    print(f"  {rpath}\tworktree\t{rpath}\t{meta}\t{rpath}\t{mk}")
                else:
                    print(f"  {rpath}\tdir\t{rpath}\t\t\t{mk}")
            continue
        if kind == "session" and target in fresh_session_targets:
            # Optimistic hide for recently-killed sessions should still keep the
            # underlying path selectable.
            if rpath:
                base = os.path.basename(rpath.rstrip("/")) or rpath
                meta = worktree_meta_for_path(rpath)
                br = meta.split(":", 1)[1] if ":" in meta else ""
                mk = f"{base}|{br} {base} {rpath}" if br else f"{base} {rpath}"
                if os.path.exists(os.path.join(rpath, ".git")):
                    print(f"  {rpath}\tworktree\t{rpath}\t{meta}\t{rpath}\t{mk}")
                else:
                    print(f"  {rpath}\tdir\t{rpath}\t\t\t{mk}")
            continue
        print(line)
PYLIGHT
      exit 0
    fi
  fi

  # Full rehydration when cache has worktree/dir rows (session promotion, etc.)
  if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ] && command -v python3 >/dev/null 2>&1; then
    scan_roots_raw="$(tmux show-option -gqv '@pick_session_worktree_scan_roots' 2>/dev/null || printf '%s' "$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share")"
    MUTATIONS_FILE="$mutation_file" PENDING_FILE="$pending_file" MUTATION_TTL="$mutation_ttl" SESSION_TOMBSTONE_LIVE_GRACE_S="$session_tombstone_live_grace_s" PICK_SESSION_SCAN_ROOTS="$scan_roots_raw" python3 -u - "$cache_file" <<'PY'
import os
import re
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

def display_session_entry_with_suffix(name, path_display, suffix=""):
    suffix = suffix or ""
    return f"{color('38;5;42', '')}  {color('1;38;5;81', name)}{suffix}"

def display_worktree_entry(path_display):
    return f"{color('38;5;214', '')}  {color('38;5;221', path_display)}"

def display_dir_entry(path_display):
    return f"{color('38;5;75', '')}  {color('38;5;110', path_display)}"

def tildefy(p: str) -> str:
    home = os.path.expanduser("~")
    if p == home:
        return "~"
    if p.startswith(home + "/"):
        return "~/" + p[len(home) + 1 :]
    return p

def match_key(*parts: str) -> str:
    out = []
    for p in parts:
        p = (p or "").strip()
        if p:
            out.append(p)
    return " ".join(out)

def resolve_path(p):
    try:
        return str(Path(p).resolve())
    except Exception:
        return p

def is_bag_path(p: str) -> bool:
    if not p:
        return False
    s = p.replace("\\", "/")
    return "/.bag/" in s or s.endswith("/.bag")

def tmux_out(args):
    return subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout

def is_git_dir(p: str) -> bool:
    try:
        pp = Path(p)
        return (pp / ".git").exists() or (pp / "HEAD").exists()
    except Exception:
        return False

DEFAULT_BRANCH_DIRS = { "main", "master", "trunk", "develop", "dev" }

def home_rel(p: str) -> str:
    if not p:
        return ""
    try:
        rp = resolve_path(p)
    except Exception:
        rp = p
    home = os.path.expanduser("~")
    if rp == home:
        return ""
    if rp.startswith(home + os.sep):
        rel = rp[len(home) + 1 :]
        return rel.strip("/").replace(os.sep, "/")
    return rp.replace(os.sep, "/").strip("/")

def repo_id_for_root_checkout(root_checkout: str) -> str:
    if not root_checkout:
        return ""
    try:
        rc = Path(root_checkout)
        repo_path = str(rc.parent) if rc.name in DEFAULT_BRANCH_DIRS else str(rc)
        return home_rel(repo_path)
    except Exception:
        return home_rel(root_checkout)

def worktree_branch_for_path(p: str) -> str:
    p = resolve_path(p)
    if not p or not os.path.isdir(p):
        return ""
    try:
        gitp = Path(p) / ".git"
        gitdir = ""
        if gitp.is_dir():
            gitdir = str(gitp)
        elif gitp.is_file():
            first = gitp.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            if first.startswith("gitdir:"):
                raw = first.split(":", 1)[1].strip()
                gp = (Path(p) / raw) if raw and not os.path.isabs(raw) else Path(raw)
                gitdir = resolve_path(str(gp))
        if not gitdir:
            return ""
        head = Path(gitdir, "HEAD").read_text(encoding="utf-8", errors="replace").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            if ref.startswith("refs/heads/"):
                return ref[len("refs/heads/") :]
        return ""
    except Exception:
        return ""

def worktree_root_for_path(p: str) -> str:
    p = resolve_path(p)
    if not p or not os.path.isdir(p):
        return ""
    try:
        out = subprocess.run(
            ["git", "-C", p, "rev-parse", "--git-common-dir"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
    except Exception:
        return ""
    if not out:
        return ""
    common = out
    if not common.startswith("/"):
        common = resolve_path(os.path.join(p, common))
    else:
        common = resolve_path(common)
    if os.path.basename(common) == ".git":
        return resolve_path(os.path.dirname(common))
    return common

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

def load_pending_path_prefixes():
    pending_path = os.environ.get("PENDING_FILE", "").strip()
    path_prefixes = set()
    if not pending_path or not os.path.exists(pending_path):
        return path_prefixes
    with open(pending_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            if "\t" in line:
                tag, value = line.split("\t", 1)
                if tag in ("WT", "EX") and value:
                    path_prefixes.add(value)
            else:
                path_prefixes.add(line)
    return path_prefixes

mutation_path_prefixes, mutation_session_targets, fresh_session_targets = load_mutation_tombstones()
pending_path_prefixes = load_pending_path_prefixes()

def path_tombstoned(kind: str, p: str) -> bool:
    if kind not in ("dir", "worktree", "session") or not p:
        return False
    for base in mutation_path_prefixes:
        if p == base or p.startswith(base + "/"):
            return True
    if kind != "session":
        for base in pending_path_prefixes:
            if p == base or p.startswith(base + "/"):
                return True
    return False

current_name = tmux_out([ "tmux", "display-message", "-p", "#S" ]).strip()
sess_out = tmux_out([ "tmux", "list-sessions", "-F", "#{session_name}\t#{session_path}" ])
sess_by_rpath = {}
sess_raw_path = {}
live_session_names = set()
for row in sess_out.splitlines():
    if not row: continue
    name, _, path = row.partition("\t")
    name, path = name.strip(), path.strip()
    if not name or not path: continue
    rpath = resolve_path(path)
    if is_bag_path(rpath):
        continue
    if path_tombstoned("session", rpath) or name in fresh_session_targets:
        continue
    live_session_names.add(name)
    sess_by_rpath[rpath] = name
    sess_raw_path[rpath] = path

printed_sessions = set()
missing_sessions_emitted = False

def emit_missing_sessions():
    global missing_sessions_emitted
    if missing_sessions_emitted: return
    missing_sessions_emitted = True
    for rp, name in sorted(sess_by_rpath.items()):
        if name in printed_sessions or rp in printed_sessions:
            continue
        raw = sess_raw_path.get(rp, rp)
        suffix = color("2;38;5;244", " (current)") if name == current_name else ""
        disp = display_session_entry_with_suffix(name, "", suffix)
        print(f"{disp}\tsession\t{rp}\t\t{name}\t{match_key(name)}")
        printed_sessions.add(name)

def parse_cache_row(raw_line: str):
    line = raw_line.rstrip("\n")
    if not line: return None
    parts = line.split("\t")
    if len(parts) < 5: return None
    return { "raw": line, "kind": parts[1], "path": parts[2], "meta": parts[3], "target": parts[4], "mk": parts[5] if len(parts) > 5 else "" }

with open(cache_file, "r", encoding="utf-8", errors="replace") as f:
    for raw in f:
        row = parse_cache_row(raw)
        if not row:
            if raw.strip(): print(raw.rstrip("\n"))
            continue

        kind, path, target, meta = row["kind"], row["path"], row["target"], row["meta"]
        rpath = resolve_path(path) if path else ""
        if is_bag_path(rpath):
            continue
        if path_tombstoned(kind, rpath): continue
        if kind == "session":
            if target in printed_sessions:
                continue
            if target in fresh_session_targets:
                # Optimistic hide while the kill is in-flight; keep the path selectable.
                if rpath:
                    mk = match_key(Path(rpath).name, tildefy(rpath), rpath)
                    if is_git_dir(rpath):
                        root = worktree_root_for_path(rpath) or rpath
                        if root:
                            br = worktree_branch_for_path(rpath)
                            repo_id = repo_id_for_root_checkout(root)
                            meta = f"wt_root:{br}" if br and root == rpath else (f"wt:{br}" if br else "")
                            if repo_id:
                                meta += f"|repo={repo_id}"
                            print(f"{display_worktree_entry(tildefy(rpath))}\tworktree\t{rpath}\t{meta}\t{root}\t{mk}")
                    elif os.path.isdir(rpath):
                        print(f"{display_dir_entry(tildefy(rpath))}\tdir\t{rpath}\t\t\t{mk}")
                continue
            if target not in live_session_names:
                # The cache can contain session rows that temporarily replaced a
                # worktree row for the same path. If the session no longer
                # exists, emit a worktree entry so the path stays selectable.
                if rpath:
                    mk = match_key(Path(rpath).name, tildefy(rpath), rpath)
                    if is_git_dir(rpath):
                        root = worktree_root_for_path(rpath) or rpath
                        if root:
                            br = worktree_branch_for_path(rpath)
                            repo_id = repo_id_for_root_checkout(root)
                            meta = f"wt_root:{br}" if br and root == rpath else (f"wt:{br}" if br else "")
                            if repo_id:
                                meta += f"|repo={repo_id}"
                            print(f"{display_worktree_entry(tildefy(rpath))}\tworktree\t{rpath}\t{meta}\t{root}\t{mk}")
                    elif os.path.isdir(rpath):
                        print(f"{display_dir_entry(tildefy(rpath))}\tdir\t{rpath}\t\t\t{mk}")
                continue
            printed_sessions.add(target)
            printed_sessions.add(rpath)
            suffix = color("2;38;5;244", " (current)") if target == current_name else ""
            mk = match_key(target)
            print(f"{display_session_entry_with_suffix(target, '', suffix)}\tsession\t{path}\t{meta}\t{target}\t{mk}")
            continue

        if rpath in sess_by_rpath:
            continue

        print(row["raw"])

emit_missing_sessions()
PY
    exit 0
  fi

  # If python isn't available, still emit a 6th "match key" field so fzf can
  # prioritize name matching before paths.
  awk -F $'\t' '
	    BEGIN { OFS = "\t" }
	    NF < 5 { print; next }
	    NF >= 6 { print; next }
	    {
      kind = $2
      path = $3
      meta = $4
      target = $5
      base = path
      sub(".*/", "", base)
      mk = ""
      if (kind == "session") {
        mk = target
      } else if (kind == "worktree") {
        mk = base " " path
      } else if (kind == "dir") {
        mk = base " " path
	      } else {
	        mk = base " " path
	      }
	      print $1, kind, path, meta, target, mk
	    }
	  ' "$cache_file"
  exit 0
fi

# Kick off a background refresh if we're inside tmux.
if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  # If the cache is missing, prefer a full refresh in the background so the
  # next open (or a ctrl-r) has complete data.
  if [ "$cache_was_present" -eq 1 ]; then
    tmux run-shell -b "$HOME/.config/tmux/scripts/pick_session_index_update.sh --quiet --quick-only" 2>/dev/null || true
  else
    tmux run-shell -b "$HOME/.config/tmux/scripts/pick_session_index_update.sh --quiet" 2>/dev/null || true
  fi
fi

# Fast path: when cache is empty, show sessions + recent dirs immediately.
# No wait loop — wait_ms=0 by default for instant popup.
elapsed=0
while [ "$elapsed" -lt "$wait_ms" ]; do
  if [ -f "$cache_file" ]; then
    cat "$cache_file"
    exit 0
  fi
  sleep 0.03
  elapsed="$((elapsed + 30))"
done

# Fallback: tmux sessions + zoxide recent dirs (if available) + home.
# Sort sessions by path so same-repo sessions (e.g. ~/work/kibana, ~/code/kibana) group together.
if command -v tmux >/dev/null 2>&1; then
  cur="$(tmux display-message -p '#S' 2>/dev/null || true)"
  tmp_sessions="$(mktemp -t pick_session_fallback.XXXXXX)"
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
    base="$(basename "$path" 2>/dev/null || printf '%s' "$path")"
    mk="${name} ${base} ${tpath} ${path}"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(display_session_entry "$name" "$tpath")" "session" "$path" "" "$name" "$mk"
  done >"$tmp_sessions"
  [ -s "$tmp_sessions" ] && sort -t$'\t' -k3 "$tmp_sessions"
  rm -f "$tmp_sessions"
fi

# Add zoxide recent dirs (if available) for snappy discovery like tmux-session-wizard.
if command -v zoxide >/dev/null 2>&1; then
  zoxide query -l 2>/dev/null | while IFS= read -r path; do
    [ -n "$path" ] || continue
    [ -d "$path" ] || continue
    [ "$path" = "$HOME" ] && continue
    tpath="$path"
    # shellcheck disable=SC2088
    case "$path" in
    "$HOME") tpath="~" ;;
    "$HOME"/*) tpath="~/${path#"$HOME"/}" ;;
    esac
    base="$(basename "$path" 2>/dev/null || printf '%s' "$path")"
    mk="${base} ${tpath} ${path}"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(display_dir_entry "$tpath")" "dir" "$path" "" "" "$mk"
  done
fi

mk="home ~ $HOME"
printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(display_dir_entry '~')" "dir" "$HOME" "" "" "$mk"
