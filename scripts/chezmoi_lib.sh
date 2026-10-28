#!/usr/bin/env bash
# Shared library for chezmoi merge/apply scripts.
#
# Source this at the top of any run_onchange_after_07-merge-*.sh.tmpl:
#   source "$source_dir/../scripts/chezmoi_lib.sh"
#

set -euo pipefail

_CHEZMOI_MANIFEST="${XDG_STATE_HOME:-$HOME/.local/state}/chezmoi/managed_configs.tsv"
_CHEZMOI_ARTIFACT_LEDGER="${CHEZMOI_ARTIFACT_LEDGER:-${XDG_STATE_HOME:-$HOME/.local/state}/chezmoi/generated_artifacts.v1.json}"
_CHEZMOI_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
_CHEZMOI_MANIFEST_HELPER="$_CHEZMOI_LIB_DIR/managed_config_manifest.py"
_CHEZMOI_ARTIFACT_HELPER="$_CHEZMOI_LIB_DIR/generated_artifact_ledger.py"

# Record a target file's sha256 in the managed-configs manifest.
#   chezmoi_record_checksum <target_path>
chezmoi_record_checksum() {
  local target="${1:-}"
  python3 "$_CHEZMOI_MANIFEST_HELPER" record "$_CHEZMOI_MANIFEST" "$target"
}

# Record one generated AI artifact after its target write succeeds.
chezmoi_record_artifact() {
  python3 "$_CHEZMOI_ARTIFACT_HELPER" --ledger "$_CHEZMOI_ARTIFACT_LEDGER" record "$@"
}

# Write a string to a target file only if content differs.
#   chezmoi_write_if_changed <desired_content> <target_path> [mode]
# Creates parent directories and enforces mode even when content is current.
chezmoi_write_if_changed() {
  local desired="$1" target="$2" mode="${3:-0644}"

  mkdir -p "$(dirname "$target")"

  if [ -f "$target" ] && printf '%s\n' "$desired" | cmp -s - "$target"; then
    chmod "$mode" "$target"
    chezmoi_record_checksum "$target"
    return 0
  fi

  printf '%s\n' "$desired" > "$target"
  chmod "$mode" "$target"
  chezmoi_record_checksum "$target"
}

# Copy a source file to target via install(1) only if content differs.
#   chezmoi_install_if_changed <src_path> <target_path> [mode]
# Creates parent directories and enforces mode even when content is current.
chezmoi_install_if_changed() {
  local src="$1" target="$2" mode="${3:-0644}"

  mkdir -p "$(dirname "$target")"

  if [ -f "$target" ] && cmp -s "$src" "$target"; then
    chmod "$mode" "$target"
    chezmoi_record_checksum "$target"
    return 0
  fi

  install -m "$mode" "$src" "$target"
  chezmoi_record_checksum "$target"
}
