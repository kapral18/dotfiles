#!/usr/bin/env bash
# Create an issue or epic from the GitHub picker (global, non-cursor action).
#
# Usage: gh_create.sh <issue|epic> <default_repo> <mode_file> <scope_file> <items_cmd>
#
# Wired to alt-i (issue) and alt-E (epic). Resolves a target repo (defaulting to
# the cursor row's repo), composes title/body in $EDITOR, creates via
# gh_create.py, then offers to create a worktree + focus its tmux session.
#
# Worktree handoff: on "yes", writes the new issue's identity to
# `gh_picker_create_pin`; gh_picker.sh's transform sees the file, aborts the
# picker, and routes it through the existing checkout path
# (,gh-worktree issue ... --focus, interactive branch prompt). On "no", POSTs a
# dashboard refresh to the fzf listen socket so the new item appears and the
# picker stays open.
set -euo pipefail

die() {
  if [ -n "${TMUX:-}" ]; then
    tmux display-message "gh_create: $*" 2> /dev/null || true
  fi
  printf 'gh_create: %s\n' "$*" >&2
  exit 1
}

show_loader() {
  local message="$1"
  if [ -n "${TMUX:-}" ]; then
    tmux display-message "gh-create: Loading... ${message}" 2> /dev/null || true
  fi
  if [ -t 2 ]; then
    printf '\033[2;38;5;244m  Loading... %s\033[0m\n' "$message" >&2
  fi
}

kind="${1:-}"
default_repo="${2:-}"
mode_file="${3:-}"
scope_file="${4:-}"
items_cmd="${5:-}"

case "$kind" in
  issue | epic) ;;
  *) die "kind must be issue or epic (got: ${kind:-empty})" ;;
esac
[ -n "$items_cmd" ] || die "missing items command"

EDITOR="${EDITOR:-nvim}"
script_dir="$(cd "$(dirname "$0")" && pwd)"
create_py="$script_dir/lib/gh_create.py"
[ -f "$create_py" ] || die "missing helper: $create_py"

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2> /dev/null || true
create_pin_file="${cache_dir}/gh_picker_create_pin"

mode="$(cat "$mode_file" 2> /dev/null || echo work)"
scope="$(cat "$scope_file" 2> /dev/null || echo all)"
items_cache="${cache_dir}/gh_picker_${mode}.tsv"

repo_valid() {
  printf '%s' "$1" | grep -qE '^[^/[:space:]]+/[^/[:space:]]+$'
}

# --- resolve target repo (default = cursor row repo; fzf to confirm/override) ---
default_candidate=""
if repo_valid "$default_repo"; then
  default_candidate="$default_repo"
fi

candidates="$(python3 "$create_py" repo-candidates --cache-file "$items_cache" 2> /dev/null || true)"

repo="$(printf '%s' "$candidates" | fzf \
  --prompt "  target repo > " \
  --height=40% \
  --reverse \
  --print-query \
  --query "$default_candidate" \
  --header "enter=use repo  ·  type owner/repo to override  ·  esc=cancel" \
  --color "prompt:111,query:223,header:244,pointer:81" \
  || true)"
repo="$(printf '%s\n' "$repo" | tail -1 | tr -d '[:space:]')"

[ -n "$repo" ] || exit 0
repo_valid "$repo" || die "invalid repo (expected owner/repo): $repo"

# --- compose title/body in $EDITOR ---
tmpfile="$(mktemp "/tmp/gh_create_${kind}_XXXXXX.md")"
trap 'rm -f "$tmpfile"' EXIT

if [ "$kind" = "issue" ]; then
  {
    printf '<!-- New issue in %s — first non-empty line is the title, the rest is the body. -->\n' "$repo"
    printf '<!-- Save with content to create; save empty to cancel. -->\n\n'
  } > "$tmpfile"
else
  {
    printf '<!-- New epic in %s. -->\n' "$repo"
    printf '<!-- First section is the PARENT issue (first line = title, rest = body). -->\n'
    printf '<!-- Separate each child issue with a line containing only: --- -->\n'
    printf '<!-- The first line of each child section is its title. Save empty to cancel. -->\n\n'
  } > "$tmpfile"
fi

$EDITOR "$tmpfile"

# Cancel if nothing but instruction comments / whitespace remains.
remaining="$(sed 's/<!--.*-->//g' "$tmpfile" | tr -d '[:space:]')"
if [ -z "$remaining" ]; then
  echo "gh_create: empty, cancelled." >&2
  exit 0
fi

# --- create via the Python helper (stdout = "<num>\t<url>") ---
show_loader "creating ${kind} in ${repo}"
result="$(python3 "$create_py" create --repo "$repo" --kind "$kind" --file "$tmpfile")" \
  || die "failed to create $kind in $repo"

IFS=$'\t' read -r num url <<< "$result"
[ -n "$num" ] || die "no issue number returned"

if [ -n "${TMUX:-}" ]; then
  tmux display-message "gh_create: created ${repo}#${num}" 2> /dev/null || true
fi

# --- optional worktree + focus ---
printf '\n' > /dev/tty 2> /dev/null || true
printf 'Created %s#%s. Create worktree + focus session now? (y/N) ' "$repo" "$num" > /dev/tty 2> /dev/null || true
answer=""
IFS= read -r answer < /dev/tty 2> /dev/null || answer=""

case "$answer" in
  y | Y | yes | YES | Yes)
    # Hand off to gh_picker.sh's post-exit checkout (interactive branch prompt +
    # ,gh-worktree issue ... --focus). The binding's transform aborts the picker
    # once this file exists.
    printf 'issue\t%s\t%s\t%s\n' "$repo" "$num" "$url" > "$create_pin_file"
    ;;
  *)
    # Refresh the dashboard so the new issue/epic appears; picker stays open.
    if [ -n "${FZF_PORT:-}" ]; then
      reload_cmd="GH_PICKER_MODE=$(printf %q "$mode") GH_PICKER_SCOPE=$(printf %q "$scope") $(printf %q "$items_cmd") --refresh"
      curl -s --max-time 5 -XPOST "http://127.0.0.1:${FZF_PORT}" -d "reload(${reload_cmd})+track" > /dev/null 2>&1 || true
    fi
    ;;
esac

exit 0
