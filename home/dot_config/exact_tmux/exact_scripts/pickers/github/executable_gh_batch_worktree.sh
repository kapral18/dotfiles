#!/usr/bin/env bash
# Batch worktree creation for the GitHub picker.
# Accepts one or more TSV lines (from fzf selection file).
# PRs: creates worktrees automatically (branch comes from the PR).
# Issues: opens $EDITOR with a naming buffer, then creates worktrees.
#
# Usage: gh_batch_worktree.sh <selection_file> [--background]
#
# The selection file contains one TSV line per selected item.
# Each line has fields: display\tkind\trepo_nwo\tnumber\turl\t...
set -euo pipefail

PATH="$HOME/bin:$PATH"
EDITOR="${EDITOR:-nvim}"

die() {
  printf 'gh_batch_worktree: %s\n' "$*" >&2
  exit 1
}

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2> /dev/null || true

row_loader_lib="$HOME/.config/tmux/scripts/pickers/github/lib/gh_row_loader.sh"
if [ -f "$row_loader_lib" ]; then
  # shellcheck source=/dev/null
  . "$row_loader_lib"
fi

selection_file=""
background=0
branches_file=""
dispatch_mode="${GH_PICKER_DISPATCH_MODE:-}"
dispatch_scope="${GH_PICKER_DISPATCH_SCOPE:-}"
dispatch_port="${GH_PICKER_DISPATCH_PORT:-}"
dispatch_cache_file="${GH_PICKER_DISPATCH_CACHE_FILE:-}"
dispatch_outer_tmux_socket="${OUTER_TMUX_SOCKET:-}"
if [ -z "$dispatch_outer_tmux_socket" ] && [ -n "${TMUX:-}" ]; then
  dispatch_outer_tmux_socket="${TMUX%%,*}"
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --background)
      background=1
      shift
      ;;
    --branches-file)
      [ $# -ge 2 ] || die "missing value for --branches-file"
      branches_file="$2"
      shift 2
      ;;
    --dispatch-mode)
      [ $# -ge 2 ] || die "missing value for --dispatch-mode"
      dispatch_mode="$2"
      shift 2
      ;;
    --dispatch-scope)
      [ $# -ge 2 ] || die "missing value for --dispatch-scope"
      dispatch_scope="$2"
      shift 2
      ;;
    --dispatch-port)
      [ $# -ge 2 ] || die "missing value for --dispatch-port"
      dispatch_port="$2"
      shift 2
      ;;
    --dispatch-cache-file)
      [ $# -ge 2 ] || die "missing value for --dispatch-cache-file"
      dispatch_cache_file="$2"
      shift 2
      ;;
    -*)
      die "unknown flag: $1"
      ;;
    *)
      if [ -z "$selection_file" ]; then
        selection_file="$1"
      fi
      shift
      ;;
  esac
done

[ -n "$selection_file" ] && [ -f "$selection_file" ] || die "missing or invalid selection file"

if [ -z "$dispatch_mode" ]; then
  dispatch_mode="$(cat "${cache_dir}/gh_picker_mode" 2> /dev/null || echo work)"
fi
if [ -z "$dispatch_scope" ]; then
  dispatch_scope="$(cat "${cache_dir}/gh_picker_scope" 2> /dev/null || echo all)"
fi
if [ -z "$dispatch_port" ]; then
  dispatch_port="${FZF_PORT:-}"
fi
if [ -z "$dispatch_port" ]; then
  dispatch_port="$(cat "${cache_dir}/gh_picker_port" 2> /dev/null || true)"
fi
if [ -z "$dispatch_cache_file" ]; then
  dispatch_cache_file="${cache_dir}/gh_picker_${dispatch_mode}.tsv"
fi

# Background mode is the last consumer of `$selection_file` (a per-binding
# snapshot minted by gh_picker_ctrl_t.sh / gh_picker_enter.sh). Foreground
# mode hands the snapshot off via a detached nohup job, so only the background
# pass should unlink it on exit. The branches buffer is foreground-owned and
# unlinked with its own trap below.
if [ "$background" -eq 1 ]; then
  trap 'rm -f "$selection_file" "${branches_file:-}" 2>/dev/null || true' EXIT
