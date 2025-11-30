#!/usr/bin/env bash

set -euo pipefail

mkdir -p ~/.local/bin

# YtSurf
curl -o ~/.local/bin/ytsurf https://raw.githubusercontent.com/kapral18/ytsurf/reduce-deps/ytsurf.sh
chmod +x ~/.local/bin/ytsurf


# amp
if ! command -v amp &>/dev/null; then
  curl -fsSL https://ampcode.com/install.sh | bash
fi
