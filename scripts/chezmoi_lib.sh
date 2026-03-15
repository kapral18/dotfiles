#!/usr/bin/env bash
# Shared library for chezmoi merge/apply scripts.
#
# Source this at the top of any run_onchange_after_07-merge-*.sh.tmpl:
#   source "$source_dir/../scripts/chezmoi_lib.sh"
#
# Provides:
#   chezmoi_pick_src   – resolve work vs personal source file
#   chezmoi_write_if_changed – atomic string write, skip if unchanged
#   chezmoi_install_if_changed – file copy via install(1), skip if unchanged
#   chezmoi_get_litellm_api_base – fetch and normalize LiteLLM base URL from pass

set -euo pipefail

# ── Source selection ──────────────────────────────────────────────────────────

# Pick work or personal source path.
#   chezmoi_pick_src <is_work> <source_dir> <work_relpath> <personal_relpath>
# Prints the resolved absolute path to stdout.
chezmoi_pick_src() {
  local is_work="$1" source_dir="$2" work_rel="$3" personal_rel="$4"
  if [ "$is_work" = "true" ]; then
    printf '%s' "$source_dir/$work_rel"
  else
    printf '%s' "$source_dir/$personal_rel"
  fi
}

# ── Idempotent write helpers ─────────────────────────────────────────────────

# Write a string to a target file only if content differs.
#   chezmoi_write_if_changed <desired_content> <target_path> [mode]
# Creates parent directories. Returns 0 if written or already current.
chezmoi_write_if_changed() {
  local desired="$1" target="$2" mode="${3:-0644}"

  mkdir -p "$(dirname "$target")"

  if [ -f "$target" ] && [ "$(cat "$target")" = "$desired" ]; then
    return 0
  fi

  printf '%s\n' "$desired" > "$target"
  chmod "$mode" "$target"
}

# Copy a source file to target via install(1) only if content differs.
#   chezmoi_install_if_changed <src_path> <target_path> [mode]
# Creates parent directories. Returns 0 if copied or already current.
chezmoi_install_if_changed() {
  local src="$1" target="$2" mode="${3:-0644}"

  mkdir -p "$(dirname "$target")"

  if [ -f "$target" ] && cmp -s "$src" "$target"; then
    return 0
  fi

  install -m "$mode" "$src" "$target"
}

# ── LiteLLM / pass helpers ───────────────────────────────────────────────────

# Fetch and normalize the LiteLLM API base URL from pass.
# Ensures the URL ends with /v1. Exits 1 on missing prerequisites.
#   chezmoi_get_litellm_api_base
# Prints the normalized URL to stdout.
chezmoi_get_litellm_api_base() {
  if ! command -v pass > /dev/null 2>&1; then
    echo "pass is required to resolve LiteLLM API base" >&2
    return 1
  fi

  local base
  base="$(pass show litellm/api/base | tr -d '\n')"
  if [ -z "$base" ]; then
    echo "Missing pass entry: litellm/api/base" >&2
    return 1
  fi

  base="${base%/}"
  case "$base" in
    */v1) ;;
    *) base="$base/v1" ;;
  esac

  printf '%s' "$base"
}
