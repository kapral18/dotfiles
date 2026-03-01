#!/usr/bin/env bash

_comma_w_issue_normalize_number() {
  local input="$1"
  local issue_number=""

  if [[ "$input" =~ ^#[0-9]+$ ]]; then
    issue_number="${input#\#}"
  elif [[ "$input" =~ ^[0-9]+$ ]]; then
    issue_number="$input"
  elif [[ "$input" =~ /issues/([0-9]+) ]]; then
    issue_number="${BASH_REMATCH[1]}"
  else
    return 1
  fi

  printf '%s\n' "$issue_number"
}

_comma_w_issue_slugify_kebab() {
  local s="$1"
  s="$(printf '%s' "$s" | tr '[:upper:]' '[:lower:]')"
  s="$(printf '%s' "$s" | tr ' _/' '---')"
  s="$(printf '%s' "$s" | tr -cd 'a-z0-9-\n')"
  s="$(printf '%s' "$s" | sed -E 's/-+/-/g; s/^-+//; s/-+$//')"
  printf '%s\n' "$s"
}

_comma_w_issue_infer_type() {
  local title="$1"
  title="$(printf '%s' "$title" | tr '[:upper:]' '[:lower:]')"

  case "$title" in
  fix* | bugfix* | hotfix*) echo "fix" ;;
  feat* | feature*) echo "feat" ;;
  docs* | doc*) echo "docs" ;;
  refactor*) echo "refactor" ;;
  test* | tests*) echo "test" ;;
  ci*) echo "ci" ;;
  build*) echo "build" ;;
  perf*) echo "perf" ;;
  style*) echo "style" ;;
  revert*) echo "revert" ;;
  *) echo "chore" ;;
  esac
}

_comma_w_issue_extract_scope() {
  local title="$1"
  local scope_raw=""
  if [[ "$title" =~ ^\\[([^\\]]+)\\][[:space:]]*(.*)$ ]]; then
    scope_raw="${BASH_REMATCH[1]}"
  fi

  local scope
  scope="$(_comma_w_issue_slugify_kebab "$scope_raw")"
  if [ -z "$scope" ]; then
    scope="misc"
  fi
  printf '%s\n' "$scope"
}

_comma_w_issue_strip_scope() {
  local title="$1"
  if [[ "$title" =~ ^\\[[^\\]]+\\][[:space:]]*(.*)$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi
  printf '%s\n' "$title"
}

_comma_w_issue_words_to_kebab() {
  local text="$1"
  local tokens
  tokens="$(
    printf '%s' "$text" |
      tr '[:upper:]' '[:lower:]' |
      sed -E 's/[^a-z0-9]+/ /g' |
      awk '
        BEGIN {
          split("a an the and or but if then else when while to from into onto in on at by for of with without over under between within per as is are was were be been being this that these those it its our your you we i me my mine their they them he she his her", stop, " ");
          for (i in stop) stopw[stop[i]] = 1;
        }
        {
          for (i=1; i<=NF; i++) {
            w=$i;
            if (length(w) < 2) continue;
            if (stopw[w] == 1) continue;
            print w;
          }
        }
      '
  )"

  if [ -z "${tokens//[[:space:]]/}" ]; then
    printf '%s\n' ""
    return 0
  fi

  local slug
  slug="$(
    printf '%s\n' "$tokens" |
      awk 'NR<=8 {print}' |
      paste -sd'-' -
  )"

  local count
  count="$(printf '%s' "$slug" | awk -F'-' '{print NF}')"
  while [ "$count" -lt 5 ]; do
    slug="${slug}-update"
    count=$((count + 1))
  done

  printf '%s\n' "$slug"
}

_comma_w_issue_validate_slug() {
  local slug="$1"
  [ -n "$slug" ] || return 1
  if ! printf '%s\n' "$slug" | grep -Eq '^[a-z0-9]+(-[a-z0-9]+){4,7}$'; then
    return 1
  fi
  return 0
}

