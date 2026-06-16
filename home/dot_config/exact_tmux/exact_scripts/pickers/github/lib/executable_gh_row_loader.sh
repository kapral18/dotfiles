#!/usr/bin/env bash
# Shared row-scoped loading markers for the GitHub picker.
set -euo pipefail

_gh_row_loader_cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
_gh_row_loader_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_gh_row_loader_picker_dir="$(cd "${_gh_row_loader_lib_dir}/.." && pwd)"
_gh_row_loader_patcher="${_gh_row_loader_lib_dir}/gh_patch_picker_cache.py"
_gh_row_loader_frames=(loading-0 loading-1 loading-2 loading-3)
_gh_row_loader_interval="0.8"
_gh_row_loader_header_idle=" GitHub cockpit "
_gh_row_loader_header_loading=" GitHub cockpit | Loading... "

gh_row_loader_mk_restore_file() {
  local prefix="${1:-row}"
  mkdir -p "$_gh_row_loader_cache_dir" 2> /dev/null || true
  mktemp "${_gh_row_loader_cache_dir}/gh_row_loader_${prefix}_XXXXXX"
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
  local frame_file
  frame_file="$(gh_row_loader_prepare_cache_file "$mode" "$scope" "$items_cmd" 2> /dev/null || true)"
  [ -n "$frame_file" ] || return 0
  gh_row_loader_notify_file "$frame_file"
}

gh_row_loader_notify_file() {
  local frame_file="$1"
  local port reload_cmd cmd_file
  [ -s "$frame_file" ] || return 0
  port="${FZF_PORT:-}"
  [ -n "$port" ] || port="$(cat "${_gh_row_loader_cache_dir}/gh_picker_port" 2> /dev/null || true)"
  [ -n "$port" ] || return 0
  cmd_file="$(mktemp "${_gh_row_loader_cache_dir}/gh_row_loader_cmd_XXXXXX" 2> /dev/null || true)"
  [ -n "$cmd_file" ] || return 0
  {
    printf '#!/usr/bin/env bash\n'
    printf 'cat %q\n' "$frame_file"
    printf 'rm -f %q %q 2>/dev/null || true\n' "$frame_file" "$cmd_file"
  } > "$cmd_file"
  chmod +x "$cmd_file" 2> /dev/null || true
  reload_cmd="$(printf '%q' "$cmd_file")"
  (curl -s --max-time 1 -XPOST "http://127.0.0.1:${port}" -d "reload-sync(${reload_cmd})+track" > /dev/null 2>&1 &) 2> /dev/null
  (
    sleep 5
    rm -f "$frame_file" "$cmd_file" 2> /dev/null || true
  ) > /dev/null 2>&1 &
}

gh_row_loader_post_action() {
  local action="$1"
  local port
  port="${FZF_PORT:-}"
  [ -n "$port" ] || port="$(cat "${_gh_row_loader_cache_dir}/gh_picker_port" 2> /dev/null || true)"
  [ -n "$port" ] || return 0
  curl -s --max-time 1 -XPOST "http://127.0.0.1:${port}" -d "$action" > /dev/null 2>&1 || true
}

gh_row_loader_global_start() {
  gh_row_loader_post_action "change-header-label(${_gh_row_loader_header_loading})"
}

gh_row_loader_global_stop() {
  gh_row_loader_post_action "change-header-label(${_gh_row_loader_header_idle})"
}

gh_row_loader_frame_state() {
  local idx="${1:-0}"
  printf '%s' "${_gh_row_loader_frames[$((idx % ${#_gh_row_loader_frames[@]}))]}"
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

gh_row_loader_patch_file() {
  local cache_file="$1" targets_file="$2" state="$3"
  local kind repo num
  [ -f "$_gh_row_loader_patcher" ] && [ -f "$cache_file" ] && [ -f "$targets_file" ] || return 0
  while IFS=$'\t' read -r kind repo num; do
    [ -n "$kind" ] && [ -n "$repo" ] && [ -n "$num" ] || continue
    python3 -u "$_gh_row_loader_patcher" \
      --cache-file "$cache_file" --kind "$kind" --repo "$repo" --num "$num" \
      --state "$state" 2> /dev/null || true
  done < "$targets_file"
}

gh_row_loader_prepare_cache_file() {
  local mode="$1" scope="$2" items_cmd="$3"
  local tmp
  tmp="$(mktemp "${_gh_row_loader_cache_dir}/gh_row_loader_render_XXXXXX" 2> /dev/null || true)"
  [ -n "$tmp" ] || return 0
  GH_PICKER_MODE="$mode" GH_PICKER_SCOPE="$scope" "$items_cmd" --cache-only > "$tmp" 2> /dev/null || true
  if [ ! -s "$tmp" ]; then
    rm -f "$tmp" 2> /dev/null || true
    return 0
  fi
  printf '%s\n' "$tmp"
}

gh_row_loader_prepare_render_file() {
  local items_cmd="$1" mode="$2" scope="$3" target="$4" state="$5" a="${6:-}" b="${7:-}" c="${8:-}"
  local tmp
  tmp="$(gh_row_loader_prepare_cache_file "$mode" "$scope" "$items_cmd" 2> /dev/null || true)"
  [ -n "$tmp" ] || return 0
  case "$target" in
    all)
      python3 -u "$_gh_row_loader_patcher" --cache-file "$tmp" --all --state "$state" 2> /dev/null || true
      ;;
    item)
      python3 -u "$_gh_row_loader_patcher" --cache-file "$tmp" --kind "$a" --repo "$b" --num "$c" --state "$state" 2> /dev/null || true
      ;;
    file)
      gh_row_loader_patch_file "$tmp" "$a" "$state"
      ;;
  esac
  printf '%s\n' "$tmp"
}

