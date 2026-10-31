#!/usr/bin/env bash

set -euo pipefail

# adapted from https://github.com/dNitza/dotfiles/blob/d75164b637713b91ee4f1b3d33f27dfa1d7bf748/.chezmoiscripts/run_once_00_install-xcode-devtools.sh.tmpl
echo "-------------------------------------------"
echo "xcode command line tools setup: applying..."
echo "-------------------------------------------"

echo "===> Installing Xcode Command Line Tools"

if xcode-select -p > /dev/null 2>&1; then
  echo "Command Line Tools already installed"
else
  xcode-select --install || echo "xcode-select --install failed; install the Command Line Tools manually" >&2
  echo "Finish the Command Line Tools installer, then press enter."
  read -r _ || true
  xcode-select -p > /dev/null 2>&1 || {
    echo "Command Line Tools are still missing" >&2
    exit 1
  }
fi

# Only full Xcode has a license to accept; Command Line Tools alone do not.
developer_dir="$(xcode-select -p)"
[ -d "$developer_dir/../MacOS" ] || developer_dir=/Applications/Xcode.app/Contents/Developer
if [ -d "$developer_dir/../MacOS" ]; then
  echo "--------------------------------------"
  echo "xcodebuild license accept: applying..."
  echo "--------------------------------------"
  sudo DEVELOPER_DIR="$developer_dir" xcodebuild -license accept
  echo "-------------------------------"
  echo "xcodebuild license accept: done"
  echo "-------------------------------"
fi

echo ""
