#!/usr/bin/env bash

set -eou pipefail

echo "------------------------------"
echo "brew install fish: applying..."
echo "------------------------------"
brew install fish
echo "-----------------------"
echo "brew install fish: done"
echo "-----------------------"

fish_path="$(command -v fish)"
if ! grep -qxF "$fish_path" /etc/shells; then
  printf '%s\n' "$fish_path" | sudo tee -a /etc/shells > /dev/null
fi

if [ "$(dscl . -read "$HOME" UserShell 2> /dev/null | awk '{print $2}')" != "$fish_path" ]; then
  echo "---------------------------------------"
  echo "setting fish as main shell: applying..."
  echo "---------------------------------------"
  sudo chsh -s "$fish_path" "$USER"
  echo "--------------------------------"
  echo "setting fish as main shell: done"
  echo "--------------------------------"
else
  echo "--------------------------"
  echo "fish is already main shell"
  echo "--------------------------"
fi

echo ""
