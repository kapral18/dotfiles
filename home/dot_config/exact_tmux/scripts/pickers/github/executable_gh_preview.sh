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

_render_pr() {
  gh pr view "$num" -R "$repo" \
    --json number,title,body,author,labels,createdAt,updatedAt,reviewDecision,state,additions,deletions,headRefName,baseRefName,isDraft,comments,reviews \
    --jq '
      "# PR #\(.number): \(.title)" +
      (if .isDraft then " (DRAFT)" else "" end) + "\n\n" +
      "**State:** \(.state)  **Review:** \(.reviewDecision)\n" +
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

_fetch_and_cache() {
  local content
  case "$kind" in
    pr) content="$(_render_pr)" ;;
    issue) content="$(_render_issue)" ;;
    *) return 1 ;;
  esac
  if [ -n "$content" ]; then
    printf '%s\n' "$content" > "$cache_file"
    printf '%s\n' "$content" | _truncate_body | _colorize
    return 0
  fi
  return 1
}

rc=0
_show_cache || rc=$?

case $rc in
  0)
    exit 0
    ;;
  1)
    (_fetch_and_cache > /dev/null 2>&1) &
    disown 2> /dev/null || true
    exit 0
    ;;
  *)
    _fetch_and_cache || printf 'Failed to fetch %s #%s from %s\n' "$kind" "$num" "$repo"
    ;;
esac