_comma_w_issue_generate_slug_ollama() {
  local scope="$1"
  local title="$2"
  local body="$3"

  if ! command -v ollama >/dev/null 2>&1; then
    return 1
  fi

  local prompt
  prompt="$(
    cat <<EOF
You are generating a git branch slug.

Constraints:
- Output ONLY the slug, with no surrounding text.
- Use 5 to 8 words.
- Words MUST be lowercase alphanumeric.
- Separate words with single hyphens.
- No punctuation, no quotes, no explanations.

Context:
- scope: ${scope}
- title: ${title}
- description: ${body}
EOF
  )"

  local out
  out="$(ollama run gemma3 2>/dev/null <<<"$prompt" || true)"
  out="$(printf '%s' "$out" | tr -d '\r' | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' | head -n 1)"
  out="$(_comma_w_issue_slugify_kebab "$out")"

  if _comma_w_issue_validate_slug "$out"; then
    printf '%s\n' "$out"
    return 0
  fi

  return 1
}

_comma_w_issue_get_repo_name() {
  gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || true
}

_comma_w_issue_find_by_metadata() {
  local repo_name="$1"
  local issue_number="$2"
  local line key value worktree_path=""

  while IFS= read -r line; do
    key="${line%% *}"
    value="${line#* }"
    case "$key" in
    worktree)
      worktree_path="$value"
      if [ -z "$worktree_path" ] || [ ! -e "$worktree_path/.git" ]; then
        continue
      fi

      local wt_repo wt_num
      wt_repo="$(git -C "$worktree_path" config --worktree --get comma.w.issue.repo 2>/dev/null || true)"
      wt_num="$(git -C "$worktree_path" config --worktree --get comma.w.issue.number 2>/dev/null || true)"
      if [ "$wt_repo" = "$repo_name" ] && [ "$wt_num" = "$issue_number" ]; then
        printf '%s\n' "$worktree_path"
        return 0
      fi
      ;;
    esac
  done < <(git worktree list --porcelain 2>/dev/null)

  return 1
}

_comma_w_issue_find_by_heuristics() {
  local issue_number="$1"
  local -a candidates=()
  local candidates_seen=" "
  local line key value worktree_path="" branch_ref=""

  _maybe_add_candidate() {
    local p="$1"
    local br_ref="$2"
    [ -n "$p" ] || return 0

    local branch=""
    if [[ "$br_ref" == refs/heads/* ]]; then
      branch="${br_ref#refs/heads/}"
    fi

    local matched=0
    if [ -n "$branch" ] && printf '%s' "$branch" | grep -Eq "(^|[^0-9])${issue_number}([^0-9]|$)"; then
      matched=1
    elif printf '%s' "$p" | grep -Eq "(^|[^0-9])${issue_number}([^0-9]|$)"; then
      matched=1
    fi

    if [ "$matched" -eq 1 ]; then
      case "$candidates_seen" in
      *" ${p} "*) return 0 ;;
      esac
      candidates+=("$p")
      candidates_seen+="${p} "
    fi
  }

  while IFS= read -r line; do
    key="${line%% *}"
    value="${line#* }"
    case "$key" in
    worktree)
      _maybe_add_candidate "$worktree_path" "$branch_ref"
      worktree_path="$value"
      branch_ref=""
      ;;
    branch)
      branch_ref="$value"
      ;;
    esac
  done < <(git worktree list --porcelain 2>/dev/null)

  _maybe_add_candidate "$worktree_path" "$branch_ref"

  if [ "${#candidates[@]}" -eq 1 ]; then
    printf '%s\n' "${candidates[0]}"
    return 0
  fi

  if [ "${#candidates[@]}" -gt 1 ]; then
    echo ",w issue: multiple existing worktrees match heuristics for issue #${issue_number}:" >&2
    printf '%s\n' "${candidates[@]}" >&2
    return 2
  fi

  return 1
}

_comma_w_issue_store_metadata() {
  local worktree_path="$1"
  local repo_name="$2"
  local issue_number="$3"

  git config extensions.worktreeConfig true
  git -C "$worktree_path" config --worktree comma.w.issue.repo "$repo_name"
  git -C "$worktree_path" config --worktree comma.w.issue.number "$issue_number"
}
