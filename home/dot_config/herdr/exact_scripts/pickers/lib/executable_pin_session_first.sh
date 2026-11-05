#!/usr/bin/env bash
set -euo pipefail

kind="${1:-}" # "pr" or "issue"
repo="${2:-}" # best-effort, may be empty
num="${3:-}"

if [ -z "$kind" ] || [ -z "$num" ]; then
  cat
  exit 0
fi

match="$(mktemp -t sess_pin_match.XXXXXX)"
rest="$(mktemp -t sess_pin_rest.XXXXXX)"
cleanup() { rm -f "$match" "$rest" 2> /dev/null || true; }
trap cleanup EXIT

if [ -n "$repo" ]; then
  awk -F $'\t' -v k="$kind" -v r="$repo" -v n="$num" -v mf="$match" -v rf="$rest" '
    function trim_trailing_slash(value) {
      sub(/\/+$/, "", value)
      return value
    }
    function segment_url(segment, kind, number,    url) {
      if (kind == "pr") {
        if (segment !~ ("^pr=" number ":")) {
          return ""
        }
        url = segment
        sub("^pr=" number ":[^:]*:[^:]*:[^:]*:", "", url)
        return trim_trailing_slash(url)
      }
      if (kind == "issue") {
        if (segment !~ ("^issue=" number ":")) {
          return ""
        }
        url = segment
        sub("^issue=" number ":[^:]*:", "", url)
        return trim_trailing_slash(url)
      }
      return ""
    }
    function has_exact_repo_match(meta, kind, repo, number,    expected_https, expected_http, path_suffix, count, i, segment, url, parts) {
      path_suffix = (kind == "pr" ? "/pull/" : "/issues/") number
      expected_https = trim_trailing_slash("https://github.com/" repo path_suffix)
      expected_http = trim_trailing_slash("http://github.com/" repo path_suffix)
      count = split(meta, parts, /\|/)
      for (i = 1; i <= count; i++) {
        segment = parts[i]
        url = segment_url(segment, kind, number)
        if (url == "") {
          continue
        }
        if (url == expected_https || url == expected_http) {
          return 1
        }
      }
      return 0
    }
    NF < 5 { print > rf; next }
    (($2 == "session" || $2 == "worktree") && has_exact_repo_match($4, k, r, n)) { print > mf; next }
    { print > rf }
  '
else
  segment_prefix="${kind}=${num}:"
  awk -F $'\t' -v segment_prefix="$segment_prefix" -v mf="$match" -v rf="$rest" '
    function has_segment_prefix(meta, prefix,    count, i, segment, parts) {
      count = split(meta, parts, /\|/)
      for (i = 1; i <= count; i++) {
        segment = parts[i]
        if (index(segment, prefix) == 1) {
          return 1
        }
      }
      return 0
    }
    NF < 5 { print > rf; next }
    # meta is field 4; pin session + worktree rows
    (($2 == "session" || $2 == "worktree") && has_segment_prefix($4, segment_prefix)) { print > mf; next }
    { print > rf }
  '
fi

cat "$match" "$rest"
