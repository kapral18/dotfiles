#!/usr/bin/env bash

set -ou pipefail #

# adapted from https://github.com/dNitza/dotfiles/blob/d75164b637713b91ee4f1b3d33f27dfa1d7bf748/.chezmoiscripts/run_once_00_install-xcode-devtools.sh.tmpl
echo "-------------------------------------------"
echo "xcode command line tools setup: applying..."
echo "-------------------------------------------"

echo "===> Installing Xcode Command Line Tools"

softwareupdate --install -a >/dev/null 2>&1
sudo xcode-select --install >/dev/null 2>&1

echo "--------------------------------------"
echo "xcodebuild license accept: applying..."
echo "--------------------------------------"

# Accept T&Cs
sudo xcodebuild -license accept
echo "-------------------------------"
echo "xcodebuild license accept: done"
echo "-------------------------------"

echo ""
