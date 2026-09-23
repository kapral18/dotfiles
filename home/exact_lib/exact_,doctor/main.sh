#!/usr/bin/env bash
# Description: System-wide health check for the dotfiles ecosystem

set -euo pipefail

if [ "${1:-}" = "ai" ]; then
  shift
  exec python3 "$HOME/lib/,doctor/ai.py" report "$@"
fi

# ── ANSI helpers ─────────────────────────────────────────────────────────────

C_PASS=$'\033[38;5;42m'
C_WARN=$'\033[38;5;214m'
C_FAIL=$'\033[38;5;196m'
C_DIM=$'\033[38;5;244m'
C_HEAD=$'\033[1;38;5;81m'
C_R=$'\033[0m'

ICON_PASS="${C_PASS}✓${C_R}"
ICON_WARN="${C_WARN}⚠${C_R}"
ICON_FAIL="${C_FAIL}✗${C_R}"

quiet=0
verbose=0
total_pass=0
total_warn=0
total_fail=0

# ── CLI ──────────────────────────────────────────────────────────────────────

show_usage() {
  cat << 'EOF'
Usage: ,doctor [options]
       ,doctor ai [--json] [--live] [--quiet] [--verbose]

Comprehensive health check for the dotfiles ecosystem.

Options:
  -q, --quiet     Only show warnings and failures
  -v, --verbose   Show extra detail on each check
  -h, --help      Show this help message
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -q | --quiet) quiet=1 ;;
    -v | --verbose) verbose=1 ;;
    -h | --help)
      show_usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      show_usage
      exit 1
      ;;
  esac
  shift
done

# ── result helpers ───────────────────────────────────────────────────────────

pass() {
  total_pass=$((total_pass + 1))
  [ "$quiet" -eq 1 ] && return 0
  printf '  %s  %s\n' "$ICON_PASS" "$1"
}

warn() {
  total_warn=$((total_warn + 1))
  printf '  %s  %s' "$ICON_WARN" "$1"
  [ -n "${2:-}" ] && printf '  %s%s%s' "$C_DIM" "$2" "$C_R"
  printf '\n'
}

fail() {
  total_fail=$((total_fail + 1))
  printf '  %s  %s' "$ICON_FAIL" "$1"
  [ -n "${2:-}" ] && printf '  %s%s%s' "$C_DIM" "$2" "$C_R"
  printf '\n'
}

section() {
  [ "$quiet" -eq 1 ] && return 0
  printf '\n%s── %s%s\n' "$C_HEAD" "$1" "$C_R"
}

has_cmd() { command -v "$1" > /dev/null 2>&1; }

# ── checks ───────────────────────────────────────────────────────────────────

check_core() {
  section "Core"

  if has_cmd chezmoi; then
    pass "chezmoi installed"
    local diff_lines
    diff_lines="$(chezmoi diff --no-pager 2> /dev/null | wc -l | tr -d ' ')"
    if [ "$diff_lines" -gt 0 ]; then
      warn "chezmoi has pending changes" "chezmoi diff"
    else
      pass "chezmoi state clean"
    fi
  else
    fail "chezmoi not installed" "curl -sfL https://get.chezmoi.io | sh"
  fi

  if has_cmd brew; then
    pass "Homebrew installed"
    if [ "$verbose" -eq 1 ]; then
      local outdated
      outdated="$(brew outdated --quiet 2> /dev/null | wc -l | tr -d ' ')"
      if [ "$outdated" -gt 0 ]; then
        warn "$outdated Homebrew packages outdated" "brew upgrade"
      else
        pass "Homebrew packages up to date"
      fi
    fi
  else
    fail "Homebrew not installed" "/usr/bin/env bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  fi

  if has_cmd xcode-select && xcode-select -p > /dev/null 2>&1; then
    pass "Xcode CLI tools installed"
  else
    fail "Xcode CLI tools missing" "xcode-select --install"
  fi
}

