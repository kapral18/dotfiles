#!/usr/bin/env bash
set -euo pipefail

tmux_opt() {
  local key="$1"
  local default_value="$2"
  local value=""
  if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
    value="$(tmux show-option -gqv "${key}" 2>/dev/null || true)"
  fi
  if [ -n "$value" ]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

now_epoch() { date +%s; }

mtime_epoch() {
  local f="$1"
  if stat -c %Y "$f" >/dev/null 2>&1; then
    stat -c %Y "$f"
    return 0
  fi
  stat -f %m "$f"
}

force=0
quiet=0
ttl_override=""
lock_stale_seconds=180
quick_only=0

while [ $# -gt 0 ]; do
  case "$1" in
  --force) force=1 ;;
  --quiet) quiet=1 ;;
  --ttl=*) ttl_override="${1#--ttl=}" ;;
  --lock-stale-seconds=*) lock_stale_seconds="${1#--lock-stale-seconds=}" ;;
  --quick-only) quick_only=1 ;;
  esac
  shift
done

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
mkdir -p "$cache_dir"

ttl="$(tmux_opt '@pick_session_cache_ttl' '60')"
mutation_ttl="$(tmux_opt '@pick_session_mutation_tombstone_ttl' '300')"
if [ -n "$ttl_override" ]; then
  ttl="$ttl_override"
fi
case "$mutation_ttl" in
'' | *[!0-9]*) mutation_ttl=300 ;;
esac

if [ "$force" -ne 1 ] && [ -f "$cache_file" ]; then
  mt="$(mtime_epoch "$cache_file" 2>/dev/null || echo 0)"
  age="$(($(now_epoch) - mt))"
  if [ "$age" -ge 0 ] && [ "$age" -lt "$ttl" ]; then
    exit 0
  fi
fi

lock_dir="${cache_file}.lock"
if ! mkdir "$lock_dir" 2>/dev/null; then
  pid_file="${lock_dir}/pid"
  stale=0
  if [ -f "$pid_file" ]; then
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      exit 0
    fi
    stale=1
  else
    mt="$(mtime_epoch "$lock_dir" 2>/dev/null || echo 0)"
    age="$(($(now_epoch) - mt))"
    if [ "$age" -ge "$lock_stale_seconds" ]; then
      stale=1
    fi
  fi
  if [ "$stale" -ne 1 ]; then
    # Another update is already running.
    exit 0
  fi
  rm -rf "$lock_dir" 2>/dev/null || exit 0
  mkdir "$lock_dir" 2>/dev/null || exit 0
fi
cleanup() {
  rm -f "${tmp_quick:-}" "${tmp_full:-}" "${tmp_combined:-}" "${tmp_sessions:-}" 2>/dev/null || true
  rm -f "${lock_dir}/pid" 2>/dev/null || true
  rmdir "$lock_dir" 2>/dev/null || true
}
trap cleanup EXIT
printf '%s\n' "$$" >"${lock_dir}/pid" 2>/dev/null || true

gen="$HOME/.config/tmux/scripts/pick_session_index.sh"
if [ ! -x "$gen" ]; then
  exit 0
fi

publish_cache_from() {
  local src="$1"
  local out_tmp
  [ -f "$src" ] || return 1
  out_tmp="$(mktemp -t pick_session_items.XXXXXX)"
  if [ -f "$pending_file" ] || [ -f "$mutation_file" ]; then
    CACHE_FILE="$src" \
      PENDING_FILE="$pending_file" \
      MUTATIONS_FILE="$mutation_file" \
      MUTATION_TTL="$mutation_ttl" \
      CACHE_OUT="$out_tmp" python3 - <<'PY'
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
        [ "tmux", "list-sessions", "-F", "#{session_name}" ],
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
    if kind not in ("dir", "worktree", "session"):
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
PY
  else
    cp "$src" "$out_tmp"
  fi
  mv -f "$out_tmp" "$cache_file"
}

file_has_dir_rows() {
  local f="$1"
  [ -f "$f" ] || return 1
  awk -F $'\t' 'NF>=5 && $2 == "dir" { found=1; exit } END { exit(found?0:1) }' "$f" 2>/dev/null
}

file_has_worktree_rows() {
  local f="$1"
  [ -f "$f" ] || return 1
  awk -F $'\t' 'NF>=5 && $2 == "worktree" { found=1; exit } END { exit(found?0:1) }' "$f" 2>/dev/null
}

file_has_non_session_rows() {
  local f="$1"
  [ -f "$f" ] || return 1
  awk -F $'\t' 'NF>=5 && $2 != "session" { found=1; exit } END { exit(found?0:1) }' "$f" 2>/dev/null
}