fi

# Detach background work from the dashboard popup/pane lifetime. Probed on
# tmux 3.7b: `tmux run-shell -b` started from a pane that then exits is
# cancelled; `nohup` (with TMUX unset) survives for as long as the server host
# process tree stays up.
_dispatch_background() {
  local cmd="$1"
  nohup env -u TMUX -u TMUX_PANE OUTER_TMUX_SOCKET="$dispatch_outer_tmux_socket" bash -c "$cmd" < /dev/null > /dev/null 2>&1 &
  disown 2> /dev/null || true
}

prs=()
pr_repos=()
issues=()
issue_repos=()
issue_titles=()

while IFS=$'\t' read -r _display kind repo num _rest; do
  [ -n "$kind" ] && [ -n "$repo" ] && [ -n "$num" ] || continue
  [ "$kind" = "header" ] && continue
  case "$kind" in
    pr)
      prs+=("$num")
      pr_repos+=("$repo")
      ;;
    issue)
      issues+=("$num")
      issue_repos+=("$repo")
      if [ "$background" -eq 0 ]; then
        title="$(gh issue view "$num" -R "$repo" --json title --jq .title 2> /dev/null || echo "")"
      else
        title=""
      fi
      issue_titles+=("$title")
      ;;
  esac
done < "$selection_file"

issue_branches=()