check_shell() {
  section "Shell"

  if has_cmd fish; then
    pass "fish installed"
  else
    fail "fish not installed" "brew install fish"
  fi

  local login_shell
  login_shell="$(dscl . -read "$HOME" UserShell 2> /dev/null | awk '{print $2}' || true)"
  if [[ "$login_shell" == *fish* ]]; then
    pass "fish is default shell"
  else
    warn "default shell is ${login_shell:-unknown}, not fish" "chsh -s \$(which fish)"
  fi

  if has_cmd starship; then
    pass "starship prompt installed"
  else
    warn "starship not installed" "brew install starship"
  fi

  if has_cmd zoxide; then
    pass "zoxide installed"
  else
    warn "zoxide not installed" "brew install zoxide"
  fi
}

check_tmux() {
  section "tmux"

  if has_cmd tmux; then
    pass "tmux installed"
  else
    fail "tmux not installed" "brew install tmux"
    return
  fi

  local tpm_dir="$HOME/.config/tmux/plugins/tpm"
  if [ -d "$tpm_dir" ]; then
    pass "TPM installed"
  else
    fail "TPM not installed" "chezmoi apply --include=externals"
  fi

  if tmux info > /dev/null 2>&1; then
    pass "tmux server running"
    local sess_count
    sess_count="$(tmux list-sessions 2> /dev/null | wc -l | tr -d ' ')"
    pass "$sess_count active session(s)"
  else
    warn "tmux server not running"
  fi

  if has_cmd fzf; then
    pass "fzf installed (picker dependency)"
  else
    fail "fzf not installed (session picker broken)" "brew install fzf"
  fi

  if has_cmd fd; then
    pass "fd installed (picker dependency)"
  else
    warn "fd not installed (picker will be slow)" "brew install fd"
  fi
}

check_git() {
  section "Git"

  if has_cmd git; then
    pass "git installed"
  else
    fail "git not installed" "brew install git"
    return
  fi

  local git_name git_email
  git_name="$(git config --global user.name 2> /dev/null || true)"
  git_email="$(git config --global user.email 2> /dev/null || true)"
  if [ -n "$git_name" ] && [ -n "$git_email" ]; then
    pass "git identity configured ($git_name <$git_email>)"
  else
    fail "git identity not configured" "git config --global user.name / user.email"
  fi

  local sign_format
  sign_format="$(git config --global gpg.format 2> /dev/null || true)"
  if [ -n "$sign_format" ]; then
    pass "commit signing configured (format: $sign_format)"
  else
    warn "commit signing not configured"
  fi

  if has_cmd delta; then
    pass "delta pager installed"
  else
    warn "delta not installed" "brew install git-delta"
  fi

  if has_cmd gh; then
    pass "GitHub CLI installed"
    if gh auth status > /dev/null 2>&1; then
      pass "gh authenticated"
    else
      warn "gh not authenticated" "gh auth login"
    fi
  else
    fail "GitHub CLI not installed" "brew install gh"
  fi

  if has_cmd lazygit; then
    pass "lazygit installed"
  else
    warn "lazygit not installed" "brew install lazygit"
  fi
}

check_security() {
  section "Security & Secrets"

  if has_cmd pass; then
    pass "pass installed"
    local store_dir="${PASSWORD_STORE_DIR:-$HOME/.password-store}"
    if [ -d "$store_dir" ]; then
      pass "password store exists"
    else
      fail "password store missing" "pass init <gpg-id>"
    fi
  else
    warn "pass not installed" "brew install pass"
  fi

  if has_cmd gpg; then
    pass "gpg installed"
    local key_count
    key_count="$(gpg --list-secret-keys --keyid-format long 2> /dev/null | grep -c '^sec' || true)"
    if [ "$key_count" -gt 0 ]; then
      pass "$key_count GPG secret key(s) available"
    else
      warn "no GPG secret keys found"
    fi
  else
    warn "gpg not installed" "brew install gnupg"
  fi

  local ssh_agent_sock="${SSH_AUTH_SOCK:-}"
  if [ -n "$ssh_agent_sock" ]; then
    if [[ "$ssh_agent_sock" == *1Password* || "$ssh_agent_sock" == *1password* ]]; then
      pass "SSH agent: 1Password"
    else
      pass "SSH agent active ($ssh_agent_sock)"
    fi
  else
    warn "no SSH agent detected" "check 1Password SSH agent settings"
  fi

  if has_cmd op; then
    pass "1Password CLI installed"
  else
    warn "1Password CLI not installed" "brew install 1password-cli"
  fi
}

