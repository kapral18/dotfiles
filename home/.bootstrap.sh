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
prepare_1password
prepare_github