if [ "$background" -eq 0 ]; then
  # Foreground: collect issue branch names (if any), then dispatch everything to background.
  if [ ${#issues[@]} -gt 0 ]; then
    tmpfile="$(mktemp /tmp/gh_batch_worktree_XXXXXX.conf)"
    trap 'rm -f "$tmpfile"' EXIT

    {
      printf '# Branch names for issue worktrees\n'
      printf '# Format: <repo>#<number>|<branch-name>  (empty branch = skip)\n'
      printf '# Branch will be created as: <branch-name>-<number>\n'
      printf '# Tip: do NOT include tmux/session prefixes like work/kibana|...; just use the branch name (e.g. chore/foo)\n'
      printf '#\n'
      for i in "${!issues[@]}"; do
        printf '# %s\n' "${issue_titles[$i]}"
        printf '%s#%s|\n' "${issue_repos[$i]}" "${issues[$i]}"
      done
    } > "$tmpfile"

    # Open the scratch buffer, and when the editor is nvim, add a vertical-split
    # terminal sidecar running the interactive agent with the fixed branch-naming
    # prompt (not the bare scratch path). The terminal auto-closes when the agent
    # exits (run_in_split close_on_exit). Non-nvim editors keep the plain open.
    prompt_template="$(cd "$(dirname "$0")" && pwd)/gh_batch_branch_prompt.txt"
    prompt_inst=""
    agent_launcher=""
    if command -v nvim > /dev/null 2>&1 && [[ "$EDITOR" == *nvim* ]] && [ -f "$prompt_template" ]; then
      prompt_inst="$(mktemp /tmp/gh_batch_branch_prompt_XXXXXX.txt)"
      agent_launcher="$(mktemp /tmp/gh_batch_branch_agent_XXXXXX.sh)"
      # Substitute the concrete scratch path into the durable prompt template, then
      # launch via a tiny wrapper so the multiline prompt never has to be embedded
      # inside nvim `-c` / Lua string quoting.
      sed "s|__SCRATCH__|${tmpfile}|g" "$prompt_template" > "$prompt_inst"
      {
        printf '#!/usr/bin/env bash\n'
        printf 'set -euo pipefail\n'
        printf 'exec ,cursor-openrouter --model deepseek/deepseek-v4-flash-0731 --effort max -- "$(cat "$1")"\n'
      } > "$agent_launcher"
      chmod +x "$agent_launcher"
      agent_cmd="$(printf '%q %q' "$agent_launcher" "$prompt_inst")"
      agent_cmd_lua="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$agent_cmd")"
      trap 'rm -f "$tmpfile" "$prompt_inst" "$agent_launcher" 2>/dev/null || true' EXIT
      $EDITOR "$tmpfile" \
        -c "lua require('util.terminal').run_in_split(${agent_cmd_lua}, { close_on_exit = true, focus_original = true })"
    else
      $EDITOR "$tmpfile"
    fi

    branches_file="$(mktemp "${cache_dir}/gh_batch_worktree_branches_XXXXXX.conf")"
    # If we crash between `mktemp` and the background dispatch, we'd leak the
    # branches file. The trap is replaced once the background process owns it
    # (the dispatch line below).
    trap 'rm -f "$tmpfile" "$branches_file" "$prompt_inst" "$agent_launcher" 2>/dev/null || true' EXIT
    cp "$tmpfile" "$branches_file" 2> /dev/null || die "failed to persist branches file"

    _dispatch_background "$(printf %q "$0") $(printf %q "$selection_file") --background --branches-file $(printf %q "$branches_file") --dispatch-mode $(printf %q "$dispatch_mode") --dispatch-scope $(printf %q "$dispatch_scope") --dispatch-port $(printf %q "$dispatch_port") --dispatch-cache-file $(printf %q "$dispatch_cache_file")"
    # Background mode owns `$branches_file` and `$selection_file` from here.
    trap 'rm -f "$tmpfile" "$prompt_inst" "$agent_launcher" 2>/dev/null || true' EXIT
  else
    _dispatch_background "$(printf %q "$0") $(printf %q "$selection_file") --background --dispatch-mode $(printf %q "$dispatch_mode") --dispatch-scope $(printf %q "$dispatch_scope") --dispatch-port $(printf %q "$dispatch_port") --dispatch-cache-file $(printf %q "$dispatch_cache_file")"
  fi
  exit 0
fi

if [ ${#issues[@]} -gt 0 ] && [ -n "$branches_file" ] && [ -f "$branches_file" ]; then
  while IFS='|' read -r issue_ref branch; do
    [ -n "$issue_ref" ] || continue
    [[ "$issue_ref" =~ ^# ]] && continue
    issue_ref="$(printf '%s' "$issue_ref" | tr -d '[:space:]')"
    issue_repo="${issue_ref%#*}"
    num="${issue_ref##*#}"
    [ -n "$issue_repo" ] || continue
    [ -n "$num" ] || continue
    branch="$(printf '%s' "$branch" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    issue_branches+=("${issue_repo}#${num}:${branch}")
  done < "$branches_file"
fi

# Per-item outcome counters. They drive nothing user-visible on their own: all
# feedback is delivered through the dashboard markers (animated amber spinner,
# cyan ◆ done, cleared on skip/fail). The batch run prints nothing to its pane.
created=0
skipped=0
failed=0

# Detached nohup survival must still be bounded: a hung `,gh-worktree` (network,
# lock, prompt) would otherwise leave a rogue process + amber spinner forever.
# Overrides: GH_BATCH_ITEM_TIMEOUT_SECS (default 600), GH_BATCH_TOTAL_TIMEOUT_SECS (1800).
ITEM_TIMEOUT_SECS="${GH_BATCH_ITEM_TIMEOUT_SECS:-600}"
TOTAL_TIMEOUT_SECS="${GH_BATCH_TOTAL_TIMEOUT_SECS:-1800}"
batch_deadline=$((SECONDS + TOTAL_TIMEOUT_SECS))
job_ledger_dir="${cache_dir}/gh_batch_worktree_jobs"
job_ledger="${job_ledger_dir}/$$.tsv"
batch_create_lock="${job_ledger_dir}/create.lock"
mkdir -p "$job_ledger_dir" 2> /dev/null || true

_TIMEOUT_BIN=""
if command -v timeout > /dev/null 2>&1; then
  _TIMEOUT_BIN=timeout
elif command -v gtimeout > /dev/null 2>&1; then
  _TIMEOUT_BIN=gtimeout
fi

# Detached nohup job: keep stdout/stderr silent so the only feedback is the
# in-dashboard markers (and so closing the popup cannot reclaim a tty).
exec > /dev/null 2>&1

_notify_fzf_reload() {
  local mode scope port items_cmd cache_load_cmd
  mode="$dispatch_mode"
  scope="$dispatch_scope"
  port="$dispatch_port"
  [ -n "$port" ] || return 0
  items_cmd="$HOME/.config/tmux/scripts/pickers/github/gh_items.sh"
  cache_load_cmd="GH_PICKER_MODE=$(printf %q "$mode") GH_PICKER_SCOPE=$(printf %q "$scope") $(printf %q "$items_cmd") --cache-only 2>/dev/null"
  # Use IPv4 explicitly; on macOS `localhost` may resolve to ::1 while fzf binds 127.0.0.1.
  # Fire-and-forget: backgrounded so the per-item progress feedback never adds
  # latency to the batch loop (curl roundtrip + 1s timeout for stale ports
  # would otherwise serialize against `,w prs/issue` work). Reloads are
  # idempotent re-reads of the cache file, so out-of-order arrival is safe.
  # The subshell breaks the parent-child relationship so the script can exit
  # without `wait`-ing on stragglers.
  (curl -s --max-time 1 -XPOST "http://127.0.0.1:${port}" -d "reload($cache_load_cmd)+track" 9>&- > /dev/null 2>&1 &) 2> /dev/null
}

_patch_cache_entry() {
  local kind="$1" repo="$2" num="$3" state="${4:-done}"
  local cache_file script_dir patcher
  cache_file="$dispatch_cache_file"
  script_dir="$HOME/.config/tmux/scripts/pickers/github"
  patcher="${script_dir}/lib/gh_patch_picker_cache.py"
  if [ -f "$patcher" ] && [ -f "$cache_file" ]; then
    python3 -u "$patcher" --cache-file "$cache_file" --kind "$kind" --repo "$repo" --num "$num" --state "$state" 2> /dev/null || true
  fi
}

_start_loading() {
  # Sets loading_pid. Must be called directly, not via $(...): the command
  # substitution subshell would orphan the spinner, escaping the create's
  # process tree and the finalize tree-kill.
  local kind="$1" repo="$2" num="$3"
  loading_pid=""
  if declare -F gh_row_loader_start_item > /dev/null 2>&1; then
    # Spinner frames must render the dispatch packet's cache, not whatever the
    # shared global mode/scope files point at now.
    gh_row_loader_start_item "$kind" "$repo" "$num" "$dispatch_mode" "$dispatch_scope" 9>&- > /dev/null 2>&1 || true
    loading_pid="${gh_row_loader_last_pid:-}"
    return
  fi
  _patch_cache_entry "$kind" "$repo" "$num" loading
  _notify_fzf_reload
}

_stop_loading() {
  local pid="${1:-}"
  if declare -F gh_row_loader_stop_spinner > /dev/null 2>&1; then
    gh_row_loader_stop_spinner "$pid" "$dispatch_mode" "$dispatch_scope" 9>&- 2> /dev/null || true
  fi
}

_run_timed() {
  # Bound one `,gh-worktree` invocation so a single hung clone cannot pin the item.
  if [ -n "$_TIMEOUT_BIN" ]; then
    "$_TIMEOUT_BIN" --kill-after=10s "${ITEM_TIMEOUT_SECS}s" "$@"
  else
    "$@"
  fi
}

_kill_pid_tree() {
  local pid="$1" sig="${2:-TERM}" child
  [ -n "$pid" ] || return 0
  for child in $(pgrep -P "$pid" 2> /dev/null || true); do
    _kill_pid_tree "$child" "$sig"
  done
  kill "-${sig}" "$pid" 2> /dev/null || true
}

_pid_start_identity() {
  local pid="$1"
  ps -o lstart= -p "$pid" 2> /dev/null \
    | tr -s '[:space:]' ' ' \
    | sed 's/^ //;s/ $//' \
    || true
}

# Append, drop, and reap protect each ledger with the same mkdir lock. Create
# jobs retain the cross-batch fd until their row is durable, so a later lock
# holder cannot miss an orphan that is still publishing its identity.
_ledger_lock_acquire() {
  local ledger lock i=0
  ledger="${1:-$job_ledger}"
  lock="${ledger}.lockdir"
  while ! mkdir "$lock" 2> /dev/null; do
    i=$((i + 1))
    [ "$i" -gt 200 ] && return 1
    sleep 0.05
  done
  return 0
}

_ledger_lock_release() {
  local ledger="${1:-$job_ledger}"
  rmdir "${ledger}.lockdir" 2> /dev/null || true
}

_ledger_append() {
  local create_pid="$1" kind="$2" repo="$3" num="$4" spinner_pid="${5:-}"
  local create_start spinner_start=""
  create_start="$(_pid_start_identity "$create_pid")"
  if [ -n "$spinner_pid" ]; then
    spinner_start="$(_pid_start_identity "$spinner_pid")"
  fi
  _ledger_lock_acquire "$job_ledger" || return 1
  if ! printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$create_pid" "$kind" "$repo" "$num" "$create_start" "$spinner_pid" "$spinner_start" \
    >> "$job_ledger" 2> /dev/null; then
    _ledger_lock_release "$job_ledger"
    return 1
  fi
  _ledger_lock_release "$job_ledger"
}

_ledger_drop_pid() {
  local create_pid="$1" tmp
  [ -f "$job_ledger" ] || return 0
  _ledger_lock_acquire "$job_ledger" || return 0
  if [ ! -f "$job_ledger" ]; then
    _ledger_lock_release "$job_ledger"
    return 0
  fi
  tmp="$(mktemp "${job_ledger}.XXXXXX" 2> /dev/null || true)"
  if [ -n "$tmp" ]; then
    awk -F '\t' -v pid="$create_pid" '$1 != pid { print }' "$job_ledger" > "$tmp" 2> /dev/null || true
    mv -f "$tmp" "$job_ledger" 2> /dev/null || rm -f "$tmp" 2> /dev/null || true
  fi
  _ledger_lock_release "$job_ledger"
}

_kill_if_batch_process() {
  # Stale ledgers outlive their batch, so a recorded pid may have been recycled
  # by an unrelated process. Only signal pids whose command line is still a
  # detached gh_batch_worktree subshell (create jobs and their row spinners
  # share the script argv); anything else is left alone.
  local pid="$1" expected_start="$2" actual_start args
  [ -n "$pid" ] || return 0
  [ -n "$expected_start" ] || return 0
  kill -0 "$pid" 2> /dev/null || return 0
  actual_start="$(_pid_start_identity "$pid")"
  [ "$actual_start" = "$expected_start" ] || return 0
  args="$(ps -o args= -p "$pid" 2> /dev/null || true)"
  case "$args" in
    *gh_batch_worktree.sh*--background*)
      _kill_pid_tree "$pid" TERM
      sleep 0.2
      _kill_pid_tree "$pid" KILL
      ;;
  esac
}

_reap_ledger_file() {
  # Kill leftover create/spinner trees and clear their loading markers.
  # kill_mode: "own" (ledger of THIS batch — only pids that are still our live
  # children may be killed; a dead/recycled pid must never take an unrelated
  # process down), "stale" (dead batch — verify start identity + argv before
  # killing to avoid pid-reuse collateral).
  local ledger="$1" kill_mode="${2:-own}" create_pid kind repo num create_start spinner_pid spinner_start
  [ -f "$ledger" ] || return 0
  # Once the cross-batch lock moves to a later batch, no prior create can still
  # be publishing: it retained fd 9 until append + release. Any stale lockdir
  # therefore belongs to a process that died inside the ledger critical section.
  [ "$kill_mode" = "stale" ] && rmdir "${ledger}.lockdir" 2> /dev/null || true
  _ledger_lock_acquire "$ledger" || return 0
  while IFS=$'\t' read -r create_pid kind repo num create_start spinner_pid spinner_start; do
    [ -n "$create_pid" ] || continue
    case "$kill_mode" in
      own)
        if pgrep -P "$$" 2> /dev/null | grep -qx "$create_pid"; then
          # Spinner subshells are children of their create subshell, so the
          # tree kill reaps them; the create's EXIT trap also stops it.
          _kill_pid_tree "$create_pid" TERM
          sleep 0.2
          _kill_pid_tree "$create_pid" KILL
        fi
        ;;
      stale)
        _kill_if_batch_process "$create_pid" "$create_start"
        [ -n "$spinner_pid" ] && _kill_if_batch_process "$spinner_pid" "$spinner_start"
        ;;
    esac
    if [ -n "$kind" ] && [ -n "$repo" ] && [ -n "$num" ]; then
      _patch_cache_entry "$kind" "$repo" "$num" clear
    fi
  done < "$ledger"
  rm -f "$ledger" 2> /dev/null || true
  _ledger_lock_release "$ledger"
  _notify_fzf_reload
}

_reap_stale_batch_jobs() {
  # The global batch lock is held before this runs, so every existing ledger is
  # stale. Verify each recorded process start identity + argv before signalling;
  # ledger filenames and row pids may both have been reused. A ledger-less lock
  # directory can survive SIGKILL between ledger removal and lock release; drop
  # it before a reused batch pid creates that ledger again.
  local ledger lock
  [ -d "$job_ledger_dir" ] || return 0
  for lock in "$job_ledger_dir"/*.tsv.lockdir; do
    [ -d "$lock" ] || continue
    ledger="${lock%.lockdir}"
    [ -f "$ledger" ] || rmdir "$lock" 2> /dev/null || true
  done
  for ledger in "$job_ledger_dir"/*.tsv; do
    [ -f "$ledger" ] || continue
    _reap_ledger_file "$ledger" stale
  done
}

_finalize_batch_jobs() {
  # Bound the whole detached batch: any still-running create trees are killed and
  # their loading markers cleared so the dashboard cannot spin forever.
  _reap_ledger_file "$job_ledger" own
}

_create_pr_worktree() {
  local repo="$1" num="$2" loading_pid="" settled=0 ledger_published=0
  # shellcheck disable=SC2329
  _item_cleanup() {
    _stop_loading "$loading_pid"
    if [ "$settled" -eq 0 ]; then
      _patch_cache_entry "pr" "$repo" "$num" clear
      _notify_fzf_reload
    fi
    [ "$ledger_published" -eq 0 ] || _ledger_drop_pid "$BASHPID"
  }
  trap '_item_cleanup' EXIT
  _start_loading "pr" "$repo" "$num"
  # Background `func &` keeps $$ as the parent batch pid; BASHPID is this create job.
  _ledger_append "$BASHPID" "pr" "$repo" "$num" "$loading_pid" || return 1
  ledger_published=1
  if ! _run_timed ,gh-worktree pr "$repo" "$num" --print-root --no-bootstrap 9>&- > /dev/null 2>&1; then
    skipped=$((skipped + 1))
    return
  fi
  if _run_timed ,gh-worktree pr "$repo" "$num" --quiet --no-bootstrap 9>&- 2> /dev/null; then
    settled=1
    created=$((created + 1))
    _patch_cache_entry "pr" "$repo" "$num" "done"
    # Progressive feedback: re-render fzf so the ◆ marker for this item appears
    # immediately, instead of waiting for the whole batch to finish.
    _notify_fzf_reload
  else
    failed=$((failed + 1))
  fi
}

_create_issue_worktree() {
  local repo="$1" num="$2" branch="$3" loading_pid="" settled=0 ledger_published=0
  if [ -z "$branch" ]; then
    skipped=$((skipped + 1))
    return
  fi
  # shellcheck disable=SC2329
  _item_cleanup() {
    _stop_loading "$loading_pid"
    if [ "$settled" -eq 0 ]; then
      _patch_cache_entry "issue" "$repo" "$num" clear
      _notify_fzf_reload
    fi
    [ "$ledger_published" -eq 0 ] || _ledger_drop_pid "$BASHPID"
  }
  trap '_item_cleanup' EXIT
  _start_loading "issue" "$repo" "$num"
  _ledger_append "$BASHPID" "issue" "$repo" "$num" "$loading_pid" || return 1
  ledger_published=1
  if ! _run_timed ,gh-worktree issue "$repo" "$num" --print-root --no-bootstrap --branch "$branch" 9>&- > /dev/null 2>&1; then
    skipped=$((skipped + 1))
    return
  fi
  if _run_timed ,gh-worktree issue "$repo" "$num" --quiet --branch "$branch" --no-bootstrap 9>&- 2> /dev/null; then
    settled=1
    created=$((created + 1))
    _patch_cache_entry "issue" "$repo" "$num" "done"
    # Progressive feedback: re-render fzf so the ◆ marker for this item appears
    # immediately, instead of waiting for the whole batch to finish.
    _notify_fzf_reload
  else
    failed=$((failed + 1))
  fi
}

_wait_for_creates() {
  local remaining pid still
  if [ ${#pids[@]} -eq 0 ]; then
    if [ "$SECONDS" -ge "$batch_deadline" ]; then
      batch_timed_out=1
    fi
    return 0
  fi
  while [ ${#pids[@]} -gt 0 ]; do
    still=()
    for pid in "${pids[@]}"; do
      if kill -0 "$pid" 2> /dev/null; then
        still+=("$pid")
      else
        wait "$pid" 2> /dev/null || true
      fi
    done
    pids=("${still[@]+"${still[@]}"}")
    if [ ${#pids[@]} -eq 0 ]; then
      if [ "$SECONDS" -ge "$batch_deadline" ]; then
        batch_timed_out=1
      fi
      return 0
    fi
    remaining=$((batch_deadline - SECONDS))
    if [ "$remaining" -le 0 ]; then
      batch_timed_out=1
      for pid in "${pids[@]}"; do
        _kill_pid_tree "$pid" TERM
      done
      sleep 1
      for pid in "${pids[@]}"; do
        _kill_pid_tree "$pid" KILL
        wait "$pid" 2> /dev/null || true
      done
      return 0
    fi
    sleep 0.2
  done
}

_batch_can_launch() {
  if [ "$batch_timed_out" -ne 0 ] || [ "$SECONDS" -ge "$batch_deadline" ]; then
    batch_timed_out=1
    return 1
  fi
  return 0
}

# Reap leftovers from prior detached batches before starting new creates.
# BSD lockf holds this descriptor lock until the batch exits. Separate popup
# dispatches therefore cannot overlap full-repo checkouts or race marker state.
exec 9> "$batch_create_lock"
remaining=$((batch_deadline - SECONDS))
[ "$remaining" -gt 0 ] || exit 0
/usr/bin/lockf -s -t "$remaining" 9 || exit 0
_reap_stale_batch_jobs

# Create marked worktrees one at a time. A single Git checkout may already use
# every configured worker, so overlapping full-repo checkouts can starve tmux
# and make every item hit its timeout. Each item still runs in a child subshell
# so its cleanup trap and ledger row settle independently.
pids=()
batch_timed_out=0
: > "$job_ledger" 2> /dev/null || true
trap 'rm -f "$selection_file" "${branches_file:-}" 2>/dev/null || true; _finalize_batch_jobs' EXIT

for i in "${!prs[@]}"; do
  _batch_can_launch || break
  _create_pr_worktree "${pr_repos[$i]}" "${prs[$i]}" &
  pids+=("$!")
  _wait_for_creates
done

for entry in "${issue_branches[@]+"${issue_branches[@]}"}"; do
  _batch_can_launch || break
  issue_ref="${entry%%:*}"
  repo="${issue_ref%#*}"
  num="${issue_ref##*#}"
  branch="${entry#*:}"
  for i in "${!issues[@]}"; do
    if [ "${issues[$i]}" = "$num" ] && [ "${issue_repos[$i]}" = "$repo" ]; then
      _create_issue_worktree "$repo" "$num" "$branch" &
      pids+=("$!")
      _wait_for_creates
      break
    fi
  done
done

_wait_for_creates
# Successful completions already dropped themselves from the ledger; finalize
# only clears stragglers (and removes the ledger file).
_finalize_batch_jobs
trap 'rm -f "$selection_file" "${branches_file:-}" 2>/dev/null || true' EXIT