check_editors_ai() {
  section "Editors & AI Tools"

  local -a editor_checks=(
    "cursor:Cursor"
    "nvim:Neovim"
  )
  for entry in "${editor_checks[@]}"; do
    local cmd="${entry%%:*}"
    local label="${entry#*:}"
    if has_cmd "$cmd"; then
      pass "$label installed"
    else
      warn "$label not installed"
    fi
  done

  local -a ai_checks=(
    "claude:Claude Code"
    "codex:OpenAI Codex"
    "opencode:OpenCode"
    "agy:Antigravity CLI"
    "cursor-agent:Cursor Agent"
  )
  for entry in "${ai_checks[@]}"; do
    local cmd="${entry%%:*}"
    local label="${entry#*:}"
    if has_cmd "$cmd"; then
      pass "$label installed"
    else
      warn "$label not installed"
    fi
  done

  _doctor_pi_runtime
}

# The pi shim and pnpm-global-links must name the same pnpm store directory;
# a stale shim after a global upgrade breaks every pi-subagents background launch.
_doctor_pi_runtime() {
  local probe="$HOME/lib/,doctor/pi_runtime.py"
  [ -f "$probe" ] || return 0
  local report status detail hint
  report="$(python3 "$probe" 2> /dev/null || true)"
  [ -n "$report" ] || return 0
  IFS=$'\t' read -r status detail hint < <(
    printf '%s' "$report" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("status",""), d.get("detail",""), d.get("hint",""), sep="\t")' 2> /dev/null || true
  )
  case "$status" in
    pass) pass "Pi runtime: $detail" ;;
    warn) warn "Pi runtime: $detail" "$hint" ;;
    skip) [ "$verbose" -eq 1 ] && pass "Pi runtime (skipped — $detail)" ;;
  esac
  return 0
}

check_tools() {
  section "Key CLI Tools"

  local -a tool_checks=(
    "bat:bat"
    "rg:ripgrep"
    "jq:jq"
    "yq:yq"
    "htop:htop"
    "hyperfine:hyperfine"
    "watchexec:watchexec"
    ",parallel:parallel"
  )

  for entry in "${tool_checks[@]}"; do
    local cmd="${entry%%:*}"
    local label="${entry#*:}"
    if has_cmd "$cmd"; then
      pass "$label"
    else
      warn "$label not installed" "brew install $label"
    fi
  done
}

check_bin_wrappers() {
  section "~/bin Wrappers & Agent Runtime"

  # Forwarding wrappers in ~/bin that exec a brew-installed binary.
  # If the brew formula is gone, the wrapper breaks silently.
  local -a wrappers=(
    ",sem:sem-cli"
    ",parallel:parallel"
  )
  local entry name formula
  for entry in "${wrappers[@]}"; do
    name="${entry%%:*}"
    formula="${entry#*:}"
    if [ -x "$HOME/bin/$name" ]; then
      if brew --prefix "$formula" > /dev/null 2>&1; then
        pass "~/bin/$name wrapper resolves ($formula)"
      else
        fail "~/bin/$name wrapper broken: brew formula '$formula' missing" "brew install $formula"
      fi
    fi
  done

  # Cursor CLI bundles its own ripgrep; a missing binary makes agent file
  # search (Glob/Grep) fail with spawn ENOENT.
  if [ -d "$HOME/.local/share/cursor-agent/versions" ]; then
    local cursor_rg
    cursor_rg="$(ls -1 "$HOME"/.local/share/cursor-agent/versions/*/rg 2> /dev/null | tail -1 || true)"
    if [ -n "$cursor_rg" ] && [ -x "$cursor_rg" ]; then
      pass "cursor-cli bundled rg present"
    else
      warn "cursor-cli bundled rg missing (agent Glob/Grep may ENOENT)" "reinstall cursor-cli: curl https://cursor.com/install | bash"
    fi
  fi
}

check_worktrees() {
  section "Worktrees"

  if ! has_cmd git || ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    pass "not inside a git repo (skipping worktree checks)"
    return
  fi

  local stale_count=0
  local wt_path=""
  while IFS= read -r line; do
    case "$line" in
      worktree\ *)
        wt_path="${line#worktree }"
        if [ -n "$wt_path" ] && [ ! -e "$wt_path" ]; then
          stale_count=$((stale_count + 1))
        fi
        ;;
    esac
  done < <(git worktree list --porcelain 2> /dev/null || true)

  if [ "$stale_count" -gt 0 ]; then
    warn "$stale_count stale worktree(s)" ",w prune"
  else
    pass "no stale worktrees"
  fi
}

