#!/usr/bin/env bash
# Pre-warm preview cache for GitHub picker items.
# Reads the items TSV cache and fetches previews for entries without a fresh
# cache file.  Runs at most MAX_CONCURRENT fetches in parallel to stay within
# GitHub API rate limits.
#
# Usage: gh_preview_warm.sh <items_cache_tsv>
set -euo pipefail

items_file="${1:-}"
[ -f "$items_file" ] || exit 0

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux/gh_preview"
mkdir -p "$cache_dir" 2> /dev/null || true
cache_ttl=120
MAX_CONCURRENT=3

_render_pr() {
  local repo="$1" num="$2"
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
  local repo="$1" num="$2"
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

_fetch_one() {
  local kind="$1" repo="$2" num="$3"
  local safe_repo
  safe_repo="$(printf '%s' "$repo" | tr '/' '_')"
  local cache_file="${cache_dir}/${kind}_${safe_repo}_${num}.md"

  if [ -f "$cache_file" ]; then
    local mt now age
    mt="$(stat -c %Y "$cache_file" 2> /dev/null || stat -f %m "$cache_file" 2> /dev/null || echo 0)"
    now="$(date +%s)"
    age=$((now - mt))
    [ "$age" -lt "$cache_ttl" ] && return 0
  fi

  local content=""
  case "$kind" in
    pr) content="$(_render_pr "$repo" "$num")" ;;
    issue) content="$(_render_issue "$repo" "$num")" ;;
    *) return 0 ;;
  esac

  if [ -n "$content" ]; then
    local tmp
    tmp="$(mktemp "${cache_file}.XXXXXX")"
    printf '%s\n' "$content" > "$tmp"
    mv -f "$tmp" "$cache_file"
  fi
}

pids=""
running=0
while IFS=$'\t' read -r _ kind repo num _rest; do
  [ "$kind" = "header" ] && continue
  [ -z "$repo" ] || [ -z "$num" ] && continue

  _fetch_one "$kind" "$repo" "$num" &
  pids="$pids $!"
  running=$((running + 1))

  if [ "$running" -ge "$MAX_CONCURRENT" ]; then
    # bash 3.2 lacks wait -n; poll for any finished pid
    while true; do
      for p in $pids; do
        if ! kill -0 "$p" 2> /dev/null; then
          wait "$p" 2> /dev/null || true
          pids="$(printf '%s\n' $pids | grep -v "^${p}$" | tr '\n' ' ')"
          running=$((running - 1))
          break 2
        fi
      done
      sleep 0.1
    done
  fi
done < "$items_file"

wait