gh_row_loader_render() {
  local frame_file
  frame_file="$(gh_row_loader_prepare_render_file "$@" 2> /dev/null || true)"
  [ -n "$frame_file" ] || return 0
  cat "$frame_file"
  rm -f "$frame_file" 2> /dev/null || true
}

gh_row_loader_notify_render_item() {
  local kind="$1" repo="$2" num="$3" state="$4"
  local mode="${5:-$(gh_row_loader_mode_from_file)}" scope="${6:-$(gh_row_loader_scope_from_file)}"
  local items_cmd="${7:-${_gh_row_loader_picker_dir}/gh_items.sh}"
  local frame_file
  frame_file="$(gh_row_loader_prepare_render_file "$items_cmd" "$mode" "$scope" item "$state" "$kind" "$repo" "$num" 2> /dev/null || true)"
  [ -n "$frame_file" ] || return 0
  gh_row_loader_notify_file "$frame_file"
}

gh_row_loader_notify_render_file() {
  local targets_file="$1" state="$2"
  local mode="${3:-$(gh_row_loader_mode_from_file)}" scope="${4:-$(gh_row_loader_scope_from_file)}"
  local items_cmd="${5:-${_gh_row_loader_picker_dir}/gh_items.sh}"
  local frame_file
  frame_file="$(gh_row_loader_prepare_render_file "$items_cmd" "$mode" "$scope" file "$state" "$targets_file" 2> /dev/null || true)"
  [ -n "$frame_file" ] || return 0
  gh_row_loader_notify_file "$frame_file"
}

gh_row_loader_notify_render_all() {
  local mode="$1" scope="$2" items_cmd="$3" state="$4"
  local frame_file
  frame_file="$(gh_row_loader_prepare_render_file "$items_cmd" "$mode" "$scope" all "$state" 2> /dev/null || true)"
  [ -n "$frame_file" ] || return 0
  gh_row_loader_notify_file "$frame_file"
}

gh_row_loader_start_item() {
  local kind="$1" repo="$2" num="$3"
  local mode="${4:-$(gh_row_loader_mode_from_file)}" scope="${5:-$(gh_row_loader_scope_from_file)}"
  local items_cmd="${6:-${_gh_row_loader_picker_dir}/gh_items.sh}"
  (
    local i=0 state
    while :; do
      state="$(gh_row_loader_frame_state "$i")"
      gh_row_loader_notify_render_item "$kind" "$repo" "$num" "$state" "$mode" "$scope" "$items_cmd"
      i=$((i + 1))
      sleep "$_gh_row_loader_interval"
    done
  ) > /dev/null 2>&1 &
  printf '%s\n' "$!"
}

gh_row_loader_start_file() {
  local targets_file="$1"
  local mode="${2:-$(gh_row_loader_mode_from_file)}" scope="${3:-$(gh_row_loader_scope_from_file)}"
  local items_cmd="${4:-${_gh_row_loader_picker_dir}/gh_items.sh}"
  (
    local i=0 state
    while :; do
      state="$(gh_row_loader_frame_state "$i")"
      gh_row_loader_notify_render_file "$targets_file" "$state" "$mode" "$scope" "$items_cmd"
      i=$((i + 1))
      sleep "$_gh_row_loader_interval"
    done
  ) > /dev/null 2>&1 &
  printf '%s\n' "$!"
}

gh_row_loader_start_all() {
  local mode="$1" scope="$2" items_cmd="$3"
  (
    local i=0 state
    while :; do
      state="$(gh_row_loader_frame_state "$i")"
      gh_row_loader_notify_render_all "$mode" "$scope" "$items_cmd" "$state"
      i=$((i + 1))
      sleep "$_gh_row_loader_interval"
    done
  ) > /dev/null 2>&1 &
  printf '%s\n' "$!"
}

gh_row_loader_stop_spinner() {
  local pid="${1:-}" mode="${2:-$(gh_row_loader_mode_from_file)}" scope="${3:-$(gh_row_loader_scope_from_file)}"
  local items_cmd="${4:-${_gh_row_loader_picker_dir}/gh_items.sh}"
  if [ -n "$pid" ]; then
    kill "$pid" 2> /dev/null || true
    wait "$pid" 2> /dev/null || true
  fi
  gh_row_loader_notify "$mode" "$scope" "$items_cmd"
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
  local spinner_pid rc
  gh_row_loader_global_start
  spinner_pid="$(gh_row_loader_start_all "$mode" "$scope" "$items_cmd" 2> /dev/null || true)"
  set +e
  GH_PICKER_MODE="$mode" GH_PICKER_SCOPE="$scope" "$items_cmd" --refresh > /dev/null 2>&1
  rc=$?
  set -e
  gh_row_loader_stop_spinner "$spinner_pid" "$mode" "$scope" "$items_cmd"
  gh_row_loader_global_stop
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
    global-start)
      gh_row_loader_global_start
      ;;
    global-stop)
      gh_row_loader_global_stop
      ;;
    render-all)
      shift
      [ $# -ge 4 ] || exit 0
      gh_row_loader_render "$1" "$2" "$3" all "$4"
      ;;
    render-item)
      shift
      [ $# -ge 7 ] || exit 0
      gh_row_loader_render "$1" "$2" "$3" item "$7" "$4" "$5" "$6"
      ;;
    render-file)
      shift
      [ $# -ge 5 ] || exit 0
      gh_row_loader_render "$1" "$2" "$3" file "$5" "$4"
      ;;
    *)
      exit 0
      ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