check_ai_configs() {
  section "AI Tool Configs"

  local -a config_checks=(
    "$HOME/.cursor/mcp.json:cursor:Cursor MCP"
    "$HOME/.claude/settings.json:claude:Claude Code settings"
    "$HOME/.claude.json:claude:Claude Code MCP"
    "$HOME/.gemini/config/hooks.json:agy:Antigravity hooks"
    "$HOME/.gemini/config/mcp_config.json:agy:Antigravity MCP"
    "$HOME/.config/opencode/opencode.jsonc:opencode:OpenCode config"
    "$HOME/.codex/config.toml:codex:Codex config"
    "$HOME/.pi/agent/settings.json:pi:Pi settings"
    "$HOME/.pi/agent/mcp.json:pi:Pi MCP"
    "$HOME/.pi/agent/models.json:pi:Pi models"
  )

  for entry in "${config_checks[@]}"; do
    local path="${entry%%:*}"
    local remainder="${entry#*:}"
    local command="${remainder%%:*}"
    local label="${remainder#*:}"
    if [ -f "$path" ]; then
      local size
      size="$(wc -c < "$path" | tr -d ' ')"
      if [ "$size" -gt 2 ]; then
        pass "$label"
        if [ "$verbose" -eq 1 ]; then
          local mtime_raw
          mtime_raw="$(stat -f %m "$path" 2> /dev/null || true)"
          case "$mtime_raw" in
            '' | *[!0-9]*) mtime_raw="$(stat -c %Y "$path" 2> /dev/null || true)" ;;
          esac
          case "$mtime_raw" in
            '' | *[!0-9]*) mtime_raw=0 ;;
          esac
          local age_days
          if age_days="$((($(date +%s) - mtime_raw) / 86400))"; then
            if [ "$age_days" -gt 30 ]; then
              warn "$label last modified ${age_days}d ago" "chezmoi apply"
            fi
          fi
        fi
      else
        warn "$label exists but appears empty" "chezmoi apply"
      fi
    else
      if has_cmd "$command" 2> /dev/null; then
        warn "$label missing" "chezmoi apply"
      else
        [ "$verbose" -eq 1 ] && pass "$label (skipped — tool not installed)"
      fi
    fi
  done

  if has_cmd chezmoi && [ "$verbose" -eq 1 ]; then
    local diff_lines
    diff_lines="$(chezmoi diff --no-pager 2> /dev/null | wc -l | tr -d ' ')"
    if [ "$diff_lines" -gt 0 ]; then
      warn "chezmoi has $diff_lines lines of pending changes" "chezmoi apply"
    fi
  fi
}

# Resolve the chezmoi source directory. Honors CHEZMOI_SOURCE_DIR (set by
# chezmoi when it runs scripts) so tests can point at fixtures.
_doctor_source_dir() {
  if [ -n "${CHEZMOI_SOURCE_DIR:-}" ]; then
    printf '%s' "$CHEZMOI_SOURCE_DIR"
  elif has_cmd chezmoi; then
    chezmoi source-path 2> /dev/null || true
  fi
  return 0
}

# Ledger evaluation cache: TSV rows "target<TAB>reasons<TAB>producer", one per
# artifact target plus one per json-declared baseline path (reasons "baseline").
# Built from a single `ai.py report --json` pass joined with the raw ledger.
# Empty when the ledger tooling is unavailable; callers then fall back to
# whole-file comparison.
_doctor_ledger_eval() {
  local ledger="$1" ai_py="$2"
  [ -f "$ai_py" ] || return 0
  local report_json
  report_json="$(python3 "$ai_py" report --json 2> /dev/null || true)"
  [ -n "$report_json" ] || return 0
  printf '%s' "$report_json" | python3 -c '
import json, sys
try:
    raw = json.load(open(sys.argv[1], encoding="utf-8"))
    report = json.loads(sys.stdin.read())
    rows = report["artifacts"]
except (ValueError, OSError, KeyError, TypeError, AttributeError):
    sys.exit(1)
producers = {}
baselines = {}
for entry in raw.get("artifacts", {}).values():
    target = str(entry.get("target", ""))
    producers[target] = str(entry.get("producer", ""))
    baseline = (entry.get("ownership") or {}).get("baseline_path")
    if baseline:
        baselines[str(baseline)] = producers[target]
seen = set()
for row in rows:
    target = row["trace"]["target"]
    seen.add(target)
    print("%s\t%s\t%s" % (target, ",".join(row["reasons"]), producers.get(target, "")))
for baseline, producer in sorted(baselines.items()):
    if baseline not in seen:
        print("%s\tbaseline\t%s" % (baseline, producer))
' "$ledger" 2> /dev/null || true
  return 0
}

