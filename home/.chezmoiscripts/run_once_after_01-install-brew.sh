#!/usr/bin/env bash

set -eou pipefail

echo "--------------------------------"
echo "install bash: applying..."
echo "--------------------------------"
if [[ ! -x "$(command -v brew)" ]]; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
echo "-------------------------"
echo "install bash: done"
echo "-------------------------"

echo ""
