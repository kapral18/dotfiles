#!/usr/bin/env bash

set -euo pipefail

# YtSurf
mkdir -p ~/.local/bin
curl -o ~/.local/bin/ytsurf https://raw.githubusercontent.com/kapral18/ytsurf/reduce-deps/ytsurf.sh
chmod +x ~/.local/bin/ytsurf
