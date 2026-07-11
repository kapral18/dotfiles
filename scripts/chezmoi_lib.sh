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
#   chezmoi_record_checksum – record a file's sha256 in the managed-configs manifest
#   chezmoi_forget_checksum – retire a literal path from the managed-configs manifest
#   chezmoi_record_artifact – record one ownership-aware generated AI artifact
#   chezmoi_forget_artifact – retire one generated AI artifact id

set -euo pipefail

_CHEZMOI_MANIFEST="${XDG_STATE_HOME:-$HOME/.local/state}/chezmoi/managed_configs.tsv"
_CHEZMOI_ARTIFACT_LEDGER="${CHEZMOI_ARTIFACT_LEDGER:-${XDG_STATE_HOME:-$HOME/.local/state}/chezmoi/generated_artifacts.v1.json}"
_CHEZMOI_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
_CHEZMOI_MANIFEST_HELPER="$_CHEZMOI_LIB_DIR/managed_config_manifest.py"
_CHEZMOI_ARTIFACT_HELPER="$_CHEZMOI_LIB_DIR/generated_artifact_ledger.py"

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

# ── Manifest recording ───────────────────────────────────────────────────────

# Record a target file's sha256 in the managed-configs manifest.
# Called automatically by the write helpers after a successful write.
#   chezmoi_record_checksum <target_path>
chezmoi_record_checksum() {
  local target="${1:-}"
  python3 "$_CHEZMOI_MANIFEST_HELPER" record "$_CHEZMOI_MANIFEST" "$target"
}

# Remove every checksum row whose first TSV field exactly matches a retired
# generated target. Missing manifests and absent rows are true no-ops.
#   chezmoi_forget_checksum <target_path>
chezmoi_forget_checksum() {
  local target="${1:-}"
  python3 "$_CHEZMOI_MANIFEST_HELPER" forget "$_CHEZMOI_MANIFEST" "$target"
}

# Record one generated AI artifact after its target write succeeds.
# Metadata is passed through to the stdlib Python implementation.
chezmoi_record_artifact() {
  python3 "$_CHEZMOI_ARTIFACT_HELPER" --ledger "$_CHEZMOI_ARTIFACT_LEDGER" record "$@"
}

# Retire one exact artifact id. Missing ledgers and absent ids are no-ops.
chezmoi_forget_artifact() {
  local artifact_id="${1:-}"
  python3 "$_CHEZMOI_ARTIFACT_HELPER" --ledger "$_CHEZMOI_ARTIFACT_LEDGER" forget --id "$artifact_id"
}

# ── Idempotent write helpers ─────────────────────────────────────────────────

# Write a string to a target file only if content differs.
#   chezmoi_write_if_changed <desired_content> <target_path> [mode]
# Creates parent directories. Returns 0 if written or already current.
chezmoi_write_if_changed() {
  local desired="$1" target="$2" mode="${3:-0644}"

  mkdir -p "$(dirname "$target")"

  if [ -f "$target" ] && [ "$(cat "$target")" = "$desired" ]; then
    chezmoi_record_checksum "$target"
    return 0
  fi

  printf '%s\n' "$desired" > "$target"
  chmod "$mode" "$target"
  chezmoi_record_checksum "$target"
}

# Copy a source file to target via install(1) only if content differs.
#   chezmoi_install_if_changed <src_path> <target_path> [mode]
# Creates parent directories. Returns 0 if copied or already current.
chezmoi_install_if_changed() {
  local src="$1" target="$2" mode="${3:-0644}"

  mkdir -p "$(dirname "$target")"

  if [ -f "$target" ] && cmp -s "$src" "$target"; then
    chezmoi_record_checksum "$target"
    return 0
  fi

  install -m "$mode" "$src" "$target"
  chezmoi_record_checksum "$target"
}

# ── Provider / pass helpers ──────────────────────────────────────────────────

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

# Fetch the Azure Foundry endpoint from pass.
# Ensures the URL ends with /openai/v1. Exits 1 on missing prerequisites.
#   chezmoi_get_azure_foundry_endpoint
# Prints the normalized URL to stdout.
chezmoi_get_azure_foundry_endpoint() {
  if ! command -v pass > /dev/null 2>&1; then
    echo "pass is required to resolve Azure Foundry endpoint" >&2
    return 1
  fi

  local base
  base="$(pass show azure/foundry/endpoint | tr -d '\n')"
  if [ -z "$base" ]; then
    echo "Missing pass entry: azure/foundry/endpoint" >&2
    return 1
  fi

  base="${base%/}"
  case "$base" in
    */openai/v1) ;;
    */openai) base="$base/v1" ;;
    *) base="$base/openai/v1" ;;
  esac

  printf '%s' "$base"
}
