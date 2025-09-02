#!/usr/bin/env bash

set -eou pipefail

echo "------------------------------"
echo "brew install fish: applying..."
echo "------------------------------"
brew install fish
echo "-----------------------"
echo "brew install fish: done"
echo "-----------------------"

if ! grep -q "$(which fish)" /etc/shells; then
  echo "---------------------------------------"
  echo "setting fish as main shell: applying..."
  echo "---------------------------------------"
  which fish | sudo tee -a /etc/shells
  chsh -s "$(which fish)"
  echo "--------------------------------"
  echo "setting fish as main shell: done"
  echo "--------------------------------"
else
  echo "--------------------------"
  echo "fish is already main shell"
  echo "--------------------------"
fi

echo ""