build_cache_refreshing_sessions_preserving_others() {
  local src="$1"
  local out="$2"

  : >"$out"
  # When src has both sessions and worktrees, preserve its repo-grouped order
  # (sessions and worktrees from the same repo together). Only append dirs from
  # cache. This keeps "kibana|main", "kibana|feature-x" grouped with kibana
  # worktrees instead of flattening all sessions then all worktrees.
  if file_has_worktree_rows "$src"; then
    awk -F $'\t' 'NF>=5 && ($2 == "session" || $2 == "worktree") { print }' "$src" 2>/dev/null >>"$out" || true
    if file_has_dir_rows "$src"; then
      awk -F $'\t' 'NF>=5 && $2 == "dir" { print }' "$src" 2>/dev/null >>"$out" || true
    elif file_has_dir_rows "$cache_file"; then
      awk -F $'\t' 'NF>=5 && $2 == "dir" { print }' "$cache_file" 2>/dev/null >>"$out" || true
    fi
    awk -F $'\t' 'NF>=5 && $2 != "session" && $2 != "worktree" && $2 != "dir" { print }' "$src" 2>/dev/null >>"$out" || true
    return 0
  fi

  # Fallback: kind-based merge when src has only sessions (e.g. minimal scan).
  awk -F $'\t' 'NF>=5 && $2 == "session" { print }' "$src" 2>/dev/null >>"$out" || true
  if file_has_worktree_rows "$cache_file"; then
    awk -F $'\t' 'NF>=5 && $2 == "worktree" { print }' "$cache_file" 2>/dev/null >>"$out" || true
  else
    awk -F $'\t' 'NF>=5 && $2 == "worktree" { print }' "$src" 2>/dev/null >>"$out" || true
  fi
  if file_has_dir_rows "$cache_file"; then
    awk -F $'\t' 'NF>=5 && $2 == "dir" { print }' "$cache_file" 2>/dev/null >>"$out" || true
  else
    awk -F $'\t' 'NF>=5 && $2 == "dir" { print }' "$src" 2>/dev/null >>"$out" || true
  fi
  if file_has_non_session_rows "$cache_file"; then
    awk -F $'\t' 'NF>=5 && $2 != "session" && $2 != "worktree" && $2 != "dir" { print }' "$cache_file" 2>/dev/null >>"$out" || true
  else
    awk -F $'\t' 'NF>=5 && $2 != "session" && $2 != "worktree" && $2 != "dir" { print }' "$src" 2>/dev/null >>"$out" || true
  fi
}

tmp_quick="$(mktemp -t pick_session_items.quick.XXXXXX)"
tmp_full="$(mktemp -t pick_session_items.full.XXXXXX)"
tmp_sessions="$(mktemp -t pick_session_items.sessions.XXXXXX)"
tmp_combined="$(mktemp -t pick_session_items.combined.XXXXXX)"

if [ "$quiet" -ne 1 ] && command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux display-message -d 1500 "pick_session: updating list…" 2>/dev/null || true
fi

quick_ok=0
full_ok=0
quick_published=0
if [ "$quick_only" -eq 1 ]; then
  # Quick refresh: sessions only. We merge into the existing cache to preserve
  # the full worktree/dir lists (quick scans do not discover all worktrees).
  if "$gen" --quick --sessions-only >"$tmp_quick" 2>/dev/null; then
    quick_ok=1
    if [ -s "$tmp_quick" ]; then
      # Always try to merge to preserve worktrees and directories in the cache.
      if [ -f "$cache_file" ]; then
        build_cache_refreshing_sessions_preserving_others "$tmp_quick" "$tmp_combined" || true
        if [ -s "$tmp_combined" ]; then
          publish_cache_from "$tmp_combined" || true
        else
          publish_cache_from "$tmp_quick" || true
        fi
      else
        publish_cache_from "$tmp_quick" || true
      fi
      quick_published=1
    fi
  fi
  if [ "$quick_ok" -ne 1 ] || [ "$quick_published" -ne 1 ]; then
    exit 0
  fi
else
  # Quick scan: sessions only (merged into existing cache).
  "$gen" --quick --sessions-only >"$tmp_quick" 2>/dev/null &
  pid_quick=$!
  # Perform a full scan (including directories) in the background.
  "$gen" >"$tmp_full" 2>/dev/null &
  pid_full=$!

  if wait "$pid_quick"; then
    quick_ok=1
    if [ -s "$tmp_quick" ]; then
      # Merge new sessions into existing cache immediately.
      if [ -f "$cache_file" ]; then
        build_cache_refreshing_sessions_preserving_others "$tmp_quick" "$tmp_combined" || true
        if [ -s "$tmp_combined" ]; then
          publish_cache_from "$tmp_combined" || true
        else
          publish_cache_from "$tmp_quick" || true
        fi
      else
        publish_cache_from "$tmp_quick" || true
      fi
      quick_published=1
    fi
  fi

  if wait "$pid_full"; then
    full_ok=1
    if [ -s "$tmp_full" ]; then
      publish_cache_from "$tmp_full" || true
    elif [ "$quick_published" -eq 0 ] && [ "$quick_ok" -eq 1 ] && [ -s "$tmp_quick" ]; then
      publish_cache_from "$tmp_quick" || true
    fi
  fi

  if [ "$full_ok" -ne 1 ] && [ "$quick_ok" -eq 1 ] && [ "$quick_published" -eq 0 ] && [ -s "$tmp_quick" ]; then
    publish_cache_from "$tmp_quick" || true
    quick_published=1
  fi

  if [ "$full_ok" -ne 1 ] && [ "$quick_ok" -ne 1 ]; then
    exit 0
  fi
fi

if [ "$quiet" -ne 1 ] && command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux display-message -d 1500 "pick_session: list updated" 2>/dev/null || true
fi
