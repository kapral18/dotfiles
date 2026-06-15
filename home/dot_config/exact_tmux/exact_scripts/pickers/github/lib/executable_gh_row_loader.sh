#!/usr/bin/env bash
# Shared row-scoped loading markers for the GitHub picker.
set -euo pipefail

_gh_row_loader_cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
_gh_row_loader_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_gh_row_loader_picker_dir="$(cd "${_gh_row_loader_lib_dir}/.." && pwd)"
_gh_row_loader_patcher="${_gh_row_loader_lib_dir}/gh_patch_picker_cache.py"

gh_row_loader_mk_restore_file() {
  local prefix="${1:-row}"
  mkdir -p "$_gh_row_loader_cache_dir" 2> /dev/null || true
  mktemp "${_gh_row_loader_cache_dir}/gh_row_loader_${prefix}_XXXXXX.json"
}

gh_row_loader_mode_from_file() {
  local mode_file="${1:-}"
  if [ -n "$mode_file" ] && [ -f "$mode_file" ]; then
    cat "$mode_file" 2> /dev/null || echo work
  else
    cat "${_gh_row_loader_cache_dir}/gh_picker_mode" 2> /dev/null || echo work
  fi
}

gh_row_loader_scope_from_file() {
  local scope_file="${1:-}"
  if [ -n "$scope_file" ] && [ -f "$scope_file" ]; then
    cat "$scope_file" 2> /dev/null || echo all
  else
    cat "${_gh_row_loader_cache_dir}/gh_picker_scope" 2> /dev/null || echo all
  fi
}

gh_row_loader_notify() {
  local mode="$1" scope="$2" items_cmd="${3:-${_gh_row_loader_picker_dir}/gh_items.sh}"
  local port reload_cmd
  port="${FZF_PORT:-}"
  [ -n "$port" ] || port="$(cat "${_gh_row_loader_cache_dir}/gh_picker_port" 2> /dev/null || true)"
  [ -n "$port" ] || return 0
  reload_cmd="GH_PICKER_MODE=$(printf %q "$mode") GH_PICKER_SCOPE=$(printf %q "$scope") $(printf %q "$items_cmd") --cache-only 2>/dev/null"
  (curl -s --max-time 1 -XPOST "http://127.0.0.1:${port}" -d "reload(${reload_cmd})+track" > /dev/null 2>&1 &) 2> /dev/null
}

gh_row_loader_patch() {
  local kind="$1" repo="$2" num="$3" state="$4" restore_file="${5:-}"
  local mode="${6:-$(gh_row_loader_mode_from_file)}"
  local cache_file="${_gh_row_loader_cache_dir}/gh_picker_${mode}.tsv"
  [ -f "$_gh_row_loader_patcher" ] && [ -f "$cache_file" ] || return 0
  if [ -n "$restore_file" ]; then
    python3 -u "$_gh_row_loader_patcher" \
      --cache-file "$cache_file" --kind "$kind" --repo "$repo" --num "$num" \
      --state "$state" --save-file "$restore_file" --restore-loading-only 2> /dev/null || true
  else
    python3 -u "$_gh_row_loader_patcher" \
      --cache-file "$cache_file" --kind "$kind" --repo "$repo" --num "$num" \
      --state "$state" 2> /dev/null || true
  fi
}

gh_row_loader_mark() {
  local kind="$1" repo="$2" num="$3" restore_file="$4"
  local mode="${5:-$(gh_row_loader_mode_from_file)}" scope="${6:-$(gh_row_loader_scope_from_file)}"
  local items_cmd="${7:-${_gh_row_loader_picker_dir}/gh_items.sh}"
  gh_row_loader_patch "$kind" "$repo" "$num" loading "$restore_file" "$mode"
  gh_row_loader_notify "$mode" "$scope" "$items_cmd"
}

gh_row_loader_restore() {
  local kind="$1" repo="$2" num="$3" restore_file="$4"
  local mode="${5:-$(gh_row_loader_mode_from_file)}" scope="${6:-$(gh_row_loader_scope_from_file)}"
  local items_cmd="${7:-${_gh_row_loader_picker_dir}/gh_items.sh}"
  gh_row_loader_patch "$kind" "$repo" "$num" restore "$restore_file" "$mode"
  gh_row_loader_notify "$mode" "$scope" "$items_cmd"
}

gh_row_loader_patch_all() {
  local mode="$1" state="$2" restore_file="$3"
  local cache_file="${_gh_row_loader_cache_dir}/gh_picker_${mode}.tsv"
  [ -f "$_gh_row_loader_patcher" ] && [ -f "$cache_file" ] || return 0
  python3 -u "$_gh_row_loader_patcher" \
    --cache-file "$cache_file" --all --state "$state" \
    --save-file "$restore_file" --restore-loading-only 2> /dev/null || true
}

gh_row_loader_mark_all() {
  local mode="$1" scope="$2" items_cmd="$3" restore_file="$4"
  gh_row_loader_patch_all "$mode" loading "$restore_file"
  gh_row_loader_notify "$mode" "$scope" "$items_cmd"
}

gh_row_loader_restore_all() {
  local mode="$1" scope="$2" items_cmd="$3" restore_file="$4"
  gh_row_loader_patch_all "$mode" restore "$restore_file"
  gh_row_loader_notify "$mode" "$scope" "$items_cmd"
}

gh_row_loader_refresh_all() {
  local items_cmd="$1" mode="$2" scope="$3"
  local restore_file rc
  restore_file="$(gh_row_loader_mk_restore_file refresh 2> /dev/null || true)"
  if [ -n "$restore_file" ]; then
    gh_row_loader_mark_all "$mode" "$scope" "$items_cmd" "$restore_file"
  fi
  set +e
  GH_PICKER_MODE="$mode" GH_PICKER_SCOPE="$scope" "$items_cmd" --refresh > /dev/null 2>&1
  rc=$?
  set -e
  if [ -n "$restore_file" ]; then
    gh_row_loader_restore_all "$mode" "$scope" "$items_cmd" "$restore_file"
    rm -f "$restore_file" 2> /dev/null || true
  else
    gh_row_loader_notify "$mode" "$scope" "$items_cmd"
  fi
  return "$rc"
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    refresh-all)
      shift
      [ $# -ge 3 ] || exit 0
      gh_row_loader_refresh_all "$1" "$2" "$3"
      ;;
    *)
      exit 0
      ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