# Print "reasons<TAB>producer" for a manifest target, or fail when the target
# has no ledger row.
_doctor_ledger_lookup() {
  local eval_cache="$1" target="$2"
  [ -n "$eval_cache" ] || return 1
  local row
  row="$(printf '%s\n' "$eval_cache" | grep -F -e "$target"$'\t' | head -n 1 || true)"
  [ -n "$row" ] || return 1
  printf '%s' "$row" | cut -f2,3
}

# Display form of a manifest target: ~/... under $HOME, absolute otherwise.
# Basenames alone are ambiguous (several settings.json rows exist).
_doctor_short_path() {
  case "${1:-}" in
    "$HOME"/*) printf '~/%s' "${1#$HOME/}" ;;
    *) printf '%s' "${1:-}" ;;
  esac
}

# Last two path components of a $HOME-relative path, used as a conservative
# "still referenced" signal for variable-constructed script targets.
_doctor_tail2() {
  local rel="$1"
  local base="${rel##*/}" parent="${rel%/*}"
  if [ "$parent" = "$rel" ]; then
    printf '%s' "$base"
  else
    printf '%s/%s' "${parent##*/}" "$base"
  fi
}

# Print the first source file referencing a manifest target (absolute form,
# $HOME-relative form, or parent/basename tail), or fail when unreferenced.
_doctor_first_reference() {
  local source_dir="$1" target="$2"
  [ -n "$source_dir" ] && [ -d "$source_dir" ] || return 1
  local rel="$target"
  case "$target" in
    "$HOME"/*) rel="${target#$HOME/}" ;;
  esac
  local tail
  tail="$(_doctor_tail2 "$rel")"
  grep -rlF -e "$target" -e "\$HOME/$rel" -e "$tail" --exclude-dir=.git "$source_dir" 2> /dev/null | head -n 1
}

# True when a manifest target is listed in .chezmoiremove (intentionally
# removed upstream, so absence is the expected state).
_doctor_removed_upstream() {
  local source_dir="$1" target="$2"
  [ -n "$source_dir" ] || return 1
  local remove_file="$source_dir/.chezmoiremove"
  [ -f "$remove_file" ] || return 1
  case "$target" in
    "$HOME"/*) ;;
    *) return 1 ;;
  esac
  grep -qFx -e "${target#$HOME/}" "$remove_file" 2> /dev/null
}

# Retire one manifest row via the manifest helper. Fails when the helper is
# unavailable; recording on the next apply re-adds any row still produced.
_doctor_forget_row() {
  local source_dir="$1" manifest="$2" target="$3"
  local helper="$source_dir/../scripts/managed_config_manifest.py"
  [ -f "$helper" ] || return 1
  python3 "$helper" forget "$manifest" "$target" 2> /dev/null
}

# Print the .chezmoiscripts source file for a ledger producer stem, or fail
# unless exactly one file matches.
_doctor_find_producer_script() {
  local source_dir="$1" producer="$2"
  [ -n "$source_dir" ] && [ -n "$producer" ] || return 1
  local scripts_dir="$source_dir/.chezmoiscripts"
  [ -d "$scripts_dir" ] || return 1
  local match="" count=0 candidate
  for candidate in "$scripts_dir"/*"$producer"*; do
    [ -e "$candidate" ] || continue
    count=$((count + 1))
    match="$candidate"
  done
  [ "$count" -eq 1 ] || return 1
  printf '%s' "$match"
}

# Print the entryState key ($HOME/.chezmoiscripts/<stem>) for a script source
# file, or fail. run_onchange re-runs are gated on entryState contentsSHA256,
# not on the scriptState run log: deleting a scriptState key does not force a
# re-run (verified live 2026-09-14).
_doctor_script_entry_key() {
  [ -n "${1:-}" ] || return 1
  local base="${1##*/}"
  base="${base%.tmpl}"
  case "$base" in
    run_once_* | run_onchange_*) ;;
    *) return 1 ;;
  esac
  base="${base#run_once_}"
  base="${base#run_onchange_}"
  case "$base" in
    before_* | after_*) ;;
    *) return 1 ;;
  esac
  base="${base#before_}"
  base="${base#after_}"
  [ -n "$base" ] || return 1
  printf '$HOME/.chezmoiscripts/%s' "$base"
}

