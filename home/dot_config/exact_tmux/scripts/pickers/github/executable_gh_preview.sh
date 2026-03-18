#!/usr/bin/env bash
# Preview a PR or issue for the GitHub picker.
# Reads a TSV line from fzf {f} (temp file) or raw argument.
#
# Caching: previews are cached per repo/kind/number with a short TTL.
# On cache hit, the cache is shown instantly and a background refresh
# updates it for next view.
#
# Body truncation: by default the description is truncated to BODY_MAX
# lines. Set GH_PREVIEW_FULL=1 (or pass --full) to show the entire body.
set -euo pipefail

BODY_MAX=15

# Expand mode: 0=all collapsed, 1=body expanded, 2=everything expanded
expand_mode="${GH_PREVIEW_EXPAND:-0}"
args=()
for a in "$@"; do
  case "$a" in
    --expand=*) expand_mode="${a#--expand=}" ;;
    --full) expand_mode=2 ;;
    *) args+=("$a") ;;
  esac
done
set -- "${args[@]+"${args[@]}"}"

if [ -f "${1:-}" ]; then
  line="$(head -n 1 "$1" 2> /dev/null || true)"
else
  line="${1:-}"
fi
[ -n "$line" ] || exit 0

kind="$(printf '%s' "$line" | awk -F $'\t' '{print $2}')"
repo="$(printf '%s' "$line" | awk -F $'\t' '{print $3}')"
num="$(printf '%s' "$line" | awk -F $'\t' '{print $4}')"

case "$kind" in
  header)
    printf '\033[2mSection header — select a PR or issue below.\033[0m\n'
    exit 0
    ;;
esac

[ -n "$repo" ] && [ -n "$num" ] || exit 0

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux/gh_preview"
mkdir -p "$cache_dir" 2> /dev/null || true
safe_repo="$(printf '%s' "$repo" | tr '/' '_')"
cache_file="${cache_dir}/${kind}_${safe_repo}_${num}.md"
cache_ttl=120
fetch_lock_dir="${cache_file}.fetch.lock"

# fast path for collapsed mode
if [ "${expand_mode:-0}" -eq 0 ]; then
  if [ -f "$cache_file" ]; then
    mt="$(stat -c %Y "$cache_file" 2> /dev/null || stat -f %m "$cache_file" 2> /dev/null || echo 0)"
    now="$(date +%s)"
    age=$((now - mt))
    if [ "$age" -lt "$cache_ttl" ]; then
      if command -v bat > /dev/null 2>&1; then
        head -n 30 "$cache_file" 2> /dev/null | bat --style=plain --color=always --wrap=never --paging=never --language=Markdown 2> /dev/null || true
      else
        head -n 30 "$cache_file" 2> /dev/null || true
      fi
      exit 0
    fi
  fi
fi

active_key_file="${cache_dir}/active_key"
global_fetch_lock_dir="${cache_dir}/fetch_global.lock"
debounce_lock_dir="${cache_dir}/debounce.lock"
active_key="${kind}:${safe_repo}:${num}"

_render_pr() {
  gh pr view "$num" -R "$repo" \
    --json number,title,body,author,labels,createdAt,updatedAt,reviewDecision,state,mergeable,additions,deletions,headRefName,baseRefName,isDraft,comments,reviews \
    --jq '
      "# PR #\(.number): \(.title)" +
      (if .isDraft then " (DRAFT)" else "" end) + "\n\n" +
      "**State:** \(.state)  **Review:** \(.reviewDecision // "")  **Mergeable:** \(.mergeable // "")\n" +
      "**Branch:** \(.headRefName) → \(.baseRefName)\n" +
      "**Author:** \(.author.login)\n" +
      "**Created:** \(.createdAt)  **Updated:** \(.updatedAt)\n" +
      "**Changes:** +\(.additions) / -\(.deletions)\n" +
      (if (.labels | length) > 0 then "**Labels:** " + ([.labels[].name] | join(", ")) + "\n" else "" end) +
      "\n---\n\n" +
      (.body // "(no description)") + "\n" +
      (if ((.comments | length) + (.reviews | length)) > 0 then
        "\n---\n\n## Activity (\((.comments | length) + (.reviews | length)))\n\n" +
        ([
          (.reviews // [] | map(select(.body != "" and .body != null) |
            "**\(.author.login)** reviewed (\(.state // "COMMENTED")) — \(.submittedAt // "")\n\(.body)\n"
          )),
          (.comments // [] | map(
            "**\(.author.login)** commented — \(.createdAt)\n\(.body)\n"
          ))
        ] | add // [] | join("\n---\n\n"))
      else "" end)
    ' 2> /dev/null
}

