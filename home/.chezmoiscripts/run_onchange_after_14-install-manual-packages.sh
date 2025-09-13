#!/usr/bin/env bash

set -euo pipefail

mkdir -p ~/.local/bin

# YtSurf
curl -o ~/.local/bin/ytsurf https://raw.githubusercontent.com/kapral18/ytsurf/reduce-deps/ytsurf.sh
chmod +x ~/.local/bin/ytsurf

# lazygit

# fzf

if ! command -v lazygit &>/dev/null; then
  git clone --branch fix-copy-status-support --single-branch --depth 1 https://github.com/kapral18/lazygit.git ~/.local/share/lazygit
  pushd ~/.local/share/lazygit
  make install
  popd
  asdf reshim golang
fi