# Print the command that forces a producer script to re-run on next apply:
# delete its entryState row (idempotent no-op when already absent), then
# apply. Prints nothing when the producer script is unknown — no hint beats
# a wrong one.
_doctor_rerun_hint() {
  local entry_key
  entry_key="$(_doctor_script_entry_key "${1:-}" || true)"
  [ -n "$entry_key" ] || return 0
  printf 'chezmoi state delete --bucket=entryState --key="%s" && chezmoi apply' "$entry_key"
}

# Resolve a referencing source file to its producer run_* script: directly
# when the reference already is one, else via the consuming script. Fail when
# the producer is ambiguous or unknown.
_doctor_script_for_reference() {
  local source_dir="$1" ref="$2"
  [ -n "$source_dir" ] && [ -d "$source_dir/.chezmoiscripts" ] || return 1
  local base="${ref##*/}"
  case "$ref" in
    "$source_dir/.chezmoiscripts/"*)
      case "$base" in
        run_*)
          printf '%s' "$ref"
          return 0
          ;;
      esac
      ;;
  esac
  local consumers count
  consumers="$(grep -rlF -e "$base" --exclude-dir=.git "$source_dir/.chezmoiscripts" 2> /dev/null || true)"
  [ -n "$consumers" ] || return 1
  count="$(printf '%s\n' "$consumers" | wc -l | tr -d ' ')"
  [ "$count" -eq 1 ] || return 1
  case "${consumers##*/}" in
    run_*) printf '%s' "$consumers" ;;
    *) return 1 ;;
  esac
}

# Print the entryState-based re-run command for a ledger producer stem.
_doctor_rerun_hint_for_producer() {
  local source_dir="$1" producer="$2"
  local script=""
  if [ -n "$source_dir" ] && [ -n "$producer" ]; then
    script="$(_doctor_find_producer_script "$source_dir" "$producer" || true)"
  fi
  _doctor_rerun_hint "$script"
}