_render_issue() {
  gh issue view "$num" -R "$repo" \
    --json number,title,body,author,labels,createdAt,updatedAt,state,assignees,comments \
    --jq '
      "# Issue #\(.number): \(.title)\n\n" +
      "**State:** \(.state)\n" +
      "**Author:** \(.author.login)\n" +
      "**Created:** \(.createdAt)  **Updated:** \(.updatedAt)\n" +
      (if (.assignees | length) > 0 then "**Assignees:** " + ([.assignees[].login] | join(", ")) + "\n" else "" end) +
      (if (.labels | length) > 0 then "**Labels:** " + ([.labels[].name] | join(", ")) + "\n" else "" end) +
      "\n---\n\n" +
      (.body // "(no description)") + "\n" +
      (if (.comments | length) > 0 then
        "\n---\n\n## Comments (\(.comments | length))\n\n" +
        ([.comments[] |
          "**\(.author.login)** — \(.createdAt)\n\(.body)\n"
        ] | join("\n---\n\n"))
      else "" end)
    ' 2> /dev/null
}

_truncate_body() {
  if [ "$expand_mode" -eq 2 ]; then
    cat
    return
  fi
  python3 -c '
import sys, re

BODY_LIMIT = int(sys.argv[1])
COMMENT_LIMIT = 8
expand_mode = int(sys.argv[2])
SEP = "\n---\n"

text = sys.stdin.read()
parts = text.split(SEP)
if len(parts) < 2:
    print(text, end="")
    sys.exit()

def trunc(block, limit, hint):
    lines = block.strip("\n").split("\n")
    if len(lines) <= limit:
        return "\n".join(lines)
    omitted = len(lines) - limit
    return "\n".join(lines[:limit]) + f"\n\n> *… +{omitted} more lines — {hint}*\n"

header = parts[0]
body = parts[1]
activity_parts = parts[2:]

if expand_mode == 0:
    body = "\n" + trunc(body, BODY_LIMIT, "alt-e to expand body") + "\n"
else:
    body = "\n" + body.strip("\n") + "\n"

trunc_comments = expand_mode < 2
truncated_activity = []
for part in activity_parts:
    lines = part.split("\n", 2)
    if trunc_comments and len(lines) >= 3 and lines[0] == "" and re.match(r"\*\*\S+\*\*\s+(commented|reviewed)", lines[1]):
        meta = lines[0] + "\n" + lines[1]
        comment_body = lines[2]
        truncated_activity.append(meta + "\n" + trunc(comment_body, COMMENT_LIMIT, "alt-e to expand all"))
    else:
        truncated_activity.append(part)

print(header + SEP + body + SEP + SEP.join(truncated_activity), end="")
' "$BODY_MAX" "$expand_mode"
}

_colorize() {
  if command -v bat > /dev/null 2>&1; then
    bat --style=plain --color=always --wrap=never --paging=never --language=Markdown 2> /dev/null
  else
    cat
  fi
}

_atomic_write() {
  local dest="$1"
  local tmp
  tmp="$(mktemp "${dest}.XXXXXX")"
  cat > "$tmp"
  mv -f "$tmp" "$dest"
}

_render_with_timeout() {
  local seconds="$1"
  shift
  local tmp
  tmp="$(mktemp "${cache_file}.render.XXXXXX")"
  local start
  start="$(date +%s)"

  (
    "$@" > "$tmp" 2> /dev/null
  ) &
  local pid=$!

  while kill -0 "$pid" 2> /dev/null; do
    if [ $(( $(date +%s) - start )) -ge "$seconds" ]; then
      kill "$pid" 2> /dev/null || true
      sleep 0.1
      kill -9 "$pid" 2> /dev/null || true
      break
    fi
    sleep 0.1
  done

  wait "$pid" 2> /dev/null || true
  cat "$tmp" 2> /dev/null || true
  rm -f "$tmp" 2> /dev/null || true
}

_spawn_fetch() {
  # At most one debounce worker at a time; avoids accumulating sleepers while scrolling.
  if ! mkdir "$debounce_lock_dir" 2> /dev/null; then
    # bash 3.2 doesn't expose BASHPID reliably; use lock age to clear stale dirs.
    mt="$(stat -c %Y "$debounce_lock_dir" 2> /dev/null || stat -f %m "$debounce_lock_dir" 2> /dev/null || echo 0)"
    now="$(date +%s)"
    age=$((now - mt))
    if [ "$age" -gt 2 ]; then
      rm -rf "$debounce_lock_dir" 2> /dev/null || true
      mkdir "$debounce_lock_dir" 2> /dev/null || return 0
    else
      return 0
    fi
  fi

  # Debounce: only fetch if selection remains stable briefly.
  printf '%s\n' "$active_key" > "$active_key_file" 2> /dev/null || true

  (
    set +e
    sleep 0.25
    cur="$(cat "$active_key_file" 2> /dev/null || true)"
    if [ "$cur" != "$active_key" ]; then
      rm -rf "$debounce_lock_dir" 2> /dev/null || true
      exit 0
    fi

    # Global limiter: avoid accumulating many concurrent gh calls while scrolling.
    if ! mkdir "$global_fetch_lock_dir" 2> /dev/null; then
      mt="$(stat -c %Y "$global_fetch_lock_dir" 2> /dev/null || stat -f %m "$global_fetch_lock_dir" 2> /dev/null || echo 0)"
      now="$(date +%s)"
      age=$((now - mt))
      if [ "$age" -gt 30 ]; then
        rm -rf "$global_fetch_lock_dir" 2> /dev/null || true
        mkdir "$global_fetch_lock_dir" 2> /dev/null || exit 0
      else
        # The lock is fresh: wait briefly for the in-flight fetch to finish.
        i=0
        while [ "$i" -lt 15 ]; do
          sleep 0.1
          if mkdir "$global_fetch_lock_dir" 2> /dev/null; then
            break
          fi
          i=$((i + 1))
        done
        if [ ! -d "$global_fetch_lock_dir" ]; then
          rm -rf "$debounce_lock_dir" 2> /dev/null || true
          exit 0
        fi
      fi
    fi

    # Per-item lock to avoid redundant fetches.
    if ! mkdir "$fetch_lock_dir" 2> /dev/null; then
      mt="$(stat -c %Y "$fetch_lock_dir" 2> /dev/null || stat -f %m "$fetch_lock_dir" 2> /dev/null || echo 0)"
      now="$(date +%s)"
      age=$((now - mt))
      if [ "$age" -gt 30 ]; then
        rm -rf "$fetch_lock_dir" 2> /dev/null || true
        mkdir "$fetch_lock_dir" 2> /dev/null || exit 0
      else
        rm -rf "$global_fetch_lock_dir" 2> /dev/null || true
        rm -rf "$debounce_lock_dir" 2> /dev/null || true
        exit 0
      fi
    fi

    local content=""
    case "$kind" in
      pr) content="$(_render_with_timeout 10 _render_pr)" ;;
      issue) content="$(_render_with_timeout 10 _render_issue)" ;;
    esac
    if [ -n "$content" ]; then
      printf '%s\n' "$content" | _atomic_write "$cache_file" 2> /dev/null || true
    fi
    rm -rf "$fetch_lock_dir" 2> /dev/null || true
    rm -rf "$global_fetch_lock_dir" 2> /dev/null || true
    rm -rf "$debounce_lock_dir" 2> /dev/null || true
  ) > /dev/null 2>&1 &
  disown 2> /dev/null || true
}

_show_cache() {
  if [ -f "$cache_file" ]; then
    mt="$(stat -c %Y "$cache_file" 2> /dev/null || stat -f %m "$cache_file" 2> /dev/null || echo 0)"
    now="$(date +%s)"
    age=$((now - mt))
    if [ "$age" -lt "$cache_ttl" ]; then
      _truncate_body < "$cache_file" | _colorize
      return 0
    fi
    _truncate_body < "$cache_file" | _colorize
    return 1
  fi
  return 2
}

rc=0
_show_cache || rc=$?

case $rc in
  0)
    exit 0
    ;;
  1)
    _spawn_fetch
    exit 0
    ;;
  *)
    # Cold miss: never block the UI; fetch in the background.
    printf '\033[2;38;5;244m  Loading… (reselect or alt-e to refresh)\033[0m\n'
    _spawn_fetch
    ;;
esac
