#!/bin/bash
set -euo pipefail

[ "${CHEZMOI_COMMAND:-}" = init ] || exit 0

if [ "$(uname -s)" != Darwin ]; then
  echo "This bootstrap requires macOS." >&2
  exit 1
fi

onepassword_app_installed() {
  [ -d "/Applications/1Password.app" ] || [ -d "$HOME/Applications/1Password.app" ]
}

onepassword_ready() {
  if ! op signin < /dev/null > /dev/null; then
    echo "1Password CLI authentication failed. Check the settings above, then rerun the setup command." >&2
    return 1
  fi

  if ! SSH_AUTH_SOCK="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock" ssh-add -l > /dev/null; then
    echo "1Password SSH agent is unavailable or has no keys. Enable Use the SSH agent, unlock 1Password, and make your GitHub SSH key available before rerunning the setup command." >&2
    return 1
  fi
}

ensure_cask() {
  if brew list --cask --versions "$1" > /dev/null 2>&1; then
    brew reinstall --cask "$1"
  else
    brew install --cask "$1"
  fi
}

load_brew() {
  brew_bin="$(command -v brew || true)"
  if [ -z "$brew_bin" ]; then
    if [ "$(uname -m)" = arm64 ]; then
      brew_bin=/opt/homebrew/bin/brew
    else
      brew_bin=/usr/local/bin/brew
    fi
    if [ ! -x "$brew_bin" ]; then
      installer="$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      /bin/bash -c "$installer"
    fi
  fi

  brew_env="$("$brew_bin" shellenv)"
  eval "$brew_env"
}

prepare_1password() {
  if command -v brew > /dev/null 2>&1 && onepassword_app_installed && onepassword_ready 2> /dev/null; then
    return 0
  fi

  if ! command -v brew > /dev/null 2>&1 || ! onepassword_app_installed || ! command -v op > /dev/null 2>&1; then
    load_brew

    if onepassword_app_installed && onepassword_ready 2> /dev/null; then
      return 0
    fi

    if ! onepassword_app_installed; then
      ensure_cask 1password
    fi
    if ! command -v op > /dev/null 2>&1; then
      ensure_cask 1password-cli
    fi
  fi
  open -a '1Password'

  cat << 'MSG'
Sign in to 1Password, then enable:
  Settings > Developer > Integrate with 1Password CLI
  Settings > Developer > Use the SSH agent
Unlock 1Password and make sure your GitHub SSH key is available to the agent.
Press Enter when ready. macOS and 1Password may ask for approval during setup.
MSG
  read -r _ || {
    echo "1Password setup needs a terminal; rerun init interactively." >&2
    exit 1
  }

  onepassword_ready
}

repo_argument_given() {
  local url="" line word words repo owner skip_value="" config="${CHEZMOI_WORKING_TREE:-}/.git/config"
  [ -f "$config" ] || return 1
  while read -r line; do
    case "$line" in "url = "*)
      url="${line#url = }"
      break
      ;;
    esac
  done < "$config"
  [ -n "$url" ] || return 1
  repo="$(printf '%s' "${url%.git}" | tr '[:upper:]' '[:lower:]')"
  repo="${repo#*github.com[:/]}"
  owner="${repo%%/*}"
  read -r -a words <<< "${CHEZMOI_ARGS:-}"
  for word in "${words[@]:1}"; do
    if [ -n "$skip_value" ]; then
      skip_value=""
      continue
    fi
    case "$word" in
      --age-recipient | --age-recipient-file | --branch | --cache | --config-format | --mode | --persistent-state | --promptBool | --promptChoice | --promptInt | --promptMultichoice | --promptString | \
        -c | --config | -C | --config-path | -d | --depth | -D | --destination | -i | --include | -o | --output | \
        -S | --source | -W | --working-tree | -x | --exclude)
        skip_value=1
        continue
        ;;
      -*) continue ;;
    esac
    word="$(printf '%s' "${word%/}" | tr '[:upper:]' '[:lower:]')"
    word="${word%.git}"
    word="${word#*github.com[:/]}"
    if [ "$word" = "$repo" ] || { [ -n "$owner" ] && [ "$word" = "$owner" ]; }; then
      return 0
    fi
  done
  return 1
}

refresh_source() {
  repo_argument_given || return 0

  local tree="$CHEZMOI_WORKING_TREE" branch
  command -v brew > /dev/null 2>&1 || load_brew
  if [ -n "$(git -C "$tree" status --porcelain)" ]; then
    echo "$tree has local changes. Commit, stash or remove them, then rerun the setup command." >&2
    exit 1
  fi

  if ! branch="$(git -C "$tree" symbolic-ref --short -q HEAD)"; then
    echo "$tree is not on a branch. Check out its main branch, then rerun the setup command." >&2
    exit 1
  fi
  git -C "$tree" fetch --quiet origin "$branch"
  if git -C "$tree" merge-base --is-ancestor FETCH_HEAD HEAD; then
    return 0
  fi
  if ! git -C "$tree" merge --ff-only --quiet FETCH_HEAD; then
    echo "$tree has commits that are not on GitHub. Push or remove them, then rerun the setup command." >&2
    exit 1
  fi
  echo "Updated $tree to the latest version. Rerun the setup command." >&2
  exit 1
}

prepare_github() {
  if ! command -v gh > /dev/null 2>&1; then
    command -v brew > /dev/null 2>&1 || load_brew
    command -v gh > /dev/null 2>&1 || brew install gh
  fi

  if ! gh auth status --hostname github.com > /dev/null 2>&1; then
    gh auth login --hostname github.com --git-protocol ssh --skip-ssh-key --web
  fi

  if ! ssh-keygen -F github.com > /dev/null 2>&1; then
    mkdir -p -m 700 "$HOME/.ssh"
    gh api meta --jq '.ssh_keys[] | "github.com " + .' >> "$HOME/.ssh/known_hosts"
  fi
}

/bin/bash "${BASH_SOURCE[0]%/*}/.require-terminal-permissions.sh"
refresh_source
prepare_1password
prepare_github