check_config_drift() {
  section "Config Drift"

  local state_home="${XDG_STATE_HOME:-$HOME/.local/state}/chezmoi"
  local manifest="$state_home/managed_configs.tsv"
  if [ ! -f "$manifest" ]; then
    warn "no managed-configs manifest found" "chezmoi apply"
    return
  fi

  local ledger="${CHEZMOI_ARTIFACT_LEDGER:-$state_home/generated_artifacts.v1.json}"
  local source_dir eval_cache
  source_dir="$(_doctor_source_dir || true)"
  eval_cache="$(_doctor_ledger_eval "$ledger" "$HOME/lib/,doctor/ai.py" || true)"

  local drifted=0 checked=0 retired=0
  local name reasons producer ledger_hit lookup ref script actual_hash
  while IFS=$'\t' read -r target expected_hash _timestamp; do
    [ -z "$target" ] && continue
    [[ "$target" == \#* ]] && continue
    checked=$((checked + 1))

    name="$(_doctor_short_path "$target")"
    reasons="" producer="" ledger_hit=0
    if lookup="$(_doctor_ledger_lookup "$eval_cache" "$target" || true)" && [ -n "$lookup" ]; then
      IFS=$'\t' read -r reasons producer <<< "$lookup"
      ledger_hit=1
    fi

    if [ ! -f "$target" ]; then
      if [ "$ledger_hit" -eq 1 ]; then
        warn "$name missing (managed by ${producer:-unknown producer})" "$(_doctor_rerun_hint_for_producer "$source_dir" "$producer")"
        drifted=$((drifted + 1))
      elif _doctor_removed_upstream "$source_dir" "$target"; then
        if [ -n "$source_dir" ] && _doctor_forget_row "$source_dir" "$manifest" "$target"; then
          retired=$((retired + 1))
          [ "$verbose" -eq 1 ] && pass "$name retired (intentionally removed upstream)"
        else
          warn "$name missing (was managed)" "chezmoi apply"
          drifted=$((drifted + 1))
        fi
      elif ref="$(_doctor_first_reference "$source_dir" "$target" || true)" && [ -n "$ref" ]; then
        script="$(_doctor_script_for_reference "$source_dir" "$ref" || true)"
        warn "$name missing (was managed)" "$(_doctor_rerun_hint "$script")"
        drifted=$((drifted + 1))
      elif [ -n "$source_dir" ] && _doctor_forget_row "$source_dir" "$manifest" "$target"; then
        retired=$((retired + 1))
        [ "$verbose" -eq 1 ] && pass "$name retired (no producer in source)"
      else
        warn "$name missing (was managed)" "chezmoi apply"
        drifted=$((drifted + 1))
      fi
      continue
    fi

    actual_hash="$(shasum -a 256 "$target" | cut -d' ' -f1)"

    if [ "$ledger_hit" -eq 1 ] && [ "$reasons" != "baseline" ]; then
      case ",$reasons," in
        *,owned-drift,*)
          warn "$name changed outside chezmoi (managed keys differ from policy; re-run restores them)" "$(_doctor_rerun_hint_for_producer "$source_dir" "$producer")"
          drifted=$((drifted + 1))
          ;;
        *,target-invalid,*)
          warn "$name content unreadable (managed state cannot be verified; re-run restores it)" "$(_doctor_rerun_hint_for_producer "$source_dir" "$producer")"
          drifted=$((drifted + 1))
          ;;
        *)
          if [ "$actual_hash" != "$expected_hash" ]; then
            [ "$verbose" -eq 1 ] && pass "$name differs from last apply (managed keys intact)"
          else
            [ "$verbose" -eq 1 ] && pass "$name matches managed state"
          fi
          ;;
      esac
    elif [ "$actual_hash" != "$expected_hash" ]; then
      if [ "$ledger_hit" -eq 1 ]; then
        warn "$name has drifted from managed state" "$(_doctor_rerun_hint_for_producer "$source_dir" "$producer")"
      else
        ref="$(_doctor_first_reference "$source_dir" "$target" || true)"
        script=""
        if [ -n "$ref" ]; then
          script="$(_doctor_script_for_reference "$source_dir" "$ref" || true)"
        fi
        warn "$name has drifted from managed state" "$(_doctor_rerun_hint "$script")"
      fi
      drifted=$((drifted + 1))
    else
      [ "$verbose" -eq 1 ] && pass "$name matches managed state"
    fi
  done < "$manifest"

  if [ "$drifted" -eq 0 ] && [ "$checked" -gt 0 ]; then
    pass "$checked managed config(s) in sync"
  fi
  if [ "$retired" -gt 0 ]; then
    pass "$retired stale manifest row(s) retired"
  fi
}

# ── main ─────────────────────────────────────────────────────────────────────

if [ "$quiet" -eq 0 ]; then
  printf '%s,doctor%s — dotfiles ecosystem health check\n' "$C_HEAD" "$C_R"
fi

check_core
check_shell
check_tmux
check_git
check_security
check_editors_ai
check_tools
check_bin_wrappers
check_worktrees
check_ai_configs
check_config_drift

# ── summary ──────────────────────────────────────────────────────────────────

printf '\n%s── Summary%s\n' "$C_HEAD" "$C_R"
printf '  %s %s passed' "$ICON_PASS" "$total_pass"
if [ "$total_warn" -gt 0 ]; then
  printf '   %s %s warning(s)' "$ICON_WARN" "$total_warn"
fi
if [ "$total_fail" -gt 0 ]; then
  printf '   %s %s failure(s)' "$ICON_FAIL" "$total_fail"
fi
printf '\n'

if [ "$total_fail" -gt 0 ]; then
  exit 1
elif [ "$total_warn" -gt 0 ]; then
  exit 0
fi
exit 0
