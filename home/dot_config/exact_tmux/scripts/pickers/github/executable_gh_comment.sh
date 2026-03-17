#!/usr/bin/env bash
# Comment actions for the GitHub picker.
# Handles new comments, quote-replies, and editing own comments.
#
# Usage: gh_comment.sh <action> <kind> <repo_nwo> <number>
#
# Actions:
#   new      Open $EDITOR to write a new comment, post on save
#   reply    Pick a comment via fzf, quote it, open $EDITOR, post
#   edit     Pick one of your own comments via fzf, edit in $EDITOR, update
set -euo pipefail

die() {
  printf 'gh_comment: %s\n' "$*" >&2
  exit 1
}

action="${1:-}"
kind="${2:-}"
repo_nwo="${3:-}"
number="${4:-}"

[ -n "$action" ] || die "missing action"
[ -n "$kind" ] || die "missing kind"
[ -n "$repo_nwo" ] || die "missing repo"
[ -n "$number" ] || die "missing number"

EDITOR="${EDITOR:-nvim}"

_strip_html_comments() {
  sed 's/<!--.*-->//g' | tr -d '[:space:]'
}

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux/gh_preview"
safe_repo="$(printf '%s' "$repo_nwo" | tr '/' '_')"
preview_cache="${cache_dir}/${kind}_${safe_repo}_${number}.md"

_invalidate_preview_cache() {
  rm -f "$preview_cache" 2> /dev/null || true
}

_post_comment() {
  local file="$1"
  [ -s "$file" ] || {
    echo "Empty file, skipping."
    return 1
  }

  case "$kind" in
    pr) gh pr comment "$number" -R "$repo_nwo" -F "$file" ;;
    issue) gh issue comment "$number" -R "$repo_nwo" -F "$file" ;;
    *) die "unknown kind: $kind" ;;
  esac
}

_pick_comment() {
  local filter="${1:-}"
  local current_user=""
  if [ "$filter" = "own" ]; then
    current_user="$(gh api user --jq .login 2> /dev/null)"
  fi

  local jq_filter
  if [ -n "$current_user" ]; then
    jq_filter="select(.user.login == \"${current_user}\") | "
  else
    jq_filter=""
  fi

  local lines
  lines="$(gh api "repos/${repo_nwo}/issues/${number}/comments" \
    --paginate \
    --jq ".[] | ${jq_filter}"'
      "\(.id)\t@\(.user.login)  \(.created_at[:10])  \(.body | split("\n") | first | .[:120])"
    ' 2> /dev/null)"

  [ -n "$lines" ] || {
    echo "No comments found." >&2
    return 1
  }

  local picked
  picked="$(printf '%s\n' "$lines" | fzf \
    --ansi \
    --height=100% \
    --reverse \
    --delimiter=$'\t' \
    --with-nth=2 \
    --prompt "  pick comment  " \
    --preview "gh api repos/${repo_nwo}/issues/comments/{1} --jq .body 2>/dev/null | bat --style=plain --color=always --language=Markdown 2>/dev/null || cat" \
    --preview-window 'right,55%,border-left,wrap' \
    --color "prompt:111,query:223,header:244,pointer:81" \
    --header "enter=select  esc=cancel" \
    || true)"

  [ -n "$picked" ] || return 1
  printf '%s' "$picked" | awk -F $'\t' '{print $1}'
}

case "$action" in
  new)
    tmpfile="$(mktemp /tmp/gh_comment_XXXXXX.md)"
    trap 'rm -f "$tmpfile"' EXIT

    printf '<!-- %s #%s (%s) — save+quit to post, empty to cancel -->\n\n' \
      "$kind" "$number" "$repo_nwo" > "$tmpfile"

    $EDITOR "$tmpfile"

    if [ -z "$(_strip_html_comments < "$tmpfile")" ]; then
      echo "Comment empty, cancelled."
      exit 0
    fi

    sed -i'' '/^<!--.*-->$/d' "$tmpfile"
    _post_comment "$tmpfile"
    _invalidate_preview_cache
    echo "Comment posted."
    ;;

  reply)
    comment_id="$(_pick_comment)" || exit 0

    comment_raw="$(gh api "repos/${repo_nwo}/issues/comments/${comment_id}" 2> /dev/null)"
    comment_author="$(printf '%s' "$comment_raw" | python3 -c 'import sys,json; print(json.load(sys.stdin)["user"]["login"])')"
    comment_body="$(printf '%s' "$comment_raw" | python3 -c 'import sys,json; print(json.load(sys.stdin)["body"])')"

    tmpfile="$(mktemp /tmp/gh_reply_XXXXXX.md)"
    trap 'rm -f "$tmpfile"' EXIT

    {
      printf '<!-- replying to @%s — save+quit to post, empty to cancel -->\n\n' "$comment_author"
      printf '%s\n' "$comment_body" | sed 's/^/> /'
      printf '\n\n'
    } > "$tmpfile"

    $EDITOR "$tmpfile"

    user_text="$(sed '/^<!--.*-->$/d; /^>/d' "$tmpfile" | tr -d '[:space:]')"
    if [ -z "$user_text" ]; then
      echo "Reply empty, cancelled."
      exit 0
    fi

    sed -i'' '/^<!--.*-->$/d' "$tmpfile"
    _post_comment "$tmpfile"
    _invalidate_preview_cache
    echo "Reply posted."
    ;;

  edit)
    comment_id="$(_pick_comment own)" || exit 0

    comment_body="$(gh api "repos/${repo_nwo}/issues/comments/${comment_id}" --jq '.body' 2> /dev/null)"

    tmpfile="$(mktemp /tmp/gh_edit_XXXXXX.md)"
    trap 'rm -f "$tmpfile"' EXIT

    printf '%s' "$comment_body" > "$tmpfile"

    $EDITOR "$tmpfile"

    if [ -z "$(tr -d '[:space:]' < "$tmpfile")" ]; then
      echo "Body empty, cancelled."
      exit 0
    fi

    new_body="$(< "$tmpfile")"
    if [ "$new_body" = "$comment_body" ]; then
      echo "No changes, skipping."
      exit 0
    fi

    python3 -c 'import sys,json; print(json.dumps({"body": sys.stdin.read()}))' < "$tmpfile" \
      | gh api -X PATCH "repos/${repo_nwo}/issues/comments/${comment_id}" \
        --input - --silent 2> /dev/null
    _invalidate_preview_cache
    echo "Comment updated."
    ;;

  *)
    die "unknown action: $action"
    ;;
esac
